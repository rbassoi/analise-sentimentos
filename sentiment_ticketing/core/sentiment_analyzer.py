import os
import re
import unicodedata
import warnings
from pathlib import Path
from typing import Protocol

from .models import SentimentResult


class SentimentAnalyzer(Protocol):
    def analyze(self, text: str) -> SentimentResult:
        ...


class KeywordSentimentAnalyzer:
    def __init__(
        self,
        positive_words: list[str] | None = None,
        negative_words: list[str] | None = None,
    ):
        self.positive_words = positive_words or [
            "bom",
            "otimo",
            "excelente",
            "maravilhoso",
            "incrivel",
            "feliz",
            "fantastico",
            "perfeito",
            "resolvido",
            "satisfeito",
        ]
        self.negative_words = negative_words or [
            "ruim",
            "pessimo",
            "horrivel",
            "terrivel",
            "frustrado",
            "raiva",
            "problema",
            "erro",
            "falha",
            "insatisfeito",
        ]

    def analyze(self, text: str) -> SentimentResult:
        normalized_text = self._normalize(text)
        positive_matches = self._find_words(normalized_text, self.positive_words)
        negative_matches = self._find_words(normalized_text, self.negative_words)

        positive_count = len(positive_matches)
        negative_count = len(negative_matches)
        score = (positive_count - negative_count) / (positive_count + negative_count + 1)

        return SentimentResult(
            score=score,
            label=self._get_sentiment_label(score),
            positive_matches=positive_matches,
            negative_matches=negative_matches,
            engine="keyword",
        )

    def _find_words(self, normalized_text: str, words: list[str]) -> list[str]:
        matches: list[str] = []
        for word in words:
            normalized_word = self._normalize(word)
            if re.search(rf"\b{re.escape(normalized_word)}\b", normalized_text):
                matches.append(word)
        return matches

    def _normalize(self, text: str) -> str:
        without_accents = unicodedata.normalize("NFKD", text or "")
        ascii_text = without_accents.encode("ascii", "ignore").decode("ascii")
        return ascii_text.lower()

    def _get_sentiment_label(self, score: float) -> str:
        if score > 0.5:
            return "Altamente Positivo"
        if score > 0:
            return "Positivo"
        if score == 0:
            return "Neutro"
        if score > -0.5:
            return "Negativo"
        return "Altamente Negativo"


class SklearnJoblibSentimentAnalyzer:
    def __init__(self, model_path: str | Path):
        try:
            from joblib import load as load_joblib
        except ImportError as exc:
            raise RuntimeError(
                "joblib is required to use SklearnJoblibSentimentAnalyzer."
            ) from exc

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            self.pipeline = load_joblib(model_path)

    def analyze(self, text: str) -> SentimentResult:
        vectorizer = self.pipeline.named_steps["vectorizer"]
        model = self.pipeline.named_steps["model"]
        vector = vectorizer.transform([text or ""])
        model_label = str(model.predict(vector)[0])
        confidence = self._confidence(model, vector)
        score = self._score_from_label(model_label, confidence)

        return SentimentResult(
            score=score,
            label=self._ticket_label(score),
            engine="sklearn_joblib",
            confidence=confidence,
            model_label=model_label,
        )

    def _confidence(self, model, vector) -> float | None:
        if not hasattr(model, "predict_proba"):
            return None
        probabilities = model.predict_proba(vector)[0]
        return float(max(probabilities))

    def _score_from_label(self, label: str, confidence: float | None) -> float:
        confidence_score = confidence if confidence is not None else 0.65
        normalized_label = label.lower()
        if normalized_label.startswith("pos"):
            return confidence_score
        if normalized_label.startswith("neg"):
            return -confidence_score
        return 0.0

    def _ticket_label(self, score: float) -> str:
        return KeywordSentimentAnalyzer()._get_sentiment_label(score)


class HybridTicketSentimentAnalyzer:
    def __init__(
        self,
        keyword_analyzer: KeywordSentimentAnalyzer | None = None,
        model_analyzer: SklearnJoblibSentimentAnalyzer | None = None,
        keyword_weight: float = 0.65,
    ):
        self.keyword_analyzer = keyword_analyzer or KeywordSentimentAnalyzer()
        self.model_analyzer = model_analyzer
        self.keyword_weight = keyword_weight

    def analyze(self, text: str) -> SentimentResult:
        keyword_result = self.keyword_analyzer.analyze(text)
        if self.model_analyzer is None:
            return keyword_result

        model_result = self.model_analyzer.analyze(text)
        model_weight = 1 - self.keyword_weight
        score = (keyword_result.score * self.keyword_weight) + (
            model_result.score * model_weight
        )

        return SentimentResult(
            score=score,
            label=self.keyword_analyzer._get_sentiment_label(score),
            positive_matches=keyword_result.positive_matches,
            negative_matches=keyword_result.negative_matches,
            engine="hybrid",
            confidence=model_result.confidence,
            model_label=model_result.model_label,
        )


def create_default_analyzer() -> SentimentAnalyzer:
    model_path = os.getenv("SENTIMENT_MODEL_PATH")
    if not model_path:
        return HybridTicketSentimentAnalyzer()

    path = Path(model_path)
    if not path.exists():
        raise FileNotFoundError(f"SENTIMENT_MODEL_PATH does not exist: {path}")

    return HybridTicketSentimentAnalyzer(
        model_analyzer=SklearnJoblibSentimentAnalyzer(path),
    )
