# Guia AWS para publicar e atualizar o projeto

Material de estudo do Projeto Integrado da UNIFEOB. Chácara Retirinho, Grupo Canela. Referência técnica da versão online-2-auditoria, em 8 de novembro de 2026.

Este guia ensina a reconhecer os serviços usados no sistema, preparar o computador, publicar uma cópia nova e atualizar o ambiente existente. Os comandos são exemplos para Linux com Bash. Leia a etapa inteira antes de executá-los. A preparação desta documentação não criou um novo ambiente na AWS.

## 1 Entender o caminho do sistema

Quando alguém abre o site, recebe a interface pelo CloudFront. O Cognito verifica o login. Depois, a interface envia as operações à API, que confere o acesso e grava os dados no DynamoDB. O código e o banco têm funções diferentes: atualizar o código não deve apagar o histórico.

| Serviço | Função neste projeto |
|---|---|
| S3 | Guarda HTML, CSS, JavaScript e logotipo em bucket privado |
| CloudFront | Entrega esses arquivos pelo endereço HTTPS público |
| Cognito | Mantém o login e envia convites de acesso |
| API Gateway | Recebe chamadas HTTPS e valida o access token |
| Lambda | Executa regras de entrada, saída, usuários e auditoria |
| DynamoDB | Persiste movimentos, saldos, usuários e eventos |
| CloudWatch | Reúne logs operacionais da API e da função |
| CloudFormation | Descreve e atualiza a infraestrutura como código |

**Frontend** é a interface; **backend** é a lógica no servidor; **deploy** é a publicação. Uma **stack** é o conjunto de recursos gerenciados pelo CloudFormation. Um **change set** é o plano que mostra as mudanças antes de executá-las.

O sistema usa serviços gerenciados e serverless: a equipe mantém código, permissões e configurações sem administrar uma máquina virtual. IaaS pode ser entendido como alugar infraestrutura, como uma VM; PaaS oferece uma plataforma gerenciada; serverless executa funções sob demanda. O projeto atual não inclui uma VM EC2.

Fonte técnica: código em `infra/build_template.py` e documentação AWS sobre CloudFormation e S3 com OAC, nas referências.

<!-- pagebreak -->
## 2 Acessos região e controle de consumo

O acesso à AWS administra a infraestrutura. O acesso ao sistema da Chácara é um usuário da aplicação no Cognito. Convidar um operador no sistema não o transforma em membro do projeto AWS.

Na nova experiência AWS, use **AWS Settings** para administrar o projeto e **AWS Management Console** para visualizar seus recursos. Confirme a região em AWS Settings > View all projects > Overview > Additional Info > Region. Neste projeto, ela é **us-east-2**.

Antes de qualquer publicação, confira AWS Settings > Billing. O combinado é usar somente plano gratuito e créditos disponíveis, sem ativar plano pago. Serviços podem consumir créditos mesmo que não haja pagamento imediato. Se os créditos ou o plano não permitirem a operação, pare e revise o consumo.

No terminal, dentro da pasta do projeto, configure a sessão. Repita este bloco quando abrir um terminal novo:

```bash
export AWS_PROFILE=pi-computacao-em-nuvem
export AWS_REGION=us-east-2
export AWS_DEFAULT_REGION=us-east-2
export AWS_PAGER=""
aws --version
aws configure get region --profile "$AWS_PROFILE"
BROWSER=firefox aws login --profile "$AWS_PROFILE"
aws sts get-caller-identity
aws freetier get-account-plan-state
```

Use AWS CLI v2 compatível com `aws login` (a documentação indica v2.32.0 ou posterior). O Firefox abrirá a autorização; conclua na página e volte ao terminal. O resultado do STS identifica o projeto acessado. No plano, confira `accountPlanType: FREE` e `accountPlanStatus: ACTIVE`; verifique também o saldo em Billing.

