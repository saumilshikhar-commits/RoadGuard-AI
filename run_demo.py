import os
import subprocess
import time
import webbrowser

print("===================================")
print("CLEANING UP PREVIOUS SYSTEM PROCESSES...")
print("===================================")
os.system("pkill -f app_dashboard.py")
os.system("pkill -f app_dashboard_custom.py")
os.system("pkill -f main.py")
os.system("kill -9 $(lsof -t -i:5001) >/dev/null 2>&1")
time.sleep(1)

print("===================================")
print("STARTING AI SMART ROAD SYSTEM...")
print("===================================")

# ================= START YOLO DETECTION =================
subprocess.Popen(["python3", "main.py"])

# Wait few seconds
time.sleep(3)

# ================= START DASHBOARD SERVER =================
subprocess.Popen(["python3", "app_dashboard.py"])

# Wait for Flask to fully start
time.sleep(5)

# ================= OPEN MAIN DASHBOARD =================
webbrowser.open("http://127.0.0.1:5001")


print("===================================")
print("SYSTEM RUNNING SUCCESSFULLY")
print("===================================")