"""
Download memory images from Pexels API.
Run from project root: python scripts/download_memory_images.py
"""
import os, time, sys

try:
    import requests
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'requests', '-q'])
    import requests

API_KEY = 'c864uDk9vHLsUiR192IgZHqgdhvB73qhhfBYFxyKkFRBb0e0o3LKFT5D'
BASE    = os.path.join(os.path.dirname(__file__), '..', 'frontend', 'static', 'memory')

# Søgeord per billede — Pexels finder det bedste foto
IMAGES = {
  'animals': [
    'lion', 'tiger', 'elephant', 'giraffe', 'zebra',
    'dolphin', 'wolf', 'bear', 'primate ape', 'cheetah',
    'penguin', 'koala', 'panda', 'flamingo', 'owl',
    'kangaroo', 'jaguar', 'leopard', 'rhinoceros', 'hippopotamus',
    'crocodile', 'fox', 'camel', 'peacock', 'meerkat',
    'lynx', 'moose', 'bison', 'armadillo', 'sloth',
    'chameleon', 'parrot',
  ],
  'space': [
    'moon', 'galaxy', 'astronaut', 'rocket', 'nebula',
    'saturn', 'comet', 'aurora', 'mars', 'jupiter',
    'milky way', 'sun', 'asteroid', 'space station', 'black hole',
    'hubble telescope', 'meteor', 'pillars of creation', 'solar eclipse', 'venus',
    'earth from space', 'uranus', 'pluto', 'supernova', 'cosmic dust',
    'lunar crater', 'spacewalk', 'observatory telescope', 'mercury planet', 'neptune',
    'satellite orbit', 'rocket launch',
  ],
  'ocean': [
    'shark', 'whale', 'octopus', 'coral reef', 'seahorse',
    'jellyfish', 'clownfish', 'sea turtle', 'lobster', 'seal',
    'starfish', 'walrus', 'dolphin', 'crab', 'orca',
    'narwhal', 'pufferfish', 'manta ray', 'squid', 'swordfish',
    'sea lion', 'manatee', 'barracuda', 'sea urchin', 'anglerfish',
    'hammerhead shark', 'sea anemone', 'moray eel', 'blue whale', 'sailfish',
    'sea cucumber', 'pelican',
  ],
  'nature': [
    'waterfall', 'mountain', 'forest', 'volcano', 'glacier',
    'rainbow', 'northern lights', 'butterfly', 'mushroom', 'sunflower',
    'sahara desert', 'grand canyon', 'sunset', 'dragonfly', 'oak tree',
    'cherry blossom', 'autumn leaves', 'ice cave', 'coral', 'fern',
    'lightning storm', 'sand dunes', 'cave stalactite', 'mangrove', 'lavender field',
    'frozen lake', 'redwood tree', 'meadow wildflowers', 'hot spring', 'fog forest',
    'cactus', 'bamboo forest',
  ],
  'food': [
    'pizza', 'sushi', 'taco', 'chocolate cake', 'donut',
    'ice cream', 'strawberry', 'watermelon', 'avocado', 'pineapple',
    'ramen', 'pancakes', 'croissant', 'chocolate', 'mango',
    'lemon', 'pomegranate', 'burger', 'pasta', 'cookie',
    'cheesecake', 'waffles', 'macarons', 'lobster dish', 'paella',
    'dim sum', 'baklava', 'acai bowl', 'churros', 'tiramisu',
    'crepes', 'bruschetta',
  ],
  'transport': [
    'steam train', 'sailboat', 'helicopter', 'motorcycle', 'submarine',
    'hot air balloon', 'bicycle', 'racing car', 'fire truck', 'jet plane',
    'vintage car', 'tram', 'speedboat', 'zeppelin', 'snowmobile',
    'double decker bus', 'cable car', 'kayak', 'space shuttle', 'hovercraft',
    'amphibious vehicle', 'dog sled', 'paraglider', 'jet ski', 'tugboat',
    'tank', 'horse carriage', 'rickshaw', 'monorail', 'seaplane',
    'container ship', 'quad bike',
  ],
}

