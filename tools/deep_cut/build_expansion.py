"""Build an immutable NHL prompt release from complete, audited NHL facts.

Run explicitly when releasing content, never during the daily roster refresh.
Membership comes from NHL records; scores are editorial estimates, not surveys.
"""
from collections import defaultdict
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import unicodedata

ROOT = Path(__file__).resolve().parents[2]
FACTS = ROOT / 'tools/deep_cut/prompt_facts.json'
OUT = ROOT / 'static/deep-cut/expansion.json'


def normalized(text):
    return ''.join(char for char in unicodedata.normalize('NFD', text).lower() if char.isalpha())


class Evidence:
    def __init__(self, facts):
        self.facts = facts
        self.bio = {int(pid): row for pid, row in facts['bio'].items()}
        self.seasons = defaultdict(list)
        self.club_seasons = defaultdict(set)
        for row in facts['seasons']:
            self.seasons[row[0]].append(row)
            for club in row[2]: self.club_seasons[club, row[1]].add(row[0])
        self.franchises = {t['triCode']: t['franchiseId'] for t in facts['teams'] if t['franchiseId'] is not None}
        # WIN is the 1979 Jets, who moved to Phoenix. WPG is the relocated
        # Thrashers (2011 onward). The stats team table mislabels WIN as 35.
        self.franchises['WIN'] = 28
        self.totals = {pid: [sum(row[i] for row in rows) for i in range(3, 10)] for pid, rows in self.seasons.items()}
        self.shared = {}

    def name(self, pid):
        b = self.bio[pid]
        return b.get('skaterFullName') or b['goalieFullName']

    def position(self, pid):
        return 'G' if 'goalieFullName' in self.bio[pid] else self.bio[pid]['positionCode']

    def matches(self, pid, rule):
        b, rows, kind = self.bio[pid], self.seasons[pid], rule['kind']
        if kind == 'team-era': return any(rule['decade'] <= row[1] // 10000 < rule['decade'] + 10 and rule['team'] in row[2] for row in rows)
        if kind == 'legacy-team': return any(rule['team'] in row[2] for row in rows)
        if kind == 'shared-season':
            anchor = rule['player']
            if anchor not in self.shared:
                self.shared[anchor] = set().union(*(self.club_seasons[t, r[1]] for r in self.seasons[anchor] for t in r[2])) - {anchor}
            return pid in self.shared[anchor]
        if kind == 'draft-round': return b.get('draftRound') == rule['round']
        if kind == 'draft-top': return 0 < (b.get('draftOverall') or 0) <= rule['top']
        if kind == 'draft-late': return (b.get('draftOverall') or 0) >= rule['pick']
        if kind == 'draft-year': return b.get('draftYear') == rule['year']
        if kind == 'undrafted': return not b.get('draftYear') and min(r[1] for r in rows) >= 19791980
        if kind in ('season-stat', 'career-stat'):
            col = self.facts['season_columns'].index(rule['stat'])
            if rule.get('position') and self.position(pid) != rule['position']: return False
            if rule.get('goalie') and self.position(pid) != 'G': return False
            if kind == 'career-stat': return self.totals[pid][col - 3] >= rule['min']
            return any(r[col] >= rule['min'] and ('decade' not in rule or rule['decade'] <= r[1] // 10000 < rule['decade'] + 10) for r in rows)
        if kind == 'franchises': return len({self.franchises[t] for row in rows for t in row[2]}) >= rule['min']
        if kind == 'height': return bool(b.get('height')) and (b['height'] <= rule['max'] if 'max' in rule else b['height'] >= rule['min'])
        if kind == 'hand': return b.get('shootsCatches') == rule['hand'] and (self.position(pid) == rule['position'] if 'position' in rule else self.position(pid) != 'G')
        if kind == 'province': return b.get('birthCountryCode') == rule['country'] and b.get('birthStateProvinceCode') == rule['province']
        if kind == 'birth-country': return b.get('birthCountryCode') == rule['country']
        if kind == 'played-decade': return any(rule['decade'] <= r[1] // 10000 < rule['decade'] + 10 for r in rows)
        if kind == 'name':
            name, last = self.name(pid), b['lastName']
            first = name[:-len(last)].strip() if name.endswith(last) else name.split()[0]
            if rule['type'] == 'alliteration': return bool(first) and normalized(first)[:1] == normalized(last)[:1]
            if rule['type'] == 'hyphen-first': return '-' in first
            if rule['type'] == 'hyphen-last': return '-' in last
            if rule['type'] == 'mc-mac': return normalized(last).startswith(('mc', 'mac'))
            if rule['type'] == 'short-last': return len(normalized(last)) <= 4
            if rule['type'] == 'long-first': return len(normalized(first)) >= 10
        raise ValueError(f'Unknown expansion rule: {rule}')


def build(facts=None):
    raw = FACTS.read_bytes()
    facts = facts or json.loads(raw)
    e = Evidence(facts)
    spec = importlib.util.spec_from_file_location('original_deep_cut', Path(__file__).with_name('build_data.py'))
    original = importlib.util.module_from_spec(spec);spec.loader.exec_module(original)
    source = json.loads((ROOT / 'static/community-games/data.json').read_text())
    review = json.loads((ROOT / 'static/deep-cut/familiarity.json').read_text())
    caps = {r['id']: r['points'] for r in review['global_caps']}
    connections = {(r['team'], r['id']): r['points'] for r in review['team_connections']}
    prior = {p[0]: p for p in json.loads((ROOT / 'static/deep-cut/data.json').read_text())['players']}
    prompts = []
    cutoff = f"NHL regular-season records verified {facts['asof']}. Retired players count."

    def add(key, family, text, rule, note='', roster_team=None):
        eligible = [pid for pid in e.bio if e.matches(pid, rule)]
        if len(eligible) < 9: return
        def familiarity(pid):
            b = e.bio[pid]
            fame = math.log1p(b['gamesPlayed']) + 1.4 * (b.get('isInHallOfFameYn') == 'Y') + .8 * len(source['awards'].get(str(pid), []))
            fame += max(0, max(r[1] // 10000 for r in e.seasons[pid]) - 1980) / 100
            if e.name(pid) in original.ICONS: fame += 5
            return fame
        ordered = sorted(eligible, key=lambda pid: (-familiarity(pid), pid))
        candidates = [pid for pid in ordered[max(1, len(ordered) // 2):] if e.bio[pid]['gamesPlayed'] >= 100 and max(r[1] for r in e.seasons[pid]) >= 19801981 and pid not in caps and (roster_team, pid) not in connections]
        gems = set(sorted(candidates, key=lambda pid: (-e.bio[pid]['gamesPlayed'], pid))[:2] or ordered[-1:])
        answers = []
        for i, pid in enumerate(ordered):
            fraction = i / max(1, len(ordered) - 1)
            points = 10 if fraction < .15 else 15 if fraction < .35 else 30 if fraction < .60 else 60 if fraction < .85 else 85
            points = min(100 if pid in gems else points, caps.get(pid, 100))
            if roster_team and (roster_team, pid) in connections: points = connections[roster_team, pid]
            answers.append([pid, points])
        if not any(score == 100 for _, score in answers): raise ValueError(f'No editorial gem for {key}')
        prompt = {'id': 'x1-' + key, 'family': family, 'text': text, 'note': (note + ' ' + cutoff).strip(),
                  'answers': sorted(answers), 'rule': 'expansion', 'criteria': rule, 'contentVersion': 1}
        if roster_team: prompt['rosterTeam'] = roster_team
        prompts.append(prompt)

    for team, name in original.TEAMS.items():
        for decade in (2000, 2010):
            add(f'era-{team}-{decade}', 'Team time machine', f'Name a {name} player from the {decade}s.',
                {'kind': 'team-era', 'team': team, 'decade': decade},
                f'At least one appearance for this club in a season starting {decade}–{decade + 9}. Predecessors are separate.', roster_team=team)
    for team, name in [('QUE','Quebec Nordiques'),('HFD','Hartford Whalers'),('ATL','Atlanta Thrashers'),('AFM','Atlanta Flames'),('MNS','Minnesota North Stars'),('WIN','original Winnipeg Jets (1979–96)'),('PHX','Phoenix Coyotes'),('ARI','Arizona Coyotes'),('CGS','California Golden Seals'),('CLR','Colorado Rockies')]:
        add('legacy-' + team, 'Lost sweaters', f'Name a player who played for the {name}.', {'kind':'legacy-team','team':team}, 'Only appearances under that team name count; relocated successors are separate.')
    for pid in [8447400, 8448208, 8471675, 8471214, 8478402, 8474141, 8466138, 8465009, 8451101, 8458520, 8467876, 8471679]:
        name = e.name(pid)
        add(f'shared-{pid}', 'Shared sweaters', f'Name a player who played for the same NHL team in the same season as {name}.',
            {'kind':'shared-season','player':pid}, f'Must have regular-season appearances for the same club in the same season as {name}; the named player is excluded. This does not require playing the same game.')
    for round_no in range(1, 10):
        add(f'draft-round-{round_no}', 'Draft day', f'Name an NHL player drafted in round {round_no}.', {'kind':'draft-round','round':round_no}, 'NHL draft round listed in the official player bio; must have played in the NHL.')
    for top in [1,3,5]:
        add(f'draft-top-{top}', 'Draft day', 'Name a first-overall NHL draft pick.' if top == 1 else f'Name an NHL player drafted in the top {top}.', {'kind':'draft-top','top':top})
    add('draft-late-100', 'Draft day', 'Name an NHL player drafted 100th overall or later.', {'kind':'draft-late','pick':100})
    add('undrafted', 'Draft day', 'Name an undrafted NHL player who debuted in 1979 or later.', {'kind':'undrafted'}, 'No NHL draft selection in the official bio; first NHL season started in 1979 or later. WHA arrivals count.')
    for year in [1990,1993,1998,2003,2005,2008,2010,2015]:
        add(f'draft-class-{year}', 'Draft day', f'Name an NHL player from the {year} draft class.', {'kind':'draft-year','year':year})
    for stat, thresholds, noun in [('goals',[20,60],'goals'),('assists',[40,60,80],'assists'),('points',[60,80,100,120],'points'),('pim',[150,200,300],'penalty minutes'),('wins',[30,40],'wins'),('shutouts',[10],'shutouts')]:
        for threshold in thresholds:
            goalie = stat in ('wins','shutouts')
            add(f'season-{stat}-{threshold}', 'Season stat lines', f'Name a {"goalie" if goalie else "player"} with {threshold}+ {noun} in one NHL season.',
                {'kind':'season-stat','stat':stat,'min':threshold, **({'goalie':True} if goalie else {})}, 'One regular season; totals across traded clubs are combined.')
    for stat, threshold, noun in [('goals',20,'goals'),('points',50,'points')]:
        add(f'defence-{stat}-{threshold}', 'Season stat lines', f'Name a defenceman with {threshold}+ {noun} in one NHL season.', {'kind':'season-stat','stat':stat,'min':threshold,'position':'D'}, 'Position listed in NHL bios. One regular season; traded totals are combined.')
    for decade in [1980,1990,2000,2010]:
        for stat, threshold, noun in [('goals',40,'goals'),('points',100,'points')]:
            add(f'era-stat-{stat}-{decade}', 'Season stat lines', f'Name a player with a {threshold}-{noun[:-1]} NHL season in the {decade}s.', {'kind':'season-stat','stat':stat,'min':threshold,'decade':decade}, f'At least {threshold} {noun} in a regular season starting {decade}–{decade + 9}. Traded totals are combined.')
    for stat, thresholds, noun in [('goals',[200,400,500,600],'goals'),('assists',[500,750],'assists'),('points',[500,1000,1500],'points'),('pim',[1000,2000],'penalty minutes'),('wins',[100,300],'wins'),('shutouts',[25,50],'shutouts')]:
        for threshold in thresholds:
            goalie = stat in ('wins','shutouts')
            add(f'career-{stat}-{threshold}', 'Career totals', f'Name a {"goalie" if goalie else "player"} with {threshold:,}+ career NHL {noun}.', {'kind':'career-stat','stat':stat,'min':threshold, **({'goalie':True} if goalie else {})}, 'NHL regular-season career totals only; playoffs and other leagues are excluded.')
    for count in [5,7,9]:
        add(f'franchises-{count}', 'Journeymen', f'Name a player who appeared for {count}+ NHL franchises.', {'kind':'franchises','min':count}, 'Relocations and name changes count as one franchise: original Jets/Coyotes, Nordiques/Avalanche and Thrashers/current Jets. Utah is separate from Arizona.')
    for bound, inches, label in [('max',68,'5 ft 8 or shorter'),('max',70,'5 ft 10 or shorter'),('min',76,'6 ft 4 or taller'),('min',78,'6 ft 6 or taller')]:
        add(f'height-{bound}-{inches}', 'Tale of the tape', f'Name an NHL player listed at {label}.', {'kind':'height',bound:inches}, 'Listed height in NHL player bios; this may differ from other published measurements.')
    for position, hand, text in [('D','R','a right-shooting NHL defenceman'),('G','R','an NHL goalie who catches with his right hand'),(None,'R','a right-shooting NHL skater')]:
        add('hand-' + (position or 'skater'), 'Tale of the tape', f'Name {text}.', {'kind':'hand','hand':hand, **({'position':position} if position else {})}, 'Position and shoots/catches field in NHL player bios.')
    for kind, text in [('alliteration','an NHL player whose first and last names start with the same letter'),('hyphen-first','an NHL player with a hyphen in his first name'),('hyphen-last','an NHL player with a hyphen in his last name'),('mc-mac','an NHL player whose last name starts with Mc or Mac'),('short-last','an NHL player with a last name of four letters or fewer'),('long-first','an NHL player with a first name of at least ten letters')]:
        add('name-' + kind, 'Name game', f'Name {text}.', {'kind':'name','type':kind}, 'The published NHL bio name decides eligibility. Accents, spaces and punctuation do not count as letters.')
    for country, provinces in [('CAN', [('ON','Ontario'),('QC','Quebec'),('AB','Alberta'),('BC','British Columbia'),('SK','Saskatchewan'),('MB','Manitoba'),('NS','Nova Scotia'),('NB','New Brunswick'),('NL','Newfoundland and Labrador'),('PE','Prince Edward Island')]),('USA',[('MN','Minnesota'),('MA','Massachusetts'),('MI','Michigan'),('NY','New York'),('CA','California'),('WI','Wisconsin')])]:
        for province, name in provinces:
            add('birth-' + country + '-' + province, 'Hometowns', f'Name an NHL player born in {name}.', {'kind':'province','country':country,'province':province}, 'Birthplace recorded in NHL bios; nationality and where a player grew up may differ.')
    for country, name in [('NOR','Norway'),('BLR','Belarus'),('KAZ','Kazakhstan'),('UKR','Ukraine'),('GBR','the United Kingdom'),('FRA','France'),('ITA','Italy'),('POL','Poland')]:
        add('birth-country-' + country, 'Hometowns', f'Name an NHL player born in {name}.', {'kind':'birth-country','country':country}, 'Birth country recorded in NHL bios; nationality and national-team eligibility can differ.')
    for decade in range(1950,2030,10):
        add(f'played-{decade}', 'Time machine', f'Name someone who played in the NHL in the {decade}s.', {'kind':'played-decade','decade':decade}, f'At least one regular-season appearance in a season starting {decade}–{decade + 9}; debut need not be in that decade.')
    used = {pid for p in prompts for pid, _ in p['answers']}
    return {'version':1, 'asof':facts['asof'], 'facts_sha256':hashlib.sha256(raw).hexdigest(), 'sources':facts['sources'],
            'scoring':'Editorial familiarity estimates from career GP, awards, Hall of Fame status, era and reviewed name recognition. No live answer frequencies.',
            'players':[prior.get(pid, [pid,e.name(pid),int(e.bio[pid]['birthDate'][:4]),original.ALIASES.get(e.name(pid),[])]) for pid in sorted(used)],
            'prompts':prompts}


if __name__ == '__main__':
    data = build()
    if OUT.exists() and json.loads(OUT.read_text()) != data:
        raise SystemExit('Published expansion differs. Release a new content version instead.')
    OUT.write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':')) + '\n')
    print('New verified prompts:',len(data['prompts']), '; players:',len(data['players']))
    from collections import Counter
    print(dict(Counter(p['family'] for p in data['prompts'])))
