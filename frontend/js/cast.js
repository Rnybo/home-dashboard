// js/cast.js — Google Cast / Nest afspiller widget

let castState = {};        // device name → state
let castPanelOpen = false;
let castWs = null;

const CAST_BTN_ICONS = {
  spotify: `<svg width="24" height="24" viewBox="0 0 24 24" fill="white"><path d="M12 2C6.477 2 2 6.477 2 12s4.477 10 10 10 10-4.477 10-10S17.523 2 12 2zm4.586 14.424a.623.623 0 01-.857.207c-2.348-1.435-5.304-1.76-8.785-.964a.623.623 0 01-.277-1.215c3.809-.87 7.076-.496 9.712 1.115a.623.623 0 01.207.857zm1.223-2.722a.78.78 0 01-1.072.257c-2.687-1.652-6.785-2.131-9.965-1.166a.78.78 0 01-.973-.517.781.781 0 01.517-.972c3.632-1.102 8.147-.568 11.236 1.326a.78.78 0 01.257 1.072zm.105-2.835C14.692 8.95 9.375 8.775 6.297 9.71a.937.937 0 11-.543-1.793c3.532-1.072 9.404-.865 13.115 1.337a.937.937 0 01-.955 1.613z"/></svg>`,
  dr: `<svg width="24" height="24" viewBox="0 0 24 24" fill="white"><text x="3" y="17" font-size="11" font-weight="800" font-family="Arial,sans-serif">DR</text></svg>`,
  default: `<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2" stroke-linecap="round"><path d="M2 16.1A5 5 0 0 1 5.9 20M2 12.05A9 9 0 0 1 9.95 20M2 8V6a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2h-6"/><circle cx="2" cy="20" r="1" fill="white" stroke="none"/></svg>`,
};

const CAST_BTN_COLORS = {
  spotify: '#1DB954',
  dr:      '#E4002B',
  default: '#333',
};

function castBtnIconForApp(app) {
  if (!app) return { icon: CAST_BTN_ICONS.default, color: CAST_BTN_COLORS.default };
  const a = app.toLowerCase();
  if (a.includes('spotify'))    return { icon: CAST_BTN_ICONS.spotify, color: CAST_BTN_COLORS.spotify };
  if (a.includes('dr'))         return { icon: CAST_BTN_ICONS.dr,      color: CAST_BTN_COLORS.dr };
  return { icon: CAST_BTN_ICONS.default, color: CAST_BTN_COLORS.default };
}


// App-ikoner (emoji til panel)
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
  return Object.values(castState).filter(s => {
    if (!s.state || s.state === 'IDLE' || s.state === 'UNKNOWN') return false;
    // Apps med upålidelig media info vises stadig som PLAYING — samme som HA
    if (s.unreliable_info && s.state === 'PLAYING') return true;
    return s.state === 'PLAYING' || s.state === 'BUFFERING' || s.state === 'PAUSED';
  });
}

function castRenderHomeWidget() {
  const el = document.getElementById('cast-home-widget');
  if (!el) return;
  const active = castActivePlaying();
  if (active.length === 0) { el.style.display = 'none'; return; }
  el.style.display = 'flex';
  el.innerHTML = active.map(s => {
    const artHtml = s.image
      ? `<img class="cast-home-art" src="${s.image}" onerror="this.style.display='none'">`
      : `<div class="cast-home-art-placeholder">${castAppIcon(s.app)}</div>`;
    const enc = encodeURIComponent(s.device);
    const isPaused = s.state === 'PAUSED';
    return `
      <div class="cast-home-card ${isPaused ? 'paused' : 'playing'}" onclick="castTogglePanel()">
        ${artHtml}
        <div class="cast-home-info">
          <div class="cast-home-device">${castAppIcon(s.app)} ${s.device}</div>
          <div class="cast-home-title">${s.title || '(ukendt titel)'}</div>
          ${s.artist ? `<div class="cast-home-artist">${s.artist}</div>` : ''}
        </div>
        <div class="cast-home-controls" onclick="event.stopPropagation()">
          <button onclick="castControl('${s.device}','previous')" title="Forrige">⏮</button>
          <button onclick="castControl('${s.device}','${isPaused ? 'play' : 'pause'}')">${isPaused ? '▶' : '⏸'}</button>
          <button onclick="castControl('${s.device}','next')" title="Næste">⏭</button>
        </div>
      </div>`;
  }).join('');
}

