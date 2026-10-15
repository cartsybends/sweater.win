// Sweater leaderboard API (Cloudflare Worker + D1)
// Endpoints:
//   POST /api/name         {uid, secret, name}           create a player or change the name
//   POST /api/result       {uid, secret, game, day, guesses}  save today's daily result (scored here, not in the browser)
//   GET  /api/leaderboard  ?game=<any key in GAMES>&period=today|week|all&uid=...
//   GET  /api/health

import { COMMUNITY_MODEL } from '../../static/community-games/model.mjs';

const PICK6 = [10, 8, 6, 4, 2, 1];
const GAMES = {
  grid: { days: 'grid_days', custom: 'community' },
  benchboss: { days: 'benchboss_days', custom: 'community' },
  teammatetrail: { days: 'teammatetrail_days', custom: 'community' },
  classic:  { days: "days",          max: 8 },
  statline: { days: "statline_days", max: 8 },
  team:     { days: "team_days",     max: 5 },
  journey:  { days: "journey_days",  max: 6, points: PICK6 },
  blur:     { days: "blur_days",     max: 6, points: PICK6 },
  number:   { days: "number_days",   max: 5, points: [10, 7, 5, 3, 1], guessNumber: true },
  roster:   { days: "roster_days",   roster: true },
  draft:    { days: "draft_days",    max: 5, points: [10, 7, 5, 3, 1], guessDraft: true },
  map:      { days: "map_days",      mapGame: true },
  conn:     { days: "conn_days",     conn: true },
  rank:     { days: "rank_days",     custom: "rank" },
  puck:     { days: "puck_days",     custom: "puck" },
  shoot:    { days: "shoot_days",    custom: "shoot" },
  zam:      { days: "zam_days",      custom: "zam" },
  truths:   { days: "truths_days",   custom: "truths" },
  hlt:      { days: "hlt_days",      custom: "hlt" },
  season:   { days: "season_days",   custom: "season" },
  playoff:  { days: "playoff_days",  max: 6, points: PICK6, custom: "playoff" },
  trophy:   { days: "trophy_days",   custom: "trophy" },
  mroster:  { days: "mroster_days",  custom: "mroster" },
  cups:     { days: "cups_days",     custom: "cups" },
  // Higher or Lower: one board per stat; "col" is the column in a player's career rows
  hl_goals:   { days: "hl_days", stat: "goals",   col: 3, max: 40 },
  hl_assists: { days: "hl_days", stat: "assists", col: 4, max: 40 },
  hl_points:  { days: "hl_days", stat: "points",  col: 5, max: 40 },
  hl_pim:     { days: "hl_days", stat: "pim",     col: 6, max: 40 },
  hl_gp:      { days: "hl_days", stat: "gp",      max: 40 },
  hl_height:  { days: "hl_days", stat: "height",  max: 40 },
  hl_weight:  { days: "hl_days", stat: "weight",  max: 40 },
  hl_age:     { days: "hl_days", stat: "age",     max: 40 },
};
const TEAM_POINTS = [10, 6, 3, 2, 1];
const NAME_RE = /^[A-Za-z0-9 _.\-]{3,16}$/;
const BLOCKED = ["fuck", "shit", "cunt", "nigg", "fag", "bitch", "whore", "slut", "rape", "nazi", "hitler", "admin", "sweater"];
const SCHEDULE_TTL_MS = 5 * 60 * 1000;

let scheduleCache = { at: 0, data: null };

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const cors = corsHeaders(request, env);
    if (request.method === "OPTIONS") return new Response(null, { status: 204, headers: cors });
    try {
      let out;
      if (url.pathname === "/api/health") out = { ok: true, today: etToday() };
      else if (url.pathname === "/api/leaderboard" && request.method === "GET") out = await leaderboard(url, env);
      else if (url.pathname === "/api/name" && request.method === "POST") out = await setName(await readJson(request), env);
      else if (url.pathname === "/api/result" && request.method === "POST") out = await saveResult(await readJson(request), env);
      else if (url.pathname === "/api/party/create" && request.method === "POST") out = await partyCreate(env);
      else if (url.pathname === "/api/party/join" && request.method === "POST") out = await partyJoin(await readJson(request), env);
      else if (url.pathname === "/api/party/host" && request.method === "POST") out = await partyHost(await readJson(request), env);
      else if (url.pathname === "/api/party/answer" && request.method === "POST") out = await partyAnswer(await readJson(request), env);
      else if (url.pathname === "/api/party/state" && request.method === "GET") out = await partyState(url, env);
      else throw httpError(404, "Not found");
      return reply(out, 200, cors);
    } catch (e) {
      if (!e.status) console.error(e);
      return reply({ error: e.status ? e.message : "Something went wrong" }, e.status || 500, cors);
    }
  },
};

// ---------------------------------------------------------------- helpers
function httpError(status, message) { return Object.assign(new Error(message), { status }); }

function corsHeaders(request, env) {
  const allowed = String(env.ALLOWED_ORIGINS || "").split(",").map(s => s.trim()).filter(Boolean);
  const origin = request.headers.get("Origin") || "";
  return {
    "Access-Control-Allow-Origin": allowed.includes(origin) ? origin : (allowed[0] || "*"),
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
    "Access-Control-Max-Age": "86400",
    "Vary": "Origin",
  };
}

function reply(obj, status, cors) {
  return new Response(JSON.stringify(obj), {
    status,
    headers: { "Content-Type": "application/json", "Cache-Control": "no-store", ...cors },
  });
}

