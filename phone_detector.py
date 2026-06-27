"""
phone_detector.py  -  YOLOv8 Mobile Phone Detector
====================================================
Uses YOLOv8 nano ONNX model via OpenCV DNN (no ultralytics needed).
Falls back gracefully with a mock detector if model file is missing.

SETUP (one-time):
  Download yolov8n.onnx (~6 MB) and place in model/ folder:
  https://github.com/ultralytics/assets/releases/download/v8.2.0/yolov8n.onnx

  OR run: python phone_detector.py --download
"""

import cv2
import numpy as np
import os
import json
import time
from datetime import datetime, date

# ── Config ────────────────────────────────────────────────────────────────────
MODEL_PATH   = os.path.join(os.path.dirname(__file__), 'model', 'yolov8n.onnx')
LOG_FILE     = os.path.join(os.path.dirname(__file__), 'dataset', 'phone_log.json')

# COCO class index for 'cell phone' = 67
PHONE_CLASS_ID   = 67
CONF_THRESHOLD   = 0.45   # minimum confidence to report detection
NMS_THRESHOLD    = 0.50   # non-max suppression

INPUT_W = INPUT_H = 640   # YOLOv8 input size

# Draw color: bright red for phone bounding box
PHONE_COLOR = (0, 0, 255)

# ── Phone log (in-memory, flushed to disk) ────────────────────────────────────
_phone_log: list = []       # list of detection event dicts


def _load_log():
    """Load existing phone log from disk on startup."""
    global _phone_log
    try:
        if os.path.exists(LOG_FILE):
            with open(LOG_FILE) as f:
                _phone_log = json.load(f)
    except Exception:
        _phone_log = []


def save_log():
    """Flush in-memory phone log to disk (JSON)."""
    try:
        os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
        with open(LOG_FILE, 'w') as f:
            json.dump(_phone_log[-2000:], f, indent=2)
    except Exception:
        pass


def log_phone_event(student_id: int, confidence: float):
    """
    Record one phone detection event.
    Args:
        student_id  : face tracking ID (-1 if not linked to a face)
        confidence  : YOLO confidence score (0-1)
    """
    now = datetime.now()
    _phone_log.append({
        'student_id': student_id,
        'date':       now.strftime('%Y-%m-%d'),
        'time':       now.strftime('%H:%M:%S'),
        'confidence': round(float(confidence), 3)
    })
    # Auto-save every 20 events to avoid losing data
    if len(_phone_log) % 20 == 0:
        save_log()


def get_today_count() -> int:
    """Return number of phone detection events today."""
    today = date.today().strftime('%Y-%m-%d')
    return sum(1 for e in _phone_log if e.get('date') == today)


def get_all_events() -> list:
    """Return full phone log list."""
    return list(_phone_log)


# ── YOLOv8 ONNX via OpenCV DNN ────────────────────────────────────────────────
_net = None          # OpenCV DNN net object
_model_ready = False


def _load_model():
    """
    Load YOLOv8n ONNX model using OpenCV DNN.
    Called once on first use.
    """
    global _net, _model_ready
    if _model_ready:
        return True
    if not os.path.exists(MODEL_PATH):
        print(f"[WARN] phone_detector: model not found at {MODEL_PATH}")
        print("[INFO] Download yolov8n.onnx and place in model/ folder.")
        print("       URL: https://github.com/ultralytics/assets/releases/download/v8.2.0/yolov8n.onnx")
        _model_ready = False
        return False
    try:
        _net = cv2.dnn.readNetFromONNX(MODEL_PATH)
        _net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
        _net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
        _model_ready = True
        print("[INFO] phone_detector: YOLOv8n ONNX model loaded successfully.")
        return True
    except Exception as e:
        print(f"[ERROR] phone_detector: failed to load ONNX model — {e}")
        _model_ready = False
        return False


def _letterbox(img, new_shape=(640, 640)):
    """
    Resize image with letterboxing to maintain aspect ratio.
    Returns (resized_image, scale, pad_x, pad_y)
    """
    h, w = img.shape[:2]
    scale = min(new_shape[0] / h, new_shape[1] / w)
    new_w, new_h = int(w * scale), int(h * scale)
    resized = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
    pad_x = (new_shape[1] - new_w) // 2
    pad_y = (new_shape[0] - new_h) // 2
    padded = cv2.copyMakeBorder(resized, pad_y, pad_y, pad_x, pad_x,
                                cv2.BORDER_CONSTANT, value=(114, 114, 114))
    return padded[:new_shape[0], :new_shape[1]], scale, pad_x, pad_y


