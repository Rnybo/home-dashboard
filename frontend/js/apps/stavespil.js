// apps/stavespil.js — Stavespil

const SS_LEVELS = [
  { id: 'easy',   icon: '🌱', label: 'Let',    color: '#22c55e', desc: '2-3 bogstaver', hidden: 1 },
  { id: 'medium', icon: '🌙', label: 'Mellem', color: '#3b82f6', desc: '4-5 bogstaver', hidden: 2 },
  { id: 'hard',   icon: '🚀', label: 'Svær',  color: '#ec4899', desc: '6+ bogstaver',  hidden: 3 },
];

// img: sti under /static/memory/ — genbrug huskespillets billeder
const SS_WORDS = {
  easy: [
    { word: 'ABE',   emoji: '🐒', hint: 'Hvad hedder dette dyr?',        img: '/static/memory/animals/gorilla.jpg' },
    { word: 'AND',   emoji: '🦆', hint: 'Hvad hedder dette dyr?' },
    { word: 'BI',    emoji: '🐝', hint: 'Hvad hedder dette insekt?' },
    { word: 'KO',    emoji: '🐄', hint: 'Hvad hedder dette dyr?' },
    { word: 'ORM',   emoji: '🪱', hint: 'Hvad hedder dette dyr?' },
    { word: 'SOL',   emoji: '☀️', hint: 'Hvad skinner på himlen?',       img: '/static/memory/space/sun.jpg' },
    { word: 'BIL',   emoji: '🚗', hint: 'Hvad er dette køretøj?',       img: '/static/memory/transport/racing-car.jpg' },
    { word: 'BUS',   emoji: '🚌', hint: 'Hvad er dette køretøj?',       img: '/static/memory/transport/bus.jpg' },
    { word: 'HUS',   emoji: '🏠', hint: 'Hvad bor man i?' },
    { word: 'IS',    emoji: '🍦', hint: 'Hvad er dette?'},
    { word: 'KAT',   emoji: '🐱', hint: 'Hvad hedder dette dyr?' },
    { word: 'HUND',  emoji: '🐶', hint: 'Hvad hedder dette dyr?' },
    { word: 'FISK',  emoji: '🐟', hint: 'Hvad hedder dette dyr?',         img: '/static/memory/ocean/clownfish.jpg' },
    { word: 'GRIS',  emoji: '🐷', hint: 'Hvad hedder dette dyr?' },
    { word: 'FUGL',  emoji: '🐦', hint: 'Hvad hedder dette dyr?',         img: '/static/memory/animals/flamingo.jpg' },
    { word: 'ULV',  emoji: '🐺', hint: 'Hvad hedder dette dyr?',         img: '/static/memory/animals/wolf.jpg' },
    { word: 'BJØRN', emoji: '🐻', hint: 'Hvad hedder dette dyr?',         img: '/static/memory/animals/bear.jpg' },
    { word: 'PANDA', emoji: '🐼', hint: 'Hvad hedder dette dyr?',         img: '/static/memory/animals/panda.jpg' },
    { word: 'RÆV',  emoji: '🦊', hint: 'Hvad hedder dette dyr?',         img: '/static/memory/animals/fox.jpg' },
    { word: 'KAMEL', emoji: '🐫', hint: 'Hvad hedder dette dyr?',         img: '/static/memory/animals/camel.jpg' },
  ],
  medium: [
    { word: 'ZEBRA',   emoji: '🦓', hint: 'Et dyr med striber',           img: '/static/memory/animals/zebra.jpg' },
    { word: 'GIRAF',   emoji: '🦒', hint: 'Et dyr med lang hals',         img: '/static/memory/animals/giraffe.jpg' },
    { word: 'TIGER',   emoji: '🐯', hint: 'Et vildt kattedyr',            img: '/static/memory/animals/tiger.jpg' },
    { word: 'BANAN',   emoji: '🍌', hint: 'En gul frugt' },
    { word: 'PIZZA',   emoji: '🍕', hint: 'Hvad er dette?'},
    { word: 'CYKEL',   emoji: '🚲', hint: 'Hvad er dette køretøj?',     img: '/static/memory/transport/bicycle.jpg' },
    { word: 'BLOMST',  emoji: '🌸', hint: 'Hvad hedder dette?',           img: '/static/memory/nature/flower.jpg' },
    { word: 'SNEGL',   emoji: '🐌', hint: 'Et langsomt dyr med hus' },
    { word: 'KOALA',   emoji: '🐨', hint: 'Et blødt dyr fra Australien', img: '/static/memory/animals/koala.jpg' },
    { word: 'PANDA',   emoji: '🐼', hint: 'Et sort og hvidt dyr',         img: '/static/memory/animals/panda.jpg' },
    { word: 'RAKET',   emoji: '🚀', hint: 'Hvad flyver i rummet?',        img: '/static/memory/space/rocket.jpg' },
    { word: 'STJERNE', emoji: '⭐', hint: 'Hvad lyser om natten?' },
    { word: 'KAGE',    emoji: '🎂', hint: 'Hvad spiser man til fødselsdag?'},
    { word: 'BURGER',  emoji: '🍔', hint: 'Hvad er dette?'},
    { word: 'PASTA',   emoji: '🍝', hint: 'Hvad er dette?'},
    { word: 'UGLE',    emoji: '🦉', hint: 'En natteravn af en fugl',      img: '/static/memory/animals/owl.jpg' },
    { word: 'GEPARD',  emoji: '🐆', hint: 'Det hurtigste dyr på land',   img: '/static/memory/animals/cheetah.jpg' },
    { word: 'DELFIN',  emoji: '🐬', hint: 'Et smart havdyr',              img: '/static/memory/animals/dolphin.jpg' },
  ],
  hard: [
    { word: 'SOMMERFUGL', emoji: '🦋', hint: 'Et farverigt insekt',       img: '/static/memory/nature/butterfly.jpg' },
    { word: 'KROKODILLE', emoji: '🐊', hint: 'Et farligt krybdyr',        img: '/static/memory/animals/crocodile.jpg' },
    { word: 'FLODHEST',   emoji: '🦛', hint: 'Et stort dyr ved floden',   img: '/static/memory/animals/hippopotamus.jpg' },
    { word: 'PINGVIN',    emoji: '🐧', hint: 'En fugl der ikke flyver',   img: '/static/memory/animals/penguin.jpg' },
    { word: 'REGNBUE',    emoji: '🌈', hint: 'Hvad ses efter regn?',      img: '/static/memory/nature/rainbow.jpg' },
    { word: 'NÆSEHORN', emoji: '🦏', hint: 'Dyr med horn på næsen', img: '/static/memory/animals/rhinoceros.jpg' },
    { word: 'KENGURU',    emoji: '🦘', hint: 'Et hoppende dyr fra Australien', img: '/static/memory/animals/kangaroo.jpg' },
    { word: 'GORILLA',    emoji: '🦍', hint: 'En stor abe',               img: '/static/memory/animals/gorilla.jpg' },
    { word: 'VANDMAND',   emoji: '🪼', hint: 'Et gennemsigtigt havdyr',   img: '/static/memory/ocean/jellyfish.jpg' },
    { word: 'HELIKOPTER', emoji: '🚁', hint: 'Hvad er dette køretøj?',  img: '/static/memory/transport/helicopter.jpg' },
    { word: 'UBÅD',     emoji: '🤿', hint: 'Et fartøj under vandet',    img: '/static/memory/transport/submarine.jpg' },
    { word: 'LUFTBALLON', emoji: '🎈', hint: 'Flyver med varm luft',      img: '/static/memory/transport/hot-air-balloon.jpg' },
    { word: 'KAMÆLEON',   emoji: '🦎', hint: 'Et dyr der skifter farve', img: '/static/memory/animals/chameleon.jpg' },
  ],
};

