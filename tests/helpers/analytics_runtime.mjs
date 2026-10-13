import {DatabaseSync} from 'node:sqlite';
import assert from 'node:assert/strict';
export class AnalyticsDB {
  constructor(){this.sql=new DatabaseSync(':memory:');this.queries=0;this.maxBindings=0;}
  prepare(query){return {bind:(...values)=>this.statement(query,values),...this.statement(query,[])};}
  statement(query,values){const db=this;db.maxBindings=Math.max(db.maxBindings,values.length);assert(values.length<=100,'D1 parameter budget');const execute=all=>{db.queries++;let sql=query,args=values;if(/\?\d/.test(sql)){args=[];sql=sql.replace(/\?(\d+)/g,(_,n)=>{args.push(values[Number(n)-1]);return '?';});}const s=db.sql.prepare(sql);if(all||/^\s*(SELECT|WITH)/i.test(sql))return {results:s.all(...args),meta:{changes:0},success:true};const r=s.run(...args);return {results:[],meta:{changes:Number(r.changes)},success:true};};return {run:async()=>execute(false),all:async()=>execute(true),first:async()=>execute(true).results[0]||null,execute};}
  async batch(statements){this.sql.exec('BEGIN');try{const out=statements.map(s=>s.execute(false));this.sql.exec('COMMIT');return out;}catch(e){this.sql.exec('ROLLBACK');throw e;}}
}
