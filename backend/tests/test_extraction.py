"""Unit tests for the Claude-based AI extraction service (PRD §22)."""
import asyncio
import base64
import json
import os
import tempfile
from unittest.mock import MagicMock, patch

STORAGE = tempfile.mkdtemp()
os.environ.setdefault("STORAGE_PATH", STORAGE)
os.environ.setdefault("SECRET_KEY", "extraction-tests-secret-key-xyz")

import pytest

from app.services import ai_extraction


# ---------------------------------------------------------------------------
# Fixtures — fake Claude responses
# ---------------------------------------------------------------------------
def _fake_anthropic(response_text: str):
    """Build a mock anthropic.Anthropic client that returns response_text."""
    client = MagicMock()
    msg = MagicMock()
    msg.content = [MagicMock(text=response_text)]
    client.messages.create.return_value = msg
    return client


# A minimal valid 1×1 PNG (89 50 4e 47 …) — enough for base64 encoding paths
PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGNgAAIAAAUAAeImBZsAAAAASUVORK5CYII="
)


# ---------------------------------------------------------------------------
# Mock-mode behaviour (no API key)
# ---------------------------------------------------------------------------
def test_mock_mode_when_no_api_key():
    """Without ANTHROPIC_API_KEY, both extractors return deterministic mocks."""
    with patch.object(ai_extraction.settings, "ANTHROPIC_API_KEY", ""):
        rd = asyncio.run(ai_extraction.extract_rd_invoice(PNG_BYTES, "image/png"))
        vb = asyncio.run(ai_extraction.extract_vendor_bill(PNG_BYTES, "image/png"))
    assert rd["_mock"] is True
    assert rd["invoice_number"] == "MOCK-001"
    assert vb["_mock"] is True
    assert vb["vendor"] == "Sample Vendor Inc."


# ---------------------------------------------------------------------------
# Claude vision wire format
# ---------------------------------------------------------------------------
def test_rd_extraction_sends_base64_image_to_claude():
    payload = {
        "invoice_number": "12345",
        "invoice_date": "2026-06-01",
        "grand_total": 100.0,
        "lines": [{"line": "1", "item": "24514", "description": "X",
                   "price": 10.0, "cu": "C", "qty": 10, "total": 100.0,
                   "confidence": 0.97}],
    }
    fake_client = _fake_anthropic(json.dumps(payload))
    with patch.object(ai_extraction.settings, "ANTHROPIC_API_KEY", "test-key"), \
         patch("app.services.ai_extraction.anthropic.Anthropic", return_value=fake_client):
        result = asyncio.run(ai_extraction.extract_rd_invoice(PNG_BYTES, "image/png"))

    # Wire format assertions: image source must be base64 of the PNG bytes
    call = fake_client.messages.create.call_args.kwargs
    content = call["messages"][0]["content"]
    assert content[0]["type"] == "image"
    assert content[0]["source"]["type"] == "base64"
    assert content[0]["source"]["media_type"] == "image/png"
    assert content[0]["source"]["data"] == base64.standard_b64encode(PNG_BYTES).decode()
    assert content[1]["type"] == "text"
    assert "Restaurant Depot" in content[1]["text"]
    assert call["model"].startswith("claude-")
    # Result correctly parsed
    assert result["invoice_number"] == "12345"
    assert result["lines"][0]["item"] == "24514"