const SS_EXTRA_LETTERS = 'ABCDEFGHIJKLMNOPRSTVÆØÅ'.split('');

let ss = {
  level: 'easy', phase: 'setup',
  childName: '', childPhoto: '',
  word: null, slots: [], tiles: [],
  score: 0, streak: 0,
  dragging: null, answered: false,
};

// ── Setup ────────────────────────────────────────────────────────────────────

function renderStavespil() {
  const el = document.getElementById('view-app-spell');
  if (!el) return;
  ss.phase = 'setup';

  const hasChildren = typeof CHILDREN !== 'undefined' && CHILDREN.length > 0;
  const childSection = hasChildren
    ? '<div class="rs-setup-section"><div class="rs-setup-label">Hvem spiller?</div><div class="rs-child-row">'
      + CHILDREN.map((c, i) => {
          const active = ss.childName === c.name;
          const photo  = (c._photoUrl || c.photoUrl) ? aulaImg(c._photoUrl || c.photoUrl) : '';
          return '<button class="rs-child-btn ' + (active ? 'rs-child-active' : '') + '" onclick="ssSelectChild(' + i + ')">'
            + (photo ? '<img class="rs-child-img" src="' + photo + '" alt="" onerror="this.style.display=\'none\';this.nextElementSibling.style.display=\'flex\'">' : '')
            + '<div class="rs-child-initials" style="' + (photo ? 'display:none' : '') + '">' + c.name.charAt(0) + '</div>'
            + '<span class="rs-child-name">' + c.name + '</span></button>';
        }).join('') + '</div></div>'
    : '<div class="rs-setup-section"><div class="rs-setup-label">Hvem spiller?</div>'
      + '<input class="rs-name-input" type="text" placeholder="Skriv navn..." value="' + ss.childName + '" oninput="ss.childName=this.value.trim();ss.childPhoto=\'\'"></div>';

  el.innerHTML = '<div class="rs-shell rs-setup-shell">'
    + '<div class="rs-topbar"><button class="family-back-btn" onclick="familyAppBack(\'family-kids\')" style="padding:0;margin:0">← Tilbage</button>'
    + '<span class="rs-setup-title">✏️ Stavespil</span></div>'
    + '<div class="rs-setup-body">' + childSection
    + '<div class="rs-setup-section"><div class="rs-setup-label">Vælg sværhedsgrad</div><div class="rs-level-grid">'
    + SS_LEVELS.map(lv => '<button class="rs-level-btn ' + (ss.level === lv.id ? 'rs-level-active' : '') + '" data-level="' + lv.id + '" style="--lv-color:' + lv.color + '" onclick="ssSelectLevel(\'' + lv.id + '\')">'
        + '<span class="rs-level-icon">' + lv.icon + '</span><span class="rs-level-name">' + lv.label + '</span><span class="rs-level-desc">' + lv.desc + '</span></button>').join('')
    + '</div></div>'
    + '<button class="rs-start-btn" onclick="ssStartGame()">Spil nu! ✏️</button>'
    + '</div></div>';
}

