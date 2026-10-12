import assert from 'node:assert/strict';
import vm from 'node:vm';
import {loginPage} from '../backend/src/dashboard.mjs';

const html=loginPage('');
const source=html.match(/<script[^>]*>([\s\S]*?)<\/script>/)[1];
function browser(fetch){
  const elements=Object.fromEntries(['login-form','password','login-submit','login-message','show-password'].map(id=>[id,{
    value:'mobile test password with + & spaces',type:'password',textContent:'',disabled:false,
    listeners:{},attributes:{},classes:new Set(),
    addEventListener(name,fn){this.listeners[name]=fn;},
    setAttribute(name,value){this.attributes[name]=value;}
  }]));
  for(const element of Object.values(elements))element.classList={add:name=>element.classes.add(name),remove:name=>element.classes.delete(name)};
  const navigations=[],requests=[];let timer;
  const context={document:{getElementById:id=>elements[id]},AbortController,URLSearchParams,
    fetch:async(url,options)=>{requests.push({url,options});return fetch(url,options);},
    setTimeout:callback=>{timer=callback;return 1;},clearTimeout:()=>{timer=null;},
    location:{replace:url=>navigations.push(url)}};
  vm.runInNewContext(source,context);
  return {elements,requests,navigations,timeout:()=>timer?.(),submit:()=>elements['login-form'].listeners.submit({preventDefault(){}})};
}
const json=(body,status=200)=>new Response(JSON.stringify(body),{status,headers:{'Content-Type':'application/json'}});

let b=browser(async url=>url==='/analytics/login'?json({ok:true}):json({authenticated:true}));
await b.submit();assert.deepEqual(b.navigations,['/analytics']);assert.equal(b.requests.length,2);
assert.equal(b.requests[0].options.body.get('password'),b.elements.password.value,'Mobile entry preserves the exact password, including punctuation and spaces');
assert.equal(b.requests[0].options.mode,'cors');assert.equal(b.requests[0].options.credentials,'same-origin');assert.equal(b.requests[1].options.credentials,'same-origin');
assert.equal(b.requests[1].url,'/api/analytics/session','The browser verifies its saved cookie before navigating');

b=browser(async()=>json({error:'That password did not match.'},401));await b.submit();
assert.equal(b.elements['login-message'].textContent,'That password did not match.');assert.equal(b.elements['login-submit'].disabled,false);assert.equal(b.navigations.length,0);assert.equal(b.requests.length,1);

b=browser(async url=>url==='/analytics/login'?json({ok:true}):json({error:'Sign in required'},401));await b.submit();
assert.match(b.elements['login-message'].textContent,/did not keep the sign-in session/);assert.equal(b.navigations.length,0,'Blocked cookies show an explanation instead of a login loop');assert.equal(b.elements['login-submit'].disabled,false);

b=browser(async()=>json({error:'Too many requests; try again shortly'},429));await b.submit();assert.match(b.elements['login-message'].textContent,/Too many requests/);assert.equal(b.elements['login-submit'].disabled,false);

b=browser(async()=>{throw new Error('Connection unavailable');});await b.submit();assert.equal(b.elements['login-message'].textContent,'Connection unavailable');assert.equal(b.elements['login-submit'].disabled,false);

b=browser(async()=>new Response('<html>unexpected redirect</html>'));await b.submit();assert.match(b.elements['login-message'].textContent,/Reload this page/);assert.equal(b.navigations.length,0);

b=browser(async(_url,options)=>new Promise((_,reject)=>options.signal.addEventListener('abort',()=>{const error=new Error();error.name='AbortError';reject(error);})));
const waiting=b.submit();await b.submit();assert.equal(b.requests.length,1,'Repeated taps cannot submit duplicate password attempts');b.timeout();await waiting;assert.match(b.elements['login-message'].textContent,/took too long/);assert.equal(b.elements['login-submit'].disabled,false);

b.elements['show-password'].listeners.click();assert.equal(b.elements.password.type,'text');assert.equal(b.elements['show-password'].attributes['aria-pressed'],'true');
b.elements['show-password'].listeners.click();assert.equal(b.elements.password.type,'password');assert.equal(b.elements['show-password'].attributes['aria-pressed'],'false');
assert.match(html,/autocapitalize="none" autocorrect="off" spellcheck="false"/);
console.log('Analytics sign-in: saved session verification, missing cookies, exact password entry, password errors, rate limits, network failures, timeouts, duplicate taps and visibility toggle passed.');
