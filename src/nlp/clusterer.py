"""Semantic Clustering & Centroid Synthesis Engine.

Groups similar user friction points into coherent problem clusters using
dense semantic embeddings or TF-IDF representations.
Synthesizes PM cluster narratives and assigns evidence confidence tiers.
"""

import logging
from typing import Any, Dict, List, Optional
import numpy as np
from sklearn.cluster import AgglomerativeClustering
from sklearn.feature_extraction.text import TfidfVectorizer

from src.nlp.fallback_engine import FallbackEngine
from src.nlp.llm_client import GroqLLMClient

logger = logging.getLogger("ai_discovery_engine.clusterer")


class IssueClusterer:
    """Discovers and synthesizes semantic problem clusters from extracted issues."""

    def __init__(self, llm_client: Optional[GroqLLMClient] = None):
        self.llm = llm_client or GroqLLMClient()
        self._embedder = None

    def _get_embedder(self):
        """Lazy loader for sentence-transformers when explicitly enabled in settings."""
        if self._embedder is None:
            from config.settings import get_settings
            settings = get_settings()
            if not settings.USE_DENSE_EMBEDDINGS or settings.is_offline:
                # Fast, robust TF-IDF representations (default)
                self._embedder = False
            else:
                try:
                    from sentence_transformers import SentenceTransformer
                    self._embedder = SentenceTransformer("all-MiniLM-L6-v2")
                except Exception as e:
                    logger.info(f"SentenceTransformer not available or failed to load ({e}). Using TF-IDF.")
                    self._embedder = False
        return self._embedder

    def cluster_issues(
        self,
        issues: List[Dict[str, Any]],
        distance_threshold: float = 0.40,
    ) -> List[Dict[str, Any]]:
        """Clusters a list of extracted issue dictionaries.

        Args:
            issues: List of dicts representing ExtractedIssue instances.
            distance_threshold: Cosine distance threshold for agglomerative clustering.

        Returns:
            List of synthesized cluster dicts containing metadata, member IDs, and evidence tier.
        """
        if not issues:
            return []

        if len(issues) <= 2:
            return FallbackEngine.cluster_issues_offline(issues, n_clusters=len(issues))

        texts = [f"{i.get('core_problem', '')}. {i.get('verbatim_excerpt', '')}" for i in issues]

        # 1. Compute Embeddings or TF-IDF Matrix
        embedder = self._get_embedder()
        if embedder:
            try:
                embeddings = embedder.encode(texts, normalize_embeddings=True)
            except Exception as e:
                logger.warning(f"Dense embedding encoding failed: {e}. Reverting to TF-IDF.")
                embeddings = None
        else:
            embeddings = None

        if embeddings is None:
            vectorizer = TfidfVectorizer(max_features=150, stop_words="english")
            embeddings = vectorizer.fit_transform(texts).toarray()

        # 2. Agglomerative Hierarchical Clustering
        # Calculate target k clusters
        k = max(2, min(len(issues) // 3, 10))
        k = min(k, len(issues))

        clustering = AgglomerativeClustering(n_clusters=k)
        labels = clustering.fit_predict(embeddings)

        # 3. Synthesize Clusters
        clusters: List[Dict[str, Any]] = []

        for cluster_id in range(k):
            members = [issues[idx] for idx, label in enumerate(labels) if label == cluster_id]
            if not members:
                continue

            count = len(members)

            # Determine dominant category
            cat_counts: Dict[str, int] = {}
            has_official_doc = False
            for m in members:
                cat = m.get("category_id") or m.get("suggested_category_code") or "cat_13"
                cat_counts[cat] = cat_counts.get(cat, 0) + 1
                if m.get("is_synthetic_demo") is False or "official" in m.get("source_type", ""):
                    has_official_doc = True

            dominant_cat = max(cat_counts.items(), key=lambda x: x[1])[0]

            # Assign Evidence Tier
            if has_official_doc or count >= 5:
                evidence_tier = "strong"
            elif count >= 2:
                evidence_tier = "moderate"
            else:
                evidence_tier = "weak"

            # Synthesize Theme Title & Narrative
            theme_title = members[0].get("core_problem", f"Cluster {cluster_id + 1}")
            summary = self._synthesize_cluster_summary(members, dominant_cat)

            clusters.append({
                "theme_title": theme_title,
                "summary_description": summary,
                "category_id": dominant_cat,
                "primary_root_cause": dominant_cat,
                "supporting_record_count": count,
                "evidence_tier": evidence_tier,
                "member_ids": [m.get("id") for m in members if m.get("id")],
                "members": members,
            })

        return clusters

    def _synthesize_cluster_summary(self, members: List[Dict[str, Any]], dominant_cat: str) -> str:
        """Synthesizes a PM problem narrative for the cluster."""
        count = len(members)
        sample_excerpts = [m.get("verbatim_excerpt", "")[:120] for m in members[:3] if m.get("verbatim_excerpt")]

        if self.llm.is_available and len(sample_excerpts) >= 2:
            try:
                system_prompt = (
                    "You are a Product Discovery Lead. Summarize the recurring user problem represented by these sample excerpts "
                    "into a concise 2-sentence PM problem narrative explaining what is happening and the user consequence."
                )
                user_msg = f"Category: {dominant_cat}\nSample Evidence:\n" + "\n".join(f"- {e}" for e in sample_excerpts)
                narrative = self.llm.generate_chat_completion(
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_msg},
                    ],
                    max_tokens=200,
                )
                if narrative and len(narrative.strip()) > 20:
                    return narrative.strip()
            except Exception as e:
                logger.debug(f"LLM cluster narrative synthesis skipped: {e}")

        # Deterministic summary
        evidence_preview = " | ".join(sample_excerpts[:2]) if sample_excerpts else "No excerpts."
        return f"Recurring issue affecting {count} records categorized under {dominant_cat}. Evidence highlights: {evidence_preview}"
