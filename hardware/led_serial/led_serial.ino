// Uno pin 8 -> 220 ohm resistor -> red LED anode; cathode -> GND.
const int LED_PIN = 8;

void setup() {
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);
  Serial.begin(9600);
  Serial.println("READY");
}

void loop() {
  if (Serial.available() > 0) {
    String command = Serial.readStringUntil('\n');
    command.trim();
    if (command == "LED_ON") {
      digitalWrite(LED_PIN, HIGH);
      Serial.println("LED_ON");
    } else if (command == "LED_OFF") {
      digitalWrite(LED_PIN, LOW);
      Serial.println("LED_OFF");
    } else {
      Serial.println("ERROR: Unknown command");
    }
  }
}
