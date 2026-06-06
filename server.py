import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from sentiment_ticketing.core.sentiment_analyzer import create_default_analyzer


HOST = "127.0.0.1"
PORT = 8000


CONNECTORS = [
    {
        "id": "freshdesk",
        "name": "Freshdesk",
        "status": "available",
        "fields": ["domain", "apiKey"],
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
          </div>
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
            </div>
            <div class="actions">
              <button type="submit" class="primary">Salvar configuracao</button>
              <button type="button" class="secondary" data-test-config="freshdesk">Validar campos</button>
            </div>
            <div class="toast" id="freshdesk-toast"></div>
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
    </main>
  </div>
  <script>
    const text = document.getElementById('text');
    const button = document.getElementById('analyze');
    const clearButton = document.getElementById('clear-text');
    const meterFill = document.getElementById('meter-fill');

    function setActiveView(view) {
      document.querySelectorAll('.nav-button').forEach((item) => {
        item.classList.toggle('active', item.dataset.view === view);
      });
      document.querySelectorAll('.view').forEach((item) => {
        item.classList.toggle('active', item.id === `${view}-view`);
      });
    }

    document.querySelectorAll('.nav-button').forEach((item) => {
      item.addEventListener('click', () => setActiveView(item.dataset.view));
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
      document.getElementById('score').textContent = score.toFixed(2);
      document.getElementById('label').textContent = data.label;
      document.getElementById('positive').textContent = data.positive_matches.join(', ') || '-';
      document.getElementById('negative').textContent = data.negative_matches.join(', ') || '-';
      document.getElementById('engine').textContent = data.engine || 'keyword';
      document.getElementById('model').textContent = data.model_label
        ? `${data.model_label}${data.confidence ? ` (${Math.round(data.confidence * 100)}%)` : ''}`
        : '-';
      document.getElementById('result-hint').textContent = 'Analise concluida.';
      document.getElementById('classification').textContent = score < 0 ? 'Atencao prioritaria' : 'Monitoramento normal';
      meterFill.style.width = `${Math.max(0, Math.min(100, (score + 1) * 50))}%`;
      meterFill.style.background = score < 0 ? '#b5473f' : score > 0 ? '#176b5b' : '#667782';
    }

    button.addEventListener('click', async () => {
      button.disabled = true;
      try {
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
        self.send_error(404)

    def do_POST(self) -> None:
        if self.path != "/api/analyze":
            self.send_error(404)
            return

        content_length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(content_length)
        try:
            payload = json.loads(raw_body or b"{}")
        except json.JSONDecodeError:
            self.send_error(400, "Invalid JSON")
            return

        sentiment = self.analyzer.analyze(str(payload.get("text", "")))
        self._send_json(
            200,
            {
                "score": sentiment.score,
                "label": sentiment.label,
                "positive_matches": sentiment.positive_matches,
                "negative_matches": sentiment.negative_matches,
                "engine": sentiment.engine,
                "confidence": sentiment.confidence,
                "model_label": sentiment.model_label,
            },
        )

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
