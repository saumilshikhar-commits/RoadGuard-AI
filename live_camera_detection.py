import cv2
import json
from ultralytics import YOLO
from datetime import datetime

# LOAD AI MODEL
model = YOLO("yolov8n.pt")


# OPEN LAPTOP CAMERA
cap = cv2.VideoCapture(0)

if not cap.isOpened():
    print("Camera not detected")
    exit()

print("AI Camera Started...")



while True:

    ret, frame = cap.read()

    if not ret:
        break

    # AI DETECTION
    results = model(frame)

    pothole_count = 0

    for result in results:

        boxes = result.boxes

        for box in boxes:

            x1, y1, x2, y2 = map(int, box.xyxy[0])

            confidence = float(box.conf[0])

            label = model.names[int(box.cls[0])]

            # TEMP LOGIC
            # Treat large road objects as potholes demo
            if confidence > 0.5:

                pothole_count += 1

                cv2.rectangle(
                    frame,
                    (x1, y1),
                    (x2, y2),
                    (0, 255, 255),
                    2
                )

                cv2.putText(
                    frame,
                    f"Pothole {confidence:.2f}",
                    (x1, y1 - 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0, 255, 255),
                    2
                )

    # SAVE DATA TO JSON
    detection_data = {
        "time": datetime.now().strftime("%H:%M:%S"),
        "potholes": pothole_count
    }

    try:

        with open("detection_log.json", "r") as f:
            data = json.load(f)

    except:
        data = []

    data.append(detection_data)

    data = data[-20:]

    with open("detection_log.json", "w") as f:
        json.dump(data, f, indent=4)

    # DASHBOARD TEXT
    cv2.putText(
        frame,
        f"Potholes Detected: {pothole_count}",
        (20, 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        1,
        (0, 255, 255),
        3
    )

    cv2.imshow("AI Smart Road Monitoring", frame)

    # PRESS Q TO EXIT
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()