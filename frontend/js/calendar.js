    function switchTab(idx) {
      activeTab = idx;
      activeGoogleTab = -1;
      document.querySelectorAll('#child-tabs .tab').forEach((t,i) => t.classList.toggle('active', i===idx));
      renderWeek();
    }
    function switchGoogleTab(idx) {
      activeGoogleTab = idx;
      const allTabs = document.querySelectorAll('#child-tabs .tab');
      allTabs.forEach((t,i) => t.classList.toggle('active', i === CHILDREN.length + idx));
      renderWeek();
    }
    function changeWeek(delta) { weekOffset += delta; loadCalendar(); loadPresence(); loadGoogleCalendar(); }

    // ── Today widget ──
    function renderTodayWidget() {
      const el = document.getElementById('today-widget');
      if (!el || !CHILDREN.length) return;
      const today = new Date();
      const todayStr = localDateStr(today);
      const cap = s => s ? s.charAt(0).toUpperCase() + s.slice(1) : s;
      let html = '';
      CHILDREN.forEach(child => {
        const tpl = (presenceData[child.id]||[]).find(t => t.byDate===todayStr);
        const dayEvents = allEvents.filter(e => e.start && (e.profiles||[]).includes(child.id) && isSameDay(new Date(e.start), today));
        let rows = '';
        if (tpl?.isOnVacation) {
          rows += `<div class="tc-row"><span style="font-size:.9rem">🏖️</span><span class="tc-label">Ferie/fri</span></div>`;
        } else {
          if (tpl?.entryTime) rows += `<div class="tc-row"><span style="font-size:.9rem">🧒🎒</span><span class="tc-time">${tpl.entryTime.substring(0,5)}</span><span class="tc-label">Aflevering</span></div>`;
          if (tpl?.exitTime) rows += `<div class="tc-row"><span style="font-size:.9rem">🏠</span><span class="tc-time">${tpl.exitTime.substring(0,5)}</span><span class="tc-label">${tpl.exitWith ? 'Hentes af '+tpl.exitWith : 'Hentning'}</span></div>`;
        }
        dayEvents.filter(e => !e.allDay).slice(0,2).forEach(e => {
          const t = new Date(e.start).toLocaleTimeString('da-DK',{hour:'2-digit',minute:'2-digit'});
          rows += `<div class="tc-row"><span style="font-size:.9rem">📌</span><span class="tc-time">${t}</span><span class="tc-label" style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:90px">${cap(e.title||'')}</span></div>`;
        });
        if (!rows) rows = `<div class="tc-row"><span class="tc-label" style="color:#ccc">Ingen data</span></div>`;
        html += `<div class="today-card"><div class="tc-name">${child.name} <span style="font-weight:400;color:#bbb;font-size:0.65rem">I dag</span></div>${rows}</div>`;
      });
      const todayGoogle = googleEvents.filter(e => isSameDay(e.allDay?new Date(e.start+'T00:00:00'):new Date(e.start), today));
      let famRows = todayGoogle.slice(0,4).map(e => {
        const t = e.allDay ? 'Hele dagen' : new Date(e.start).toLocaleTimeString('da-DK',{hour:'2-digit',minute:'2-digit'});
        return `<div class="tc-row"><span class="tc-dot" style="background:${e.color}"></span><span class="tc-time" style="min-width:56px">${t}</span><span class="tc-label" style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:100px">${cap(e.title)}</span></div>`;
      }).join('');
      if (!famRows) famRows = `<div class="tc-row"><span class="tc-label" style="color:#ccc">Ingen events</span></div>`;
      const famHeader = `<div class="tc-name">Familien <span style="font-weight:400;color:#bbb;font-size:0.65rem">I dag</span></div>`;
      html += `<div class="today-card">${famHeader}${famRows}</div>`;

      // Route cards — only on weekdays
      const isWeekday = today.getDay() >= 1 && today.getDay() <= 5;
      if (isWeekday && routeData.length) {
        const adultRoutes = routeData.filter(d => d.name !== 'Kragelundskolen');
        const kidRoutes = routeData.filter(d => d.name === 'Kragelundskolen');

        let famRouteRows = todayGoogle.slice(0,2).map(e => {
          const t = e.allDay ? 'Hele dagen' : new Date(e.start).toLocaleTimeString('da-DK',{hour:'2-digit',minute:'2-digit'});
          return `<div class="tc-row"><span class="tc-dot" style="background:${e.color}"></span><span class="tc-time" style="min-width:56px">${t}</span><span class="tc-label" style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:80px">${cap(e.title)}</span></div>`;
        }).join('');
        adultRoutes.forEach(dest => {
          const m = dest.modes[dest.default];
          if (m) famRouteRows += `<div class="tc-row"><span style="font-size:.85rem">${ROUTE_MODE_LABELS[dest.default]}</span><span class="tc-time">${m.duration}min</span><span class="tc-label">${m.distance}km → ${dest.name}</span></div>`;
        });
        if (!famRouteRows) famRouteRows = `<div class="tc-row"><span class="tc-label" style="color:#ccc">Ingen events</span></div>`;

        // Replace familien card
        html = html.replace(`<div class="today-card">${famHeader}${famRows}</div>`,
          `<div class="today-card">${famHeader}${famRouteRows}</div>`);

        // Add kid route to each child card
        if (kidRoutes.length) {
          const kidRoute = kidRoutes[0];
          const m = kidRoute.modes[kidRoute.default];
          if (m) {
            const kidRow = `<div class="tc-row"><span style="font-size:.85rem">${ROUTE_MODE_LABELS[kidRoute.default]}</span><span class="tc-time">${m.duration}min</span><span class="tc-label">${kidRoute.name}</span></div>`;
            const childNames = CHILDREN.map(c => c.name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|');
            const re = new RegExp(`(<div class="today-card"><div class="tc-name">(${childNames})[\\s\\S]*?<\\/div>)([\\s\\S]*?)(<\\/div>)(?=\\s*<div class="today-card">|$)`, 'g');
            html = html.replace(re, (match, p1, name, content, p4) => p1 + content + kidRow + p4);
          }
        }
      }

      el.innerHTML = html;
    }

    // ── Overview ──
    async function loadOverview() {
      const ids = getChildIds();
      const [postsData, datesData, bdayData] = await Promise.all([
        apiFetch(`/api/posts?inst_profile_ids=${ids}`).then(r => r.json()).catch(() => ({})),
        apiFetch(`/api/important-dates?inst_profile_ids=${ids}`).then(r => r.json()).catch(() => []),
        apiFetch(`/api/birthdays?inst_profile_ids=${ids}`).then(r => r.json()).catch(() => []),
      ]);
      try{localStorage.setItem('ls_dates',JSON.stringify(datesData));}catch(e){}
      try{localStorage.setItem('ls_bdays',JSON.stringify(bdayData));}catch(e){}
      renderOverviewEvents(datesData, bdayData);
      renderOverviewPosts(postsData.posts || []);
    }

    function renderOverviewEvents(dates, birthdays) {
      const el = document.getElementById('overview-events');
      const all = [
        ...(dates || []).map(d => ({ type: 'event', date: new Date(d.startDateTime || d.start), data: d })),
        ...(birthdays || []).map(b => {
          const raw = new Date(b.birthday);
          const today = new Date();
          let date = new Date(today.getFullYear(), raw.getMonth(), raw.getDate());
          if (date < today && !isSameDay(date, today)) date.setFullYear(today.getFullYear() + 1);
          return { type: 'birthday', date, data: b };
        }),
      ].sort((a, b) => a.date - b.date);

      el.innerHTML = all.length ? all.map(({ type, date, data: d }) => {
        if (type === 'event') {
          const label = date.toLocaleDateString('da-DK', {weekday:'short', day:'numeric', month:'short'});
          const avatars = CHILDREN.filter(c => (d.profiles||d.belongsToProfiles||[]).includes(c.id)).map(c =>
            c._photoUrl ? `<img src="${aulaImg(c._photoUrl)}" style="width:20px;height:20px;border-radius:50%;object-fit:cover;border:1px solid #cce4f7;margin-right:2px">` : ''
          ).join('');
          return `<div class="event-item"><div class="event-date">${label}</div>
            <div style="flex:1"><div class="event-title">${d.title||'(ingen titel)'}</div>
            <div class="event-sub">${avatars}${d.institutionName||''}</div></div></div>`;
        } else {
          const label = date.toLocaleDateString('da-DK', {day:'numeric', month:'short'});
          const avatars = (d.relatedChildrenIds||[]).map(id => {
            const c = CHILDREN.find(c => c.id === id);
            return c?._photoUrl ? `<img src="${aulaImg(c._photoUrl)}" style="width:20px;height:20px;border-radius:50%;object-fit:cover;border:1px solid #cce4f7;margin-right:2px">` : '';
          }).join('');
          return `<div class="event-item"><div class="event-date birthday">🎂 ${label}</div>
            <div style="flex:1"><div class="event-title">${d.name}</div>
            <div class="event-sub">${avatars}${d.mainGroupName||''}</div></div></div>`;
        }
      }).join('') : '<span class="loading">Ingen kommende datoer</span>';
    }

    function renderOverviewPosts(posts) {
      const el = document.getElementById('overview-posts');
      if (!posts.length) { el.innerHTML = '<span class="loading">Ingen opslag</span>'; return; }
      const seenTs = new Date(getSeen().overview || 0);
      el.innerHTML = posts.map(p => {
        const isNew = new Date(p.timestamp) > seenTs;
        const thumb = p.attachments?.[0]?.media?.largeThumbnailUrl || p.attachments?.[0]?.media?.thumbnailUrl || '';
        const date = new Date(p.timestamp).toLocaleDateString('da-DK', {day:'numeric', month:'short', year:'numeric'});
        const preview = (p.content?.html||'').replace(/<[^>]+>/g,'').trim().substring(0, 120);
        const important = p.isImportant ? '<span class="post-important">⚠️ Vigtigt</span>' : '';
        const thumbHtml = thumb ? `<img class="post-thumb" src="${thumb}" loading="lazy" onerror="this.style.display='none'">` : `<div class="post-thumb-placeholder">📰</div>`;
        return `<div class="post-item${isNew?' unread':''}" onclick="openPost(${p.id})">${thumbHtml}
          <div class="post-body">${important}
            <div class="post-title">${isNew?'🔴 ':''}${p.title||'(ingen titel)'}</div>
            <div class="post-meta">${p.ownerProfile?.fullName||''} · ${date}${p.commentCount ? ' · 💬 '+p.commentCount : ''}</div>
            <div class="post-preview">${preview}</div>
          </div></div>`;
      }).join('');
      window._cachedPosts = posts; try{localStorage.setItem('ls_posts',JSON.stringify(posts));}catch(e){}
      renderSidebarOverview();
      if (currentView !== 'overview') updateBadges();
    }

    function renderSidebarOverview() {
      const el = document.getElementById('sidebar-overview');
      if (!el) return;
      const posts = (window._cachedPosts || []).slice(0, 3);
      if (!posts.length) { el.innerHTML = '<span class="loading">Ingen opslag</span>'; return; }
      el.innerHTML = posts.map(p => {
        const date = new Date(p.timestamp).toLocaleDateString('da-DK', {day:'numeric', month:'short'});
        const important = p.isImportant ? '⚠️ ' : '';
        return `<div class="msg-item" onclick="openPost(${p.id})" style="cursor:pointer">
          <div class="subject">${important}${p.title||'(ingen titel)'}</div>
          <div class="meta">${p.ownerProfile?.fullName||''} · ${date}</div>
        </div>`;
      }).join('');
    }

    function openPost(postId) {
      const p = (window._cachedPosts||[]).find(x => x.id === postId); if (!p) return;

      // Mark as read — update seen timestamp and remove unread styling
      const seen = getSeen();
      const postTs = new Date(p.timestamp).getTime();
      if (!seen.overview || postTs > seen.overview) {
        setSeen('overview', postTs);
      }
      // Remove unread dot from this post item
      const postEl = document.querySelector(`.post-item[onclick="openPost(${postId})"]`);
      if (postEl) {
        postEl.classList.remove('unread');
        const titleEl = postEl.querySelector('.post-title');
        if (titleEl) titleEl.textContent = titleEl.textContent.replace('🔴 ', '');
      }
      document.getElementById('post-modal-title').textContent = p.title||'(ingen titel)';
      const date = new Date(p.timestamp).toLocaleString('da-DK', {day:'numeric',month:'short',year:'numeric',hour:'2-digit',minute:'2-digit'});
      document.getElementById('post-modal-meta').textContent = `${p.ownerProfile?.fullName||''} · ${date}`;
      document.getElementById('post-modal-body').innerHTML = p.content?.html || p.content?.text || '(intet indhold)';
      const plainText = (p.content?.html||p.content?.text||'').replace(/<[^>]*>/g,' ').replace(/\s+/g,' ').trim();
      const btnId = 'parse-btn-' + postId;
      document.getElementById('post-modal-body').innerHTML += `<div style="margin-top:12px"><button class="parse-event-btn" id="${btnId}">📅 Tilføj til kalender</button></div>`;
      document.getElementById(btnId).addEventListener('click', e => { e.stopPropagation(); openEventModal(plainText); });
      document.getElementById('post-modal-attachments').innerHTML = renderAttachments(p.attachments || []);
      document.getElementById('post-modal-overlay').classList.add('open');
    }
    // ── Børnelås ──────────────────────────────────────────────────────────────
    const CL_KEY = 'childlock_pin_hash';
    let clLocked = false, clLockPin = '', clInactivityTimer = null;

    function clHash(pin) {
      let h = 5381;
      for (const c of pin) h = ((h << 5) + h) + c.charCodeAt(0);
      return (h >>> 0).toString(16);
    }

    function clUpdateBtn() {
      const stored = localStorage.getItem(CL_KEY);
      const btn = document.getElementById('lock-btn');
      const settingsLink = document.getElementById('settings-link');
      if (!stored) { btn.style.display = 'none'; return; }
      btn.style.display = 'inline';
      btn.textContent = clLocked ? '🔒' : '🔓';
      btn.title = clLocked ? 'Låst — klik for at låse op' : 'Klik for at aktivere børnelås';
      if (settingsLink) settingsLink.style.display = clLocked ? 'none' : '';
    }

    function clApplyLock(locked) {
      clLocked = locked;
      document.body.classList.toggle('child-locked', locked);
      // PIN dialog only shown when unlocking — not when locking
      if (!locked) document.getElementById('lock-overlay').classList.remove('open');
      clUpdateBtn();
      if (locked) clResetInactivity();
    }

    function clLockBtnClick() {
      if (!localStorage.getItem(CL_KEY)) return;
      if (clLocked) {
        // Show PIN dialog to unlock
        clLockPin = '';
        for (let i=0;i<4;i++) document.getElementById('ld'+i).classList.remove('filled');
        document.getElementById('lock-msg').textContent = '';
        document.getElementById('lock-overlay').classList.add('open');
      } else {
        clApplyLock(true);
      }
    }

    function clLockCancel() {
      document.getElementById('lock-overlay').classList.remove('open');
      clLockPin = '';
      for (let i=0;i<4;i++) document.getElementById('ld'+i).classList.remove('filled');
      document.getElementById('lock-msg').textContent = '';
    }

    // PIN input for unlock overlay
    function clLockNum(n) {
      if (clLockPin.length >= 4) return;
      clLockPin += n;
      for (let i=0;i<4;i++) document.getElementById('ld'+i).classList.toggle('filled', i < clLockPin.length);
      if (clLockPin.length === 4) setTimeout(clLockSubmit, 150);
    }
    function clLockDel() {
      if (clLockPin.length) { clLockPin = clLockPin.slice(0,-1); }
      for (let i=0;i<4;i++) document.getElementById('ld'+i).classList.toggle('filled', i < clLockPin.length);
    }
    function clLockSubmit() {
      const stored = localStorage.getItem(CL_KEY);
      if (clHash(clLockPin) === stored) {
        clLockPin = '';
        for (let i=0;i<4;i++) document.getElementById('ld'+i).classList.remove('filled');
        document.getElementById('lock-msg').textContent = '';
        clApplyLock(false);
      } else {
        document.getElementById('lock-msg').textContent = '❌ Forkert PIN';
        clLockPin = '';
        for (let i=0;i<4;i++) document.getElementById('ld'+i).classList.remove('filled');
      }
    }

    // Auto-lock after 5 min inactivity
    function clResetInactivity() {
      clearTimeout(clInactivityTimer);
      if (!localStorage.getItem(CL_KEY)) return;
      clInactivityTimer = setTimeout(() => { if (!clLocked) clApplyLock(true); }, 5 * 60 * 1000);
    }
    ['click','touchstart','mousemove','keydown'].forEach(e =>
      document.addEventListener(e, () => { if (!clLocked) clResetInactivity(); }, { passive: true })
    );

    // Init on load
    function clInit() {
      const stored = localStorage.getItem(CL_KEY);
      if (stored) {
        clApplyLock(true);  // start locked if PIN is set
      }
      clUpdateBtn();
    }
    // ──────────────────────────────────────────────────────────────────────────

    function openLightboxUrl(url) {
      lightboxItems = [{url, thumbUrl: url, isVideo: url.match(/\.(mov|mp4|webm)/i), title:''}];
      lightboxIdx = 0; showLightboxItem(); document.getElementById('lightbox').classList.add('open');
    }

    // ── File helpers ──
    const FILE_ICONS = { pdf:'📄', doc:'📝', docx:'📝', xls:'📊', xlsx:'📊', ppt:'📋', pptx:'📋', txt:'📃', zip:'🗜️', default:'📎' };
    function fileIcon(name) {
      const ext = (name||'').split('.').pop().toLowerCase();
      return FILE_ICONS[ext] || FILE_ICONS.default;
    }
    function proxyUrl(url) {
      return `/api/file-proxy?url=${encodeURIComponent(url)}`;
    }
    function openFileModal(fileUrl, name) {
      const proxy = proxyUrl(fileUrl);
      document.getElementById('file-modal-title').textContent = name || 'Fil';
      document.getElementById('file-modal-dl').href = proxy;
      document.getElementById('file-modal-dl').download = name || 'fil';
      document.getElementById('file-modal-frame').src = proxy;
      document.getElementById('file-modal-overlay').classList.add('open');
    }
    function closeFileModal(e) {
      if (!e || e.target === document.getElementById('file-modal-overlay') || e.target === document.getElementById('file-modal-close')) {
        document.getElementById('file-modal-frame').src = '';
        document.getElementById('file-modal-overlay').classList.remove('open');
      }
    }
    function renderAttachments(attachments) {
      if (!attachments?.length) return '';
      return attachments.map(a => {
        // Image/video with thumbnail → lightbox
        if (a.media?.thumbnailUrl || a.media?.largeThumbnailUrl) {
          const thumb = a.media.largeThumbnailUrl || a.media.thumbnailUrl;
          const full  = a.media.file?.url || thumb;
          return `<img src="${thumb}" loading="lazy" onclick="openLightboxUrl('${full}')" style="width:120px;height:120px;object-fit:cover;border-radius:8px;cursor:pointer;flex-shrink:0">`;
        }
        // File attachment — check both a.file.url and a.media.file.url
        const fileUrl = a.file?.url || a.media?.file?.url || a.url || '';
        const name = a.file?.name || a.name || a.media?.file?.name || fileUrl.split('/').pop().split('?')[0] || 'Fil';
        if (!fileUrl) return '';
        const safeName = name.replace(/'/g, "\\'");
        return `<div class="file-card" onclick="openFileModal('${fileUrl}','${safeName}')"><span class="file-icon">${fileIcon(name)}</span><span class="file-name">${name}</span></div>`;
      }).join('');
    }
    function closePostModal(e) {
      if (!e || e.target===document.getElementById('post-modal-overlay') || e.target===document.getElementById('post-modal-close'))
        document.getElementById('post-modal-overlay').classList.remove('open');
    }

    // ── Timetable ──
    function renderWeek() {
      if (!CHILDREN.length) return;
      window._evRegistry = [];  // reset event registry for allday badge clicks
      const days = getWeekDays(), today = new Date();
      document.getElementById('week-nr').textContent = getWeekNr(days[0]);
      const hourH = parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--hour-h')) || 52;
      const totalH = HOURS * hourH;

      // Determine active google filter
      const gTab = activeGoogleTab >= 0 ? GOOGLE_TABS[activeGoogleTab] : null;

      let html = `<div class="th-spacer"></div>`;
      days.forEach((day,i) => {
        const isToday = isSameDay(day,today);
        // Collect all-day events for this day to show in header
        const dayAllDay = gTab
          ? googleEvents.filter(e => {
              if (!e.allDay) return false;
              const start = new Date(e.start + 'T00:00:00');
              const endRaw = e.end && e.end !== e.start ? e.end : e.start;
              const end = new Date(endRaw + 'T00:00:00');
              const dayStart = new Date(day.getFullYear(), day.getMonth(), day.getDate());
              // ICS all-day DTEND is exclusive — use < for end comparison
              return dayStart >= start && dayStart < end;
            })
          : allEvents.filter(e => {
              if (!e.allDay) return false;
              if (!(e.profiles||[]).includes(CHILDREN[activeTab]?.id)) return false;
              return e.start && isSameDay(new Date(e.start.substring(0,10)+'T00:00:00'), day);
            }).concat(googleEvents.filter(e => {
              if (!e.allDay || !e.custom) return false;
              const calId = 'cal-child-' + CHILDREN[activeTab]?.id;
              if (!(e.calendar || '').split(',').includes(calId)) return false;
              const start = new Date(e.start + 'T00:00:00');
              const endRaw = e.end && e.end !== e.start ? e.end : e.start;
              const end = new Date(endRaw + 'T00:00:00');
              const dayStart = new Date(day.getFullYear(), day.getMonth(), day.getDate());
              return dayStart >= start && dayStart < end;
            }));
        const allDayBadges = dayAllDay.map(e => {
          const idx = window._evRegistry.push({
            title: e.title || e.summary || '(ingen titel)',
            start: e.start || '',
            end: e.end || '',
            allDay: true,
            color: e.color || '',
            description: e.description || e.content || '',
            custom: !!e.custom,
            id: e.id || '',
            famcals: e.familieoverblik_calendars || e.calendar || '',
          }) - 1;
          const calStr = e.familieoverblik_calendars || e.calendar || '';
          const bgGrad = calEventBackground(calStr);
          const bgStyle = bgGrad ? bgGrad : (e.color || 'var(--blue-accent)');
          return `<div onclick="event.stopPropagation();openEvInfo(window._evRegistry[${idx}])" style="font-size:0.6rem;font-weight:700;
            background:${bgStyle};color:#fff;border-radius:3px;
            padding:1px 5px;margin-top:2px;white-space:nowrap;cursor:pointer;
            overflow:hidden;text-overflow:ellipsis;">${e.title || e.summary || '(ingen titel)'}</div>`;
        }).join('');
        // Weather — header strip (same style for all days)
        let weatherStrip = '';
        if (weatherData.length) {
          const dayHours = weatherData.filter(w => isSameDay(new Date(w.time), day));
          if (dayHours.length) {
            const midday = dayHours.find(w => new Date(w.time).getHours() === 12) || dayHours[Math.floor(dayHours.length/2)];
            const minT = Math.round(Math.min(...dayHours.map(w => w.temp)));
            const maxT = Math.round(Math.max(...dayHours.map(w => w.temp)));
            const avgWind = Math.round(dayHours.reduce((s,w) => s+w.wind, 0) / dayHours.length * 10) / 10;
            const midWind = midday.wind_dir !== undefined ? windArrow(midday.wind_dir) : '';
            weatherStrip = `<div style="font-size:0.62rem;color:#555;margin-top:3px;text-align:center;line-height:1.4">
              ${weatherIcon(midday.symbol)} ${maxT}° <span style="color:#999">(${minT}°)</span><br>
              <span style="color:#888">${midWind}${avgWind}m/s</span>
            </div>`;
          }
        }
        html += `<div class="day-header ${isToday?'today':''} ${(day.getDay()===0||day.getDay()===6)?'weekend':''}" style="min-height:48px">
          ${DAY_NAMES[i]}<br><span class="date-num">${day.getDate()}</span>
          ${weatherStrip}
          <div class="allday-badges">${allDayBadges}</div>
        </div>`;
      });
      html += `<div class="time-gutter" style="height:${totalH}px;grid-row:2">`;
      for (let h=START_H; h<=END_H; h++) html += `<div class="hour-label" style="top:${(h-START_H)*hourH}px">${String(h).padStart(2,'0')}:00</div>`;
      html += `</div>`;

      days.forEach((day,i) => {
        const isToday = isSameDay(day,today), dateStr = `${day.getFullYear()}-${String(day.getMonth()+1).padStart(2,'0')}-${String(day.getDate()).padStart(2,'0')}`;
        const isWeekend = day.getDay() === 0 || day.getDay() === 6;
        html += `<div class="day-col ${isToday?'today':''} ${isWeekend?'weekend':''}" style="height:${totalH}px;grid-row:2" data-date="${dateStr}" onclick="onDayColClick(event, this)">`;
        for (let h=START_H; h<=END_H; h++) {
          html += `<div class="hour-line full" style="top:${(h-START_H)*hourH}px"></div>`;
          if (h<END_H) html += `<div class="hour-line" style="top:${(h-START_H)*hourH+hourH/2}px;border-top-style:dashed;opacity:.5"></div>`;
        }

        // Weather — hour-by-hour for today in timetable
        if (isToday && weatherData.length) {
          const todayHours = weatherData.filter(w => isSameDay(new Date(w.time), day));
          todayHours.forEach(w => {
            const h = new Date(w.time).getHours();
            if (h < START_H || h >= END_H) return;
            const icon = weatherIcon(w.symbol);
            if (!icon) return;
            const bottom = 100 - pct((h + 1) * 60);
            html += `<div style="position:absolute;bottom:${bottom}%;right:1px;font-size:0.58rem;color:#aaa;
              pointer-events:none;z-index:1;white-space:nowrap;line-height:1.2;text-align:right">
              ${icon}${w.temp}° ${windArrow(w.wind_dir)}${w.wind}</div>`;
          });
        }

        if (gTab) {
          const filtered = googleEvents.filter(e => {
            const d = e.allDay ? new Date(e.start + 'T00:00:00') : new Date(e.start);
            if (!isSameDay(d, day)) return false;
            if (e.custom) {
              return (e.calendar || '').split(',').includes('cal-faelles');
            }
            return gTab.owner === null || e.owner === gTab.owner;
          });
          // Google/custom events on google tab
          const timed = filtered.filter(e => !e.allDay);
          html += renderCalEvents(timed, pct, false);
        } else {
          // ── Aula child tab — same logic as gTab but filtered by child ──
          const child = CHILDREN[activeTab];
          const tabColor = childColor(activeTab);
          const childPresence = presenceData[child.id] || [];
          const tpl = childPresence.find(t => t.byDate===dateStr);
          const presenceEvents = [];
          if (tpl && !tpl.isOnVacation) {
            const ds = dateStr;
            // Data til edit-modal — JSON-encoded som attribut
            const tplData = JSON.stringify({
              childId:   child.id,
              date:      ds,
              entryTime: tpl.entryTime || '',
              exitTime:  tpl.exitTime  || '',
              exitWith:  tpl.exitWith  || '',
              comment:   tpl.comment   || '',
            }).replace(/'/g, '&#39;');
            if (tpl.entryTime) presenceEvents.push({
              _presence: true, _label: `🧒🎒 ${tpl.entryTime.substring(0,5)}`, _style: `border-left-color:${tabColor};color:${tabColor}`,
              start: `${ds}T${tpl.entryTime}`, end: `${ds}T${tpl.entryTime.replace(/(\d+):(\d+)/,(_,h,m)=>String(parseInt(h)*60+parseInt(m)+30).replace(/(\d+)/,n=>String(Math.floor(n/60)).padStart(2,'0')+':'+String(n%60).padStart(2,'0')))}`,
              _tplData: tplData,
            });
            if (tpl.exitTime) presenceEvents.push({
              _presence: true, _label: `🏠 ${tpl.exitTime.substring(0,5)}${tpl.exitWith?' · '+tpl.exitWith:''}`, _style: `border-left-color:${tabColor};color:${tabColor}`,
              start: `${ds}T${tpl.exitTime}`, end: null,
              _tplData: tplData,
            });
          }

          // All events for this child — aula + custom + presence — in one layout pass
          const childEvents = [
            ...presenceEvents,
            ...allEvents.filter(e => !e.allDay && (e.profiles||[]).includes(child.id) && isSameDay(new Date(e.start), day)),
            ...googleEvents.filter(e => e.custom && !e.allDay && isSameDay(new Date(e.start), day) && (e.calendar || '').split(',').includes('cal-child-' + child.id)),
          ];
          html += renderCalEvents(childEvents, pct, true);
        }

        if (isToday) { const nm=new Date().getHours()*60+new Date().getMinutes(); if(nm>=START_H*60&&nm<=END_H*60) html+=`<div class="now-line" style="top:${pct(nm)}%"></div>`; }
        html += `</div>`;
      });
      document.getElementById('timetable').innerHTML = html;
      const wrap = document.querySelector('.timetable-wrap');
      const now = new Date();
      wrap.style.maxHeight = (hourH * 10) + 'px';
      if (!wrap.dataset.scrolled) {
        const scrollToHour = days.some(d => isSameDay(d, now)) ? Math.max(0, now.getHours() - 1) : 7;
        wrap.scrollTop = scrollToHour * hourH;
        wrap.dataset.scrolled = '1';
      }
    }
