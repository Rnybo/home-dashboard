// apps/tal.js — Tal-appen
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
function talReset() {
  talCount = 0;
  const el = document.getElementById('tal-number');
  if (el) el.textContent = '0';
}
