"""Observed two-way sportsbook moneylines; never substitute model-generated odds."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import math

ESPN = 'https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/scoreboard?dates='
ALIASES = {'SJ':'SJS','TB':'TBL','LA':'LAK','NJ':'NJD','WSH':'WSH','UTAH':'UTA','ARI':'UTA'}


def american(value):
    """Accept American prices, including EVEN; reject spreads and malformed prices."""
    if isinstance(value, str):
        value = value.strip().upper().replace('−', '-')
        if value in {'EVEN', 'EV', 'PK'}:
            return 100
    try:
        n = float(value)
    except (TypeError, ValueError):
        return None
    return int(n) if math.isfinite(n) and n.is_integer() and 100 <= abs(n) <= 100000 else None


def valid_market(market, game, now=None):
    try:
        at = datetime.fromisoformat(market['observed_at'].replace('Z', '+00:00'))
        start = datetime.fromisoformat(game['start'].replace('Z', '+00:00'))
        return (market['source'] == 'ESPN' and isinstance(market['provider'], str) and 0 < len(market['provider']) <= 50
                and market['source_url'].startswith('https://www.espn.com/nhl/game/_/gameId/')
                and all(type(market[k]) is int and american(market[k]) is not None for k in ['home', 'away'])
                and at < start and at <= (now or datetime.now(timezone.utc)) + timedelta(minutes=5))
    except (KeyError, TypeError, ValueError):
        return False


def event_market(event, game, observed_at):
    """Join by both clubs, venue order and scheduled start, not similar team names."""
    try:
        competition = event['competitions'][0]
        teams = {r['homeAway']: ALIASES.get(r['team']['abbreviation'], r['team']['abbreviation']) for r in competition['competitors']}
        start = datetime.fromisoformat(event['date'].replace('Z', '+00:00'))
        official = datetime.fromisoformat(game['start'].replace('Z', '+00:00'))
        observed = datetime.fromisoformat(observed_at.replace('Z', '+00:00'))
        if teams != {'home':game['home'], 'away':game['away']} or abs((start-official).total_seconds()) > 1800 or observed >= official:
            return None
        candidates = []
        for odds in competition.get('odds', []):
            line = odds.get('moneyline', {})
            h = american(line.get('home', {}).get('close', {}).get('odds', odds.get('homeTeamOdds', {}).get('moneyLine')))
            a = american(line.get('away', {}).get('close', {}).get('odds', odds.get('awayTeamOdds', {}).get('moneyLine')))
            if h is None or a is None:
                continue
            provider = odds.get('provider', {}).get('name', '')
            provider = 'DraftKings' if provider.lower().replace(' ', '') == 'draftkings' else provider
            result = {'home':h, 'away':a, 'provider':provider, 'source':'ESPN', 'observed_at':observed_at,
                      'source_url':f'https://www.espn.com/nhl/game/_/gameId/{event["id"]}'}
            if valid_market(result, game, observed):
                candidates.append((0 if provider == 'DraftKings' else 1, odds.get('provider', {}).get('priority', 999), result))
        return min(candidates, key=lambda r:r[:2])[2] if candidates else None
    except (KeyError, TypeError, ValueError, IndexError):
        return None


def enrich_markets(output, old, fetch, now, clock=None):
    """Refresh upcoming prices and preserve the last actually observed pregame snapshot."""
    at = datetime.fromisoformat(now.replace('Z', '+00:00'))
    previous = {g['id']:g for g in old.get('games', [])}
    upcoming = [g for g in output['games'] if datetime.fromisoformat(g['start'].replace('Z', '+00:00')) > at]
    dates = {datetime.fromisoformat(g['start'].replace('Z', '+00:00')).strftime('%Y%m%d') for g in upcoming}
    # ESPN's daily calendar is Eastern; include the NHL game date across midnight.
    dates.update(g['date'].replace('-', '') for g in upcoming)
    def get(day):
        try:
            events=fetch(ESPN+day).get('events', [])
            observed=(clock() if clock else datetime.now(timezone.utc)).isoformat(timespec='seconds').replace('+00:00','Z')
            return events,observed
        except Exception:
            return [],now
    events = {}
    with ThreadPoolExecutor(max_workers=3) as pool:
        for batch,observed in pool.map(get, sorted(dates)):
            for event in batch:
                events[event.get('id')] = (event,observed)
    for g in output['games']:
        saved = previous.get(g['id'], {})
        prior = saved.get('market') if saved.get('home') == g['home'] and saved.get('away') == g['away'] and saved.get('start')==g['start'] else None
        candidates = [m for e,observed in events.values() if (m:=event_market(e, g, observed))]
        if len(candidates) == 1:
            g['market'] = candidates[0]
        elif prior and valid_market(prior, g, at):
            g['market'] = prior
    output['market_version'] = 1
    return output
