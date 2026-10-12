// Aggregate mode usage; no player names, guesses, referrers, or leaderboard identities.
(() => {
  const noop={view(){},context(){},beginRound(){},completeRound(){},leave(){}};
  globalThis.SweaterAnalytics=noop;
  if(!API_ON||!['sweater.win','www.sweater.win'].includes(location.hostname)||navigator.globalPrivacyControl||navigator.doNotTrack==='1'||!globalThis.crypto?.randomUUID)return;
  const storageKey='sweater-usage-session-v1';
  let saved;try{saved=JSON.parse(sessionStorage.getItem(storageKey)||'null');}catch{}
  if(!saved||typeof saved.id!=='string'||!saved.rounds||typeof saved.rounds!=='object')saved={id:crypto.randomUUID(),rounds:{}};
  const persist=()=>{try{sessionStorage.setItem(storageKey,JSON.stringify(saved));}catch{}};
  persist();let enabled=null,current=null,round=null,active=0,lastTick=performance.now(),lastInteraction=performance.now(),sending=false;
  const queue=[],device=matchMedia('(pointer:coarse)').matches?(innerWidth<768?'mobile':'tablet'):'desktop';
  const awake=()=>document.visibilityState!=='hidden'&&document.hasFocus()&&performance.now()-lastInteraction<45000;
  function event(kind,extra={}) {
    if(!current||enabled===false)return;
    if(queue.length>=32)queue.shift();
    queue.push({data:{id:crypto.randomUUID(),session:saved.id,mode:current.mode,variant:current.variant,kind,device,...extra},attempts:0});
    flush();
  }
  async function flush() {
    if(!enabled||sending)return;sending=true;
    try {while(queue.length){const e=queue[0];try{const r=await fetch(API+'/api/analytics/collect',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(e.data),credentials:'omit',keepalive:true});if(r.ok||r.status>=400&&r.status<500&&r.status!==429){queue.shift();continue;}throw new Error('retry');}catch{e.attempts++;if(e.attempts>=3){queue.shift();continue;}setTimeout(flush,1500*2**e.attempts);break;}}}finally{sending=false;}
  }
  function tick() {const now=performance.now();if(current&&awake())active+=Math.min(2000,Math.max(0,now-lastTick));lastTick=now;}
  function engagement(){tick();const ms=Math.min(60000,Math.round(active));active=0;if(ms>0)event('engagement',{active_ms:ms});}
  function view(mode,variant) {
    if(current?.mode===mode&&current?.variant===variant)return;
    engagement();current={mode,variant};round=null;lastTick=lastInteraction=performance.now();event('mode_open');
  }
  function context(mode,variant,target,fresh=false) {
    view(mode,variant);const key=JSON.stringify([mode,variant,target]);
    if(fresh||!saved.rounds[key])saved.rounds[key]={id:crypto.randomUUID(),started:false,complete:false};
    round=saved.rounds[key];
    const keys=Object.keys(saved.rounds);if(keys.length>120)for(const k of keys.slice(0,keys.length-120))delete saved.rounds[k];
    persist();
  }
  function beginRound(){if(!round||round.started||round.complete)return;round.started=true;persist();event('round_start',{round:round.id});}
  function completeRound(won){if(!round||!round.started||round.complete)return;round.complete=true;persist();event('round_complete',{round:round.id,won:!!won});}
  function leave(){engagement();current=round=null;}
  globalThis.SweaterAnalytics={view,context,beginRound,completeRound,leave};
  for(const name of ['pointerdown','keydown','scroll','touchstart','pointermove'])document.addEventListener(name,()=>{lastInteraction=performance.now();},{passive:true});
  document.addEventListener('visibilitychange',()=>{engagement();lastTick=performance.now();});
  window.addEventListener('pagehide',engagement);window.addEventListener('blur',engagement);window.addEventListener('focus',()=>{lastTick=lastInteraction=performance.now();});
  setInterval(tick,1000);setInterval(engagement,30000);
  const controller=new AbortController(),timeout=setTimeout(()=>controller.abort(),5000);
  fetch(API+'/api/analytics/status',{credentials:'omit',cache:'no-store',signal:controller.signal}).then(r=>r.ok?r.json():{enabled:false}).then(d=>{enabled=d.enabled===true;if(enabled)flush();else queue.length=0;}).catch(()=>{enabled=false;queue.length=0;}).finally(()=>clearTimeout(timeout));
})();
