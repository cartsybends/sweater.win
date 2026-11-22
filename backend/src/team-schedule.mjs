import {PLAYOFF_PICTURE} from '../../static/playoffs/model.mjs';

const NHL = 'https://api-web.nhle.com/v1/club-schedule-season/';
const FRESH_MS = 120000;
const FALLBACK_MS = 86400000;
const pending = new Map();
const states = new Map([['OFF', 'final'], ['FINAL', 'final'], ['LIVE', 'live'], ['CRIT', 'live'],
  ['OVER', 'pending'], ['FUT', 'scheduled'], ['PRE', 'scheduled']]);

function scheduleGame(game) {
  const status = game.gameScheduleState === 'PPD' ? 'postponed'
    : game.gameScheduleState === 'CNCL' ? 'cancelled' : states.get(game.gameState);
  const final = status === 'final';
  const hasScore = (status === 'live' || status === 'pending') &&
    Number.isInteger(game.homeTeam?.score) && Number.isInteger(game.awayTeam?.score);
  return {
    id: game.id, type: game.gameType, start: game.startTimeUTC, home: game.homeTeam?.abbrev, away: game.awayTeam?.abbrev,
    status, time_tbd: game.gameScheduleState === 'TBD',
    hg: final || hasScore ? game.homeTeam?.score : null,
    ag: final || hasScore ? game.awayTeam?.score : null,
    end: final ? game.gameOutcome?.lastPeriodType ?? game.periodDescriptor?.periodType : null,
  };
}

export async function handleTeamSchedule(request, env, {fetcher = fetch, cache = globalThis.caches?.default, now = Date.now()} = {}) {
  const url = new URL(request.url);
  if (url.pathname !== '/api/playoffs/team-schedule') return null;
  const origin = request.headers.get('Origin');
  const allowed = ['https://sweater.win', 'https://www.sweater.win', ...String(env.ALLOWED_ORIGINS || '').split(',').map(value => value.trim())];
  if (origin && !allowed.includes(origin)) return Response.json({error: 'Origin not allowed'}, {status: 403});
  const headers = {'Access-Control-Allow-Origin': origin || '*', 'Access-Control-Allow-Methods': 'GET,OPTIONS',
    'Vary': 'Origin', 'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'};
  const json = (body, status = 200) => Response.json(body, {status, headers});
  if (request.method === 'OPTIONS') return new Response(null, {status: 204, headers});
  if (request.method !== 'GET') return json({error: 'Method not allowed'}, 405);

  const team = url.searchParams.get('team'), seasonText = url.searchParams.get('season');
  const season = Number(seasonText), year = Math.floor(season / 10000), date = new Date(now);
  const current = date.getUTCFullYear() - Number(date.getUTCMonth() < 6);
  if (!PLAYOFF_PICTURE.clubs.has(team) || !/^20\d{6}$/.test(seasonText || '') ||
      season !== year * 10000 + year + 1 || year < 2024 || year > current) {
    return json({error: 'Invalid NHL club or season'}, 400);
  }
  const load = async () => {
    const key = new Request(`https://api.sweater.win/api/playoffs/team-schedule?team=${team}&season=${season}`);
    let saved;
    try { saved = PLAYOFF_PICTURE.validateSchedule(await (await cache?.match(key))?.json(), team, season, now); } catch {}
    const age = saved ? now - Date.parse(saved.checked_at) : Infinity;
    if (age >= 0 && age < FRESH_MS) return saved;
    try {
      const response = await fetcher(NHL + team + '/' + season, {redirect: 'manual', cache: 'no-store', signal: AbortSignal.timeout(7000)});
      if (!response.ok) throw new Error('NHL schedule unavailable');
      const body = await response.text();
      if (body.length > 500000) throw new Error('Oversized NHL schedule');
      const raw = JSON.parse(body);
      if (!Array.isArray(raw.games) || raw.games.length > 150) throw new Error('Invalid NHL schedule');
      const games = raw.games.filter(game => game.season === season && [2, 3].includes(game.gameType)).map(scheduleGame);
      games.sort((a, b) => Date.parse(a.start) - Date.parse(b.start) || a.id - b.id);
      const data = PLAYOFF_PICTURE.validateSchedule({version: 1, team, season, checked_at: new Date(now).toISOString(), stale: false, games}, team, season, now);
      if (!data) throw new Error('Incomplete NHL team schedule');
      try { await cache?.put(key, Response.json(data, {headers: {'Cache-Control': 'public,max-age=86400'}})); } catch {}
      return data;
    } catch {
      return age >= 0 && age < FALLBACK_MS ? {...saved, stale: true} : null;
    }
  };
  const id = `${team}:${season}`;
  if (!pending.has(id)) pending.set(id, load().finally(() => pending.delete(id)));
  const data = await pending.get(id);
  return data ? json(data) : json({error: 'Team schedule temporarily unavailable'}, 503);
}
