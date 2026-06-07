    // ── Simpel cache-utility til localStorage ────────────────────────────────
    // Data vises altid fra cache uanset alder.
    // TTL styrer kun hvornår vi forsøger at hente friske data i baggrunden.
    const CACHE_TTL = {
      calendar:   15 * 60 * 1000,
      presence:   15 * 60 * 1000,
      google:     10 * 60 * 1000,
      weather:    30 * 60 * 1000,
      messages:   15 * 60 * 1000,
      posts:      15 * 60 * 1000,
      dates:      60 * 60 * 1000,
      birthdays:  60 * 60 * 1000,
      routes:     60 * 60 * 1000,
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
      try {
        const raw = localStorage.getItem('cache_' + key);
        if (!raw) return Infinity;
        return Date.now() - JSON.parse(raw).ts;
      } catch(e) { return Infinity; }
    }

    function cacheIsStale(key) {
      return cacheAge(key) > (CACHE_TTL[key] ?? 15 * 60 * 1000);
    }

    // Hent data fra API — vis cache straks uanset alder, opdater i baggrunden når TTL udløber
    async function cacheFetch(key, fetchFn, onData) {
      const cached = cacheGet(key);
      if (cached !== null) onData(cached, true);

      // Forsøg kun API-kald hvis TTL er udløbet (eller ingen cache)
      if (!cacheIsStale(key) && cached !== null) return;

      try {
        const fresh = await fetchFn();
        if (fresh !== undefined && fresh !== null) {
          cacheSet(key, fresh);
          onData(fresh, false);
        }
      } catch(e) {
        if (e && (e.status === 401 || e.status === 403 || (e.message && e.message.includes('401')))) {
          if (typeof renderAccountDropdown === 'function') renderAccountDropdown(true);
        }
        // API fejlede — cached data er allerede vist
      }
    }