def test_vendor_bill_extraction_strips_markdown_fences():
    payload = {
        "vendor": "Globex Foods",
        "invoice_number": "INV-9",
        "invoice_date": "2026-06-05",
        "bill_type": "invoice",
        "header_confidence": {"vendor": 0.98, "invoice_number": 0.95, "invoice_date": 0.92},
        "lines": [{"bill_item_code": "GF-1", "description": "Tomato", "qty": 10,
                   "rate": 5.0, "total": 50.0, "confidence": 0.96,
                   "field_confidence": {"qty": 0.99, "rate": 0.96, "total": 0.98}}],
    }
    fenced = f"```json\n{json.dumps(payload)}\n```"
    fake_client = _fake_anthropic(fenced)
    with patch.object(ai_extraction.settings, "ANTHROPIC_API_KEY", "test-key"), \
         patch("app.services.ai_extraction.anthropic.Anthropic", return_value=fake_client):
        result = asyncio.run(ai_extraction.extract_vendor_bill(PNG_BYTES, "image/png"))
    assert result["vendor"] == "Globex Foods"
    assert result["lines"][0]["bill_item_code"] == "GF-1"


def test_extraction_returns_raw_on_invalid_json():
    fake_client = _fake_anthropic("this is not JSON at all")
    with patch.object(ai_extraction.settings, "ANTHROPIC_API_KEY", "test-key"), \
         patch("app.services.ai_extraction.anthropic.Anthropic", return_value=fake_client):
        result = asyncio.run(ai_extraction.extract_rd_invoice(PNG_BYTES, "image/jpeg"))
    assert "error" in result
    assert result["raw"] == "this is not JSON at all"


# ---------------------------------------------------------------------------
# Low-confidence flagging cascade
# ---------------------------------------------------------------------------
def test_flag_low_confidence_per_line_and_field():
    extracted = {
        "vendor": "ACME",
        "header_confidence": {"vendor": 0.92, "invoice_number": 0.4, "invoice_date": 0.99},
        "lines": [
            # High overall, low rate: only rate flagged, line marked needs_review
            {"description": "A", "qty": 1, "rate": 1.0, "total": 1.0,
             "confidence": 0.97, "field_confidence": {"rate": 0.5, "total": 0.99}},
            # Missing required qty → auto-flagged
            {"description": "B", "qty": None, "rate": 2.0, "total": 4.0,
             "confidence": 0.95, "field_confidence": {}},
            # Overall confidence low → needs_review
            {"description": "C", "qty": 3, "rate": 1.0, "total": 3.0,
             "confidence": 0.3, "field_confidence": {"rate": 0.95}},
        ],
    }
    out = ai_extraction.flag_low_confidence(extracted, threshold=0.9)

    assert out["header_needs_review"] == ["invoice_number"]
    assert out["lines"][0]["field_needs_review"] == ["rate"]
    assert out["lines"][0]["needs_review"] is True
    assert "qty" in out["lines"][1]["field_needs_review"]
    assert out["lines"][1]["needs_review"] is True
    assert out["lines"][2]["needs_review"] is True  # via overall confidence
    assert out["has_low_confidence"] is True


def test_flag_low_confidence_all_good():
    extracted = {
        "header_confidence": {"vendor": 0.99, "invoice_number": 0.99, "invoice_date": 0.99},
        "lines": [
            {"description": "A", "qty": 1, "rate": 1.0, "total": 1.0,
             "confidence": 0.99, "field_confidence": {"rate": 0.99, "total": 0.99}},
        ],
    }
    out = ai_extraction.flag_low_confidence(extracted, threshold=0.9)
    assert out["header_needs_review"] == []
    assert out["lines"][0]["needs_review"] is False
    assert out["lines"][0]["field_needs_review"] == []
    assert out["has_low_confidence"] is False


# ---------------------------------------------------------------------------
# Prompt contracts (PRD §22 / §13.4)
# ---------------------------------------------------------------------------
def test_prompts_pin_required_fields():
    # If these strings move, downstream review UI breaks — pin them here.
    rd = ai_extraction.RD_INVOICE_PROMPT
    vb = ai_extraction.VENDOR_BILL_PROMPT
    for token in ("invoice_number", "invoice_date", "grand_total", "lines", "confidence"):
        assert token in rd
    for token in ("header_confidence", "field_confidence", "individual_weights",
                  "bill_type", "credit_memo", "notes"):
        assert token in vb
