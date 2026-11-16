export const GAME_PREVIEW=(()=>{
 const number=(n,a,b)=>typeof n==='number'&&Number.isFinite(n)&&n>=a&&n<=b;
 const integer=(n,a,b)=>Number.isInteger(n)&&number(n,a,b);
 const date=s=>typeof s==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(s)&&Number.isFinite(Date.parse(s+'T12:00:00Z'))&&new Date(s+'T12:00:00Z').toISOString().slice(0,10)===s;
 function meeting(g,game){return g&&/^20\d{2}0[23]\d{4}$/.test(String(g.id))&&date(g.date)&&Number.isFinite(Date.parse(g.start))&&[2,3].includes(g.type)&&g.home!==g.away&&[g.home,g.away].every(t=>[game.home,game.away].includes(t))&&['FUT','PRE','LIVE','CRIT','OFF','FINAL'].includes(g.state)&&(!['OFF','FINAL'].includes(g.state)||integer(g.hg,0,30)&&integer(g.ag,0,30)&&g.hg!==g.ag&&['REG','OT','SO'].includes(g.end));}
 function validate(d,g,now=Date.now()){
  if(!d||d.version!==1||d.id!==g.id||d.start!==g.start||d.home!==g.home||d.away!==g.away||!['pregame','reconstructed'].includes(d.basis)||!Number.isFinite(Date.parse(d.as_of))||Date.parse(d.as_of)>now+300000||d.basis==='pregame'&&Date.parse(d.as_of)>=Date.parse(g.start)||d.model!=='sweater-player-shares-v1'||!d.teams)return null;
  for(const club of [g.home,g.away]){
   const t=d.teams[club];if(!t||t.abbr!==club||!['available','partial','unavailable'].includes(t.status))return null;
   if(t.status==='unavailable')continue;
   const source=t.source_game;if(!source||!Number.isInteger(source.id)||source.id===g.id||!date(source.date)||source.date>=g.date||!Number.isFinite(Date.parse(source.start))||Date.parse(source.start)>=Date.parse(g.start)||source.url!==`https://www.nhl.com/gamecenter/${source.id}`||![g.home,g.away].includes(club)||!date(t.stats_through)||t.stats_through>=g.date)return null;
   if(!Array.isArray(t.players)||t.players.length<15||t.players.length>21||!number(t.team_goals,.01,20)||!t.units||!t.special_teams||!['pp','pk'].every(key=>t.special_teams[key]===null||number(t.special_teams[key],0,100)))return null;
   if(t.special_teams.ranks&&(!Object.keys(t.special_teams.ranks).every(k=>['pp','pk'].includes(k))||!Object.values(t.special_teams.ranks).every(r=>integer(r,1,32))))return null;
   const players=new Map();for(const p of t.players){const s=p.stats;if(!integer(p.id,1,99999999)||players.has(p.id)||typeof p.name!=='string'||!p.name.length||p.name.length>100||!['C','L','R','F','D','LW','RW'].includes(p.position)||p.number!==null&&!integer(p.number,1,99)||!number(p.expected_goals,0,20)||!s||!integer(s.gp,0,84)||!integer(s.fo_attempts,0,5000)||![s.sog,s.blocks].every(v=>v===null||number(v,0,25))||s.fo!==null&&!number(s.fo,0,100)||p.availability!==null&&p.availability!==undefined&&(typeof p.availability!=='string'||p.availability.length>50))return null;players.set(p.id,p);}
   if(Math.abs(t.players.reduce((n,p)=>n+p.expected_goals,0)-t.team_goals)>.0001||t.forward_count+t.defense_count!==players.size||t.forward_count!==t.players.filter(p=>p.position!=='D').length)return null;
   const assigned=new Set();for(const [kind,count] of [['f',4],['d',3],['pp',2],['pk',2]]){const units=t.units[kind];if(!Array.isArray(units)||units.length>count)return null;for(let i=0;i<units.length;i++){const unit=units[i],ids=unit.players;if(unit.rank!==i+1||!number(unit.seconds,1,7200)||!Array.isArray(ids)||new Set(ids).size!==ids.length||!ids.every(id=>players.has(id))||kind==='f'&&(ids.length!==3||ids.some(id=>players.get(id).position==='D'))||kind==='d'&&(ids.length!==2||ids.some(id=>players.get(id).position!=='D'))||kind==='pp'&&![4,5].includes(ids.length)||kind==='pk'&&![3,4].includes(ids.length))return null;
     if(['f','d'].includes(kind)){for(const id of ids){if(assigned.has(id))return null;assigned.add(id);}if(unit.expected_goals!==null&&(!number(unit.expected_goals,0,20)||Math.abs(unit.expected_goals-ids.reduce((n,id)=>n+players.get(id).expected_goals,0))>.0002))return null;for(const [id,m] of Object.entries(unit.movement||{}))if(!ids.includes(Number(id))||!integer(m.previous,1,count)||m.current!==unit.rank||m.previous===m.current)return null;}
    }}
   if(!Array.isArray(t.other)||new Set(t.other).size!==t.other.length||!t.other.every(id=>players.has(id)&&!assigned.has(id))||assigned.size+t.other.length!==players.size)return null;
  }
  const h=d.matchups;if(!h||!Number.isFinite(Date.parse(h.checked_at))||Date.parse(h.checked_at)>now+300000||h.source_url!=='https://www.nhl.com/schedule'||!Array.isArray(h.season)||h.season.length>25||!Array.isArray(h.recent)||h.recent.length>10||!h.wins)return null;
  for(const [rows,descending] of [[h.season,false],[h.recent,true]]){const ids=new Set();let previous=descending?Infinity:-Infinity;for(const match of rows){const at=Date.parse(match.start);if(!meeting(match,g)||ids.has(match.id)||descending&&(!['OFF','FINAL'].includes(match.state)||at>previous)||!descending&&at<previous)return null;ids.add(match.id);previous=at;}}
  if(h.season.some(m=>m.season!==Number(String(g.id).slice(0,4))*10000+Number(String(g.id).slice(0,4))+1)||![g.home,g.away].every(club=>h.wins[club]===h.recent.filter(m=>(m.hg>m.ag?m.home:m.away)===club).length))return null;
  return d;
 }
 return Object.freeze({validate});
})();
