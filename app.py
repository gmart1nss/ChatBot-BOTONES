# app.py
#
# Botones - chatbot web que ajuda guitarristas a montar presets no Amplitube 5.
#
# Este arquivo e o servidor Python/Flask do projeto. Ele sera responsavel por:
#   - servir a pagina de chat (rota GET "/", a partir de templates/index.html);
#   - receber e validar as mensagens do guitarrista (rota POST "/chat");
#   - gerar as respostas do Botones via Amazon Bedrock (modelo Claude Haiku)
#     usando boto3, com a personalidade definida na constante SYSTEM_PROMPT.
#
# O servidor e stateless: o historico da conversa vive no navegador e e
# reenviado no corpo da requisicao. As credenciais da AWS sao lidas apenas de
# variaveis de ambiente, nunca escritas no codigo.
#
# Execucao: python app.py (sobe em localhost:5000).

from flask import Flask, render_template, request, jsonify

# Instancia principal da aplicacao Flask.
app = Flask(__name__)

# Garante que os acentos apareçam legiveis nas respostas JSON, em vez de
# serem escapados como sequencias \uXXXX (Requisito 2.5).
app.json.ensure_ascii = False

# ---------------------------------------------------------------------------
# Constantes de configuracao
# ---------------------------------------------------------------------------
# Regiao da AWS onde o Amazon Bedrock e invocado (exigida pelo steering).
REGIAO = "us-east-1"

# Identificador do perfil de inferencia do modelo Claude Haiku na Bedrock.
# Deve ser usado exatamente como abaixo (Requisito 3.2).
MODEL_ID = "us.anthropic.claude-haiku-4-5-20251001-v1:0"

# Limite de tempo (em segundos) por invocacao do modelo (Requisito 3.1).
TIMEOUT_SEGUNDOS = 30

# Numero maximo de caracteres aceitos no campo "message" da rota /chat
# (Requisito 2.3).
LIMITE_CARACTERES = 4000


# ---------------------------------------------------------------------------
# Memoria de conversa (historico no servidor)
# ---------------------------------------------------------------------------
# Lista global que guarda o historico completo da conversa no proprio servidor.
# Cada turno e um dict {"author": "guitarrista"|"botones", "text": "..."}.
# A cada pergunta nova, todos os turnos anteriores sao reenviados ao Bedrock,
# dando ao modelo a memoria da conversa inteira.
#
# OBS.: por ser uma unica lista no processo, a memoria e compartilhada entre
# todos os acessos e persiste apenas enquanto o servidor estiver rodando.
HISTORICO_CONVERSA = []


