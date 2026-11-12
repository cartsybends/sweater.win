let ppFeedTimer=null,ppFeedController=null,ppFeedBusy=false,ppFeedAttempt=0,ppFeedRequest=0,ppFeedError=false;
const ppFeed=POINT_PROJECTIONS_FEED;
const ppSnapshotChecked=()=>ppShared?ppShared.checkedAt||null:PROJECTION_DATA.collected_at||null;
function ppCheckedLabel(value,fallback=''){
 return value&&Number.isFinite(Date.parse(value))?new Date(value).toLocaleString(undefined,{month:'short',day:'numeric',hour:'numeric',minute:'2-digit',timeZoneName:'short'}):fallback;
}
function ppFeedEligible(){return !$('view-projections').hidden&&!document.hidden&&!ppShared&&(ppState.mode==='players'||!ppPlayers.size);}
function ppFeedStatus(){
 $('ppFeedBar').hidden=ppState.mode==='manual';$('ppRefreshStats').hidden=!!ppShared;$('ppRefreshStats').disabled=ppFeedBusy;
 const checked=ppSnapshotChecked(),fallback=ppShared?.asof||PROJECTION_DATA.asof||'unavailable';
 $('ppFeedTime').textContent=`${ppShared?'Shared snapshot':'NHL stats checked'} · ${ppCheckedLabel(checked,fallback)}`;
 $('ppFeedNote').textContent=ppShared?'This shared stat line stays fixed.':ppFeedBusy?'Checking for newer stats…':ppFeedError?'Latest check unavailable. Keeping the last verified stats.':'Refreshes about every 15 minutes';
}
function ppApplyFeed(raw,now=Date.now()){
 const data=ppFeed.validate(raw,now);if(!data)throw new Error('Invalid NHL projection feed');
 if(!ppFeed.newer(data,PROJECTION_DATA))return false;
 Object.assign(PROJECTION_DATA,data);ppPlayers.clear();for(const p of data.players)ppPlayers.set(p.id,p);
 $('ppPlayersTab').disabled=false;$('ppAvailability').hidden=true;
 ppState.ids=ppState.ids.filter(id=>ppPlayers.has(id)||ppShared?.player.id===id);
 if(!ppState.ids.length&&!ppShared){const first=ppPlayers.has(ppDefault)?ppDefault:[...ppPlayers.values()].sort((a,b)=>b.points-a.points)[0]?.id;if(first)ppState.ids=[first];}
 if(!ppState.ids.includes(ppState.selected))ppState.selected=ppState.ids[0];
 // A late response can update the catalog, but never replace a shared stat line or manual inputs.
 if(!$('view-projections').hidden&&!ppShared&&ppState.mode==='players'){
  const focused=document.activeElement,selection=focused?.id==='ppSearch'?{start:focused.selectionStart,end:focused.selectionEnd}:null;
  ppRender();if(selection&&focused===document.activeElement)focused.setSelectionRange(selection.start,selection.end);
 }
 return true;
}
async function ppRefreshFeed(force=false){
 if(!ppFeedEligible()||ppFeedBusy||!force&&Date.now()-ppFeedAttempt<ppFeed.interval)return;
 ppFeedAttempt=Date.now();ppFeedBusy=true;ppFeedStatus();const request=++ppFeedRequest,controller=new AbortController();ppFeedController=controller;
 const timeout=setTimeout(()=>controller.abort(),12000);
 try{
  const response=await fetch(ppFeed.url+'?v='+Math.floor(Date.now()/(force?1000:ppFeed.interval)),{cache:'no-store',credentials:'omit',signal:controller.signal});
  if(!response.ok)throw new Error('Projection feed unavailable');const data=await response.json();if(request!==ppFeedRequest)return;
  ppApplyFeed(data);ppFeedError=false;
 }catch{if(request===ppFeedRequest)ppFeedError=true;}
 finally{clearTimeout(timeout);if(request===ppFeedRequest){ppFeedBusy=false;ppFeedController=null;ppFeedStatus();}}
}
function ppStartFeed(){if($('view-projections').hidden)return;if(!ppFeedTimer)ppFeedTimer=setInterval(()=>ppRefreshFeed(),ppFeed.interval);ppRefreshFeed();}
function ppStopFeed(){clearInterval(ppFeedTimer);ppFeedTimer=null;ppFeedRequest++;ppFeedController?.abort();ppFeedController=null;ppFeedBusy=false;ppFeedAttempt=0;}
$('ppRefreshStats').onclick=()=>ppRefreshFeed(true);
document.addEventListener('visibilitychange',()=>{if(!document.hidden)ppRefreshFeed();});
