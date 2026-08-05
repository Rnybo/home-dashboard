// apps/huskespil.js — Huskespillet (Memory)

const MEM_CATEGORIES = [
  { id: 'animals',   label: 'Dyr',       icon: '🦁', words: ['lion','tiger','elephant','giraffe','zebra','dolphin','wolf','bear','gorilla','cheetah','penguin','koala','panda','flamingo','owl','kangaroo','jaguar','leopard','rhinoceros','hippopotamus','crocodile','fox','camel','peacock','meerkat','lynx','moose','bison','armadillo','sloth','chameleon','parrot'] },
  { id: 'space',     label: 'Rummet',    icon: '🪐', words: ['moon','galaxy','astronaut','rocket','nebula','saturn','comet','aurora','mars','jupiter','milky way','sun','asteroid','space station','black hole','hubble telescope','meteor','pillars of creation','solar eclipse','venus','earth from space','uranus','pluto','supernova','cosmic dust','lunar crater','spacewalk','observatory telescope','mercury planet','neptune','satellite orbit','rocket launch'] },
  { id: 'ocean',     label: 'Havet',     icon: '🌊', words: ['shark','whale','octopus','coral reef','seahorse','jellyfish','clownfish','sea turtle','lobster','seal','starfish','swordfish','walrus','dolphin','crab','orca','ray','narwhal','pufferfish','moray eel','sea lion','manatee','barracuda','sea urchin','anglerfish','hammerhead shark','sea anemone','blue whale','sailfish','sea cucumber','pelican'] },
  { id: 'nature',    label: 'Natur',     icon: '🌿', words: ['waterfall','mountain','forest','volcano','canyon','glacier','sunset','rainbow','flower','mushroom','butterfly','dragonfly','fern','oak tree','cherry blossom','autumn leaves','ice cave','northern lights','desert','coral','lightning storm','sand dunes','cave stalactite','mangrove','lavender field','frozen lake','redwood tree','meadow wildflowers','hot spring','fog forest','cactus','bamboo forest'] },
  { id: 'food',      label: 'Mad',       icon: '🍕', words: ['pizza','sushi','taco','burger','pasta','cake','donut','ice cream','strawberry','watermelon','avocado','pineapple','ramen','pancakes','croissant','chocolate','mango','lemon','pomegranate','cookie','cheesecake','waffles','macarons','lobster dish','paella','dim sum','baklava','acai bowl','churros','tiramisu','crepes','bruschetta'] },
  { id: 'transport', label: 'Transport', icon: '🚂', words: ['steam train','sailboat','helicopter','motorcycle','submarine','hot air balloon','bicycle','racing car','fire truck','jet plane','vintage car','tram','speedboat','zeppelin','snowmobile','double decker bus','cable car','kayak','space shuttle','hovercraft','amphibious vehicle','dog sled','paraglider','jet ski','tugboat','tank','horse carriage','rickshaw','monorail','seaplane','container ship','quad bike'] },
];

const MEM_GRIDS = [
  { id: '4x4', label: '4 × 4', cols: 4, pairs: 8  },
  { id: '6x6', label: '6 × 6', cols: 6, pairs: 18 },
  { id: '8x8', label: '8 × 8', cols: 8, pairs: 32 },
];

