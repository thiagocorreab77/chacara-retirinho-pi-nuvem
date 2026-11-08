"""API HTTP: o API Gateway valida a assinatura JWT antes de invocar a função."""
import base64
import binascii
from datetime import datetime, timezone
from decimal import Decimal
import json
import hashlib
import re
import logging
import os
import time
from uuid import UUID, uuid4

import boto3
from boto3.dynamodb.conditions import Attr, Key, ConditionExpressionBuilder
from botocore.exceptions import ClientError
from domain import AppError, UNITS, ROLES, validate_record, record_key, fingerprint, require_role, public_user, text

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

def now():
    return datetime.now(timezone.utc).isoformat()

def native_json(value):
    if isinstance(value, Decimal): return int(value) if value == value.to_integral_value() else float(value)
    raise TypeError(type(value).__name__)

class Store:
    def __init__(self, table_name, pool_id):
        resource = boto3.resource('dynamodb')
        self.table = resource.Table(table_name)
        self.client = resource.meta.client
        self.table_name, self.pool_id = table_name, pool_id
        self.cognito = boto3.client('cognito-idp')

    def get(self, pk, sk):
        return self.table.get_item(Key={'pk':pk,'sk':sk}, ConsistentRead=True).get('Item')

    def users(self):
        pages = self.client.get_paginator('query').paginate(TableName=self.table_name,
            KeyConditionExpression='pk = :pk', ExpressionAttributeValues={':pk':'USERS'}, ConsistentRead=True)
        return [item for page in pages for item in page.get('Items', [])]

    def records(self, cursor=None):
        kwargs = {'KeyConditionExpression':Key('pk').eq('MOVEMENTS'), 'ConsistentRead':True, 'Limit':100}
        if cursor:
            try:
                key = json.loads(base64.urlsafe_b64decode(cursor.encode()))
                if set(key) != {'pk','sk'} or key['pk'] != 'MOVEMENTS': raise ValueError()
                UUID(key['sk'])
            except (ValueError, TypeError, KeyError, UnicodeError, binascii.Error, AttributeError):
                raise AppError(400, 'Página inválida.')
            kwargs['ExclusiveStartKey'] = key
        page = self.table.query(**kwargs)
        next_key = page.get('LastEvaluatedKey')
        return {'items':[self.view_record(item) for item in page.get('Items',[]) if not item.get('deleted')],
                'cursor':base64.urlsafe_b64encode(json.dumps(next_key).encode()).decode() if next_key else None}

    @staticmethod
    def view_record(item):
        return {**item['record'], 'kind':item['kind'], 'created':item['created'], 'registeredBy':item['registeredBy']}

    def transaction(self, operations):
        # Condition builders são compilados para as operações transacionais da API.
        for op in operations:
            value = next(iter(op.values()))
            value['TableName'] = self.table_name
            condition = value.get('ConditionExpression')
            if condition is not None and not isinstance(condition, str):
                built = ConditionExpressionBuilder().build_expression(condition)
                value['ConditionExpression'] = built.condition_expression
                if built.attribute_name_placeholders:
                    value.setdefault('ExpressionAttributeNames', {}).update(built.attribute_name_placeholders)
                if built.attribute_value_placeholders:
                    value.setdefault('ExpressionAttributeValues', {}).update(built.attribute_value_placeholders)
        self.client.transact_write_items(TransactItems=operations)

    def actor_check(self, actor, allowed):
        return {'ConditionCheck': {'Key':{'pk':'USERS','sk':actor['id']},
                'ConditionExpression':Attr('active').eq(True) & Attr('role').is_in(list(allowed))}}

    def stock_update(self, record, direction):
        values = {f':delta{i}': direction * record[u] for i,u in enumerate(UNITS)}
        names = {f'#u{i}':u for i,u in enumerate(UNITS)}
        update = {'Key':{'pk':'STOCK','sk':record_key(record['quality'],record['size'])},
                  'UpdateExpression':'ADD '+', '.join(f'#u{i} :delta{i}' for i in range(len(UNITS))),
                  'ExpressionAttributeNames':names, 'ExpressionAttributeValues':values}
        if direction < 0:
            condition = None
            for u in UNITS:
                if record[u]:
                    part = Attr(u).gte(record[u])
                    condition = part if condition is None else condition & part
            update['ConditionExpression'] = condition
        return {'Update':update}

    def add_record(self, record, kind, actor):
        digest = fingerprint(record, kind)
        existing = self.get('MOVEMENTS',record['id'])
        if existing:
            if existing['fingerprint'] == digest and not existing.get('deleted'):
                return self.view_record(existing)
            raise AppError(409, 'Este identificador já foi utilizado. Atualize os históricos antes de tentar novamente.')
        item = {'pk':'MOVEMENTS','sk':record['id'],'record':record,'kind':kind,'fingerprint':digest,
                'created':int(time.time()*1000),'registeredBy':actor['name'],'createdBy':actor['id'],'deleted':False}
        try:
            self.transaction([{'Put':{'Item':item,'ConditionExpression':Attr('pk').not_exists()}},
                self.stock_update(record, 1 if kind == 'entries' else -1),self.actor_check(actor,('admin','operator')),
                self.audit_event(actor, kind+'.created', record['id'], {'quality':record['quality'],'size':record['size'], **{u:record[u] for u in UNITS}, **({'weightKg':record['weightKg']} if 'weightKg' in record else {})})])
        except self.client.exceptions.TransactionCanceledException:
            previous = self.get('MOVEMENTS',record['id'])
            if previous and previous['fingerprint'] == digest and not previous.get('deleted'):
                return self.view_record(previous)
            require_role(self.get('USERS',actor['id']),('admin','operator'))
            raise AppError(409, 'Não foi possível registrar: saldo insuficiente ou atualização simultânea. Atualize os históricos e confira a embalagem, a qualidade e o tamanho.')
        return self.view_record(item)

    def remove_record(self, record_id, kind, actor):
        item = self.get('MOVEMENTS',record_id)
        if not item or item['kind'] != kind: raise AppError(404,'Registro não encontrado.')
        if item.get('deleted'): return {'ok':True}
        try:
            self.transaction([
                {'Update':{'Key':{'pk':'MOVEMENTS','sk':record_id},'UpdateExpression':'SET deleted = :yes, deletedAt = :at, deletedBy = :by',
                    'ExpressionAttributeValues':{':yes':True,':at':now(),':by':actor['id']},'ConditionExpression':Attr('deleted').eq(False)}},
                self.stock_update(item['record'], -1 if kind == 'entries' else 1),self.actor_check(actor,('admin',)),
                self.audit_event(actor,kind+'.deleted',record_id,{'quality':item['record']['quality'],'size':item['record']['size']})])
        except self.client.exceptions.TransactionCanceledException:
            current = self.get('MOVEMENTS',record_id)
            if current and current.get('deleted'): return {'ok':True}
            require_role(self.get('USERS',actor['id']),('admin',))
            raise AppError(409,'A exclusão deixaria o estoque negativo ou houve outra atualização. Confira os históricos.')
        return {'ok':True}

    def invite_user(self, body, actor):
        name = text(body.get('name',''),'Nome',60,True)
        email = text(body.get('email',''),'E-mail',254,True).lower()
        import re
        if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email): raise AppError(400,'Informe um e-mail válido.')
        role = body.get('role')
        if role not in ROLES: raise AppError(400,'Perfil inválido.')
        # Convite é solicitado explicitamente na interface. A senha é gerada pelo Cognito.
        try:
            created = self.cognito.admin_create_user(UserPoolId=self.pool_id, Username=email,
                UserAttributes=[{'Name':'email','Value':email},{'Name':'name','Value':name}],
                DesiredDeliveryMediums=['EMAIL'])
        except self.cognito.exceptions.UsernameExistsException:
            raise AppError(409,'Este e-mail já tem um acesso. Confira a lista de usuários.')
        attrs = {a['Name']:a['Value'] for a in created['User']['Attributes']}
        user = {'pk':'USERS','sk':attrs['sub'],'id':attrs['sub'],'username':created['User']['Username'],
                'name':name,'email':email,'role':role,'active':True,'created':now()}
        try:
            self.transaction([{'Put':{'Item':user,'ConditionExpression':Attr('pk').not_exists()}},self.actor_check(actor,('admin',)), self.audit_event(actor,'user.invited',user['id'],{'name':name,'role':role})])
        except Exception:
            # Sem registro de permissão, este usuário não acessa a API.
            self.cognito.admin_disable_user(UserPoolId=self.pool_id,Username=user['username'])
            raise
        return public_user(user)

    def update_user(self, user_id, body, actor):
        if user_id == actor['id']: raise AppError(400,'Seu próprio perfil e acesso são preservados.')
        target = self.get('USERS',user_id)
        if not target: raise AppError(404,'Usuário não encontrado.')
        role, active = body.get('role',target['role']), body.get('active',target['active'])
        if role not in ROLES or type(active) is not bool: raise AppError(400,'Perfil ou situação inválidos.')
        if target['role']==role and target['active']==active: return public_user(target)
        # O próprio acesso é preservado; mudanças concorrentes exigem nova leitura.
        try:
            self.transaction([{'Update':{'Key':{'pk':'USERS','sk':user_id},
                'UpdateExpression':'SET #role = :role, active = :active',
                'ExpressionAttributeNames':{'#role':'role'}, 'ExpressionAttributeValues':{':role':role,':active':active},
                'ConditionExpression':Attr('role').eq(target['role']) & Attr('active').eq(target['active'])}},
                self.actor_check(actor,('admin',)),
                self.audit_event(actor,'user.updated',user_id,{'name':target['name'],'before':{'role':target['role'],'active':target['active']},'after':{'role':role,'active':active}})])
        except self.client.exceptions.TransactionCanceledException:
            require_role(self.get('USERS',actor['id']),('admin',))
            raise AppError(409,'O acesso mudou durante a alteração. Atualize a lista e tente novamente.')
        # O banco é a autoridade de permissões e bloqueia já na próxima chamada, mesmo com JWT válido.
        target.update(role=role,active=active)
        return public_user(target)

    def audit_event(self, actor, action, target, details):
        at = now()
        item = {'pk':'AUDIT','sk':f'{int(time.time()*1000):013d}#{uuid4()}', 'at':at,
            'actorId':actor['id'],'actorName':actor['name'],'actorRole':actor['role'],
            'action':action,'target':target,'details':details}
        return {'Put':{'Item':item,'ConditionExpression':Attr('pk').not_exists()}}


    def audit(self, cursor=None):
        kwargs={'KeyConditionExpression':Key('pk').eq('AUDIT'),'ConsistentRead':True,'Limit':100,'ScanIndexForward':False}
        if cursor:
            try:
                key=json.loads(base64.urlsafe_b64decode(cursor.encode()))
                if set(key)!={'pk','sk'} or key['pk']!='AUDIT' or not re.fullmatch(r'\d{13}#[0-9a-f-]{36}',key['sk']): raise ValueError()
                UUID(key['sk'].split('#')[1])
            except (ValueError,TypeError,KeyError,UnicodeError,binascii.Error,AttributeError):
                raise AppError(400,'Página de auditoria inválida.')
            kwargs['ExclusiveStartKey']=key
        page=self.table.query(**kwargs)
        next_key=page.get('LastEvaluatedKey')
        return {'items':[{k:v for k,v in item.items() if k not in ('pk','sk')}|{'id':item['sk']} for item in page.get('Items',[])],
            'cursor':base64.urlsafe_b64encode(json.dumps(next_key).encode()).decode() if next_key else None}


    def record_access(self, actor, claims):
        # Deduplica pelo instante de autenticação assinado pelo Cognito, não pelo navegador.
        try:
            authenticated=int(claims.get('auth_time',0))
            if not 0 < authenticated <= time.time()+300: return
        except (ValueError,TypeError): return
        key=hashlib.sha256(f"{actor['id']}|{authenticated}".encode()).hexdigest()
        if self.get('SESSIONS',key): return
        event=self.audit_event(actor,'session.observed',actor['id'],{'authenticatedAt':datetime.fromtimestamp(authenticated,timezone.utc).isoformat()})
        try:
            self.transaction([{'Put':{'Item':{'pk':'SESSIONS','sk':key},'ConditionExpression':Attr('pk').not_exists()}},event,self.actor_check(actor,ROLES)])
        except self.client.exceptions.TransactionCanceledException:
            require_role(self.get('USERS',actor['id']))
            if not self.get('SESSIONS',key): raise


    def status(self):
        self.table.get_item(Key={'pk':'HEALTH','sk':'READ'},ConsistentRead=True)
        return {'database':'connected','api':'connected','authentication':'cognito','region':os.environ.get('AWS_REGION','us-east-2'),
                'checkedAt':now(),'version':os.environ.get('APP_VERSION','online-2-auditoria')}

