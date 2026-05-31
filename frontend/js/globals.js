    const START_H = 0, END_H = 24, HOURS = END_H - START_H;
    const DAY_NAMES = ['Mandag','Tirsdag','Onsdag','Torsdag','Fredag','Lørdag','Søndag'];
    let API_KEY = '';
    let CHILDREN = [];
    let INST_PROFILE_IDS = [];
    let activeTab = 0, weekOffset = 0, allEvents = [], presenceData = {};
    // Tab modes: 'aula' = child tab, 'google' = google calendar tab
    const GOOGLE_TABS = [
      { name: 'Fælles', owner: null, color: '#2e7d32' },
    ];
    let currentView = 'cal';
    let lightboxItems = [], lightboxIdx = 0;

    async function initConfig() {
      try {
        const cfg = await fetch('/api/config').then(r => r.json());
        API_KEY = cfg.api_key || '';
        document.querySelector('header h1').textContent = '🏠 ' + (cfg.dashboard_title || 'Hjem');
        document.title = cfg.dashboard_title || 'Familieoverblik';
      } catch(e) {
        await new Promise(r => setTimeout(r, 1000));
        try {
          const cfg = await fetch('/api/config').then(r => r.json());
          API_KEY = cfg.api_key || '';
          document.querySelector('header h1').textContent = '🏠 ' + (cfg.dashboard_title || 'Hjem');
          document.title = cfg.dashboard_title || 'Familieoverblik';
        } catch(e) {}
      }
    }
    function apiFetch(url, opts = {}) {
      return fetch(url, { ...opts, headers: { ...(opts.headers||{}), 'x-api-key': API_KEY } });
    }
    function getChildIds() { return CHILDREN.map(c => c.id).join(','); }

    const CAL_COLORS = { faelles: '#e53935' };
    const CHILD_PALETTE = ['#1e88e5','#43a047','#8e24aa','#fb8c00','#00897b'];
    function childColor(idx) { return CHILD_PALETTE[idx % CHILD_PALETTE.length]; }
    function aulaImg(url) {
      if (!url) return '';
      if (url.startsWith('http')) return `/api/profile-picture?url=${encodeURIComponent(url)}`;
      return url;
    }
    function calColorMap() {
      const m = { 'cal-faelles': { label: 'Fælles', color: CAL_COLORS.faelles } };
      CHILDREN.forEach((c,i) => m['cal-child-' + c.id] = { label: c.name, color: childColor(i) });
      return m;
    }
    function calEventBackground(calendarStr) {
      if (!calendarStr) return null;
      const cals = calendarStr.split(',').filter(Boolean);
      if (cals.length <= 1) return null;
      const map = calColorMap();
      const colors = cals.map(cid => (map[cid] || {color:'#888'}).color);
      const pct = 100 / colors.length;
      const stops = colors.map((c, i) => `${c} ${i*pct}%, ${c} ${(i+1)*pct}%`).join(', ');
      return `linear-gradient(135deg, ${stops})`;
    }
    const AULA_VIEWS = ['overview', 'gallery', 'klasse', 'msg'];
    const VIEWS = ['cal', 'overview', 'gallery', 'klasse', 'msg'];

    function toggleAulaMenu(e) {
      e.stopPropagation();
      const dd = document.getElementById('aula-dropdown');
      dd.style.display = dd.style.display === 'none' ? 'block' : 'none';
    }
    function switchAulaView(view) {
      document.getElementById('aula-dropdown').style.display = 'none';
      switchView(view);
    }
    document.addEventListener('click', () => {
      const dd = document.getElementById('aula-dropdown');
      if (dd) dd.style.display = 'none';
    });

    function switchView(view) {
      currentView = view;
      document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
      document.getElementById('view-' + view).classList.add('active');
      // Top nav — Kalender or Aula active
      const calBtn = document.querySelector('.top-nav-btn:first-child');
      const aulaBtn = document.getElementById('aula-nav-btn');
      if (calBtn) calBtn.classList.toggle('active', view === 'cal');
      if (aulaBtn) aulaBtn.classList.toggle('active', AULA_VIEWS.includes(view));
      // Dropdown items active state
      document.querySelectorAll('.aula-dd-item').forEach(item => {
        const v = item.getAttribute('onclick').match(/'(\w+)'/)?.[1];
        item.classList.toggle('active', v === view);
      });
      // Bottom nav
      document.querySelectorAll('.bottom-nav button').forEach((b,i) => b.classList.toggle('active', VIEWS[i] === view));
      if (view === 'gallery' && !galleryLoaded) loadGallery();
      if (view === 'klasse' && !klasseLoaded) loadGroups();
      if (view === 'msg') syncMessagesFull();
      setBadge(view, 0);
      setSeen(view, Date.now());
    }

    function updateClock() {
      const now = new Date();
      document.getElementById('clock').textContent = window.innerWidth < 600
        ? now.toLocaleTimeString('da-DK', {hour:'2-digit',minute:'2-digit'})
        : now.toLocaleDateString('da-DK', {weekday:'long',day:'numeric',month:'long'}) + '  ' + now.toLocaleTimeString('da-DK', {hour:'2-digit',minute:'2-digit'});
    }
    updateClock(); setInterval(updateClock, 30000); window.addEventListener('resize', updateClock);

    function getWeekDays() {
      const now = new Date(); now.setDate(now.getDate() + weekOffset * 7);
      const day = now.getDay() || 7; const mon = new Date(now); mon.setDate(now.getDate() - day + 1);
      return Array.from({length:7}, (_,i) => { const d = new Date(mon); d.setDate(mon.getDate()+i); return d; });
    }
    function getWeekNr(date) {
      const d = new Date(date); d.setHours(0,0,0,0);
      d.setDate(d.getDate() + 3 - (d.getDay()+6)%7);
      const w1 = new Date(d.getFullYear(), 0, 4);
      return 1 + Math.round(((d-w1)/86400000 - 3 + (w1.getDay()+6)%7)/7);
    }
    function isSameDay(a,b) { return a.getFullYear()===b.getFullYear()&&a.getMonth()===b.getMonth()&&a.getDate()===b.getDate(); }
    function pct(min) { return ((min - START_H*60) / (HOURS*60)) * 100; }

    let googleEvents = [];
    let weatherData = [];
    let routeData = [];
    const ROUTE_MODE_LABELS = {'cycling-regular':'🚴','foot-walking':'🚶','driving-car':'🚗'};
    let routeModes = {};

    async function loadRoutes() {
      try {
        routeData = await apiFetch('/api/routes').then(r => r.json());
        routeData.forEach(d => { if (!routeModes[d.name]) routeModes[d.name] = d.default; });
        renderTodayWidget();
      } catch(e) { routeData = []; }
    }
    function cycleRouteMode(name) {
      const modes = ['cycling-regular','foot-walking','driving-car'];
      const cur = routeModes[name] || modes[0];
      routeModes[name] = modes[(modes.indexOf(cur)+1) % modes.length];
      renderTodayWidget();
    }

    // Met.no symbol → emoji mapping
    const WEATHER_ICONS = {
      clearsky: '☀️', fair: '🌤️', partlycloudy: '⛅', cloudy: '☁️',
      rainshowers: '🌦️', rainshowersandthunder: '⛈️', sleetshowers: '🌨️',
      snowshowers: '❄️', rain: '🌧️', heavyrain: '🌧️', lightrainshowersandthunder: '⛈️',
      rainandthunder: '⛈️', sleet: '🌨️', snow: '❄️', snowandthunder: '❄️',
      fog: '🌫️', lightrain: '🌦️', lightrainshowers: '🌦️',
    };
    function weatherIcon(symbol) {
      if (!symbol) return '';
      const key = symbol.replace(/_day|_night|_polartwilight/g, '').replace(/_/g,'').toLowerCase();
      for (const [k, v] of Object.entries(WEATHER_ICONS)) if (key.startsWith(k)) return v;
      return '🌡️';
    }
    function windArrow(deg) {
      // Arrow points in the direction wind is blowing TO (opposite of from)
      const arrows = ['↓','↙','←','↖','↑','↗','→','↘'];
      return arrows[Math.round(((deg + 180) % 360) / 45) % 8];
    }

    async function loadWeather() {
      try { weatherData = await apiFetch('/api/weather').then(r => r.json()); renderWeek(); }
      catch(e) { weatherData = []; }
    }

    async function loadGoogleCalendar() {
      const days = getWeekDays();
      // Always fetch from today regardless of week offset
      const today = new Date();
      const from = today.toISOString().split('T')[0];
      const toDate = new Date(today); toDate.setDate(toDate.getDate() + 90);
      const to = toDate.toISOString().split('T')[0];
      try {
        googleEvents = await apiFetch(`/api/google-calendar?from_date=${from}&to_date=${to}`).then(r => r.json());
        const custom = await apiFetch('/api/custom-events').then(r => r.json()).catch(() => []);
        custom.forEach(e => googleEvents.push({ ...e, allDay: !e.start.includes('T'), custom: true }));
      } catch(e) { googleEvents = []; }
      renderWeek();
      renderUpcomingGoogleEvents();
      renderTodayWidget();
    }
    async function loadProfileConfig() {
      try {
        const cfg = await apiFetch('/api/profile-config').then(r => r.json());
        CHILDREN = cfg.children || [];
        INST_PROFILE_IDS = cfg.inst_profile_ids || [];
        CHILDREN.forEach(c => { c._photoUrl = c.photoUrl; });
        try{
          const toStore = CHILDREN.map(c => ({ ...c, photoUrl: '' }));
          localStorage.setItem('ls_children', JSON.stringify(toStore));
          localStorage.setItem('ls_inst_ids', JSON.stringify(INST_PROFILE_IDS));
        }catch(e){}
        document.getElementById('child-tabs').innerHTML = [
          ...CHILDREN.map((c, i) =>
            `<div class="tab ${i===0?'active':''}" onclick="switchTab(${i})" style="border-bottom:3px solid ${childColor(i)}">
              ${c.photoUrl ? `<img src="${aulaImg(c.photoUrl)}" alt="${c.name}" onerror="this.style.display='none'">` : ''}
              ${c.name}
            </div>`
          ),
          ...GOOGLE_TABS.map((g, i) =>
            `<div class="tab" onclick="switchGoogleTab(${i})" style="border-bottom:3px solid ${CAL_COLORS.faelles}">
              <span style="color:${CAL_COLORS.faelles}">📅</span> ${g.name}
            </div>`
          ),
        ].join('');
      } catch(e) {}
    }

    let activeGoogleTab = -1; // -1 = aula tab active, >=0 = google tab index
