"""Teste real com identidades descartáveis, sem envio de e-mail. Limpa apenas dados criados por este teste."""
import json
import secrets
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
from pathlib import Path
from uuid import uuid4
import boto3
import requests
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from domain import record_key
s=boto3.Session(profile_name='pi-computacao-em-nuvem',region_name='us-east-2')
o={x['OutputKey']:x['OutputValue'] for x in s.client('cloudformation').describe_stacks(StackName='chacara-retirinho')['Stacks'][0]['Outputs']}
c=s.client('cognito-idp');t=s.resource('dynamodb').Table(o['TableName']);run=uuid4().hex[:12]
created_users=[];movements=[];stockkeys=set();users={};headers={};checks=[]
def check(name,condition):
    if not condition: raise AssertionError(name)
    checks.append(name);print('PASS',name,flush=True)
def call(role,method,path,body=None):
    return requests.request(method,o['ApiURL']+path,headers=headers.get(role,{}),json=body,timeout=25)
def payload(kind='entries',unit='caixotes',amount=10):
    value={'id':str(uuid4()),'quality':'Teste automatizado '+run,'size':'2','date':'2026-10-31T10:30' if kind=='entries' else '2026-10-31',unit:amount,'notes':'Registro descartável de verificação'}
    movements.append(value['id']);stockkeys.add(record_key(value['quality'],value['size']));return value
try:
    response=requests.get(o['SiteURL'],timeout=30)
    check('Site HTTPS e cabeçalhos de proteção',response.status_code==200 and 'frame-ancestors' in response.headers.get('content-security-policy',''))
    check('Bucket do site bloqueia acesso público',requests.get('https://'+o['S3Bucket']+'.s3.us-east-2.amazonaws.com/index.html',timeout=20).status_code==403)
    check('Sem login não consulta registros',call(None,'GET','/records').status_code==401)
    cors=requests.options(o['ApiURL']+'/entries',headers={'Origin':o['SiteURL'].rstrip('/'),'Access-Control-Request-Method':'POST','Access-Control-Request-Headers':'authorization,content-type'},timeout=20)
    check('Preflight CORS do site',cors.status_code in (200,204) and cors.headers.get('access-control-allow-origin')==o['SiteURL'].rstrip('/'))
    for role in ['admin','operator','viewer']:
        email='qa-'+run+'-'+role+'@example.invalid';password='Aa1!'+secrets.token_urlsafe(30)
        u=c.admin_create_user(UserPoolId=o['UserPoolId'],Username=email,MessageAction='SUPPRESS',UserAttributes=[{'Name':'email','Value':email},{'Name':'email_verified','Value':'true'},{'Name':'name','Value':'QA '+role}])['User']
        sub=next(a['Value'] for a in u['Attributes'] if a['Name']=='sub');created_users.append((u['Username'],sub));users[role]=sub
        c.admin_set_user_password(UserPoolId=o['UserPoolId'],Username=u['Username'],Password=password,Permanent=True)
        t.put_item(Item={'pk':'USERS','sk':sub,'id':sub,'username':u['Username'],'email':email,'name':'QA '+role,'role':role,'active':True,'created':datetime.now(timezone.utc).isoformat()})
        result=c.initiate_auth(ClientId=o['ClientId'],AuthFlow='USER_PASSWORD_AUTH',AuthParameters={'USERNAME':email,'PASSWORD':password})['AuthenticationResult']
        headers[role]={'Authorization':'Bearer '+result['AccessToken']}
        check('Login e leitura '+role,call(role,'GET','/me').json().get('role')==role)
        check('ID token recusado '+role,requests.get(o['ApiURL']+'/records',headers={'Authorization':'Bearer '+result['IdToken']},timeout=20).status_code in (401,403))
        time.sleep(1)
    check('Consulta não grava',call('viewer','POST','/entries',payload()).status_code==403)
    check('Operador não gerencia usuários',call('operator','GET','/users').status_code==403)
    check('Operador ativo não consulta auditoria',call('operator','GET','/audit').status_code==403)
    check('Visualizador não consulta auditoria',call('viewer','GET','/audit').status_code==403)
    entry=payload();r=call('operator','POST','/entries',entry);check('Operador registra entrada',r.status_code==200)
    check('Entrada identifica o operador autenticado',r.json().get('registeredBy')=='QA operator')
    check('Reenvio idempotente',call('operator','POST','/entries',entry).status_code==200)
    time.sleep(1)
    exits=[payload('exits',amount=7),payload('exits',amount=7)]
    for outgoing in exits: outgoing['weightKg']=70.25
    with ThreadPoolExecutor(max_workers=2) as executor:
        results=list(executor.map(lambda body:call('operator','POST','/exits',body),exits))
    check('Duas saídas concorrentes não deixam saldo negativo',sorted(r.status_code for r in results)==[200,409])
    saved_exit=next(r.json() for r in results if r.status_code==200)
    check('Saída preserva peso e responsável',saved_exit.get('weightKg')==70.25 and saved_exit.get('registeredBy')=='QA operator')
    check('Saldo correto no banco',t.get_item(Key={'pk':'STOCK','sk':next(iter(stockkeys))},ConsistentRead=True)['Item']['caixotes']==3)
    time.sleep(1)
    check('Embalagens têm saldos separados',call('operator','POST','/exits',payload('exits','sacos',1)).status_code==409)
    check('Exclusão não pode tornar saldo negativo',call('admin','DELETE','/entries/'+entry['id']).status_code==409)
    check('Operador não exclui',call('operator','DELETE','/entries/'+entry['id']).status_code==403)
    check('Administrador preserva próprio acesso',call('admin','PATCH','/users/'+users['admin'],{'active':False}).status_code==400)
    time.sleep(1)
    check('Pausar acesso',call('admin','PATCH','/users/'+users['operator'],{'active':False}).status_code==200)
    check('Token ainda válido não ignora pausa',call('operator','GET','/records').status_code==403)
    status=call('admin','GET','/status').json()
    check('Verificação real das integrações',status.get('database')=='connected')
    check('API da revisão publicada',status.get('version')=='online-2-auditoria')
    audit=call('admin','GET','/audit')
    check('Administrador consulta auditoria',audit.status_code==200)
    check('Auditoria identifica a saída e o operador',any(e.get('action')=='exits.created' and e.get('target')==saved_exit['id'] and e.get('actorId')==users['operator'] and e.get('details',{}).get('weightKg')==70.25 for e in audit.json()['items']))
    check('Consulta visualiza os históricos',call('viewer','GET','/records').status_code==200)
    print('Verificações concluídas:',len(checks),flush=True)
finally:
    # IDs/qualidade são únicos desta execução. Não apaga registros de pessoas reais.
    with t.batch_writer() as batch:
        for value in movements: batch.delete_item(Key={'pk':'MOVEMENTS','sk':value})
        for value in stockkeys: batch.delete_item(Key={'pk':'STOCK','sk':value})
        for username,sub in created_users: batch.delete_item(Key={'pk':'USERS','sk':sub})
    for username,sub in created_users: c.admin_delete_user(UserPoolId=o['UserPoolId'],Username=username)
    print('Dados e identidades descartáveis removidos. Eventos de auditoria dos testes são preservados.',flush=True)
