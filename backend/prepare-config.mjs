import {readFileSync,writeFileSync} from 'node:fs';
import {execFileSync} from 'node:child_process';
const config=JSON.parse(readFileSync(new URL('./wrangler.jsonc',import.meta.url),'utf8'));
let id=process.env.SWEATER_D1_DATABASE_ID;
if(!id) {
  try {
    const rows=JSON.parse(execFileSync('npx',['--no-install','wrangler','d1','list','--json'],{encoding:'utf8',stdio:['ignore','pipe','pipe']}));
    const matches=rows.filter(r=>r.name==='sweater-leaderboard');
    if(matches.length!==1)throw new Error('Expected one existing sweater-leaderboard database');
    id=matches[0].uuid||matches[0].id;
  } catch {
    throw new Error('Could not resolve the existing sweater-leaderboard database. Set SWEATER_D1_DATABASE_ID to its existing Database ID in build variables; no new database will be created.');
  }
}
if(!/^[a-f0-9]{8}(-[a-f0-9]{4}){3}-[a-f0-9]{12}$/i.test(id||''))throw new Error('Invalid existing D1 Database ID');
if(process.argv.includes('--production')&&id==='00000000-0000-0000-0000-000000000000')throw new Error('The dry-run Database ID cannot be deployed');
config.d1_databases[0].database_id=id;
writeFileSync(new URL('./wrangler.generated.json',import.meta.url),JSON.stringify(config,null,2)+'\n');
console.log('Prepared sweater-api with its existing DB binding; dashboard variables and secrets preserved.');
