"""Automated Live Play Store Pipeline: Ingest, Filter, and Rank 5000 Groww Reviews.

Fetches 5,000 real reviews from Google Play Store for Groww (India),
runs high-throughput PII sanitization, filters for mutual fund SIP relevance,
scores information richness/suitability, and stores the top discoveries in SQLite.
"""

import sys
import logging
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import re
import pandas as pd
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple
from google_play_scraper import reviews, Sort

from src.models.database import (
    get_session,
    RawRecord,
    compute_content_hash,
)
from src.nlp.sanitizer import sanitize_text
from src.nlp.pipeline import AnalysisPipeline
from src.prioritization.scorer import OpportunityScorer

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("groww_5000_processor")

APP_ID = "com.nextbillion.groww"
TARGET_REVIEW_COUNT = 5000

# Keywords indicating high mutual fund / SIP persistency relevance
SIP_KEYWORDS = [
    "sip", "mutual fund", "mutual funds", "autopay", "auto pay", "mandate",
    "e-mandate", "emandate", "nach", "npci", "bounce", "ecs", "instalment",
    "installment", "deduct", "deducted", "pause", "cancel", "stop", "stopp",
    "kyc", "folio", "amc", "nav", "xirr", "cagr", "dividend", "elss",
    "salary", "bank account", "penalty", "charges", "hidden charges", "loss",
    "market crash", "drawdown", "redemption", "withdraw", "units"
]

# Exclusion keywords for non-SIP topics
EXCLUDE_KEYWORDS = [
    "f&o", "options trading", "futures and options", "call option", "put option",
    "intraday", "day trading", "crypto", "bitcoin", "candlestick", "stoploss",
    "delivery margin", "ipo allotment", "stock pledge"
]


def calculate_suitability_score(text: str, rating: int) -> float:
    """Calculates an objective PM suitability score in [0.0, 1.0] for a review."""
    lower = text.lower()

    # Immediate disqualification if pure stock/crypto day-trading or 1-word spam
    if any(ex in lower for ex in EXCLUDE_KEYWORDS):
        return 0.05
    if len(text.split()) < 4:
        return 0.0

    # 1. Keyword density / domain specificity (0 to 0.40)
    matched_kws = sum(1 for kw in SIP_KEYWORDS if re.search(r"\b" + re.escape(kw) + r"\b", lower))
    kw_score = min(0.40, matched_kws * 0.08)

    # 2. Informational length & depth (0 to 0.30)
    word_count = len(text.split())
    length_score = min(0.30, word_count / 100.0 * 0.30)

    # 3. Actionability & Root cause presence (0 to 0.20)
    has_root_cause = any(phrase in lower for phrase in [
        "failed", "rejected", "charged", "delay", "not working", "cannot find",
        "confusing", "error", "deducted but", "mandate rejected", "bounce charge",
        "pause option", "salary date", "loss", "customer care", "unhelpful"
    ])
    actionability_score = 0.20 if has_root_cause else 0.05

    # 4. Rating insightfulness (0 to 0.10)
    # 1-3 star reviews contain richer friction insights
    rating_score = 0.10 if rating in [1, 2, 3] else 0.05

    total_score = kw_score + length_score + actionability_score + rating_score
    return round(min(1.0, max(0.0, total_score)), 4)


def fetch_live_playstore_reviews(total_count: int = TARGET_REVIEW_COUNT) -> List[Dict[str, Any]]:
    """Fetches up to total_count reviews from Google Play Store for Groww."""
    logger.info(f"Fetching {total_count} reviews from Google Play Store for {APP_ID}...")
    all_reviews = []
    
    # 1. Fetch newest reviews
    batch_size = 2500
    try:
        res_newest, continuation_token = reviews(
            APP_ID,
            lang="en",
            country="in",
            sort=Sort.NEWEST,
            count=batch_size,
        )
        all_reviews.extend(res_newest)
        logger.info(f"Fetched {len(res_newest)} newest reviews.")
    except Exception as e:
        logger.warning(f"Error fetching newest reviews: {e}")

    # 2. Fetch most relevant reviews to get rich text
    try:
        res_relevant, _ = reviews(
            APP_ID,
            lang="en",
            country="in",
            sort=Sort.MOST_RELEVANT,
            count=batch_size,
        )
        all_reviews.extend(res_relevant)
        logger.info(f"Fetched {len(res_relevant)} most relevant reviews.")
    except Exception as e:
        logger.warning(f"Error fetching relevant reviews: {e}")

    # Deduplicate by reviewId or content
    seen_ids = set()
    unique_reviews = []
    for r in all_reviews:
        r_id = r.get("reviewId") or r.get("content")
        if r_id not in seen_ids:
            seen_ids.add(r_id)
            unique_reviews.append(r)

    logger.info(f"Total unique reviews collected: {len(unique_reviews)}")
    return unique_reviews


