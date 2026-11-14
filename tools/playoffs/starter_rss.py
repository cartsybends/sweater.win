"""Public NHL news syndication: retain only sourced starter facts, never prose."""
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
import re
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET

from advanced import normalized

URL='https://www.rotowire.com/rss/news.php?sport=NHL'
LINK=re.compile(r'https://www\.rotowire\.com/hockey/player/[a-z0-9-]+-\d+$')
CLUBS={'ANA':'Anaheim|Ducks','BOS':'Boston|Bruins','BUF':'Buffalo|Sabres','CAR':'Carolina|Hurricanes',
       'CBJ':'Columbus|Blue Jackets','CGY':'Calgary|Flames','CHI':'Chicago|Blackhawks','COL':'Colorado|Avalanche',
       'DAL':'Dallas|Stars','DET':'Detroit|Red Wings','EDM':'Edmonton|Oilers','FLA':'Florida|Panthers',
       'LAK':'Los Angeles|Kings','MIN':'Minnesota|Wild','MTL':'Montreal|Montréal|Canadiens',
       'NJD':'New Jersey|Devils','NSH':'Nashville|Predators','NYI':'Islanders','NYR':'Rangers',
       'OTT':'Ottawa|Senators','PHI':'Philadelphia|Flyers','PIT':'Pittsburgh|Penguins','SEA':'Seattle|Kraken',
       'SJS':'San Jose|Sharks','STL':'St. Louis|Blues','TBL':'Tampa Bay|Lightning','TOR':'Toronto|Maple Leafs',
       'UTA':'Utah|Mammoth','VAN':'Vancouver|Canucks','VGK':'Vegas|Golden Knights','WPG':'Winnipeg|Jets','WSH':'Washington|Capitals'}


def opponents_match(description, game):
    for match in re.finditer(r'\b(?:against|versus|vs\.?|face|facing|at|host|hosting)\s+(?:the\s+)?([^,;\n]+)',description,re.I):
        target=match[1]
        for team,aliases in CLUBS.items():
            if any(re.match(re.escape(alias)+r'\b',target,re.I) for alias in (aliases+'|'+team).split('|')) and team not in {game['home'],game['away']}:
                return False
    return True


def timestamp(value):
    # This publisher uses a 12-hour RFC-style date; normalize AM/PM before parsing.
    def hour(match):
        h=int(match[1])%12+(12 if match[4].upper()=='PM' else 0)
        return f'{h:02}:{match[2]}:{match[3]}'
    value=re.sub(r'\b(\d{1,2}):(\d{2}):(\d{2})\s+(AM|PM)\b',hour,value,flags=re.I)
    at=parsedate_to_datetime(value)
    if at.tzinfo is None:
        raise ValueError('News date has no timezone')
    return at.astimezone(timezone.utc).isoformat(timespec='seconds').replace('+00:00','Z')


def parse(payload, games, rosters, now):
    from starters import parse_post,valid_report
    if len(payload)>1000000 or b'<!DOCTYPE' in payload.upper() or b'<!ENTITY' in payload.upper():
        raise ValueError('Unexpected news feed')
    root=ET.fromstring(payload);channel=root.find('channel')
    if root.tag!='rss' or channel is None or 'NHL' not in (channel.findtext('title') or ''):
        raise ValueError('Not an NHL RSS feed')
    reports=[]
    for item in channel.findall('item')[:500]:
        title=(item.findtext('title') or '').strip();description=(item.findtext('description') or '').strip()
        link=(item.findtext('link') or '').strip().replace('rotowire.com//','rotowire.com/')
        if not LINK.fullmatch(link) or ':' not in title:
            continue
        name=normalized(title.split(':',1)[0])
        candidates=[(t,p) for t,players in rosters.items() for p in players if p['position']=='goalies' and normalized(p['name'])==name]
        if len(candidates)!=1:
            continue
        team,player=candidates[0]
        try:
            reported=timestamp(item.findtext('pubDate') or '')
        except (TypeError,ValueError,OverflowError):
            continue
        text=title+'. '+description
        source={'name':'RotoWire','teams':[team]}
        rows=parse_post({'id':item.findtext('guid') or link.rsplit('-',1)[-1], 'text':text,'created_at':reported},'rotowire',source,games,{team:[player]})
        for row in rows:
            if row['status']=='confirmed' and re.search(r'\b(expected|likely|projected|probable|slated|scheduled|first goalie off|morning skate)\b',title,re.I):
                row['status']='likely'
            row.update(source_url=link,author='RotoWire',source_kind='news',provider='RotoWire RSS',
                       via_url='https://www.rotowire.com/rss/',report_id=item.findtext('guid'))
            game=next(g for g in games if g['id']==row['game_id']);row['game_start']=game['start']
            if opponents_match(description.split('\n\n',1)[0],game) and valid_report(row,game,rosters,now):
                reports.append(row)
    try:
        interval=max(300,min(3600,int(channel.findtext('ttl') or '10')*60))
    except ValueError:
        interval=600
    return reports,interval


def request(headers):
    req=urllib.request.Request(URL,headers={'User-Agent':'Sweater.win NHL RSS reader (+https://sweater.win)',**headers})
    try:
        with urllib.request.urlopen(req,timeout=15) as response:
            return response.status,response.read(1000001),dict(response.headers)
    except urllib.error.HTTPError as error:
        if error.code==304:
            return 304,b'',dict(error.headers)
        raise


