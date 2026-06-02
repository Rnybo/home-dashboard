// family.js — Familie-sider (Børn & Voksne) + apps

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

function getFamilyConfig() {
  return {
    kids:   JSON.parse(localStorage.getItem('family_kids_apps')   || '[]'),
    adults: JSON.parse(localStorage.getItem('family_adults_apps') || '[]'),
  };
}

function updateFamilyNav() {
  const cfg = getFamilyConfig();
  const btn      = document.getElementById('family-nav-btn');
  const ddKids   = document.getElementById('family-dd-kids');
  const ddAdults = document.getElementById('family-dd-adults');
  if (!btn) return;
  btn.style.display      = (cfg.kids.length || cfg.adults.length) ? '' : 'none';
  if (ddKids)   ddKids.style.display   = cfg.kids.length   ? '' : 'none';
  if (ddAdults) ddAdults.style.display = cfg.adults.length ? '' : 'none';
}

function toggleFamilyMenu(e) {
  e.stopPropagation();
  const dd = document.getElementById('family-dropdown');
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

function renderFamilyPage(type) {
  const cfg     = getFamilyConfig();
  const enabled = type === 'kids' ? cfg.kids : cfg.adults;
  const gridEl  = document.getElementById(`family-${type}-grid`);
  if (!gridEl) return;

  const apps = FAMILY_APPS[type].filter(a => enabled.includes(a.id));
  if (!apps.length) {
    gridEl.innerHTML = '<p style="color:#aaa;font-size:0.9rem;padding:20px 0">Ingen apps aktiveret.<br>Gå til ⚙️ Indstillinger → Familie Apps.</p>';
    return;
  }
  gridEl.innerHTML = apps.map(app => app.comingSoon
    ? `<div class="family-app-tile coming-soon"><div class="family-app-icon">${app.icon}</div><div class="family-app-label">${app.label}</div><div class="family-app-soon">Kommer snart</div></div>`
    : `<div class="family-app-tile" onclick="openFamilyApp('${app.id}')"><div class="family-app-icon">${app.icon}</div><div class="family-app-label">${app.label}</div></div>`
  ).join('');
}

function openFamilyApp(id)        { switchView('app-' + id); }
function familyAppBack(parentView) { switchView(parentView); }

// ══════════════════════════════════════════════════════════════════════════════
// APP: TAL
// ══════════════════════════════════════════════════════════════════════════════
let talCount = 0;

function renderTalApp() {
  const el = document.getElementById('view-app-tal');
  if (!el) return;
  el.innerHTML = `<div class="family-app-page">
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
  if (el) { el.textContent = talCount; el.classList.remove('tal-pop'); void el.offsetWidth; el.classList.add('tal-pop'); }
}
function talReset() { talCount = 0; const el = document.getElementById('tal-number'); if (el) el.textContent = '0'; }

// ══════════════════════════════════════════════════════════════════════════════
// APP: NYHEDER
// ══════════════════════════════════════════════════════════════════════════════
let nyhedItems = null;

async function renderNyhedApp() {
  const el = document.getElementById('view-app-nyheder');
  if (!el) return;
  el.innerHTML = `<div class="family-app-page">
    <button class="family-back-btn" onclick="familyAppBack('family-adults')">← Tilbage</button>
    <div class="nyhed-header">
      <span class="nyhed-logo">DR</span>
      <span class="nyhed-title">Nyheder</span>
      <button class="nyhed-refresh" onclick="loadNyheder(true)">↻</button>
    </div>
    <div id="nyhed-list" class="nyhed-list"><div class="nyhed-loading">Henter nyheder…</div></div>
  </div>`;
  await loadNyheder(false);
}

async function loadNyheder(force) {
  const listEl = document.getElementById('nyhed-list');
  if (!listEl) return;
  if (!force && nyhedItems) { renderNyhedList(nyhedItems); return; }
  listEl.innerHTML = '<div class="nyhed-loading">Henter nyheder…</div>';
  try {
    const FEED = 'https://www.dr.dk/nyheder/service/feeds/allenyheder';
    const res  = await fetch(`https://api.allorigins.win/get?url=${encodeURIComponent(FEED)}`, { signal: AbortSignal.timeout(8000) });
    const json = await res.json();
    const doc  = new DOMParser().parseFromString(json.contents, 'text/xml');
    nyhedItems = [...doc.querySelectorAll('item')].slice(0, 15).map(item => ({
      title: item.querySelector('title')?.textContent || '',
      link:  item.querySelector('link')?.textContent  || '',
      date:  item.querySelector('pubDate')?.textContent || '',
      img:   item.querySelector('enclosure')?.getAttribute('url') || item.querySelector('thumbnail')?.getAttribute('url') || '',
    }));
    renderNyhedList(nyhedItems);
  } catch(e) {
    listEl.innerHTML = '<div class="nyhed-loading" style="color:#c00">Kunne ikke hente nyheder.</div>';
  }
}

