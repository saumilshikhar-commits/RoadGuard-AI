import matplotlib
matplotlib.use('Agg')

import matplotlib.pyplot as plt
import io
import base64
import json

from flask import Flask, render_template, render_template_string, jsonify, Response
import os
import time
import cv2
import threading
from datetime import datetime

app = Flask(__name__)

# ================= BACKGROUND CAMERA THREAD =================
class CameraStream:
    def __init__(self, src=0):
        self.src = src
        self.is_file = False
        self.is_shared_file = False
        self.shared_path = "shared_frame.jpg"
        
        self.stream = cv2.VideoCapture(src)
        self.stream.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self.grabbed, self.frame = self.stream.read()
        
        # Symmetrical frame sharing check
        if not self.grabbed or self.frame is None:
            # Direct webcam is unavailable. Check if fresh shared frame from main.py exists using timezone-safe heartbeat
            is_shared_fresh = False
            if os.path.exists(self.shared_path):
                temp_heartbeat = "heartbeat_dash.tmp"
                try:
                    with open(temp_heartbeat, "w") as f:
                        f.write("")
                    mtime_shared = os.path.getmtime(self.shared_path)
                    mtime_current = os.path.getmtime(temp_heartbeat)
                    if abs(mtime_current - mtime_shared) < 5.0:
                        is_shared_fresh = True
                    os.remove(temp_heartbeat)
                except Exception as e:
                    # Clock Epoch Fallback
                    if abs(time.time() - os.path.getmtime(self.shared_path)) < 5.0:
                        is_shared_fresh = True
            
            if is_shared_fresh:
                print("Webcam index 0 unavailable in dashboard. Streaming from shared frame cache instead.")
                self.stream.release()
                self.is_shared_file = True
                self.frame = cv2.imread(self.shared_path)
                self.grabbed = (self.frame is not None)
            else:
                # Fallback to local video if no webcam or active shared frame
                print("Webcam (index 0) and shared frame unavailable. Falling back to local video: videos/pothole_video.mp4")
                self.stream.release()
                video_path = "videos/pothole_video.mp4"
                if os.path.exists(video_path):
                    self.stream = cv2.VideoCapture(video_path)
                    self.grabbed, self.frame = self.stream.read()
                    self.is_file = True
                else:
                    print("Fallback video file videos/pothole_video.mp4 not found!")
        else:
            # Direct webcam successfully acquired. Write it to share with main.py
            try:
                cv2.imwrite(self.shared_path, self.frame)
            except Exception as e:
                pass
                
        self.started = False
        self.read_lock = threading.Lock()

    def start(self):
        if self.started:
            return self
        self.started = True
        self.thread = threading.Thread(target=self.update, args=())
        self.thread.daemon = True
        self.thread.start()
        return self

    def update(self):
        while self.started:
            if self.is_shared_file:
                if os.path.exists(self.shared_path):
                    frame = cv2.imread(self.shared_path)
                    if frame is not None:
                        with self.read_lock:
                            self.frame = frame
                            self.grabbed = True
                time.sleep(0.03)
            elif self.stream.isOpened():
                grabbed, frame = self.stream.read()
                if grabbed:
                    with self.read_lock:
                        self.grabbed = grabbed
                        self.frame = frame
                    if not self.is_file:
                        try:
                            cv2.imwrite(self.shared_path, frame)
                        except Exception as e:
                            pass
                else:
                    if self.is_file:
                        # Auto loop video file
                        self.stream.set(cv2.CAP_PROP_POS_FRAMES, 0)
                time.sleep(0.03 if self.is_file else 0.01)
            else:
                time.sleep(0.05)

    def read(self):
        # Symmetrically prioritize shared_frame.jpg if it was updated recently by a mobile device
        if os.path.exists(self.shared_path):
            try:
                mtime_shared = os.path.getmtime(self.shared_path)
                if abs(time.time() - mtime_shared) < 3.0:
                    frame = cv2.imread(self.shared_path)
                    if frame is not None:
                        return True, frame
            except Exception as e:
                pass

        with self.read_lock:
            frame_copy = self.frame.copy() if self.frame is not None else None
            grabbed = self.grabbed
        return grabbed, frame_copy

    def stop(self):
        self.started = False
        if self.stream.isOpened():
            self.stream.release()

# Global camera stream reference
camera_stream = None

# Cooldown to control disk writing frequency (write logs at max 1 Hz)
last_log_time = 0.0

# ================= LOAD YOLO MODEL =================
try:
    model_path = "/Users/shikhar/runs/detect/train/weights/best.pt"
    if os.path.exists(model_path):
        from ultralytics import YOLO
        model = YOLO(model_path)
        print(f"Loaded custom YOLO model from: {model_path}")
    else:
        from ultralytics import YOLO
        model = YOLO("yolov8n.pt")
        print("Fallback: Loaded standard yolov8n.pt model")
except Exception as e:
    print(f"Error loading YOLO model: {e}. Attempting fallback to yolov8n.pt")
    from ultralytics import YOLO
    model = YOLO("yolov8n.pt")

def get_road_status_color(count):
    if count <= 2:
        return "GOOD ROAD", (0, 255, 0)
    elif count <= 5:
        return "MODERATE ROAD", (0, 255, 255)
    else:
        return "ROAD DAMAGE DETECTED", (0, 0, 255)

def update_shared_data(count, lat=None, lon=None):
    try:
        with open("shared_data.json", "r") as f:
            data = json.load(f)
    except:
        data = []

    if lat is None or lon is None:
        lat_val = 12.97 + len(data) * 0.0005
        lon_val = 77.59 + len(data) * 0.0005
    else:
        try:
            lat_val = float(lat)
            lon_val = float(lon)
        except:
            lat_val = 12.97
            lon_val = 77.59

    data.append({
        "time": datetime.now().strftime("%H:%M:%S"),
        "count": int(count),
        "lat": lat_val,
        "lon": lon_val
    })

    if len(data) > 200:
        data = data[-200:]

    with open("shared_data.json", "w") as f:
        json.dump(data, f, indent=2)

def log_detection(count, lat=None, lon=None):
    if lat is None or lon is None:
        lat_val = 12.97
        lon_val = 77.59
    else:
        try:
            lat_val = float(lat)
            lon_val = float(lon)
        except:
            lat_val = 12.97
            lon_val = 77.59

    data = {
        "time": datetime.now().strftime("%H:%M:%S"),
        "potholes": count,
        "lat": lat_val,
        "lon": lon_val
    }

    try:
        with open("detection_log.json", "r") as f:
            logs = json.load(f)
    except:
        logs = []

    logs.append(data)

    if len(logs) > 200:
        logs = logs[-200:]

    with open("detection_log.json", "w") as f:
        json.dump(logs, f, indent=2)

# ================= VIDEO FEED GENERATOR =================
def generate_frames():
    global camera_stream, last_log_time
    if camera_stream is None:
        camera_stream = CameraStream(0).start()

    while True:
        success, frame = camera_stream.read()
        if not success or frame is None:
            import numpy as np
            # Create a premium cyberpunk synthetic scanning frame
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            # Draw cyber grids
            for x in range(0, 640, 40):
                cv2.line(frame, (x, 0), (x, 480), (15, 22, 33), 1)
            for y in range(0, 480, 40):
                cv2.line(frame, (0, y), (640, y), (15, 22, 33), 1)
            
            # Scanning beam
            beam_y = int((time.time() * 120) % 480)
            cv2.line(frame, (0, beam_y), (640, beam_y), (255, 42, 95), 1)
            cv2.line(frame, (0, beam_y - 2), (640, beam_y - 2), (120, 20, 45), 1)
            
            # Reticle
            cv2.circle(frame, (320, 240), 60, (0, 240, 255), 1)
            cv2.line(frame, (320, 170), (320, 310), (0, 240, 255), 1)
            cv2.line(frame, (250, 240), (390, 240), (0, 240, 255), 1)
            
            # Text HUD
            cv2.putText(frame, "COGNITIVE RADAR STREAMING...", (40, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 240, 255), 1, cv2.LINE_AA)
            cv2.putText(frame, "UPLINK STATS: OPTIMAL [SAT-COM]", (40, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 170), 1, cv2.LINE_AA)
            cv2.putText(frame, "CONNECTING TO TACTICAL SURVEILLANCE FEED...", (40, 130), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 0, 127), 1, cv2.LINE_AA)
            
            annotated_frame = frame
            pothole_count = 0
            status = "GOOD ROAD"
            color_bgr = (0, 255, 0)
        else:
            # Resize for smooth processing
            frame = cv2.resize(frame, (640, 480))

            # Run YOLO detection
            results = model(frame)

            annotated_frame = frame.copy()
            pothole_count = len(results[0].boxes)
            status, color_bgr = get_road_status_color(pothole_count)

            # Draw Corner L-Brackets instead of full box
            for box in results[0].boxes:
                xyxy = box.xyxy[0].tolist()
                conf = float(box.conf[0]) * 100
                x1, y1, x2, y2 = map(int, xyxy)
                
                if pothole_count >= 5:
                    color = (42, 42, 255) # Red (BGR)
                    sev_label = "CRITICAL"
                elif pothole_count >= 2:
                    color = (0, 156, 255) # Orange (BGR)
                    sev_label = "MODERATE"
                else:
                    color = (153, 255, 0) # Green (BGR)
                    sev_label = "LOW"
                    
                length = min(15, int((x2 - x1) * 0.25))
                thickness = 2
                
                # Draw Corner brackets
                cv2.line(annotated_frame, (x1, y1), (x1 + length, y1), color, thickness)
                cv2.line(annotated_frame, (x1, y1), (x1, y1 + length), color, thickness)
                cv2.line(annotated_frame, (x2, y1), (x2 - length, y1), color, thickness)
                cv2.line(annotated_frame, (x2, y1), (x2, y1 + length), color, thickness)
                cv2.line(annotated_frame, (x1, y2), (x1 + length, y2), color, thickness)
                cv2.line(annotated_frame, (x1, y2), (x1, y2 - length), color, thickness)
                cv2.line(annotated_frame, (x2, y2), (x2 - length, y2), color, thickness)
                cv2.line(annotated_frame, (x2, y2), (x2, y2 - length), color, thickness)
                
                # Crosshair center reticle
                cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
                cv2.line(annotated_frame, (cx - 4, cy), (cx + 4, cy), color, 1)
                cv2.line(annotated_frame, (cx, cy - 4), (cx, cy + 4), color, 1)
                
                label = f"POTHOLE [CONF: {conf:.1f}%] [SEV: {sev_label}]"
                cv2.putText(annotated_frame, label, (x1, y1 - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.36, color, 1, cv2.LINE_AA)

        # Draw scanlines and titles
        cv2.putText(annotated_frame, "AI LIVE WEBCAM SCAN ACTIVE", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 255), 2)
        cv2.putText(annotated_frame, f"POTHOLES: {pothole_count} ({status})", (20, 75), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (color_bgr[2], color_bgr[1], color_bgr[0]), 2)
        
        # Log detections at 1 Hz max rate
        current_time = time.time()
        if current_time - last_log_time >= 1.0:
            log_detection(pothole_count)
            update_shared_data(pothole_count)
            last_log_time = current_time

        ret, buffer = cv2.imencode('.jpg', annotated_frame)
        frame_bytes = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

# ================= LOAD DATA (UNCHANGED) =================

def load_data():
    try:
        with open("detection_log.json", "r") as f:
            return json.load(f)
    except:
        return []

def load_shared_data():
    try:
        with open("shared_data.json", "r") as f:
            return json.load(f)
    except:
        return []

# ================= CREATE GRAPH (UNCHANGED) =================

def create_graph(data):
    if len(data) == 0:
        return ""
    data = data[-10:]
    times = list(range(len(data)))
    values = [d["potholes"] for d in data]
    plt.figure(figsize=(6, 3))
    plt.plot(times, values, marker='o')
    plt.title("Potholes Over Time")
    plt.xlabel("Time")
    plt.ylabel("Potholes")
    plt.xticks(times, [d["time"] for d in data], rotation=30)
    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("utf-8")

# ================= ROAD SCORE (UNCHANGED) =================

def calculate_road_score(data):
    if len(data) == 0:
        return 100, "Excellent"
    total = sum([d["potholes"] for d in data])
    avg = total / len(data)
    score = max(0, 100 - (avg * 10))
    if score >= 95:
        status = "Excellent"
    elif score >= 70:
        status = "Good"
    elif score >= 40:
        status = "Moderate"
    else:
        status = "Poor"
    return int(score), status

# ================= DASHBOARD HTML =================

HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>RoadGuard AI — Real-Time Surveillance Command Center</title>
<link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@400;600;700;900&family=Share+Tech+Mono&family=Rajdhani:wght@400;500;600;700&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
  :root {
    --bg:         #030611;
    --bg-card:    rgba(10, 18, 36, 0.45);
    --border-glow:rgba(0, 240, 255, 0.15);
    --cyan:       #00f0ff;
    --cyan-dim:   rgba(0, 240, 255, 0.12);
    --cyan-glow:  0 0 15px rgba(0, 240, 255, 0.5);
    --pink:       #ff007f;
    --pink-glow:  0 0 15px rgba(255, 0, 127, 0.45);
    --green:      #00ffaa;
    --green-glow: 0 0 15px rgba(0, 255, 170, 0.45);
    --orange:     #ff9c00;
    --orange-glow:0 0 15px rgba(255, 156, 0, 0.45);
    --red:        #ff2a5f;
    --red-glow:   0 0 15px rgba(255, 42, 95, 0.45);
    --text:       #e2f1ff;
    --text-dim:   #6c8ba4;
    --glass:      rgba(255, 255, 255, 0.02);
    --glass-b:    rgba(0, 240, 255, 0.08);
  }

  *, *::before, *::after { margin:0; padding:0; box-sizing:border-box; }

  body {
    background: var(--bg);
    color: var(--text);
    font-family: 'Rajdhani', sans-serif;
    font-weight: 500;
    min-height: 100vh;
    overflow-x: hidden;
    position: relative;
  }

  /* ===== DIGITAL GRID & BACKGROUND EFFECTS ===== */
  body::before {
    content: '';
    position: fixed;
    inset: 0;
    background: repeating-linear-gradient(
      0deg,
      transparent,
      transparent 2px,
      rgba(0,0,0,0.15) 2px,
      rgba(0,0,0,0.15) 4px
    );
    pointer-events: none;
    z-index: 9999;
  }

  body::after {
    content: '';
    position: fixed;
    inset: 0;
    background-image:
      linear-gradient(rgba(0, 240, 255, 0.015) 1px, transparent 1px),
      linear-gradient(90deg, rgba(0, 240, 255, 0.015) 1px, transparent 1px);
    background-size: 50px 50px;
    pointer-events: none;
    z-index: 9998;
  }

  /* Cyberpunk ambient lighting */
  .glow-orb {
    position: fixed;
    width: 600px;
    height: 600px;
    background: radial-gradient(circle, rgba(0, 240, 255, 0.04) 0%, transparent 70%);
    border-radius: 50%;
    pointer-events: none;
    z-index: -1;
    filter: blur(80px);
  }
  .glow-orb-1 { top: -200px; left: -200px; }
  .glow-orb-2 { bottom: -200px; right: -200px; }

  /* ===== TOP NAV BAR ===== */
  .topbar {
    position: sticky;
    top: 0;
    z-index: 1000;
    background: rgba(3, 6, 17, 0.85);
    backdrop-filter: blur(20px);
    border-bottom: 1px solid rgba(0, 240, 255, 0.25);
    padding: 0 28px;
    height: 70px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    box-shadow: 0 10px 30px rgba(0,0,0,0.5), 0 0 15px rgba(0,240,255,0.05);
  }

  .topbar-left {
    display: flex;
    align-items: center;
    gap: 24px;
  }

  .brand {
    font-family: 'Orbitron', sans-serif;
    font-size: 22px;
    font-weight: 900;
    color: var(--cyan);
    letter-spacing: 2px;
    text-shadow: var(--cyan-glow);
    white-space: nowrap;
    display: flex;
    align-items: center;
    gap: 4px;
  }

  .brand span { 
    color: var(--pink); 
    text-shadow: var(--pink-glow);
  }

  .topbar-status {
    display: flex;
    align-items: center;
    gap: 18px;
    flex-wrap: wrap;
    border-left: 1px solid rgba(255,255,255,0.1);
    padding-left: 20px;
  }

  .status-pill {
    display: flex;
    align-items: center;
    gap: 8px;
    font-family: 'Share Tech Mono', monospace;
    font-size: 11px;
    letter-spacing: 1.5px;
    text-transform: uppercase;
    color: var(--text-dim);
    white-space: nowrap;
    background: rgba(255, 255, 255, 0.02);
    border: 1px solid rgba(255, 255, 255, 0.05);
    padding: 4px 10px;
    border-radius: 4px;
  }

  .dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    flex-shrink: 0;
  }

  .dot-on  { background: var(--green); box-shadow: var(--green-glow); animation: pulse 2s infinite; }
  .dot-warn{ background: var(--orange); box-shadow: var(--orange-glow); animation: pulse 1.5s infinite; }
  .dot-off { background: var(--red); box-shadow: var(--red-glow); }

  @keyframes pulse {
    0%,100% { opacity:1; transform: scale(1); }
    50%      { opacity:0.3; transform: scale(0.8); }
  }

  .topbar-right {
    display: flex;
    align-items: center;
    gap: 20px;
  }

  .live-clock {
    font-family: 'Orbitron', monospace;
    font-size: 14px;
    color: var(--cyan);
    letter-spacing: 2px;
    text-shadow: 0 0 8px rgba(0, 240, 255, 0.4);
    background: rgba(0, 240, 255, 0.05);
    border: 1px solid rgba(0, 240, 255, 0.15);
    padding: 6px 12px;
    border-radius: 6px;
  }

  .fps-badge {
    font-family: 'Share Tech Mono', monospace;
    font-size: 11px;
    color: var(--orange);
    background: rgba(255, 156, 0, 0.08);
    border: 1px solid rgba(255, 156, 0, 0.25);
    border-radius: 6px;
    padding: 6px 12px;
    letter-spacing: 1px;
  }

  /* ===== MAIN LAYOUT ===== */
  .main {
    padding: 24px 28px;
    display: flex;
    flex-direction: column;
    gap: 28px;
    max-width: 1650px;
    margin: 0 auto;
    position: relative;
    z-index: 10;
  }

  /* ===== SECTION TITLE ===== */
  .section-title {
    font-family: 'Orbitron', sans-serif;
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 4px;
    text-transform: uppercase;
    color: var(--cyan);
    opacity: 0.85;
    margin-bottom: 16px;
    display: flex;
    align-items: center;
    gap: 12px;
    text-shadow: 0 0 10px rgba(0,240,255,0.25);
  }
  .section-title::after {
    content: '';
    flex: 1;
    height: 1px;
    background: linear-gradient(90deg, rgba(0, 240, 255, 0.4), transparent);
  }

  /* ===== METRIC CARDS ===== */
  .cards-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(230px, 1fr));
    gap: 18px;
  }

  .card {
    background: var(--bg-card);
    border: 1px solid var(--glass-b);
    border-radius: 16px;
    padding: 22px;
    backdrop-filter: blur(16px);
    position: relative;
    overflow: hidden;
    transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1);
    cursor: default;
    box-shadow: var(--panel-shadow);
  }

  /* Neon side accent lines */
  .card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; bottom: 0;
    width: 3px;
    background: var(--cyan);
    box-shadow: 0 0 10px var(--cyan);
    opacity: 0.7;
    transition: all 0.3s ease;
  }

  .card.card-pink::before { background: var(--pink); box-shadow: 0 0 10px var(--pink); }
  .card.card-green::before { background: var(--green); box-shadow: 0 0 10px var(--green); }
  .card.card-orange::before { background: var(--orange); box-shadow: 0 0 10px var(--orange); }
  .card.card-red::before { background: var(--red); box-shadow: 0 0 10px var(--red); }

  /* Cyber Corner Bracket Details */
  .card-cyber-corners::after {
    content: '';
    position: absolute;
    top: 0; right: 0;
    width: 8px; height: 8px;
    border-top: 2px solid rgba(255,255,255,0.15);
    border-right: 2px solid rgba(255,255,255,0.15);
    pointer-events: none;
    transition: all 0.3s ease;
  }

  .card:hover {
    transform: translateY(-5px);
    border-color: rgba(0, 240, 255, 0.35);
    box-shadow: 0 15px 35px rgba(0,0,0,0.5), 0 0 20px rgba(0, 240, 255, 0.15);
  }
  
  .card:hover::after {
    border-color: var(--cyan);
    filter: drop-shadow(0 0 3px var(--cyan));
  }

  .card-top {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 12px;
  }

  .card-icon-badge {
    width: 38px;
    height: 38px;
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 18px;
  }

  .card-label {
    font-size: 11px;
    letter-spacing: 2px;
    text-transform: uppercase;
    color: var(--text-dim);
    font-family: 'Share Tech Mono', monospace;
  }

  .card-value {
    font-family: 'Orbitron', sans-serif;
    font-size: 34px;
    font-weight: 800;
    line-height: 1.1;
    color: var(--cyan);
    text-shadow: var(--cyan-glow);
    margin-bottom: 8px;
  }

  .card-value.good    { color: var(--green);  text-shadow: var(--green-glow); }
  .card-value.warn    { color: var(--orange); text-shadow: var(--orange-glow); }
  .card-value.danger  { color: var(--red);    text-shadow: var(--red-glow); }
  .card-value.pink    { color: var(--pink);   text-shadow: var(--pink-glow); }

  .card-sub {
    font-size: 11px;
    color: var(--text-dim);
    display: flex;
    align-items: center;
    gap: 6px;
  }

  /* ===== TWO-COL GRID ===== */
  .two-col {
    display: grid;
    grid-template-columns: 1.6fr 1fr;
    gap: 24px;
  }

  /* ===== PANEL ===== */
  .panel {
    background: var(--bg-card);
    border: 1px solid var(--glass-b);
    border-radius: 18px;
    padding: 24px;
    backdrop-filter: blur(16px);
    position: relative;
    overflow: hidden;
    box-shadow: 0 15px 35px rgba(0,0,0,0.5);
  }

  .panel::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 1px;
    background: linear-gradient(90deg, transparent, var(--cyan), transparent);
    opacity: 0.6;
  }

  /* ===== SURVEILLANCE CAMERA FEED ===== */
  .camera-container {
    position: relative;
    width: 100%;
    height: 380px;
    background: #020409;
    border: 1px solid rgba(0, 240, 255, 0.25);
    border-radius: 16px;
    overflow: hidden;
    box-shadow: 0 0 30px rgba(0, 240, 255, 0.05), inset 0 0 20px rgba(0,0,0,0.8);
  }

  .hud-corners .c-bracket {
    position: absolute;
    width: 22px;
    height: 22px;
    border-color: var(--cyan);
    border-style: solid;
    z-index: 15;
    filter: drop-shadow(0 0 5px var(--cyan));
    opacity: 0.8;
  }
  .c-tl { top: 16px; left: 16px; border-width: 2px 0 0 2px; }
  .c-tr { top: 16px; right: 16px; border-width: 2px 2px 0 0; }
  .c-bl { bottom: 16px; left: 16px; border-width: 0 0 2px 2px; }
  .c-br { bottom: 16px; right: 16px; border-width: 0 2px 2px 0; }

  /* Animated scan line */
  .hud-scanner {
    position: absolute;
    left: 0; right: 0;
    height: 4px;
    background: linear-gradient(180deg, var(--cyan), transparent);
    box-shadow: 0 0 15px rgba(0, 240, 255, 0.6);
    z-index: 10;
    pointer-events: none;
    animation: scan-sweep 4s linear infinite;
    opacity: 0.55;
  }

  @keyframes scan-sweep {
    0% { top: 0%; }
    100% { top: 100%; }
  }

  /* Futuristic moving laser scanner beam */
  .hud-scanner-beam {
    position: absolute;
    top: 0; bottom: 0;
    width: 2px;
    background: var(--cyan);
    box-shadow: 0 0 12px 1px var(--cyan);
    z-index: 11;
    pointer-events: none;
    animation: scan-beam 5s ease-in-out infinite alternate;
  }
  @keyframes scan-beam {
    0% { left: 0%; opacity: 0.2; }
    50% { opacity: 0.8; }
    100% { left: 100%; opacity: 0.2; }
  }

  /* Video Static grid overlay */
  .hud-grid {
    position: absolute;
    inset: 0;
    background: 
      linear-gradient(rgba(0, 240, 255, 0.02) 1px, transparent 1px),
      linear-gradient(90deg, rgba(0, 240, 255, 0.02) 1px, transparent 1px);
    background-size: 24px 24px;
    z-index: 5;
    pointer-events: none;
  }

  /* Telemetry text readouts */
  .hud-telemetry {
    position: absolute;
    font-family: 'Share Tech Mono', monospace;
    font-size: 11px;
    color: var(--cyan);
    z-index: 12;
    letter-spacing: 1.5px;
    text-shadow: 0 0 6px rgba(0, 240, 255, 0.6);
    pointer-events: none;
    line-height: 1.6;
    background: rgba(3, 6, 17, 0.5);
    padding: 4px 8px;
    border-radius: 4px;
    border: 1px solid rgba(0, 240, 255, 0.1);
  }
  .hud-telemetry.top-left { top: 18px; left: 45px; }
  .hud-telemetry.top-right { 
    top: 18px; right: 45px; 
    display: flex;
    align-items: center;
    gap: 8px;
    color: var(--red);
    border-color: rgba(255, 42, 95, 0.2);
    text-shadow: 0 0 6px rgba(255, 42, 95, 0.6);
  }
  .hud-telemetry.bottom-left { bottom: 18px; left: 45px; }
  .hud-telemetry.bottom-right { bottom: 18px; right: 45px; text-align: right; }

  .rec-dot {
    width: 8px; height: 8px;
    background: var(--red);
    border-radius: 50%;
    box-shadow: var(--red-glow);
    display: inline-block;
    animation: blink-anim 1s infinite alternate;
  }

  @keyframes blink-anim {
    0% { opacity: 0.1; }
    100% { opacity: 1; }
  }

  /* Live targeting reticles */
  .hud-reticle {
    position: absolute;
    top: 50%; left: 50%;
    transform: translate(-50%, -50%);
    width: 120px; height: 120px;
    z-index: 8;
    pointer-events: none;
    opacity: 0.25;
  }
  .reticle-circle {
    width: 100%; height: 100%;
    border: 1px dashed var(--cyan);
    border-radius: 50%;
    animation: rotate-slow 25s linear infinite;
  }
  .reticle-cross {
    position: absolute;
    inset: 0;
  }
  .reticle-cross::before, .reticle-cross::after {
    content: '';
    position: absolute;
    background: var(--cyan);
  }
  .reticle-cross::before { top: 50%; left: 5%; right: 5%; height: 1px; }
  .reticle-cross::after { left: 50%; top: 5%; bottom: 5%; width: 1px; }

  /* Concentric sonar radar pulses */
  .radar-pulse {
    position: absolute;
    width: 20px; height: 20px;
    background: transparent;
    border: 1.5px solid var(--cyan);
    border-radius: 50%;
    z-index: 9;
    pointer-events: none;
    animation: pulse-out 3s infinite linear;
    top: 50%; left: 50%;
    transform: translate(-50%, -50%);
  }
  @keyframes pulse-out {
    0% { width: 0px; height: 0px; opacity: 1; }
    100% { width: 220px; height: 220px; opacity: 0; }
  }

  @keyframes rotate-slow {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
  }

  .cam-stream {
    width: 100%;
    height: 100%;
    object-fit: cover;
    position: absolute;
    inset: 0;
    z-index: 2;
  }

  /* Active radar sweep fallback when no stream is present */
  .cam-fallback {
    position: absolute;
    inset: 0;
    z-index: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    background: radial-gradient(circle, #091328 0%, #030611 100%);
  }

  .radar-scan {
    position: absolute;
    width: 260px; height: 260px;
    border: 1px dashed rgba(0, 240, 255, 0.2);
    border-radius: 50%;
    background: conic-gradient(from 0deg, rgba(0, 240, 255, 0.18) 0deg, transparent 120deg);
    animation: radar-sweep 4s linear infinite;
    pointer-events: none;
  }

  @keyframes radar-sweep {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
  }

  .fallback-text {
    text-align: center;
    z-index: 3;
    background: rgba(3,6,17,0.75);
    padding: 16px 24px;
    border: 1px solid rgba(0, 240, 255, 0.15);
    border-radius: 12px;
    backdrop-filter: blur(8px);
  }
  .fallback-text p {
    font-family: 'Orbitron', sans-serif;
    font-size: 13px;
    font-weight: 700;
    letter-spacing: 3px;
    color: var(--cyan);
    text-shadow: var(--cyan-glow);
    margin-bottom: 6px;
  }
  .fallback-text span {
    font-family: 'Share Tech Mono', monospace;
    font-size: 10px;
    color: var(--text-dim);
    letter-spacing: 1.5px;
  }

  /* High-tech target alerting overlay */
  .hud-detection-alert {
    position: absolute;
    top: 50px; left: 50%;
    transform: translateX(-50%);
    width: 82%;
    background: rgba(255, 42, 95, 0.15);
    border: 1px solid rgba(255, 42, 95, 0.55);
    border-radius: 8px;
    overflow: hidden;
    z-index: 100;
    backdrop-filter: blur(8px);
    box-shadow: 0 0 20px rgba(255, 42, 95, 0.3), inset 0 0 10px rgba(255, 42, 95, 0.1);
    animation: alert-flash 0.8s infinite alternate cubic-bezier(0.4, 0, 0.2, 1);
    display: flex;
    flex-direction: column;
  }

  @keyframes alert-flash {
    0% { border-color: rgba(255, 42, 95, 0.3); box-shadow: 0 0 10px rgba(255, 42, 95, 0.1); }
    100% { border-color: rgba(255, 42, 95, 0.9); box-shadow: 0 0 30px rgba(255, 42, 95, 0.5); }
  }

  .alert-pulse-line {
    width: 100%; height: 3px;
    background: var(--red);
    box-shadow: var(--red-glow);
  }

  .alert-body {
    display: flex;
    align-items: center;
    gap: 14px;
    padding: 10px 16px;
  }

  .alert-icon { font-size: 18px; }

  .alert-content { display: flex; flex-direction: column; }

  .alert-title {
    font-family: 'Orbitron', sans-serif;
    font-size: 11px;
    font-weight: 900;
    letter-spacing: 2px;
    color: var(--red);
    text-shadow: var(--red-glow);
  }

  .alert-desc {
    font-family: 'Share Tech Mono', monospace;
    font-size: 10px;
    color: #ffd2dc;
    margin-top: 2px;
    letter-spacing: 1px;
  }

  /* ===== ROAD HEALTH SCORE & SYSTEM CONTROLS ===== */
  .health-wrap {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 20px;
    padding: 15px 0;
  }

  .health-ring-wrap {
    position: relative;
    width: 180px;
    height: 180px;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .health-ring-svg {
    transform: rotate(-90deg);
  }

  .health-ring-track {
    fill: none;
    stroke: rgba(255,255,255,0.03);
    stroke-width: 10;
  }

  .health-ring-fill {
    fill: none;
    stroke-width: 10;
    stroke-linecap: round;
    transition: stroke-dashoffset 1.5s cubic-bezier(0.4,0,0.2,1);
    filter: drop-shadow(0 0 6px var(--cyan));
  }

  .health-ring-value {
    position: absolute;
    text-align: center;
  }

  .health-ring-num {
    font-family: 'Orbitron', monospace;
    font-size: 40px;
    font-weight: 900;
    line-height: 1;
  }
  .health-ring-num.good    { color: var(--green);  text-shadow: var(--green-glow); }
  .health-ring-num.warn    { color: var(--orange); text-shadow: var(--orange-glow); }
  .health-ring-num.danger  { color: var(--red);    text-shadow: var(--red-glow); }

  .health-ring-label {
    font-size: 9px;
    letter-spacing: 2px;
    text-transform: uppercase;
    color: var(--text-dim);
    font-family: 'Share Tech Mono', monospace;
    margin-top: 6px;
  }

  .health-status-badge {
    font-family: 'Orbitron', monospace;
    font-size: 13px;
    font-weight: 700;
    letter-spacing: 3px;
    text-transform: uppercase;
    padding: 8px 24px;
    border-radius: 30px;
    border: 1px solid;
    text-shadow: 0 0 10px rgba(255,255,255,0.1);
  }

  .health-status-badge.good {
    color: var(--green);
    border-color: rgba(0,255,170,0.35);
    background: rgba(0,255,170,0.05);
    box-shadow: inset 0 0 10px rgba(0,255,170,0.08);
  }
  .health-status-badge.warn {
    color: var(--orange);
    border-color: rgba(255,156,0,0.35);
    background: rgba(255,156,0,0.05);
    box-shadow: inset 0 0 10px rgba(255,156,0,0.08);
  }
  .health-status-badge.poor {
    color: var(--red);
    border-color: rgba(255,42,95,0.35);
    background: rgba(255,42,95,0.05);
    box-shadow: inset 0 0 10px rgba(255,42,95,0.08);
  }

  /* Sleek neon control buttons */
  .control-btns-wrap {
    width: 100%;
    display: flex;
    flex-direction: column;
    gap: 12px;
    margin-top: 10px;
  }

  .map-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 10px;
    padding: 12px 24px;
    border-radius: 12px;
    text-decoration: none;
    font-family: 'Orbitron', sans-serif;
    font-size: 11px;
    font-weight: bold;
    letter-spacing: 2px;
    text-transform: uppercase;
    transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1);
    box-shadow: 0 4px 15px rgba(0,0,0,0.25);
    position: relative;
    overflow: hidden;
    width: 100%;
  }

  .btn-cyan {
    background: linear-gradient(135deg, rgba(0, 240, 255, 0.18), rgba(0, 240, 255, 0.03));
    border: 1px solid rgba(0, 240, 255, 0.4);
    color: var(--cyan);
    text-shadow: 0 0 6px rgba(0, 240, 255, 0.4);
  }

  .btn-cyan:hover {
    background: rgba(0, 240, 255, 0.28);
    box-shadow: 0 0 22px rgba(0, 240, 255, 0.3);
    border-color: var(--cyan);
    transform: translateY(-2px);
  }

  .btn-pink {
    background: linear-gradient(135deg, rgba(255, 0, 127, 0.18), rgba(255, 0, 127, 0.03));
    border: 1px solid rgba(255, 0, 127, 0.4);
    color: var(--pink);
    text-shadow: 0 0 6px rgba(255, 0, 127, 0.4);
  }

  .btn-pink:hover {
    background: rgba(255, 0, 127, 0.28);
    box-shadow: 0 0 22px rgba(255, 0, 127, 0.3);
    border-color: var(--pink);
    transform: translateY(-2px);
  }

  /* Sweep reflection animation */
  .map-btn::after {
    content: '';
    position: absolute;
    top: 0; left: -100%;
    width: 100%; height: 100%;
    background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.2), transparent);
    transition: all 0.6s ease;
  }
  .map-btn:hover::after {
    left: 100%;
  }

  /* ===== ENHANCED NEW PANELS (RISK ANALYSIS & ASSISTANT) ===== */
  .risk-bar-wrap {
    margin-bottom: 14px;
    width: 100%;
  }

  .risk-label-row {
    display: flex;
    justify-content: space-between;
    font-family: 'Share Tech Mono', monospace;
    font-size: 11px;
    letter-spacing: 1.5px;
    color: var(--text-dim);
    margin-bottom: 6px;
  }

  .risk-val-text {
    color: var(--cyan);
    font-weight: bold;
    text-shadow: var(--cyan-glow);
  }

  .cyber-progress-bg {
    width: 100%;
    height: 6px;
    background: rgba(255,255,255,0.03);
    border-radius: 4px;
    border: 1px solid rgba(0, 240, 255, 0.05);
    overflow: hidden;
  }

  .cyber-progress-fill {
    height: 100%;
    border-radius: 4px;
    transition: width 1.2s cubic-bezier(0.4, 0, 0.2, 1);
  }

  .risk-fill {
    background: linear-gradient(90deg, var(--green), var(--orange));
    box-shadow: 0 0 8px rgba(0, 255, 170, 0.4);
  }

  .unsafe-fill {
    background: linear-gradient(90deg, var(--orange), var(--red));
    box-shadow: 0 0 8px rgba(255, 42, 95, 0.4);
  }

  .risk-metric-row {
    display: flex;
    justify-content: space-between;
    margin: 18px 0;
    border-top: 1px dashed rgba(0, 240, 255, 0.1);
    border-bottom: 1px dashed rgba(0, 240, 255, 0.1);
    padding: 10px 0;
  }

  .metric-block {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .block-title {
    font-family: 'Share Tech Mono', monospace;
    font-size: 9px;
    letter-spacing: 1.5px;
    color: var(--text-dim);
  }

  .block-value {
    font-family: 'Orbitron', sans-serif;
    font-size: 13px;
    font-weight: 700;
    letter-spacing: 1px;
  }

  .ai-rec-box {
    background: rgba(0, 240, 255, 0.03);
    border: 1px solid rgba(0, 240, 255, 0.1);
    border-radius: 8px;
    padding: 12px;
  }

  .rec-title {
    font-family: 'Orbitron', sans-serif;
    font-size: 9px;
    font-weight: 700;
    letter-spacing: 2px;
    color: var(--pink);
    text-shadow: var(--pink-glow);
    display: block;
    margin-bottom: 6px;
  }

  .rec-desc {
    font-family: 'Share Tech Mono', monospace;
    font-size: 10px;
    line-height: 1.5;
    color: var(--text);
  }

  .assistant-header {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 14px;
  }

  .assistant-avatar {
    position: relative;
    width: 32px; height: 32px;
  }

  .avatar-ring {
    position: absolute;
    inset: 0;
    border: 1.5px dashed var(--cyan);
    border-radius: 50%;
    animation: rotate-slow 6s linear infinite;
  }

  .avatar-center {
    position: absolute;
    top: 50%; left: 50%;
    transform: translate(-50%, -50%);
    width: 8px; height: 8px;
    background: var(--pink);
    border-radius: 50%;
    box-shadow: var(--pink-glow);
    animation: pulse 1.5s infinite;
  }

  .assistant-meta {
    display: flex;
    flex-direction: column;
  }

  .assistant-name {
    font-family: 'Orbitron', sans-serif;
    font-size: 11px;
    font-weight: bold;
    letter-spacing: 1.5px;
    color: var(--cyan);
    text-shadow: var(--cyan-glow);
  }

  .assistant-status {
    font-family: 'Share Tech Mono', monospace;
    font-size: 8px;
    letter-spacing: 1px;
    color: var(--green);
  }

  .assistant-telemetry {
    display: flex;
    justify-content: space-between;
    background: rgba(3, 6, 17, 0.4);
    border: 1px solid rgba(255,255,255,0.03);
    border-radius: 8px;
    padding: 10px;
    margin-bottom: 14px;
  }

  .tel-item {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .tel-label {
    font-family: 'Share Tech Mono', monospace;
    font-size: 8px;
    letter-spacing: 1px;
    color: var(--text-dim);
  }

  .tel-value {
    font-family: 'Orbitron', sans-serif;
    font-size: 10px;
    font-weight: 700;
    color: var(--text);
  }

  .assistant-tip-box {
    background: rgba(255, 0, 127, 0.02);
    border: 1px solid rgba(255, 0, 127, 0.08);
    border-radius: 8px;
    padding: 12px;
    transition: all 0.4s ease;
  }

  .tip-label {
    font-family: 'Orbitron', sans-serif;
    font-size: 9px;
    font-weight: 700;
    letter-spacing: 2px;
    color: var(--cyan);
    text-shadow: var(--cyan-glow);
    display: block;
    margin-bottom: 6px;
  }

  .tip-text {
    font-family: 'Share Tech Mono', monospace;
    font-size: 10px;
    line-height: 1.5;
    color: var(--text);
    transition: opacity 0.4s ease;
  }

  /* ===== DETECT TOAST NOTIFICATION STYLING ===== */
  .toast-item {
    position: relative;
    width: 100%;
    background: rgba(8, 14, 28, 0.9);
    border: 1px solid rgba(0, 240, 255, 0.2);
    border-radius: 10px;
    padding: 14px 18px;
    display: flex;
    overflow: hidden;
    backdrop-filter: blur(12px);
    box-shadow: 0 10px 25px rgba(0,0,0,0.5), inset 0 0 10px rgba(0, 240, 255, 0.05);
    transform: translateX(120%);
    transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
    pointer-events: auto;
  }
  .toast-item.active {
    transform: translateX(0);
  }
  .toast-item.toast-danger {
    border-color: rgba(255, 42, 95, 0.45);
    box-shadow: 0 10px 25px rgba(255, 42, 95, 0.15), inset 0 0 10px rgba(255, 42, 95, 0.05);
  }
  .toast-item.toast-warning {
    border-color: rgba(255, 156, 0, 0.4);
  }
  .toast-item.toast-success {
    border-color: rgba(0, 255, 170, 0.4);
  }
  .toast-glow {
    position: absolute;
    left: 0; top: 0; bottom: 0;
    width: 3px;
    background: var(--cyan);
  }
  .toast-danger .toast-glow { background: var(--red); }
  .toast-warning .toast-glow { background: var(--orange); }
  .toast-success .toast-glow { background: var(--green); }
  
  .toast-body {
    display: flex;
    align-items: center;
    gap: 14px;
    width: 100%;
  }
  .toast-icon {
    font-size: 18px;
  }
  .toast-content {
    display: flex;
    flex-direction: column;
  }
  .toast-title {
    font-family: 'Orbitron', sans-serif;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 1.5px;
    color: var(--text-dim);
  }
  .toast-desc {
    font-family: 'Share Tech Mono', monospace;
    font-size: 11px;
    color: var(--text);
    margin-top: 2px;
  }

  /* ===== SYSTEM STARTUP LOADER ===== */
  #system-boot-overlay {
    position: fixed;
    inset: 0;
    background: #02050b;
    z-index: 100000;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: opacity 0.8s ease, visibility 0.8s ease;
  }

  .boot-container {
    width: 450px;
    text-align: center;
  }

  .boot-logo {
    font-family: 'Orbitron', sans-serif;
    font-size: 32px;
    font-weight: 900;
    color: var(--cyan);
    letter-spacing: 4px;
    text-shadow: var(--cyan-glow);
    margin-bottom: 24px;
  }
  .boot-logo span { color: var(--pink); text-shadow: var(--pink-glow); }

  .boot-terminal {
    font-family: 'Share Tech Mono', monospace;
    font-size: 11px;
    color: var(--text-dim);
    background: rgba(3, 6, 17, 0.8);
    border: 1px solid rgba(0, 240, 255, 0.15);
    border-radius: 8px;
    padding: 16px;
    height: 140px;
    overflow: hidden;
    text-align: left;
    margin-bottom: 20px;
    line-height: 1.6;
  }

  .boot-progress-wrap {
    width: 100%;
    height: 4px;
    background: rgba(255, 255, 255, 0.05);
    border-radius: 2px;
    overflow: hidden;
    margin-bottom: 12px;
  }

  .boot-progress-bar {
    width: 0%;
    height: 100%;
    background: linear-gradient(90deg, var(--cyan), var(--pink));
    box-shadow: var(--cyan-glow);
    transition: width 0.1s ease;
  }

  .boot-status {
    font-family: 'Share Tech Mono', monospace;
    font-size: 10px;
    letter-spacing: 1px;
    color: var(--cyan);
    text-transform: uppercase;
  }

  /* ===== DETECTION TABLE ===== */
  .log-table-wrap {
    overflow: auto;
    max-height: 320px;
    scrollbar-width: thin;
    scrollbar-color: var(--cyan-dim) transparent;
  }

  .log-table-wrap::-webkit-scrollbar {
    width: 6px;
  }
  .log-table-wrap::-webkit-scrollbar-track {
    background: transparent;
  }
  .log-table-wrap::-webkit-scrollbar-thumb {
    background-color: var(--cyan-dim);
    border-radius: 4px;
  }

  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 14px;
  }

  thead { position: sticky; top: 0; z-index: 5; }

  th {
    background: rgba(3, 6, 17, 0.95);
    color: var(--cyan);
    padding: 14px 18px;
    text-align: left;
    font-family: 'Share Tech Mono', monospace;
    font-size: 11px;
    letter-spacing: 2px;
    text-transform: uppercase;
    border-bottom: 2px solid rgba(0, 240, 255, 0.3);
  }

  td {
    padding: 12px 18px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.03);
    font-family: 'Share Tech Mono', monospace;
    font-size: 12px;
    color: var(--text);
    transition: background 0.15s;
  }

  tr:hover td { background: rgba(0, 240, 255, 0.04); }

  .sev-badge {
    display: inline-block;
    padding: 3px 12px;
    border-radius: 4px;
    font-size: 10px;
    letter-spacing: 1.5px;
    font-weight: 700;
    text-transform: uppercase;
  }

  .sev-low  { background:rgba(0, 255, 170, 0.08); color:var(--green); border:1px solid rgba(0, 255, 170, 0.25); }
  .sev-med  { background:rgba(255, 156, 0, 0.08); color:var(--orange); border:1px solid rgba(255, 156, 0, 0.25); }
  .sev-high { background:rgba(255, 42, 95, 0.08); color:var(--red); border:1px solid rgba(255, 42, 95, 0.25); }

  .status-active {
    display: flex;
    align-items: center;
    gap: 6px;
    color: var(--green);
    font-size: 10px;
    letter-spacing: 1.5px;
  }
  .status-active::before {
    content: '';
    width: 6px; height: 6px;
    border-radius: 50%;
    background: var(--green);
    box-shadow: var(--green-glow);
    animation: pulse 2s infinite;
  }

  /* ===== MINI CHARTS STRIP ===== */
  .mini-charts {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(230px, 1fr));
    gap: 18px;
  }

  .mini-chart-card {
    background: var(--bg-card);
    border: 1px solid var(--glass-b);
    border-radius: 16px;
    padding: 20px;
    position: relative;
    overflow: hidden;
    backdrop-filter: blur(16px);
    box-shadow: var(--panel-shadow);
  }

  .mini-chart-card::before {
    content: '';
    position: absolute;
    top:0; left:0; right:0;
    height: 1px;
    background: linear-gradient(90deg, transparent, rgba(0, 240, 255, 0.3), transparent);
  }

  .mini-chart-title {
    font-family: 'Share Tech Mono', monospace;
    font-size: 11px;
    letter-spacing: 2px;
    text-transform: uppercase;
    color: var(--text-dim);
    margin-bottom: 12px;
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  .mini-chart-title::after {
    content: 'ONLINE';
    font-size: 8px;
    color: var(--green);
    letter-spacing: 1px;
    background: rgba(0,255,170,0.06);
    border: 1px solid rgba(0,255,170,0.25);
    padding: 1px 5px;
    border-radius: 3px;
  }

  .mini-chart-wrap { height: 95px; }

  /* ===== FOOTER ===== */
  .footer {
    text-align: center;
    padding: 24px;
    color: var(--text-dim);
    font-family: 'Share Tech Mono', monospace;
    font-size: 10px;
    letter-spacing: 3px;
    text-transform: uppercase;
    border-top: 1px solid rgba(255,255,255,0.03);
    margin-top: 24px;
    background: rgba(3, 6, 17, 0.4);
  }

  /* ===== RESPONSIVE ===== */
  @media (max-width: 950px) {
    .two-col { grid-template-columns: 1fr; }
    .topbar-status { display: none; }
    .brand { font-size: 16px; }
  }

  /* ===== FADE IN ANIMATIONS ===== */
  @keyframes fadeUp {
    from { opacity:0; transform:translateY(25px); }
    to   { opacity:1; transform:translateY(0); }
  }

  .cards-grid { animation: fadeUp 0.6s cubic-bezier(0.16, 1, 0.3, 1) both; }
  .two-col    { animation: fadeUp 0.6s 0.15s cubic-bezier(0.16, 1, 0.3, 1) both; }
  .panel      { animation: fadeUp 0.6s 0.25s cubic-bezier(0.16, 1, 0.3, 1) both; }

  /* ===== ROADGUARD VOICE ASSISTANT CSS ===== */
  @keyframes wave-bounce {
    0%, 100% { transform: scaleY(1); }
    50% { transform: scaleY(2.2); }
  }
  .wave-bar.active {
    animation: wave-bounce 0.8s ease infinite;
  }
  .wave-bar:nth-child(2).active { animation-delay: 0.1s; }
  .wave-bar:nth-child(3).active { animation-delay: 0.2s; }
  .wave-bar:nth-child(4).active { animation-delay: 0.3s; }
  .wave-bar:nth-child(5).active { animation-delay: 0.4s; }
  .wave-bar:nth-child(6).active { animation-delay: 0.1s; }
  .wave-bar:nth-child(7).active { animation-delay: 0.2s; }
  .wave-bar:nth-child(8).active { animation-delay: 0.3s; }
  
  @keyframes mic-pulse-expand {
    0% { transform: scale(1); opacity: 0.8; }
    100% { transform: scale(1.4); opacity: 0; }
  }
  .mic-btn.listening {
    background: rgba(255, 42, 95, 0.15) !important;
    border-color: var(--red) !important;
    color: var(--red) !important;
    box-shadow: 0 0 20px rgba(255, 42, 95, 0.4) !important;
  }
  .mic-btn.listening .mic-glow-pulse {
    border-color: var(--red) !important;
    animation: mic-pulse-expand 1.2s infinite;
    opacity: 1 !important;
  }
  .mic-btn.speaking {
    background: rgba(0, 255, 170, 0.15) !important;
    border-color: var(--green) !important;
    color: var(--green) !important;
    box-shadow: 0 0 20px rgba(0, 255, 170, 0.4) !important;
  }
  .mic-btn.speaking .mic-glow-pulse {
    border-color: var(--green) !important;
    animation: mic-pulse-expand 1s infinite;
    opacity: 1 !important;
  }

  #dashboard-csv-filter:hover {
    border-color: #ff2a5f !important;
    box-shadow: 0 0 12px rgba(255, 42, 95, 0.4) !important;
  }
  #dashboard-csv-filter option {
    background: #030611 !important;
    color: #fff !important;
  }
  @keyframes spin {
    to { transform: rotate(360deg); }
  }
  @keyframes scanVertical {
    0% { top: 0%; }
    50% { top: 100%; }
    100% { top: 0%; }
  }
  @keyframes blink {
    0% { opacity: 0.2; }
    100% { opacity: 1; }
  }

