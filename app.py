import os
import datetime
import psycopg2
from flask import Flask, request, jsonify, render_template, redirect, url_for, flash
from flask_httpauth import HTTPBasicAuth
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = 'super_secret_session_key'  # Needed for flash messages
auth = HTTPBasicAuth()

# Configuration
DB_HOST = os.getenv("POSTGRES_HOST", "localhost")
DB_NAME = os.getenv("POSTGRES_DB", "attendance_db")
DB_USER = os.getenv("POSTGRES_USER", "postgres")
DB_PASS = os.getenv("POSTGRES_PASSWORD", "password")
ADMIN_USER = os.getenv("ADMIN_USER", "admin")
ADMIN_PASS = os.getenv("ADMIN_PASS", "admin123")
API_KEY = os.getenv("API_KEY", "secret")

def get_db_connection():
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASS
    )
    return conn

@auth.verify_password
def verify_password(username, password):
    if username == ADMIN_USER and password == ADMIN_PASS:
        return username

# --- API Endpoints ---

@app.route('/')
def index():
    return redirect(url_for('dashboard'))

@app.route('/scan', methods=['POST'])
def scan_card():
    data = request.json
    if not data or 'uid' not in data:
        return jsonify({"error": "No UID provided"}), 400
    
    card_uid = data['uid']
    now = datetime.datetime.now()
    current_time = now.time()
    
    # 1. Check correct time (8 AM Rule)
    # The rule says: If Server Time < 08:00 AM -> Reject.
    # Adjust as needed (e.g. maybe they meant entry is ONLY allowed before 8? 
    # Usually attendance is "Before 8 you are on time". 
    # "If Server Time < 08:00 AM -> Ignore/Reject" implies scans BEFORE 8 are invalid? 
    # Let's re-read: "If Server Time < 08:00 AM -> Ignore/Reject." 
    # This might mean the system only accepts scans AFTER 8? Or maybe it is for "Late" attendance?
    # I will implement strictly: If (now.hour < 8) -> return Match Rejected.
    
    if now.hour < 8:
        return jsonify({"status": "rejected", "message": "System not active before 08:00 AM"}), 403

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        # 2. Check if Student exists
        cur.execute("SELECT full_name FROM students WHERE card_uid = %s", (card_uid,))
        student = cur.fetchone()
        
        if not student:
            return jsonify({"status": "error", "message": "Unknown Card UID"}), 404
            
        student_name = student[0]

        # 3. Check for Duplicate Scan today after 8 AM
        today_date = now.date()
        # We check logs for this UID where entry_time is today
        cur.execute("""
            SELECT id FROM attendance_logs 
            WHERE card_uid = %s AND date(entry_time) = %s
        """, (card_uid, today_date))
        
        existing_log = cur.fetchone()
        
        if existing_log:
            return jsonify({"status": "ignored", "message": f"Already checked in today: {student_name}"}), 200

        # 4. Insert Attendance
        cur.execute("INSERT INTO attendance_logs (card_uid, entry_time) VALUES (%s, %s)", (card_uid, now))
        conn.commit()
        
        return jsonify({"status": "success", "message": f"Welcome, {student_name}!"}), 201

    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        conn.close()

@app.route('/api/history', methods=['GET'])
def api_history():
    key = request.headers.get('x-api-key')
    if key != API_KEY:
        return jsonify({"error": "Unauthorized"}), 401
    
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT a.id, s.full_name, a.card_uid, a.entry_time 
        FROM attendance_logs a
        JOIN students s ON a.card_uid = s.card_uid
        ORDER BY a.entry_time DESC
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    
    history = []
    for row in rows:
        history.append({
            "id": row[0],
            "name": row[1],
            "uid": row[2],
            "time": row[3].strftime("%Y-%m-%d %H:%M:%S")
        })
        
    return jsonify(history)

# --- Admin Dashboard ---

@app.route('/dashboard')
@auth.login_required
def dashboard():
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Get Today's Logs
    today = datetime.date.today()
    cur.execute("""
        SELECT s.full_name, a.entry_time 
        FROM attendance_logs a
        JOIN students s ON a.card_uid = s.card_uid
        WHERE date(a.entry_time) = %s
        ORDER BY a.entry_time DESC
    """, (today,))
    attendance_data = cur.fetchall()
    
    # Get All Students
    cur.execute("SELECT card_uid, full_name, created_at FROM students ORDER BY created_at DESC")
    all_students = cur.fetchall()
    
    cur.close()
    conn.close()
    
    return render_template('dashboard.html', attendance=attendance_data, students=all_students)

@app.route('/students/add', methods=['POST'])
@auth.login_required
def add_student():
    card_uid = request.form.get('card_uid')
    full_name = request.form.get('full_name')
    
    if not card_uid or not full_name:
        flash("UID and Name are required!", "error")
        return redirect(url_for('dashboard'))
        
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO students (card_uid, full_name) VALUES (%s, %s)", (card_uid, full_name))
        conn.commit()
        flash(f"Student {full_name} added successfully!", "success")
    except psycopg2.IntegrityError:
        conn.rollback()
        flash("Error: Student with this UID already exists.", "error")
    except Exception as e:
        conn.rollback()
        flash(f"Error: {str(e)}", "error")
    finally:
        cur.close()
        conn.close()
        
    return redirect(url_for('dashboard'))

@app.route('/students/delete/<uid>', methods=['POST'])
@auth.login_required
def delete_student(uid):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM students WHERE card_uid = %s", (uid,))
        conn.commit()
        flash("Student deleted.", "success")
    except Exception as e:
        conn.rollback()
        flash(f"Error: {str(e)}", "error")
    finally:
        cur.close()
        conn.close()
    
    return redirect(url_for('dashboard'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