function renderNyhedList(items) {
  const listEl = document.getElementById('nyhed-list');
  if (!listEl) return;
  if (!items?.length) { listEl.innerHTML = '<div class="nyhed-loading">Ingen nyheder.</div>'; return; }
  listEl.innerHTML = items.map((it, i) => `
    <div class="nyhed-item" onclick="openNyhed(${i})">
      ${it.img ? `<img class="nyhed-thumb" src="${it.img}" alt="" loading="lazy" onerror="this.style.display='none'">` : ''}
      <div class="nyhed-body">
        <div class="nyhed-item-title">${it.title}</div>
        <div class="nyhed-item-date">${formatNyhedDate(it.date)}</div>
      </div>
    </div>`).join('');
}
function openNyhed(idx) { if (nyhedItems?.[idx]) window.open(nyhedItems[idx].link, '_blank'); }
function formatNyhedDate(dateStr) {
  try {
    const diff = Math.floor((new Date() - new Date(dateStr)) / 60000);
    if (diff < 1) return 'Lige nu';
    if (diff < 60) return `${diff} min. siden`;
    if (diff < 1440) return `${Math.floor(diff/60)} timer siden`;
    return new Date(dateStr).toLocaleDateString('da-DK', { weekday:'short', day:'numeric', month:'short' });
  } catch(e) { return ''; }
}

// ══════════════════════════════════════════════════════════════════════════════
// APP: REGNESPIL
// ══════════════════════════════════════════════════════════════════════════════

const RS_EMOJIS = ['🍎','🌟','🐠','🦋','🌸','🍭','🎈','🐸','🍓','🔵','🟡','🟠'];

const RS_LEVELS = [
  { id: 'seed',   icon: '🌱', label: 'Frø',     color: '#22c55e', maxAnswer: 9,   maxN: 8,  desc: 'Op til 9'   },
  { id: 'moon',   icon: '🌙', label: 'Måne',    color: '#3b82f6', maxAnswer: 20,  maxN: 15, desc: 'Op til 20'  },
  { id: 'rocket', icon: '🚀', label: 'Raket',   color: '#ec4899', maxAnswer: 50,  maxN: 40, desc: 'Op til 50'  },
  { id: 'star',   icon: '⭐', label: 'Stjerne', color: '#f59e0b', maxAnswer: 100, maxN: 90, desc: 'Op til 100' },
];

const RS_OPS = [
  { id: 'plus',   sym: '+', label: 'Plus',     icon: '➕' },
  { id: 'minus',  sym: '−', label: 'Minus',    icon: '➖' },
  { id: 'times',  sym: '×', label: 'Gange',    icon: '✖️' },
  { id: 'divide', sym: '÷', label: 'Division', icon: '➗' },
];

let rs = {
  a: 0, b: 0, answer: 0, op: 'plus',
  options: [], emoji: '🍎',
  score: 0, streak: 0, total: 0,
  dragging: null, answered: false,
  level: 'seed',
  ops: ['plus'],
  phase: 'setup',
  childName: '',
  childPhoto: '',
};

// Vis N bobler — over 9 vises emoji + ×N badge
function rsBubbles(n, emoji) {
  if (n <= 9) return emoji.repeat(n);
  return `${emoji}<span class="rs-badge">×${n}</span>`;
}

// Vis bobler i svarkortet — max 6 synlige, resten som +N
function rsOptBubbles(n, emoji) {
  if (n <= 6) return emoji.repeat(n);
  return `${emoji.repeat(6)}<span class="rs-badge">+${n - 6}</span>`;
}

