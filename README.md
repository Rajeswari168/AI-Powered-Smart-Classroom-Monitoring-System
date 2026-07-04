# Smart Classroom Attention Detector

An AI-powered real-time classroom monitoring system built with Python, OpenCV, DeepFace, and Flask.

---

## Quick Start

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Run the app
```bash
python app.py
```
Or double-click **`run.bat`**

### 3. Open browser
```
http://localhost:5000
```

### 4. Login

| Field | Value |
|-------|-------|
| Username | `teacher` |
| Password | `admin123` |

---

## Folder Structure

```text
Mini project/
│
├── app.py                    ← Flask server (main entry point)
├── attention_detector.py     ← Core AI engine
├── run.bat                   ← Double-click to run
├── requirements.txt
│
├── templates/
│   ├── index.html            ← Login page
│   ├── dashboard.html        ← Live monitoring dashboard
│   ├── analytics.html        ← Analytics charts
│   └── reports.html          ← Session history & export
│
├── static/
│   ├── css/style.css         ← Design system
│   └── js/dashboard.js       ← Real-time JS logic
│
├── model/                    ← Place custom .h5 models here
└── dataset/                  ← Training data (optional)
```

---

## How the AI Works

| Feature | Method |
|---------|--------|
| **Face Detection** | OpenCV Haar Cascade (`haarcascade_frontalface_default.xml`) |
| **Eye Detection** | OpenCV Haar Cascade (`haarcascade_eye.xml`) |
| **Drowsiness** | Eye Aspect Ratio (EAR) — geometric algorithm |
| **Emotion** | DeepFace (pre-trained VGG-Face / FER2013 model) |
| **Attention %** | `Attentive Frames / Total Frames × 100` |

### Eye Aspect Ratio (EAR)

```text
EAR = (vertical height) / (2 × horizontal width)

If EAR < 0.25 for 20+ consecutive frames → Drowsy Alert
```

---

## Dashboard Pages

| Page | URL | Description |
|------|-----|-------------|
| Login | `/` | Authentication |
| Dashboard | `/dashboard` | Live webcam feed + real-time stats |
| Analytics | `/analytics` | Charts, emotion breakdown, student table |
| Reports | `/reports` | Session history & CSV export |

---

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/video_feed` | GET | MJPEG video stream |
| `/api/start` | POST | Start monitoring session |
| `/api/stop` | POST | Stop monitoring session |
| `/api/stats` | GET | JSON: current frame stats |
| `/api/history` | GET | JSON: last 60 seconds of data |
| `/api/stream` | GET | SSE: live stats push |
| `/api/reset` | POST | Reset session counters |

---

## Configuration

Edit `attention_detector.py` to tune:

```python
EAR_THRESHOLD = 0.25      # EAR below this → eyes closed
EAR_CONSEC_FRAMES = 20    # Frames before drowsy alert
ATTENTION_WINDOW = 100     # Rolling window size
```

---

## Tech Stack

- **Python 3.x**
- **Flask 3.x** — Web server
- **OpenCV 4.x** — Video capture & Haar cascades
- **DeepFace** — Emotion detection (wraps FER2013 CNN)
- **SciPy** — EAR distance calculations
- **Chart.js** — Analytics charts (CDN)
- **HTML5/CSS3/JavaScript** — Dark purple dashboard UI

---

## Notes

- The app uses your **default webcam** (index `0`). If you have multiple cameras, change `cv2.VideoCapture(0)` in `app.py`.
- DeepFace downloads pre-trained weights on the **first run** (~1 GB). Allow internet access.
- For offline use, the app automatically falls back to **brightness-based emotion heuristics** if DeepFace is unavailable.
