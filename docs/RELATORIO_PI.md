# Sistema de controle de batatas em nuvem

Documentação do Projeto Integrado da Chácara Retirinho, Grupo Canela. UNIFEOB, Escola de Negócios e Tecnologia EAD, curso de Análise e Desenvolvimento de Sistemas, módulo Computação em Nuvem, 4º trimestre letivo de 2026.

Gabriel Trinca de Marchi, RA 24002112. Miguel Augusto de Faria Camilo, RA 24002076. Thiago Perinoto Correa, RA 24002167. Wagner da Silva Gomes Junior, RA 24002152.

Orientadora indicada no documento do módulo: Prof.ª Mariangela Martimbianco Santos. São João da Boa Vista, SP, novembro de 2026. Versão técnica de referência: online-2-auditoria, publicada em 8 de novembro de 2026.

## Resumo

O projeto desenvolveu e publicou um sistema web de controle de entradas, saídas e estoque de batatas para a Chácara Retirinho, Grupo Canela. A solução centraliza movimentos por qualidade, tamanho e embalagem, identifica o responsável pelos lançamentos e separa os acessos de administrador, operador e visualizador. A infraestrutura utiliza serviços gerenciados da AWS: CloudFront, S3, Cognito, API Gateway, Lambda, DynamoDB, CloudWatch e CloudFormation. A qualidade foi trabalhada por validação de dados, autorização no servidor, transações de estoque, testes automatizados e revisão da publicação. A revisão documentada apresentou 64 testes locais aprovados e 15 verificações online de leitura e OPTIONS aprovadas, além da preservação dos dados e acessos existentes. O fluxo completo de gravação autenticada, o desempenho sob carga e a restauração real de backup ainda não foram comprovados por essa verificação. O trabalho integra a aplicação prática de computação em nuvem ao controle de qualidade do software e registra os limites do resultado alcançado.

**Palavras-chave:** computação em nuvem; qualidade de software; controle de estoque; AWS; rastreabilidade.

## 1 Contexto e finalidade

A necessidade apresentada foi disponibilizar um sistema compartilhado para acompanhar a movimentação de batatas. Além das quantidades recebidas e retiradas, o usuário precisava visualizar o estoque atual, filtrar informações e identificar quem efetuou cada lançamento. A aplicação foi ajustada de forma incremental conforme as solicitações recebidas.

Este documento descreve a solução implementada, a arquitetura, as regras, a operação e as evidências de qualidade. Ele apoia a entrega textual e as análises das unidades de estudo. A entrega institucional também requer pôster, vídeo e documentos da beneficiária, tratados na seção final.

<!-- pagebreak -->
## 2 Beneficiária e objetivos

A organização identificada no projeto é a **Chácara Retirinho, Grupo Canela**, cujo logotipo foi fornecido para a aplicação. O sistema atende ao controle de batatas da propriedade, com acesso por navegador. Razão social, CNPJ, endereço completo e representante legal não foram fornecidos para esta documentação; devem ser confirmados pelo grupo e comprovados pelos anexos reais da empresa.

O objetivo geral é disponibilizar uma aplicação web em nuvem que organize os movimentos e os saldos de batatas com controle de acesso e rastreabilidade.

Os objetivos específicos são registrar entradas e saídas por qualidade, tamanho e embalagem; facilitar a consulta do histórico e do saldo atual; vincular as operações ao usuário autenticado; separar permissões; publicar a aplicação em HTTPS; preservar dados entre atualizações; e verificar regras críticas por testes e monitoramento.

## 3 Escopo e evolução do desenvolvimento

O desenvolvimento partiu de uma interface em HTML, CSS e JavaScript e evoluiu para armazenamento compartilhado, autenticação e publicação em nuvem. A separação entre visão geral e registro de movimentos simplificou a navegação. Foram acrescentados tipos e tamanhos de batata, embalagens independentes, filtros de período, peso de saída e autoria dos movimentos.

A versão final adotada mantém os perfis Administrador, Operador e Visualizador. Auditoria e acompanhamento de acessos foram incorporados à aba Integrações do administrador. A proposta intermediária de perfil de desenvolvedor e edição dinâmica de campos não faz parte desta versão.

O método empregado foi incremental: identificar a necessidade, alterar a interface e as regras afetadas, validar localmente, revisar a infraestrutura e publicar uma revisão controlada. As evidências não registram uma divisão formal de atividades por integrante; por isso, este documento não atribui contribuições individuais não confirmadas.