// ── Opsætningsskærm ───────────────────────────────────────────────────────────
function renderRegnespil() {
  const el = document.getElementById('view-app-regnespil');
  if (!el) return;
  rs.phase = 'setup';

  // Børn fra Aula (CHILDREN er global) — fallback til manuel tekstinput
  const hasChildren = typeof CHILDREN !== 'undefined' && CHILDREN.length > 0;
  const childSection = hasChildren
    ? `<div class="rs-setup-section">
        <div class="rs-setup-label">Hvem spiller?</div>
        <div class="rs-child-row">
          ${CHILDREN.map((c, i) => {
            const active = rs.childName === c.name;
            const photo  = (c._photoUrl || c.photoUrl) ? aulaImg(c._photoUrl || c.photoUrl) : '';
            return `<button class="rs-child-btn ${active ? 'rs-child-active' : ''}"
              onclick="rsSelectChild(${i})">
              ${photo ? `<img class="rs-child-img" src="${photo}" alt="" onerror="this.style.display='none';this.nextElementSibling.style.display='flex'">` : ''}
              <div class="rs-child-initials" style="${photo ? 'display:none' : ''}">${c.name.charAt(0)}</div>
              <span class="rs-child-name">${c.name}</span>
            </button>`;
          }).join('')}
        </div>
      </div>`
    : `<div class="rs-setup-section">
        <div class="rs-setup-label">Hvem spiller?</div>
        <input class="rs-name-input" type="text" placeholder="Skriv navn…"
          value="${rs.childName}"
          oninput="rs.childName=this.value.trim();rs.childPhoto=''">
      </div>`;

  el.innerHTML = `
    <div class="rs-shell rs-setup-shell">
      <div class="rs-topbar">
        <button class="family-back-btn" onclick="familyAppBack('family-kids')" style="padding:0;margin:0">← Tilbage</button>
        <span class="rs-setup-title">🎮 Regnespil</span>
      </div>
      <div class="rs-setup-body">

        ${childSection}

        <div class="rs-setup-section">
          <div class="rs-setup-label">Vælg sværhedsgrad</div>
          <div class="rs-level-grid">
            ${RS_LEVELS.map(lv => `
              <button class="rs-level-btn ${rs.level === lv.id ? 'rs-level-active' : ''}"
                data-level="${lv.id}" style="--lv-color:${lv.color}"
                onclick="rsSelectLevel('${lv.id}')">
                <span class="rs-level-icon">${lv.icon}</span>
                <span class="rs-level-name">${lv.label}</span>
                <span class="rs-level-desc">${lv.desc}</span>
              </button>`).join('')}
          </div>
        </div>

        <div class="rs-setup-section">
          <div class="rs-setup-label">Vælg regneart <span class="rs-setup-hint">(kan vælge flere)</span></div>
          <div class="rs-ops-grid">
            ${RS_OPS.map(op => `
              <button class="rs-op-btn ${rs.ops.includes(op.id) ? 'rs-op-active' : ''}"
                data-op="${op.id}" onclick="rsToggleOp('${op.id}')">
                <span class="rs-op-icon">${op.icon}</span>
                <span class="rs-op-label">${op.label}</span>
              </button>`).join('')}
          </div>
        </div>

        <button class="rs-start-btn" onclick="rsStartGame()">Spil nu! 🎮</button>
      </div>
    </div>`;
}

function rsSelectChild(idx) {
  const c = CHILDREN[idx];
  if (!c) return;
  rs.childName  = c.name;
  rs.childPhoto = (c._photoUrl || c.photoUrl) ? aulaImg(c._photoUrl || c.photoUrl) : '';
  document.querySelectorAll('.rs-child-btn').forEach((b, i) =>
    b.classList.toggle('rs-child-active', i === idx));
}

function rsSelectLevel(id) {
  rs.level = id;
  document.querySelectorAll('.rs-level-btn').forEach(b => b.classList.toggle('rs-level-active', b.dataset.level === id));
}

function rsToggleOp(id) {
  if (rs.ops.includes(id)) {
    if (rs.ops.length === 1) return;
    rs.ops = rs.ops.filter(o => o !== id);
  } else {
    rs.ops.push(id);
  }
  document.querySelectorAll('.rs-op-btn').forEach(b => b.classList.toggle('rs-op-active', rs.ops.includes(b.dataset.op)));
}