async function readJson(request) {
  const text = await request.text();
  if (text.length > 16000) throw httpError(413, "Request too large");
  try { return JSON.parse(text); } catch { throw httpError(400, "Invalid JSON"); }
}

function etToday(offsetDays = 0) {
  const d = new Date(Date.now() + offsetDays * 86400000);
  const parts = Object.fromEntries(new Intl.DateTimeFormat("en-CA", {
    timeZone: "America/New_York", year: "numeric", month: "2-digit", day: "2-digit",
  }).formatToParts(d).map(p => [p.type, p.value]));
  return `${parts.year}-${parts.month}-${parts.day}`;
}

function shiftDay(day, n) {
  const [y, m, d] = day.split("-").map(Number);
  return new Date(Date.UTC(y, m - 1, d) + n * 86400000).toISOString().slice(0, 10);
}

async function sha256(text) {
  const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return [...new Uint8Array(buf)].map(b => b.toString(16).padStart(2, "0")).join("");
}

function checkIdentity(body) {
  if (typeof body.uid !== "string" || !/^[a-f0-9-]{36}$/.test(body.uid)) throw httpError(400, "Invalid player");
  if (typeof body.secret !== "string" || !/^[a-f0-9]{64}$/.test(body.secret)) throw httpError(400, "Invalid player");
}

async function verifyPlayer(env, body) {
  checkIdentity(body);
  const row = await env.DB.prepare("SELECT secret_hash FROM players WHERE uid = ?1").bind(body.uid).first();
  if (!row) throw httpError(403, "Pick a leaderboard name first");
  if (row.secret_hash !== await sha256(body.secret)) throw httpError(403, "Not allowed");
}

export async function loadSchedule(env) {
  if (scheduleCache.data && Date.now() - scheduleCache.at < SCHEDULE_TTL_MS) return scheduleCache.data;
  const res = await fetch(env.SCHEDULE_URL, { cf: { cacheTtl: 300 } });
  if (!res.ok) throw httpError(503, "Couldn't load today's puzzles");
  scheduleCache = { at: Date.now(), data: await res.json() };
  return scheduleCache.data;
}

// ---------------------------------------------------------------- Rank 'Em, Puck Drop, Shootout, Zamboni
function rankValue(p, stat) {
  const car = p?.car || [];
  if (stat === "goals") return car.reduce((n, r) => n + (r[3] || 0), 0);
  if (stat === "points") return car.reduce((n, r) => n + (r[5] || 0), 0);
  if (stat === "gp") return car.reduce((n, r) => n + (r[2] || 0), 0);
  if (stat === "height") return p?.ht || 0;
  if (stat === "weight") return p?.wt || 0;
  return -Number(String(p?.birth || "2000-01-01").replace(/-/g, ""));
}
function scoreRank(puzzle, guesses, schedule) {
  if (!puzzle?.ids?.length) throw httpError(503, "Today's puzzle data is missing");
  const correct = puzzle.ids.slice().sort((a, b) =>
    rankValue(schedule.players?.[String(b)], puzzle.stat) - rankValue(schedule.players?.[String(a)], puzzle.stat)).join(",");
  const want = puzzle.ids.slice().sort((a, b) => a - b).join(",");
  if (!Array.isArray(guesses) || guesses.length < 1 || guesses.length > 3 || new Set(guesses).size !== guesses.length) throw httpError(400, "Invalid guesses");
  for (const g of guesses) {
    if (typeof g !== "string" || g.split(",").map(Number).sort((a, b) => a - b).join(",") !== want) throw httpError(400, "Invalid guesses");
  }
  const hit = guesses.indexOf(correct);
  if (hit !== -1 && hit !== guesses.length - 1) throw httpError(400, "Invalid guesses");
  const won = hit !== -1;
  if (!won && guesses.length !== 3) throw httpError(400, "That game isn't finished yet");
  return { won, tries: guesses.length, points: won ? [10, 6, 3][guesses.length - 1] : 0 };
}
function puckMatch(rule, p) {
  if (!p) return false;
  if (rule.kind === "team") return p.team === rule.key;
  if (rule.kind === "nation") return p.nation === rule.key;
  if (rule.kind === "pos") return p.pos === rule.key;
  return Array.isArray(p.draft) && p.draft[1] === 1;
}
function scorePuck(puzzle, guesses, schedule) {
  if (!puzzle?.ids?.length) throw httpError(503, "Today's puzzle data is missing");
  if (!Array.isArray(guesses) || guesses[guesses.length - 1] !== "END") throw httpError(400, "That game isn't finished yet");
  const taps = guesses.slice(0, -1);
  if (new Set(taps).size !== taps.length || !taps.every(t => Number.isInteger(t) && puzzle.ids.includes(t))) throw httpError(400, "Invalid guesses");
  const right = taps.filter(t => puckMatch(puzzle, schedule.players?.[String(t)])).length;
  const total = puzzle.ids.filter(t => puckMatch(puzzle, schedule.players?.[String(t)])).length;
  const wrong = taps.length - right;
  return { won: right === total && wrong === 0, tries: right, points: Math.max(0, right - wrong) };
}
function scoreShootout(puzzle, guesses) {
  const rounds = puzzle?.rounds;
  if (!Array.isArray(rounds) || rounds.length !== 5) throw httpError(503, "Today's puzzle data is missing");
  if (!Array.isArray(guesses) || guesses.length !== 5) throw httpError(400, "That game isn't finished yet");
  let goals = 0;
  guesses.forEach((g, i) => {
    const m = typeof g === "string" && /^([0-3]):(-1|[0-4])$/.exec(g);
    if (!m) throw httpError(400, "Invalid guesses");
    const right = Number(m[1]) === rounds[i].a, zone = Number(m[2]);
    if (right && zone >= 0 && !rounds[i].keep.includes(zone)) goals++;
  });
  return { won: goals >= 3, tries: goals, points: goals * 2 };
}
function scoreZamboni(answer, guesses) {
  if (!Array.isArray(guesses) || guesses.length < 1 || guesses.length > 3) throw httpError(400, "Invalid guesses");
  let last = 0;
  const parsed = guesses.map(g => {
    const m = typeof g === "string" && /^(\d+)@(\d{1,3})$/.exec(g);
    if (!m || Number(m[2]) > 100 || Number(m[2]) < last) throw httpError(400, "Invalid guesses");
    last = Number(m[2]);
    return [Number(m[1]), last];
  });
  if (new Set(parsed.map(x => x[0])).size !== parsed.length) throw httpError(400, "Invalid guesses");
  const hit = parsed.findIndex(x => x[0] === answer);
  if (hit !== -1 && hit !== parsed.length - 1) throw httpError(400, "Invalid guesses");
  const won = hit !== -1;
  if (!won && parsed.length !== 3) throw httpError(400, "That game isn't finished yet");
  if (!won) return { won, tries: parsed.length, points: 0 };
  const pct = parsed[hit][1];
  return { won, tries: parsed.length, points: Math.max(1, 10 - Math.floor(pct / 10) - 2 * (parsed.length - 1)) };
}

