"""
attention_detector.py  -  Smart Classroom Attention Detector (v3)
=================================================================
Existing features (UNCHANGED):
  - Haar Cascade face detection
  - EAR-based eye tracking and drowsiness detection
  - DeepFace emotion classification (optional)

NEW integrations (added, nothing removed):
  - phone_detector.detect_phones()       -> YOLOv8 phone detection
  - distraction_scorer.calculate_score() -> AI distraction score
  - distraction_scorer.estimate_head_pose() -> head pose from geometry
  - stats dict: adds mobile_count, avg_distraction_score, per-student new fields
"""

import cv2, numpy as np, time, threading
from datetime import datetime

# Thresholds (UNCHANGED)
EAR_THRESHOLD     = 0.25
EAR_CONSEC_FRAMES = 20
ATTENTION_WINDOW  = 100

EMOTION_DISPLAY = {
    'angry':'Distracted','disgust':'Distracted','fear':'Distracted',
    'happy':'Happy','neutral':'Neutral','sad':'Bored','surprise':'Distracted'
}
STATUS_COLOR = {
    'Focused':(0,220,100), 'Distracted':(0,165,255), 'Sleeping':(0,0,255)
}

# Haar Cascades (UNCHANGED)
_D = cv2.data.haarcascades
FACE_CASCADE = cv2.CascadeClassifier(_D + 'haarcascade_frontalface_default.xml')
EYE_CASCADE  = cv2.CascadeClassifier(_D + 'haarcascade_eye.xml')

# DeepFace optional (UNCHANGED)
_deepface_ok = False
try:
    from deepface import DeepFace
    _deepface_ok = True
    print("[INFO] DeepFace loaded.")
except Exception as e:
    print(f"[WARN] DeepFace not available ({e}).")

# NEW: phone detector
_phone_ok = False
try:
    import phone_detector as _pd
    _phone_ok = True
    print("[INFO] phone_detector loaded.")
except Exception as e:
    print(f"[WARN] phone_detector unavailable ({e}).")

# NEW: distraction scorer
_scorer_ok = False
try:
    import distraction_scorer as _ds
    _scorer_ok = True
    print("[INFO] distraction_scorer loaded.")
except Exception as e:
    print(f"[WARN] distraction_scorer unavailable ({e}).")

# NEW: Import SQLite database backend
import database

class StudentState:
    def __init__(self, sid):
        self.sid = sid
        self.ear_counter = 0
        self.is_drowsy   = False
        self.emotion     = 'Neutral'
        self.status      = 'Focused'
        self.attn_frames = []
        self.last_seen   = time.time()
        self._cx = self._cy = 0
        # NEW fields
        self.head_pose        = 'Forward'
        self.distraction_score = 80
        self.mobile_detected   = False
        # DB fields
        self.db_id            = f"21CS{str(sid+1).zfill(3)}"
        self.name             = f"Student {sid+1}"
        self._load_db_name()

    def _load_db_name(self):
        try:
            student = database.get_student_by_id(self.db_id)
            if student:
                self.name = student['name'].split()[0] # Use first name (e.g., 'Ramesh')
        except Exception:
            pass

    @property
    def attention_pct(self):
        w = self.attn_frames[-ATTENTION_WINDOW:]
        return round(sum(w)/len(w)*100, 1) if w else 100.0


