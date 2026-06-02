// apps/nyheder.js — Nyheder-appen (DR RSS)
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

function openNyhed(idx) {
  if (nyhedItems?.[idx]) window.open(nyhedItems[idx].link, '_blank');
}

function formatNyhedDate(dateStr) {
  try {
    const diff = Math.floor((new Date() - new Date(dateStr)) / 60000);
    if (diff < 1) return 'Lige nu';
    if (diff < 60) return diff + ' min. siden';
    if (diff < 1440) return Math.floor(diff/60) + ' timer siden';
    return new Date(dateStr).toLocaleDateString('da-DK', { weekday:'short', day:'numeric', month:'short' });
  } catch(e) { return ''; }
}
