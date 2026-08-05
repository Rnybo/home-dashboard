    // utils.js — bevidst holdt som separat script-fil for load-order (må ikke merges ind
    // i andre filer, se CLAUDE.md). loadWeather()/loadGoogleCalendar()/loadProfileConfig()
    // lå tidligere HER som duplikater af de rigtige (cache-understøttede) versioner i
    // globals.js. Fordi scripts indlæses globals→...→utils, overskrev disse simplere
    // duplikater stille dem fra globals.js, hvilket gjorde cache-laget for vejr og
    // Google-kalender til dødt kode. Fjernet — globals.js's versioner er nu de eneste.
