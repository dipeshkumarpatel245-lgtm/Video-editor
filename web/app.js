/* Video Template Studio SPA — Elegant Studio edition */
const API = '/api';
const $ = s => document.querySelector(s);

const state = { fileId: null, templateId: null, templateMeta: null, clipIds: [], editId: null, viz: null };

function fmtDur(s) {
  if (s === undefined || s === null || isNaN(s)) return '–';
  const m = Math.floor(s / 60);
  return m + ':' + String(Math.round(s % 60)).padStart(2, '0');
}

/* ---------- robust API helpers ---------- */
async function api(url, fd) {
  const res = await fetch(url, { method: 'POST', body: fd });
  let body;
  const ct = res.headers.get('content-type') || '';
  if (ct.includes('json')) {
    body = await res.json();
  } else {
    const text = await res.text();
    body = { ok: false, detail: text || `HTTP ${res.status}` };
  }
  if (!res.ok || body.ok === false) {
    const msg = body.detail || body.message || `HTTP ${res.status}`;
    throw new Error(msg);
  }
  return body;
}

async function apiGet(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const body = await res.json();
  if (body.ok === false) throw new Error(body.detail || 'request failed');
  return body;
}

function showError(el, msg) {
  if (!el) return alert(msg);
  el.style.display = '';
  el.style.color = '#f88';
  el.textContent = msg;
}

/* ================================================================
   Immersive engine — dust, 3D tilt, scroll reveals, story spine
   ================================================================ */
const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
const io = new IntersectionObserver(es => {
  for (const e of es) {
    if (e.isIntersecting) { e.target.classList.add('in'); io.unobserve(e.target); }
  }
}, { threshold: 0.12 });

function observe(el) { io.observe(el); }

/* ----- gold dust background ----- */
(function dust() {
  const cv = document.getElementById('aurora');
  if (!cv || reduceMotion) return;
  const ctx = cv.getContext('2d');
  const DPR = Math.min(2, window.devicePixelRatio || 1);
  let W = 0, H = 0, pts = [];
  const tgt = { x: 0, y: 0 };

  function size() {
    W = innerWidth; H = innerHeight;
    cv.width = W * DPR; cv.height = H * DPR;
    ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
    const n = Math.min(90, Math.floor(W * H / 26000));
    pts = [];
    for (let i = 0; i < n; i++) pts.push({
      x: Math.random() * W, y: Math.random() * H,
      r: 0.6 + Math.random() * 1.9,
      a: 0.06 + Math.random() * 0.22,
      vx: (Math.random() - 0.5) * 0.12,
      vy: -(0.02 + Math.random() * 0.09),
      ph: Math.random() * Math.PI * 2,
    });
  }
  addEventListener('pointermove', e => {
    tgt.x = e.clientX / W - 0.5; tgt.y = e.clientY / H - 0.5;
  }, { passive: true });

  let t = 0;
  (function loop() {
    t += 0.016;
    ctx.clearRect(0, 0, W, H);
    const px = tgt.x * 20, py = tgt.y * 14;
    for (const p of pts) {
      p.x += p.vx; p.y += p.vy; p.ph += 0.02;
      if (p.y < -12) { p.y = H + 12; p.x = Math.random() * W; }
      if (p.x < -12) p.x = W + 12; else if (p.x > W + 12) p.x = -12;
      const tw = 0.5 + 0.5 * Math.sin(t + p.ph);
      ctx.globalAlpha = p.a * (0.35 + 0.65 * tw);
      ctx.fillStyle = p.r > 1.6 ? '#f2dcae' : '#d8b46a';
      ctx.beginPath();
      ctx.arc(p.x + px * p.r, p.y + py * p.r, p.r, 0, Math.PI * 2);
      ctx.fill();
    }
    requestAnimationFrame(loop);
  })();

  size();
  addEventListener('resize', size);
})();

/* ----- 3D tilt on pointer ----- */
if (!reduceMotion && window.matchMedia('(pointer: fine)').matches) {
  for (const el of document.querySelectorAll('[data-tilt]')) {
    el.addEventListener('pointermove', e => {
      const r = el.getBoundingClientRect();
      const dx = (e.clientX - r.left) / r.width - 0.5;
      const dy = (e.clientY - r.top) / r.height - 0.5;
      el.style.setProperty('--rx', (dy * -6).toFixed(2) + 'deg');
      el.style.setProperty('--ry', (dx * 8).toFixed(2) + 'deg');
      el.style.setProperty('--glx', ((dx + 0.5) * 100).toFixed(1) + '%');
      el.style.setProperty('--gly', ((dy + 0.5) * 100).toFixed(1) + '%');
    });
    el.addEventListener('pointerleave', () => {
      el.style.setProperty('--rx', '0deg'); el.style.setProperty('--ry', '0deg');
    });
  }
}

