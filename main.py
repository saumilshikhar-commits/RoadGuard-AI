import cv2
from ultralytics import YOLO
import json
from datetime import datetime
import time
import os
import csv
import threading
import sys

# ================= SETTINGS =================

model = YOLO("/Users/shikhar/runs/detect/train/weights/best.pt")

USE_CAMERA = True

AUTO_CLOSE_DURATION = 240   # 4 minutes

THRESHOLD = 2
SEVERE_THRESHOLD = 5
BEEP_COOLDOWN = 1.5

last_beep_time = 0

# ================= CAMERA / VIDEO SOURCE =================

shared_frame_path = "shared_frame.jpg"
is_shared_source = False
is_file_source = False
cap = None

if USE_CAMERA:
    print("Attempting to initialize direct webcam capture...")
    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    ret, test_frame = cap.read()
    if not ret or test_frame is None:
        print("Direct webcam index 0 unavailable (occupied, locked, or missing).")
        if cap is not None:
            cap.release()
        cap = None
        
        # Check if fresh shared frame from dashboard exists using timezone-safe heartbeat
        is_shared_fresh = False
        if os.path.exists(shared_frame_path):
            temp_heartbeat = "heartbeat_main.tmp"
            try:
                with open(temp_heartbeat, "w") as f:
                    f.write("")
                mtime_shared = os.path.getmtime(shared_frame_path)
                mtime_current = os.path.getmtime(temp_heartbeat)
                if abs(mtime_current - mtime_shared) < 5.0:
                    is_shared_fresh = True
                os.remove(temp_heartbeat)
            except Exception as e:
                if abs(time.time() - os.path.getmtime(shared_frame_path)) < 5.0:
                    is_shared_fresh = True
                    
        if is_shared_fresh:
            print("Webcam index 0 unavailable in main.py. Streaming from shared frame cache instead.")
            is_shared_source = True
        else:
            print("Webcam and shared frame unavailable. Falling back to local video: videos/pothole_video.mp4")
            cap = cv2.VideoCapture("videos/pothole_video.mp4")
            is_file_source = True
else:
    print("Vocal or configuration override: Loading demo video.")
    cap = cv2.VideoCapture("videos/pothole_video.mp4")
    is_file_source = True

# Verification
if not is_shared_source and (cap is None or not cap.isOpened()):
    print("Error: Could not establish camera or video fallback source.")
    sys.exit()

# ================= TIMER =================

start_time = time.time()

# ================= CSV LOG =================

file = open("road_log.csv", "w", newline="")
writer = csv.writer(file)
writer.writerow([
    "Time",
    "Pothole Count",
    "Road Status",
    "Confidence"
])

# ================= FUNCTIONS =================

def play_beep():
    os.system("afplay /System/Library/Sounds/Ping.aiff")

def update_shared_data(count):

    try:
        with open("shared_data.json", "r") as f:
            data = json.load(f)

    except:
        data = []

    data.append({
        "time": datetime.now().strftime("%H:%M:%S"),
        "count": int(count),
        "lat": 12.97 + len(data) * 0.0005,
        "lon": 77.59 + len(data) * 0.0005
    })

    with open("shared_data.json", "w") as f:
        json.dump(data, f, indent=2)

def get_road_status(count):

    if count <= 2:
        return "GOOD ROAD", (0, 255, 0)

    elif count <= 5:
        return "MODERATE ROAD", (0, 255, 255)

    else:
        return "BAD ROAD", (0, 0, 255)

def save_pothole(lat, lon, severity="high"):

    data = {
        "time": str(datetime.now()),
        "lat": lat,
        "lon": lon,
        "severity": severity
    }

    with open("data.json", "a") as f:
        json.dump(data, f)
        f.write("\n")

def log_detection(count):

    data = {
        "time": datetime.now().strftime("%H:%M:%S"),
        "potholes": count,
        "lat": 12.97,
        "lon": 77.59
    }

    try:
        with open("detection_log.json", "r") as f:
            logs = json.load(f)

    except:
        logs = []

    logs.append(data)

    with open("detection_log.json", "w") as f:
        json.dump(logs, f, indent=2)

# ================= MAIN LOOP =================

print("====================================")
print("AI SMART ROAD MONITORING STARTED")
print("====================================")

prev_frame_time = 0
last_log_time = 0

