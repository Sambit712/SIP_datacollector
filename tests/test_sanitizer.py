"""Unit tests for PII Sanitization & Data Masking Engine (Phase 0)."""

import pytest
from src.nlp.sanitizer import (
    sanitize_text,
    contains_pii,
    detect_pii,
    PAN_PATTERN,
    EMAIL_PATTERN,
    PHONE_PATTERN,
)


class TestPanSanitization:
    """Tests for Indian Permanent Account Number (PAN) detection and masking."""

    def test_standard_pan_masking(self):
        text = "My PAN number is ABCDE1234F registered with Groww KYC."
        sanitized = sanitize_text(text)
        assert "ABCDE1234F" not in sanitized
        assert "[REDACTED_PAN]" in sanitized
        assert sanitized == "My PAN number is [REDACTED_PAN] registered with Groww KYC."

    def test_lowercase_pan_masking(self):
        text = "kyc failed for pan abcde1234f on the app"
        sanitized = sanitize_text(text)
        assert "abcde1234f" not in sanitized
        assert "[REDACTED_PAN]" in sanitized

    def test_multiple_pans_in_single_string(self):
        text = "First account ABCDE1234F and joint holder FGHIJ5678K failed."
        sanitized = sanitize_text(text)
        assert "ABCDE1234F" not in sanitized
        assert "FGHIJ5678K" not in sanitized
        assert sanitized.count("[REDACTED_PAN]") == 2


class TestPhoneSanitization:
    """Tests for Indian mobile number detection and masking."""

    def test_ten_digit_mobile_starting_with_9(self):
        text = "Please call customer support at 9876543210 regarding my SIP."
        sanitized = sanitize_text(text)
        assert "9876543210" not in sanitized
        assert "[REDACTED_PHONE]" in sanitized

    def test_international_prefix_plus91(self):
        text = "My registered number is +91 9876543210 but OTP didn't arrive."
        sanitized = sanitize_text(text)
        assert "9876543210" not in sanitized
        assert "[REDACTED_PHONE]" in sanitized

    def test_hyphenated_phone_number(self):
        text = "Reach me at 98765-43210 for account recovery."
        sanitized = sanitize_text(text)
        assert "98765" not in sanitized or "[REDACTED_PHONE]" in sanitized

    def test_mobile_starting_with_other_indian_prefixes(self):
        for number in ["8123456789", "7012345678", "6312345678"]:
            text = f"Contact was {number} on record."
            assert contains_pii(text)
            assert "[REDACTED_PHONE]" in sanitize_text(text)


class TestEmailSanitization:
    """Tests for email address masking."""

    def test_standard_email(self):
        text = "Send my SIP statement to investor.rahul@gmail.com please."
        sanitized = sanitize_text(text)
        assert "investor.rahul@gmail.com" not in sanitized
        assert "[REDACTED_EMAIL]" in sanitized

    def test_corporate_email(self):
        text = "Support emailed me from support@groww.in with ticket #123."
        sanitized = sanitize_text(text)
        assert "support@groww.in" not in sanitized
        assert "[REDACTED_EMAIL]" in sanitized


class TestBankAccountSanitization:
    """Tests for bank account masking."""

    def test_contextual_bank_account(self):
        text = "My a/c no: 123456789012 was charged ₹295 for insufficient balance."
        sanitized = sanitize_text(text)
        assert "123456789012" not in sanitized
        assert "[REDACTED_ACCOUNT]" in sanitized
        # Preserves the penalty amount ₹295
        assert "₹295" in sanitized

    def test_standalone_long_account(self):
        text = "AutoPay failed for account number 50100234567890 at HDFC Bank."
        sanitized = sanitize_text(text)
        assert "50100234567890" not in sanitized
        assert "[REDACTED_ACCOUNT]" in sanitized


class TestCardAndAadhaarSanitization:
    """Tests for credit cards and Aadhaar identifiers."""

    def test_payment_card_redaction(self):
        text = "Card used was 4111 2222 3333 4444 for initial mandate."
        sanitized = sanitize_text(text)
        assert "4111 2222 3333 4444" not in sanitized
        assert "[REDACTED_CARD]" in sanitized

    def test_aadhaar_redaction(self):
        text = "Aadhaar e-sign 2345 6789 0123 failed during verification."
        sanitized = sanitize_text(text)
        assert "2345 6789 0123" not in sanitized
        assert "[REDACTED_AADHAAR]" in sanitized


class TestDomainPreservation:
    """Verifies that legitimate financial figures, mutual fund names, and normal text are NOT corrupted."""

    def test_preserves_sip_amounts(self):
        text = "I set up a monthly SIP of ₹500 on 5th of every month, later increased to ₹2,500."
        sanitized = sanitize_text(text)
        assert "₹500" in sanitized
        assert "₹2,500" in sanitized
        assert contains_pii(text) is False

    def test_preserves_percentages_and_nav(self):
        text = "My portfolio return dropped by -4.5% when NAV went from 145.20 to 138.65."
        sanitized = sanitize_text(text)
        assert "-4.5%" in sanitized
        assert "145.20" in sanitized
        assert contains_pii(text) is False

    def test_preserves_fund_names_and_jargon(self):
        text = "Parag Parikh Flexi Cap Fund Regular Growth folio 1234567 had 12.3% XIRR."
        sanitized = sanitize_text(text)
        assert "Parag Parikh Flexi Cap Fund" in sanitized
        assert "12.3%" in sanitized
        assert "XIRR" in sanitized


class TestDetectionHelper:
    """Tests for detect_pii returning accurate entity dictionaries."""

    def test_detect_multiple_entities(self):
        text = "User rahul@test.com with PAN ABCDE1234F and phone 9876543210 encountered error."
        detected = detect_pii(text)
        assert "email" in detected
        assert "pan" in detected
        assert "phone" in detected
        assert "rahul@test.com" in detected["email"]
        assert "ABCDE1234F" in detected["pan"]

