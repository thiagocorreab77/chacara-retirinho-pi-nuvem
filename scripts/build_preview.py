"""Gera uma prévia estática independente de login, rede e dados reais."""
from pathlib import Path
root=Path(__file__).resolve().parents[1]
html=(root/'web/index.html').read_text()
html=html.replace('href="style.css"','href="web/style.css"')
html=html.replace('src="assets/','src="web/assets/')
html=html.replace('<script src="config.js"></script>','')
html=html.replace('src="access.js"','src="preview/access.js"')
html=html.replace('src="inventory.js"','src="web/inventory.js"')
html=html.replace('src="script.js"','src="web/script.js"')
html=html.replace('</head>','<link rel="stylesheet" href="preview/style.css">\n</head>')
html=html.replace('<body>','''<body>
<div class="preview-banner" role="region" aria-label="Demonstração local"><div><strong>PRÉVIA LOCAL — DADOS FICTÍCIOS</strong>Teste os ajustes sem alterar o site online. Os testes ficam somente neste navegador. Confira Auditoria e acessos dentro de Integrações, no perfil Administrador.</div><div class="preview-profile"><label for="previewProfile">Simular perfil</label><select id="previewProfile"><option value="admin">Administrador</option><option value="operator">Operador</option><option value="viewer">Visualizador</option></select></div><button type="button" id="previewReset">Restaurar exemplos</button></div>''')
html=html.replace('Estoque compartilhado.', 'Dados de demonstração.')
html=html.replace('Ambiente online · us-east-2','Prévia local · sem conexão com AWS')
html=html.replace('Acessos protegidos pelo Amazon Cognito','Acesso fictício para conferência')
html=html.replace('O convite será enviado ao e-mail informado.', 'Cadastros fictícios locais. Nenhum e-mail será enviado.')
html=html.replace('Acompanhe os serviços que mantêm o sistema online.', 'Os serviços abaixo são simulados nesta prévia. Não há consulta ao ambiente online.')
(root/'ABRIR_PREVIA.html').write_text(html)
print('Prévia gerada: ABRIR_PREVIA.html')
