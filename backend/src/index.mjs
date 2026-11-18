import existingAPI from './existing-api.mjs';
import {handleAnalytics,purgeAnalytics} from './analytics.mjs';
import {handleGridPopularity,pruneGridPopularity} from './grid-popularity.mjs';
import {refreshPlayoffs} from './playoff-refresh.mjs';
import {handlePlayoffLive} from './playoff-live.mjs';
import {purgeMarketQuotes} from './market-history.mjs';
import {handleGameCenter} from './game-center.mjs';
import {handleGamePreview} from './game-preview.mjs';
import {handleTeamLeaders} from './team-leaders.mjs';
export default {
  async fetch(request,env,ctx) {
    const leaders=await handleTeamLeaders(request,env);if(leaders)return leaders;
    const preview=await handleGamePreview(request,env,ctx);if(preview)return preview;
    const center=await handleGameCenter(request,env,ctx);if(center)return center;
    const live=await handlePlayoffLive(request,env,ctx);if(live)return live;
    const grid=await handleGridPopularity(request,env);if(grid)return grid;
    const analytics=await handleAnalytics(request,env);
    return analytics || existingAPI.fetch(request,env,ctx);
  },
  async scheduled(controller,env,ctx) {
    if(controller.cron==='* * * * *'){
      ctx.waitUntil(refreshPlayoffs(env).then(result=>{if(['dispatched','github_error','unavailable','feed_unavailable','invalid_feed','invalid_runs'].includes(result.status))console.log('Playoff refresh watchdog',result);}));
      return;
    }
    ctx.waitUntil(purgeAnalytics(env));
    ctx.waitUntil(pruneGridPopularity(env));
    ctx.waitUntil(purgeMarketQuotes(env));
  }
};
