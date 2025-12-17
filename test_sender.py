import requests
import sys

import os
from dotenv import load_dotenv

load_dotenv()

# Konfiqurasiya
SERVER_URL = os.getenv("SERVER_URL", "https://rfid.onurbayramov.codes")
SCAN_ENDPOINT = f"{SERVER_URL}/scan"

print("=========================================")
print(f"📡 Server Test Aləti: {SCAN_ENDPOINT}")
print("=========================================")

while True:
    uid = input("\n🆔 Kart UID daxil edin (çıxmaq üçün 'q'): ").strip()
    
    if uid.lower() == 'q':
        print("👋 Sağ olun!")
        break
        
    if not uid:
        continue

    # Cloudflare bloklamasın deyə başlıqlar
    headers = {
        'User-Agent': 'Mozilla/5.0 (Test Client)',
        'Content-Type': 'application/json'
    }

    payload = {'uid': uid}

    try:
        print(f"⏳ Göndərilir: {uid} ...")
        response = requests.post(SCAN_ENDPOINT, json=payload, headers=headers, timeout=5)
        
        print(f"📥 Status: {response.status_code}")
        
        try:
            data = response.json()
            status = data.get('status', 'info')
            msg = data.get('message', '')
            print(f"📝 Cavab: [{status.upper()}] {msg}")
        except:
            print("⚠️  Xam Cavab:", response.text)
            
    except Exception as e:
        print(f"❌ Xəta baş verdi: {e}")
