#include <Wire.h>
#include <Adafruit_PWMServoDriver.h>

// Khởi tạo PCA9685
Adafruit_PWMServoDriver pwm = Adafruit_PWMServoDriver();

// Kênh cắm vật lý trên PCA9685 (Đế, Vai, Khuỷu, Cổ, Xoay, Kẹp)
const int KENH_SERVO[6] = {0, 1, 2, 3, 8, 12};

// Vị trí Home (Nghỉ) ban đầu
int goc_hien_tai[6] = {90, 100, 90, 90, 90, 170};

// Bộ đệm đọc UART (chống tràn RAM)
const byte MAX_BUFFER_SIZE = 64;
char dataBuffer[MAX_BUFFER_SIZE];
byte dataIndex = 0;
bool newDataReady = false;

// Hàm quy đổi góc 0-180 sang xung PWM cho PCA9685
int angleToPulse(int ang) {
  ang = constrain(ang, 0, 180);
  return map(ang, 0, 180, 150, 600); 
}

void setup() {
  // 1. Giao tiếp máy tính (để debug)
  Serial.begin(115200);
  
  // 2. Giao tiếp Raspberry Pi (UART2: RX=16, TX=17)
  Serial2.begin(115200, SERIAL_8N1, 16, 17);
  
  // 3. Khởi tạo PWM
  pwm.begin();
  pwm.setPWMFreq(50); // Servo tương tự chạy ở tần số 50Hz
  
  Serial.println("=============================================");
  Serial.println("🚀 ARTEMIS - REAL-TIME KINEMATIC SLAVE 🚀");
  Serial.println("=============================================");
  Serial.println("[HỆ THỐNG] Đang đưa robot về vị trí Home...");

  // Ép góc Home
  for(int i = 0; i < 6; i++) {
    pwm.setPWM(KENH_SERVO[i], 0, angleToPulse(goc_hien_tai[i]));
  }
  
  Serial.println("[HỆ THỐNG] Đã sẵn sàng nhận luồng dữ liệu liên tục!");
}

void loop() {
  // Lắng nghe dữ liệu UART ở chế độ Non-blocking (Không làm khựng hệ thống)
  nhanDuLieuUART();

  // Khi nhận đủ 1 bản tin (kết thúc bằng \n), tiến hành xử lý ngay
  if (newDataReady) {
    xuLyBanTin(dataBuffer);
    
    // Reset buffer để đón bản tin tiếp theo
    dataIndex = 0;
    newDataReady = false;
  }
}

// ==========================================
// HÀM NHẬN DỮ LIỆU TỐC ĐỘ CAO
// ==========================================
void nhanDuLieuUART() {
  while (Serial2.available() > 0 && !newDataReady) {
    char rc = Serial2.read();
    
    // Ký tự ngắt dòng báo hiệu hết 1 chuỗi lệnh
    if (rc == '\n') {
      dataBuffer[dataIndex] = '\0'; // Chốt chuỗi
      newDataReady = true;
    } 
    else {
      dataBuffer[dataIndex] = rc;
      dataIndex++;
      if (dataIndex >= MAX_BUFFER_SIZE) {
        dataIndex = MAX_BUFFER_SIZE - 1; // Chống tràn bộ đệm
      }
    }
  }
}

// ==========================================
// HÀM BÓC TÁCH & ĐIỀU KHIỂN
// ==========================================
void xuLyBanTin(char* banTin) {
  // Kiểm tra tính toàn vẹn của gói tin: phải bắt đầu bằng '<' và kết thúc bằng '>'
  if (banTin[0] == '<' && banTin[strlen(banTin)-1] == '>') {
    
    // Tạo các biến tạm để chứa 6 góc
    int de, vai, khuyu, co, xoay, kep;
    
    // Dùng sscanf để quét nhanh 6 con số phân cách bằng dấu phẩy
    // Định dạng mong đợi: <De,Vai,Khuyu,Co,Xoay,Kep>
    int soLuongThamSo = sscanf(banTin, "<%d,%d,%d,%d,%d,%d>", &de, &vai, &khuyu, &co, &xoay, &kep);
    
    // Nếu Pi chỉ gửi 2 thông số (Cổ và Kẹp) ở giai đoạn bạn đang test
    if (soLuongThamSo == 2) {
      // Đọc lại vào đúng biến (ở đây mượn tạm biến de và vai làm co và kep để test 2 trục)
      sscanf(banTin, "<%d,%d>", &co, &kep);
      
      // Cập nhật mảng và ra lệnh
      pwm.setPWM(KENH_SERVO[3], 0, angleToPulse(co));
      pwm.setPWM(KENH_SERVO[5], 0, angleToPulse(kep));
      
      // In ra Serial máy tính để bạn theo dõi
      Serial.printf(">> [VR] Cập nhật: Cổ = %d | Kẹp = %d\n", co, kep);
    }
    // Nếu Pi gửi full 6 thông số
    else if (soLuongThamSo == 6) {
      pwm.setPWM(KENH_SERVO[0], 0, angleToPulse(de));
      pwm.setPWM(KENH_SERVO[1], 0, angleToPulse(vai));
      pwm.setPWM(KENH_SERVO[2], 0, angleToPulse(khuyu));
      pwm.setPWM(KENH_SERVO[3], 0, angleToPulse(co));
      pwm.setPWM(KENH_SERVO[4], 0, angleToPulse(xoay));
      pwm.setPWM(KENH_SERVO[5], 0, angleToPulse(kep));
      
      Serial.printf(">> [VR] Full 6 trục: %d, %d, %d, %d, %d, %d\n", de, vai, khuyu, co, xoay, kep);
    }
    else {
      Serial.println("[CẢNH BÁO] Gói tin không đủ thông số hoặc bị nhiễu.");
    }
  }
}