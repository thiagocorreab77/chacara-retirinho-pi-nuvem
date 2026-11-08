const {test}=require('node:test');
const assert=require('node:assert/strict');
const vm=require('node:vm');
const fs=require('node:fs');
const path=require('node:path');
const crypto=require('node:crypto').webcrypto;
const source=fs.readFileSync(path.join(__dirname,'../web/access.js'),'utf8');
function setup({url='https://site.example/',saved={},responses=[]}={}) {
  const memory=new Map(Object.entries(saved)), calls=[];let clock=Date.now();
  const location={href:url,origin:'https://site.example',assign:value=>calls.push({redirect:value})};
  const config={apiUrl:'https://api.example',authDomain:'https://auth.example',clientId:'public-client'};
  const context={window:{RETIRINHO_CONFIG:config,location},location,history:{replaceState:(state,title,value)=>{location.href=value;}},
    sessionStorage:{getItem:k=>memory.get(k)||null,setItem:(k,v)=>memory.set(k,v),removeItem:k=>memory.delete(k)},crypto,URL,URLSearchParams,TextEncoder,TextDecoder,Uint8Array,atob,btoa,AbortSignal,
    Date:class extends Date {static now(){return clock;}},fetch:async(url,options)=>{calls.push({url,options});const next=responses.shift();if(!next)throw Error('Unexpected fetch');return {ok:next.status===undefined||next.status===200,status:next.status||200,json:async()=>next.body};}};
  vm.runInNewContext(source,context);
  return {api:context.window.RetirinhoAccess,memory,calls,location,advance:ms=>clock+=ms};
}
const SESSION='retirinhoOnlineAccessV1',PENDING='retirinhoOAuthV1';
const user={id:'person',name:'Pessoa',role:'viewer',active:true};
const jwt=nonce=>'header.'+Buffer.from(JSON.stringify({nonce})).toString('base64url')+'.signature';
test('login uses code + PKCE S256, state and nonce; no client secret',async()=>{
 const s=setup();await s.api.initialize();await s.api.login();const u=new URL(s.calls[0].redirect),pending=JSON.parse(s.memory.get(PENDING));
 assert.equal(u.searchParams.get('response_type'),'code');assert.equal(u.searchParams.get('code_challenge_method'),'S256');assert.equal(u.searchParams.get('state'),pending.state);assert.equal(u.searchParams.get('nonce'),pending.nonce);
 const digest=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(pending.verifier));assert.equal(u.searchParams.get('code_challenge'),Buffer.from(digest).toString('base64url'));assert.equal(u.searchParams.get('client_secret'),null);
});
test('rejects unmatched callback state before sending the code',async()=>{
 const s=setup({url:'https://site.example/?code=test&state=wrong',saved:{[PENDING]:JSON.stringify({state:'right',created:Date.now()})}});await assert.rejects(s.api.initialize(),/expirou/);assert.equal(s.calls.length,0);assert.equal(s.location.href,'https://site.example/');
});
test('callback verifies nonce, loads server role and does not persist refresh token',async()=>{
 const s=setup({url:'https://site.example/?code=test&state=state',saved:{[PENDING]:JSON.stringify({state:'state',nonce:'nonce',verifier:'verifier',created:Date.now()})},responses:[{body:{access_token:'access',refresh_token:'refresh',expires_in:900,id_token:jwt('nonce')}},{body:user},{body:{access_token:'renewed',expires_in:900}},{body:{items:[]}}]});
 await s.api.initialize();assert.equal(s.api.currentUser().role,'viewer');assert.equal(s.memory.get(SESSION).includes('refresh'),false);
 s.advance(901000);await s.api.request('/records');assert.equal(s.calls[2].options.body.get('grant_type'),'refresh_token');assert.equal(s.calls[3].options.headers.Authorization,'Bearer renewed');
});
test('rejects callback nonce mismatch',async()=>{
 const s=setup({url:'https://site.example/?code=test&state=state',saved:{[PENDING]:JSON.stringify({state:'state',nonce:'expected',created:Date.now(),verifier:'v'})},responses:[{body:{access_token:'access',expires_in:900,id_token:jwt('wrong')}}]});await assert.rejects(s.api.initialize(),/confirmar/);assert.equal(s.memory.has(SESSION),false);
});
test('paused server access clears the session even with an unexpired token',async()=>{
 const s=setup({saved:{[SESSION]:JSON.stringify({token:'existing',expiresAt:Date.now()+900000})},responses:[{status:403,body:{message:'Acesso pausado'}}]});await assert.rejects(s.api.initialize(),/pausado/);assert.equal(s.api.currentUser(),null);assert.equal(s.memory.has(SESSION),false);
});