# ---------------------------------------------------------------------------
# Personalidade e limites do Botones (SYSTEM_PROMPT)
# ---------------------------------------------------------------------------
# A constante abaixo concentra, em texto, as regras de personalidade (R4) e do
# fluxo de coleta de informacoes (R5). Ela e enviada ao modelo no campo
# "system" da invocacao (Requisito 3.3), de modo que o proprio modelo conduz a
# conversa a partir destas instrucoes e do historico recebido.
SYSTEM_PROMPT = """\
Voce e o Botones, um assistente que ajuda guitarristas a montar presets no \
Amplitube 5.

PERSONALIDADE E TOM (R4.1)
- Voce curte rock e metal e manja de tom pesado, mas fala de boa, como um \
amigo que entende do assunto. Nada de forcar barra.
- Seja direto e natural. Pode usar uma giria ou outra quando encaixar, sem \
exagero e sem soar como um tiozao tentando parecer jovem. Prefira clareza a \
empolgacao artificial.
- Mantenha SEMPRE linguagem respeitosa. Nunca use palavroes ofensivos, \
xingamentos, nem conteudo que desrespeite ou ofenda alguem.

FORMATO DAS RESPOSTAS
- Escreva em texto corrido, sem markdown. NAO use asteriscos (*), NAO use \
cerquilhas (#), NAO use titulos nem negrito.
- Se precisar listar as configuracoes de um preset, use uma lista simples com \
hifen ou numeros, sem qualquer outra formatacao.
- Seja conciso: va direto ao ponto e evite enrolacao.

IDIOMA (R4.2, R4.3)
- Responda SEMPRE em portugues do Brasil, em todas as mensagens.
- Mesmo que o guitarrista escreva em ingles, espanhol ou qualquer outro idioma, \
sua resposta deve continuar sendo em portugues do Brasil.

ESCOPO (R4.4, R4.5)
- Voce so fala sobre estes temas: montagem de presets no Amplitube 5, tom de \
guitarra, equipamentos de guitarra e tecnica de guitarra.
- Se o guitarrista mandar uma mensagem fora desses temas (ex.: receita de bolo, \
politica, futebol, ajuda com codigo), recuse educadamente: explique que esse \
assunto esta fora do seu escopo e peca pra pessoa reformular a pergunta dentro \
dos temas permitidos (presets do Amplitube 5, tom, equipamentos e tecnica de \
guitarra).

FLUXO DE SUGESTAO (R5)
- Seja resolutivo: na duvida, JA SUGIRA um preset em vez de ficar \
perguntando. Evite interrogatorios.
- Quatro informacoes ajudam a afinar a sugestao: (1) o que a pessoa quer \
tocar, (2) referencias de som que curte, (3) o tipo de guitarra que tem e \
(4) a banda cujo som quer replicar. Mas elas sao OPCIONAIS, nao obrigatorias.
- Assim que tiver qualquer pista do que a pessoa quer (ex.: um genero, uma \
banda ou um tipo de tom), ja monte uma sugestao de preset pro Amplitube 5 \
(amplificador, pedais, cabinet, efeitos, equalizacao etc.) assumindo padroes \
sensatos para o que estiver faltando.
- NAO faca uma pergunta de cada vez de forma arrastada. No maximo, faca UMA \
unica pergunta curta e so quando faltar algo realmente essencial; mesmo \
assim, ja entregue uma sugestao inicial junto, sem travar a conversa.
- Se quiser refinar, convide a pessoa de boa a mandar mais detalhes (ex.: \
"se quiser, me diz tua guitarra que eu ajusto"), mas sempre depois de ja ter \
dado uma sugestao utilizavel.
"""

# ---------------------------------------------------------------------------
# Seguranca das credenciais AWS (Requisito 6)
# ---------------------------------------------------------------------------
import os
import sys

# Indicador usado no lugar de qualquer valor de credencial em logs/erros.
# Nunca registramos o valor real de uma chave: apenas este marcador oculto
# (Requisito 6.4).
VALOR_OCULTADO = "***oculto***"

# Variaveis de ambiente esperadas para as Credenciais_AWS. As chaves ficam
# EXCLUSIVAMENTE no ambiente (R6.1, R6.2); o codigo so conhece os NOMES das
# variaveis, nunca os valores.
VARIAVEIS_CREDENCIAIS = (
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
)