# Filnavne (samme rækkefølge som IMAGES)
FILENAMES = {
  'animals':   ['lion','tiger','elephant','giraffe','zebra','dolphin','wolf','bear','gorilla','cheetah','penguin','koala','panda','flamingo','owl','kangaroo','jaguar','leopard','rhinoceros','hippopotamus','crocodile','fox','camel','peacock','meerkat','lynx','moose','bison','armadillo','sloth','chameleon','parrot'],
  'space':     ['moon','galaxy','astronaut','rocket','nebula','saturn','comet','aurora','mars','jupiter','milkyway','sun','asteroid','space-station','blackhole','hubble','meteor','pillars','eclipse','venus','earth','uranus','pluto','supernova','cosmic-dust','lunar-crater','spacewalk','observatory','mercury','neptune','satellite','rocket-launch'],
  'ocean':     ['shark','whale','octopus','coral-reef','seahorse','jellyfish','clownfish','sea-turtle','lobster','seal','starfish','walrus','dolphin','crab','orca','narwhal','pufferfish','ray','squid','swordfish','sea-lion','manatee','barracuda','sea-urchin','anglerfish','hammerhead','sea-anemone','moray-eel','blue-whale','sailfish','sea-cucumber','pelican'],
  'nature':    ['waterfall','mountain','forest','volcano','glacier','rainbow','northern-lights','butterfly','mushroom','flower','desert','canyon','sunset','dragonfly','oak-tree','cherry-blossom','autumn-leaves','ice-cave','coral','fern','lightning','sand-dunes','stalactite','mangrove','lavender','frozen-lake','redwood','meadow','hot-spring','fog-forest','cactus','bamboo'],
  'food':      ['pizza','sushi','taco','cake','donut','ice-cream','strawberry','watermelon','avocado','pineapple','ramen','pancakes','croissant','chocolate','mango','lemon','pomegranate','burger','pasta','cookie','cheesecake','waffles','macarons','lobster-dish','paella','dim-sum','baklava','acai-bowl','churros','tiramisu','crepes','bruschetta'],
  'transport': ['steam-train','sailboat','helicopter','motorcycle','submarine','hot-air-balloon','bicycle','racing-car','fire-truck','jet-plane','vintage-car','tram','speedboat','zeppelin','snowmobile','bus','cable-car','kayak','space-shuttle','hovercraft','amphibious','dog-sled','paraglider','jet-ski','tugboat','tank','horse-carriage','rickshaw','monorail','seaplane','container-ship','quad-bike'],
}

def fetch_pexels(session, query):
    """Hent første foto-URL fra Pexels søgning."""
    r = session.get(
        'https://api.pexels.com/v1/search',
        params={'query': query, 'per_page': 1, 'orientation': 'square'},
        timeout=15
    )
    r.raise_for_status()
    photos = r.json().get('photos', [])
    if not photos:
        return None
    return photos[0]['src']['medium']  # ~350x350px

def download_one(session, filename, query, out_dir):
    path = os.path.join(out_dir, filename + '.jpg')
    if os.path.exists(path) and os.path.getsize(path) > 5000:
        print(f'  SKIP  {filename}')
        return True
    try:
        img_url = fetch_pexels(session, query)
        if not img_url:
            print(f'  NONE  {filename} — ingen resultater for "{query}"')
            return False
        r = session.get(img_url, timeout=20)
        r.raise_for_status()
        with open(path, 'wb') as f:
            f.write(r.content)
        print(f'  OK    {filename} ({len(r.content)//1024}KB) — {query}')
        return True
    except Exception as e:
        print(f'  FAIL  {filename}: {e}')
        return False

def main():
    session = requests.Session()
    session.headers['Authorization'] = API_KEY

    ok = fail = 0
    for cat, queries in IMAGES.items():
        out_dir = os.path.join(BASE, cat)
        os.makedirs(out_dir, exist_ok=True)
        filenames = FILENAMES[cat]
        print(f'\n[{cat}]')
        for i, query in enumerate(queries):
            fname = filenames[i]
            if download_one(session, fname, query, out_dir):
                ok += 1
            else:
                fail += 1
            time.sleep(0.3)  # Pexels er generøs — 200 req/min
    print(f'\nFaerdig: {ok} OK, {fail} fejlede')

if __name__ == '__main__':
    main()