function ssSelectChild(idx) {
  const c = CHILDREN[idx]; if (!c) return;
  ss.childName  = c.name;
  ss.childPhoto = (c._photoUrl || c.photoUrl) ? aulaImg(c._photoUrl || c.photoUrl) : '';
  document.querySelectorAll('.rs-child-btn').forEach((b, i) => b.classList.toggle('rs-child-active', i === idx));
}
function ssSelectLevel(id) {
  ss.level = id;
  document.querySelectorAll('.rs-level-btn').forEach(b => b.classList.toggle('rs-level-active', b.dataset.level === id));
}

// ── Game ─────────────────────────────────────────────────────────────────────

function ssStartGame() {
  ss.phase = 'play'; ss.score = 0; ss.streak = 0;
  const el = document.getElementById('view-app-spell'); if (!el) return;
  const lv = SS_LEVELS.find(l => l.id === ss.level);
  const playerBadge = ss.childName
    ? '<div class="rs-player-badge">'
      + (ss.childPhoto ? '<img class="rs-player-img" src="' + ss.childPhoto + '" alt="">' : '<div class="rs-player-initials">' + ss.childName.charAt(0) + '</div>')
      + '<span class="rs-player-name">' + ss.childName + '</span></div>'
    : '';
  el.innerHTML = '<div class="rs-shell">'
    + '<div class="rs-topbar"><button class="family-back-btn" onclick="renderStavespil()" style="padding:0;margin:0">← Indstillinger</button>'
    + '<div class="rs-score-row">' + playerBadge
    + '<span class="rs-level-chip" style="background:' + lv.color + '22;color:' + lv.color + ';border-color:' + lv.color + '55">' + lv.icon + ' ' + lv.label + '</span>'
    + '<span id="rs-stars"></span><span class="rs-score-label">Point: <strong id="rs-score">0</strong></span></div></div>'
    + '<div class="rs-stage" id="rs-stage"></div>'
    + '<div class="rs-fb-overlay" id="rs-fb-overlay" onclick="ssFbOverlayClick(event)" style="display:none">'
    + '<div class="rs-fb-modal" id="rs-fb-modal"><div class="rs-fb-msg" id="rs-fb-msg"></div>'
    + '<button class="rs-fb-next" onclick="ssDismissFeedback()">Næste ord →</button></div></div>';
  ssNewRound();
}

