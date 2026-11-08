"""Publica apenas web/. Requer perfil AWS local; não persiste credenciais."""
import argparse
import json
import mimetypes
from pathlib import Path
import boto3
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--profile',default='pi-computacao-em-nuvem');p.add_argument('--stack',default='chacara-retirinho');args=p.parse_args()
session=boto3.Session(profile_name=args.profile,region_name='us-east-2')
plan=session.client('freetier').get_account_plan_state()
if plan['accountPlanType']!='FREE' or plan['accountPlanStatus']!='ACTIVE': raise SystemExit('Publicação interrompida: confirme o plano e os créditos antes de continuar.')
stack=session.client('cloudformation').describe_stacks(StackName=args.stack)['Stacks'][0]
if stack['StackStatus'] not in ('CREATE_COMPLETE','UPDATE_COMPLETE'): raise SystemExit('A infraestrutura ainda não está pronta.')
o={x['OutputKey']:x['OutputValue'] for x in stack['Outputs']}
config={'apiUrl':o['ApiURL'],'authDomain':o['AuthDomain'],'clientId':o['ClientId']}
(ROOT/'web/config.js').write_text('window.RETIRINHO_CONFIG = '+json.dumps(config)+';\n')
s3=session.client('s3')
files=['index.html','style.css','script.js','access.js','inventory.js','config.js','assets/logo.jpeg']
for name in files:
    s3.upload_file(str(ROOT/'web'/name),o['S3Bucket'],name,ExtraArgs={'ContentType':mimetypes.guess_type(name)[0] or 'application/octet-stream','CacheControl':'public,max-age=86400' if name.startswith('assets/') else 'no-cache','ServerSideEncryption':'AES256'})
# CloudFront é global. Sua API e a entrega de logs usam us-east-1; dados ficam em us-east-2.
cloudfront=session.client('cloudfront',region_name='us-east-1')
import time
cloudfront.create_invalidation(DistributionId=o['DistributionId'],InvalidationBatch={'Paths':{'Quantity':1,'Items':['/*']},'CallerReference':'publish-'+str(time.time_ns())})
account=session.client('sts').get_caller_identity()['Account']
logs=session.client('logs',region_name='us-east-1')
source=args.stack+'-site'
logs.put_delivery_source(name=source,resourceArn=f"arn:aws:cloudfront::{account}:distribution/{o['DistributionId']}",logType='ACCESS_LOGS')
destination=logs.put_delivery_destination(name=source,deliveryDestinationConfiguration={'destinationResourceArn':'arn:aws:s3:::'+o['AccessLogsBucket']},outputFormat='json')['deliveryDestination']
# Somente campos operacionais; nunca query, cookies, referer ou cabeçalhos de autenticação.
fields=['date','time','cs-method','cs-uri-stem','sc-status','x-edge-result-type','time-taken','ssl-protocol']
existing=[]
for page in logs.get_paginator('describe_deliveries').paginate():
    existing.extend(d for d in page.get('deliveries',[]) if d['deliverySourceName']==source)
if not existing:
    logs.create_delivery(deliverySourceName=source,deliveryDestinationArn=destination['arn'],recordFields=fields)
else:
    for delivery in existing: logs.update_delivery_configuration(id=delivery['id'],recordFields=fields)
session.client('cognito-idp').set_ui_customization(UserPoolId=o['UserPoolId'],ClientId=o['ClientId'],CSS='.banner-customizable {background-color: #006634;} .submitButton-customizable {background-color: #006634; color: #ffffff;} .submitButton-customizable:hover {background-color: #00532a;}',ImageFile=(ROOT/'web/assets/logo.jpeg').read_bytes())
print('Site publicado:',o['SiteURL'])
print('Arquivos enviados:',len(files),'; logs sem dados de autenticação configurados.')
