"""Deterministic checks for Gemini-generated project plans."""

from __future__ import annotations

import re
from typing import Any

from app.schemas import (
    PlanQuestion,
    PlanRequest,
    PlanResponse,
    PlanScope,
    PlanSimulatorChecks,
)


class InvalidGeneratedPlan(ValueError):
    """Gemini returned a schema-valid plan outside the supported boundary."""


def _normalized(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()


def _user_explicitly_needs_part(
    canonical_name: str, request: PlanRequest, canonical_by_alias: dict[str, str]
) -> bool:
    user_text = _normalized(
        " ".join(filter(None, [request.project_description, request.constraints.notes]))
    )
    need_markers = (
        "need to buy", "need to get", "need to obtain", "need to purchase",
        "must buy", "must get", "have to buy", "do not have", "don t have",
        "do not own", "don t own",
    )
    aliases = [
        alias for alias, canonical in canonical_by_alias.items()
        if canonical == canonical_name
    ]
    for marker in need_markers:
        if marker not in user_text:
            continue
        tail = user_text.split(marker, 1)[1][:100]
        if any(alias and alias in tail for alias in aliases):
            return True
    return False


def _known_parts(reference: dict[str, Any]) -> tuple[dict[str, str], dict[str, set[str]]]:
    aliases = {
        "red_led": {"red led", "led", "single red led"},
        "series_resistor": {
            "series current limiting resistor", "current limiting resistor",
            "series resistor", "resistor",
        },
        "dc_source": {
            "dc voltage source", "positive dc source", "positive dc voltage source",
            "5 v dc source", "5v dc source", "5 v supply", "5v supply",
        },
    }
    canonical_by_alias: dict[str, str] = {}
    ratings_by_id: dict[str, set[str]] = {}
    components = reference["verified"]["components"]
    for component in components:
        component_id = component["id"]
        canonical = component["name"]
        facts = component.get("facts", {})
        aliases_for_part = set(aliases.get(component_id, set()))
        aliases_for_part.add(canonical)
        aliases_for_part.add(component_id.replace("_", " "))
        for alias in aliases_for_part:
            canonical_by_alias[_normalized(alias)] = canonical

        allowed: set[str] = set()
        if component_id == "red_led":
            allowed.add("red")
            allowed.add(_normalized("red LED color"))
            if "color" in facts:
                allowed.add(_normalized(f"color {facts['color']}"))
            if "model_forward_voltage_v" in facts:
                value = facts["model_forward_voltage_v"]
                allowed.update({
                    _normalized(f"model forward voltage {value} V"),
                    _normalized(f"forward voltage approximately {value} V"),
                    _normalized(f"forward voltage approx {value} V"),
                    _normalized(f"forward voltage about {value} V"),
                    _normalized(f"approximately {value:g} V forward voltage"),
                    _normalized(f"{value:g} V forward voltage"),
                })
            if "maximum_current_ma" in facts:
                value = facts["maximum_current_ma"]
                allowed.update({
                    _normalized(f"maximum current {value} mA"),
                    _normalized(f"{value} mA maximum"),
                    _normalized(f"max {value} mA"),
                })
            band = facts.get("safety_current_band_ma", {})
            if band:
                low = band["minimum_inclusive"]
                high = band["maximum_inclusive"]
                target = band["target_approximate"]
                allowed.update({
                    _normalized(f"safety band {low} to {high} mA; target approximately {target} mA"),
                    _normalized(f"{low}-{high} mA current band, target about {target} mA"),
                    _normalized(f"{low}-{high} mA; target approximately {target} mA"),
                })
        elif component_id == "series_resistor":
            if facts.get("required"):
                allowed.update({
                    "required",
                    _normalized("required series current-limiting resistor"),
                })
            if facts.get("zero_ohms_classification"):
                allowed.add(_normalized(f"zero ohms classified as {facts['zero_ohms_classification']}"))
            if facts.get("preferred_value_series"):
                allowed.update({
                    _normalized(f"{facts['preferred_value_series']} values preferred"),
                    _normalized(f"{facts['preferred_value_series']} preferred values"),
                    _normalized(f"preferred value series {facts['preferred_value_series']}"),
                })
            demo_values = facts.get("values_exercised_at_5v_ohm", [])
            if len(demo_values) == 2:
                allowed.update({
                    _normalized(f"{demo_values[0]} ohms and {demo_values[1]} ohms exercised in the 5 V demo"),
                    _normalized(f"{demo_values[0]} and {demo_values[1]} ohm values exercised at 5 V"),
                })
        elif component_id == "dc_source":
            if facts.get("polarity"):
                allowed.update({
                    _normalized(facts["polarity"]),
                    _normalized("positive DC to ground"),
                })
            if "voltage_used_in_verified_demo_v" in facts:
                voltage = facts["voltage_used_in_verified_demo_v"]
                allowed.update({
                    _normalized(f"{voltage} V used in the verified demo"),
                    _normalized(f"{voltage} V used in the demo"),
                })
        ratings_by_id[component_id] = allowed

    board_name = reference["verified"].get("board", {}).get("name")
    if board_name:
        canonical_by_alias[_normalized(board_name)] = board_name
        canonical_by_alias[_normalized(f"{board_name} board")] = board_name
        ratings_by_id["board"] = {
            _normalized(f"{board_name} accepted for the planning example only")
        }
    return canonical_by_alias, ratings_by_id


def _all_response_text(plan: PlanResponse) -> str:
    return plan.model_dump_json()


# Units recognized inside a single verified_ratings string, normalized the same
# way as the global electrical-value scan.
_RATING_VALUE_RE = re.compile(
    r"(?<![\w.])(\d+(?:\.\d+)?)\s*"
    r"(mAh|Ah|mA|A|mV|kΩ|V|Ω|ohms?|mW|kW|W|watts?|mm|cm|inches?|%)"
    r"(?=$|[^a-z])",
    re.IGNORECASE,
)


def _rating_values(rating: str) -> set[tuple[float, str]]:
    """Electrical (value, unit) pairs mentioned in a rating string."""
    found: set[tuple[float, str]] = set()
    for m in _RATING_VALUE_RE.finditer(rating):
        unit = m.group(2).casefold()
        unit = "ohm" if unit in {"ω", "ohm", "ohms"} else unit
        found.add((float(m.group(1)), unit))
    return found


def _approved_values(reference: dict[str, Any]) -> set[tuple[float, str]]:
    """(value, unit) electrical facts permitted by the verified reference."""
    approved: set[tuple[float, str]] = set()
    for component in reference["verified"]["components"]:
        facts = component.get("facts", {})
        if "model_forward_voltage_v" in facts:
            approved.add((float(facts["model_forward_voltage_v"]), "v"))
        if "maximum_current_ma" in facts:
            approved.add((float(facts["maximum_current_ma"]), "ma"))
        band = facts.get("safety_current_band_ma", {})
        for key in ("minimum_inclusive", "maximum_inclusive", "target_approximate"):
            if key in band:
                approved.add((float(band[key]), "ma"))
        if "zero_ohms_classification" in facts:
            approved.add((0.0, "ohm"))
        for resistance in facts.get("values_exercised_at_5v_ohm", []):
            approved.add((float(resistance), "ohm"))
        if "voltage_used_in_verified_demo_v" in facts:
            approved.add((float(facts["voltage_used_in_verified_demo_v"]), "v"))
    return approved


def _rating_is_acceptable(
    rating: str, approved_ratings: set[str], approved_values: set[tuple[float, str]]
) -> bool:
    """Accept a verified_ratings entry on value, not exact phrasing.

    A rating is accepted when it matches a known phrasing, OR it is a plain
    descriptive fact whose electrical numbers (if any) are all approved values
    from the trusted reference. A rating that asserts an unbacked
    verification/capability claim (e.g. "current sourcing limit verified") is
    rejected even when it contains no number, because the model must not invent
    a verification the reference does not state. The global electrical-value
    scan is a second net against unverified numbers.
    """
    if _normalized(rating) in approved_ratings:
        return True
    # Reject ratings that assert a verification or capability the reference
    # does not establish, rather than merely describing a known fact.
    if re.search(
        r"\b(?:capable|capability|sourcing|sinking|can (?:supply|source|provide|drive))\b",
        rating,
        re.IGNORECASE,
    ):
        return False
    values = _rating_values(rating)
    if not values:
        return True
    return values.issubset(approved_values)


def _claim_segments(plan: PlanResponse) -> list[str]:
    """Affirmative plan text that could assert an unsupported fact.

    Forbidden-claim patterns run against these segments one at a time, so a wide
    ``.{0,N}`` gap cannot stitch words across unrelated fields. Disclaimer-only
    fields (not_included, cannot_verify, limitations, questions) are excluded on
    purpose: they exist to state what is NOT supported, so a "capability"-shaped
    match there is a disclaimer, not a claim.
    """
    segments: list[str] = [plan.project_summary]
    segments += plan.scope.included
    segments += plan.assumptions
    segments += plan.safety_and_common_problems
    segments += plan.simulator_checks.can_verify
    for part in plan.parts:
        segments += [part.name, part.purpose, *part.notes]
        segments += part.verified_ratings
    for stage in plan.stages:
        segments += [stage.title, stage.goal, stage.learn_or_observe, stage.check_before_continuing]
    return [s for s in segments if s]


def _ensure_guidance_limits(plan: PlanResponse, reference: dict[str, Any]) -> None:
    segments = _claim_segments(plan)
    forbidden_patterns = {
        "pin number or pin mapping": r"\b(?:pin\s*(?:number\s*)?#?\s*\d+|[AD]\d{1,2})\b",
        "Arduino code": r"\b(?:pinMode|digitalWrite|analogWrite)\s*\(|\bvoid\s+(?:setup|loop)\s*\(|#include\s*<",
        "wire-by-wire connection directions": (
            r"\b(?:connect|wire|attach)\b.{0,100}\b"
            r"(?:pin\s*\d+|D\d{1,2}|anode|cathode|5\s*V|GND|ground)\b"
        ),
        "price or purchase cost": r"(?:\$\s*\d|\bUSD\s*\d)",
        "specific part number": r"\b(?:part number|model number|SKU)\s*[:#]\s*[A-Z0-9-]+",
    }
    for reason, pattern in forbidden_patterns.items():
      for segment in segments:
        for match in re.finditer(pattern, segment, re.IGNORECASE):
            prefix = segment[max(0, match.start() - 60):match.start()]
            suffix = segment[match.end():match.end() + 80]
            allow_negated_warning = reason == "wire-by-wire connection directions"
            _neg = (
                r"\b(?:not|no|never|cannot|can'?t|don'?t|doesn'?t|does not|do not|"
                r"unknown|unconfirmed|unverified|avoid|unsupported|dangerous|danger|"
                r"required|must|whether|if|needs? confirmation|cannot verify|"
                r"can'?t verify|not verified|is unknown|are unknown)\b"
            )
            # A warning can carry the negation cue BEFORE the match ("do not
            # drive the LED directly") or AFTER it ("...without a resistor is
            # not supported / is dangerous / is classified as danger").
            if allow_negated_warning and (
                re.search(_neg + r"(?:\W+\w+){0,4}\W*$", prefix, re.IGNORECASE)
                or re.search(r"^(?:\W*\w+){0,8}\W*" + _neg, suffix, re.IGNORECASE)
            ):
                continue
            raise InvalidGeneratedPlan(f"Plan includes unsupported {reason}.")

    # Permit numeric electrical claims only when their value and unit appear
    # in the trusted reference. This also checks notes and stages.
    approved_values = _approved_values(reference)

    electrical_value = re.compile(
        r"(?<![\w.])(\d+(?:\.\d+)?)\s*"
        r"(mAh|Ah|mA|A|mV|kΩ|V|Ω|ohms?|mW|kW|W|watts?|mm|cm|inches?|%)"
        r"(?=$|[^a-z])",
        re.IGNORECASE,
    )
    full_text = _all_response_text(plan)
    for match in electrical_value.finditer(full_text):
        value = float(match.group(1))
        unit = match.group(2).casefold()
        unit = "ohm" if unit in {"ω", "ohm", "ohms"} else unit
        if (value, unit) not in approved_values:
            raise InvalidGeneratedPlan(
                f"Plan includes an electrical value absent from the verified reference: {match.group(0)}."
            )


def _request_blockers(request: PlanRequest, reference: dict[str, Any]) -> list[tuple[str, str]]:
    blockers: list[tuple[str, str]] = []
    description = _normalized(request.project_description)
    unsupported_led_terms = (
        "color changing", "colour changing", "rgb", "ws2812", "neopixel",
        "addressable led", "multi color", "multicolor", "multi colour", "multicolour",
        "change color", "change the color", "different colors", "cycle colors",
        "cycling colors", "change colour", "change the colour", "cycle colours",
        "two leds", "multiple leds", "several leds", "three leds", "more than one led",
    )
    if any(term in description for term in unsupported_led_terms):
        blockers.append((
            "single_red_led_confirmation",
            "The verified v1 project supports one red LED, which cannot change color. "
            "Would you like to continue with the single-red-LED version?",
        ))
    elif re.search(r"\bleds?\b", description) and not re.search(r"\bred\b", description):
        blockers.append((
            "led_type_confirmation",
            "The verified v1 reference covers one red LED only. Is a single red LED acceptable for this project?",
        ))

    unsupported_requests = (
        (
            "detail_level_confirmation",
            r"\b(?:which pin|pin map|pin assignment|pin number|pin\s*\d+|[AD]\d{1,2}|"
            r"wire by wire|step by step|exact steps|exact wiring|how to wire|how to connect|"
            r"wiring instructions|pwm|digital output|firmware|sketch|code|"
            r"wiring diagram|exact wiring|complete (?:arduino )?(?:sketch|program|code)|"
            r"write (?:the )?(?:arduino )?(?:sketch|program|code))\b",
            "V1 provides broad build stages, not pin assignments, wire-by-wire instructions, or complete Arduino code. Would that broader guidance still help?",
        ),
        (
            "extra_components_confirmation",
            r"\b(?:transistors?|drivers?|level shifters?|level shifting)\b",
            "The verified v1 circuit does not include transistors, drivers, or level shifting. Would you like to continue with the simpler supported circuit?",
        ),
        (
            "power_or_layout_confirmation",
            r"\b(?:battery powered|battery power|use a battery|battery operated|"
            r"usb powered|power from usb|usb supply|breadboard layout|breadboard placement|"
            r"where to place .*breadboard)\b",
            "V1 only uses the verified positive DC source and ground example; battery, USB, and breadboard advice are outside its verified scope. Would you like to continue without those details?",
        ),
        (
            "purchase_details_confirmation",
            r"\b(?:prices?|costs?|where to buy|shopping list|part numbers?|purchase links?)\b",
            "V1 can name supported component types but has no approved source for prices, part numbers, or shopping links. Would a no-price parts list still help?",
        ),
    )
    for question_id, pattern, question_text in unsupported_requests:
        if re.search(pattern, request.project_description, re.IGNORECASE):
            blockers.append((question_id, question_text))

    board_name = reference.get("project_scope", {}).get("board")
    requested_board = request.board_model
    if requested_board and board_name and _normalized(requested_board) != _normalized(board_name):
        blockers.append((
            "supported_board_confirmation",
            f"The only board named in the verified v1 scope is {board_name}. "
            "Would you like a plan limited to that board?",
        ))
    elif request.constraints.must_use_board is True and not requested_board:
        blockers.append((
            "board_model_confirmation",
            "Which board must this project use? The first-version planning scope names Arduino Uno R3 only.",
        ))
    return blockers


def confirmation_response_for_request(
    request: PlanRequest, reference: dict[str, Any]
) -> PlanResponse | None:
    """Return a deterministic clarification instead of an unsupported plan."""
    blockers = _request_blockers(request, reference)
    if not blockers:
        return None

    questions = [
        PlanQuestion(
            id=question_id,
            question=question_text,
            why_it_matters="This detail is not established in the verified v1 planning scope; confirming it prevents the planner from guessing.",
        )
        for question_id, question_text in blockers
    ]
    wants_color_change = any(
        question_id == "single_red_led_confirmation"
        for question_id, _ in blockers
    )
    requested_board = request.board_model
    supported_board = reference["project_scope"]["board"]
    summary_parts: list[str] = []
    included: list[str] = []
    excluded: list[str] = []
    cannot_verify: list[str] = []

    if wants_color_change:
        summary_parts.append(
            "V1 supports one red LED, which cannot change color. CircuitGuard can plan that simpler project if you accept the change."
        )
        included.append(
            "Conditional option: one red LED, one current-limiting resistor, a positive DC source, and ground."
        )
        excluded.append("The requested color-changing effect and all multi-color or addressable LEDs.")
        cannot_verify.append("A color-changing effect or a multi-color LED.")

    generic_blockers = [
        (question_id, question_text)
        for question_id, question_text in blockers
        if question_id not in {
            "single_red_led_confirmation",
            "supported_board_confirmation",
            "board_model_confirmation",
        }
    ]
    if generic_blockers:
        summary_parts.append(
            "The request includes details outside the verified v1 boundary. CircuitGuard can offer broad guidance for the supported single-red-LED circuit after you confirm that scope."
        )
        included.append(
            "Conditional option: one red LED, one current-limiting resistor, a positive DC source, and ground."
        )
        excluded.extend([
            "Exact pin assignments, wire-by-wire directions, complete code, and unsupported parts or power details.",
            "Prices, part numbers, and shopping links.",
        ])
        cannot_verify.append(
            "Details such as pin behavior, physical wiring, unsupported power sources, or current product prices."
        )

    if requested_board and _normalized(requested_board) != _normalized(supported_board):
        summary_parts.append(
            f"The requested board is not the board named in the verified v1 scope. This planner can only offer a plan for {supported_board} after you confirm that choice."
        )
        excluded.append("Use of the requested board as verified for this plan.")
        cannot_verify.append("Electrical behavior or compatibility of the requested board.")
    elif request.constraints.must_use_board is True and not requested_board:
        summary_parts.append(
            f"The board is not specified. The only board named in the verified v1 scope is {supported_board}."
        )
        excluded.append("Any board-specific plan until the board model is confirmed.")
        cannot_verify.append("Board-specific behavior while the board model is unknown.")

    simulator = reference["verified"].get("simulator", {})
    can_verify = []
    if wants_color_change and simulator.get("supported_measurement"):
        can_verify.append(
            "If you accept the single-red-LED option, PhysBox can report simulated current through that modeled circuit."
        )
    limitations = [
        "This is a clarification, not a completed project plan.",
        "Simulation does not verify the physical build or Arduino Uno R3 electrical limits.",
        "No prices, part numbers, pin assignments, wiring diagram, or firmware are provided.",
    ]
    return PlanResponse(
        status="needs_confirmation",
        project_summary=" ".join(summary_parts),
        scope=PlanScope(included=included, not_included=excluded),
        questions=questions,
        assumptions=[],
        parts=[],
        stages=[],
        safety_and_common_problems=[],
        simulator_checks=PlanSimulatorChecks(
            can_verify=can_verify,
            cannot_verify=cannot_verify,
        ),
        limitations=limitations,
    )


def validate_generated_plan(
    request: PlanRequest, plan: PlanResponse, reference: dict[str, Any]
) -> PlanResponse:
    """Reject unsupported content and correct status/ownership from trusted input."""
    _ensure_guidance_limits(plan, reference)
    canonical_by_alias, ratings_by_id = _known_parts(reference)
    component_id_by_canonical = {
        component["name"]: component["id"]
        for component in reference["verified"]["components"]
    }
    component_id_by_canonical[reference["verified"]["board"]["name"]] = "board"

    owned = {_normalized(item.name) for item in request.parts_owned}
    owned_canonical = {
        canonical_by_alias.get(name, name)
        for name in owned
    }
    required_canonical_names = {
        component["name"]
        for component in reference["verified"]["components"]
        if component.get("facts", {}).get("required", True)
    }
    reference_values = _approved_values(reference)
    present: set[str] = set()
    for part in plan.parts:
        normalized_name = _normalized(part.name)
        canonical = canonical_by_alias.get(normalized_name)
        if canonical is None:
            raise InvalidGeneratedPlan(f"Plan contains an unverified part: {part.name}.")
        part.name = canonical
        present.add(canonical)
        component_id = component_id_by_canonical[canonical]

        approved_ratings = ratings_by_id.get(component_id, set())
        for rating in part.verified_ratings:
            # Value-based acceptance: the rating is fine if it uses a known
            # phrasing, is plain descriptive text, or only cites numbers that
            # are approved in the verified reference. This keeps the fast model
            # usable (it phrases facts freely) while still blocking unverified
            # electrical values here and in the global electrical-value scan.
            if not _rating_is_acceptable(rating, approved_ratings, reference_values):
                raise InvalidGeneratedPlan(
                    f"Plan contains an unverified rating for {canonical}: {rating}."
                )

        if component_id != "board":
            component = next(
                item for item in reference["verified"]["components"]
                if item["id"] == component_id
            )
            expected_quantity = component.get("typical_quantity", 1)
            if part.quantity is not None and part.quantity != expected_quantity:
                raise InvalidGeneratedPlan(
                    f"Plan exceeds the verified quantity for {canonical}."
                )
            part.quantity = expected_quantity

        # The request has an owned-parts list but no purchase-intent field.
        # Therefore true/false claims not grounded in that list are not kept.
        if canonical in owned_canonical:
            part.obtain = False
        elif _user_explicitly_needs_part(canonical, request, canonical_by_alias):
            part.obtain = True
        elif part.obtain is not None:
            part.obtain = None

    blockers = _request_blockers(request, reference)
    if plan.status == "ready" and not blockers and not required_canonical_names.issubset(present):
        missing = sorted(required_canonical_names - present)
        raise InvalidGeneratedPlan(
            "A ready plan is missing required supported parts: " + ", ".join(missing)
        )

    if blockers:
        plan.status = "needs_confirmation"
        questions_by_id = {question.id: question for question in plan.questions}
        for question_id, question_text in blockers:
            why = "The requested feature or board is outside the verified v1 planning scope."
            if question_id in questions_by_id:
                questions_by_id[question_id].question = question_text
                questions_by_id[question_id].why_it_matters = why
            else:
                plan.questions.append(PlanQuestion(
                    id=question_id,
                    question=question_text,
                    why_it_matters=why,
                ))
        not_included = plan.scope.not_included
        excluded_scope = "The requested feature or board is outside the verified v1 scope."
        if excluded_scope not in not_included:
            not_included.append(excluded_scope)
        if "User confirmation is required before treating this plan as complete." not in plan.limitations:
            plan.limitations.append("User confirmation is required before treating this plan as complete.")
    elif plan.status == "needs_confirmation" and not plan.questions:
        raise InvalidGeneratedPlan(
            "A plan that needs confirmation must include at least one question."
        )

    # Unknown physical ratings must remain visible whenever their parts appear.
    for part in plan.parts:
        part_id = component_id_by_canonical[part.name]
        if part_id == "board":
            note = (
                "Needs confirmation: the board name is accepted for planning only; "
                "its electrical limits have not been established by this reference."
            )
            if note not in part.notes:
                part.notes.append(note)
        elif part_id == "red_led":
            note = (
                "Needs confirmation: the physical LED part number and its actual "
                "forward voltage have not been provided."
            )
            if note not in part.notes:
                part.notes.append(note)
        elif part_id == "series_resistor":
            for note in (
                "Needs confirmation: the physical resistor wattage rating has not been provided.",
                "Needs confirmation: the exact resistance depends on the confirmed supply and the user's actual LED.",
            ):
                if note not in part.notes:
                    part.notes.append(note)
        elif part_id == "dc_source":
            note = (
                "Needs confirmation: the simulation does not verify whether an "
                "Arduino Uno R3 supply pin can provide the planned current."
            )
            if note not in part.notes:
                part.notes.append(note)

    board_limit_note = (
        "Needs confirmation: Arduino Uno R3 pin current limits and 5 V regulator "
        "capability are unknown; the circuit simulation does not verify them."
    )
    if board_limit_note not in plan.limitations:
        plan.limitations.append(board_limit_note)

    return plan
