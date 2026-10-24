// CircuitGuard Uno sketch. Serial 9600 baud, one command per line.
//
//   LED circuit      pin 8 -> 220 ohm resistor -> LED anode; cathode -> GND
//   LED with switch  same LED on pin 8, plus a switch/button between pin 2 and GND
//   RGB LED          pins 9 (R), 10 (G), 11 (B) -> 220 ohm each -> common-cathode
//                    RGB LED; common cathode -> GND
//
// Commands (each is echoed back as the acknowledgement):
//   LED_ON, LED_OFF   drive pin 8 (also stops switch-follow mode)
//   MODE_SWITCH       pin 8 LED follows the switch on pin 2 (closed = LED on)
//   SWITCH?           replies SWITCH_CLOSED or SWITCH_OPEN
//   RGB r g b         each 0 or 1, e.g. "RGB 1 0 1"
const int LED_PIN = 8;
const int SWITCH_PIN = 2;
const int RGB_PINS[3] = {9, 10, 11};
bool followSwitch = false;

bool switchClosed() { return digitalRead(SWITCH_PIN) == LOW; }  // INPUT_PULLUP: pressed = LOW

void setup() {
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);
  pinMode(SWITCH_PIN, INPUT_PULLUP);
  for (int i = 0; i < 3; i++) {
    pinMode(RGB_PINS[i], OUTPUT);
    digitalWrite(RGB_PINS[i], LOW);
  }
  Serial.begin(9600);
  Serial.println("READY");
}

void loop() {
  if (followSwitch) {
    digitalWrite(LED_PIN, switchClosed() ? HIGH : LOW);
  }
  if (Serial.available() > 0) {
    String command = Serial.readStringUntil('\n');
    command.trim();
    int r, g, b;
    if (command == "LED_ON") {
      followSwitch = false;
      digitalWrite(LED_PIN, HIGH);
      Serial.println("LED_ON");
    } else if (command == "LED_OFF") {
      followSwitch = false;
      digitalWrite(LED_PIN, LOW);
      Serial.println("LED_OFF");
    } else if (command == "MODE_SWITCH") {
      followSwitch = true;
      Serial.println("MODE_SWITCH");
    } else if (command == "SWITCH?") {
      Serial.println(switchClosed() ? "SWITCH_CLOSED" : "SWITCH_OPEN");
    } else if (sscanf(command.c_str(), "RGB %d %d %d", &r, &g, &b) == 3) {
      digitalWrite(RGB_PINS[0], r ? HIGH : LOW);
      digitalWrite(RGB_PINS[1], g ? HIGH : LOW);
      digitalWrite(RGB_PINS[2], b ? HIGH : LOW);
      Serial.println(String("RGB ") + (r ? 1 : 0) + " " + (g ? 1 : 0) + " " + (b ? 1 : 0));
    } else {
      Serial.println("ERROR: Unknown command");
    }
  }
}
