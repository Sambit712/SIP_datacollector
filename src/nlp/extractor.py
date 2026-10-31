"""Structured Entity & Complaint Extractor.

Extracts structured problem instances conforming to ExtractedIssueSchema.
Enforces character-exact substring verification on verbatim_excerpt to
guarantee zero hallucination of user quotations.

Uses Groq llama-3.3-70b-versatile when online, with fallback to FallbackEngine.
"""

import logging
from typing import Optional
import re

from src.models.schemas import ExtractedIssueSchema
from src.nlp.fallback_engine import FallbackEngine
from src.nlp.llm_client import GroqLLMClient

logger = logging.getLogger("ai_discovery_engine.extractor")


class ComplaintExtractor:
    """Extracts structured friction entities and corroborated excerpts from raw records."""

    def __init__(self, llm_client: Optional[GroqLLMClient] = None):
        self.llm = llm_client or GroqLLMClient()

    def extract_issue(self, raw_text: str, platform: str = "Groww") -> ExtractedIssueSchema:
        """Extracts structured problem schema from raw record text.

        Enforces verbatim substring verification: verbatim_excerpt MUST be
        a character-exact substring of raw_text.
        """
        if not raw_text or not raw_text.strip():
            return FallbackEngine.extract_issue("Empty record content.", platform)

        # Attempt Groq extraction when available
        if self.llm.is_available:
            try:
                system_prompt = (
                    "You are a rigorous AI Research Analyst extracting mutual fund SIP problems for a Product Manager.\n"
                    "Extract the core complaint into structured JSON according to the schema:\n"
                    "- core_problem: Single-sentence summary of the obstacle.\n"
                    "- verbatim_excerpt: An EXACT, character-for-character substring copied directly from the text supporting the claim.\n"
                    "- journey_stage: 'pre_sip' | 'setup' | 'active' | 'instalment_failed' | 'life_event' | 'churned'\n"
                    "- mentions_groww: boolean\n"
                    "- is_first_hand_experience: boolean (True if lived experience, False if hypothetical)\n"
                    "- sip_status: 'active' | 'paused' | 'failed' | 'discontinued' | 'unknown'\n"
                    "- stated_discontinuation_reason: explicit stated reason or null\n"
                    "- severity_level: 'low' | 'medium' | 'high' | 'critical'\n"
                    "- epistemic_type: 'observed_evidence' | 'interpretation' | 'hypothesis'\n"
                    "- confidence_score: float between 0.0 and 1.0\n"
                    "- suggested_category_code: taxonomy category code if applicable\n"
                    "CRITICAL: verbatim_excerpt MUST be an exact substring from the input text with no word changes."
                )

                user_prompt = f"Platform: {platform}\n\nContent:\n{raw_text[:2500]}"

                result: ExtractedIssueSchema = self.llm.generate_structured_json(
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    schema=ExtractedIssueSchema,
                    model=self.llm.primary_model,
                )

                # Verification check: Ensure verbatim_excerpt is an exact substring
                cleaned_excerpt = result.verbatim_excerpt.strip()
                if cleaned_excerpt not in raw_text:
                    # If LLM slightly trimmed or paraphrased, locate best exact sentence substring
                    exact_sub = self._find_best_exact_substring(cleaned_excerpt, raw_text)
                    result.verbatim_excerpt = exact_sub

                return result
            except Exception as e:
                logger.warning(f"Groq complaint extraction failed ({e}). Reverting to fallback engine.")

        # Deterministic offline fallback
        return FallbackEngine.extract_issue(raw_text, platform)

    def _find_best_exact_substring(self, candidate_excerpt: str, raw_text: str) -> str:
        """Finds the closest exact sentence from raw_text matching the candidate excerpt."""
        sentences = [s.strip() for s in re.split(r"(?<=[.!?\n])\s+", raw_text) if len(s.strip()) > 10]
        candidate_words = set(candidate_excerpt.lower().split())

        best_sentence = ""
        best_overlap = -1

        for s in sentences:
            if s in raw_text:
                overlap = len(set(s.lower().split()) & candidate_words)
                if overlap > best_overlap:
                    best_overlap = overlap
                    best_sentence = s

        if best_sentence and best_sentence in raw_text:
            return best_sentence

        # Default to first 100 characters of raw text if sentence matching fails
        return raw_text[:100].strip()