Se a configuração de região estiver vazia, confirme-a primeiro em AWS Settings e então execute `aws configure set region us-east-2 --profile pi-computacao-em-nuvem`. A sessão pode expirar: renove com `aws login`. Não copie tokens ou senhas para o código, README ou GitHub.

Os recursos regionais desta aplicação ficam em us-east-2. CloudFront é global; seu script usa us-east-1 para a API global e para a configuração de entrega de logs. Isso não autoriza mover Lambda, API Gateway ou banco para us-east-1.

Fontes: guia oficial de login da AWS CLI e lista de serviços da nova experiência AWS, nas referências.

<!-- pagebreak -->
## 3 Preparar o computador e testar localmente

Tenha Git, Python 3.13, Node.js e AWS CLI v2. Use os instaladores oficiais indicados nas referências. A pasta do repositório deve conter `web`, `backend`, `infra`, `scripts` e `tests`. Abra o terminal nessa pasta.

Para examinar a interface, abra `ABRIR_PREVIA.html` no navegador. Essa demonstração usa dados fictícios e não grava no banco online. O login da prévia não comprova o funcionamento do Cognito em produção.

Crie um ambiente Python isolado e instale as versões registradas pelo projeto:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m pytest -q tests/test_api.py
node tests/inventory.test.cjs
node tests/access.test.cjs
```

O primeiro comando separa as bibliotecas do projeto das bibliotecas do computador. A ativação vale para o terminal atual. Os testes Python simulam serviços com Moto; os testes JavaScript verificam regras de estoque e autenticação sem criar registros na AWS real.

Depois de alterar a interface, gere novamente a demonstração:

```bash
python scripts/build_preview.py
```

Para validar o modelo da infraestrutura, gere o JSON e execute o linter:

```bash
python infra/build_template.py
cfn-lint infra/template.json
wc -c infra/template.json
```

Instale também o cfn-guard pela distribuição oficial, verificando a versão e o checksum do arquivo baixado. A biblioteca Python não substitui automaticamente o executável do comando abaixo:

```bash
cfn-guard validate --data infra/template.json \
  --rules infra/security.guard --show-summary all
```

Corrija falhas antes de publicar. O envio inline do template ao CloudFormation tem limite de 51.200 bytes; o template desta versão possui 39.935 bytes. Se ele crescer além do limite, prepare envio por S3 ou reorganização do modelo em uma mudança específica. Não remova validações para fazê-lo passar.

<!-- pagebreak -->
## 4 Preparar um ambiente novo de estudo

Esta etapa cria outra infraestrutura e consome créditos. Use-a somente quando decidir criar um laboratório e depois de conferir o plano e o saldo. Para atualizar o site que já existe, pule para a seção 7.

Comece com uma cópia isolada do código, por exemplo clonando o repositório em uma pasta chamada `chacara-retirinho-lab`. Não faça os passos abaixo na pasta usada para atualizar a produção. Cada laboratório deve ter um nome de stack diferente.

Na cópia de laboratório, o arquivo `infra/retained-resources.json` precisa deixar de ser aplicado: ele contém os nomes físicos do ambiente de produção. Guarde-o na pasta local ignorada pelo Git e regenere o template:

```bash
mkdir -p local
mv infra/retained-resources.json local/retained-resources.json
python infra/build_template.py
cfn-lint infra/template.json
cfn-guard validate --data infra/template.json \
  --rules infra/security.guard --show-summary all
```

A remoção é somente na cópia de laboratório. Preserve o arquivo original no repositório e no ambiente existente. Sem isso, um projeto novo tentaria reutilizar nomes de buckets já ocupados; em uma atualização existente, a remoção pode propor substituições.

Confirme a sessão da seção 2 e prepare um plano de criação. Use um nome único para cada plano:

```bash
PI_STACK=chacara-retirinho-lab
PI_PLANO=criar-lab-001
aws cloudformation create-change-set \
  --stack-name "$PI_STACK" \
  --change-set-name "$PI_PLANO" \
  --change-set-type CREATE \
  --template-body file://infra/template.json \
  --capabilities CAPABILITY_IAM
