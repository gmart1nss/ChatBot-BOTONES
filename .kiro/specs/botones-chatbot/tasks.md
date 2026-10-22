# Plano de Implementação: Botones (chatbot de presets do Amplitube 5)

## Visão Geral

A implementação segue a stack obrigatória do steering: projeto Python/Flask mínimo e didático, com `app.py` na raiz e `templates/index.html` como página de chat. As respostas são geradas pelo Amazon Bedrock (Claude Haiku) via `boto3`, e a personalidade/limites ficam na constante `SYSTEM_PROMPT`.

Cada tarefa constrói sobre a anterior e termina com a integração das partes (sem código órfão). O servidor é stateless: o histórico vive no navegador e é reenviado no corpo da requisição.

> Observação: o steering do projeto **proíbe testes automatizados** (unitários, de integração ou property-based). Portanto, não há tarefas de teste automatizado neste plano. A validação é **manual**, conforme a Estratégia de Validação do design.

## Tarefas

- [x] 1. Preparar a estrutura do projeto e as dependências
  - Criar o arquivo `requirements.txt` na raiz declarando `flask` e `boto3`.
  - Criar a pasta `templates/` para abrigar a página de chat.
  - Criar o esqueleto de `app.py` na raiz com `app = Flask(__name__)` e `app.json.ensure_ascii = False`, além dos comentários iniciais em português descrevendo o propósito do arquivo.
  - _Requisitos: 7.3, 7.4, 2.5_

- [x] 2. Definir configuração, personalidade e segurança de credenciais em `app.py`
  - [x] 2.1 Declarar constantes de configuração e o `SYSTEM_PROMPT`
    - Declarar `REGIAO = "us-east-1"`, `MODEL_ID = "us.anthropic.claude-haiku-4-5-20251001-v1:0"`, `TIMEOUT_SEGUNDOS = 30` e `LIMITE_CARACTERES = 4000`.
    - Escrever a constante `SYSTEM_PROMPT` com personalidade (guitarrista de death metal, tom informal, gírias, respeitoso), idioma sempre em português do Brasil, restrição de escopo (presets Amplitube 5, tom, equipamentos e técnica de guitarra) com recusa educada fora do escopo, e o fluxo de coleta de informações (o que quer tocar, referências de som, tipo de guitarra, banda a replicar) uma pergunta por vez, com sugestão de preset ao reunir tudo e sugestão parcial quando solicitado antes.
    - _Requisitos: 3.2, 3.3, 4.1, 4.2, 4.3, 4.4, 4.5, 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7_

  - [x] 2.2 Verificar as credenciais AWS na inicialização
    - Implementar a leitura das variáveis de ambiente esperadas (ex.: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, região `us-east-1`) sem gravar chaves no código.
    - Interromper a inicialização registrando quais credenciais faltam, sem expor valores (usar indicador de valor ocultado em logs/erros).
    - _Requisitos: 6.1, 6.2, 6.3, 6.4_

  - [x] 2.3 Criar o cliente Bedrock com timeout
    - Instanciar `boto3.client("bedrock-runtime", region_name="us-east-1", config=Config(read_timeout=30, connect_timeout=30))`.
    - As credenciais devem ser resolvidas pelo `boto3` a partir das variáveis de ambiente, sem chaves no código.
    - _Requisitos: 3.1, 6.1, 6.2_

- [x] 3. Implementar a lógica de validação e invocação do modelo em `app.py`
  - [x] 3.1 Implementar a validação de mensagens (`validar_mensagem`)
    - Tratar corpo ausente/não-JSON → erro de "corpo deve ser JSON válido".
    - Tratar `message` ausente/não-texto/vazio/só espaços → erro de campo obrigatório não vazio.
    - Tratar `message` acima de 4000 caracteres → erro de limite excedido.
    - Retornar o texto saneado ou a mensagem de erro apropriada.
    - _Requisitos: 2.2, 2.3, 2.4_

  - [x] 3.2 Implementar a montagem do payload (`montar_payload`)
    - Montar o corpo no formato Anthropic/Bedrock (`anthropic_version`, `max_tokens`, `system` com `SYSTEM_PROMPT`, `messages`).
    - Reconstruir os turnos a partir do `history` (autor `guitarrista` → `user`, `botones` → `assistant`) seguidos da mensagem atual como `user`.
    - _Requisitos: 3.3, 5.2_

  - [x] 3.3 Implementar a invocação e extração de texto (`invocar_modelo`, `extrair_texto`)
    - Chamar `invoke_model` com o `MODEL_ID` exato e respeitar o timeout de 30s.
    - Ler o corpo da resposta, decodificar JSON e extrair o texto do primeiro bloco de conteúdo (`content[0].text`).
    - Retornar texto vazio quando não houver texto gerado, para acionar o tratamento de erro.
    - _Requisitos: 3.1, 3.2, 3.4, 3.5_