/* ----- chapter reveals + story spine spy ----- */
for (const el of document.querySelectorAll('.chapter, .stat')) observe(el);

function spineSpy() {
  const chs = [...document.querySelectorAll('.chapter')].filter(el => el.style.display !== 'none');
  let best = null, bestTop = -1e9;
  const mid = innerHeight * 0.42;
  for (const el of chs) {
    const top = el.getBoundingClientRect().top;
    if (top <= mid && top > bestTop) { bestTop = top; best = el.dataset.chap; }
  }
  for (const n of document.querySelectorAll('.spine-node')) {
    n.classList.toggle('active', n.dataset.chap === best);
  }
}
addEventListener('scroll', spineSpy, { passive: true });
addEventListener('resize', spineSpy);

/* ----- small animation helpers ----- */
function countUp(el, to, fmt = v => String(Math.round(v))) {
  if (!el || !to) return;
  const t0 = performance.now(), dur = 1000;
  (function tick(t) {
    const p = Math.min(1, (t - t0) / dur), e = 1 - Math.pow(1 - p, 3);
    el.textContent = fmt(to * e);
    if (p < 1) requestAnimationFrame(tick);
  })(t0);
}
function clamp01(v) { return Math.max(0, Math.min(1, v)); }
function mix(a, b, t) { return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t]; }
function luma(c) { return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]; }
const rgb = (c, a = 1) => `rgba(${Math.round(clamp01(c[0]) * 255)},${Math.round(clamp01(c[1]) * 255)},${Math.round(clamp01(c[2]) * 255)},${a})`;

/* ================================================================
   The Story — arc banner, waveform, abstract scenes
   ================================================================ */
async function loadStory(templateId) {
  const story = $('#story');
  if (!story) return;
  try {
    const j = await apiGet(`${API}/templates/${templateId}/viz`);
    if (!j.shots) return;
    state.viz = j;
    $('#storyTitle').textContent = 'The Story of ' + (j.title || 'Your Template');
    countUp($('#statShots'), j.shots.length);
    countUp($('#statBeats'), (j.beats || []).length);
    if (j.tempo) countUp($('#statTempo'), j.tempo, v => Math.round(v) + ' BPM');
    $('#statDur').textContent = fmtDur(j.duration);
    renderArc(j.structure || []);
    renderWave(j.loudness || [], j.duration || 0);
    renderScenes(j);
    story.style.display = '';
    observe(story);
  } catch (e) {
    console.warn('story viz unavailable:', e);
  }
}

function renderArc(acts) {
  const el = $('#arcBanner');
  if (!acts.length || !acts.some(a => (a.end || 0) > (a.start || 0))) { el.style.display = 'none'; return; }
  el.style.display = '';
  const lastEnd = Math.max(...acts.map(a => a.end || 0));
  const inner = el.querySelector('.arc-inner');
  inner.innerHTML = '';
  const palette = ['#d8b46a', '#e7c98c', '#b8995a', '#f0d9a6'];
  acts.forEach((a, i) => {
    const w = lastEnd > 0 ? Math.max(6, ((a.end - a.start) / lastEnd) * 100) : 6;
    const seg = document.createElement('div');
    seg.className = 'arc-seg';
    seg.style.setProperty('--seg', palette[i % palette.length]);
    seg.style.width = w.toFixed(2) + '%';
    if (acts.length <= 7) {
      const sp = document.createElement('span');
      sp.textContent = (a.act || 'act').toUpperCase();
      seg.appendChild(sp);
    }
    inner.appendChild(seg);
  });
}

