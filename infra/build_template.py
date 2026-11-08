"""Gera o template; inclui somente o código da API, nunca credenciais."""
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
R = {}
def ref(name): return {'Ref':name}
def sub(value): return {'Fn::Sub':value}
def att(name, attr): return {'Fn::GetAtt':[name,attr]}
def resource(name, typ, properties, why, must=None, retain=False, depends=None):
    r={'Type':typ,'Properties':properties,'Metadata':{'com.aws.cloudformation.Context':{'why':why,'must':must or ['Manter recursos regionais em us-east-2.']}}}
    if retain: r.update(DeletionPolicy='Retain',UpdateReplacePolicy='Retain')
    if depends: r['DependsOn']=depends
    R[name]=r
site=sub('https://${Distribution.DomainName}/')
resource('SiteBucket','AWS::S3::Bucket',{
 'PublicAccessBlockConfiguration':{k:True for k in ['BlockPublicAcls','BlockPublicPolicy','IgnorePublicAcls','RestrictPublicBuckets']},
 'OwnershipControls':{'Rules':[{'ObjectOwnership':'BucketOwnerEnforced'}]},
 'BucketEncryption':{'ServerSideEncryptionConfiguration':[{'ServerSideEncryptionByDefault':{'SSEAlgorithm':'AES256'}}]},
 'VersioningConfiguration':{'Status':'Enabled'},
 'LifecycleConfiguration':{'Rules':[{'Id':'OldAssets','Status':'Enabled','NoncurrentVersionExpiration':{'NoncurrentDays':30},'AbortIncompleteMultipartUpload':{'DaysAfterInitiation':1}}]}
},'Arquivos públicos do aplicativo, acessíveis somente pelo CloudFront.',['Nunca publicar código do servidor, credenciais ou documentos neste bucket.','Bloquear acesso direto público.'],True)
resource('OriginAccess','AWS::CloudFront::OriginAccessControl',{'OriginAccessControlConfig':{'Name':sub('${AWS::StackName}-site'),'OriginAccessControlOriginType':'s3','SigningBehavior':'always','SigningProtocol':'sigv4'}},'CloudFront assina as leituras do bucket privado.')
resource('Headers','AWS::CloudFront::ResponseHeadersPolicy',{'ResponseHeadersPolicyConfig':{
 'Name':sub('${AWS::StackName}-headers'),
 'SecurityHeadersConfig':{
  'ContentTypeOptions':{'Override':True}, 'FrameOptions':{'FrameOption':'DENY','Override':True},
  'ReferrerPolicy':{'ReferrerPolicy':'no-referrer','Override':True},
  'StrictTransportSecurity':{'AccessControlMaxAgeSec':31536000,'IncludeSubdomains':True,'Override':True},
  'ContentSecurityPolicy':{'ContentSecurityPolicy':"default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self'; font-src 'self'; connect-src 'self' https://*.execute-api.us-east-2.amazonaws.com https://*.auth.us-east-2.amazoncognito.com; base-uri 'none'; object-src 'none'; frame-ancestors 'none'; form-action 'self'; upgrade-insecure-requests",'Override':True}},
 'CustomHeadersConfig':{'Items':[{'Header':'Permissions-Policy','Value':'camera=(), microphone=(), geolocation=()','Override':True}]}
}},'Limitar scripts e conexões aos arquivos locais e aos serviços usados pelo sistema.')
resource('CachePolicy','AWS::CloudFront::CachePolicy',{'CachePolicyConfig':{'Name':sub('${AWS::StackName}-cache'),'MinTTL':0,'DefaultTTL':60,'MaxTTL':86400,'ParametersInCacheKeyAndForwardedToOrigin':{'CookiesConfig':{'CookieBehavior':'none'},'HeadersConfig':{'HeaderBehavior':'none'},'QueryStringsConfig':{'QueryStringBehavior':'none'},'EnableAcceptEncodingGzip':True,'EnableAcceptEncodingBrotli':True}}},'Ignorar parâmetros OAuth no cache; navegador processa o código de autenticação.')
resource('Distribution','AWS::CloudFront::Distribution',{'DistributionConfig':{
 'Enabled':True,'Comment':'Chacara Retirinho - controle de batatas','DefaultRootObject':'index.html','PriceClass':'PriceClass_100','HttpVersion':'http2and3','IPV6Enabled':True,
 'Origins':[{'Id':'site','DomainName':att('SiteBucket','RegionalDomainName'),'OriginAccessControlId':ref('OriginAccess'),'S3OriginConfig':{'OriginAccessIdentity':''}}],
 'DefaultCacheBehavior':{'TargetOriginId':'site','ViewerProtocolPolicy':'redirect-to-https','AllowedMethods':['GET','HEAD','OPTIONS'],'CachedMethods':['GET','HEAD'],'Compress':True,'CachePolicyId':ref('CachePolicy'),'ResponseHeadersPolicyId':ref('Headers')},
 'ViewerCertificate':{'CloudFrontDefaultCertificate':True}
}},'HTTPS público usando domínio CloudFront sem compra de domínio.',['Usar somente origem S3 privada e plano por uso coberto pelo projeto FREE/créditos.'])
resource('SitePolicy','AWS::S3::BucketPolicy',{'Bucket':ref('SiteBucket'),'PolicyDocument':{'Version':'2012-10-17','Statement':[
 {'Sid':'CloudFrontOnly','Effect':'Allow','Principal':{'Service':'cloudfront.amazonaws.com'},'Action':'s3:GetObject','Resource':sub('${SiteBucket.Arn}/*'),'Condition':{'StringEquals':{'AWS:SourceAccount':ref('AWS::AccountId'),'AWS:SourceArn':sub('arn:${AWS::Partition}:cloudfront::${AWS::AccountId}:distribution/${Distribution}')}}},
 {'Sid':'RequireTLS','Effect':'Deny','Principal':'*','Action':'s3:*','Resource':[att('SiteBucket','Arn'),sub('${SiteBucket.Arn}/*')],'Condition':{'Bool':{'aws:SecureTransport':'false'}}}
]}},'Restringir arquivos à distribuição e exigir transporte seguro.')
resource('AccessLogsBucket','AWS::S3::Bucket',{
 'PublicAccessBlockConfiguration':{k:True for k in ['BlockPublicAcls','BlockPublicPolicy','IgnorePublicAcls','RestrictPublicBuckets']},
 'OwnershipControls':{'Rules':[{'ObjectOwnership':'BucketOwnerEnforced'}]},
 'BucketEncryption':{'ServerSideEncryptionConfiguration':[{'ServerSideEncryptionByDefault':{'SSEAlgorithm':'AES256'}}]},
 'VersioningConfiguration':{'Status':'Enabled'},
 'LifecycleConfiguration':{'Rules':[{'Id':'Retention','Status':'Enabled','ExpirationInDays':14,'NoncurrentVersionExpiration':{'NoncurrentDays':1}}]}
},'Logs padrão CloudFront sem campos de query/cookies, privados e retidos por 14 dias.',retain=True)
resource('AccessLogsPolicy','AWS::S3::BucketPolicy',{'Bucket':ref('AccessLogsBucket'),'PolicyDocument':{'Version':'2012-10-17','Statement':[
 {'Effect':'Deny','Principal':'*','Action':'s3:*','Resource':[att('AccessLogsBucket','Arn'),sub('${AccessLogsBucket.Arn}/*')],'Condition':{'Bool':{'aws:SecureTransport':'false'}}},
 {'Effect':'Allow','Principal':{'Service':'delivery.logs.amazonaws.com'},'Action':'s3:GetBucketAcl','Resource':att('AccessLogsBucket','Arn'),'Condition':{'StringEquals':{'aws:SourceAccount':ref('AWS::AccountId')},'ArnLike':{'aws:SourceArn':sub('arn:${AWS::Partition}:logs:us-east-1:${AWS::AccountId}:*')}}},
 {'Effect':'Allow','Principal':{'Service':'delivery.logs.amazonaws.com'},'Action':'s3:PutObject','Resource':sub('${AccessLogsBucket.Arn}/*'),'Condition':{'StringEquals':{'aws:SourceAccount':ref('AWS::AccountId'),'s3:x-amz-acl':'bucket-owner-full-control'},'ArnLike':{'aws:SourceArn':sub('arn:${AWS::Partition}:logs:us-east-1:${AWS::AccountId}:*')}}}
]}},'Permitir somente a entrega de logs do próprio projeto. A configuração global é feita pelo script de publicação.')
resource('Table','AWS::DynamoDB::Table',{'BillingMode':'PAY_PER_REQUEST','AttributeDefinitions':[{'AttributeName':'pk','AttributeType':'S'},{'AttributeName':'sk','AttributeType':'S'}],'KeySchema':[{'AttributeName':'pk','KeyType':'HASH'},{'AttributeName':'sk','KeyType':'RANGE'}],'DeletionProtectionEnabled':True,'PointInTimeRecoverySpecification':{'PointInTimeRecoveryEnabled':True,'RecoveryPeriodInDays':7}},'Movimentos, saldos e acessos da única propriedade. Chave STOCK por qualidade/tamanho e atualizações transacionais.',['Retenção e proteção contra exclusão; criptografia padrão AWS-owned sem CMK pago.','Não reutilizar para propriedades independentes sem acrescentar isolamento.'],True)
resource('Pool','AWS::Cognito::UserPool',{
 'UserPoolName':sub('${AWS::StackName}-users'),'UserPoolTier':'LITE','UsernameAttributes':['email'],'UsernameConfiguration':{'CaseSensitive':False},'AutoVerifiedAttributes':['email'],
 'Schema':[{'Name':'email','Required':True,'Mutable':True},{'Name':'name','Required':True,'Mutable':True}],
 'Policies':{'PasswordPolicy':{'MinimumLength':12,'RequireLowercase':True,'RequireUppercase':True,'RequireNumbers':True,'RequireSymbols':True,'TemporaryPasswordValidityDays':7}},
 'MfaConfiguration':'OPTIONAL','EnabledMfas':['SOFTWARE_TOKEN_MFA'],
 'AccountRecoverySetting':{'RecoveryMechanisms':[{'Name':'verified_email','Priority':1}]},
 'AdminCreateUserConfig':{'AllowAdminCreateUserOnly':True,'InviteMessageTemplate':{'EmailSubject':'Seu acesso - Chácara Retirinho','EmailMessage':sub('Você recebeu um convite para o controle de batatas da Chácara Retirinho.<br>Acesse https://${Distribution.DomainName}/ e clique em Entrar no sistema.<br>E-mail de acesso: {username}<br>Senha temporária: {####}<br>Crie sua senha pessoal no primeiro acesso. Este convite vale por 7 dias.')}},
 'EmailConfiguration':{'EmailSendingAccount':'COGNITO_DEFAULT'},'DeletionProtection':'ACTIVE'
},'Autenticação por convite; plano Lite e interface clássica.',['Não habilitar cadastro público nem guardar senhas no aplicativo.'],True)
resource('PoolDomain','AWS::Cognito::UserPoolDomain',{'Domain':sub('${AWS::StackName}-${AWS::AccountId}'),'UserPoolId':ref('Pool'),'ManagedLoginVersion':1},'Domínio de login HTTPS fornecido pelo Cognito, sem certificado ou domínio comprado.')
resource('Client','AWS::Cognito::UserPoolClient',{
 'UserPoolId':ref('Pool'),'ClientName':sub('${AWS::StackName}-web'),'GenerateSecret':False,
 'AllowedOAuthFlowsUserPoolClient':True,'AllowedOAuthFlows':['code'],'AllowedOAuthScopes':['openid','email','profile','aws.cognito.signin.user.admin'],
 'SupportedIdentityProviders':['COGNITO'],'CallbackURLs':[site],'LogoutURLs':[site],
 'ExplicitAuthFlows':['ALLOW_USER_SRP_AUTH','ALLOW_USER_PASSWORD_AUTH'],
 'AccessTokenValidity':15,'IdTokenValidity':15,'RefreshTokenValidity':1,'TokenValidityUnits':{'AccessToken':'minutes','IdToken':'minutes','RefreshToken':'days'},
 'EnableTokenRevocation':True,'PreventUserExistenceErrors':'ENABLED','AuthSessionValidity':3,
 'ReadAttributes':['email','email_verified','name'],'WriteAttributes':['email','name']
},'Cliente público com authorization code/PKCE e tokens curtos.',['Não criar client secret para o navegador.','Servidor lê permissões atuais do banco em cada operação.'])
resource('ApiLogs','AWS::Logs::LogGroup',{'RetentionInDays':14},'Log HTTP sem tokens, corpos ou parâmetros de autenticação.')
resource('LambdaLogs','AWS::Logs::LogGroup',{'LogGroupName':sub('/aws/lambda/${AWS::StackName}-api'),'RetentionInDays':14},'Erros operacionais da API com retenção limitada.')
resource('ApiRole','AWS::IAM::Role',{'AssumeRolePolicyDocument':{'Version':'2012-10-17','Statement':[{'Effect':'Allow','Principal':{'Service':'lambda.amazonaws.com'},'Action':'sts:AssumeRole'}]},'Policies':[{'PolicyName':'RuntimeOnly','PolicyDocument':{'Version':'2012-10-17','Statement':[
 {'Effect':'Allow','Action':['dynamodb:GetItem','dynamodb:Query','dynamodb:PutItem','dynamodb:UpdateItem','dynamodb:ConditionCheckItem'],'Resource':att('Table','Arn')},
 {'Effect':'Allow','Action':['cognito-idp:AdminCreateUser','cognito-idp:AdminDisableUser'],'Resource':att('Pool','Arn')},
 {'Effect':'Allow','Action':['logs:CreateLogStream','logs:PutLogEvents'],'Resource':att('LambdaLogs','Arn')}
]}}]},'Permissões mínimas da API para a tabela, o pool e seus logs.')
code=(ROOT/'backend/domain.py').read_text()+'\n'+(ROOT/'backend/app.py').read_text()
code='\n'.join(line for line in code.splitlines() if not line.startswith('from domain import '))+'\n'
resource('Function','AWS::Lambda::Function',{'FunctionName':sub('${AWS::StackName}-api'),'Runtime':'python3.13','Architectures':['arm64'],'Handler':'index.handler','Role':att('ApiRole','Arn'),'MemorySize':256,'Timeout':15,'Environment':{'Variables':{'TABLE_NAME':ref('Table'),'USER_POOL_ID':ref('Pool'),'APP_VERSION':'online-2-auditoria'}},'Code':{'ZipFile':code}},'API sob demanda; auditoria transacional e consulta exclusiva do administrador.', ['Preservar os três perfis existentes, usuários e movimentos.','Não incluir senhas ou tokens nos eventos de auditoria.'])
resource('Api','AWS::ApiGatewayV2::Api',{'Name':sub('${AWS::StackName}-http'),'ProtocolType':'HTTP','CorsConfiguration':{'AllowOrigins':[sub('https://${Distribution.DomainName}')],'AllowMethods':['GET','POST','PATCH','DELETE','OPTIONS'],'AllowHeaders':['authorization','content-type'],'MaxAge':300}},'API HTTPS; CORS limitado ao site publicado.')
resource('Jwt','AWS::ApiGatewayV2::Authorizer',{'ApiId':ref('Api'),'AuthorizerType':'JWT','IdentitySource':['$request.header.Authorization'],'Name':'CognitoAccess','JwtConfiguration':{'Audience':[ref('Client')],'Issuer':sub('https://cognito-idp.${AWS::Region}.amazonaws.com/${Pool}')}},'Validar assinatura, emissor, audiência e validade antes da função.')
resource('Integration','AWS::ApiGatewayV2::Integration',{'ApiId':ref('Api'),'IntegrationType':'AWS_PROXY','IntegrationUri':att('Function','Arn'),'PayloadFormatVersion':'2.0','TimeoutInMillis':20000},'Encaminhar chamadas autenticadas para a API Python.')
resource('Route','AWS::ApiGatewayV2::Route',{'ApiId':ref('Api'),'RouteKey':'$default','Target':sub('integrations/${Integration}'),'AuthorizationType':'JWT','AuthorizerId':ref('Jwt'),'AuthorizationScopes':['aws.cognito.signin.user.admin']},'Exigir access token em todas as rotas.',['Nenhuma rota de dados anônima.'])
resource('Stage','AWS::ApiGatewayV2::Stage',{'ApiId':ref('Api'),'StageName':'$default','AutoDeploy':True,'DefaultRouteSettings':{'ThrottlingBurstLimit':10,'ThrottlingRateLimit':5},'AccessLogSettings':{'DestinationArn':att('ApiLogs','Arn'),'Format':'{"requestId":"$context.requestId","status":"$context.status","route":"$context.routeKey","latency":"$context.responseLatency"}'}},'Limitar volume de requisições e registrar resultados sem conteúdo sensível.')
# OPTIONS precisa permanecer anônimo para o preflight de CORS em uma rota $default protegida.
resource('Options','AWS::ApiGatewayV2::Route',{'ApiId':ref('Api'),'RouteKey':'OPTIONS /{proxy+}','AuthorizationType':'NONE','Target':sub('integrations/${Integration}')},'Permitir preflight CORS; resposta vazia da função com cabeçalhos do API Gateway, sem leitura de dados.')
resource('Invoke','AWS::Lambda::Permission',{'Action':'lambda:InvokeFunction','FunctionName':ref('Function'),'Principal':'apigateway.amazonaws.com','SourceArn':sub('arn:${AWS::Partition}:execute-api:${AWS::Region}:${AWS::AccountId}:${Api}/*'),'SourceAccount':ref('AWS::AccountId')},'Somente esta API pode invocar a função.')
# Recursos preservados durante a primeira implantação são importados com os nomes originais.
retained = ROOT/'infra/retained-resources.json'
if retained.exists():
    for logical_id, properties in json.loads(retained.read_text()).items():
        R[logical_id]['Properties'].update(properties)
template={'AWSTemplateFormatVersion':'2010-09-09','Description':'Controle de batatas Chacara Retirinho: site HTTPS, login por convite e estoque transacional compartilhado. Recursos regionais somente us-east-2; manter plano FREE e usar creditos.','Metadata':{'AWSToolsMetrics':{'AWSAgentToolkit':'aws-cloudformation@3'}},'Resources':R,'Outputs':{k:{'Value':v} for k,v in {'SiteURL':site,'ApiURL':att('Api','ApiEndpoint'),'UserPoolId':ref('Pool'),'ClientId':ref('Client'),'AuthDomain':sub('https://${PoolDomain}.auth.${AWS::Region}.amazoncognito.com'),'TableName':ref('Table'),'DistributionId':ref('Distribution'),'S3Bucket':ref('SiteBucket'),'FunctionName':ref('Function'),'AccessLogsBucket':ref('AccessLogsBucket')}.items()}}
# Unicode escapado preserva os acentos mesmo quando a CLI usa um locale ASCII.
path=ROOT/'infra/template.json'; path.write_text(json.dumps(template,ensure_ascii=True,separators=(',',':'))); print(f'Template gerado: {path.name}, {path.stat().st_size} bytes, {len(R)} recursos.')