const MEM_DANISH = {
  lion:'Løve',tiger:'Tiger',elephant:'Elefant',giraffe:'Giraf',zebra:'Zebra',dolphin:'Delfin',wolf:'Ulv',bear:'Bjørn',gorilla:'Gorilla',cheetah:'Gepard',penguin:'Pingvin',koala:'Koala',panda:'Panda',flamingo:'Flamingo',owl:'Ugle',kangaroo:'Kænguru',jaguar:'Jaguar',leopard:'Leopard',rhinoceros:'Næsehorn',hippopotamus:'Flodhest',crocodile:'Krokodille',fox:'Ræv',camel:'Kamel',peacock:'Påfugl',meerkat:'Surikat',lynx:'Los',moose:'Elg',bison:'Bison',armadillo:'Bæltedyr',sloth:'Dovendyr',chameleon:'Kamæleon',parrot:'Papegøje',
  moon:'Månen',galaxy:'Galakse',astronaut:'Astronaut',rocket:'Raket',nebula:'Tåge',saturn:'Saturn',comet:'Komet',aurora:'Nordlys',mars:'Mars',jupiter:'Jupiter',milkyway:'Mælkevejen',sun:'Solen',asteroid:'Asteroid','space-station':'Rumstation',blackhole:'Sort hul',hubble:'Hubble',meteor:'Meteor',pillars:'Støtternes søjler',eclipse:'Solformørkelse',venus:'Venus',earth:'Jorden',uranus:'Uranus',pluto:'Pluto',supernova:'Supernova','cosmic-dust':'Kosmisk støv','lunar-crater':'Månekrater',spacewalk:'Rumvandring',observatory:'Observatorium',mercury:'Merkur',neptune:'Neptun',satellite:'Satellit','rocket-launch':'Raketopskydning',
  shark:'Haj',whale:'Hval',octopus:'Blæksprutte','coral-reef':'Koralrev',seahorse:'Søhest',jellyfish:'Vandmand',clownfish:'Klovnfisk','sea-turtle':'Havskildpadde',lobster:'Hummer',seal:'Sæl',starfish:'Søstjerne',swordfish:'Sværdfisk',walrus:'Hvalros',crab:'Krabbe',orca:'Spækhugger',ray:'Manta-rokke',narwhal:'Narhval',pufferfish:'Kuglefisk','moray-eel':'Muræneal','sea-lion':'Søløve',manatee:'Manaté',barracuda:'Barracuda','sea-urchin':'Søpindsvin',anglerfish:'Havtaske',hammerhead:'Hammerhaj','sea-anemone':'Søanemone','blue-whale':'Blåhval',sailfish:'Sejlfisk','sea-cucumber':'Søpølse',pelican:'Pelikan',
  waterfall:'Vandfald',mountain:'Bjerg',forest:'Skov',volcano:'Vulkan',canyon:'Kløft',glacier:'Gletsjer',sunset:'Solnedgang',rainbow:'Regnbue',flower:'Blomst',mushroom:'Svamp',butterfly:'Sommerfugl',dragonfly:'Libelle',fern:'Bregne','oak-tree':'Egetræ','cherry-blossom':'Kirsebærblomst','autumn-leaves':'Efterårsblade','ice-cave':'Isgrotte','northern-lights':'Nordlys',desert:'Ørken',coral:'Koral',lightning:'Lyn','sand-dunes':'Sanddyner',stalactite:'Drypsten',mangrove:'Mangrove',lavender:'Lavendel','frozen-lake':'Frossen sø',redwood:'Redwood',meadow:'Eng','hot-spring':'Varm kilde','fog-forest':'Tågeskov',cactus:'Kaktus',bamboo:'Bambus',
  pizza:'Pizza',sushi:'Sushi',taco:'Taco',burger:'Burger',pasta:'Pasta',cake:'Kage',donut:'Donut','ice-cream':'Is',strawberry:'Jordbær',watermelon:'Vandmelon',avocado:'Avocado',pineapple:'Ananas',ramen:'Ramen',pancakes:'Pandekager',croissant:'Croissant',chocolate:'Chokolade',mango:'Mango',lemon:'Citron',pomegranate:'Granatæble',cookie:'Småkage',cheesecake:'Cheesecake',waffles:'Vafler',macarons:'Macarons','lobster-dish':'Hummer',paella:'Paella','dim-sum':'Dim sum',baklava:'Baklava','acai-bowl':'Acai skål',churros:'Churros',tiramisu:'Tiramisu',crepes:'Pandekager',bruschetta:'Bruschetta',
  'steam-train':'Damptog',sailboat:'Sejlbåd',helicopter:'Helikopter',motorcycle:'Motorcykel',submarine:'Ubåd','hot-air-balloon':'Luftballon',bicycle:'Cykel','racing-car':'Racerbil','fire-truck':'Brandbil','jet-plane':'Jetfly','vintage-car':'Veteranbil',tram:'Sporvogn',speedboat:'Speedbåd',zeppelin:'Luftskib',snowmobile:'Snescooter',bus:'Dobbeltdækker','cable-car':'Kabelbane',kayak:'Kajak','space-shuttle':'Rumfærge',hovercraft:'Luftpudefartøj',amphibious:'Amfibiebil','dog-sled':'Hundeslæde',paraglider:'Paraglider','jet-ski':'Vandscooter',tugboat:'Slæbebåd',tank:'Tank','horse-carriage':'Hestevogn',rickshaw:'Rickshaw',monorail:'Monorail',seaplane:'Søfly','container-ship':'Containerskib','quad-bike':'ATV',
};

