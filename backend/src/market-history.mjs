const initialized=new WeakMap(),RETENTION=2*86400000;
const prices=q=>['home','away'].every(k=>Number.isInteger(q?.[k])&&Math.abs(q[k])>=100&&Math.abs(q[k])<=100000);
export function validSavedQuote(quote,game,now){
 const at=Date.parse(quote?.observed_at),start=Date.parse(game.start);
 return !!quote&&quote.source==='ESPN'&&quote.provider==='DraftKings'&&['live','pregame'].includes(quote.basis)&&prices(quote)&&/^https:\/\/www\.espn\.com\/nhl\/game\/_\/gameId\/\d{1,12}$/.test(quote.source_url||'')&&Number.isFinite(at)&&at<=now+300000&&now-at<=RETENTION&&(quote.basis==='live'?at>=start:at<start);
}
async function schema(db){
 if(!initialized.has(db))initialized.set(db,db.prepare('CREATE TABLE IF NOT EXISTS sweater_market_quotes (game_id INTEGER PRIMARY KEY,home_team TEXT NOT NULL,away_team TEXT NOT NULL,start_time TEXT NOT NULL,quote_json TEXT NOT NULL,observed_ms INTEGER NOT NULL,expires_ms INTEGER NOT NULL)').run().catch(error=>{initialized.delete(db);throw error;}));
 await initialized.get(db);
}
export async function purgeMarketQuotes(env){if(!env.DB)return;await schema(env.DB);await env.DB.prepare('DELETE FROM sweater_market_quotes WHERE expires_ms < ?').bind(Date.now()).run();}
export async function retainMarketQuote(game,market,env,{cache,now=Date.now()}={}){
 const key=new Request(`https://api.sweater.win/api/playoffs/last-quote/${game.id}?home=${game.home}&away=${game.away}&start=${encodeURIComponent(game.start)}`);
 const identity={id:game.id,home:game.home,away:game.away,start:game.start};
 if(market.status==='live'){
  const quote={source:market.source,provider:market.provider,source_url:market.source_url,home:market.home,away:market.away,observed_at:market.observed_at,basis:'live'};
  if(!validSavedQuote(quote,game,now))return market;
  if(env.DB)try{
   await schema(env.DB);
   await env.DB.prepare('INSERT INTO sweater_market_quotes (game_id,home_team,away_team,start_time,quote_json,observed_ms,expires_ms) VALUES (?,?,?,?,?,?,?) ON CONFLICT(game_id) DO UPDATE SET home_team=excluded.home_team,away_team=excluded.away_team,start_time=excluded.start_time,quote_json=excluded.quote_json,observed_ms=excluded.observed_ms,expires_ms=excluded.expires_ms WHERE excluded.start_time != sweater_market_quotes.start_time OR excluded.observed_ms > sweater_market_quotes.observed_ms').bind(game.id,game.home,game.away,game.start,JSON.stringify(quote),Date.parse(quote.observed_at),Date.parse(quote.observed_at)+RETENTION).run();
  }catch{}
  if(cache)try{await cache.put(key,Response.json({...identity,quote},{headers:{'Cache-Control':'public,max-age=172800'}}));}catch{}
  return market;
 }
 let latest=null;
 if(cache)try{const saved=await cache.match(key);if(saved){const data=await saved.json();if(data.id===game.id&&data.home===game.home&&data.away===game.away&&data.start===game.start&&validSavedQuote(data.quote,game,now))latest=data.quote;}}catch{}
 if(env.DB)try{
  await schema(env.DB);
  const row=await env.DB.prepare('SELECT quote_json FROM sweater_market_quotes WHERE game_id=? AND home_team=? AND away_team=? AND start_time=? AND expires_ms>=?').bind(game.id,game.home,game.away,game.start,now).first();
  if(row){const saved=JSON.parse(row.quote_json);if(validSavedQuote(saved,game,now)&&(!latest||Date.parse(saved.observed_at)>Date.parse(latest.observed_at)))latest=saved;}
 }catch{}
 if(!latest){const saved={...game.market,basis:'pregame'};if(validSavedQuote(saved,game,now))latest=saved;}
 return latest?{...market,last_quote:latest}:market;
}
