# Documento de Requisitos

## Introdução

O "Botones" é um chatbot web que ajuda guitarristas a montar presets no Amplitube 5. O bot conversa com o guitarrista com a personalidade de um guitarrista meio doidão de death metal, coletando informações sobre o que a pessoa quer tocar (gênero, referências de som, tipo de guitarra e bandas a replicar) e sugerindo configurações de preset.

A aplicação é um projeto Python/Flask mínimo e didático: um arquivo `app.py` na raiz e uma página em `templates/index.html`. A página de chat é servida na rota `/`, e as mensagens são processadas na rota `/chat` (POST). As respostas são geradas pelo Amazon Bedrock (modelo Claude Haiku) via `boto3`. A personalidade e os limites do bot ficam numa constante `SYSTEM_PROMPT` dentro do `app.py`.

Este documento define os requisitos funcionais e de qualidade do sistema, seguindo os padrões EARS e as regras de qualidade INCOSE.

## Glossary

- **Botones**: O chatbot assistente de presets de Amplitube 5, com personalidade de guitarrista de death metal.
- **Servidor_Flask**: A aplicação web Python/Flask definida em `app.py` que expõe as rotas HTTP e executa em `localhost:5000`.
- **Pagina_Chat**: A interface web de conversa definida em `templates/index.html`, servida pela rota `/`.
- **Rota_Chat**: O endpoint HTTP `/chat`, que aceita requisições POST com o corpo JSON `{"message": "..."}` e responde com JSON `{"reply": "..."}`.
- **Cliente_Bedrock**: O cliente `boto3` do serviço `bedrock-runtime` configurado na região `us-east-1`, usado para invocar o modelo via `invoke_model`.
- **Model_ID**: O identificador do perfil de inferência do modelo, exatamente `us.anthropic.claude-haiku-4-5-20251001-v1:0`.
- **SYSTEM_PROMPT**: A constante em `app.py` que define a personalidade, o tom e os limites de resposta do Botones.
- **Credenciais_AWS**: As credenciais de acesso à AWS fornecidas exclusivamente por variáveis de ambiente.
- **Preset**: Uma configuração sugerida de equipamentos (amplificador, pedais, cabinet, efeitos) do Amplitube 5.
- **Guitarrista**: O usuário final que interage com o Botones para montar um preset.

## Requirements

### Requirement 1: Servir a página de chat

**User Story:** Como guitarrista, quero acessar uma página de chat no navegador, para conversar com o Botones sobre presets.

#### Acceptance Criteria

1. WHEN uma requisição GET é recebida na rota `/`, THE Servidor_Flask SHALL retornar a Pagina_Chat renderizada a partir de `templates/index.html` com status HTTP 200 em até 2 segundos.
2. IF o arquivo `templates/index.html` não puder ser encontrado ou renderizado ao processar uma requisição GET na rota `/`, THEN THE Servidor_Flask SHALL retornar uma resposta de erro com status HTTP 500 contendo uma indicação de que a página não pôde ser carregada.
3. THE Pagina_Chat SHALL exibir um único campo de entrada de texto para a mensagem do Guitarrista, aceitando no mínimo 1 e no máximo 2000 caracteres, e um controle acionável para enviar a mensagem.
4. IF o Guitarrista aciona o controle de envio com o campo de entrada vazio ou contendo apenas espaços em branco, THEN THE Pagina_Chat SHALL impedir o envio da mensagem e exibir uma indicação de que o campo de mensagem é obrigatório.
5. THE Pagina_Chat SHALL exibir o histórico de mensagens trocadas entre o Guitarrista e o Botones durante a sessão aberta no navegador, apresentando cada mensagem com identificação visível de seu autor (Guitarrista ou Botones) e em ordem cronológica de envio, da mais antiga para a mais recente.
6. WHEN a Pagina_Chat é carregada e nenhuma mensagem foi trocada na sessão atual, THE Pagina_Chat SHALL exibir a área de histórico vazia, sem nenhuma mensagem.

