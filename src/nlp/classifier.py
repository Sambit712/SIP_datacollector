"""Taxonomy Classifier & Emergence Detector.

Classifies problem statements into the 13 canonical categories and flags
outlier friction patterns as candidate Emergent Themes.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

from src.nlp.fallback_engine import FallbackEngine
from src.nlp.llm_client import GroqLLMClient

logger = logging.getLogger("ai_discovery_engine.classifier")


class TaxonomyClassifier:
    """Classifies extracted complaints into categories with emergence detection."""

    def __init__(self, llm_client: Optional[GroqLLMClient] = None):
        self.llm = llm_client or GroqLLMClient()
        self.taxonomy = FallbackEngine.get_taxonomy()
        self.category_map = {c["code"]: c["id"] for c in self.taxonomy}

    def classify(self, text: str, problem_summary: Optional[str] = None) -> Tuple[str, str, float, bool]:
        """Classifies text into a category code and category ID.

        Returns:
            Tuple of (category_id, category_code, confidence_score, is_emergent_theme)
        """
        combined = f"{problem_summary or ''} {text}".strip()

        # Try Groq classification if available
        if self.llm.is_available:
            try:
                system_prompt = (
                    "You are a Senior Product Taxonomist. Classify the user problem into exactly one of these categories:\n"
                    "- cash_flow_mismatch: salary delay, budget shortfall, rent/EMI priority\n"
                    "- unexpected_expenses: medical emergency, sudden repair, hospital bills\n"
                    "- payment_failures: ECS/NACH bounce fees (e.g. ₹295), bank server failure, debit timeout\n"
                    "- autopay_mandate: NPCI e-mandate rejection, NetBanking OTP error, mandate verification delay\n"
                    "- modification_cancellation: pause button missing, inability to change SIP date/amount\n"
                    "- expectation_mismatch: negative returns after 6-8 months, returns lower than expected\n"
                    "- volatility_anxiety: market crash panic, red portfolio distress, fear of loss\n"
                    "- lack_understanding: NAV cut-off confusion, units allotment, XIRR vs absolute returns\n"
                    "- confusing_statements: statements reconciliation, tax report difficulty\n"
                    "- app_usability: Groww app crashes, buggy UI, navigation hurdle\n"
                    "- support_trust: unresponsive customer care, unresolved double deduction, bot loops\n"
                    "- goal_changes: marriage, education, buying house/car\n"
                    "- unclassified: emergent theme not fitting any above\n"
                    "Output JSON: {'category_code': str, 'confidence': float, 'is_emergent': bool}"
                )
                user_msg = f"User problem: {combined[:1200]}"
                response = self.llm.generate_chat_completion(
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_msg},
                    ],
                    response_format={"type": "json_object"},
                    model=self.llm.fast_model,
                )
                import json
                data = json.loads(response)
                cat_code = data.get("category_code", "").lower().strip()
                confidence = float(data.get("confidence", 0.8))
                is_emergent = bool(data.get("is_emergent", False))

                if cat_code in self.category_map:
                    cat_id = self.category_map[cat_code]
                    return (cat_id, cat_code, confidence, is_emergent)
            except Exception as e:
                logger.warning(f"Groq category classification failed ({e}). Reverting to fallback taxonomy matcher.")

        # Fallback keyword matching
        code, conf = FallbackEngine.classify_category(combined)
        cat_id = self.category_map.get(code, "cat_13")
        is_emergent = (code == "unclassified" or conf < 0.55)

        return (cat_id, code, conf, is_emergent)