const MEM_FILENAMES = {
  animals:   {lion:'lion',tiger:'tiger',elephant:'elephant',giraffe:'giraffe',zebra:'zebra',dolphin:'dolphin',wolf:'wolf',bear:'bear',gorilla:'gorilla',cheetah:'cheetah',penguin:'penguin',koala:'koala',panda:'panda',flamingo:'flamingo',owl:'owl',kangaroo:'kangaroo',jaguar:'jaguar',leopard:'leopard',rhinoceros:'rhinoceros',hippopotamus:'hippopotamus',crocodile:'crocodile',fox:'fox',camel:'camel',peacock:'peacock',meerkat:'meerkat',lynx:'lynx',moose:'moose',bison:'bison',armadillo:'armadillo',sloth:'sloth',chameleon:'chameleon',parrot:'parrot'},
  space:     {moon:'moon',galaxy:'galaxy',astronaut:'astronaut',rocket:'rocket',nebula:'nebula',saturn:'saturn',comet:'comet',aurora:'aurora',mars:'mars',jupiter:'jupiter','milky way':'milkyway',sun:'sun',asteroid:'asteroid','space station':'space-station','black hole':'blackhole','hubble telescope':'hubble',meteor:'meteor','pillars of creation':'pillars','solar eclipse':'eclipse',venus:'venus','earth from space':'earth',uranus:'uranus',pluto:'pluto',supernova:'supernova','cosmic dust':'cosmic-dust','lunar crater':'lunar-crater',spacewalk:'spacewalk','observatory telescope':'observatory','mercury planet':'mercury',neptune:'neptune','satellite orbit':'satellite','rocket launch':'rocket-launch'},
  ocean:     {shark:'shark',whale:'whale',octopus:'octopus','coral reef':'coral-reef',seahorse:'seahorse',jellyfish:'jellyfish',clownfish:'clownfish','sea turtle':'sea-turtle',lobster:'lobster',seal:'seal',starfish:'starfish',swordfish:'swordfish',walrus:'walrus',dolphin:'dolphin',crab:'crab',orca:'orca',ray:'ray',narwhal:'narwhal',pufferfish:'pufferfish','moray eel':'moray-eel','sea lion':'sea-lion',manatee:'manatee',barracuda:'barracuda','sea urchin':'sea-urchin',anglerfish:'anglerfish','hammerhead shark':'hammerhead','sea anemone':'sea-anemone','blue whale':'blue-whale',sailfish:'sailfish','sea cucumber':'sea-cucumber',pelican:'pelican'},
  nature:    {waterfall:'waterfall',mountain:'mountain',forest:'forest',volcano:'volcano',canyon:'canyon',glacier:'glacier',sunset:'sunset',rainbow:'rainbow',flower:'flower',mushroom:'mushroom',butterfly:'butterfly',dragonfly:'dragonfly',fern:'fern','oak tree':'oak-tree','cherry blossom':'cherry-blossom','autumn leaves':'autumn-leaves','ice cave':'ice-cave','northern lights':'northern-lights',desert:'desert',coral:'coral','lightning storm':'lightning','sand dunes':'sand-dunes','cave stalactite':'stalactite',mangrove:'mangrove','lavender field':'lavender','frozen lake':'frozen-lake','redwood tree':'redwood','meadow wildflowers':'meadow','hot spring':'hot-spring','fog forest':'fog-forest',cactus:'cactus','bamboo forest':'bamboo'},
  food:      {pizza:'pizza',sushi:'sushi',taco:'taco',burger:'burger',pasta:'pasta',cake:'cake',donut:'donut','ice cream':'ice-cream',strawberry:'strawberry',watermelon:'watermelon',avocado:'avocado',pineapple:'pineapple',ramen:'ramen',pancakes:'pancakes',croissant:'croissant',chocolate:'chocolate',mango:'mango',lemon:'lemon',pomegranate:'pomegranate',cookie:'cookie',cheesecake:'cheesecake',waffles:'waffles',macarons:'macarons','lobster dish':'lobster-dish',paella:'paella','dim sum':'dim-sum',baklava:'baklava','acai bowl':'acai-bowl',churros:'churros',tiramisu:'tiramisu',crepes:'crepes',bruschetta:'bruschetta'},
  transport: {'steam train':'steam-train',sailboat:'sailboat',helicopter:'helicopter',motorcycle:'motorcycle',submarine:'submarine','hot air balloon':'hot-air-balloon',bicycle:'bicycle','racing car':'racing-car','fire truck':'fire-truck','jet plane':'jet-plane','vintage car':'vintage-car',tram:'tram',speedboat:'speedboat',zeppelin:'zeppelin',snowmobile:'snowmobile','double decker bus':'bus','cable car':'cable-car',kayak:'kayak','space shuttle':'space-shuttle',hovercraft:'hovercraft','amphibious vehicle':'amphibious','dog sled':'dog-sled',paraglider:'paraglider','jet ski':'jet-ski',tugboat:'tugboat',tank:'tank','horse carriage':'horse-carriage',rickshaw:'rickshaw',monorail:'monorail',seaplane:'seaplane','container ship':'container-ship','quad bike':'quad-bike'},
};

