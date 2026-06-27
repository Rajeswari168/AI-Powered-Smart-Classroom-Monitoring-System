"""
database.py - SQLite Database Management for Smart Classroom Monitoring System
=============================================================================
Manages students, attendance, mobile phone detections, distraction score logs,
and system alerts. Initializes with default mock data matching the UI screenshots.
"""

import sqlite3
import os
from datetime import datetime, date

DB_PATH = os.path.join(os.path.dirname(__file__), 'dataset', 'classroom.db')

def get_db_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Create tables if they do not exist and populate with seed data."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Students table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS students (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            class TEXT NOT NULL,
            attendance_status TEXT NOT NULL,
            attention_score INTEGER DEFAULT 0,
            emotion TEXT DEFAULT 'Neutral',
            mobile_usage TEXT DEFAULT 'No',
            distraction_score INTEGER DEFAULT 0,
            status TEXT DEFAULT 'Moderate Attention',
            photo_url TEXT
        )
    ''')

    # 2. Attendance table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            date TEXT NOT NULL,
            status TEXT NOT NULL,
            check_in TEXT,
            check_out TEXT,
            duration TEXT,
            FOREIGN KEY (student_id) REFERENCES students (id)
        )
    ''')

    # 3. Mobile phone detections table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS mobile_detections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            date TEXT NOT NULL,
            time TEXT NOT NULL,
            confidence REAL NOT NULL,
            camera TEXT NOT NULL,
            FOREIGN KEY (student_id) REFERENCES students (id)
        )
    ''')

    # 4. Alerts table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            type TEXT NOT NULL, -- 'mobile', 'sleep', 'pose', 'distraction'
            student_id TEXT,
            FOREIGN KEY (student_id) REFERENCES students (id)
        )
    ''')

    # 5. Session history logs (aggregated stats over time)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS session_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            face_count INTEGER NOT NULL,
            attention_pct REAL NOT NULL,
            distraction_score REAL NOT NULL,
            mobile_count INTEGER NOT NULL,
            focused INTEGER NOT NULL,
            distracted INTEGER NOT NULL,
            sleeping INTEGER NOT NULL
        )
    ''')

    # Check if we have student data already
    cursor.execute("SELECT COUNT(*) FROM students")
    if cursor.fetchone()[0] == 0:
        # Seed 25 students matching the screenshots
        mock_students = [
            ('21CS001', 'Ramesh Kumar', 'AI & DS - A', 'Present', 85, 'Happy', 'No', 82, 'Highly Attentive', 'ramesh.jpg'),
            ('21CS002', 'Priya Sharma', 'AI & DS - A', 'Present', 45, 'Neutral', 'Yes', 50, 'Highly Distracted', 'priya.jpg'),
            ('21CS003', 'Arjun Singh', 'AI & DS - A', 'Present', 70, 'Happy', 'No', 70, 'Moderate Attention', 'arjun.jpg'),
            ('21CS004', 'Kavya Nair', 'AI & DS - A', 'Present', 30, 'Sleepy', 'No', 35, 'Highly Distracted', 'kavya.jpg'),
            ('21CS005', 'Manoj Patel', 'AI & DS - A', 'Present', 60, 'Neutral', 'Yes', 60, 'Moderate Attention', 'manoj.jpg'),
            ('21CS006', 'Sneha Reddy', 'AI & DS - A', 'Absent', 0, '-', 'No', 0, 'Absent', 'sneha.jpg'),
            ('21CS007', 'Rahul Verma', 'AI & DS - A', 'Present', 75, 'Happy', 'No', 75, 'Moderate Attention', 'rahul.jpg'),
            ('21CS008', 'Anjali Mehta', 'AI & DS - A', 'Present', 40, 'Sad', 'Yes', 45, 'Highly Distracted', 'anjali.jpg'),
            ('21CS009', 'Deepa Nair', 'AI & DS - A', 'Present', 88, 'Happy', 'No', 90, 'Highly Attentive', 'deepa.jpg'),
            ('21CS010', 'Karthik R', 'AI & DS - A', 'Present', 73, 'Neutral', 'No', 75, 'Moderate Attention', 'karthik.jpg'),
            ('21CS011', 'Meera Pillai', 'AI & DS - A', 'Present', 96, 'Happy', 'No', 95, 'Highly Attentive', 'meera.jpg'),
            ('21CS012', 'Arun Prasad', 'AI & DS - A', 'Present', 55, 'Bored', 'No', 58, 'Highly Distracted', 'arun_p.jpg'),
            ('21CS013', 'Lakshmi Iyer', 'AI & DS - A', 'Present', 80, 'Neutral', 'No', 82, 'Highly Attentive', 'lakshmi.jpg'),
            ('21CS014', 'Vikram Singh', 'AI & DS - A', 'Present', 62, 'Neutral', 'No', 65, 'Moderate Attention', 'vikram.jpg'),
            ('21CS015', 'Siddharth M', 'AI & DS - A', 'Present', 72, 'Happy', 'No', 70, 'Moderate Attention', 'siddharth.jpg'),
            ('21CS016', 'Neha Gupta', 'AI & DS - A', 'Present', 68, 'Neutral', 'No', 70, 'Moderate Attention', 'neha.jpg'),
            ('21CS017', 'Rajesh K', 'AI & DS - A', 'Present', 82, 'Happy', 'No', 84, 'Highly Attentive', 'rajesh.jpg'),
            ('21CS018', 'Pooja Rao', 'AI & DS - A', 'Absent', 0, '-', 'No', 0, 'Absent', 'pooja.jpg'),
            ('21CS019', 'Sanjay Dutt', 'AI & DS - A', 'Present', 77, 'Neutral', 'No', 75, 'Moderate Attention', 'sanjay.jpg'),
            ('21CS020', 'Divya Teja', 'AI & DS - A', 'Present', 83, 'Happy', 'No', 85, 'Highly Attentive', 'divya.jpg'),
            ('21CS021', 'Amit Mishra', 'AI & DS - A', 'Present', 64, 'Bored', 'No', 60, 'Moderate Attention', 'amit.jpg'),
            ('21CS022', 'Ritu Sen', 'AI & DS - A', 'Present', 71, 'Neutral', 'No', 70, 'Moderate Attention', 'ritu.jpg'),
            ('21CS023', 'Varun Dhawan', 'AI & DS - A', 'Absent', 0, '-', 'No', 0, 'Absent', 'varun.jpg'),
            ('21CS024', 'Kriti Sanon', 'AI & DS - A', 'Present', 79, 'Happy', 'No', 80, 'Highly Attentive', 'kriti.jpg'),
            ('21CS025', 'Ranbir K', 'AI & DS - A', 'Absent', 0, '-', 'No', 0, 'Absent', 'ranbir.jpg'),
        ]
        cursor.executemany('''
            INSERT INTO students (id, name, class, attendance_status, attention_score, emotion, mobile_usage, distraction_score, status, photo_url)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', mock_students)

        # Seed attendance records for today
        today_str = date.today().strftime('%Y-%m-%d')
        for roll, name, cls, att_status, _, _, _, _, _, _ in mock_students:
            if att_status == 'Present':
                check_in = '09:00:15 AM' if roll != '21CS004' else '09:15:32 AM'
                status = 'Present' if roll != '21CS004' else 'Late'
                cursor.execute('''
                    INSERT INTO attendance (student_id, date, status, check_in, check_out, duration)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (roll, today_str, status, check_in, '--', '--'))
            else:
                cursor.execute('''
                    INSERT INTO attendance (student_id, date, status, check_in, check_out, duration)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (roll, today_str, 'Absent', '--', '--', '--'))

        # Seed some phone detections for today
        cursor.execute('''
            INSERT INTO mobile_detections (student_id, date, time, confidence, camera)
            VALUES ('21CS002', ?, '10:29:45 AM', 0.92, 'Camera 1'),
                   ('21CS005', ?, '10:27:33 AM', 0.88, 'Camera 1'),
                   ('21CS008', ?, '10:23:02 AM', 0.90, 'Camera 2')
        ''', (today_str, today_str, today_str))

        # Seed some alerts for today
        cursor.execute('''
            INSERT INTO alerts (message, timestamp, type, student_id)
            VALUES ('Mobile phone detected for Priya Sharma', '10:29:45 AM', 'mobile', '21CS002'),
                   ('Arjun is looking down for long time', '10:28:30 AM', 'pose', '21CS003'),
                   ('Kavya is feeling sleepy', '10:27:15 AM', 'sleep', '21CS004'),
                   ('High distraction in the class', '10:26:20 AM', 'distraction', NULL),
                   ('3 students are distracted', '10:25:10 AM', 'distraction', NULL)
        ''')

    conn.commit()
    conn.close()

