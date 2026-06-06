import json
import os
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from sentiment_ticketing.connectors import FreshdeskConnector
from sentiment_ticketing.core.sentiment_analyzer import create_default_analyzer


HOST = "127.0.0.1"
PORT = 8000
DATA_DIR = Path("data")
FEEDBACK_FILE = DATA_DIR / "sentiment_feedback.jsonl"


CONNECTORS = [
    {
        "id": "freshdesk",
        "name": "Freshdesk",
        "status": "available",
        "fields": ["domain", "apiKey", "ticketId", "limit"],
    },
    {
        "id": "jira",
        "name": "Jira Service Management",
        "status": "available",
        "fields": ["siteUrl", "email", "apiToken", "projectKey"],
    },
    {
        "id": "generic_http",
        "name": "HTTP Proprietario",
        "status": "available",
        "fields": ["baseUrl", "token", "getTicketPath", "updateTicketPath", "textField"],
    },
]


class FeedbackStore:
    def __init__(self, fallback_file: Path):
        self.fallback_file = fallback_file
        self.driver = self._load_postgres_driver()
        self.dsn = self._postgres_dsn()
        self.uses_postgres = bool(self.driver and self.dsn)
        if self.uses_postgres:
            try:
                self._ensure_postgres_schema()
            except Exception as exc:
                print(f"PostgreSQL feedback store unavailable, using JSONL fallback: {exc}")
                self.uses_postgres = False

    def save(self, record: dict) -> int:
        if self.uses_postgres:
            return self._save_postgres(record)
        return self._save_file(record)

    def list_records(self, limit: int = 500) -> list[dict]:
        if self.uses_postgres:
            return self._list_postgres_records(limit)
        return self._list_file_records(limit)

    def term_summary(self, limit: int = 500) -> dict:
        records = self.list_records(limit)
        positive_terms: Counter[str] = Counter()
        negative_terms: Counter[str] = Counter()
        examples: dict[str, list[dict]] = defaultdict(list)

        for record in records:
            for term in record.get("positive_terms", []):
                word = term.get("word")
                if word:
                    positive_terms[word] += 1
                    self._add_example(examples[word], record, "positive")
            for term in record.get("negative_terms", []):
                word = term.get("word")
                if word:
                    negative_terms[word] += 1
                    self._add_example(examples[word], record, "negative")

        words = sorted(
            set(positive_terms) | set(negative_terms),
            key=lambda word: (negative_terms[word] + positive_terms[word], word),
            reverse=True,
        )

        return {
            "storage": "postgres" if self.uses_postgres else "jsonl",
            "records": len(records),
            "words": [
                {
                    "word": word,
                    "positive": positive_terms[word],
                    "negative": negative_terms[word],
                    "total": positive_terms[word] + negative_terms[word],
                    "examples": examples[word][:3],
                }
                for word in words
            ],
        }

    def _add_example(self, examples: list[dict], record: dict, label: str) -> None:
        if len(examples) >= 3:
            return
        examples.append(
            {
                "label": label,
                "source": record.get("source"),
                "ticket_id": (record.get("ticket") or {}).get("id")
                if isinstance(record.get("ticket"), dict)
                else None,
                "text": str(record.get("text", ""))[:180],
            }
        )

    def _load_postgres_driver(self):
        try:
            import psycopg

            return psycopg
        except ImportError:
            try:
                import psycopg2

                return psycopg2
            except ImportError:
                return None

    def _postgres_dsn(self) -> str | None:
        if os.getenv("DATABASE_URL"):
            return os.getenv("DATABASE_URL")
        if not os.getenv("PGHOST") and not os.getenv("PGDATABASE"):
            return None

        parts = []
        mapping = {
            "PGHOST": "host",
            "PGPORT": "port",
            "PGDATABASE": "dbname",
            "PGUSER": "user",
            "PGPASSWORD": "password",
        }
        for env_name, dsn_name in mapping.items():
            value = os.getenv(env_name)
            if value:
                parts.append(f"{dsn_name}={value}")
        return " ".join(parts)

    def _connect(self):
        return self.driver.connect(self.dsn)

    def _ensure_postgres_schema(self) -> None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS sentiment_feedback (
                        id BIGSERIAL PRIMARY KEY,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                        record JSONB NOT NULL
                    )
                    """
                )
            connection.commit()

    def _save_postgres(self, record: dict) -> int:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO sentiment_feedback (record) VALUES (%s::jsonb)",
                    (json.dumps(record, ensure_ascii=False),),
                )
                cursor.execute("SELECT COUNT(*) FROM sentiment_feedback")
                count = cursor.fetchone()[0]
            connection.commit()
        return int(count)

    def _list_postgres_records(self, limit: int) -> list[dict]:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT record::text FROM sentiment_feedback ORDER BY id DESC LIMIT %s",
                    (limit,),
                )
                rows = cursor.fetchall()
        return [json.loads(row[0]) for row in rows]

    def _save_file(self, record: dict) -> int:
        DATA_DIR.mkdir(exist_ok=True)
        with self.fallback_file.open("a", encoding="utf-8") as feedback_file:
            feedback_file.write(json.dumps(record, ensure_ascii=False) + "\n")
        return len(self._list_file_records(100000))

    def _list_file_records(self, limit: int) -> list[dict]:
        if not self.fallback_file.exists():
            return []
        records = []
        with self.fallback_file.open("r", encoding="utf-8") as feedback_file:
            for line in feedback_file:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return records[-limit:][::-1]


FEEDBACK_STORE = FeedbackStore(FEEDBACK_FILE)


INDEX_HTML = """<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Analise de Sentimentos</title>
  <style>
    :root {
      color-scheme: light;
      font-family: Inter, Segoe UI, Arial, sans-serif;
      background: #eef2f5;
      color: #1f2933;
    }
    * {
      box-sizing: border-box;
    }
    body {
      margin: 0;
      min-height: 100vh;
      background:
        linear-gradient(180deg, rgba(255,255,255,0.78), rgba(238,242,245,0.92)),
        #eef2f5;
    }
    button, input, textarea, select {
      font: inherit;
    }
    .app {
      min-height: 100vh;
      display: grid;
      grid-template-columns: 260px 1fr;
    }
    aside {
      background: #172026;
      color: #edf4f2;
      padding: 24px 18px;
      display: flex;
      flex-direction: column;
      gap: 24px;
    }
    .brand {
      display: grid;
      gap: 5px;
    }
    .brand strong {
      font-size: 18px;
      letter-spacing: 0;
    }
    .brand span {
      color: #aebdc5;
      font-size: 13px;
      line-height: 1.45;
    }
    nav {
      display: grid;
      gap: 8px;
    }
    .nav-button {
      width: 100%;
      border: 1px solid transparent;
      background: transparent;
      color: #d9e6e2;
      border-radius: 6px;
      padding: 10px 12px;
      text-align: left;
      cursor: pointer;
    }
    .nav-button.active {
      background: #243139;
      border-color: #3a4b54;
      color: #ffffff;
    }
    .sidebar-note {
      margin-top: auto;
      border-top: 1px solid #33444d;
      padding-top: 16px;
      color: #aebdc5;
      font-size: 12px;
      line-height: 1.5;
    }
    main {
      padding: 28px;
      display: grid;
      gap: 20px;
      align-content: start;
    }
    header {
      display: flex;
      align-items: flex-end;
      justify-content: space-between;
      gap: 16px;
    }
    h1, h2, h3, p {
      margin: 0;
    }
    h1 {
      font-size: 28px;
      letter-spacing: 0;
    }
    .subtitle {
      margin-top: 6px;
      color: #5b6871;
      line-height: 1.45;
    }
    .status-pill {
      border: 1px solid #cad6dd;
      background: #ffffff;
      color: #35434b;
      border-radius: 999px;
      padding: 7px 12px;
      font-size: 13px;
      white-space: nowrap;
    }
    .view {
      display: none;
    }
    .view.active {
      display: grid;
      gap: 18px;
    }
    .grid {
      display: grid;
      grid-template-columns: minmax(0, 1.35fr) minmax(320px, 0.65fr);
      gap: 18px;
      align-items: start;
    }
    .panel {
      background: #ffffff;
      border: 1px solid #d7e0e6;
      border-radius: 8px;
      padding: 18px;
      box-shadow: 0 10px 26px rgba(31, 41, 51, 0.07);
    }
    .panel-header {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: start;
      margin-bottom: 14px;
    }
    .panel h2 {
      font-size: 18px;
      letter-spacing: 0;
    }
    .panel p {
      color: #60707a;
      line-height: 1.45;
      font-size: 14px;
    }
    label {
      display: grid;
      gap: 6px;
      color: #2f3c44;
      font-size: 13px;
      font-weight: 700;
    }
    textarea, input, select {
      width: 100%;
      border: 1px solid #b9c7cf;
      border-radius: 6px;
      background: #ffffff;
      color: #172026;
      padding: 10px 11px;
      outline: none;
    }
    textarea:focus, input:focus, select:focus {
      border-color: #176b5b;
      box-shadow: 0 0 0 3px rgba(23, 107, 91, 0.15);
    }
    textarea {
      min-height: 260px;
      resize: vertical;
      line-height: 1.45;
    }
    .form-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
    }
    .full {
      grid-column: 1 / -1;
    }
    .actions {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 14px;
    }
    .primary, .secondary {
      border: 0;
      border-radius: 6px;
      padding: 10px 14px;
      cursor: pointer;
      font-weight: 700;
    }
    .primary {
      background: #176b5b;
      color: #ffffff;
    }
    .secondary {
      background: #e8eef1;
      color: #26343c;
    }
    .primary:disabled, .secondary:disabled {
      cursor: not-allowed;
      opacity: 0.65;
    }
    .score-box {
      display: grid;
      gap: 12px;
    }
    .score-value {
      display: flex;
      align-items: baseline;
      gap: 10px;
    }
    .score-value strong {
      font-size: 38px;
      letter-spacing: 0;
    }
    .score-value span {
      color: #60707a;
      font-weight: 700;
    }
    .meter {
      height: 10px;
      border-radius: 999px;
      background: #d7e0e6;
      overflow: hidden;
    }
    .meter-fill {
      width: 50%;
      height: 100%;
      background: #176b5b;
      transition: width 180ms ease;
    }
    .result-list {
      display: grid;
      gap: 9px;
      margin-top: 4px;
    }
    .result-row {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      border-top: 1px solid #edf1f3;
      padding-top: 9px;
      color: #34444c;
      font-size: 14px;
    }
    .result-row span:first-child {
      font-weight: 700;
    }
    .feedback-panel {
      border-top: 1px solid #edf1f3;
      padding-top: 12px;
      display: grid;
      gap: 12px;
    }
    .segmented {
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 8px;
    }
    .segmented button {
      border: 1px solid #c8d5dc;
      background: #f7fafb;
      color: #2f3c44;
      border-radius: 6px;
      padding: 9px 10px;
      cursor: pointer;
      font-weight: 700;
    }
    .segmented button.active {
      background: #172026;
      color: #ffffff;
      border-color: #172026;
    }
    .word-labels {
      display: none;
      gap: 12px;
    }
    .word-labels.active {
      display: grid;
    }
    .chip-grid {
      display: flex;
      flex-wrap: wrap;
      gap: 7px;
    }
    .clickable-text {
      max-height: 260px;
      overflow: auto;
      border: 1px solid #d7e0e6;
      border-radius: 8px;
      background: #f8fafb;
      padding: 10px;
      line-height: 1.75;
      white-space: pre-wrap;
    }
    .word-chip {
      border: 1px solid #c8d5dc;
      border-radius: 999px;
      background: #ffffff;
      color: #2f3c44;
      padding: 6px 10px;
      cursor: pointer;
      font-size: 13px;
    }
    .word-chip.positive {
      background: #e8f4ef;
      border-color: #9dccba;
      color: #176b5b;
    }
    .word-chip.negative {
      background: #faecea;
      border-color: #e0aaa5;
      color: #a33a32;
    }
    .word-chip.neutral {
      background: #ffffff;
      border-color: #c8d5dc;
      color: #2f3c44;
    }
    .word-token {
      display: inline-flex;
      align-items: center;
      gap: 3px;
      margin: 2px 3px;
      vertical-align: middle;
    }
    .word-token-label {
      font-weight: 700;
      color: #25343c;
    }
    .polarity-button {
      border: 1px solid #c8d5dc;
      border-radius: 999px;
      background: #ffffff;
      color: #2f3c44;
      cursor: pointer;
      min-width: 28px;
      height: 28px;
      padding: 0 7px;
      font-weight: 700;
      line-height: 1;
    }
    .polarity-button.positive.active {
      background: #176b5b;
      border-color: #176b5b;
      color: #ffffff;
    }
    .polarity-button.negative.active {
      background: #a33a32;
      border-color: #a33a32;
      color: #ffffff;
    }
    .feedback-status {
      color: #176b5b;
      font-weight: 700;
      font-size: 13px;
      min-height: 18px;
    }
    .tabs {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-bottom: 14px;
    }
    .tab {
      border: 1px solid #c8d5dc;
      background: #f7fafb;
      color: #2f3c44;
      border-radius: 999px;
      padding: 8px 12px;
      cursor: pointer;
      font-weight: 700;
      font-size: 13px;
    }
    .tab.active {
      background: #172026;
      border-color: #172026;
      color: #ffffff;
    }
    .connector-panel {
      display: none;
    }
    .connector-panel.active {
      display: grid;
      gap: 12px;
    }
    .connector-summary {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 12px;
    }
    .summary-item {
      border: 1px solid #d7e0e6;
      border-radius: 8px;
      padding: 14px;
      background: #ffffff;
    }
    .summary-item strong {
      display: block;
      margin-bottom: 6px;
    }
    .summary-item span {
      color: #60707a;
      font-size: 13px;
    }
    .toast {
      min-height: 20px;
      color: #176b5b;
      font-weight: 700;
      font-size: 13px;
    }
    .ticket-list {
      display: grid;
      gap: 8px;
      margin-top: 12px;
    }
    .ticket-item {
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 12px;
      align-items: center;
      border: 1px solid #d7e0e6;
      border-radius: 8px;
      padding: 12px;
      background: #f8fafb;
    }
    .ticket-item strong {
      display: block;
      margin-bottom: 4px;
    }
    .ticket-item span {
      color: #60707a;
      font-size: 13px;
    }
    .ticket-score {
      color: #172026;
      font-weight: 700;
      text-align: right;
      white-space: nowrap;
    }
    .batch-panel {
      display: none;
    }
    .batch-panel.active {
      display: block;
    }
    .batch-header {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: center;
      margin-bottom: 14px;
    }
    .batch-grid {
      display: grid;
      gap: 8px;
    }
    .batch-ticket {
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto auto;
      gap: 12px;
      align-items: center;
      border: 1px solid #d7e0e6;
      border-radius: 8px;
      padding: 12px;
      background: #ffffff;
    }
    .batch-ticket strong {
      display: block;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .batch-ticket span {
      color: #60707a;
      font-size: 13px;
    }
    .sentiment-pill {
      border-radius: 999px;
      padding: 6px 10px;
      background: #eef4f2;
      color: #176b5b;
      font-weight: 700;
      font-size: 13px;
      white-space: nowrap;
    }
    .sentiment-pill.negative {
      background: #faecea;
      color: #a33a32;
    }
    .company-aggregate {
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto auto;
      gap: 12px;
      align-items: center;
      border: 1px solid #d7e0e6;
      border-radius: 8px;
      padding: 12px;
      background: #f8fafb;
    }
    .company-aggregate strong {
      display: block;
      margin-bottom: 4px;
    }
    .company-aggregate span {
      color: #60707a;
      font-size: 13px;
    }
    .training-table {
      display: grid;
      gap: 8px;
    }
    .training-row {
      display: grid;
      grid-template-columns: minmax(160px, 1fr) repeat(3, 96px);
      gap: 12px;
      align-items: center;
      border: 1px solid #d7e0e6;
      border-radius: 8px;
      padding: 12px;
      background: #ffffff;
    }
    .training-row.header {
      background: #f2f6f7;
      font-weight: 700;
    }
    .training-word {
      font-weight: 700;
    }
    .training-examples {
      grid-column: 1 / -1;
      color: #60707a;
      font-size: 13px;
      line-height: 1.45;
    }
    @media (max-width: 920px) {
      .app {
        grid-template-columns: 1fr;
      }
      aside {
        position: static;
      }
      .grid, .connector-summary {
        grid-template-columns: 1fr;
      }
      .batch-ticket {
        grid-template-columns: 1fr;
      }
      .company-aggregate {
        grid-template-columns: 1fr;
      }
      .training-row {
        grid-template-columns: 1fr;
      }
      header {
        align-items: start;
        flex-direction: column;
      }
    }
    @media (max-width: 560px) {
      main {
        padding: 18px;
      }
      .form-grid {
        grid-template-columns: 1fr;
      }
      .score-value strong {
        font-size: 30px;
      }
    }
  </style>
</head>
<body>
  <div class="app">
    <aside>
      <div class="brand">
        <strong>Sentiment Desk</strong>
        <span>Analise de tickets e integracoes para ferramentas de suporte.</span>
      </div>
      <nav>
        <button class="nav-button active" data-view="analyzer">Analise</button>
        <button class="nav-button" data-view="connectors">Conectores</button>
        <button class="nav-button" data-view="training">Retreino</button>
      </nav>
      <div class="sidebar-note">
        As configuracoes digitadas nesta tela ficam no navegador. Nenhuma chave e salva em arquivo pelo servidor.
      </div>
    </aside>
    <main>
      <header>
        <div>
          <h1>Analise de Sentimentos</h1>
          <p class="subtitle">Cole um texto, avalie o sentimento e prepare a integracao com Freshdesk, Jira ou APIs proprietarias.</p>
        </div>
        <div class="status-pill" id="connector-count">Carregando conectores...</div>
      </header>

      <section class="view active" id="analyzer-view">
        <div class="grid">
          <div class="panel">
            <div class="panel-header">
              <div>
                <h2>Texto do ticket</h2>
                <p>Use assunto, descricao e conversas relevantes para uma leitura mais fiel.</p>
              </div>
            </div>
            <label>
              Conteudo para analise
              <textarea id="text" placeholder="Ex.: Cliente insatisfeito com erro recorrente no portal..."></textarea>
            </label>
            <div class="actions">
              <button class="primary" id="analyze">Analisar sentimento</button>
              <button class="secondary" id="clear-text">Limpar</button>
            </div>
          </div>
          <div class="panel score-box">
            <div class="panel-header">
              <div>
                <h2>Resultado</h2>
                <p id="result-hint">Aguardando texto para analise.</p>
              </div>
            </div>
            <div class="score-value">
              <strong id="score">0.00</strong>
              <span id="label">Neutro</span>
            </div>
            <div class="meter"><div class="meter-fill" id="meter-fill"></div></div>
            <div class="result-list">
              <div class="result-row"><span>Palavras positivas</span><span id="positive">-</span></div>
              <div class="result-row"><span>Palavras negativas</span><span id="negative">-</span></div>
              <div class="result-row"><span>Motor</span><span id="engine">keyword</span></div>
              <div class="result-row"><span>Modelo PT-BR</span><span id="model">-</span></div>
              <div class="result-row"><span>Classificacao</span><span id="classification">Manual</span></div>
            </div>
            <div class="feedback-panel">
              <div>
                <h2>Validacao</h2>
                <p>Informe se a analise esta correta. Se estiver errada, marque palavras para retreino.</p>
              </div>
              <div class="segmented">
                <button type="button" id="feedback-correct">Certa</button>
                <button type="button" id="feedback-wrong">Errada</button>
              </div>
              <div class="word-labels" id="word-labels">
                <label>
                  Clique nas palavras para retreino
                  <div class="clickable-text" id="feedback-chip-list"></div>
                </label>
              </div>
              <div class="actions">
                <button type="button" class="primary" id="save-feedback">Salvar feedback</button>
              </div>
              <div class="feedback-status" id="feedback-status"></div>
            </div>
          </div>
        </div>
        <div class="panel batch-panel" id="batch-panel">
          <div class="batch-header">
            <div>
              <h2>Tickets analisados</h2>
              <p id="batch-summary">Cada ticket e analisado separadamente.</p>
            </div>
            <button class="secondary" id="clear-batch">Limpar lista</button>
          </div>
          <div class="batch-grid" id="batch-results"></div>
        </div>
        <div class="panel batch-panel" id="company-panel">
          <div class="batch-header">
            <div>
              <h2>Agregado por empresa</h2>
              <p id="company-summary">Sentimento medio por empresa nos tickets retornados.</p>
            </div>
          </div>
          <div class="batch-grid" id="company-results"></div>
        </div>
      </section>

      <section class="view" id="connectors-view">
        <div class="connector-summary" id="connector-summary"></div>
        <div class="panel">
          <div class="panel-header">
            <div>
              <h2>Configuracoes de conexao</h2>
              <p>Escolha uma ferramenta e preencha os dados de acesso. Para producao, mova estes segredos para variaveis de ambiente ou um secret manager.</p>
            </div>
          </div>
          <div class="tabs">
            <button class="tab active" data-connector="freshdesk">Freshdesk</button>
            <button class="tab" data-connector="jira">Jira</button>
            <button class="tab" data-connector="generic">HTTP proprietario</button>
          </div>

          <form class="connector-panel active" id="freshdesk-panel" data-config-key="freshdesk">
            <div class="form-grid">
              <label>Dominio Freshdesk
                <input name="domain" placeholder="sua-conta">
              </label>
              <label>API key
                <input name="apiKey" type="password" placeholder="Freshdesk API key">
              </label>
              <label class="full">Campos customizados
                <input name="customFields" value="sentiment_score,sentiment_label">
              </label>
              <label>Ticket ID
                <input name="ticketId" placeholder="Opcional">
              </label>
              <label>Quantidade
                <select name="limit">
                  <option value="10">Ultimos 10</option>
                  <option value="20">Ultimos 20</option>
                  <option value="50">Ultimos 50</option>
                  <option value="100">Ultimos 100</option>
                </select>
              </label>
            </div>
            <div class="actions">
              <button type="submit" class="primary">Salvar configuracao</button>
              <button type="button" class="secondary" id="freshdesk-fetch">Buscar e analisar</button>
              <button type="button" class="secondary" id="freshdesk-update">Analisar e atualizar</button>
              <button type="button" class="secondary" data-test-config="freshdesk">Validar campos</button>
            </div>
            <div class="toast" id="freshdesk-toast"></div>
            <div class="ticket-list" id="freshdesk-ticket-list"></div>
          </form>

          <form class="connector-panel" id="jira-panel" data-config-key="jira">
            <div class="form-grid">
              <label>URL do site
                <input name="siteUrl" placeholder="https://empresa.atlassian.net">
              </label>
              <label>Projeto
                <input name="projectKey" placeholder="SUP">
              </label>
              <label>Email
                <input name="email" type="email" placeholder="usuario@empresa.com">
              </label>
              <label>API token
                <input name="apiToken" type="password" placeholder="Atlassian API token">
              </label>
              <label class="full">Campo de destino
                <input name="sentimentField" placeholder="customfield_12345">
              </label>
            </div>
            <div class="actions">
              <button type="submit" class="primary">Salvar configuracao</button>
              <button type="button" class="secondary" data-test-config="jira">Validar campos</button>
            </div>
            <div class="toast" id="jira-toast"></div>
          </form>

          <form class="connector-panel" id="generic-panel" data-config-key="generic">
            <div class="form-grid">
              <label>URL base
                <input name="baseUrl" placeholder="https://tickets.empresa.com/api">
              </label>
              <label>Token bearer
                <input name="token" type="password" placeholder="Opcional">
              </label>
              <label>Endpoint de leitura
                <input name="getTicketPath" value="/tickets/{id}">
              </label>
              <label>Endpoint de atualizacao
                <input name="updateTicketPath" value="/tickets/{id}/sentiment">
              </label>
              <label>Campo de texto
                <input name="textField" value="description">
              </label>
              <label>Campo de assunto
                <input name="subjectField" value="subject">
              </label>
            </div>
            <div class="actions">
              <button type="submit" class="primary">Salvar configuracao</button>
              <button type="button" class="secondary" data-test-config="generic">Validar campos</button>
            </div>
            <div class="toast" id="generic-toast"></div>
          </form>
        </div>
      </section>

      <section class="view" id="training-view">
        <div class="panel">
          <div class="panel-header">
            <div>
              <h2>Palavras salvas para retreino</h2>
              <p id="training-summary">Carregando feedback salvo...</p>
            </div>
            <button class="secondary" id="refresh-training">Atualizar</button>
          </div>
          <div class="training-table" id="training-results"></div>
        </div>
      </section>
    </main>
  </div>
  <script>
    const text = document.getElementById('text');
    const button = document.getElementById('analyze');
    const clearButton = document.getElementById('clear-text');
    const clearBatchButton = document.getElementById('clear-batch');
    const meterFill = document.getElementById('meter-fill');
    const feedbackState = {
      currentTicket: null,
      currentSentiment: null,
      correctness: null,
      positiveWords: new Set(),
      negativeWords: new Set(),
      positiveTerms: new Map(),
      negativeTerms: new Map()
    };

    function setActiveView(view) {
      document.querySelectorAll('.nav-button').forEach((item) => {
        item.classList.toggle('active', item.dataset.view === view);
      });
      document.querySelectorAll('.view').forEach((item) => {
        item.classList.toggle('active', item.id === `${view}-view`);
      });
    }

    document.querySelectorAll('.nav-button').forEach((item) => {
      item.addEventListener('click', () => {
        setActiveView(item.dataset.view);
        if (item.dataset.view === 'training') {
          loadTrainingTerms();
        }
      });
    });

    async function loadConnectors() {
      const response = await fetch('/api/connectors');
      const connectors = await response.json();
      document.getElementById('connector-count').textContent = `${connectors.length} conectores configuraveis`;
      document.getElementById('connector-summary').innerHTML = connectors.map((connector) => `
        <div class="summary-item">
          <strong>${connector.name}</strong>
          <span>${connector.status === 'available' ? 'Disponivel' : 'Planejado'} - ${connector.fields.length} campos</span>
        </div>
      `).join('');
    }

    function updateResult(data) {
      const score = Number(data.score || 0);
      feedbackState.currentSentiment = data;
      document.getElementById('score').textContent = score.toFixed(2);
      document.getElementById('label').textContent = data.label || 'Neutro';
      document.getElementById('positive').textContent = (data.positive_matches || []).join(', ') || '-';
      document.getElementById('negative').textContent = (data.negative_matches || []).join(', ') || '-';
      document.getElementById('engine').textContent = data.engine || 'keyword';
      document.getElementById('model').textContent = data.model_label
        ? `${data.model_label}${data.confidence ? ` (${Math.round(data.confidence * 100)}%)` : ''}`
        : '-';
      document.getElementById('result-hint').textContent = 'Analise concluida.';
      document.getElementById('classification').textContent = score < 0 ? 'Atencao prioritaria' : 'Monitoramento normal';
      meterFill.style.width = `${Math.max(0, Math.min(100, (score + 1) * 50))}%`;
      meterFill.style.background = score < 0 ? '#b5473f' : score > 0 ? '#176b5b' : '#667782';
      resetFeedbackControls();
    }

    button.addEventListener('click', async () => {
      button.disabled = true;
      try {
        feedbackState.currentTicket = null;
        const response = await fetch('/api/analyze', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text: text.value })
        });
        updateResult(await response.json());
      } finally {
        button.disabled = false;
      }
    });

    clearButton.addEventListener('click', () => {
      text.value = '';
      updateResult({ score: 0, label: 'Neutro', positive_matches: [], negative_matches: [] });
      document.getElementById('result-hint').textContent = 'Aguardando texto para analise.';
    });

    document.querySelectorAll('.tab').forEach((tab) => {
      tab.addEventListener('click', () => {
        document.querySelectorAll('.tab').forEach((item) => item.classList.remove('active'));
        document.querySelectorAll('.connector-panel').forEach((item) => item.classList.remove('active'));
        tab.classList.add('active');
        document.getElementById(`${tab.dataset.connector}-panel`).classList.add('active');
      });
    });

    function formToObject(form) {
      return Object.fromEntries(new FormData(form).entries());
    }

    function fillForm(form, data) {
      Object.entries(data || {}).forEach(([key, value]) => {
        const field = form.elements.namedItem(key);
        if (field) field.value = value;
      });
    }

    document.querySelectorAll('.connector-panel').forEach((form) => {
      const key = form.dataset.configKey;
      fillForm(form, JSON.parse(localStorage.getItem(`connector:${key}`) || '{}'));
      form.addEventListener('submit', (event) => {
        event.preventDefault();
        localStorage.setItem(`connector:${key}`, JSON.stringify(formToObject(form)));
        document.getElementById(`${key}-toast`).textContent = 'Configuracao salva no navegador.';
      });
    });

    document.querySelectorAll('[data-test-config]').forEach((item) => {
      item.addEventListener('click', () => {
        const key = item.dataset.testConfig;
        const form = document.querySelector(`[data-config-key="${key}"]`);
        const values = formToObject(form);
        const missing = Object.entries(values).filter(([_, value]) => !String(value).trim()).map(([name]) => name);
        document.getElementById(`${key}-toast`).textContent = missing.length
          ? `Campos pendentes: ${missing.join(', ')}`
          : 'Campos obrigatorios preenchidos.';
      });
    });

    async function analyzeFreshdeskTicket(updateTicket) {
      const form = document.getElementById('freshdesk-panel');
      const values = formToObject(form);
      localStorage.setItem('connector:freshdesk', JSON.stringify(values));
      document.getElementById('freshdesk-toast').textContent = 'Buscando ticket no Freshdesk...';
      const response = await fetch('/api/freshdesk/ticket', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...values, update: updateTicket })
      });
      const data = await response.json();
      if (!response.ok) {
        document.getElementById('freshdesk-toast').textContent = data.error || 'Falha ao buscar ticket.';
        return;
      }
      if (data.tickets) {
        renderFreshdeskTickets(data.tickets);
        renderBatchTickets(data.tickets);
        renderCompanyAggregates(data.tickets);
      } else {
        const ticket = {
          id: data.ticket.id,
          subject: data.ticket.subject,
          status: data.ticket.status,
          priority: data.ticket.priority,
          company_id: data.ticket.company_id,
          company_name: data.ticket.company_name,
          analysis_text: data.ticket.analysis_text,
          sentiment: data.sentiment
        };
        renderFreshdeskTickets([ticket]);
        renderBatchTickets([ticket]);
        renderCompanyAggregates([ticket]);
        text.value = data.ticket.analysis_text;
        updateResult(data.sentiment);
      }
      setActiveView('analyzer');
      document.getElementById('freshdesk-toast').textContent = updateTicket
        ? 'Ticket analisado e atualizado no Freshdesk.'
        : 'Ticket analisado sem atualizar o Freshdesk.';
    }

    function renderFreshdeskTickets(tickets) {
      const container = document.getElementById('freshdesk-ticket-list');
      container.innerHTML = tickets.map((ticket, index) => `
        <div class="ticket-item">
          <div>
            <strong>#${ticket.id} ${ticket.subject || 'Sem assunto'}</strong>
            <span>${ticket.sentiment.label} - status ${ticket.status || '-'} - prioridade ${ticket.priority || '-'}</span>
          </div>
          <button type="button" class="secondary" data-load-ticket="${index}">${Number(ticket.sentiment.score || 0).toFixed(2)}</button>
        </div>
      `).join('');

      container.querySelectorAll('[data-load-ticket]').forEach((item) => {
        item.addEventListener('click', () => {
          const ticket = tickets[Number(item.dataset.loadTicket)];
          loadTicketIntoAnalyzer(ticket);
        });
      });
    }

    function renderBatchTickets(tickets) {
      const panel = document.getElementById('batch-panel');
      const container = document.getElementById('batch-results');
      document.getElementById('batch-summary').textContent = `${tickets.length} ticket(s) analisado(s) individualmente.`;
      panel.classList.add('active');
      container.innerHTML = tickets.map((ticket, index) => {
        const score = Number(ticket.sentiment.score || 0);
        const isNegative = score < 0;
        return `
          <div class="batch-ticket">
            <div>
              <strong>#${ticket.id} ${ticket.subject || 'Sem assunto'}</strong>
              <span>Status ${ticket.status || '-'} - prioridade ${ticket.priority || '-'} - motor ${ticket.sentiment.engine || '-'}</span>
            </div>
            <div class="sentiment-pill ${isNegative ? 'negative' : ''}">${ticket.sentiment.label} ${score.toFixed(2)}</div>
            <button type="button" class="secondary" data-batch-ticket="${index}">Ver texto</button>
          </div>
        `;
      }).join('');

      container.querySelectorAll('[data-batch-ticket]').forEach((item) => {
        item.addEventListener('click', () => {
          loadTicketIntoAnalyzer(tickets[Number(item.dataset.batchTicket)]);
        });
      });
    }

    function loadTicketIntoAnalyzer(ticket) {
      feedbackState.currentTicket = ticket;
      text.value = ticket.analysis_text;
      updateResult(ticket.sentiment);
      document.getElementById('result-hint').textContent = `Ticket #${ticket.id} carregado para revisao.`;
      setActiveView('analyzer');
    }

    function resetFeedbackControls() {
      feedbackState.correctness = null;
      feedbackState.positiveWords = new Set();
      feedbackState.negativeWords = new Set();
      feedbackState.positiveTerms = new Map();
      feedbackState.negativeTerms = new Map();
      document.getElementById('feedback-correct').classList.remove('active');
      document.getElementById('feedback-wrong').classList.remove('active');
      document.getElementById('word-labels').classList.remove('active');
      document.getElementById('feedback-chip-list').innerHTML = '';
      document.getElementById('feedback-status').textContent = '';
    }

    function tokenizeForFeedback(value) {
      const source = value || '';
      const matches = Array.from(source.matchAll(/[\\p{L}\\p{N}][\\p{L}\\p{N}._-]*/gu));
      return matches.map((match, index) => ({
        id: `${index}-${match.index}`,
        index,
        word: normalizeFeedbackWord(match[0]),
        start: match.index,
        end: match.index + match[0].length
      }));
    }

    function normalizeFeedbackWord(value) {
      return String(value || '').normalize('NFD')
        .replace(/[\u0300-\u036f]/g, '')
        .toLowerCase();
    }

    function renderWordChips() {
      const tokens = tokenizeForFeedback(text.value);
      const container = document.getElementById('feedback-chip-list');
      if (tokens.length === 0) {
        container.innerHTML = '<span class="feedback-status">Nenhuma palavra encontrada no texto atual.</span>';
        return;
      }
      container.innerHTML = renderClickableText(text.value, tokens);
      container.querySelectorAll('.polarity-button').forEach((chip) => {
        chip.addEventListener('click', () => toggleFeedbackWord(chip));
      });
    }

    function renderClickableText(originalText, tokens) {
      let html = '';
      let cursor = 0;
      tokens.forEach((token) => {
        html += escapeHtml(originalText.slice(cursor, token.start));
        html += `
          <span class="word-token" data-token-id="${token.id}">
            <span class="word-token-label">${escapeHtml(originalText.slice(token.start, token.end))}</span>
            <button type="button" class="polarity-button positive" data-token-id="${token.id}" data-token-index="${token.index}" data-word="${escapeHtml(token.word)}" data-polarity="positive">+</button>
            <button type="button" class="polarity-button negative" data-token-id="${token.id}" data-token-index="${token.index}" data-word="${escapeHtml(token.word)}" data-polarity="negative">-</button>
          </span>`;
        cursor = token.end;
      });
      html += escapeHtml(originalText.slice(cursor));
      return html;
    }

    function escapeHtml(value) {
      return String(value)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
    }

    function toggleFeedbackWord(button) {
      const word = button.dataset.word;
      const tokenId = button.dataset.tokenId;
      const tokenIndex = Number(button.dataset.tokenIndex || 0);
      const polarity = button.dataset.polarity;
      const isActive = button.classList.contains('active');
      const tokenButtons = document.querySelectorAll(`.polarity-button[data-token-id="${tokenId}"]`);

      feedbackState.positiveTerms.delete(tokenId);
      feedbackState.negativeTerms.delete(tokenId);
      tokenButtons.forEach((item) => item.classList.remove('active'));

      if (!isActive && polarity === 'positive') {
        feedbackState.positiveTerms.set(tokenId, { word, index: tokenIndex });
        button.classList.add('active');
      }
      if (!isActive && polarity === 'negative') {
        feedbackState.negativeTerms.set(tokenId, { word, index: tokenIndex });
        button.classList.add('active');
      }

      syncFeedbackWordSets();
    }

    function syncFeedbackWordSets() {
      feedbackState.positiveWords = new Set(
        Array.from(feedbackState.positiveTerms.values()).map((term) => term.word)
      );
      feedbackState.negativeWords = new Set(
        Array.from(feedbackState.negativeTerms.values()).map((term) => term.word)
      );
    }

    function renderCompanyAggregates(tickets) {
      const panel = document.getElementById('company-panel');
      const container = document.getElementById('company-results');
      const groups = new Map();

      tickets.forEach((ticket) => {
        const key = ticket.company_id || ticket.company_name || 'sem_empresa';
        const name = ticket.company_name || (ticket.company_id ? `Empresa ${ticket.company_id}` : 'Sem empresa');
        if (!groups.has(key)) {
          groups.set(key, { name, scores: [], count: 0 });
        }
        const group = groups.get(key);
        group.scores.push(Number(ticket.sentiment.score || 0));
        group.count += 1;
      });

      const aggregates = Array.from(groups.values()).map((group) => {
        const average = group.scores.reduce((total, score) => total + score, 0) / group.scores.length;
        return { ...group, average };
      }).sort((a, b) => a.average - b.average);

      document.getElementById('company-summary').textContent = `${aggregates.length} empresa(s) com sentimento medio calculado.`;
      panel.classList.add('active');
      container.innerHTML = aggregates.map((group) => `
        <div class="company-aggregate">
          <div>
            <strong>${group.name}</strong>
            <span>${group.count} ticket(s) analisado(s)</span>
          </div>
          <div class="sentiment-pill ${group.average < 0 ? 'negative' : ''}">${getScoreLabel(group.average)}</div>
          <div class="ticket-score">${group.average.toFixed(2)}</div>
        </div>
      `).join('');
    }

    function getScoreLabel(score) {
      if (score > 0.5) return 'Altamente Positivo';
      if (score > 0) return 'Positivo';
      if (score === 0) return 'Neutro';
      if (score > -0.5) return 'Negativo';
      return 'Altamente Negativo';
    }

    clearBatchButton.addEventListener('click', () => {
      document.getElementById('batch-results').innerHTML = '';
      document.getElementById('company-results').innerHTML = '';
      document.getElementById('batch-summary').textContent = 'Cada ticket e analisado separadamente.';
      document.getElementById('batch-panel').classList.remove('active');
      document.getElementById('company-panel').classList.remove('active');
    });

    document.getElementById('feedback-correct').addEventListener('click', () => {
      feedbackState.correctness = true;
      document.getElementById('feedback-correct').classList.add('active');
      document.getElementById('feedback-wrong').classList.remove('active');
      document.getElementById('word-labels').classList.remove('active');
    });

    document.getElementById('feedback-wrong').addEventListener('click', () => {
      feedbackState.correctness = false;
      document.getElementById('feedback-wrong').classList.add('active');
      document.getElementById('feedback-correct').classList.remove('active');
      document.getElementById('word-labels').classList.add('active');
      renderWordChips();
    });

    document.getElementById('save-feedback').addEventListener('click', async () => {
      if (feedbackState.correctness === null) {
        document.getElementById('feedback-status').textContent = 'Marque se a analise esta certa ou errada.';
        return;
      }

      const response = await fetch('/api/feedback', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          source: feedbackState.currentTicket ? 'freshdesk' : 'manual',
          ticket: feedbackState.currentTicket,
          text: text.value,
          sentiment: feedbackState.currentSentiment,
          is_correct: feedbackState.correctness,
          positive_words: Array.from(feedbackState.positiveWords),
          negative_words: Array.from(feedbackState.negativeWords),
          positive_terms: Array.from(feedbackState.positiveTerms.values()),
          negative_terms: Array.from(feedbackState.negativeTerms.values())
        })
      });
      const data = await response.json();
      document.getElementById('feedback-status').textContent = response.ok
        ? `Feedback salvo para retreino (${data.count} registro(s)).`
        : data.error || 'Falha ao salvar feedback.';
      if (response.ok) {
        loadTrainingTerms();
      }
    });

    async function loadTrainingTerms() {
      const response = await fetch('/api/retraining/terms');
      const data = await response.json();
      const container = document.getElementById('training-results');
      document.getElementById('training-summary').textContent =
        `${data.words.length} palavra(s), ${data.records} feedback(s), armazenamento: ${data.storage}.`;

      if (data.words.length === 0) {
        container.innerHTML = '<div class="feedback-status">Nenhuma palavra salva ainda.</div>';
        return;
      }

      container.innerHTML = `
        <div class="training-row header">
          <div>Palavra</div>
          <div>Positiva</div>
          <div>Negativa</div>
          <div>Total</div>
        </div>
        ${data.words.map((item) => `
          <div class="training-row">
            <div class="training-word">${escapeHtml(item.word)}</div>
            <div>${item.positive}</div>
            <div>${item.negative}</div>
            <div>${item.total}</div>
            <div class="training-examples">
              ${item.examples.map((example) => `${example.label}: ${escapeHtml(example.text)}`).join('<br>')}
            </div>
          </div>
        `).join('')}
      `;
    }

    document.getElementById('refresh-training').addEventListener('click', loadTrainingTerms);

    document.getElementById('freshdesk-fetch').addEventListener('click', () => analyzeFreshdeskTicket(false));
    document.getElementById('freshdesk-update').addEventListener('click', () => analyzeFreshdeskTicket(true));

    loadConnectors();
  </script>