O escopo não inclui faturamento, emissão fiscal, múltiplas empresas independentes, conversão automática de embalagens ou edição livre da estrutura do banco. O sistema depende de conexão com a internet para consultar e gravar os dados online.

<!-- pagebreak -->
## 4 Requisitos e regras de negócio

| Identificação | Requisito implementado | Referência no código |
|---|---|---|
| RF01 | Registrar entradas e saídas com validação | backend/domain.py e app.py |
| RF02 | Controlar saldo por qualidade, tamanho e embalagem | domain.py e web/inventory.js |
| RF03 | Consultar históricos e filtrar por período | web/script.js e inventory.js |
| RF04 | Identificar o autor autenticado do movimento | backend/app.py |
| RF05 | Aplicar três perfis e pausar acessos | backend/app.py e web/access.js |
| RF06 | Consultar auditoria e integrações como administrador | backend/app.py e web/script.js |
| RNF01 | Exigir HTTPS e autenticação nas rotas de dados | infra/build_template.py |
| RNF02 | Evitar saldo negativo e gravações duplicadas | Transações e idempotência na API |
| RNF03 | Preservar históricos em atualizações | Exclusão lógica e compatibilidade |
| RNF04 | Permitir validação e reprodução da infraestrutura | tests/ e infra/ |

As qualidades disponibilizadas incluem Ágata 00 importada, Ágata F1 importada, Orkestra 00 importada, Orkestra F1 importada, Asterix, Potia e Libra. Os tamanhos são 1, 2 e 3. Caixotes, sacos, meiões e bags têm quantidades independentes: uma saída de sacos não reduz caixotes.

Na saída, o operador seleciona uma embalagem e sua quantidade. O peso em kg é opcional e deve ser positivo quando informado. Na entrada, o peso líquido é obtido pela diferença entre bruto e tara. Ausência de peso em movimentos antigos pode tornar o saldo em kg parcial. A proteção transacional contra retirada excessiva é aplicada às embalagens; o saldo em kg é uma informação calculada, não um limite transacional equivalente.

O filtro de datas inclui os dias inicial e final no histórico e nos totais de movimentação. O cartão de estoque atual considera todos os períodos para a qualidade e o tamanho selecionados. Câmara e pesquisa textual não transformam esse cartão em um inventário físico por câmara. Essa distinção evita confundir movimentos de um período com o saldo disponível.

<!-- pagebreak -->
## 5 Perfis e uso da aplicação

| Ação | Administrador | Operador | Visualizador |
|---|:---:|:---:|:---:|
| Ver estoque, histórico e filtros | Sim | Sim | Sim |
| Registrar entradas e saídas | Sim | Sim | Não |
| Excluir logicamente movimentos | Sim | Não | Não |
| Gerenciar usuários e permissões | Sim | Não | Não |
| Consultar Integrações e Auditoria | Sim | Não | Não |

A visão geral reúne indicadores e históricos. O registro de movimentos fica em aba própria. Para registrar uma entrada, o usuário preenche a classificação, as quantidades e os demais dados disponíveis. Para registrar uma saída, seleciona classificação, embalagem, quantidade, data e, quando conhecido, peso. Após salvar, consulta o histórico e o saldo atualizado.

O servidor associa a operação à identidade autenticada. A autoria de entradas e saídas aparece no histórico e na exportação, sem depender de um nome digitado livremente no formulário. Registros antigos são preservados; a aplicação não inventa autores ausentes em dados legados.

Na gestão de acessos, o administrador convida usuários e define seus perfis. Pausar um acesso impede novas operações mesmo que ainda exista um token válido. A API consulta o estado atual do usuário a cada chamada. Um administrador não pode alterar o próprio acesso pelo fluxo de gestão previsto.

O aplicativo atualiza informações periodicamente, a cada 45 segundos quando a página está visível, e após operações de gravação. Também há atualização manual. Em falha de conexão, o formulário é preservado para permitir correção ou nova tentativa.

O relato de seletores invisíveis em uma gravação de tela deve ser distinguido de uma falha funcional. As opções nativas podem não aparecer em determinados mecanismos de captura. A revisão documentada não contém uma reprodução controlada desse efeito em todos os navegadores; portanto, não o apresenta como defeito comprovadamente corrigido.

<!-- pagebreak -->
## 6 Arquitetura e persistência

