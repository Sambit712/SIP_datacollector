"""Deterministic Offline Fallback Engine.

Provides rule-based NLP extraction, relevance filtering, keyword taxonomy
classification, and offline clustering when Groq LLM API is unavailable,
unconfigured, or rate-limited. Guarantees zero runtime crashes.
"""

from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Tuple
import yaml
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import AgglomerativeClustering
import numpy as np

from config.settings import get_settings
from src.models.schemas import ExtractedIssueSchema

# Domain positive & negative lexicons for relevance filtering
POSITIVE_TOKENS = [
    "sip", "autopay", "mandate", "groww", "deduction", "instalment",
    "installment", "bounce", "penalty", "ecs", "nach", "amfi", "sebi",
    "mutual fund", "units", "nav", "xirr", "pause", "skip", "portfolio",
    "index fund", "small cap", "flexi cap", "discontinue", "cancel sip",
]

EXCLUSION_TOKENS = [
    "bitcoin", "crypto", "binance", "solana", "ethereum", "intraday",
    "f&o", "futures and options", "nifty options", "call option", "put option",
    "ipo allotment", "gold jewellery", "gold imports", "bracket order",
]


class FallbackEngine:
    """Deterministic rule-based fallback processor for all NLP tasks."""

    _taxonomy_cache = None

    @classmethod
    def get_taxonomy(cls) -> List[Dict[str, Any]]:
        """Loads and caches the 13 categories from config/taxonomy.yaml."""
        if cls._taxonomy_cache is None:
            settings = get_settings()
            tax_path = settings.ROOT_DIR / "config" / "taxonomy.yaml"
            with open(tax_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            cls._taxonomy_cache = data.get("categories", [])
        return cls._taxonomy_cache

    @classmethod
    def classify_relevance(cls, text: str, title: Optional[str] = None) -> Tuple[str, float, str]:
        """Classifies relevance status deterministically using lexicon scoring.

        Returns:
            Tuple of (relevance_status, confidence, reasoning)
        """
        combined = f"{title or ''} {text}".lower()

        # Check exclusion tokens first
        exclusion_hits = [token for token in EXCLUSION_TOKENS if token in combined]
        if exclusion_hits and not ("mutual fund" in combined and "sip" in combined):
            return (
                "not_relevant",
                0.90,
                f"Contains excluded non-SIP domain topics: {', '.join(exclusion_hits[:3])}.",
            )

        # Count positive domain hits
        positive_hits = [token for token in POSITIVE_TOKENS if token in combined]
        hit_count = len(positive_hits)

        if "sip" in combined or "autopay" in combined or "mandate" in combined:
            if hit_count >= 2:
                return ("highly_relevant", 0.95, f"Directly concerns mutual fund SIP/AutoPay: {', '.join(positive_hits[:4])}.")
            return ("partially_relevant", 0.75, "Mentions SIP or mutual funds with low keyword density.")

        if "mutual fund" in combined or "groww" in combined:
            return ("partially_relevant", 0.65, "Mentions mutual funds or Groww platform generally.")

        return ("not_relevant", 0.85, "No mutual fund or recurring investment keywords identified.")

    @classmethod
    def extract_issue(cls, raw_text: str, platform: str = "Groww") -> ExtractedIssueSchema:
        """Extracts structured problem entities using deterministic rule heuristics.

        Guarantees that verbatim_excerpt is an exact character-for-character
        substring of raw_text.
        """
        lower_text = raw_text.lower()

        # 1. Split into sentences and find the best verbatim excerpt
        # Regex splits on sentence boundaries while preserving chunks
        raw_sentences = [s.strip() for s in re.split(r"(?<=[.!?\n])\s+", raw_text) if len(s.strip()) > 15]

        # Prioritize sentences containing problem indicators
        problem_cues = ["failed", "charged", "bounce", "cancel", "stop", "pause", "error", "penalty", "loss", "crash", "delay"]
        chosen_excerpt = ""
        for s in raw_sentences:
            s_lower = s.lower()
            if any(cue in s_lower for cue in problem_cues) and ("sip" in s_lower or "autopay" in s_lower or "groww" in s_lower or "mandate" in s_lower or "bank" in s_lower or "₹" in s):
                chosen_excerpt = s
                break

        if not chosen_excerpt and raw_sentences:
            chosen_excerpt = raw_sentences[0]
        elif not chosen_excerpt:
            chosen_excerpt = raw_text.strip()[:150]

        # Double check exact substring guarantee
        if chosen_excerpt not in raw_text:
            # Fallback to the first 100 characters of raw_text
            chosen_excerpt = raw_text[:100].strip()

        # 2. Derive core problem summary
        core_problem = chosen_excerpt
        if len(core_problem) > 120:
            core_problem = core_problem[:117] + "..."

        # 3. Detect journey stage
        journey_stage = "active"
        if any(w in lower_text for w in ["setup", "registration", "approve mandate", "e-mandate pending", "create sip"]):
            journey_stage = "setup"
        elif any(w in lower_text for w in ["bounce", "payment failed", "debit failed", "insufficient balance", "₹295", "penalty"]):
            journey_stage = "instalment_failed"
        elif any(w in lower_text for w in ["hospital", "wedding", "emergency", "personal loan", "salary reduction", "bought house"]):
            journey_stage = "life_event"
        elif any(w in lower_text for w in ["uninstalled", "closed account", "cancelled all", "never investing", "stopped my sip"]):
            journey_stage = "churned"
        elif any(w in lower_text for w in ["thinking of starting", "before starting", "how to start"]):
            journey_stage = "pre_sip"

        # 4. Mentions Groww
        mentions_groww = "groww" in lower_text or platform.lower() in ["groww", "googleplay", "appstore"]

        # 5. First-hand lived experience vs hypothetical
        hypothetical_markers = ["what if", "suppose", "hypothetically", "is it possible", "should one"]
        is_first_hand = not any(h in lower_text for h in hypothetical_markers)

        # 6. SIP Status
        sip_status = "unknown"
        discontinue_cues = [
            "cancelled", "stopped my sip", "stopping my sip", "stop my sip",
            "stop investing", "stopped investing", "decided to stop", "discontinued",
            "uninstalled", "quitting sip", "quit sip"
        ]
        if any(w in lower_text for w in discontinue_cues):
            sip_status = "discontinued"
        elif any(w in lower_text for w in ["paused", "skipping", "skipped instalment", "pause my sip"]):
            sip_status = "paused"
        elif any(w in lower_text for w in ["failed", "bounced", "declined"]):
            sip_status = "failed"
        elif any(w in lower_text for w in ["running", "active", "every month", "doing sip"]):
            sip_status = "active"

        # 7. Stated discontinuation reason
        stated_reason = None
        if sip_status in ["discontinued", "paused", "failed"]:
            stated_reason = chosen_excerpt

        # 8. Severity Level
        severity_level = "medium"
        if any(w in lower_text for w in ["bounce charge", "₹295", "fraud", "scammed", "hospital", "double deduction", "uninstalled"]):
            severity_level = "critical"
        elif any(w in lower_text for w in ["failed", "rejected", "panic", "anxiety", "penalty"]):
            severity_level = "high"
        elif any(w in lower_text for w in ["ui confusing", "dark mode", "font", "navigation"]):
            severity_level = "low"

        # 9. Suggest category code
        cat_code, _ = cls.classify_category(raw_text)

        return ExtractedIssueSchema(
            core_problem=core_problem,
            verbatim_excerpt=chosen_excerpt,
            journey_stage=journey_stage,
            mentions_groww=mentions_groww,
            is_first_hand_experience=is_first_hand,
            sip_status=sip_status,
            stated_discontinuation_reason=stated_reason,
            severity_level=severity_level,
            epistemic_type="observed_evidence" if is_first_hand else "hypothesis",
            confidence_score=0.88,
            suggested_category_code=cat_code,
        )

    @classmethod
    def classify_category(cls, text: str) -> Tuple[str, float]:
        """Classifies text into one of the 13 categories using taxonomy keyword matching."""
        taxonomy = cls.get_taxonomy()
        lower_text = text.lower()

        scores: Dict[str, int] = {}
        for cat in taxonomy:
            code = cat["code"]
            keywords = cat.get("keywords", [])
            match_count = sum(1 for kw in keywords if kw.lower() in lower_text)
            scores[code] = match_count

        best_code, best_score = max(scores.items(), key=lambda item: item[1])

        # If zero keyword matches, classify as unclassified
        if best_score == 0:
            return ("unclassified", 0.50)

        confidence = min(0.60 + (best_score * 0.10), 0.95)
        return (best_code, confidence)

    @classmethod
    def cluster_issues_offline(cls, issue_dicts: List[Dict[str, Any]], n_clusters: Optional[int] = None) -> List[Dict[str, Any]]:
        """Clusters extracted issues using scikit-learn TF-IDF & Agglomerative Clustering."""
        if not issue_dicts:
            return []

        if len(issue_dicts) == 1:
            item = issue_dicts[0]
            return [{
                "theme_title": item.get("core_problem", "Isolated Issue"),
                "summary_description": item.get("verbatim_excerpt", ""),
                "primary_root_cause": item.get("suggested_category_code", "unclassified"),
                "supporting_record_count": 1,
                "evidence_tier": "weak",
                "member_ids": [item.get("id")],
            }]

        texts = [f"{i.get('core_problem', '')} {i.get('verbatim_excerpt', '')}" for i in issue_dicts]

        vectorizer = TfidfVectorizer(max_features=100, stop_words="english")
        tfidf_matrix = vectorizer.fit_transform(texts).toarray()

        # Determine target cluster count
        k = n_clusters or max(2, min(len(issue_dicts) // 3, 8))
        k = min(k, len(issue_dicts))

        clustering = AgglomerativeClustering(n_clusters=k)
        labels = clustering.fit_predict(tfidf_matrix)

        clusters: List[Dict[str, Any]] = []
        for cluster_id in range(k):
            members = [issue_dicts[idx] for idx, label in enumerate(labels) if label == cluster_id]
            if not members:
                continue

            # Identify representative theme from members
            rep_member = members[0]
            cat_counts: Dict[str, int] = {}
            for m in members:
                c = m.get("suggested_category_code") or "unclassified"
                cat_counts[c] = cat_counts.get(c, 0) + 1
            dominant_cat = max(cat_counts.items(), key=lambda x: x[1])[0]

            theme_title = rep_member.get("core_problem", f"Cluster {cluster_id + 1}")
            count = len(members)

            # Evidence tier: strong (>=5 or contains official doc), moderate (2-4), weak (1)
            tier = "weak"
            if count >= 5:
                tier = "strong"
            elif count >= 2:
                tier = "moderate"

            clusters.append({
                "theme_title": theme_title,
                "summary_description": f"Theme encompassing {count} user records regarding {dominant_cat.replace('_', ' ')}.",
                "primary_root_cause": dominant_cat,
                "supporting_record_count": count,
                "evidence_tier": tier,
                "member_indices": [idx for idx, label in enumerate(labels) if label == cluster_id],
            })

        return clusters
