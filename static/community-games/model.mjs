// Pure rules shared by the browser, leaderboard worker, and regression tests.
export const COMMUNITY_MODEL = (() => {
  const cache = new WeakMap();
  const group = pos => pos === 'G' ? 'G' : pos === 'D' ? 'D' : 'F';
  function index(data) {
    if (cache.has(data)) return cache.get(data);
    const cups = new Set(data.cup_winners||[]);
    const players = new Map(data.players.map(r => [r[0], {id:r[0],name:r[1],pos:r[2],nation:r[3],gp:r[4],hall:r[5],first:r[6],last:r[7],teams:r[8],birthYear:r[9],awards:data.awards?.[r[0]]||[],cup:cups.has(r[0]),seasonGoals:data.season_goals?.[r[0]]||0} ]));
    const result = {players,links:null,neighbors:null,grids:new WeakMap()}; cache.set(data,result); return result;
  }
  function graph(data) {
    const result=index(data);if(result.links)return result;
    const links = new Map(), neighbors = new Map();
    for (const row of data.links) {
      const [a,b,team,year,ga,gb] = row;
      links.set([a,b].sort((x,y)=>x-y).join(':'), {team,year,ga,gb});
      for (const [from,to] of [[a,b],[b,a]]) {if(!neighbors.has(from))neighbors.set(from,new Set());neighbors.get(from).add(to);}
    }
    result.links=links;result.neighbors=neighbors;return result;
  }
  function qualifies(p, clue) {
    if(clue.kind==='team')return (p.teams[clue.value]||0)>0;
    if(clue.kind==='country')return p.nation===clue.value;
    if(clue.kind==='position')return group(p.pos)===clue.value;
    if(clue.kind==='games')return p.gp>=clue.value;
    if(clue.kind==='hall')return p.hall;
    if(clue.kind==='trophy')return clue.value==='Stanley Cup'?p.cup:p.awards.includes(clue.value);
    if(clue.kind==='season_goals')return p.seasonGoals>=clue.value;
    return false;
  }
  function candidates(target,data) {
    const idx=index(data);
    if(!idx.grids.has(target))idx.grids.set(target,target.rows.flatMap(team=>target.cols.map(clue=>[...idx.players.values()].filter(p=>p.teams[team]>0&&qualifies(p,clue)).map(p=>p.id))));
    return idx.grids.get(target);
  }
  function criterion(target,cell){const team=target.rows[Math.floor(cell/3)],clue=target.cols[cell%3];return clue.kind==='team'?'teams:'+ [team,clue.value].sort().join(':'):`${team}:${clue.kind}:${clue.value}`;}
  function raritySnapshot(target,popularity){return Array.from({length:9},(_,cell)=>{const row=popularity?.criteria?.[criterion(target,cell)];if(!row||!Number.isInteger(row.total)||row.total<100||!row.counts)return null;const counts=Object.fromEntries(Object.entries(row.counts).filter(([id,n])=>/^\d{7}$/.test(id)&&Number.isInteger(n)&&n>0&&n<=row.total));if(Object.values(counts).reduce((n,c)=>n+c,0)!==row.total)return null;return {total:row.total,counts};});}
  function bonus(target,cell,p) {
    const rarity=target.rarity?.[cell];if(rarity&&rarity.total>=100){const n=rarity.counts[p.id]||0,total=rarity.total;return n*100<=total?5:n*20<=total?3:n*10<=total?2:n*5<total?1:0;}
    const clue=target.cols[cell%3],gp=p.teams[target.rows[Math.floor(cell/3)]]+(clue.kind==='team'?p.teams[clue.value]:0);
    return gp<=100?5:gp<=250?3:0;
  }
  function grid(target,guesses,data) {
    const idx=index(data),valid=candidates(target,data),state={cells:Array(9).fill(null),used:new Set(),tried:new Set(),over:false,won:false,score:0,last:null};
    for(const action of guesses){
      if(state.over)throw Error('This grid has already finished');
      if(action==='END'){state.over=true;continue;}
      const match=typeof action==='string'&&action.match(/^([0-8]):(\d{7})$/);
      if(!match)throw Error('Choose a player for an open square');
      const cell=Number(match[1]),id=Number(match[2]);
      if(!idx.players.has(id)||state.cells[cell]!==null||state.used.has(id)||state.tried.has(action))throw Error('That player or square has already been used');
      state.tried.add(action);
      const correct=valid[cell].includes(id);state.last={cell,id,correct};
      if(correct){state.cells[cell]=id;state.used.add(id);state.score+=10+bonus(target,cell,idx.players.get(id));}
      state.won=state.cells.every(id=>id!==null);state.over=state.won||state.tried.size>=12;
    }
    return state;
  }
  function fillGrid(target,state,data){
    const cells=state.cells.slice(),used=new Set(state.used),valid=candidates(target,data);
    function fill(cell){if(cell===9)return true;if(cells[cell]!==null)return fill(cell+1);for(const id of valid[cell]){if(used.has(id))continue;cells[cell]=id;used.add(id);if(fill(cell+1))return true;used.delete(id);cells[cell]=null;}return false;}
    if(!fill(0))throw Error('The grid has no complete answer');return cells;
  }
  function draft(target,ids,data){
    const idx=index(data),cards=new Map(target.cards.map(c=>[c[0],c])),counts={F:0,D:0,G:0};let cost=0,points=0;
    if(!Array.isArray(ids)||new Set(ids).size!==ids.length)throw Error('Use each player once');
    for(const id of ids){const card=cards.get(id),p=idx.players.get(id);if(!card||!p)throw Error('Choose players from this market');counts[group(card[8])]++;cost+=card[1];points+=card[2];}
    if(counts.F>3||counts.D>2||counts.G>1)throw Error('Fill three forward, two defense, and one goalie slot');
    if(cost>target.budget)throw Error('That lineup is over the draft budget');
    return {cost,points,counts,complete:ids.length===6};
  }
  function boss(target,guesses,data){
    if(!guesses.length)return {over:false,won:false,score:0,ids:[],points:0};
    if(guesses.length!==1)throw Error('Submit one completed lineup');
    const action=guesses[0];if(action==='END')return {over:true,won:false,score:0,ids:[],points:0};
    if(typeof action!=='string'||!/^LOCK:\d{7}(,\d{7}){5}$/.test(action))throw Error('Fill all six lineup slots');
    const ids=action.slice(5).split(',').map(Number),result=draft(target,ids,data);
    if(!result.complete)throw Error('Fill all six lineup slots');
    return {over:true,won:result.points>=target.par*.9,score:Math.min(10,Math.round(result.points/target.par*10)),ids,points:result.points,cost:result.cost,perfect:result.points===target.par};
  }
  function link(data,a,b){return graph(data).links.get([a,b].sort((x,y)=>x-y).join(':'))||null;}
  function teammates(data,id){return [...(graph(data).neighbors.get(id)||[])];}
  function shortest(data,start,end,blocked=[]){
    const adj=graph(data).neighbors,seen=new Set(blocked.filter(id=>id!==start&&id!==end)),queue=[[start]];seen.add(start);
    for(let i=0;i<queue.length;i++){const path=queue[i];if(path.at(-1)===end)return path;for(const id of adj.get(path.at(-1))||[])if(!seen.has(id)){seen.add(id);queue.push([...path,id]);}}return null;
  }
  function trail(target,guesses,data){
    const rounds=target.rounds.map(q=>({path:[q.start],done:false,won:false,points:0,hinted:false,undos:0}));let current=0;
    function complete(){const r=rounds[current],q=target.rounds[current];if(link(data,r.path.at(-1),q.end)){r.path.push(q.end);r.done=r.won=true;r.points=!r.hinted&&!r.undos&&r.path.length===q.solution.length?10:6;}}
    for(const action of guesses){
      const r=rounds[current],q=target.rounds[current];
      if(current===rounds.length-1&&r.done)throw Error('This run has already finished');
      if(action==='END'){for(let i=current;i<rounds.length;i++)rounds[i].done=true;current=rounds.length-1;continue;}
      if(action==='NEXT'){if(!r.done||current>=rounds.length-1)throw Error('Finish this trail first');current++;continue;}
      if(r.done)throw Error('This trail has already finished');
      if(action==='REVEAL'){r.done=true;continue;}
      if(action==='UNDO'){if(r.path.length<=(r.hinted?2:1))throw Error('There is no step to undo');r.path.pop();r.undos++;continue;}
      if(action==='HINT'){if(r.hinted)throw Error('The hint has already been used');r.hinted=true;r.path=q.solution.slice(0,2);complete();continue;}
      const match=typeof action==='string'&&action.match(/^ADD:(\d{7})$/),id=match&&Number(match[1]);
      if(!match||!link(data,r.path.at(-1),id)||r.path.includes(id)||id===q.end)throw Error('Choose an available teammate');
      if(r.path.length-1>=q.solution.length-1)throw Error('Undo a step to make room for another teammate');
      r.path.push(id);complete();
    }
    if(guesses.length>=100){for(let i=current;i<rounds.length;i++)rounds[i].done=true;current=rounds.length-1;}
    const over=current===rounds.length-1&&rounds[current].done;
    return {rounds,current,over,won:over&&rounds.every(r=>r.won),score:rounds.reduce((n,r)=>n+r.points,0)};
  }
  function result(mode,target,guesses,data){
    if(!Array.isArray(guesses)||guesses.length>100)throw Error('Invalid actions');
    const state=mode==='grid'?grid(target,guesses,data):mode==='benchboss'?boss(target,guesses,data):trail(target,guesses,data);
    if(!state.over)throw Error('Finish the game before submitting');
    return {won:state.won,tries:guesses.length,points:state.score};
  }
  return {group,index,qualifies,candidates,criterion,raritySnapshot,bonus,grid,fillGrid,draft,boss,link,teammates,shortest,trail,result};
})();