O frontend é composto por HTML, CSS e JavaScript. Seus arquivos ficam em um bucket S3 privado e são entregues pelo CloudFront. O Cognito oferece a tela de login e o gerenciamento de credenciais. O API Gateway recebe o access token e encaminha chamadas autorizadas à função Lambda. A função aplica as regras de negócio e acessa o DynamoDB.

A tabela utiliza as chaves `pk` e `sk`. Os conjuntos lógicos incluem USERS para acessos da aplicação, MOVEMENTS para lançamentos, STOCK para saldos, AUDIT para eventos e SESSIONS para evitar duplicação de sessões observadas. Essa organização é voltada a uma única propriedade; atender empresas independentes exigiria um desenho adicional de isolamento.

Movimentos possuem identificador único e validação de idempotência: repetir uma solicitação igual não deve duplicar a movimentação. A alteração de estoque e o evento de auditoria da operação são gravados em transação. Condições sobre o saldo ajudam a impedir retiradas concorrentes acima da quantidade disponível.

A exclusão de um movimento é lógica e restrita ao administrador. O sistema preserva o registro e ajusta o saldo com as verificações necessárias. Uma entrada não pode ser retirada do cálculo se isso fizer o saldo das embalagens ficar negativo.

| Interface da API | Finalidade | Acesso |
|---|---|---|
| GET /me | Perfil atual e sessão observada | Usuário ativo |
| GET /records | Consulta paginada dos movimentos | Usuário ativo |
| POST /entries e /exits | Registrar movimento | Admin ou operador |
| DELETE /entries/{id} e /exits/{id} | Exclusão lógica | Admin |
| GET e POST /users | Listar e convidar acessos | Admin |
| PATCH /users/{id} | Alterar acesso | Admin |
| GET /audit e /status | Auditoria e integrações | Admin |

OPTIONS atende ao preflight do navegador sem acessar o banco. A permissão visual dos botões complementa a autorização no servidor; ocultar um botão não seria suficiente para proteger a API.

<!-- pagebreak -->
## 7 Análise da unidade de Computação em Nuvem

A solução aplica provisionamento de infraestrutura, hospedagem, autenticação, permissões, implantação e monitoramento. O CloudFormation descreve 23 recursos e seus relacionamentos. O gerador local incorpora o código da API no template, permitindo revisar a mudança junto com sua infraestrutura.

CloudFront e S3 atendem à publicação da interface. O bucket não é exposto como um site público de S3: a distribuição usa Origin Access Control para ler a origem privada. O endereço fornecido pelo CloudFront usa HTTPS; não foi adquirido nem configurado um domínio próprio. A documentação da AWS sobre acesso privado ao S3 fundamenta essa configuração.

API Gateway, Lambda e DynamoDB reduzem a necessidade de administrar servidores. Lambda executa Python 3.13 em arm64, com 256 MB e timeout de 15 segundos. O DynamoDB usa capacidade sob demanda. Esses serviços oferecem mecanismos gerenciados de escalabilidade, mas o projeto não realizou teste de carga que comprove uma capacidade máxima ou um nível de serviço próprio.

Todos os recursos regionais da aplicação ficam em us-east-2. CloudFront é global; a configuração de entrega de seus logs utiliza us-east-1, com armazenamento no bucket da região selecionada. Não há implantação multirregional ou Lambda@Edge.

O estudo de IaaS, PaaS e serverless permite comparar responsabilidades: numa VM, a equipe administraria sistema operacional e aplicação; nos serviços gerenciados adotados, concentra-se em código, dados e configurações. A implementação atual demonstra serviços gerenciados/serverless. Ela não comprova provisionamento prático de IaaS com máquinas virtuais. Como a orientação menciona IaaS e PaaS, o grupo deve validar com a orientadora se essa análise comparativa atende à expectativa ou se é necessário um exercício complementar.

A política do projeto é usar somente o plano gratuito e os créditos disponíveis, sem ativar cobrança ou plano pago. O controle exige consulta ao consumo e aos créditos em AWS Settings > Billing. A escolha de serviços sob demanda não garante custo zero: requisições, armazenamento e logs podem consumir créditos.

<!-- pagebreak -->
## 8 Análise da unidade de Qualidade de Software

A qualidade foi tratada como parte das regras e do processo de alteração. A validação rejeita quantidades inválidas; a transação preserva a consistência; a idempotência evita duplicações; os testes verificam comportamentos repetíveis; e a revisão do plano de infraestrutura procura evitar substituições inesperadas. Os logs apoiam a investigação de falhas após a publicação.

