#!/usr/bin/env python3
"""Build Deep Cut's frozen, auditable NHL answer bank from Sweater's verified data.

This is an explicit content release, not a daily refresh. Published banks and run
IDs stay immutable so scores, archives, and in-progress games never drift.
"""
import hashlib
import json
import math
from pathlib import Path
import random

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "static/community-games/data.json"
OUT = ROOT / "static/deep-cut/data.json"
TEAMS = {
    "ANA": "Anaheim Ducks", "BOS": "Boston Bruins", "BUF": "Buffalo Sabres",
    "CGY": "Calgary Flames", "CAR": "Carolina Hurricanes", "CHI": "Chicago Blackhawks",
    "COL": "Colorado Avalanche", "CBJ": "Columbus Blue Jackets", "DAL": "Dallas Stars",
    "DET": "Detroit Red Wings", "EDM": "Edmonton Oilers", "FLA": "Florida Panthers",
    "LAK": "Los Angeles Kings", "MIN": "Minnesota Wild", "MTL": "Montréal Canadiens",
    "NSH": "Nashville Predators", "NJD": "New Jersey Devils", "NYI": "New York Islanders",
    "NYR": "New York Rangers", "OTT": "Ottawa Senators", "PHI": "Philadelphia Flyers",
    "PIT": "Pittsburgh Penguins", "SJS": "San Jose Sharks", "SEA": "Seattle Kraken",
    "STL": "St. Louis Blues", "TBL": "Tampa Bay Lightning", "TOR": "Toronto Maple Leafs",
    "UTA": "Utah", "VAN": "Vancouver Canucks", "VGK": "Vegas Golden Knights",
    "WSH": "Washington Capitals", "WPG": "Winnipeg Jets (2011 onward)",
}
COUNTRIES = {"CAN": "Canada", "USA": "the United States", "SWE": "Sweden",
             "FIN": "Finland", "CZE": "Czechia", "RUS": "Russia", "SVK": "Slovakia",
             "LVA": "Latvia", "DEU": "Germany", "CHE": "Switzerland", "DNK": "Denmark",
             "AUT": "Austria"}
ALIASES = {
    "Alex Ovechkin": ["Alexander Ovechkin", "Ovi"], "Sidney Crosby": ["Sid the Kid"],
    "Wayne Gretzky": ["The Great One"], "Mario Lemieux": ["Super Mario"],
    "Maurice Richard": ["Rocket Richard"], "Henri Richard": ["Pocket Rocket"],
    "Gordie Howe": ["Mr Hockey"], "Ed Belfour": ["Eddie Belfour"],
    "Jean-Sebastien Giguere": ["JS Giguere", "J S Giguere"],
    "Jean-Gabriel Pageau": ["JG Pageau", "J G Pageau"],
    "J.T. Miller": ["JT Miller", "J T Miller"], "P.K. Subban": ["PK Subban", "P K Subban"],
    "Pierre-Edouard Bellemare": ["PE Bellemare", "P E Bellemare"],
    "James van Riemsdyk": ["JVR"],
    "William Nylander": ["Willy Nylander"], "Nicolas Aube-Kubel": ["Nicolas Aubé-Kubel"],
}
# Editorial familiarity anchors prevent iconic short-career players from being
# classified as obscure solely because of games played. Values are not surveys.
ICONS = {"Wayne Gretzky", "Mario Lemieux", "Gordie Howe", "Bobby Orr", "Sidney Crosby",
         "Alex Ovechkin", "Connor McDavid", "Jaromir Jagr", "Patrick Roy",
         "Martin Brodeur", "Dominik Hasek", "Maurice Richard", "Bobby Hull",
         "Guy Lafleur", "Steve Yzerman", "Joe Sakic", "Mark Messier", "Nicklas Lidstrom",
         "Henrik Lundqvist", "Carey Price", "Auston Matthews", "Nathan MacKinnon"}


