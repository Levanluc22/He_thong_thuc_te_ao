from machine import Pin, PWM, UART
import time

# --- CẤU HÌNH UART ---
# Sử dụng UART2, TX cắm vào RX của Pi, RX cắm vào TX của Pi
uart = UART(2, baudrate=115200, tx=17, rx=16)

# --- CẤU HÌNH SERVO ---
servo_gripper = PWM(Pin(18), freq=50) # Servo Kẹp
servo_pitch = PWM(Pin(19), freq=50)   # Servo Cúi/Ngẩng cổ tay

def set_servo_angle(servo, angle):
    # Quy đổi độ (0-180) sang Duty (40-115) cho ESP32
    duty = int(40 + (angle / 180.0) * (115 - 40))
    servo.duty(duty)

print("ESP32 sẵn sàng nhận dữ liệu UART...")

# Khởi tạo vị trí thẳng
set_servo_angle(servo_gripper, 90)
set_servo_angle(servo_pitch, 90)

buffer = ""

while True:
    if uart.any():
        # Đọc dữ liệu từ UART
        data = uart.read().decode('utf-8')
        buffer += data
        
        # Nếu đã nhận đủ 1 dòng (kết thúc bằng \n)
        if '\n' in buffer:
            lines = buffer.split('\n')
            
            # Xử lý dòng dữ liệu hoàn chỉnh (thường là dòng đầu tiên)
            msg = lines[0].strip()
            
            # Lưu phần dữ liệu thừa vào buffer cho chu kỳ sau
            buffer = lines[-1] 
            
            # Phân tích cú pháp bản tin: <180,90>
            if msg.startswith('<') and msg.endswith('>'):
                msg = msg[1:-1] # Cắt bỏ < và >
                angles = msg.split(',')
                
                if len(angles) == 2:
                    try:
                        g_angle = int(angles[0])
                        p_angle = int(angles[1])
                        
                        # Điều khiển Servo ngay lập tức
                        set_servo_angle(servo_gripper, g_angle)
                        set_servo_angle(servo_pitch, p_angle)
                    except ValueError:
                        pass # Bỏ qua nếu dữ liệu bị nhiễu không phải là số