"""
app.py  -  Smart Classroom Attention Detector  (Complete Version)
Flask backend: MJPEG stream, SSE stats, REST API, all page routes.

NEW (v3):
  - /advanced-dashboard   : full analytics page with distraction + phone stats
  - /api/phone-log        : today's phone detection events (JSON)
  - /api/distraction-summary : avg score, top attentive/distracted students
  - /api/export-csv       : enhanced CSV with distraction_score column
"""

import cv2, json, time, os, threading, io, csv, base64
from datetime import datetime, date
from functools import wraps
from flask import (Flask, Response, render_template, jsonify,
                   redirect, url_for, request, session)
from attention_detector import AttentionDetector
import database

# NEW: optional phone_detector for log access
try:
    import phone_detector as _pd
    _pd_ok = True
except Exception:
    _pd_ok = False

app = Flask(__name__)
app.secret_key = 'scad_secret_key_2024'

# ── Globals ───────────────────────────────────────────────────────────────────
detector    = AttentionDetector()
camera      = None
cam_lock    = threading.Lock()
monitoring  = True
latest_stats: dict = {}
alert_log: list   = []          # persisted alert history

HISTORY_FILE = os.path.join(os.path.dirname(__file__), 'dataset', 'history.json')


# ── Camera helpers ────────────────────────────────────────────────────────────
def open_camera():
    global camera
    with cam_lock:
        if camera is None or not camera.isOpened():
            camera = cv2.VideoCapture(0, cv2.CAP_DSHOW)
            camera.set(cv2.CAP_PROP_FRAME_WIDTH,  640)
            camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            camera.set(cv2.CAP_PROP_FPS, 20)

def release_camera():
    global camera
    with cam_lock:
        if camera and camera.isOpened():
            camera.release()
            camera = None

def gen_frames():
    global latest_stats, monitoring, alert_log
    open_camera()
    while monitoring:
        with cam_lock:
            if camera is None: break
            ok, frame = camera.read()
        if not ok:
            time.sleep(0.05); continue

        frame, stats = detector.process_frame(frame)
        latest_stats = stats

        # Log alerts
        if stats.get('alert'):
            ts  = datetime.now().strftime('%H:%M:%S')
            msg = f"{ts} — Drowsiness/Sleeping detected!"
            if not alert_log or alert_log[-1] != msg:
                alert_log.append(msg)
                if len(alert_log) > 200: alert_log.pop(0)

        _, buf = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + buf.tobytes() + b'\r\n')

    release_camera()

def save_history():
    try:
        os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
        with open(HISTORY_FILE, 'w') as f:
            json.dump(detector.get_history(), f)
    except Exception: pass

def load_history():
    try:
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE) as f:
                return json.load(f)
    except Exception: pass
    return []


# ── Auth ──────────────────────────────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

@app.route('/', methods=['GET', 'POST'])
def login():
    if 'user' in session:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        u = request.form.get('username', '')
        p = request.form.get('password', '')
        if u == 'teacher' and p == 'admin123':
            session['user'] = u
            return redirect(url_for('dashboard'))
        return render_template('index.html', error='Invalid credentials. Try teacher / admin123')
    return render_template('index.html')

@app.route('/logout')
def logout():
    global monitoring
    monitoring = False
    save_history()
    session.clear()
    return redirect(url_for('login'))


# ── Page routes ───────────────────────────────────────────────────────────────
@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html')

@app.route('/live-monitoring')
@login_required
def live_monitoring():
    return render_template('live.html')

@app.route('/analytics')
@login_required
def analytics():
    return render_template('analytics.html')

@app.route('/reports')
@login_required
def reports():
    return render_template('reports.html')

@app.route('/students')
@login_required
def students():
    return render_template('students.html')

@app.route('/attendance')
@login_required
def attendance():
    return render_template('attendance.html')

@app.route('/attention-emotions')
@login_required
def attention_emotions():
    return render_template('attention_emotions.html')

@app.route('/mobile-detection')
@login_required
def mobile_detection():
    return render_template('mobile_detection.html')

