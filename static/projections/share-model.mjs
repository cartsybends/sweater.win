// A shared projection carries its stat line, so tomorrow's NHL update cannot change it.
export function createProjectionSharing(model) {
 const clubs=new Set('ANA BOS BUF CAR CBJ CGY CHI COL DAL DET EDM FLA LAK MIN MTL NJD NSH NYI NYR OTT PHI PIT SEA SJS STL TBL TOR UTA VAN VGK WPG WSH'.split(' '));
 function normalize(raw) {
  if(!raw||raw.v!==1||!['players','manual'].includes(raw.mode)||!raw.player)return null;
  const p=raw.player,manual=raw.mode==='manual';
  if(!manual&&(!Number.isInteger(p.id)||p.id<1000000||p.id>9999999||typeof p.name!=='string'||!p.name.trim()||p.name.length>80||/[\x00-\x1f]/.test(p.name)||!['C','L','R','D'].includes(p.pos)||p.team!==null&&!clubs.has(p.team)))return null;
  if(!Number.isInteger(raw.start)||raw.start<2000||raw.start>2200||!Number.isInteger(raw.rate)||raw.rate<50||raw.rate>150)return null;
  if(raw.asof!==null&&(typeof raw.asof!=='string'||!/^\d{4}-\d{2}-\d{2}$/.test(raw.asof)||!Number.isFinite(Date.parse(raw.asof))||new Date(raw.asof).toISOString().slice(0,10)!==raw.asof))return null;
  const r=model.calculate({...p,seasonGames:raw.seasonGames,rate:raw.rate,missed:raw.missed});
  if(!r.valid)return null;
  return {v:1,mode:raw.mode,start:raw.start,asof:raw.asof,seasonGames:r.seasonGames,rate:r.rate,missed:r.missed,player:{id:manual?null:p.id,name:manual?'Your stat line':p.name.trim(),pos:manual?null:p.pos,team:manual?null:p.team,gp:r.gp,goals:r.goals,assists:r.assists,points:r.points,teamGP:r.teamGP}};
 }
 function hash(raw){const data=normalize(raw);return data?'#projections?s='+encodeURIComponent(JSON.stringify(data)):null;}
 function read(fragment){
  if(typeof fragment!=='string'||fragment.length>4000||!fragment.startsWith('#projections?'))return null;
  try{return normalize(JSON.parse(new URLSearchParams(fragment.slice(fragment.indexOf('?')+1)).get('s')));}catch{return null;}
 }
 function filename(data){const p=normalize(data);return p?`${(p.mode==='manual'?'my':p.player.name).normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/^-|-$/g,'')}-${p.seasonGames}-game-projection.png`:'sweater-projection.png';}
 return Object.freeze({normalize,hash,read,filename});
}
