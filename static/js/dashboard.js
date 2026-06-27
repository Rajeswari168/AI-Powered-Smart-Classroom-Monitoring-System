/**
 * dashboard.js  -  Smart Classroom Attention Detector  (Complete v2)
 * Shared JS: clock, sidebar, SSE, monitoring control, donut chart, alerts.
 */
'use strict';

// ── Clock ─────────────────────────────────────────────────────────────────────
function updateClock() {
  const el = document.getElementById('topbarTime');
  const now  = new Date();
  if (el) {
    el.textContent = now.toLocaleTimeString('en-IN', {
      hour:'2-digit', minute:'2-digit', second:'2-digit'
    }) + '  |  ' + now.toLocaleDateString('en-IN', {
      day:'2-digit', month:'short', year:'numeric'
    });
  }

  // Update sidebar date/time elements
  const sbTime = document.getElementById('sidebarTime');
  const sbDate = document.getElementById('sidebarDate');
  if (sbTime) {
    sbTime.textContent = now.toLocaleTimeString('en-IN', {
      hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: true
    });
  }
  if (sbDate) {
    sbDate.innerHTML = '📅 &nbsp;' + now.toLocaleDateString('en-IN', {
      day: '2-digit', month: 'short', year: 'numeric'
    });
  }
}
setInterval(updateClock, 1000);
updateClock();

// ── Sidebar toggle ────────────────────────────────────────────────────────────
function toggleSidebar() {
  const sb = document.getElementById('sidebar');
  if (!sb) return;
  sb.classList.toggle('sidebar-hidden');
}

// ── Monitoring state ──────────────────────────────────────────────────────────
let monitoringActive = false;
let monitorStart     = null;
let monTimerID       = null;
let sseSource        = null;
let alertMessages    = [];
let alertCount       = 0;

function updateMonTimer() {
  if (!monitorStart) return;
  const sec = Math.floor((Date.now() - monitorStart) / 1000);
  const h   = String(Math.floor(sec/3600)).padStart(2,'0');
  const m   = String(Math.floor((sec%3600)/60)).padStart(2,'0');
  const s   = String(sec%60).padStart(2,'0');
  safeText('monTime', `${h}:${m}:${s}`);
}

async function startMonitoring() {
  try {
    const res = await fetch('/api/start', { method:'POST' });
    if (!res.ok) throw new Error('Server error');

    monitoringActive = true;
    monitorStart     = Date.now();
    monTimerID       = setInterval(updateMonTimer, 1000);

    // Show video feed
    const feed = document.getElementById('videoFeed');
    const ph   = document.getElementById('feedPlaceholder');
    if (feed) { feed.src = '/video_feed?' + Date.now(); feed.classList.remove('hidden'); }
    if (ph)   { ph.style.display = 'none'; }

    safeClass('btnStart', 'add', 'hidden');
    safeClass('btnStop',  'remove', 'hidden');
    const dot = document.getElementById('liveDot');
    if (dot) dot.classList.add('active');

    startSSE();
  } catch(e) {
    console.error('Start monitoring failed:', e);
    alert('Could not start monitoring. Make sure the server is running.');
  }
}

async function stopMonitoring() {
  monitoringActive = false;
  clearInterval(monTimerID);

  try { await fetch('/api/stop', { method:'POST' }); } catch(_) {}

  const feed = document.getElementById('videoFeed');
  const ph   = document.getElementById('feedPlaceholder');
  if (feed) { feed.src = ''; feed.classList.add('hidden'); }
  if (ph)   { ph.style.display = 'flex'; }

  safeClass('btnStart', 'remove', 'hidden');
  safeClass('btnStop',  'add',    'hidden');
  const dot = document.getElementById('liveDot');
  if (dot) dot.classList.remove('active');

  if (sseSource) { sseSource.close(); sseSource = null; }
}