function ssPickWord() {
  const pool = SS_WORDS[ss.level];
  const filtered = pool.filter(w => !ss.word || w.word !== ss.word.word);
  return filtered[Math.floor(Math.random() * filtered.length)];
}

function ssNewRound() {
  ss.answered = false;
  ss.word = ssPickWord();
  const lv = SS_LEVELS.find(l => l.id === ss.level);
  const letters = ss.word.word.toUpperCase().split('');
  const numHidden = Math.min(lv.hidden, letters.length - 1);
  const positions = shuffle([...Array(letters.length).keys()]).slice(0, numHidden);
  ss.slots = letters.map((l, i) => ({
    letter: l, hidden: positions.includes(i), filled: null, id: 'ss-slot-' + i
  }));
  const hiddenLetters = ss.slots.filter(s => s.hidden).map(s => s.letter);
  const numExtra = Math.max(2, hiddenLetters.length + 2);
  const extras = shuffle(SS_EXTRA_LETTERS.filter(l => !hiddenLetters.includes(l))).slice(0, numExtra);
  ss.tiles = shuffle([...hiddenLetters, ...extras]).map((l, i) => ({
    letter: l, id: 'ss-tile-' + i, used: false
  }));
  ssRenderRound();
}

function ssRenderRound() {
  const stage = document.getElementById('rs-stage'); if (!stage) return;
  const w = ss.word;

  // Vis billede hvis tilgaengeligt, ellers emoji
  const visual = w.img
    ? '<img class="ss-img" src="' + w.img + '" alt="" onerror="this.style.display=\'none\';this.nextElementSibling.style.display=\'block\'">'
      + '<div class="ss-emoji" style="display:none">' + w.emoji + '</div>'
    : '<div class="ss-emoji">' + w.emoji + '</div>';

  const slotsHtml = ss.slots.map(s =>
    s.hidden
      ? '<div class="ss-slot ss-slot-empty" id="' + s.id + '" data-slot="' + s.id + '"><span class="ss-slot-hint">_</span></div>'
      : '<div class="ss-slot ss-slot-fixed">' + s.letter + '</div>'
  ).join('');

  const tilesHtml = ss.tiles.map(t =>
    '<div class="ss-tile" id="' + t.id + '" data-tile="' + t.id + '">' + t.letter + '</div>'
  ).join('');

  stage.innerHTML =
    '<div class="ss-emoji-box">'
    + visual
    + '<div class="ss-hint">' + w.hint + '</div>'
    + '</div>'
    + '<div class="ss-slots-row" id="ss-slots-row">' + slotsHtml + '</div>'
    + '<div class="ss-tiles-row" id="ss-tiles-row">' + tilesHtml + '</div>';

  ssUpdateStars();
  ssBindDrag();
}

function ssUpdateStars() {
  const el = document.getElementById('rs-stars'); if (!el) return;
  const s = Math.min(ss.streak, 5);
  el.innerHTML = '⭐'.repeat(s) + '☆'.repeat(5 - s);
}

// ── Drag ─────────────────────────────────────────────────────────────────────

let ssGhost = null;

function ssBindDrag() {
  document.querySelectorAll('.ss-tile').forEach(tile =>
    tile.addEventListener('pointerdown', ssPointerDown, { passive: false })
  );
  // Klik på udfyldt slot fjerner tile igen
  document.querySelectorAll('.ss-slot-filled').forEach(slot =>
    slot.addEventListener('click', () => ssRemoveFromSlot(slot.id))
  );
}