// ── Spilskærm ─────────────────────────────────────────────────────────────────
function rsStartGame() {
  rs.phase = 'play';
  rs.score = 0; rs.streak = 0; rs.total = 0;
  const el = document.getElementById('view-app-regnespil');
  if (!el) return;
  const lv = RS_LEVELS.find(l => l.id === rs.level);

  const playerBadge = rs.childName
    ? `<div class="rs-player-badge">
        ${rs.childPhoto
          ? `<img class="rs-player-img" src="${rs.childPhoto}" alt="${rs.childName}">`
          : `<div class="rs-player-initials">${rs.childName.charAt(0)}</div>`}
        <span class="rs-player-name">${rs.childName}</span>
      </div>`
    : '';

  el.innerHTML = `
    <div class="rs-shell">
      <div class="rs-topbar">
        <button class="family-back-btn" onclick="renderRegnespil()" style="padding:0;margin:0">← Indstillinger</button>
        <div class="rs-score-row">
          ${playerBadge}
          <span class="rs-level-chip" style="background:${lv.color}22;color:${lv.color};border-color:${lv.color}55">${lv.icon} ${lv.label}</span>
          <span id="rs-stars"></span>
          <span class="rs-score-label">Point: <strong id="rs-score">0</strong></span>
        </div>
      </div>
      <div class="rs-stage" id="rs-stage">
        <div class="rs-equation" id="rs-equation"></div>
        <div class="rs-options" id="rs-options"></div>
      </div>
    </div>
    <div class="rs-fb-overlay" id="rs-fb-overlay" onclick="rsFbOverlayClick(event)" style="display:none">
      <div class="rs-fb-modal" id="rs-fb-modal">
        <div class="rs-fb-msg" id="rs-fb-msg"></div>
        <button class="rs-fb-next" onclick="rsDismissFeedback()">Næste spørgsmål →</button>
      </div>
    </div>`;

  rsNewRound();
}

function rsNewRound() {
  rs.answered = false;
  const lv = RS_LEVELS.find(l => l.id === rs.level);
  rs.op    = rs.ops[Math.floor(Math.random() * rs.ops.length)];
  rs.emoji = RS_EMOJIS[Math.floor(Math.random() * RS_EMOJIS.length)];

  rsGenerateNumbers(lv);

  // Forkerte svar — tæt på svaret
  const spread = lv.maxAnswer <= 9 ? 2 : lv.maxAnswer <= 20 ? 3 : 5;
  const wrong = new Set();
  let attempts = 0;
  while (wrong.size < 2 && attempts < 200) {
    attempts++;
    const delta = (Math.floor(Math.random() * spread) + 1) * (Math.random() < 0.5 ? 1 : -1);
    const w = rs.answer + delta;
    if (w >= 0 && w !== rs.answer && Number.isInteger(w)) wrong.add(w);
  }
  rs.options = shuffle([rs.answer, ...wrong]);
  rsRenderRound();
}

function rsGenerateNumbers(lv) {
  let a, b, answer, tries = 0;
  do {
    tries++;
    if (rs.op === 'plus') {
      a = 1 + Math.floor(Math.random() * lv.maxN);
      b = 1 + Math.floor(Math.random() * lv.maxN);
      answer = a + b;
    } else if (rs.op === 'minus') {
      a = 2 + Math.floor(Math.random() * lv.maxN);
      b = 1 + Math.floor(Math.random() * (a - 1));
      answer = a - b;
    } else if (rs.op === 'times') {
      const mf = lv.maxAnswer <= 9 ? 3 : lv.maxAnswer <= 20 ? 5 : lv.maxAnswer <= 50 ? 9 : 12;
      a = 2 + Math.floor(Math.random() * (mf - 1));
      b = 2 + Math.floor(Math.random() * (mf - 1));
      answer = a * b;
    } else {
      const mf = lv.maxAnswer <= 9 ? 3 : lv.maxAnswer <= 20 ? 5 : lv.maxAnswer <= 50 ? 9 : 12;
      b = 2 + Math.floor(Math.random() * (mf - 1));
      answer = 1 + Math.floor(Math.random() * (mf - 1));
      a = b * answer;
    }
  } while (answer > lv.maxAnswer && tries < 100);
  rs.a = a; rs.b = b; rs.answer = answer;
}

