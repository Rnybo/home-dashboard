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
    const res = await fetch('/api/news/dr', { signal: AbortSignal.timeout(8000) });
    if (!res.ok) throw new Error(res.status);
    nyhedItems = await res.json();
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

async function openNyhed(idx) {
  const item = nyhedItems?.[idx];
  if (!item) return;
  // Neither an iframe (DR sends X-Frame-Options that blocks embedding) nor
  // window.open (Fully Kiosk Browser has no tabs to open) work for showing
  // the full article on this kiosk tablet. Instead: fetch a server-side
  // extracted, script-free reading view (/api/article-extract) and show it
  // in the same modal already used for Aula posts.
  document.getElementById('post-modal-title').textContent = item.title || 'Nyhed';
  document.getElementById('post-modal-meta').textContent = 'DR · ' + formatNyhedDate(item.date);
  document.getElementById('post-modal-body').innerHTML = '<div class="nyhed-loading">Henter artikel…</div>';
  document.getElementById('post-modal-attachments').innerHTML = '';
  document.getElementById('post-modal-overlay').classList.add('open');
  try {
    const r = await fetch(`/api/article-extract?url=${encodeURIComponent(item.link)}`, { signal: AbortSignal.timeout(10000) });
    if (!r.ok) throw new Error(String(r.status));
    const data = await r.json();
    document.getElementById('post-modal-body').innerHTML = data.html || '<p>Intet indhold fundet.</p>';
  } catch(e) {
    document.getElementById('post-modal-body').innerHTML = '<p style="color:#c00">Kunne ikke hente artiklen. Prøv igen senere.</p>';
  }
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
