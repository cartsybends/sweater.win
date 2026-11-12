const PP_SWEATER_MARK='<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 40 40" aria-hidden="true"><rect width="40" height="40" rx="10" fill="#18232f"/><path d="M27 11H17a5 5 0 0 0 0 10h6a4 4 0 0 1 0 8H12" fill="none" stroke="#fff" stroke-width="4" stroke-linecap="round"/><path d="M12 35h16" stroke="#8055ff" stroke-width="3"/></svg>';
const ppImageCache=new Map(),ppExportCache=new Map();
let ppPrepared=null,ppPreviewURL='',ppPreviewSnapshot=null,ppPreviewBlob=null;
$('ppCardBrand').innerHTML=PP_SWEATER_MARK+'<span>sweater.win</span>';

function ppShareSnapshot(){
 const p=ppCurrent();if(!p)return null;
 return ppSharing.normalize({v:1,mode:ppState.mode,player:p,start:ppShared?.start||PROJECTION_DATA.start||2026,asof:ppState.mode==='manual'?null:ppShared?.asof||PROJECTION_DATA.asof||null,seasonGames:ppState.seasonGames,rate:ppState.rate,missed:ppState.missed});
}
function ppShareURL(snapshot){const url=new URL(SITE||location.href);url.search='';url.hash=ppSharing.hash(snapshot);return url.href;}
function ppCloseShare(focus=false){$('ppShareMenu').hidden=true;$('ppShareToggle').setAttribute('aria-expanded','false');if(focus)$('ppShareToggle').focus();}
function ppRenderShare(p,r,manual){
 const snapshot=ppShareSnapshot(),start=snapshot?.start||PROJECTION_DATA.start||2026;
 $('ppShareToggle').disabled=!r.valid;$('ppShareStatus').textContent='';if(!r.valid)ppCloseShare();
 $('ppSharedNotice').hidden=!ppShared;$('ppSharedNotice').querySelector('span').textContent=manual?'Viewing shared calculator settings.':'Viewing a shared stat snapshot.';$('ppUseLatest').hidden=manual;
 $('ppCardKicker').textContent=`${start}–${String(start+1).slice(-2)} POINT PROJECTION`;
 $('ppCardTeam').textContent=p?(manual?`${p.gp||0} games played · your numbers`:`${p.team?teamFullName(p.team):'NHL skater'} · ${p.gp} GP`):'Choose an NHL skater';
 const identity=manual?'manual':String(p?.id||'empty');
 if($('ppCardPortrait').dataset.player!==identity){
  $('ppCardPortrait').dataset.player=identity;
  const initials=p?.name.split(' ').map(s=>s[0]).slice(0,2).join('')||'?';
  $('ppCardPortrait').innerHTML=manual?uiIcon('chart'):`<span>${esc(initials)}</span>${p?`<img src="projection-headshots/${p.id}.webp" alt="" onload="this.previousElementSibling.hidden=true" onerror="this.remove()">`:''}`;
 }
 const team=!manual&&p?.team&&Object.hasOwn(TEAMS,p.team)?p.team:null;
 $('ppTeamArt').hidden=!team;if(team&&$('ppTeamArt').getAttribute('src')!==`team-logos/${team}.svg`)$('ppTeamArt').src=`team-logos/${team}.svg`;
 $('ppCardFootnote').textContent=manual?'Pace estimate · manual calculator':`Pace estimate${snapshot?.asof?' · '+snapshot.asof:''}`;
 if(!$('ppShareMenu').hidden)ppCloseShare();
}
function ppLoadImage(src){
 if(ppImageCache.has(src))return ppImageCache.get(src);
 const promise=new Promise(resolve=>{
  const img=new Image();let done=false;
  const finish=value=>{if(done)return;done=true;clearTimeout(timer);img.onload=img.onerror=null;resolve(value);};
  const timer=setTimeout(()=>finish(null),8000);img.crossOrigin='anonymous';img.onload=()=>finish(img);img.onerror=()=>finish(null);img.src=src;
 });
 ppImageCache.set(src,promise);if(ppImageCache.size>32)ppImageCache.delete(ppImageCache.keys().next().value);return promise;
}
function ppRoundRect(ctx,x,y,w,h,r,fill){ctx.beginPath();if(ctx.roundRect)ctx.roundRect(x,y,w,h,r);else ctx.rect(x,y,w,h);if(fill){ctx.fillStyle=fill;ctx.fill();}}
function ppDrawContain(ctx,img,x,y,w,h){if(!img)return;const scale=Math.min(w/img.width,h/img.height),dw=img.width*scale,dh=img.height*scale;ctx.drawImage(img,x+(w-dw)/2,y+h-dh,dw,dh);}
async function ppDrawExport(snapshot){
 const p=snapshot.player,r=ppModel.calculate({...p,...snapshot}),manual=snapshot.mode==='manual';
 const [portrait,crest,mark]=await Promise.all([manual?null:ppLoadImage(`projection-headshots/${p.id}.webp`),p.team?ppLoadImage(`team-logos/${p.team}.svg`):null,ppLoadImage('data:image/svg+xml,'+encodeURIComponent(PP_SWEATER_MARK))]);
 const canvas=document.createElement('canvas');canvas.width=1200;canvas.height=1040;const ctx=canvas.getContext('2d');
 ppRoundRect(ctx,0,0,1200,1040,36,'#102b35');ctx.save();ctx.clip();
 if(crest){ctx.globalAlpha=.1;ppDrawContain(ctx,crest,690,190,570,480);ctx.globalAlpha=1;}
 ctx.restore();
 const text=(value,x,y,size=22,color='#f3f8f8',weight=500,align='left')=>{ctx.font=`${weight} ${size}px Arial, sans-serif`;ctx.textAlign=align;ctx.fillStyle=color;ctx.fillText(String(value),x,y);};
 const fit=(value,max,size,min=24)=>{for(;size>min;size--){ctx.font=`750 ${size}px Arial, sans-serif`;if(ctx.measureText(value).width<=max)break;}return size;};
 ppRoundRect(ctx,60,62,156,156,78,'#203e49');ctx.save();ctx.clip();
 if(portrait)ppDrawContain(ctx,portrait,60,62,156,156);else if(manual){ctx.strokeStyle='#81e2c4';ctx.lineWidth=9;[47,75,105].forEach((v,i)=>{ctx.beginPath();ctx.moveTo(104+i*30,180);ctx.lineTo(104+i*30,180-v);ctx.stroke();});}else text(p.name.split(' ').map(v=>v[0]).slice(0,2).join(''),138,158,50,'#a8c6cc',700,'center');
 ctx.restore();
 text(`${snapshot.start}–${String(snapshot.start+1).slice(-2)}  ·  POINT PROJECTION`,244,92,16,'#81e2c4',600);
 text(p.name,242,151,fit(p.name,900,52),'#f3f8f8',750);
 text(manual?'Your numbers. Your pace.':`${p.team?teamFullName(p.team):'NHL skater'} · ${p.pos==='D'?'Defense':'Forward'}`,244,190,23,'#a6bfc5');
 text(`${r.seasonGames}-game pace`,62,306,23,'#abc4c9');
 const points=ppFmt(r.pace.points),size=fit(points,750,170,80);text(points,54,456,size,'#81e2c4',750);
 ctx.font=`750 ${size}px Arial, sans-serif`;const pw=ctx.measureText(points).width;text('POINTS',Math.min(830,70+pw),451,18,'#abc4c9',600);
 text(ppRate(r.ppg),1138,409,58,'#f3f8f8',650,'right');text('POINTS / GAME',1138,443,15,'#abc4c9',500,'right');
 [['PROJECTED GOALS',r.pace.goals],['PROJECTED ASSISTS',r.pace.assists],['POINTS SO FAR',r.points]].forEach(([label,n],i)=>{const x=60+i*366;ppRoundRect(ctx,x,510,348,128,16,'#193640');text(label,x+24,550,15,'#abc4c9',500);text(ppFmt(n),x+24,610,fit(ppFmt(n),300,48), '#f3f8f8',650);});
 text('YOUR SCENARIO FINISH',62,716,17,'#abc4c9',600);text(`${ppFmt(r.finish.points)} points`,1138,722,fit(`${ppFmt(r.finish.points)} points`,620,54),'#f3f8f8',650,'right');
 text(`${r.points} recorded points + ${ppRate(r.ppg*r.rate/100)} points/game × ${r.remaining} remaining games`,62,775,21,'#abc4c9');
 text(`${r.points} PTS in ${r.gp} GP  ·  future scoring ${r.rate}%  ·  ${r.missed} future games missed`,62,818,19,'#8faeb7');
 if(mark)ctx.drawImage(mark,60,930,44,44);text('sweater.win',116,962,30,'#d6e5e8',700);
 text('PACE ESTIMATE · REGULAR SEASON',1138,943,15,'#90aeb5',500,'right');text(manual?'Manual calculator':`Stats recorded · ${snapshot.asof||'date unavailable'}`,1138,973,16,'#90aeb5',500,'right');
 return new Promise((resolve,reject)=>canvas.toBlob(blob=>blob?resolve(blob):reject(new Error('Image export failed')),'image/png'));
}
function ppGetExport(snapshot){const key=JSON.stringify(snapshot);if(!ppExportCache.has(key)){ppExportCache.set(key,ppDrawExport(snapshot));if(ppExportCache.size>2)ppExportCache.delete(ppExportCache.keys().next().value);}return ppExportCache.get(key);}
function ppWarmExport(snapshot){
 const key=JSON.stringify(snapshot);$('ppNativeShare').disabled=true;
 ppGetExport(snapshot).then(blob=>{if(JSON.stringify(ppShareSnapshot())===key){ppPrepared={key,blob};$('ppNativeShare').disabled=false;}}).catch(()=>{});
}
function ppSaveImage(blob,snapshot){const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=ppSharing.filename(snapshot);document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),30000);}
function ppShowImage(blob,snapshot,message){
 if(ppPreviewURL)URL.revokeObjectURL(ppPreviewURL);ppPreviewURL=URL.createObjectURL(blob);ppPreviewSnapshot=snapshot;ppPreviewBlob=blob;
 $('ppImagePreview').src=ppPreviewURL;$('ppImageMessage').textContent=message;if(!$('ppImageDialog').open)$('ppImageDialog').showModal();
}
async function ppShareAction(action){
 const snapshot=ppShareSnapshot();if(!snapshot)return;
 ppCloseShare();
 if(action==='link'){await copyToClipboard(ppShareURL(snapshot),'Projection link copied');return;}
 if(action==='native'){
  if(ppPrepared?.key!==JSON.stringify(snapshot)){$('ppShareStatus').textContent='The image is preparing. Open Share and try again in a moment.';return;}
  try{await navigator.share({files:[new File([ppPrepared.blob],ppSharing.filename(snapshot),{type:'image/png'})],title:`${snapshot.player.name} · Point Projections`});}catch(error){if(error.name!=='AbortError')ppShowImage(ppPrepared.blob,snapshot,'Save this image to share it with your friends.');}return;
 }
 const image=ppGetExport(snapshot);$('ppShareStatus').textContent='Preparing your image…';
 try{
  if(action==='copy'&&navigator.clipboard?.write&&globalThis.ClipboardItem){
   // Start the clipboard write during the click, before awaiting image loading (Safari).
   try{await navigator.clipboard.write([new ClipboardItem({'image/png':image})]);$('ppShareStatus').textContent='';toast('Projection image copied');return;}catch{}
  }
  const blob=await image;$('ppShareStatus').textContent='';
  if(action==='save'){ppSaveImage(blob,snapshot);toast('Projection image ready to save');}else ppShowImage(blob,snapshot,'Image copy isn’t available here. Save the image, or touch and hold it to send it to a friend.');
 }catch{$('ppShareStatus').textContent='The image could not be prepared. Please try again.';}
}
$('ppShareToggle').onclick=e=>{
 const open=$('ppShareMenu').hidden;$('ppShareMenu').hidden=!open;$('ppShareToggle').setAttribute('aria-expanded',String(open));
 if(open){const snapshot=ppShareSnapshot();if(snapshot)ppWarmExport(snapshot);if(e.detail===0)$('ppShareMenu').querySelector('button').focus();}
};
$('ppShareMenu').onclick=e=>{const b=e.target.closest('[data-pp-share]');if(b)ppShareAction(b.dataset.ppShare);};
document.addEventListener('click',e=>{if(!e.target.closest('.pp-share-wrap'))ppCloseShare();});
$('ppShareMenu').parentElement.addEventListener('keydown',e=>{
 if(e.key==='Escape'){e.preventDefault();e.stopPropagation();ppCloseShare(true);return;}
 if(!['ArrowDown','ArrowUp','Home','End'].includes(e.key))return;e.preventDefault();
 $('ppShareMenu').hidden=false;$('ppShareToggle').setAttribute('aria-expanded','true');
 const buttons=[...$('ppShareMenu').querySelectorAll('button')].filter(b=>!b.hidden&&!b.disabled),index=buttons.indexOf(document.activeElement);
 const next=e.key==='Home'?0:e.key==='End'?buttons.length-1:(index+(e.key==='ArrowUp'?-1:1)+buttons.length)%buttons.length;buttons[next]?.focus();
});
try{$('ppNativeShare').hidden=!(navigator.share&&navigator.canShare?.({files:[new File([''], 'projection.png',{type:'image/png'})]}));}catch{$('ppNativeShare').hidden=true;}
$('ppImageClose').onclick=()=>$('ppImageDialog').close();$('ppImageSave').onclick=()=>{if(ppPreviewBlob&&ppPreviewSnapshot)ppSaveImage(ppPreviewBlob,ppPreviewSnapshot);};
$('ppImageDialog').addEventListener('close',()=>{if(ppPreviewURL)URL.revokeObjectURL(ppPreviewURL);ppPreviewURL='';ppPreviewSnapshot=null;ppPreviewBlob=null;$('ppImagePreview').removeAttribute('src');$('ppShareToggle').focus();});
$('ppUseLatest').onclick=()=>{if(ppShared&&!ppPlayers.has(ppShared.player.id)){toast('Current-season stats are unavailable for this player. Choose another skater above.');return;}ppDropShared();ppRender();ppSave();};

// Drag from anywhere on either scenario track, including touch. Native keys still work.
for(const id of ['ppRate','ppMissed']){
 const range=$(id);let pointer=null;
 const update=e=>{const rect=range.getBoundingClientRect(),inset=8,ratio=Math.max(0,Math.min(1,(e.clientX-rect.left-inset)/(rect.width-2*inset))),step=Number(range.step)||1;range.value=Number(range.min)+Math.round(ratio*(Number(range.max)-Number(range.min))/step)*step;range.dispatchEvent(new Event('input',{bubbles:true}));};
 range.addEventListener('pointerdown',e=>{if(e.button!==0)return;e.preventDefault();pointer=e.pointerId;range.focus({preventScroll:true});range.setPointerCapture(pointer);update(e);});
 range.addEventListener('pointermove',e=>{if(e.pointerId===pointer)update(e);});
 for(const event of ['pointerup','pointercancel','lostpointercapture'])range.addEventListener(event,()=>{pointer=null;});
}
