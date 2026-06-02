// family.js — Familie-sider (Børn & Voksne) + apps
// Config gemmes i localStorage:
//   family_kids_apps   → array af app-id'er
//   family_adults_apps → array af app-id'er

const FAMILY_APPS = {
  kids: [
    { id: 'regnespil', label: 'Regnespil',   icon: '➕', comingSoon: false },
    { id: 'tal',       label: 'Tal',          icon: '🔢', comingSoon: false },
    { id: 'spell',     label: 'Stavespil',    icon: '🔤', comingSoon: true  },
    { id: 'wordgame',  label: 'Ordleg',       icon: '🃏', comingSoon: true  },
    { id: 'drawing',   label: 'Tegnesjov',    icon: '🎨', comingSoon: true  },
    { id: 'memory',    label: 'Memory',       icon: '🧠', comingSoon: true  },
  ],
  adults: [
    { id: 'nyheder',  label: 'Nyheder',       icon: '📰', comingSoon: false },
    { id: 'tv2',      label: 'TV2 Nyheder',   icon: '📡', comingSoon: true  },
    { id: 'borsen',   label: 'Børsen',        icon: '📈', comingSoon: true  },
    { id: 'weather',  label: 'DMI Vejr',      icon: '🌤️', comingSoon: true  },
    { id: 'bt',       label: 'BT',            icon: '🗞️', comingSoon: true  },
  ],
};

// ── Config helpers ────────────────────────────────────────────────────────────
function getFamilyConfig() {
  return {
    kids:   JSON.parse(localStorage.getItem('family_kids_apps')   || '[]'),
    adults: JSON.parse(localStorage.getItem('family_adults_apps') || '[]'),
  };
}

// ── Nav visibility ────────────────────────────────────────────────────────────
function updateFamilyNav() {
  const cfg     = getFamilyConfig();
  const hasKids   = cfg.kids.length   > 0;
  const hasAdults = cfg.adults.length > 0;

  const btn      = document.getElementById('family-nav-btn');
  const ddKids   = document.getElementById('family-dd-kids');
  const ddAdults = document.getElementById('family-dd-adults');
  if (!btn) return;

  btn.style.display      = (hasKids || hasAdults) ? '' : 'none';
  if (ddKids)   ddKids.style.display   = hasKids   ? '' : 'none';
  if (ddAdults) ddAdults.style.display = hasAdults ? '' : 'none';
}

// ── Dropdown toggle ───────────────────────────────────────────────────────────
function toggleFamilyMenu(e) {
  e.stopPropagation();
  const dd    = document.getElementById('family-dropdown');
  const aulaDD = document.getElementById('aula-dropdown');
  if (aulaDD) aulaDD.style.display = 'none';
  if (!dd) return;
  const open = dd.style.display !== 'block';
  dd.style.display = open ? 'block' : 'none';
  if (open) {
    setTimeout(() => {
      document.addEventListener('click', function h() {
        dd.style.display = 'none';
        document.removeEventListener('click', h);
      });
    }, 0);
  }
}

// ── App grid pages ────────────────────────────────────────────────────────────
function renderFamilyPage(type) {
  const cfg      = getFamilyConfig();
  const enabled  = type === 'kids' ? cfg.kids : cfg.adults;
  const allApps  = FAMILY_APPS[type];
  const gridEl   = document.getElementById(`family-${type}-grid`);
  if (!gridEl) return;

  const apps = allApps.filter(a => enabled.includes(a.id));
  if (!apps.length) {
    gridEl.innerHTML = '<p style="color:#aaa;font-size:0.9rem;padding:20px 0">Ingen apps aktiveret.<br>Gå til ⚙️ Indstillinger → Familie Apps.</p>';
    return;
  }

  gridEl.innerHTML = apps.map(app => {
    if (app.comingSoon) {
      return `<div class="family-app-tile coming-soon">
        <div class="family-app-icon">${app.icon}</div>
        <div class="family-app-label">${app.label}</div>
        <div class="family-app-soon">Kommer snart</div>
      </div>`;
    }
    return `<div class="family-app-tile" onclick="openFamilyApp('${app.id}')">
      <div class="family-app-icon">${app.icon}</div>
      <div class="family-app-label">${app.label}</div>
    </div>`;
  }).join('');
}

