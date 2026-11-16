export const PLAYOFF_FIELD=(()=>{
 const divisions={E:['Atlantic','Metropolitan'],W:['Central','Pacific']};
 const divisionCodes={Atlantic:'A',Metropolitan:'M',Central:'C',Pacific:'P'};
 const clinches={x:'Clinched a playoff berth',y:'Clinched the division',z:'Clinched the conference',p:'Clinched the Presidents’ Trophy'};
 function clinched(team){const code=String(team?.clinch||'').trim().toLowerCase();return clinches[code]?{code,label:clinches[code]}:null;}
 function field(teams){
  if(!Array.isArray(teams)||teams.length!==32||new Set(teams.map(t=>t.abbr)).size!==32||new Set(teams.map(t=>t.official_rank)).size!==32||teams.some(t=>!Number.isInteger(t.official_rank)||t.official_rank<1||t.official_rank>32||!divisions[t.conference]?.includes(t.division)))return null;
  const order=(a,b)=>a.official_rank-b.official_rank,matches=[],qualifiers=[],seeds={};
  for(const conference of ['E','W']){
   const members=teams.filter(t=>t.conference===conference),hasConferenceRanks=members.every(t=>Number.isInteger(t.conference_rank)&&t.conference_rank>=1&&t.conference_rank<=16)&&new Set(members.map(t=>t.conference_rank)).size===16;
   const confOrder=hasConferenceRanks?(a,b)=>a.conference_rank-b.conference_rank:order;
   const ranked=members.sort(confOrder),groups=divisions[conference].map(division=>{const group=ranked.filter(t=>t.division===division),complete=group.length===8&&group.every(t=>Number.isInteger(t.division_rank)&&t.division_rank>=1&&t.division_rank<=8)&&new Set(group.map(t=>t.division_rank)).size===8;return complete?group.sort((a,b)=>a.division_rank-b.division_rank):group;});
   if(ranked.length!==16||groups.some(g=>g.length!==8))return null;
   const automatic=new Set(groups.flatMap(g=>g.slice(0,3).map(t=>t.abbr))),wild=ranked.filter(t=>!automatic.has(t.abbr)).slice(0,2);
   for(const group of groups)group.slice(0,3).forEach((t,i)=>seeds[t.abbr]=divisionCodes[t.division]+(i+1));
   wild.forEach((t,i)=>seeds[t.abbr]='WC'+(i+1));
   // The better division winner gets WC2 even when both wild cards are from
   // its own division. Division runners-up play the third-place club.
   groups.sort((a,b)=>confOrder(a[0],b[0]));
   groups.forEach((group,index)=>{
    const division=group[0].division;
    for(const [round,pair] of [[1,[group[0],wild[index===0?1:0]]],[2,[group[1],group[2]]]]){
     matches.push({id:conference+'-'+divisionCodes[division]+'-'+round,conference,division,
      teams:pair.map(t=>({abbr:t.abbr,name:t.name,seed:seeds[t.abbr],points:t.points,gp:t.gp}))});
    }
   });
   qualifiers.push(...ranked.filter(t=>automatic.has(t.abbr)||wild.includes(t)).map(t=>t.abbr));
  }
  return {qualifiers,seeds,matches};
 }
 function geometry(matches){
  return matches.map((m,i)=>{const start=-Math.PI/2+i*Math.PI/4,end=start+Math.PI/4,angle=(start+end)/2;
   return {...m,start,end,angle,teams:m.teams.map((t,j)=>{const angle=start+(j+.5)*Math.PI/8;return {...t,angle,x:450+392*Math.cos(angle),y:450+392*Math.sin(angle)};})};
  });
 }
 return Object.freeze({field,clinched,geometry});
})();
