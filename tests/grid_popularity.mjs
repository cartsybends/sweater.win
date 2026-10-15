import assert from 'node:assert/strict';
import fs from 'node:fs';
import {DatabaseSync} from 'node:sqlite';
import {COMMUNITY_MODEL as M} from '../static/community-games/model.mjs';
import {handleGridPopularity,gridVotes,pruneGridPopularity} from '../backend/src/grid-popularity.mjs';
import {scoreGame} from '../backend/src/existing-api.mjs';

class DB{
  constructor(){this.sql=new DatabaseSync(':memory:');}
  prepare(sql){const db=this;return {bind(...args){return db.statement(sql,args);},...this.statement(sql,[])};}
  statement(sql,args){const run=()=>{const s=this.sql.prepare(sql);if(/^\s*(SELECT|WITH)/i.test(sql))return {results:s.all(...args),meta:{changes:0}};return {results:[],meta:{changes:Number(s.run(...args).changes)}};};return {execute:run,run:async()=>run(),all:async()=>run(),first:async()=>run().results[0]||null};}
  async batch(statements){this.sql.exec('BEGIN');try{const rows=statements.map(s=>s.execute());this.sql.exec('COMMIT');return rows;}catch(e){this.sql.exec('ROLLBACK');throw e;}}
}
const data=JSON.parse(fs.readFileSync('static/community-games/data.json')),t=data.grid[0];
const day=new Intl.DateTimeFormat('en-CA',{timeZone:'America/New_York',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
const schedule={community:data,grid_days:{[day]:{id:t.id}}},visitor=crypto.randomUUID();
const guesses=M.fillGrid(t,M.grid(t,[],data),data).map((id,i)=>`${i}:${id}`);
const body={visitor,puzzle:t.id,guesses,variant:'daily',day};
assert.equal(gridVotes(body,schedule).length,9);
assert.equal(gridVotes({...body,guesses:[guesses[0],'END']},schedule).length,1,'Revealed answers never become votes');
assert.throws(()=>gridVotes({...body,guesses:[]},schedule),e=>e.status===400);
assert.throws(()=>gridVotes({...body,guesses:[guesses[0],guesses[0]]},schedule),e=>e.status===400);
assert.throws(()=>gridVotes({...body,puzzle:data.grid[1].id},schedule),e=>e.status===400);
assert.throws(()=>gridVotes({...body,variant:'archive'},schedule),e=>e.status===400);
assert.throws(()=>gridVotes({...body,name:'typed-name'},schedule),e=>e.status===400);
const env={DB:new DB(),SWEATER_ANALYTICS_PASSWORD:'only-a-test-secret-01234567890123456789',SCHEDULE_URL:'https://snapshot.example.test/schedule.json'};
const original=globalThis.fetch;
try{
  globalThis.fetch=async url=>{assert.equal(url,env.SCHEDULE_URL);return new Response(JSON.stringify(schedule));};
  const call=(path,body,origin='https://sweater.win')=>handleGridPopularity(new Request('https://api.example.test/api/grid/'+path,{method:body?'POST':'GET',headers:{Origin:origin,'Content-Type':'application/json','CF-Connecting-IP':'203.0.113.5'},...(body?{body:JSON.stringify(body)}:{})}),env);
  assert.equal((await call('answers',body)).status,200);assert.equal((await call('answers',body)).status,200);
  assert.equal(env.DB.sql.prepare('SELECT COUNT(*) n FROM sweater_grid_answers').get().n,9,'One anonymous vote per intersection despite retries');
  assert.notEqual(env.DB.sql.prepare('SELECT visitor_hash FROM sweater_grid_answers LIMIT 1').get().visitor_hash,visitor,'Raw browser identity is not stored');
  let pop=await (await call('popularity')).json();assert(Object.values(pop.criteria).every(row=>row.total===1));
  assert(M.raritySnapshot(t,pop).every(row=>row===null),'Low-volume samples do not pretend to be reliable rarity');
  assert.equal((await call('answers',{...body,visitor:crypto.randomUUID()})).status,200);
  pop=await (await call('popularity')).json();assert(Object.values(pop.criteria).every(row=>row.total===2));
  assert.equal((await call('answers',body,'https://elsewhere.example')).status,403);
  assert.equal((await call('answers',{...body,guesses:[]})).status,400);
  assert.equal((await call('answers',{...body,visitor:'invalid'})).status,400);
  assert.equal((await call('answers',{...body,guesses:['0:0000000','END']})).status,400);
  for(let i=0;i<28;i++)await call('answers',body);
  assert.equal((await call('answers',body)).status,429,'Repeated anonymous submissions are rate limited');
  const disabled=await handleGridPopularity(new Request('https://api.example.test/api/grid/popularity'),{});assert.deepEqual(await disabled.json(),{collecting:false,criteria:{}});
  env.DB.sql.prepare('UPDATE sweater_grid_answers SET received_at=?').run(Date.now()-366*86400000);await pruneGridPopularity(env);assert.equal(env.DB.sql.prepare('SELECT COUNT(*) n FROM sweater_grid_answers').get().n,0);
}finally{globalThis.fetch=original;}

const common=Number(guesses[0].split(':')[1]),other=M.candidates(t,data)[0].find(id=>id!==common);
const pop={criteria:{[M.criterion(t,0)]:{total:100,counts:{[common]:99,[other]:1}}}};
const frozen={...t,rarity:M.raritySnapshot(t,pop)};
assert.equal(M.bonus(frozen,0,M.index(data).players.get(common)),0);
assert.equal(M.bonus(frozen,0,M.index(data).players.get(other)),5);
assert.equal(M.bonus(t,0,M.index(data).players.get(common)),M.bonus({...t,rarity:Array(9).fill(null)},0,M.index(data).players.get(common)),'Old boards retain original short-stint scoring');
const result=M.result('grid',frozen,guesses,data);
assert.deepEqual(scoreGame('grid',{id:t.id,rarity:frozen.rarity},guesses,{community:data}),result,'Authoritative snapshot determines server scoring');
pop.criteria[M.criterion(t,0)].counts[common]=1;assert.equal(frozen.rarity[0].counts[common],99,'Live votes cannot change an in-progress snapshot');
assert(M.raritySnapshot(t,{criteria:{[M.criterion(t,0)]:{total:100,counts:{[common]:101}}}}).every(row=>row===null));
console.log('Grid popularity: real SQLite, replay validation, anonymous deduplication, origin/rate controls, retention, 100-answer threshold, frozen rarity, and server parity passed.');