try:

    while True:
        if is_shared_source:
            if os.path.exists(shared_frame_path):
                frame = cv2.imread(shared_frame_path)
                ret = (frame is not None)
            else:
                ret = False
            
            if not ret or frame is None:
                time.sleep(0.1)
                continue
            time.sleep(0.03) # Frame rate limiter
        else:
            if cap is None or not cap.isOpened():
                break
            ret, frame = cap.read()
            if not ret:
                if is_file_source:
                    # Loop fallback demo video continuously
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    continue
                else:
                    print("Failed to grab frame")
                    break
            
            # Symmetrically save raw frames to shared_frame.jpg for the dashboard if main.py is capturing webcam
            if not is_file_source:
                try:
                    cv2.imwrite(shared_frame_path, frame)
                except Exception as e:
                    pass

        # ================= AUTO CLOSE =================

        elapsed_time = time.time() - start_time

        if elapsed_time >= AUTO_CLOSE_DURATION:
            print("Demo completed successfully")
            break

        # ================= YOLO DETECTION =================

        results = model(frame)

        pothole_count = len(results[0].boxes)

        annotated_frame = results[0].plot()

        count = pothole_count

        current_time = time.time()

        time_now = datetime.now().strftime("%H:%M:%S")

        # ================= FPS =================

        new_frame_time = time.time()

        fps = 1 / (new_frame_time - prev_frame_time) if prev_frame_time != 0 else 0

        prev_frame_time = new_frame_time

        # ================= CONFIDENCE =================

        confidence = 0

        if len(results[0].boxes) > 0:
            confidence = float(results[0].boxes.conf[0]) * 100

        confidence_text = f"{confidence:.1f}%"

        # ================= LOGGING =================

        if current_time - last_log_time >= 1.0:
            log_detection(count)
            update_shared_data(count)
            last_log_time = current_time

        if count >= THRESHOLD:

            severity = "moderate"

            if count >= SEVERE_THRESHOLD:
                severity = "high"

            save_pothole(
                12.97,
                77.59,
                severity
            )

        # ================= ROAD STATUS =================

        status, color = get_road_status(count)

        # ================= TITLE =================

        cv2.putText(
            annotated_frame,
            "AI SMART ROAD MONITORING SYSTEM",
            (40, 40),
            cv2.FONT_HERSHEY_COMPLEX,
            0.9,
            (255, 0, 0),
            2
        )

        # ================= POTHOLE COUNT =================

        cv2.putText(
            annotated_frame,
            f"POTHOLES DETECTED: {count}",
            (20, 90),
            cv2.FONT_HERSHEY_COMPLEX,
            0.9,
            (255, 255, 255),
            2
        )

        # ================= ROAD STATUS =================

        cv2.putText(
            annotated_frame,
            f"STATUS: {status}",
            (20, 140),
            cv2.FONT_HERSHEY_COMPLEX,
            0.9,
            color,
            3
        )

        # ================= CONFIDENCE =================

        cv2.putText(
            annotated_frame,
            f"CONFIDENCE: {confidence_text}",
            (20, 190),
            cv2.FONT_HERSHEY_COMPLEX,
            0.8,
            (255, 255, 0),
            2
        )

        # ================= FPS =================

        cv2.putText(
            annotated_frame,
            f"FPS: {int(fps)}",
            (20, 240),
            cv2.FONT_HERSHEY_COMPLEX,
            0.8,
            (0, 255, 255),
            2
        )

        # ================= TIMER =================

        remaining_time = int(AUTO_CLOSE_DURATION - elapsed_time)

        cv2.putText(
            annotated_frame,
            f"AUTO CLOSE IN: {remaining_time}s",
            (20, 290),
            cv2.FONT_HERSHEY_COMPLEX,
            0.8,
            (255, 255, 255),
            2
        )

        # ================= TIMESTAMP =================

        cv2.putText(
            annotated_frame,
            time_now,
            (frame.shape[1] - 200, 40),
            cv2.FONT_HERSHEY_COMPLEX,
            0.7,
            (0, 0, 0),
            2
        )

        # ================= ALERTS =================

        if count >= THRESHOLD:

            cv2.putText(
                annotated_frame,
                "WARNING: ROAD DAMAGE DETECTED",
                (70, 350),
                cv2.FONT_HERSHEY_COMPLEX,
                1,
                (0, 0, 255),
                3
            )

            # Beep cooldown logic
            if current_time - last_beep_time > BEEP_COOLDOWN:

                threading.Thread(
                    target=play_beep,
                    daemon=True
                ).start()

                last_beep_time = current_time

        # ================= SEVERE ALERT =================

        if count >= SEVERE_THRESHOLD:

            cv2.putText(
                annotated_frame,
                "SEVERE ROAD DAMAGE",
                (120, 410),
                cv2.FONT_HERSHEY_COMPLEX,
                1.1,
                (0, 0, 255),
                4
            )

        # ================= CSV LOG =================

        writer.writerow([
            time_now,
            count,
            status,
            confidence_text
        ])

        # ================= DISPLAY =================

        cv2.imshow(
            "AI Smart Road Monitoring System",
            annotated_frame
        )

        # ================= EXIT =================

        key = cv2.waitKey(1) & 0xFF

        if key == ord('q'):
            print("Closed manually")
            break

except KeyboardInterrupt:

    print("Program interrupted")

# ================= CLEANUP =================

finally:

    print("Closing system...")

    if cap is not None:
        cap.release()

    cv2.destroyAllWindows()

    # Important macOS cleanup
    for i in range(5):
        cv2.waitKey(1)
        time.sleep(0.1)

    file.close()

    print("Camera closed successfully")
    print("Program ended successfully")

    sys.exit()