### Requirement 2: Receber e validar mensagens do usuário

**User Story:** Como guitarrista, quero enviar minhas mensagens para o Botones, para receber ajuda sobre o preset.

#### Acceptance Criteria

1. WHEN uma requisição POST com corpo JSON válido contendo o campo `message` do tipo texto, não vazio (com ao menos um caractere diferente de espaço em branco) e com no máximo 4000 caracteres é recebida na Rota_Chat, THE Servidor_Flask SHALL processar a mensagem e retornar um JSON contendo o campo `reply` com status HTTP 200.
2. IF uma requisição POST é recebida na Rota_Chat com o campo `message` ausente, com valor que não seja texto, com string vazia, ou contendo somente espaços em branco, THEN THE Servidor_Flask SHALL rejeitar a requisição com status HTTP 400 e incluir no corpo JSON uma mensagem de erro indicando que o campo `message` é obrigatório e deve conter texto não vazio.
3. IF uma requisição POST é recebida na Rota_Chat com `message` cujo texto excede 4000 caracteres, THEN THE Servidor_Flask SHALL rejeitar a requisição com status HTTP 400 e incluir no corpo JSON uma mensagem de erro indicando que a mensagem excede o limite de caracteres permitido.
4. IF uma requisição POST é recebida na Rota_Chat com corpo ausente ou que não seja JSON válido, THEN THE Servidor_Flask SHALL rejeitar a requisição com status HTTP 400 e incluir no corpo JSON uma mensagem de erro indicando que o corpo deve ser um JSON válido.
5. THE Servidor_Flask SHALL serializar as respostas JSON com acentos legíveis configurando `app.json.ensure_ascii = False`.

### Requirement 3: Gerar respostas via Amazon Bedrock

**User Story:** Como guitarrista, quero que as respostas do Botones sejam geradas por um modelo de IA, para obter sugestões úteis de preset.

#### Acceptance Criteria

1. WHEN o Servidor_Flask processa uma mensagem válida do Guitarrista, THE Cliente_Bedrock SHALL invocar o modelo usando `invoke_model` no serviço `bedrock-runtime` na região `us-east-1`, com um limite de tempo de resposta de 30 segundos por invocação.
2. THE Cliente_Bedrock SHALL utilizar o Model_ID exatamente igual a `us.anthropic.claude-haiku-4-5-20251001-v1:0`.
3. THE Servidor_Flask SHALL incluir a constante SYSTEM_PROMPT na invocação do modelo para definir a personalidade e os limites do Botones.
4. WHEN o Cliente_Bedrock retorna uma resposta contendo texto gerado não vazio, THE Servidor_Flask SHALL extrair esse texto e retorná-lo no campo `reply` da resposta JSON com status HTTP 200.
5. IF o Cliente_Bedrock retorna uma resposta sem texto gerado ou com texto vazio, THEN THE Servidor_Flask SHALL retornar status HTTP 500 com o campo `error` no corpo da resposta indicando falha na geração da resposta, sem incluir o campo `reply`.
6. IF a invocação do Cliente_Bedrock falha por erro do serviço ou por exceder o limite de tempo de 30 segundos, THEN THE Servidor_Flask SHALL retornar status HTTP 500 com o campo `error` no corpo da resposta indicando falha na comunicação com o modelo, sem incluir o campo `reply`.

### Requirement 4: Personalidade do Botones

**User Story:** Como guitarrista, quero conversar com um bot com personalidade de guitarrista de death metal, para ter uma experiência divertida e temática.

#### Acceptance Criteria

