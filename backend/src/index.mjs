import existingAPI from './existing-api.mjs';
import {handleAnalytics,purgeAnalytics} from './analytics.mjs';
import {handleGridPopularity,pruneGridPopularity} from './grid-popularity.mjs';
export default {
  async fetch(request,env,ctx) {
    const grid=await handleGridPopularity(request,env);if(grid)return grid;
    const analytics=await handleAnalytics(request,env);
    return analytics || existingAPI.fetch(request,env,ctx);
  },
  async scheduled(controller,env,ctx) {
    ctx.waitUntil(purgeAnalytics(env));
    ctx.waitUntil(pruneGridPopularity(env));
  }
};