let mem = {
  phase:'setup', category:'animals', grid:'4x4',
  players:[], currentPlayer:0,
  cards:[], flipped:[], locked:false, moves:0,
  customWords: null, // null = tilfældig, array = brugervalg
};

function renderHuskespil() {
  const el = document.getElementById('view-app-huske'); if (!el) return;
  mem.phase = 'setup';
  const hasChildren = typeof CHILDREN !== 'undefined' && CHILDREN.length > 0;
  const fixedPlayers = [{ name:'Far', photo:'', initials:'👨' },{ name:'Mor', photo:'', initials:'👩' }];
  const childPlayers = hasChildren ? CHILDREN.map(c => ({ name:c.name, photo:(c._photoUrl||c.photoUrl)?aulaImg(c._photoUrl||c.photoUrl):'', initials:c.name.charAt(0) })) : [];
  // Custom spillere fra cache
  const customPlayers = JSON.parse(localStorage.getItem('mem_custom_players') || '[]')
    .map(name => ({ name, photo:'', initials:name.charAt(0).toUpperCase(), custom:true }));
  const allPlayers = [...childPlayers, ...fixedPlayers, ...customPlayers];

  const playerBtns = allPlayers.map((p, i) => {
    const active = mem.players.some(pl => pl.name === p.name);
    const photoHtml = p.photo
      ? '<img class="rs-child-img" src="' + p.photo + '" alt="" onerror="this.style.display=\'none\';this.nextElementSibling.style.display=\'flex\'">'
        + '<div class="rs-child-initials" style="display:none">' + p.initials + '</div>'
      : '<div class="rs-child-initials">' + p.initials + '</div>';
    // Custom spillere får et lille ×-mærke
    const removeBtn = p.custom
      ? '<span class="mem-player-remove" onclick="event.stopPropagation();memRemoveCustomPlayer(\'' + p.name + '\')" title="Fjern">×</span>'
      : '';
    return '<button class="rs-child-btn ' + (active?'rs-child-active':'') + '" onclick="memToggleFixed(' + i + ')" style="position:relative">'
      + photoHtml + '<span class="rs-child-name">' + p.name + '</span>' + removeBtn + '</button>';
  }).join('');

  const catBtns = MEM_CATEGORIES.map(cat =>
    '<button class="mem-cat-btn ' + (mem.category===cat.id?'mem-cat-active':'') + '" data-catid="' + cat.id + '" onclick="memSelectCat(\'' + cat.id + '\')">'
    + '<span class="mem-cat-icon">' + cat.icon + '</span><span class="mem-cat-label">' + cat.label + '</span></button>').join('');

  const gridBtns = MEM_GRIDS.map(g =>
    '<button class="mem-grid-btn ' + (mem.grid===g.id?'mem-grid-active':'') + '" data-gridid="' + g.id + '" onclick="memSelectGrid(\'' + g.id + '\')">'
    + '<span class="mem-grid-label">' + g.label + '</span><span class="mem-grid-desc">' + g.pairs + ' par</span></button>').join('');

  el.innerHTML = '<div class="mem-shell mem-setup-shell">'
    + '<div class="mem-topbar"><button class="family-back-btn" onclick="familyAppBack(\'family-kids\')" style="padding:0;margin:0">← Tilbage</button>'
    + '<span class="mem-setup-title">🧠 Huskespillet</span></div>'
    + '<div class="mem-setup-body">'
    + '<div class="mem-setup-section"><div class="mem-setup-label">Hvem spiller? <span class="mem-setup-hint">(vælg 1 eller flere)</span></div>'
    + '<div class="mem-child-row" id="mem-player-row">' + playerBtns
    + '<button class="mem-add-player-btn" onclick="memShowAddPlayer()" id="mem-add-btn">＋ Tilføj</button></div>'
    + '<div id="mem-add-input-wrap" style="display:none;margin-top:8px">'
    + '<input class="rs-name-input" id="mem-add-input" type="text" placeholder="Skriv navn…" style="margin-bottom:6px">'
    + '<button class="rs-start-btn" style="padding:10px;font-size:.9rem" onclick="memAddCustomPlayer()">Tilføj</button>'
    + '</div></div>'
    + '<div class="mem-setup-section"><div class="mem-setup-label">Vælg kategori</div><div class="mem-cat-grid">' + catBtns + '</div></div>'
    + '<div class="mem-setup-section"><div class="mem-setup-label">Vælg størrelse</div><div class="mem-grid-row">' + gridBtns + '</div></div>'
    + memPickerSummary()
    + '<button class="rs-start-btn" onclick="memStartGame()">Spil nu! 🧠</button>'
    + '</div></div>';
  el._memAllPlayers = allPlayers;
}