function ssRemoveFromSlot(slotId) {
  if (ss.answered) return;
  const slotData = ss.slots.find(s => s.id === slotId);
  if (!slotData || !slotData.filled) return;
  const tileData = ss.tiles.find(t => t.id === slotData.filled);
  if (tileData) {
    tileData.used = false;
    const tileEl = document.getElementById(tileData.id);
    if (tileEl) tileEl.classList.remove('ss-tile-used');
  }
  slotData.filled = null;
  const slotEl = document.getElementById(slotId);
  if (slotEl) {
    slotEl.innerHTML = '<span class="ss-slot-hint">_</span>';
    slotEl.classList.remove('ss-slot-filled');
    slotEl.classList.add('ss-slot-empty');
    slotEl.onclick = null;
  }
}

function ssPointerDown(e) {
  // Same guard as regnespil.js's rsPointerDown — ignore a second touch while
  // a drag is already active, or a second finger touching another tile
  // orphans the first drag's ghost element on screen.
  if (ss.answered || ss.dragging) return;
  e.preventDefault();
  const tile = e.currentTarget;
  const tileData = ss.tiles.find(t => t.id === tile.dataset.tile);
  if (!tileData || tileData.used) return;
  const rect = tile.getBoundingClientRect();
  ssGhost = document.createElement('div');
  ssGhost.className = 'ss-tile ss-ghost';
  ssGhost.textContent = tileData.letter;
  ssGhost.style.cssText = 'position:fixed;left:' + rect.left + 'px;top:' + rect.top + 'px;width:' + rect.width + 'px;height:' + rect.height + 'px;pointer-events:none;z-index:9999;';
  document.body.appendChild(ssGhost);
  ss.dragging = { tileData, tile, startX: e.clientX, startY: e.clientY, origTop: rect.top, origLeft: rect.left };
  tile.classList.add('rs-dragging-src');
  document.addEventListener('pointermove',  ssPointerMove,  { passive: false });
  document.addEventListener('pointerup',    ssPointerUp);
  document.addEventListener('pointercancel', ssPointerCancel);
}

function ssPointerMove(e) {
  if (!ssGhost || !ss.dragging) return;
  e.preventDefault();
  ssGhost.style.left = (ss.dragging.origLeft + e.clientX - ss.dragging.startX) + 'px';
  ssGhost.style.top  = (ss.dragging.origTop  + e.clientY - ss.dragging.startY) + 'px';
  document.querySelectorAll('.ss-slot-empty').forEach(slot => {
    const sr = slot.getBoundingClientRect(), gr = ssGhost.getBoundingClientRect();
    slot.classList.toggle('rs-dz-hover', gr.left < sr.right && gr.right > sr.left && gr.top < sr.bottom && gr.bottom > sr.top);
  });
}

function ssPointerUp(e) {
  document.removeEventListener('pointermove',  ssPointerMove);
  document.removeEventListener('pointerup',    ssPointerUp);
  document.removeEventListener('pointercancel', ssPointerCancel);
  if (!ssGhost || !ss.dragging) return;
  const gr = ssGhost.getBoundingClientRect();
  let droppedSlot = null;
  document.querySelectorAll('.ss-slot-empty').forEach(slot => {
    const sr = slot.getBoundingClientRect();
    if (gr.left < sr.right && gr.right > sr.left && gr.top < sr.bottom && gr.bottom > sr.top) droppedSlot = slot;
  });
  ssGhost.remove(); ssGhost = null;
  ss.dragging.tile.classList.remove('rs-dragging-src');
  document.querySelectorAll('.ss-slot-empty').forEach(s => s.classList.remove('rs-dz-hover'));
  if (droppedSlot) ssPlaceTile(ss.dragging.tileData, droppedSlot.id);
  ss.dragging = null;
}
function ssPointerCancel() {
  document.removeEventListener('pointermove',  ssPointerMove);
  document.removeEventListener('pointerup',    ssPointerUp);
  document.removeEventListener('pointercancel', ssPointerCancel);
  if (ssGhost) { ssGhost.remove(); ssGhost = null; }
  if (ss.dragging) {
    ss.dragging.tile.classList.remove('rs-dragging-src');
    document.querySelectorAll('.ss-slot-empty').forEach(s => s.classList.remove('rs-dz-hover'));
    ss.dragging = null;
  }
}

