"""Reddit Discussions Collector.

Collects public discussions and user feedback from relevant subreddits:
- r/IndiaInvestments
- r/mutualfunds
- r/personalfinanceindia

Supports both live public Reddit JSON API queries and deterministic mock generation
for offline air-gapped environments.
"""

from datetime import datetime, timezone
import json
import logging
from typing import Any, Dict, List, Optional
import urllib.parse
import urllib.request

from src.ingestion.base import BaseIngestor

logger = logging.getLogger("ai_discovery_engine.reddit")

DEFAULT_SUBREDDITS = ["IndiaInvestments", "mutualfunds", "personalfinanceindia"]

SAMPLE_REDDIT_QUERIES = [
    "Groww SIP failed",
    "Groww AutoPay issue",
    "Unable to continue SIP",
    "SIP insufficient balance",
    "Why did you stop your SIP?",
    "Monthly salary and SIP investment",
    "Unexpected expenses and investments",
    "First time mutual fund investor problems",
]

# Curated synthetic/mock discussion templates for offline mode
MOCK_REDDIT_DISCUSSIONS: List[Dict[str, Any]] = [
    {
        "title": "SIP instalment failed on Groww because salary was credited 1 day late",
        "text": "Every month my SIP is scheduled for 5th. This month salary came on 6th morning. Groww AutoPay failed and bank debited ₹295 ECS bounce fee. I want to know if I can change the debit date to 10th without deleting the SIP.",
        "subreddit": "IndiaInvestments",
        "permalink": "/r/IndiaInvestments/comments/sip_salary_late",
        "created_utc": "2026-04-06",
    },
    {
        "title": "Why does Groww not allow 1-click pause for 3 months?",
        "text": "Had an emergency root canal surgery costing ₹22,000. Needed to pause all 3 of my mutual fund SIPs for 90 days. On Groww app there is only a Skip Instalment button for 1 month, and when I skipped, the mandate still triggered! Very stressful.",
        "subreddit": "mutualfunds",
        "permalink": "/r/mutualfunds/comments/groww_pause_friction",
        "created_utc": "2026-05-14",
    },
    {
        "title": "Stopped investing after 8 months because portfolio was at -2%",
        "text": "Everyone on social media claims SIP gives 15% guaranteed. Invested ₹3000 every month for 8 months in small cap funds. Current value is ₹23,400 against ₹24,000 invested. I stopped the SIP and moved to Bank FD.",
        "subreddit": "personalfinanceindia",
        "permalink": "/r/personalfinanceindia/comments/stopping_sip_loss",
        "created_utc": "2026-06-20",
    },
    {
        "title": "Groww AutoPay mandate rejected repeatedly with MD01 error",
        "text": "Attempted to register UPI AutoPay via PhonePe for my index fund SIP. Groww kept showing verification pending for 5 days and then rejected it with error code MD01. Customer support ticket has had no response for a week.",
        "subreddit": "IndiaInvestments",
        "permalink": "/r/IndiaInvestments/comments/groww_mandate_md01",
        "created_utc": "2026-07-08",
    },
    {
        "title": "First time investor confusion: XIRR vs Absolute Returns",
        "text": "Groww app dashboard shows XIRR of 12% on top of my portfolio card, but right below it shows total returns of -₹350. Can someone explain how both can be true? As a first time investor this is completely baffling.",
        "subreddit": "mutualfunds",
        "permalink": "/r/mutualfunds/comments/xirr_confusion_first_timer",
        "created_utc": "2026-08-01",
    },
]


class RedditCollector(BaseIngestor):
    """Ingestor connector for Reddit community forums."""

    def __init__(self):
        super().__init__(source_type="reddit", platform="Reddit")

    def fetch(self, query_or_params: Optional[Any] = None) -> List[Dict[str, Any]]:
        """Fetches Reddit posts matching target mutual fund and SIP discontinuation keywords.

        Args:
            query_or_params: Specific query string or dict with 'query', 'subreddit', 'use_live_api'.

        Returns:
            List of normalized candidate record dictionaries.
        """
        records: List[Dict[str, Any]] = []
        use_live_api = False
        query = "Groww SIP failed"
        subreddits = DEFAULT_SUBREDDITS

        if isinstance(query_or_params, str):
            query = query_or_params
        elif isinstance(query_or_params, dict):
            query = query_or_params.get("query", query)
            subreddits = query_or_params.get("subreddits", [query_or_params.get("subreddit")]) if query_or_params.get("subreddit") else subreddits
            use_live_api = query_or_params.get("use_live_api", False)

        if use_live_api:
            for sub in subreddits:
                try:
                    live_records = self._fetch_live_reddit(query, sub)
                    records.extend(live_records)
                except Exception as e:
                    logger.warning(f"Live Reddit fetch failed for r/{sub} ({e}). Falling back to curated records.")

        # If live retrieval yielded no results or in offline mode, load curated discussions
        if not records:
            records = self._generate_mock_discussions(query)

        return records

    def _fetch_live_reddit(self, query: str, subreddit: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Queries Reddit's public search JSON endpoint."""
        encoded_query = urllib.parse.quote(query)
        url = f"https://www.reddit.com/r/{subreddit}/search.json?q={encoded_query}&restrict_sr=1&sort=relevance&limit={limit}"

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AI-Discovery-Engine/1.0"
        }
        req = urllib.request.Request(url, headers=headers)

        with urllib.request.urlopen(req, timeout=5) as response:
            if response.status != 200:
                return []
            data = json.loads(response.read().decode("utf-8"))

        children = data.get("data", {}).get("children", [])
        results: List[Dict[str, Any]] = []

        for child in children:
            post = child.get("data", {})
            selftext = post.get("selftext", "")
            title = post.get("title", "")
            if not selftext and not title:
                continue

            full_text = f"{title}\n\n{selftext}".strip()
            permalink = f"https://reddit.com{post.get('permalink', '')}"
            pub_date = datetime.fromtimestamp(post.get("created_utc", 0), tz=timezone.utc).strftime("%Y-%m-%d")

            results.append({
                "source_type": self.source_type,
                "platform": self.platform,
                "source_url": permalink,
                "title": title,
                "raw_text": full_text,
                "publication_date": pub_date,
                "rating": None,
                "is_synthetic_demo": False,
                "relevance_status": "highly_relevant" if "sip" in full_text.lower() else "partially_relevant",
            })

        return results

    def _generate_mock_discussions(self, query: str) -> List[Dict[str, Any]]:
        """Returns structured mock Reddit records for testing and offline execution."""
        results: List[Dict[str, Any]] = []
        for i, item in enumerate(MOCK_REDDIT_DISCUSSIONS):
            full_text = f"{item['title']}\n\n{item['text']}"
            permalink = f"https://reddit.com{item['permalink']}"
            results.append({
                "source_type": self.source_type,
                "platform": self.platform,
                "source_url": permalink,
                "title": item["title"],
                "raw_text": full_text,
                "publication_date": item["created_utc"],
                "rating": None,
                "is_synthetic_demo": True,
                "relevance_status": "highly_relevant",
            })
        return results

