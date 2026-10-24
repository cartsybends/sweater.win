// Run from the repository root: node tests/who_scored_leaderboard.mjs
import assert from 'node:assert/strict';
import fs from 'node:fs';
import worker, {scoreGame} from '../backend/src/existing-api.mjs';
import {AnalyticsDB} from './helpers/analytics_runtime.mjs';

const clips=JSON.parse(fs.readFileSync('static/who-scored/clips.json'));
const answer=clips[0].pid, yesterdayAnswer=clips[1].pid;
const misses=clips.map(c=>c.pid).filter(id=>id!==answer).slice(0,6);
const points=[10,8,6,4,2,1];
for(let tries=1;tries<=6;tries++){
  assert.deepEqual(scoreGame('whoscored',answer,[...misses.slice(0,tries-1),answer],{}),{won:true,tries,points:points[tries-1]});
}
assert.deepEqual(scoreGame('whoscored',answer,misses,{}),{won:false,tries:6,points:0});
for(const guesses of [[],[misses[0]],[answer,misses[0]],[misses[0],misses[0]],
  [...misses,answer],[String(answer)],[null],null]){
  assert.throws(()=>scoreGame('whoscored',answer,guesses,{}),error=>error.status===400);
}

const today=new Intl.DateTimeFormat('en-CA',{timeZone:'America/New_York',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
const shift=n=>new Date(Date.parse(today+'T12:00:00Z')+n*86400000).toISOString().slice(0,10);
const env={DB:new AnalyticsDB(),SCHEDULE_URL:'https://puzzles.example.test/schedule.json'};
env.DB.sql.exec(`
  CREATE TABLE players (uid TEXT PRIMARY KEY, secret_hash TEXT, name TEXT, name_key TEXT UNIQUE, created TEXT);
  CREATE TABLE results (uid TEXT, game TEXT, day TEXT, won INTEGER, tries INTEGER, points INTEGER, created TEXT,
    PRIMARY KEY (uid, game, day));
`);
const people=['First player','Second player','Third player'].map(name=>({uid:crypto.randomUUID(),secret:'a'.repeat(64),name}));
const call=(path,body)=>worker.fetch(new Request('https://api.example.test'+path,{
  method:body===undefined?'GET':'POST',headers:{'Content-Type':'application/json'},
  ...(body===undefined?{}:{body:JSON.stringify(body)})
}),env);
const result=(person,guesses,day=today,extra={})=>call('/api/result',{...person,game:'whoscored',day,guesses,...extra});
const originalFetch=globalThis.fetch;
try{
  globalThis.fetch=async url=>{
    assert.equal(url,env.SCHEDULE_URL);
    return new Response(JSON.stringify({whoscored_days:{[today]:answer,[shift(-1)]:yesterdayAnswer}}));
  };
  assert.equal((await result(people[0],[answer])).status,403,'A leaderboard name is required');
  for(const person of people)assert.equal((await call('/api/name',person)).status,200);
  assert.equal((await result({...people[0],secret:'b'.repeat(64)},[answer])).status,403);
  assert.equal((await result(people[0],[misses[0]])).status,400,'Unfinished rounds cannot be saved');
  assert.equal((await result(people[0],[answer,misses[0]])).status,400);
  assert.equal((await result(people[0],[answer],shift(-2))).status,400,'Older dates cannot be submitted');
  let response=await result(people[0],[...misses.slice(0,2),answer],today,{points:99999,won:false});
  assert.equal(response.status,200);
  assert.deepEqual(await response.json(),{ok:true,won:true,tries:3,points:6,alreadySaved:false},'The server computes points from the published scorer');
  response=await result(people[0],[answer]);
  assert.deepEqual(await response.json(),{ok:true,won:true,tries:3,points:6,alreadySaved:true},'Retries preserve the first completed result');
  assert.equal((await result(people[1],[answer])).status,200);
  response=await result(people[2],misses,today,{points:99999,won:true});
  assert.deepEqual(await response.json(),{ok:true,won:false,tries:6,points:0,alreadySaved:false});
  response=await result(people[0],[answer,yesterdayAnswer],shift(-1));
  assert.deepEqual(await response.json(),{ok:true,won:true,tries:2,points:8,alreadySaved:false},'Yesterday uses its own scheduled scorer');

  const insert=env.DB.sql.prepare('INSERT INTO results VALUES (?,?,?,?,?,?,?)');
  insert.run(people[0].uid,'whoscored',shift(-7),1,1,10,new Date().toISOString());
  insert.run(people[0].uid,'classic',today,1,1,10,new Date().toISOString());
  for(const [period,totalPoints,rank] of [['today',6,2],['week',14,1],['all',24,1]]){
    response=await call(`/api/leaderboard?game=whoscored&period=${period}&uid=${people[0].uid}`);
    assert.equal(response.status,200);
    const board=await response.json();
    assert.equal(board.total,3);assert.equal(board.you.points,totalPoints);assert.equal(board.you.rank,rank);
    assert.equal(board.rows.find(row=>row.me).name,people[0].name);
    assert.equal(board.rows.find(row=>row.name===people[2].name).points,0,'Losses appear on the board');
    if(period==='today'){
      assert.equal(board.rows[0].name,people[1].name);assert.equal(board.rows[0].best,1);
      assert.equal(board.rows.find(row=>row.me).best,3);
    }
  }
  response=await call('/api/leaderboard?game=whoscored&period=today');
  const anonymous=await response.json();assert.equal(anonymous.you,null);assert(anonymous.rows.every(row=>!row.me));
  assert.equal((await call('/api/leaderboard?game=whoscored&period=invalid')).status,400);
  assert.equal(env.DB.sql.prepare("SELECT COUNT(*) AS n FROM results WHERE game='whoscored' AND day=?").get(today).n,3);
}finally{globalThis.fetch=originalFetch;env.DB.sql.close();}
console.log('Who Scored? leaderboard: all six scores, validation, authenticated results, published daily answers, losses, immutable retries, Today/Week/All time ranking and game isolation passed.');