aws cloudformation wait change-set-create-complete \
  --stack-name "$PI_STACK" --change-set-name "$PI_PLANO"
aws cloudformation describe-change-set \
  --stack-name "$PI_STACK" --change-set-name "$PI_PLANO"
```

`CAPABILITY_IAM` reconhece que o modelo cria a função de serviço necessária para a Lambda. Não cria um novo login humano. Criar o plano ainda não executa a criação dos recursos; uma stack provisória pode aparecer como REVIEW_IN_PROGRESS.

<!-- pagebreak -->
## 5 Revisar e executar a primeira publicação

Leia a lista de recursos do plano. Para esta aplicação são esperados S3, CloudFront, Cognito, DynamoDB, Lambda, API Gateway, logs e permissões de serviço. Confirme região, nomes e ausência de dependências de produção. Se o plano falhar, consulte seu motivo; não execute um plano diferente sem revisar.

No console, abra CloudFormation > stack do laboratório > Change sets. Veja as mudanças e os eventos de validação. Pela CLI, os eventos podem ser consultados com o ARN retornado na criação:

```bash
PI_PLANO_ARN=$(aws cloudformation describe-change-set \
  --stack-name "$PI_STACK" --change-set-name "$PI_PLANO" \
  --query ChangeSetId --output text)
aws cloudformation describe-events \
  --change-set-name "$PI_PLANO_ARN"
```

Depois de revisar o plano e decidir criar o laboratório, execute e aguarde:

```bash
aws cloudformation execute-change-set \
  --stack-name "$PI_STACK" --change-set-name "$PI_PLANO"
aws cloudformation wait stack-create-complete \
  --stack-name "$PI_STACK"
aws cloudformation describe-stacks \
  --stack-name "$PI_STACK" --query 'Stacks[0].Outputs'
python scripts/publish_assets.py \
  --profile "$AWS_PROFILE" --stack "$PI_STACK"
```

Aguarde CREATE_COMPLETE antes de publicar os arquivos. O script escreve `web/config.js` com os endereços do ambiente selecionado, envia sete arquivos, solicita atualização do cache, configura a entrega de logs CloudFront e aplica o logo na página do Cognito. Ele exige plano FREE/ACTIVE, mas não substitui a conferência de créditos em Billing.

Para o primeiro administrador de um laboratório vazio, substitua os textos abaixo pelo nome e e-mail da pessoa que receberá o convite:

```bash
python scripts/invite_admin.py \
  --profile "$AWS_PROFILE" --stack "$PI_STACK" \
  --email 'SEU_EMAIL' --name 'SEU_NOME_COMPLETO'
