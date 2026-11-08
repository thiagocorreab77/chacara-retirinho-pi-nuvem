"""Convite inicial explícito; a senha temporária é gerada e enviada pelo Cognito."""
import argparse
from datetime import datetime,timezone
import boto3
p=argparse.ArgumentParser();p.add_argument('--email',required=True);p.add_argument('--name',required=True);p.add_argument('--profile',default='pi-computacao-em-nuvem');p.add_argument('--stack',default='chacara-retirinho');args=p.parse_args()
s=boto3.Session(profile_name=args.profile,region_name='us-east-2')
o={x['OutputKey']:x['OutputValue'] for x in s.client('cloudformation').describe_stacks(StackName=args.stack)['Stacks'][0]['Outputs']}
c=s.client('cognito-idp');table=s.resource('dynamodb').Table(o['TableName'])
email=args.email.strip().lower()
# Falha se o e-mail já existe: não substituir perfil, senha ou acesso de alguém.
u=c.admin_create_user(UserPoolId=o['UserPoolId'],Username=email,MessageAction='SUPPRESS',UserAttributes=[{'Name':'email','Value':email},{'Name':'name','Value':args.name}])['User']
sub=next(a['Value'] for a in u['Attributes'] if a['Name']=='sub')
try:
    table.put_item(Item={'pk':'USERS','sk':sub,'id':sub,'username':u['Username'],'email':email,'name':args.name,'role':'admin','active':True,'created':datetime.now(timezone.utc).isoformat()},ConditionExpression='attribute_not_exists(pk)')
except Exception:
    c.admin_disable_user(UserPoolId=o['UserPoolId'],Username=u['Username']);raise
c.admin_create_user(UserPoolId=o['UserPoolId'],Username=email,MessageAction='RESEND',DesiredDeliveryMediums=['EMAIL'])
print('Convite de administrador solicitado ao Cognito para',email)
print('Acesse',o['SiteURL'])