function renderWave(curve, dur) {
  const svg = $('#wave'), stage = $('#waveStage');
  if (!curve || curve.length < 2) { stage.style.display = 'none'; return; }
  stage.style.display = '';
  const W = 1000, H = 120;
  svg.setAttribute('viewBox', `0 0 ${W} ${H}`);
  const data = curve.map(c => [c.t || 0, Math.max(-70, c.db === undefined ? -70 : c.db)]);
  const tmax = data[data.length - 1][0] || dur || 1;
  const dmin = Math.min(...data.map(d => d[1]));
  const x = t => (t / tmax) * W;
  const y = v => H - ((v - dmin) / Math.max(1e-6, 0 - dmin)) * (H - 16) - 8;
  let d = '';
  for (let i = 0; i < data.length; i++) d += (i ? 'L' : 'M') + x(data[i][0]).toFixed(2) + ' ' + y(data[i][1]).toFixed(2);
  svg.innerHTML =
    `<defs><linearGradient id="wg" x1="0" y1="0" x2="1" y2="0">` +
    `<stop offset="0" stop-color="#8a7a4d"/><stop offset=".5" stop-color="#f0d9a6"/><stop offset="1" stop-color="#d8b46a"/>` +
    `</linearGradient></defs>` +
    `<path d="${d}" fill="none" stroke="url(#wg)" stroke-width="2.4" stroke-linejoin="round"/>`;
}

function scenePalette(s) {
  const col = s.color || {};
  const raw = Array.isArray(col.mean_rgb) && col.mean_rgb.length === 3 ? col.mean_rgb.slice() : [0.28, 0.17, 0.12];
  const tags = Array.isArray(col.tags) ? col.tags : [];
  const L = luma(raw);
  const mono = tags.indexOf('bw') !== -1 || (typeof col.sat === 'number' && col.sat < 0.28);
  const dark = tags.indexOf('dark') !== -1 || L < 0.18;
  const bright = tags.indexOf('bright') !== -1 || L > 0.62;
  let base = mono ? [L, L, L] : raw.slice();
  if (!mono) {
    const sat = clamp01(typeof col.sat === 'number' ? col.sat / 1.5 : 0.4);
    base = base.map(v => L + (v - L) * (0.6 + sat * 0.9)).map(clamp01);
  }
  const temp = typeof col.temp === 'number' ? col.temp : 0;
  const GOLD = [0.82, 0.65, 0.34], CREAM = [0.95, 0.88, 0.70], STEEL = [0.60, 0.72, 0.92];
  const acc = temp >= 0
    ? mix(GOLD, CREAM, clamp01(temp * 3))
    : mix(GOLD, STEEL, clamp01(-temp * 3));
  const b1 = dark ? mix(base, [0, 0, 0], 0.42) : (bright ? mix(base, [1, 1, 1], 0.26) : base);
  const b2 = mix(b1, dark ? [0.04, 0.04, 0.05] : [0, 0, 0], 0.3);
  return {
    base1: cross(b1), base2: cross(b2),
    glow1: rgb(mix(acc, [1, 1, 1], 0.5), dark ? 0.5 : 0.34),
    glow2: rgb(mix(b1, acc, 0.4), 0.28),
    ring: rgb(mix(acc, [1, 1, 1], 0.45), 0.75),
  };
}
const cross = c => rgb(c, 1);

function motifFor(motion) {
  switch (String(motion || '').toLowerCase()) {
    case 'pan': case 'swipe': return 'motif-swipe';
    case 'zoom': case 'dolly': case 'parallax': return 'motif-swell';
    case 'handheld': case 'shake': return 'motif-shatter';
    case 'static': case 'stationary': case 'fixed': return 'motif-orbit';
    default: return 'motif-pulse';
  }
}

function renderScenes(j) {
  const rail = $('#filmRail');
  rail.innerHTML = '';
  const beats = j.beats || [];
  const pulse = j.tempo ? 60 / j.tempo : 0.55;
  (j.shots || []).forEach((s, i) => {
    const pal = scenePalette(s);
    const motion = (s.motion && s.motion.classification) || 'static';
    const cls = motifFor(motion);
    const tags = (s.color && Array.isArray(s.color.tags) && s.color.tags.length)
      ? s.color.tags.join(' · ') : '—';
    const nBeats = beats.filter(b => b.t >= (s.start || 0) && b.t < (s.end || 0)).length;
    const sc = document.createElement('div');
    sc.className = 'scene';
    sc.style.setProperty('--i', i % 7);
    sc.innerHTML = `
      <div class="scene-art ${cls}"
           style="--base1:${pal.base1};--base2:${pal.base2};--glow1:${pal.glow1};--glow2:${pal.glow2};--ring:${pal.ring};--pulse:${pulse.toFixed(2)}s">
      </div>
      <div class="scene-badge">${String(i + 1).padStart(2, '0')}</div>
      <div class="scene-meta">
        <div class="scene-title">${motion.charAt(0).toUpperCase() + motion.slice(1)}${nBeats ? ' &middot; ' + nBeats + ' beats' : ''}</div>
        <div class="scene-tags">${tags}</div>
        <div class="scene-stats">Shot ${fmtDur(s.start)} – ${fmtDur(s.end)} &nbsp;·&nbsp; ${fmtDur(s.duration)} long</div>
      </div>`;
    observe(sc);
    rail.appendChild(sc);
  });
}

