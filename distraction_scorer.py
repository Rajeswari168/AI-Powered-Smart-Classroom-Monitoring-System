"""
distraction_scorer.py  -  AI-Based Distraction Score Calculator
================================================================
Calculates a 0-100 distraction score per student using:
  - Attention (eye tracking / eye open state)
  - Emotion (DeepFace result)
  - Head Pose (up / down / forward estimate)
  - Mobile Phone Detection (YOLOv8 result)

Scoring Logic:
  +40   Eyes open / Looking at board (attentive)
  +20   Happy or Neutral emotion
  -30   Mobile phone detected near this student
  -20   Looking down (head pose)
  -40   Sleeping / Drowsy

Score is normalised to 0-100:
  80-100  → "Highly Attentive"   (green)
  60-79   → "Moderate Attention" (orange)
  0-59    → "Highly Distracted"  (red)
"""

# ── Score weights (tweak here without touching other files) ───────────────────
WEIGHTS = {
    'eyes_open':       +40,   # looking at the board
    'positive_emotion':+20,   # happy / neutral
    'mobile_detected': -30,   # phone in hand / nearby
    'looking_down':    -20,   # head tilted down
    'sleeping':        -40,   # drowsy / eyes closed for N frames
}

# Emotions considered "positive" for attention
POSITIVE_EMOTIONS = {'Happy', 'Neutral'}

# Labels and their colours (CSS / hex) for the UI
SCORE_LABELS = {
    'Highly Attentive':   {'min': 80, 'color': '#22c55e', 'bg': '#f0fdf4'},
    'Moderate Attention': {'min': 60, 'color': '#f59e0b', 'bg': '#fffbeb'},
    'Highly Distracted':  {'min':  0, 'color': '#ef4444', 'bg': '#fef2f2'},
}


# ── Public API ────────────────────────────────────────────────────────────────

def calculate_score(
    eyes_open:        bool,
    is_drowsy:        bool,
    emotion:          str,
    mobile_detected:  bool,
    head_pose:        str   = 'Forward',
) -> int:
    """
    Calculate distraction score for one student in one frame.

    Args:
        eyes_open       : True if eyes are detected as open (EAR check)
        is_drowsy       : True if drowsiness counter >= threshold
        emotion         : Emotion string from DeepFace ('Happy','Neutral','Bored','Distracted')
        mobile_detected : True if a phone was detected near this student
        head_pose       : 'Up' | 'Forward' | 'Down'  (from head_pose_estimator)

    Returns:
        Integer score 0-100
    """
    score = 0

    # +40 for looking at the board (eyes open and not sleeping)
    if eyes_open and not is_drowsy:
        score += WEIGHTS['eyes_open']

    # +20 for positive / calm emotion
    if emotion in POSITIVE_EMOTIONS:
        score += WEIGHTS['positive_emotion']

    # -30 if mobile phone detected nearby
    if mobile_detected:
        score += WEIGHTS['mobile_detected']   # negative

    # -20 if student is looking down
    if head_pose == 'Down':
        score += WEIGHTS['looking_down']      # negative

    # -40 if sleeping / drowsy
    if is_drowsy:
        score += WEIGHTS['sleeping']          # negative

    # Normalise: base is 0, max possible raw = +60, min = -70
    # Shift by +40 to keep "neutral eyes-open student" at ~60
    normalised = score + 40

    # Clamp to [0, 100]
    return max(0, min(100, normalised))


def get_label(score: int) -> str:
    """
    Return human-readable attention label for a given score.

    Args:
        score : integer 0-100

    Returns:
        'Highly Attentive' | 'Moderate Attention' | 'Highly Distracted'
    """
    if score >= 80:
        return 'Highly Attentive'
    elif score >= 60:
        return 'Moderate Attention'
    else:
        return 'Highly Distracted'


def get_color(score: int) -> str:
    """Return hex color string for the score badge."""
    if score >= 80:
        return SCORE_LABELS['Highly Attentive']['color']
    elif score >= 60:
        return SCORE_LABELS['Moderate Attention']['color']
    else:
        return SCORE_LABELS['Highly Distracted']['color']


def get_bgr_color(score: int) -> tuple:
    """Return BGR tuple for OpenCV drawing."""
    if score >= 80:
        return (100, 200, 0)    # green
    elif score >= 60:
        return (0, 165, 255)    # orange
    else:
        return (0, 0, 255)      # red


# ── Head Pose Estimator (geometry-based, no MediaPipe needed) ─────────────────

def estimate_head_pose(face_rect: tuple, eye_rects: list) -> str:
    """
    Estimate head pose from face bounding box and eye positions.
    Uses simple geometry: if detected eyes are in the upper half of the face
    → looking forward/up.  If no eyes detected or eyes are low → looking down.

    Args:
        face_rect  : (fx, fy, fw, fh) face bounding box
        eye_rects  : list of (ex, ey, ew, eh) within face ROI

    Returns:
        'Forward' | 'Down' | 'Up'
    """
    fx, fy, fw, fh = face_rect

    # If no eyes detected at all → likely looking down
    if len(eye_rects) == 0:
        return 'Down'

    # Average vertical position of eyes within face (0 = top, 1 = bottom)
    avg_eye_y = sum(ey + eh // 2 for (ex, ey, ew, eh) in eye_rects) / len(eye_rects)
    ratio = avg_eye_y / fh   # 0.0 (top of face) → 1.0 (bottom)

    if ratio < 0.35:
        return 'Up'
    elif ratio > 0.65:
        return 'Down'
    else:
        return 'Forward'


# ── Batch summary helper ──────────────────────────────────────────────────────

def summarise_students(students: list) -> dict:
    """
    Given the current students list from the stats dict, return summary metrics.

    Args:
        students : list of student dicts (each has 'distraction_score', 'status', etc.)

    Returns:
        dict with 'avg_score', 'most_attentive', 'most_distracted'
    """
    if not students:
        return {'avg_score': 0, 'most_attentive': None, 'most_distracted': None}

    scores = [(s['id'], s.get('distraction_score', 50)) for s in students]
    avg    = round(sum(v for _, v in scores) / len(scores), 1)

    most_attentive   = max(scores, key=lambda x: x[1])
    most_distracted  = min(scores, key=lambda x: x[1])

    return {
        'avg_score':       avg,
        'most_attentive':  {'id': most_attentive[0],  'score': most_attentive[1]},
        'most_distracted': {'id': most_distracted[0], 'score': most_distracted[1]},
    }
