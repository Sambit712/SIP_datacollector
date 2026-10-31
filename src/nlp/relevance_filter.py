"""Relevance Filtering Module.

Classifies ingested records into:
- highly_relevant: directly concerns SIP initiation, AutoPay, affordability, retention, or discontinuation
- partially_relevant: general mutual fund or wealth app discussion with indirect SIP context
- not_relevant: stock trading, intraday, crypto, promotional noise, or unrelated financial advice

Employs Groq fast model (llama-3.1-8b-instant) when online, and delegates
to the Deterministic Fallback Engine when offline.
"""

import json
import logging
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field

from src.nlp.fallback_engine import FallbackEngine
from src.nlp.llm_client import GroqLLMClient, GroqOfflineError

logger = logging.getLogger("ai_discovery_engine.relevance")


class RelevanceResponseSchema(BaseModel):
    relevance_status: str = Field(description="'highly_relevant', 'partially_relevant', or 'not_relevant'")
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str = Field(description="Brief explanation of classification")


class RelevanceFilter:
    """Filters and classifies research records by relevance to SIP continuation."""

    def __init__(self, llm_client: Optional[GroqLLMClient] = None):
        self.llm = llm_client or GroqLLMClient()

    def classify_record(self, text: str, title: Optional[str] = None) -> Tuple[str, float, str]:
        """Classifies a single record's relevance status.

        Returns:
            Tuple of (relevance_status, confidence, reasoning)
        """
        # Try Groq fast model if online
        if self.llm.is_available:
            try:
                system_prompt = (
                    "You are a Senior Product Research Analyst investigating mutual fund SIP (Systematic Investment Plan) "
                    "discontinuation and retention among first-time investors on Groww.\n"
                    "Classify whether the text is:\n"
                    "- 'highly_relevant': mentions SIP setup, AutoPay failures, mandate issues, salary timing, unexpected expenses, "
                    "stopping/pausing SIP, XIRR confusion, market fear, or app friction.\n"
                    "- 'partially_relevant': general mutual fund investing, Groww app feedback, or indirect wealth tracking.\n"
                    "- 'not_relevant': crypto, bitcoin, intraday trading, F&O options, IPO tips, advertisements, or spam.\n"
                    "Output JSON matching: {'relevance_status': str, 'confidence': float, 'reasoning': str}"
                )
                user_msg = f"Title: {title or 'N/A'}\n\nContent:\n{text[:1000]}"

                result: RelevanceResponseSchema = self.llm.generate_structured_json(
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_msg},
                    ],
                    schema=RelevanceResponseSchema,
                    model=self.llm.fast_model,
                )
                status = result.relevance_status.lower().strip()
                if status not in ["highly_relevant", "partially_relevant", "not_relevant"]:
                    status = "partially_relevant"
                return (status, result.confidence, result.reasoning)
            except Exception as e:
                logger.warning(f"Groq relevance classification failed ({e}). Reverting to fallback engine.")

        # Deterministic offline fallback
        return FallbackEngine.classify_relevance(text, title=title)

    def filter_batch(self, records: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """Classifies a batch of candidate records and partitions them by relevance status."""
        partitioned: Dict[str, List[Dict[str, Any]]] = {
            "highly_relevant": [],
            "partially_relevant": [],
            "not_relevant": [],
        }

        for r in records:
            status, conf, reason = self.classify_record(r.get("raw_text", ""), r.get("title"))
            r["relevance_status"] = status
            r["relevance_confidence"] = conf
            r["relevance_reasoning"] = reason
            partitioned.setdefault(status, []).append(r)

        return partitioned