1. THE SYSTEM_PROMPT SHALL definir a personalidade do Botones como a de um guitarrista de death metal, caracterizada por tom informal, uso de gírias de músico e entusiasmo exagerado por guitarra e distorção, mantendo linguagem respeitosa e sem conteúdo ofensivo.
2. THE SYSTEM_PROMPT SHALL instruir o Botones a redigir todas as respostas em português do Brasil.
3. WHEN o usuário enviar uma mensagem em idioma diferente do português, THE SYSTEM_PROMPT SHALL instruir o Botones a responder em português do Brasil independentemente do idioma da mensagem recebida.
4. THE SYSTEM_PROMPT SHALL restringir o escopo das respostas do Botones exclusivamente aos seguintes temas: montagem de presets no Amplitube 5, tom de guitarra, equipamentos de guitarra e técnica de guitarra.
5. IF o usuário enviar uma mensagem fora dos temas definidos no escopo, THEN THE SYSTEM_PROMPT SHALL instruir o Botones a recusar a resposta, informar ao usuário que o assunto está fora do escopo e sugerir que a pergunta seja reformulada dentro dos temas permitidos.

### Requirement 5: Fluxo de coleta de informações do preset

**User Story:** Como guitarrista, quero que o Botones me faça perguntas sobre o som que quero, para que ele sugira um preset adequado.

#### Acceptance Criteria

1. WHEN o Guitarrista inicia uma conversa, THE Botones SHALL perguntar o que o Guitarrista quer tocar.
2. WHILE ainda houver informações pendentes entre "o que quer tocar", "referências de som", "tipo de guitarra" e "banda a replicar", THE Botones SHALL solicitar ao Guitarrista a próxima informação pendente, uma por vez.
3. THE Botones SHALL perguntar quais referências de som o Guitarrista deseja.
4. THE Botones SHALL perguntar qual o tipo de guitarra do Guitarrista.
5. THE Botones SHALL perguntar qual banda o Guitarrista deseja replicar o som.
6. WHEN o Guitarrista tiver fornecido as quatro informações (o que quer tocar, referências de som, tipo de guitarra e banda a replicar), THE Botones SHALL sugerir uma configuração de Preset para o Amplitube 5 baseada nessas informações.
7. IF o Guitarrista solicitar uma sugestão de Preset antes de fornecer todas as quatro informações, THEN THE Botones SHALL sugerir um Preset com base nas informações disponíveis e sinalizar quais informações estão faltando.

### Requirement 6: Segurança das credenciais AWS

**User Story:** Como desenvolvedor, quero que as credenciais AWS fiquem fora do código, para evitar vazamento de chaves.

#### Acceptance Criteria

1. WHEN o Servidor_Flask é iniciado, THE Servidor_Flask SHALL obter as Credenciais_AWS exclusivamente a partir de variáveis de ambiente.
2. THE Servidor_Flask SHALL referenciar as Credenciais_AWS sem gravar valores de chaves no código-fonte.
3. IF uma ou mais variáveis de ambiente das Credenciais_AWS estiverem ausentes ou vazias na inicialização, THEN THE Servidor_Flask SHALL interromper a inicialização e registrar uma mensagem de erro indicando quais Credenciais_AWS estão ausentes, sem expor os valores das chaves.
4. WHEN o Servidor_Flask registra logs ou retorna respostas de erro, THE Servidor_Flask SHALL omitir integralmente os valores das Credenciais_AWS, substituindo-os por um indicador de valor ocultado.

### Requirement 7: Execução e dependências do projeto

**User Story:** Como desenvolvedor, quero executar o projeto de forma simples, para rodar o chatbot localmente.

#### Acceptance Criteria

1. WHEN o Servidor_Flask é iniciado com o comando `python app.py`, THE Servidor_Flask SHALL passar a aceitar requisições na porta 5000 em `localhost`.
2. IF a porta 5000 já estiver em uso quando o Servidor_Flask é iniciado, THEN THE Servidor_Flask SHALL encerrar a inicialização e registrar uma mensagem de erro indicando que a porta está indisponível.
3. THE Servidor_Flask SHALL declarar as dependências `flask` e `boto3` em um arquivo `requirements.txt`.
4. THE Servidor_Flask SHALL organizar o código em `app.py` na raiz do projeto e a página em `templates/index.html`.