function memToggleFixed(idx) {
  const el = document.getElementById('view-app-huske');
  const all = el?._memAllPlayers; if (!all) return;
  const p = all[idx];
  const exists = mem.players.findIndex(pl => pl.name === p.name);
  if (exists >= 0) mem.players.splice(exists, 1);
  else mem.players.push({ name:p.name, photo:p.photo||'', score:0 });
  document.querySelectorAll('#mem-player-row .rs-child-btn').forEach((b,i) =>
    b.classList.toggle('rs-child-active', mem.players.some(pl => pl.name === all[i]?.name)));
}
function memShowAddPlayer() {
  const wrap = document.getElementById('mem-add-input-wrap'); if (!wrap) return;
  wrap.style.display = wrap.style.display === 'none' ? 'block' : 'none';
  if (wrap.style.display === 'block') document.getElementById('mem-add-input')?.focus();
}
function memAddCustomPlayer() {
  const input = document.getElementById('mem-add-input');
  const name = input?.value.trim(); if (!name) return;
  // Gem i cache
  const cached = JSON.parse(localStorage.getItem('mem_custom_players') || '[]');
  if (!cached.includes(name)) { cached.push(name); localStorage.setItem('mem_custom_players', JSON.stringify(cached)); }
  input.value = ''; document.getElementById('mem-add-input-wrap').style.display = 'none';
  // Genrender så knappen dukker op
  renderHuskespil();
  // Vælg den nye spiller automatisk
  const el = document.getElementById('view-app-huske');
  const all = el?._memAllPlayers || [];
  const idx = all.findIndex(p => p.name === name);
  if (idx >= 0) memToggleFixed(idx);
}

function memRemoveCustomPlayer(name) {
  const cached = JSON.parse(localStorage.getItem('mem_custom_players') || '[]')
    .filter(n => n !== name);
  localStorage.setItem('mem_custom_players', JSON.stringify(cached));
  // Fjern fra aktive spillere hvis valgt
  mem.players = mem.players.filter(p => p.name !== name);
  renderHuskespil();
}
function memSelectCat(id) {
  mem.category = id; mem.customWords = null;
  document.querySelectorAll('.mem-cat-btn').forEach(b=>b.classList.toggle('mem-cat-active',b.dataset.catid===id));
  memRefreshPickerSummary();
}
function memSelectGrid(id) {
  mem.grid = id; mem.customWords = null;
  document.querySelectorAll('.mem-grid-btn').forEach(b=>b.classList.toggle('mem-grid-active',b.dataset.gridid===id));
  memRefreshPickerSummary();
}

// ── Billedvælger ──────────────────────────────────────────────────────────

function memPickerSummary() {
  const gridCfg = MEM_GRIDS.find(g => g.id === mem.grid);
  const needed = gridCfg.pairs;
  const chosen = mem.customWords ? mem.customWords.length : 0;
  const label = mem.customWords
    ? (chosen === needed
        ? '✅ Valgt selv: ' + chosen + '/' + needed + ' billeder'
        : '🖼️ Valgt selv: ' + chosen + '/' + needed + ' billeder')
    : '🖼️ Tilfældige billeder';
  const btnLabel = mem.customWords ? 'Rediger valg' : 'Vælg selv';
  return '<div class="mem-picker-bar">'
    + '<span class="mem-picker-status' + (mem.customWords && chosen < needed ? ' mem-picker-incomplete' : '') + '">' + label + '</span>'
    + '<button class="mem-picker-open-btn" onclick="memOpenPicker()">' + btnLabel + ' 🎨</button>'
    + '</div>';
}

function memRefreshPickerSummary() {
  const bar = document.querySelector('.mem-picker-bar');
  if (!bar) return;
  const newEl = document.createElement('div');
  newEl.innerHTML = memPickerSummary();
  bar.replaceWith(newEl.firstChild);
}

