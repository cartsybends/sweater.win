// Anonymous usage diagnostics contain no typed input or answer content. Grid
// popularity separately submits verified public player IDs, respecting opt-out.
(() => {
  const noop={view(){},hub(){},context(){},beginRound(){},step(){},completeRound(){},gridAnswers(){},leave(){},share(){},interaction(){},team(){}};
  globalThis.SweaterAnalytics=noop;
  if(!API_ON||!['sweater.win','www.sweater.win'].includes(location.hostname)||navigator.globalPrivacyControl||navigator.doNotTrack==='1'||!globalThis.crypto?.randomUUID)return;
  const UUID=/^[a-f0-9]{8}(-[a-f0-9]{4}){3}-[a-f0-9]{12}$/i,storageKey='sweater-usage-session-v1',optoutKey='sweater-analytics-optout';
  let landingURL,referrer='';
  try{
    const root=window.parent&&window.parent!==window&&['sweater.win','www.sweater.win'].includes(window.parent.location.hostname)?window.parent:window;
    landingURL=new URL(root.location?.href||location.href||'https://'+location.hostname+'/');referrer=root.document?.referrer||document.referrer||'';
  }catch{try{landingURL=new URL(location.href||'https://'+location.hostname+'/');referrer=document.referrer||'';}catch{}}
  const preference=landingURL?.searchParams.get('analytics');let excluded=false;
  try{if(preference==='off')localStorage.setItem(optoutKey,'1');if(preference==='on')localStorage.removeItem(optoutKey);excluded=localStorage.getItem(optoutKey)==='1';}catch{}
  if(preference==='off'||excluded&&preference!=='on')return;
  let visitor,saved;
  try{visitor=JSON.parse(localStorage.getItem('sweater-usage-visitor-v2')||'null');}catch{}
  if(!visitor||!UUID.test(visitor.id||'')||!Number.isFinite(visitor.expires)||visitor.expires<Date.now())visitor={id:crypto.randomUUID(),expires:Date.now()+365*86400000};
  try{localStorage.setItem('sweater-usage-visitor-v2',JSON.stringify(visitor));}catch{}
  try{saved=JSON.parse(sessionStorage.getItem(storageKey)||'null');}catch{}
  if(!saved||!UUID.test(saved.id||'')||!saved.rounds||typeof saved.rounds!=='object'||Array.isArray(saved.rounds))saved={id:crypto.randomUUID(),rounds:{}};
  const persist=()=>{try{sessionStorage.setItem(storageKey,JSON.stringify(saved));}catch{}};persist();
  const visit=crypto.randomUUID(),queue=[],ua=navigator.userAgent||'',coarse=matchMedia('(pointer:coarse)').matches;
  const device=coarse?(innerWidth<768?'mobile':'tablet'):'desktop';
  const browser=/DuckDuckGo/i.test(ua)?'duckduckgo':/Edg/i.test(ua)?'edge':/SamsungBrowser/i.test(ua)?'samsung':/OPR|Opera/i.test(ua)?'opera':/Firefox|FxiOS/i.test(ua)?'firefox':/Chrome|CriOS/i.test(ua)?'chrome':/Safari/i.test(ua)?'safari':ua?'other':'unknown';
  const os=/iPhone|iPad|iPod/i.test(ua)||/Macintosh/i.test(ua)&&navigator.maxTouchPoints>1?'ios':/Android/i.test(ua)?'android':/Windows/i.test(ua)?'windows':/Macintosh|Mac OS/i.test(ua)?'macos':/Linux/i.test(ua)?'linux':ua?'other':'unknown';
  const sources=['direct','google','bing','duckduckgo','yahoo','instagram','tiktok','youtube','facebook','x','reddit','discord','referral','other'];
  const clean=value=>typeof value==='string'&&/^[a-z0-9][a-z0-9._-]{0,59}$/i.test(value)?value:undefined;
  let source='direct';
  try{
    const host=new URL(referrer).hostname.toLowerCase().replace(/^www\./,''),domain=name=>host===name||host.endsWith('.'+name);
    if(!['sweater.win','api.sweater.win'].includes(host))source=/(^|\.)google\.(com|[a-z]{2}|(?:co|com)\.[a-z]{2})$/.test(host)?'google':host==='t.co'||host==='x.com'?'x':domain('instagram.com')?'instagram':domain('tiktok.com')?'tiktok':domain('youtube.com')||host==='youtu.be'?'youtube':domain('facebook.com')?'facebook':domain('reddit.com')?'reddit':domain('discord.com')||host==='discord.gg'?'discord':domain('duckduckgo.com')?'duckduckgo':domain('bing.com')?'bing':domain('yahoo.com')?'yahoo':'referral';
  }catch{}
  const tagged=clean(landingURL?.searchParams.get('utm_source'))?.toLowerCase();if(tagged)source=sources.includes(tagged)?tagged:'other';
  const campaign=clean(landingURL?.searchParams.get('utm_campaign')),medium=clean(landingURL?.searchParams.get('utm_medium'));
  const build=typeof BUILT==='string'?BUILT.match(/builder v(\d{1,5})/)?.[1]:undefined;
  const metadata=()=>({version:2,visitor:visitor.id,visit,browser,os,source,...(campaign?{campaign}:{}),...(medium?{medium}:{}),...(build?{build}:{}),theme:['light','dark'].includes(document.documentElement?.dataset?.theme)?document.documentElement.dataset.theme:'unknown',viewport:innerWidth<400?'small':innerWidth<768?'medium':innerWidth<1280?'large':'wide'});
  let enabled=null,version=1,diagnostics=false,current=null,round=null,roundKey=null,previous=null,active=0,lastTick=performance.now(),lastInteraction=performance.now(),sending=false,errors=0;
  const diagnosticFields=['release','error_type','error_file','error_line','error_column','resource','asset','online'];
  const payload=data=>diagnostics?data:Object.fromEntries(Object.entries(data).filter(([key])=>!diagnosticFields.includes(key)));
  const awake=()=>document.visibilityState!=='hidden'&&document.hasFocus()&&performance.now()-lastInteraction<45000;
  function event(kind,extra={},scope=current){
    if(!scope||enabled===false)return;
    if(queue.length>=128)queue.shift();
    queue.push({data:{id:crypto.randomUUID(),session:saved.id,mode:scope.mode,variant:scope.variant,kind,device,...metadata(),...extra},attempts:0});
    Promise.resolve().then(flush);
  }
  const legacyKinds=new Set(['mode_open','round_start','round_complete','engagement']);
  function legacy(data){const keys=['id','session','mode','variant','kind','round','device','active_ms','won'];return Object.fromEntries(keys.filter(k=>data[k]!==undefined).map(k=>[k,k==='won'?!!data[k]:data[k]]));}
  async function flush(){
    if(!enabled||sending)return;sending=true;
    try{while(queue.length){
      if(version<2&&(!legacyKinds.has(queue[0].data.kind)||queue[0].data.mode==='hub')){queue.shift();continue;}
      const batch=queue.slice(0,version>=2?5:1),body=version>=2?{events:batch.map(e=>payload(e.data))}:legacy(batch[0].data);
      try{
        const r=await fetch(API+'/api/analytics/collect',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body),credentials:'omit',keepalive:true});
        if(r.ok||r.status>=400&&r.status<500&&r.status!==429){queue.splice(0,batch.length);continue;}
        throw new Error('retry');
      }catch{for(const e of batch)e.attempts++;if(batch.every(e=>e.attempts>=3)){queue.splice(0,batch.length);continue;}setTimeout(flush,1500*2**Math.max(...batch.map(e=>e.attempts)));break;}
    }}finally{sending=false;}
  }
  function tick(){const now=performance.now();if(current&&awake()){const ms=Math.min(2000,Math.max(0,now-lastTick));active+=ms;if(round&&!round.complete)round.active_ms=Math.min(604800000,(round.active_ms||0)+ms);}lastTick=now;}
  function engagement(){tick();const ms=Math.min(60000,Math.round(active));active=0;persist();if(ms>0)event('engagement',{active_ms:ms,...(round?{round:round.id}:{})});}
  function exitRound(){if(!round||!round.started||round.complete)return;tick();round.exit_id ||= crypto.randomUUID();event('round_exit',{id:round.exit_id,round:round.id,step:round.step||0,elapsed_ms:Math.round(round.active_ms||0)});persist();}
  function view(mode,variant){
    if(current?.mode===mode&&current?.variant===variant)return;
    engagement();exitRound();const from=current?.mode||previous;
    current={mode,variant};round=null;roundKey=null;previous=mode;lastTick=lastInteraction=performance.now();
    event(mode==='hub'?'page_view':'mode_open',from&&from!==mode?{from_mode:from}:{});
  }
  function context(mode,variant,target,fresh=false){
    view(mode,variant);const key=JSON.stringify([mode,variant,target]);
    if(round&&(roundKey!==key||fresh))exitRound();
    if(fresh||!saved.rounds[key])saved.rounds[key]={id:crypto.randomUUID(),started:false,complete:false,active_ms:0,step:0,last_step_ms:0};
    round=saved.rounds[key];roundKey=key;
    if(!Number.isFinite(round.active_ms)||round.active_ms<0)round.active_ms=0;
    if(!Number.isInteger(round.step)||round.step<0)round.step=0;
    if(!Number.isFinite(round.last_step_ms)||round.last_step_ms<0)round.last_step_ms=0;
    const keys=Object.keys(saved.rounds);if(keys.length>120)for(const k of keys.slice(0,keys.length-120))delete saved.rounds[k];persist();
    return round.id;
  }
  function beginRound(){if(!round||round.started||round.complete)return;tick();round.started=true;persist();event('round_start',{round:round.id});}
  function step(index,correct,token){
    if(token&&token!==round?.id)return;
    if(!round||round.complete||!Number.isInteger(index)||index<1||index>10000||index<=(round.step||0))return;
    beginRound();tick();const response=Math.max(0,Math.round((round.active_ms||0)-(round.last_step_ms||0)));
    round.step=index;round.last_step_ms=round.active_ms||0;persist();event('round_step',{round:round.id,step:index,response_ms:response,...(typeof correct==='boolean'?{correct}:{})});
  }
  function completeRound(won,details={}){
    if(details.token&&details.token!==round?.id)return;
    if(!round||!round.started||round.complete)return;tick();round.complete=true;persist();
    const index=Number.isInteger(details.attempts)?Math.max(0,Math.min(10000,details.attempts)):round.step||0;
    const score=Number.isFinite(details.score)&&Math.abs(details.score)<=1000000?details.score:undefined;
    event('round_complete',{round:round.id,won:typeof won==='boolean'?won:null,step:index,elapsed_ms:Math.round(round.active_ms||0),...(score!==undefined?{score}:{})});
  }
  function gridAnswers(puzzle,guesses,variant,day){
    if(enabled!==true||!['daily','unlimited'].includes(variant))return;
    if(navigator.globalPrivacyControl||navigator.doNotTrack==='1')return;
    try{if(localStorage.getItem(optoutKey)==='1')return;}catch{}
    const body={visitor:visitor.id,puzzle,guesses,variant,day};
    fetch(API+'/api/grid/answers',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body),credentials:'omit',keepalive:true}).catch(()=>{});
  }
  function leave(){engagement();exitRound();previous=current?.mode||previous;current=round=null;roundKey=null;}
  const interaction=(action,extra={})=>{const {mode:target,...fields}=extra;event('interaction',{action,...fields,...(target?{from_mode:target}:{})},current||{mode:'hub',variant:'hub'});};
  const safe=fn=>(...args)=>{try{return fn(...args);}catch{}};
  globalThis.SweaterAnalytics=Object.fromEntries(Object.entries({view,hub:()=>view('hub','hub'),context,beginRound,step,completeRound,gridAnswers,leave,share:mode=>event('share',{},mode?{mode,variant:current?.variant||'daily'}:current),interaction,team:team=>interaction('team_select',{team})}).map(([k,fn])=>[k,safe(fn)]));
  for(const name of ['pointerdown','keydown','scroll','touchstart','pointermove'])document.addEventListener(name,()=>{tick();lastInteraction=performance.now();},{passive:true});
  let lcp,cls,windowShift=0,windowStart=0,windowEnd=0,performanceSent=false;
  try{if(globalThis.PerformanceObserver){
    const types=PerformanceObserver.supportedEntryTypes||[];
    if(types.includes('largest-contentful-paint'))try{new PerformanceObserver(list=>{for(const e of list.getEntries())lcp=Math.round(e.startTime);}).observe({type:'largest-contentful-paint',buffered:true});}catch{}
    if(types.includes('layout-shift'))try{new PerformanceObserver(list=>{for(const e of list.getEntries())if(!e.hadRecentInput){if(e.startTime-windowEnd>1000||e.startTime-windowStart>5000){windowShift=0;windowStart=e.startTime;}windowEnd=e.startTime;windowShift+=e.value;cls=Math.max(cls||0,windowShift);}}).observe({type:'layout-shift',buffered:true});cls=0;}catch{}
  }}catch{}
  function performanceSample(){
    if(performanceSent)return;const nav=performance.getEntriesByType?.('navigation')?.[0],fields={};
    for(const [k,v]of [['load_ms',nav?.loadEventEnd],['ttfb_ms',nav?.responseStart],['lcp_ms',lcp]])if(Number.isFinite(v)&&v>0&&v<=120000)fields[k]=Math.round(v);
    if(Number.isFinite(cls))fields.cls=Math.min(10,Math.max(0,cls));
    if(!Object.keys(fields).length)return;performanceSent=true;event('performance',fields,current||{mode:'hub',variant:'hub'});
  }
  document.addEventListener('visibilitychange',()=>{engagement();if(document.visibilityState==='hidden')performanceSample();lastTick=performance.now();});
  window.addEventListener('pagehide',()=>{engagement();exitRound();performanceSample();event('page_exit',{},current||{mode:'hub',variant:'hub'});flush();});
  window.addEventListener('blur',engagement);window.addEventListener('focus',()=>{lastTick=lastInteraction=performance.now();});
  window.addEventListener('load',()=>setTimeout(performanceSample,5000));
  const errorTypes=['Error','TypeError','ReferenceError','SyntaxError','RangeError','URIError','EvalError','AbortError','NotAllowedError','NotSupportedError','SecurityError','QuotaExceededError','NetworkError'];
  function scriptLocation(filename,line,column){
    try{
      const url=new URL(filename,location.href);
      if(!['sweater.win','www.sweater.win'].includes(url.hostname))return {error_file:'external'};
      const file={'/app.html':'app.html','/':'home','/index.html':'home','/sw.js':'sw.js'}[url.pathname];
      if(!file)return {error_file:'unknown'};
      return {error_file:file,...(Number.isInteger(line)&&line>0&&line<=200000?{error_line:line}:{}),...(Number.isInteger(column)&&column>0&&column<=10000000?{error_column:column}:{})};
    }catch{return {error_file:'unknown'};}
  }
  function errorDetails(reason){
    const details={error_type:'unknown'};
    try{if(errorTypes.includes(reason?.name))details.error_type=reason.name;}catch{}
    try{
      // Inspect frame locations only; never send messages, stacks, function names or URLs.
      for(const [index,frame] of (typeof reason?.stack==='string'?reason.stack:'').split('\n').entries()){
        // Safari/Firefox can start directly with a frame; Chrome starts with the message.
        if(index===0&&!/^(?:[^@\s]*@)?https?:\/\/[^\s]+:\d+:\d+$/.test(frame))continue;
        const match=frame.match(/(https?:\/\/[^\s)]+):(\d+):(\d+)\)?$/);
        if(!match)continue;
        const place=scriptLocation(match[1],Number(match[2]),Number(match[3]));
        if(['app.html','home','sw.js'].includes(place.error_file)){Object.assign(details,place);break;}
      }
    }catch{}
    return details;
  }
  function resourceDetails(target){
    const tag=String(target?.tagName||'').toLowerCase(),kinds={img:'image',video:'video',audio:'audio',source:'media',script:'script',link:'stylesheet'};
    const details={resource:kinds[tag]||'other'};
    try{
      const url=new URL(target.currentSrc||target.src||target.href,location.href);
      const local=['sweater.win','www.sweater.win'].includes(url.hostname);
      if(local&&/^\/who-scored\/goal-\d{2,3}-(?:(?:masked|original)-v[1-9]\d*\.mp4|v[1-9]\d*\.jpg)$/.test(url.pathname)){
        details.resource=url.pathname.endsWith('.mp4')?'goal_video':'goal_poster';details.asset=url.pathname.split('/').pop();
      }else if(url.hostname==='assets.nhle.com')details.resource=/\/(mugs|headshots)\//.test(url.pathname)?'headshot':/\/logos\//.test(url.pathname)?'team_logo':details.resource;
      else if(local&&/^\/team-logos\/[A-Z]{3}\.svg$/.test(url.pathname))details.resource='team_logo';
      else if(local&&/^\/grid-flags\/(ca|us|se|fi)\.svg$/.test(url.pathname))details.resource='country_flag';
      else if(url.hostname==='flagcdn.com')details.resource='country_flag';
      else if(local&&url.pathname==='/sweater-icon.svg')details.resource='site_icon';
      if(tag==='link'&&target.rel==='manifest')details.resource='manifest';
      const mediaTypes={1:'MediaAbortError',2:'MediaNetworkError',3:'MediaDecodeError',4:'MediaSourceError'};
      if(mediaTypes[target?.error?.code])details.error_type=mediaTypes[target.error.code];
    }catch{}
    return details;
  }
  const error=(action,details={})=>{if(errors++>=10)return;event('error',{action,...details,...(typeof SITE_RELEASE==='string'&&/^[a-f0-9]{12}$/.test(SITE_RELEASE)?{release:SITE_RELEASE}:{}),...(typeof navigator.onLine==='boolean'?{online:navigator.onLine}:{})},current||{mode:'hub',variant:'hub'});};
  window.addEventListener('error',safe(e=>{
    if(e?.target&&e.target!==window)error('resource',resourceDetails(e.target));
    else error('javascript',{...errorDetails(e?.error),...(e?.filename?scriptLocation(e.filename,e.lineno,e.colno):{})});
  }),true);
  window.addEventListener('unhandledrejection',safe(e=>error('promise',errorDetails(e?.reason))));
  setInterval(tick,1000);setInterval(engagement,30000);
  const hash=(landingURL?.hash||location.hash||'').slice(1),entry=typeof G==='object'&&G!==null&&Object.hasOwn(G,hash)?hash:hash==='hl'?'hl':hash==='teams'||hash.startsWith('team-')?'teams':hash==='party'||hash.startsWith('party-')?'party':'hub';
  let play='daily';try{const stored=JSON.parse(localStorage.getItem('sweater-mode')||'null');if(['daily','unlimited','archive'].includes(stored))play=stored;}catch{}
  event('site_visit',{}, {mode:entry,variant:entry==='hub'?'hub':entry==='party'?'party':entry==='teams'?'unlimited':play});
  const controller=new AbortController(),timeout=setTimeout(()=>controller.abort(),5000);
  fetch(API+'/api/analytics/status',{credentials:'omit',cache:'no-store',signal:controller.signal}).then(r=>r.ok?r.json():{enabled:false}).then(d=>{enabled=d.enabled===true;version=d.version>=2?2:1;diagnostics=d.diagnostics===1;if(enabled)flush();else queue.length=0;}).catch(()=>{enabled=false;queue.length=0;}).finally(()=>clearTimeout(timeout));
})();
