(() => {
  'use strict';
  const config = window.RETIRINHO_CONFIG;
  const SESSION = 'retirinhoOnlineAccessV1', PENDING = 'retirinhoOAuthV1';
  let token = '', refreshToken = '', expiresAt = 0, user = null, users = [], refreshTask;
  const base64url = bytes => btoa(String.fromCharCode(...bytes)).replace(/\+/g,'-').replace(/\//g,'_').replace(/=+$/,'');
  const random = () => base64url(crypto.getRandomValues(new Uint8Array(32)));
  const callback = () => window.location.origin + '/';
  const forget = () => { token = ''; refreshToken = ''; expiresAt = 0; user = null; users = []; sessionStorage.removeItem(SESSION); };
  function remember(result) {
    token = result.access_token;
    refreshToken = result.refresh_token || refreshToken;
    expiresAt = Date.now() + Number(result.expires_in) * 1000;
    if (!token || !Number.isFinite(expiresAt)) throw new Error('Resposta de autenticação inválida.');
    // Somente o token curto nesta aba. O refresh token permanece apenas em memória.
    sessionStorage.setItem(SESSION, JSON.stringify({ token, expiresAt }));
  }
  async function exchange(params) {
    const response = await fetch(config.authDomain + '/oauth2/token', {method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:new URLSearchParams(params)});
    const result = await response.json();
    if (!response.ok) throw new Error('Não foi possível renovar o acesso. Entre novamente.');
    return result;
  }
  async function freshToken() {
    if (token && expiresAt > Date.now() + 30000) return token;
    if (!refreshToken) { forget(); throw Object.assign(new Error('Sua sessão expirou. Entre novamente.'),{status:401}); }
    if (!refreshTask) refreshTask = exchange({grant_type:'refresh_token',client_id:config.clientId,refresh_token:refreshToken}).then(remember).finally(() => {refreshTask=null;});
    try { await refreshTask; return token; } catch (error) { forget(); throw Object.assign(error,{status:401}); }
  }
  async function request(path, options = {}) {
    const bearer = await freshToken();
    const response = await fetch(config.apiUrl + path, { ...options, headers:{'Content-Type':'application/json',Authorization:'Bearer '+bearer,...options.headers},cache:'no-store',signal:AbortSignal.timeout(20000) });
    const result = await response.json().catch(() => ({}));
    if (!response.ok) {
      if (response.status === 401 || (response.status === 403 && path === '/me')) forget();
      throw Object.assign(new Error(result.message || 'Não foi possível acessar o serviço.'), {status:response.status});
    }
    return result;
  }
  async function initialize() {
    if (!config?.apiUrl || !config?.authDomain || !config?.clientId) throw new Error('A publicação ainda está sendo configurada. Tente novamente em alguns minutos.');
    const url = new URL(location.href);
    if (url.searchParams.has('code') || url.searchParams.has('error')) {
      const pending = JSON.parse(sessionStorage.getItem(PENDING) || 'null');
      sessionStorage.removeItem(PENDING);
      history.replaceState({},'',callback());
      if (!pending || url.searchParams.get('state') !== pending.state || Date.now()-pending.created > 15*60*1000) throw new Error('A solicitação de login expirou. Inicie o acesso novamente.');
      if (url.searchParams.has('error')) throw new Error('O login foi cancelado ou não pôde ser concluído.');
      const result = await exchange({grant_type:'authorization_code',client_id:config.clientId,code:url.searchParams.get('code'),redirect_uri:callback(),code_verifier:pending.verifier});
      // ID token recebido diretamente do endpoint TLS; usado somente para conferir o nonce.
      const claims = JSON.parse(new TextDecoder().decode(Uint8Array.from(atob(result.id_token.split('.')[1].replace(/-/g,'+').replace(/_/g,'/')), c=>c.charCodeAt(0))));
      if (claims.nonce !== pending.nonce) throw new Error('Não foi possível confirmar a solicitação de login.');
      remember(result);
    } else {
      const saved = JSON.parse(sessionStorage.getItem(SESSION) || 'null');
      if (saved?.token && saved.expiresAt > Date.now()) { token=saved.token; expiresAt=saved.expiresAt; }
      else forget();
    }
    if (token) {
      try { user = await request('/me'); }
      catch (error) { forget(); throw error; }
    }
  }
  async function login() {
    const state = random(), nonce = random(), verifier = random();
    const challenge = base64url(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(verifier))));
    sessionStorage.setItem(PENDING,JSON.stringify({state,nonce,verifier,created:Date.now()}));
    const query = new URLSearchParams({response_type:'code',client_id:config.clientId,redirect_uri:callback(),scope:'openid email profile aws.cognito.signin.user.admin',state,nonce,code_challenge:challenge,code_challenge_method:'S256'});
    location.assign(config.authDomain+'/oauth2/authorize?'+query);
  }
  async function logout() {
    const refresh = refreshToken;
    forget();
    if (refresh) {
      try { await fetch(config.authDomain+'/oauth2/revoke',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:new URLSearchParams({token:refresh,client_id:config.clientId}),signal:AbortSignal.timeout(5000)}); } catch { /* sessão local já encerrada */ }
    }
    location.assign(config.authDomain+'/logout?'+new URLSearchParams({client_id:config.clientId,logout_uri:callback()}));
  }
  async function refreshUser() { user = await request('/me'); return user; }
  async function refreshUsers() { users = user?.role === 'admin' ? await request('/users') : []; return users; }
  async function loadRecords() {
    const result = {entries:[],exits:[]};
    let cursor;
    do {
      const page = await request('/records'+(cursor?'?cursor='+encodeURIComponent(cursor):''));
      for (const record of page.items) { const {kind,...value} = record; result[kind].push(value); }
      cursor=page.cursor;
    } while (cursor);
    return result;
  }
  window.RetirinhoAccess = Object.freeze({initialize,login,logout,forget,request,loadRecords,refreshUser,refreshUsers,
    currentUser:()=>user, listUsers:()=>users,
    createUser:body=>request('/users',{method:'POST',body:JSON.stringify(body)}),
    setRole:(id,role)=>request('/users/'+encodeURIComponent(id),{method:'PATCH',body:JSON.stringify({role})}),
    setActive:(id,active)=>request('/users/'+encodeURIComponent(id),{method:'PATCH',body:JSON.stringify({active})})});
})();
