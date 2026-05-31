    async function loadWeather() {
      try { weatherData = await apiFetch('/api/weather').then(r => r.json()); renderWeek(); }
      catch(e) { weatherData = []; }
    }

    async function loadGoogleCalendar() {
      const days = getWeekDays();
      // Always fetch from today regardless of week offset
      const today = new Date();
      const from = localDateStr(today);
      const toDate = new Date(today); toDate.setDate(toDate.getDate() + 90);
      const to = localDateStr(toDate);
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