- [x] 4. Implementar as rotas HTTP em `app.py`
  - [x] 4.1 Implementar a rota `GET /` para servir a página
    - Renderizar `templates/index.html` com `render_template` e retornar status 200.
    - Em falha de renderização/template ausente, retornar 500 indicando que a página não pôde ser carregada.
    - _Requisitos: 1.1, 1.2_

  - [x] 4.2 Implementar a rota `POST /chat`
    - Chamar `validar_mensagem`; em entrada inválida retornar 400 com `error`.
    - Em entrada válida, montar o payload, invocar o modelo e extrair o texto.
    - Em sucesso com texto, retornar `200 {"reply": "..."}`.
    - Em texto vazio, falha do serviço ou timeout, retornar `500 {"error": "..."}` sem o campo `reply`, com `try/except` em torno da invocação.
    - _Requisitos: 2.1, 3.4, 3.5, 3.6_

- [~] 5. Checkpoint - Validação manual do backend
  - Rodar `python app.py` e verificar manualmente: `GET /` retorna 200; `POST /chat` com `{"message":"oi"}` retorna `reply`; corpo não-JSON, `message` vazio/ausente e `message` acima de 4000 caracteres retornam 400; respostas com acento aparecem legíveis; indisponibilidade do Bedrock retorna 500 sem `reply`; inicialização sem credenciais interrompe o servidor sem expor valores. Pergunte ao usuário caso surjam dúvidas.
  - _Requisitos: 1.1, 2.1, 2.2, 2.3, 2.4, 2.5, 3.5, 3.6, 6.3, 6.4, 7.1_

- [x] 6. Implementar a página de chat (`templates/index.html`)
  - [x] 6.1 Estruturar o HTML e o CSS embutidos
    - Criar a página única com HTML e CSS embutidos (sem assets externos), com campo de entrada (`maxlength="2000"`), botão de envio e área de histórico que inicia vazia.
    - Exibir cada mensagem com rótulo de autor ("Você" para o Guitarrista e "Botones") em ordem cronológica (mais antiga no topo).
    - _Requisitos: 1.3, 1.5, 1.6_

  - [x] 6.2 Implementar o JavaScript de interação e comunicação
    - Manter o histórico em um array em memória do navegador (descartado ao recarregar).
    - Bloquear o envio quando o campo estiver vazio ou só com espaços e exibir aviso de campo obrigatório; permitir envio por botão e por tecla Enter.
    - Chamar `fetch("/chat", {method:"POST", ...})` enviando `message` e `history`; ao receber `reply`, acrescentar ao histórico; ao receber `error` (400/500), exibir mensagem amigável sem quebrar a página.
    - _Requisitos: 1.4, 1.5, 2.1_

- [x] 7. Finalizar a execução do projeto
  - Garantir que `python app.py` sobe o servidor em `localhost:5000` e que, se a porta 5000 estiver em uso, a inicialização é encerrada com erro de porta indisponível.
  - Confirmar que `requirements.txt` declara `flask` e `boto3` e que o fluxo `pip install -r requirements.txt` + `python app.py` funciona.
  - _Requisitos: 7.1, 7.2, 7.3_

- [~] 8. Checkpoint final - Validação manual completa (ponta a ponta)
  - Verificar manualmente o fluxo completo pelo navegador em `http://localhost:5000`: personalidade/escopo (tom death metal em português; resposta em português mesmo para mensagem em inglês; recusa educada fora do escopo), fluxo de coleta (perguntas uma por vez: o que tocar, referências, tipo de guitarra, banda; sugestão ao reunir as quatro; sugestão parcial quando pedido antes) e a página (histórico cronológico, bloqueio de envio vazio). Pergunte ao usuário caso surjam dúvidas.
  - _Requisitos: 4.1, 4.3, 4.5, 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 1.4, 1.5_

## Notas

- Este plano **não inclui testes automatizados** porque o steering do projeto os proíbe; toda a validação é manual (checkpoints das tarefas 5 e 8), conforme a Estratégia de Validação do design.
- Cada tarefa referencia requisitos específicos para rastreabilidade.
- As tarefas constroem incrementalmente: backend primeiro (configuração → validação/modelo → rotas), depois a página, encerrando com a integração e a execução.
- Os checkpoints asseguram validação manual incremental antes de prosseguir.

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1"] },
    { "id": 1, "tasks": ["2.1", "2.2", "2.3"] },
    { "id": 2, "tasks": ["3.1", "3.2", "3.3"] },
    { "id": 3, "tasks": ["4.1", "4.2"] },
    { "id": 4, "tasks": ["6.1"] },
    { "id": 5, "tasks": ["6.2", "7"] }
  ]
}
```