def build():
    raw = SOURCE.read_bytes()
    source = json.loads(raw)
    players = source["players"]
    by_id = {p[0]: p for p in players}
    awards = source["awards"]
    prompts = []

    def add(key, family, text, eligible, context=None, clue=None):
        rows = sorted(eligible, key=lambda p: p[0])
        if len(rows) < 9:
            return

        def familiarity(p):
            fame = math.log1p(p[4]) + 1.4 * bool(p[5]) + .8 * len(awards.get(str(p[0]), []))
            fame += max(0, p[7] - 1980) / 100
            if p[1] in ICONS:
                fame += 5
            if context:
                fame = .65 * fame + .35 * math.log1p(context(p))
            return fame

        ordered = sorted(rows, key=lambda p: (-familiarity(p), p[0]))
        # A full-name role player is a more satisfying jackpot than an unknown
        # one-game appearance. Two reachable editorial gems per prompt.
        gems = [p for p in ordered[max(1, len(rows) // 2):]
                if p[4] >= 100 and p[7] >= 1980 and (not context or context(p) >= 5)]
        gems = sorted(gems, key=lambda p: (-p[4], p[0]))[:2] or ordered[-1:]
        gem_ids = {p[0] for p in gems}
        answers = []
        for i, p in enumerate(ordered):
            fraction = i / max(1, len(rows) - 1)
            points = 10 if fraction < .15 else 15 if fraction < .35 else 30 if fraction < .60 else 60 if fraction < .85 else 85
            answers.append([p[0], 100 if p[0] in gem_ids else points])
        prompts.append({"id": key, "family": family, "text": text,
                        "note": clue or "NHL regular-season records through 2025–26. Retired players count.",
                        "answers": sorted(answers), "rule": key})

    for team, name in TEAMS.items():
        add(f"team-{team}", "Sweaters", f"Name a player who played for {name}.",
            [p for p in players if p[8].get(team, 0) > 0], lambda p, t=team: p[8].get(t, 0))
        add(f"goalie-{team}", "Between the pipes", f"Name a goalie who played for {name}.",
            [p for p in players if p[2] == "G" and p[8].get(team, 0) > 0], lambda p, t=team: p[8].get(t, 0))
    for code, country in COUNTRIES.items():
        add(f"country-{code}", "Around the world", f"Name an NHL player born in {country}.",
            [p for p in players if p[3] == code], clue="Birth country in NHL bios; nationality and national-team eligibility can differ.")
    for trophy in sorted({t for values in awards.values() for t in values}):
        add("award-" + trophy.split()[0].lower(), "Hardware", f"Name a {trophy} winner.",
            [p for p in players if trophy in awards.get(str(p[0]), [])],
            clue="At least one career win as a player, through the completed 2025–26 season.")
    for threshold in [30, 40, 50]:
        add(f"goals-{threshold}", "Milestones", f"Name a player with a {threshold}-goal NHL season.",
            [p for p in players if source["season_goals"].get(str(p[0]), 0) >= threshold],
            clue=f"At least {threshold} goals in one NHL regular season through 2025–26. Traded players’ totals are combined.")
    for threshold in [500, 1000, 1500]:
        add(f"games-{threshold}", "Milestones", f"Name a player with {threshold:,}+ career NHL games.",
            [p for p in players if p[4] >= threshold])
    add("cup-winner", "Hardware", "Name a Stanley Cup winner.",
        [p for p in players if p[0] in source["cup_winners"]],
        clue="An NHL-recorded Cup win as a player through 2025–26; being on a finalist’s roster does not count.")
    add("hall-of-fame", "Hardware", "Name an NHL player in the Hockey Hall of Fame.", [p for p in players if p[5]])
    for decade in range(1940, 2010, 10):
        add(f"debut-{decade}", "Time machine", f"Name a player who made his NHL debut in the {decade}s.",
            [p for p in players if decade <= p[6] < decade + 10],
            clue=f"First NHL regular-season appearance in a season starting from {decade} to {decade + 9}.")
    for a, b in [("VAN", "FLA"), ("TOR", "BOS"), ("MTL", "NYR"), ("PIT", "WSH"),
                 ("EDM", "LAK"), ("DET", "CHI"), ("NYI", "NJD"), ("DAL", "STL"),
                 ("BUF", "VAN"), ("PHI", "PIT"), ("SJS", "BOS"), ("COL", "NYR"),
                 ("TBL", "NYR"), ("CGY", "TOR"), ("ANA", "PIT"), ("MIN", "NSH"),
                 ("CAR", "FLA"), ("OTT", "TOR"), ("LAK", "VAN"), ("WPG", "BUF")]:
        add(f"both-{a}-{b}", "Connections", f"Name a player who played for both {TEAMS[a]} and {TEAMS[b]}.",
            [p for p in players if p[8].get(a, 0) and p[8].get(b, 0)],
            lambda p, a=a, b=b: min(p[8][a], p[8][b]))

    families = {}
    for prompt in prompts:
        families.setdefault(prompt["family"], []).append(prompt["id"])
    runs, used = [], set()
    for i in range(365):
        rng = random.Random(f"sweater-deepcut-v1-{i}")
        for _ in range(100):
            selected = [rng.choice(values) for values in families.values()]
            rng.shuffle(selected)
            if tuple(selected) not in used:
                break
        used.add(tuple(selected))
        runs.append({"id": f"dc-v1-{i:03}", "prompts": selected})
    included = {pid for p in prompts for pid, _ in p["answers"]}
    return {"version": 1, "asof": source["asof"], "through": "2025–26",
            "source_sha256": hashlib.sha256(raw).hexdigest(), "sources": source["sources"],
            "scoring": "Fixed editorial tiers estimated from career games, Hall of Fame status, awards, era and prompt-specific team appearances. Not player-pick percentages.",
            "players": [[pid, by_id[pid][1], by_id[pid][9], ALIASES.get(by_id[pid][1], [])] for pid in sorted(included)],
            "prompts": prompts, "runs": runs}


if __name__ == "__main__":
    data = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    if OUT.exists() and json.loads(OUT.read_text()) != data:
        raise SystemExit("Published bank differs. Release a new bank version instead of changing v1.")
    OUT.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n")
    print(f"Deep Cut: {len(data['players'])} players, {len(data['prompts'])} prompts, {len(data['runs'])} seven-round runs")