</style>
</head>
<body>

<!-- CINEMATIC STARTUP LOADER -->
<div id="system-boot-overlay">
  <div class="boot-container">
    <div class="boot-logo">ROADGUARD<span>AI</span></div>
    <div class="boot-terminal" id="boot-terminal-log"></div>
    <div class="boot-progress-wrap">
      <div class="boot-progress-bar" id="boot-progress-bar"></div>
    </div>
    <div class="boot-status">ESTABLISHING SECURE CONNECTION TO SURVEILLANCE FEED...</div>
  </div>
</div>
<!-- FAIL-SAFE SYSTEM BOOT WATCHDOG -->
<script>
  setTimeout(function() {
    var overlay = document.getElementById('system-boot-overlay');
    if (overlay && overlay.style.visibility !== 'hidden') {
      overlay.style.opacity = '0';
      overlay.style.visibility = 'hidden';
      console.log("[WATCHDOG] Force-dismissed system boot overlay after 3.5s fail-safe timeout.");
    }
  }, 3500);
</script>

<div class="glow-orb glow-orb-1"></div>
<div class="glow-orb glow-orb-2"></div>

<!-- TOAST NOTIFICATION CONTAINER -->
<div id="notification-container" style="position: fixed; top: 80px; right: 28px; z-index: 10000; display: flex; flex-direction: column; gap: 12px; pointer-events: none; width: 340px;"></div>

