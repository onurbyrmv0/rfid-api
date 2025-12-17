import time
import os
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

# Setup GPIO
GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)
GPIO.setup(BUZZER_PIN, GPIO.OUT)

reader = SimpleMFRC522()

def beep(duration=0.2):
    """Triggers the active buzzer for a short duration."""
    GPIO.output(BUZZER_PIN, GPIO.HIGH)
    time.sleep(duration)
    GPIO.output(BUZZER_PIN, GPIO.LOW)

def main():
    print(f"Attendance Client Started.")
    print(f"Server URL: {SCAN_ENDPOINT}")
    print("Waiting for cards...")
    
    try:
        while True:
            # reader.read() blocks until a card is detected
            card_id, text = reader.read()
            
            # 1. Immediate Feedback
            print(f"\nCard Detected! UID: {card_id}")
            beep()
            
            # 2. Send to Server (Async validation)
            try:
                payload = {'uid': str(card_id).strip()}
                print("Sending to server...", end="")
                
                # We use a short timeout so we don't hang if server is down, 
                # but the prompt implies we "Do not wait for server response" for the BEEP. 
                # The beep is already done. Now we just send.
                response = requests.post(SCAN_ENDPOINT, json=payload, timeout=2)
                
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
                print(f" [FAILED] Could not connect to server: {e}")
            
            # 3. Wait before next scan
            time.sleep(3)
            
    except KeyboardInterrupt:
        print("\nStopping...")
        GPIO.cleanup()

if __name__ == "__main__":
    main()
