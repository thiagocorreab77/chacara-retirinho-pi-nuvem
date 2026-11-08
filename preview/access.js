/* Somente demonstração local. Nunca publicar este arquivo em web/. */
(() => {
  'use strict';
  const key='retirinho-preview-v2-auditoria-2026-11-08', profileKey=key+'-profile';
  const ROLE_LABELS={admin:'Administrador',operator:'Operador',viewer:'Visualizador'};
  const base={quality:'Ágata 00 importada',size:'1',caixotes:0,sacos:0,meiao:0,bags:0,notes:'Exemplo fictício'};
  const initial=()=>({entries:[
    {...base,id:'demo-entry-1',date:'2026-11-02T10:30',caixotes:100,gross:12000,tare:2000,destination:'Câmara 1',driver:'Motorista de exemplo',truck:'DEMO001',registeredBy:'Ana — demonstração'},
    {...base,id:'demo-entry-2',date:'2026-11-01T09:00',quality:'Asterix',sacos:20,gross:0,tare:0,destination:'Câmara 2',registeredBy:'Bruno — demonstração'}
  ],exits:[{...base,id:'demo-exit-1',date:'2026-11-03',caixotes:22,weightKg:2200,registeredBy:'Bruno — demonstração'}],
  users:Object.entries(ROLE_LABELS).map(([role,label])=>({id:'demo-'+role,name:label+' — demonstração',email:role+'@example.invalid',role,active:true})),
  audit:[]});
  let data=initial(), profile='admin';
  try {const saved=JSON.parse(localStorage.getItem(key));if(saved&&Array.isArray(saved.users)&&Array.isArray(saved.audit))data=saved;profile=sessionStorage.getItem(profileKey)||profile;} catch {}
  if(!Object.hasOwn(ROLE_LABELS,profile)) profile='admin';
  const user=()=>data.users.find(u=>u.id==='demo-'+profile);
  const persist=()=>{try{localStorage.setItem(key,JSON.stringify(data));}catch{}};
  const fail=(message,status=403)=>{throw Object.assign(new Error(message),{status});};
  const requireRole=roles=>{if(!user()?.active||!roles.includes(user()?.role))fail('Este perfil não permite a ação.');};
  const manage=()=>requireRole(['admin']);
  const audit=(action,target,details)=>data.audit.unshift({id:crypto.randomUUID(),at:new Date().toISOString(),actorId:user().id,actorName:user().name,actorRole:user().role,action,target,details});
  const changeUser=async(id,changes)=>{const target=data.users.find(u=>u.id===id);if(!target)fail('Acesso não encontrado.',404);if(id===user().id)fail('Seu próprio acesso é preservado.',400);manage(target,changes.role);const before={role:target.role,active:target.active};Object.assign(target,changes);audit('user.updated',id,{name:target.name,before,after:{role:target.role,active:target.active}});persist();};
  window.RetirinhoAccess={preview:true,
    initialize:async()=>{requireRole(Object.keys(ROLE_LABELS));audit('session.observed',user().id,{description:'Acesso fictício à prévia'});persist();},
    currentUser:user,refreshUser:async()=>{requireRole(Object.keys(ROLE_LABELS));return user();},
    listUsers:()=>data.users,refreshUsers:async()=>{requireRole(['admin']);return data.users;},
    loadRecords:async()=>structuredClone({entries:data.entries,exits:data.exits}),
    login:async()=>fail('Use o seletor de perfil da prévia.',400),logout:async()=>{},forget:()=>{},
    createUser:async(body)=>{manage(null,body.role);if(!Object.hasOwn(ROLE_LABELS,body.role))fail('Perfil inválido.',400);if(data.users.some(u=>u.email.toLowerCase()===body.email.toLowerCase()))fail('E-mail fictício já cadastrado.',409);const created={...body,id:crypto.randomUUID(),active:true};data.users.push(created);audit('user.invited',created.id,{name:created.name,role:created.role});persist();return created;},
    setRole:async(id,role)=>{if(!Object.hasOwn(ROLE_LABELS,role))fail('Perfil inválido.',400);return changeUser(id,{role});},
    setActive:async(id,active)=>changeUser(id,{active}),
    request:async(path,options={})=>{
      const method=options.method||'GET', url=new URL(path,'http://preview.invalid');
      if(url.pathname==='/audit'){requireRole(['admin']);const start=Number(url.searchParams.get('cursor')||0);return {items:structuredClone(data.audit.slice(start,start+100)),cursor:data.audit.length>start+100?String(start+100):null};}
      if(url.pathname==='/status'){requireRole(['admin']);return {database:'demo',api:'demo',version:'online-2-auditoria (prévia)',checkedAt:new Date().toISOString()};}
      const [,kind,recordId]=url.pathname.split('/');
      if(!['entries','exits'].includes(kind))fail('Rota não simulada.',404);
      if(method==='POST'){
        requireRole(['admin','operator']);const record=JSON.parse(options.body);
        if(data[kind].some(item=>item.id===record.id))return {};
        if(kind==='exits'){const available=window.RetirinhoInventory.balance(data,record);if(Object.keys(available).some(unit=>Number(record[unit]||0)>available[unit]))fail('Saldo insuficiente.',409);}
        data[kind].push({...record,created:Date.now(),registeredBy:user().name});audit(kind+'.created',record.id,{quality:record.quality,size:record.size,...Object.fromEntries(Object.keys(window.RetirinhoInventory.UNITS).map(u=>[u,record[u]])),...(record.weightKg?{weightKg:record.weightKg}:{})});persist();return {};
      }
      if(method==='DELETE'){
        requireRole(['admin']);const record=data[kind].find(item=>item.id===recordId);
        if(record&&kind==='entries'&&!window.RetirinhoInventory.canRemoveEntry(data,record))fail('A exclusão deixaria saldo negativo.',409);
        if(record){data[kind]=data[kind].filter(item=>item.id!==recordId);audit(kind+'.deleted',recordId,{quality:record.quality,size:record.size});persist();}return {};
      }
      fail('Ação indisponível.',404);
    }
  };
  const selector=document.getElementById('previewProfile');selector.value=profile;
  selector.addEventListener('change',()=>{try{sessionStorage.setItem(profileKey,selector.value);}catch{}location.reload();});
  document.getElementById('previewReset').addEventListener('click',()=>{data=initial();persist();try{sessionStorage.setItem(profileKey,'admin');}catch{}location.reload();});
  const logout=document.getElementById('logout');logout.disabled=true;logout.textContent='Acesso demonstrativo';
})();
