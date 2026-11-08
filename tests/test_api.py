import json
import os
import sys
from pathlib import Path
from uuid import uuid4
import boto3
import pytest
from moto import mock_aws
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from app import Store, handle
from domain import AppError, validate_record, record_key

def test_preflight_without_token_or_database(monkeypatch):
    import app
    monkeypatch.setattr(app,'_store',None)
    result=app.handler({'requestContext':{'http':{'method':'OPTIONS'}}},None)
    assert result['statusCode']==204 and result['body']=='' and app._store is None

@pytest.fixture
def store(monkeypatch):
    monkeypatch.setenv('AWS_DEFAULT_REGION','us-east-2')
    with mock_aws():
        boto3.client('dynamodb').create_table(TableName='test',BillingMode='PAY_PER_REQUEST',AttributeDefinitions=[{'AttributeName':'pk','AttributeType':'S'},{'AttributeName':'sk','AttributeType':'S'}],KeySchema=[{'AttributeName':'pk','KeyType':'HASH'},{'AttributeName':'sk','KeyType':'RANGE'}])
        s=Store('test','test-pool')
        for role in ['admin','operator','viewer']:
            s.table.put_item(Item={'pk':'USERS','sk':role,'id':role,'name':role,'role':role,'active':True})
        yield s

def event(role,method,path,body=None,token_use='access'):
    return {'rawPath':path,'requestContext':{'http':{'method':method},'authorizer':{'jwt':{'claims':{'sub':role,'token_use':token_use}}}},'body':json.dumps(body or {})}
def record(kind='entries',**changes):
    return validate_record({'id':str(uuid4()),'quality':'Ágata 00 importada','size':'2','date':'2026-10-31T10:30' if kind=='entries' else '2026-10-31','caixotes':10,**changes},kind)
def actor(store,role='admin'): return store.get('USERS',role)

def test_transaction_idempotency_stock_and_soft_delete(store):
    a=actor(store); entry=record(); exit=record('exits',caixotes=4)
    store.add_record(entry,'entries',a); store.add_record(entry,'entries',a)
    store.add_record(exit,'exits',a)
    key=record_key(entry['quality'],entry['size'])
    assert store.get('STOCK',key)['caixotes']==6
    with pytest.raises(AppError,match='negativo'): store.remove_record(entry['id'],'entries',a)
    store.remove_record(exit['id'],'exits',a); store.remove_record(exit['id'],'exits',a)
    assert store.get('STOCK',key)['caixotes']==10
    store.remove_record(entry['id'],'entries',a)
    assert store.get('STOCK',key)['caixotes']==0
    assert store.records()['items']==[]

def test_negative_and_wrong_unit_are_atomic(store):
    a=actor(store); entry=record(); store.add_record(entry,'entries',a)
    for exit in [record('exits',caixotes=11),record('exits',caixotes=0,sacos=1),record('exits',size='3',caixotes=1)]:
        with pytest.raises(AppError) as e: store.add_record(exit,'exits',a)
        assert e.value.status==409
        assert store.get('MOVEMENTS',exit['id']) is None
    assert store.get('STOCK',record_key(entry['quality'],'2'))['caixotes']==10

@pytest.mark.parametrize('role,method,path',[('viewer','POST','/entries'),('viewer','POST','/exits'),('viewer','GET','/users'),('operator','GET','/users'),('operator','GET','/status'),('operator','DELETE','/entries/'+str(uuid4())),('viewer','PATCH','/users/admin')])
def test_server_permissions(store,role,method,path):
    with pytest.raises(AppError) as e: handle(event(role,method,path),store)
    assert e.value.status==403

def test_pausing_and_demotion_immediately_apply(store):
    a=actor(store); stale=actor(store,'operator')
    store.update_user('operator',{'active':False},a)
    with pytest.raises(AppError): handle(event('operator','GET','/records'),store)
    with pytest.raises(AppError): store.add_record(record(),'entries',stale)
    store.update_user('operator',{'active':True,'role':'viewer'},a)
    assert handle(event('operator','GET','/records'),store)['items']==[]
    with pytest.raises(AppError): store.add_record(record(),'entries',stale)