def verificar_credenciais():
    """Verifica, na inicializacao, se as Credenciais_AWS estao presentes.

    Le as variaveis de ambiente esperadas (R6.1) e tambem confirma que a
    regiao configurada corresponde a exigida (us-east-1). Se faltar qualquer
    credencial, interrompe a inicializacao do servidor registrando APENAS os
    NOMES das variaveis ausentes e um indicador de valor ocultado -- nunca o
    valor real de qualquer chave (R6.3, R6.4).

    Esta funcao nao retorna os valores das credenciais; o proprio boto3 os
    resolve a partir do ambiente quando o cliente Bedrock for criado (tarefa
    2.3), de modo que nenhuma chave e gravada no codigo (R6.2).
    """
    # Coleta apenas os NOMES das variaveis que estao ausentes ou vazias.
    # Em nenhum momento guardamos ou imprimimos o conteudo das variaveis.
    ausentes = []
    for nome in VARIAVEIS_CREDENCIAIS:
        valor = os.environ.get(nome, "")
        # Consideramos ausente tanto a variavel inexistente quanto a que
        # contem apenas espacos em branco (R6.3).
        if not valor.strip():
            ausentes.append(nome)

    # A regiao tambem precisa estar coerente com a exigida pelo steering.
    # Aceitamos a ausencia da variavel (pois usamos a constante REGIAO ao
    # criar o cliente), mas, se definida, deve ser us-east-1.
    regiao_ambiente = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION")
    regiao_invalida = regiao_ambiente is not None and regiao_ambiente.strip() != REGIAO

    if ausentes or regiao_invalida:
        # Monta a mensagem de erro SEM expor nenhum valor de credencial:
        # listamos somente os nomes das variaveis e o indicador ocultado.
        partes = []
        if ausentes:
            # Ex.: "AWS_ACCESS_KEY_ID=***oculto***, AWS_SECRET_ACCESS_KEY=***oculto***"
            detalhe = ", ".join(f"{nome}={VALOR_OCULTADO}" for nome in ausentes)
            partes.append(
                "Credenciais AWS ausentes ou vazias nas variaveis de ambiente: "
                f"{detalhe}."
            )
        if regiao_invalida:
            partes.append(
                "A regiao configurada em AWS_REGION/AWS_DEFAULT_REGION deve ser "
                f"'{REGIAO}'."
            )
        partes.append(
            "Defina as variaveis de ambiente necessarias antes de iniciar o servidor."
        )
        mensagem = " ".join(partes)

        # Registra o erro e interrompe a inicializacao (R6.3). Usamos stderr e
        # um codigo de saida diferente de zero para sinalizar a falha.
        print(f"[ERRO] {mensagem}", file=sys.stderr)
        raise SystemExit(1)

    # Todas as credenciais esperadas estao presentes. Nao retornamos nem
    # registramos seus valores (R6.4).
    print("[OK] Credenciais AWS detectadas nas variaveis de ambiente.")

# ---------------------------------------------------------------------------
# Cliente do Amazon Bedrock (Requisito 3.1)
# ---------------------------------------------------------------------------
# O cliente abaixo e usado para invocar o modelo Claude Haiku via
# bedrock-runtime. Importamos Config de botocore.config para configurar os
# limites de tempo da conexao e da leitura da resposta (R3.1): ambos usam a
# constante TIMEOUT_SEGUNDOS (30s), de modo que nenhuma invocacao do modelo
# ultrapasse esse limite.
import boto3
from botocore.config import Config

# Configuracao de timeouts aplicada ao cliente. read_timeout limita o tempo de
# espera pela resposta do modelo e connect_timeout limita o tempo para abrir a
# conexao; ambos sao definidos em TIMEOUT_SEGUNDOS (Requisito 3.1).
config_bedrock = Config(
    read_timeout=TIMEOUT_SEGUNDOS,
    connect_timeout=TIMEOUT_SEGUNDOS,
)

# Cria o cliente do bedrock-runtime na regiao exigida (REGIAO = us-east-1).
# IMPORTANTE: nenhuma credencial e passada aqui. O proprio boto3 resolve as
# Credenciais_AWS a partir das variaveis de ambiente (R6.1, R6.2), de modo que
# nenhuma chave e gravada no codigo.
cliente_bedrock = boto3.client(
    "bedrock-runtime",
    region_name=REGIAO,
    config=config_bedrock,
)


