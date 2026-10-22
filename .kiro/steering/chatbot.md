---
inclusion: always
---
# Stack obrigatória do projeto


- Python com Flask. Estrutura: app.py na raiz e a página
  em templates/index.html.
- Rota / exibe a página de chat. Rota /chat (POST) recebe
  {"message": "..."} e devolve {"reply": "..."}. Mensagem
  vazia retorna erro 400.
- Respostas geradas pelo Amazon Bedrock via boto3, usando
  bedrock-runtime e invoke_model, região us-east-1.
- Model ID: us.anthropic.claude-haiku-4-5-20251001-v1:0
  (perfil de inferência, usar exatamente este).
- Credenciais AWS somente por variáveis de ambiente. Nunca
  escrever chaves no código.
- A personalidade, o tom e os limites do bot ficam em uma
  constante SYSTEM_PROMPT no app.py.
- Respostas JSON com acentos legíveis
  (app.json.ensure_ascii = False).
- Dependências em requirements.txt (flask, boto3).
- Rodar com: python app.py, em localhost:5000.


# Proibido neste projeto


- Não usar FastAPI, Django, banco de dados, LangChain, RAG,
  autenticação ou login.
- Não criar testes automatizados.
- Não usar OpenAI nem outras APIs de IA além do Bedrock.


# Estilo


- Projeto mínimo e didático: poucos arquivos e código
  simples, comentado em português.
