from flask import Flask, Response
import cv2
from flask import Flask, render_template, Response, request
from flask import Flask, jsonify, render_template
from ultralytics import YOLO
from datetime import datetime
import time
import os
import threading
from pothole_data import locations



app = Flask(__name__)

# Load model
model = YOLO("yolov8n.pt")

# Webcam
camera = cv2.VideoCapture(0)
# FPS variables
prev_frame_time = 0
new_frame_time = 0

def generate_frames():

    global prev_frame_time

    while True:

        success, frame = camera.read()

        if not success:
            break

        # Run YOLO detection
        results = model(frame)

        # Draw detection boxes
        annotated_frame = results[0].plot()

        # FPS Calculation
        new_frame_time = time.time()

        fps = 1 / (new_frame_time - prev_frame_time)

        prev_frame_time = new_frame_time

        fps_text = f"FPS: {int(fps)}"

        cv2.putText(
            annotated_frame,
            fps_text,
            (20, 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (0, 255, 255),
            2
        )

        # Convert image to jpg
        ret, buffer = cv2.imencode('.jpg', annotated_frame)

        frame = buffer.tobytes()

        # Send frames to browser
        yield (
            b'--frame\r\n'
            b'Content-Type: image/jpeg\r\n\r\n' +
            frame +
            b'\r\n'
        )

@app.route('/')
def index():
    return render_template('map.html')


@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')


if __name__ == "__main__":
    app.run(debug=True)

# ================= MODEL =================
model = YOLO("/Users/shikhar/runs/detect/train/weights/best.pt")

# ================= VIDEO =================
video_path = "/Users/shikhar/AI_Pothole_Detection/pothole_video.mp4"


def play_beep():
    os.system("afplay /System/Library/Sounds/Ping.aiff")


def get_status(count):
    if count <= 2:
        return "GOOD ROAD", (0, 255, 0)
    elif count <= 5:
        return "MODERATE ROAD", (0, 255, 255)
    else:
        return "ROAD DAMAGE DETECTED", (0, 0, 255)


def generate_frames():

    cap = cv2.VideoCapture(video_path)

    last_beep = 0

    while True:
        success, frame = cap.read()

        if not success:
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            continue

        frame = cv2.resize(frame, (640, 360))

        results = model(frame)
        annotated = results[0].plot()

        count = len(results[0].boxes)
        status, color = get_status(count)

        now = datetime.now().strftime("%H:%M:%S")

        # ================= TITLE =================
        cv2.putText(
            annotated,
            "AI SMART ROAD MONITORING SYSTEM",
            (40, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 0, 0),
            2
        )

        # ================= COUNT =================
        cv2.putText(
            annotated,
            f"Potholes Detected: {count}",
            (20, 80),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 0, 255),
            2
        )

        # ================= STATUS =================
        cv2.putText(
            annotated,
            status,
            (20, 120),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            color,
            2
        )

        # ================= TIMESTAMP =================
        (w, h), _ = cv2.getTextSize(now, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)

        x = 640 - w - 10
        y = 25

        cv2.putText(
            annotated,
            now,
            (x, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 0, 0),
            2
        )

        # ================= BEEP (CONTROLLED) =================
        if count > 0 and time.time() - last_beep > 3:
            threading.Thread(target=play_beep, daemon=True).start()
            last_beep = time.time()

        # ================= STREAM FIX =================
        ret, buffer = cv2.imencode('.jpg', annotated)
        if not ret:
            continue

        frame = buffer.tobytes()

        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')


@app.route('/')
def home():
    return "AI Smart Road Monitoring System Running"


@app.route('/video')
def video():
    return Response(generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/video_feed')
def video_feed():
    return Response(
        generate_frames(),
        mimetype='multipart/x-mixed-replace; boundary=frame'
    )

@app.route('/')
def home():

    area = request.args.get('area')

    area_data = None

    if area in locations:
        area_data = locations[area]

    return render_template(
        'index.html',
        locations=locations,
        area_data=area_data,
        selected_area=area
    )

@app.route('/video_feed')
def video_feed():
    return Response(
        generate_frames(),
        mimetype='multipart/x-mixed-replace; boundary=frame'
    )

@app.route('/')
def index():
    return render_template('map.html')

@app.route('/api/potholes')
def potholes_api():

    sample_data = [
        {
            "lat": 12.9716,
            "lon": 77.5946,
            "severity": "high",
            "location": "MG Road"
        }
    ]

    return jsonify(sample_data)

# =========================
# MOBILE API
# =========================

@app.route('/api/potholes')
def potholes_api():

    sample_data = [
        {
            "lat": 12.9716,
            "lon": 77.5946,
            "severity": "high",
            "location": "MG Road"
        },
        {
            "lat": 12.9800,
            "lon": 77.6000,
            "severity": "medium",
            "location": "Indiranagar"
        },
        {
            "lat": 12.9500,
            "lon": 77.5800,
            "severity": "low",
            "location": "Whitefield"
        }
    ]

    return jsonify(sample_data)

if __name__ == '__main__':
    app.run(debug=True)



    if __name__ == "__main__":
        app.run(debug=True, port=5001)



# ==============================
# MOBILE API
# ==============================

@app.route('/api/potholes')
def potholes_api():

    sample_data = [
        {
            "lat": 12.9716,
            "lon": 77.5946,
            "severity": "high",
            "location": "MG Road"
        },
        {
            "lat": 12.9800,
            "lon": 77.6000,
            "severity": "medium",
            "location": "Indiranagar"
        },
        {
            "lat": 12.9500,
            "lon": 77.5800,
            "severity": "low",
            "location": "Whitefield"
        }
    ]

    return jsonify(sample_data)