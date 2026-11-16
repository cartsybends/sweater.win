import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {PLAYOFF_FIELD as model} from '../static/playoffs/field-model.mjs';
const feed=JSON.parse(await readFile(new URL('../playoffs_cache.json',import.meta.url))),teams=feed.teams;
let checks=0;const test=(name,fn)=>{fn();checks++;console.log('PASS '+name);};
test('The published standings yield exactly sixteen clubs in eight disjoint first-round pairings',()=>{
 const field=model.field(teams);assert(field);assert.equal(field.qualifiers.length,16);assert.equal(field.matches.length,8);
 const ids=field.matches.flatMap(m=>m.teams.map(t=>t.abbr));assert.equal(new Set(ids).size,16);assert.deepEqual(new Set(ids),new Set(field.qualifiers));
 for(const conference of ['E','W'])assert.equal(field.matches.filter(m=>m.conference===conference).length,4);
});
test('Qualification follows actual standings regardless of model odds or projected points',()=>{
 const old=model.field(teams),changed=model.field(teams.map(t=>({...t,odds:{playoffs:100-t.odds.playoffs},projected_points:0})));
 assert.deepEqual(changed,old);
});
const synthetic=()=>{
 const grouped=['E','W'].flatMap(conference=>teams.filter(t=>t.conference===conference).sort((a,b)=>a.division.localeCompare(b.division)||a.abbr.localeCompare(b.abbr)));
 return grouped.map((t,i)=>({...t,official_rank:i+1,conference_rank:undefined,division_rank:undefined,wildcard_rank:undefined,points:100-i}));
};
test('Each division gets three places; both wild cards can come from the same division',()=>{
 const data=synthetic(),field=model.field(data);
 for(const c of ['E','W']){
  const members=data.filter(t=>t.conference===c),strong=members.slice(0,8),weak=members.slice(8);
  assert.deepEqual(field.qualifiers.filter(t=>strong.some(x=>x.abbr===t)),strong.slice(0,5).map(t=>t.abbr));
  assert.deepEqual(field.qualifiers.filter(t=>weak.some(x=>x.abbr===t)),weak.slice(0,3).map(t=>t.abbr));
  const matches=field.matches.filter(m=>m.conference===c);
  assert.deepEqual(matches[0].teams.map(t=>t.abbr),[strong[0].abbr,strong[4].abbr]);
  assert.deepEqual(matches[2].teams.map(t=>t.abbr),[weak[0].abbr,strong[3].abbr]);
 }
});
test('Conference and division sequences take precedence when supplied by the NHL',()=>{
 const data=synthetic();for(const c of ['E','W']){const members=data.filter(t=>t.conference===c);members.forEach((t,i)=>{t.conference_rank=16-i;t.division_rank=8-i%8;});}
 const field=model.field(data);for(const c of ['E','W']){const last=data.filter(t=>t.conference===c).at(-1);assert.equal(field.matches.find(m=>m.conference===c).teams[0].abbr,last.abbr);}
});
test('Malformed seed metadata cannot create an invented bracket',()=>{
 assert.equal(model.field(teams.slice(1)),null);const duplicate=structuredClone(teams);duplicate[1].official_rank=duplicate[0].official_rank;assert.equal(model.field(duplicate),null);
 const wrong=structuredClone(teams);wrong[0].division='Unknown';assert.equal(model.field(wrong),null);
});
test('Official wild-card sequences resolve the remaining field independently of league order',()=>{
 const data=synthetic();for(const c of ['E','W']){const members=data.filter(t=>t.conference===c),automatic=new Set([0,1,2,8,9,10].map(i=>members[i].abbr));members.filter(t=>!automatic.has(t.abbr)).forEach((t,i)=>t.wildcard_rank=10-i);}
 const field=model.field(data);for(const c of ['E','W']){const members=data.filter(t=>t.conference===c),last=members.at(-1);assert.equal(field.seeds[last.abbr],'WC1');}
});
test('Clinch badges use NHL indicators and never infer a clinch from simulated certainty',()=>{
 for(const code of ['x','y','z','p'])assert.equal(model.clinched({clinch:code}).code,code);
 for(const clinch of ['',null,'e','<script>','pending'])assert.equal(model.clinched({clinch,odds:{playoffs:100}}),null);
});
test('The radial bracket puts all sixteen logos outside its team ring without collisions',()=>{
 const layout=model.geometry(model.field(teams).matches),logos=layout.flatMap(m=>m.teams);
 assert.equal(logos.length,16);assert(Math.abs(layout.at(-1).end-layout[0].start-Math.PI*2)<1e-8);
 for(const p of logos){assert(Math.hypot(p.x-450,p.y-450)>360);for(const q of logos)if(p!==q)assert(Math.hypot(p.x-q.x,p.y-q.y)>100);}
});
console.log(checks+' standings-field checks passed');
