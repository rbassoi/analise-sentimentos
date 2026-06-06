import argparse
import json
import os

from sentiment_ticketing.connectors import FreshdeskConnector
from sentiment_ticketing.pipeline import TicketSentimentPipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Analyze and update sentiment metadata for a Freshdesk ticket.",
    )
    parser.add_argument("ticket_id", help="Freshdesk ticket ID to analyze.")
    parser.add_argument(
        "--domain",
        default=os.getenv("FRESHDESK_DOMAIN"),
        help="Freshdesk account subdomain. Can also be set with FRESHDESK_DOMAIN.",
    )
    parser.add_argument(
        "--api-key",
        default=os.getenv("FRESHDESK_API_KEY"),
        help="Freshdesk API key. Can also be set with FRESHDESK_API_KEY.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()

    if not args.domain or not args.api_key:
        raise SystemExit(
            "Missing Freshdesk credentials. Set FRESHDESK_DOMAIN and "
            "FRESHDESK_API_KEY or pass --domain and --api-key."
        )

    connector = FreshdeskConnector(domain=args.domain, api_key=args.api_key)
    pipeline = TicketSentimentPipeline(connector=connector)
    sentiment = pipeline.analyze_and_update(args.ticket_id)

    print(
        json.dumps(
            {
                "ticket_id": args.ticket_id,
                "score": sentiment.score,
                "label": sentiment.label,
                "positive_matches": sentiment.positive_matches,
                "negative_matches": sentiment.negative_matches,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