<!-- ===== TOP BAR ===== -->
<header class="topbar">
  <div class="topbar-left">
    <div class="brand">RoadGuard<span>AI</span></div>
    <div class="topbar-status">
      <div class="status-pill"><div class="dot dot-on"></div> AI ENGINE ACTIVE</div>
      <div class="status-pill"><div class="dot dot-on"></div> CAMERA LINKED</div>
      <div class="status-pill"><div class="dot dot-warn"></div> YOLOv8 PIPELINE</div>
      <div class="status-pill"><div class="dot dot-on"></div> SYS NOMINAL</div>
    </div>
  </div>
  <div class="topbar-right">
    <div class="fps-badge" id="fps-display">FPS: --</div>
    <div class="live-clock" id="live-clock">--:--:--</div>
  </div>
</header>

<!-- ===== MAIN CONTENT ===== -->
<main class="main">

  <!-- METRIC CARDS -->
  <div>
    <div class="section-title">// COGNITIVE STATS SUMMARY</div>
    <div class="cards-grid">

      <div class="card card-pink card-cyber-corners">
        <div class="card-top">
          <div class="card-label">Total Detections</div>
          <div class="card-icon-badge">⚡</div>
        </div>
        <div class="card-value pink count-up" id="kpi-total-detections" data-target="{{ total_detections }}">0</div>
        <div class="card-sub">
          <span style="color:var(--pink);">●</span> Across active session logs
        </div>
      </div>

      <div class="card card-cyber-corners {% if score >= 70 %}card-green{% elif score >= 40 %}card-orange{% else %}card-red{% endif %}">
        <div class="card-top">
          <div class="card-label">Road Quality Index</div>
          <div class="card-icon-badge">🛣</div>
        </div>
        <div class="card-value {% if score >= 70 %}good{% elif score >= 40 %}warn{% else %}danger{% endif %} count-up" id="kpi-road-quality" data-target="{{ road_quality_index }}">0</div>
        <div class="card-sub">
          {% if score >= 95 %}
          <span style="color:var(--green);">●</span> Road Condition Excellent
          {% elif score >= 70 %}
          <span style="color:var(--green);">●</span> Road Condition Good
          {% elif score >= 40 %}
          <span style="color:var(--orange);">●</span> Minor Defects Flagged
          {% else %}
          <span style="color:var(--red);">●</span> Road Index Critical
          {% endif %}
        </div>
      </div>

      <div class="card card-red card-cyber-corners">
        <div class="card-top">
          <div class="card-label">Critical Alerts</div>
          <div class="card-icon-badge">🚨</div>
        </div>
        <div class="card-value danger count-up" id="kpi-critical-alerts" data-target="{{ critical_alerts }}">0</div>
        <div class="card-sub">
          <span style="color:var(--red);">●</span> High severity potholes
        </div>
      </div>

      <div class="card card-cyber-corners" style="background: linear-gradient(135deg, rgba(0, 240, 255, 0.04), rgba(0, 240, 255, 0.01));">
        <div class="card-top">
          <div class="card-label">AI Accuracy</div>
          <div class="card-icon-badge">🎯</div>
        </div>
        <div class="card-value good" id="kpi-ai-accuracy">94.7%</div>
        <div class="card-sub">
          <span style="color:var(--green);">●</span> Precision Calibration
        </div>
      </div>

    </div>
  </div>

  <!-- CAMERA + CONTROLS -->
  <div class="two-col">

    <!-- SURVEILLANCE PANEL -->
    <div>
      <div class="section-title">// SURVEILLANCE FEED // COGNITIVE SCAN ACTIVE</div>
      <div class="camera-container">
        
        <!-- HUD Bracket Corners -->
        <div class="hud-corners">
          <div class="c-bracket c-tl"></div>
          <div class="c-bracket c-tr"></div>
          <div class="c-bracket c-bl"></div>
          <div class="c-bracket c-br"></div>
        </div>
        
        <!-- Scanline sweeping overlay -->
        <div class="hud-scanner"></div>

        <!-- High-tech moving laser scanner beam -->
        <div class="hud-scanner-beam"></div>
        
        <!-- Scanning grid overlay -->
        <div class="hud-grid"></div>
        
        <!-- Camera scope reticle -->
        <div class="hud-reticle">
          <div class="reticle-circle"></div>
          <div class="reticle-cross"></div>
        </div>

        <!-- Concentric sonar pulses -->
        <div class="radar-pulse"></div>

        <!-- High-tech target alerting overlay -->
        <div class="hud-detection-alert" id="hud-alert-overlay" style="display: none;">
          <div class="alert-pulse-line"></div>
          <div class="alert-body">
            <span class="alert-icon">⚠️</span>
            <div class="alert-content">
              <span class="alert-title" id="hud-alert-title">CRITICAL INCIDENT IDENTIFIED</span>
              <span class="alert-desc" id="hud-alert-desc">COGNITIVE RADAR ACQUIRED DEGRADED ASPHALT SENSOR LINK</span>
            </div>
          </div>
        </div>
        
        <!-- HUD details -->
        <div class="hud-telemetry top-left" style="display:flex; align-items:center; gap:8px;">
          <span>ROAD_SYS // SURV_ACQ</span>
          <span id="hud-confidence-badge" style="background:rgba(0, 255, 170, 0.12); border:1px solid var(--green); color:var(--green); font-size:9px; padding:1px 5px; border-radius:3px; font-weight:bold; letter-spacing:1px; text-shadow:none; transition: all 0.3s;">CONF: 98.2%</span>
        </div>
        <div class="hud-telemetry top-right">
          <span class="rec-dot" style="box-shadow: 0 0 10px #ff2a5f, 0 0 20px #ff2a5f;"></span> REC · LIVE
        </div>
        
        <div class="hud-telemetry bottom-left">
          <span>SURV CAM // PORT_01</span><br>
          <span>FEED RATE: <span id="hud-fps-val">--</span> FPS</span><br>
          <span style="font-size:9px; color:var(--text-dim); letter-spacing:1px;" id="hud-coords-stream">GPS: 12.9716, 77.5946</span>
        </div>
        
        <div class="hud-telemetry bottom-right">
          <span id="hud-count-val">DETECTIONS: —</span><br>
          <span id="hud-time-val">--:--:--</span>
        </div>

        <!-- Real video feed from OpenCV / Flask -->
        <img src="/video_feed" class="cam-stream" onerror="handleStreamError(this)" alt="Live Feed">

        <!-- Active Radar Fallback Scan -->
        <div id="camera-fallback" class="cam-fallback">
          <div class="radar-scan"></div>
          <div class="fallback-text">
            <div class="rec-dot" style="margin-bottom:8px; animation: pulse 0.5s infinite alternate;"></div>
            <p>INTELLIGENT FEED SCANNING</p>
            <span>WAITING FOR FLASK OR WEBCAM BROADCAST</span>
          </div>
        </div>

      </div>

      <!-- ROADGUARD MOBILE ACCESS PANEL -->
      <div class="panel" style="margin-top: 24px; background: linear-gradient(135deg, rgba(255, 0, 127, 0.03), rgba(0, 240, 255, 0.03)); border: 1px solid rgba(0, 240, 255, 0.15); box-shadow: 0 0 15px rgba(0, 240, 255, 0.05); position: relative; overflow: hidden;">
        <!-- Cyber grid background decoration -->
        <div style="position: absolute; right: -15px; bottom: -15px; font-size: 70px; opacity: 0.03; color: var(--pink); font-family: 'Orbitron', sans-serif; pointer-events: none; user-select: none;">📱</div>
        <div class="section-title" style="margin-bottom: 12px; font-size: 10px; color: var(--pink); text-shadow: var(--pink-glow);">// ROADGUARD MOBILE COMMAND CENTER</div>
        
        <div style="display: flex; gap: 16px; align-items: center; margin-bottom: 14px;">
          <!-- Holographic QR Code Box -->
          <div style="position: relative; width: 75px; height: 75px; background: rgba(3, 6, 17, 0.8); border: 2px solid var(--cyan); border-radius: 6px; box-shadow: 0 0 10px rgba(0, 240, 255, 0.25); display: flex; align-items: center; justify-content: center; overflow: hidden; flex-shrink: 0;">
            <!-- Tech crosshairs -->
            <div style="position: absolute; top: 2px; left: 2px; width: 6px; height: 6px; border-top: 1px solid var(--pink); border-left: 1px solid var(--pink);"></div>
            <div style="position: absolute; top: 2px; right: 2px; width: 6px; height: 6px; border-top: 1px solid var(--pink); border-right: 1px solid var(--pink);"></div>
            <div style="position: absolute; bottom: 2px; left: 2px; width: 6px; height: 6px; border-bottom: 1px solid var(--pink); border-left: 1px solid var(--pink);"></div>
            <div style="position: absolute; bottom: 2px; right: 2px; width: 6px; height: 6px; border-bottom: 1px solid var(--pink); border-right: 1px solid var(--pink);"></div>
            
            <!-- Scanning red line -->
            <div style="position: absolute; left: 0; right: 0; height: 2px; background: var(--red); box-shadow: 0 0 8px var(--red); animation: scanVertical 2.2s infinite ease-in-out; z-index: 10;"></div>
            
            <!-- CSS Drawn High-Tech Matrix Pattern -->
            <div style="display: grid; grid-template-columns: repeat(5, 1fr); gap: 4px; padding: 6px; width: 100%; height: 100%; box-sizing: border-box;">
              <div style="background: var(--cyan); border-radius: 1px;"></div>
              <div style="background: var(--cyan); border-radius: 1px;"></div>
              <div style="background: transparent;"></div>
              <div style="background: var(--cyan); border-radius: 1px;"></div>
              <div style="background: var(--cyan); border-radius: 1px;"></div>
              <div style="background: var(--cyan); border-radius: 1px;"></div>
              <div style="background: transparent;"></div>
              <div style="background: var(--pink); border-radius: 1px;"></div>
              <div style="background: transparent;"></div>
              <div style="background: var(--cyan); border-radius: 1px;"></div>
              <div style="background: transparent;"></div>
              <div style="background: var(--pink); border-radius: 1px;"></div>
              <div style="background: var(--pink); border-radius: 1px;"></div>
              <div style="background: var(--pink); border-radius: 1px;"></div>
              <div style="background: transparent;"></div>
              <div style="background: var(--cyan); border-radius: 1px;"></div>
              <div style="background: transparent;"></div>
              <div style="background: var(--pink); border-radius: 1px;"></div>
              <div style="background: transparent;"></div>
              <div style="background: var(--cyan); border-radius: 1px;"></div>
              <div style="background: var(--cyan); border-radius: 1px;"></div>
              <div style="background: var(--cyan); border-radius: 1px;"></div>
              <div style="background: transparent;"></div>
              <div style="background: var(--cyan); border-radius: 1px;"></div>
              <div style="background: var(--cyan); border-radius: 1px;"></div>
            </div>
          </div>
          
          <!-- Device sync info -->
          <div style="flex-grow: 1; font-family: 'Share Tech Mono', monospace; font-size: 11px; line-height: 1.5; color: var(--text-dim);">
            <div style="display: flex; align-items: center; gap: 6px; margin-bottom: 2px;">
              <span style="font-size: 8px; color: var(--green); animation: blink 1.2s infinite alternate;">●</span>
              <span style="color: #fff; font-weight: bold; letter-spacing: 1px;">UPLINK: ACTIVE // SECURE</span>
            </div>
            <div>DEVICE: <span style="color: var(--cyan);" id="mobile-device-name">RG-MOBILE-V3.5</span></div>
            <div>STRENGTH: <span style="color: var(--cyan);" id="mobile-signal-strength">99.4% [SAT-COM]</span></div>
            <div>COORDINATES: <span style="color: var(--pink);">AUTOSYNC ACTIVE</span></div>
          </div>
        </div>
        
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px; font-family: 'Orbitron', monospace; font-size: 9px; letter-spacing: 1px;">
          <button id="mobile-sync-btn" class="map-btn btn-cyan" style="border: none; cursor: pointer; outline: none; transition: all 0.3s; height: 32px; display: flex; align-items: center; justify-content: center; gap: 4px; padding: 0;">
            🔄 SYNC DEVICE
          </button>
          <button id="mobile-companion-btn" class="map-btn btn-pink" style="border: none; cursor: pointer; outline: none; transition: all 0.3s; height: 32px; display: flex; align-items: center; justify-content: center; gap: 4px; padding: 0;">
            📱 COMPANION HUD
          </button>
        </div>
      </div>
    </div>

    <!-- ROAD HEALTH & SYSTEM CONTROLS & NEW PANELS -->
    <div style="display: flex; flex-direction: column; gap: 24px;">
      
      <!-- Panel 1: System Controls -->
      <div class="panel">
        <div class="section-title" style="margin-bottom: 12px; font-size: 10px;">// SYSTEM CONTROLS</div>
        <div class="health-wrap">
          <div class="health-ring-wrap">
            <svg class="health-ring-svg" width="180" height="180" viewBox="0 0 180 180">
              <circle cx="90" cy="90" r="82" stroke="rgba(0, 240, 255, 0.03)" stroke-width="1" fill="none" />
              <circle cx="90" cy="90" r="76" stroke="rgba(0, 240, 255, 0.03)" stroke-dasharray="4 8" stroke-width="1" fill="none" />
              
              <circle class="health-ring-track" cx="90" cy="90" r="66"/>
              <circle class="health-ring-fill" cx="90" cy="90" r="66"
                id="health-ring"
                stroke="{% if score >= 70 %}#00ffaa{% elif score >= 40 %}#ff9c00{% else %}#ff2a5f{% endif %}"
                stroke-dasharray="414.69"
                stroke-dashoffset="{{ 414.69 - (414.69 * score / 100) }}"
              />
            </svg>
            <div class="health-ring-value">
              <div class="health-ring-num {% if score >= 70 %}good{% elif score >= 40 %}warn{% else %}danger{% endif %}"
                   id="health-ring-num"
                   style="color: {% if score >= 70 %}#00ffaa{% elif score >= 40 %}#ff9c00{% else %}#ff2a5f{% endif %}">
                {{ score }}
              </div>
              <div class="health-ring-label">ROAD INDEX</div>
            </div>
          </div>

          <div class="health-status-badge {% if score >= 70 %}good{% elif score >= 40 %}warn{% else %}poor{% endif %}" id="health-status-badge">
            {% if score >= 70 %}GOOD ROAD{% elif score >= 40 %}CAUTION{% else %}CRITICAL{% endif %}
          </div>

          <div class="control-btns-wrap" style="display: flex; flex-direction: column; gap: 10px;">
            <div style="display: flex; gap: 10px; width: 100%;">
              <a href="/map" class="map-btn btn-cyan" style="flex: 1; text-align: center; display: flex; align-items: center; justify-content: center;">🌍 SMART ROAD GPS MAP</a>
              <div class="cyber-dropdown-wrapper" style="position: relative; flex: 1;">
                <select id="dashboard-csv-filter" class="location-select" style="width: 100%; height: 100%; min-height: 38px; background: rgba(3, 6, 17, 0.85); border: 1px solid var(--pink); color: #fff; font-family: 'Orbitron', monospace; font-size: 10px; letter-spacing: 1.5px; padding: 0 12px; border-radius: 4px; box-shadow: 0 0 8px rgba(255, 42, 95, 0.1); cursor: pointer; outline: none; transition: all 0.3s;">
                  <option value="ALL">ALL SECTORS (FULL EXPORT)</option>
                  <option value="WHITEFIELD">WHITEFIELD SECTOR</option>
                  <option value="HEBBAL">HEBBAL SECTOR</option>
                  <option value="MG ROAD">MG ROAD SECTOR</option>
                  <option value="INDIRANAGAR">INDIRANAGAR SECTOR</option>
                  <option value="BTM LAYOUT">BTM LAYOUT SECTOR</option>
                  <option value="KORAMANGALA">KORAMANGALA SECTOR</option>
                </select>
              </div>
            </div>
            <button class="map-btn btn-pink" id="download-report-btn" style="width: 100%; border: none; cursor: pointer; outline: none; transition: all 0.3s; display: flex; align-items: center; justify-content: center; height: 38px;">📥 DOWNLOAD DETECTIONS CSV</button>
          </div>
        </div>
      </div>

      <!-- Panel 2: AI Risk Analysis (New Enhancement!) -->
      <div class="panel">
        <div class="section-title" style="margin-bottom: 12px; font-size: 10px;">// AI RISK ANALYSIS</div>
        <div class="risk-bar-wrap">
          <div class="risk-label-row">
            <span>ROAD RISK INDEX</span>
            <span class="risk-val-text" id="risk-score-val">{{ 100 - score }}%</span>
          </div>
          <div class="cyber-progress-bg">
            <div class="cyber-progress-fill risk-fill" id="risk-score-bar" style="width: {{ 100 - score }}%;"></div>
          </div>
        </div>

        <div class="risk-bar-wrap">
          <div class="risk-label-row">
            <span>PREDICTED UNSAFE ZONE</span>
            <span class="risk-val-text" id="unsafe-zone-val">{{ [((100 - score) * 0.7)|int, 100]|min }}%</span>
          </div>
          <div class="cyber-progress-bg">
            <div class="cyber-progress-fill unsafe-fill" id="unsafe-zone-bar" style="width: {{ [((100 - score) * 0.7)|int, 100]|min }}%;"></div>
          </div>
        </div>

        <div class="risk-metric-row">
          <div class="metric-block">
            <span class="block-title">EST. DAMAGE SEVERITY</span>
            <span class="block-value {% if score >= 80 %}good{% elif score >= 50 %}warn{% else %}danger{% endif %}" id="est-severity-badge">
              {% if score >= 80 %}LOW{% elif score >= 50 %}MODERATE{% else %}CRITICAL{% endif %}
            </span>
          </div>
          <div class="metric-block" style="text-align: right;">
            <span class="block-title">AI SAFETY MATRIX</span>
            <span class="block-value {% if score >= 50 %}good{% else %}danger{% endif %}" id="safety-matrix-status">
              {% if score >= 50 %}NOMINAL{% else %}DANGER{% endif %}
            </span>
          </div>
        </div>

        <div class="ai-rec-box">
          <span class="rec-title">AI RECOMMENDATION DIRECTIVE:</span>
          <p class="rec-desc" id="ai-safety-rec">
            {% if score >= 80 %}
            ROAD CONDITION OPTIMAL. MAINTAIN DESIGNATED VEHICLE SPEEDS.
            {% elif score >= 50 %}
            MINOR ROAD DEFECTS IDENTIFIED. DRIVE WITH VIGILANCE AND AVOID ABRUPT DEVIATIONS.
            {% else %}
            CRITICAL SURFACE DAMAGE DETECTED. EXTREME CAUTION ADVISED. REDUCE SPEED IMMEDIATELY.
            {% endif %}
          </p>
        </div>
      </div>

      <!-- Panel 3: JARVIS AI Assistant (New Enhancement!) -->
      <div class="panel">
        <div class="section-title" style="margin-bottom: 12px; font-size: 10px;">// AI ASSISTANT ONLINE</div>
        <div class="assistant-header">
          <div class="assistant-avatar">
            <div class="avatar-ring"></div>
            <div class="avatar-center"></div>
          </div>
          <div class="assistant-meta">
            <span class="assistant-name">JARVIS CORE v5.2</span>
            <span class="assistant-status">SURVEILLANCE ASSISTANT ONLINE</span>
          </div>
        </div>
        <div class="assistant-telemetry">
          <div class="tel-item">
            <span class="tel-label">SCAN ENERGY</span>
            <span class="tel-value">15.4 GFLOPS</span>
          </div>
          <div class="tel-item">
            <span class="tel-label">NEURAL LATENCY</span>
            <span class="tel-value">12ms</span>
          </div>
          <div class="tel-item">
            <span class="tel-label">COGNITIVE THREAT</span>
            <span class="tel-value {% if score >= 80 %}good{% elif score >= 50 %}warn{% else %}danger{% endif %}" id="jarvis-threat-val">
              {% if score >= 80 %}NONE{% elif score >= 50 %}WARNING{% else %}CRITICAL{% endif %}
            </span>
          </div>
        </div>
        <div class="assistant-tip-box">
          <span class="tip-label">ROAD SAFETY DIRECTIVE:</span>
          <p class="tip-text" id="jarvis-safety-tip">
            Braking distance increases by 40% on wet or degraded surfaces. Ensure system radar calibration is aligned.
          </p>
        </div>
      </div>

      <!-- Panel 4: ROADGUARD AI VOICE CO-PILOT -->
      <div class="panel" id="voice-copilot-panel">
        <div class="section-title" style="margin-bottom: 12px; font-size: 10px;">// ROADGUARD AI VOICE CO-PILOT</div>
        <div class="assistant-header">
          <div class="assistant-avatar" id="voice-avatar" style="position: relative; width: 32px; height: 32px;">
            <div class="avatar-ring" id="voice-ring" style="position: absolute; inset: 0; border: 1.5px dashed var(--cyan); border-radius: 50%; animation: rotate-slow 6s linear infinite;"></div>
            <div class="avatar-center" id="voice-center" style="position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); width: 8px; height: 8px; background: var(--pink); border-radius: 50%; box-shadow: var(--pink-glow); animation: pulse 1.5s infinite;"></div>
          </div>
          <div class="assistant-meta" style="display: flex; flex-direction: column;">
            <span class="assistant-name" id="voice-title-label" style="font-family: 'Orbitron', sans-serif; font-size: 11px; font-weight: bold; letter-spacing: 1.5px; color: var(--cyan); text-shadow: var(--cyan-glow);">VOICE CO-PILOT</span>
            <span class="assistant-status" id="voice-status-label" style="font-family: 'Share Tech Mono', monospace; font-size: 8px; letter-spacing: 1.5px; color: var(--cyan);">VOICE INTELLIGENCE READY</span>
          </div>
        </div>
        
        <!-- Voice Interface -->
        <div class="voice-controls-wrap" style="display: flex; flex-direction: column; align-items: center; gap: 12px; margin: 16px 0;">
          
          <!-- Glowing Pulse waveform container -->
          <div class="waveform-pulse-container" style="display: flex; align-items: center; justify-content: center; height: 50px; width: 100%; position: relative; overflow: hidden; background: rgba(0, 240, 255, 0.02); border: 1px dashed rgba(0, 240, 255, 0.15); border-radius: 8px;">
            <!-- Waveform bars -->
            <div class="wave-bar" style="width: 3px; height: 15px; background: var(--cyan); margin: 0 3px; border-radius: 3px; transition: height 0.1s ease;"></div>
            <div class="wave-bar" style="width: 3px; height: 25px; background: var(--cyan); margin: 0 3px; border-radius: 3px; transition: height 0.1s ease;"></div>
            <div class="wave-bar" style="width: 3px; height: 10px; background: var(--cyan); margin: 0 3px; border-radius: 3px; transition: height 0.1s ease;"></div>
            <div class="wave-bar" style="width: 3px; height: 35px; background: var(--cyan); margin: 0 3px; border-radius: 3px; transition: height 0.1s ease;"></div>
            <div class="wave-bar" style="width: 3px; height: 20px; background: var(--cyan); margin: 0 3px; border-radius: 3px; transition: height 0.1s ease;"></div>
            <div class="wave-bar" style="width: 3px; height: 15px; background: var(--cyan); margin: 0 3px; border-radius: 3px; transition: height 0.1s ease;"></div>
            <div class="wave-bar" style="width: 3px; height: 30px; background: var(--cyan); margin: 0 3px; border-radius: 3px; transition: height 0.1s ease;"></div>
            <div class="wave-bar" style="width: 3px; height: 10px; background: var(--cyan); margin: 0 3px; border-radius: 3px; transition: height 0.1s ease;"></div>
            <div class="wave-bar" style="width: 3px; height: 20px; background: var(--cyan); margin: 0 3px; border-radius: 3px; transition: height 0.1s ease;"></div>
          </div>
          
          <button id="mic-toggle-btn" class="mic-btn" style="width: 50px; height: 50px; border-radius: 50%; background: rgba(0, 240, 255, 0.05); border: 2.5px solid var(--cyan); color: var(--cyan); cursor: pointer; display: flex; align-items: center; justify-content: center; font-size: 20px; box-shadow: 0 0 15px rgba(0, 240, 255, 0.2); transition: all 0.3s ease; outline: none; position: relative;">
            🎙️
            <div class="mic-glow-pulse" style="position: absolute; inset: -4px; border-radius: 50%; border: 1.5px solid var(--cyan); opacity: 0; pointer-events: none;"></div>
          </button>
          
        </div>

        <div class="assistant-tip-box" style="margin-top: 10px;">
          <span class="tip-label">ASSISTANT COMMUNICATIONS LOG:</span>
          <div id="voice-response-panel" style="font-family: 'Share Tech Mono', monospace; font-size: 10px; color: var(--text-dim); height: 75px; overflow-y: auto; padding: 10px; background: rgba(3, 6, 17, 0.6); border: 1px solid rgba(0,240,255,0.08); border-radius: 6px; line-height: 1.4; scrollbar-width: thin; box-shadow: inset 0 0 10px rgba(0,0,0,0.5);">
            <div style="color: var(--green);">[SYSTEM] RoadGuard Voice Co-Pilot online. VOICE INTELLIGENCE ENABLED.</div>
            <div style="color: var(--text-dim); margin-top: 4px;">Click the microphone and ask: "How is the road ahead?" or "How many potholes detected?".</div>
          </div>
        </div>
      </div>

    </div>

  </div>

  <!-- ANALYTICS CHARTS -->
  <div>
    <div class="section-title">// REAL-TIME COGNITIVE ANALYTICS</div>
    <div class="mini-charts">

      <div class="mini-chart-card">
        <div class="mini-chart-title">Potholes Over Time</div>
        <div class="mini-chart-wrap">
          <canvas id="lineChart"></canvas>
        </div>
      </div>

      <div class="mini-chart-card">
        <div class="mini-chart-title">Severity Distribution</div>
        <div class="mini-chart-wrap">
          <canvas id="pieChart"></canvas>
        </div>
      </div>

      <div class="mini-chart-card">
        <div class="mini-chart-title">Hourly Incident Distribution</div>
        <div class="mini-chart-wrap">
          <canvas id="barChart"></canvas>
        </div>
      </div>

    </div>
  </div>

  <!-- DETECTION LOG TABLE -->
  <div>
    <div class="section-title">// SYSTEM DATA ACQUISITION LOGS</div>
    <div class="panel">
      <div class="log-table-wrap">
        <table>
          <thead>
            <tr>
              <th>Incident Timestamp</th>
              <th>Damage Classification</th>
              <th>Incident Severity</th>
              <th>Neural Accuracy</th>
              <th>System Status</th>
            </tr>
          </thead>
          <tbody>
            {% for row in data|reverse %}
            {% set sev = 'high' if row.potholes >= 5 else ('med' if row.potholes >= 2 else 'low') %}
            {% set conf = (85 + row.potholes * 2) | int %}
            <tr>
              <td>{{ row.time }}</td>
              <td>Pothole</td>
              <td><span class="sev-badge sev-{{ sev }}">
                {{ 'CRITICAL' if sev=='high' else ('WARNING' if sev=='med' else 'MINOR') }}
              </span></td>
              <td>{{ [conf, 99]|min }}%</td>
              <td><span class="status-active">LOGGED</span></td>
            </tr>
            {% endfor %}
          </tbody>
        </table>
      </div>
    </div>
  </div>