def test_self_admin_change_forbidden(store):
    with pytest.raises(AppError) as e: store.update_user('admin',{'role':'viewer'},actor(store))
    assert e.value.status==400
    assert store.get('USERS','admin')['role']=='admin'

def test_id_token_and_unknown_user_denied(store):
    with pytest.raises(AppError) as e: handle(event('admin','GET','/me',token_use='id'),store)
    assert e.value.status==401
    with pytest.raises(AppError): handle(event('stranger','GET','/records'),store)

@pytest.mark.parametrize('changes',[{'caixotes':-1},{'caixotes':True},{'caixotes':1.1},{'size':'4'},{'date':'2026-02-30T10:00'},{'gross':'NaN'},{'tare':2,'gross':1},{'quality':''},{'notes':'x'*1001}])
def test_input_validation(changes):
    with pytest.raises(AppError) as e: record(**changes)
    assert e.value.status==400

def test_normalized_quality_shares_stock(store):
    a=actor(store); store.add_record(record(),'entries',a)
    store.add_record(record('exits',quality=' agata  00 IMPORTADA ',caixotes=10),'exits',a)
    assert store.get('STOCK',record_key('Ágata 00 importada','2'))['caixotes']==0

def test_pagination_includes_all_records(store):
    for i in range(103):
        value=record(); store.table.put_item(Item={'pk':'MOVEMENTS','sk':value['id'],'record':value,'kind':'entries','created':i,'registeredBy':'test'})
    first=store.records(); second=store.records(first['cursor'])
    assert len(first['items'])==100 and len(second['items'])==3 and not second['cursor']
    assert len({r['id'] for r in first['items']+second['items']})==103

@pytest.mark.parametrize('weight',[0,-1,True,False,'NaN','Infinity','1.234',1000000001,{},[]])
def test_invalid_exit_weight(weight):
    with pytest.raises(AppError) as e: record('exits',weightKg=weight)
    assert e.value.status==400

@pytest.mark.parametrize('weight',[None,''])
def test_optional_exit_weight_preserves_old_records(weight):
    assert 'weightKg' not in record('exits',weightKg=weight)
    assert 'weightKg' not in record('exits')

def test_exit_weight_and_authenticated_author_roundtrip(store):
    from decimal import Decimal
    entry={'id':str(uuid4()),'quality':'Libra','size':'1','date':'2026-11-02T23:59','caixotes':10,'gross':100.10,'tare':0,'registeredBy':'Nome forjado','createdBy':'alguem'}
    outgoing={'id':str(uuid4()),'quality':'Libra','size':'1','date':'2026-11-03','caixotes':2,'weightKg':20.05,'registeredBy':'Nome forjado'}
    handle(event('operator','POST','/entries',entry),store)
    handle(event('admin','POST','/exits',outgoing),store)
    handle(event('admin','POST','/exits',outgoing),store)
    items={r['id']:r for r in handle(event('viewer','GET','/records'),store)['items']}
    assert len(items)==2
    assert items[entry['id']]['registeredBy']=='operator'
    assert items[outgoing['id']]['registeredBy']=='admin'
    assert items[outgoing['id']]['weightKg']==Decimal('20.05')
    assert store.get('STOCK',record_key('Libra','1'))['caixotes']==8
    changed={**outgoing,'weightKg':25}
    with pytest.raises(AppError) as e: handle(event('admin','POST','/exits',changed),store)
    assert e.value.status==409
    store.table.update_item(Key={'pk':'USERS','sk':'operator'},UpdateExpression='SET #name = :n',ExpressionAttributeNames={'#name':'name'},ExpressionAttributeValues={':n':'Novo nome'})
    assert next(r for r in store.records()['items'] if r['id']==entry['id'])['registeredBy']=='operator'


def test_failed_movement_does_not_leave_success_event(store):
    with pytest.raises(AppError): store.add_record(record('exits'),'exits',actor(store))
    assert store.audit()['items']==[]


