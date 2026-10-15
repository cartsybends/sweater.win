"""Append trophy boards without changing previously published puzzle IDs."""
import argparse,hashlib,json,random
from pathlib import Path
from build_data import qualifies

ROOT=Path(__file__).resolve().parents[2]

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--count',type=int,default=48)
    args=parser.parse_args()
    path=ROOT/'static/community-games/data.json'
    data=json.loads(path.read_text())
    source=ROOT/'tools/community_games/award_winners.json'
    awards=json.loads(source.read_text())
    membership={}
    for title,year,pid,name in awards['rows']:
        membership.setdefault(str(pid),set()).add(title)
    data['awards']={pid:sorted(names) for pid,names in membership.items()}
    data['awards_sha256']=hashlib.sha256(source.read_bytes()).hexdigest()
    players=data['players'];rng=random.Random(20261015)
    eligible={title:[team for team in sorted({t for p in players for t in p[8]}) if sum(team in p[8] and title in membership.get(str(p[0]),set()) for p in players)>=9] for title in sorted({r[0] for r in awards['rows']})}
    eligible={title:teams for title,teams in eligible.items() if len(teams)>=3}
    assert len(eligible)>=4,eligible
    existing=list(data['grid'])
    seen={json.dumps([t['rows'],t['cols']],sort_keys=True) for t in existing}
    added=0
    for _ in range(30000):
        title=rng.choice(sorted(eligible));rows=rng.sample(eligible[title],3)
        other=[{'kind':'team','value':t} for t in sorted({t for p in players for t in p[8]}) if t not in rows]+[{'kind':'country','value':c} for c in ['CAN','USA','SWE','FIN']]+[{'kind':'position','value':v} for v in ['F','D','G']]+[{'kind':'games','value':1000}]
        cols=[{'kind':'trophy','value':title},*rng.sample(other,2)];rng.shuffle(cols)
        key=json.dumps([rows,cols],sort_keys=True)
        if key in seen:continue
        def match(p,c):return c['value'] in membership.get(str(p[0]),set()) if c['kind']=='trophy' else qualifies(p,c)
        if any(sum(team in p[8] and match(p,c) for p in players)<9 for team in rows for c in cols):continue
        seen.add(key);data['grid'].append({'id':f'grid-{len(data["grid"]):03}','rows':rows,'cols':cols});added+=1
        if added==args.count:break
    assert added==args.count
    assert data['grid'][:len(existing)]==existing
    path.write_text(json.dumps(data,ensure_ascii=False,separators=(',',':'))+'\n')
    print('Appended',added,'trophy grids:',', '.join(eligible))

if __name__=='__main__':main()
