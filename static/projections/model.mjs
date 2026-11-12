// Shared pure arithmetic. Rates keep full precision until the view formats them.
export const POINT_PROJECTIONS=(()=>{
 const number=value=>typeof value==='number'?value:typeof value==='string'&&value.trim()!==''?Number(value):NaN;
 function calculate(input){
  const goals=number(input.goals),assists=number(input.assists),gp=number(input.gp),seasonGames=number(input.seasonGames??84),teamGP=number(input.teamGP??gp),missed=number(input.missed??0),rate=number(input.rate??100);
  for(const [label,value,min,max] of [['Goals',goals,0,9999],['Assists',assists,0,9999],['Games played',gp,0,200],['Season length',seasonGames,1,200],['Club games played',teamGP,0,200],['Games missed',missed,0,200]])if(!Number.isInteger(value)||value<min||value>max)return {valid:false,reason:`${label} must be a whole number from ${min} to ${max}.`};
  if(!Number.isFinite(rate)||rate<0||rate>300)return {valid:false,reason:'Scoring rate must be between 0% and 300%.'};
  if(!gp)return {valid:false,reason:'Enter at least one game played to calculate a pace.'};
  const points=goals+assists,gpg=goals/gp,apg=assists/gp,ppg=points/gp,clubRemaining=Math.max(0,seasonGames-teamGP),remaining=Math.max(0,clubRemaining-missed),factor=rate/100;
  return {valid:true,goals,assists,points,gp,seasonGames,teamGP,ppg,gpg,apg,clubRemaining,remaining,rate,missed,
   pace:{goals:gpg*seasonGames,assists:apg*seasonGames,points:ppg*seasonGames},
   finish:{goals:goals+gpg*factor*remaining,assists:assists+apg*factor*remaining,points:points+ppg*factor*remaining,gp:gp+remaining}};
 }
 return Object.freeze({calculate,number});
})();