// Two Truths: five rounds, each guess is the statement the player thinks is false.
function scoreTruths(puzzle, guesses) {
  const rounds = puzzle?.rounds;
  if (!Array.isArray(rounds) || rounds.length !== 5) throw httpError(503, "Today's puzzle data is missing");
  if (!Array.isArray(guesses) || guesses.length !== 5) throw httpError(400, "That game isn't finished yet");
  let right = 0;
  guesses.forEach((g, i) => {
    const c = Number(g);
    if (!Number.isInteger(c) || c < 0 || c > 2) throw httpError(400, "Invalid guesses");
    if (c === rounds[i].f) right++;
  });
  return { won: right === 5, tries: right, points: right * 2 };
}

// Higher or Lower: Teams — same rules as the player version, using the stored team values.
function scoreTeamHL(puzzle, answers) {
  const seq = puzzle?.seq;
  if (!Array.isArray(seq) || seq.length < 2) throw httpError(503, "Today's puzzle data is missing");
  const limit = seq.length - 1;
  if (!Array.isArray(answers) || answers.length < 1 || answers.length > limit) throw httpError(400, "Invalid guesses");
  if (!answers.every(a => a === "H" || a === "L")) throw httpError(400, "Invalid guesses");
  let streak = 0;
  for (let i = 0; i < answers.length; i++) {
    const a = Number(seq[i][1]), b = Number(seq[i + 1][1]);
    const right = answers[i] === "H" ? b >= a : b <= a;
    if (!right) {
      if (i !== answers.length - 1) throw httpError(400, "Invalid guesses");
      return { won: false, tries: streak, points: streak };
    }
    streak++;
  }
  if (streak !== limit) throw httpError(400, "That game isn't finished yet");
  return { won: true, tries: streak, points: streak };
}

// Mystery Season: guesses are season start years; 3 tries.
function scoreSeason(puzzle, guesses) {
  const answer = puzzle?.y;
  if (!Number.isInteger(answer)) throw httpError(503, "Today's puzzle data is missing");
  if (!Array.isArray(guesses) || guesses.length < 1 || guesses.length > 3) throw httpError(400, "Invalid guesses");
  if (!guesses.every(g => Number.isInteger(g) && g > 1900 && g < 2100)) throw httpError(400, "Invalid guesses");
  if (new Set(guesses).size !== guesses.length) throw httpError(400, "Invalid guesses");
  const hit = guesses.indexOf(answer);
  if (hit !== -1 && hit !== guesses.length - 1) throw httpError(400, "Invalid guesses");
  const won = hit !== -1;
  if (!won && guesses.length !== 3) throw httpError(400, "That game isn't finished yet");
  return { won, tries: guesses.length, points: won ? [10, 6, 3][guesses.length - 1] : 0 };
}

// Trophy Case: five rounds, each guess is the option the player picked.
function scoreTrophy(puzzle, guesses) {
  const rounds = puzzle?.rounds;
  if (!Array.isArray(rounds) || rounds.length < 5) throw httpError(503, "Today's puzzle data is missing");
  if (!Array.isArray(guesses) || ![5, 10, 15, 20].includes(guesses.length) || guesses.length > rounds.length) {
    throw httpError(400, "That game isn't finished yet");
  }
  let right = 0;
  guesses.forEach((g, i) => {
    const c = Number(g);
    if (!Number.isInteger(c) || c < 0 || c > 3) throw httpError(400, "Invalid guesses");
    if (c === rounds[i].a) right++;
  });
  return { won: right === guesses.length, tries: right, points: right * 2 };
}

