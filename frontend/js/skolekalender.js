// skolekalender.js — Børnevenlig "skoledag/skoleuge"-visning.
//
// Åbnes via 🎒-knappen på et barns fane (se globals.js's child-tabs render).
// Viser KUN events fra ugebrev-featuren (backend/ugebrev.py, source==="ugebrev"),
// afkoblet fra den komplekse uge-grid — store ikoner, ét formål: "hvad skal
// jeg i dag/denne uge". Genbruger /api/custom-events, ingen ny backend-kode.

let _schoolCalChildId = null;
// 'child' = almindelig per-barn skoledag/uge, 'sfo' = kombineret SFO-visning
// på tværs af ALLE børn (samme SFO-plan bliver i praksis synkroniseret
// separat pr. barn med identisk indhold, se _renderSchoolCalendarBody()).
let _schoolCalMode = 'child';
let _schoolCalScope = 'day';
// Uger relativt til DENNE kalenderuge (0 = denne uge, -1 = forrige, +1 = næste,
// osv.) — erstatter den tidligere faste 'nextweek'-knap med fri navigation
// vilkårligt frem/tilbage, da et ugebrev-dokument typisk indeholder mange
// uger (skolen genbruger ét løbende Google Doc for hele skoleåret).
let _schoolCalWeekOffset = 0;

function openSchoolCalendar(childId, initialScope, initialOffset) {
  _schoolCalMode = 'child';
  _schoolCalChildId = childId;
  _schoolCalScope = initialScope || 'day';
  _schoolCalWeekOffset = initialOffset || 0;
  document.querySelectorAll('#school-cal-toggle .scope-btn').forEach(b => b.classList.toggle('active', b.dataset.scope === _schoolCalScope));
  const child = (CHILDREN || []).find(c => c.id === childId);
  document.getElementById('school-cal-title').dataset.baseTitle = '🎒 ' + (child ? child.name + 's skoledag' : 'Skoledag');
  document.getElementById('school-cal-title').textContent = document.getElementById('school-cal-title').dataset.baseTitle;
  document.getElementById('school-cal-info-box').classList.remove('open');
  document.getElementById('school-cal-overlay').classList.add('open');
  renderSchoolCalendar();
}

// Samme modal som openSchoolCalendar(), men uden en bestemt childId — viser
// SFO-events for ALLE børn samlet ét sted, i stedet for at man skal tjekke
// hvert barns fane for sig for at se den samme SFO-plan gentaget.
function openSfoCalendar(initialScope, initialOffset) {
  _schoolCalMode = 'sfo';
  _schoolCalChildId = null;
  _schoolCalScope = initialScope || 'day';
  _schoolCalWeekOffset = initialOffset || 0;
  document.querySelectorAll('#school-cal-toggle .scope-btn').forEach(b => b.classList.toggle('active', b.dataset.scope === _schoolCalScope));
  document.getElementById('school-cal-title').dataset.baseTitle = '🏠 SFO';
  document.getElementById('school-cal-title').textContent = document.getElementById('school-cal-title').dataset.baseTitle;
  document.getElementById('school-cal-info-box').classList.remove('open');
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
  if (scope === 'day') _schoolCalWeekOffset = 0;  // "I dag" nulstiller altid til nu
  document.querySelectorAll('#school-cal-toggle .scope-btn').forEach(b => b.classList.toggle('active', b.dataset.scope === scope));
  document.getElementById('school-cal-info-box').classList.remove('open');
  renderSchoolCalendar();
}

function shiftSchoolCalWeek(delta) {
  _schoolCalScope = 'week';
  _schoolCalWeekOffset += delta;
  document.querySelectorAll('#school-cal-toggle .scope-btn').forEach(b => b.classList.toggle('active', b.dataset.scope === 'week'));
  document.getElementById('school-cal-info-box').classList.remove('open');
  renderSchoolCalendar();
}

