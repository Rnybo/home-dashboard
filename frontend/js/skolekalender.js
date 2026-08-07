// skolekalender.js — Børnevenlig "skoledag/skoleuge"-visning.
//
// Åbnes via 🎒-knappen på et barns fane (se globals.js's child-tabs render).
// Viser KUN events fra ugebrev-featuren (backend/ugebrev.py, source==="ugebrev"),
// afkoblet fra den komplekse uge-grid — store ikoner, ét formål: "hvad skal
// jeg i dag/denne uge". Genbruger /api/custom-events, ingen ny backend-kode.

let _schoolCalChildId = null;
let _schoolCalScope = 'day';

function openSchoolCalendar(childId) {
  _schoolCalChildId = childId;
  _schoolCalScope = 'day';
  document.querySelectorAll('#school-cal-toggle .scope-btn').forEach((b, i) => b.classList.toggle('active', i === 0));
  const child = (CHILDREN || []).find(c => c.id === childId);
  document.getElementById('school-cal-title').textContent = '🎒 ' + (child ? child.name + 's skoledag' : 'Skoledag');
  document.getElementById('school-cal-overlay').classList.add('open');
  renderSchoolCalendar();
}

function closeSchoolCalendar(e) {
  if (!e || e.target.id === 'school-cal-overlay' || e.target.id === 'school-cal-close') {
    document.getElementById('school-cal-overlay').classList.remove('open');
  }
}

function setSchoolCalScope(scope) {
  _schoolCalScope = scope;
  document.querySelectorAll('#school-cal-toggle .scope-btn').forEach(b =>
    b.classList.toggle('active', b.textContent.trim() === (scope === 'day' ? 'I dag' : 'Denne uge')));
  renderSchoolCalendar();
}

async function renderSchoolCalendar() {
  const body = document.getElementById('school-cal-body');
  body.innerHTML = '<div class="school-cal-empty">Indlæser…</div>';

  let events;
  try {
    events = await apiFetch('/api/custom-events').then(r => r.json());
  } catch (e) {
    body.innerHTML = '<div class="school-cal-empty">Kunne ikke hente skemaet.</div>';
    return;
  }

  const calTag = 'cal-child-' + _schoolCalChildId;
  const mine = events.filter(e => e.source === 'ugebrev' && e.calendar === calTag);

  const today = new Date(); today.setHours(0, 0, 0, 0);
  // Lokale dato-komponenter, IKKE toISOString() — den konverterer til UTC og
  // forskyder datoen en dag i dansk sommertid (UTC+2), så "i dag" fredag
  // aften ville matche torsdagens events i stedet. Samme fejlklasse som ved
  // "days" nedenfor, som også bruger lokale Date-metoder konsekvent.
  const isoDate = d => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
  let days;
  if (_schoolCalScope === 'day') {
    days = [today];
  } else {
    const monday = new Date(today);
    monday.setDate(monday.getDate() - ((monday.getDay() + 6) % 7));
    days = [0, 1, 2, 3, 4].map(i => { const d = new Date(monday); d.setDate(d.getDate() + i); return d; });
  }

  const DAY_LABELS = ['Søndag', 'Mandag', 'Tirsdag', 'Onsdag', 'Torsdag', 'Fredag', 'Lørdag'];
  let html = '';
  for (const day of days) {
    const dayEvents = mine
      .filter(e => e.start && e.start.slice(0, 10) === isoDate(day))
      .sort((a, b) => a.start.localeCompare(b.start));

    if (_schoolCalScope === 'week') {
      html += `<div class="day-group-label">${DAY_LABELS[day.getDay()]} ${day.getDate()}.</div>`;
    }
    if (!dayEvents.length) {
      html += `<div class="school-cal-empty">Intet skema${_schoolCalScope === 'day' ? ' for i dag' : ''}.</div>`;
      continue;
    }
    for (const ev of dayEvents) {
      const spaceIdx = ev.title.indexOf(' ');
      const icon = spaceIdx > -1 ? ev.title.slice(0, spaceIdx) : '📋';
      const label = spaceIdx > -1 ? ev.title.slice(spaceIdx + 1) : ev.title;
      const time = ev.start.slice(11, 16);
      html += `<div class="school-cal-item"><span class="icon">${icon}</span>` +
        `<div class="info"><div class="time">${time}</div><div class="title">${label}</div></div></div>`;
    }
  }
  body.innerHTML = html || '<div class="school-cal-empty">Intet skema fundet.</div>';
}
