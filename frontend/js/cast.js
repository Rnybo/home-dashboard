// js/cast.js — Google Cast / Nest afspiller widget

let castState = {};        // device name → state
let castPanelOpen = false;
let castEvtSource = null;

// App-ikoner
const CAST_APP_ICONS = {
  'Spotify':       '🎵',
  'YouTube':       '▶️',
  'YouTube Music': '🎶',
  'DR':            '📻',
  'Netflix':       '🎬',
  'Default Media Receiver': '🔊',
};

function castAppIcon(app) {
  if (!app) return '🔊';
  for (const [k, v] of Object.entries(CAST_APP_ICONS)) {
    if (app.toLowerCase().includes(k.toLowerCase())) return v;
  }
  return '🔊';
}

function castActivePlaying() {
  return Object.values(castState).filter(s => s.state === 'PLAYING' || s.state === 'BUFFERING' || s.state === 'PAUSED');
}

function castRenderButton() {
  const playing = castActivePlaying();
  const btn = document.getElementById('cast-btn');
  if (!btn) return;
  if (playing.length === 0) {
    btn.style.display = 'none';
    if (castPanelOpen) castClosePanel();
  } else {
    btn.style.display = 'flex';
    const isPlaying = playing.some(s => s.state === 'PLAYING' || s.state === 'BUFFERING');
    btn.innerHTML = isPlaying ? '🎵' : '⏸';
    btn.title = playing.map(s => `${s.device}: ${s.title || s.app}`).join('\n');
    if (castPanelOpen) castRenderPanel();
  }
}

function castOpenPanel() {
  castPanelOpen = true;
  const panel = document.getElementById('cast-panel');
  if (panel) { panel.style.display = 'block'; castRenderPanel(); }
}

function castClosePanel() {
  castPanelOpen = false;
  const panel = document.getElementById('cast-panel');
  if (panel) panel.style.display = 'none';
}

function castTogglePanel() {
  castPanelOpen ? castClosePanel() : castOpenPanel();
}

function castRenderPanel() {
  const panel = document.getElementById('cast-panel');
  if (!panel) return;
  const playing = castActivePlaying();
  if (playing.length === 0) { castClosePanel(); return; }

  panel.innerHTML = playing.map(s => `
    <div class="cast-device">
      <div class="cast-device-header">
        <span class="cast-app-icon">${castAppIcon(s.app)}</span>
        <span class="cast-device-name">${s.device}</span>
        <span class="cast-status ${s.state === 'PAUSED' ? 'paused' : ''}">${s.state === 'PAUSED' ? 'Sat på pause' : s.state === 'BUFFERING' ? 'Indlæser...' : 'Afspiller'}</span>
      </div>
      ${s.image ? `<img class="cast-album-art" src="${s.image}" onerror="this.style.display='none'">` : ''}
      <div class="cast-track-info">
        <div class="cast-title">${s.title || '(ukendt titel)'}</div>
        ${s.artist ? `<div class="cast-artist">${s.artist}</div>` : ''}
        ${s.album  ? `<div class="cast-album">${s.album}</div>`   : ''}
      </div>
      ${s.volume !== null ? `<div class="cast-volume">🔊 ${Math.round(s.volume * 100)}%</div>` : ''}
      <div class="cast-controls">
        <button onclick="castControl('${s.device}','previous')" title="Forrige">⏮</button>
        <button onclick="castControl('${s.device}','seek_back')" title="10 sek tilbage">⏪</button>
        <button onclick="castControl('${s.device}','${s.state === 'PAUSED' ? 'play' : 'pause'}')" class="cast-playpause">
          ${s.state === 'PAUSED' ? '▶' : '⏸'}
        </button>
        <button onclick="castControl('${s.device}','seek_fwd')" title="10 sek frem">⏩</button>
        <button onclick="castControl('${s.device}','next')" title="Næste">⏭</button>
        <button onclick="castControl('${s.device}','stop')" title="Stop" class="cast-stop">⏹</button>
      </div>
      <div class="cast-vol-row">
        <span>🔇</span>
        <input type="range" min="0" max="100" value="${Math.round((s.volume||0)*100)}"
          oninput="castSetVolume('${s.device}', this.value/100)">
        <span>🔊</span>
      </div>
    </div>
  `).join('');
}

async function castControl(device, action) {
  const enc = encodeURIComponent(device);
  const key = window.API_KEY || '';
  const headers = { 'x-api-key': key, 'Content-Type': 'application/json' };

  if (action === 'seek_back' || action === 'seek_fwd') {
    const s = castState[device];
    const delta = action === 'seek_back' ? -10 : 10;
    await fetch(`/api/cast/${enc}/seek`, { method: 'POST', headers, body: JSON.stringify({ delta }) });
  } else if (action === 'previous') {
    await fetch(`/api/cast/${enc}/previous`, { method: 'POST', headers });
  } else if (action === 'next') {
    await fetch(`/api/cast/${enc}/next`, { method: 'POST', headers });
  } else {
    await fetch(`/api/cast/${enc}/${action}`, { method: 'POST', headers });
  }
}

let _volTimer = null;
function castSetVolume(device, level) {
  clearTimeout(_volTimer);
  _volTimer = setTimeout(() => {
    const key = window.API_KEY || '';
    fetch(`/api/cast/${encodeURIComponent(device)}/volume`, {
      method: 'POST',
      headers: { 'x-api-key': key, 'Content-Type': 'application/json' },
      body: JSON.stringify({ level: parseFloat(level) })
    });
  }, 200);
}

function castStartSSE() {
  if (castEvtSource) return;
  castEvtSource = new EventSource('/api/cast/stream');
  castEvtSource.onmessage = e => {
    try {
      const s = JSON.parse(e.data);
      if (s.device) {
        castState[s.device] = s;
        castRenderButton();
      }
    } catch(err) {}
  };
  castEvtSource.onerror = () => {
    castEvtSource.close(); castEvtSource = null;
    setTimeout(castStartSSE, 10000); // genopret efter 10s
  };
}

async function castInit() {
  // Hent initial state
  try {
    const r = await apiFetch('/api/cast/state');
    const data = await r.json();
    castState = data || {};
    castRenderButton();
  } catch(e) {}
  castStartSSE();
}
