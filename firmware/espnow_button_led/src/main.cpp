#include <Arduino.h>

#include "board.h"
#include "button.h"
#include "espnow_hal.h"
#include "led.h"

namespace {
const uint8_t kMagic = 0x62;

// Press events are broadcast; the receiver toggles its LED for each new
// sequence number, so a lost packet never causes a stuck state.
struct __attribute__((packed)) PressEvent {
  uint8_t magic;
  uint8_t sequence;
};

Led led;
Button button;
uint8_t sequence = 0;
uint8_t last_remote_sequence = 0;
bool have_remote_sequence = false;

void printMac(const uint8_t* mac) {
  char buffer[18];
  snprintf(buffer, sizeof(buffer), "%02X:%02X:%02X:%02X:%02X:%02X",
           mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]);
  Serial.print(buffer);
}

void sendPress() {
  PressEvent event;
  event.magic = kMagic;
  event.sequence = ++sequence;
  espNow.sendBroadcast((const uint8_t*)&event, sizeof(event));
}

void handleMessage(const EspNowMessage& message) {
  if (message.length < sizeof(PressEvent)) {
    return;
  }
  PressEvent event;
  memcpy(&event, message.data, sizeof(event));
  if (event.magic != kMagic) {
    return;
  }
  if (have_remote_sequence && event.sequence == last_remote_sequence) {
    return;
  }
  last_remote_sequence = event.sequence;
  have_remote_sequence = true;

  led.toggle();
  Serial.print("remote press from ");
  printMac(message.mac);
  Serial.print(" -> LED ");
  Serial.println(led.state() ? "ON" : "OFF");
}
}  // namespace

void setup() {
  Serial.begin(115200);
  delay(200);
  Serial.println();
  Serial.println("ESP-NOW button/LED link test");

  led.begin(PIN_LED, LED_ACTIVE_LOW);
  button.begin(PIN_BUTTON, 30);

  if (!espNow.begin(ESPNOW_CHANNEL)) {
    Serial.println("ESP-NOW init failed, check the board and channel");
  }

  Serial.print("local MAC: ");
  printMac(espNow.ownMac());
  Serial.println();
  Serial.println("press the button here to toggle the LED on the other board");
}

void loop() {
  if (button.update()) {
    Serial.println(button.pressed() ? "local button pressed" : "local button released");
    if (button.pressed()) {
      sendPress();
    }
  }

  EspNowMessage message;
  while (espNow.poll(message, 0)) {
    handleMessage(message);
  }

  delay(2);
}