// ── App launcher ──────────────────────────────────────────────────────────────
function openFamilyApp(id) {
  switchView('app-' + id);
}

// ── Back button helper ────────────────────────────────────────────────────────
function familyAppBack(parentView) {
  switchView(parentView);
}

// ══════════════════════════════════════════════════════════════════════════════
// APP: TAL (børne-tælle-app)
// ══════════════════════════════════════════════════════════════════════════════
let talCount = 0;

function renderTalApp() {
  const el = document.getElementById('view-app-tal');
  if (!el) return;
  el.innerHTML = `
    <div class="family-app-page">
      <button class="family-back-btn" onclick="familyAppBack('family-kids')">← Tilbage</button>
      <div class="tal-container">
        <div class="tal-number" id="tal-number">${talCount}</div>
        <div class="tal-controls">
          <button class="tal-btn tal-minus" onclick="talChange(-1)">−</button>
          <button class="tal-btn tal-reset" onclick="talReset()">↺</button>
          <button class="tal-btn tal-plus"  onclick="talChange(1)">+</button>
        </div>
        <div class="tal-hint">Tæl hvad som helst!</div>
      </div>
    </div>`;
}

function talChange(delta) {
  talCount = Math.max(0, talCount + delta);
  const el = document.getElementById('tal-number');
  if (el) {
    el.textContent = talCount;
    el.classList.remove('tal-pop');
    void el.offsetWidth; // reflow
    el.classList.add('tal-pop');
  }
}

function talReset() {
  talCount = 0;
  const el = document.getElementById('tal-number');
  if (el) el.textContent = '0';
}

// ══════════════════════════════════════════════════════════════════════════════
// APP: NYHEDER (DR RSS via allOrigins proxy)
// ══════════════════════════════════════════════════════════════════════════════
let nyhedItems = null; // cached

async function renderNyhedApp() {
  const el = document.getElementById('view-app-nyheder');
  if (!el) return;

  el.innerHTML = `
    <div class="family-app-page">
      <button class="family-back-btn" onclick="familyAppBack('family-adults')">← Tilbage</button>
      <div class="nyhed-header">
        <span class="nyhed-logo">DR</span>
        <span class="nyhed-title">Nyheder</span>
        <button class="nyhed-refresh" onclick="loadNyheder(true)" title="Opdater">↻</button>
      </div>
      <div id="nyhed-list" class="nyhed-list">
        <div class="nyhed-loading">Henter nyheder…</div>
      </div>
    </div>`;

  await loadNyheder(false);
}

async function loadNyheder(force) {
  const listEl = document.getElementById('nyhed-list');
  if (!listEl) return;

  // Use cache unless forced
  if (!force && nyhedItems) {
    renderNyhedList(nyhedItems);
    return;
  }

  listEl.innerHTML = '<div class="nyhed-loading">Henter nyheder…</div>';

  try {
    const FEED = 'https://www.dr.dk/nyheder/service/feeds/allenyheder';
    const url  = `https://api.allorigins.win/get?url=${encodeURIComponent(FEED)}`;
    const res  = await fetch(url, { signal: AbortSignal.timeout(8000) });
    const json = await res.json();
    const parser = new DOMParser();
    const doc  = parser.parseFromString(json.contents, 'text/xml');
    const items = [...doc.querySelectorAll('item')].slice(0, 15).map(item => ({
      title:   item.querySelector('title')?.textContent || '',
      link:    item.querySelector('link')?.textContent  || '',
      date:    item.querySelector('pubDate')?.textContent || '',
      desc:    item.querySelector('description')?.textContent || '',
      img:     item.querySelector('enclosure')?.getAttribute('url')
            || item.querySelector('thumbnail')?.getAttribute('url')
            || '',
    }));
    nyhedItems = items;
    renderNyhedList(items);
  } catch(e) {
    listEl.innerHTML = '<div class="nyhed-loading" style="color:#c00">Kunne ikke hente nyheder. Tjek netværksforbindelsen.</div>';
  }
}

