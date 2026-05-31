    function normalizeAulaEvents(raw) {
      return raw.map(e => ({
        title:       e.title || e.description || '(ingen titel)',
        start:       e.startDateTime,
        end:         e.endDateTime || null,
        allDay:      e.isAllDayEvent || e.allDay || (e.endDateTime && (new Date(e.endDateTime) - new Date(e.startDateTime)) >= 23*3600000),
        color:       'var(--blue-accent)',
        owner:       (e.belongsToProfiles||[])[0] || null,
        profiles:    e.belongsToProfiles || [],
        source:      'aula',
        id:          e.id || null,
        location:    [e.primaryResourceText, e.additionalResourceText].filter(Boolean).join(', ') || '',
        creator:     e.creatorName || '',
        institution: e.institutionName || '',
        type:        e.type || '',
        responseRequired: e.responseRequired || false,
        responseStatus:   e.responseStatus || null,
        repeating:   !!e.repeating,
      }));
    }

    async function loadCalendar() {
      const days=getWeekDays(), from=days[0].toISOString().split('T')[0], to=days[6].toISOString().split('T')[0];
      try {
        const res = await apiFetch(`/api/calendar?inst_profile_ids=${getChildIds()}&from_date=${from}&to_date=${to}`);
        if (res.status === 401) {
          try { const c=localStorage.getItem('ls_events'); if(c){ allEvents=JSON.parse(c); renderWeek(); renderTodayWidget(); } } catch(e) {}
          return;
        }
        allEvents = normalizeAulaEvents(await res.json());
        try { localStorage.setItem('ls_events', JSON.stringify(allEvents)); } catch(e) {}
        renderWeek(); renderTodayWidget();
      } catch(e) {}
    }
    async function loadPresence() {
      const days=getWeekDays(), from=days[0].toISOString().split('T')[0], to=days[6].toISOString().split('T')[0];
      try {
        const res=await apiFetch(`/api/presence?inst_profile_ids=${getChildIds()}&from_date=${from}&to_date=${to}`);
        if(res.status!==200) return; presenceData={};
        for (const t of await res.json()) presenceData[t.institutionProfile.id]=t.dayTemplates||[];
        try{localStorage.setItem('ls_presence',JSON.stringify(presenceData));}catch(e){}
        renderWeek(); renderTodayWidget();
      } catch(e) {}
    }

    // ── Boot ──
    let pollTimer=null, sessionWasExpired=false;
    async function loadAll() {
      await initConfig();
      const valid=await checkSession();
      if (valid) {
        if (sessionWasExpired) { window.location.reload(); return; }
        await loadProfileConfig();
        loadCalendar(); loadPresence(); loadMessages(); loadOverview(); loadGoogleCalendar(); loadWeather(); loadRoutes();
        schedulePoll(5*60*1000);
      } else {
        sessionWasExpired = true;
        // Restore cached Aula data from localStorage
        try{const c=localStorage.getItem('ls_children');if(c){CHILDREN=JSON.parse(c);INST_PROFILE_IDS=JSON.parse(localStorage.getItem('ls_inst_ids')||'[]');
          document.getElementById('child-tabs').innerHTML=[...CHILDREN.map((c,i)=>`<div class="tab ${i===0?'active':''}" onclick="switchTab(${i})">${c.photoUrl?`<img src="${aulaImg(c.photoUrl)}" alt="${c.name}" onerror="this.style.display='none'">`:''}${c.name}</div>`),
          ...GOOGLE_TABS.map((g,i)=>`<div class="tab" onclick="switchGoogleTab(${i})" style="border-left:3px solid ${g.color}"><span style="color:${g.color}">📅</span> ${g.name}</div>`)].join('');}}catch(e){}
        try{const e=localStorage.getItem('ls_events');if(e){allEvents=JSON.parse(e);if(!Array.isArray(allEvents))allEvents=[];}}catch(e){}
        try{const p=localStorage.getItem('ls_presence');if(p){presenceData=JSON.parse(p)||{};}}catch(e){}
        try{const t=localStorage.getItem('ls_threads');if(t){cachedThreads=JSON.parse(t);if(!Array.isArray(cachedThreads))cachedThreads=[];renderMessages('messages-cal');}}catch(e){}
        try{const p=localStorage.getItem('ls_posts');if(p){window._cachedPosts=JSON.parse(p);if(!Array.isArray(window._cachedPosts))window._cachedPosts=[];renderSidebarOverview();renderOverviewPosts(window._cachedPosts);}}catch(e){}
        try{const d=localStorage.getItem('ls_dates');const b=localStorage.getItem('ls_bdays');if(d||b){renderOverviewEvents(d?JSON.parse(d):[],b?JSON.parse(b):[]);}}catch(e){}
        if(CHILDREN.length){renderWeek();renderTodayWidget();}
        loadGoogleCalendar(); loadWeather(); loadRoutes();
      }
      schedulePoll(5*60*1000);
    }
    // ── Event overlap layout ──────────────────────────────────────────────────
    function layoutEvents(events) {
      if (!events.length) return [];
      // Copy events to avoid mutating shared objects
      const evs = events.map(e => ({...e}));
      evs.forEach(e => {
        e._s = new Date(e.start||e.startDateTime).getTime();
        e._e = e.end||e.endDateTime ? new Date(e.end||e.endDateTime).getTime() : e._s + 3600000;
      });
      const sorted = evs.sort((a,b) => a._s - b._s);
      const colEnd = [];
      sorted.forEach(e => {
        let col = 0;
        while (col < colEnd.length && colEnd[col] > e._s) col++;
        e._col = col;
        colEnd[col] = e._e;
      });
      sorted.forEach(e => {
        const concurrent = sorted.filter(o => o._s < e._e && o._e > e._s);
        const maxCol = Math.max(...concurrent.map(o => o._col)) + 1;
        e._left  = (e._col / maxCol) * 100;
        e._width = 100 / maxCol;
      });
      return sorted;
    }

    function renderCalEvents(events, pctFn, isAula) {
      let html = '';
      layoutEvents(events).forEach(e => {
        const s = new Date(e.start||e.startDateTime);
        const en = e.end||e.endDateTime ? new Date(e.end||e.endDateTime) : new Date(s.getTime()+3600000);
        const cS = Math.max(s.getHours()*60+s.getMinutes(), START_H*60);
        const cE = Math.min(en.getHours()*60+en.getMinutes(), END_H*60);
        if (cS >= cE) return;
        const ts = s.toLocaleTimeString('da-DK',{hour:'2-digit',minute:'2-digit'})+'–'+en.toLocaleTimeString('da-DK',{hour:'2-digit',minute:'2-digit'});
        const l = (e._left||0).toFixed(1), w = (e._width||100).toFixed(1);
        const topPct = pctFn(cS), heightPct = Math.max(pctFn(cE)-pctFn(cS), 3);

        // Presence bars render differently — small indicators, not full events
        if (e._presence) {
          const clickAttr = e._tplData
            ? `onclick="(function(){const d=JSON.parse(this.dataset.tpl);openPresenceEdit(d.childId,d.date,d.entryTime,d.exitTime,d.exitWith,d.comment)}).call(this)" data-tpl='${e._tplData}'`
            : '';
          html += `<div class="presence-bar" ${clickAttr} style="top:${topPct}%;height:14px;min-height:14px;left:calc(2px + ${l}%);width:calc(${w}% - 4px);right:auto;cursor:pointer;${e._style}">${e._label}</div>`;
          return;
        }
        const title = e.title||'(ingen titel)';
        const color = e.color || 'var(--blue-accent)';
        const calStr = e.calendar || e.familieoverblik_calendars || '';
        const bgGradient = calEventBackground(calStr);
        const bgStyle = bgGradient ? `background:${bgGradient}` : `background:${color}`;
        const id = e.id ? `data-evid="${e.id}"` : '';
        const isCustom = e.custom ? 'data-custom="1"' : '';
        const calsAttr = e.calendar ? `data-calendar="${e.calendar}"` : '';
        const famCalAttr = `data-famcals="${e.familieoverblik_calendars || e.calendar || ''}"`;
        const descAttr = e.description ? `data-desc="${e.description.replace(/"/g,'&quot;').replace(/\n/g,'&#10;')}"` : '';
        const extra = { location: e.location||'', creator: e.creator||'', institution: e.institution||'', responseRequired: e.responseRequired||false, responseStatus: e.responseStatus||null, repeating: e.repeating||false, source: e.source||'' };
        const extraAttr = `data-extra='${JSON.stringify(extra).replace(/'/g,'&#39;')}'`;
        html += `<div class="cal-event" style="top:${topPct}%;height:${heightPct}%;min-height:20px;${bgStyle};left:calc(3px + ${l}%);width:calc(${w}% - 6px);right:auto" 
          ${id} ${isCustom} ${calsAttr} ${famCalAttr} ${descAttr} ${extraAttr} onclick="openEvInfo(this,event)"
          data-title="${title.replace(/"/g,'&quot;')}" data-time="${ts}" data-color="${color}">
          <span class="ev-title">${title}</span><span class="ev-time">${ts}</span></div>`;
      });
      return html;
    }

    function openEvInfo(elOrEvt, evt) {
      // Called either as openEvInfo(domEl, mouseEvt) from cal-events
      // or as openEvInfo(evtObj) from allday badges with a plain data object
      let title, time, color, isCustom, evId, desc, extra = {}, famCals = '';

      if (elOrEvt && elOrEvt.dataset) {
        // DOM element path
        if (evt) evt.stopPropagation();
        title    = elOrEvt.dataset.title;
        time     = elOrEvt.dataset.time;
        color    = elOrEvt.dataset.color;
        isCustom = elOrEvt.dataset.custom === '1';
        evId     = elOrEvt.dataset.evid;
        desc     = elOrEvt.dataset.desc || '';
        famCals  = elOrEvt.dataset.famcals || '';
        try { extra = JSON.parse(elOrEvt.dataset.extra || '{}'); } catch(e) {}
      } else {
        // Plain object path (from allday badge onclick)
        const d = elOrEvt;
        title    = d.title || '(ingen titel)';
        color    = d.color || 'var(--blue-accent)';
        isCustom = !!d.custom;
        evId     = d.id || '';
        desc     = d.description || '';
        famCals  = d.famcals || d.familieoverblik_calendars || d.calendar || '';
        if (d.allDay) {
          const fmt = s => s ? new Date(s+'T00:00:00').toLocaleDateString('da-DK',{weekday:'short',day:'numeric',month:'short'}) : '';
          time = 'Heldagsarrangement' + (d.start ? ' · ' + fmt(d.start) + (d.end && d.end !== d.start ? ' – ' + fmt(d.end) : '') : '');
        } else {
          const s = d.start ? new Date(d.start) : null;
          const e = d.end   ? new Date(d.end)   : null;
          const fmtT = dt => dt.toLocaleTimeString('da-DK',{hour:'2-digit',minute:'2-digit'});
          time = s ? (fmtT(s) + (e ? ' – ' + fmtT(e) : '')) : '';
        }
      }

      document.getElementById('ev-info-title').textContent = title;
      document.getElementById('ev-info-time').textContent  = time;
      const descEl = document.getElementById('ev-info-desc');
      if (desc) { descEl.textContent = desc; descEl.style.display = 'block'; }
      else { descEl.textContent = ''; descEl.style.display = 'none'; }

      const detailsEl = document.getElementById('ev-info-details');
      const rows = [];
      if (extra.location)    rows.push(`📍 ${extra.location}`);
      if (extra.creator)     rows.push(`👤 ${extra.creator}`);
      if (extra.institution) rows.push(`🏫 ${extra.institution}`);
      if (extra.repeating)   rows.push(`🔁 Gentages`);
      if (extra.responseRequired) {
        const status = extra.responseStatus === 'accepted' ? '✅ Accepteret'
          : extra.responseStatus === 'declined' ? '❌ Afvist' : '⏳ Afventer svar';
        rows.push(`📋 ${status}`);
      }
      detailsEl.innerHTML = rows.map(r => `<div style="padding:3px 0;font-size:0.8rem;color:#444">${r}</div>`).join('');
      detailsEl.style.display = rows.length ? 'block' : 'none';
      const cal = document.getElementById('ev-info-cal');
      cal.style.background = color; cal.textContent = isCustom ? '📌 Lokal begivenhed' : '📅 Kalender';

      // "Vises i" badges
      const famCalEl = document.getElementById('ev-info-famcals');
      if (famCalEl) famCalEl.remove();
      if (famCals) {
        const calLabels = calColorMap();
        const badges = famCals.split(',').filter(Boolean).map(cid => {
          const info = calLabels[cid] || { label: cid, color: '#888' };
          return `<span style="display:inline-block;padding:2px 8px;border-radius:10px;font-size:0.72rem;font-weight:700;color:#fff;background:${info.color};margin-right:4px">${info.label}</span>`;
        }).join('');
        const div = document.createElement('div');
        div.id = 'ev-info-famcals';
        div.style.cssText = 'margin-bottom:10px;margin-top:4px';
        div.innerHTML = '<div style="font-size:0.7rem;color:#aaa;margin-bottom:4px">Vises i</div>' + badges;
        cal.insertAdjacentElement('afterend', div);
      }

      const btns = document.getElementById('ev-info-btns');
      btns.innerHTML = '';

      if (isCustom && evId) {
        const calList = famCals ? famCals.split(',').filter(Boolean) : [];
        const calLabels2 = calColorMap();

        if (calList.length > 1) {
          // Multiple calendars — checkboxes inline, buttons below
          const label = document.createElement('div');
          label.style.cssText = 'font-size:0.75rem;font-weight:600;color:#555;margin-bottom:6px;width:100%';
          label.textContent = 'Fjern fra kalender';
          btns.appendChild(label);

          const optWrap = document.createElement('div');
          optWrap.style.cssText = 'display:flex;flex-wrap:wrap;gap:20px;padding:10px;background:#f8f9fa;border-radius:8px;justify-content:space-evenly;width:100%;margin-bottom:10px';
          calList.forEach(cid => {
            const info = calLabels2[cid] || { label: cid, color: '#888' };
            const lbl = document.createElement('label');
            lbl.style.cssText = 'display:flex;align-items:center;gap:6px;font-size:0.82rem;font-weight:600;cursor:pointer';
            lbl.innerHTML = `<input type="checkbox" class="del-cal-cb" data-calid="${cid}" checked style="accent-color:${info.color};width:15px;height:15px;flex-shrink:0"><span style="color:${info.color}">${info.label}</span>`;
            optWrap.appendChild(lbl);
          });
          btns.appendChild(optWrap);

          const delBtn = document.createElement('button');
          delBtn.className = 'btn-delete-ev';
          delBtn.textContent = '🗑️ Fjern valgte fra kalender';
          delBtn.onclick = async () => {
            const checked = [...optWrap.querySelectorAll('.del-cal-cb:checked')].map(cb => cb.dataset.calid);
            if (!checked.length) return;
            delBtn.disabled = true; delBtn.textContent = 'Fjerner...';
            for (const calId of checked) {
              await apiFetch(`/api/custom-events/${evId}?calendar=${calId}`, { method:'DELETE' });
            }
            document.getElementById('ev-info-overlay').classList.remove('open');
            loadGoogleCalendar();
          };
          btns.appendChild(delBtn);
          // Tilføj Luk eksplicit her for multi-kalender
          const closeBtnM = document.createElement('button');
          closeBtnM.className = 'btn-close-ev';
          closeBtnM.textContent = 'Luk';
          closeBtnM.onclick = () => document.getElementById('ev-info-overlay').classList.remove('open');
          btns.appendChild(closeBtnM);
          document.getElementById('ev-info-overlay').classList.add('open');
          return;
        } else {
          const delBtn = document.createElement('button');
          delBtn.className = 'btn-delete-ev';
          delBtn.style.cssText = 'flex:1';
          delBtn.textContent = '🗑️ Fjern fra kalender';
          delBtn.onclick = async () => {
            const calId = calList[0] || '';
            await apiFetch(`/api/custom-events/${evId}${calId ? '?calendar='+calId : ''}`, { method:'DELETE' });
            document.getElementById('ev-info-overlay').classList.remove('open');
            loadGoogleCalendar();
          };
          btns.appendChild(delBtn);
        }
      }
      const closeBtn = document.createElement('button');
      closeBtn.className = 'btn-close-ev';
      closeBtn.textContent = 'Luk';
      closeBtn.onclick = () => document.getElementById('ev-info-overlay').classList.remove('open');
      btns.appendChild(closeBtn);
      document.getElementById('ev-info-overlay').classList.add('open');
    }

    function onDayColClick(evt, col) {
      if (clLocked) return;  // børnelås
      // Ignore if clicking on an existing event
      if (evt.target.closest('.cal-event') || evt.target.closest('.presence-bar')) return;
      const dateStr = col.dataset.date;
      if (!dateStr) return;

      // Calculate clicked time from Y position
      const rect = col.getBoundingClientRect();
      const y = evt.clientY - rect.top;
      const totalH = col.offsetHeight;
      const totalMins = (END_H - START_H) * 60;
      const clickedMin = START_H * 60 + Math.round((y / totalH) * totalMins / 30) * 30;
      const h = Math.floor(clickedMin / 60), m = clickedMin % 60;
      const startStr = `${dateStr}T${String(h).padStart(2,'0')}:${String(m).padStart(2,'0')}`;
      const endH = Math.floor((clickedMin + 60) / 60), endM = (clickedMin + 60) % 60;
      const endStr = `${dateStr}T${String(endH).padStart(2,'0')}:${String(endM).padStart(2,'0')}`;

      // Open event modal pre-filled with time
      _eventText = '';
      document.getElementById('event-title').value = '';
      document.getElementById('event-start').value = startStr;
      document.getElementById('event-end').value = endStr;
      document.getElementById('event-start-date').value = dateStr;
      document.getElementById('event-end-date').value = dateStr;
      document.getElementById('event-allday').checked = false;
      toggleAllDay(false);

      // Render calendar options
      const calOpts = document.getElementById('event-cal-options');
      const calMap = calColorMap();
      const cals = Object.entries(calMap).map(([id, v]) => ({ id, ...v }));
      calOpts.innerHTML = cals.map(c =>
        `<label style="display:flex;align-items:center;gap:4px;font-size:0.8rem;cursor:pointer">
          <span style="background:${c.color};color:#fff;padding:2px 10px;border-radius:10px;font-size:0.72rem;white-space:nowrap">${c.label}</span>
          <input type="checkbox" class="cal-opt" id="${c.id}" style="accent-color:${c.color};width:15px;height:15px;flex-shrink:0">
        </label>`
      ).join('');

      const status = document.getElementById('event-parse-status');
      status.style.cssText = 'font-size:0.8rem;color:#555;background:#f0f4ff;padding:8px;border-radius:6px;margin-bottom:12px';
      status.textContent = `📅 Ny begivenhed ${new Date(startStr).toLocaleDateString('da-DK',{weekday:'long',day:'numeric',month:'long'})} kl. ${String(h).padStart(2,'0')}:${String(m).padStart(2,'0')}`;

      document.getElementById('event-modal-overlay').classList.add('open');
      // Auto-focus titel felt
      setTimeout(() => document.getElementById('event-title').focus(), 50);
    }

    function closeEvInfo(e) {
      if (!e || e.target === document.getElementById('ev-info-overlay'))
        document.getElementById('ev-info-overlay').classList.remove('open');
    }
    let _eventText = '';
    async function openEventModal(text) {
      if (clLocked) return;  // børnelås
      _eventText = text;
      document.getElementById('event-title').value = '';
      document.getElementById('event-start').value = '';
      document.getElementById('event-end').value = '';
      document.getElementById('event-start-date').value = '';
      document.getElementById('event-end-date').value = '';
      document.getElementById('event-allday').checked = false;
      toggleAllDay(false);
      const status = document.getElementById('event-parse-status');
      status.style.background = '#f0f4ff';
      status.style.color = '#555';
      status.textContent = '🔍 Søger efter dato og tidspunkt i teksten...';
      document.getElementById('event-modal-overlay').classList.add('open');

      // Render calendar options — children + Fælles + Vælg alle
      const calOpts = document.getElementById('event-cal-options');
      const calMap = calColorMap();
      const cals = Object.entries(calMap).map(([id, v]) => ({ id, ...v }));
      calOpts.innerHTML = cals.map(c =>
        `<label style="display:flex;align-items:center;gap:4px;font-size:0.8rem;cursor:pointer">
          <span style="background:${c.color};color:#fff;padding:2px 10px;border-radius:10px;font-size:0.72rem;white-space:nowrap">${c.label}</span>
          <input type="checkbox" class="cal-opt" id="${c.id}" style="accent-color:${c.color};width:15px;height:15px;flex-shrink:0">
        </label>`
      ).join('');

      try {
        const r = await apiFetch('/api/parse-event', { method:'POST',
          headers:{'Content-Type':'application/json'}, body: JSON.stringify({text}) });
        const d = await r.json();
        if (d.hasDate) {
          document.getElementById('event-title').value = d.title || '';
          if (d.allDay) {
            toggleAllDay(true);
            document.getElementById('event-allday').checked = true;
            document.getElementById('event-start-date').value = d.start ? d.start.substring(0,10) : '';
            document.getElementById('event-end-date').value   = d.end   ? d.end.substring(0,10)   : '';
          } else {
            document.getElementById('event-start').value = d.start ? d.start.substring(0,16) : '';
            document.getElementById('event-end').value   = d.end   ? d.end.substring(0,16)   : '';
          }
          status.style.background = '#f0fff4';
          status.style.color = '#276749';
          status.textContent = '✅ Dato fundet — ret hvis nødvendigt, vælg kalender og gem';
        } else {
          status.style.background = '#fff8e1';
          status.style.color = '#7c5800';
          status.textContent = '⚠️ Ingen dato fundet i teksten — udfyld manuelt';
        }
      } catch(e) {
        status.style.background = '#fff0f0';
        status.style.color = '#c00';
        status.textContent = '⚠️ Kunne ikke analysere tekst — udfyld manuelt';
      }
    }

    function toggleAllDay(allDay) {
      document.getElementById('event-time-fields').style.display = allDay ? 'none' : 'block';
      document.getElementById('event-date-fields').style.display = allDay ? 'block' : 'none';
    }

    function closeEventModal(e) {
      if (!e || e.target === document.getElementById('event-modal-overlay'))
        document.getElementById('event-modal-overlay').classList.remove('open');
    }

    function toggleAllCals(checked) {
      document.querySelectorAll('.cal-opt').forEach(cb => cb.checked = checked);
    }

    let _savingEvent = false;
    async function saveEventLocal() {
      if (_savingEvent) return;
      _savingEvent = true;
      const btn = document.querySelector('#event-modal .btn-save-local');
      if (btn) { btn.disabled = true; btn.textContent = 'Gemmer...'; }
      const title = document.getElementById('event-title').value.trim();
      const allDay = document.getElementById('event-allday').checked;
      const start = allDay
        ? document.getElementById('event-start-date').value
        : document.getElementById('event-start').value;
      const end = allDay
        ? document.getElementById('event-end-date').value || null
        : document.getElementById('event-end').value || null;
      if (!title || !start) {
        const s = document.getElementById('event-parse-status');
        s.textContent = '⚠️ Udfyld titel og startdato'; s.style.background = '#fff0f0'; s.style.color = '#c00';
        _savingEvent = false; if (btn) { btn.disabled = false; btn.textContent = '📌 Gem til Familieoverblik'; }
        return;
      }
      const selectedCals = [...document.querySelectorAll('.cal-opt:checked')].map(cb => cb.id);
      if (!selectedCals.length) {
        const s = document.getElementById('event-parse-status');
        s.textContent = '⚠️ Vælg mindst én kalender'; s.style.background = '#fff0f0'; s.style.color = '#c00';
        _savingEvent = false; if (btn) { btn.disabled = false; btn.textContent = '📌 Gem til Familieoverblik'; }
        return;
      }
      const colors = calColorMap();
      const calendarStr = selectedCals.join(',');
      const childCals = selectedCals.filter(c => c.startsWith('cal-child-'));
      const primaryId = childCals.length ? childCals[0] : selectedCals[0];
      const primaryColor = (colors[primaryId] || {color:'#7c3aed'}).color;
      const ac = new AbortController();
      const fetchTimeout = setTimeout(() => ac.abort(), 8000);
      try {
        await apiFetch('/api/custom-events', { method:'POST',
          signal: ac.signal,
          headers:{'Content-Type':'application/json'},
          body: JSON.stringify({ title, start, end, allDay, color: primaryColor,
            calendar: calendarStr, description: _eventText })
        });
      } catch(e) {}
      clearTimeout(fetchTimeout);
      // Show confirmation
      const startDate = new Date(allDay ? start + 'T00:00:00' : start);
      const fmt = startDate.toLocaleDateString('da-DK', {weekday:'short', day:'numeric', month:'short'});
      const time = allDay ? '' : ' kl. ' + startDate.toLocaleTimeString('da-DK', {hour:'2-digit', minute:'2-digit'});
      const status = document.getElementById('event-parse-status');
      status.style.cssText = 'font-size:1rem;font-weight:700;color:#fff;background:#2e7d32;padding:14px;border-radius:8px;text-align:center;margin-bottom:12px';
      status.textContent = `✅ Gemt — ${fmt}${time}`;
      _savingEvent = false;
      if (btn) { btn.disabled = false; btn.textContent = '📌 Gem til Familieoverblik'; }
      setTimeout(() => document.getElementById('event-modal-overlay').classList.remove('open'), 1200);
      loadGoogleCalendar();
    }

    function schedulePoll(ms) { clearTimeout(pollTimer); pollTimer=setTimeout(loadAll,ms); }
    setInterval(()=>{ if(document.querySelector('.now-line')) renderWeek(); },60000);
    // Auto-refresh Google calendar events every 5 min to pick up external deletions
    setInterval(() => loadGoogleCalendar(), 5 * 60 * 1000);
    // Reload config if settings were changed in another tab
    window.addEventListener('storage', e => {
      if (e.key === 'config_updated') initConfig();
    });
    clInit();
    loadAll().then(() => castInit());
    window._dashboardLoaded = true; // fase-0 testmarkør