```

O convite é enviado pelo Cognito. Não reutilize esse comando para recriar os usuários já existentes de produção. Abra o `SiteURL` exibido nos Outputs, entre com o convite e defina a senha pessoal. A propagação do CloudFront pode levar alguns minutos.

<!-- pagebreak -->
## 6 Conferir uma publicação nova

Abra o site em HTTPS. Verifique a aparência, o logo, o login e a navegação. Em um laboratório preparado para testes, use movimentos fictícios claramente identificados e confira o ciclo completo: entrada, consulta, saída e saldo restante. Não use dados reais de clientes nesse exercício.

Teste os três perfis com usuários de teste do laboratório: o administrador gerencia acessos e vê auditoria; o operador registra movimentos; o visualizador consulta. A API também precisa impedir operações proibidas, mesmo que alguém tente fazê-las fora dos botões da tela.

Não execute o `scripts/smoke_test.py` fornecido de forma genérica: nesta versão ele tem referências ao ambiente publicado e cria identidades e lançamentos. Um teste remoto automático deve ser adaptado e revisado para o laboratório antes de executar.

| Onde conferir | O que procurar |
|---|---|
| CloudFormation > Outputs | Endereço SiteURL e nomes dos recursos |
| CloudFront > Invalidations | Solicitação de atualização concluída |
| Lambda > Monitor | Erros e duração das chamadas |
| CloudWatch > Log groups | Falhas de execução, status HTTP e latência |
| DynamoDB > Backups | Recuperação contínua habilitada |
| Cognito > User pools | Usuários convidados e estado dos acessos |
| Aplicação > Integrações | Situação das integrações e novos eventos de auditoria |
| AWS Settings > Billing | Consumo, créditos e situação do plano |

Anote data, versão, ambiente, verificações e resultados. Uma tela abrindo não comprova todas as regras do sistema. Os testes locais e as verificações na nuvem se complementam.

Ao terminar os estudos, decida se precisa manter o laboratório. Recursos retidos podem continuar existindo mesmo após excluir a stack, porque o modelo protege dados com Retain. Planeje a limpeza somente dos recursos do laboratório, depois de salvar o que for necessário; nunca remova recursos da produção para economizar sem uma decisão específica.

<!-- pagebreak -->
## 7 Preparar uma alteração no site existente

O ambiente existente usa a stack **chacara-retirinho** e o endereço **https://d1rgdc3ev01d0e.cloudfront.net/**. Uma atualização normal mantém esse endereço. Preserve usuários, movimentos e `infra/retained-resources.json`.

1. Atualize sua cópia do repositório e crie uma branch para a alteração.
2. Faça uma mudança pequena e confira a interface na prévia.
3. Execute os testes locais e as validações da seção 3.
4. Revise o diff para saber exatamente o que será publicado.
5. Registre a versão anterior e confirme os mecanismos de recuperação.
6. Só publique quando o resultado e o plano estiverem revisados.

```bash
git pull --ff-only
git switch -c ajuste-descricao
git diff
git status --short
```

Use uma branch com nome novo. Se houver mudanças locais, salve-as antes do pull. HTML/CSS/textos costumam exigir apenas nova publicação do frontend. Alterações em regras, campos persistidos, permissões ou auditoria podem envolver frontend, API e testes. Acrescentar um campo visual sozinho não faz o servidor gravá-lo.

Antes de atualizar, mantenha um commit da versão estável, o código anterior da Lambda e as referências às versões dos objetos do S3 em uma pasta privada, fora do GitHub. Verifique em DynamoDB a janela de recuperação e a proteção contra exclusão. Não é necessário exportar dados reais para o repositório.

O banco tem recuperação contínua configurada em sete dias. Isso auxilia uma recuperação, mas não elimina a necessidade de um plano: a restauração cria outra tabela e exige validação antes de mudar o aplicativo para ela. A existência do backup não comprova que a equipe já testou a recuperação.

**Compatibilidade:** um campo novo deve aceitar registros antigos que ainda não o possuem. Evite migrações destrutivas. O sistema já segue essa ideia no peso opcional da saída e nos dados históricos de autoria.

<!-- pagebreak -->
## 8 Publicar uma atualização revisada

Na cópia destinada à produção, confira que `infra/retained-resources.json` está presente e contém os nomes originais. Repita a configuração de sessão da seção 2. Se mudou a API ou a infraestrutura, regenere e valide o template e prepare o plano:

```bash
PI_STACK=chacara-retirinho
PI_PLANO=atualizar-001
python infra/build_template.py
cfn-lint infra/template.json
cfn-guard validate --data infra/template.json \
  --rules infra/security.guard --show-summary all
aws cloudformation create-change-set \
  --stack-name "$PI_STACK" \
  --change-set-name "$PI_PLANO" \
  --change-set-type UPDATE \
  --template-body file://infra/template.json \
  --capabilities CAPABILITY_IAM
aws cloudformation wait change-set-create-complete \
  --stack-name "$PI_STACK" --change-set-name "$PI_PLANO"
aws cloudformation describe-change-set \
  --stack-name "$PI_STACK" --change-set-name "$PI_PLANO"
