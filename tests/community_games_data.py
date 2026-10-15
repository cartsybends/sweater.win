"""Independent checks against the NHL source snapshots and exhaustive markets."""
import hashlib
import importlib.util
from datetime import date,timedelta
import json
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]

def role(pos):
    return pos if pos in ('D','G') else 'F'

def qualifies(p, clue, awards):
    kind,value=clue['kind'],clue['value']
    return {'team':lambda:p[8].get(value,0)>0,'country':lambda:p[3]==value,
            'position':lambda:role(p[2])==value,'games':lambda:p[4]>=value,'hall':lambda:p[5],
            'trophy':lambda:value in awards.get(str(p[0]),[])}[kind]()


class CommunityData(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data=json.loads((ROOT/'static/community-games/data.json').read_text())
        cls.players={p[0]:p for p in cls.data['players']}
        cls.history=json.loads((ROOT/'team_history_cache.json').read_text())['teams']
        cls.appearances={}
        source=ROOT/'tools/community_games/season_totals.json'
        cls.league=json.loads(source.read_text())
        cls.league_hash=hashlib.sha256(source.read_bytes()).hexdigest()
        cls.stats={(int(year),r[0]):r for year,rows in cls.league['seasons'].items() for r in rows}
        for team,raw in cls.history.items():
            for kind in ('s','g'):
                for r in raw[kind]:
                    year,gp=(r[3],r[4]) if kind=='s' else (r[2],r[3])
                    key=(team,year,r[0])
                    cls.appearances[key]=max(gp,cls.appearances.get(key,0))

    def test_player_catalog_and_clues(self):
        self.assertEqual(len(self.players),len(self.data['players']))
        for p in self.players.values():
            self.assertTrue(p[1]);self.assertRegex(p[3],r'^[A-Z]{3}$')
            self.assertIsInstance(p[4],int);self.assertGreaterEqual(p[4],sum(p[8].values()))
            self.assertTrue(1860<=p[9]<=2020)
            self.assertTrue(all(gp>0 for gp in p[8].values()))

    def test_all_grid_squares_have_nine_real_candidates(self):
        self.assertGreaterEqual(len(self.data['grid']),168)
        for puzzle in self.data['grid']:
            self.assertEqual(len(set(puzzle['rows'])),3)
            for team in puzzle['rows']:
                for clue in puzzle['cols']:
                    candidates=[p for p in self.players.values() if p[8].get(team,0)>0 and qualifies(p,clue,self.data.get('awards',{}))]
                    self.assertGreaterEqual(len(candidates),9,(puzzle['id'],team,clue))

    def test_each_teammate_link_has_guaranteed_shared_games(self):
        seen=set()
        for a,b,team,year,ga,gb in self.data['links']:
            self.assertLess(a,b);self.assertNotIn((a,b),seen);seen.add((a,b))
            self.assertEqual(self.appearances[(team,year,a)],ga)
            self.assertEqual(self.appearances[(team,year,b)],gb)
            self.assertGreaterEqual(ga+gb-84,5)
            self.assertTrue(0<ga<=84 and 0<gb<=84)

    def test_trophy_membership_matches_verified_winner_snapshot(self):
        path=ROOT/'tools/community_games/award_winners.json'
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),self.data['awards_sha256'])
        source=json.loads(path.read_text());expected={}
        self.assertGreaterEqual(source['cross_checked_existing_seasons'],432)
        for title,year,pid,name in source['rows']:
            self.assertIn(pid,self.players);self.assertTrue(1923<=year<=2025)
            self.assertTrue(16<=year+1-self.players[pid][9]<=55,(year,name))
            expected.setdefault(str(pid),set()).add(title)
        self.assertEqual({pid:sorted(titles) for pid,titles in expected.items()},self.data['awards'])
        self.assertEqual(sum(any(c['kind']=='trophy' for c in p['cols']) for p in self.data['grid']),48)
        old_goalie=next(p for p in self.players.values() if p[1]=='Michel Larocque' and p[9]==1952)
        newer_goalie=next(p for p in self.players.values() if p[1]=='Michel Larocque' and p[9]==1976)
        self.assertIn('Vezina Trophy',self.data['awards'][str(old_goalie[0])])
        self.assertNotIn('Vezina Trophy',self.data['awards'].get(str(newer_goalie[0]),[]))
        self.assertIn('Vezina Trophy',self.data['awards']['8450138'],'Joint winners such as Gilles Villemure must qualify')

    def test_original_puzzles_are_unchanged(self):
        original=json.loads((ROOT/'tools/community_games/original_bank_hashes.json').read_text())
        for mode in ('players','benchboss','teammatetrail','grid'):
            row=original[mode];raw=json.dumps(self.data[mode][:row['count']],ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
            self.assertEqual(hashlib.sha256(raw).hexdigest(),row['sha256'])

    def test_all_trails_have_unique_pairs_and_valid_proof_paths(self):
        links={tuple(row[:2]) for row in self.data['links']};seen=set()
        for puzzle in self.data['teammatetrail']:
            self.assertEqual(len(puzzle['rounds']),3)
            for q in puzzle['rounds']:
                pair=tuple(sorted((q['start'],q['end'])))
                self.assertNotIn(pair,seen);seen.add(pair)
                self.assertEqual(q['solution'][0],q['start']);self.assertEqual(q['solution'][-1],q['end'])
                self.assertEqual(len(set(q['solution'])),len(q['solution']))
                for a,b in zip(q['solution'],q['solution'][1:]):self.assertIn(tuple(sorted((a,b))),links)

    def test_boss_card_totals_match_completed_nhl_seasons(self):
        self.assertEqual(self.league_hash,self.data['league_sha256'])
        self.assertEqual(len(self.league['response_sha256']),40)
        for puzzle in self.data['benchboss']:
            self.assertTrue(2005<=puzzle['year']<=2024)
            counts={'F':0,'D':0,'G':0}
            for c in puzzle['cards']:
                official=self.stats[(puzzle['year'],c[0])]
                self.assertEqual(list(c[3:6]),official[3:6])
                self.assertEqual(c[7],official[2]);self.assertEqual(c[8],official[1])
                position=role(c[8]);counts[position]+=1
                self.assertEqual(c[2],c[5]*3 if position=='G' else c[3]*2+c[4])
            self.assertEqual(counts,{'F':9,'D':6,'G':3})

    def test_every_market_optimum_is_exact_and_feasible(self):
        for puzzle in self.data['benchboss']:
            # Independent knapsack DP, rather than the generator's combination
            # search, verifies the exact maximum under all slot/budget limits.
            states={(0,0,0,0):0}
            for c in puzzle['cards']:
                slot={'F':0,'D':1,'G':2}[role(c[8])]
                for key,points in list(states.items()):
                    updated=list(key);updated[slot]+=1;updated[3]+=c[1]
                    if updated[0]>3 or updated[1]>2 or updated[2]>1 or updated[3]>puzzle['budget']:continue
                    key2=tuple(updated);states[key2]=max(states.get(key2,-1),points+c[2])
            score=max(value for key,value in states.items() if key[:3]==(3,2,1))
            self.assertEqual(score,puzzle['par'])
            chosen=[c for c in puzzle['cards'] if c[0] in puzzle['optimal']]
            self.assertEqual(len(chosen),6);self.assertLessEqual(sum(c[1] for c in chosen),100)
            self.assertEqual(sum(c[2] for c in chosen),score)

    def test_daily_schedule_preserves_published_puzzles_and_archives(self):
        spec=importlib.util.spec_from_file_location('sweater_schedule',ROOT/'build_sweater.py')
        app=importlib.util.module_from_spec(spec);spec.loader.exec_module(app)
        today=date(2026,10,14)
        for mode in ('grid','benchboss','teammatetrail'):
            bank=self.data[mode]
            published={(today-timedelta(days=1)).isoformat():{'id':bank[0]['id']},today.isoformat():{'id':bank[1]['id']}}
            planned=app.plan_community_days(published,bank,today,mode)
            self.assertTrue(all(planned[k]==v for k,v in published.items()))
            self.assertEqual(len(planned),app.AHEAD+2)
            self.assertEqual(len({p['id'] for p in planned.values()}),len(planned))
            self.assertEqual(planned,app.plan_community_days(planned,bank,today,mode))
            with self.assertRaises(ValueError):app.plan_community_days(published,bank[1:],today,mode)

    def test_rarity_snapshots_validate_sample_size_and_freeze_counts(self):
        spec=importlib.util.spec_from_file_location('sweater_rarity',ROOT/'build_sweater.py')
        app=importlib.util.module_from_spec(spec);spec.loader.exec_module(app)
        t=self.data['grid'][0];key='teams:'+':'.join(sorted((t['rows'][0],t['cols'][0]['value'])))
        counts={'8478403':99,'8475791':1};pop={'criteria':{key:{'total':100,'counts':counts}}}
        snapshot=app.grid_rarity_snapshot(t,pop)
        self.assertEqual(snapshot[0],{'total':100,'counts':counts})
        counts['8478403']=1;self.assertEqual(snapshot[0]['counts']['8478403'],99)
        self.assertIsNone(app.grid_rarity_snapshot(t,pop)[0])
        self.assertTrue(all(row is None for row in app.grid_rarity_snapshot(t,{'criteria':{key:{'total':99,'counts':{'8478403':99}}}})))


if __name__=='__main__':unittest.main()
