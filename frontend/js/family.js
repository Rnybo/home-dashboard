// family.js — Familie nav og app-grid

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
  btn.style.display = (cfg.kids.length || cfg.adults.length) ? '' : 'none';
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

// Deles af regnespil og huskespil
function shuffle(arr) {
  for (let i = arr.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [arr[i], arr[j]] = [arr[j], arr[i]];
  }
  return arr;
}

document.addEventListener('DOMContentLoaded', () => { updateFamilyNav(); });
