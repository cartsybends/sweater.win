// Original pixel scenery. Animation is derived from frame time, without timers
// or game state, so reduced motion and background exports stay deterministic.
export const DEEP_CUT_SCENERY=(()=>{
  const layouts=new Map();
  const mod=(n,d)=>((n%d)+d)%d;
  const mix=(a,b,t)=>a+(b-a)*Math.max(0,Math.min(1,t));
  const skateProfiles=[
    // Run, brake, settle (ms), peak rink speed (pixels/s), stride cycles/s.
    [1800,200,200,68,2.4],[1700,220,220,90,2.9],[1550,250,240,128,3.5],
    [1400,300,280,190,4.3],[1200,430,340,290,5.3],[1050,560,420,390,6.5],
  ];
  const smooth=t=>{t=Math.max(0,Math.min(1,t));return t*t*(3-2*t);};
  function skateMotion(score,elapsed,still=false){
    const level=[10,15,30,60,85,100].indexOf(score)+1;
    const idle={level,phase:'idle',duration:0,runMs:0,brakeMs:0,progress:1,distanceRatio:1,speed:0,travelPixels:0,cadence:0,swing:0,bob:0,lean:0,turn:0,shift:0,stopMs:-1,hardStop:false,done:true};
    if(!level||still)return idle;
    const [runMs,brakeMs,settleMs,peak,cadence]=skateProfiles[level-1],duration=runMs+brakeMs+settleMs;
    const t=Math.max(0,elapsed),pushMs=Math.min(220,runMs*.2),brake=Math.max(0,Math.min(brakeMs,t-runMs));
    const run=Math.min(t,runMs),integral=run<pushMs?run*run/(2*pushMs):run-pushMs/2;
    const travel=integral+brake-brake*brake/(2*brakeMs),total=runMs-pushMs/2+brakeMs/2;
    const ratio=t<runMs?Math.min(1,t/pushMs):Math.max(0,1-(t-runMs)/brakeMs);
    const done=t>=duration,phase=done?'idle':t<pushMs?'push':t<runMs?'sprint':t<runMs+brakeMs?'brake':'settle';
    const hardStop=level>=5,stopMs=t>=runMs?t-runMs:-1;
    const turn=hardStop&&stopMs>=0?smooth(stopMs/(brakeMs*.6))*(1-smooth((stopMs-brakeMs)/settleMs)):0;
    const swing=t<runMs?Math.sin(travel/1000*cadence*Math.PI*2):Math.sin((runMs-pushMs/2)/1000*cadence*Math.PI*2)*(1-smooth((t-runMs)/100));
    return {level,phase,duration,runMs,brakeMs,progress:Math.min(1,t/duration),distanceRatio:Math.min(1,travel/total),speed:peak*ratio,
      travelPixels:peak*travel/1000,cadence:cadence*ratio,swing,bob:Math.abs(swing)*(level>=4?2:1),
      lean:(1+level)*ratio-3*turn,turn,shift:6*ratio-3*turn,stopMs,hardStop,done};
  }
  function pixelLine(paint,x1,y1,x2,y2,width,color){
    const steps=Math.max(1,Math.ceil(Math.max(Math.abs(x2-x1),Math.abs(y2-y1))));
    for(let i=0;i<=steps;i++)paint(mix(x1,x2,i/steps),mix(y1,y2,i/steps),width,width,color);
  }
  function skater(paint,{x,foot,zone,motion=skateMotion(0,0)}){
    const m=motion,turn=m.turn,y=foot-39,crouch=turn*3,bob=m.bob+crouch,gold=zone===4;
    const alpha=(hex,value)=>hex+Math.round(Math.max(0,Math.min(1,value))*255).toString(16).padStart(2,'0');
    paint(x-6,foot+1,35,3,'#315a6a55');
    if(m.speed>5&&m.phase!=='brake'){
      for(let i=0;i<4+m.level*2;i++){
        const t=mod(m.travelPixels/24+i*.137,1);
        paint(x-4-t*(10+m.level*5),foot-1-t*(2+m.level),1+i%2,1,'#ecfff199');
      }
    }
    if(m.hardStop&&m.stopMs>=0&&!m.done){
      const legendary=m.level===6,count=legendary?84:42,seconds=m.stopMs/1000;
      for(let i=0;i<count;i++){
        const seed=mod(i*37,101)/100,birth=i%7*.025,age=seconds-birth,life=Math.min(.38+seed*.4,(m.duration-m.runMs)/1000-birth-.04);
        if(age<0||age>life)continue;
        const angle=-Math.PI*(.14+mod(i*19,83)/100),velocity=(legendary?85:58)*(1+seed);
        const px=x+12+Math.cos(angle)*velocity*age,py=foot-2+Math.sin(angle)*velocity*age+85*age*age;
        paint(px,Math.min(foot+1,py),i%5===0?3:1+i%2,1+i%3,alpha(i%3?'#edfff8':'#b8e2ed',1-age/life));
      }
      const fade=Math.max(0,1-m.stopMs/(m.brakeMs+300));
      pixelLine(paint,x-9,foot+3,x+11,foot-2,1,alpha('#f4fff6',fade));
      pixelLine(paint,x+8,foot+4,x+28,foot-1,1,alpha('#f4fff6',fade));
    }
    const px=(dx,dy,w,h,fill)=>paint(x+dx+m.lean*Math.max(0,1-dy/30),y+dy+bob,w,h,fill);
    px(3,0,9,2,'#ece9ce');px(1,2,13,6,'#e4e7cf');px(3,3,8,2,'#f7f3d7');
    if(turn>.45){px(4,6,8,4,'#d7ad8d');px(3,5,10,2,'#24384d');px(6,7,1,1,'#24384d');px(10,7,1,1,'#24384d');}
    else {px(12,5,3,5,'#d7ad8d');px(11,5,2,2,'#24384d');px(12,10,2,2,'#c89f81');}
    px(2,8,9,4,'#233c50');px(-1-turn,12,15+turn*2,12,gold?'#e5b861':'#64c9c2');px(2,13,8,9,gold?'#ffdb82':'#8ce3d0');px(0,18,13,2,'#eef1d8');px(3,15,3,4,'#244c54');px(7,15,2,4,'#244c54');
    px(-5-turn*2,13,5,5,'#5ab9b6');px(-7-turn*2,18,6,4,'#253c50');px(12,13,6,5,'#7bd5c6');px(16-turn*3,17,5,5,'#263d51');px(18-turn*3,18,4,2,'#e4ddc2');
    px(0,24,13,5,'#233e53');
    for(let i=0;i<2;i++){
      const swing=m.swing*(i?-1:1),hip=x+(i?9:2),knee=x+(i?10:1)+swing*3;
      const boot=mix(x+(i?10:0)+swing*9,x+(i?16:-6),turn),lift=(1-turn)*Math.max(0,-swing)*3;
      pixelLine(paint,hip,y+27+bob,knee,y+31+bob,4,i?'#29455a':'#20394e');
      pixelLine(paint,knee,y+31+bob,boot+2,foot-5-lift,3,i?'#29455a':'#20394e');
      pixelLine(paint,boot,foot-4-lift,boot+6,foot-4-lift-turn*3,3,'#e9ebd4');
      pixelLine(paint,boot-1,foot-lift,boot+9,foot-lift-turn*4,1,'#243b4c');
    }
    const bladeX=x+33-turn*12,bladeY=foot-3;
    pixelLine(paint,x+20+m.lean*.3-turn*3,y+22+bob,bladeX,bladeY,2,'#b49d76');
    paint(bladeX,bladeY,10,2,'#eee9cd');paint(bladeX,bladeY+2,11,1,'#65717a');paint(bladeX+2,bladeY,1,2,'#83929b');paint(bladeX+6,bladeY,1,2,'#83929b');
    // The caller draws one puck at this toe, always resting on the ice.
    return {x:bladeX+13,y:foot};
  }
  const glyphs={A:'010101111101101',B:'110101110101110',C:'011100100100011',D:'110101101101110',E:'111100110100111',F:'111100110100100',I:'111010010010111',K:'101101110101101',L:'100100100100111',M:'101111111101101',N:'101111111111101',O:'010101101101010',P:'110101110100100',R:'110101110101101',S:'011100010001110',T:'111010010010010',U:'101101101101111',V:'101101101101010',W:'101101111111101',X:'101101010101101',Z:'111001010100111'};
  Object.assign(glyphs,{G:'011100101101011',H:'101101111101101',J:'001001001101010',Q:'010101101111011',Y:'101101010010010','0':'111101101101111','1':'010110010010111','2':'110001010100111','3':'110001010001110','4':'101101111001001','5':'111100110001110','6':'011100111101111','7':'111001010010010','8':'111101111101111','9':'111101111001110',' ':'000000000000000','/':'001001010100100','-':'000000111000000','+':'000010111010000',':':'000010000010000','%':'101001010100101'});
  function word(paint,text,x,y,color){
    [...text].forEach((letter,i)=>{const glyph=glyphs[letter]||glyphs.X;for(let j=0;j<15;j++)if(glyph[j]==='1')paint(x+i*4+j%3,y+Math.floor(j/3),1,1,color);});
  }
  function ring(paint,x,y,rx,ry,color){
    const count=Math.max(64,Math.ceil(rx*6));
    for(let i=0;i<=count;i++){const a=i/count*Math.PI*2;paint(x+Math.cos(a)*rx,y+Math.sin(a)*ry,1,1,color);}
  }
  function windowState(seed,time,still=false){
    if(still)return {lit:seed%3!==0,person:seed%17===0,figureX:2,blind:seed%11===0?.5:0,stage:'still'};
    const cycle=55+mod(seed*13,37),phase=mod(time/1000+seed*11.3,cycle),visitor=seed%4===0,closes=seed%8===0;
    const lit=phase<(visitor?35:23+seed%13);
    const person=visitor&&phase>=10&&phase<24;
    const figureX=phase<12?mix(-2,2,(phase-10)/2):phase<20||closes?2:mix(2,7,(phase-20)/4);
    const blind=visitor&&closes&&phase>=20&&phase<35?Math.min(1,(phase-20)/4):0;
    const stage=!lit?'off':!person?blind?'closed':'lit':phase<12?'arriving':phase<20?'watching':closes?'closing-blinds':'leaving';
    return {lit,person,figureX,blind,stage};
  }
  function houseWindow(paint,{x,y,seed,time,still}){
    const state=windowState(seed,time,still);
    paint(x-1,y-1,8,8,'#1c3847');paint(x,y,6,6,state.lit?'#e4ce95':'#486a79');paint(x+1,y,4,1,state.lit?'#f2dda6':'#5c7d87');
    const clipped=(px,py,w,h,color)=>{const left=Math.max(x,px),top=Math.max(y,py),right=Math.min(x+6,px+w),bottom=Math.min(y+6,py+h);if(right>left&&bottom>top)paint(left,top,right-left,bottom-top,color);};
    if(state.person&&state.lit){const px=x+Math.round(state.figureX);clipped(px,y+1,2,2,'#273b44');clipped(px-1,y+3,4,3,'#304751');}
    if(state.blind){const h=Math.ceil(6*state.blind);paint(x,y,6,h,state.lit?'#aaab94':'#647d83');for(let row=1;row<h;row+=2)paint(x,y+row,6,1,'#6c817f');}
    if(!state.person&&!state.blind)paint(x+3,y,1,6,'#6c8585');paint(x-1,y+6,8,1,'#a3bdbb');
  }
  function dogWalkerState(index,W,ice,time,still=false){
    const direction=index===0?1:-1,travel=mod((still?0:time/1000*(index?6:8))+W*(index?.63:.18),W+80)-40;
    const x=still?W*(index?.72:.2):direction===1?travel:W-travel;
    return {x,y:ice-7+index,direction,dogX:x+direction*13,step:still?0:Math.floor(time/180+index)%2};
  }
  function neighbourhoodWalkers(paint,{W,ice,time,still}){
    paint(0,ice-11,W,5,'#829fa3');paint(0,ice-11,W,1,'#adc7c5');
    for(let i=0;i<2;i++){
      const a=dogWalkerState(i,W,ice,time,still),x=a.x,y=a.y,d=a.direction,s=a.step,coat=i?'#957783':'#637e96';
      paint(x-2,y-15,4,4,'#c9ad90');paint(x-3,y-16,5,2,i?'#b3b59b':'#b9c3b6');paint(x+(d>0?1:-2),y-13,1,1,'#223847');
      paint(x-3,y-11,6,7,coat);paint(x-3,y-11,6,1,'#b8aa7e');paint(x+1,y-10,1,4,'#b8aa7e');paint(x+d*3,y-9,2,4,coat);
      paint(x-2-s,y-4,2,4,'#2a4051');paint(x+1+s,y-4,2,4,'#2a4051');paint(x-3-s,y,3,1,'#c2ccbf');paint(x+1+s,y,3,1,'#c2ccbf');
      const dog=a.dogX,fur=i?'#9f8c70':'#b8b1a0';
      for(let j=0;j<=12;j++)paint(mix(x+d*4,dog-d*2,j/12),mix(y-6,y-3,j/12),1,1,'#bebba0');
      paint(dog-3,y-4,7,3,fur);paint(dog+d*3-(d<0?2:0),y-6,3,3,fur);paint(dog+d*3,y-6,1,2,'#5b5650');paint(dog+d*5,y-4,1,1,'#303d44');
      paint(dog-d*5,y-5,2,1,fur);paint(dog-2-s,y-1,1,2,'#605e56');paint(dog+2+s,y-1,1,2,'#605e56');paint(dog+d*2,y-3,2,1,'#a66f72');
    }
  }
  function logo(paint,kind,x,y,color){
    if(kind==='cup'){paint(x+1,y+1,4,4,color);paint(x+5,y+2,2,2,color);paint(x,y+5,7,1,color);paint(x+2,y-1,1,1,color);paint(x+4,y-1,1,1,color);}
    else if(kind==='leaf'){paint(x+3,y,1,6,color);paint(x+1,y+1,5,2,color);paint(x,y+2,7,1,color);paint(x+2,y+3,3,2,color);}
    else if(kind==='skate'){paint(x+1,y,3,3,color);paint(x+1,y+2,6,2,color);paint(x,y+5,8,1,color);paint(x+2,y+4,1,1,color);paint(x+5,y+4,1,1,color);}
    else if(kind==='pizza'){for(let row=0;row<5;row++)paint(x+Math.floor(row/2),y+row,7-row,1,color);paint(x,y-1,7,1,color);paint(x+2,y+1,1,1,'#b46d66');paint(x+3,y+3,1,1,'#b46d66');}
    else if(kind==='mountain'){for(let row=0;row<5;row++){paint(x+3-row,y+row,2,1,color);paint(x+4+row,y+row,2,1,color);}paint(x+3,y,3,1,color);}
    else if(kind==='bolt'){paint(x+3,y,3,1,color);paint(x+2,y+1,3,2,color);paint(x+1,y+3,5,1,color);paint(x+3,y+4,2,2,color);}
    else {paint(x,y+1,7,1,color);paint(x+1,y,5,1,color);for(let i=1;i<6;i+=2)paint(x+i,y+2,1,3,color);paint(x,y+5,7,1,color);}
  }
  function ribbonMessage({score=0,round=1,over=false,lastScore=0}={}){
    score=Math.max(0,Math.min(700,Math.round(score)));round=Math.max(1,Math.min(7,round));
    const next=Math.min(700,(Math.floor(score/150)+1)*150),celebration=score===700?'PERFECT SHIFT':score>=600?'LEGENDS ONLY':score>=450?'UP IN THE RAFTERS':score>=300?'THE BIG LEAGUES':'KEEP SKATING';
    const goal=score===700?'PERFECT 700':over?'TRY ANOTHER SHIFT':score<600?'NEXT ARENA '+next:'CHASE 700';
    return `${over?'SHIFT COMPLETE':'ROUND '+round+' OF 7'} / ${score} POINTS / ${score*10} M SKATED / ${goal} / ${lastScore>=60?'DEEP CUT +'+lastScore+' / ':''}${celebration}`;
  }
  function ribbon(paint,{W,y,time,still,zone,progress={}}){
    const gold=zone===4,purple=zone===3,background=gold?'#70532c':purple?'#50366c':'#155b71',ink=gold?'#ffdf95':purple?'#dec9f7':'#a6eced',message=ribbonMessage(progress),span=message.length*4+28,shift=still?0:mod(time*.012,span);
    paint(0,y-1,W,11,'#0a1728');paint(0,y,W,8,background);paint(0,y,W,1,ink);paint(0,y+7,W,1,'#31465b');
    for(let x=2;x<W;x+=4)paint(x,y+1,1,5,'#ffffff08');
    for(let x=-shift;x<W;x+=span){word(paint,message,x+3,y+2,ink);logo(paint,'bolt',x+span-15,y+2,ink);}
    paint(0,y+7,W*Math.max(0,Math.min(1,(progress.score||0)/700)),1,ink);
  }
  function person(paint,x,y,seed,{pose='sit',carry=null,time=0,zone=1,cheer=0}={}){
    const rise=Math.round(cheer*2),head=y-(pose==='sit'?11:15)-rise,step=pose==='walk'?Math.floor(time/160+seed)%2:0;
    const skin=['#deb995','#af866e','#edc9aa','#946c58'][mod(seed,4)],hair=['#443b37','#8b7051','#302f36','#af9470'][mod(seed*3,4)];
    const shirt=(zone===4?['#bd984e','#647d91','#b19b7c','#7d6385']:zone===3?['#9278ab','#687fa4','#b6808a','#5d999d']:['#6895a5','#b17c83','#6f9c91','#8e87ad','#b79568'])[mod(seed,zone>=3?4:5)];
    paint(x-2,head,4,4,skin);paint(x-2,head,4,1,hair);paint(x+1,head+2,1,1,'#1b2937');
    if(seed%3===0){paint(x-3,head-1,5,2,shirt);paint(x+2,head,2,1,shirt);}else paint(x-2,head+1,1,2,hair);
    paint(x-3,head+4,6,5,shirt);paint(x-3,head+7,6,1,seed%2?'#dce6d7':'#304b61');paint(x-1,head+5,1,2,'#cbd8c5');
    if(pose==='cheer'){paint(x-4,head-1,1,7,shirt);paint(x+3,head-1,1,7,shirt);paint(x-5,head-3,2,2,skin);paint(x+3,head-3,2,2,skin);}
    else {paint(x-4,head+5,1,4,shirt);paint(x+3,head+5,1,4,shirt);paint(x-4,head+8,1,1,skin);paint(x+3,head+8,1,1,skin);}
    if(pose==='sit'){paint(x-3,y-2,3,2,'#243a50');paint(x+1,y-2,3,2,'#243a50');paint(x-3,y,3,1,'#a9b9be');paint(x+2,y,3,1,'#a9b9be');}
    else {paint(x-2-step,head+9,2,6+rise,'#263b51');paint(x+1+step,head+9,2,6+rise,'#30465d');paint(x-3-step,y,3,1,'#adbfc2');paint(x+1+step,y,3,1,'#adbfc2');}
    if(carry==='popcorn'){paint(x+4,head+6,3,4,'#b8615f');paint(x+5,head+6,1,4,'#f2e3ba');paint(x+3,head+4,5,2,'#e7cf86');paint(x+4,head+3,1,1,'#fff0b8');paint(x+6,head+4,1,1,'#fff0b8');}
    if(carry==='drink'){paint(x+4,head+6,3,4,'#91bbc7');paint(x+4,head+5,3,1,'#edf0da');paint(x+5,head+2,1,4,'#d8cf9d');paint(x+5,head+2,2,1,'#d8cf9d');}
  }
  function communityActor(index,W,ice,time,still=false){
    const seatX=W*[.16,.48,.86][index],seatY=ice-[12,26,19][index],aisleX=W*[.28,.62,.72][index],walkY=ice-39,doorX=W*.82+7;
    const t=still?0:mod(time/1000+index*17,64),result={x:seatX,y:seatY,pose:'sit',visible:true,stage:'seated'};
    const walk=(x,y,stage)=>Object.assign(result,{x,y,pose:'walk',stage});
    if(t<14)return result;
    if(t<18)return {...result,pose:'stand',stage:'standing'};
    if(t<23)return walk(mix(seatX,aisleX,(t-18)/5),seatY,'to-aisle');
    if(t<28)return walk(aisleX,mix(seatY,walkY,(t-23)/5),'up-steps');
    if(t<40)return walk(mix(aisleX,doorX,(t-28)/12),walkY,'to-door');
    if(t<49)return {...result,x:doorX,y:walkY,visible:false,stage:'outside'};
    if(t<57)return walk(mix(doorX,aisleX,(t-49)/8),walkY,'returning');
    if(t<60)return walk(aisleX,mix(walkY,seatY,(t-57)/3),'down-steps');
    if(t<63)return walk(mix(aisleX,seatX,(t-60)/3),seatY,'to-seat');
    return {...result,pose:'stand',stage:'sitting-down'};
  }
  function vendingLit(index,time,still=false){const phase=mod(time/1000,19);return still||index!==1||!(phase>=14.1&&phase<14.4||phase>=14.9&&phase<15.2);}
  function vending(paint,x,base,index,time,still){
    const lit=vendingLit(index,time,still),body=['#714b58','#425d72','#686f68'][index];
    paint(x,base-26,13,26,'#182b3c');paint(x+1,base-25,11,24,body);paint(x+2,base-24,9,3,'#b4c8bf');
    paint(x+2,base-20,7,15,lit?'#b6d1ba':'#4c6265');paint(x+3,base-19,5,13,lit?'#5d7b78':'#30474e');
    for(let row=0;row<4;row++){paint(x+3,base-16+row*3,5,1,lit?'#a5b5a5':'#5d7072');for(let col=0;col<2;col++)if((index+row*2+col)%4!==1)paint(x+3+col*3,base-19+row*3,2,2,['#c19e62','#a76f73','#899f80'][(row+col)%3]);}
    paint(x+10,base-17,1,2,'#c6cab1');paint(x+10,base-12,1,1,lit?'#b8d895':'#6c7e76');paint(x+3,base-4,6,2,'#102735');paint(x+1,base-1,2,1,'#a6b2a9');paint(x+10,base-1,2,1,'#a6b2a9');
  }
  function community(paint,{W,ice,time,still}){
    paint(0,30,W,ice-30,'#213747');paint(0,48,W,ice-82,'#2a4351');paint(0,ice-36,W,25,'#304a57');
    paint(0,28,W,4,'#637684');paint(0,43,W,2,'#415966');
    for(let x=0;x<W+65;x+=65)for(let j=0;j<8;j++){paint(x+j*4,32+j,4,1,'#566c7b');paint(x+32+j*4,39-j,4,1,'#566c7b');}
    for(let x=0;x<W;x+=54){paint(x,57,1,Math.max(1,ice-94),'#385361');paint(x+6,ice-70,31,1,'#46616e');}
    paint(0,ice-41,W,9,'#47616b');paint(0,ice-41,W,1,'#718791');
    const actors=[0,1,2].map(i=>communityActor(i,W,ice,time,still)),doorX=W*.82,doorOpen=actors.some(p=>p.visible&&Math.abs(p.x-(doorX+7))<5&&Math.abs(p.y-(ice-39))<2);
    paint(doorX,ice-70,15,32,'#102638');paint(doorX+1,ice-69,13,30,doorOpen?'#8eac9b':'#304c5b');paint(doorX+3,ice-65,9,10,doorOpen?'#c4ccaa':'#77949c');paint(doorX+11,ice-47,1,2,'#d3d1af');paint(doorX-1,ice-72,17,2,'#a8b8ad');paint(doorX+5,ice-75,5,2,'#9dc5a2');
    for(let i=0;i<3;i++)vending(paint,9+i*16,ice-41,i,time,still);
    for(let row=3;row>=0;row--){
      const y=ice-10-row*7;paint(0,y,W,5,'#293f4e');
      for(let i=0;i<Math.ceil(W/24);i++){
        const x=i*24,broken=(i+row*5)%13===4;
        paint(x,y,broken?9:23,2,'#929181');paint(x,y+2,broken?9:23,1,'#657573');
        if(broken){paint(x+15,y+1,7,2,'#7d8175');paint(x+11,y+3,3,1,'#a59d83');}
        else {paint(x+4+(i%3)*3,y,2,1,'#c0b69b');paint(x+15,y+1,3,1,'#596a67');}
        paint(x+3,y+3,1,2,'#566875');paint(x+20,y+3,1,2,'#566875');
      }
      for(const fraction of [.28,.62,.72]){const x=W*fraction-4;paint(x,y,9,5,'#526a75');paint(x,y,9,1,'#bdc8bd');}
    }
    for(const [i,actor] of actors.entries())if(actor.visible)person(paint,actor.x,actor.y,9+i*7,{pose:actor.pose,time,zone:1});
    paint(0,ice-20,W,20,'#a4d3de10');paint(0,ice-20,W,1,'#8faeba88');for(let x=0;x<W;x+=36)paint(x,ice-20,1,20,'#80a5b277');
  }
  function arenaLayout(W,ice,zone=2){
    const key=`${W}:${ice}:${zone}`;if(layouts.has(key))return layouts.get(key);
    const compact=ice<160,pitch=compact?7:11,lowerRows=compact?3:4,upperRows=compact?2:4,sectionWidth=W<240?62:84;
    const lowerBottom=ice-10,lowerTop=lowerBottom-(lowerRows-1)*pitch,walkY=lowerTop-(compact?8:12),ribbonY=walkY-(compact?16:22),upperBottom=ribbonY-8,upperTop=upperBottom-(upperRows-1)*pitch,upperWalkY=upperTop-(compact?8:13);
    const sections=[],seats=[];
    for(let s=0;s<Math.ceil(W/sectionWidth);s++){
      const start=s*sectionWidth,aisle=start+sectionWidth-5,door=start+sectionWidth*.5;
      if(start>W-15)continue;sections.push({index:s,start,aisle,door});
      for(const [bowl,rows,bottom] of [[0,lowerRows,lowerBottom],[1,upperRows,upperBottom]])for(let row=0;row<rows;row++)for(let col=0;col<Math.floor((sectionWidth-15)/10);col++){
        const x=start+10+col*10;if(x>W-5)continue;
        const seed=s*37+row*13+col*7+bowl*19;
        seats.push({id:`${bowl}:${s}:${row}:${col}`,bowl,section:s,row,col,x,y:bottom-row*pitch,seed,occupied:true});
      }
    }
    seats.sort((a,b)=>a.y-b.y||a.x-b.x);
    for(const bowl of [0,1]){
      const rowSeats=seats.filter(seat=>seat.bowl===bowl),empty=zone===4?0:Math.round(rowSeats.length*(zone===3?.125:.25));
      rowSeats.forEach((seat,index)=>{seat.occupied=Math.floor((index+1)*empty/rowSeats.length)===Math.floor(index*empty/rowSeats.length);});
    }
    const travellers=[];
    for(const section of sections)for(const bowl of [0,1]){
      if(section.index%2!==0||bowl===1&&section.index%4!==0)continue;
      const seat=seats.find(p=>p.section===section.index&&p.bowl===bowl&&p.row===1&&p.col>=2&&p.occupied);
      if(seat)travellers.push({...seat,aisle:section.aisle,door:section.door,walkY:bowl===0?walkY:upperWalkY,traveller:travellers.length});
    }
    // Sold-out seats stay filled; extra visitors use the aisles. The rafters
    // similarly limit vacant seats during trips so their occupancy stays high.
    const seatedTrips=Math.max(0,Math.floor(seats.filter(seat=>seat.occupied).length-seats.length*(zone===4?1:zone===3?.85:.7)+1e-9));
    travellers.forEach((seat,index)=>{if(index>=seatedTrips)Object.assign(seat,{x:seat.aisle,seed:seat.seed+101,standingRoom:true});});
    const result={W,ice,pitch,lowerRows,upperRows,lowerBottom,lowerTop,walkY,ribbonY,upperBottom,upperTop,upperWalkY,sections,seats,travellers};
    if(layouts.size>=8)layouts.clear();layouts.set(key,result);return result;
  }
  function arenaActor(seat,time,still=false){
    const t=still?0:mod(time/1000+seat.traveller*13,64),result={x:seat.x,y:seat.y,pose:seat.standingRoom?'stand':'sit',visible:true,stage:seat.standingRoom?'watching':'seated',carry:null};
    const carry=seat.seed%2?'popcorn':'drink',walk=(x,y,stage,snack=null)=>Object.assign(result,{x,y,pose:'walk',stage,carry:snack});
    if(t<18)return result;
    if(t<22)return {...result,pose:'stand',stage:'standing'};
    if(t<27)return seat.standingRoom?result:walk(mix(seat.x,seat.aisle,(t-22)/5),seat.y,'to-aisle');
    if(t<32)return walk(seat.aisle,mix(seat.y,seat.walkY,(t-27)/5),'up-steps');
    if(t<36)return walk(mix(seat.aisle,seat.door,(t-32)/4),seat.walkY,'to-concourse');
    if(t<45)return {...result,x:seat.door,y:seat.walkY,visible:false,stage:'concessions'};
    if(t<49)return walk(mix(seat.door,seat.aisle,(t-45)/4),seat.walkY,'returning',carry);
    if(t<54)return walk(seat.aisle,mix(seat.walkY,seat.y,(t-49)/5),'down-steps',carry);
    if(t<59)return walk(mix(seat.aisle,seat.x,(t-54)/5),seat.y,'to-seat',carry);
    return {...result,carry};
  }
  function waveLift(seat,W,time,wave){
    if(!wave)return 0;
    const pulse=(time-wave.start)/1000-seat.x/W*3.2-seat.bowl*.65-seat.row*.06;
    return pulse>0&&pulse<1.25?Math.sin(pulse/1.25*Math.PI):0;
  }
  function arena(paint,{W,ice,time,still,zone,wave=null,progress={}}){
    const layout=arenaLayout(W,ice,zone),gold=zone===4,purple=zone===3,wall=gold?'#30283a':purple?'#25243f':'#152c43',metal=gold?'#766046':purple?'#565073':'#425a71';
    paint(0,30,W,ice-30,wall);paint(0,29,W,3,metal);
    for(let x=0;x<W;x+=60){paint(x,31,2,Math.max(4,layout.upperWalkY-48),metal);paint(x,31,61,2,metal);for(let j=0;j<6;j++)paint(x+j*10,33+j*2,2,2,metal);}
    if(zone>=3&&ice>=160)for(let x=14;x<W;x+=45){paint(x,44,16,25,gold?'#9d783d':'#675785');paint(x+2,46,12,20,gold?'#d1aa56':'#9682bb');paint(x+6,51,4,10,'#202b43');paint(x+4,68,8,2,gold?'#d9c486':'#b4a2c6');}
    for(const [bowl,rows,bottom,walkY] of [[1,layout.upperRows,layout.upperBottom,layout.upperWalkY],[0,layout.lowerRows,layout.lowerBottom,layout.walkY]]){
      paint(0,walkY-1,W,5,gold?'#5e5353':purple?'#4a4862':'#435a6e');paint(0,walkY,W,1,'#82949e');
      for(const section of layout.sections){paint(section.door-5,walkY-15,11,15,'#091a2b');paint(section.door-6,walkY-16,13,2,metal);paint(section.door-2,walkY-18,5,1,gold?'#c7b47b':'#8eb1a5');}
      for(let row=rows-1;row>=0;row--){const y=bottom-row*layout.pitch;paint(0,y,W,3,gold?'#4c4455':purple?'#393d5b':'#2b435b');paint(0,y,W,1,gold?'#7d705f':'#65798a');}
      for(const section of layout.sections){
        for(let row=0;row<rows;row++){const y=bottom-row*layout.pitch;paint(section.aisle-4,y-layout.pitch+2,9,layout.pitch,gold?'#68636b':purple?'#5d6075':'#607789');paint(section.aisle-4,y,9,1,'#9aa9ac');}
        paint(section.aisle+4,walkY-3,1,bottom-walkY+4,'#8a9ca4');
      }
    }
    ribbon(paint,{W,y:layout.ribbonY,time,still,zone,progress});
    const actors=layout.travellers.map(seat=>({seat,actor:arenaActor(seat,time,still)})),travellers=new Map(actors.filter(({seat})=>!seat.standingRoom).map(p=>[p.seat.id,p]));
    for(const seat of layout.seats){
      paint(seat.x-3,seat.y-5,6,4,gold?'#635264':purple?'#4a4266':'#39576e');paint(seat.x-2,seat.y-5,4,1,gold?'#87715e':'#638293');
      const traveller=travellers.get(seat.id);if(!seat.occupied||traveller&&(!traveller.actor.visible||traveller.actor.pose!=='sit'))continue;
      const cheer=still?0:waveLift(seat,W,time,wave);
      person(paint,seat.x,seat.y,seat.seed,{zone,pose:cheer>.15?'cheer':'sit',cheer,carry:cheer>.15?null:traveller?.actor.carry||(seat.seed%13===0?'popcorn':seat.seed%17===0?'drink':null),time:still?0:time});
    }
    for(const {seat,actor} of actors)if(actor.visible&&actor.pose!=='sit')person(paint,actor.x,actor.y,seat.seed,{pose:actor.pose,carry:actor.carry,time:still?0:time,zone});
    paint(0,ice-8,W,1,'#8aa7b6');for(let x=0;x<W;x+=38)paint(x,ice-8,1,8,'#7d9aa688');
    if(gold)for(let i=0;i<18;i++){const x=(i*47+20)%W,y=40+(i*23)%Math.max(1,layout.upperTop-50);paint(x,y,1,5,'#e7c87588');paint(x-2,y+2,5,1,'#e7c87588');}
    return layout;
  }
  function boards(paint,{W,ice,zone,offset}){
    if(zone===0){
      paint(0,ice,W,11,'#745b48');
      for(let row=0;row<3;row++){
        const y=ice+1+row*3;paint(0,y,W,2,['#a68b67','#947957','#b09570'][row]);
        for(let i=0;i<Math.ceil(W/30)+2;i++){const x=mod(i*31-offset*.6,W+62)-31;paint(x,y,1,2,'#4d4941');paint(x+3,y,4+i%5,1,'#c0a57d');paint(x+16,y+1,6,1,'#766249');if((i+row)%4===0)paint(x+11,y,2,2,'#5e5445');}
      }
      for(let i=0;i<Math.ceil(W/36)+2;i++){const x=mod(i*37-offset*.6,W+74)-37;paint(x,ice-1,3,12,'#66513f');paint(x+1,ice+1,1,1,'#b7b8a0');paint(x+1,ice+7,1,1,'#a4ab9b');if(i%3===0)paint(x+4,ice,9,1,'#d7e4d6');}
      paint(0,ice,W,1,'#b0a38b');return;
    }
    paint(0,ice,W,2,'#a7c4cc');paint(0,ice+2,W,8,zone===1?'#cbd7cd':'#dce8e4');paint(0,ice+10,W,1,'#d4ae5f');
    if(zone===1){for(let x=16;x<W;x+=53){paint(x,ice+5,14,1,'#8ca49e');paint(x+5,ice+7,7,1,'#b3beb1');}return;}
    const ads=[['MAPLE','leaf'],['COFFEE','cup'],['NORTH','mountain'],['PIZZA','pizza'],['SKATES','skate'],['ZORP','bolt'],['HOME ICE','mountain'],['BANK','bank'],['FROST','bolt'],['','leaf']];
    for(let i=0;i<Math.ceil(W/59)+2;i++){
      const x=mod(i*59-offset*.6,W+118)-59,color=['#557e93','#926577','#538b83','#8b724d'][i%4],[label,icon]=ads[i%ads.length];
      paint(x,ice+2,1,8,'#a4b8bb');logo(paint,icon,x+(label?5:25),ice+3,color);if(label)word(paint,label,x+16,ice+3,color);
    }
  }
  function iceSurface(paint,{W,H,ice,zone,offset}){
    const top=ice+11,depth=H-top,rough=zone===0;
    paint(0,top,W,depth,rough?'#9dbdbf':zone===4?'#c3d5ce':zone===3?'#b8cedb':'#bdd8df');
    if(rough){
      for(let i=0;i<35;i++){const x=mod(i*83-offset*1.2,W+40)-20,y=top+4+i*17%Math.max(1,depth-6);paint(x,y,7+i%20,2+i%3,i%2?'#b3ceca66':'#749da344');}
      for(let i=0;i<170;i++){const x=mod(i*73-offset*1.2,W+40)-20,y=top+2+i*19%Math.max(1,depth-3),length=3+i%16;paint(x,y,length,1,i%3?'#d3e4d466':'#59848e55');if(i%4===0)paint(x+length,y-1,3,1,'#d3e4d466');}
      for(let i=0;i<Math.ceil(W/9);i++){const x=mod(i*11-offset*.9,W+22)-11;paint(x,top,4+i%5,1+i%3,'#d6e3d4');}return;
    }
    for(let i=0;i<65;i++){const x=mod(i*73-offset*1.2,W+40)-20,y=top+3+i*7%Math.max(1,depth-3);paint(x,y,5+i%14,1,i%2?'#e9f2e055':'#8eb3bf33');}
    const period=Math.max(320,W*1.25),shift=mod(offset*1.2,period),cy=top+depth*.5,rx=Math.min(38,W*.085),ry=Math.max(4,depth*.176);
    for(let repeat=-1;repeat<=2;repeat++){
      const center=W/2-shift+repeat*period;
      if(center+period*.5<-4||center-period*.5>W+4)continue;
      for(const [x,color,width] of [[center,'#b86f7c99',2],[center-period*.25,'#608bb199',3],[center+period*.25,'#608bb199',3]])if(x>-10&&x<W+10)for(let y=top;y<H;y++)paint(center+(x-center)*(.88+(y-top)/Math.max(1,depth)*.24),y,width,1,color);
      if(center+rx>=0&&center-rx<=W){ring(paint,center,cy,rx,ry,'#638cafaa');paint(center-1,cy-1,3,2,'#4f799a');}
      for(const side of [-1,1]){
        for(const across of [-1,1]){
          const faceY=cy+across*depth*.26,neutralX=center+side*period*.2;
          if(neutralX>=0&&neutralX<W)paint(neutralX-1,faceY-1,2,2,'#b87984');
          const x=center+side*period*.4;if(x+rx<0||x-rx>W)continue;
          ring(paint,x,faceY,rx,ry,'#ac697b88');paint(x-1,faceY-1,2,2,'#b87984');
          for(const sign of [-1,1]){paint(x-rx-2,faceY+sign*3,4,1,'#ac697b88');paint(x+rx-1,faceY+sign*3,4,1,'#ac697b88');}
        }
      }
    }
  }
  return Object.freeze({skateMotion,skater,windowState,houseWindow,dogWalkerState,neighbourhoodWalkers,ribbonMessage,ribbon,communityActor,vendingLit,community,arenaLayout,arenaActor,waveLift,arena,boards,iceSurface,ring});
})();
