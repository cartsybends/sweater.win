// Pure rules shared by the browser and leaderboard Worker.
export const DEEP_CUT_MODEL = (() => {
  const tiers = Object.freeze([
    {score:0,name:'Off the ice',color:'#71829e',mark:'⬛'},
    {score:10,name:'Household name',color:'#9baac4',mark:'⬜'},
    {score:15,name:'Fan favourite',color:'#6dc5ff',mark:'🟦'},
    {score:30,name:'Roster regular',color:'#60e4bd',mark:'🟩'},
    {score:60,name:'Hidden gem',color:'#c09bff',mark:'🟪'},
    {score:85,name:'Deep cut',color:'#ff9b67',mark:'🟧'},
    {score:100,name:'Cult legend',color:'#ffdb82',mark:'🟨'},
  ]);
  const cache = new WeakMap();
  const normalize = text => String(text).normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/ø/g,'o').replace(/ł/g,'l').replace(/ß/g,'ss').replace(/æ/g,'ae').replace(/œ/g,'oe').replace(/[^a-z0-9]/g,'');
  const tier = score => tiers.find(t=>t.score===score) || tiers[0];
  function index(data) {
    if(cache.has(data))return cache.get(data);
    const players=new Map(),full=new Map(),aliases=new Map(),prompts=new Map(),runs=new Map();
    const add=(map,key,id)=>{if(!key)return;const ids=map.get(key)||new Set();ids.add(id);map.set(key,ids);};
    for(const [id,name,born,other=[]] of data.players){
      players.set(id,{id,name,born});add(full,normalize(name),id);add(full,normalize(name+' '+born),id);
      const parts=name.trim().split(/\s+/);add(aliases,normalize(parts.at(-1)),id);if(parts.length>2)add(aliases,normalize(parts.slice(1).join(' ')),id);
      for(const alias of other)add(aliases,normalize(alias),id);
    }
    for(const p of data.prompts)prompts.set(p.id,{...p,points:new Map(p.answers)});
    for(const run of data.runs)runs.set(run.id,run);
    const out={players,full,aliases,prompts,runs};cache.set(data,out);return out;
  }
  function oneEdit(a,b){
    if(Math.abs(a.length-b.length)>1)return false;
    if(a===b)return true;
    if(a.length===b.length){const dif=[];for(let i=0;i<a.length;i++)if(a[i]!==b[i])dif.push(i);return dif.length===1||dif.length===2&&dif[1]===dif[0]+1&&a[dif[0]]===b[dif[1]]&&a[dif[1]]===b[dif[0]];}
    if(a.length>b.length)[a,b]=[b,a];
    let i=0;while(i<a.length&&a[i]===b[i])i++;return a.slice(i)===b.slice(i+1);
  }
  function match(text,promptId,data){
    const ix=index(data),prompt=ix.prompts.get(promptId),key=normalize(text);
    if(!prompt||!key||key.length>80)return {status:'missing'};
    // Exact identities take precedence over fuzzy matches and prompt filtering.
    let ids=ix.full.get(key)||ix.aliases.get(key),fuzzy=false;
    if(!ids&&key.length>=5){
      ids=new Set();fuzzy=true;
      for(const map of [ix.full,ix.aliases])for(const [alias,candidates] of map)if(oneEdit(key,alias))for(const id of candidates)ids.add(id);
    }
    if(!ids?.size)return {status:'missing'};
    const eligible=[...ids].filter(id=>prompt.points.has(id));
    if(eligible.length>1)return {status:'ambiguous'};
    if(eligible.length===1){const id=eligible[0];return {status:'accepted',id,score:prompt.points.get(id),name:ix.players.get(id).name,fuzzy};}
    return {status:'wrong'};
  }
  function state(run,actions,data){
    const ix=index(data);
    if(!run||!Array.isArray(run.prompts)||run.prompts.length!==7||new Set(run.prompts).size!==7||run.prompts.some(id=>!ix.prompts.has(id)))throw Error('Invalid Deep Cut run');
    if(!Array.isArray(actions)||actions.length>7)throw Error('Invalid answers');
    const rounds=actions.map((action,i)=>{
      const p=ix.prompts.get(run.prompts[i]);
      if(action==='MISS')return {prompt:p,id:null,score:0,tier:tier(0)};
      if(typeof action!=='string'||!/^\d{7}$/.test(action)||!p.points.has(Number(action)))throw Error('That player does not fit this prompt');
      const id=Number(action),score=p.points.get(id);
      return {prompt:p,id,name:ix.players.get(id).name,score,tier:tier(score)};
    });
    const score=rounds.reduce((n,r)=>n+r.score,0),over=rounds.length===7;
    return {rounds,score,distance:score*10,over,won:over&&score>=300};
  }
  function result(run,actions,data){const s=state(run,actions,data);if(!s.over)throw Error('Finish all seven prompts first');return {won:s.won,tries:7,points:s.score};}
  function rank(score){return score>=600?'Cult legend':score>=450?'Deep-cut specialist':score>=300?'Rink rat':score>=150?'Season-ticket holder':score>0?'Fresh legs':'Back to practice';}
  return Object.freeze({tiers,normalize,tier,index,match,state,result,rank,oneEdit});
})();