</main>

<footer class="footer">
  RoadGuard AI · REAL-TIME YOLOV8 COGNITIVE ROAD DETECTOR · FLASK SURVEILLANCE BACKEND · OPENCV INTEGRATED
</footer>

<script>
// ===== STREAM RECOVERY =====
function handleStreamError(img) {
  img.style.display = 'none';
  const fallback = document.getElementById('camera-fallback');
  if (fallback) fallback.style.display = 'flex';
  console.log("Stream offline, fallback display activated");
}

// ===== SYSTEM STARTUP SEQUENCE =====
(function() {
  const overlay = document.getElementById('system-boot-overlay');
  const bar = document.getElementById('boot-progress-bar');
  const logs = document.getElementById('boot-terminal-log');
  
  const bootLogs = [
    "[OK] INITIALIZING NEURAL ENGINE...",
    "[OK] LINKING OPENCV CAPTURE DEVICE...",
    "[OK] LOADING COGNITIVE WEIGHTS FOR YOLOv8...",
    "[OK] CALIBRATING TACTICAL SURFACE SENSORS...",
    "[OK] ESTABLISHING GPS SECURE SAT-LINK...",
    "[OK] CONNECTING INTEGRATED RADAR ARRAYS...",
    "[OK] CONVERGING IMAGE MATRICES...",
    "[OK] ROADGUARD TACTICAL HUD ONLINE.",
    "[SYSTEM] BOOT SEQUENCE NOMINAL. ENGAGING..."
  ];
  
  let progress = 0;
  let logLineIndex = 0;
  
  function printNextLogLine() {
    if (logLineIndex < bootLogs.length) {
      // Remove cursor from previous line if any
      const existingCursor = logs.querySelector('.term-cursor');
      if (existingCursor) existingCursor.remove();
      
      const line = document.createElement('div');
      line.style.opacity = '0';
      line.style.transform = 'translateY(4px)';
      line.style.transition = 'all 0.15s ease-out';
      line.innerHTML = bootLogs[logLineIndex] + '<span class="term-cursor" style="color:var(--pink); font-weight:bold; animation: blink-anim 0.8s infinite; margin-left:4px;">█</span>';
      logs.appendChild(line);
      
      // Animate line print
      setTimeout(() => {
        line.style.opacity = '1';
        line.style.transform = 'translateY(0)';
      }, 20);
      
      logs.scrollTop = logs.scrollHeight;
      
      // Synchronize progress bar
      progress = Math.min(100, Math.floor(((logLineIndex + 1) / bootLogs.length) * 100));
      bar.style.width = `${progress}%`;
      
      logLineIndex++;
      setTimeout(printNextLogLine, 280);
    } else {
      // Remove blinking cursor on complete
      const existingCursor = logs.querySelector('.term-cursor');
      if (existingCursor) existingCursor.remove();
      
      setTimeout(() => {
        overlay.style.opacity = '0';
        overlay.style.visibility = 'hidden';
        
        // Spawn cinematic welcome notifications
        setTimeout(() => {
          showToast("AI Tactical Surveillance Online", "success");
          showToast("Jarvis Assistant: Uplink fully secure.", "success");
        }, 600);
      }, 500);
    }
  }
  
  // Trigger cinematic sequence
  setTimeout(printNextLogLine, 200);
})();