function handleFeedError() {
  const feed = document.getElementById('videoFeed');
  if (feed && monitoringActive) {
    setTimeout(() => { feed.src = '/video_feed?' + Date.now(); }, 1500);
  }
}

// ── SSE ───────────────────────────────────────────────────────────────────────
function startSSE() {
  if (sseSource) { sseSource.close(); }
  sseSource = new EventSource('/api/stream');
  sseSource.onmessage = (e) => {
    try { applyStats(JSON.parse(e.data)); } catch(_) {}
  };
  sseSource.onerror = () => {
    sseSource.close(); sseSource = null;
    if (monitoringActive) setTimeout(startSSE, 2000);
  };
}

// ── Apply stats to DOM ────────────────────────────────────────────────────────
function applyStats(s) {
  if (!s || typeof s !== 'object') return;

  const total = s.total_students || 0;
  const foc   = s.focused        || 0;
  const dis   = s.distracted     || 0;
  const slp   = s.sleeping       || 0;
  const att   = parseFloat(s.attention_pct) || 0;

  // Cards
  safeText('statStudents',   total);
  safeText('statFocused',    foc);
  safeText('statDistracted', dis);
  safeText('statSleeping',   slp);
  safeText('attPct',         att.toFixed(1) + '%');
  safeText('distrPct',       total ? ((dis/total)*100).toFixed(0)+'%' : '0%');
  safeText('sleepPct',       total ? ((slp/total)*100).toFixed(0)+'%' : '0%');
  safeText('totalFrames',    s.total_frames || 0);
  safeText('sessionStart',   s.session_start || '--:--:--');

  // NEW: mobile count + distraction score
  const mob   = s.mobile_count          || 0;
  const dscore= s.avg_distraction_score || 0;
  safeText('mobileCount',        mob);
  safeText('avgDistractionScore', dscore.toFixed(0) + '%');
  // Also update advanced dashboard elements if on that page
  safeText('attPctAdv',          att.toFixed(1) + '%');
  safeText('totalStudentsAdv',   total);

  // Overview
  safeText('ovAttentive', foc);
  safeText('ovPresent',   total);
  safeText('ovInactive',  slp);
  safeText('ovAvgScore',  att.toFixed(0) + '%');

  // Detection bars
  const mx = Math.max(total, 1);
  safeText('detAtt', foc); safeWidth('barAtt', foc/mx*100);
  safeText('detDis', dis); safeWidth('barDis', dis/mx*100);
  safeText('detSlp', slp); safeWidth('barSlp', slp/mx*100);

  // Donut
  drawDonut('attentionDonut', att, total?(dis/total*100):0, total?(slp/total*100):0);
  safeText('donutPct', att.toFixed(0)+'%');
  safeText('legAtt', att.toFixed(1)+'%');
  safeText('legDis', (total?(dis/total*100):0).toFixed(1)+'%');
  safeText('legSlp', (total?(slp/total*100):0).toFixed(1)+'%');

  // Emotion bars
  const ec    = s.emotion_counts || {};
  const etot  = Object.values(ec).reduce((a,b)=>a+b,0) || 1;
  const ep    = (k) => (ec[k]||0)/etot*100;
  safeWidth('emoHappy',      ep('Happy'));      safeText('emoHappyPct',      ep('Happy').toFixed(0)+'%');
  safeWidth('emoNeutral',    ep('Neutral'));    safeText('emoNeutralPct',    ep('Neutral').toFixed(0)+'%');
  safeWidth('emoBored',      ep('Bored'));      safeText('emoBoredPct',      ep('Bored').toFixed(0)+'%');
  safeWidth('emoDistracted', ep('Distracted')); safeText('emoDistractedPct', ep('Distracted').toFixed(0)+'%');

  // Analytics fields
  safeText('aAvgAtt',     att.toFixed(1)+'%');
  safeText('aTotalFrames', s.total_frames || 0);
  safeText('aDistrPct',   total?(dis/total*100).toFixed(1)+'%':'--');
  safeText('aAlerts',     alertCount);

  // Alert banner
  if (s.alert) {
    const banner = document.getElementById('alertBanner');
    if (banner) banner.style.display = 'flex';
    const ts  = new Date().toLocaleTimeString('en-IN',{hour:'2-digit',minute:'2-digit'});
    const msg = `${ts} — Drowsiness detected!`;
    if (!alertMessages.length || alertMessages[0] !== msg) {
      alertMessages.unshift(msg);
      alertCount++;
      if (alertMessages.length > 20) alertMessages.pop();
      renderAlertList();
      // Beep sound
      try {
        const ctx = new (window.AudioContext || window.webkitAudioContext)();
        const osc = ctx.createOscillator();
        osc.connect(ctx.destination); osc.frequency.value = 880;
        osc.start(); osc.stop(ctx.currentTime + 0.3);
      } catch(_) {}
    }
  }

  // Student table (analytics/students page) — now includes new fields
  const tbody = document.getElementById('studentTableBody');
  if (tbody && (s.students||[]).length) {
    tbody.innerHTML = (s.students||[]).map((st,i) => {
      const sc  = st.distraction_score || st.attention_pct || 0;
      const stCls = st.status==='Focused'?'status-good':st.status==='Sleeping'?'status-bad':'status-warn';
      const sCls  = sc>=80?'status-good':sc>=60?'status-warn':'status-bad';
      const mob   = st.mobile_detected
        ? '<span style="color:#ef4444;font-weight:700">\u{1F4F1} YES</span>'
        : 'No';
      return `<tr>
        <td>${i+1}</td>
        <td>Student ${st.id+1}</td>
        <td><span class="status-badge ${stCls}">${st.status}</span></td>
        <td>${st.emotion}</td>
        <td>${st.head_pose||'Forward'}</td>
        <td>${mob}</td>
        <td><strong>${st.attention_pct}%</strong></td>
        <td><span class="status-badge ${sCls}">${sc}%</span></td>
        <td>${st.is_drowsy?'<span style="color:#ef4444">\u26A0 Yes</span>':'No'}</td>
      </tr>`;
    }).join('');
  }
}

