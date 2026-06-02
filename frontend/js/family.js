// family.js — Familie-sider (Børn & Voksne) + apps

const FAMILY_APPS = {
  kids: [
    { id: 'regnespil', label: 'Regnespil',    icon: '➕', comingSoon: false },
    { id: 'huske',     label: 'Huskespillet', icon: '🧠', comingSoon: false },
    { id: 'tal',       label: 'Tal',          icon: '🔢', comingSoon: false },
    { id: 'spell',     label: 'Stavespil',    icon: '🔤', comingSoon: true  },
    { id: 'wordgame',  label: 'Ordleg',       icon: '🃏', comingSoon: true  },
    { id: 'drawing',   label: 'Tegnesjov',    icon: '🎨', comingSoon: true  },
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
  const gridEl  = document.getElementById('family-' + type + '-grid');
  if (!gridEl) return;
  const apps = FAMILY_APPS[type].filter(a => enabled.includes(a.id));
  if (!apps.length) {
    gridEl.innerHTML = '<p style="color:#aaa;font-size:0.9rem;padding:20px 0">Ingen apps aktiveret.<br>Gå til ⚙️ Indstillinger → Familie Apps.</p>';
    return;
  }
  gridEl.innerHTML = apps.map(app => app.comingSoon
    ? '<div class="family-app-tile coming-soon"><div class="family-app-icon">' + app.icon + '</div><div class="family-app-label">' + app.label + '</div><div class="family-app-soon">Kommer snart</div></div>'
    : '<div class="family-app-tile" onclick="openFamilyApp(\'' + app.id + '\')"><div class="family-app-icon">' + app.icon + '</div><div class="family-app-label">' + app.label + '</div></div>'
  ).join('');
}

function openFamilyApp(id)         { switchView('app-' + id); }
function familyAppBack(parentView) { switchView(parentView); }

// ══════════════════════════════════════════════════════════════════════════════
// APP: TAL
// ══════════════════════════════════════════════════════════════════════════════
let talCount = 0;

function renderTalApp() {
  const el = document.getElementById('view-app-tal');
  if (!el) return;
  el.innerHTML = '<div class="family-app-page">'
    + '<button class="family-back-btn" onclick="familyAppBack(\'family-kids\')">← Tilbage</button>'
    + '<div class="tal-container">'
    + '<div class="tal-number" id="tal-number">' + talCount + '</div>'
    + '<div class="tal-controls">'
    + '<button class="tal-btn tal-minus" onclick="talChange(-1)">−</button>'
    + '<button class="tal-btn tal-reset" onclick="talReset()">↺</button>'
    + '<button class="tal-btn tal-plus"  onclick="talChange(1)">+</button>'
    + '</div><div class="tal-hint">Tæl hvad som helst!</div></div></div>';
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
  el.innerHTML = '<div class="family-app-page">'
    + '<button class="family-back-btn" onclick="familyAppBack(\'family-adults\')">← Tilbage</button>'
    + '<div class="nyhed-header"><span class="nyhed-logo">DR</span><span class="nyhed-title">Nyheder</span>'
    + '<button class="nyhed-refresh" onclick="loadNyheder(true)">↻</button></div>'
    + '<div id="nyhed-list" class="nyhed-list"><div class="nyhed-loading">Henter nyheder…</div></div></div>';
  await loadNyheder(false);
}

async function loadNyheder(force) {
  const listEl = document.getElementById('nyhed-list');
  if (!listEl) return;
  if (!force && nyhedItems) { renderNyhedList(nyhedItems); return; }
  listEl.innerHTML = '<div class="nyhed-loading">Henter nyheder…</div>';
  try {
    const FEED = 'https://www.dr.dk/nyheder/service/feeds/allenyheder';
    const res  = await fetch('https://api.allorigins.win/get?url=' + encodeURIComponent(FEED), { signal: AbortSignal.timeout(8000) });
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
  listEl.innerHTML = items.map((it, i) =>
    '<div class="nyhed-item" onclick="openNyhed(' + i + ')">'
    + (it.img ? '<img class="nyhed-thumb" src="' + it.img + '" alt="" loading="lazy" onerror="this.style.display=\'none\'">' : '')
    + '<div class="nyhed-body"><div class="nyhed-item-title">' + it.title + '</div>'
    + '<div class="nyhed-item-date">' + formatNyhedDate(it.date) + '</div></div></div>'
  ).join('');
}
function openNyhed(idx) { if (nyhedItems?.[idx]) window.open(nyhedItems[idx].link, '_blank'); }
function formatNyhedDate(dateStr) {
  try {
    const diff = Math.floor((new Date() - new Date(dateStr)) / 60000);
    if (diff < 1) return 'Lige nu';
    if (diff < 60) return diff + ' min. siden';
    if (diff < 1440) return Math.floor(diff/60) + ' timer siden';
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
  level: 'seed', ops: ['plus'], phase: 'setup',
  childName: '', childPhoto: '',
};

function rsBubbles(n, emoji) {
  if (n <= 9) return emoji.repeat(n);
  return emoji + '<span class="rs-badge">×' + n + '</span>';
}
function rsOptBubbles(n, emoji) {
  if (n <= 9) return emoji.repeat(n);
  return emoji + '<span class="rs-badge">×' + n + '</span>';
}

function renderRegnespil() {
  const el = document.getElementById('view-app-regnespil');
  if (!el) return;
  rs.phase = 'setup';
  const hasChildren = typeof CHILDREN !== 'undefined' && CHILDREN.length > 0;

  const childSection = hasChildren
    ? '<div class="rs-setup-section"><div class="rs-setup-label">Hvem spiller?</div><div class="rs-child-row">'
      + CHILDREN.map((c, i) => {
          const active = rs.childName === c.name;
          const photo  = (c._photoUrl || c.photoUrl) ? aulaImg(c._photoUrl || c.photoUrl) : '';
          return '<button class="rs-child-btn ' + (active ? 'rs-child-active' : '') + '" onclick="rsSelectChild(' + i + ')">'
            + (photo ? '<img class="rs-child-img" src="' + photo + '" alt="" onerror="this.style.display=\'none\';this.nextElementSibling.style.display=\'flex\'">' : '')
            + '<div class="rs-child-initials" style="' + (photo ? 'display:none' : '') + '">' + c.name.charAt(0) + '</div>'
            + '<span class="rs-child-name">' + c.name + '</span></button>';
        }).join('')
      + '</div></div>'
    : '<div class="rs-setup-section"><div class="rs-setup-label">Hvem spiller?</div>'
      + '<input class="rs-name-input" type="text" placeholder="Skriv navn…" value="' + rs.childName + '" oninput="rs.childName=this.value.trim();rs.childPhoto=\'\'"></div>';

  el.innerHTML = '<div class="rs-shell rs-setup-shell">'
    + '<div class="rs-topbar"><button class="family-back-btn" onclick="familyAppBack(\'family-kids\')" style="padding:0;margin:0">← Tilbage</button>'
    + '<span class="rs-setup-title">🎮 Regnespil</span></div>'
    + '<div class="rs-setup-body">' + childSection
    + '<div class="rs-setup-section"><div class="rs-setup-label">Vælg sværhedsgrad</div><div class="rs-level-grid">'
    + RS_LEVELS.map(lv => '<button class="rs-level-btn ' + (rs.level === lv.id ? 'rs-level-active' : '') + '" data-level="' + lv.id + '" style="--lv-color:' + lv.color + '" onclick="rsSelectLevel(\'' + lv.id + '\')">'
        + '<span class="rs-level-icon">' + lv.icon + '</span><span class="rs-level-name">' + lv.label + '</span><span class="rs-level-desc">' + lv.desc + '</span></button>').join('')
    + '</div></div>'
    + '<div class="rs-setup-section"><div class="rs-setup-label">Vælg regneart <span class="rs-setup-hint">(kan vælge flere)</span></div><div class="rs-ops-grid">'
    + RS_OPS.map(op => '<button class="rs-op-btn ' + (rs.ops.includes(op.id) ? 'rs-op-active' : '') + '" data-op="' + op.id + '" onclick="rsToggleOp(\'' + op.id + '\')">'
        + '<span class="rs-op-icon">' + op.icon + '</span><span class="rs-op-label">' + op.label + '</span></button>').join('')
    + '</div></div>'
    + '<button class="rs-start-btn" onclick="rsStartGame()">Spil nu! 🎮</button>'
    + '</div></div>';
}

function rsSelectChild(idx) {
  const c = CHILDREN[idx]; if (!c) return;
  rs.childName  = c.name;
  rs.childPhoto = (c._photoUrl || c.photoUrl) ? aulaImg(c._photoUrl || c.photoUrl) : '';
  document.querySelectorAll('.rs-child-btn').forEach((b, i) => b.classList.toggle('rs-child-active', i === idx));
}
function rsSelectLevel(id) {
  rs.level = id;
  document.querySelectorAll('.rs-level-btn').forEach(b => b.classList.toggle('rs-level-active', b.dataset.level === id));
}
function rsToggleOp(id) {
  if (rs.ops.includes(id)) { if (rs.ops.length === 1) return; rs.ops = rs.ops.filter(o => o !== id); }
  else rs.ops.push(id);
  document.querySelectorAll('.rs-op-btn').forEach(b => b.classList.toggle('rs-op-active', rs.ops.includes(b.dataset.op)));
}

function rsStartGame() {
  rs.phase = 'play'; rs.score = 0; rs.streak = 0; rs.total = 0;
  const el = document.getElementById('view-app-regnespil'); if (!el) return;
  const lv = RS_LEVELS.find(l => l.id === rs.level);
  const playerBadge = rs.childName
    ? '<div class="rs-player-badge">'
      + (rs.childPhoto ? '<img class="rs-player-img" src="' + rs.childPhoto + '" alt="">' : '<div class="rs-player-initials">' + rs.childName.charAt(0) + '</div>')
      + '<span class="rs-player-name">' + rs.childName + '</span></div>'
    : '';
  el.innerHTML = '<div class="rs-shell">'
    + '<div class="rs-topbar"><button class="family-back-btn" onclick="renderRegnespil()" style="padding:0;margin:0">← Indstillinger</button>'
    + '<div class="rs-score-row">' + playerBadge
    + '<span class="rs-level-chip" style="background:' + lv.color + '22;color:' + lv.color + ';border-color:' + lv.color + '55">' + lv.icon + ' ' + lv.label + '</span>'
    + '<span id="rs-stars"></span><span class="rs-score-label">Point: <strong id="rs-score">0</strong></span></div></div>'
    + '<div class="rs-stage" id="rs-stage"><div class="rs-equation" id="rs-equation"></div><div class="rs-options" id="rs-options"></div></div></div>'
    + '<div class="rs-fb-overlay" id="rs-fb-overlay" onclick="rsFbOverlayClick(event)" style="display:none">'
    + '<div class="rs-fb-modal" id="rs-fb-modal"><div class="rs-fb-msg" id="rs-fb-msg"></div>'
    + '<button class="rs-fb-next" onclick="rsDismissFeedback()">Næste spørgsmål →</button></div></div>';
  rsNewRound();
}

function rsNewRound() {
  rs.answered = false;
  const lv = RS_LEVELS.find(l => l.id === rs.level);
  rs.op    = rs.ops[Math.floor(Math.random() * rs.ops.length)];
  rs.emoji = RS_EMOJIS[Math.floor(Math.random() * RS_EMOJIS.length)];
  rsGenerateNumbers(lv);
  const spread = lv.maxAnswer <= 9 ? 2 : lv.maxAnswer <= 20 ? 3 : 5;
  const wrong = new Set(); let attempts = 0;
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
    if (rs.op === 'plus') { a = 1+Math.floor(Math.random()*lv.maxN); b = 1+Math.floor(Math.random()*lv.maxN); answer = a+b; }
    else if (rs.op === 'minus') { a = 2+Math.floor(Math.random()*lv.maxN); b = 1+Math.floor(Math.random()*(a-1)); answer = a-b; }
    else if (rs.op === 'times') { const mf = lv.maxAnswer<=9?3:lv.maxAnswer<=20?5:lv.maxAnswer<=50?9:12; a=2+Math.floor(Math.random()*(mf-1)); b=2+Math.floor(Math.random()*(mf-1)); answer=a*b; }
    else { const mf = lv.maxAnswer<=9?3:lv.maxAnswer<=20?5:lv.maxAnswer<=50?9:12; b=2+Math.floor(Math.random()*(mf-1)); answer=1+Math.floor(Math.random()*(mf-1)); a=b*answer; }
  } while (answer > lv.maxAnswer && tries < 100);
  rs.a = a; rs.b = b; rs.answer = answer;
}

function rsRenderRound() {
  const eq = document.getElementById('rs-equation'), opts = document.getElementById('rs-options');
  if (!eq || !opts) return;
  const em = rs.emoji, op = RS_OPS.find(o => o.id === rs.op), lv = RS_LEVELS.find(l => l.id === rs.level);
  const showBubbles = lv.maxAnswer <= 20;
  eq.innerHTML = '<div class="rs-group">' + (showBubbles ? '<div class="rs-bubbles">' + rsBubbles(rs.a,em) + '</div>' : '') + '<div class="rs-num">' + rs.a + '</div></div>'
    + '<div class="rs-plus">' + op.sym + '</div>'
    + '<div class="rs-group">' + (showBubbles ? '<div class="rs-bubbles">' + rsBubbles(rs.b,em) + '</div>' : '') + '<div class="rs-num">' + rs.b + '</div></div>'
    + '<div class="rs-equals">=</div><div class="rs-dropzone" id="rs-dropzone"><span class="rs-dz-hint">?</span></div>';
  opts.innerHTML = rs.options.map(v => {
    const bh = showBubbles ? rsOptBubbles(v, em) : '';
    return '<div class="rs-option" data-val="' + v + '" id="rs-opt-' + v + '">'
      + (bh ? '<div class="rs-opt-bubbles">' + bh + '</div>' : '')
      + '<div class="rs-opt-num">' + v + '</div></div>';
  }).join('');
  rsUpdateStars(); rsBindDrag();
}

function rsUpdateStars() {
  const el = document.getElementById('rs-stars'); if (!el) return;
  const s = Math.min(rs.streak, 5);
  el.innerHTML = '⭐'.repeat(s) + '☆'.repeat(5 - s);
}

function rsBindDrag() {
  document.querySelectorAll('.rs-option').forEach(opt => opt.addEventListener('pointerdown', rsPointerDown, { passive: false }));
}
let rsGhost = null;
function rsPointerDown(e) {
  if (rs.answered) return; e.preventDefault();
  const opt = e.currentTarget, val = parseInt(opt.dataset.val), rect = opt.getBoundingClientRect();
  const lv = RS_LEVELS.find(l => l.id === rs.level), showBubbles = lv.maxAnswer <= 20;
  rsGhost = document.createElement('div'); rsGhost.className = 'rs-ghost';
  const gb = showBubbles ? rsOptBubbles(val, rs.emoji) : '';
  rsGhost.innerHTML = (gb ? '<div class="rs-opt-bubbles">' + gb + '</div>' : '') + '<div class="rs-opt-num">' + val + '</div>';
  rsGhost.style.cssText = 'left:' + rect.left + 'px;top:' + rect.top + 'px;width:' + rect.width + 'px;';
  document.body.appendChild(rsGhost);
  rs.dragging = { val, opt, startX: e.clientX, startY: e.clientY, origTop: rect.top, origLeft: rect.left };
  opt.classList.add('rs-dragging-src');
  document.addEventListener('pointermove', rsPointerMove, { passive: false });
  document.addEventListener('pointerup',   rsPointerUp);
}
function rsPointerMove(e) {
  if (!rsGhost || !rs.dragging) return; e.preventDefault();
  rsGhost.style.left = (rs.dragging.origLeft + e.clientX - rs.dragging.startX) + 'px';
  rsGhost.style.top  = (rs.dragging.origTop  + e.clientY - rs.dragging.startY) + 'px';
  const dz = document.getElementById('rs-dropzone');
  if (dz) { const dzR = dz.getBoundingClientRect(), gR = rsGhost.getBoundingClientRect();
    dz.classList.toggle('rs-dz-hover', gR.left<dzR.right && gR.right>dzR.left && gR.top<dzR.bottom && gR.bottom>dzR.top); }
}
function rsPointerUp(e) {
  document.removeEventListener('pointermove', rsPointerMove);
  document.removeEventListener('pointerup',   rsPointerUp);
  if (!rsGhost || !rs.dragging) return;
  const dz = document.getElementById('rs-dropzone'), dzR = dz?.getBoundingClientRect(), gR = rsGhost.getBoundingClientRect();
  const dropped = dz && dzR && gR.left<dzR.right && gR.right>dzR.left && gR.top<dzR.bottom && gR.bottom>dzR.top;
  rsGhost.remove(); rsGhost = null;
  rs.dragging.opt.classList.remove('rs-dragging-src');
  if (dropped) rsCheckAnswer(rs.dragging.val);
  rs.dragging = null;
}

function rsCheckAnswer(val) {
  if (rs.answered) return;
  rs.answered = true; rs.total++;
  const correct = val === rs.answer, dz = document.getElementById('rs-dropzone'), n = rs.childName;
  if (correct) {
    rs.score++; rs.streak++;
    if (dz) { dz.innerHTML = '<span class="rs-dz-answer rs-dz-correct">' + val + '</span>'; dz.classList.add('rs-dz-filled-correct'); }
    rsBurst(dz);
    const msgs = n ? ['Flot, '+n+'! 🌟','Godt, '+n+'! 👏','Genial, '+n+'! 🚀','Perfekt, '+n+'! ⭐','Sejt, '+n+'! 🎉','Dygtig, '+n+'! 🏆','Skarp, '+n+'! 🎊','Brilliant, '+n+'! 🥳']
                   : ['Flot! 🌟','Godt! 👏','Perfekt! ⭐','Sejt! 🎉','Dygtig! 🏆'];
    rsShowFeedback(msgs[Math.floor(Math.random()*msgs.length)], true);
  } else {
    rs.streak = 0;
    if (dz) { dz.innerHTML = '<span class="rs-dz-answer rs-dz-wrong">' + rs.answer + '</span>'; dz.classList.add('rs-dz-filled-wrong'); }
    const wo = document.getElementById('rs-opt-' + val);
    if (wo) { wo.classList.add('rs-shake'); setTimeout(() => wo.classList.remove('rs-shake'), 500); }
    rsShowFeedback(n ? 'Prøv igen, ' + n + ' — svaret er ' + rs.answer + ' 💪' : 'Ikke helt — svaret er ' + rs.answer + ' 💪', false);
  }
  document.getElementById('rs-score').textContent = rs.score;
  rsUpdateStars();
}

function rsShowFeedback(msg, correct) {
  const overlay = document.getElementById('rs-fb-overlay'), modal = document.getElementById('rs-fb-modal'), msgEl = document.getElementById('rs-fb-msg');
  if (!overlay || !msgEl) return;
  msgEl.innerHTML = msg; overlay.style.display = 'flex';
  modal.className = 'rs-fb-modal ' + (correct ? 'rs-fb-correct' : 'rs-fb-wrong');
  modal.classList.remove('rs-fb-bounce'); void modal.offsetWidth; modal.classList.add('rs-fb-bounce');
}
function rsDismissFeedback() { const o = document.getElementById('rs-fb-overlay'); if (o) o.style.display = 'none'; rsNewRound(); }
function rsFbOverlayClick(e) { if (e.target === document.getElementById('rs-fb-overlay')) rsDismissFeedback(); }

function rsBurst(anchor) {
  const stage = document.getElementById('rs-stage'); if (!stage || !anchor) return;
  const rect = anchor.getBoundingClientRect(), stageR = stage.getBoundingClientRect();
  const cx = rect.left+rect.width/2-stageR.left, cy = rect.top+rect.height/2-stageR.top;
  const colors = ['#FFD700','#FF6B6B','#4ECDC4','#45B7D1','#96CEB4','#FFEAA7'];
  for (let i = 0; i < 18; i++) {
    const p = document.createElement('div'); p.className = 'rs-particle';
    p.style.cssText = 'left:'+cx+'px;top:'+cy+'px;background:'+colors[i%6]+';--dx:'+(Math.random()-.5)*200+'px;--dy:'+-(40+Math.random()*160)+'px;--rot:'+Math.random()*720+'deg;';
    stage.appendChild(p); setTimeout(() => p.remove(), 900);
  }
}

// ══════════════════════════════════════════════════════════════════════════════
// APP: HUSKESPILLET
// ══════════════════════════════════════════════════════════════════════════════

const MEM_CATEGORIES = [
  { id: 'animals',   label: 'Dyr',       icon: '🦁', words: ['lion','tiger','elephant','giraffe','zebra','dolphin','wolf','bear','gorilla','cheetah','penguin','koala','panda','flamingo','owl','kangaroo','jaguar','leopard','rhinoceros','hippopotamus'] },
  { id: 'space',     label: 'Rummet',    icon: '🪐', words: ['planet','galaxy','astronaut','rocket','nebula','comet','saturn','moon','star','telescope','asteroid','aurora','spaceship','mars','jupiter','cosmos','meteor','black hole','space station','solar system'] },
  { id: 'ocean',     label: 'Havet',     icon: '🌊', words: ['shark','whale','octopus','coral reef','seahorse','jellyfish','clownfish','sea turtle','lobster','seal','starfish','swordfish','walrus','dolphin','crab','orca','ray','narwhal','pufferfish','moray eel'] },
  { id: 'nature',    label: 'Natur',     icon: '🌿', words: ['waterfall','mountain','forest','volcano','canyon','glacier','sunset','rainbow','flower','mushroom','butterfly','dragonfly','fern','oak tree','cherry blossom','autumn leaves','ice cave','northern lights','desert','coral'] },
  { id: 'food',      label: 'Mad',       icon: '🍕', words: ['pizza','sushi','taco','burger','pasta','cake','donut','ice cream','strawberry','watermelon','avocado','pineapple','ramen','pancakes','croissant','chocolate','mango','lemon','pomegranate','cookie'] },
  { id: 'transport', label: 'Transport', icon: '🚂', words: ['steam train','sailboat','helicopter','motorcycle','submarine','hot air balloon','bicycle','racing car','fire truck','jet plane','vintage car','tram','speedboat','cable car','zeppelin','snowmobile','double decker bus','kayak','space shuttle','hovercraft'] },
];

const MEM_GRIDS = [
  { id: '4x4', label: '4 × 4', cols: 4, pairs: 8  },
  { id: '6x6', label: '6 × 6', cols: 6, pairs: 18 },
  { id: '8x8', label: '8 × 8', cols: 8, pairs: 32 },
];

let mem = {
  phase: 'setup', category: 'animals', grid: '4x4',
  players: [], currentPlayer: 0,
  cards: [], flipped: [], locked: false, moves: 0,
};

function renderHuskespil() {
  const el = document.getElementById('view-app-huske');
  if (!el) return;
  mem.phase = 'setup';
  const hasChildren = typeof CHILDREN !== 'undefined' && CHILDREN.length > 0;

  const playerSection = hasChildren
    ? '<div class="mem-setup-section"><div class="mem-setup-label">Hvem spiller? <span class="mem-setup-hint">(vælg 1 eller flere)</span></div><div class="mem-child-row">'
      + CHILDREN.map((c, i) => {
          const active = mem.players.some(p => p.name === c.name);
          const photo  = (c._photoUrl || c.photoUrl) ? aulaImg(c._photoUrl || c.photoUrl) : '';
          return '<button class="rs-child-btn ' + (active ? 'rs-child-active' : '') + '" onclick="memTogglePlayer(' + i + ')">'
            + (photo ? '<img class="rs-child-img" src="' + photo + '" alt="" onerror="this.style.display=\'none\';this.nextElementSibling.style.display=\'flex\'">' : '')
            + '<div class="rs-child-initials" style="' + (photo ? 'display:none' : '') + '">' + c.name.charAt(0) + '</div>'
            + '<span class="rs-child-name">' + c.name + '</span></button>';
        }).join('')
      + '</div></div>'
    : '';

  const catBtns = MEM_CATEGORIES.map(cat =>
    '<button class="mem-cat-btn ' + (mem.category === cat.id ? 'mem-cat-active' : '') + '" data-catid="' + cat.id + '" onclick="memSelectCat(\'' + cat.id + '\')">'
    + '<span class="mem-cat-icon">' + cat.icon + '</span><span class="mem-cat-label">' + cat.label + '</span></button>'
  ).join('');

  const gridBtns = MEM_GRIDS.map(g =>
    '<button class="mem-grid-btn ' + (mem.grid === g.id ? 'mem-grid-active' : '') + '" data-gridid="' + g.id + '" onclick="memSelectGrid(\'' + g.id + '\')">'
    + '<span class="mem-grid-label">' + g.label + '</span><span class="mem-grid-desc">' + g.pairs + ' par</span></button>'
  ).join('');

  el.innerHTML = '<div class="mem-shell mem-setup-shell">'
    + '<div class="mem-topbar"><button class="family-back-btn" onclick="familyAppBack(\'family-kids\')" style="padding:0;margin:0">← Tilbage</button>'
    + '<span class="mem-setup-title">🧠 Huskespillet</span></div>'
    + '<div class="mem-setup-body">' + playerSection
    + '<div class="mem-setup-section"><div class="mem-setup-label">Vælg kategori</div><div class="mem-cat-grid">' + catBtns + '</div></div>'
    + '<div class="mem-setup-section"><div class="mem-setup-label">Vælg størrelse</div><div class="mem-grid-row">' + gridBtns + '</div></div>'
    + '<button class="rs-start-btn" onclick="memStartGame()">Spil nu! 🧠</button>'
    + '</div></div>';
}

function memTogglePlayer(idx) {
  const c = CHILDREN[idx]; if (!c) return;
  const photo  = (c._photoUrl || c.photoUrl) ? aulaImg(c._photoUrl || c.photoUrl) : '';
  const exists = mem.players.findIndex(p => p.name === c.name);
  if (exists >= 0) mem.players.splice(exists, 1);
  else mem.players.push({ name: c.name, photo, score: 0 });
  document.querySelectorAll('.mem-child-row .rs-child-btn').forEach((b, i) =>
    b.classList.toggle('rs-child-active', mem.players.some(p => p.name === CHILDREN[i]?.name)));
}
function memSelectCat(id) {
  mem.category = id;
  document.querySelectorAll('.mem-cat-btn').forEach(b => b.classList.toggle('mem-cat-active', b.dataset.catid === id));
}
function memSelectGrid(id) {
  mem.grid = id;
  document.querySelectorAll('.mem-grid-btn').forEach(b => b.classList.toggle('mem-grid-active', b.dataset.gridid === id));
}

function memStartGame() {
  const gridCfg = MEM_GRIDS.find(g => g.id === mem.grid);
  const cat     = MEM_CATEGORIES.find(c => c.id === mem.category);
  mem.players.forEach(p => p.score = 0);
  if (!mem.players.length) mem.players = [{ name: '', photo: '', score: 0 }];
  mem.currentPlayer = 0; mem.moves = 0; mem.flipped = []; mem.locked = false; mem.phase = 'play';

  const words = shuffle([...cat.words]).slice(0, gridCfg.pairs);
  mem.cards = shuffle([...words, ...words].map((word, i) => ({
    id: i, word,
    img: 'https://source.unsplash.com/featured/400x400/?' + encodeURIComponent(word) + '&sig=' + i,
    flipped: false, matched: false,
  })));
  memRender();
}

function memRender() {
  const el = document.getElementById('view-app-huske'); if (!el) return;
  const gridCfg = MEM_GRIDS.find(g => g.id === mem.grid);
  const multi   = mem.players.length > 1;
  const cur     = mem.players[mem.currentPlayer];
  const catIcon = MEM_CATEGORIES.find(c => c.id === mem.category)?.icon || '❓';

  const scoreboard = multi
    ? mem.players.map((p, i) =>
        '<div class="mem-player' + (i === mem.currentPlayer ? ' mem-player-active' : '') + '">'
        + (p.photo ? '<img class="mem-player-img" src="' + p.photo + '" alt="">' : '<div class="mem-player-init">' + (p.name ? p.name.charAt(0) : '?') + '</div>')
        + '<span class="mem-player-name">' + (p.name || 'Spiller') + '</span>'
        + '<span class="mem-player-score">' + p.score + '</span></div>'
      ).join('')
    : '<div class="mem-solo-info">'
      + (cur?.photo ? '<img class="mem-player-img" src="' + cur.photo + '" alt="">' : '')
      + '<span class="mem-move-count">Træk: <strong>' + mem.moves + '</strong></span></div>';

  const cardHtml = mem.cards.map((card, idx) =>
    '<div class="mem-card' + (card.flipped||card.matched ? ' mem-flipped' : '') + (card.matched ? ' mem-matched' : '') + '"'
    + ' id="mem-card-' + idx + '" onclick="memFlip(' + idx + ')">'
    + '<div class="mem-card-inner">'
    + '<div class="mem-card-back">🧠</div>'
    + '<div class="mem-card-front"><img src="' + card.img + '" alt="' + card.word + '" loading="lazy"'
    + ' onerror="this.parentElement.innerHTML=\'<span class=mem-card-emoji>' + catIcon + '</span><span class=mem-card-word>' + card.word + '</span>\'"></div>'
    + '</div></div>'
  ).join('');

  el.innerHTML = '<div class="mem-shell" style="--mem-cols:' + gridCfg.cols + '">'
    + '<div class="mem-topbar"><button class="family-back-btn" onclick="renderHuskespil()" style="padding:0;margin:0">← Indstillinger</button>'
    + '<div class="mem-scoreboard">' + scoreboard + '</div></div>'
    + '<div class="mem-board" id="mem-board">' + cardHtml + '</div></div>';
}

function memFlip(idx) {
  if (mem.locked) return;
  const card = mem.cards[idx];
  if (!card || card.flipped || card.matched || mem.flipped.length >= 2) return;
  card.flipped = true;
  mem.flipped.push(idx);
  document.getElementById('mem-card-' + idx)?.classList.add('mem-flipped');

  if (mem.flipped.length === 2) {
    mem.locked = true; mem.moves++;
    const mc = document.querySelector('.mem-move-count strong');
    if (mc) mc.textContent = mem.moves;
    const [i1, i2] = mem.flipped;
    const match = mem.cards[i1].word === mem.cards[i2].word;
    setTimeout(() => {
      if (match) {
        mem.cards[i1].matched = mem.cards[i2].matched = true;
        document.getElementById('mem-card-'+i1)?.classList.add('mem-matched');
        document.getElementById('mem-card-'+i2)?.classList.add('mem-matched');
        if (mem.players.length) mem.players[mem.currentPlayer].score++;
        // Update score display
        document.querySelectorAll('.mem-player-score').forEach((el, i) => { if (mem.players[i]) el.textContent = mem.players[i].score; });
        mem.flipped = []; mem.locked = false;
        if (mem.cards.every(c => c.matched)) setTimeout(memShowWin, 400);
      } else {
        mem.cards[i1].flipped = mem.cards[i2].flipped = false;
        document.getElementById('mem-card-'+i1)?.classList.remove('mem-flipped');
        document.getElementById('mem-card-'+i2)?.classList.remove('mem-flipped');
        mem.flipped = [];
        if (mem.players.length > 1) {
          mem.currentPlayer = (mem.currentPlayer + 1) % mem.players.length;
          document.querySelectorAll('.mem-player').forEach((el, i) => el.classList.toggle('mem-player-active', i === mem.currentPlayer));
        }
        mem.locked = false;
      }
    }, 900);
  }
}

function memShowWin() {
  const el = document.getElementById('view-app-huske'); if (!el) return;
  const multi = mem.players.length > 1;
  let inner;
  if (multi) {
    const sorted = [...mem.players].sort((a, b) => b.score - a.score);
    const winner = sorted[0], tied = sorted.filter(p => p.score === winner.score).length > 1;
    inner = '<div class="mem-win-trophy">' + (tied ? '🤝' : '🏆') + '</div>'
      + '<div class="mem-win-title">' + (tied ? 'Uafgjort!' : (winner.name || 'Spiller') + ' vandt!') + '</div>'
      + '<div class="mem-win-scores">'
      + sorted.map((p, i) => '<div class="mem-win-row' + (i===0&&!tied ? ' mem-win-first' : '') + '">'
          + (p.photo ? '<img class="mem-player-img" src="' + p.photo + '" alt="">' : '<div class="mem-player-init">' + (p.name?p.name.charAt(0):'?') + '</div>')
          + '<span>' + (p.name||'Spiller') + '</span><span class="mem-win-pts">' + p.score + ' par</span></div>').join('')
      + '</div>';
  } else {
    const p = mem.players[0];
    inner = '<div class="mem-win-trophy">🎉</div>'
      + '<div class="mem-win-title">' + (p?.name ? 'Flot, ' + p.name + '!' : 'Flot klaret!') + '</div>'
      + '<div class="mem-win-sub">' + mem.moves + ' træk</div>';
  }
  el.innerHTML = '<div class="mem-shell mem-win-shell"><div class="mem-win-box">' + inner
    + '<button class="rs-start-btn" onclick="memStartGame()" style="margin-top:8px">Spil igen! 🔄</button>'
    + '<button class="mem-back-btn" onclick="renderHuskespil()">← Ny opsætning</button>'
    + '</div></div>';
}

function shuffle(arr) {
  for (let i = arr.length-1; i > 0; i--) { const j = Math.floor(Math.random()*(i+1)); [arr[i],arr[j]]=[arr[j],arr[i]]; }
  return arr;
}

document.addEventListener('DOMContentLoaded', () => { updateFamilyNav(); });