function rsRenderRound() {
  const eq  = document.getElementById('rs-equation');
  const opts = document.getElementById('rs-options');
  if (!eq || !opts) return;

  const em  = rs.emoji;
  const op  = RS_OPS.find(o => o.id === rs.op);
  const lv  = RS_LEVELS.find(l => l.id === rs.level);
  const showBubbles = lv.maxAnswer <= 20;

  eq.innerHTML = `
    <div class="rs-group">
      ${showBubbles ? `<div class="rs-bubbles">${rsBubbles(rs.a, em)}</div>` : ''}
      <div class="rs-num">${rs.a}</div>
    </div>
    <div class="rs-plus">${op.sym}</div>
    <div class="rs-group">
      ${showBubbles ? `<div class="rs-bubbles">${rsBubbles(rs.b, em)}</div>` : ''}
      <div class="rs-num">${rs.b}</div>
    </div>
    <div class="rs-equals">=</div>
    <div class="rs-dropzone" id="rs-dropzone"><span class="rs-dz-hint">?</span></div>`;

  opts.innerHTML = rs.options.map(v => `
    <div class="rs-option" data-val="${v}" id="rs-opt-${v}">
      ${showBubbles ? `<div class="rs-opt-bubbles">${rsOptBubbles(v, em)}</div>` : ''}
      <div class="rs-opt-num">${v}</div>
    </div>`).join('');

  rsUpdateStars();
  rsBindDrag();
}

function rsUpdateStars() {
  const el = document.getElementById('rs-stars');
  if (!el) return;
  const s = Math.min(rs.streak, 5);
  el.innerHTML = '⭐'.repeat(s) + '☆'.repeat(5 - s);
}

// ── Drag & Drop ───────────────────────────────────────────────────────────────
function rsBindDrag() {
  document.querySelectorAll('.rs-option').forEach(opt =>
    opt.addEventListener('pointerdown', rsPointerDown, { passive: false }));
}

let rsGhost = null;

function rsPointerDown(e) {
  if (rs.answered) return;
  e.preventDefault();
  const opt  = e.currentTarget;
  const val  = parseInt(opt.dataset.val);
  const rect = opt.getBoundingClientRect();
  const lv   = RS_LEVELS.find(l => l.id === rs.level);
  const showBubbles = lv.maxAnswer <= 20;

  rsGhost = document.createElement('div');
  rsGhost.className = 'rs-ghost';
  rsGhost.innerHTML = `${showBubbles ? `<div class="rs-opt-bubbles">${rsOptBubbles(val, rs.emoji)}</div>` : ''}<div class="rs-opt-num">${val}</div>`;
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
  rsGhost.style.left = (rs.dragging.origLeft + e.clientX - rs.dragging.startX) + 'px';
  rsGhost.style.top  = (rs.dragging.origTop  + e.clientY - rs.dragging.startY) + 'px';
  const dz = document.getElementById('rs-dropzone');
  if (dz) {
    const dzR = dz.getBoundingClientRect(), gR = rsGhost.getBoundingClientRect();
    dz.classList.toggle('rs-dz-hover',
      gR.left < dzR.right && gR.right > dzR.left && gR.top < dzR.bottom && gR.bottom > dzR.top);
  }
}

function rsPointerUp(e) {
  document.removeEventListener('pointermove', rsPointerMove);
  document.removeEventListener('pointerup',   rsPointerUp);
  if (!rsGhost || !rs.dragging) return;
  const dz = document.getElementById('rs-dropzone');
  const dzR = dz?.getBoundingClientRect();
  const gR  = rsGhost.getBoundingClientRect();
  const dropped = dz && dzR &&
    gR.left < dzR.right && gR.right > dzR.left && gR.top < dzR.bottom && gR.bottom > dzR.top;
  rsGhost.remove(); rsGhost = null;
  rs.dragging.opt.classList.remove('rs-dragging-src');
  if (dropped) rsCheckAnswer(rs.dragging.val);
  rs.dragging = null;
}

