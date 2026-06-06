import unittest

from sentiment_ticketing.connectors.base import TicketConnector
from sentiment_ticketing.core.models import SentimentResult, Ticket
from sentiment_ticketing.core.sentiment_analyzer import (
    HybridTicketSentimentAnalyzer,
    KeywordSentimentAnalyzer,
)
from sentiment_ticketing.pipeline import TicketSentimentPipeline


class FakeConnector(TicketConnector):
    def __init__(self):
        self.updated_ticket_id = None
        self.updated_sentiment = None

    def get_ticket(self, ticket_id):
        return Ticket(
            id=str(ticket_id),
            subject="Erro no sistema",
            description="Cliente insatisfeito com problema recorrente.",
            source="fake",
        )

    def update_ticket_sentiment(self, ticket_id, sentiment):
        self.updated_ticket_id = ticket_id
        self.updated_sentiment = sentiment


class KeywordSentimentAnalyzerTest(unittest.TestCase):
    def test_analyze_negative_text_with_accents(self):
        analyzer = KeywordSentimentAnalyzer()

        sentiment = analyzer.analyze("Servico péssimo, erro horrível e problema aberto.")

        self.assertLess(sentiment.score, 0)
        self.assertEqual(sentiment.label, "Altamente Negativo")
        self.assertIn("pessimo", sentiment.negative_matches)
        self.assertIn("erro", sentiment.negative_matches)

    def test_analyze_matches_whole_words(self):
        analyzer = KeywordSentimentAnalyzer(positive_words=["bom"], negative_words=[])

        sentiment = analyzer.analyze("bombom nao deve contar. bom deve contar.")

        self.assertEqual(sentiment.positive_matches, ["bom"])

    def test_analyze_negated_positive_word_as_negative(self):
        analyzer = KeywordSentimentAnalyzer()

        sentiment = analyzer.analyze("Nao estou feliz com o suporte.")

        self.assertLess(sentiment.score, 0)
        self.assertIn("nao feliz", sentiment.negative_matches)


class FakeModelAnalyzer:
    def analyze(self, text):
        return SentimentResult(
            score=0.9,
            label="Altamente Positivo",
            engine="sklearn_joblib",
            confidence=0.9,
            model_label="Positivo",
        )


class HybridTicketSentimentAnalyzerTest(unittest.TestCase):
    def test_hybrid_keeps_support_keywords_as_stronger_signal(self):
        analyzer = HybridTicketSentimentAnalyzer(
            model_analyzer=FakeModelAnalyzer(),
            keyword_weight=0.65,
        )

        sentiment = analyzer.analyze("Cliente insatisfeito com erro horrivel.")

        self.assertLess(sentiment.score, 0)
        self.assertEqual(sentiment.engine, "hybrid_leia_ml")
        self.assertIn("Positivo", sentiment.model_label)
        self.assertIn("erro", sentiment.negative_matches)


class TicketSentimentPipelineTest(unittest.TestCase):
    def test_pipeline_gets_ticket_analyzes_and_updates_connector(self):
        connector = FakeConnector()
        pipeline = TicketSentimentPipeline(connector)

        sentiment = pipeline.analyze_and_update("42")

        self.assertIsInstance(sentiment, SentimentResult)
        self.assertEqual(connector.updated_ticket_id, "42")
        self.assertEqual(connector.updated_sentiment, sentiment)
        self.assertLess(sentiment.score, 0)


if __name__ == "__main__":
    unittest.main()
