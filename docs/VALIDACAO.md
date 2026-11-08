# Evidências da versão online 2 com auditoria

Data de referência: 08/11/2026. Este documento resume a verificação registrada na publicação; não implica acompanhamento contínuo do ambiente.

| Camada | Evidência | Limite |
|---|---|---|
| API e domínio | 47 testes Python aprovados, incluindo parametrizações | Serviços simulados com Moto |
| Estoque no frontend | 12 testes JavaScript aprovados | Testes de funções, não de navegador completo |
| Autenticação no frontend | 5 testes JavaScript aprovados | Fluxos simulados, sem login real no provedor |
| Infraestrutura | cfn-lint aprovado; 5 regras cfn-guard aprovadas | Regras verificam apenas as propriedades cobertas |
| Publicação | CloudFormation UPDATE_COMPLETE; alteração somente de Function, sem substituição | Evidência pontual da revisão |
| Ambiente online | 15 verificações de leitura e OPTIONS aprovadas | Sem criar movimentos ou usuários |
| Preservação | Hashes anteriores e posteriores iguais para os registros e acessos existentes | Não é um ensaio de restauração |

Os testes locais cobrem idempotência, consistência de saldo por embalagem, saída acima do saldo, exclusão lógica, autorização por perfil, bloqueio de usuário pausado, paginação, peso opcional, identificação autenticada do autor e auditoria transacional. Consulte os casos em `tests/` para conhecer exatamente as entradas verificadas.

As 15 verificações online compreenderam sete arquivos públicos comparados por SHA-256, três rotas de dados recusando acesso anônimo, CORS, acesso direto ao bucket bloqueado, correspondência do código e versão da API, execução de OPTIONS no runtime e estado final da stack. A preservação dos dados foi verificada separadamente.

Template publicado: 23 recursos, 39.935 bytes. SHA-256:

```text
df46eba3c98c0907cd575504f3aecd828a54bd71ab05b1f55eccc59c176da1da
```

O ensaio remoto completo não foi executado. A revisão automática de aprovação rejeitou a criação de identidades e lançamentos temporários em produção sem autorização específica; a verificação foi limitada a leitura e OPTIONS. A confirmação de login e gravação autenticada de ponta a ponta permanece pendente nesta revisão.

Não foram medidos cobertura percentual de código, latência sob carga, disponibilidade mensal, redução de perdas comerciais ou tempo de recuperação por restauração real. Não atribua valores a essas métricas na apresentação sem coletá-las.

Próximas verificações sugeridas: homologação autorizada com os três perfis, ensaio de restauração em tabela separada e medição de tempo de resposta em ambiente de teste. Cada atividade deve ter escopo, ambiente, resultado esperado, responsável e evidência. A ativação de serviços com consumo adicional depende dos créditos e da autorização do projeto.

A cópia preparada para o GitHub foi novamente validada localmente em 08/11/2026: 47 testes Python, 12 de estoque e 5 de autenticação aprovados; cfn-lint e as cinco regras cfn-guard aprovados. Nenhum arquivo da aplicação foi alterado nessa preparação. Os 17 blocos Bash do README e do guia passaram pela verificação sintática bash -n, sem execução das operações de nuvem.
