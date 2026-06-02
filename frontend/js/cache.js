    // ── Simpel cache-utility til localStorage ────────────────────────────────
    const CACHE_TTL = {
      calendar:       5 * 60 * 1000,
      presence:       5 * 60 * 1000,
      google:        10 * 60 * 1000,
      weather:       30 * 60 * 1000,
      messages:       5 * 60 * 1000,
      posts:         10 * 60 * 1000,
      dates:         30 * 60 * 1000,
      birthdays:     60 * 60 * 1000,
      routes:        60 * 60 * 1000,
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

    // Hent data fra API — vis cache straks, opdater når API svarer
    // fetchFn: async () => data
    // onData(data, fromCache): kaldes med data
    async function cacheFetch(key, fetchFn, onData) {
      // Vis cached data straks uanset alder
      const cached = cacheGet(key);
      if (cached !== null) onData(cached, true);

      // Hent frisk fra API i baggrunden
      try {
        const fresh = await fetchFn();
        if (fresh !== undefined && fresh !== null) {
          cacheSet(key, fresh);
          onData(fresh, false);
        }
      } catch(e) {
        // API fejlede — cached data er allerede vist
      }
    }