</body>
</html>
"""


class SentimentRequestHandler(BaseHTTPRequestHandler):
    analyzer = create_default_analyzer()

    def do_GET(self) -> None:
        if self.path == "/":
            self._send(200, INDEX_HTML.encode("utf-8"), "text/html; charset=utf-8")
            return
        if self.path == "/api/connectors":
            self._send_json(200, CONNECTORS)
            return
        if self.path == "/api/retraining/terms":
            self._send_json(200, FEEDBACK_STORE.term_summary())
            return
        self.send_error(404)

    def do_POST(self) -> None:
        if self.path == "/api/analyze":
            self._handle_analyze()
            return
        if self.path == "/api/freshdesk/ticket":
            self._handle_freshdesk_ticket()
            return
        if self.path == "/api/feedback":
            self._handle_feedback()
            return
        self.send_error(404)

    def _handle_analyze(self) -> None:
        payload = self._read_json_body()
        if payload is None:
            return

        sentiment = self.analyzer.analyze(str(payload.get("text", "")))
        self._send_sentiment(sentiment)

    def _handle_freshdesk_ticket(self) -> None:
        payload = self._read_json_body()
        if payload is None:
            return

        domain = str(payload.get("domain", "")).strip()
        api_key = str(payload.get("apiKey", "")).strip()
        ticket_id = str(payload.get("ticketId", "")).strip()
        limit = int(payload.get("limit") or 10)
        should_update = bool(payload.get("update"))

        if limit not in {10, 20, 50, 100}:
            limit = 10

        if not domain or not api_key:
            self._send_json(
                400,
                {"error": "Preencha dominio e API key do Freshdesk."},
            )
            return

        try:
            connector = FreshdeskConnector(domain=domain, api_key=api_key)
            if ticket_id:
                ticket = connector.get_ticket(ticket_id)
                sentiment = self.analyzer.analyze(ticket.analysis_text)
                if should_update:
                    connector.update_ticket_sentiment(ticket.id, sentiment)
                self._send_json(
                    200,
                    {
                        "ticket": self._ticket_payload(ticket),
                        "sentiment": self._sentiment_payload(sentiment),
                        "updated": should_update,
                    },
                )
                return

            tickets = connector.list_tickets(limit)
            analyzed_tickets = []
            for ticket in tickets:
                sentiment = self.analyzer.analyze(ticket.analysis_text)
                if should_update:
                    connector.update_ticket_sentiment(ticket.id, sentiment)
                analyzed_tickets.append(
                    {
                        **self._ticket_payload(ticket),
                        "sentiment": self._sentiment_payload(sentiment),
                    }
                )
        except Exception as exc:
            self._send_json(502, {"error": str(exc)})
            return

        self._send_json(
            200,
            {
                "tickets": analyzed_tickets,
                "updated": should_update,
            },
        )

    def _handle_feedback(self) -> None:
        payload = self._read_json_body()
        if payload is None:
            return

        text = str(payload.get("text", "")).strip()
        if not text:
            self._send_json(400, {"error": "Feedback sem texto analisado."})
            return
        if "is_correct" not in payload:
            self._send_json(400, {"error": "Informe se a analise esta certa."})
            return

        record = {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "source": payload.get("source", "manual"),
            "ticket": payload.get("ticket"),
            "text": text,
            "sentiment": payload.get("sentiment"),
            "is_correct": bool(payload.get("is_correct")),
            "positive_words": self._clean_word_list(payload.get("positive_words", [])),
            "negative_words": self._clean_word_list(payload.get("negative_words", [])),
            "positive_terms": self._clean_term_list(payload.get("positive_terms", [])),
            "negative_terms": self._clean_term_list(payload.get("negative_terms", [])),
        }

        self._send_json(200, {"count": FEEDBACK_STORE.save(record)})

    def _clean_word_list(self, words: object) -> list[str]:
        if not isinstance(words, list):
            return []
        cleaned_words = []
        for word in words:
            normalized = re.sub(r"[^0-9a-zA-ZÀ-ÿ_-]", "", str(word).strip().lower())
            if normalized and normalized not in cleaned_words:
                cleaned_words.append(normalized)
        return cleaned_words

    def _clean_term_list(self, terms: object) -> list[dict]:
        if not isinstance(terms, list):
            return []
        cleaned_terms = []
        for term in terms:
            if not isinstance(term, dict):
                continue
            word = re.sub(
                r"[^0-9a-zA-ZÀ-ÿ_.-]",
                "",
                str(term.get("word", "")).strip().lower(),
            )
            if not word:
                continue
            cleaned_terms.append(
                {
                    "word": word,
                    "index": int(term.get("index", 0) or 0),
                }
            )
        return cleaned_terms

    def _ticket_payload(self, ticket) -> dict:
        return {
            "id": ticket.id,
            "subject": ticket.subject,
            "status": ticket.status,
            "priority": ticket.priority,
            "company_id": ticket.company_id,
            "company_name": ticket.company_name,
            "analysis_text": ticket.analysis_text,
        }

    def _read_json_body(self) -> dict | None:
        content_length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(content_length)
        try:
            payload = json.loads(raw_body or b"{}")
        except json.JSONDecodeError:
            self.send_error(400, "Invalid JSON")
            return None
        return payload

    def _send_sentiment(self, sentiment) -> None:
        self._send_json(200, self._sentiment_payload(sentiment))

    def _sentiment_payload(self, sentiment) -> dict:
        return {
            "score": sentiment.score,
            "label": sentiment.label,
            "positive_matches": sentiment.positive_matches,
            "negative_matches": sentiment.negative_matches,
            "engine": sentiment.engine,
            "confidence": sentiment.confidence,
            "model_label": sentiment.model_label,
        }

    def log_message(self, format: str, *args: object) -> None:
        print(f"{self.address_string()} - {format % args}")

    def _send_json(self, status: int, payload: object) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self._send(status, body, "application/json; charset=utf-8")

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), SentimentRequestHandler)
    print(f"Server running at http://{HOST}:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