# ---------------------------------------------------------------------------
# Validacao das mensagens recebidas na rota /chat (Requisito 2)
# ---------------------------------------------------------------------------
# A funcao abaixo concentra todas as regras de validacao do corpo da
# requisicao POST /chat. Ela e intencionalmente separada da rota para manter o
# codigo simples e didatico: a rota apenas chama esta funcao e decide o status
# HTTP com base no resultado.
#
# Contrato (conforme o design): validar_mensagem(dados) -> (ok, erro, texto)
#   - ok    : booleano que indica se a validacao passou.
#   - erro  : em caso de falha, a mensagem de erro apropriada (str); em caso de
#             sucesso, vale None.
#   - texto : em caso de sucesso, o texto da mensagem ja saneado (sem espacos
#             nas pontas); em caso de falha, vale None.
#
# O parametro "dados" e o corpo JSON ja desserializado da requisicao. Quando o
# corpo esta ausente ou nao e um JSON valido, convencionamos que a rota chama
# esta funcao passando None, acionando o tratamento do R2.4.
def validar_mensagem(dados):
    """Valida o corpo da requisicao /chat e devolve (ok, erro, texto).

    Regras aplicadas, na ordem do design:
      1. Corpo ausente ou que nao seja JSON valido (dados nao e um dict) ->
         erro de "corpo deve ser JSON valido" (R2.4).
      2. Campo `message` ausente, nao-texto, vazio ou so com espacos em branco
         -> erro de campo obrigatorio nao vazio (R2.2).
      3. `message` com mais de LIMITE_CARACTERES (4000) caracteres -> erro de
         limite excedido (R2.3).

    Em caso de sucesso, retorna (True, None, texto_saneado), onde o texto
    saneado e a mensagem sem espacos em branco nas extremidades.
    """
    # Regra 1 (R2.4): o corpo precisa ser um JSON valido. Quando o Flask nao
    # consegue desserializar o corpo (ausente ou nao-JSON), a rota repassa None
    # para ca; qualquer coisa que nao seja um objeto/dict tambem e considerada
    # corpo invalido (ex.: um JSON que seja apenas um numero ou uma lista).
    if not isinstance(dados, dict):
        return (False, "O corpo da requisicao deve ser um JSON valido.", None)

    # Regra 2 (R2.2): o campo `message` e obrigatorio, precisa ser texto e nao
    # pode estar vazio nem conter apenas espacos em branco.
    mensagem = dados.get("message")
    if not isinstance(mensagem, str) or not mensagem.strip():
        return (
            False,
            "O campo 'message' e obrigatorio e deve conter texto nao vazio.",
            None,
        )

    # A partir daqui trabalhamos com o texto saneado (sem espacos nas pontas).
    texto = mensagem.strip()

    # Regra 3 (R2.3): o texto nao pode exceder o limite de caracteres. Medimos
    # o comprimento do texto ja saneado contra LIMITE_CARACTERES (4000).
    if len(texto) > LIMITE_CARACTERES:
        return (
            False,
            f"A mensagem excede o limite de {LIMITE_CARACTERES} caracteres permitido.",
            None,
        )

    # Validacao concluida com sucesso: devolvemos o texto saneado.
    return (True, None, texto)


# ---------------------------------------------------------------------------
# Montagem do payload de invocacao da Bedrock (Requisitos 3.3, 5.2)
# ---------------------------------------------------------------------------
# A funcao abaixo monta o corpo (JSON) enviado ao modelo Claude Haiku via
# invoke_model, no formato de mensagens do Anthropic na Bedrock. Mantemos a
# logica separada da rota para o codigo ficar simples e didatico: a rota apenas
# chama esta funcao com a mensagem ja validada e o historico recebido.
#
# Contrato (conforme o design): montar_payload(mensagem, history) -> dict
#   - mensagem : o texto atual do guitarrista, ja validado/saneado.
#   - history  : lista opcional de turnos anteriores da conversa. Cada turno e
#                um objeto {"author": "guitarrista"|"botones", "text": "..."}.
#                Pode vir ausente (None) ou como lista vazia; nesse caso a
#                conversa e tratada como inicio (sem turnos anteriores).
#
# O corpo resultante tem o formato:
#   {
#     "anthropic_version": "bedrock-2023-05-31",
#     "max_tokens": 1024,
#     "system": "<conteudo de SYSTEM_PROMPT>",
#     "messages": [ {"role": "user"|"assistant", "content": "..."}, ... ]
#   }
# A constante SYSTEM_PROMPT vai no campo "system" (R3.3), e os turnos de
# "messages" sao reconstruidos a partir do historico (autor guitarrista ->
# role user; autor botones -> role assistant), seguidos da mensagem atual do
# guitarrista como um turno "user" (R5.2).

# Versao do formato de mensagens do Anthropic exigida pela Bedrock.
ANTHROPIC_VERSION = "bedrock-2023-05-31"

# Numero maximo de tokens que o modelo pode gerar em uma resposta.
MAX_TOKENS = 1024

# Mapa de autor (como vem do historico, no corpo da requisicao) para o papel
# (role) esperado pela Bedrock. Qualquer autor fora deste mapa e ignorado por
# ser considerado uma entrada malformada.
MAPA_AUTOR_PARA_ROLE = {
    "guitarrista": "user",
    "botones": "assistant",
}


