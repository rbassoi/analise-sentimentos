# Analise de Sentimentos para Tickets

Projeto para analisar sentimento em tickets de suporte e gravar o resultado de volta
na ferramenta de atendimento. O Freshdesk agora e apenas um conector; a arquitetura
permite adicionar Zendesk, Jira Service Management, ServiceNow, GLPI, Movidesk ou
sistemas proprietarios por HTTP/API.

## Objetivo

- Centralizar a regra de analise de sentimento.
- Padronizar tickets vindos de ferramentas diferentes.
- Permitir conectores plugaveis.
- Manter a interface React para analises manuais.
- Preparar evolucao futura para modelos ML/LLM sem reescrever integracoes.

## Estrutura

```text
sentiment_ticketing/
  core/
    models.py
    sentiment_analyzer.py
  connectors/
    base.py
    freshdesk.py
    generic_http.py
  pipeline.py
freshdesk-sentiment-integration.py
sentiment-analyzer.tsx
tests/
```

## Freshdesk

Configure as credenciais por variaveis de ambiente:

```bash
set FRESHDESK_DOMAIN=sua_conta
set FRESHDESK_API_KEY=sua_api_key
python freshdesk-sentiment-integration.py 123
```

Ou passe explicitamente:

```bash
python freshdesk-sentiment-integration.py 123 --domain sua_conta --api-key sua_api_key
```

O conector busca o ticket, inclui conversas no texto analisado e atualiza os campos
customizados `sentiment_score` e `sentiment_label`.

## Sistemas Proprietarios

Use `GenericHttpConnector` quando o sistema interno tiver endpoints HTTP simples.
O conector aceita URL base, endpoint de leitura, endpoint de atualizacao e campos de
texto configuraveis.

Exemplo conceitual:

```python
from sentiment_ticketing.connectors import GenericHttpConnector
from sentiment_ticketing.pipeline import TicketSentimentPipeline

connector = GenericHttpConnector(
    base_url="https://tickets.empresa.com/api",
    get_ticket_path="/tickets/{id}",
    update_ticket_path="/tickets/{id}/sentiment",
    token="token",
    text_field="description",
)

pipeline = TicketSentimentPipeline(connector)
sentiment = pipeline.analyze_and_update("ABC-123")
```

## Feedback e Retreino

A tela de analise permite marcar se o resultado esta certo ou errado. Quando
estiver errado, cada palavra do texto aparece com botoes `+` e `-` para marcar
aquela ocorrencia como positiva ou negativa.

Os feedbacks sao salvos para retreino. Por padrao, o projeto usa:

```text
data/sentiment_feedback.jsonl
```

Para usar PostgreSQL, instale as dependencias e configure `DATABASE_URL`:

```bash
pip install -r requirements.txt
set DATABASE_URL=postgresql://usuario:senha@localhost:5432/sentimentos
python server.py
```

Tambem e possivel usar variaveis `PGHOST`, `PGPORT`, `PGDATABASE`, `PGUSER` e
`PGPASSWORD`. A aplicacao cria automaticamente a tabela `sentiment_feedback`.

A pagina **Retreino** mostra as palavras salvas, contagens positivas/negativas
e exemplos de origem.

## Modelo PT-BR com scikit-learn/joblib

O analisador padrao usa uma abordagem hibrida:

- LeIA, uma adaptacao em portugues do algoritmo VADER;
- lexico operacional de suporte para termos como `erro`, `falha`, `problema` e
  `insatisfeito`;
- modelo opcional `joblib/scikit-learn` quando `SENTIMENT_MODEL_PATH` esta
  configurado.

O suporte a `joblib` foi inspirado pelo repositorio
`thiagonogueira/sentiment-analysis-ptbr`. Esse repositorio usa um pipeline com
`vectorizer` e `model`, e retorna rotulos como `Negativo`, `Neutro` e
`Positivo`.

Para usar um modelo desse tipo, informe o caminho pelo ambiente:

```bash
set SENTIMENT_MODEL_PATH=d:\modelos\sentiments-v2.joblib
python server.py
```

Quando `SENTIMENT_MODEL_PATH` esta definido, a aplicacao usa um analisador
hibrido:

- LeIA contribui com `compound`, negacao, pontuacao e intensificadores;
- o modelo treinado contribui com classificacao e confianca;
- o lexico de suporte reforca termos operacionais de tickets;
- a resposta da API mostra `engine`, `model_label` e `confidence`.

O modelo do repositorio externo nao foi copiado para este projeto porque nao ha
licenca explicita no repositorio analisado. Tambem pode haver alerta de versao
do scikit-learn ao carregar um `.joblib` treinado em versao diferente.

## LeIA

Este projeto incorpora codigo e lexicos do LeIA
(`https://github.com/rafjaa/LeIA`), licenciado sob MIT. O LeIA preserva a API do
VADER, aceita texto sem pre-processamento e retorna `pos`, `neg`, `neu` e
`compound`, onde `compound` varia de -1 a +1. A atribuicao esta documentada em
`THIRD_PARTY_NOTICES.md`.

## Proximos Passos Recomendados

- Adicionar conectores especificos para Zendesk e Jira Service Management.
- Criar arquivo de configuracao YAML/JSON para conectores proprietarios.
- Persistir historico de sentimento por ticket.
- Treinar um modelo proprio com dados reais de tickets de suporte.
- Adicionar webhook/API para processamento automatico.
- Decidir licenciamento caso o uso com software proprietario seja requisito.

## Licenca

Este repositorio contem atualmente uma licenca GPLv3 no arquivo `LICENSE`. Se a
intencao for distribuir junto com software proprietario, revise a estrategia de
licenciamento antes de empacotar ou redistribuir.