def process_and_rank_reviews():
    """Main execution orchestrator."""
    raw_reviews = fetch_live_playstore_reviews(TARGET_REVIEW_COUNT)
    if not raw_reviews:
        logger.error("No reviews could be fetched from Google Play Store.")
        return

    logger.info("Scoring and filtering reviews for SIP persistency suitability...")
    scored_records = []

    for r in raw_reviews:
        content = (r.get("content") or "").strip()
        if not content:
            continue

        rating = r.get("score", 3)
        suitability = calculate_suitability_score(content, rating)

        # High-precision filter threshold: keep reviews with suitability >= 0.25
        if suitability >= 0.25:
            sanitized = sanitize_text(content)
            pub_date = r.get("at")
            pub_str = pub_date.strftime("%Y-%m-%d") if isinstance(pub_date, datetime) else str(pub_date or "")

            scored_records.append({
                "source_type": "app_store",
                "platform": "GooglePlay",
                "title": f"Google Play Review ({rating}★)",
                "raw_text": content,
                "sanitized_text": sanitized,
                "content_hash": compute_content_hash(sanitized),
                "rating": rating,
                "publication_date": pub_str,
                "relevance_status": "highly_relevant" if suitability >= 0.45 else "partially_relevant",
                "suitability_score": suitability,
                "author": r.get("userName", "Anonymous"),
                "review_id": r.get("reviewId", ""),
            })

    # Sort descending by suitability score
    scored_records.sort(key=lambda x: x["suitability_score"], reverse=True)
    logger.info(f"Found {len(scored_records)} relevant mutual fund / SIP reviews out of {len(raw_reviews)} total!")

    # 1. Export top reviews to CSV for PM analysis
    output_dir = PROJECT_ROOT / "data" / "exports"
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "top_suitable_playstore_reviews.csv"

    df_export = pd.DataFrame(scored_records)
    df_export.to_csv(csv_path, index=False, encoding="utf-8")
    logger.info(f"Exported top suitable reviews to: {csv_path}")

    # 2. Ingest top suitable records into SQLite Database
    logger.info("Ingesting top suitable records into database...")
    session = get_session()
    inserted_count = 0

    try:
        for item in scored_records[:150]:  # Ingest top 150 most suitable into database
            existing = session.query(RawRecord).filter_by(content_hash=item["content_hash"]).first()
            if not existing:
                rec = RawRecord(
                    source_type=item["source_type"],
                    platform=item["platform"],
                    title=item["title"],
                    raw_text=item["raw_text"],
                    sanitized_text=item["sanitized_text"],
                    content_hash=item["content_hash"],
                    rating=item["rating"],
                    publication_date=item["publication_date"],
                    relevance_status=item["relevance_status"],
                    is_user_verified=True,
                    is_synthetic_demo=False,
                )
                session.add(rec)
                inserted_count += 1

        session.commit()
        logger.info(f"Successfully inserted {inserted_count} new high-value records into SQLite!")

        # 3. Trigger extraction & clustering pipeline
        logger.info("Running AI Extraction & Problem Clustering on fresh records...")
        pipeline = AnalysisPipeline()
        pipeline.process_all_unanalyzed(session, batch_size=100)
        n_clusters = pipeline.cluster_all_extracted_issues(session)
        logger.info(f"Synthesized {n_clusters} semantic problem clusters.")

        # 4. Recalculate Opportunity Scores
        scorer = OpportunityScorer()
        ranked = scorer.score_all_clusters(session, persist=True)
        logger.info(f"Recalculated priority scores for {len(ranked)} opportunities.")

    finally:
        session.close()

    # Print top 5 discoveries to console
    print("\n" + "="*80)
    print(f"[SUCCESS] PROCESSED {len(raw_reviews)} REVIEWS -> IDENTIFIED {len(scored_records)} SUITABLE ONES")
    print("="*80)
    print(f"Top Suitable Reviews Exported to: {csv_path}\n")
    for idx, r in enumerate(scored_records[:5], start=1):
        clean_excerpt = r['sanitized_text'][:140].encode('ascii', errors='replace').decode('ascii')
        print(f"Rank #{idx} [Score: {r['suitability_score']:.2f}] Rating: {r['rating']} Stars")
        print(f"Excerpt: \"{clean_excerpt}...\"\n")
    print("="*80)


if __name__ == "__main__":
    process_and_rank_reviews()
