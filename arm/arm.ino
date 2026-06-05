#include <Wire.h>
#include <Adafruit_PWMServoDriver.h>
#include <WiFi.h>
#include <PubSubClient.h>

// 1. CẤU HÌNH MẠNG & CLOUD
const char* ssid = "iQOO Z9 Turbo";
const char* password = "12121212";

const char* mqtt_server = "10.149.116.175";
const int mqtt_port = 1883;
const char* mqtt_topic = "vku/artemis/robot_arm/control";

WiFiClient espClient;
PubSubClient client(espClient);

// 2. CẤU HÌNH PHẦN CỨNG (PCA9685)
Adafruit_PWMServoDriver pwm = Adafruit_PWMServoDriver();

// Kênh vật lý tương ứng với mảng Home
const int KENH_SERVO[6] = { 0, 1, 2, 3, 8, 12 };
int goc_hien_tai[6] = { 0, 100, 90, 0, 0, 170 };

// Hàm quy đổi góc 0-180 sang xung PCA9685
int angleToPulse(int ang) {
  ang = constrain(ang, 0, 180);
  return map(ang, 0, 180, 150, 600);
}

// 3. HÀM XỬ LÝ DỮ LIỆU TỪ CLOUD (CALLBACK)
void mqttCallback(char* topic, byte* payload, unsigned int length) {
  char msg[length + 1];
  for (int i = 0; i < length; i++) {
    msg[i] = (char)payload[i];
  }
  msg[length] = '\0';

  // Kiểm tra gói tin nguyên vẹn
  if (msg[0] == '<' && msg[length - 1] == '>') {
    int de, vai, khuyu, co, xoay, kep;
    int parsed = sscanf(msg, "<%d,%d,%d,%d,%d,%d>", &de, &vai, &khuyu, &co, &xoay, &kep);

    if (parsed == 6) {
      pwm.setPWM(KENH_SERVO[0], 0, angleToPulse(de));
      pwm.setPWM(KENH_SERVO[1], 0, angleToPulse(vai));
      pwm.setPWM(KENH_SERVO[2], 0, angleToPulse(khuyu));
      pwm.setPWM(KENH_SERVO[3], 0, angleToPulse(co));
      pwm.setPWM(KENH_SERVO[4], 0, angleToPulse(xoay));
      pwm.setPWM(KENH_SERVO[5], 0, angleToPulse(kep));

      Serial.printf("[KINEMATICS] Trục chạy an toàn -> Đế:%d Vai:%d Khuỷu:%d Cổ:%d Xoay:%d Kẹp:%d\n", de, vai, khuyu, co, xoay, kep);
    } else {
      Serial.println("[LỖI DATA] Gói tin không đủ 6 thông số.");
    }
  }
}

// 4. HÀM DUY TRÌ KẾT NỐI (AUTO RECONNECT)
void reconnect() {
  while (!client.connected()) {
    Serial.print("[MQTT] Đang kết nối tới Broker... ");
    String clientId = "Artemis-ESP32-" + String(random(0xffff), HEX);

    if (client.connect(clientId.c_str())) {
      Serial.println("KẾT NỐI THÀNH CÔNG!");
      client.subscribe(mqtt_topic);
      Serial.printf("[MQTT] Đã đăng ký lắng nghe kênh: %s\n", mqtt_topic);
    } else {
      Serial.print("THẤT BẠI. Mã lỗi rc=");
      Serial.print(client.state());
      Serial.println(" -> Thử lại sau 5 giây.");
      delay(5000);
    }
  }
}

void setup() {
  Serial.begin(115200);
  Serial.println("\n=============================================");
  Serial.println("🚀 ARTEMIS - CLOUD KINEMATIC SLAVE 🚀");
  Serial.println("=============================================");

  // Khởi động Servo và ép vào vị trí Home ngay khi bật nguồn
  pwm.begin();
  pwm.setPWMFreq(50);
  for (int i = 0; i < 6; i++) {
    pwm.setPWM(KENH_SERVO[i], 0, angleToPulse(goc_hien_tai[i]));
  }
  Serial.println("[HỆ THỐNG] Servo đã vào vị trí Home.");

  // Kết nối WiFi
  Serial.printf("[WIFI] Đang kết nối tới %s ", ssid);
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\n[WIFI] Đã cấp IP: " + WiFi.localIP().toString());

  // Cấu hình MQTT
  client.setServer(mqtt_server, mqtt_port);
  client.setCallback(mqttCallback);
}

void loop() {
  if (!client.connected()) {
    reconnect();
  }
  client.loop();
}