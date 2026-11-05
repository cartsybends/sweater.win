"""Independent NHL record, edge-case and immutable rotation release checks."""
from collections import Counter, defaultdict
from datetime import date, timedelta
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


def module(name, file):
    spec = importlib.util.spec_from_file_location(name, ROOT / file)
    obj = importlib.util.module_from_spec(spec);spec.loader.exec_module(obj)
    return obj


b = module('sweater_expansion_test', 'build_sweater.py')
fetcher = module('nhl_fact_test', 'tools/deep_cut/fetch_prompt_facts.py')
DATA = b.load_deep_cut_data()
BANK = json.loads((ROOT / 'static/deep-cut/expansion.json').read_text())
FACTS = json.loads((ROOT / 'tools/deep_cut/prompt_facts.json').read_text())
BIO = {int(pid): row for pid, row in FACTS['bio'].items()}
PLAYED = defaultdict(list)
for row in FACTS['seasons']: PLAYED[row[0]].append(row)
PROMPTS = {p['id']: p for p in BANK['prompts']}
NAMES = {(p.get('skaterFullName') or p.get('goalieFullName')): pid for pid, p in BIO.items()}


class ExpansionTests(unittest.TestCase):
    def qualifies(self, prompt, *names):
        answers = dict(PROMPTS['x1-' + prompt]['answers'])
        for name in names: self.assertIn(NAMES[name], answers, (prompt, name))

    def excludes(self, prompt, *names):
        answers = dict(PROMPTS['x1-' + prompt]['answers'])
        for name in names: self.assertNotIn(NAMES[name], answers, (prompt, name))

    def test_season_records_cover_every_official_career_appearance(self):
        self.assertGreater(len(BIO), 8800)
        self.assertGreater(len(FACTS['seasons']), 53000)
        self.assertEqual(BANK['facts_sha256'], hashlib.sha256((ROOT / 'tools/deep_cut/prompt_facts.json').read_bytes()).hexdigest())
        self.assertEqual(len(FACTS['seasons']), len({(r[0], r[1]) for r in FACTS['seasons']}))
        for pid, bio in BIO.items(): self.assertEqual(sum(r[3] for r in PLAYED[pid]), bio['gamesPlayed'], pid)
        self.assertTrue(all(len(a['sha256']) == 64 and a['url'].startswith('https://api.nhle.com/') for a in FACTS['sources']))

    def test_team_eras_legacy_names_and_shared_seasons_are_complete(self):
        for prompt in BANK['prompts']:
            rule = prompt['criteria'];kind = rule['kind']
            if kind in ('legacy-team','team-era'):
                expected = {r[0] for r in FACTS['seasons'] if rule['team'] in r[2] and (kind == 'legacy-team' or rule['decade'] <= r[1] // 10000 <= rule['decade'] + 9)}
            elif kind == 'shared-season':
                anchor = rule['player']
                clubs = {(t,r[1]) for r in PLAYED[anchor] for t in r[2]}
                expected = {r[0] for r in FACTS['seasons'] if any((t,r[1]) in clubs for t in r[2])} - {anchor}
            else: continue
            self.assertEqual({pid for pid,_ in prompt['answers']}, expected, prompt['id'])
        self.qualifies('era-CGY-2000','Michael Cammalleri')
        self.qualifies('era-CGY-2010','Michael Cammalleri')
        self.excludes('era-CGY-2000','Matt Coronato')
        self.qualifies('legacy-WIN','Teemu Selanne','Shane Doan')
        self.excludes('legacy-WIN','Patrik Laine')
        self.qualifies('shared-8471675','Mark Recchi','Evgeni Malkin')
        self.excludes('shared-8471675','Sidney Crosby','Jaromir Jagr')

    def test_all_draft_and_numeric_stat_memberships_use_full_records(self):
        for prompt in BANK['prompts']:
            r = prompt['criteria'];kind = r['kind']
            if kind == 'draft-round': expected = {pid for pid,p in BIO.items() if p.get('draftRound') == r['round']}
            elif kind == 'draft-top': expected = {pid for pid,p in BIO.items() if p.get('draftOverall') and p['draftOverall'] <= r['top']}
            elif kind == 'draft-late': expected = {pid for pid,p in BIO.items() if (p.get('draftOverall') or 0) >= r['pick']}
            elif kind == 'draft-year': expected = {pid for pid,p in BIO.items() if p.get('draftYear') == r['year']}
            elif kind == 'undrafted': expected = {pid for pid,p in BIO.items() if not p.get('draftYear') and min(s[1] for s in PLAYED[pid]) // 10000 >= 1979}
            elif kind in ('season-stat','career-stat'):
                col = FACTS['season_columns'].index(r['stat'])
                def eligible(pid):
                    bio = BIO[pid]
                    if r.get('goalie') and 'goalieFullName' not in bio: return False
                    if r.get('position') and bio.get('positionCode') != r['position']: return False
                    records = PLAYED[pid]
                    if kind == 'career-stat': return sum(s[col] for s in records) >= r['min']
                    return any(s[col] >= r['min'] and ('decade' not in r or r['decade'] <= s[1] // 10000 <= r['decade'] + 9) for s in records)
                expected = {pid for pid in BIO if eligible(pid)}
            else: continue
            self.assertEqual({pid for pid,_ in prompt['answers']}, expected, prompt['id'])
        self.qualifies('draft-round-2','Michael Cammalleri')
        self.qualifies('undrafted','Wayne Gretzky')
        self.excludes('draft-top-1','Wayne Gretzky')
        self.qualifies('career-goals-500','Jarome Iginla')
        self.excludes('season-points-100','Jarome Iginla')
        self.qualifies('season-points-100','Sidney Crosby')

    def test_measurements_hand_birthplace_and_names_have_clear_boundaries(self):
        self.qualifies('height-min-78','Zdeno Chara')
        self.qualifies('height-max-68','Nathan Gerbe')
        self.excludes('height-max-68','Zdeno Chara')
        self.qualifies('hand-D','Cale Makar')
        self.excludes('hand-D','Quinn Hughes')
        self.qualifies('hand-G','Jose Theodore')
        self.excludes('hand-G','Martin Brodeur')
        self.qualifies('birth-CAN-ON','Brett Hull')
        self.qualifies('birth-CAN-AB','Alexander Nylander')
        self.excludes('birth-CAN-SK','Robyn Regehr')
        self.qualifies('name-alliteration','Mark Messier')
        self.qualifies('name-hyphen-first','Pierre-Edouard Bellemare')
        self.qualifies('name-hyphen-last','Nicolas Aube-Kubel')
        self.qualifies('name-short-last','Patrick Roy')

    def test_franchise_relocations_are_not_counted_twice(self):
        self.qualifies('franchises-9','Mike Sillinger','Jaromir Jagr')
        self.excludes('franchises-5','Shane Doan','Joe Sakic','Teemu Selanne')

    def test_rotation_covers_all_questions_with_seven_different_families(self):
        self.assertEqual(len(BANK['prompts']),189)
        self.assertEqual(DATA['content_prompts'],308)
        self.assertEqual(DATA['content_families'],17)
        prompts = {p['id']:p for p in DATA['prompts']}
        runs = {r['id']:r for r in DATA['runs']}
        usage = Counter()
        for key in DATA['practice_runs']:
            ids = runs[key]['prompts']
            self.assertEqual(len({prompts[k]['family'] for k in ids}),7)
            usage.update(ids)
        self.assertEqual(set(usage),set(DATA['active_prompt_ids']))
        self.assertGreater(min(usage.values()),0)
        for p in BANK['prompts']:
            team = p.get('rosterTeam')
            if p['criteria']['kind'] == 'shared-season': team = DATA['roster_snapshot'].get(str(p['criteria']['player']))
            if not team: continue
            updated = prompts[DATA['current_prompts'][p['id']]]
            expected = {pid for pid,_ in p['answers'] if DATA['roster_snapshot'].get(str(pid)) == team}
            self.assertEqual(set(updated['currentRoster']),expected)
            for pid, points in updated['answers']:
                if pid in expected: self.assertEqual(points,15 if pid in updated['lowToiRoster'] else 10)

    def test_archive_answers_and_todays_daily_remain_available(self):
        base = json.loads((ROOT / 'static/deep-cut/data.json').read_text())
        b.deep_cut_scoring().validate(base,DATA)
        today = date(2026,11,4)
        saved = {today.isoformat():{'id':base['runs'][0]['id']},(today+timedelta(days=1)).isoformat():{'id':base['runs'][1]['id']}}
        days = b.plan_deep_cut_days(saved,DATA,today)
        self.assertEqual(days[today.isoformat()],saved[today.isoformat()])
        self.assertIn(days[(today+timedelta(days=1)).isoformat()]['id'],DATA['practice_runs'])

    def test_official_service_response_cap_and_missing_seasons_are_rejected(self):
        def capped(name,url): return {'data':[{}]*10000,'total':10000}, {'url':url}
        with self.assertRaisesRegex(ValueError,'Incomplete'): fetcher.collect(capped,date(2026,11,4))
        def missing(name,url):
            rows = []
            if name == 'skater-bios-None.json': rows = [{'playerId':1234567,'gamesPlayed':2}]
            if name == 'skater-summary-2020.json': rows = [{'playerId':1234567,'seasonId':20202021,'gamesPlayed':1,'teamAbbrevs':'BOS'}]
            return {'data':rows,'total':len(rows)}, {'url':url}
        with self.assertRaisesRegex(ValueError,'complete official career GP'): fetcher.collect(missing,date(2026,11,4))


if __name__ == '__main__': unittest.main()