def montar_payload(mensagem, history=None):
    """Monta o corpo da invocacao do modelo no formato Anthropic/Bedrock.

    Reconstroi os turnos anteriores a partir de `history` (quando houver),
    convertendo o autor de cada turno no papel correspondente, e acrescenta a
    mensagem atual do guitarrista como ultimo turno "user". Retorna o dicionario
    pronto para ser serializado como corpo de invoke_model.

    O tratamento do historico e defensivo (R5.2): se `history` for ausente,
    None, nao for uma lista, ou contiver entradas malformadas (que nao sejam
    dicts, sem autor reconhecido ou sem texto valido), essas entradas sao
    simplesmente ignoradas, sem quebrar a montagem do payload.
    """
    # Lista de turnos que ira para o campo "messages" do payload.
    messages = []

    # Reconstroi os turnos anteriores apenas se o historico for uma lista.
    # Qualquer outro valor (None, string, dict solto etc.) e tratado como
    # "sem historico", mantendo a montagem segura (R5.2).
    if isinstance(history, list):
        for turno in history:
            # Ignora entradas que nao sejam objetos/dicts (malformadas).
            if not isinstance(turno, dict):
                continue

            # Converte o autor no papel esperado pela Bedrock. Autores
            # desconhecidos (ou ausentes) resultam em role None e sao ignorados.
            autor = turno.get("author")
            role = MAPA_AUTOR_PARA_ROLE.get(autor)
            if role is None:
                continue

            # O texto precisa ser uma string nao vazia (desconsiderando
            # espacos). Entradas sem texto valido sao ignoradas.
            texto = turno.get("text")
            if not isinstance(texto, str) or not texto.strip():
                continue

            messages.append({"role": role, "content": texto})

    # Acrescenta a mensagem atual do guitarrista como ultimo turno "user".
    messages.append({"role": "user", "content": mensagem})

    # Monta o corpo final no formato esperado pelo Claude na Bedrock. O campo
    # "system" recebe a constante SYSTEM_PROMPT (R3.3).
    return {
        "anthropic_version": ANTHROPIC_VERSION,
        "max_tokens": MAX_TOKENS,
        "system": SYSTEM_PROMPT,
        "messages": messages,
    }

# ---------------------------------------------------------------------------
# Invocacao do modelo e extracao do texto gerado (Requisitos 3.1, 3.2, 3.4, 3.5)
# ---------------------------------------------------------------------------
# As duas funcoes abaixo completam o caminho entre o payload ja montado por
# montar_payload e o texto que sera devolvido no campo "reply" da rota /chat.
# Mantemos a logica separada da rota para o codigo ficar simples e didatico.
#
# Precisamos do modulo json para serializar o payload (corpo enviado a Bedrock)
# e para desserializar o corpo da resposta retornada pelo modelo.
import json


def extrair_texto(resposta_bruta):
    """Extrai o texto gerado a partir da resposta bruta da Bedrock.

    O corpo da resposta e um stream que precisa ser lido com
    `resposta_bruta["body"].read()`, decodificado como JSON e, no formato do
    Claude na Bedrock, o texto fica no primeiro bloco de conteudo
    (`content[0].text`).

    O tratamento e defensivo (R3.5): se a estrutura vier inesperada -- corpo
    ausente, JSON invalido, lista de conteudo vazia, bloco sem o campo "text"
    etc. -- retornamos string vazia em vez de levantar excecao. A rota /chat
    usa esse "" como sinal de que nao houve texto gerado e aciona o erro 500.
    """
    try:
        # Le o corpo da resposta (stream) e decodifica como JSON. Caso o corpo
        # esteja ausente ou nao possa ser lido/decodificado, caimos no except.
        corpo_bruto = resposta_bruta["body"].read()
        corpo = json.loads(corpo_bruto)

        # No formato Anthropic/Bedrock, o texto fica em content[0].text.
        texto = corpo["content"][0]["text"]

        # So consideramos valido um texto que seja string; qualquer outro tipo
        # e tratado como ausencia de texto (retorna "").
        if isinstance(texto, str):
            return texto
        return ""
    except (KeyError, IndexError, TypeError, ValueError, AttributeError):
        # Estruturas inesperadas (chave/indice ausente, corpo nao-dict, JSON
        # invalido, body sem metodo read etc.) resultam em texto vazio para
        # acionar o tratamento de erro do R3.5, sem quebrar o servidor.
        return ""