// ── Svar ──────────────────────────────────────────────────────────────────────
function rsCheckAnswer(val) {
  if (rs.answered) return;
  rs.answered = true; rs.total++;
  const correct = val === rs.answer;
  const dz = document.getElementById('rs-dropzone');
  const n  = rs.childName;

  if (correct) {
    rs.score++; rs.streak++;
    if (dz) { dz.innerHTML = `<span class="rs-dz-answer rs-dz-correct">${val}</span>`; dz.classList.add('rs-dz-filled-correct'); }
    rsBurst(dz);
    const msgs = n ? [
      `Flot, ${n}! 🌟`,
      `Godt, ${n}! 👏`,
      `Genial, ${n}! 🚀`,
      `Perfekt, ${n}! ⭐`,
      `Sejt, ${n}! 🎉`,
      `Dygtig, ${n}! 🏆`,
      `Skarp, ${n}! 🎊`,
      `Brilliant, ${n}! 🥳`,
    ] : ['Flot! 🌟','Godt! 👏','Perfekt! ⭐','Sejt! 🎉','Dygtig! 🏆'];
    rsShowFeedback(msgs[Math.floor(Math.random() * msgs.length)], true);
  } else {
    rs.streak = 0;
    if (dz) { dz.innerHTML = `<span class="rs-dz-answer rs-dz-wrong">${rs.answer}</span>`; dz.classList.add('rs-dz-filled-wrong'); }
    const wo = document.getElementById(`rs-opt-${val}`);
    if (wo) { wo.classList.add('rs-shake'); setTimeout(() => wo.classList.remove('rs-shake'), 500); }
    rsShowFeedback(n
      ? `Prøv igen, ${n} — svaret er ${rs.answer} 💪`
      : `Ikke helt — svaret er ${rs.answer} 💪`, false);
  }
  document.getElementById('rs-score').textContent = rs.score;
  rsUpdateStars();
}

function rsShowFeedback(msg, correct) {
  const overlay = document.getElementById('rs-fb-overlay');
  const modal   = document.getElementById('rs-fb-modal');
  const msgEl   = document.getElementById('rs-fb-msg');
  if (!overlay || !msgEl) return;
  msgEl.innerHTML = msg;
  overlay.style.display = 'flex';
  modal.className = 'rs-fb-modal ' + (correct ? 'rs-fb-correct' : 'rs-fb-wrong');
  // lille bounce-animation
  modal.classList.remove('rs-fb-bounce');
  void modal.offsetWidth;
  modal.classList.add('rs-fb-bounce');
}

function rsDismissFeedback() {
  const overlay = document.getElementById('rs-fb-overlay');
  if (overlay) overlay.style.display = 'none';
  rsNewRound();
}

function rsFbOverlayClick(e) {
  // Luk kun ved klik på baggrunden (ikke på selve modalen)
  if (e.target === document.getElementById('rs-fb-overlay')) rsDismissFeedback();
}

// ── Konfetti ──────────────────────────────────────────────────────────────────
function rsBurst(anchor) {
  const stage = document.getElementById('rs-stage');
  if (!stage || !anchor) return;
  const rect = anchor.getBoundingClientRect(), stageR = stage.getBoundingClientRect();
  const cx = rect.left + rect.width/2 - stageR.left, cy = rect.top + rect.height/2 - stageR.top;
  const colors = ['#FFD700','#FF6B6B','#4ECDC4','#45B7D1','#96CEB4','#FFEAA7'];
  for (let i = 0; i < 18; i++) {
    const p = document.createElement('div');
    p.className = 'rs-particle';
    p.style.cssText = `left:${cx}px;top:${cy}px;background:${colors[i%6]};--dx:${(Math.random()-.5)*200}px;--dy:${-(40+Math.random()*160)}px;--rot:${Math.random()*720}deg;`;
    stage.appendChild(p);
    setTimeout(() => p.remove(), 900);
  }
}

function shuffle(arr) {
  for (let i = arr.length-1; i > 0; i--) { const j = Math.floor(Math.random()*(i+1)); [arr[i],arr[j]]=[arr[j],arr[i]]; }
  return arr;
}

document.addEventListener('DOMContentLoaded', () => { updateFamilyNav(); });