/* ---------- drop zones ---------- */
function setupDrop(dropEl, fileEl, onFiles) {
  dropEl.addEventListener('click', () => fileEl.click());
  dropEl.addEventListener('dragover', e => { e.preventDefault(); dropEl.classList.add('dragover'); });
  dropEl.addEventListener('dragleave', () => dropEl.classList.remove('dragover'));
  dropEl.addEventListener('drop', e => { e.preventDefault(); dropEl.classList.remove('dragover'); onFiles([...e.dataTransfer.files]); });
  fileEl.addEventListener('change', () => { onFiles([...fileEl.files]); fileEl.value = ''; });
}

/* ---------- template upload ---------- */
setupDrop($('#dropTemplate'), $('#fileTemplate'), async files => {
  if (!files[0]) return;
  const f = files[0];
  const info = $('#templateInfo'); info.style.display = '';
  info.style.color = ''; info.textContent = `Uploading ${f.name}…`;
  try {
    const fd = new FormData(); fd.append('kind', 'template'); fd.append('file', f);
    const j = await api(`${API}/upload`, fd);
    state.fileId = j.file_id;
    info.style.color = ''; info.textContent = `✓ ${f.name}  (${fmtDur(j.duration)}, ${j.width}×${j.height})`;
    $('#step-analyze').style.display = '';
    $('#title').value = f.name.replace(/\.[^.]+$/, '');
  } catch (err) { showError(info, 'Upload failed: ' + err.message); }
});

/* ---------- analyze ---------- */
$('#btnAnalyze').addEventListener('click', async () => {
  const btn = $('#btnAnalyze'); btn.disabled = true; btn.textContent = 'Analyzing…';
  $('#analyzeProgress').style.display = '';
  const fill = $('#analyzeFill'), lbl = $('#analyzeLabel');
  let pct = 5;
  const iv = setInterval(() => { pct = Math.min(pct + 2, 92); fill.style.width = pct + '%'; }, 400);
  try {
    const fd = new FormData(); fd.append('file_id', state.fileId); fd.append('title', $('#title').value);
    const j = await api(`${API}/analyze`, fd);
    clearInterval(iv); fill.style.width = '100%';
    lbl.style.color = ''; lbl.textContent = 'Done — the story is ready below.';
    btn.textContent = '✓ Analyzed';
    state.templateId = j.template_id; state.templateMeta = j;
    renderTemplateSummary(j);
    loadStory(state.templateId);
    $('#step-clips').style.display = '';
  } catch (err) {
    clearInterval(iv); fill.style.width = '0';
    showError(lbl, 'Analysis failed: ' + err.message);
    btn.textContent = 'Analyze Template'; btn.disabled = false;
  }
});

function renderRecommendation(s, r) {
  if (!r || !r.message) return;
  s.innerHTML += `<p><strong>Suggested clips:</strong> ${r.message}</p>`;
}

function renderTemplateSummary(j) {
  const s = $('#templateSummary'); s.style.display = '';
  s.innerHTML = `
    <h3>${j.title || ''}</h3>
    <table>
      <tr><th>Duration</th><td>${fmtDur(j.duration)}</td>
          <th>Tempo</th><td>${j.tempo ? j.tempo + ' BPM' : '–'}</td></tr>
      <tr><th>Shots</th><td>${j.shots ?? '–'}</td>
          <th>Beats</th><td>${j.beats ?? '–'}</td></tr>
    </table>`;
  renderRecommendation(s, j.recommendation);
}

/* ---------- clips upload ---------- */
setupDrop($('#dropClips'), $('#fileClips'), async files => {
  const chips = $('#clipChips');
  for (const f of files) {
    const chip = document.createElement('div'); chip.className = 'chip';
    chip.innerHTML = `<span>${f.name} …</span><button title="Remove">×</button>`;
    chip.querySelector('button').addEventListener('click', () => chip.remove());
    chips.appendChild(chip);
    try {
      const fd = new FormData(); fd.append('kind', 'clip'); fd.append('file', f);
      const j = await api(`${API}/upload`, fd);
      state.clipIds.push(j.file_id);
      chip.querySelector('span').textContent = `${f.name} ${fmtDur(j.duration)}`;
    } catch (err) {
      chip.querySelector('span').textContent = `${f.name} ❌ ${err.message}`;
    }
  }
  if (state.clipIds.length) $('#step-recreate').style.display = '';
});

