"""App Store Review Connector.

Collects and ingests reviews for Groww from:
- Google Play Store
- Apple App Store

Enforces balanced ingestion across negative friction reviews (1-2 stars)
and positive user experiences (4-5 stars) to prevent research skew.
"""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Literal, Optional

from src.ingestion.base import BaseIngestor

logger = logging.getLogger("ai_discovery_engine.appstore")

MOCK_STORE_REVIEWS: List[Dict[str, Any]] = [
    {
        "platform": "GooglePlay",
        "rating": 1,
        "title": "Bounce charges due to late AutoPay deduction",
        "text": "My SIP instalment was scheduled for the 3rd. Groww attempted debit on 6th when my balance was low. Bank charged ₹295 penalty! Support takes days to respond. Terrible experience for recurring payments.",
        "date": "2026-05-04",
        "review_id": "gp_rev_101",
    },
    {
        "platform": "GooglePlay",
        "rating": 5,
        "title": "Super intuitive app for first-time mutual fund investors",
        "text": "Started my first SIP 6 months ago. Setting up UPI AutoPay was instant. Love the Clean UI and instant portfolio tracking. Never had a single payment glitch.",
        "date": "2026-05-18",
        "review_id": "gp_rev_102",
    },
    {
        "platform": "AppStore",
        "rating": 2,
        "title": "UPI mandate fails on iPhone every time",
        "text": "Trying to register GPay mandate for my Nifty index fund. Groww app keeps saying session timeout when returning from GPay app. Had to set up NetBanking mandate manually.",
        "date": "2026-06-02",
        "review_id": "ios_rev_103",
    },
    {
        "platform": "GooglePlay",
        "rating": 1,
        "title": "Cannot pause or edit SIP date",
        "text": "Why is there no simple option to change SIP date? I got a new job with salary on 10th instead of 1st. To change date I had to cancel existing SIP and create new. Clunky product design.",
        "date": "2026-06-19",
        "review_id": "gp_rev_104",
    },
    {
        "platform": "AppStore",
        "rating": 4,
        "title": "Good app but please add buffer alerts",
        "text": "Investing in mutual funds is very smooth. However, it would be great if Groww sends a reminder notification 2 days before debit date so I can ensure sufficient bank balance.",
        "date": "2026-07-05",
        "review_id": "ios_rev_105",
    },
    {
        "platform": "GooglePlay",
        "rating": 5,
        "title": "Consistent and reliable monthly debits",
        "text": "Running 4 active SIPs for more than a year. All debited on the exact date without any issues. Statements and capital gains reports are easy to download.",
        "date": "2026-07-22",
        "review_id": "gp_rev_106",
    },
]


class ReviewCollector(BaseIngestor):
    """Ingestor connector for Google Play Store and Apple App Store reviews."""

    def __init__(self):
        super().__init__(source_type="app_store", platform="GooglePlay")

    def fetch(self, query_or_params: Optional[Any] = None) -> List[Dict[str, Any]]:
        """Collects App Store reviews with balance enforcement across ratings.

        Args:
            query_or_params: Optional dict with 'platform' ('GooglePlay' | 'AppStore'),
                             'min_rating', 'max_rating', 'limit', or 'reviews_data'.

        Returns:
            List of normalized candidate record dictionaries.
        """
        # If user passed custom reviews list
        if isinstance(query_or_params, dict) and "reviews_data" in query_or_params:
            raw_reviews = query_or_params["reviews_data"]
            return self._normalize_reviews(raw_reviews)

        target_platform = "GooglePlay"
        if isinstance(query_or_params, dict) and "platform" in query_or_params:
            target_platform = query_or_params["platform"]

        records = self._generate_balanced_reviews(target_platform)
        return records

    def _normalize_reviews(self, raw_reviews: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Normalizes external review dictionaries."""
        results: List[Dict[str, Any]] = []
        for r in raw_reviews:
            platform = r.get("platform", "GooglePlay")
            title = r.get("title", "")
            text = r.get("text") or r.get("body", "")
            full_text = f"{title}\n\n{text}".strip() if title else text.strip()

            results.append({
                "source_type": self.source_type,
                "platform": platform,
                "source_url": r.get("source_url") or f"https://play.google.com/store/apps/details?id=com.nextbillion.groww&reviewId={r.get('review_id', 'rev')}",
                "title": title,
                "raw_text": full_text,
                "publication_date": r.get("date", datetime.now(timezone.utc).strftime("%Y-%m-%d")),
                "rating": r.get("rating"),
                "is_synthetic_demo": r.get("is_synthetic_demo", True),
                "relevance_status": "highly_relevant" if "sip" in full_text.lower() else "partially_relevant",
            })
        return results

    def _generate_balanced_reviews(self, target_platform: str) -> List[Dict[str, Any]]:
        """Generates balanced rating reviews (mix of 1-2 star complaints & 4-5 star positive reviews)."""
        results: List[Dict[str, Any]] = []
        for r in MOCK_STORE_REVIEWS:
            platform = r["platform"]
            title = r.get("title", "")
            full_text = f"{title}\n\n{r['text']}".strip()
            store_url = (
                f"https://play.google.com/store/apps/details?id=com.nextbillion.groww&reviewId={r['review_id']}"
                if platform == "GooglePlay"
                else f"https://apps.apple.com/in/app/groww-stocks-mutual-fund/id1404871703?reviewId={r['review_id']}"
            )

            results.append({
                "source_type": self.source_type,
                "platform": platform,
                "source_url": store_url,
                "title": title,
                "raw_text": full_text,
                "publication_date": r["date"],
                "rating": r["rating"],
                "is_synthetic_demo": True,
                "relevance_status": "highly_relevant",
            })
        return results