| Verificação da revisão | Resultado registrado | Interpretação |
|---|---|---|
| Casos Python de API e domínio | 47 aprovados | Serviços simulados com Moto |
| Casos JavaScript de estoque | 12 aprovados | Funções de cálculo e filtros |
| Casos JavaScript de autenticação | 5 aprovados | Fluxos simulados do frontend |
| Total automatizado local | 64 aprovados | Não representa cobertura percentual |
| cfn-lint e cfn-guard | Aprovado e 5 regras aprovadas | Validação estática do template |
| Verificações online de leitura e OPTIONS | 15 aprovadas | Sem gravar dados de teste |
| Comparação dos dados e acessos | Preservados | Hashes iguais antes e depois |

Os testes incluem retirada acima do saldo, saldo por embalagem, normalização de classificação, filtros inclusivos de datas, pesos opcionais, pausa de acessos, restrições por perfil, paginação e atomicidade da auditoria. A lista detalhada está nos arquivos de teste e em `docs/VALIDACAO.md`.

A integração e entrega contínuas ainda não estão automatizadas em um pipeline. Há testes e scripts repetíveis, mas sua execução e a decisão de publicar permanecem manuais. Assim, o requisito de CI/CD deve ser apresentado como parcialmente desenvolvido. Uma evolução é executar testes por pull request e, posteriormente, desenhar uma entrega com autorização e identidade temporária.

Confiabilidade foi avaliada por casos funcionais e preservação de dados. Manutenibilidade é apoiada pela separação entre interface, domínio, API e infraestrutura e pela documentação. Desempenho possui logs e limites configurados, mas não foi medido sob carga. Não há evidência para afirmar cobertura de 100%, disponibilidade mensal, ausência de defeitos ou redução percentual de perdas.

<!-- pagebreak -->
## 9 Segurança auditoria e governança

O Cognito gerencia as senhas e o processo de autenticação. A interface utiliza authorization code com PKCE, sem segredo de cliente no navegador. A API exige access token e verifica o usuário ativo e seu perfil no banco. O template define política de senha e suporte opcional a MFA; isso não significa que todos os usuários tenham MFA ativado.

O tráfego utiliza HTTPS. O S3 bloqueia acesso público direto, aplica criptografia e versionamento. A política da função restringe o acesso aos recursos utilizados. As respostas da distribuição incluem controles de segurança do navegador. As configurações públicas de URL e client ID não são credenciais secretas.

A auditoria está em Integrações, restrita ao administrador. Ela registra novos movimentos, exclusões lógicas, convites, mudanças de acesso e sessões observadas pelo endpoint /me. As operações de negócio e seus eventos usam transações quando pertencem ao DynamoDB. O convite envolve também Cognito; em caso de falha ao persistir o novo acesso, a API procura desabilitar a identidade recém-criada.

A auditoria não registra senhas, tokens ou todas as tentativas de login na página externa do provedor. Não há API para editar ou excluir eventos de auditoria, mas administradores da infraestrutura ainda têm poderes sobre o armazenamento. Portanto, ela não é uma trilha imutável WORM. A busca e os contadores consideram os eventos carregados, com paginação de 100 por consulta. Não há expiração configurada para esses eventos nesta versão.

CloudWatch mantém logs de Lambda e API por 14 dias. A entrega de logs do CloudFront evita campos de query, cookies e cabeçalhos de autenticação. O Event history do CloudTrail oferece histórico regional de gerenciamento dos últimos 90 dias; não foi criada uma trilha permanente adicional. As retenções devem ser revistas se a empresa precisar de comprovação por períodos maiores.

A governança mínima proposta utiliza três práticas: registrar quem pode operar; revisar e documentar cada publicação; e manter evidências de testes e recuperação. Os anexos com dados da empresa e pessoas devem permanecer sob acesso controlado. O projeto implementa controles técnicos, mas esta documentação não certifica conformidade legal ou de uma norma de segurança.

<!-- pagebreak -->
## 10 Publicação manutenção e preservação

A revisão online-2-auditoria foi publicada em 8 de novembro de 2026, mantendo o endereço https://d1rgdc3ev01d0e.cloudfront.net/. O plano executado alterou somente a função da API, sem substituição de recursos. A stack concluiu em UPDATE_COMPLETE e a invalidação do cache foi concluída.