/* ---------- recreate ---------- */
$('#btnRecreate').addEventListener('click', async () => {
  const btn = $('#btnRecreate'); btn.disabled = true; btn.textContent = 'Recreating…';
  try {
    const fd = new FormData();
    fd.append('template_id', state.templateId);
    fd.append('mode', $('#mode').value);
    fd.append('clip_ids', state.clipIds.join(','));
    const j = await api(`${API}/recreate`, fd);
    btn.textContent = '✓ ' + $('#mode').value;
    state.editId = j.edit_id;
    renderExportPanel(j);
    $('#step-export').style.display = '';
  } catch (err) {
    btn.textContent = 'Recreate'; btn.disabled = false;
    alert('Recreate failed: ' + err.message);
  }
});

function renderExportPanel(j) {
  $('#editSummary').innerHTML = `
    <span class="badge">${j.mode} mode</span>
    <div>Duration ${fmtDur(j.duration)} &middot; ${j.segments} segments</div>`;
  renderRecommendation($('#editSummary'), j.recommendation);
  const links = $('#exportLinks'); links.innerHTML = '';
  for (const [fmt, label] of [['fcpxml', 'FCPXML (Resolve/FCP X)'], ['premiere', 'Premiere XML'], ['edl', 'EDL'], ['capcut', 'CapCut Draft'], ['capcut_pkg', 'CapCut (with media)']]) {
    const a = document.createElement('a');
    a.href = '#'; a.textContent = label;
    a.addEventListener('click', e => { e.preventDefault(); downloadExport(fmt); });
    links.appendChild(a);
  }
}

async function downloadExport(fmt) {
  try {
    const fd = new FormData(); fd.append('edit_id', state.editId); fd.append('fmt', fmt); fd.append('title', state.templateMeta?.title || 'Recreated');
    const res = await fetch(`${API}/export`, { method: 'POST', body: fd });
    if (!res.ok) { const t = await res.text(); throw new Error(t || 'export failed'); }
    const blob = await res.blob();
    const cd = res.headers.get('content-disposition') || '';
    const fn = (cd.match(/filename="([^"]+)"/) || [])[1] || 'export_' + fmt;
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a'); a.href = url; a.download = fn; a.click();
    URL.revokeObjectURL(url);
  } catch (err) { alert('Export failed: ' + err.message); }
}

/* ---------- render preview ---------- */
$('#btnRender').addEventListener('click', async () => {
  const btn = $('#btnRender'); btn.disabled = true; btn.textContent = 'Rendering…';
  const st = $('#renderStatus'); st.style.display = ''; st.style.color = '#9c9'; st.textContent = 'Rendering preview…';
  $('#renderProgress').style.display = '';
  const fill = $('#renderFill'); let pct = 5;
  const iv = setInterval(() => { pct = Math.min(pct + 1, 90); fill.style.width = pct + '%'; }, 600);
  try {
    const fd = new FormData();
    fd.append('edit_id', state.editId);
    fd.append('width', $('#renderW').value);
    fd.append('height', $('#renderH').value);
    fd.append('fps', $('#renderFps').value);
    const res = await fetch(`${API}/render`, { method: 'POST', body: fd });
    clearInterval(iv); fill.style.width = '100%';
    if (!res.ok) { const t = await res.text(); throw new Error(t || 'render failed'); }
    const j = await res.json();
    if (!j.render_url) throw new Error('render failed: no url');
    const vid = $('#preview'); vid.src = j.render_url; vid.style.display = '';
    try { vid.currentTime = 0; } catch (_) {}
    vid.load();
    vid.play().catch(() => {});
    vid.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    const dl = $('#downloadLink'); dl.href = j.render_url; dl.download = (state.templateMeta?.title || 'preview') + '.mp4';
    dl.textContent = '↓ Download preview (' + ((j.size || 0) / 1024).toFixed(0) + ' KB)'; dl.style.display = '';
    st.style.color = '#9c9'; st.textContent = '✓ Preview ready';
    btn.textContent = '✓ Rendered';
  } catch (err) {
    clearInterval(iv); fill.style.width = '0';
    btn.textContent = 'Render Preview'; btn.disabled = false;
    st.style.color = '#f88'; st.textContent = 'Render failed: ' + err.message;
  }
});