"""Official season series and completed head-to-head meetings, no preseason."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
import time
from player_data import CACHE, current_season, get_json

CLUBS='ANA BOS BUF CAR CBJ CGY CHI COL DAL DET EDM FLA LAK MIN MTL NJD NSH NYI NYR OTT PHI PIT SEA SJS STL TBL TOR UTA VAN VGK WPG WSH'.split()


def compact(raw,season):
    if raw.get('gameType') not in (2,3) or str(raw.get('id',''))[:4]!=str(season):
        return None
    state=raw.get('gameState');home=raw.get('homeTeam',{});away=raw.get('awayTeam',{})
    if not home.get('abbrev') or not away.get('abbrev') or not raw.get('startTimeUTC'):
        raise ValueError('Incomplete NHL meeting identity')
    result={'id':raw['id'],'season':season*10000+season+1,'type':raw['gameType'],
      'date':raw['gameDate'],'start':raw['startTimeUTC'],'home':home['abbrev'],'away':away['abbrev'],'state':state}
    if state in ('OFF','FINAL'):
        hg,ag=home.get('score'),away.get('score');end=raw.get('gameOutcome',{}).get('lastPeriodType')
        if not isinstance(hg,int) or not isinstance(ag,int) or hg==ag or end not in ('REG','OT','SO'):
            raise ValueError('Incomplete NHL meeting final')
        result.update(hg=hg,ag=ag,end=end)
    elif state in ('LIVE','CRIT') and all(isinstance(t.get('score'),int) and 0<=t['score']<=30 for t in (home,away)):
        result.update(hg=home['score'],ag=away['score'])
    return result


def season_games(season):
    path=CACHE/f'matchups-{season}.json'
    if path.exists() and (season<current_season() or time.time()-path.stat().st_mtime<600):
        return json.loads(path.read_text())
    clubs=[t for t in CLUBS if not (t=='UTA' and season<2024 or t=='SEA' and season<2021)]
    def load(team):
        return get_json(f'https://api-web.nhle.com/v1/club-schedule-season/{team}/{season*10000+season+1}').get('games',[])
    games={}
    with ThreadPoolExecutor(max_workers=4) as pool:
        for rows in pool.map(load,clubs):
            for raw in rows:
                row=compact(raw,season)
                if row:
                    previous=games.get(row['id'])
                    if previous and previous!=row:
                        # Live updates can arrive between club requests. A verified
                        # final takes precedence; differing finals fail closed.
                        final=lambda g:g['state'] in ('OFF','FINAL')
                        if final(previous) and final(row):
                            raise ValueError('NHL meeting results disagree')
                        if final(previous):
                            continue
                    games[row['id']]=row
    output=sorted(games.values(),key=lambda g:(g['start'],g['id']))
    if len(output)<800:
        raise ValueError('Incomplete season meeting schedule')
    path.parent.mkdir(parents=True,exist_ok=True);temp=path.with_suffix('.tmp')
    temp.write_text(json.dumps(output,separators=(',',':'))+'\n');temp.replace(path)
    return output


def collect(first=2018,last=None):
    return [game for season in range(first,(last or current_season())+1) for game in season_games(season)]


def for_game(game,games,now):
    pair={game['home'],game['away']}
    # Utah is its own NHL franchise. Do not relabel old Arizona meetings as Utah.
    meetings=[g for g in games if {g['home'],g['away']}==pair]
    season=sorted([g for g in meetings if g['season']==int(str(game['id'])[:4])*10000+int(str(game['id'])[:4])+1],key=lambda g:(g['start'],g['id']))
    end=datetime.fromisoformat(now.replace('Z','+00:00'))
    recent=sorted([g for g in meetings if g['state'] in ('OFF','FINAL') and datetime.fromisoformat(g['start'].replace('Z','+00:00'))<=end],key=lambda g:(g['start'],g['id']),reverse=True)[:10]
    wins={t:sum((g['home'] if g['hg']>g['ag'] else g['away'])==t for g in recent) for t in pair}
    return {'checked_at':now,'season':season,'recent':recent,'wins':wins,
      'types':'Regular season and playoffs','source_url':'https://www.nhl.com/schedule'}


if __name__=='__main__':
    games=collect()
    print('Verified season-series history:',len(games),'regular-season/playoff games',flush=True)
