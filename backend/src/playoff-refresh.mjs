const ROOT='https://api.github.com/repos/cartsybends/sweater.win';
const WORKFLOW=ROOT+'/actions/workflows/refresh-playoffs.yml';
const FEED='https://raw.githubusercontent.com/cartsybends/sweater.win/main/playoffs_cache.json';
const ERROR_CODES=new Set(['AbortError','TimeoutError','TypeError','SyntaxError']);

// The Worker supplies a dependable clock; the existing Python job still validates
// and publishes the complete forecast. No public endpoint can dispatch jobs.
export async function refreshPlayoffs(env,{fetcher=fetch,now=Date.now()}={}){
 const token=env.GITHUB_REFRESH_TOKEN;if(!token)return {status:'not_configured'};
 let stage='feed_fetch';
 try{
  const response=await fetcher(FEED+'?watchdog='+Math.floor(now/60000),{signal:AbortSignal.timeout(10000),cache:'no-store'});
  if(!response.ok)return {status:'feed_unavailable',code:response.status};
  stage='feed_parse';
  const feed=await response.json(),checked=Date.parse(feed.checked_at);
  if(!Number.isFinite(checked)||checked>now+300000)return {status:'invalid_feed'};
  if(now-checked<300000)return {status:'fresh'};
  const headers={Authorization:'Bearer '+token,Accept:'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28','User-Agent':'Sweater-Playoff-Refresh'};
  // Workers supports manual/follow only. Reject redirects without forwarding
  // the credential to another destination; redirect:"error" throws in workerd.
  stage='github_runs_fetch';
  const active=await fetcher(WORKFLOW+'/runs?per_page=5',{headers,signal:AbortSignal.timeout(10000),redirect:'manual'});
  if(!active.ok)return {status:'github_error',stage,code:active.status};
  stage='github_runs_parse';
  const runs=(await active.json()).workflow_runs;
  if(!Array.isArray(runs))return {status:'invalid_runs'};
  if(runs.some(run=>['queued','in_progress','waiting','pending','requested'].includes(run.status)))return {status:'running'};
  if(runs.some(run=>Number.isFinite(Date.parse(run.created_at))&&now-Date.parse(run.created_at)<300000))return {status:'cooldown'};
  stage='github_dispatch';
  const dispatched=await fetcher(WORKFLOW+'/dispatches',{method:'POST',headers:{...headers,'Content-Type':'application/json'},body:JSON.stringify({ref:'main'}),signal:AbortSignal.timeout(10000),redirect:'manual'});
  return dispatched.status===204?{status:'dispatched'}:{status:'github_error',stage,code:dispatched.status};
 }catch(error){
  // Only static stages and allowlisted error types reach logs. Never expose a
  // response body, arbitrary exception message, request headers or the token.
  return {status:'unavailable',stage,code:ERROR_CODES.has(error?.name)?error.name:'Error'};
 }
}
