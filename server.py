import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from sentiment_ticketing.core.sentiment_analyzer import KeywordSentimentAnalyzer


HOST = "127.0.0.1"
PORT = 8000


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
      background: #f5f7f8;
      color: #1f2933;
    }
    body {
      margin: 0;
      min-height: 100vh;
      display: grid;
      place-items: center;
      padding: 24px;
    }
    main {
      width: min(720px, 100%);
      background: #ffffff;
      border: 1px solid #d9e1e7;
      border-radius: 8px;
      padding: 24px;
      box-shadow: 0 12px 32px rgba(31, 41, 51, 0.08);
    }
    h1 {
      margin: 0 0 16px;
      font-size: 24px;
      font-weight: 700;
      letter-spacing: 0;
    }
    textarea {
      box-sizing: border-box;
      width: 100%;
      min-height: 180px;
      resize: vertical;
      border: 1px solid #b8c4ce;
      border-radius: 6px;
      padding: 12px;
      font: inherit;
    }
    button {
      margin-top: 12px;
      border: 0;
      border-radius: 6px;
      background: #176b5b;
      color: #ffffff;
      font: inherit;
      font-weight: 700;
      padding: 10px 16px;
      cursor: pointer;
    }
    button:disabled {
      cursor: not-allowed;
      opacity: 0.6;
    }
    section {
      margin-top: 18px;
      padding: 14px;
      border-radius: 6px;
      background: #eef4f2;
      border: 1px solid #c9dbd6;
      display: none;
    }
    dl {
      display: grid;
      grid-template-columns: max-content 1fr;
      gap: 8px 12px;
      margin: 0;
    }
    dt {
      font-weight: 700;
    }
    dd {
      margin: 0;
    }
  </style>
</head>
<body>
  <main>
    <h1>Analise de Sentimentos</h1>
    <textarea id="text" placeholder="Cole aqui o texto do ticket..."></textarea>
    <button id="analyze">Analisar</button>
    <section id="result">
      <dl>
        <dt>Sentimento</dt><dd id="label"></dd>
        <dt>Pontuacao</dt><dd id="score"></dd>
        <dt>Positivas</dt><dd id="positive"></dd>
        <dt>Negativas</dt><dd id="negative"></dd>
      </dl>
    </section>
  </main>
  <script>
    const text = document.getElementById('text');
    const button = document.getElementById('analyze');
    const result = document.getElementById('result');

    button.addEventListener('click', async () => {
      button.disabled = true;
      try {
        const response = await fetch('/api/analyze', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text: text.value })
        });
        const data = await response.json();
        document.getElementById('label').textContent = data.label;
        document.getElementById('score').textContent = data.score.toFixed(2);
        document.getElementById('positive').textContent = data.positive_matches.join(', ') || '-';
        document.getElementById('negative').textContent = data.negative_matches.join(', ') || '-';
        result.style.display = 'block';
      } finally {
        button.disabled = false;
      }
    });
  </script>
</body>
</html>
"""


class SentimentRequestHandler(BaseHTTPRequestHandler):
    analyzer = KeywordSentimentAnalyzer()

    def do_GET(self) -> None:
        if self.path != "/":
            self.send_error(404)
            return
        self._send(200, INDEX_HTML.encode("utf-8"), "text/html; charset=utf-8")

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
        body = json.dumps(
            {
                "score": sentiment.score,
                "label": sentiment.label,
                "positive_matches": sentiment.positive_matches,
                "negative_matches": sentiment.negative_matches,
            },
            ensure_ascii=False,
        ).encode("utf-8")
        self._send(200, body, "application/json; charset=utf-8")

    def log_message(self, format: str, *args: object) -> None:
        print(f"{self.address_string()} - {format % args}")

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
