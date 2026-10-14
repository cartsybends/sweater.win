#!/usr/bin/env python3
"""Build verified NHL career paths for Team Journey from official player records.

Single-club seasons come from NHL season totals. Every multi-club season is
ordered using dated game logs and must reconcile exactly with those totals.
Active careers refresh weekly; completed careers remain stable.
"""
import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
import json
from pathlib import Path
import sys
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from build_sweater import abbrev_for, TEAMS

KNOWN = set(TEAMS) | {"ARI", "ATL", "MNS", "HFD", "QUE", "AFM", "CLR", "KCS", "CGS", "OAK", "CLE", "WIN"}


def canonical_team(code, year):
    # Phoenix/Arizona is a rename of the same club; Utah is a separate stop.
    if code == "PHX":
        return "ARI"
    if code == "WPG" and year < 1996:
        return "WIN"
    return code


def season_rows(landing):
    rows = []
    for row in landing.get("seasonTotals", []):
        if row.get("leagueAbbrev") != "NHL" or row.get("gameTypeId") != 2 or not row.get("gamesPlayed"):
            continue
        year = int(str(row["season"])[:4])
        code = row.get("teamAbbrev")
        if isinstance(code, dict):
            code = code.get("default")
        name = row.get("teamName", {})
        name = name.get("default", "") if isinstance(name, dict) else str(name)
        code = canonical_team(code or abbrev_for(name), year)
        if code not in KNOWN:
            raise ValueError(f"Unrecognized NHL team: {name}")
        rows.append((year, code, int(row["gamesPlayed"])))
    if not rows:
        raise ValueError("No NHL regular-season appearances")
    return sorted(rows, key=lambda r: r[0])


def verified_stints(rows, get_log):
    by_year = defaultdict(Counter)
    for year, team, gp in rows:
        by_year[year][team] += gp
    stints = []

    def append(team, year, gp):
        if stints and stints[-1]["team"] == team:
            stints[-1]["to"] = year
            stints[-1]["gp"] += gp
        else:
            stints.append({"team": team, "from": year, "to": year, "gp": gp})

    for year, totals in sorted(by_year.items()):
        if len(totals) == 1:
            team, gp = next(iter(totals.items()))
            append(team, year, gp)
            continue
        games = get_log(year)
        if len({g["gameId"] for g in games}) != len(games):
            raise ValueError(f"Duplicate games in {year}")
        counts = Counter(canonical_team(g["teamAbbrev"], year) for g in games)
        if counts != totals:
            raise ValueError(f"Incomplete {year} game log: {dict(counts)} != {dict(totals)}")
        for game in sorted(games, key=lambda g: (date.fromisoformat(g["gameDate"]), g["gameId"])):
            append(canonical_team(game["teamAbbrev"], year), year, 1)
    return stints


def get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Sweater NHL trivia)"})
    with urllib.request.urlopen(req, timeout=20) as response:
        return json.load(response)


def fetch_career(pid):
    url = f"https://api-web.nhle.com/v1/player/{pid}/landing"
    landing = get_json(url)
    if landing.get("playerId") != pid:
        raise ValueError("Player record does not match requested ID")
    rows = season_rows(landing)
    career_gp = (landing.get("careerTotals") or {}).get("regularSeason", {}).get("gamesPlayed")
    if type(career_gp) is not int or sum(r[2] for r in rows) != career_gp:
        raise ValueError("Season totals do not cover the complete NHL career")
    log_seasons = []

    def log(year):
        season = int(f"{year}{year + 1}")
        data = get_json(f"https://api-web.nhle.com/v1/player/{pid}/game-log/{season}/2")
        if data.get("seasonId") != season or data.get("gameTypeId") != 2:
            raise ValueError("Unexpected game log season or type")
        log_seasons.append(season)
        return data.get("gameLog", [])

    stints = verified_stints(rows, log)
    return {"id": pid, "name": f'{landing["firstName"]["default"]} {landing["lastName"]["default"]}',
            "pos": landing.get("position", "?"), "headshot": landing.get("headshot", ""),
            "active": bool(landing.get("isActive")), "verified": date.today().isoformat(),
            "source": url, "career_gp": career_gp, "log_seasons": log_seasons, "stints": stints}


def candidates(history, cache):
    players = {}
    for team, data in history.items():
        for row in data.get("s", []):
            p = players.setdefault(row[0], {"teams": Counter()})
            p["teams"][team] += row[4]
        for row in data.get("g", []):
            p = players.setdefault(row[0], {"teams": Counter()})
            p["teams"][team] += row[3]
    out = set()
    for team in TEAMS:
        pool = [(pid, p) for pid, p in players.items() if p["teams"].get(team, 0) >= 20 and
                (len(p["teams"]) >= 3 or len(cache.get(str(pid), {}).get("teams", [])) >= 3)]
        # A club's long-serving alumni make the default game recognizable.
        pool.sort(key=lambda item: (-item[1]["teams"][team], -sum(item[1]["teams"].values())))
        out.update(pid for pid, _ in pool[:24])
    # Include well-known alumni whose earlier clubs are now defunct.
    veterans = [(pid, p) for pid, p in players.items() if len(p["teams"]) >= 2 and sum(p["teams"].values()) >= 700]
    veterans.sort(key=lambda item: -sum(item[1]["teams"].values()))
    out.update(pid for pid, _ in veterans[:100])
    return sorted(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--out", type=Path, default=ROOT / "team_careers.json")
    args = ap.parse_args()
    saved = json.loads(args.out.read_text()) if args.out.exists() else {"version": 1, "players": []}
    old = {p["id"]: p for p in saved["players"]}
    history = json.loads((ROOT / "team_history_cache.json").read_text())["teams"]
    cache = json.loads((ROOT / "career_cache.json").read_text())
    ids = sorted(set(candidates(history, cache)) | set(old))
    today = date.today()
    todo = [pid for pid in ids if args.force or pid not in old or "career_gp" not in old[pid] or
            old[pid].get("active") and (today - date.fromisoformat(old[pid]["verified"])).days >= 7]
    print(f"Team Journey: {len(old)} saved careers, {len(todo)} to verify", flush=True)
    failed = 0
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {pool.submit(fetch_career, pid): pid for pid in todo}
        for i, future in enumerate(as_completed(futures), 1):
            pid = futures[future]
            try:
                old[pid] = future.result()
            except Exception as exc:
                failed += 1
                if pid in old and "career_gp" not in old[pid]:
                    del old[pid]
                print(f"  {pid}: retaining saved path / excluding unverified path ({exc})", flush=True)
            if i % 40 == 0 or i == len(todo):
                print(f"  {i}/{len(todo)} checked", flush=True)
    result = {"version": 1, "players": sorted(old.values(), key=lambda p: p["id"])}
    if result != saved:
        args.out.write_text(json.dumps(result, ensure_ascii=False, separators=(",", ":")) + "\n")
    counts = {t: sum(3 <= len(p["stints"]) <= 5 and any(s["team"] == t and s["gp"] >= 20 for s in p["stints"])
                     for p in result["players"]) for t in TEAMS}
    print(f"Verified careers: {len(old)}; refresh failures: {failed}; Classic pools: {counts}")
    if any(n < 5 for n in counts.values()):
        raise SystemExit("Every club needs at least five verified Classic careers")


if __name__ == "__main__":
    main()