def invocar_modelo(payload):
    """Invoca o modelo Claude Haiku na Bedrock e retorna o texto gerado.

    Serializa o `payload` (ja montado por montar_payload) como JSON e o envia
    no corpo (body) de `cliente_bedrock.invoke_model`, usando o `MODEL_ID`
    exato (R3.2). O limite de tempo de 30s ja esta configurado no cliente
    (read_timeout/connect_timeout em TIMEOUT_SEGUNDOS), portanto NAO e
    reconfigurado aqui (R3.1).

    Retorna o texto extraido da resposta via extrair_texto. Eventuais erros do
    servico ou estouro do timeout propagam como excecao e sao tratados pela
    rota /chat (R3.6), que decide o status HTTP apropriado.
    """
    resposta_bruta = cliente_bedrock.invoke_model(
        modelId=MODEL_ID,
        body=json.dumps(payload),
    )
    return extrair_texto(resposta_bruta)


# ---------------------------------------------------------------------------
# Rota GET "/" - servir a pagina de chat (Requisito 1)
# ---------------------------------------------------------------------------
# Esta rota entrega a interface de conversa do Botones. Ela renderiza o
# template templates/index.html e devolve o HTML com status 200 (R1.1).
#
# Caso a renderizacao falhe -- por exemplo, se o arquivo templates/index.html
# estiver ausente ou tiver algum erro --, o render_template lanca uma excecao.
# Capturamos essa falha com try/except e devolvemos uma resposta de erro com
# status HTTP 500 indicando que a pagina nao pode ser carregada (R1.2), em vez
# de deixar o servidor estourar um erro generico.
@app.route("/")
def pagina_chat():
    """Serve a pagina de chat renderizando templates/index.html.

    Em caso de sucesso, retorna o HTML renderizado com status 200 (R1.1).
    Se a renderizacao falhar (template ausente ou com erro), retorna uma
    resposta de texto com status 500 indicando que a pagina nao pode ser
    carregada (R1.2).
    """
    try:
        # Renderiza a pagina de chat. O Flask procura o arquivo em
        # templates/index.html. Em sucesso, o retorno padrao ja tem status 200.
        return render_template("index.html")
    except Exception:
        # Qualquer falha ao localizar ou renderizar o template resulta em uma
        # resposta de erro clara, sem expor detalhes internos ao usuario (R1.2).
        return "Nao foi possivel carregar a pagina de chat.", 500