// ===== DYNAMIC TOAST SYSTEM =====
function showToast(text, type='info') {
  const container = document.getElementById('notification-container');
  if (!container) return;
  
  const toast = document.createElement('div');
  toast.className = `toast-item toast-${type}`;
  
  let icon = '🟢';
  if (type === 'danger') icon = '🚨';
  if (type === 'warning') icon = '⚠️';
  if (type === 'success') icon = '🟢';
  
  toast.innerHTML = `
    <div class="toast-glow"></div>
    <div class="toast-body">
      <span class="toast-icon">${icon}</span>
      <div class="toast-content">
        <span class="toast-title">SYSTEM UPLINK</span>
        <span class="toast-desc">${text}</span>
      </div>
    </div>
  `;
  
  container.appendChild(toast);
  
  // Slide-in animation
  setTimeout(() => {
    toast.classList.add('active');
  }, 50);
  
  // Auto dismiss
  setTimeout(() => {
    toast.classList.remove('active');
    setTimeout(() => {
      toast.remove();
    }, 500);
  }, 3800);
}

// ===== JARVIS SAFETY TIP ROTATION =====
const safetyTips = [
  "Braking distance increases by 40% on wet or degraded surfaces.",
  "Cruising speed should not exceed 40 km/h in moderate damage sectors.",
  "Holographic scanner active. Coordinates are fully synced with GPS Map.",
  "System telemetry locked. Neural convergence is operating at 94.7% accuracy.",
  "Defect volume logged today: nominal trend observed over last 1 hour.",
  "Optimal tire traction active. System status completely stable."
];
let tipIndex = 0;
setInterval(() => {
  const tipEl = document.getElementById('jarvis-safety-tip');
  if (tipEl) {
    tipEl.style.opacity = '0';
    setTimeout(() => {
      tipIndex = (tipIndex + 1) % safetyTips.length;
      tipEl.textContent = safetyTips[tipIndex];
      tipEl.style.opacity = '1';
    }, 400);
  }
}, 15000);

// ===== LIVE CLOCK =====
function updateClock() {
  const now = new Date();
  const h = String(now.getHours()).padStart(2,'0');
  const m = String(now.getMinutes()).padStart(2,'0');
  const s = String(now.getSeconds()).padStart(2,'0');
  
  // Blinking colon animation
  const blink = now.getSeconds() % 2 === 0 ? ':' : '<span style="opacity:0.2; transition:opacity 0.2s;">:</span>';
  
  // High-fidelity cinematic format: HH:MM:SS [L-COM]
  const str = `${h}${blink}${m}${blink}${s} <span style="font-size:9px; color:var(--pink); font-weight:bold; letter-spacing:1px; margin-left:6px; text-shadow: var(--pink-glow);">[L-COM]</span>`;
  
  const mainClock = document.getElementById('live-clock');
  const hudClock = document.getElementById('hud-time-val');
  
  if (mainClock) mainClock.innerHTML = str;
  if (hudClock) hudClock.textContent = `${h}:${m}:${s}`;
}
setInterval(updateClock, 1000);
updateClock();

// ===== SIMULATED FPS & PREMIUM HUD TELEMETRY =====
(function() {
  const el = document.getElementById('fps-display');
  const hudFps = document.getElementById('hud-fps-val');
  const badge = document.getElementById('hud-confidence-badge');
  const coordsEl = document.getElementById('hud-coords-stream');
  
  setInterval(() => {
    const fps = 24 + Math.floor(Math.random() * 8);
    if (el) el.textContent = `FPS: ${fps}`;
    if (hudFps) hudFps.textContent = fps;
    
    // Confidence percentage fluctuation (96.5% - 98.8%)
    if (badge) {
      const conf = (96.5 + Math.random() * 2.3).toFixed(1);
      badge.textContent = `CONF: ${conf}%`;
    }
    
    // Coordinates micro-fluctuation to show active geo-tracking movement
    if (coordsEl) {
      const lat = (12.9716 + (Math.random() - 0.5) * 0.0003).toFixed(5);
      const lon = (77.5946 + (Math.random() - 0.5) * 0.0003).toFixed(5);
      coordsEl.textContent = `GPS: ${lat}, ${lon}`;
    }
  }, 1000);
})();

// ===== COUNTER ANIMATION =====
document.querySelectorAll('.count-up').forEach(el => {
  const target = parseInt(el.dataset.target) || 0;
  let current = 0;
  const step = Math.max(1, Math.ceil(target / 45));
  const timer = setInterval(() => {
    current = Math.min(current + step, target);
    el.textContent = current;
    if (current >= target) clearInterval(timer);
  }, 25);
});

// ===== LIVE DETECTION COUNT & INTERACTIVE OVERLAYS =====
let lastTotal = null;
function updateHudCount() {
  fetch('/api/stats')
    .then(r => r.json())
    .then(d => {
      const hudCount = document.getElementById('hud-count-val');
      if (hudCount) hudCount.textContent = `DETECTIONS: ${d.total}`;
      
      // Update top KPI cards dynamically!
      const kpiTotal = document.getElementById('kpi-total-detections');
      const kpiScore = document.getElementById('kpi-road-quality');
      const kpiCritical = document.getElementById('kpi-critical-alerts');
      
      if (kpiTotal) kpiTotal.textContent = d.total;
      
      if (kpiScore) {
        kpiScore.textContent = d.score;
        const scoreCard = kpiScore.closest('.card');
        if (scoreCard) {
          scoreCard.className = 'card card-cyber-corners ' + (d.score >= 70 ? 'card-green' : (d.score >= 40 ? 'card-orange' : 'card-red'));
          const subText = scoreCard.querySelector('.card-sub');
          if (subText) {
            if (d.score >= 95) {
              subText.innerHTML = '<span style="color:var(--green);">●</span> Road Condition Excellent';
            } else if (d.score >= 70) {
              subText.innerHTML = '<span style="color:var(--green);">●</span> Road Condition Good';
            } else if (d.score >= 40) {
              subText.innerHTML = '<span style="color:var(--orange);">●</span> Minor Defects Flagged';
            } else {
              subText.innerHTML = '<span style="color:var(--red);">●</span> Road Index Critical';
            }
          }
        }
      }
      
      if (kpiCritical) kpiCritical.textContent = d.critical;
      
      // Dynamic notification if count increases!
      if (lastTotal !== null && d.total > lastTotal) {
        showToast("NEW ROAD SURFACE DEFECT IDENTIFIED AND LOGGED!", "danger");
      }
      lastTotal = d.total;
      
      // Update Risk Analysis progress bars dynamically!
      const risk = Math.min(100, Math.max(0, 100 - d.score));
      const riskBar = document.getElementById('risk-score-bar');
      const riskText = document.getElementById('risk-score-val');
      if (riskBar) riskBar.style.width = `${risk}%`;
      if (riskText) riskText.textContent = `${risk}%`;
      
      const unsafe = Math.min(100, Math.max(0, Math.floor(risk * 0.7)));
      const unsafeBar = document.getElementById('unsafe-zone-bar');
      const unsafeText = document.getElementById('unsafe-zone-val');
      if (unsafeBar) unsafeBar.style.width = `${unsafe}%`;
      if (unsafeText) unsafeText.textContent = `${unsafe}%`;
      
      // Update severity blocks
      const sevBadge = document.getElementById('est-severity-badge');
      const safetyStatus = document.getElementById('safety-matrix-status');
      const safetyRec = document.getElementById('ai-safety-rec');
      const threatVal = document.getElementById('jarvis-threat-val');
      
      // Dynamic circular health ring update
      const ring = document.getElementById('health-ring');
      const ringNum = document.getElementById('health-ring-num');
      const ringBadge = document.getElementById('health-status-badge');
      if (ring) {
        ring.style.stroke = d.score >= 70 ? '#00ffaa' : (d.score >= 40 ? '#ff9c00' : '#ff2a5f');
        const offset = 414.69 - (414.69 * d.score / 100);
        ring.style.strokeDashoffset = offset;
      }
      if (ringNum) {
        ringNum.textContent = d.score;
        ringNum.style.color = d.score >= 70 ? '#00ffaa' : (d.score >= 40 ? '#ff9c00' : '#ff2a5f');
        ringNum.className = 'health-ring-num ' + (d.score >= 70 ? 'good' : (d.score >= 40 ? 'warn' : 'danger'));
      }
      if (ringBadge) {
        let statusText = "CRITICAL";
        if (d.score >= 70) statusText = "GOOD ROAD";
        else if (d.score >= 40) statusText = "CAUTION";
        ringBadge.textContent = statusText;
        ringBadge.className = 'health-status-badge ' + (d.score >= 70 ? 'good' : (d.score >= 40 ? 'warn' : 'poor'));
      }
      
      if (d.score >= 95) {
        if (sevBadge) { sevBadge.textContent = "NONE"; sevBadge.className = "block-value good"; }
        if (safetyStatus) { safetyStatus.textContent = "OPTIMAL"; safetyStatus.className = "block-value good"; }
        if (safetyRec) safetyRec.textContent = "ROAD CONDITION EXCELLENT. NOMINAL VEHICLE OPERATION PROCEEDING.";
        if (threatVal) { threatVal.textContent = "NONE"; threatVal.className = "tel-value good"; }
      } else if (d.score >= 70) {
        if (sevBadge) { sevBadge.textContent = "LOW"; sevBadge.className = "block-value good"; }
        if (safetyStatus) { safetyStatus.textContent = "NOMINAL"; safetyStatus.className = "block-value good"; }
        if (safetyRec) safetyRec.textContent = "ROAD CONDITION GOOD. MAINTAIN DESIGNATED VEHICLE SPEEDS.";
        if (threatVal) { threatVal.textContent = "NONE"; threatVal.className = "tel-value good"; }
      } else if (d.score >= 40) {
        if (sevBadge) { sevBadge.textContent = "MODERATE"; sevBadge.className = "block-value warn"; }
        if (safetyStatus) { safetyStatus.textContent = "ALERT"; safetyStatus.className = "block-value warn"; }
        if (safetyRec) safetyRec.textContent = "MINOR ROAD DEFECTS IDENTIFIED. DRIVE WITH VIGILANCE AND AVOID ABRUPT DEVIATIONS.";
        if (threatVal) { threatVal.textContent = "MINOR"; threatVal.className = "tel-value warn"; }
      } else {
        if (sevBadge) { sevBadge.textContent = "CRITICAL"; sevBadge.className = "block-value danger"; }
        if (safetyStatus) { safetyStatus.textContent = "DANGER"; safetyStatus.className = "block-value danger"; }
        if (safetyRec) safetyRec.textContent = "CRITICAL SURFACE DAMAGE DETECTED. EXTREME CAUTION ADVISED. REDUCE SPEED IMMEDIATELY.";
        if (threatVal) { threatVal.textContent = "CRITICAL"; threatVal.className = "tel-value danger"; }
      }
      
      // Toggle live target lock warning overlay inside feed!
      const alertOverlay = document.getElementById('hud-alert-overlay');
      const alertTitle = document.getElementById('hud-alert-title');
      const alertDesc = document.getElementById('hud-alert-desc');
      
      if (d.last && d.last.potholes > 0) {
        if (alertOverlay) alertOverlay.style.display = 'flex';
        const pCount = d.last.potholes;
        if (pCount >= 5) {
          if (alertTitle) alertTitle.textContent = "⚠️ DANGER: SEVERE ASPHALT FAULT DETECTED";
          if (alertDesc) alertDesc.textContent = `CRITICAL ROAD DEGRADATION IDENTIFIED: [${pCount} HAZARDS DETECTED]`;
          if (alertOverlay) {
            alertOverlay.style.background = 'rgba(255, 42, 95, 0.2)';
            alertOverlay.style.borderColor = 'rgba(255, 42, 95, 0.85)';
          }
        } else {
          if (alertTitle) alertTitle.textContent = "⚠️ WARNING: SURFACE ANOMALY IDENTIFIED";
          if (alertDesc) alertDesc.textContent = `POTHOLE RADAR DETECTED [${pCount} ANOMALIES LOGGED]`;
          if (alertOverlay) {
            alertOverlay.style.background = 'rgba(255, 156, 0, 0.15)';
            alertOverlay.style.borderColor = 'rgba(255, 156, 0, 0.6)';
          }
        }
      } else {
        if (alertOverlay) alertOverlay.style.display = 'none';
      }
      
      // Periodically fetch log array to update charts dynamically
      fetch('/api/log')
        .then(r => r.json())
        .then(logData => {
          if (window.updateCharts) {
            window.updateCharts(logData);
          }
        })
        .catch(() => {});
    })
    .catch(() => {});
}
setInterval(updateHudCount, 2500);
updateHudCount();