function ssPlaceTile(tileData, slotId) {
  const slotData = ss.slots.find(s => s.id === slotId);
  if (!slotData || !slotData.hidden) return;
  if (slotData.filled) {
    const oldTile = ss.tiles.find(t => t.id === slotData.filled);
    if (oldTile) { oldTile.used = false; const oldEl = document.getElementById(oldTile.id); if (oldEl) oldEl.classList.remove('ss-tile-used'); }
  }
  tileData.used = true;
  slotData.filled = tileData.id;
  const slotEl = document.getElementById(slotId);
  if (slotEl) {
    slotEl.innerHTML = tileData.letter;
    slotEl.classList.add('ss-slot-filled');
    slotEl.classList.remove('ss-slot-empty');
    // Tillad at fjerne ved klik eller drag ud
    slotEl.onclick = () => ssRemoveFromSlot(slotId);
  }
  const tileEl = document.getElementById(tileData.id);
  if (tileEl) tileEl.classList.add('ss-tile-used');
  if (ss.slots.filter(s => s.hidden).every(s => s.filled)) ssCheckAnswer();
}

// ── Check ────────────────────────────────────────────────────────────────────

function ssCheckAnswer() {
  if (ss.answered) return;
  ss.answered = true;
  const correct = ss.slots.every(s => {
    if (!s.hidden) return true;
    const t = ss.tiles.find(t => t.id === s.filled);
    return t && t.letter === s.letter;
  });
  const n = ss.childName;
  if (correct) {
    ss.score++; ss.streak++;
    document.getElementById('rs-score').textContent = ss.score;
    ssUpdateStars();
    ss.slots.forEach(s => { const el = document.getElementById(s.id); if (el) el.classList.add('ss-slot-correct'); });
    rsBurst(document.getElementById('ss-slots-row'));
    const msgs = n
      ? ['Flot stavet, ' + n + '! 🌟', 'Rigtig! Godt klaret, ' + n + '! 👏', 'Perfekt, ' + n + '! ⭐', 'Du er sej, ' + n + '! 🎉']
      : ['Flot stavet! 🌟', 'Rigtig! 👏', 'Perfekt! ⭐', 'Godt klaret! 🎉'];
    ssShowFeedback(msgs[Math.floor(Math.random() * msgs.length)], true);
  } else {
    ss.streak = 0;
    document.getElementById('rs-score').textContent = ss.score;
    ssUpdateStars();
    ss.slots.filter(s => s.hidden).forEach(s => {
      const t = ss.tiles.find(t => t.id === s.filled);
      const wrong = !t || t.letter !== s.letter;
      const el = document.getElementById(s.id);
      if (el) { el.textContent = s.letter; el.classList.add(wrong ? 'ss-slot-wrong' : 'ss-slot-correct'); }
    });
    ssShowFeedback(n
      ? 'Ikke helt, ' + n + ' — det staves <strong>' + ss.word.word + '</strong> 💪'
      : 'Ikke helt — det staves <strong>' + ss.word.word + '</strong> 💪', false);
  }
}

function ssShowFeedback(msg, correct) {
  const overlay = document.getElementById('rs-fb-overlay'), modal = document.getElementById('rs-fb-modal'), msgEl = document.getElementById('rs-fb-msg');
  if (!overlay || !msgEl) return;
  msgEl.innerHTML = msg; overlay.style.display = 'flex';
  modal.className = 'rs-fb-modal ' + (correct ? 'rs-fb-correct' : 'rs-fb-wrong');
  modal.classList.remove('rs-fb-bounce'); void modal.offsetWidth; modal.classList.add('rs-fb-bounce');
}
function ssDismissFeedback() { const o = document.getElementById('rs-fb-overlay'); if (o) o.style.display = 'none'; ssNewRound(); }
function ssFbOverlayClick(e) { if (e.target === document.getElementById('rs-fb-overlay')) ssDismissFeedback(); }
