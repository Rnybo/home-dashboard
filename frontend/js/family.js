// family.js — Familie-sider (Børn & Voksne) + apps
// Config gemmes i localStorage:
//   family_kids_apps   → array af app-id'er
//   family_adults_apps → array af app-id'er

const FAMILY_APPS = {
  kids: [
    { id: 'tal',      label: 'Tal',          icon: '🔢', comingSoon: false },
    { id: 'spell',    label: 'Stavespil',     icon: '🔤', comingSoon: true  },
    { id: 'wordgame', label: 'Ordleg',        icon: '🃏', comingSoon: true  },
    { id: 'drawing',  label: 'Tegnesjov',     icon: '🎨', comingSoon: true  },
    { id: 'memory',   label: 'Memory',        icon: '🧠', comingSoon: true  },
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

// ── Boot ──────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  updateFamilyNav();
});