@app.route('/distraction-score')
@login_required
def distraction_score():
    return render_template('distraction_score.html')

@app.route('/settings')
@login_required
def settings_page():
    return render_template('settings.html')

# NEW: Advanced Dashboard page
@app.route('/advanced-dashboard')
@login_required
def advanced_dashboard():
    return render_template('advanced_dashboard.html')

# 404 handler
@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404


# ── Video stream ──────────────────────────────────────────────────────────────
@app.route('/video_feed')
@login_required
def video_feed():
    if not monitoring:
        return Response(status=204)
    return Response(gen_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')


# ── Control API ───────────────────────────────────────────────────────────────
@app.route('/api/start', methods=['POST'])
@login_required
def api_start():
    global monitoring
    detector.reset()
    monitoring = True
    return jsonify({'status': 'started', 'time': datetime.now().strftime('%H:%M:%S')})

@app.route('/api/stop', methods=['POST'])
@login_required
def api_stop():
    global monitoring
    monitoring = False
    save_history()
    return jsonify({'status': 'stopped'})

@app.route('/api/reset', methods=['POST'])
@login_required
def api_reset():
    detector.reset()
    alert_log.clear()
    return jsonify({'status': 'reset'})


# ── Data API ──────────────────────────────────────────────────────────────────
@app.route('/api/stats')
@login_required
def api_stats():
    return jsonify(latest_stats)

@app.route('/api/history')
@login_required
def api_history():
    live  = detector.get_history()
    saved = load_history() if not live else []
    combined = (saved + live)[-300:]
    return jsonify(combined)

@app.route('/api/alerts')
@login_required
def api_alerts():
    return jsonify(alert_log[-50:])

@app.route('/api/status')
@login_required
def api_status():
    return jsonify({
        'monitoring': monitoring,
        'total_frames': latest_stats.get('total_frames', 0),
        'session_start': latest_stats.get('session_start', '--'),
        'alert_count': len(alert_log),
    })


# ── NEW API routes ────────────────────────────────────────────────────────────

@app.route('/api/phone-log')
@login_required
def api_phone_log():
    """Return today's mobile phone detection events."""
    if _pd_ok:
        events = _pd.get_all_events()
        today  = date.today().strftime('%Y-%m-%d')
        today_events = [e for e in events if e.get('date') == today]
        return jsonify({
            'today_count': len(today_events),
            'events': today_events[-50:],
        })
    # Fallback: use stats counter
    return jsonify({
        'today_count': latest_stats.get('mobile_count', 0),
        'events': []
    })


@app.route('/api/distraction-summary')
@login_required
def api_distraction_summary():
    """Return avg distraction score and top attentive/distracted students."""
    history = detector.get_history()
    students_now = latest_stats.get('students', [])

    # Current session summary
    avg_score = latest_stats.get('avg_distraction_score', 0)

    # Sort students by distraction score
    sorted_students = sorted(students_now, key=lambda s: s.get('distraction_score', 50))
    most_distracted = sorted_students[:3]   if sorted_students else []
    most_attentive  = sorted_students[-3:][::-1] if sorted_students else []

    # Weekly trend from history (last 300 records)
    daily_scores = {}
    for rec in history[-300:]:
        day = rec.get('timestamp','')[:5]  # HH:MM
        if day:
            daily_scores.setdefault(day, []).append(rec.get('avg_distraction', 0))
    trend = [
        {'time': k, 'score': round(sum(v)/len(v), 1)}
        for k, v in daily_scores.items()
    ]

    return jsonify({
        'avg_distraction_score': avg_score,
        'most_distracted': most_distracted,
        'most_attentive':  most_attentive,
        'trend': trend[-30:],
        'mobile_today': latest_stats.get('mobile_count', 0),
    })


@app.route('/api/export-csv')
@login_required
def api_export_csv():
    """
    Export full session history as CSV.
    NEW column: avg_distraction, mobile_count added to each row.
    """
    history = detector.get_history()
    si  = io.StringIO()
    cw  = csv.writer(si)
    # Header
    cw.writerow(['Timestamp','Face Count','Attention %','Avg Distraction Score',
                 'Mobile Count','Focused','Distracted','Sleeping'])
    for rec in history:
        students = rec.get('students', [])
        focused    = sum(1 for s in students if s.get('status')=='Focused')
        distracted = sum(1 for s in students if s.get('status')=='Distracted')
        sleeping   = sum(1 for s in students if s.get('status')=='Sleeping')
        cw.writerow([
            rec.get('timestamp',''),
            rec.get('face_count', 0),
            rec.get('attention_pct', 0),
            rec.get('avg_distraction', 0),    # NEW
            rec.get('mobile_count', 0),       # NEW
            focused, distracted, sleeping,
        ])
    output = si.getvalue()
    return Response(
        output,
        mimetype='text/csv',
        headers={'Content-Disposition':
                 f'attachment; filename=session_{datetime.now().strftime("%Y%m%d_%H%M")}.csv'}
    )


# ── SQLite Database API ───────────────────────────────────────────────────────

@app.route('/api/db-students')
@login_required
def api_db_students():
    """Return all registered students from SQLite."""
    q = request.args.get('q')
    students = database.get_all_students(q)
    return jsonify(students)

@app.route('/api/db-alerts')
@login_required
def api_db_alerts():
    """Return recent alerts from SQLite."""
    limit = request.args.get('limit', 10, type=int)
    alerts = database.get_recent_alerts(limit)
    return jsonify(alerts)

@app.route('/api/db-attendance')
@login_required
def api_db_attendance():
    """Return attendance list for a specific date from SQLite."""
    d = request.args.get('date')
    records = database.get_attendance(d)
    return jsonify(records)

@app.route('/api/db-mobile-detections')
@login_required
def api_db_mobile_detections():
    """Return mobile detections for a specific date from SQLite."""
    d = request.args.get('date')
    records = database.get_phone_detections(d)
    return jsonify(records)

@app.route('/api/add-student', methods=['POST'])
@login_required
def api_add_student():
    """Add a new student to the database roster and save their face photo."""
    data = request.json or {}
    sid = data.get('id')
    name = data.get('name')
    dept = data.get('department', '').strip()
    sect = data.get('section', '').strip()
    face_image_b64 = data.get('face_image')  # base64 string
    
    if not sid or not name:
        return jsonify({'success': False, 'error': 'Missing ID or Name'}), 400
    
    cls = f"{dept} - {sect}" if (dept and sect) else (dept or sect or 'AI & DS - A')
    
    photo_url = 'avatar.jpg'
    if face_image_b64 and ',' in face_image_b64:
        try:
            # Create uploads directory if not exists
            faces_dir = os.path.join(app.static_folder, 'uploads', 'faces')
            os.makedirs(faces_dir, exist_ok=True)
            
            # Decode base64
            img_data = base64.b64decode(face_image_b64.split(',')[1])
            file_name = f"{sid}.jpg"
            file_path = os.path.join(faces_dir, file_name)
            
            with open(file_path, 'wb') as f:
                f.write(img_data)
                
            photo_url = f"/static/uploads/faces/{file_name}"
        except Exception as e:
            print(f"[ERROR] Failed to save face photo: {e}")
            
    success = database.add_student(sid, name, cls, photo_url=photo_url)
    if success:
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'error': 'Student ID already exists'})



# ── SSE live stream ───────────────────────────────────────────────────────────
@app.route('/api/stream')
@login_required
def api_stream():
    def gen():
        while True:
            yield f"data: {json.dumps(latest_stats)}\n\n"
            time.sleep(0.5)
    return Response(gen(), mimetype='text/event-stream',
                    headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == '__main__':
    print("=" * 55)
    print("  Smart Classroom Attention Detector  v2.0")
    print("  URL  -> http://127.0.0.1:5000")
    print("  Login-> teacher / admin123")
    print("=" * 55)
    app.run(debug=False, threaded=True, host='0.0.0.0', port=5000)