function renderNyhedList(items) {
  const listEl = document.getElementById('nyhed-list');
  if (!listEl) return;
  if (!items || !items.length) {
    listEl.innerHTML = '<div class="nyhed-loading">Ingen nyheder.</div>';
    return;
  }
  listEl.innerHTML = items.map((it, i) => `
    <div class="nyhed-item" onclick="openNyhed(${i})">
      ${it.img ? `<img class="nyhed-thumb" src="${it.img}" alt="" loading="lazy" onerror="this.style.display='none'">` : ''}
      <div class="nyhed-body">
        <div class="nyhed-item-title">${it.title}</div>
        <div class="nyhed-item-date">${formatNyhedDate(it.date)}</div>
      </div>
    </div>`).join('');
}

function openNyhed(idx) {
  if (!nyhedItems || !nyhedItems[idx]) return;
  const it = nyhedItems[idx];
  // Open in new tab/window — fullscreen browser handles it fine
  window.open(it.link, '_blank');
}

function formatNyhedDate(dateStr) {
  try {
    const d = new Date(dateStr);
    const now = new Date();
    const diff = Math.floor((now - d) / 60000); // minutes
    if (diff < 1)   return 'Lige nu';
    if (diff < 60)  return `${diff} min. siden`;
    if (diff < 1440) return `${Math.floor(diff/60)} timer siden`;
    return d.toLocaleDateString('da-DK', { weekday: 'short', day: 'numeric', month: 'short' });
  } catch(e) { return ''; }
}

// ══════════════════════════════════════════════════════════════════════════════
// APP: REGNESPIL — Træk svaret til lighedstegnet
// ══════════════════════════════════════════════════════════════════════════════

// Emoji-sæt per talstørrelse — bruges til at vise kugler visuelt
const RS_EMOJIS = ['🍎','🌟','🐠','🦋','🌸','🍭','🎈','🐸','🍓','🔵','🟡','🟠'];

let rs = {
  a: 0, b: 0,          // de to led
  answer: 0,           // korrekt svar
  options: [],         // de tre svarmuligheder (tal)
  score: 0,
  streak: 0,
  total: 0,
  dragging: null,      // { value, el, startX, startY, origRect }
  answered: false,
};

function renderRegnespil() {
  const el = document.getElementById('view-app-regnespil');
  if (!el) return;
  el.innerHTML = `
    <div class="rs-shell">
      <div class="rs-topbar">
        <button class="family-back-btn" onclick="familyAppBack('family-kids')" style="padding:0;margin:0">← Tilbage</button>
        <div class="rs-score-row">
          <span id="rs-stars"></span>
          <span class="rs-score-label">Point: <strong id="rs-score">0</strong></span>
        </div>
      </div>
      <div class="rs-stage" id="rs-stage">
        <div class="rs-equation" id="rs-equation"></div>
        <div class="rs-options" id="rs-options"></div>
      </div>
      <div class="rs-feedback" id="rs-feedback" style="display:none"></div>
    </div>`;
  rs.score = 0; rs.streak = 0; rs.total = 0;
  rsNewRound();
}

function rsNewRound() {
  rs.answered = false;
  // Difficulty: scale max number with streak
  const maxN = Math.min(5 + Math.floor(rs.streak / 3), 9);
  rs.a = 1 + Math.floor(Math.random() * maxN);
  rs.b = 1 + Math.floor(Math.random() * (maxN - rs.a + 1));
  rs.answer = rs.a + rs.b;

  // Pick ONE emoji for the whole round
  rs.emoji = RS_EMOJIS[Math.floor(Math.random() * RS_EMOJIS.length)];

  // Three options: correct + two wrong (unique, close to correct so it's educational)
  const wrong = new Set();
  let attempts = 0;
  while (wrong.size < 2 && attempts < 100) {
    attempts++;
    // Bias wrong answers to be close (±1–3) so bubbles are countable
    const delta = (Math.random() < 0.7)
      ? (Math.floor(Math.random() * 3) + 1) * (Math.random() < 0.5 ? 1 : -1)
      : Math.floor(Math.random() * 5) + 1;
    const w = rs.answer + delta;
    if (w >= 1 && w !== rs.answer) wrong.add(w);
  }
  rs.options = shuffle([rs.answer, ...wrong]);

  rsRenderRound();
}

