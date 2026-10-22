# Botones

Botones é um chatbot web que ajuda guitarristas a montar presets no Amplitube 5. Você conversa com ele em português, diz o que quer tocar (gênero, banda, tipo de tom) e ele sugere um preset com amplificador, pedais, cabinet, efeitos e equalização.

## Como funciona

- Interface de chat servida por um servidor Flask (`app.py`).
- As respostas são geradas pelo modelo Claude Haiku via Amazon Bedrock.
- Botones só fala sobre guitarra: presets do Amplitube 5, tom, equipamentos e técnica. Assuntos fora disso são recusados educadamente.
- Responde sempre em português do Brasil, mesmo que você escreva em outro idioma.

## Requisitos

- Python 3
- Dependências listadas em `requirements.txt` (Flask e boto3)
- Credenciais da AWS com acesso ao Amazon Bedrock na região `us-east-1`

## Instalação

```bash
pip install -r requirements.txt
```

## Configuração

As credenciais da AWS são lidas apenas de variáveis de ambiente (nunca ficam no código):

```bash
export AWS_ACCESS_KEY_ID="sua-access-key"
export AWS_SECRET_ACCESS_KEY="sua-secret-key"
```

A região usada é `us-east-1`. Se você definir `AWS_REGION` ou `AWS_DEFAULT_REGION`, ela precisa ser `us-east-1`.

## Como rodar

```bash
python app.py
```

O servidor sobe em `http://localhost:5000`. Abra esse endereço no navegador para conversar com o Botones.

## Rotas

- `GET /` — serve a página de chat.
- `POST /chat` — recebe a mensagem do guitarrista (campo `message`, até 4000 caracteres) e devolve a resposta no campo `reply`.

## Créditos

Projeto desenvolvido no Workshop da Computação de 2026 da UNIFAL-MG.
