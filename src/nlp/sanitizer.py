"""PII Sanitization & Data Masking Engine.

Implements high-precision regex scrubbers to detect and mask Indian Personally
Identifiable Information (PII) and sensitive financial identifiers before storage
or LLM transmission.

Masked Entities:
- Indian Permanent Account Number (PAN)
- Indian Mobile / Phone Numbers
- Bank Account Numbers
- Email Addresses
- Aadhaar Numbers (12-digit UID)
- Payment Card Numbers (Credit / Debit)
"""

import re
from typing import Dict, List, Pattern, Tuple

# 1. PAN Pattern: 5 letters, 4 numbers, 1 letter (e.g., ABCDE1234F)
PAN_PATTERN: Pattern = re.compile(
    r"\b[A-Z]{5}[0-9]{4}[A-Z]\b",
    re.IGNORECASE,
)

# 2. Email Address Pattern
EMAIL_PATTERN: Pattern = re.compile(
    r"\b[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+\b"
)

# 3. Indian Phone / Mobile Number Pattern
# Matches:
#   +91 9876543210, +91-98765-43210, 09876543210, 9876543210, 98765 43210
# Starting with 6, 7, 8, or 9 for Indian cellular networks.
PHONE_PATTERN: Pattern = re.compile(
    r"(?:(?:\+|00)91[\s\-\.]?|0)?[6-9]\d{4}[\s\-\.]?\d{5}\b"
)

# 4. Aadhaar Number Pattern: 12 digits, often formatted as 4-4-4
AADHAAR_PATTERN: Pattern = re.compile(
    r"\b[2-9]\d{3}[\s\-]\d{4}[\s\-]\d{4}\b|\b[2-9]\d{11}\b"
)

# 5. Payment Card Number Pattern (Visa/Mastercard/RuPay: 16 digits)
CARD_PATTERN: Pattern = re.compile(
    r"\b(?:\d{4}[\s\-]){3}\d{4}\b"
)

# 6. Bank Account Numbers:
# Explicit contextual accounts: "a/c: 1234567890", "acct 1234567890123"
# Or standalone 11-18 digit numbers that are not timestamps/URLs.
BANK_ACC_CONTEXT_PATTERN: Pattern = re.compile(
    r"(?i)\b(?:a/?c|acct?|account(?:\s*no\.?)?|bank\s*acc(?:ount)?)\s*[:#-]?\s*([0-9]{9,18})\b"
)
STANDALONE_BANK_ACC_PATTERN: Pattern = re.compile(
    r"\b(?<!₹)(?<!Rs\.)(?<!Rs\s)(?<!INR)[0-9]{12,18}\b"
)

PII_REPLACEMENTS: List[Tuple[Pattern, str, str]] = [
    (EMAIL_PATTERN, "[REDACTED_EMAIL]", "email"),
    (PAN_PATTERN, "[REDACTED_PAN]", "pan"),
    (CARD_PATTERN, "[REDACTED_CARD]", "card"),
    (AADHAAR_PATTERN, "[REDACTED_AADHAAR]", "aadhaar"),
    (BANK_ACC_CONTEXT_PATTERN, "[REDACTED_ACCOUNT]", "account_context"),
    (STANDALONE_BANK_ACC_PATTERN, "[REDACTED_ACCOUNT]", "account_standalone"),
    (PHONE_PATTERN, "[REDACTED_PHONE]", "phone"),
]


def detect_pii(text: str) -> Dict[str, List[str]]:
    """Detects and returns all PII matches categorized by entity type.

    Args:
        text: Raw un-sanitized string.

    Returns:
        Dict mapping entity type name to a list of matched text strings.
    """
    if not text:
        return {}

    detected: Dict[str, List[str]] = {}

    for pattern, _, entity_type in PII_REPLACEMENTS:
        matches = pattern.findall(text)
        if matches:
            # Handle regex groups (e.g. from bank context capture)
            cleaned_matches = []
            for m in matches:
                if isinstance(m, tuple):
                    cleaned_matches.append(m[0])
                else:
                    cleaned_matches.append(m)
            if cleaned_matches:
                entity_key = entity_type.split("_")[0]  # normalize "account_context" -> "account"
                detected.setdefault(entity_key, []).extend(cleaned_matches)

    return detected


def contains_pii(text: str) -> bool:
    """Checks whether the input text contains any detectable PII entities."""
    if not text:
        return False

    for pattern, _, _ in PII_REPLACEMENTS:
        if pattern.search(text):
            return True
    return False


def sanitize_text(text: str) -> str:
    """Scrubs all sensitive Indian financial identifiers and PII from the input string.

    Preserves safe domain text, currency amounts (e.g., ₹500, Rs. 1000, 10,000),
    percentages, and mutual fund terminology while redacting personal details.

    Args:
        text: Input string potentially containing personal/financial identifiers.

    Returns:
        Sanitized string with redacted token placeholders.
    """
    if not text:
        return ""

    sanitized = text

    # 1. Emails
    sanitized = EMAIL_PATTERN.sub("[REDACTED_EMAIL]", sanitized)

    # 2. PANs
    sanitized = PAN_PATTERN.sub("[REDACTED_PAN]", sanitized)

    # 3. Credit/Debit Cards
    sanitized = CARD_PATTERN.sub("[REDACTED_CARD]", sanitized)

    # 4. Bank account with explicit context (e.g. "a/c no: 1234567890" -> "a/c no: [REDACTED_ACCOUNT]")
    def _replace_account_context(match: re.Match) -> str:
        full_match = match.group(0)
        account_digits = match.group(1)
        return full_match.replace(account_digits, "[REDACTED_ACCOUNT]")

    sanitized = BANK_ACC_CONTEXT_PATTERN.sub(_replace_account_context, sanitized)

    # 5. Standalone long bank accounts (12-18 digits not preceded by currency)
    sanitized = STANDALONE_BANK_ACC_PATTERN.sub("[REDACTED_ACCOUNT]", sanitized)

    # 6. Aadhaar numbers (spaced or continuous 12-digit)
    sanitized = AADHAAR_PATTERN.sub("[REDACTED_AADHAAR]", sanitized)

    # 7. Phone numbers
    sanitized = PHONE_PATTERN.sub("[REDACTED_PHONE]", sanitized)

    return sanitized


class PIISanitizer:
    """Convenience class wrapper around PII sanitization functions."""

    @staticmethod
    def sanitize(text: str) -> str:
        return sanitize_text(text)

    @staticmethod
    def detect(text: str) -> Dict[str, List[str]]:
        return detect_pii(text)

    @staticmethod
    def contains_pii(text: str) -> bool:
        return contains_pii(text)

