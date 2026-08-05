    let klasseLoaded = false;
    const contactCache = {}; // groupId -> {childId -> contactData}

    async function loadGroups() {
      if (klasseLoaded) return;
      klasseLoaded = true;
      const el = document.getElementById('klasse-content');
      const cached = (() => { try { const v = localStorage.getItem('ls_groups'); return v ? JSON.parse(v) : null; } catch(e) { return null; } })();
      if (cached) renderGroups(cached, el);
      try {
        const groups = await apiFetch('/api/groups').then(r => r.json());
        try { localStorage.setItem('ls_groups', JSON.stringify(groups)); } catch(e) {}
        renderGroups(groups, el);
      } catch(e) {
        if (!cached) el.innerHTML = '<span class="loading">Kunne ikke hente gruppedata</span>';
      }
    }

    function renderGroups(groups, el) {
      if (!groups || !groups.length) { el.innerHTML = '<span class="loading">Ingen grupper fundet</span>'; return; }
      el.innerHTML = groups.map((group, gi) => {
        const children = group.children || [];
        const myKidsHtml = (group.myChildren || []).map(k => {
          const ini = k.name.split(' ').map(w => w[0]).join('').substring(0, 2).toUpperCase();
          // Brug signeret URL fra CHILDREN (profile-config) hvis tilgængelig — match på fornavn
          const child = CHILDREN.find(c => k.name.startsWith(c.name));
          const picUrl = child?.photoUrl || k.photoSignedUrl || k.photoUrl;
          return picUrl
            ? `<img src="${aulaImg(picUrl)}" title="${k.name}" style="width:24px;height:24px;border-radius:50%;object-fit:cover;border:2px solid var(--blue);margin-left:4px" onerror="this.style.display='none'">`
            : `<span style="background:var(--blue);color:#fff;border-radius:50%;width:24px;height:24px;display:inline-flex;align-items:center;justify-content:center;font-size:0.65rem;font-weight:700;margin-left:4px" title="${k.name}">${ini}</span>`;
        }).join('');

        const childrenHtml = children.map((child, ci) => {
          const ini = child.name.split(' ').map(w => w[0]).join('').substring(0, 2).toUpperCase();
          const isOwn = child.isOwnChild;
          const avatarHtml = `<div class="klasse-child-avatar" style="${isOwn ? 'background:var(--blue);color:#fff' : ''}">${ini}</div>`;
          return `
            <div class="klasse-child-row${isOwn ? ' own-child' : ''}" data-child-id="${child.id}" onclick="toggleParents(${gi},${ci},${group.id},${child.id})">
              ${avatarHtml}
              <div style="flex:1;min-width:0">
                <div class="klasse-child-name">${child.name}${isOwn ? ' ⭐' : ''}</div>
                <div class="klasse-child-bday" id="bday-${gi}-${ci}"></div>
              </div>
              <span class="klasse-child-expand" id="arrow-${gi}-${ci}">▶ kontakt</span>
            </div>
            <div class="klasse-parents" id="parents-${gi}-${ci}">
              <div class="klasse-loading-contacts">Henter kontaktinfo...</div>
            </div>`;
        }).join('');

        return `
          <div class="klasse-group">
            <div class="klasse-group-header" onclick="toggleGroup(${gi})" id="group-header-${gi}">
              <span style="display:flex;align-items:center;gap:6px">👥 ${group.name}${myKidsHtml}</span>
              <span style="display:flex;align-items:center;gap:8px">
                <span class="klasse-count">${children.length} børn</span>
                <span class="klasse-arrow" id="group-arrow-${gi}">▶</span>
              </span>
            </div>
            <div class="klasse-children" id="group-children-${gi}" data-group-id="${group.id}">${childrenHtml}</div>
          </div>`;
      }).join('');
    }

    async function toggleParents(gi, ci, groupId, childId) {
      const panel = document.getElementById(`parents-${gi}-${ci}`);
      const arrow = document.getElementById(`arrow-${gi}-${ci}`);
      const open = panel.classList.toggle('open');
      if (arrow) arrow.textContent = open ? '▼ kontakt' : '▶ kontakt';
      if (!open) return;

      // Check if already rendered with real data
      if (panel.dataset.loaded) return;

      // Load contacts for this group (cached per group)
      if (!contactCache[groupId]) {
        try {
          const cacheKey = 'ls_contacts_' + groupId;
          const stored = (() => { try { const v = localStorage.getItem(cacheKey); return v ? JSON.parse(v) : null; } catch(e) { return null; } })();
          if (stored) contactCache[groupId] = stored;

          const fresh = await apiFetch(`/api/groups/${groupId}/contacts`).then(r => r.json());
          contactCache[groupId] = {};
          fresh.forEach(c => { contactCache[groupId][c.id] = c; });
          try { localStorage.setItem(cacheKey, JSON.stringify(contactCache[groupId])); } catch(e) {}
        } catch(e) {
          panel.innerHTML = '<div class="klasse-loading-contacts">Kunne ikke hente kontaktinfo</div>';
          return;
        }
      }

      const contact = contactCache[groupId]?.[childId];
      if (!contact) {
        panel.innerHTML = '<div class="klasse-loading-contacts">Ingen kontaktinfo tilgængelig</div>';
        return;
      }

      panel.dataset.loaded = '1';
      panel.innerHTML = renderContactPanel(contact);
    }

    function renderContactPanel(contact) {
      let html = '';

      // Parents
      const parents = contact.parents || [];
      if (!parents.length) {
        html += '<div class="klasse-loading-contacts">Ingen forældre registreret</div>';
      } else {
        html += parents.map(p => {
          const ini = p.name.split(' ').map(w => w[0]).join('').substring(0, 2).toUpperCase();
          const pPicUrl = p.photoSignedUrl || p.photoUrl;
          const pProxyUrl = pPicUrl ? `/api/profile-picture?url=${encodeURIComponent(pPicUrl)}` : '';
          const avatarHtml = pProxyUrl
            ? `<img class="klasse-parent-avatar" src="${pProxyUrl}" onerror="this.outerHTML='<div class=\\'klasse-parent-avatar\\'>${ini}</div>'">`
            : `<div class="klasse-parent-avatar">${ini}</div>`;
          const relLabel = p.relation || (p.gender === 'F' ? 'Mor' : p.gender === 'M' ? 'Far' : 'Forælder');
          let contactRows = '';
          if (p.mobile) contactRows += `<div class="klasse-contact-row">📞 <a href="tel:${p.mobile}">${p.mobile}</a></div>`;
          if (p.email)  contactRows += `<div class="klasse-contact-row">✉️ <a href="mailto:${p.email}">${p.email}</a></div>`;
          if (p.address && p.address.trim()) contactRows += `<div class="klasse-contact-row">🏠 ${p.address}</div>`;
          return `<div class="klasse-parent-row">
            ${avatarHtml}
            <div class="klasse-parent-info">
              <div class="klasse-parent-name">${p.name}</div>
              <div class="klasse-parent-relation">${relLabel}</div>
              ${contactRows || '<div class="klasse-contact-row" style="color:#bbb">Ingen kontaktinfo delt</div>'}
            </div>
          </div>`;
        }).join('');
      }
      return html;
    }

    function toggleGroup(gi) {
      const header = document.getElementById('group-header-' + gi);
      const childrenEl = document.getElementById('group-children-' + gi);
      const arrow = document.getElementById('group-arrow-' + gi);
      const open = childrenEl.classList.toggle('open');
      header.classList.toggle('open', open);
      if (arrow) arrow.style.transform = open ? 'rotate(90deg)' : '';
      // Load contacts in background to populate birthdays
      if (open && !childrenEl.dataset.contactsLoaded) {
        childrenEl.dataset.contactsLoaded = '1';
        const groupId = parseInt(childrenEl.dataset.groupId);
        _prefetchContacts(gi, groupId);
      }
    }

    async function _prefetchContacts(gi, groupId) {
      if (contactCache[groupId]) { _applyBirthdays(gi, groupId); return; }
      try {
        const cacheKey = 'ls_contacts_' + groupId;
        const stored = (() => { try { const v = localStorage.getItem(cacheKey); return v ? JSON.parse(v) : null; } catch(e) { return null; } })();
        if (stored) { contactCache[groupId] = stored; _applyBirthdays(gi, groupId); }
        const fresh = await apiFetch(`/api/groups/${groupId}/contacts`).then(r => r.json());
        contactCache[groupId] = {};
        fresh.forEach(c => { contactCache[groupId][c.id] = c; });
        try { localStorage.setItem(cacheKey, JSON.stringify(contactCache[groupId])); } catch(e) {}
        _applyBirthdays(gi, groupId);
      } catch(e) {}
    }

    function _applyBirthdays(gi, groupId) {
      const childrenEl = document.getElementById('group-children-' + gi);
      if (!childrenEl) return;
      childrenEl.querySelectorAll('[id^="bday-' + gi + '-"]').forEach(el => {
        const row = el.closest('.klasse-child-row');
        if (!row) return;
        // data-child-id instead of regex-parsing the onclick attribute string
        // (which used to grab the 4th number found anywhere in the string —
        // fragile if any of the earlier ids ever weren't plain integers).
        const childId = parseInt(row.dataset.childId);
        const contact = contactCache[groupId]?.[childId];
        if (!contact) return;

        // Update avatar with contactlist photo via proxy
        const picUrl = contact.photoSignedUrl || contact.photoUrl;
        if (picUrl) {
          const proxyUrl = `/api/profile-picture?url=${encodeURIComponent(picUrl)}`;
          const img = row.querySelector('.klasse-child-avatar');
          if (img && img.tagName === 'IMG') {
            img.src = proxyUrl;
          } else if (img) {
            const ini = img.textContent;
            const newImg = document.createElement('img');
            newImg.className = 'klasse-child-avatar';
            newImg.src = proxyUrl;
            newImg.alt = contact.name;
            if (row.classList.contains('own-child')) newImg.style.cssText = 'border-color:var(--blue);border-width:3px';
            newImg.onerror = () => { newImg.outerHTML = `<div class="klasse-child-avatar" style="${row.classList.contains('own-child') ? 'background:var(--blue);color:#fff' : ''}">${ini}</div>`; };
            img.replaceWith(newImg);
          }
        }

        // Update birthday
        if (!contact.birthday) return;
        const bd = new Date(contact.birthday);
        const today = new Date();
        const thisYear = new Date(today.getFullYear(), bd.getMonth(), bd.getDate());
        const daysUntil = Math.round((thisYear - today) / 86400000);
        const bdStr = bd.toLocaleDateString('da-DK', { day: 'numeric', month: 'long' });
        const upcoming = daysUntil === 0 ? ' 🎉' : daysUntil > 0 && daysUntil <= 14 ? ` (om ${daysUntil} dage)` : '';
        el.textContent = `🎂 ${bdStr}${upcoming}`;
      });
    }