async function toggleSchoolCalInfo() {
  const box = document.getElementById('school-cal-info-box');
  if (box.classList.contains('open')) { box.classList.remove('open'); return; }
  // Fast lille header med et eksplicit luk-kryds + en separat scrollbar
  // tekst-container — lange ugebrev-noter (set i praksis: op til ~2000
  // tegn) skal kunne scrolles UDEN at skjule resten af dialogen eller
  // gøre den umulig at lukke (se CSS-kommentaren for #school-cal-info-box).
  box.innerHTML = '<div class="info-box-head"><span>📋 Besked fra ugebrevet</span>' +
    '<button class="info-box-close" onclick="toggleSchoolCalInfo()" title="Luk">✕</button></div>' +
    '<div class="info-box-text">Indlæser…</div>';
  box.classList.add('open');
  const calTag = box.dataset.calTag || ('cal-child-' + _schoolCalChildId);
  const week = box.dataset.week, year = box.dataset.year;
  // cacheFetch, IKKE et rent apiFetch — samme grund som i renderSchoolCalendar()
  // nedenfor: skolekalenderen skal kunne læses uden en gyldig Aula-session.
  await cacheFetch(
    `ugebrev_info_${calTag}_${year}_${week}`,
    () => apiFetch(`/api/ugebrev/info?calendar=${calTag}&week=${week}&year=${year}`).then(r => r.json()),
    (data) => {
      const textEl = box.querySelector('.info-box-text');
      if (textEl) textEl.textContent = (data && data.text && data.text.trim()) ? data.text : 'Ingen besked fundet for denne uge i ugebrevet.';
    },
    true  // se kommentaren i renderSchoolCalendar() — denne endpoint kræver ikke Aula-session
  );
}

// ISO 8601-ugenummer — bruges kun til at vise "· Uge X" i titlen, så "Denne
// uge" og "Næste uge" ikke er umulige at skelne når begge (endnu) er tomme.
function _isoWeekNumber(d) {
  const dt = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()));
  const dayNr = (dt.getUTCDay() + 6) % 7;
  dt.setUTCDate(dt.getUTCDate() - dayNr + 3);
  const firstThursday = new Date(Date.UTC(dt.getUTCFullYear(), 0, 4));
  const diffDays = (dt - firstThursday) / 86400000;
  return 1 + Math.round(diffDays / 7);
}

async function renderSchoolCalendar() {
  const body = document.getElementById('school-cal-body');
  body.innerHTML = '<div class="school-cal-empty">Indlæser…</div>';

  // cacheFetch (localStorage), IKKE et rent apiFetch — uden dette var
  // skolekalenderen helt tom hvis Aula-sessionen var udløbet eller nettet
  // hakkede, selv når /api/custom-events reelt kunne have svaret fint (den
  // læser en lokal fil, ikke Aula, og afhænger derfor IKKE af Aula-session —
  // sessionValid sættes derfor bevidst til `true` her, ikke den globale
  // Aula-sessionstilstand, som ville være den forkerte ting at spørge om).
  // Matcher det etablerede mønster i resten af appen, se cache.js. Cache-hit
  // kalder onData synkront FØR noget netværkskald overhovedet forsøges, så
  // "Indlæser…" ovenfor bliver i praksis aldrig synlig når der er en cache.
  await cacheFetch(
    'ugebrev_custom_events',
    () => apiFetch('/api/custom-events').then(r => r.json()),
    (events) => _renderSchoolCalendarBody(events || []),
    true
  );
}