// ── Progress ──────────────────────────────────────────────────────────────────
let _progressTimer = null;

function castStartProgress() {
  if (_progressTimer) return;
  _progressTimer = setInterval(() => {
    if (!castPanelOpen) return;
    document.querySelectorAll('.cast-progress-bar').forEach(bar => {
      const dev = bar.dataset.device;
      const s = castState[dev];
      if (!s || !s.duration || s.state !== 'PLAYING') return;
      const elapsed = s.current_time + (Date.now() / 1000 - s.last_updated);
      const pct = Math.min(100, (elapsed / s.duration) * 100);
      bar.style.width = pct + '%';
      const timeEl = bar.closest('.cast-progress-wrap')?.querySelector('.cast-time');
      if (timeEl) timeEl.textContent = castFmtTime(elapsed) + ' / ' + castFmtTime(s.duration);
    });
  }, 1000);
}

function castStopProgress() {
  clearInterval(_progressTimer);
  _progressTimer = null;
}

function castFmtTime(sec) {
  if (!sec || isNaN(sec)) return '0:00';
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return m + ':' + String(s).padStart(2, '0');
}

function castProgressHtml(s) {
  if (!s.duration || s.duration <= 0) return '';
  const elapsed = (s.current_time || 0) + (s.state === 'PLAYING' ? (Date.now() / 1000 - (s.last_updated || 0)) : 0);
  const pct = Math.min(100, (elapsed / s.duration) * 100);
  return `
    <div class="cast-progress-wrap" style="padding:4px 14px 8px">
      <div style="background:#eee;border-radius:2px;height:3px;cursor:${s.supports_seek ? 'pointer' : 'default'}"
           onclick="${s.supports_seek ? `castSeekClick(event,'${s.device}',${s.duration})` : ''}">
        <div class="cast-progress-bar" data-device="${s.device}"
             style="height:3px;background:#111;border-radius:2px;width:${pct}%;transition:width 0.5s linear"></div>
      </div>
      <div class="cast-time" style="font-size:0.68rem;color:#aaa;margin-top:3px;text-align:right">
        ${castFmtTime(elapsed)} / ${castFmtTime(s.duration)}
      </div>
    </div>`;
}

function castSeekClick(evt, device, duration) {
  const bar = evt.currentTarget;
  const rect = bar.getBoundingClientRect();
  const pct = (evt.clientX - rect.left) / rect.width;
  const target_time = pct * duration;
  apiFetch(`/api/cast/${encodeURIComponent(device)}/seek_abs`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ position: target_time })
  });
}


function castRenderButton() {
  const active  = castActivePlaying();
  const btn = document.getElementById('cast-btn');
  if (!btn) return;
  if (active.length === 0) {
    btn.style.display = 'none';
    if (castPanelOpen) castClosePanel();
  } else {
    const topApp = active.find(s => s.state === 'PLAYING' || s.state === 'BUFFERING')?.app
                || active[0]?.app;
    const { icon, color } = castBtnIconForApp(topApp);
    btn.style.display = 'flex';
    btn.style.background = color;
    btn.style.opacity = active.some(s => s.state === 'PLAYING' || s.state === 'BUFFERING') ? '1' : '0.6';
    btn.innerHTML = icon;
    btn.title = active.map(s => `${s.device}: ${s.title || s.app}`).join('\n');
  }
  if (castPanelOpen) castRenderPanel();
}

function castOpenPanel() {
  castPanelOpen = true;
  const panel = document.getElementById('cast-panel');
  if (panel) { panel.style.display = 'block'; castRenderPanel(); }
  castStartProgress();
}

