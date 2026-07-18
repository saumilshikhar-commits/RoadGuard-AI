from flask import Flask, Response, jsonify
from ultralytics import YOLO
import cv2

app = Flask(__name__)

# ==========================
# LOAD YOLO MODEL
# ==========================

MODEL_PATH = "/Users/shikhar/runs/detect/train/weights/best.pt"

model = YOLO(MODEL_PATH)

# ==========================
# OPEN CAMERA
# ==========================

camera = cv2.VideoCapture(0)

camera.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

if not camera.isOpened():
    raise Exception("Could not open webcam")

# ==========================
# GLOBAL STATS
# ==========================

total_potholes = 0
last_frame_potholes = 0
critical = 0
road_score = 100
road_status = "Excellent"

# ==========================
# VIDEO STREAM
# ==========================

def generate_frames():

    global total_potholes
    global last_frame_potholes
    global critical
    global road_score
    global road_status

    while True:

        success, frame = camera.read()

        if not success:
            break

        results = model(frame)

        boxes = results[0].boxes

        potholes = len(boxes)

        last_frame_potholes = potholes

        total_potholes += potholes

        critical = potholes

        road_score = max(100 - potholes * 5, 40)

        if potholes == 0:
            road_status = "Excellent"
        elif potholes <= 2:
            road_status = "Good"
        elif potholes <= 5:
            road_status = "Warning"
        else:
            road_status = "Critical"

        annotated = results[0].plot()

        ret, buffer = cv2.imencode(".jpg", annotated)

        if not ret:
            continue

        frame = buffer.tobytes()

        yield (
            b'--frame\r\n'
            b'Content-Type: image/jpeg\r\n\r\n' +
            frame +
            b'\r\n'
        )

# ==========================
# ROUTES
# ==========================

@app.route("/")
def home():
    return "RoadGuard AI Backend Running"


@app.route("/video_feed")
def video_feed():

    return Response(
        generate_frames(),
        mimetype="multipart/x-mixed-replace; boundary=frame"
    )


@app.route("/api/stats")
def stats():

    return jsonify({

        "total": total_potholes,

        "score": road_score,

        "status": road_status,

        "critical": critical,

        "last": {

            "potholes": last_frame_potholes

        }

    })


@app.route("/api/potholes")
def potholes():

    return jsonify({

        "live": last_frame_potholes,

        "total": total_potholes

    })


@app.route("/api/log")
def log():

    return jsonify([

        {

            "time": "Live",

            "potholes": last_frame_potholes,

            "severity": road_status

        }

    ])


@app.route("/favicon.ico")
def favicon():
    return "", 204


# ==========================
# START SERVER
# ==========================

if __name__ == "__main__":

    print("\n==============================")
    print(" RoadGuard AI Backend Running ")
    print("==============================")
    print("Video Feed : http://192.168.0.10:5001/video_feed")
    print("Stats API  : http://192.168.0.10:5001/api/stats")
    print("==============================\n")

    app.run(
        host="0.0.0.0",
        port=5001,
        threaded=True,
        debug=False
    )