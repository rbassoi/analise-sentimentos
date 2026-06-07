from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Iterable

from .sentiment_analyzer import KeywordSentimentAnalyzer


DEFAULT_MODEL_PATH = Path("models") / "sentiment-feedback.joblib"


def train_feedback_model(
    records: Iterable[dict],
    model_path: str | Path = DEFAULT_MODEL_PATH,
) -> dict:
    try:
        from joblib import dump
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.linear_model import LogisticRegression
        from sklearn.pipeline import Pipeline
    except ImportError as exc:
        raise RuntimeError(
            "Instale as dependencias com: pip install -r requirements.txt"
        ) from exc

    examples = build_training_examples(records)
    labels = sorted({label for _, label in examples})
    if len(labels) < 2:
        raise ValueError(
            "E preciso feedback com pelo menos duas classes para retreinar."
        )

    texts = [text for text, _ in examples]
    y = [label for _, label in examples]

    pipeline = Pipeline(
        steps=[
            (
                "vectorizer",
                TfidfVectorizer(
                    strip_accents="unicode",
                    lowercase=True,
                    ngram_range=(1, 2),
                    min_df=1,
                    max_features=12000,
                ),
            ),
            (
                "model",
                LogisticRegression(
                    class_weight="balanced",
                    max_iter=1000,
                    random_state=42,
                ),
            ),
        ]
    )
    pipeline.fit(texts, y)

    path = Path(model_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    dump(pipeline, path)

    counts = Counter(y)
    return {
        "model_path": str(path.resolve()),
        "examples": len(examples),
        "labels": dict(counts),
    }


def build_training_examples(records: Iterable[dict]) -> list[tuple[str, str]]:
    examples = _seed_examples()

    for record in records:
        text = str(record.get("text", "")).strip()
        positive_terms = _terms(record.get("positive_terms"))
        negative_terms = _terms(record.get("negative_terms"))

        for word in positive_terms:
            _add_weighted_example(examples, word, "Positivo", 5)
        for word in negative_terms:
            _add_weighted_example(examples, word, "Negativo", 5)

        if text and positive_terms and len(positive_terms) >= len(negative_terms):
            _add_weighted_example(examples, text, "Positivo", 2)
        elif text and negative_terms:
            _add_weighted_example(examples, text, "Negativo", 2)
        elif text and bool(record.get("is_correct")):
            label = _label_from_sentiment(record.get("sentiment"))
            if label:
                _add_weighted_example(examples, text, label, 1)

    return examples


def _seed_examples() -> list[tuple[str, str]]:
    analyzer = KeywordSentimentAnalyzer()
    examples: list[tuple[str, str]] = []
    for word in analyzer.positive_words:
        examples.append((word, "Positivo"))
        examples.append((f"ticket {word}", "Positivo"))
    for word in analyzer.negative_words:
        examples.append((word, "Negativo"))
        examples.append((f"ticket {word}", "Negativo"))
    for text in [
        "solicitacao recebida",
        "atualizacao de cadastro",
        "informacao do chamado",
        "sem avaliacao de sentimento",
        "aguardando retorno",
    ]:
        examples.append((text, "Neutro"))
    return examples


def _terms(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    words = []
    for item in value:
        if isinstance(item, dict):
            word = str(item.get("word", "")).strip().lower()
        else:
            word = str(item).strip().lower()
        if word:
            words.append(word)
    return words


def _label_from_sentiment(sentiment: object) -> str | None:
    if not isinstance(sentiment, dict):
        return None
    value = str(sentiment.get("model_label") or sentiment.get("label") or "").lower()
    if "neg" in value:
        return "Negativo"
    if "pos" in value:
        return "Positivo"
    if "neut" in value:
        return "Neutro"
    return None


def _add_weighted_example(
    examples: list[tuple[str, str]],
    text: str,
    label: str,
    weight: int,
) -> None:
    for _ in range(max(1, weight)):
        examples.append((text, label))
