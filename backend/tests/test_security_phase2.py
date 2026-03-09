"""Phase 2 security tests: log redaction."""
import pytest
from security import redact_log_content


def test_redact_log_content_empty():
    assert redact_log_content("") == ""


def test_redact_log_content_masks_token():
    content = "2024-01-01 INFO HF_TOKEN=hf_abc123xyz"
    result = redact_log_content(content)
    assert "hf_abc123xyz" not in result
    assert "HF_TOKEN=" in result
    assert "***REDACTED***" in result


def test_redact_log_content_masks_password():
    content = "PASSWORD=secret123\nUSER=admin"
    result = redact_log_content(content)
    assert "secret123" not in result
    assert "***REDACTED***" in result
    assert "USER=admin" in result


def test_redact_log_content_masks_api_key():
    content = "API_KEY=sk-12345"
    assert "sk-12345" not in redact_log_content(content)
    assert "***REDACTED***" in redact_log_content(content)


def test_redact_log_content_preserves_normal_lines():
    content = "2024-01-01 INFO Model loaded successfully"
    assert redact_log_content(content) == content