// Mystery Roster: guesses are team codes; 4 tries.
function scoreMysteryRoster(puzzle, guesses) {
  const answer = puzzle?.team;
  if (!answer) throw httpError(503, "Today's puzzle data is missing");
  if (!Array.isArray(guesses) || guesses.length < 1 || guesses.length > 4) throw httpError(400, "Invalid guesses");
  if (!guesses.every(g => typeof g === "string" && /^[A-Z]{3}$/.test(g))) throw httpError(400, "Invalid guesses");
  if (new Set(guesses).size !== guesses.length) throw httpError(400, "Invalid guesses");
  const hit = guesses.indexOf(answer);
  if (hit !== -1 && hit !== guesses.length - 1) throw httpError(400, "Invalid guesses");
  const won = hit !== -1;
  if (!won && guesses.length !== 4) throw httpError(400, "That game isn't finished yet");
  return { won, tries: guesses.length, points: won ? [10, 6, 3, 1][guesses.length - 1] : 0 };
}

// Playoff History: a grid of Cup winners, runners-up and Conn Smythe winners. Guesses are typed names.
const cupsNorm = s => String(s).normalize("NFD").replace(/[\u0300-\u036f]/g, "")
  .toLowerCase().replace(/[^a-z0-9 ]/g, " ").replace(/\s+/g, " ").trim();
// A guess fills a square when it appears in the answer as whole words; players need the surname.
function cupsMatch(full, isPlayer, guess) {
  if (!full || guess.length < 3) return false;
  if (!(" " + full + " ").includes(" " + guess + " ")) return false;
  return !isPlayer || guess.split(" ").includes(full.split(" ").slice(-1)[0]);
}
function cupsKeys(rows) {
  const cells = [];
  rows.forEach(r => [1, 2, 3].forEach(c => { if (r[c]) cells.push({ full: cupsNorm(r[c]), player: c === 3 }); }));
  return cells;
}
function scoreCups(puzzle, guesses) {
  const rows = puzzle?.rows;
  if (!Array.isArray(rows) || !rows.length) throw httpError(503, "Today's puzzle data is missing");
  if (!Array.isArray(guesses) || guesses.length > 200) throw httpError(400, "Invalid guesses");
  const ended = guesses[guesses.length - 1] === "END";
  const typed = (ended ? guesses.slice(0, -1) : guesses).map(g => {
    if (typeof g !== "string" || g.length > 40) throw httpError(400, "Invalid guesses");
    return cupsNorm(g);
  });
  const keys = cupsKeys(rows), total = keys.length;
  const filled = keys.filter(k => typed.some(t => cupsMatch(k.full, k.player, t))).length;
  if (!ended && filled < total) throw httpError(400, "That game isn't finished yet");
  return { won: filled === total, tries: filled, points: filled };
}

// ---------------------------------------------------------------- Party Mode (live rooms, polled about once a second)
const PARTY_LETTERS = "ABCDEFGHJKLMNPQRSTUVWXYZ";
const PARTY_MAX_PLAYERS = 30, PARTY_LIMIT_S = 15, PARTY_TTL_MS = 6 * 3600 * 1000;
const randomHex = n => [...crypto.getRandomValues(new Uint8Array(n))].map(b => b.toString(16).padStart(2, "0")).join("");

async function partyRoom(env, code) {
  const row = await env.DB.prepare("SELECT code, host_hash, state, created FROM party_rooms WHERE code = ?1").bind(String(code || "").toUpperCase()).first();
  if (!row) throw httpError(404, "No game with that code");
  return { ...row, state: JSON.parse(row.state) };
}
const saveParty = (env, code, state) =>
  env.DB.prepare("UPDATE party_rooms SET state = ?1, updated = ?2 WHERE code = ?3").bind(JSON.stringify(state), Date.now(), code).run();

async function partyCreate(env) {
  const cutoff = Date.now() - PARTY_TTL_MS;
  const old = await env.DB.prepare("SELECT code FROM party_rooms WHERE created < ?1").bind(cutoff).all();
  for (const r of old.results) {
    await env.DB.batch([
      env.DB.prepare("DELETE FROM party_answers WHERE code = ?1").bind(r.code),
      env.DB.prepare("DELETE FROM party_players WHERE code = ?1").bind(r.code),
      env.DB.prepare("DELETE FROM party_rooms WHERE code = ?1").bind(r.code),
    ]);
  }
  for (let i = 0; i < 20; i++) {
    const code = Array.from(crypto.getRandomValues(new Uint8Array(4)), b => PARTY_LETTERS[b % PARTY_LETTERS.length]).join("");
    const hostKey = randomHex(24);
    const state = { status: "lobby", qi: -1, questions: [], limit: PARTY_LIMIT_S };
    const res = await env.DB.prepare("INSERT OR IGNORE INTO party_rooms (code, host_hash, state, created, updated) VALUES (?1, ?2, ?3, ?4, ?4)")
      .bind(code, await sha256(hostKey), JSON.stringify(state), Date.now()).run();
    if (res.meta.changes) return { code, hostKey };
  }
  throw httpError(503, "Couldn't create a game. Try again.");
}