function renderAlertList() {
  const list = document.getElementById('alertList');
  if (!list) return;
  if (!alertMessages.length) {
    list.innerHTML = '<li class="alert-empty">No alerts yet</li>';
    return;
  }
  list.innerHTML = alertMessages.map(m =>
    `<li class="alert-sleep">🚨 ${m}</li>`
  ).join('');
}

function dismissAlert() {
  const b = document.getElementById('alertBanner');
  if (b) b.style.display = 'none';
}

function clearAlerts() {
  alertMessages = []; alertCount = 0;
  renderAlertList();
}

// ── Vanilla donut canvas ──────────────────────────────────────────────────────
function drawDonut(id, attPct, disPct, slpPct) {
  const canvas = document.getElementById(id);
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const cx  = canvas.width  / 2;
  const cy  = canvas.height / 2;
  const R   = Math.min(cx, cy) - 8;
  const r   = R * 0.62;

  const total = attPct + disPct + slpPct || 100;
  const slices = attPct+disPct+slpPct > 0
    ? [{p:attPct/total,c:'#10b981'},{p:disPct/total,c:'#f59e0b'},{p:slpPct/total,c:'#ef4444'}]
    : [{p:1,c:'#1e293b'}];

  ctx.clearRect(0, 0, canvas.width, canvas.height);
  let start = -Math.PI/2;
  for (const sl of slices) {
    if (sl.p <= 0) continue;
    const sw = sl.p * 2 * Math.PI;
    ctx.beginPath(); ctx.moveTo(cx,cy);
    ctx.arc(cx, cy, R, start, start+sw);
    ctx.closePath(); ctx.fillStyle = sl.c; ctx.fill();
    start += sw;
  }
  // hole
  ctx.beginPath(); ctx.arc(cx, cy, r, 0, 2*Math.PI);
  ctx.fillStyle = '#141e35'; ctx.fill();
}