class AttentionDetector:
    def __init__(self):
        self._states: dict       = {}
        self._next_id            = 0
        self._lock               = threading.Lock()
        self.total_frames        = 0
        self.att_frames          = 0
        self.session_start       = datetime.now()
        self.history: list       = []
        self._last_log           = time.time()
        self.emotion_counts      = {'Happy':0,'Neutral':0,'Bored':0,'Distracted':0}
        # NEW counters
        self.mobile_detections   = 0
        self.total_distraction   = 0.0
        self.distraction_samples = 0

    @staticmethod
    def _ear(rect) -> float:
        x, y, w, h = rect
        return (h/(2.0*w)) if w > 0 else 0.0

    def _get_emotion(self, bgr_roi: np.ndarray) -> str:
        if _deepface_ok and bgr_roi.size > 300:
            try:
                r   = DeepFace.analyze(bgr_roi, actions=['emotion'],
                                       enforce_detection=False, silent=True)
                raw = r[0]['dominant_emotion'].lower()
                return EMOTION_DISPLAY.get(raw, 'Neutral')
            except Exception:
                pass
        gray = cv2.cvtColor(bgr_roi, cv2.COLOR_BGR2GRAY)
        b    = np.mean(gray)
        return 'Happy' if b > 140 else 'Neutral' if b > 100 else 'Bored'

    def _match(self, cx, cy) -> int:
        best_id, best_d = None, 120
        now = time.time()
        for sid, st in self._states.items():
            if now - st.last_seen > 3: continue
            d = abs(st._cx - cx) + abs(st._cy - cy)
            if d < best_d: best_d, best_id = d, sid
        if best_id is None:
            best_id = self._next_id
            self._states[best_id] = StudentState(best_id)
            self._next_id += 1
        st = self._states[best_id]
        st._cx, st._cy, st.last_seen = cx, cy, time.time()
        return best_id

    def _cleanup(self):
        stale = [s for s,st in self._states.items() if time.time()-st.last_seen > 5]
        for s in stale: del self._states[s]

    @staticmethod
    def _phone_near_face(phones, fx, fy, fw, fh) -> bool:
        """True if any phone bbox centroid is within 2x face width of face centre."""
        fcx, fcy = fx + fw//2, fy + fh//2
        r = fw * 2
        for d in phones:
            px1,py1,px2,py2 = d['bbox']
            if abs((px1+px2)//2 - fcx) < r and abs((py1+py2)//2 - fcy) < r:
                return True
        return False

    def process_frame(self, frame: np.ndarray):
        with self._lock:
            self.total_frames += 1
            self._cleanup()

            gray  = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            gray  = cv2.equalizeHist(gray)
            faces = FACE_CASCADE.detectMultiScale(
                gray, scaleFactor=1.1, minNeighbors=5, minSize=(50,50))

            # NEW: phone detection every 3 frames
            phone_detections = []
            if _phone_ok and self.total_frames % 3 == 0:
                phone_detections = _pd.detect_phones(frame)
                if phone_detections:
                    self.mobile_detections += len(phone_detections)
            if _phone_ok and phone_detections:
                frame = _pd.draw_phone_boxes(frame, phone_detections)

            any_att  = False
            students = []

            for (fx, fy, fw, fh) in faces:
                sid   = self._match(fx+fw//2, fy+fh//2)
                state = self._states[sid]
                roi_gray = gray[fy:fy+fh, fx:fx+fw]
                roi_bgr  = frame[fy:fy+fh, fx:fx+fw]

                # Eye detection (UNCHANGED)
                eyes = EYE_CASCADE.detectMultiScale(
                    roi_gray, scaleFactor=1.1, minNeighbors=4, minSize=(15,15))
                eyes_open   = False
                eye_rects_l = []
                for (ex,ey,ew,eh) in eyes[:2]:
                    if self._ear((ex,ey,ew,eh)) > EAR_THRESHOLD: eyes_open = True
                    eye_rects_l.append((ex,ey,ew,eh))
                    cv2.rectangle(frame, (fx+ex,fy+ey), (fx+ex+ew,fy+ey+eh), (0,255,255), 1)
                if len(eyes) == 0: eyes_open = False

                # Drowsiness (UNCHANGED)
                state.ear_counter = (state.ear_counter+1) if not eyes_open \
                                    else max(0, state.ear_counter-1)
                state.is_drowsy   = state.ear_counter >= EAR_CONSEC_FRAMES

                # Emotion every 15 frames (UNCHANGED)
                if self.total_frames % 15 == 0 and roi_bgr.size > 0:
                    try: state.emotion = self._get_emotion(roi_bgr)
                    except Exception: pass

                # Attention (UNCHANGED)
                att = eyes_open and not state.is_drowsy
                state.attn_frames.append(att)
                if att: any_att = True

                # Status (UNCHANGED)
                state.status = ('Sleeping'   if state.is_drowsy else
                                'Distracted' if not eyes_open   else 'Focused')

                emo = state.emotion
                if emo in self.emotion_counts: self.emotion_counts[emo] += 1
                pct = state.attention_pct

                # NEW: head pose
                state.head_pose = _ds.estimate_head_pose((fx,fy,fw,fh), eye_rects_l) \
                                  if _scorer_ok else 'Forward'

                # NEW: mobile near face
                state.mobile_detected = self._phone_near_face(phone_detections, fx,fy,fw,fh)
                if state.mobile_detected:
                    if _phone_ok:
                        best_c = max((d['confidence'] for d in phone_detections), default=0.0)
                        _pd.log_phone_event(sid, best_c)
                    # Write to database (NEW)
                    try:
                        database.add_phone_detection(state.db_id, 0.85, 'Camera 1')
                    except Exception:
                        pass

                # NEW: distraction score
                if _scorer_ok:
                    state.distraction_score = _ds.calculate_score(
                        eyes_open=eyes_open, is_drowsy=state.is_drowsy,
                        emotion=emo, mobile_detected=state.mobile_detected,
                        head_pose=state.head_pose)
                    score_label = _ds.get_label(state.distraction_score)
                    score_bgr   = _ds.get_bgr_color(state.distraction_score)
                else:
                    state.distraction_score = int(pct)
                    score_label = state.status
                    score_bgr   = STATUS_COLOR.get(state.status,(180,180,180))

                self.total_distraction   += state.distraction_score
                self.distraction_samples += 1

                # Update database student stats in real-time (NEW)
                try:
                    database.update_student_stats(
                        state.db_id,
                        int(pct),
                        emo,
                        'Yes' if state.mobile_detected else 'No',
                        state.distraction_score,
                        score_label
                    )
                except Exception:
                    pass

                students.append({
                    'id':sid,
                    'roll_no':state.db_id,
                    'name':state.name,
                    'status':state.status,
                    'emotion':emo,
                    'is_drowsy':state.is_drowsy,
                    'attention_pct':pct,
                    'head_pose':state.head_pose,
                    'mobile_detected':state.mobile_detected,
                    'distraction_score':state.distraction_score,
                    'score_label':score_label,
                })

                # Determine BGR color for drawing bounding box
                col = (0, 220, 100) # Green default
                if state.mobile_detected:
                    col = (0, 0, 255) # Red for mobile usage
                elif state.is_drowsy:
                    col = (180, 0, 180) # Purple for sleeping
                elif state.head_pose == 'Down':
                    col = (0, 165, 255) # Orange for looking down
                elif state.status == 'Distracted':
                    col = (0, 165, 255) # Orange for distracted

                # Draw student face bounding box
                cv2.rectangle(frame, (fx, fy), (fx+fw, fy+fh), col, 2)

                # Solid header block on top of face box (matching screenshots)
                header_h = 58
                cv2.rectangle(frame, (fx, fy - header_h), (fx + fw, fy), col, -1)
                
                # Text inside header (white text)
                cv2.putText(frame, state.name, (fx + 5, fy - 44), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (255, 255, 255), 1, cv2.LINE_AA)
                cv2.putText(frame, f"Attention: {pct:.0f}%", (fx + 5, fy - 32), cv2.FONT_HERSHEY_SIMPLEX, 0.32, (255, 255, 255), 1, cv2.LINE_AA)
                cv2.putText(frame, f"Emotion: {emo}", (fx + 5, fy - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.32, (255, 255, 255), 1, cv2.LINE_AA)
                cv2.putText(frame, f"Score: {state.distraction_score}%", (fx + 5, fy - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.32, (255, 255, 255), 1, cv2.LINE_AA)

                # Label below chin if looking down
                if state.head_pose == 'Down':
                    cv2.rectangle(frame, (fx, fy + fh), (fx + fw, fy + fh + 18), (0, 165, 255), -1)
                    cv2.putText(frame, "Looking Down", (fx + 5, fy + fh + 13), cv2.FONT_HERSHEY_SIMPLEX, 0.32, (255, 255, 255), 1, cv2.LINE_AA)

                # Bounding box for phone if detected
                if state.mobile_detected:
                    cv2.rectangle(frame, (fx - 10, fy + fh//2), (fx + fw + 10, fy + fh + 30), (0, 0, 255), 2)
                    cv2.rectangle(frame, (fx - 10, fy + fh//2 - 18), (fx + 95, fy + fh//2), (0, 0, 255), -1)
                    cv2.putText(frame, "Mobile Detected", (fx - 7, fy + fh//2 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.32, (255, 255, 255), 1, cv2.LINE_AA)

            # Global attention
            if any_att: self.att_frames += 1
            overall = round(self.att_frames/self.total_frames*100,1) if self.total_frames else 0.0
            avg_dis = round(self.total_distraction/self.distraction_samples,1) \
                      if self.distraction_samples > 0 else 0.0

            # HUD (UNCHANGED + mobile count)
            h,w = frame.shape[:2]
            ov = frame.copy()
            cv2.rectangle(ov,(0,0),(w,36),(10,14,30),-1)
            frame = cv2.addWeighted(ov,0.75,frame,0.25,0)
            phone_cnt = _pd.get_today_count() if _phone_ok else self.mobile_detections
            hud = (f"Students:{len(faces)}  Att:{overall:.1f}%  "
                   f"Score:{avg_dis:.0f}%  Phones:{phone_cnt}  F:{self.total_frames}")
            cv2.putText(frame,hud,(8,24),cv2.FONT_HERSHEY_SIMPLEX,0.48,(180,210,255),2)

            # History tick
            if time.time()-self._last_log >= 1.0:
                self._last_log = time.time()
                self.history.append({
                    'timestamp':datetime.now().strftime('%H:%M:%S'),
                    'face_count':len(faces),
                    'attention_pct':overall,
                    'students':students,
                    'avg_distraction':avg_dis,
                    'mobile_count':self.mobile_detections,
                })
                if len(self.history) > 3600: self.history.pop(0)

            focused    = sum(1 for s in students if s['status']=='Focused')
            distracted = sum(1 for s in students if s['status']=='Distracted')
            sleeping   = sum(1 for s in students if s['status']=='Sleeping')

            stats = {
                'total_students':len(faces),'focused':focused,
                'distracted':distracted,'sleeping':sleeping,
                'attention_pct':overall,'total_frames':self.total_frames,
                'attentive_frames':self.att_frames,
                'emotion_counts':dict(self.emotion_counts),
                'students':students,
                'alert':sleeping>0 or any(s['mobile_detected'] for s in students),
                'session_start':self.session_start.strftime('%H:%M:%S'),
                # NEW
                'mobile_count':self.mobile_detections,
                'avg_distraction_score':avg_dis,
                'phone_detections':len(phone_detections),
            }
            return frame, stats

    def get_history(self):
        with self._lock: return list(self.history)

    def reset(self):
        with self._lock:
            self._states.clear()
            self.total_frames = self.att_frames = 0
            self.history.clear()
            self.emotion_counts = {'Happy':0,'Neutral':0,'Bored':0,'Distracted':0}
            self.session_start  = datetime.now()
            self.mobile_detections   = 0
            self.total_distraction   = 0.0
            self.distraction_samples = 0
