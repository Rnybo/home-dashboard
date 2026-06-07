    // ── Simpel cache-utility til localStorage ────────────────────────────────
    // TTL: where possible, keep data long enough to survive a full day without Aula session.
    // Cache is always shown immediately; TTL only controls when a background refresh is attempted.
    const CACHE_TTL = {
      calendar:   24 * 60 * 60 * 1000,  // 24h — weekly schedule doesn't change often
      presence:   24 * 60 * 60 * 1000,  // 24h — presence templates are set days ahead
      google:     30 * 60 * 1000,        // 30min — Google calendar changes more often
      weather:    30 * 60 * 1000,        // 30min
      messages:    6 * 60 * 60 * 1000,  // 6h
      posts:       6 * 60 * 60 * 1000,  // 6h
      dates:      24 * 60 * 60 * 1000,  // 24h
      birthdays:  24 * 60 * 60 * 1000,  // 24h
      routes:     60 * 60 * 1000,        // 1h
    };

    function cacheSet(key, data) {
      try { localStorage.setItem('cache_' + key, JSON.stringify({ ts: Date.now(), data })); } catch(e) {}
    }

    function cacheGet(key) {
      try {
        const raw = localStorage.getItem('cache_' + key);
        if (!raw) return null;
        const { data } = JSON.parse(raw);
        return data ?? null;
      } catch(e) { return null; }
    }

    function cacheAge(key) {
      // Returns age in milliseconds, or Infinity if not cached
      try {
        const raw = localStorage.getItem('cache_' + key);
        if (!raw) return Infinity;
        const { ts } = JSON.parse(raw);
        return Date.now() - ts;
      } catch(e) { return Infinity; }
    }

    function cacheIsStale(key) {
      const ttl = CACHE_TTL[key] ?? 5 * 60 * 1000;
      return cacheAge(key) > ttl;
    }

    // Hent data fra API — vis cache straks, opdater kun hvis TTL er udløbet
    // fetchFn: async () => data
    // onData(data, fromCache): kaldes med data
    async function cacheFetch(key, fetchFn, onData) {
      // Vis cached data straks uanset alder
      const cached = cacheGet(key);
      if (cached !== null) onData(cached, true);

      // Hent kun frisk fra API hvis TTL er udløbet (eller ingen cache)
      if (!cacheIsStale(key) && cached !== null) return;

      try {
        const fresh = await fetchFn();
        if (fresh !== undefined && fresh !== null) {
          cacheSet(key, fresh);
          onData(fresh, false);
        }
      } catch(e) {
        // Tjek om det er en session-fejl — vis login-banner med det samme
        if (e && (e.status === 401 || e.status === 403 || (e.message && e.message.includes('401')))) {
          if (typeof renderAccountDropdown === 'function') renderAccountDropdown(true);
        }
        // API fejlede — cached data er allerede vist
      }
    }