function _renderSchoolCalendarBody(events) {
  const body = document.getElementById('school-cal-body');
  // 'ugebrev' = tabel-baseret skoleskema, 'sfo_ugebrev'/'ugebrev_billede' =
  // billed-tolkede ugeplaner (OCR, se backend/ugebrev.py) — alle skal vises
  // her, ikke kun det oprindelige tabel-format.
  let mine, infoCalTag;
  if (_schoolCalMode === 'sfo') {
    // Samme SFO-plan synkroniseres separat PR. BARN (identisk indhold, kun
    // calendar_tag adskiller dem) — uden dedup ville hver aktivitet vises
    // én gang pr. barn, dvs. dobbelt op når begge børn er omfattet.
    const seen = new Map();
    for (const e of events) {
      if (e.source !== 'sfo_ugebrev') continue;
      const key = `${e.start}|${e.end}|${e.title}`;
      if (!seen.has(key)) seen.set(key, e);
    }
    mine = [...seen.values()];
    // ℹ️-noten er gemt PR. barn (samme tekst for alle, se ugebrev.py) — vi
    // skal bare bruge ét vilkårligt barns calendar_tag for at slå den op.
    infoCalTag = mine.length ? mine[0].calendar : (CHILDREN[0] ? `cal-child-${CHILDREN[0].id}` : null);
  } else {
    const calTag = 'cal-child-' + _schoolCalChildId;
    mine = events.filter(e => ['ugebrev', 'sfo_ugebrev', 'ugebrev_billede'].includes(e.source) && e.calendar === calTag);
    infoCalTag = calTag;
  }
  document.getElementById('school-cal-info-box').dataset.calTag = infoCalTag || '';

  const today = new Date(); today.setHours(0, 0, 0, 0);
  // Lokale dato-komponenter, IKKE toISOString() — den konverterer til UTC og
  // forskyder datoen en dag i dansk sommertid (UTC+2), så "i dag" fredag
  // aften ville matche torsdagens events i stedet. Samme fejlklasse som ved
  // "days" nedenfor, som også bruger lokale Date-metoder konsekvent.
  const isoDate = d => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
  let days;
  const titleEl = document.getElementById('school-cal-title');
  const baseTitle = titleEl.dataset.baseTitle || titleEl.textContent;
  const monday = new Date(today);
  monday.setDate(monday.getDate() - ((monday.getDay() + 6) % 7));
  monday.setDate(monday.getDate() + _schoolCalWeekOffset * 7);

  if (_schoolCalScope === 'day') {
    days = [today];
    titleEl.textContent = baseTitle;
  } else {
    days = [0, 1, 2, 3, 4].map(i => { const d = new Date(monday); d.setDate(d.getDate() + i); return d; });
    titleEl.textContent = `${baseTitle} · Uge ${_isoWeekNumber(monday)}`;
  }

  // Info-boksen (ℹ️-ikon) skal altid pege på den uge der reelt vises, også i
  // "I dag"-scope — ellers ved toggleSchoolCalInfo() ikke hvilken uge den
  // skal hente brødtekst for.
  const infoBox = document.getElementById('school-cal-info-box');
  infoBox.dataset.week = _isoWeekNumber(monday);
  infoBox.dataset.year = monday.getFullYear();
  infoBox.classList.remove('open');

  const DAY_LABELS = ['Søndag', 'Mandag', 'Tirsdag', 'Onsdag', 'Torsdag', 'Fredag', 'Lørdag'];
  let html = '';
  for (const day of days) {
    const dayEvents = mine
      .filter(e => e.start && e.start.slice(0, 10) === isoDate(day))
      .sort((a, b) => a.start.localeCompare(b.start));

    if (_schoolCalScope !== 'day') {
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
      // Heldagsevents (SFO/billed-ugeplaner har intet rigtigt klokkeslæt,
      // se _build_events_from_days_dict i backend/ugebrev.py) skal ikke vise
      // det kunstige "00:00" fra start-strengen.
      const time = ev.allDay ? '' : ev.start.slice(11, 16);
      html += `<div class="school-cal-item"><span class="icon">${icon}</span>` +
        `<div class="info"><div class="time">${time}</div><div class="title">${label}</div></div></div>`;
    }
  }
  body.innerHTML = html || '<div class="school-cal-empty">Intet skema fundet.</div>';
}
