import re
import unicodedata

from .models import SentimentResult


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