_store = None

def handle(event, store):
    claims = event.get('requestContext',{}).get('authorizer',{}).get('jwt',{}).get('claims',{})
    if not claims.get('sub') or claims.get('token_use') != 'access': raise AppError(401,'Entre novamente para continuar.')
    actor = store.get('USERS',claims['sub'])
    require_role(actor)
    method = event.get('requestContext',{}).get('http',{}).get('method','')
    path = event.get('rawPath','').rstrip('/')
    raw = event.get('body') or '{}'
    if event.get('isBase64Encoded'): raw = base64.b64decode(raw).decode()
    if len(raw.encode()) > 16000: raise AppError(413,'Solicitação muito grande.')
    try: body = json.loads(raw)
    except (ValueError,TypeError): raise AppError(400,'Solicitação inválida.')
    if not isinstance(body,dict): raise AppError(400,'Solicitação inválida.')
    if method == 'GET' and path == '/me':
        store.record_access(actor,claims); return public_user(actor)
    if method == 'GET' and path == '/audit':
        require_role(actor,('admin',)); return store.audit((event.get('queryStringParameters') or {}).get('cursor'))
    if method == 'GET' and path == '/records': return store.records((event.get('queryStringParameters') or {}).get('cursor'))
    if method == 'POST' and path in ('/entries','/exits'):
        require_role(actor,('admin','operator'))
        kind = path[1:]
        return store.add_record(validate_record(body,kind),kind,actor)
    if method == 'DELETE' and (path.startswith('/entries/') or path.startswith('/exits/')):
        require_role(actor,('admin',))
        _,kind,record_id = path.split('/',2)
        try: record_id = str(UUID(record_id))
        except ValueError: raise AppError(400,'Identificador inválido.')
        return store.remove_record(record_id,kind,actor)
    if path == '/users' and method == 'GET':
        require_role(actor,('admin',)); return [public_user(u) for u in store.users()]
    if path == '/users' and method == 'POST':
        require_role(actor,('admin',)); return store.invite_user(body,actor)
    if path.startswith('/users/') and method == 'PATCH':
        require_role(actor,('admin',)); return store.update_user(path.split('/')[-1],body,actor)
    if path == '/status' and method == 'GET':
        require_role(actor,('admin',)); return store.status()
    raise AppError(404,'Recurso não encontrado.')

def handler(event, context):
    global _store
    # Preflight não lê dados nem exige sessão. API Gateway acrescenta os cabeçalhos CORS.
    if event.get('requestContext',{}).get('http',{}).get('method') == 'OPTIONS':
        return {'statusCode':204,'headers':{'cache-control':'no-store'},'body':''}
    try:
        if _store is None: _store = Store(os.environ['TABLE_NAME'],os.environ['USER_POOL_ID'])
        payload, status = handle(event,_store), 200
    except AppError as error:
        payload,status = {'message':error.message},error.status
    except ClientError as error:
        log.error('AWS operation failed code=%s request=%s',error.response['Error']['Code'],getattr(context,'aws_request_id',''))
        payload,status = {'message':'Serviço temporariamente indisponível. Tente novamente.'},503
    except Exception:
        log.exception('Unexpected server error')
        payload,status = {'message':'Não foi possível concluir a operação. Tente novamente.'},500
    return {'statusCode':status,'headers':{'content-type':'application/json; charset=utf-8','cache-control':'no-store'},
            'body':json.dumps(payload,ensure_ascii=False,default=native_json)}
