"""Application-owned connection to the local PhysBox MCP server.

The coding assistant's MCP connection is separate from the FastAPI process.
This client launches its own ``physbox-mcp --stdio`` subprocess so backend
requests can reach the same local PhysBox relay and open Volt browser tab.
"""

from __future__ import annotations

import logging
import asyncio
from typing import Any

from mcp import Client, StdioServerParameters

logger = logging.getLogger(__name__)


class PhysBoxConnectionError(RuntimeError):
    """Raised when the backend cannot communicate with PhysBox MCP."""


def _jsonable(value: Any) -> Any:
    """Convert MCP SDK models and nested values into JSON-compatible data."""
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json", exclude_none=True)
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


class PhysBoxMCPClient:
    """Long-lived MCP client owned by the FastAPI application."""

    def __init__(self) -> None:
        self._context: Any | None = None
        self._client: Any | None = None
        self._entered = False
        self._tools: list[Any] = []
        self.last_error: str | None = None

    @property
    def connected(self) -> bool:
        return self._client is not None

    @property
    def tool_names(self) -> list[str]:
        return [tool.name for tool in self._tools]

    def tool_schemas(self, names: set[str] | None = None) -> list[dict[str, Any]]:
        """Return JSON schemas for selected advertised tools."""
        selected = self._tools if names is None else [
            tool for tool in self._tools if tool.name in names
        ]
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "input_schema": _jsonable(tool.input_schema),
            }
            for tool in selected
        ]

    async def start(self) -> None:
        """Launch the PhysBox MCP subprocess and discover its tools."""
        if self.connected:
            return

        # Imported here to avoid the config -> simulator -> MCP client cycle.
        from app.config import settings

        # Record what we're about to launch so any failure names the command.
        launch = f"{settings.physbox_mcp_command} {' '.join(settings.physbox_mcp_args)}"
        try:
            self._context = Client(
                StdioServerParameters(
                    command=settings.physbox_mcp_command,
                    args=settings.physbox_mcp_args,
                )
            )
            self._client = await asyncio.wait_for(self._context.__aenter__(), timeout=30)
            self._entered = True
            page = await asyncio.wait_for(self._client.list_tools(), timeout=30)
            self._tools = list(page.tools)
            while page.next_cursor:
                page = await asyncio.wait_for(
                    self._client.list_tools(cursor=page.next_cursor), timeout=30
                )
                self._tools.extend(page.tools)
            self.last_error = None
            logger.info("Connected to PhysBox MCP; discovered %d tools.", len(self._tools))
        except Exception as exc:  # noqa: BLE001 - startup should not disable mock mode
            self.last_error = self._describe_startup_error(exc, launch)
            # Full traceback at WARNING so the real cause is never hidden.
            logger.warning(
                "Could not connect to PhysBox MCP (command: %s): %s",
                launch, self.last_error, exc_info=True,
            )
            await self.stop()

    @staticmethod
    def _describe_startup_error(exc: BaseException, launch: str) -> str:
        """Build a non-empty, actionable error string for a startup failure.

        Some MCP/stdio failures raise exceptions whose str() is empty or whose
        type alone is uninformative (e.g. a bare ExceptionGroup or a subprocess
        that exits instantly). Never return None/empty: always say something
        the next person can act on.
        """
        parts: list[str] = []

        def _collect(e: BaseException) -> None:
            name = type(e).__name__
            text = str(e).strip()
            parts.append(f"{name}: {text}" if text else name)
            # Unwrap ExceptionGroup (Python 3.11+) so the real cause shows.
            for sub in getattr(e, "exceptions", ()) or ():
                _collect(sub)
            cause = e.__cause__ or e.__context__
            if cause is not None and cause is not e:
                _collect(cause)

        _collect(exc)
        detail = " <- ".join(dict.fromkeys(parts))  # de-dup, keep order
        if not detail:
            detail = type(exc).__name__ or "unknown error"

        return (
            f"{detail} | launch command: {launch}. "
            "Check that physbox-mcp is installed in this environment, the "
            "command/python above is correct, and Volt is open with the "
            "PhysBox relay running."
        )

    async def stop(self) -> None:
        """Close the MCP session and its subprocess."""
        context, self._context = self._context, None
        self._client = None
        self._tools = []
        was_entered, self._entered = self._entered, False
        if context is not None and was_entered:
            try:
                await asyncio.wait_for(context.__aexit__(None, None, None), timeout=3)
            except Exception as exc:  # noqa: BLE001 - shutdown must continue
                logger.warning("Error while closing PhysBox MCP: %s", exc)

    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> Any:
        """Call a discovered tool, refusing names not advertised by the server."""
        if self._client is None:
            detail = self.last_error or "The PhysBox MCP client is not connected."
            raise PhysBoxConnectionError(detail)
        if name not in self.tool_names:
            raise PhysBoxConnectionError(f"PhysBox MCP did not advertise tool '{name}'.")

        try:
            result = await self._client.call_tool(name, arguments or {})
        except Exception as exc:  # noqa: BLE001 - normalize MCP transport errors
            raise PhysBoxConnectionError(
                f"PhysBox MCP tool '{name}' failed: {type(exc).__name__}: {exc}"
            ) from exc

        if getattr(result, "is_error", getattr(result, "isError", False)):
            raise PhysBoxConnectionError(
                f"PhysBox MCP tool '{name}' returned an error: {_jsonable(result)}"
            )
        return _jsonable(result)

    async def status(self, *, check_volt: bool = False) -> dict[str, Any]:
        """Report the MCP connection and optionally make a read-only Volt call."""
        data: dict[str, Any] = {
            "connected": self.connected,
            "tool_count": len(self._tools),
            "circuit_tools": [name for name in self.tool_names if name.startswith("circuit_")],
        }
        if not self.connected:
            data["error"] = self.last_error or "The PhysBox MCP client is not connected."
            return data

        if check_volt:
            if "circuit_get_state" not in self.tool_names:
                data["volt_reachable"] = False
                data["error"] = "PhysBox MCP did not advertise circuit_get_state."
            else:
                try:
                    state = await self.call_tool("circuit_get_state")
                    data["volt_reachable"] = True
                    data["state_result"] = state
                except PhysBoxConnectionError as exc:
                    data["volt_reachable"] = False
                    data["error"] = str(exc)
        return data
