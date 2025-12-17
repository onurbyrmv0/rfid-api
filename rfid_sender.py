import time
import os
import sqlite3
import requests
import RPi.GPIO as GPIO
from mfrc522 import SimpleMFRC522
from dotenv import load_dotenv

# Load Environment Variables
# Expecting .env in the same directory
load_dotenv()

SERVER_URL = os.getenv("SERVER_URL", "http://localhost:5000")
SCAN_ENDPOINT = f"{SERVER_URL}/scan"
BUZZER_PIN = 19
DB_FILE = "offline.db"

# Setup GPIO
GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)
GPIO.setup(BUZZER_PIN, GPIO.OUT)

reader = SimpleMFRC522()

def beep(duration=0.2, count=1):
    """Triggers the active buzzer with a specific pattern."""
    for _ in range(count):
        GPIO.output(BUZZER_PIN, GPIO.HIGH)
        time.sleep(duration)
        GPIO.output(BUZZER_PIN, GPIO.LOW)
        time.sleep(0.1)

def init_db():
    """Initializes the local SQLite database for offline storage."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS scans
                 (uid TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    conn.close()

def save_offline(uid):
    """Saves the scan locally when the server is unreachable."""
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("INSERT INTO scans (uid) VALUES (?)", (str(uid),))
        conn.commit()
        conn.close()
        print(f" [OFFLINE] Saved UID {uid} to local DB.")
        beep(0.1, 2) # Double beep for offline save
    except Exception as e:
        print(f" [ERROR] Could not save offline: {e}")

def get_offline_count():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM scans")
    count = c.fetchone()[0]
    conn.close()
    return count

def sync_offline_data():
    """Attempts to send offline data to the server."""
    count = get_offline_count()
    if count == 0:
        return

    print(f" [SYNC] Found {count} offline records. Attempting to sync...")
    
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT rowid, uid FROM scans")
    rows = c.fetchall()
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Raspberry Pi; RFID Client)',
        'Content-Type': 'application/json'
    }

    for row in rows:
        row_id, uid = row
        try:
            payload = {'uid': uid}
            # Send to server
            response = requests.post(SCAN_ENDPOINT, json=payload, headers=headers, timeout=5)
            
            # If server accepted (200/201) or rejected logic (403/404) -> We delete from local
            # Basically if we reached the server, we consider it synced.
            # Only network errors should keep it in DB.
            if response.status_code in [200, 201, 403, 404]:
                c.execute("DELETE FROM scans WHERE rowid = ?", (row_id,))
                print(f" [SYNCED] UID {uid} -> Server Status {response.status_code}")
            else:
                print(f" [SYNC FAIL] Server Error {response.status_code} for UID {uid}")
                
        except Exception as e:
            print(f" [SYNC ERROR] Could not connect: {e}")
            break # Stop trying if network is down
            
    conn.commit()
    conn.close()

def main():
    print(f"Attendance Client Started (Offline Support Enabled).")
    print(f"Server URL: {SCAN_ENDPOINT}")
    
    init_db()
    
    try:
        while True:
            # 1. Try to sync before scanning (if there are old records)
            sync_offline_data()
            
            print("Waiting for cards...")
            # reader.read() blocks until a card is detected
            card_id, text = reader.read()
            
            print(f"\nCard Detected! UID: {card_id}")
            # Immediate feedback (1 beep)
            beep(0.2, 1)
            
            # 2. Try to Send to Server
            try:
                payload = {'uid': str(card_id).strip()}
                print("Sending to server...", end="")
                
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Raspberry Pi; RFID Client)',
                    'Content-Type': 'application/json'
                }
                
                response = requests.post(SCAN_ENDPOINT, json=payload, headers=headers, timeout=5)
                
                if response.status_code == 201:
                    print(f" [SUCCESS] {response.json().get('message')}")
                elif response.status_code == 200:
                    print(f" [IGNORED] {response.json().get('message')}")
                elif response.status_code == 403:
                    print(f" [REJECTED] {response.json().get('message')}")
                elif response.status_code == 404:
                    print(f" [UNKNOWN] Card not registered.")
                else:
                    print(f" [ERROR] Status {response.status_code}")
                    
            except requests.exceptions.RequestException as e:
                print(f" [NETWORK ERROR] Switching to Offline Mode...")
                save_offline(card_id)
            
            # 3. Wait before next scan
            time.sleep(3)
            
    except KeyboardInterrupt:
        print("\nStopping...")
        GPIO.cleanup()
    finally:
        GPIO.cleanup()

if __name__ == "__main__":
    main()