Os sete arquivos públicos foram comparados por SHA-256 com a versão local revisada. O código efetivo da Lambda também foi conferido. A comparação separada dos hashes dos movimentos, saldos e acessos existentes mostrou preservação após a publicação. Não houve necessidade de recriar os usuários ou reinserir lançamentos.

O ambiente utiliza recuperação contínua do DynamoDB com janela configurada de sete dias e proteção contra exclusão. O S3 possui versionamento, com retenção limitada de versões antigas. O código anterior e referências de versões dos arquivos foram guardados localmente fora do pacote público. Esses mecanismos auxiliam recuperação, mas não substituem um ensaio real de restauração.

Para alterações futuras, o procedimento é editar uma cópia controlada, testar, revisar o diff, gerar o template quando necessário, examinar o change set e publicar os arquivos. O arquivo `infra/retained-resources.json` preserva nomes físicos da implantação original e deve ser mantido ao atualizar a produção. O guia AWS anexo detalha o processo e distingue uma atualização de um laboratório novo.

As 15 verificações online foram limitadas a leitura e OPTIONS. O ensaio remoto que criaria usuários e movimentos temporários foi rejeitado pela revisão automática de aprovação por falta de autorização específica para essas criações em produção. Ele não foi executado. A confirmação completa de login e gravação autenticada de ponta a ponta permanece pendente nessa revisão.

## 11 Resultados alcançados

O resultado técnico é uma aplicação web publicada, com dados compartilhados, separação de perfis, cálculo de estoque por embalagem, filtros, autoria dos movimentos e consulta de auditoria. A atualização documentada preservou os dados e acessos já existentes.

O retorno relatado pelo usuário indica que o sistema atende à necessidade operacional e motivou melhorias de consulta e rastreabilidade. Não foram coletados indicadores comerciais para estimar economia de tempo, redução de perdas ou retorno financeiro. Esses benefícios permanecem potenciais e devem ser medidos antes de serem apresentados como resultados quantitativos.

<!-- pagebreak -->
## 12 Atendimento à orientação e próximos passos

| Tema da orientação | Evidência nesta versão | Limite ou ação seguinte |
|---|---|---|
| Aplicação web em nuvem | Site HTTPS funcional e serviços provisionados | Homologação completa da revisão pendente |
| Provisionamento e automação | Template e scripts locais | Operação de publicação manual |
| IaaS e PaaS | Análise dos modelos e serviços gerenciados | Sem VM IaaS implementada; validar expectativa |
| Domínios | Endereço HTTPS CloudFront e login Cognito | Sem domínio próprio |
| Permissões e autenticação | Três perfis, Cognito e validação na API | MFA é opcional |
| Escalabilidade e monitoramento | Serviços sob demanda, limites e logs | Sem teste de carga ou SLA próprio |
| Testes e métricas | 64 testes locais e 15 verificações online | Sem cobertura percentual ou benchmark |
| CI/CD | Scripts e sequência de validação | Pipeline automático ainda não implementado |
| Recuperação | PITR, versionamento e cópia de código | Restauração real ainda não ensaiada |

As prioridades de evolução são homologar os três perfis em ambiente adequado, exercitar a recuperação em tabela separada, automatizar a validação por pull request e medir tempos de resposta. A criação de recursos ou testes com consumo adicional depende da política de créditos do projeto.

## 13 Relação com a extensão e o ODS

O projeto aproxima a formação em tecnologia de uma necessidade de organização operacional da beneficiária. Como enquadramento proposto, o **ODS 9, Indústria, inovação e infraestrutura**, é pertinente ao uso de tecnologia e infraestrutura digital para apoiar processos. A relação é uma interpretação da equipe a validar na entrega, apoiada na descrição oficial da ONU.

A rastreabilidade e a consulta de saldo podem contribuir para decisões mais informadas. Não há medição que permita afirmar redução de desperdício, aumento de produtividade ou atendimento integral às metas do ODS. O relatório individual de extensão deve registrar a experiência efetivamente realizada por cada estudante, com dificuldades e resultados observados.

<!-- pagebreak -->
## 14 Organização da entrega acadêmica

O documento de orientação do módulo estabelece entregas específicas. Este relatório serve como base para as análises de Computação em Nuvem e Qualidade de Software; ele não substitui todos os anexos exigidos. Confira datas e regras atualizadas no AVA antes do envio.

