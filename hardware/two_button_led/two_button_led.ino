// D5 -> 220 ohm -> LED anode; cathode -> GND.
// ON button: D9 to GND. OFF button: D8 to GND. Internal pullups enabled.
const byte LED_PIN = 5, ON_PIN = 9, OFF_PIN = 8;
bool ledOn = false;
bool rawOn = HIGH, rawOff = HIGH, stableOn = HIGH, stableOff = HIGH;
unsigned long changedOn = 0, changedOff = 0;
char input[32];
byte used = 0;
bool overflowed = false;

void setLed(bool value) {
  ledOn = value;
  digitalWrite(LED_PIN, ledOn ? HIGH : LOW);
}

void reportState() {
  Serial.print("STATE {\"state\":\"");
  Serial.print(ledOn ? "on" : "off");
  Serial.print("\",\"button_on_pressed\":");
  Serial.print(stableOn == LOW ? "true" : "false");
  Serial.print(",\"button_off_pressed\":");
  Serial.print(stableOff == LOW ? "true" : "false");
  Serial.println(",\"led_pin\":5,\"on_pin\":9,\"off_pin\":8}");
}

void command(const char* text) {
  if (strcmp(text, "LED_ON") == 0) {
    setLed(true); Serial.println("LED_ON");
  } else if (strcmp(text, "LED_OFF") == 0) {
    setLed(false); Serial.println("LED_OFF");
  } else if (strcmp(text, "STATE") == 0) {
    reportState();
  } else if (strcmp(text, "PING") == 0) {
    Serial.println("PONG");
  } else {
    Serial.println("ERROR: Unknown command");
  }
}

void setup() {
  pinMode(LED_PIN, OUTPUT); setLed(false);
  pinMode(ON_PIN, INPUT_PULLUP);
  pinMode(OFF_PIN, INPUT_PULLUP);
  Serial.begin(9600);
  Serial.println("READY");
}

void loop() {
  unsigned long now = millis();
  bool on = digitalRead(ON_PIN), off = digitalRead(OFF_PIN);
  if (on != rawOn) { rawOn = on; changedOn = now; }
  if (off != rawOff) { rawOff = off; changedOff = now; }
  bool onEdge = false, offEdge = false;
  if (now - changedOn >= 30 && stableOn != rawOn) {
    stableOn = rawOn; onEdge = stableOn == LOW;
  }
  if (now - changedOff >= 30 && stableOff != rawOff) {
    stableOff = rawOff; offEdge = stableOff == LOW;
  }
  if (stableOff == LOW && (onEdge || offEdge)) setLed(false);
  else if (onEdge) setLed(true);

  // No unsolicited serial messages: replies correspond to one backend request.
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\r') continue;
    if (c == '\n') {
      if (overflowed) Serial.println("ERROR: Command too long");
      else { input[used] = '\0'; command(input); }
      used = 0; overflowed = false;
    } else if (used < sizeof(input) - 1 && !overflowed) input[used++] = c;
    else overflowed = true;
  }
}
