import cv2
import mediapipe as mp
import math
import serial
import time
from flask import Flask, Response

# Khởi tạo Web Server
app = Flask(__name__)

# ==========================================
# CẤU HÌNH UART GIAO TIẾP VỚI ESP32
# ==========================================
try:
    ser = serial.Serial('/dev/serial0', 115200, timeout=1)
    print("[HỆ THỐNG] Đã mở cổng UART thành công.")
except:
    ser = None
    print("[CẢNH BÁO] Chưa kết nối chân UART với ESP32.")

# ==========================================
# CẤU HÌNH MEDIAPIPE & CAMERA
# ==========================================
mp_hands = mp.solutions.hands
mp_draw = mp.solutions.drawing_utils
hands = mp_hands.Hands(max_num_hands=1, min_detection_confidence=0.7)

cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
cap.set(cv2.CAP_PROP_FPS, 30)

def map_value(x, in_min, in_max, out_min, out_max):
    val = (x - in_min) * (out_max - out_min) / (in_max - in_min) + out_min
    return int(max(min(val, max(out_min, out_max)), min(out_min, out_max)))

# Biến toàn cục cho bộ lọc EMA
prev_kep = 170  
prev_co = 90    
ALPHA = 0.2

def generate_frames():
    global prev_kep, prev_co
    
    while cap.isOpened():
        success, img = cap.read()
        if not success:
            break
        
        img = cv2.flip(img, 1)
        h, w, _ = img.shape
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        results = hands.process(img_rgb)
        
        if results.multi_hand_landmarks:
            for hand_landmarks in results.multi_hand_landmarks:
                mp_draw.draw_landmarks(img, hand_landmarks, mp_hands.HAND_CONNECTIONS)
                
                # --- 1. ĐIỀU KHIỂN KẸP ---
                thumb = hand_landmarks.landmark[4]
                index = hand_landmarks.landmark[8]
                distance = math.hypot((index.x - thumb.x) * w, (index.y - thumb.y) * h)
                raw_kep = map_value(distance, 30, 150, 80, 170)

                # --- 2. ĐIỀU KHIỂN CỔ TAY ---
                wrist = hand_landmarks.landmark[0]
                middle_mcp = hand_landmarks.landmark[9]
                pitch_rad = math.atan2(middle_mcp.y - wrist.y, middle_mcp.x - wrist.x)
                raw_co = map_value(math.degrees(pitch_rad), -90, 90, 0, 180)

                # --- 3. LỌC NHIỄU & GỬI UART ---
                final_kep = int((ALPHA * raw_kep) + ((1 - ALPHA) * prev_kep))
                final_co = int((ALPHA * raw_co) + ((1 - ALPHA) * prev_co))
                
                prev_kep = final_kep
                prev_co = final_co

                payload = f"<{final_co},{final_kep}>\n"
                if ser:
                    try:
                        ser.write(payload.encode('utf-8'))
                    except:
                        pass
                    
                cv2.putText(img, f'Co: {final_co} | Kep: {final_kep}', (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

        # --- ĐÓNG GÓI KHUNG HÌNH LÊN WEB ---
        # Nén ảnh thành chuẩn JPEG để truyền qua mạng nhẹ hơn
        ret, buffer = cv2.imencode('.jpg', img)
        frame = buffer.tobytes()
        
        # Bắn từng khung hình ra cho trình duyệt web (chuẩn MJPEG)
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

# ==========================================
# CÁC ĐƯỜNG DẪN WEB (ROUTES)
# ==========================================
@app.route('/')
def index():
    # Trả về một trang HTML đơn giản nhúng luồng video vào giữa
    return '''
    <html>
        <head>
            <title>Artemis - VR Controller</title>
            <style>
                body { text-align: center; background-color: #222; color: white; font-family: Arial; }
                img { border: 5px solid #444; border-radius: 10px; margin-top: 20px; }
            </style>
        </head>
        <body>
            <h1>Artemis VR Teleoperation</h1>
            <h3>Live Camera Feed từ Raspberry Pi</h3>
            <img src="/video_feed" width="640" height="480">
        </body>
    </html>
    '''

@app.route('/video_feed')
def video_feed():
    # Cung cấp luồng video liên tục từ hàm generate_frames()
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == "__main__":
    # Chạy Web Server ở Port 5000, cho phép mọi thiết bị trong mạng truy cập (0.0.0.0)
    print("[HỆ THỐNG] Đang khởi động Web Server...")
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)