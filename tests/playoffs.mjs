import assert from 'node:assert/strict';
import fs from 'node:fs';
import {PLAYOFF_PICTURE as M} from '../static/playoffs/model.mjs';
const data=JSON.parse(fs.readFileSync('playoffs_cache.json'));
const now=Math.max(Date.now(),Date.parse(data.checked_at));
let count=0;function test(name,fn){fn();console.log('PASS',name);count++;}
test('published forecast validates with all probability conservation checks',()=>assert(M.validate(data,now)));
test('incomplete, corrupt, future-dated or nonfinite feeds are rejected',()=>{
 for(const patch of [{teams:[]},{version:2},{season:20242025},{total_games:1},{simulations:0},{checked_at:new Date(now+600000).toISOString()},{updated_at:'bad'}])assert.equal(M.validate({...data,...patch},now),null);
 for(const mutate of [d=>d.teams[0].odds.cup=101,d=>d.teams[0].odds.playoffs=NaN,d=>d.teams[0].odds.round2=100,d=>d.teams[1].abbr=d.teams[0].abbr,d=>d.teams[0].projected_points=10000,d=>d.teams[0].distribution=[[0,100]],d=>d.teams[0].opponents=[{team:'BAD',chance:100}]]){const copy=structuredClone(data);mutate(copy);assert.equal(M.validate(copy,now),null);}
});
test('simulation extremes are never displayed as mathematical certainty',()=>{
 assert.equal(M.percent(0),'<0.1%');assert.equal(M.percent(100),'>99.9%');assert.equal(M.percent(.001),'<0.1%');assert.equal(M.percent(99.999),'>99.9%');assert.equal(M.percent(72.23),'72.2%');
});
test('model fair odds convert consistently with probabilities',()=>{assert.equal(M.fair(25,'american'),'+300');assert.equal(M.fair(75,'american'),'−300');assert.equal(M.fair(50,'decimal'),'2.00');assert.equal(M.fair(25,'decimal'),'4.00');assert.equal(M.fair(0,'american'),'—');assert.equal(M.fair(100,'decimal'),'—');});
const t=data.teams[0],snapshot={v:1,team:t.abbr,name:t.name,start:data.start,at:data.updated_at,gp:t.gp,points:t.points,projected:t.projected_points,n:data.simulations,odds:t.odds};
test('shared links preserve exactly the original forecast',()=>{const normalized=M.snapshot(snapshot),hash='#playoffs?s='+encodeURIComponent(JSON.stringify(normalized));assert.deepEqual(M.read(hash),normalized);assert.deepEqual(M.read(hash).odds,t.odds);assert.equal(M.read(hash).at,new Date(data.updated_at).toISOString());});
test('malformed and oversized share links cannot replace a forecast',()=>{for(const hash of ['#playoffs?s=bad','#playoffs?s='+encodeURIComponent('{}'),'#playoffs?s='+'a'.repeat(3000),'#projections'])assert.equal(M.read(hash),null);for(const patch of [{team:'BAD'},{gp:1000},{points:-1},{n:0},{name:'X'.repeat(81)},{odds:{...t.odds,playoffs:-1}},{at:'bad'}])assert.equal(M.snapshot({...snapshot,...patch}),null);});
test('history validates all team values and chronological order',()=>{const d=structuredClone(data);d.history[0].teams[t.abbr][0]=200;assert.equal(M.validate(d,now),null);const e=structuredClone(data);e.history.push({...e.history[0],at:'1990-01-01T00:00:00Z'});assert.equal(M.validate(e,now),null);});
test('builder integrates tool routes, source modules and cleanup',()=>{const b=fs.readFileSync('build_sweater.py','utf8');for(const token of ['/*__PLAYOFFS_CSS__*/','<!--__PLAYOFFS_VIEW__-->','/*__PLAYOFFS_MODEL__*/','/*__PLAYOFFS_APP__*/','openPlayoffs(false)','data-open="playoffs"'])assert(b.includes(token));assert.match(b,/function showHub\(push = true\) \{\s+if \(typeof closePlayoffs/);assert.match(b,/function openTeams\(team = "", push = true\) \{\s+if \(typeof closePlayoffs/);});
console.log(`${count} Playoff Picture client checks passed`);
