const ROOT='https://api.github.com/repos/cartsybends/sweater.win';
const RAW='https://raw.githubusercontent.com/cartsybends/sweater.win/main/';
const PLAYOFFS={workflow:'refresh-playoffs.yml',feed:'playoffs_cache.json',timestamp:'checked_at'};
const PROJECTIONS={workflow:'refresh-projections.yml',feed:'projections_cache.json',timestamp:'collected_at'};
const ERROR_CODES=new Set(['AbortError','TimeoutError','TypeError','SyntaxError']);

// The Worker supplies a dependable clock; the existing Python job still validates
// and publishes the complete forecast. No public endpoint can dispatch jobs.
async function refreshFeed(env,source,{fetcher=fetch,now=Date.now()}={}){
 const token=env.GITHUB_REFRESH_TOKEN;if(!token)return {status:'not_configured'};
 const workflow=ROOT+'/actions/workflows/'+source.workflow;
 let stage='feed_fetch';
 try{
  const response=await fetcher(RAW+source.feed+'?watchdog='+Math.floor(now/60000),{signal:AbortSignal.timeout(10000),cache:'no-store'});
  if(!response.ok)return {status:'feed_unavailable',code:response.status};
  stage='feed_parse';
  const feed=await response.json(),checked=Date.parse(feed[source.timestamp]);
  if(!Number.isFinite(checked)||checked>now+300000)return {status:'invalid_feed'};
  if(now-checked<900000)return {status:'fresh'};
  const headers={Authorization:'Bearer '+token,Accept:'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28','User-Agent':'Sweater-Feed-Refresh'};
  // Workers supports manual/follow only. Reject redirects without forwarding
  // the credential to another destination; redirect:"error" throws in workerd.
  stage='github_runs_fetch';
  const active=await fetcher(workflow+'/runs?per_page=5',{headers,signal:AbortSignal.timeout(10000),redirect:'manual'});
  if(!active.ok)return {status:'github_error',stage,code:active.status};
  stage='github_runs_parse';
  const runs=(await active.json()).workflow_runs;
  if(!Array.isArray(runs))return {status:'invalid_runs'};
  if(runs.some(run=>['queued','in_progress','waiting','pending','requested'].includes(run.status)))return {status:'running'};
  if(runs.some(run=>Number.isFinite(Date.parse(run.created_at))&&now-Date.parse(run.created_at)<300000))return {status:'cooldown'};
  stage='github_dispatch';
  const dispatched=await fetcher(workflow+'/dispatches',{method:'POST',headers:{...headers,'Content-Type':'application/json'},body:JSON.stringify({ref:'main'}),signal:AbortSignal.timeout(10000),redirect:'manual'});
  return dispatched.status===204?{status:'dispatched'}:{status:'github_error',stage,code:dispatched.status};
 }catch(error){
  // Only static stages and allowlisted error types reach logs. Never expose a
  // response body, arbitrary exception message, request headers or the token.
  return {status:'unavailable',stage,code:ERROR_CODES.has(error?.name)?error.name:'Error'};
 }
}

export const refreshPlayoffs=(env,options)=>refreshFeed(env,PLAYOFFS,options);
export const refreshProjections=(env,options)=>refreshFeed(env,PROJECTIONS,options);