// ── Analytics charts (Chart.js) ───────────────────────────────────────────────
let trendChart = null, emoDonut = null;
const trendBuf = { labels:[], vals:[] };

function initAnalyticsCharts() {
  if (!window.Chart) return;
  Chart.defaults.color       = '#64748b';
  Chart.defaults.borderColor = '#1e293b';

  const tEl = document.getElementById('trendChart');
  if (tEl) {
    trendChart = new Chart(tEl, {
      type:'line',
      data:{ labels:trendBuf.labels, datasets:[{
        label:'Attention %', data:trendBuf.vals,
        borderColor:'#7c3aed', backgroundColor:'rgba(124,58,237,.12)',
        tension:0.4, fill:true, pointRadius:2
      }]},
      options:{ animation:false,
        plugins:{ legend:{display:false} },
        scales:{
          y:{ min:0,max:100, ticks:{color:'#64748b'}, grid:{color:'#1e293b'} },
          x:{ ticks:{color:'#64748b',maxTicksLimit:15}, grid:{color:'#1e293b'} }
        }
      }
    });
  }

  const eEl = document.getElementById('emoDonut');
  if (eEl) {
    emoDonut = new Chart(eEl, {
      type:'doughnut',
      data:{ labels:['Happy','Neutral','Bored','Distracted'],
             datasets:[{data:[25,25,25,25],
               backgroundColor:['#10b981','#3b82f6','#eab308','#ef4444'],
               borderWidth:0}]},
      options:{ cutout:'68%', plugins:{legend:{display:false}}, animation:{duration:400} }
    });
  }

  startSSE();
  setInterval(refreshAnalytics, 1000);
}

function refreshAnalytics() {
  fetch('/api/stats').then(r=>r.json()).then(s => {
    applyStats(s);
    if (!s.total_frames) return;

    const ts = new Date().toLocaleTimeString('en-IN',{hour:'2-digit',minute:'2-digit',second:'2-digit'});
    trendBuf.labels.push(ts);
    trendBuf.vals.push(s.attention_pct||0);
    if (trendBuf.labels.length > 60) { trendBuf.labels.shift(); trendBuf.vals.shift(); }
    if (trendChart) {
      trendChart.data.labels = trendBuf.labels;
      trendChart.data.datasets[0].data = trendBuf.vals;
      trendChart.update('none');
    }
    if (emoDonut && s.emotion_counts) {
      const ec = s.emotion_counts;
      emoDonut.data.datasets[0].data = [ec.Happy||0,ec.Neutral||0,ec.Bored||0,ec.Distracted||0];
      emoDonut.update('none');
      const et = Object.values(ec).reduce((a,b)=>a+b,0)||1;
      safeText('eLegHappy',   ((ec.Happy  ||0)/et*100).toFixed(0)+'%');
      safeText('eLegNeutral', ((ec.Neutral||0)/et*100).toFixed(0)+'%');
      safeText('eLegBored',   ((ec.Bored  ||0)/et*100).toFixed(0)+'%');
      safeText('eLegDist',    ((ec.Distracted||0)/et*100).toFixed(0)+'%');
    }
  }).catch(()=>{});
}

// ── DOM helpers ───────────────────────────────────────────────────────────────
function safeText(id, val) {
  const el = document.getElementById(id);
  if (el) el.textContent = val;
}
function safeWidth(id, pct) {
  const el = document.getElementById(id);
  if (el) el.style.width = Math.min(100, Math.max(0, pct)).toFixed(1)+'%';
}
function safeClass(id, action, cls) {
  const el = document.getElementById(id);
  if (el) el.classList[action](cls);
}

// Auto-start live camera monitoring on page load (NEW)
window.addEventListener('load', () => {
  const feed = document.getElementById('videoFeed');
  if (feed) {
    // Small delay to ensure all charts and SSE channels are prepared
    setTimeout(startMonitoring, 300);
  }
});