function rsRenderRound() {
  const eq   = document.getElementById('rs-equation');
  const opts = document.getElementById('rs-options');
  if (!eq || !opts) return;

  const em = rs.emoji;

  eq.innerHTML = `
    <div class="rs-group">
      <div class="rs-bubbles">${em.repeat(rs.a)}</div>
      <div class="rs-num">${rs.a}</div>
    </div>
    <div class="rs-plus">+</div>
    <div class="rs-group">
      <div class="rs-bubbles">${em.repeat(rs.b)}</div>
      <div class="rs-num">${rs.b}</div>
    </div>
    <div class="rs-equals">=</div>
    <div class="rs-dropzone" id="rs-dropzone">
      <span class="rs-dz-hint">?</span>
    </div>`;

  opts.innerHTML = rs.options.map(v => {
    return `<div class="rs-option" data-val="${v}" id="rs-opt-${v}">
      <div class="rs-opt-bubbles">${em.repeat(v)}</div>
      <div class="rs-opt-num">${v}</div>
    </div>`;
  }).join('');

  rsUpdateStars();
  rsBindDrag();
}

// ── Stjerner ──────────────────────────────────────────────────────────────────
function rsUpdateStars() {
  const el = document.getElementById('rs-stars');
  if (!el) return;
  const stars = Math.min(rs.streak, 5);
  el.innerHTML = '⭐'.repeat(stars) + '☆'.repeat(5 - stars);
}

// ── Drag & Drop (pointer events — virker på touch og mus) ────────────────────
function rsBindDrag() {
  document.querySelectorAll('.rs-option').forEach(opt => {
    opt.addEventListener('pointerdown', rsPointerDown, { passive: false });
  });
}

function rsBindDrop() {
  // handled in pointermove/up via overlap detection
}

let rsGhost = null; // flydende kopi mens man trækker

function rsPointerDown(e) {
  if (rs.answered) return;
  e.preventDefault();
  const opt = e.currentTarget;
  const val = parseInt(opt.dataset.val);
  const rect = opt.getBoundingClientRect();

  // Lav en "ghost" der følger fingeren
  rsGhost = document.createElement('div');
  rsGhost.className = 'rs-ghost';
  rsGhost.innerHTML = `<div class="rs-opt-bubbles">${rs.emoji.repeat(val)}</div><div class="rs-opt-num">${val}</div>`;
  rsGhost.style.cssText = `left:${rect.left}px;top:${rect.top}px;width:${rect.width}px;`;
  document.body.appendChild(rsGhost);

  rs.dragging = { val, opt, startX: e.clientX, startY: e.clientY, origTop: rect.top, origLeft: rect.left };
  opt.classList.add('rs-dragging-src');

  document.addEventListener('pointermove', rsPointerMove, { passive: false });
  document.addEventListener('pointerup',   rsPointerUp);
}

function rsPointerMove(e) {
  if (!rsGhost || !rs.dragging) return;
  e.preventDefault();
  const dx = e.clientX - rs.dragging.startX;
  const dy = e.clientY - rs.dragging.startY;
  rsGhost.style.left = (rs.dragging.origLeft + dx) + 'px';
  rsGhost.style.top  = (rs.dragging.origTop  + dy) + 'px';

  // Highlight dropzone ved overlap
  const dz   = document.getElementById('rs-dropzone');
  const dzR  = dz ? dz.getBoundingClientRect() : null;
  const ghostR = rsGhost.getBoundingClientRect();
  if (dz && dzR) {
    const over = ghostR.left < dzR.right && ghostR.right > dzR.left &&
                 ghostR.top  < dzR.bottom && ghostR.bottom > dzR.top;
    dz.classList.toggle('rs-dz-hover', over);
  }
}

