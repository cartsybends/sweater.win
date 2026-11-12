"""Publish same-origin NHL portraits so image exports never depend on CDN CORS."""
from concurrent.futures import ThreadPoolExecutor
import hashlib,io,json,shutil,sys,urllib.parse,urllib.request
from pathlib import Path
from PIL import Image

ROOT=Path(__file__).resolve().parents[2]

def source(player):
    if type(player['id']) is not int or not 1000000<=player['id']<=9999999:
        raise ValueError('Invalid NHL player identifier')
    url=player.get('headshot') or f"https://assets.nhle.com/mugs/nhl/latest/{player['id']}.png"
    parsed=urllib.parse.urlsplit(url)
    if parsed.scheme!='https' or parsed.netloc!='assets.nhle.com' or not parsed.path.startswith('/mugs/nhl/') or not parsed.path.endswith(f"/{player['id']}.png") or parsed.query or parsed.fragment:
        raise ValueError('Unexpected NHL portrait source')
    return url

def publish(data,destination,cache):
    destination.mkdir(parents=True,exist_ok=True);cache.mkdir(parents=True,exist_ok=True)
    def portrait(player):
        url=source(player);key=hashlib.sha256(url.encode()).hexdigest()[:16]
        saved=cache/f"{player['id']}-{key}.webp"
        if not saved.exists():
            with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Sweater point projections'}),timeout=20) as response:
                content=response.read(4*1024*1024)
            with Image.open(io.BytesIO(content)) as image:
                image=image.convert('RGBA');image.thumbnail((256,256),Image.Resampling.LANCZOS)
                image.save(saved,'WEBP',quality=88,method=4)
        shutil.copy2(saved,destination/f"{player['id']}.webp")
    def attempt(player):
        try:portrait(player);return True
        except Exception as error:
            print('Portrait unavailable:',player['id'],type(error).__name__);return False
    with ThreadPoolExecutor(max_workers=6) as pool:count=sum(pool.map(attempt,data['players']))
    print(f"Published {count}/{len(data['players'])} same-origin projection portraits")
    return count

if __name__=='__main__':
    data=json.loads((ROOT/'projections_cache.json').read_text())
    if '--cache-key' in sys.argv:
        print('key='+hashlib.sha256(json.dumps([(p['id'],source(p)) for p in data['players']]).encode()).hexdigest()[:24]);sys.exit(0)
    out=Path(sys.argv[1] if len(sys.argv)>1 else 'site/projection-headshots')
    publish(data,out,ROOT/'.cache/projection-headshots')
