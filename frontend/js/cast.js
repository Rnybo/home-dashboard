// js/cast.js — Google Cast / Nest afspiller widget

let castState = {};        // device name -> state
let castPanelOpen = false;
let castWs = null;

const CAST_BTN_ICONS = {
  spotify: `<svg width="24" height="24" viewBox="0 0 24 24" fill="white"><path d="M12 2C6.477 2 2 6.477 2 12s4.477 10 10 10 10-4.477 10-10S17.523 2 12 2zm4.586 14.424a.623.623 0 01-.857.207c-2.348-1.435-5.304-1.76-8.785-.964a.623.623 0 01-.277-1.215c3.809-.87 7.076-.496 9.712 1.115a.623.623 0 01.207.857zm1.223-2.722a.78.78 0 01-1.072.257c-2.687-1.652-6.785-2.131-9.965-1.166a.78.78 0 01-.973-.517.781.781 0 01.517-.972c3.632-1.102 8.147-.568 11.236 1.326a.78.78 0 01.257 1.072zm.105-2.835C14.692 8.95 9.375 8.775 6.297 9.71a.937.937 0 11-.543-1.793c3.532-1.072 9.404-.865 13.115 1.337a.937.937 0 01-.955 1.613z"/></svg>`,
  dr: `<svg width="48" height="48" viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg"><rect width="48" height="48" rx="7" fill="#000000"/><text x="50%" y="58%" dominant-baseline="middle" text-anchor="middle" font-family="Arial Black,Arial,sans-serif" font-weight="900" font-size="19" letter-spacing="1" fill="#ffffff">DR</text></svg>`,
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

const CAST_APP_ICONS = {
  'Spotify':       '🎵',
  'YouTube':       '▶️',
  'YouTube Music': '🎶',
  'DR':            `<svg width="48" height="48" viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg"><rect width="48" height="48" rx="7" fill="#000000"/><text x="50%" y="58%" dominant-baseline="middle" text-anchor="middle" font-family="Arial Black,Arial,sans-serif" font-weight="900" font-size="19" letter-spacing="1" fill="#ffffff">DR</text></svg>`,
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
  const active = castActivePlaying();
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
  // Opdater kun tekst/billede in-place hvis panelet er åbent — undgå fuld re-render
  if (castPanelOpen) castUpdatePanelInPlace();
}

// Opdaterer kun titel/artist/billede/status in-place uden at røre ved controls
function castUpdatePanelInPlace() {
  for (const s of castActivePlaying()) {
    const device = document.querySelector(`.cast-device[data-device="${CSS.escape(s.device)}"]`);
    if (!device) { castRenderPanel(); return; } // nyt device — fuld render nødvendig

    const titleEl  = device.querySelector('.cast-title');
    const artistEl = device.querySelector('.cast-artist');
    const albumEl  = device.querySelector('.cast-album');
    const artEl    = device.querySelector('.cast-album-art, .cast-art-placeholder');
    const dotEl    = device.querySelector('.cast-status-dot');
    const ppBtn    = device.querySelector('.cast-playpause');

    if (titleEl  && titleEl.textContent  !== (s.title  || ''))  titleEl.textContent  = s.title  || '(ukendt titel)';
    if (artistEl && artistEl.textContent !== (s.artist || ''))  artistEl.textContent = s.artist || '';
    if (albumEl  && albumEl.textContent  !== (s.album  || ''))  albumEl.textContent  = s.album  || '';

    if (artEl && s.image && artEl.tagName === 'IMG' && artEl.src !== s.image) artEl.src = s.image;

    if (dotEl) {
      dotEl.className = 'cast-status-dot' + (s.state === 'PAUSED' ? ' paused' : s.state === 'BUFFERING' ? ' buffering' : '');
    }
    if (ppBtn) ppBtn.textContent = s.state === 'PAUSED' ? '▶' : '⏸';
  }
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

const CAST_ICON_SVG = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2 16.1A5 5 0 0 1 5.9 20M2 12.05A9 9 0 0 1 9.95 20M2 8V6a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2h-6"/><circle cx="2" cy="20" r="1" fill="currentColor"/></svg>`;

function castRenderPanel() {
  const panel = document.getElementById('cast-panel');
  if (!panel) return;
  const playing = castActivePlaying();
  if (playing.length === 0) { castClosePanel(); return; }

  panel.innerHTML = playing.map(s => {
    const isPaused    = s.state === 'PAUSED';
    const isBuffering = s.state === 'BUFFERING';
    const isSpotifyApp = (s.app || '').toLowerCase().includes('spotify');
    const dotClass   = isPaused ? 'paused' : isBuffering ? 'buffering' : '';
    const statusText = isPaused ? 'Sat på pause' : isBuffering ? 'Indlæser…' : 'Afspiller';
    const artHtml    = s.image
      ? `<img class="cast-album-art" src="${s.image}" onerror="this.parentElement.innerHTML='<div class=cast-art-placeholder>${castAppIcon(s.app)}</div>'">`
      : `<div class="cast-art-placeholder">${castAppIcon(s.app)}</div>`;
    const vol = Math.round((s.volume || 0) * 100);
    return `
    <div class="cast-device" data-device="${s.device}">
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
        <button onclick="castControl('${s.device}','seek_back')" title="-10s" style="font-size:0.75rem">-10s</button>
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
      ${isSpotifyApp ? `
      <div style="padding:0 14px 10px">
        <button onclick="event.stopPropagation();spotifySearchOpen('${s.device}',this)"
          style="width:100%;padding:7px;border:0.5px solid #1DB954;border-radius:6px;background:none;cursor:pointer;font-size:0.82rem;color:#1DB954;font-weight:600;display:flex;align-items:center;justify-content:center;gap:6px">
          🔍 Søg i Spotify
        </button>
      </div>` : `
      <div style="padding:0 14px 6px">
        <button class="cast-transfer-btn" onclick="castShowTransferMenu('${s.device}',this)"
          style="width:100%;padding:6px;border:0.5px solid var(--border);border-radius:6px;background:none;cursor:pointer;font-size:0.8rem;color:#555;display:flex;align-items:center;justify-content:center;gap:6px">
          ${CAST_ICON_SVG} Afspil på anden enhed
        </button>
      </div>`}
    </div>`;
  }).join('');
}

async function castShowTransferMenu(sourceDevice, anchorEl) {
  let allDevices = [];
  try {
    const r = await apiFetch('/api/cast/devices');
    allDevices = (await r.json()).devices || [];
  } catch(e) {}

  document.querySelectorAll('.cast-transfer-menu').forEach(el => el.remove());
  const others = allDevices.filter(d => d !== sourceDevice);
  if (others.length === 0) return;

  const menu = document.createElement('div');
  menu.className = 'cast-transfer-menu';
  menu.innerHTML = `<div style="padding:6px 12px 4px;font-size:0.68rem;font-weight:700;color:#aaa;text-transform:uppercase;letter-spacing:.05em">Afspil på</div>` +
    others.map(d => {
      const s = castState[d];
      const isActive = s && (s.state === 'PLAYING' || s.state === 'BUFFERING' || s.state === 'PAUSED');
      const right = isActive
        ? `<span style="font-size:0.72rem;color:#ff9800;font-weight:600">Afspiller ✕</span>`
        : CAST_ICON_SVG;
      return `<div class="cast-transfer-item" data-device="${d}" data-active="${isActive}">
        <span style="margin-right:6px">${castAppIcon(s?.app)}</span>
        <span style="flex:1">${d}</span>${right}
      </div>`;
    }).join('');

  const rect = anchorEl.getBoundingClientRect();
  menu.style.cssText = `position:fixed;bottom:${window.innerHeight - rect.top + 4}px;right:${window.innerWidth - rect.right}px;
    background:#fff;border:0.5px solid var(--border);border-radius:8px;
    box-shadow:0 4px 16px rgba(0,0,0,0.15);z-index:2000;min-width:200px;overflow:hidden`;
  document.body.appendChild(menu);

  menu.querySelectorAll('.cast-transfer-item').forEach(item => {
    item.addEventListener('click', async () => {
      menu.remove();
      const target   = item.dataset.device;
      const isActive = item.dataset.active === 'true';
      try {
        if (isActive) {
          await apiFetch(`/api/cast/${encodeURIComponent(target)}/stop`, { method: 'POST' });
        } else {
          const res = await apiFetch(`/api/cast/${encodeURIComponent(sourceDevice)}/transfer`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ target })
          });
          const data = await res.json();
          if (!data.ok) setTimeout(() => alert('⚠️ ' + (data.detail || 'Transfer fejlede')), 100);
        }
      } catch(e) { console.warn('Cast transfer fejl:', e); }
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
      if (s.device) {
        castState[s.device] = s;
        if (castPanelOpen) {
          _castPanelDirty = true; // re-render udskydes til panelet lukkes/genåbnes
        }
        castRenderButton();
      }
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

// ── Spotify search modal ──────────────────────────────────────────────────────
let _spotifySearchDevice = '';
let _spotifyDeviceId     = '';
let _spotifySearchTimer  = null;
const SPOTIFY_TYPES = [
  { key: 'track',    label: '🎵 Sange' },
  { key: 'album',    label: '💿 Album' },
  { key: 'playlist', label: '📋 Playlists' },
  { key: 'show',     label: '🎙 Podcasts' },
];
let _spotifyActiveType = 'track';

async function spotifySearchOpen(castDeviceName, triggerBtn) {
  _spotifySearchDevice = castDeviceName;
  _spotifyDeviceId = '';

  // Byg og vis modal med det samme — vent ikke på device lookup
  document.getElementById('spotify-search-modal')?.remove();

  const anchor = triggerBtn || document.querySelector(`[onclick*="spotifySearchOpen"]`);
  const rect = anchor ? anchor.getBoundingClientRect() : null;
  const right = rect ? (window.innerWidth - rect.right) : 20;
  const bottom = rect ? (window.innerHeight - rect.top + 6) : 78;

  const modal = document.createElement('div');
  modal.id = 'spotify-search-modal';
  modal.innerHTML = `
    <div id="spotify-search-box">
      <div style="display:flex;align-items:center;justify-content:space-between;padding:12px 14px 0">
        <span style="font-weight:700;font-size:0.9rem;color:#1DB954">🔍 Søg i Spotify</span>
        <div style="display:flex;align-items:center;gap:8px">
          ${window._spotifyMockEnabled !== undefined ? `
          <label style="display:flex;align-items:center;gap:4px;font-size:0.72rem;color:#aaa;cursor:pointer" title="Skift mellem mock og rigtig Spotify">
            <input type="checkbox" id="sp-mock-toggle" ${window._spotifyMockEnabled ? 'checked' : ''}
              onchange="window._spotifyMockEnabled=this.checked; spotifySearchDebounce(document.getElementById('spotify-search-input')?.value||'')"
              style="cursor:pointer">
            mock
          </label>` : ''}
          <button onclick="spotifySearchClose()" style="background:none;border:none;font-size:1rem;cursor:pointer;color:#aaa;padding:2px 6px;line-height:1">✕</button>
        </div>
      </div>
      <div style="display:flex;gap:4px;padding:8px 14px 6px;overflow-x:auto">
        ${SPOTIFY_TYPES.map(t => `
          <button class="sp-tab${t.key === _spotifyActiveType ? ' active' : ''}"
            data-type="${t.key}" onclick="spotifySetType('${t.key}')">${t.label}</button>
        `).join('')}
      </div>
      <div style="padding:0 14px 8px">
        <input id="spotify-search-input" type="search" placeholder="Søg..."
          style="width:100%;box-sizing:border-box;padding:7px 12px;border:1px solid #ddd;border-radius:8px;font-size:0.88rem;outline:none"
          oninput="spotifySearchDebounce(this.value)" />
      </div>
      <div id="spotify-search-results" style="overflow-y:auto;max-height:480px;border-top:1px solid #f0f0f0">
        <div style="padding:20px;text-align:center;color:#bbb;font-size:0.82rem">Skriv for at søge</div>
      </div>
    </div>`;
  modal.style.cssText = `position:fixed;bottom:${bottom}px;right:${right}px;width:400px;z-index:2100;
    transform:translateY(8px);opacity:0;transition:transform .18s ease,opacity .18s ease`;
  document.body.appendChild(modal);

  requestAnimationFrame(() => {
    modal.style.transform = 'translateY(0)';
    modal.style.opacity = '1';
  });

  setTimeout(() => document.addEventListener('click', _spotifyOutsideClick), 50);
  setTimeout(() => document.getElementById('spotify-search-input')?.focus(), 100);

  // Hent device_id i baggrunden — påvirker ikke modal-visning
  try {
    const r = await apiFetch('/api/spotify/devices');
    const data = await r.json();
    const devices = data.devices || [];
    const match = devices.find(d =>
      d.name === castDeviceName ||
      castDeviceName.toLowerCase().includes(d.name.toLowerCase())
    );
    if (match) _spotifyDeviceId = match.id;
  } catch(e) { /* ingen device_id — play sender uden */ }
}

function _spotifyOutsideClick(e) {
  const modal = document.getElementById('spotify-search-modal');
  const panel = document.getElementById('cast-panel');
  if (modal && !modal.contains(e.target) && !(panel && panel.contains(e.target))) {
    spotifySearchClose();
  }
}

function spotifySearchClose() {
  clearTimeout(_spotifySearchTimer);
  document.removeEventListener('click', _spotifyOutsideClick);
  document.getElementById('spotify-search-modal')?.remove();
}

function spotifySetType(type) {
  _spotifyActiveType = type;
  document.querySelectorAll('.sp-tab').forEach(b => b.classList.toggle('active', b.dataset.type === type));
  const q = document.getElementById('spotify-search-input')?.value || '';
  if (q.trim()) spotifyDoSearch(q);
}

function spotifySearchDebounce(q) {
  clearTimeout(_spotifySearchTimer);
  if (!q.trim()) {
    document.getElementById('spotify-search-results').innerHTML =
      '<div style="padding:24px;text-align:center;color:#bbb;font-size:0.85rem">Skriv for at søge</div>';
    return;
  }
  _spotifySearchTimer = setTimeout(() => spotifyDoSearch(q), 350);
}

async function spotifyDoSearch(q) {
  const resultsEl = document.getElementById('spotify-search-results');
  if (!resultsEl) return;
  resultsEl.innerHTML = '<div style="padding:24px;text-align:center;color:#bbb;font-size:0.85rem">Søger…</div>';
  try {
    const r = await apiFetch(`/api/spotify/search?q=${encodeURIComponent(q)}&type=${_spotifyActiveType}`);
    const { items } = await r.json();
    if (!items || items.length === 0) {
      resultsEl.innerHTML = '<div style="padding:24px;text-align:center;color:#bbb;font-size:0.85rem">Ingen resultater</div>';
      return;
    }
    resultsEl.innerHTML = items.map(item => `
      <div class="sp-result" onclick="spotifyPlay('${encodeURIComponent(item.uri)}')">
        ${item.image
          ? `<img src="${item.image}" style="width:44px;height:44px;border-radius:4px;object-fit:cover;flex-shrink:0">`
          : `<div style="width:44px;height:44px;border-radius:4px;background:#eee;display:flex;align-items:center;justify-content:center;font-size:1.2rem;flex-shrink:0">${_spotifyTypeIcon(item.type)}</div>`}
        <div style="flex:1;min-width:0">
          <div style="font-size:0.88rem;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;color:#111">${item.name}</div>
          ${item.sub ? `<div style="font-size:0.78rem;color:#999;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;margin-top:2px">${item.sub}</div>` : ''}
        </div>
      </div>`).join('');
  } catch(e) {
    resultsEl.innerHTML = '<div style="padding:24px;text-align:center;color:#e53935;font-size:0.85rem">Fejl ved søgning</div>';
  }
}

function _spotifyTypeIcon(type) {
  return { track: '🎵', album: '💿', playlist: '📋', show: '🎙' }[type] || '🎵';
}

async function spotifyPlay(encodedUri) {
  const uri = decodeURIComponent(encodedUri);
  try {
    const r = await apiFetch('/api/spotify/play', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ uri, device_id: _spotifyDeviceId }),
    });
    if (r.ok) spotifySearchClose();
    else console.warn('Spotify play fejl:', await r.text());
  } catch(e) { console.warn('Spotify play fejl:', e); }
}

// ── Dev mock ──────────────────────────────────────────────────────────────────
const _mockSearchData = {
  track: [
    { uri: 'spotify:track:1',  name: 'Bohemian Rhapsody',      sub: 'Queen',             image: '', type: 'track' },
    { uri: 'spotify:track:2',  name: 'Hotel California',        sub: 'Eagles',            image: '', type: 'track' },
    { uri: 'spotify:track:3',  name: 'Stairway to Heaven',      sub: 'Led Zeppelin',      image: '', type: 'track' },
    { uri: 'spotify:track:4',  name: 'Smells Like Teen Spirit', sub: 'Nirvana',           image: '', type: 'track' },
    { uri: 'spotify:track:5',  name: 'Billie Jean',             sub: 'Michael Jackson',   image: '', type: 'track' },
    { uri: 'spotify:track:6',  name: 'Purple Rain',             sub: 'Prince',            image: '', type: 'track' },
    { uri: 'spotify:track:7',  name: 'Like a Rolling Stone',    sub: 'Bob Dylan',         image: '', type: 'track' },
    { uri: 'spotify:track:8',  name: 'Johnny B. Goode',         sub: 'Chuck Berry',       image: '', type: 'track' },
    { uri: 'spotify:track:9',  name: 'Superstition',            sub: 'Stevie Wonder',     image: '', type: 'track' },
    { uri: 'spotify:track:10', name: 'Respect',                 sub: 'Aretha Franklin',   image: '', type: 'track' },
  ],
  album: [
    { uri: 'spotify:album:1',  name: 'Abbey Road',              sub: 'The Beatles',       image: '', type: 'album' },
    { uri: 'spotify:album:2',  name: 'Thriller',                sub: 'Michael Jackson',   image: '', type: 'album' },
    { uri: 'spotify:album:3',  name: 'Dark Side of the Moon',   sub: 'Pink Floyd',        image: '', type: 'album' },
    { uri: 'spotify:album:4',  name: 'Rumours',                 sub: 'Fleetwood Mac',     image: '', type: 'album' },
    { uri: 'spotify:album:5',  name: 'Led Zeppelin IV',         sub: 'Led Zeppelin',      image: '', type: 'album' },
    { uri: 'spotify:album:6',  name: 'Back in Black',           sub: 'AC/DC',             image: '', type: 'album' },
    { uri: 'spotify:album:7',  name: 'Purple Rain',             sub: 'Prince',            image: '', type: 'album' },
    { uri: 'spotify:album:8',  name: 'Born to Run',             sub: 'Bruce Springsteen', image: '', type: 'album' },
    { uri: 'spotify:album:9',  name: 'Nevermind',               sub: 'Nirvana',           image: '', type: 'album' },
    { uri: 'spotify:album:10', name: 'Kind of Blue',            sub: 'Miles Davis',       image: '', type: 'album' },
  ],
  playlist: [
    { uri: 'spotify:playlist:1',  name: 'All Out 70s',          sub: 'Spotify',           image: '', type: 'playlist' },
    { uri: 'spotify:playlist:2',  name: 'Rock Classics',        sub: 'Spotify',           image: '', type: 'playlist' },
    { uri: 'spotify:playlist:3',  name: 'Peaceful Piano',       sub: 'Spotify',           image: '', type: 'playlist' },
    { uri: 'spotify:playlist:4',  name: 'Top 50 Danmark',       sub: 'Spotify Charts',    image: '', type: 'playlist' },
    { uri: 'spotify:playlist:5',  name: 'Morning Motivation',   sub: 'Spotify',           image: '', type: 'playlist' },
    { uri: 'spotify:playlist:6',  name: 'Soft Pop Hits',        sub: 'Spotify',           image: '', type: 'playlist' },
    { uri: 'spotify:playlist:7',  name: 'Jazz Classics',        sub: 'Spotify',           image: '', type: 'playlist' },
    { uri: 'spotify:playlist:8',  name: 'Power Workout',        sub: 'Spotify',           image: '', type: 'playlist' },
    { uri: 'spotify:playlist:9',  name: 'Chill Hits',           sub: 'Spotify',           image: '', type: 'playlist' },
    { uri: 'spotify:playlist:10', name: 'Danes Only',           sub: 'Spotify',           image: '', type: 'playlist' },
  ],
  show: [
    { uri: 'spotify:show:1',  name: 'Dansernes Nat',                    sub: 'DR',                image: '', type: 'show' },
    { uri: 'spotify:show:2',  name: 'Lex & Lotte',                      sub: 'Podcaster.dk',      image: '', type: 'show' },
    { uri: 'spotify:show:3',  name: 'How I Built This',                 sub: 'Guy Raz / NPR',     image: '', type: 'show' },
    { uri: 'spotify:show:4',  name: 'Tidernes Morgen',                  sub: 'Berlingske',        image: '', type: 'show' },
    { uri: 'spotify:show:5',  name: 'Serial',                           sub: 'This American Life',image: '', type: 'show' },
    { uri: 'spotify:show:6',  name: 'Historier fra Danmarkshistorien',  sub: 'DR',                image: '', type: 'show' },
    { uri: 'spotify:show:7',  name: 'The Daily',                        sub: 'The New York Times',image: '', type: 'show' },
    { uri: 'spotify:show:8',  name: 'Vores Penge',                      sub: 'Finans.dk',         image: '', type: 'show' },
    { uri: 'spotify:show:9',  name: 'Mysteriet om',                     sub: 'Politiken',         image: '', type: 'show' },
    { uri: 'spotify:show:10', name: "Conan O'Brien Needs a Friend",     sub: 'Team Coco',         image: '', type: 'show' },
  ],
};

function castMockSpotify() {
  castState['Stue TV'] = {
    device: 'Stue TV', app: 'Spotify', state: 'PLAYING',
    title: 'Bohemian Rhapsody', artist: 'Queen', album: 'A Night at the Opera',
    image: 'https://i.scdn.co/image/ab67616d0000b27358591cfc5e3044be8d1c21cc',
    volume: 0.6, duration: 354, current_time: 45,
    last_updated: Date.now() / 1000, supports_seek: true,
  };
  castRenderButton();

  // Monkey-patch apiFetch for mock search
  const _realApiFetch = window._realApiFetch || apiFetch;
  window._realApiFetch = _realApiFetch;
  window.apiFetch = function(url, opts) {
    if (!window._spotifyMockEnabled) return _realApiFetch(url, opts);
    if (url.startsWith('/api/spotify/search')) {
      const type = new URLSearchParams(url.split('?')[1]).get('type') || 'track';
      const items = _mockSearchData[type] || _mockSearchData.track;
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ items }) });
    }
    if (url === '/api/spotify/devices') {
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ devices: [{ id: 'mock-device-id', name: 'Stue TV' }] }) });
    }
    if (url === '/api/spotify/play') {
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ ok: true }) });
    }
    return _realApiFetch(url, opts);
  };
  window._spotifyMockEnabled = true;
}

async function castInit() {
  try {
    const r = await apiFetch('/api/cast/state');
    const data = await r.json();
    castState = data || {};
    castRenderButton();
  } catch(e) {}
  castStartWS();

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