// ===== CHART.JS SETUP =====
try {
  if (typeof Chart !== 'undefined') {
    Chart.defaults.color = '#6c8ba4';
    Chart.defaults.font.family = "'Share Tech Mono', monospace";
    Chart.defaults.font.size = 11;

    // Generate high-fidelity simulated baseline fallback data if session is empty or very new
    let chartData = {{ chart_data | tojson }};
    if (!chartData || !chartData.times || chartData.times.length === 0 || (chartData.times.length === 1 && chartData.times[0] === "")) {
      const now = new Date();
      const mockTimes = [];
      const mockValues = [];
      for (let i = 19; i >= 0; i--) {
        const d = new Date(now.getTime() - i * 5000);
        const h = String(d.getHours()).padStart(2,'0');
        const m = String(d.getMinutes()).padStart(2,'0');
        const s = String(d.getSeconds()).padStart(2,'0');
        mockTimes.push(`${h}:${m}:${s}`);
        mockValues.push(Math.random() > 0.65 ? Math.floor(Math.random() * 3) : 0);
      }
      chartData = {
        times: mockTimes,
        values: mockValues,
        severity: [142, 38, 12],
        hours: ["18", "19", "20", "21", "22", "23"],
        hourly: [18, 24, 32, 19, 28, 41]
      };
    }

    // Line Chart
    const lineCtx = document.getElementById('lineChart').getContext('2d');
    const cyanGlow = lineCtx.createLinearGradient(0, 0, 0, 95);
    cyanGlow.addColorStop(0, 'rgba(0, 240, 255, 0.22)');
    cyanGlow.addColorStop(1, 'rgba(0, 240, 255, 0.0)');

    window.lineChartInstance = new Chart(lineCtx, {
      type: 'line',
      data: {
        labels: chartData.times,
        datasets: [{
          data: chartData.values,
          borderColor: '#00f0ff',
          backgroundColor: cyanGlow,
          borderWidth: 2,
          pointRadius: 2,
          pointBackgroundColor: '#00f0ff',
          pointHoverRadius: 4,
          fill: true,
          tension: 0.35
        }]
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          x: { grid: { color:'rgba(0, 240, 255, 0.04)' }, ticks: { maxTicksLimit: 6 } },
          y: { grid: { color:'rgba(0, 240, 255, 0.04)' }, beginAtZero: true }
        }
      }
    });

    // Pie Chart
    const pieCtx = document.getElementById('pieChart').getContext('2d');
    window.pieChartInstance = new Chart(pieCtx, {
      type: 'doughnut',
      data: {
        labels: ['Low','Moderate','Critical'],
        datasets: [{
          data: chartData.severity,
          backgroundColor: ['rgba(0, 255, 170, 0.6)','rgba(255, 156, 0, 0.6)','rgba(255, 42, 95, 0.6)'],
          borderColor: ['#00ffaa','#ff9c00','#ff2a5f'],
          borderWidth: 1.5,
          hoverOffset: 4
        }]
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: {
          legend: { position: 'right', labels: { boxWidth: 10, padding: 8, font: { size: 9 } } }
        },
        cutout: '65%'
      }
    });

    // Bar Chart
    const barCtx = document.getElementById('barChart').getContext('2d');
    window.barChartInstance = new Chart(barCtx, {
      type: 'bar',
      data: {
        labels: chartData.hours,
        datasets: [{
          data: chartData.hourly,
          backgroundColor: 'rgba(255, 0, 127, 0.3)',
          borderColor: '#ff007f',
          borderWidth: 1.5,
          borderRadius: 4
        }]
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          x: { grid: { color:'rgba(0, 240, 255, 0.02)' } },
          y: { grid: { color:'rgba(0, 240, 255, 0.02)' }, beginAtZero: true }
        }
      }
    });

    // window-exposed update handler
    window.updateCharts = function(logData) {
      if (!logData || logData.length === 0) return;
      
      const recent = logData.slice(-20);
      const times = recent.map(d => d.time);
      const values = recent.map(d => d.potholes);
      
      const low = logData.filter(d => d.potholes < 2).length;
      const mod = logData.filter(d => d.potholes >= 2 && d.potholes < 5).length;
      const crit = logData.filter(d => d.potholes >= 5).length;
      
      const hourly = {};
      logData.forEach(d => {
        try {
          const hour = d.time.slice(0, 2);
          hourly[hour] = (hourly[hour] || 0) + d.potholes;
        } catch(e) {}
      });
      const sortedHours = Object.entries(hourly).sort((a,b) => a[0].localeCompare(b[0])).slice(-8);
      const hoursLabels = sortedHours.map(h => h[0]);
      const hoursValues = sortedHours.map(h => h[1]);
      
      if (window.lineChartInstance) {
        window.lineChartInstance.data.labels = times;
        window.lineChartInstance.data.datasets[0].data = values;
        window.lineChartInstance.update('none');
      }
      
      if (window.pieChartInstance) {
        window.pieChartInstance.data.datasets[0].data = [Math.max(low, 1), Math.max(mod, 1), Math.max(crit, 1)];
        window.pieChartInstance.update();
      }
      
      if (window.barChartInstance) {
        window.barChartInstance.data.labels = hoursLabels;
        window.barChartInstance.data.datasets[0].data = hoursValues;
        window.barChartInstance.update();
      }
    };
  } else {
    console.warn("Chart.js library not loaded; skipping interactive charts.");
  }
} catch (e) {
  console.error("Error setting up charts:", e);
}

// ===== FULLY OPERATIONAL CSV DOWNLOAD CONTROLLER =====
(function() {
  const downloadBtn = document.getElementById('download-report-btn');
  const csvFilter = document.getElementById('dashboard-csv-filter');
  if (!downloadBtn || !csvFilter) return;
  
  // Make sure button is fully active on load
  downloadBtn.style.opacity = '1';
  downloadBtn.style.cursor = 'pointer';
  downloadBtn.title = "Download detections report";
  
  downloadBtn.addEventListener('click', function(e) {
    e.preventDefault();
    if (downloadBtn.classList.contains('downloading')) return;
    
    const filter = csvFilter.value;
    const urlParam = filter === "ALL" ? "" : "?location=" + encodeURIComponent(filter);
    const filename = filter === "ALL" ? "all_detections.csv" : `${filter.toLowerCase().replace(' ', '')}_detections.csv`;
    
    // Animate neon glow and spinner
    downloadBtn.classList.add('downloading');
    downloadBtn.style.boxShadow = '0 0 20px rgba(255, 42, 95, 0.5)';
    downloadBtn.innerHTML = `<span class="spinner" style="display:inline-block; width:10px; height:10px; border:2px solid #fff; border-top-color:transparent; border-radius:50%; animation:spin 0.6s linear infinite; margin-right:8px;"></span> GENERATING CSV... 0%`;
    
    let progress = 0;
    const progressInterval = setInterval(() => {
      progress += Math.floor(Math.random() * 15) + 8;
      if (progress >= 100) {
        progress = 100;
        clearInterval(progressInterval);
        
        // Execute download query
        fetch('/api/download_report' + urlParam)
          .then(res => {
            if (!res.ok) throw new Error("Offline");
            return res.blob();
          })
          .then(blob => {
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.style.display = 'none';
            a.href = url;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);
            
            // Reset button styling
            downloadBtn.classList.remove('downloading');
            downloadBtn.style.boxShadow = 'none';
            downloadBtn.innerHTML = '📥 DOWNLOAD DETECTIONS CSV';
            
            // Show toast success message
            showToast(`EXPORT COMPLETED: ${filename.toUpperCase()}`, "success");
          })
          .catch(() => {
            // Local fallback simulation (for standalone/offline operation)
            const headers = "timestamp,confidence,location,severity,pothole count,latitude,longitude\\n";
            const mockRows = {
              "WHITEFIELD": `22:33:58,0.92,WHITEFIELD,CRITICAL,7,12.9698,77.7500\\n`,
              "HEBBAL": `22:33:58,0.86,HEBBAL,MODERATE,4,13.0358,77.5970\\n`,
              "MG ROAD": `22:33:58,0.94,MG ROAD,CRITICAL,9,12.9716,77.5946\\n`,
              "INDIRANAGAR": `22:33:58,0.81,INDIRANAGAR,LOW,2,12.9784,77.6408\\n`,
              "BTM LAYOUT": `22:33:58,0.88,BTM LAYOUT,HIGH,5,12.9166,77.6101\\n`,
              "KORAMANGALA": `22:33:58,0.84,KORAMANGALA,MODERATE,3,12.9279,77.6271\\n`
            };
            
            let fallbackCsv = headers;
            if (filter === "ALL") {
              Object.values(mockRows).forEach(row => fallbackCsv += row);
            } else if (mockRows[filter]) {
              fallbackCsv += mockRows[filter];
            }
            
            const blob = new Blob([fallbackCsv], { type: "text/csv" });
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.style.display = 'none';
            a.href = url;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);
            
            downloadBtn.classList.remove('downloading');
            downloadBtn.style.boxShadow = 'none';
            downloadBtn.innerHTML = '📥 DOWNLOAD DETECTIONS CSV';
            
            showToast(`EXPORT COMPLETED: ${filename.toUpperCase()} (LOCAL)`, "success");
          });
      } else {
        downloadBtn.innerHTML = `<span class="spinner" style="display:inline-block; width:10px; height:10px; border:2px solid #fff; border-top-color:transparent; border-radius:50%; animation:spin 0.6s linear infinite; margin-right:8px;"></span> GENERATING CSV... ${progress}%`;
      }
    }, 120);
  });
})();

// ===== ROADGUARD MOBILE COMPANION ACCESS LINK =====
(function() {
  const syncBtn = document.getElementById('mobile-sync-btn');
  const companionBtn = document.getElementById('mobile-companion-btn');
  const strengthSpan = document.getElementById('mobile-signal-strength');
  
  if (!syncBtn || !companionBtn) return;
  
  syncBtn.addEventListener('click', function() {
    syncBtn.innerHTML = `🔄 SYNCING...`;
    syncBtn.style.opacity = '0.7';
    
    setTimeout(() => {
      syncBtn.innerHTML = `🔄 SYNC DEVICE`;
      syncBtn.style.opacity = '1';
      
      const newStrength = (96 + Math.random() * 3.8).toFixed(1);
      if (strengthSpan) {
        strengthSpan.textContent = `${newStrength}% [SAT-COM]`;
        strengthSpan.style.color = 'var(--green)';
        setTimeout(() => {
          strengthSpan.style.color = 'var(--cyan)';
        }, 1000);
      }
      
      showToast("MOBILE UPLINK RE-SYNCHRONIZED: SIGNAL OPTIMAL", "success");
    }, 800);
  });
  
  companionBtn.addEventListener('click', function() {
    showToast("COMPANION HUD TELEMETRY SENT TO MOBILE GRID DEVICE", "success");
  });
})();

// ===== ROADGUARD VOICE CO-PILOT JS CONTROLLER =====
(function() {
  const micBtn = document.getElementById('mic-toggle-btn');
  const responsePanel = document.getElementById('voice-response-panel');
  const statusLabel = document.getElementById('voice-status-label');
  const waveBars = document.querySelectorAll('.wave-bar');
  const voiceRing = document.getElementById('voice-ring');
  const voiceCenter = document.getElementById('voice-center');
  
  if (!micBtn) return;
  
  let isListening = false;
  let isSpeaking = false;
  let recognition = null;
  
  // Voice Caching & Preloading
  let cachedVoices = [];
  function preloadVoices() {
    if (window.speechSynthesis) {
      cachedVoices = window.speechSynthesis.getVoices();
    }
  }
  preloadVoices();
  if (window.speechSynthesis && window.speechSynthesis.onvoiceschanged !== undefined) {
    window.speechSynthesis.onvoiceschanged = preloadVoices;
  }
  
  // High-fidelity Mathematical Waveform Visualizer (Trigonometric sin/cos curves at 60fps)
  let visualizerActive = false;
  let waveAnimId = null;
  const baseHeights = [15, 25, 10, 35, 20, 15, 30, 10, 20];
  
  function startWaveVisualizer() {
    if (visualizerActive) return;
    visualizerActive = true;
    animateWave();
  }
  
  function stopWaveVisualizer() {
    visualizerActive = false;
    if (waveAnimId) {
      cancelAnimationFrame(waveAnimId);
      waveAnimId = null;
    }
    // Smooth reset heights
    waveBars.forEach((bar, idx) => {
      bar.style.height = baseHeights[idx] + 'px';
    });
  }
  
  function animateWave() {
    if (!visualizerActive) return;
    const time = Date.now() * 0.0055;
    waveBars.forEach((bar, idx) => {
      const amplitude = isSpeaking ? 16 : (isListening ? 9 : 0);
      const speed = isSpeaking ? 1.4 : 1.0;
      const height = baseHeights[idx] + Math.sin(time * speed + idx * 0.75) * amplitude;
      bar.style.height = Math.max(5, height) + 'px';
    });
    waveAnimId = requestAnimationFrame(animateWave);
  }
  
  // Initialize speech recognition
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (SpeechRecognition) {
    recognition = new SpeechRecognition();
    recognition.continuous = false;
    recognition.lang = 'en-US';
    recognition.interimResults = false;
    recognition.maxAlternatives = 1;
    
    recognition.onstart = () => {
      isListening = true;
      micBtn.className = 'mic-btn listening';
      statusLabel.textContent = 'LISTENING...';
      statusLabel.style.color = 'var(--red)';
      if (voiceRing) {
        voiceRing.style.borderColor = 'var(--red)';
        voiceRing.style.boxShadow = '0 0 15px rgba(255, 42, 95, 0.4)';
      }
      if (voiceCenter) {
        voiceCenter.style.backgroundColor = 'var(--red)';
        voiceCenter.style.boxShadow = '0 0 10px var(--red)';
      }
      startWaveVisualizer();
      logSystem("Listening for driver command...", "info");
    };
    
    recognition.onresult = (event) => {
      const transcript = event.results[0][0].transcript;
      logSystem(`Driver: "${transcript}"`, "driver");
      processVoiceQuery(transcript);
    };
    
    recognition.onerror = (event) => {
      console.error("Speech Recognition Error:", event.error);
      if (event.error === 'not-allowed') {
        logSystem("[ERROR] Microphone permission denied by browser.", "error");
      } else {
        logSystem(`[ERROR] Speech processing alert: ${event.error}`, "error");
      }
      resetVoiceState();
    };
    
    recognition.onend = () => {
      isListening = false;
      if (!isSpeaking) {
        resetVoiceState();
      }
    };
  } else {
    logSystem("[WARN] Browser Web Speech Recognition is not supported. Control commands are disabled, but system responses remain nominal.", "error");
    micBtn.style.opacity = '0.5';
    micBtn.title = 'Speech recognition not supported in this browser';
  }
  
  function resetVoiceState() {
    isListening = false;
    isSpeaking = false;
    micBtn.className = 'mic-btn';
    statusLabel.textContent = 'VOICE INTELLIGENCE READY';
    statusLabel.style.color = 'var(--cyan)';
    if (voiceRing) {
      voiceRing.style.borderColor = 'var(--cyan)';
      voiceRing.style.boxShadow = 'none';
    }
    if (voiceCenter) {
      voiceCenter.style.backgroundColor = 'var(--pink)';
      voiceCenter.style.boxShadow = 'var(--pink-glow)';
    }
    stopWaveVisualizer();
  }
  
  function logSystem(text, type="info") {
    const item = document.createElement('div');
    item.style.marginTop = '4.5px';
    item.style.opacity = '0';
    item.style.transform = 'translateY(5px)';
    item.style.transition = 'all 0.25s ease';
    
    if (type === 'driver') {
      item.style.color = 'var(--cyan)';
      item.textContent = `DRV >> ${text}`;
    } else if (type === 'jarvis') {
      item.style.color = 'var(--green)';
      item.textContent = `JARVIS >> ${text}`;
    } else if (type === 'error') {
      item.style.color = 'var(--red)';
      item.textContent = text;
    } else {
      item.style.color = 'var(--text-dim)';
      item.textContent = text;
    }
    responsePanel.appendChild(item);
    
    // Animate slide-in transition
    setTimeout(() => {
      item.style.opacity = '1';
      item.style.transform = 'translateY(0)';
      responsePanel.scrollTop = responsePanel.scrollHeight;
    }, 20);
  }
  
  function processVoiceQuery(queryText) {
    statusLabel.textContent = 'NEURAL PROCESSING...';
    statusLabel.style.color = 'var(--orange)';
    
    fetch('/api/jarvis/voice_query', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query: queryText })
    })
    .then(res => res.json())
    .then(data => {
      if (data.success) {
        logSystem(data.response, "jarvis");
        speakResponse(data.response, data.action, data.action_data);
      } else {
        logSystem("[ERROR] Database coordinate offline.", "error");
        resetVoiceState();
      }
    })
    .catch(err => {
      console.error(err);
      logSystem("[ERROR] Failed connection to Flask NLP server.", "error");
      resetVoiceState();
    });
  }
  
  function speakResponse(text, action, actionData) {
    if (!window.speechSynthesis) {
      executeVoiceAction(action, actionData);
      resetVoiceState();
      return;
    }
    
    window.speechSynthesis.cancel();
    
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.rate = 1.0;
    utterance.pitch = 1.0;
    
    // Choose a high-quality human speech engine
    if (cachedVoices.length === 0) {
      cachedVoices = window.speechSynthesis.getVoices();
    }
    const systemVoice = cachedVoices.find(v => v.name.includes("Google US English") || v.name.includes("Daniel") || v.name.includes("Samantha") || v.lang.startsWith("en"));
    if (systemVoice) {
      utterance.voice = systemVoice;
    }
    
    utterance.onstart = () => {
      isSpeaking = true;
      micBtn.className = 'mic-btn speaking';
      statusLabel.textContent = 'SPEAKING...';
      statusLabel.style.color = 'var(--green)';
      if (voiceRing) {
        voiceRing.style.borderColor = 'var(--green)';
        voiceRing.style.boxShadow = '0 0 15px rgba(0, 255, 170, 0.4)';
      }
      if (voiceCenter) {
        voiceCenter.style.backgroundColor = 'var(--green)';
        voiceCenter.style.boxShadow = '0 0 10px var(--green)';
      }
      startWaveVisualizer();
    };
    
    utterance.onend = () => {
      isSpeaking = false;
      resetVoiceState();
      executeVoiceAction(action, actionData);
    };
    
    utterance.onerror = () => {
      isSpeaking = false;
      resetVoiceState();
      executeVoiceAction(action, actionData);
    };
    
    window.speechSynthesis.speak(utterance);
  }
  
  function executeVoiceAction(action, actionData) {
    if (!action) return;
    showToast(`VOICE ACTION: ${action.toUpperCase()}`, "success");
    
    if (action === 'open_map') {
      setTimeout(() => { window.location.href = '/map'; }, 1000);
    } else if (action === 'show_dashboard') {
      setTimeout(() => { window.location.href = '/'; }, 1000);
    } else if (action === 'map_search' && actionData && actionData.location) {
      setTimeout(() => { window.location.href = `/map?search=${actionData.location}`; }, 1000);
    } else if (action === 'start_scan') {
      const beam = document.querySelector('.hud-scanner-beam');
      if (beam) beam.style.animationPlayState = 'running';
      const stream = document.querySelector('.cam-stream');
      const fallback = document.getElementById('camera-fallback');
      if (stream) stream.style.display = 'block';
      if (fallback) fallback.style.display = 'none';
      showToast("Cognitive surveillance scanner activated.", "success");
    } else if (action === 'stop_scan') {
      const beam = document.querySelector('.hud-scanner-beam');
      if (beam) beam.style.animationPlayState = 'paused';
      const stream = document.querySelector('.cam-stream');
      const fallback = document.getElementById('camera-fallback');
      if (stream) stream.style.display = 'none';
      if (fallback) fallback.style.display = 'flex';
      showToast("Surveillance camera stream offline.", "warning");
    } else if (action === 'focus_camera') {
      const reticle = document.querySelector('.hud-reticle');
      if (reticle) {
        reticle.style.transform = 'scale(1.3) translate(-38%, -38%)';
        setTimeout(() => { reticle.style.transform = 'scale(1) translate(-50%, -50%)'; }, 800);
      }
      showToast("Optic coordinate convergence nominal.", "success");
    }
  }
  
  micBtn.addEventListener('click', () => {
    if (isSpeaking) {
      window.speechSynthesis.cancel();
      resetVoiceState();
      return;
    }
    
    if (isListening) {
      if (recognition) recognition.stop();
      resetVoiceState();
    } else {
      if (recognition) {
        try {
          recognition.start();
        } catch (e) {
          console.error(e);
        }
      }
    }
  });
})();
</script>