function rsPointerUp(e) {
  document.removeEventListener('pointermove', rsPointerMove);
  document.removeEventListener('pointerup',   rsPointerUp);
  if (!rsGhost || !rs.dragging) return;

  const dz   = document.getElementById('rs-dropzone');
  const dzR  = dz ? dz.getBoundingClientRect() : null;
  const ghostR = rsGhost.getBoundingClientRect();

  const dropped = dz && dzR &&
    ghostR.left < dzR.right && ghostR.right > dzR.left &&
    ghostR.top  < dzR.bottom && ghostR.bottom > dzR.top;

  rsGhost.remove(); rsGhost = null;
  rs.dragging.opt.classList.remove('rs-dragging-src');

  if (dropped) {
    rsCheckAnswer(rs.dragging.val);
  }
  rs.dragging = null;
}

// ── Facit ─────────────────────────────────────────────────────────────────────
function rsCheckAnswer(val) {
  if (rs.answered) return;
  rs.answered = true;
  rs.total++;

  const correct = val === rs.answer;
  const dz = document.getElementById('rs-dropzone');
  const fb = document.getElementById('rs-feedback');

  if (correct) {
    rs.score++;
    rs.streak++;
    if (dz) {
      dz.innerHTML = `<span class="rs-dz-answer rs-dz-correct">${val}</span>`;
      dz.classList.add('rs-dz-filled-correct');
    }
    rsBurst(dz);
    if (fb) {
      const msgs = ['Fantastisk! 🎉','Super! ⭐','Bravo! 🌟','Perfekt! 🎊','Dygtig! 🏆'];
      fb.textContent = msgs[Math.floor(Math.random() * msgs.length)];
      fb.className = 'rs-feedback rs-feedback-correct';
      fb.style.display = 'block';
    }
  } else {
    rs.streak = 0;
    // Show correct answer in dropzone
    if (dz) {
      dz.innerHTML = `<span class="rs-dz-answer rs-dz-wrong">${rs.answer}</span>`;
      dz.classList.add('rs-dz-filled-wrong');
    }
    // Shake wrong option
    const wrongOpt = document.getElementById(`rs-opt-${val}`);
    if (wrongOpt) { wrongOpt.classList.add('rs-shake'); setTimeout(() => wrongOpt.classList.remove('rs-shake'), 500); }
    if (fb) {
      fb.textContent = `Ikke helt — svaret er ${rs.answer} 💪`;
      fb.className = 'rs-feedback rs-feedback-wrong';
      fb.style.display = 'block';
    }
  }

  document.getElementById('rs-score').textContent = rs.score;
  rsUpdateStars();

  // Næste opgave efter pause
  setTimeout(() => {
    if (fb) fb.style.display = 'none';
    rsNewRound();
  }, correct ? 1400 : 2000);
}

// ── Konfetti-burst ved rigtigt svar ──────────────────────────────────────────
function rsBurst(anchor) {
  const stage = document.getElementById('rs-stage');
  if (!stage || !anchor) return;
  const rect = anchor.getBoundingClientRect();
  const stageR = stage.getBoundingClientRect();
  const cx = rect.left + rect.width/2  - stageR.left;
  const cy = rect.top  + rect.height/2 - stageR.top;
  const colors = ['#FFD700','#FF6B6B','#4ECDC4','#45B7D1','#96CEB4','#FFEAA7'];
  for (let i = 0; i < 18; i++) {
    const p = document.createElement('div');
    p.className = 'rs-particle';
    p.style.cssText = `left:${cx}px;top:${cy}px;background:${colors[i%colors.length]};
      --dx:${(Math.random()-0.5)*200}px;--dy:${-(40+Math.random()*160)}px;
      --rot:${Math.random()*720}deg;`;
    stage.appendChild(p);
    setTimeout(() => p.remove(), 900);
  }
}

// ── Hjælper ───────────────────────────────────────────────────────────────────
function shuffle(arr) {
  for (let i = arr.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [arr[i], arr[j]] = [arr[j], arr[i]];
  }
  return arr;
}

// ── Boot ──────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  updateFamilyNav();
});
