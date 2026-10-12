"""Reproducible public NHL clip collection; never record expiring delivery URLs."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import urllib.request, json, re, html, hashlib, subprocess, shutil, unicodedata, argparse

WORK = Path(__file__).resolve().parents[3]
ROOT = WORK / 'goal-expansion'
REPO = WORK / 'sweater-live'
NAMES = ['Jack Hughes','David Pastrnak','Nikita Kucherov','Aleksander Barkov','Mitch Marner','William Nylander','Kirill Kaprizov','Tim Stützle','Matthew Tkachuk','Brady Tkachuk','Nick Suzuki','Cole Caufield','Sebastian Aho','Brayden Point','Patrick Kane','Lucas Raymond','Dylan Larkin','Jason Robertson','Filip Forsberg','Adam Fox','Erik Karlsson','Zach Werenski','Rasmus Dahlin','Jake Sanderson','Brock Boeser','Timo Meier','Nico Hischier','Jesper Bratt','Seth Jarvis','Sam Reinhart']
PIDS = [8481559,8477956,8476453,8477493,8478483,8477939,8478864,8482116,8479314,8480801,8480018,8481540,8478427,8478010,8474141,8482078,8477946,8480027,8476887,8479323,8474578,8478460,8480839,8482105,8478444,8478414,8480002,8479407,8482093,8477933]
def normalize(s): return ''.join(c for c in unicodedata.normalize('NFKD',s.lower()) if not unicodedata.combining(c))
def get(url,headers=None): return urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0',**(headers or {})}),timeout=50)
def jsonget(url):
    with get(url) as response:return json.load(response)
def api(path):
    cache=ROOT/'api'/(path.replace('/','_')+'.json')
    if cache.exists():return json.loads(cache.read_text())
    data=jsonget('https://api-web.nhle.com/v1/'+path)
    cache.parent.mkdir(parents=True,exist_ok=True);cache.write_text(json.dumps(data))
    return data
def atomic(path,data):
    tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n');tmp.replace(path)
def probe(path):return json.loads(subprocess.check_output(['ffprobe','-v','error','-show_format','-show_streams','-of','json',str(path)],text=True))
def storyboard(path,ident,duration):
    from PIL import Image,ImageDraw
    frames=ROOT/'storyboards'/(ident+'-frames');frames.mkdir(exist_ok=True)
    subprocess.run(['ffmpeg','-v','error','-y','-i',str(path),'-vf','fps=2/3,scale=320:180','-q:v','3',str(frames/'%04d.jpg')],check=True)
    tiles=[]
    for index,fp in enumerate(sorted(frames.glob('*.jpg'))):
        t=index*1.5;im=Image.open(fp)
        tile=Image.new('RGB',(320,205),'#141414');tile.paste(im,(0,0));ImageDraw.Draw(tile).text((8,185),f'{ident}  {t:.1f}s',fill='white');tiles.append(tile)
    cols=5
    for offset in range(0,len(tiles),40):
        subset=tiles[offset:offset+40];sheet=Image.new('RGB',(320*cols,205*((len(subset)+cols-1)//cols)),'#141414')
        for n,tile in enumerate(subset):sheet.paste(tile,((n%cols)*320,(n//cols)*205))
        sheet.save(ROOT/'storyboards'/f'{ident}-{offset//40+1:02d}.jpg',quality=86)

def candidates():
    roster=json.loads((REPO/'current_rosters.json').read_text())
    pids={normalize(v['name']):(int(k),v) for k,v in roster.items()}
    records=[]
    for i,n in enumerate(NAMES,10):
        pid=PIDS[i-10];records.append({'id':f'goal-{i:02d}','pid':pid,'player':n,'status':'awaiting_source','candidates':[]})
    games=[]
    for date in ['2025-01-25','2025-02-01','2025-10-11']:
        games.extend(api('score/'+date)['games'])
    targets={r['pid']:r for r in records}
    def gameinfo(game):
        data=api(f"gamecenter/{game['id']}/landing")
        box=api(f"gamecenter/{game['id']}/boxscore")
        jerseys={}
        for team in box.get('playerByGameStats',{}).values():
            for players in team.values():
                if isinstance(players,list):
                    for p in players:jerseys[p['playerId']]=p.get('sweaterNumber')
        found=[]
        for period in data.get('summary',{}).get('scoring',[]):
            for goal in period['goals']:
                if goal['playerId'] in targets and goal.get('highlightClip'):
                    found.append((goal['playerId'],{'game_id':game['id'],'date':data['gameDate'],'team':goal['teamAbbrev']['default'],'jersey':jerseys.get(goal['playerId']),'source':goal.get('highlightClipSharingUrl') or f"https://www.nhl.com/gamecenter/{game['id']}",'source_video_id':str(goal['highlightClip']),'shot_type':goal.get('shotType'),'event_id':goal['eventId']}))
        return found
    with ThreadPoolExecutor(max_workers=6) as pool:
        for result in pool.map(gameinfo,games):
            for pid,record in result:targets[pid]['candidates'].append(record)
    for r in records:
        r['candidates'].sort(key=lambda c:(c['date'],c['event_id']))
        if r['candidates']:r.update(r['candidates'][0]);r['status']='source_selected'
    # Recovered media must retain the exact original source and scorer.
    overrides={10:('6367771449112','2024020779'),15:('6368137903112','2024020845'),20:('6367766068112','2024020779')}
    for i,(video,game) in overrides.items():
        r=records[i-10];match=next((c for c in r['candidates'] if c['source_video_id']==video),None)
        if match:r.update(match)
    atomic(ROOT/'new-sources.json',records)
    atomic(REPO/'tools/who_scored/expansion-sources.json',records)
    print('Source candidates: '+', '.join(f"{r['id']} {r['player']} ({len(r['candidates'])})" for r in records),flush=True)
    return records

def player_config():
    url='https://www.nhl.com/video/njd-mtl-hughes-scores-goal-against-jakub-dobes-6367771449112'
    with get(url) as response:page=response.read().decode()
    match=re.search(r'data-plugin="bc-video-player-events"\s+data-options=\'([^\']+)\'',page)
    opts=json.loads(html.unescape(match.group(1)))
    account,player=opts['brightcoveAccount'],opts['brightcovePlayer']
    config=jsonget(f'https://players.brightcove.net/{account}/{player}_default/config.json')
    return account,config['video_cloud']['policy_key']
def download(r,config):
    account,policy=config
    data=jsonget(f"https://edge.api.brightcove.com/playback/v1/accounts/{account}/videos/{r['source_video_id']}") if not policy else None
    if data is None:
        with get(f"https://edge.api.brightcove.com/playback/v1/accounts/{account}/videos/{r['source_video_id']}",{'Accept':'application/json;pk='+policy}) as response:data=json.load(response)
    surname=normalize(r['player'].split()[-1]);title=normalize(' '.join([data.get('name',''),data.get('description',''),data.get('long_description','')]))
    if surname not in title:raise ValueError('Media description does not match scorer: '+data.get('name',''))
    sources=[s for s in data.get('sources',[]) if s.get('container')=='MP4' and s.get('src','').startswith('https://') and not s.get('key_systems')]
    eligible=[s for s in sources if s.get('height',0)<=720] or sources
    if not eligible:raise ValueError('No public unencrypted MP4')
    chosen=max(eligible,key=lambda s:(s.get('height',0),s.get('avg_bitrate',0)))
    path=ROOT/'originals'/(r['id']+'.mp4')
    if not path.exists():
        partial=path.with_suffix('.partial')
        with get(chosen['src']) as response,partial.open('wb') as stream:shutil.copyfileobj(response,stream)
        partial.replace(path)
    metadata=probe(path);stream=next(s for s in metadata['streams'] if s['codec_type']=='video');duration=float(metadata['format']['duration'])
    storyboard(path,r['id'],duration)
    return {**r,'original_path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'duration':duration,'width':stream['width'],'height':stream['height'],'media_title':data.get('name'),'status':'original_ready'}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--candidates',action='store_true');parser.add_argument('--ids',nargs='*');args=parser.parse_args()
    for folder in ['api','originals','storyboards']: (ROOT/folder).mkdir(parents=True,exist_ok=True)
    records=candidates() if args.candidates or not (ROOT/'new-sources.json').exists() else json.loads((ROOT/'new-sources.json').read_text())
    config=player_config()
    selected=[r for r in records if r.get('source_video_id') and (not args.ids or r['id'] in args.ids)]
    with ThreadPoolExecutor(max_workers=3) as pool:
        fs={pool.submit(download,r,config):r for r in selected}
        for f in as_completed(fs):
            r=fs[f]
            try:
                ready=f.result();records[next(i for i,x in enumerate(records) if x['id']==r['id'])]=ready
                atomic(ROOT/'new-sources.json',records);atomic(REPO/'tools/who_scored/expansion-sources.json',records)
                print(f"Ready {r['id']} {r['player']} {ready['duration']:.2f}s",flush=True)
            except Exception as error:print(f"Failed {r['id']} {type(error).__name__}: {error}",flush=True)