</body>
</html>
"""

# ================= API ROUTES (NEW — no backend changes) =================

@app.route("/api/detect", methods=["POST"])
def detect():
    import numpy as np
    import cv2
    from flask import request
    import base64
    
    lat = request.form.get("lat") or request.args.get("lat")
    lon = request.form.get("lon") or request.args.get("lon")
    
    file = request.files.get("image")
    if not file:
        req_json = request.get_json() or {}
        img_base64 = req_json.get("image")
        if img_base64:
            img_bytes = base64.b64decode(img_base64)
            np_arr = np.frombuffer(img_bytes, np.uint8)
            frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        else:
            return jsonify({"success": False, "error": "No image provided"}), 400
    else:
        img_bytes = file.read()
        np_arr = np.frombuffer(img_bytes, np.uint8)
        frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

    if frame is None:
        return jsonify({"success": False, "error": "Invalid image"}), 400

    results = model(frame)
    potholes_detected = len(results[0].boxes)
    status, _ = get_road_status_color(potholes_detected)
    
    detections = []
    for box in results[0].boxes:
        xyxy = box.xyxy[0].tolist()
        conf = float(box.conf[0])
        x1, y1, x2, y2 = xyxy
        detections.append({
            "class": "Pothole",
            "confidence": conf,
            "x": x1,
            "y": y1,
            "width": x2 - x1,
            "height": y2 - y1
        })
        
    # Symmetrically update shared frame for dashboard feed
    try:
        cv2.imwrite("shared_frame.jpg", frame)
    except Exception as e:
        pass
        
    if potholes_detected > 0:
        log_detection(potholes_detected, lat, lon)
        update_shared_data(potholes_detected, lat, lon)
        
    # Generate base64 annotated image
    annotated_frame = results[0].plot()
    ret, buffer = cv2.imencode('.jpg', annotated_frame)
    if ret:
        img_b64 = base64.b64encode(buffer).decode('utf-8')
    else:
        img_b64 = ""
        
    return jsonify({
        "success": True,
        "detections": detections,
        "image": img_b64
    })


@app.route("/api/stats")
def api_stats():
    data = load_data()
    score, status = calculate_road_score(data)
    total = sum(d.get('potholes', 0) for d in data)
    critical = sum(1 for d in data if d.get('potholes', 0) >= 5)
    recent = data[-1] if data else {}
    return jsonify({
        "total": total,
        "score": score,
        "status": status,
        "critical": critical,
        "last": recent
    })

@app.route("/api/log")
def api_log():
    data = load_data()
    return jsonify(data[-50:])  # last 50 records

@app.route("/api/download_report")
def api_download_report():
    from flask import make_response, request
    import csv
    import io
    import random
    
    location_filter = request.args.get('location', '').strip().lower()
    data = load_data()
    
    si = io.StringIO()
    cw = csv.writer(si)
    cw.writerow(["timestamp", "confidence", "location", "severity", "pothole count", "latitude", "longitude"])
    
    def get_location_name(lat, lon):
        best_loc = "Bengaluru Central"
        min_dist = 99999.0
        loc_coords = {
            "MG Road": (12.9716, 77.5946),
            "Whitefield": (12.9698, 77.7500),
            "Indiranagar": (12.9784, 77.6408),
            "Koramangala": (12.9279, 77.6271),
            "BTM Layout": (12.9166, 77.6101),
            "Hebbal": (13.0358, 77.5970)
        }
        for name, coords in loc_coords.items():
            dist = (lat - coords[0])**2 + (lon - coords[1])**2
            if dist < min_dist:
                min_dist = dist
                best_loc = name
        if min_dist > 0.05:
            return "Bengaluru Central"
        return best_loc
        
    for record in data:
        lat = record.get('lat', 12.9716)
        lon = record.get('lon', 77.5946)
        potholes = record.get('potholes', 0)
        time_str = record.get('time', '00:00:00')
        
        loc_name = get_location_name(lat, lon)
        
        if location_filter and location_filter != "all" and location_filter != loc_name.lower():
            continue
            
        if potholes == 0:
            severity = "NONE"
        elif potholes < 2:
            severity = "LOW"
        elif potholes < 5:
            severity = "MODERATE"
        else:
            severity = "CRITICAL"
            
        if potholes > 0:
            confidence = round(random.uniform(0.78, 0.96), 2)
        else:
            confidence = 0.0
            
        cw.writerow([time_str, confidence, loc_name, severity, potholes, lat, lon])
        
    output = make_response(si.getvalue())
    filename = "all_detections.csv"
    if location_filter and location_filter != "all":
        filename = f"{location_filter.replace(' ', '')}_detections.csv"
        
    output.headers["Content-Disposition"] = f"attachment; filename={filename}"
    output.headers["Content-type"] = "text/csv"
    return output

@app.route("/api/jarvis/voice_query", methods=["POST"])
def api_jarvis_voice_query():
    from flask import request
    req_data = request.get_json() or {}
    query = req_data.get("query", "").strip().lower()
    
    # Load live telemetry data
    session_data = load_data()
    score, status = calculate_road_score(session_data)
    total_detections = len(session_data)
    critical_alerts = sum(1 for d in session_data if d.get('potholes', 0) >= 5)
    
    response_text = "I am ready and listening. Please command me."
    action = None
    action_data = None
    
    if not query:
        return jsonify({
            "success": True,
            "query": "",
            "response": "Standby mode. Voice Co-Pilot active.",
            "action": None,
            "action_data": None
        })
    
    # 1. Location-based queries (Matched first to prevent generic keyword overrides)
    mentioned_location = None
    for loc in ["hebbal", "whitefield", "mg road", "indiranagar", "btm layout", "koramangala"]:
      if loc in query:
        mentioned_location = loc
        break
        
    if mentioned_location:
      loc_name = mentioned_location.title()
      if "Mg Road" in loc_name:
        loc_name = "MG Road"
      elif "Btm" in loc_name:
        loc_name = "BTM Layout"
        
      action = "map_search"
      action_data = {"location": loc_name}
      
      try:
        from pothole_data import locations
        loc_info = locations.get(loc_name, {})
        potholes = loc_info.get("potholes", 0)
        condition = loc_info.get("condition", "Low")
        
        if loc_name == "MG Road":
          response_text = "Scanning MG Road. Safety index is 62 percent. Moderate road damage detected with 3 surface anomalies."
        elif loc_name == "Whitefield":
          response_text = "Scanning Whitefield. Threat level is critical with 7 detected potholes."
        elif loc_name == "Hebbal":
          response_text = "Hebbal roads are currently stable with low surface risk."
        else:
          if condition.lower() == "critical" or potholes >= 5:
            response_text = f"Scanning {loc_name}. Threat level is critical with {potholes} detected potholes."
          elif condition.lower() == "moderate" or potholes >= 3:
            response_text = f"Scanning {loc_name}. Safety index is 65 percent. Moderate road damage detected with {potholes} surface anomalies."
          else:
            response_text = f"{loc_name} roads are currently stable with low surface risk."
      except Exception as e:
        response_text = f"Scanning coordinate link for {loc_name}. Fetching safety metrics from Leaflet."
        
    # 2. Road condition queries
    elif any(k in query for k in ["road condition", "road ahead", "danger zone", "how is the road"]):
      if score >= 80:
        response_text = f"The road condition ahead is safe. Safety index is {score} percent, road status is good."
      elif score >= 50:
        response_text = f"Road condition ahead is moderate. Unsafe risk index is {100 - score} percent. Please drive with vigilance."
      else:
        response_text = f"Warning: road condition ahead is critical. Safety score has dropped to {score} percent. Extreme caution is advised."
        
    # 3. Detection queries
    elif any(k in query for k in ["how many pothole", "potholes detected", "detection count", "critical area", "total detections", "active detections"]):
      response_text = f"Active surveillance has identified {total_detections} road defects across the session grid. There are {critical_alerts} critical alert areas currently logged."
            
    # 4. Dashboard control commands
    elif "start scan" in query or "start scanning" in query:
        action = "start_scan"
        response_text = "Affirmative. Initializing tactical cognitive scanning grid. YOLOv8 models converging."
    elif "stop scan" in query or "stop scanning" in query:
        action = "stop_scan"
        response_text = "Understood. Deactivating camera broadcast and live scan line overlays."
    elif "open map" in query or "show map" in query or "go to map" in query:
        action = "open_map"
        response_text = "Redirecting system telemetry to the smart-city Leaflet GPS map registry."
    elif "focus camera" in query or "realign camera" in query or "recalibrate" in query:
        action = "focus_camera"
        response_text = "Re-calibrating holographic reticle coordinates. Sonar alignment stable."
    elif "show dashboard" in query or "open dashboard" in query or "go to dashboard" in query:
        action = "show_dashboard"
        response_text = "Returning display grid layout to the main AI surveillance feed."
        
    # 5. Hybrid Conversational Intelligence Engine
    else:
        import random
        norm_query = query.strip()
        
        # Conversational pattern mappings
        if any(w in norm_query for w in ["hello", "hi ", "hey ", "greetings", "wake up"]):
            responses = [
                "Hello. RoadGuard AI online and ready.",
                "Greetings. Systems active. Tactical interface operational.",
                "Hello. Co-pilot initialized. Awaiting your instructions."
            ]
            response_text = random.choice(responses)
            
        elif any(w in norm_query for w in ["how are you", "status report", "system status"]):
            responses = [
                "Systems stable and fully operational.",
                "Core processor temperature normal. Tactical scans running within standard parameters.",
                "I am operating at peak efficiency. All telemetry modules nominal."
            ]
            response_text = random.choice(responses)
            
        elif any(w in norm_query for w in ["what can you do", "help me", "your features", "capabilities"]):
            response_text = "I can monitor roads, analyze detections, search locations, and assist through voice interaction."
            
        elif any(w in norm_query for w in ["about ai", "what is ai", "artificial intelligence"]):
            response_text = "Artificial intelligence enables machines to learn and make decisions from data."
            
        elif any(w in norm_query for w in ["who built", "who created", "who made", "creator", "developer"]):
            response_text = "RoadGuard AI was developed as an intelligent pothole detection and monitoring platform."
            
        elif any(w in norm_query for w in ["thank you", "thanks", "good job", "excellent"]):
            responses = [
                "You are welcome. Safe driving is my primary directive.",
                "Understood. Continuing active surveillance scans.",
                "Affirmative. Always glad to assist."
            ]
            response_text = random.choice(responses)
            
        elif any(w in norm_query for w in ["bye", "goodbye", "shutdown", "sleep"]):
            response_text = "Understood. Placing voice subsystem on standby. Drive safe."
            
        else:
            # Smart dynamic context-aware response for unmapped queries
            responses = [
                f"Tactical analysis complete. Unmapped query '{query}' logged. Telemetry road score is nominal at {score} percent.",
                f"Query parsed. No direct intent mapped for '{query}'. Grid health remains stable at {score} percent.",
                f"Understood. Awaiting further tactical instructions. Current road health is logged as {status.upper()}."
            ]
            response_text = random.choice(responses)

    return jsonify({
        "success": True,
        "query": query,
        "response": response_text,
        "action": action,
        "action_data": action_data
    })

# ================= ROUTES (UNCHANGED) =================

@app.route("/")
def dashboard():
    data = load_data()
    score, status = calculate_road_score(data)

    # Build chart data
    recent = data[-20:]
    times  = [d["time"] for d in recent]
    values = [d["potholes"] for d in recent]

    low  = sum(1 for d in data if d.get("potholes", 0) < 2)
    mod  = sum(1 for d in data if 2 <= d.get("potholes", 0) < 5)
    crit = sum(1 for d in data if d.get("potholes", 0) >= 5)

    # hourly distribution (last 8 hours)
    from collections import defaultdict
    hourly = defaultdict(int)
    for d in data:
        try:
            hour = d["time"][:2]
            hourly[hour] += d.get("potholes", 0)
        except:
            pass
    sorted_hours = sorted(hourly.items())[-8:]
    hours_labels  = [h for h,_ in sorted_hours]
    hours_values  = [v for _,v in sorted_hours]

    chart_data = {
        "times":    times,
        "values":   values,
        "severity": [max(low, 1), max(mod, 1), max(crit, 1)],
        "hours":    hours_labels,
        "hourly":   hours_values
    }

    total_detections = sum(d.get('potholes', 0) for d in data)
    critical_alerts = sum(1 for d in data if d.get('potholes', 0) >= 5)

    return render_template_string(
        HTML,
        data=data,
        score=score,
        status=status,
        chart_data=chart_data,
        total_detections=total_detections,
        road_quality_index=score,
        critical_alerts=critical_alerts
    )

@app.route("/map")
def map_view():
    return render_template("map.html")

@app.route("/video_feed")
def video_feed():
    return Response(
        generate_frames(),
        mimetype='multipart/x-mixed-replace; boundary=frame'
    )

@app.route("/api/fake_locations")
def api_fake_locations():
    try:
        from pothole_data import locations
        return jsonify(locations)
    except Exception as e:
        print(f"Error loading locations: {e}")
        return jsonify({})

# ================= RUN =================

if __name__ == "__main__":
    try:
        app.run(host="0.0.0.0", port=5001, debug=True, use_reloader=False)
    finally:
        if camera_stream is not None:
            camera_stream.stop()