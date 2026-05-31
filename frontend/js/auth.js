    let loginPolling = null, loginAccounts = [];

    function toggleAccountMenu(e) {
      e.stopPropagation();
      const dd = document.getElementById('account-dropdown');
      dd.style.display = dd.style.display === 'none' ? 'block' : 'none';
    }
    document.addEventListener('click', () => {
      const dd = document.getElementById('account-dropdown');
      if (dd) dd.style.display = 'none';
    });

    async function loadLoginAccounts() {
      try { loginAccounts = await apiFetch('/api/login/accounts').then(r => r.json()); } catch(e) { loginAccounts = []; }
      // Don't call renderAccountDropdown here — let checkSession control state
    }

    function renderAccountDropdown(sessionExpired = false) {
      const items = document.getElementById('account-items');
      if (!items) return;
      if (sessionExpired) {
        const accs = loginAccounts.length ? loginAccounts : [{index:0, name:'Log ind'}];
        items.innerHTML = accs.map(a =>
          `<div class="acc-item" data-idx="${a.index}">🔑 Login ${a.name}</div>`
        ).join('');
        items.querySelectorAll('.acc-item[data-idx]').forEach(el => {
          el.addEventListener('click', e => { e.stopPropagation(); startLogin(parseInt(el.dataset.idx)); });
        });
        document.getElementById('session-banner').style.display = 'inline-block';
        document.getElementById('banner-msg').textContent = 'Aula offline — vælg konto';
      } else {
        // Only show the active account (index 0 unless a specific login was done)
        const active = loginAccounts.find(a => a.index === (window._activeAccountIndex ?? 0))
                    || loginAccounts[0]
                    || { name: 'Logget ind' };
        items.innerHTML = `<div class="acc-item" style="color:#aaa;cursor:default">✅ ${active.name}</div>`;
        document.getElementById('session-banner').style.display = 'none';
      }
    }

    async function startLogin(accountIndex = 0) {
      window._activeAccountIndex = accountIndex;
      document.getElementById('account-dropdown').style.display = 'none';
      document.getElementById('session-banner').style.display = 'inline-block';
      document.getElementById('banner-msg').textContent = 'Logger ind...';
      try {
        await apiFetch(`/api/login/start?account_index=${accountIndex}`, { method: 'POST' });
        document.getElementById('banner-msg').textContent = 'Godkend i MitID-appen...';
        pollLoginStatus();
      } catch(e) {
        document.getElementById('banner-msg').textContent = 'Fejl: ' + e.message;
      }
    }

    async function logoutAula() {
      document.getElementById('account-dropdown').style.display = 'none';
      try {
        await apiFetch('/api/login/cancel', { method: 'POST' });
        await apiFetch('/api/logout', { method: 'POST' });
      } catch(e) {}
      await loadLoginAccounts();
      renderAccountDropdown(true);
    }

    async function pollLoginStatus() {
      clearInterval(loginPolling);
      // Open MitID overlay
      const overlay = document.getElementById('mitid-overlay');
      const qrImg = document.getElementById('mitid-qr-img');
      const spinner = document.getElementById('mitid-spinner');
      const status = document.getElementById('mitid-status');
      const hint = document.getElementById('mitid-hint');
      overlay.classList.add('open');
      qrImg.style.display = 'none';
      spinner.style.display = 'inline-block';
      hint.textContent = 'Starter login-flow...';
      status.textContent = '';

      loginPolling = setInterval(async () => {
        try {
          const data = await apiFetch('/api/login/status').then(r => r.json());
          if (data.state === 'show_qr') {
            spinner.style.display = 'none';
            hint.textContent = 'Godkend i din MitID app eller scan QR-koden:';
            if (data.qr_image) {
              qrImg.src = 'data:image/png;base64,' + data.qr_image;
              qrImg.style.display = 'block';
            }
            status.textContent = '';
          } else if (data.state === 'running') {
            spinner.style.display = 'inline-block';
            qrImg.style.display = 'none';
            hint.textContent = 'Logger ind...';
          } else if (data.state === 'success') {
            clearInterval(loginPolling);
            spinner.style.display = 'none';
            qrImg.style.display = 'none';
            hint.textContent = '✅ Login lykkedes!';
            status.textContent = 'Genindlæser...';
            setTimeout(() => { overlay.classList.remove('open'); window.location.reload(); }, 1200);
          } else if (data.state === 'idle') {
            // State reset to idle may mean success already handled — check session
            try {
              const s = await apiFetch('/api/status').then(r => r.json());
              if (s.session_valid) {
                clearInterval(loginPolling);
                overlay.classList.remove('open');
                window.location.reload();
              }
            } catch(e) {}
          } else if (data.state === 'failed') {
            clearInterval(loginPolling);
            spinner.style.display = 'none';
            qrImg.style.display = 'none';
            hint.textContent = '❌ Login fejlede';
            status.textContent = data.error || '';
            loadLoginAccounts();
            setTimeout(() => overlay.classList.remove('open'), 3000);
          }
        } catch(e) { /* ignore poll errors */ }
      }, 1000);
    }

    function cancelMitIDLogin() {
      clearInterval(loginPolling);
      apiFetch('/api/login/cancel', { method: 'POST' }).catch(() => {});
      document.getElementById('mitid-overlay').classList.remove('open');
    }
    async function checkSession() {
      try {
        const data = await apiFetch('/api/status').then(r => r.json());
        const expired = !data.session_valid;
        await loadLoginAccounts();
        renderAccountDropdown(expired);
        return data.session_valid;
      } catch(e) {
        // Network error — don't change state, keep loading indicator
        console.warn('checkSession failed:', e);
        return false;
      }
    }

    // ── Data loaders ──