function memOpenPicker() {
  const cat = MEM_CATEGORIES.find(c => c.id === mem.category);
  const gridCfg = MEM_GRIDS.find(g => g.id === mem.grid);
  const needed = gridCfg.pairs;
  const fnMap = MEM_FILENAMES[mem.category] || {};
  // Aktuelle valg (kopi)
  const selected = new Set(mem.customWords || []);

  const shell = document.querySelector('.mem-shell'); if (!shell) return;
  document.getElementById('mem-picker-overlay')?.remove();

  const imgGrid = cat.words.map(word => {
    const fname = fnMap[word] || word.replace(/\s+/g,'-');
    const danish = MEM_DANISH[fname] || (fname.charAt(0).toUpperCase()+fname.slice(1).replace(/-/g,' '));
    const isSel = selected.has(word);
    return '<div class="mem-pick-card' + (isSel?' mem-pick-sel':'') + '" data-word="' + word + '" onclick="memPickerToggle(this,\'' + word.replace(/'/g,"\\'") + '\',' + needed + ')">'
      + '<img src="/static/memory/' + mem.category + '/' + fname + '.jpg" alt="' + danish + '" loading="lazy"'
      + ' onerror="this.style.display=\'none\'">'
      + '<span>' + danish + '</span>'
      + '<div class="mem-pick-check">✓</div>'
      + '</div>';
  }).join('');

  const overlay = document.createElement('div');
  overlay.id = 'mem-picker-overlay';
  overlay.className = 'mem-picker-overlay';
  overlay.innerHTML = '<div class="mem-picker-modal">'
    + '<div class="mem-picker-header">'
    + '<span class="mem-picker-title">Vælg billeder</span>'
    + '<span class="mem-picker-count" id="mem-pick-count">' + selected.size + '/' + needed + '</span>'
    + '</div>'
    + '<div class="mem-pick-grid">' + imgGrid + '</div>'
    + '<div class="mem-picker-footer">'
    + '<button class="mem-picker-cancel" onclick="memClosePicker()">Annuller</button>'
    + '<button class="mem-picker-confirm" id="mem-pick-confirm" onclick="memConfirmPicker(' + needed + ')"'
    + (selected.size === needed ? '' : ' disabled') + '>Brug disse ' + needed + ' billeder ✓</button>'
    + '</div>'
    + '</div>';
  overlay.addEventListener('click', e => { if (e.target===overlay) memClosePicker(); });
  document.body.appendChild(overlay);
  // Gem temp-valg på overlay
  overlay._selected = selected;
}

function memPickerToggle(el, word, needed) {
  const overlay = document.getElementById('mem-picker-overlay'); if (!overlay) return;
  const sel = overlay._selected;
  if (sel.has(word)) {
    sel.delete(word);
    el.classList.remove('mem-pick-sel');
  } else {
    if (sel.size >= needed) return; // max nået
    sel.add(word);
    el.classList.add('mem-pick-sel');
  }
  const countEl = document.getElementById('mem-pick-count');
  if (countEl) countEl.textContent = sel.size + '/' + needed;
  const confirmBtn = document.getElementById('mem-pick-confirm');
  if (confirmBtn) {
    confirmBtn.disabled = (sel.size !== needed);
    confirmBtn.textContent = sel.size === needed
      ? 'Brug disse ' + needed + ' billeder ✓'
      : 'Vælg ' + sel.size + '/' + needed + ' billeder';
  }
}

function memConfirmPicker(needed) {
  const overlay = document.getElementById('mem-picker-overlay'); if (!overlay) return;
  const sel = overlay._selected;
  if (sel.size !== needed) return;
  mem.customWords = [...sel];
  overlay.remove();
  memRefreshPickerSummary();
}

function memClosePicker() {
  document.getElementById('mem-picker-overlay')?.remove();
}

function memStartGame() {
  const gridCfg = MEM_GRIDS.find(g => g.id === mem.grid);
  const cat = MEM_CATEGORIES.find(c => c.id === mem.category);
  mem.players.forEach(p => p.score = 0);
  if (!mem.players.length) mem.players = [{ name:'', photo:'', score:0 }];
  mem.currentPlayer = Math.floor(Math.random() * mem.players.length);
  mem.moves = 0; mem.flipped = []; mem.locked = false; mem.phase = 'play';
  // Brug brugervalgte billeder eller tilfældige
  const words = mem.customWords
    ? [...mem.customWords]
    : shuffle([...cat.words]).slice(0, gridCfg.pairs);
  const fnMap = MEM_FILENAMES[mem.category] || {};
  mem.cards = shuffle([...words, ...words].map((word, i) => {
    const fname = fnMap[word] || word.replace(/\s+/g,'-');
    return { id:i, word, img:'/static/memory/'+mem.category+'/'+fname+'.jpg', flipped:false, matched:false };
  }));
  memRender();
  // Vis hvem der starter — som tur-dialog
  if (mem.players.length > 1) {
    setTimeout(() => memShowTurnDialog(), 300);
  }
}

function memRender() {
  const el = document.getElementById('view-app-huske'); if (!el) return;
  const gridCfg = MEM_GRIDS.find(g => g.id === mem.grid);
  const multi = mem.players.length > 1, cur = mem.players[mem.currentPlayer];
  const catIcon = MEM_CATEGORIES.find(c => c.id === mem.category)?.icon || '❓';

  const scoreboard = multi
    ? mem.players.map((p,i) => '<div class="mem-player'+(i===mem.currentPlayer?' mem-player-active':'')+'">'
        +(p.photo?'<img class="mem-player-img" src="'+p.photo+'" alt="">':'<div class="mem-player-init">'+(p.name?p.name.charAt(0):'?')+'</div>')
        +'<span class="mem-player-name">'+(p.name||'Spiller')+'</span><span class="mem-player-score">'+p.score+'</span></div>').join('')
    : '<div class="mem-solo-info">'+(cur?.photo?'<img class="mem-player-img" src="'+cur.photo+'" alt="">':'')
      +'<span class="mem-move-count">Træk: <strong>'+mem.moves+'</strong></span></div>';

  const cardHtml = mem.cards.map((card,idx) => {
    const fname = MEM_FILENAMES[mem.category]?.[card.word] || card.word;
    const danish = MEM_DANISH[fname] || (fname.charAt(0).toUpperCase()+fname.slice(1).replace(/-/g,' '));
    return '<div class="mem-card'+(card.flipped||card.matched?' mem-flipped':'')+(card.matched?' mem-matched':'')+'" id="mem-card-'+idx+'" onclick="memFlip('+idx+')">'
      +'<div class="mem-card-inner"><div class="mem-card-back">🧠</div>'
      +'<div class="mem-card-front"><img src="'+card.img+'" alt="'+danish+'" loading="lazy"'
      +' onerror="this.parentElement.innerHTML=\'<span class=mem-card-emoji>'+catIcon+'</span><span class=mem-card-word>'+danish+'</span>\'"></div>'
      +'</div></div>';
  }).join('');

  el.innerHTML = '<div class="mem-shell" style="--mem-cols:'+gridCfg.cols+'">'
    +'<div class="mem-topbar"><button class="family-back-btn" onclick="renderHuskespil()" style="padding:0;margin:0">← Indstillinger</button>'
    +'<div class="mem-scoreboard">'+scoreboard+'</div></div>'
    +'<div class="mem-board" id="mem-board">'+cardHtml+'</div></div>';
}

function memFlip(idx) {
  if (mem.locked) return;
  const card = mem.cards[idx];
  if (!card || card.flipped || card.matched || mem.flipped.length >= 2) return;
  card.flipped = true; mem.flipped.push(idx);
  document.getElementById('mem-card-'+idx)?.classList.add('mem-flipped');

  if (mem.flipped.length === 2) {
    mem.locked = true; mem.moves++;
    const mc = document.querySelector('.mem-move-count strong'); if (mc) mc.textContent = mem.moves;
    const [i1,i2] = mem.flipped;
    const match = mem.cards[i1].word === mem.cards[i2].word;
    setTimeout(() => {
      if (match) {
        mem.cards[i1].matched = mem.cards[i2].matched = true;
        document.getElementById('mem-card-'+i1)?.classList.add('mem-matched');
        document.getElementById('mem-card-'+i2)?.classList.add('mem-matched');
        if (mem.players.length) mem.players[mem.currentPlayer].score++;
        document.querySelectorAll('.mem-player-score').forEach((el,i) => { if (mem.players[i]) el.textContent = mem.players[i].score; });
        const fname = MEM_FILENAMES[mem.category]?.[mem.cards[i1].word] || mem.cards[i1].word;
        memShowToast('Flot ✅ ' + (MEM_DANISH[fname] || (fname.charAt(0).toUpperCase()+fname.slice(1).replace(/-/g,' '))));
        mem.flipped = []; mem.locked = false;
        if (mem.cards.every(c => c.matched)) setTimeout(memShowWin, 800);
      } else {
        mem.cards[i1].flipped = mem.cards[i2].flipped = false;
        document.getElementById('mem-card-'+i1)?.classList.remove('mem-flipped');
        document.getElementById('mem-card-'+i2)?.classList.remove('mem-flipped');
        mem.flipped = [];
        if (mem.players.length > 1) {
          mem.currentPlayer = (mem.currentPlayer+1) % mem.players.length;
          document.querySelectorAll('.mem-player').forEach((el,i) => el.classList.toggle('mem-player-active', i===mem.currentPlayer));
          memShowTurnDialog();
        } else { mem.locked = false; }
      }
    }, 900);
  }
}

function memShowTurnDialog() {
  const p = mem.players[mem.currentPlayer]; if (!p) return;
  const shell = document.querySelector('.mem-shell'); if (!shell) return;
  document.getElementById('mem-turn-overlay')?.remove();
  const overlay = document.createElement('div');
  overlay.id = 'mem-turn-overlay'; overlay.className = 'mem-turn-overlay';
  overlay.innerHTML = '<div class="mem-turn-modal">'
    +(p.photo?'<img class="mem-turn-photo" src="'+p.photo+'" alt="">':'<div class="mem-turn-initials">'+(p.name?p.name.charAt(0):'?')+'</div>')
    +'<div class="mem-turn-text">Nu er det<br><strong>'+(p.name||'Spillerens')+'</strong><br>tur! 🎯</div>'
    +'<button class="mem-turn-btn" onclick="memDismissTurn()">Klar! 👍</button>'
    +'<button class="mem-skip-btn" onclick="memSkipTurn()">Spring over ⏭️</button>'
    +'</div>';
  overlay.addEventListener('click', e => { if (e.target===overlay) memDismissTurn(); });
  shell.appendChild(overlay); mem.locked = true;
}
function memDismissTurn() { document.getElementById('mem-turn-overlay')?.remove(); mem.locked = false; }
function memSkipTurn() {
  document.getElementById('mem-turn-overlay')?.remove();
  mem.currentPlayer = (mem.currentPlayer + 1) % mem.players.length;
  document.querySelectorAll('.mem-player').forEach((el,i) => el.classList.toggle('mem-player-active', i===mem.currentPlayer));
  memShowTurnDialog();
}

function memShowToast(msg) {
  document.getElementById('mem-toast')?.remove();
  const shell = document.querySelector('.mem-shell'); if (!shell) return;
  const t = document.createElement('div'); t.id='mem-toast'; t.className='mem-toast'; t.textContent=msg;
  shell.appendChild(t); setTimeout(() => t.remove(), 1600);
}

function memShowWin() {
  const el = document.getElementById('view-app-huske'); if (!el) return;
  const multi = mem.players.length > 1;
  let inner;
  if (multi) {
    const sorted = [...mem.players].sort((a,b)=>b.score-a.score);
    const winner = sorted[0], tied = sorted.filter(p=>p.score===winner.score).length > 1;
    inner = '<div class="mem-win-trophy">'+(tied?'🤝':'🏆')+'</div>'
      +'<div class="mem-win-title">'+(tied?'Uafgjort!':(winner.name||'Spiller')+' vandt!')+'</div>'
      +'<div class="mem-win-scores">'
      +sorted.map((p,i)=>'<div class="mem-win-row'+(i===0&&!tied?' mem-win-first':'')+'">'
        +(p.photo?'<img class="mem-player-img" src="'+p.photo+'" alt="">':'<div class="mem-player-init">'+(p.name?p.name.charAt(0):'?')+'</div>')
        +'<span>'+(p.name||'Spiller')+'</span><span class="mem-win-pts">'+p.score+' par</span></div>').join('')
      +'</div>';
  } else {
    const p = mem.players[0];
    inner = '<div class="mem-win-trophy">🎉</div>'
      +'<div class="mem-win-title">'+(p?.name?'Flot, '+p.name+'!':'Flot klaret!')+'</div>'
      +'<div class="mem-win-sub">'+mem.moves+' træk</div>';
  }
  el.innerHTML = '<div class="mem-shell mem-win-shell"><div class="mem-win-box">'+inner
    +'<button class="rs-start-btn" onclick="memStartGame()" style="margin-top:8px">Spil igen! 🔄</button>'
    +'<button class="mem-back-btn" onclick="renderHuskespil()">← Ny opsætning</button>'
    +'</div></div>';
}