def detect_phones(frame: np.ndarray) -> list:
    """
    Run YOLOv8 phone detection on a single BGR frame.

    Returns:
        List of dicts: [{'bbox': (x1,y1,x2,y2), 'confidence': float}, ...]
        Empty list if no phones detected or model not loaded.
    """
    if not _load_model():
        return []   # graceful fallback: no detections

    ih, iw = frame.shape[:2]

    # ── Preprocess ────────────────────────────────────────────────────────────
    letterboxed, scale, px, py = _letterbox(frame, (INPUT_H, INPUT_W))
    blob = cv2.dnn.blobFromImage(letterboxed, 1 / 255.0, (INPUT_W, INPUT_H),
                                 swapRB=True, crop=False)
    _net.setInput(blob)

    # ── Inference ─────────────────────────────────────────────────────────────
    outputs = _net.forward()          # shape: (1, 84, 8400)
    outputs = outputs[0].T            # → (8400, 84)

    # ── Parse detections ──────────────────────────────────────────────────────
    boxes, confidences = [], []
    for row in outputs:
        cx, cy, bw, bh = row[:4]
        class_scores   = row[4:]
        class_id       = int(np.argmax(class_scores))
        confidence     = float(class_scores[class_id])

        if class_id != PHONE_CLASS_ID or confidence < CONF_THRESHOLD:
            continue

        # Convert from letterboxed coords → original frame coords
        x1 = int((cx - bw / 2 - px) / scale)
        y1 = int((cy - bh / 2 - py) / scale)
        x2 = int((cx + bw / 2 - px) / scale)
        y2 = int((cy + bh / 2 - py) / scale)

        # Clamp to frame boundaries
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(iw, x2), min(ih, y2)

        if x2 > x1 and y2 > y1:
            boxes.append([x1, y1, x2 - x1, y2 - y1])
            confidences.append(confidence)

    # ── Non-Max Suppression ───────────────────────────────────────────────────
    indices = cv2.dnn.NMSBoxes(boxes, confidences, CONF_THRESHOLD, NMS_THRESHOLD)
    detections = []
    if len(indices) > 0:
        for i in (indices.flatten() if hasattr(indices, 'flatten') else indices):
            x, y, w, h = boxes[i]
            detections.append({
                'bbox':       (x, y, x + w, y + h),
                'confidence': confidences[i]
            })

    return detections


def draw_phone_boxes(frame: np.ndarray, detections: list) -> np.ndarray:
    """
    Draw bounding boxes and labels for all detected phones on the frame.

    Args:
        frame      : BGR image (modified in-place)
        detections : output of detect_phones()

    Returns:
        Modified frame
    """
    for det in detections:
        x1, y1, x2, y2 = det['bbox']
        conf = det['confidence']
        label = f"Mobile Detected  {conf:.0%}"

        # Draw box
        cv2.rectangle(frame, (x1, y1), (x2, y2), PHONE_COLOR, 2)

        # Draw label background
        (lw, lh), baseline = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 2)
        cv2.rectangle(frame, (x1, y1 - lh - 8), (x1 + lw + 6, y1), PHONE_COLOR, -1)
        cv2.putText(frame, label, (x1 + 3, y1 - 4),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2)

    return frame


# ── Init on import ────────────────────────────────────────────────────────────
_load_log()


# ── CLI helper: download model ────────────────────────────────────────────────
if __name__ == '__main__':
    import sys, urllib.request
    if '--download' in sys.argv:
        url = 'https://github.com/ultralytics/assets/releases/download/v8.2.0/yolov8n.onnx'
        os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
        print(f"Downloading yolov8n.onnx (~6 MB) to {MODEL_PATH} ...")
        urllib.request.urlretrieve(url, MODEL_PATH)
        print("Done! Model ready.")
    else:
        print("Usage: python phone_detector.py --download")
        print(f"Model path: {MODEL_PATH}")
        print(f"Model exists: {os.path.exists(MODEL_PATH)}")