def get_all_students(search_query=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    if search_query:
        cursor.execute("SELECT * FROM students WHERE name LIKE ? OR id LIKE ?", (f'%{search_query}%', f'%{search_query}%'))
    else:
        cursor.execute("SELECT * FROM students")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_student_by_id(sid):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM students WHERE id = ?", (sid,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def update_student_stats(sid, attention, emotion, mobile, distraction, status):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE students
        SET attention_score = ?, emotion = ?, mobile_usage = ?, distraction_score = ?, status = ?
        WHERE id = ?
    ''', (attention, emotion, mobile, distraction, status, sid))
    conn.commit()
    conn.close()

def add_student(sid, name, cls, status='Present'):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO students (id, name, class, attendance_status, attention_score, emotion, mobile_usage, distraction_score, status, photo_url)
            VALUES (?, ?, ?, ?, 0, 'Neutral', 'No', 0, 'Moderate Attention', 'avatar.jpg')
        ''', (sid, name, cls, status))
        conn.commit()
        success = True
    except sqlite3.IntegrityError:
        success = False
    conn.close()
    return success

def get_attendance(date_str=None):
    if not date_str:
        date_str = date.today().strftime('%Y-%m-%d')
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT a.*, s.name, s.class, s.photo_url
        FROM attendance a
        JOIN students s ON a.student_id = s.id
        WHERE a.date = ?
    ''', (date_str,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def add_alert(message, type_str, student_id=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    now_str = datetime.now().strftime('%I:%M:%S %p')
    cursor.execute('''
        INSERT INTO alerts (message, timestamp, type, student_id)
        VALUES (?, ?, ?, ?)
    ''', (message, now_str, type_str, student_id))
    conn.commit()
    conn.close()

def get_recent_alerts(limit=10):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM alerts ORDER BY id DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def add_phone_detection(student_id, confidence, camera='Camera 1'):
    conn = get_db_connection()
    cursor = conn.cursor()
    today_str = date.today().strftime('%Y-%m-%d')
    now_str = datetime.now().strftime('%I:%M:%S %p')
    cursor.execute('''
        INSERT INTO mobile_detections (student_id, date, time, confidence, camera)
        VALUES (?, ?, ?, ?, ?)
    ''', (student_id, today_str, now_str, confidence, camera))

    # Also check student name for the alert
    cursor.execute("SELECT name FROM students WHERE id = ?", (student_id,))
    s_row = cursor.fetchone()
    name = s_row[0] if s_row else f"Student {student_id}"

    # Log phone alert
    cursor.execute('''
        INSERT INTO alerts (message, timestamp, type, student_id)
        VALUES (?, ?, ?, ?)
    ''', (f"Mobile phone detected for {name}", now_str, 'mobile', student_id))

    # Update student mobile status in students table
    cursor.execute("UPDATE students SET mobile_usage = 'Yes' WHERE id = ?", (student_id,))

    conn.commit()
    conn.close()

def get_phone_detections(date_str=None):
    if not date_str:
        date_str = date.today().strftime('%Y-%m-%d')
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT m.*, s.name, s.class
        FROM mobile_detections m
        JOIN students s ON m.student_id = s.id
        WHERE m.date = ?
        ORDER BY m.id DESC
    ''', (date_str,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]