def valid_injury_report(report, injuries, now):
    try:
        if not isinstance(report,dict) or not all(isinstance(report.get(key),str) for key in ['name','team','injury_at','source','source_url','reported_at']):
            return False
        matches=[(team,p) for team,players in injuries.items() for p in players if normalized(p['name'])==normalized(report['name'])]
        at=datetime.fromisoformat(report['reported_at'].replace('Z','+00:00'));checked=datetime.fromisoformat(now.replace('Z','+00:00'))
        return (len(matches)==1 and matches[0][0]==report['team'] and matches[0][1].get('reported_at')==report['injury_at']
                and report['source']=='RotoWire RSS' and bool(LINK.fullmatch(report['source_url']))
                and timedelta(0)<=checked-at+timedelta(minutes=5)<=timedelta(days=30)
                and at>=datetime.fromisoformat(report['injury_at'].replace('Z','+00:00'))-timedelta(hours=6))
    except (KeyError,TypeError,ValueError):
        return False


def parse_injuries(payload, injuries, now):
    if len(payload)>1000000 or b'<!DOCTYPE' in payload.upper() or b'<!ENTITY' in payload.upper():
        raise ValueError('Unexpected news feed')
    root=ET.fromstring(payload);channel=root.find('channel')
    if root.tag!='rss' or channel is None or 'NHL' not in (channel.findtext('title') or ''):
        raise ValueError('Not an NHL RSS feed')
    reports=[]
    for item in channel.findall('item')[:500]:
        title=(item.findtext('title') or '').strip();description=(item.findtext('description') or '').strip()
        name=title.split(':',1)[0];link=(item.findtext('link') or '').strip().replace('rotowire.com//','rotowire.com/')
        if ':' not in title or not LINK.fullmatch(link) or re.search(r'\b(activated|cleared|recovered|returns?|returning|will play|available)\b',title,re.I):
            continue
        if not re.search(r'\b(out|miss|missing|injury|injured|surgery|scratched|will not play|won.t play|day.to.day)\b',title+' '+description,re.I):
            continue
        matches=[(team,p) for team,players in injuries.items() for p in players if normalized(p['name'])==normalized(name)]
        if len(matches)!=1:
            continue
        team,player=matches[0]
        try:
            report={'name':player['name'],'team':team,'injury_at':player.get('reported_at'),'source':'RotoWire RSS','source_url':link,'reported_at':timestamp(item.findtext('pubDate') or '')}
            if valid_injury_report(report,injuries,now):
                reports.append(report)
        except (TypeError,ValueError,OverflowError):
            continue
    return reports


def enrich_injuries(injuries, meta, now):
    for report in meta.get('rss',{}).get('injury_reports',[]):
        if valid_injury_report(report,injuries,now):
            for player in injuries[report['team']]:
                if normalized(player['name'])==normalized(report['name']):
                    player['report']=report


def collect(games, rosters, old, now, fetch=request, injuries=None):
    from starters import valid_report
    at=datetime.fromisoformat(now.replace('Z','+00:00'));index={g['id']:g for g in games}
    prior=old.get('starter_feed',{}).get('rss',{});saved=[r for r in prior.get('reports',[]) if r.get('game_id') in index and valid_report(r,index[r['game_id']],rosters,now)]
    injuries=injuries or {};injury_reports=[r for r in prior.get('injury_reports',[]) if valid_injury_report(r,injuries,now)]
    state={**prior,'reports':saved,'injury_reports':injury_reports};meta={'source':'RotoWire RSS','source_url':'https://www.rotowire.com/rss/',
         'status':'idle' if not games else 'cached','checked_at':prior.get('checked_at'),'requests':0,'x_requests':0}
    next_check=prior.get('next_check_at')
    if not games or next_check and now<next_check:
        return saved,{**meta,'rss':state}
    headers={key:prior[field] for key,field in [('If-None-Match','etag'),('If-Modified-Since','last_modified')] if prior.get(field)}
    try:
        meta['requests']=1;status,payload,response_headers=fetch(headers)
        interval=prior.get('poll_seconds',600)
        if status==200:
            fresh,interval=parse(payload,games,rosters,now)
            fresh_injuries=parse_injuries(payload,injuries,now)
            injury_reports=list({(r['team'],normalized(r['name']),r['injury_at']):r for r in sorted(injury_reports+fresh_injuries,key=lambda r:r['reported_at'])}.values())[-256:]
            # The feed is short. Preserve earlier facts for upcoming games after items roll off.
            saved=list({(r['game_id'],r['team'],r.get('report_id'),r['reported_at']):r for r in saved+fresh}.values())[-200:]
            state.update(etag=response_headers.get('ETag') or response_headers.get('etag'),
                         last_modified=response_headers.get('Last-Modified') or response_headers.get('last-modified'))
        elif status!=304 or not prior.get('checked_at'):
            raise ValueError('News response has no usable snapshot')
        meta.update(status='checked',checked_at=now)
        state.update(checked_at=now,poll_seconds=interval,reports=saved,injury_reports=injury_reports,next_check_at=(at+timedelta(seconds=interval)).isoformat(timespec='seconds').replace('+00:00','Z'))
    except Exception:
        meta['status']='unavailable'
        state['next_check_at']=(at+timedelta(minutes=10)).isoformat(timespec='seconds').replace('+00:00','Z')
    return saved,{**meta,'rss':state}
