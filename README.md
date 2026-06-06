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

## Proximos Passos Recomendados

- Adicionar conectores especificos para Zendesk e Jira Service Management.
- Criar arquivo de configuracao YAML/JSON para conectores proprietarios.
- Persistir historico de sentimento por ticket.
- Trocar ou complementar o analisador por modelo ML/LLM.
- Adicionar webhook/API para processamento automatico.
- Decidir licenciamento caso o uso com software proprietario seja requisito.

## Licenca

Este repositorio contem atualmente uma licenca GPLv3 no arquivo `LICENSE`. Se a
intencao for distribuir junto com software proprietario, revise a estrategia de
licenciamento antes de empacotar ou redistribuir.
