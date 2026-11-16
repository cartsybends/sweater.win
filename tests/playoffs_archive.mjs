import assert from 'node:assert/strict';
import fs from 'node:fs';
import {createHash} from 'node:crypto';
import {PLAYOFF_PICTURE as M} from '../static/playoffs/model.mjs';
const root='playoffs_archive/',raw=JSON.parse(fs.readFileSync(root+'index.json')),now=Date.now();
const index=M.archiveIndex(raw,now);assert(index);assert(index.days.length);
for(const entry of index.days){const bytes=fs.readFileSync(root+entry.date+'.json'),saved=JSON.parse(bytes);assert.equal(createHash('sha256').update(bytes).digest('hex'),entry.sha256);assert(M.archived(saved,entry,now));assert.equal(M.localDay(saved.checked_at,M.archiveZone),entry.date);for(const stage of M.stages){const slices=M.circle(saved.teams,stage[0]);assert(Math.abs(slices.reduce((n,s)=>n+s.share,0)-100)<1e-8);}for(const patch of [{date:'2025-01-01'},{season:20252026},{checked_at:'2026-01-01T00:00:00Z'}])assert.equal(M.archived(saved,{...entry,...patch},now),null);}
for(const mutate of [d=>d.days.reverse(),d=>d.days.push(d.days[0]),d=>d.days[0].date='../wrong',d=>d.days[0].date='2026-02-30',d=>d.days[0].sha256='bad',d=>d.days[0].checked_at='2099-01-01T00:00:00Z',d=>d.time_zone='UTC']){const copy=structuredClone(raw);mutate(copy);assert.equal(M.archiveIndex(copy,now),null);}
const entry=index.days[0],saved=JSON.parse(fs.readFileSync(root+entry.date+'.json'));for(const mutate of [d=>d.archive.date='2026-01-01',d=>d.archive.kind='reconstructed',d=>d.teams[0].odds.cup=101,d=>d.teams[1].abbr=d.teams[0].abbr]){const copy=structuredClone(saved);mutate(copy);assert.equal(M.archived(copy,entry,now),null);}
console.log('PASS archived dates, exact hashes, all five circle stages, source identity, corrupt snapshots and unsafe/out-of-order index rejection');
