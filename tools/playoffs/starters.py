"""Read-only, source-backed goalie reports with conservative confirmation rules."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import hashlib
import json
import os
import re
import urllib.parse
import urllib.request

from advanced import normalized

SOURCES=Path(__file__).with_name('starter_sources.json')
REPORTS=Path(__file__).with_name('starter_reports.json')


def valid_source_url(url):
    return isinstance(url,str) and re.fullmatch(r'https://(?:(?:x|twitter)\.com/[A-Za-z0-9_]+/status/\d+|www\.rotowire\.com/hockey/player/[a-z0-9-]+-\d+)',url) is not None


def valid_report(report, game, rosters, now):
    try:
        at=datetime.fromisoformat(report['reported_at'].replace('Z','+00:00'))
        observed=datetime.fromisoformat(now.replace('Z','+00:00'))
        start=datetime.fromisoformat(game['start'].replace('Z','+00:00'))
        return (report['game_id']==game['id'] and report['team'] in {game['home'],game['away']}
                and report['status'] in {'confirmed','likely','conflicting','not_starting'}
                and report['player_id'] in {p['id'] for p in rosters.get(report['team'],[]) if p['position']=='goalies'}
                and start-timedelta(hours=36)<=at<start and at<=observed+timedelta(minutes=5)
                and valid_source_url(report['source_url'])
                and (not report.get('game_start') or report['game_start']==game['start'])
                and isinstance(report['author'],str) and 0<len(report['author'])<80)
    except (KeyError,TypeError,ValueError):
        return False


def parse_post(post, author, source, games, rosters):
    text=post.get('text','')
    if any(r.get('type')=='retweeted' for r in post.get('referenced_tweets',[])):
        return []
    try:
        at=datetime.fromisoformat(post['created_at'].replace('Z','+00:00'))
    except (KeyError,ValueError):
        return []
    output=[]
    for game in games:
        start=datetime.fromisoformat(game['start'].replace('Z','+00:00'))
        if not 0<(start-at).total_seconds()<=129600:
            continue
        for team in [game['home'],game['away']]:
            if team not in source['teams']:
                continue
            for player in rosters.get(team,[]):
                if player['position']!='goalies':
                    continue
                last=normalized(player['name'].split()[-1])
                for clause in re.split(r'[\n;.!?]',text):
                    words={normalized(w[:-2] if w.lower().endswith("'s") else w) for w in re.findall(r"[\wÀ-ž'-]+",clause)}
                    if last not in words:
                        continue
                    negative=bool(re.search(r"\b(will not start|won't start|is not starting|isn't starting|not starting|scratched)\b",clause,re.I))
                    uncertain=bool(re.search(r'\b(expected|likely|projected|probable|slated|slotted|scheduled|should|could|might|may|morning skate|first goalie off)\b',clause,re.I))
                    explicit=bool(re.search(r"\b(will start|(?:gets|will get|will draw|will receive) (?:the )?(?:starting )?(?:start|nod)|will be in (?:goal|net)|will (?:guard|defend) (?:the )?(?:home |road |away |visiting )?(?:goal|net|crease)|will be between the pipes|starting (?:goalie|goaltender)|confirmed (?:starter|to start|in goal|in net)|starts (?:tonight|today|tomorrow)|tonight.s starter|today.s starter)\b",clause,re.I))
                    if not explicit and not uncertain and not negative:
                        continue
                    # An untimed report applies only to the next game within 24 hours.
                    if 'tomorrow' in clause.lower():
                        from zoneinfo import ZoneInfo
                        if game['date']!=(at.astimezone(ZoneInfo('America/New_York')).date()+timedelta(days=1)).isoformat():
                            continue
                    elif re.search(r'\b(tonight|today)\b',clause,re.I):
                        from zoneinfo import ZoneInfo
                        if game['date']!=at.astimezone(ZoneInfo('America/New_York')).date().isoformat():
                            continue
                    elif any(word in clause.lower() for word in ['monday','tuesday','wednesday','thursday','friday','saturday','sunday']):
                        if datetime.fromisoformat(game['date']).strftime('%A').lower() not in clause.lower():
                            continue
                    elif (start-at).total_seconds()>86400:
                        continue
                    elif game['id']!=min((g for g in games if team in [g['home'],g['away']] and datetime.fromisoformat(g['start'].replace('Z','+00:00'))>at),key=lambda g:g['start'])['id']:
                        continue
                    output.append({'game_id':game['id'],'team':team,'player_id':player['id'],'name':player['name'],
                                   'status':'not_starting' if negative else 'likely' if uncertain else 'confirmed','author':source.get('name',author),
                                   'source_url':f'https://x.com/{author}/status/{post["id"]}','reported_at':post['created_at'],
                                   'source_kind':'team' if source.get('official') else 'journalist',
                                   'correction':bool(re.search(r"\b(update|instead|change|will not start|won't start)\b",text,re.I))})
    return output


def search_batches(sources, rosters):
    """Keep every active source in a query within the recent-search length limit."""
    if not sources:
        return []
    surnames=sorted({p['name'].split()[-1] for s in sources for t in s['teams'] for p in rosters.get(t,[]) if p['position']=='goalies'})
    if not surnames:
        return []
    query='('+' OR '.join('from:'+s['handle'] for s in sources)+') ('+' OR '.join('"'+n+'"' for n in surnames)+') (start OR starts OR starting OR net OR goalie OR crease) -is:retweet'
    if len(query)<=512:
        return [(sources,query)]
    if len(sources)==1:
        raise ValueError('Goalie source query is too long')
    middle=len(sources)//2
    return search_batches(sources[:middle],rosters)+search_batches(sources[middle:],rosters)


def collect(games, rosters, old, now):
    at=datetime.fromisoformat(now.replace('Z','+00:00'))
    future=[g for g in games if 0<(datetime.fromisoformat(g['start'].replace('Z','+00:00'))-at).total_seconds()<=129600]
    index={g['id']:g for g in future};reports=[]
    for g in old.get('games',[]):
        for side in ['home','away']:
            r=g.get('context',{}).get(side,{}).get('goalie',{}).get('report')
            if r and r.get('game_id') in index and valid_report(r,index[r['game_id']],rosters,now):
                reports.append(r)
    if REPORTS.exists():
        for r in json.loads(REPORTS.read_text()).get('reports',[]):
            if r.get('game_id') in index and valid_report(r,index[r['game_id']],rosters,now):
                reports.append(r)
    mode=os.environ.get('STARTER_REPORT_SOURCE','rss')
    if mode not in {'rss','x','manual'}:
        raise ValueError('Unknown starter report source')
    if mode=='rss':
        from starter_rss import collect as collect_rss
        fresh,meta=collect_rss(future,rosters,old,now)
        return select_reports(reports+fresh),meta
    if mode=='manual':
        return select_reports(reports),{'source':'manual','status':'manual','checked_at':None,'requests':0,'x_requests':0}
    token=os.environ.get('X_BEARER_TOKEN','');state='not_configured';cursors=dict(old.get('starter_feed',{}).get('cursors',{}));requests=0
    try:
        daily_limit=max(0,min(10000,int(os.environ.get('X_MAX_POSTS_PER_DAY','0'))))
    except ValueError:
        daily_limit=0
    usage=old.get('starter_feed',{});posts_read=usage.get('posts_read',0) if usage.get('usage_day')==now[:10] else 0
    if token and not daily_limit:
        state='disabled_until_read_cap_set'
    last=old.get('starter_feed',{}).get('checked_at')
    due=not last or (at-datetime.fromisoformat(last.replace('Z','+00:00'))).total_seconds()>=900
    if token and daily_limit and future and due:
        sources=json.loads(SOURCES.read_text())['sources'];active={g[k] for g in future for k in ['home','away']}
        sources=[s for s in sources if active.intersection(s['teams'])]
        batches=search_batches(sources,rosters)
        state='checked'
        for batch,query in batches:
            if daily_limit-posts_read<10:
                state='daily_read_limit';break
            handles={s['handle'].lower():s for s in batch}
            key=hashlib.sha256(query.encode()).hexdigest()[:16]
            params={'query':query,'max_results':10,'tweet.fields':'created_at,author_id,referenced_tweets','expansions':'author_id','user.fields':'username'}
            if cursors.get(key):
                params['since_id']=cursors[key]
            else:
                params['start_time']=(at-timedelta(hours=24)).isoformat(timespec='seconds').replace('+00:00','Z')
            request=urllib.request.Request('https://api.x.com/2/tweets/search/recent?'+urllib.parse.urlencode(params),headers={'Authorization':'Bearer '+token,'User-Agent':'Sweater.win read-only goalie reports'})
            try:
                requests+=1
                with urllib.request.urlopen(request,timeout=12) as response:
                    data=json.load(response)
                posts_read+=len(data.get('data',[]))
                authors={r['id']:r['username'] for r in data.get('includes',{}).get('users',[])}
                for post in data.get('data',[]):
                    author=authors.get(post.get('author_id'),'')
                    if author.lower() in handles:
                        reports.extend(parse_post(post,author,handles[author.lower()],future,rosters))
                # Avoid skipping older reports if a batch was truncated; overlapping reads deduplicate below.
                if not data.get('meta',{}).get('next_token') and data.get('meta',{}).get('newest_id'):
                    cursors[key]=data['meta']['newest_id']
            except Exception:
                state='unavailable'
    elif token and daily_limit:
        state=old.get('starter_feed',{}).get('status','waiting')
    return select_reports(reports),{'source':'X','status':state,'checked_at':now if token and daily_limit and due else last,'cursors':cursors,'requests':requests,'x_requests':requests,'usage_day':now[:10],'posts_read':posts_read,'daily_read_cap':daily_limit}


def select_reports(reports):
    unique={(r['game_id'],r['team'],r['source_url'],r['player_id'],r['reported_at']):r for r in reports}
    chosen={}
    for r in sorted(unique.values(),key=lambda r:(r['reported_at'],{'not_starting':0,'likely':1,'conflicting':2,'confirmed':3}[r['status']])):
        key=(r['game_id'],r['team']);previous=chosen.get(key)
        if previous and previous['status']=='confirmed' and r['status']=='confirmed' and previous['player_id']!=r['player_id'] and r.get('source_kind')!='team' and not r.get('correction'):
            r={**r,'status':'conflicting'}
        if previous and previous['status']=='confirmed' and r['status']=='likely':
            continue
        chosen[key]=r
    return chosen