# ---------------------------------------------------------------------------
# Rota POST "/chat" - processar a mensagem do guitarrista (Requisitos 2 e 3)
# ---------------------------------------------------------------------------
# Esta rota recebe o corpo JSON com a mensagem do guitarrista, valida a
# entrada, monta o payload, invoca o modelo Claude Haiku na Bedrock e devolve
# a resposta gerada no campo "reply". Toda a logica pesada ja esta nas funcoes
# auxiliares (validar_mensagem, montar_payload, invocar_modelo); aqui apenas
# orquestramos essas chamadas e decidimos o status HTTP adequado.
#
# Fluxo e tratamento de erros (conforme o design):
#   - Corpo ausente/nao-JSON ou `message` invalido/acima do limite ->
#     400 {"error": "..."} (R2.2, R2.3, R2.4).
#   - Sucesso com texto nao vazio -> 200 {"reply": "..."} (R2.1, R3.4).
#   - Texto vazio retornado pelo modelo -> 500 {"error": "..."} sem "reply"
#     (R3.5).
#   - Falha do servico ou estouro do timeout na invocacao ->
#     500 {"error": "..."} sem "reply" (R3.6).
@app.route("/chat", methods=["POST"])
def chat():
    """Processa uma mensagem do guitarrista e devolve a resposta do Botones.

    Le o corpo JSON de forma segura (corpo ausente/nao-JSON vira None), valida
    a entrada com validar_mensagem e, se valida, monta o payload com o
    historico opcional, invoca o modelo e devolve o texto gerado.
    """
    # Le o corpo JSON de forma segura. Com silent=True, um corpo ausente ou
    # que nao seja JSON valido retorna None (em vez de levantar erro), o que
    # aciona a regra do R2.4 dentro de validar_mensagem.
    dados = request.get_json(silent=True)

    # Validacao da entrada (R2.2, R2.3, R2.4). Em caso de falha, devolvemos
    # 400 com a mensagem de erro apropriada (em portugues) no campo "error".
    ok, erro, texto = validar_mensagem(dados)
    if not ok:
        return jsonify({"error": erro}), 400

    # Memoria de conversa no servidor: em vez de ler o historico do corpo da
    # requisicao, usamos a lista global HISTORICO_CONVERSA, que ja acumula
    # todos os turnos anteriores. Assim, a cada pergunta, todas as mensagens
    # anteriores sao reenviadas ao Bedrock.
    payload = montar_payload(texto, HISTORICO_CONVERSA)

    # Invoca o modelo dentro de try/except para cobrir falhas do servico e
    # estouro do timeout de 30s (R3.6). Qualquer excecao na comunicacao com a
    # Bedrock resulta em 500 com "error", sem expor detalhes internos nem
    # credenciais ao usuario.
    try:
        resposta = invocar_modelo(payload)
    except Exception:
        return (
            jsonify({"error": "Falha na comunicacao com o modelo. Tente de novo mais tarde."}),
            500,
        )

    # Texto vazio significa que o modelo nao gerou conteudo utilizavel (R3.5):
    # devolvemos 500 com "error" e SEM o campo "reply". Nesse caso NAO gravamos
    # nada no historico, para nao poluir a memoria com um turno sem resposta.
    if not resposta:
        return (
            jsonify({"error": "Falha na geracao da resposta. Tente de novo."}),
            500,
        )

    # Sucesso: so agora gravamos os dois turnos na memoria da conversa -- a
    # pergunta do guitarrista e a resposta do Botones --, nessa ordem, para que
    # a proxima pergunta leve todo o contexto ao modelo.
    HISTORICO_CONVERSA.append({"author": "guitarrista", "text": texto})
    HISTORICO_CONVERSA.append({"author": "botones", "text": resposta})

    # Devolvemos o texto gerado no campo "reply" com status 200 (R2.1, R3.4).
    return jsonify({"reply": resposta}), 200

# ---------------------------------------------------------------------------
# Inicializacao do servidor (Requisito 7)
# ---------------------------------------------------------------------------
# Este bloco so roda quando o arquivo e executado diretamente (python app.py).
# Ele verifica as credenciais AWS ANTES de subir o servidor e, em seguida,
# inicia o Flask em localhost:5000. Tambem trata o caso de a porta ja estar
# em uso, encerrando com erro claro e codigo de saida diferente de zero.
if __name__ == "__main__":
    # Verifica as Credenciais_AWS logo na partida. Se faltar qualquer uma,
    # verificar_credenciais() registra APENAS os nomes das variaveis ausentes
    # (nunca os valores) e interrompe a inicializacao via SystemExit (R6.3).
    # Assim o servidor NAO sobe sem as credenciais necessarias.
    verificar_credenciais()

    try:
        # Sobe o servidor aceitando requisicoes em localhost (127.0.0.1) na
        # porta 5000. A partir daqui, "python app.py" passa a atender em
        # localhost:5000 (R7.1).
        app.run(host="127.0.0.1", port=5000)
    except OSError as erro:
        # Se a porta 5000 ja estiver em uso (endereco indisponivel), o
        # app.run levanta um OSError. Capturamos essa falha, registramos uma
        # mensagem clara indicando que a porta esta indisponivel e encerramos
        # com codigo de saida diferente de zero (R7.2). Nenhuma credencial e
        # exposta na mensagem de erro.
        print(
            "[ERRO] Nao foi possivel iniciar o servidor: a porta 5000 ja esta "
            "em uso. Encerre o processo que a ocupa ou libere a porta e tente "
            "novamente.",
            file=sys.stderr,
        )
        raise SystemExit(1)