function castClosePanel() {
  castPanelOpen = false;
  const panel = document.getElementById('cast-panel');
  if (panel) panel.style.display = 'none';
  castStopProgress();
}

function castTogglePanel() {
  castPanelOpen ? castClosePanel() : castOpenPanel();
}

const CAST_ICON_SVG = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
  <path d="M2 16.1A5 5 0 0 1 5.9 20M2 12.05A9 9 0 0 1 9.95 20M2 8V6a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2h-6"/>
  <circle cx="2" cy="20" r="1" fill="currentColor"/>
</svg>`;

function castRenderPanel() {
  const panel = document.getElementById('cast-panel');
  if (!panel) return;
  const playing = castActivePlaying();
  if (playing.length === 0) { castClosePanel(); return; }

  panel.innerHTML = playing.map(s => {
    const isPaused   = s.state === 'PAUSED';
    const isBuffering = s.state === 'BUFFERING';
    const dotClass   = isPaused ? 'paused' : isBuffering ? 'buffering' : '';
    const statusText = isPaused ? 'Sat på pause' : isBuffering ? 'Indlæser…' : 'Afspiller';
    const artHtml    = s.image
      ? `<img class="cast-album-art" src="${s.image}" onerror="this.parentElement.innerHTML='<div class=cast-art-placeholder>${castAppIcon(s.app)}</div>'">`
      : `<div class="cast-art-placeholder">${castAppIcon(s.app)}</div>`;
    const vol = Math.round((s.volume || 0) * 100);
    return `
    <div class="cast-device">
      ${artHtml}
      <div class="cast-track-info">
        <div class="cast-title">${s.title || '(ukendt titel)'}</div>
        ${s.artist ? `<div class="cast-artist">${s.artist}</div>` : ''}
        ${s.album  ? `<div class="cast-album">${s.album}</div>`   : ''}
      </div>
      <div class="cast-device-row">
        <div class="cast-status-dot ${dotClass}" title="${statusText}"></div>
        <span class="cast-device-name">${s.device}</span>
        <span style="font-size:0.72rem;color:#aaa">${statusText}</span>
      </div>
      <div class="cast-controls">
        <button onclick="castControl('${s.device}','previous')" title="Forrige">⏮</button>
        <button onclick="castControl('${s.device}','seek_back')" title="−10s" style="font-size:0.75rem">−10s</button>
        <button onclick="castControl('${s.device}','${isPaused ? 'play' : 'pause'}')" class="cast-playpause">
          ${isPaused ? '▶' : '⏸'}
        </button>
        <button onclick="castControl('${s.device}','seek_fwd')" title="+10s" style="font-size:0.75rem">+10s</button>
        <button onclick="castControl('${s.device}','next')" title="Næste">⏭</button>
      </div>
      <div class="cast-vol-row">
        ${s.volume_control_fixed ? `<span style="font-size:0.72rem;color:#aaa">Fast lydniveau</span>` : `
        <button onclick="castToggleMute('${s.device}',${!s.volume_muted})" style="background:none;border:none;cursor:pointer;font-size:1rem;padding:0 4px" title="${s.volume_muted ? 'Slå lyd til' : 'Slå lyd fra'}">
          ${s.volume_muted ? '🔇' : '🔊'}
        </button>
        <input type="range" min="0" max="100" value="${s.volume_muted ? 0 : vol}" step="1"
          ${s.volume_muted ? 'disabled style="opacity:0.4"' : ''}
          oninput="castSetVolume('${s.device}',this.value/100)">
        <span>${s.volume_muted ? '🔇' : vol + '%'}</span>
        `}
      </div>
      ${castProgressHtml(s)}
      <div style="padding:0 14px 2px">
        <button class="cast-transfer-btn" onclick="castShowTransferMenu('${s.device}',this)">
          ${CAST_ICON_SVG} Afspil på en anden enhed
        </button>
      </div>
    </div>`;
  }).join('');
}

async function castShowTransferMenu(sourceDevice, anchorEl) {
  const srcState = castState[sourceDevice] || {};
  const isSpotify = (srcState.app || '').toLowerCase().includes('spotify');

  let allDevices = [];
  let spotifyDevices = [];

  try {
    const r = await apiFetch('/api/cast/devices');
    allDevices = (await r.json()).devices || [];
  } catch(e) {}

  if (isSpotify) {
    try {
      const r = await apiFetch('/api/spotify/devices');
      spotifyDevices = (await r.json()).devices || [];
    } catch(e) {}
  }

  document.querySelectorAll('.cast-transfer-menu').forEach(el => el.remove());
  if (allDevices.length === 0 && spotifyDevices.length === 0) return;

  const menu = document.createElement('div');
  menu.className = 'cast-transfer-menu';
  let html = '';

  if (isSpotify && spotifyDevices.length > 0) {
    // Spotify afspiller — vis Spotify-enheder med direkte ID
    html += `<div style="padding:6px 12px 4px;font-size:0.68rem;font-weight:700;color:#aaa;text-transform:uppercase;letter-spacing:.05em">Afspil på</div>`;
    html += spotifyDevices.map(d => {
      const isActive = d.is_active;
      const right = isActive
        ? `<span style="font-size:0.72rem;color:#1DB954;font-weight:700">▶ Nu</span>`
        : `<svg width="14" height="14" viewBox="0 0 24 24" fill="#1DB954"><path d="M12 2C6.477 2 2 6.477 2 12s4.477 10 10 10 10-4.477 10-10S17.523 2 12 2zm4.586 14.424a.623.623 0 01-.857.207c-2.348-1.435-5.304-1.76-8.785-.964a.623.623 0 01-.277-1.215c3.809-.87 7.076-.496 9.712 1.115a.623.623 0 01.207.857zm1.223-2.722a.78.78 0 01-1.072.257c-2.687-1.652-6.785-2.131-9.965-1.166a.78.78 0 01-.973-.517.781.781 0 01.517-.972c3.632-1.102 8.147-.568 11.236 1.326a.78.78 0 01.257 1.072zm.105-2.835C14.692 8.95 9.375 8.775 6.297 9.71a.937.937 0 11-.543-1.793c3.532-1.072 9.404-.865 13.115 1.337a.937.937 0 01-.955 1.613z"/></svg>`;
      return `<div class="cast-transfer-item" data-spotify-id="${d.id}" data-type="spotify" data-active="${isActive}">
        <span style="margin-right:6px">🎵</span><span style="flex:1">${d.name}</span>${right}
      </div>`;
    }).join('');
  } else {
    // Ikke-Spotify — vis kun stop-mulighed for kildeenhed
    html += `<div style="padding:6px 12px 4px;font-size:0.68rem;font-weight:700;color:#aaa;text-transform:uppercase;letter-spacing:.05em">Enheder</div>`;
    html += allDevices.map(d => {
      const s = castState[d];
      const isSource = d === sourceDevice;
      const isActive = s && (s.state === 'PLAYING' || s.state === 'BUFFERING' || s.state === 'PAUSED');
      const appIcon = castAppIcon(s?.app);
      let right = '';
      if (isSource)       right = `<span style="font-size:0.72rem;color:#1DB954;font-weight:700">▶ Nu</span>`;
      else if (isActive)  right = `<span style="font-size:0.72rem;color:#ff9800;font-weight:600">Afspiller ✕</span>`;
      else                right = `<span style="font-size:0.72rem;color:#ccc">Ikke tilgængelig</span>`;
      return `<div class="cast-transfer-item" data-device="${d}" data-type="cast" data-source="${isSource}" data-active="${isActive}" style="${(!isSource && !isActive) ? 'opacity:0.5;pointer-events:none' : ''}">
        <span style="margin-right:6px">${appIcon}</span><span style="flex:1">${d}</span>${right}
      </div>`;
    }).join('');
  }

  menu.innerHTML = html;

  const rect = anchorEl.getBoundingClientRect();
  menu.style.cssText = `position:fixed;bottom:${window.innerHeight - rect.top + 4}px;right:${window.innerWidth - rect.right}px;
    background:#fff;border:0.5px solid var(--border);border-radius:8px;
    box-shadow:0 4px 16px rgba(0,0,0,0.15);z-index:2000;min-width:220px;overflow:hidden`;
  document.body.appendChild(menu);

  menu.querySelectorAll('.cast-transfer-item').forEach(item => {
    item.addEventListener('click', async () => {
      menu.remove();
      const type     = item.dataset.type;
      const isSource = item.dataset.source === 'true';
      const isActive = item.dataset.active === 'true';
      try {
        if (type === 'spotify') {
          await apiFetch(`/api/cast/${encodeURIComponent(sourceDevice)}/transfer`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ target: item.querySelector('span:nth-child(2)').textContent.trim(),
                                   spotify_device_id: item.dataset.spotifyId })
          });
        } else if (isSource || isActive) {
          await apiFetch(`/api/cast/${encodeURIComponent(item.dataset.device)}/stop`, { method: 'POST' });
        }
      } catch(e) { console.warn('Cast transfer/stop fejl:', e); }
    });
  });

  setTimeout(() => document.addEventListener('click', function close() {
    menu.remove(); document.removeEventListener('click', close);
  }), 50);
}

async function castControl(device, action) {
  const enc = encodeURIComponent(device);
  if (action === 'seek_back' || action === 'seek_fwd') {
    const delta = action === 'seek_back' ? -10 : 10;
    await apiFetch(`/api/cast/${enc}/seek`, { method: 'POST', body: JSON.stringify({ delta }), headers: {'Content-Type':'application/json'} });
  } else if (action === 'previous') {
    await apiFetch(`/api/cast/${enc}/previous`, { method: 'POST' });
  } else if (action === 'next') {
    await apiFetch(`/api/cast/${enc}/next`, { method: 'POST' });
  } else {
    await apiFetch(`/api/cast/${enc}/${action}`, { method: 'POST' });
  }
}

let _volTimer = null;
function castToggleMute(device, muted) {
  apiFetch(`/api/cast/${encodeURIComponent(device)}/mute`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ muted })
  });
}

function castSetVolume(device, level) {
  clearTimeout(_volTimer);
  _volTimer = setTimeout(() => {
    apiFetch(`/api/cast/${encodeURIComponent(device)}/volume`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ level: parseFloat(level) })
    });
  }, 200);
}

function castStartWS() {
  if (castWs && castWs.readyState === WebSocket.OPEN) return;
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  const host = location.hostname + ':' + location.port;
  castWs = new WebSocket(`${proto}://${host}/ws/cast`);
  castWs.onmessage = e => {
    try {
      const s = JSON.parse(e.data);
      if (s.device) { castState[s.device] = s; castRenderButton(); }
    } catch(err) {}
  };
  castWs.onclose = () => {
    castWs = null;
    setTimeout(async () => {
      try {
        const r = await apiFetch('/api/cast/state');
        const fresh = await r.json();
        if (fresh && Object.keys(fresh).length > 0) {
          castState = fresh;
          castRenderButton();
        }
      } catch(e) {}
      castStartWS();
    }, 5000);
  };
  castWs.onerror = e => { console.warn('[cast] WS error:', e); castWs && castWs.close(); };
}

async function castInit() {
  try {
    const r = await apiFetch('/api/cast/state');
    const data = await r.json();
    castState = data || {};
    castRenderButton();
  } catch(e) {}
  castStartWS();

  // Poll de første 60 sek for at fange langsom mDNS discovery + channel_connected
  let polls = 0;
  const pollTimer = setInterval(async () => {
    polls++;
    try {
      const r = await apiFetch('/api/cast/state');
      const fresh = await r.json();
      if (fresh) {
        const hasActive = Object.values(fresh).some(s =>
          s.state === 'PLAYING' || s.state === 'BUFFERING' || s.state === 'PAUSED'
        );
        if (hasActive || Object.keys(fresh).length > Object.keys(castState).length) {
          castState = fresh;
          castRenderButton();
        }
      }
    } catch(e) {}
    if (polls >= 6) clearInterval(pollTimer);
  }, 10000);
}
