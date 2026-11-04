// Original pixel scenery. Animation is derived from frame time, without timers
// or game state, so reduced motion and background exports stay deterministic.
export const DEEP_CUT_SCENERY=(()=>{
  const layouts=new Map();
  const mod=(n,d)=>((n%d)+d)%d;
  const mix=(a,b,t)=>a+(b-a)*Math.max(0,Math.min(1,t));
  const glyphs={A:'010101111101101',B:'110101110101110',C:'011100100100011',D:'110101101101110',E:'111100110100111',F:'111100110100100',I:'111010010010111',K:'101101110101101',L:'100100100100111',M:'101111111101101',N:'101111111111101',O:'010101101101010',P:'110101110100100',R:'110101110101101',S:'011100010001110',T:'111010010010010',U:'101101101101111',V:'101101101101010',W:'101101111111101',X:'101101010101101',Z:'111001010100111'};
  function word(paint,text,x,y,color){
    [...text].forEach((letter,i)=>{const glyph=glyphs[letter]||glyphs.X;for(let j=0;j<15;j++)if(glyph[j]==='1')paint(x+i*4+j%3,y+Math.floor(j/3),1,1,color);});
  }
  function ring(paint,x,y,rx,ry,color){
    const count=Math.max(64,Math.ceil(rx*6));
    for(let i=0;i<=count;i++){const a=i/count*Math.PI*2;paint(x+Math.cos(a)*rx,y+Math.sin(a)*ry,1,1,color);}
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
  function arena(paint,{W,ice,time,still,zone,wave=null}){
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
    const ribbon=gold?'#70532c':purple?'#50366c':'#155b71',ink=gold?'#ffdf95':purple?'#dec9f7':'#a6eced';
    paint(0,layout.ribbonY-1,W,11,'#0a1728');paint(0,layout.ribbonY,W,8,ribbon);paint(0,layout.ribbonY,W,1,ink);paint(0,layout.ribbonY+7,W,1,ink);
    const advert=still?0:Math.floor(time/9000)%3;
    for(let x=3,i=0;x<W;x+=45,i++){word(paint,['NIVO','VEXA','ZORP'][(i+advert)%3],x+8,layout.ribbonY+2,ink);paint(x+40,layout.ribbonY+1,1,6,'#0d253a');}
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
    for(let i=0;i<Math.ceil(W/51)+2;i++){
      const x=mod(i*51-offset*.6,W+102)-51,color=['#557e93','#926577','#538b83','#8b724d'][i%4];
      paint(x,ice+2,1,8,'#a4b8bb');word(paint,['ZORP','VEXA','NIVO','FLIM'][i%4],x+9,ice+3,color);paint(x+35,ice+4,3,3,color);paint(x+39,ice+5,2,1,color);
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
  return Object.freeze({communityActor,vendingLit,community,arenaLayout,arenaActor,waveLift,arena,boards,iceSurface,ring});
})();
