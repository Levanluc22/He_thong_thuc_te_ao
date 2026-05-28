import cv2
import mediapipe as mp
import math
import serial
import time

# Mở cổng UART giao tiếp với ESP32
try:
    ser = serial.Serial('/dev/serial0', 115200, timeout=1)
except:
    ser = None
    print("Chưa kết nối mạch, chỉ chạy mô phỏng hiển thị Camera.")

mp_hands = mp.solutions.hands
mp_draw = mp.solutions.drawing_utils
hands = mp_hands.Hands(max_num_hands=1, min_detection_confidence=0.7)
cap = cv2.VideoCapture(0)

def map_value(x, in_min, in_max, out_min, out_max):
    val = (x - in_min) * (out_max - out_min) / (in_max - in_min) + out_min
    return int(max(min(val, max(out_min, out_max)), min(out_min, out_max)))

# Bộ lọc EMA chống nhiễu (Giúp tay robot không bị giật)
ALPHA = 0.2
prev_kep = 170  # Mặc định Há mỏ giống code Arduino
prev_co = 0     # Mặc định Cổ ở góc 0 giống code Arduino

while cap.isOpened():
    success, img = cap.read()
    if not success: break
    
    img = cv2.flip(img, 1)
    h, w, _ = img.shape
    results = hands.process(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    
    if results.multi_hand_landmarks:
        for hand_landmarks in results.multi_hand_landmarks:
            mp_draw.draw_landmarks(img, hand_landmarks, mp_hands.HAND_CONNECTIONS)
            
            # --- 1. ĐIỀU KHIỂN KẸP (Ngón cái & Ngón trỏ) ---
            thumb = hand_landmarks.landmark[4]
            index = hand_landmarks.landmark[8]
            distance = math.hypot((index.x - thumb.x) * w, (index.y - thumb.y) * h)
            
            # THEO CODE ARDUINO: Chụm tay (distance nhỏ) -> góc 80. Xòe tay (distance lớn) -> góc 170.
            raw_kep = map_value(distance, 30, 150, 80, 170)

            # --- 2. ĐIỀU KHIỂN CỔ TAY (Pitch) ---
            wrist = hand_landmarks.landmark[0]
            middle_mcp = hand_landmarks.landmark[9]
            pitch_rad = math.atan2(middle_mcp.y - wrist.y, middle_mcp.x - wrist.x)
            
            # Quy đổi góc ngẩng/cúi tay sang giới hạn của trục Cổ (Ví dụ: 0 đến 180)
            raw_co = map_value(math.degrees(pitch_rad), -90, 90, 0, 180)

            # --- LỌC NHIỄU VÀ ĐÓNG GÓI ---
            final_kep = int((ALPHA * raw_kep) + ((1 - ALPHA) * prev_kep))
            final_co = int((ALPHA * raw_co) + ((1 - ALPHA) * prev_co))
            
            prev_kep = final_kep
            prev_co = final_co

            # Định dạng gửi đi: <Góc_Cổ,Góc_Kẹp>\n
            payload = f"<{final_co},{final_kep}>\n"
            
            if ser:
                ser.write(payload.encode('utf-8'))
                
            cv2.putText(img, f'Co: {final_co} | Kep: {final_kep}', (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

    cv2.imshow("Artemis - VR Control", img)
    if cv2.waitKey(1) == ord('q'): break

cap.release()
if ser: ser.close()
cv2.destroyAllWindows()