```

Use um nome de plano ainda não utilizado. Compare Action, LogicalResourceId e Replacement. Uma mudança apenas de código da API normalmente modifica Function sem substituí-la. Se Table, Pool ou buckets aparecerem para remoção ou substituição, pare: esse não é o resultado esperado para uma pequena correção. Investigue a diferença antes de executar.

Se não houve mudanças no template, o plano pode informar que não há atualizações. Nesse caso não há plano executável; para uma mudança só do frontend, publique os arquivos depois de testá-los.

Após revisar um plano válido e decidir publicá-lo:

```bash
aws cloudformation execute-change-set \
  --stack-name "$PI_STACK" --change-set-name "$PI_PLANO"
aws cloudformation wait stack-update-complete \
  --stack-name "$PI_STACK"
python scripts/publish_assets.py \
  --profile "$AWS_PROFILE" --stack "$PI_STACK"
```

Publique a API compatível antes do frontend que depende dela. Confira UPDATE_COMPLETE, a invalidação no CloudFront e a aplicação no endereço de sempre. Não execute novamente o convite inicial para os usuários existentes.

<!-- pagebreak -->
## 9 Acompanhar corrigir e recuperar

Após publicar, confira arquivos atualizados, bloqueio de rotas sem login, histórico, saldo e auditoria. Combine qualquer teste que crie ou exclua lançamentos em produção; use um laboratório para exercícios. Registre o resultado, inclusive verificações que ficaram pendentes.

| Sintoma | Primeira verificação |
|---|---|
| AWS CLI informa sessão expirada | Renovar aws login no perfil correto |
| AWS retorna Access Denied inesperado | Conferir projeto, permissões e Billing; se houver plano pago, verificar spend limit |
| Site exibe versão antiga | Aguardar invalidação do CloudFront e atualizar a página |
| API devolve 401 | Conferir login e validade da sessão da aplicação |
| API devolve 403 | Conferir perfil e estado ativo no sistema |
| API devolve 429 | Reduzir frequência e observar limite de requisições |
| Saldo em kg aparece parcial | Conferir movimentos sem peso cadastrado |
| Atualização da stack falha | Ler eventos e causa específica no CloudFormation |

A API tem limite configurado de cinco requisições por segundo e burst de dez. Não trate isso como capacidade comprovada em carga. Os logs de Lambda e API possuem retenção de 14 dias; os logs de acesso do CloudFront ficam em um bucket privado com política de retenção de 14 dias.

A auditoria do aplicativo é diferente do CloudTrail. A primeira mostra operações de negócio e sessões observadas. O Event history do CloudTrail cobre os últimos 90 dias de eventos de gerenciamento por região; não equivale a um arquivo permanente de todas as operações de dados. Não foi configurada uma trilha permanente adicional nesta versão.

Para desfazer uma mudança de código, recupere o commit estável em uma branch de correção, gere o template, revise outro plano e publique os arquivos compatíveis. Não restaure o banco automaticamente por causa de um problema visual: isso poderia descartar lançamentos feitos depois da publicação.

Se a falha envolver dados, primeiro delimite o período e suspenda alterações afetadas de forma combinada. A recuperação pontual do DynamoDB cria **outra tabela**. Valide os registros restaurados e prepare uma mudança específica de integração. Essa operação pode consumir créditos e não foi ensaiada neste projeto.

Fontes: documentação AWS de PITR e CloudTrail, nas referências.

<!-- pagebreak -->
## 10 Usar o GitHub no trabalho do grupo

O GitHub guarda versões do código e da documentação. Ele não atualiza o site da AWS sozinho nesta versão. Para uma mudança pequena, use uma branch, revise os arquivos, registre um commit e envie ao repositório.

```bash
git status --short
git diff
git add web/style.css
git commit -m 'Ajusta o estilo do painel de estoque'
git push -u origin ajuste-descricao
```

O exemplo adiciona somente um arquivo; substitua pelo arquivo realmente alterado. Para criar um pull request, entre no repositório no GitHub, compare a branch com main e descreva problema, solução e testes. Peça revisão ao grupo antes de incorporar. Se o ajuste envolver mais arquivos, confira cada um antes de adicioná-lo.

Mantenha o repositório privado enquanto ele contiver identificações acadêmicas ou configurações específicas do projeto. A publicação de código aberto, caso desejada depois, exige revisar os arquivos e decidir uma licença. Não envie backups do banco, senhas, tokens, arquivos `.aws`, consentimentos assinados ou documentos cadastrais para um repositório público.

**CI** significa executar verificações de integração automaticamente; **CD** trata da entrega ou publicação automatizada. Atualmente o projeto possui testes e scripts, mas a execução e o deploy são manuais. Não há um pipeline GitHub Actions ativo nesta entrega.

Uma evolução possível é criar um workflow para executar pytest, os dois conjuntos de testes JavaScript, cfn-lint e cfn-guard em cada pull request. Primeiro valide esse fluxo sem permissões AWS. Um deploy automático seria outra etapa: exigiria identidade temporária, permissões restritas, proteção do ambiente e autorização de publicação. Não cole access keys no YAML.

## 11 Exercício guiado para aprender

Faça primeiro uma alteração local no texto de uma tela. Gere a prévia, observe a mudança e consulte `git diff`. Registre o commit. Esse exercício mostra a diferença entre salvar um arquivo, registrar uma versão e publicar um site.

Depois, em um laboratório previamente autorizado, publique a mesma alteração e confira a invalidação do CloudFront. Registre qual serviço foi alterado e por que o banco não precisou ser recriado. Para estudar um campo novo, planeje interface, validação no servidor, armazenamento, compatibilidade com históricos e testes antes de implementar.

<!-- pagebreak -->
## Referências e consulta rápida

Documentação oficial consultada em 8 nov. 2026. Interfaces e versões podem mudar; confira a referência antes de repetir um procedimento no futuro.

- AWS. Login da AWS CLI. https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-sign-in.html
- AWS. Instalação da AWS CLI. https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html
- AWS. Serviços da nova experiência. https://docs.aws.amazon.com/accounts/latest/reference/supported-services-sign-up-new.html
- AWS. Change sets no CloudFormation. https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/using-cfn-updating-stacks-changesets.html
- AWS. Eventos do CloudFormation pela CLI. https://docs.aws.amazon.com/cli/latest/reference/cloudformation/describe-events.html
- AWS. Acesso privado ao S3 com CloudFront. https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/private-content-restricting-access-to-s3.html
- AWS. Recuperação pontual do DynamoDB. https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/PointInTimeRecovery_Howitworks.html
- AWS. Histórico do CloudTrail. https://docs.aws.amazon.com/awscloudtrail/latest/userguide/view-cloudtrail-events.html
- AWS. CloudFormation Guard. https://github.com/aws-cloudformation/cloudformation-guard
- GITHUB. Conceitos do GitHub Actions. https://docs.github.com/en/actions/get-started/understand-github-actions
- GIT. Instalação. https://git-scm.com/downloads
- NODE.JS. Downloads. https://nodejs.org/en/download
- PYTHON SOFTWARE FOUNDATION. Downloads. https://www.python.org/downloads/

| Dado | Referência deste projeto |
|---|---|
| Perfil AWS CLI | pi-computacao-em-nuvem |
| Região dos recursos | us-east-2 |
| Stack existente | chacara-retirinho |
| Versão da aplicação | online-2-auditoria |
| Site | https://d1rgdc3ev01d0e.cloudfront.net/ |
| Regra de consumo | Somente plano gratuito e créditos disponíveis |

Para atualizar a produção, retome as seções 7 e 8. Para aprender criando outro ambiente, retome as seções 4 a 6 em uma cópia isolada e após verificar os créditos.
