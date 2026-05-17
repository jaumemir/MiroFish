"""Tests per a les funcions de construcció HTML de email_service."""
import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture
def app():
    with patch('backend.app.db.init_db'):
        from backend.app import create_app
        application = create_app()
    application.config['TESTING'] = True
    return application


@pytest.fixture
def app_ctx(app):
    with app.app_context():
        yield app


# ── Invitation HTML ────────────────────────────────────────────────────────

def test_invitation_html_contains_name(app_ctx):
    from backend.app.services.email_service import _build_invitation_html
    html = _build_invitation_html("Anna García", "https://example.com/accept/abc", 48)
    assert "Anna" in html

def test_invitation_html_contains_cta_url(app_ctx):
    from backend.app.services.email_service import _build_invitation_html
    url = "https://example.com/accept/abc123"
    html = _build_invitation_html("Test User", url, 48)
    assert url in html

def test_invitation_html_contains_ttl(app_ctx):
    from backend.app.services.email_service import _build_invitation_html
    html = _build_invitation_html("Test User", "https://example.com/x", 72)
    assert "72" in html

def test_invitation_html_escapes_xss(app_ctx):
    from backend.app.services.email_service import _build_invitation_html
    html = _build_invitation_html("<script>alert(1)</script>", "https://example.com/x", 48)
    assert "<script>" not in html
    assert "&lt;script&gt;" in html

def test_invitation_html_is_valid_html_structure(app_ctx):
    from backend.app.services.email_service import _build_invitation_html
    html = _build_invitation_html("Test", "https://example.com/x", 48)
    assert html.strip().startswith("<!DOCTYPE html>")
    assert "</html>" in html

# ── Invitation Plain Text ──────────────────────────────────────────────────

def test_invitation_plain_contains_url(app_ctx):
    from backend.app.services.email_service import _build_invitation_plain
    url = "https://example.com/accept/xyz"
    plain = _build_invitation_plain("Test User", url, 48)
    assert url in plain

def test_invitation_plain_contains_ttl(app_ctx):
    from backend.app.services.email_service import _build_invitation_plain
    plain = _build_invitation_plain("Test User", "https://example.com/x", 24)
    assert "24" in plain

def test_invitation_plain_no_html_tags(app_ctx):
    from backend.app.services.email_service import _build_invitation_plain
    plain = _build_invitation_plain("Test User", "https://example.com/x", 48)
    assert "<" not in plain
    assert ">" not in plain

# ── Reset HTML ─────────────────────────────────────────────────────────────

def test_reset_html_contains_email(app_ctx):
    from backend.app.services.email_service import _build_reset_html
    html = _build_reset_html("user@example.com", "https://example.com/reset/abc", 1)
    assert "user@example.com" in html

def test_reset_html_contains_cta_url(app_ctx):
    from backend.app.services.email_service import _build_reset_html
    url = "https://example.com/reset/abc123"
    html = _build_reset_html("user@example.com", url, 1)
    assert url in html

def test_reset_html_contains_ttl(app_ctx):
    from backend.app.services.email_service import _build_reset_html
    html = _build_reset_html("user@example.com", "https://example.com/x", 777)
    assert "777" in html

def test_reset_html_escapes_xss_in_email(app_ctx):
    from backend.app.services.email_service import _build_reset_html
    html = _build_reset_html("<b>bad</b>@example.com", "https://example.com/x", 1)
    assert "<b>" not in html
    assert "&lt;b&gt;" in html

def test_reset_html_is_valid_html_structure(app_ctx):
    from backend.app.services.email_service import _build_reset_html
    html = _build_reset_html("user@example.com", "https://example.com/x", 1)
    assert html.strip().startswith("<!DOCTYPE html>")
    assert "</html>" in html

# ── Reset Plain Text ───────────────────────────────────────────────────────

def test_reset_plain_contains_url(app_ctx):
    from backend.app.services.email_service import _build_reset_plain
    url = "https://example.com/reset/xyz"
    plain = _build_reset_plain("user@example.com", url, 1)
    assert url in plain

def test_reset_plain_no_html_tags(app_ctx):
    from backend.app.services.email_service import _build_reset_plain
    plain = _build_reset_plain("user@example.com", "https://example.com/x", 1)
    assert "<" not in plain
    assert ">" not in plain

# ── _escape_html ───────────────────────────────────────────────────────────

def test_escape_html_ampersand(app_ctx):
    from backend.app.services.email_service import _escape_html
    assert _escape_html("a & b") == "a &amp; b"

def test_escape_html_less_than(app_ctx):
    from backend.app.services.email_service import _escape_html
    assert _escape_html("<script>") == "&lt;script&gt;"

def test_escape_html_quotes(app_ctx):
    from backend.app.services.email_service import _escape_html
    assert _escape_html('"hello"') == "&quot;hello&quot;"

def test_escape_html_apostrophe(app_ctx):
    from backend.app.services.email_service import _escape_html
    assert _escape_html("it's") == "it&#39;s"

def test_escape_html_clean_string_unchanged(app_ctx):
    from backend.app.services.email_service import _escape_html
    assert _escape_html("Hello World") == "Hello World"