async function partyJoin(body, env) {
  const room = await partyRoom(env, body.code);
  if (room.state.status !== "lobby") throw httpError(409, "That game has already started");
  let name = String(body.name || "").trim().replace(/\s+/g, " ").slice(0, 14);
  if (!/^[A-Za-z0-9 _.\-']{1,14}$/.test(name)) throw httpError(400, "Use 1–14 letters or numbers for your name");
  const LEET = { "0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t", "8": "b", "9": "g" };
  if (BLOCKED.filter(w => w !== "admin" && w !== "sweater").some(w => name.toLowerCase().replace(/[0-9]/g, c => LEET[c] || c).replace(/[\s_.\-']/g, "").includes(w))) {
    throw httpError(400, "Please pick a different name");
  }
  const players = await env.DB.prepare("SELECT name FROM party_players WHERE code = ?1").bind(room.code).all();
  if (players.results.length >= PARTY_MAX_PLAYERS) throw httpError(409, "That game is full");
  const taken = new Set(players.results.map(p => p.name.toLowerCase()));
  for (let n = 2; taken.has(name.toLowerCase()); n++) name = `${name.slice(0, 12)} ${n}`;
  const pid = randomHex(8), key = randomHex(16);
  await env.DB.prepare("INSERT INTO party_players (code, pid, name, key_hash, score, joined) VALUES (?1, ?2, ?3, ?4, 0, ?5)")
    .bind(room.code, pid, name, await sha256(key), Date.now()).run();
  return { code: room.code, pid, key, name };
}

async function partyHost(body, env) {
  const room = await partyRoom(env, body.code);
  if (room.host_hash !== await sha256(String(body.hostKey || ""))) throw httpError(403, "Not allowed");
  const st = room.state, now = Date.now();
  if (body.action === "start" && st.status === "lobby") {
    const qs = body.questions;
    if (!Array.isArray(qs) || qs.length < 1 || qs.length > 20 || !qs.every(q =>
      q && typeof q.q === "string" && q.q.length < 200 && Array.isArray(q.o) && q.o.length === 4 &&
      q.o.every(o => typeof o === "string" && o.length < 80) && Number.isInteger(q.a) && q.a >= 0 && q.a < 4)) {
      throw httpError(400, "Invalid questions");
    }
    Object.assign(st, { questions: qs, qi: 0, status: "question", startedAt: now, endsAt: now + st.limit * 1000 });
  } else if (body.action === "reveal" && st.status === "question") {
    st.status = "reveal";
  } else if (body.action === "next" && st.status === "reveal") {
    if (st.qi + 1 >= st.questions.length) st.status = "done";
    else Object.assign(st, { qi: st.qi + 1, status: "question", startedAt: now, endsAt: now + st.limit * 1000 });
  } else if (body.action === "end") {
    st.status = "done";
  } else if (body.action !== "state") {
    throw httpError(409, "That doesn't fit the game right now");
  }
  await saveParty(env, room.code, st);
  return partyView(env, room.code, st, null, true);
}

async function partyAnswer(body, env) {
  const room = await partyRoom(env, body.code);
  const me = await env.DB.prepare("SELECT pid, key_hash FROM party_players WHERE code = ?1 AND pid = ?2").bind(room.code, String(body.pid || "")).first();
  if (!me || me.key_hash !== await sha256(String(body.key || ""))) throw httpError(403, "Not allowed");
  const st = room.state, now = Date.now();
  if (st.status !== "question" || body.qi !== st.qi || now > st.endsAt + 1000) throw httpError(409, "Too late for that question");
  const choice = Number(body.choice);
  if (!Number.isInteger(choice) || choice < 0 || choice > 3) throw httpError(400, "Invalid answer");
  const q = st.questions[st.qi];
  const elapsed = Math.min(1, Math.max(0, (now - st.startedAt) / (st.limit * 1000)));
  const points = choice === q.a ? Math.round(1000 - 500 * elapsed) : 0;
  const res = await env.DB.prepare("INSERT OR IGNORE INTO party_answers (code, qi, pid, choice, points) VALUES (?1, ?2, ?3, ?4, ?5)")
    .bind(room.code, st.qi, me.pid, choice, points).run();
  if (res.meta.changes) {
    await env.DB.prepare("UPDATE party_players SET score = score + ?1 WHERE code = ?2 AND pid = ?3").bind(points, room.code, me.pid).run();
  }
  return { ok: true };
}

async function partyState(url, env) {
  const room = await partyRoom(env, url.searchParams.get("code"));
  let pid = null;
  const askPid = url.searchParams.get("pid");
  if (askPid) {
    const me = await env.DB.prepare("SELECT key_hash FROM party_players WHERE code = ?1 AND pid = ?2").bind(room.code, askPid).first();
    if (me && me.key_hash === await sha256(url.searchParams.get("key") || "")) pid = askPid;
  }
  return partyView(env, room.code, room.state, pid, false);
}

async function partyView(env, code, st, pid, isHost) {
  const players = (await env.DB.prepare("SELECT pid, name, score FROM party_players WHERE code = ?1 ORDER BY score DESC, joined ASC").bind(code).all()).results;
  const out = {
    code, status: st.status, qi: st.qi, total: st.questions.length, limit: st.limit, now: Date.now(),
    players: players.map(p => ({ name: p.name, score: p.score, me: p.pid === pid })),
  };
  if (st.qi >= 0 && st.questions[st.qi]) {
    const q = st.questions[st.qi], showAnswer = st.status !== "question";
    out.question = { q: q.q, o: q.o, a: showAnswer ? q.a : undefined };
    out.endsAt = st.endsAt;
    const answers = (await env.DB.prepare("SELECT pid, choice, points FROM party_answers WHERE code = ?1 AND qi = ?2").bind(code, st.qi).all()).results;
    out.answered = answers.length;
    if (showAnswer) out.counts = [0, 1, 2, 3].map(i => answers.filter(a => a.choice === i).length);
    const mine = pid && answers.find(a => a.pid === pid);
    if (mine) out.you = { choice: mine.choice, points: showAnswer ? mine.points : undefined };
  }
  return out;
}

// ---------------------------------------------------------------- scoring
function seasonsOf(player) {
  const bySeason = new Map();
  for (const row of player?.car || []) {
    if (!bySeason.has(row[0])) bySeason.set(row[0], []);
    bySeason.get(row[0]).push(row);
  }
  return bySeason;
}

const STAT_COLS = { goals: 3, assists: 4, points: 5, pim: 6 };
function hlValue(player, game) {
  return statValue(player, GAMES[game].stat);
}
function statValue(player, stat) {
  const col = STAT_COLS[stat];
  if (col) return careerHigh(player, col);
  if (stat === "gp") return (player.car || []).reduce((n, r) => n + (r[2] || 0), 0);
  if (stat === "height") return player.ht || 0;
  if (stat === "weight") return player.wt || 0;
  return -Number(String(player.birth || "2000-01-01").replace(/-/g, ""));   // age: earlier birthday = older
}

function careerHigh(player, col) {
  let best = 0;
  for (const rows of seasonsOf(player).values()) {
    best = Math.max(best, rows.reduce((n, r) => n + (r[col] || 0), 0));
  }
  return best;
}

// Higher or Lower: answers are "H"/"L"; the run ends at the first wrong answer or after the last matchup.
function scoreHigherLower(game, sequence, answers, schedule) {
  if (!Array.isArray(sequence) || sequence.length < 2) throw httpError(503, "Today's puzzle data is missing");
  const limit = sequence.length - 1;
  if (!Array.isArray(answers) || answers.length < 1 || answers.length > limit) throw httpError(400, "Invalid guesses");
  if (!answers.every(a => a === "H" || a === "L")) throw httpError(400, "Invalid guesses");
  const highs = sequence.map(id => {
    const p = schedule.players?.[String(id)];
    if (!p) throw httpError(503, "Today's puzzle data is missing");
    return hlValue(p, game);
  });
  let streak = 0;
  for (let i = 0; i < answers.length; i++) {
    const a = highs[i], b = highs[i + 1];
    const right = answers[i] === "H" ? b >= a : b <= a;   // ties count either way
    if (!right) {
      if (i !== answers.length - 1) throw httpError(400, "Invalid guesses");
      return { won: false, tries: streak, points: streak };
    }
    streak++;
  }
  if (streak !== limit) throw httpError(400, "That game isn't finished yet");
  return { won: true, tries: streak, points: streak };
}

// Returns { won, tries, points } or throws if the guesses don't describe a finished game.
// Roster recall: guesses are player ids from the day's roster, plus "END" when time ran out.
function scoreRoster(snapshot, guesses) {
  if (!snapshot || !Array.isArray(snapshot.ids) || !snapshot.ids.length) throw httpError(503, "Today's puzzle data is missing");
  if (!Array.isArray(guesses) || guesses.length > snapshot.ids.length + 1) throw httpError(400, "Invalid guesses");
  const ended = guesses[guesses.length - 1] === "END";
  const named = ended ? guesses.slice(0, -1) : guesses;
  if (!named.every(g => Number.isInteger(g) && snapshot.ids.includes(g))) throw httpError(400, "Invalid guesses");
  if (new Set(named).size !== named.length) throw httpError(400, "Invalid guesses");
  const won = named.length === snapshot.ids.length;
  if (!ended && !won) throw httpError(400, "That game isn't finished yet");
  return { won, tries: named.length, points: named.length };
}

// Birthplace: guesses are [lat, lon] pins; a pin within 100 km ends the game, otherwise 3 pins.
const MAP_WIN_KM = 100, MAP_PINS = 3;
function distanceKm([la1, lo1], [la2, lo2]) {
  const r = Math.PI / 180, a = Math.sin((la2 - la1) * r / 2) ** 2
    + Math.cos(la1 * r) * Math.cos(la2 * r) * Math.sin((lo2 - lo1) * r / 2) ** 2;
  return 6371 * 2 * Math.asin(Math.min(1, Math.sqrt(a)));
}
function scoreMap(player, pins) {
  const at = player?.bp;
  if (!Array.isArray(at) || at.length < 2) throw httpError(503, "Today's puzzle data is missing");
  if (!Array.isArray(pins) || pins.length < 1 || pins.length > MAP_PINS) throw httpError(400, "Invalid guesses");
  if (!pins.every(x => Array.isArray(x) && x.length === 2 && x.every(Number.isFinite) && Math.abs(x[0]) <= 90 && Math.abs(x[1]) <= 180)) {
    throw httpError(400, "Invalid guesses");
  }
  const dists = pins.map(x => distanceKm(x, at));
  if (dists.slice(0, -1).some(d => d <= MAP_WIN_KM)) throw httpError(400, "Invalid guesses");
  const won = dists[dists.length - 1] <= MAP_WIN_KM;
  if (!won && pins.length < MAP_PINS) throw httpError(400, "That game isn't finished yet");
  const best = Math.min(...dists);
  const tier = [[100, 10], [250, 8], [500, 6], [1000, 4], [2500, 2]].find(([km]) => best <= km);
  const points = Math.max(0, (tier ? tier[1] : 0) - 2 * (pins.length - 1));
  return { won, tries: pins.length, points };
}

// Connections: guesses are "id,id,id,id" (sorted); 4 groups to find, the 4th mistake ends the game.
function scoreConnections(groups, guesses) {
  if (!Array.isArray(groups) || groups.length !== 4) throw httpError(503, "Today's puzzle data is missing");
  const keys = groups.map(g => g.ids.slice().sort((a, b) => a - b).join(","));
  const all = new Set(groups.flatMap(g => g.ids));
  if (!Array.isArray(guesses) || guesses.length < 1 || guesses.length > 7) throw httpError(400, "Invalid guesses");
  if (new Set(guesses).size !== guesses.length) throw httpError(400, "Invalid guesses");
  const solved = new Set();
  let mistakes = 0;
  for (const [i, g] of guesses.entries()) {
    if (solved.size === 4 || mistakes >= 4) throw httpError(400, "Invalid guesses");
    const ids = typeof g === "string" ? g.split(",").map(Number) : [];
    const sortedKey = ids.slice().sort((a, b) => a - b).join(",");
    if (ids.length !== 4 || new Set(ids).size !== 4 || !ids.every(x => all.has(x)) || sortedKey !== g) {
      throw httpError(400, "Invalid guesses");
    }
    const k = keys.indexOf(g);
    if (k >= 0) solved.add(k); else mistakes++;
  }
  const won = solved.size === 4;
  if (!won && mistakes < 4) throw httpError(400, "That game isn't finished yet");
  return { won, tries: guesses.length, points: won ? [10, 8, 6, 4][mistakes] : 0 };
}


export function scoreGame(game, answer, guesses, schedule) {
  if (GAMES[game].custom === 'community') {
    const data=schedule.community,base=data?.[game]?.find(p=>p.id===answer?.id),target=base&&{...base,...(game==='grid'&&Array.isArray(answer.rarity)?{rarity:answer.rarity}:{})};
    if(!target)throw httpError(503,"Today's puzzle data is missing");
    try{return COMMUNITY_MODEL.result(game,target,guesses,data);}catch(e){throw httpError(400,e.message);}
  }
  if (GAMES[game].stat) return scoreHigherLower(game, answer, guesses, schedule);
  if (GAMES[game].roster) return scoreRoster(answer, guesses);
  if (GAMES[game].mapGame) return scoreMap(schedule.players?.[String(answer)], guesses);
  if (GAMES[game].conn) return scoreConnections(answer, guesses);
  if (GAMES[game].custom === "rank") return scoreRank(answer, guesses, schedule);
  if (GAMES[game].custom === "puck") return scorePuck(answer, guesses, schedule);
  if (GAMES[game].custom === "shoot") return scoreShootout(answer, guesses);
  if (GAMES[game].custom === "zam") return scoreZamboni(answer, guesses);
  if (GAMES[game].custom === "truths") return scoreTruths(answer, guesses);
  if (GAMES[game].custom === "hlt") return scoreTeamHL(answer, guesses);
  if (GAMES[game].custom === "season") return scoreSeason(answer, guesses);
  if (GAMES[game].custom === "trophy") return scoreTrophy(answer, guesses);
  if (GAMES[game].custom === "mroster") return scoreMysteryRoster(answer, guesses);
  if (GAMES[game].custom === "cups") return scoreCups(answer, guesses);
  const { max } = GAMES[game];
  if (!Array.isArray(guesses) || guesses.length < 1 || guesses.length > max) throw httpError(400, "Invalid guesses");
  const isTeam = game === "team";
  for (const g of guesses) {
    const ok = GAMES[game].guessDraft ? typeof g === "string" && /^\d{4}-\d{1,2}$/.test(g)
      : isTeam ? typeof g === "string" && /^[A-Z]{3}$/.test(g) : Number.isInteger(g);
    if (!ok) throw httpError(400, "Invalid guesses");
  }
  if (new Set(guesses).size !== guesses.length) throw httpError(400, "Invalid guesses");

  let correct;
  if (GAMES[game].guessDraft) {
    const d = schedule.players?.[String(answer)]?.draft;
    if (!Array.isArray(d) || d.length < 2) throw httpError(503, "Today's puzzle data is missing");
    correct = `${d[0]}-${d[1]}`;
  } else if (GAMES[game].guessNumber) {
    correct = schedule.players?.[String(answer)]?.number;
    if (!Number.isInteger(correct)) throw httpError(503, "Today's puzzle data is missing");
    if (!guesses.every(g => g >= 0 && g <= 99)) throw httpError(400, "Invalid guesses");
  } else if (GAMES[game].custom === "playoff") {
    correct = answer?.id;
    if (!Number.isInteger(correct)) throw httpError(503, "Today's puzzle data is missing");
  } else if (isTeam) {
    const [pid, year] = answer;
    const rows = seasonsOf(schedule.players?.[String(pid)]).get(year) || [];
    if (rows.length !== 1) throw httpError(503, "Today's puzzle data is missing");
    correct = rows[0][1];
  } else {
    correct = answer;
  }

  const hit = guesses.indexOf(correct);
  if (hit !== -1 && hit !== guesses.length - 1) throw httpError(400, "Invalid guesses");
  const won = hit !== -1;
  if (!won && guesses.length !== max) throw httpError(400, "That game isn't finished yet");
  const tries = guesses.length;
  if (!won) return { won: false, tries, points: 0 };

  let points;
  if (GAMES[game].points) {
    points = GAMES[game].points[tries - 1];
  } else if (game === "classic") {
    points = 11 - tries;                                   // 10 for 1 guess ... 3 for 8 guesses
  } else if (game === "statline") {
    const seasons = seasonsOf(schedule.players?.[String(correct)]).size || 1;
    const unlocked = Math.min(seasons, tries);             // first season + one per wrong guess
    const stillLocked = seasons - unlocked;
    points = (9 - tries) + Math.min(10, 2 * stillLocked);  // up to 8, plus 2 per season never needed (max +10)
  } else {
    points = TEAM_POINTS[tries - 1];                       // 10, 6, 3, 2, 1
  }
  return { won: true, tries, points };
}

// ---------------------------------------------------------------- endpoints
async function setName(body, env) {
  checkIdentity(body);
  const name = String(body.name || "").trim().replace(/\s+/g, " ");
  if (!NAME_RE.test(name)) throw httpError(400, "Names are 3–16 letters, numbers, spaces, _ . or -");
  const LEET = { "0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t", "8": "b", "9": "g", "$": "s", "@": "a" };
  const lower = name.toLowerCase().replace(/[013457890$@]/g, c => LEET[c]).replace(/[\s_.\-]/g, "");
  if (BLOCKED.some(w => lower.includes(w))) throw httpError(400, "Please pick a different name");

  const hash = await sha256(body.secret);
  const existing = await env.DB.prepare("SELECT secret_hash FROM players WHERE uid = ?1").bind(body.uid).first();
  if (existing && existing.secret_hash !== hash) throw httpError(403, "Not allowed");

  const taken = await env.DB.prepare("SELECT 1 FROM players WHERE name_key = ?1 AND uid != ?2")
    .bind(name.toLowerCase(), body.uid).first();
  if (taken) throw httpError(409, "That name is taken");

  const now = new Date().toISOString();
  if (existing) {
    await env.DB.prepare("UPDATE players SET name = ?1, name_key = ?2 WHERE uid = ?3")
      .bind(name, name.toLowerCase(), body.uid).run();
  } else {
    await env.DB.prepare("INSERT INTO players (uid, secret_hash, name, name_key, created) VALUES (?1, ?2, ?3, ?4, ?5)")
      .bind(body.uid, hash, name, name.toLowerCase(), now).run();
  }
  return { ok: true, name };
}

async function saveResult(body, env) {
  await verifyPlayer(env, body);
  const game = body.game;
  if (!GAMES[game]) throw httpError(400, "Unknown game");
  const today = etToday();
  if (body.day !== today && body.day !== shiftDay(today, -1)) throw httpError(400, "Only today's puzzle can be submitted");

  const schedule = await loadSchedule(env);
  const day = schedule[GAMES[game].days]?.[body.day];
  const answer = GAMES[game].stat ? day?.[GAMES[game].stat] : day;
  if (answer === undefined) throw httpError(503, "Today's puzzle isn't on the leaderboard yet");

  const { won, tries, points } = scoreGame(game, answer, body.guesses, schedule);
  const now = new Date().toISOString();
  const res = await env.DB.prepare(
    "INSERT OR IGNORE INTO results (uid, game, day, won, tries, points, created) VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7)"
  ).bind(body.uid, game, body.day, won ? 1 : 0, tries, points, now).run();
  if (res.meta.changes === 0) {
    const saved = await env.DB.prepare("SELECT won, tries, points FROM results WHERE uid = ?1 AND game = ?2 AND day = ?3")
      .bind(body.uid, game, body.day).first();
    return { ok: true, won: !!saved.won, tries: saved.tries, points: saved.points, alreadySaved: true };
  }
  return { ok: true, won, tries, points, alreadySaved: false };
}

async function leaderboard(url, env) {
  const game = url.searchParams.get("game");
  if (!GAMES[game]) throw httpError(400, "Unknown game");
  const period = url.searchParams.get("period") || "today";
  const today = etToday();
  const from = period === "today" ? today : period === "week" ? shiftDay(today, -6) : period === "all" ? "0000-00-00" : null;
  if (!from) throw httpError(400, "Unknown period");
  const uid = url.searchParams.get("uid") || "";

  const base = `WITH t AS (
      SELECT r.uid, p.name, SUM(r.points) AS points, COUNT(*) AS played, SUM(r.won) AS wins,
             MIN(r.tries) AS best, MAX(r.tries) AS top, MIN(r.created) AS first
      FROM results r JOIN players p ON p.uid = r.uid
      WHERE r.game = ?1 AND r.day >= ?2 AND r.day <= ?3
      GROUP BY r.uid)`;
  const top = await env.DB.prepare(`${base}
      SELECT uid, name, points, played, wins, best, top, RANK() OVER (ORDER BY points DESC) AS rank
      FROM t ORDER BY points DESC, first ASC LIMIT 50`).bind(game, from, today).all();
  let you = null;
  if (/^[a-f0-9-]{36}$/.test(uid)) {
    you = await env.DB.prepare(`${base}
        SELECT name, points, played, wins, best,
               (SELECT COUNT(*) FROM t AS o WHERE o.points > t.points) + 1 AS rank,
               (SELECT COUNT(*) FROM t) AS total
        FROM t WHERE uid = ?4`).bind(game, from, today, uid).first();
  }
  const total = await env.DB.prepare(`${base} SELECT COUNT(*) AS n FROM t`).bind(game, from, today).first();
  return {
    game, period, today,
    total: total?.n || 0,
    rows: top.results.map(r => ({ rank: r.rank, name: r.name, points: r.points, played: r.played,
                                  wins: r.wins, best: r.best, top: r.top, me: r.uid === uid })),
    you,
  };
}