def test_audit_failure_rolls_back_movement_and_stock(store,monkeypatch):
    original=store.audit_event; existing=original(actor(store),'fixed','fixed',{})
    store.table.put_item(Item=existing['Put']['Item'])
    monkeypatch.setattr(store,'audit_event',lambda *a:existing)
    entry=record()
    with pytest.raises(AppError): store.add_record(entry,'entries',actor(store))
    assert store.get('MOVEMENTS',entry['id']) is None
    assert store.get('STOCK',record_key(entry['quality'],entry['size'])) is None


def test_sessions_are_observed_once_per_authentication_without_tokens(store):
    e=event('viewer','GET','/me');claims=e['requestContext']['authorizer']['jwt']['claims'];claims['auth_time']='1793610000';claims['secret']='do-not-save'
    handle(e,store);handle(e,store)
    assert len(store.audit()['items'])==1
    item=store.audit()['items'][0];assert item['action']=='session.observed' and item['actorId']=='viewer'
    assert 'secret' not in json.dumps(item) and 'do-not-save' not in json.dumps(item)
    claims['auth_time']='1793610001';handle(e,store);assert len(store.audit()['items'])==2


def test_audit_pagination_and_cursor_isolation(store):
    for i in range(103): store.table.put_item(Item=store.audit_event(actor(store),'test','target',{'n':i})['Put']['Item'])
    first=store.audit();second=store.audit(first['cursor'])
    assert len(first['items'])==100 and len(second['items'])==3 and not second['cursor']
    assert len({r['id'] for r in first['items']+second['items']})==103
    import base64
    bad=base64.urlsafe_b64encode(json.dumps({'pk':'USERS','sk':'admin'}).encode()).decode()
    with pytest.raises(AppError): store.audit(bad)

@pytest.mark.parametrize('role',['operator','viewer'])
def test_audit_admin_only(store,role):
    with pytest.raises(AppError) as e: handle(event(role,'GET','/audit'),store)
    assert e.value.status==403

def test_admin_audit_idempotency_and_existing_data(store):
    a=actor(store);entry=record();store.add_record(entry,'entries',a)
    store.add_record(entry,'entries',a)
    movements_before=store.records(); users_before=store.users()
    events=handle(event('admin','GET','/audit'),store)['items']
    assert len(events)==1 and events[0]['action']=='entries.created' and events[0]['actorId']=='admin'
    assert store.records()==movements_before and store.users()==users_before
    store.remove_record(entry['id'],'entries',a);store.remove_record(entry['id'],'entries',a)
    assert len(store.audit()['items'])==2
    with pytest.raises(AppError) as e: handle(event('admin','DELETE','/audit/'+events[0]['id']),store)
    assert e.value.status==404

def test_only_original_roles_and_permissions(store):
    from domain import ROLES
    assert ROLES==('admin','operator','viewer')
    for role in ROLES: assert handle(event(role,'GET','/me'),store)['role']==role
    with pytest.raises(AppError) as e: handle(event('admin','PATCH','/users/operator',{'role':'developer'}),store)
    assert e.value.status==400 and store.get('USERS','operator')['role']=='operator'
    for path in ['/settings','/governance']:
        with pytest.raises(AppError) as e: handle(event('admin','GET',path),store)
        assert e.value.status==404

def test_user_change_audit_and_noop(store):
    handle(event('admin','PATCH','/users/operator',{'role':'viewer'}),store)
    handle(event('admin','PATCH','/users/operator',{'role':'viewer'}),store)
    events=store.audit()['items']
    assert len(events)==1 and events[0]['action']=='user.updated'
    assert events[0]['details']['before']=={'role':'operator','active':True}
    assert events[0]['details']['after']=={'role':'viewer','active':True}
    assert store.get('USERS','admin')['role']=='admin'

def test_paused_admin_cannot_read_audit(store):
    store.table.update_item(Key={'pk':'USERS','sk':'admin'},UpdateExpression='SET active = :no',ExpressionAttributeValues={':no':False})
    with pytest.raises(AppError) as e: handle(event('admin','GET','/audit'),store)
    assert e.value.status==403
