import cv2
import mediapipe as mp
import math
import time
import paho.mqtt.client as mqtt
from flask import Flask, Response

# KHỞI TẠO WEB SERVER
app = Flask(__name__)

# MQTT CONFIG
MQTT_BROKER = "10.149.116.175"
MQTT_PORT = 1883
MQTT_TOPIC = "vku/artemis/robot_arm/control"

print(f"[MQTT] Đang kết nối tới {MQTT_BROKER}...")

mqtt_client = mqtt.Client()

try:
    mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
    mqtt_client.loop_start()
    mqtt_connected = True
    print("[MQTT] KẾT NỐI THÀNH CÔNG ✅")

except Exception as e:
    mqtt_connected = False
    print(f"[MQTT ERROR] {e}")
# MEDIAPIPE CONFIG
mp_hands = mp.solutions.hands
mp_draw = mp.solutions.drawing_utils
hands = mp_hands.Hands(
    max_num_hands=1, min_detection_confidence=0.7, model_complexity=0
)
# CAMERA CONFIG
cap = cv2.VideoCapture(0, cv2.CAP_V4L2)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
cap.set(cv2.CAP_PROP_FPS, 30)
cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)


# MAP FUNCTION
def map_value(x, in_min, in_max, out_min, out_max):
    val = (x - in_min) * (out_max - out_min) / (in_max - in_min) + out_min
    return int(max(min(val, max(out_min, out_max)), min(out_min, out_max)))


# ROBOT HOME POSITION
prev_angles = [0, 100, 90, 0, 0, 170]
ALPHA = 0.4
last_mqtt_send_time = time.time()
MQTT_PUBLISH_INTERVAL = 0.03


# AI + STREAM LOOP
def generate_frames():
    global prev_angles
    global last_mqtt_send_time
    while cap.isOpened():
        success, img = cap.read()
        if not success:
            break
        img = cv2.flip(img, 1)
        h, w, _ = img.shape
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        results = hands.process(img_rgb)
        final_angles = prev_angles.copy()
        # DETECT HAND
        if results.multi_hand_landmarks:
            for hand_landmarks in results.multi_hand_landmarks:
                mp_draw.draw_landmarks(img, hand_landmarks, mp_hands.HAND_CONNECTIONS)
                # LANDMARKS
                wrist = hand_landmarks.landmark[0]
                thumb_tip = hand_landmarks.landmark[4]
                index_tip = hand_landmarks.landmark[8]
                index_mcp = hand_landmarks.landmark[5]
                pinky_mcp = hand_landmarks.landmark[17]
                middle_mcp = hand_landmarks.landmark[9]
                # HAND SIZE
                hand_size = math.hypot(
                    (middle_mcp.x - wrist.x) * w, (middle_mcp.y - wrist.y) * h
                )
                hand_size = max(hand_size, 1.0)
                # BASE
                raw_de = map_value(wrist.x, 0.3, 0.7, 90, 0)
                # SHOULDER
                raw_vai = map_value(wrist.y, 0.3, 0.7, 140, 60)
                # ELBOW
                raw_khuyu = map_value(hand_size, 40, 180, 130, 50)
                # WRIST PITCH
                pitch_rad = math.atan2(middle_mcp.y - wrist.y, middle_mcp.x - wrist.x)
                raw_co = map_value(math.degrees(pitch_rad), -90, 90, 0, 160)
                # WRIST ROLL
                roll_rad = math.atan2(
                    pinky_mcp.y - index_mcp.y, pinky_mcp.x - index_mcp.x
                )
                raw_xoay = map_value(math.degrees(roll_rad), -90, 90, 90, 0)
                # GRIPPER
                grip_dist = math.hypot(
                    (index_tip.x - thumb_tip.x) * w, (index_tip.y - thumb_tip.y) * h
                )
                grip_ratio = (grip_dist / hand_size) * 100
                raw_kep = map_value(int(grip_ratio), 40, 90, 90, 170)
                # RAW ANGLES ARRAY
                raw_angles = [raw_de, raw_vai, raw_khuyu, raw_co, raw_xoay, raw_kep]
                # EMA FILTER
                for i in range(6):
                    final_angles[i] = int(
                        (ALPHA * raw_angles[i]) + ((1 - ALPHA) * prev_angles[i])
                    )
                    prev_angles[i] = final_angles[i]
                # MQTT SEND
                current_time = time.time()
                if mqtt_connected and (
                    current_time - last_mqtt_send_time > MQTT_PUBLISH_INTERVAL
                ):
                    payload = (
                        f"<{final_angles[0]},"
                        f"{final_angles[1]},"
                        f"{final_angles[2]},"
                        f"{final_angles[3]},"
                        f"{final_angles[4]},"
                        f"{final_angles[5]}>"
                    )
                    mqtt_client.publish(MQTT_TOPIC, payload)
                    last_mqtt_send_time = current_time
                    print(f"[MQTT SEND] {payload}")
                # HUD DISPLAY
                cv2.putText(
                    img,
                    f"De:{final_angles[0]} "
                    f"Vai:{final_angles[1]} "
                    f"Khuyu:{final_angles[2]}",
                    (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (0, 255, 0),
                    2,
                )
                cv2.putText(
                    img,
                    f"Co:{final_angles[3]} "
                    f"Xoay:{final_angles[4]} "
                    f"Kep:{final_angles[5]}",
                    (10, 60),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (0, 255, 255),
                    2,
                )
        # STREAM WEB
        ret, buffer = cv2.imencode(".jpg", img)
        frame = buffer.tobytes()
        yield (b"--frame\r\n" b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n")


# WEB ROUTE
@app.route("/")
def index():
    return """
    <html>
        <head>
            <title>ARTEMIS VR CONTROL</title>
            <style>
                body {
                    text-align: center;
                    background-color: #111;
                    color: #0f0;
                    font-family: monospace;
                }
                img {
                    border: 2px solid #0f0;
                    border-radius: 8px;
                }
            </style>
        </head>
        <body>
            <h1>🤖 ARTEMIS VR CLOUD DASHBOARD</h1>
            <img src="/video_feed">
        </body>
    </html>
    """


# VIDEO ROUTE
@app.route("/video_feed")
def video_feed():
    return Response(
        generate_frames(), mimetype="multipart/x-mixed-replace; boundary=frame"
    )


# MAIN
if __name__ == "__main__":
    print("[SYSTEM] Flask Server Starting...")
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