| Item | Providência do grupo |
|---|---|
| Pôster final em PDF | Sintetizar contexto, beneficiária, ações, resultados e referências no formato exigido |
| Vídeo de 10 a 15 minutos | Mostrar ambiente em nuvem, recursos, aplicação e práticas de qualidade |
| Consentimento da beneficiária | Obter o documento real assinado pelo responsável |
| Comprovante cadastral | Anexar inscrição e situação cadastral reais da empresa |
| Análises das unidades | Revisar e entregar as análises das seções 7 e 8, conforme solicitação no AVA |
| Relatório de extensão | Cada estudante preenche sua experiência na Intranet |
| Formação para a Vida | Preparar a síntese dos quatro tópicos de Desenvolvendo Ideias |

O pôster deve seguir a identificação institucional e apresentar título, autores, orientadora, resumo, palavras-chave, beneficiários, ações, desafios, resultados e referências. Dados de contato exigidos no modelo devem ser preenchidos pelo grupo com informações autorizadas.

Na orientação recebida, a primeira entrega ocorre de 9 a 13 de novembro de 2026: síntese de Ideias e oportunidades, Equipe, Fatores-chave de sucesso e Definindo uma ideia empreendedora, em PDF de até 5 MB. A entrega final está prevista de 23 a 30 de novembro. A progressão válida no AVA deve superar 75% em cada unidade até 2 de dezembro; o documento também indica essa data para correções finais do relatório de extensão. Prevalecem as comunicações atuais do AVA e da orientadora.

Um roteiro possível para o vídeo é: contexto e objetivo nos dois primeiros minutos; arquitetura até o quinto; demonstração de entrada, saída, filtro e perfis até o nono; testes, publicação e monitoramento até o décimo segundo; resultados e limites nos minutos finais. Use dados fictícios ou autorizados e não mostre senhas, tokens ou informações privadas do projeto AWS.

## Conclusão

O projeto disponibilizou um controle de batatas em nuvem com acesso compartilhado, regras de estoque e rastreabilidade. A revisão publicada preservou dados e acessos e apresentou evidências de validação local e online. A experiência relaciona infraestrutura gerenciada, implantação controlada e qualidade de software. Os próximos passos concentram-se em homologação completa, automação de testes na integração e medição de desempenho e recuperação.

<!-- pagebreak -->
## Referências

AMAZON WEB SERVICES. Amazon CloudFront Developer Guide: Restrict access to an Amazon S3 origin. Disponível em: https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/private-content-restricting-access-to-s3.html. Acesso em: 8 nov. 2026.

AMAZON WEB SERVICES. AWS CloudFormation User Guide: Update stacks using change sets. Disponível em: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/using-cfn-updating-stacks-changesets.html. Acesso em: 8 nov. 2026.

AMAZON WEB SERVICES. AWS CloudTrail User Guide: Working with event history. Disponível em: https://docs.aws.amazon.com/awscloudtrail/latest/userguide/view-cloudtrail-events.html. Acesso em: 8 nov. 2026.

AMAZON WEB SERVICES. Amazon DynamoDB Developer Guide: Point-in-time recovery. Disponível em: https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/PointInTimeRecovery_Howitworks.html. Acesso em: 8 nov. 2026.

AMAZON WEB SERVICES. AWS CLI User Guide: Sign in with your AWS credentials. Disponível em: https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-sign-in.html. Acesso em: 8 nov. 2026.

GITHUB. Understanding GitHub Actions. Disponível em: https://docs.github.com/en/actions/get-started/understand-github-actions. Acesso em: 8 nov. 2026.

NAÇÕES UNIDAS BRASIL. Objetivo de Desenvolvimento Sustentável 9: Indústria, inovação e infraestrutura. Disponível em: https://brasil.un.org/pt-br/sdgs/9. Acesso em: 8 nov. 2026.

UNIFEOB. Orientação PI E_TEC_ADS 2026: Computação em Nuvem. São João da Boa Vista: Escola de Negócios e Tecnologia EAD, 2026. Documento institucional fornecido ao grupo. Seções 6 a 10.

Evidências primárias do desenvolvimento: código da revisão online-2-auditoria; testes em tests/; infraestrutura em infra/; registro da publicação de 8 nov. 2026, resumido em docs/VALIDACAO.md. Os arquivos privados de verificação e backup permanecem fora do repositório.
