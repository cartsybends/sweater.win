import fs from 'node:fs';
import assert from 'node:assert/strict';
import {COMMUNITY_MODEL as M} from '../static/community-games/model.mjs';
import worker,{scoreGame} from '../backend/src/existing-api.mjs';
const data=JSON.parse(fs.readFileSync('static/community-games/data.json','utf8'));
let checks=0;
function test(name,fn){fn();checks++;console.log('PASS',name);}
const schedule={community:data};
test('every Grid has nine candidates per square, accepts alternative answers, and can always complete',()=>{
  for(const target of data.grid){
    const valid=M.candidates(target,data);assert(valid.every(a=>a.length>=9));
    const state=M.grid(target,[],data),solution=M.fillGrid(target,state,data);
    assert.equal(new Set(solution).size,9);
    const log=solution.map((id,i)=>`${i}:${id}`),done=M.grid(target,log,data);
    assert.equal(done.won,true);assert(done.score>=90&&done.score<=135);
    assert.deepEqual(scoreGame('grid',{id:target.id},log,schedule),{won:true,tries:9,points:done.score});
    const alternate=valid[0].find(id=>id!==solution[0]);assert(alternate);
    const partial=M.grid(target,[`0:${alternate}`],data),rest=M.fillGrid(target,partial,data);
    assert.equal(rest[0],alternate);assert.equal(new Set(rest).size,9);
  }
});
test('Grid rejects duplicate players, repeated attempts, filled squares and unfinished leaderboard submissions',()=>{
  const t=data.grid[0],solution=M.fillGrid(t,M.grid(t,[],data),data),valid=M.candidates(t,data);
  assert.throws(()=>M.grid(t,[`0:${solution[0]}`,`1:${solution[0]}`],data));
  assert.throws(()=>M.grid(t,[`0:${solution[0]}`,`0:${solution[1]}`],data));
  const wrong=data.players.find(p=>!valid[0].includes(p[0]))[0];
  assert.equal(M.grid(t,[`0:${wrong}`],data).score,0);
  assert.throws(()=>M.grid(t,[`0:${wrong}`,`0:${wrong}`],data));
  assert.throws(()=>scoreGame('grid',{id:t.id},[`0:${solution[0]}`],schedule),e=>e.status===400);
  const exhausted=data.players.filter(p=>!valid[0].includes(p[0])).slice(0,12).map(p=>`0:${p[0]}`);
  assert.equal(M.grid(t,exhausted,data).over,true);assert.equal(M.grid(t,exhausted,data).won,false);
  const ended=M.result('grid',t,[`0:${solution[0]}`,'END'],data);assert.equal(ended.won,false);assert(ended.points>=10);
});
test('new clues count career Cup wins and complete NHL regular seasons, including trades',()=>{
  const player=id=>M.index(data).players.get(id),cup={kind:'trophy',value:'Stanley Cup'},goals={kind:'season_goals',value:30};
  assert.equal(M.qualifies(player(8478403),cup),true,'Eichel qualifies with Buffalo after winning in Vegas');
  assert.equal(M.qualifies(player(8466141),cup),false,'Luongo did not win as a player');
  assert.equal(M.qualifies(player(8466138),cup),false,'Thornton was a finalist, not a winner');
  assert.equal(M.qualifies(player(8470622),goals),true,'Eaves scored 32 across two teams');
  assert.equal(M.qualifies(player(8466141),goals),false,'Goalie career GP cannot become goals');
  const t=data.grid.find(t=>t.cols.some(c=>c.kind==='season_goals'));
  const valid=M.candidates(t,data),solution=M.fillGrid(t,M.grid(t,[],data),data);
  const col=t.cols.findIndex(c=>c.kind==='season_goals'),wrong=data.players.find(p=>p[8][t.rows[0]]&&!valid[col].includes(p[0]))[0];
  const log=[`${col}:${wrong}`,...solution.map((id,i)=>`${i}:${id}`)];
  assert.equal(M.grid(t,log,data).last.correct,true);
  assert.equal(M.grid(t,log,data).tried.size,10);
  assert.deepEqual(scoreGame('grid',{id:t.id},log,schedule),M.result('grid',t,log,data));
});
test('all Bench Boss best lineups use season positions, six unique players, and at most 100 credits',()=>{
  for(const t of data.benchboss){
    const draft=M.draft(t,t.optimal,data);assert.equal(draft.complete,true);assert(draft.cost<=100);
    assert.deepEqual(draft.counts,{F:3,D:2,G:1});assert.equal(draft.points,t.par);
    const action='LOCK:'+t.optimal.join(','),state=M.boss(t,[action],data);
    assert.equal(state.score,10);assert.equal(state.perfect,true);assert.equal(state.won,true);
    assert.deepEqual(scoreGame('benchboss',{id:t.id},[action],schedule),{won:true,tries:1,points:10});
  }
});
test('Bench Boss rejects over-budget, repeated, foreign, incomplete and incorrectly positioned lineups',()=>{
  const t=data.benchboss[0];
  assert.throws(()=>M.boss(t,['LOCK:'+t.optimal.slice(1).join(',')],data));
  assert.throws(()=>M.boss(t,['LOCK:'+Array(6).fill(t.optimal[0]).join(',')],data));
  const forwards=t.cards.filter(c=>M.group(c[8])==='F').slice(0,6).map(c=>c[0]);
  assert.throws(()=>M.boss(t,['LOCK:'+forwards.join(',')],data));
  const over=data.benchboss.find(t=>{const picks=['F','D','G'].flatMap((g,i)=>t.cards.filter(c=>M.group(c[8])===g).sort((a,b)=>b[1]-a[1]).slice(0,[3,2,1][i]));return picks.reduce((n,c)=>n+c[1],0)>100;});
  assert(over);const ids=['F','D','G'].flatMap((g,i)=>over.cards.filter(c=>M.group(c[8])===g).sort((a,b)=>b[1]-a[1]).slice(0,[3,2,1][i]).map(c=>c[0]));
  assert.throws(()=>M.draft(over,ids,data));assert.deepEqual(M.result('benchboss',t,['END'],data),{won:false,tries:1,points:0});
});
test('all Teammate Trails have verified shortest routes and matching server scores',()=>{
  for(const t of data.teammatetrail){
    const log=[];
    for(const [i,q] of t.rounds.entries()){
      assert.equal(M.shortest(data,q.start,q.end).length,q.solution.length);
      for(let k=1;k<q.solution.length-1;k++)log.push('ADD:'+q.solution[k]);
      const r=M.trail(t,log,data).rounds[i];assert.equal(r.points,10);assert.equal(r.won,true);
      if(i<2)log.push('NEXT');
    }
    assert.deepEqual(M.result('teammatetrail',t,log,data),{won:true,tries:log.length,points:30});
    assert.deepEqual(scoreGame('teammatetrail',{id:t.id},log,schedule),{won:true,tries:log.length,points:30});
  }
});
test('Trail hints/Undo cap scores, reveals score zero, and invalid links cannot enter the history',()=>{
  const t=data.teammatetrail[0],q=t.rounds[0];
  const hinted=M.trail(t,['HINT'],data).rounds[0];assert.equal(hinted.points,6);assert.equal(hinted.done,true);
  assert.throws(()=>M.trail(t,['NEXT'],data));assert.throws(()=>M.trail(t,['ADD:'+q.start],data));
  const disconnected=data.players.find(p=>!M.link(data,q.start,p[0]))[0];assert.throws(()=>M.trail(t,['ADD:'+disconnected],data));
  const neighbor=M.teammates(data,q.start).find(id=>id!==q.end&&!M.link(data,id,q.end));
  assert(neighbor);const log=['ADD:'+neighbor,'UNDO','ADD:'+q.solution[1]];
  assert.equal(M.trail(t,log,data).rounds[0].points,6);
  assert.deepEqual(M.result('teammatetrail',t,['REVEAL','NEXT','REVEAL','NEXT','REVEAL'],data),{won:false,tries:5,points:0});
  assert.throws(()=>scoreGame('teammatetrail',{id:t.id},['ADD:'+neighbor],schedule),e=>e.status===400);
});
test('missing authoritative puzzle IDs fail closed and clients cannot supply invented scores',()=>{
  assert.throws(()=>scoreGame('grid',{id:'not-published'},['END'],schedule),e=>e.status===503);
  assert.throws(()=>M.result('grid',data.grid[0],[{score:135}],data));
  assert.throws(()=>M.result('teammatetrail',data.teammatetrail[0],Array(101).fill('UNDO'),data));
});
// Exercise the actual HTTP route with an isolated database and schedule fetch.
// Invented client points are ignored, invalid runs never write a result, and
// retries preserve the original daily result.
const uid=crypto.randomUUID(),secret='a'.repeat(64),rows=new Map();
const secretHash=Buffer.from(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(secret))).toString('hex');
const env={SCHEDULE_URL:'https://puzzles.example.test/schedule.json',DB:{prepare(sql){return {bind(...args){return {
  async first(){if(sql.includes('secret_hash'))return args[0]===uid?{secret_hash:secretHash}:null;return rows.get(args.slice(0,3).join(':'))||null;},
  async run(){const [who,game,day,won,tries,points]=args,key=[who,game,day].join(':');if(rows.has(key))return {meta:{changes:0}};rows.set(key,{won,tries,points});return {meta:{changes:1}};},
};}};}}};
const day=new Intl.DateTimeFormat('en-CA',{timeZone:'America/New_York',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
const oldFetch=globalThis.fetch;
try{
  const published={community:data,...Object.fromEntries(['grid','benchboss','teammatetrail'].map(id=>[id+'_days',{[day]:{id:data[id][0].id}}]))};
  globalThis.fetch=async url=>{assert.equal(url,env.SCHEDULE_URL);return new Response(JSON.stringify(published));};
  const request=(game,guesses)=>worker.fetch(new Request('https://api.example.test/api/result',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({uid,secret,game,day,guesses,points:99999,won:true})}),env);
  let response=await request('grid',[]);assert.equal(response.status,400);assert.equal(rows.size,0);
  const logs={grid:M.fillGrid(data.grid[0],M.grid(data.grid[0],[],data),data).map((id,i)=>`${i}:${id}`),benchboss:['LOCK:'+data.benchboss[0].optimal.join(',')],teammatetrail:['REVEAL','NEXT','REVEAL','NEXT','REVEAL']};
  for(const game of Object.keys(logs)){
    response=await request(game,logs[game]);assert.equal(response.status,200);const body=await response.json();
    assert.equal(body.points,M.result(game,data[game][0],logs[game],data).points);assert.equal(body.alreadySaved,false);
    response=await request(game,logs[game]);assert.equal((await response.json()).alreadySaved,true);
  }
  assert.equal(rows.size,3);checks++;console.log('PASS HTTP daily submission validates all three games, ignores forged scores, and deduplicates retries');
}finally{globalThis.fetch=oldFetch;}
console.log(`${checks} community game checks passed.`);
