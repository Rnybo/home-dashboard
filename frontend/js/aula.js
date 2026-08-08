    const SEEN_KEY = 'aula_seen';
    function getSeen() { try { return JSON.parse(localStorage.getItem(SEEN_KEY)||'{}'); } catch { return {}; } }
    function setSeen(key, val) { const s=getSeen(); s[key]=val; localStorage.setItem(SEEN_KEY, JSON.stringify(s)); }
    function setBadge(viewId, count) {
      const idx = VIEWS.indexOf(viewId);
      // Bottom nav badge
      const botBtns = document.querySelectorAll('.bottom-nav button');
      if (botBtns[idx]) {
        botBtns[idx].querySelector('.badge')?.remove();
        if (count > 0) { const b=document.createElement('span'); b.className='badge'; b.textContent=count>9?'9+':count; botBtns[idx].appendChild(b); }
      }
      // Top nav — Aula button gets combined badge for overview+gallery+msg
      if (AULA_VIEWS.includes(viewId)) {
        const aulaBtn = document.getElementById('aula-nav-btn');
        if (!aulaBtn) return;
        // Store count per view
        if (!aulaBtn._badges) aulaBtn._badges = {};
        if (count === 0) delete aulaBtn._badges[viewId];
        else aulaBtn._badges[viewId] = count;
        const total = Object.values(aulaBtn._badges).reduce((a,b) => a+b, 0);
        aulaBtn.querySelector('.badge')?.remove();
        if (total > 0) { const b=document.createElement('span'); b.className='badge'; b.textContent=total>9?'9+':total; aulaBtn.appendChild(b); }
        // Update dropdown item dot indicators (data-view, not onclick-string parsing)
        document.querySelectorAll('.aula-dd-item').forEach(item => {
          const v = item.dataset.view;
          item.querySelector('.dd-badge')?.remove();
          if (v && aulaBtn._badges?.[v] > 0) {
            const dot = document.createElement('span');
            dot.className = 'dd-badge';
            dot.style.cssText = 'display:inline-block;width:8px;height:8px;border-radius:50%;background:#e53935;margin-left:6px;vertical-align:middle;flex-shrink:0';
            item.appendChild(dot);
          }
        });
      }
    }
    function updateBadges() {
      const seen = getSeen();
      setBadge('msg', cachedThreads.filter(t => !t.read).length);
      const newPosts = (window._cachedPosts||[]).filter(p => new Date(p.timestamp) > new Date(seen.overview||0)).length;
      setBadge('overview', newPosts);
    }

    // ── Messages ──
    let cachedThreads = [];
    async function loadMessages() {
      try { const res=await apiFetch('/api/messages'); if(res.status===401) return; cachedThreads=await res.json(); try{localStorage.setItem('ls_threads',JSON.stringify(cachedThreads.slice(0,5)));}catch(e){} renderMessages('messages-cal'); updateBadges(); } catch(e) {}
    }
    function syncMessagesFull() { renderMessages('messages-full'); }
    function renderMessages(elId) {
      const el=document.getElementById(elId);
      if (!cachedThreads.length) { el.textContent='Ingen beskeder'; return; }
      const limit = elId === 'messages-cal' ? 1 : 20;
      el.innerHTML=cachedThreads.slice(0,limit).map(t => `
        <div class="msg-item ${t.read?'':'unread'}" onclick="openMsg(${t.id},'${(t.subject||'').replace(/'/g,"\\'")}')">
          <div class="subject">${t.read?'':' 🔴 '}${t.subject||'(ingen emne)'}</div>
          <div class="meta">${t.read?'✓ Læst':'● Ulæst'}</div>
        </div>`).join('') + (elId === 'messages-cal' ? `<div class="sidebar-more-link" onclick="switchAulaView('msg')">Se alle beskeder →</div>` : '');
    }
    function openGoogleEvent(idx) {
      const e = _upcomingEvents[idx]; if (!e) return;
      document.getElementById('gevent-modal-color').style.background = e.color;
      document.getElementById('gevent-modal-title').textContent = e.title;
      const d = e._date;
      let when;
      if (e.allDay) {
        const endDate = new Date(e.end + 'T00:00:00'); endDate.setDate(endDate.getDate() - 1);
        const s = d.toLocaleDateString('da-DK', {weekday:'long', day:'numeric', month:'long'});
        const en = endDate.toLocaleDateString('da-DK', {weekday:'long', day:'numeric', month:'long'});
        when = isSameDay(d, endDate) ? s : `${s} – ${en}`;
      } else {
        const day = d.toLocaleDateString('da-DK', {weekday:'long', day:'numeric', month:'long'});
        const t1 = d.toLocaleTimeString('da-DK', {hour:'2-digit', minute:'2-digit'});
        const t2 = new Date(e.end).toLocaleTimeString('da-DK', {hour:'2-digit', minute:'2-digit'});
        when = `${day}, ${t1}–${t2}`;
      }
      document.getElementById('gevent-modal-when').textContent = '🕐 ' + when;
      document.getElementById('gevent-modal-owner').textContent = e.owner !== 'Helligdag' ? '👤 ' + e.owner : '';
      document.getElementById('gevent-modal-location').textContent = e.location ? '📍 ' + e.location : '';
      document.getElementById('gevent-modal-overlay').classList.add('open');
    }
    function closeGEventModal(ev) {
      if (!ev || ev.target === document.getElementById('gevent-modal-overlay') || ev.target === document.getElementById('gevent-modal-close'))
        document.getElementById('gevent-modal-overlay').classList.remove('open');
    }
    let _upcomingEvents = [];
    function renderUpcomingGoogleEvents() {
      const el = document.getElementById('upcoming-google-cal');
      if (!el) return;
      const now = new Date();
      const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
      const seen = new Set();
      _upcomingEvents = googleEvents
        .filter(e => e.owner !== 'Helligdag')
        .map(e => ({ ...e, _date: e.allDay ? new Date(e.start + 'T00:00:00') : new Date(e.start) }))
        .filter(e => e.allDay ? e._date >= today : e._date >= now)
        .filter(e => { const k=e.title+'|'+e.start; if(seen.has(k)) return false; seen.add(k); return true; })
        .sort((a,b) => a._date - b._date)
        .slice(0, 5);
      if (!_upcomingEvents.length) { el.innerHTML = '<span class="loading">Ingen kommende</span>'; return; }
      el.innerHTML = _upcomingEvents.map((e, idx) => {
        const d = e._date;
        const dot = `<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${e.color};margin-right:5px;flex-shrink:0"></span>`;
        let label;
        if (e.allDay) {
          const endDate = new Date(e.end + 'T00:00:00'); endDate.setDate(endDate.getDate() - 1);
          const s = d.toLocaleDateString('da-DK', {day:'numeric', month:'short'});
          const en = endDate.toLocaleDateString('da-DK', {day:'numeric', month:'short'});
          label = isSameDay(d, endDate) ? s : `${s}–${en}`;
        } else {
          label = d.toLocaleDateString('da-DK', {weekday:'short', day:'numeric', month:'short'})
            + ' · ' + d.toLocaleTimeString('da-DK', {hour:'2-digit', minute:'2-digit'});
        }
        return `<div class="msg-item" onclick="openGoogleEvent(${idx})" style="cursor:pointer">
          <div class="subject" style="display:flex;align-items:center">${dot}${e.title}</div>
          <div class="meta">${label}</div>
        </div>`;
      }).join('');
    }
    async function openMsg(threadId, subject) {
      document.getElementById('msg-modal-subject').textContent=subject;
      document.getElementById('msg-modal-body').textContent='Henter...';
      document.getElementById('msg-modal-meta').textContent='';
      document.getElementById('msg-modal-overlay').classList.add('open');
      try {
        const cacheKey='ls_msg_'+threadId;
        let data;
        try { data=await apiFetch(`/api/messages/${threadId}`).then(r=>r.json()); try{localStorage.setItem(cacheKey,JSON.stringify(data));}catch(e){} }
        catch(ex) { try{const c=localStorage.getItem(cacheKey);if(c)data=JSON.parse(c);}catch(e){} if(!data){document.getElementById('msg-modal-body').textContent='Kan ikke hente besked (offline)';return;} }
        const msgs=(data.messages||[]).filter(m=>m.messageType==='Message'||m.text);
        if (!msgs.length) { document.getElementById('msg-modal-body').textContent='Ingen indhold'; return; }
        document.getElementById('msg-modal-meta').textContent=`${msgs.length} besked${msgs.length!==1?'er':''} i tråden`;
        // Was: 'parse-msg-' + (m.id || Math.random()...) at render time, but
        // 'parse-msg-' + (m.id || '') at listener-attach time below — for any
        // message missing an id these produced two DIFFERENT ids, so that
        // message's "Tilføj til kalender" button silently did nothing when
        // clicked. Use the same deterministic key (id, or array index as
        // fallback) in both places.
        document.getElementById('msg-modal-body').innerHTML=msgs.map((m, mi) => {
          const sender=m.sender?.fullName||'Ukendt', date=m.sendDateTime?new Date(m.sendDateTime).toLocaleString('da-DK',{day:'numeric',month:'short',hour:'2-digit',minute:'2-digit'}):'';
          const mBtnId = 'parse-msg-' + (m.id ?? mi);
          const attsHtml = renderAttachments(m.attachments || []);
          // "Tilføj til skolekalender" vises KUN på beskeder der rent
          // faktisk indeholder et Google Docs-link — se backend/ugebrev.py.
          const rawHtml = m.text?.html || m.text || '';
          const hasDocLink = /docs\.google\.com\/document/.test(rawHtml);
          const schoolBtnHtml = hasDocLink ? `<button class="parse-event-btn" id="ugebrev-btn-${mBtnId}">🎒 Tilføj til skolekalender</button>` : '';
          return `<div class="thread-msg"><div class="thread-msg-header"><span class="thread-msg-sender">${sender}</span><span class="thread-msg-date">${date}</span></div><div class="thread-msg-body">${m.text?.html||m.text||'(intet indhold)'}</div>${attsHtml ? `<div style="display:flex;flex-wrap:wrap;gap:8px;margin-top:8px">${attsHtml}</div>` : ''}<button class="parse-event-btn" id="${mBtnId}">📅 Tilføj til kalender</button>${schoolBtnHtml}</div>`;
        }).join('');
        // Attach event listeners after render
        msgs.forEach((m, mi) => {
          const mBtnId = 'parse-msg-' + (m.id ?? mi);
          const btn = document.getElementById(mBtnId);
          if (btn) {
            const txt = (m.text?.html||m.text||'').replace(/<[^>]*>/g,' ').replace(/\s+/g,' ').trim();
            btn.addEventListener('click', e => { e.stopPropagation(); openEventModal(txt); });
          }
          const schoolBtn = document.getElementById('ugebrev-btn-' + mBtnId);
          if (schoolBtn) {
            schoolBtn.addEventListener('click', async e => {
              e.stopPropagation();
              schoolBtn.disabled = true;
              const orig = schoolBtn.textContent;
              schoolBtn.textContent = 'Synkroniserer...';
              try {
                const r = await apiFetch(`/api/ugebrev/sync-thread/${threadId}`, { method: 'POST' });
                const data = await r.json();
                if (!r.ok) {
                  alert('⚠️ ' + (data.detail || 'Kunne ikke synkronisere.'));
                } else if (data.found && data.events_created) {
                  alert(`✅ Uge ${data.week}/${data.year}: ${data.events_created} events oprettet/opdateret.`);
                } else {
                  alert('ℹ️ ' + (data.message || 'Intet skema fundet.'));
                }
              } catch (err) {
                alert('⚠️ Fejl: ' + err.message);
              }
              schoolBtn.disabled = false;
              schoolBtn.textContent = orig;
            });
          }
        });
      } catch(e) { document.getElementById('msg-modal-body').textContent='Fejl: '+e.message; }
    }
    function closeMsgModal(e) { if (!e||e.target===document.getElementById('msg-modal-overlay')||e.target===document.getElementById('msg-modal-close')) document.getElementById('msg-modal-overlay').classList.remove('open'); }

    // ── Login / Konto dropdown ──