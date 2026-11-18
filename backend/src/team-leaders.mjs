import {GAME_CENTER} from '../../static/playoffs/game-center-model.mjs';
import {PLAYOFF_PICTURE} from '../../static/playoffs/model.mjs';

const NHL = 'https://api-web.nhle.com/v1/';
const CACHE_SECONDS = 300;
const FALLBACK_SECONDS = 86400;
const stats = GAME_CENTER.leaderStats.map(([key]) => key);
const validTotal = value => Number.isInteger(value) && value >= 0 && value <= 1000;
const validId = id => Number.isInteger(id) && id > 0 && id <= 99999999;

function teamLeaders(report, season) {
  if (String(report?.season) !== season || report.gameType !== 2 || !Array.isArray(report.skaters) || report.skaters.length > 100) {
    throw new Error('Invalid NHL club stats');
  }
  const seen = new Set();
  const players = report.skaters.map(player => {
    const id = player.playerId;
    const name = [player.firstName?.default, player.lastName?.default].filter(value => typeof value === 'string').join(' ').trim();
    if (!validId(id) || seen.has(id) || !name || name.length > 100 || !stats.every(key => validTotal(player[key]))) {
      throw new Error('Invalid NHL club skater');
    }
    seen.add(id);
    return {id, name, ...Object.fromEntries(stats.map(key => [key, player[key]]))};
  });
  return Object.fromEntries(stats.map(key => {
    const ranked = [...players].sort((a, b) => b[key] - a[key] || b.points - a.points || b.goals - a.goals || a.id - b.id);
    let rank = 1;
    const leaders = ranked.slice(0, 3).map((player, index) => {
      if (index && player[key] !== ranked[index - 1][key]) rank = index + 1;
      const tied = ranked[index - 1]?.[key] === player[key] || ranked[index + 1]?.[key] === player[key];
      return {id: player.id, name: player.name, value: player[key], rank, tied};
    });
    return [key, leaders];
  }));
}

function leagueLeaders(report) {
  return Object.fromEntries(stats.map(key => {
    const rows = report?.[key === 'penaltyMinutes' ? 'penaltyMins' : key];
    if (!Array.isArray(rows) || rows.length > 1600) throw new Error('Invalid NHL league leaders');
    const seen = new Set();
    let previous = Infinity;
    let rank = 1;
    const leaders = {};
    for (const [index, row] of rows.entries()) {
      if (!validId(row.id) || seen.has(row.id) || !validTotal(row.value) || row.value > previous) {
        throw new Error('Invalid NHL league skater');
      }
      seen.add(row.id);
      if (row.value !== previous) rank = index + 1;
      if (row.value > 0 && rank <= 3) leaders[row.id] = rank;
      previous = row.value;
    }
    return [key, leaders];
  }));
}

async function loadReport({cache, fetcher, now, season, source, url, parse}) {
  const key = new Request(`https://api.sweater.win/api/playoffs/team-leaders-cache/${season}/${source}`);
  let saved;
  try { saved = await (await cache?.match(key))?.json(); } catch {}
  const age = saved ? now - Date.parse(saved.checked_at) : Infinity;
  if (age >= 0 && age < CACHE_SECONDS * 1000) return saved;
  try {
    const response = await fetcher(url, {redirect: 'manual', cache: 'no-store', signal: AbortSignal.timeout(7000)});
    if (!response.ok) throw new Error('NHL stats unavailable');
    const body = await response.text();
    if (body.length > 2500000) throw new Error('Oversized NHL stats report');
    const next = {checked_at: new Date(now).toISOString(), rows: parse(JSON.parse(body))};
    try {
      await cache?.put(key, Response.json(next, {headers: {'Cache-Control': `public,max-age=${FALLBACK_SECONDS}`}}));
    } catch {}
    return next;
  } catch {
    return age >= 0 && age < FALLBACK_SECONDS * 1000 ? {...saved, stale: true} : null;
  }
}

export async function handleTeamLeaders(request, env, {fetcher = fetch, cache = globalThis.caches?.default, now = Date.now()} = {}) {
  const url = new URL(request.url);
  if (url.pathname !== '/api/playoffs/team-leaders') return null;
  const origin = request.headers.get('Origin');
  const allowed = ['https://sweater.win', 'https://www.sweater.win', ...String(env.ALLOWED_ORIGINS || '').split(',').map(value => value.trim())];
  if (origin && !allowed.includes(origin)) return Response.json({error: 'Origin not allowed'}, {status: 403});
  const headers = {'Access-Control-Allow-Origin': origin || '*', 'Access-Control-Allow-Methods': 'GET,OPTIONS', 'Vary': 'Origin', 'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'};
  const json = (body, status = 200) => Response.json(body, {status, headers});
  if (request.method === 'OPTIONS') return new Response(null, {status: 204, headers});
  if (request.method !== 'GET') return json({error: 'Method not allowed'}, 405);

  const {season, away, home} = Object.fromEntries(url.searchParams);
  const year = Number(season?.slice(0, 4));
  const date = new Date(now);
  const currentSeason = date.getUTCFullYear() - Number(date.getUTCMonth() < 6);
  if (!/^20\d{6}$/.test(season || '') || season !== `${year}${year + 1}` || year < 2017 || year > currentSeason || away === home || ![away, home].every(club => PLAYOFF_PICTURE.clubs.has(club))) {
    return json({error: 'Invalid NHL season or matchup'}, 400);
  }

  const options = {cache, fetcher, now, season};
  const reports = [away, home].map(club => loadReport({...options, source: club, url: `${NHL}club-stats/${club}/${season}/2`, parse: report => teamLeaders(report, season)}));
  const league = loadReport({...options, source: 'league', url: `${NHL}skater-stats-leaders/${season}/2?categories=points%2Cgoals%2Cassists%2CpenaltyMins&limit=-1`, parse: leagueLeaders});
  const [awayReport, homeReport, leagueReport] = await Promise.all([...reports, league]);
  if (!awayReport && !homeReport) return json({error: 'NHL team leaders are temporarily unavailable'}, 503);
  const teams = Object.fromEntries([[away, awayReport], [home, homeReport]].map(([club, report]) => [club, report?.rows ?? null]));
  const checkedAt = [awayReport, homeReport, leagueReport].filter(Boolean).map(report => report.checked_at).sort()[0];
  return json({version: 1, season, checked_at: checkedAt, stale: [awayReport, homeReport, leagueReport].some(report => report?.stale === true), teams, league_ranks: leagueReport?.rows ?? null});
}
