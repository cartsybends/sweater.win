import existingAPI from './existing-api.mjs';
import {handleAnalytics,purgeAnalytics} from './analytics.mjs';
export default {
  async fetch(request,env,ctx) {
    const analytics=await handleAnalytics(request,env);
    return analytics || existingAPI.fetch(request,env,ctx);
  },
  async scheduled(controller,env,ctx) {
    ctx.waitUntil(purgeAnalytics(env));
  }
};
