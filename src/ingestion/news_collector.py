"""News & Financial Research Collector.

Ingests published journalism and research analyses covering:
- SIP discontinuation trends in India
- Retail mutual fund retention challenges
- Bank ECS/NACH bounce fees impact
- Market volatility reactions and behavioral finance
"""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional

from src.ingestion.base import BaseIngestor

logger = logging.getLogger("ai_discovery_engine.news")

MOCK_NEWS_ARTICLES: List[Dict[str, Any]] = [
    {
        "publisher": "Livemint",
        "title": "Why Indian retail investors discontinue mutual fund SIPs within a year",
        "url": "https://www.livemint.com/mutual-funds/why-first-time-investors-quit-sips-within-a-year-groww-zerodha",
        "text": "Analysis across top discount brokers indicates that nearly 50% of first-time SIP investors stop recurring contributions before month 12. Financial planners highlight a persistent mismatch between fixed SIP debit dates and volatile salary disbursements among young private-sector employees.",
        "date": "2026-06-22",
    },
    {
        "publisher": "The Economic Times",
        "title": "Bank bounce charges on failed SIP debits prompt customer backlash",
        "url": "https://economictimes.indiatimes.com/wealth/invest/bank-bounce-charges-eating-into-mutual-fund-returns/articleshow/108923.cms",
        "text": "Retail investors are expressing frustration over aggressive ₹295 to ₹500 bounce fees levied by commercial banks when automated mutual fund debits fail. In many instances, novice investors cancel their investment mandates immediately following their first penalty charge.",
        "date": "2026-07-14",
    },
    {
        "publisher": "CNBC-TV18",
        "title": "Fintech platforms introduce flexible SIP tools to improve 12-month retention",
        "url": "https://www.cnbctv18.com/fintech/fintechs-simplify-sip-pause-and-step-up-to-boost-retention-123456.htm",
        "text": "In response to high 12-month attrition, digital brokers are rolling out Smart Buffer reminders, dynamic debit-date realignment, and simplified pause options to give investors breathing room during months with tight cash flows.",
        "date": "2026-10-15",
    },
]


class NewsCollector(BaseIngestor):
    """Ingestor connector for financial news articles and industry research."""

    def __init__(self):
        super().__init__(source_type="news", platform="News")

    def fetch(self, query_or_params: Optional[Any] = None) -> List[Dict[str, Any]]:
        """Collects financial news and market research publications.

        Args:
            query_or_params: Optional custom articles list or filter query.

        Returns:
            List of normalized candidate record dictionaries.
        """
        if isinstance(query_or_params, dict) and "articles" in query_or_params:
            return self._normalize_custom_articles(query_or_params["articles"])

        results: List[Dict[str, Any]] = []
        for article in MOCK_NEWS_ARTICLES:
            full_text = f"{article['title']} ({article['publisher']})\n\n{article['text']}"
            results.append({
                "source_type": self.source_type,
                "platform": "News",
                "source_url": article["url"],
                "title": f"{article['title']} - {article['publisher']}",
                "raw_text": full_text,
                "publication_date": article["date"],
                "rating": None,
                "is_synthetic_demo": True,
                "relevance_status": "highly_relevant",
            })

        return results

    def _normalize_custom_articles(self, articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Normalizes external article dictionaries."""
        results: List[Dict[str, Any]] = []
        for art in articles:
            title = art.get("title", "")
            text = art.get("text") or art.get("body", "")
            full_text = f"{title}\n\n{text}".strip() if title else text.strip()

            results.append({
                "source_type": self.source_type,
                "platform": art.get("platform", "News"),
                "source_url": art.get("url") or art.get("source_url"),
                "title": title,
                "raw_text": full_text,
                "publication_date": art.get("date", datetime.now(timezone.utc).strftime("%Y-%m-%d")),
                "rating": None,
                "is_synthetic_demo": art.get("is_synthetic_demo", False),
                "relevance_status": art.get("relevance_status", "highly_relevant"),
            })
        return results

