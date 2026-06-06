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
        // Session expired — show login buttons for all accounts
        const accs = loginAccounts.length ? loginAccounts : [{index:0, name:'Log ind', has_token:false}];
        items.innerHTML = accs.map(a =>
          `<div class="acc-item" data-idx="${a.index}">🔑 Login ${a.name}</div>`
        ).join('');
        items.querySelectorAll('.acc-item[data-idx]').forEach(el => {
          el.addEventListener('click', e => { e.stopPropagation(); startLogin(parseInt(el.dataset.idx)); });
        });
        document.getElementById('session-banner').style.display = 'inline-block';
        document.getElementById('banner-msg').textContent = 'Aula offline — vælg konto';
      } else {
        // Session active — show active account + switch options
        const active = loginAccounts.find(a => a.index === (window._activeAccountIndex ?? 0))
                    || loginAccounts[0]
                    || { name: 'Logget ind', has_token: true };
        const others = loginAccounts.filter(a => a.index !== (window._activeAccountIndex ?? 0));
        let html = `<div class="acc-item" style="color:#aaa;cursor:default">✅ ${active.name}</div>`;
        if (others.length) {
          html += `<div class="acc-item acc-divider" style="font-size:0.75rem;color:#bbb;padding:4px 12px;cursor:default">Skift konto</div>`;
          html += others.map(a => {
            const icon = a.has_token ? '🔄' : '🔑';
            const label = a.has_token ? `Skift til ${a.name}` : `Login ${a.name}`;
            return `<div class="acc-item" data-switch="${a.index}">${icon} ${label}</div>`;
          }).join('');
        }
        items.innerHTML = html;
        items.querySelectorAll('.acc-item[data-switch]').forEach(el => {
          el.addEventListener('click', async e => {
            e.stopPropagation();
            const idx = parseInt(el.dataset.switch);
            const acc = loginAccounts.find(a => a.index === idx);
            if (acc && acc.has_token) {
              await switchAccount(idx);
            } else {
              startLogin(idx);
            }
          });
        });
        document.getElementById('session-banner').style.display = 'none';
      }
    }

    async function switchAccount(accountIndex) {
      document.getElementById('account-dropdown').style.display = 'none';
      try {
        const r = await apiFetch(`/api/switch-account?account_index=${accountIndex}`, { method: 'POST' });
        if (r.ok) {
          window._activeAccountIndex = accountIndex;
          await loadLoginAccounts();
          renderAccountDropdown(false);
          // Reload all data for new account
          loadAll();
        }
      } catch(e) {
        // Token missing — fall back to login
        startLogin(accountIndex);
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

    let _qrFrames = [null, null], _qrFrameTimer = null, _qrFrameIdx = 0;

    function drawQR(canvasId, matrix) {
      const canvas = document.getElementById(canvasId);
      if (!canvas || !matrix || !matrix.length) return;
      const ctx = canvas.getContext('2d');
      const size = matrix.length;
      const cell = canvas.width / size;
      ctx.fillStyle = '#fff';
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      ctx.fillStyle = '#000';
      for (let r = 0; r < size; r++)
        for (let c = 0; c < size; c++)
          if (matrix[r][c]) ctx.fillRect(c * cell, r * cell, cell, cell);
    }

    function startQRAnimation() {
      if (_qrFrameTimer) return;
      _qrFrameTimer = setInterval(() => {
        _qrFrameIdx = 1 - _qrFrameIdx;
        if (_qrFrames[_qrFrameIdx]) drawQR('mitid-qr-canvas1', _qrFrames[_qrFrameIdx]);
      }, 500);
    }

    function stopQRAnimation() {
      clearInterval(_qrFrameTimer);
      _qrFrameTimer = null;
      _qrFrames = [null, null];
      _qrFrameIdx = 0;
    }

    async function pollLoginStatus() {
      clearInterval(loginPolling);
      // Open MitID overlay
      const overlay = document.getElementById('mitid-overlay');
      const spinner = document.getElementById('mitid-spinner');
      const status = document.getElementById('mitid-status');
      const hint = document.getElementById('mitid-hint');
      overlay.classList.add('open');
      spinner.style.display = 'inline-block';
      hint.textContent = 'Starter login-flow...';
      status.textContent = '';

      loginPolling = setInterval(async () => {
        try {
          const data = await apiFetch('/api/login/status').then(r => r.json());
          if (data.state === 'show_qr') {
            spinner.style.display = 'none';
            hint.textContent = 'Scan QR-koden med MitID-appen:';
            if (data.qr_image) {
              _qrFrames[0] = data.qr_image;
              _qrFrames[1] = data.qr_image2;
              document.getElementById('mitid-qr-wrap').style.display = 'block';
              startQRAnimation();
            }
            status.textContent = '';
          } else if (data.state === 'running') {
            spinner.style.display = 'inline-block';
            document.getElementById('mitid-qr-wrap').style.display = 'none';
            hint.textContent = 'Logger ind...';
          } else if (data.state === 'success') {
            clearInterval(loginPolling);
            stopQRAnimation();
            spinner.style.display = 'none';
            document.getElementById('mitid-qr-wrap').style.display = 'none';
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
            stopQRAnimation();
            spinner.style.display = 'none';
            document.getElementById('mitid-qr-wrap').style.display = 'none';
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
      stopQRAnimation();
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