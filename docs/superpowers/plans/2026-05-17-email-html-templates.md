# Email HTML Templates Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Substituir els emails de text pla de MiroFish (invitació i reset de contrasenya) per plantilles HTML responsius amb branding gris antracita i suport multiidioma via `t()`.

**Architecture:** Les funcions `_build_*_html()` i `_build_*_plain()` s'afegeixen a `email_service.py`. Les cadenes de text s'externalitzen als fitxers `locales/*.json` amb claus `email.*`. `_send()` rep un paràmetre opcional `html`. Cap fitxer nou ni canvi d'API.

**Tech Stack:** Python 3.11+, Flask, `utils/locale.py` (`t()`, `get_locale()`), Azure Communication Services REST API.

---

## Fitxers afectats

| Fitxer | Canvi |
|--------|-------|
| `locales/ca.json` | Afegir claus `email.*` (català) |
| `locales/en.json` | Afegir claus `email.*` (anglès) |
| `locales/es.json` | Afegir claus `email.*` + `forgotPassword.*` + `resetPassword.*` (castellà, absents) |
| `backend/app/services/email_service.py` | Afegir `_escape_html`, `_build_*_html`, `_build_*_plain`; modificar `_send` i les dues funcions públiques |
| `backend/tests/test_email_service.py` | Fitxer nou amb tests de les funcions de construcció |

---

### Task 1: Afegir claus `email.*` a `locales/ca.json`

**Files:**
- Modify: `locales/ca.json`

- [ ] **Pas 1: Obrir `locales/ca.json` i afegir la clau `email` al final del JSON**

  Afegir just **abans** del `}` de tancament final (és un objecte JSON, cal posar coma darrere de l'última clau existent):

  ```json
  "email": {
    "common": {
      "urlFallbackLabel": "Si el botó no funciona, copia aquest URL al navegador:",
      "footer": "MiroFish — Plataforma de simulació multi-agent amb IA"
    },
    "invitation": {
      "subject": "T'han convidat a MiroFish",
      "subtitle": "Plataforma de simulació multi-agent",
      "greeting": "Hola, {name}!",
      "body1": "Has estat convidat/da a MiroFish, la plataforma de simulació multi-agent amb intel·ligència artificial.",
      "body2": "Fes clic al botó per establir la teva contrasenya i activar el compte.",
      "cta": "Acceptar invitació",
      "ttlNotice": "Aquest enllaç és vàlid durant {hours} hores.",
      "ignore": "Si no esperaves aquesta invitació, pots ignorar aquest missatge.",
      "plainBody": "Has estat convidat/da a MiroFish. Per completar el teu registre, accedeix a:"
    },
    "passwordReset": {
      "subject": "MiroFish — Sol·licitud de canvi de contrasenya",
      "greeting": "Hola, {email}!",
      "body": "Hem rebut una sol·licitud per canviar la contrasenya del teu compte de MiroFish. Si no has estat tu, pots ignorar aquest correu i la contrasenya no canviarà.",
      "cta": "Canviar la contrasenya",
      "ttlNotice": "Aquest enllaç és vàlid durant {hours} hores.",
      "ignore": "Si no has sol·licitat cap canvi de contrasenya, pots ignorar aquest missatge.",
      "plainCta": "Per canviar la contrasenya, accedeix a:"
    }
  }
  ```

- [ ] **Pas 2: Verificar que el JSON és vàlid**

  ```bash
  python3 -c "import json; json.load(open('locales/ca.json')); print('OK')"
  ```
  Esperat: `OK`

- [ ] **Pas 3: Commit**

  ```bash
  git add locales/ca.json
  git commit -m "feat(email): afegir claus email.* a ca.json"
  ```

---

### Task 2: Afegir claus `email.*` a `locales/en.json`

**Files:**
- Modify: `locales/en.json`

- [ ] **Pas 1: Afegir la clau `email` a `locales/en.json`**

  ```json
  "email": {
    "common": {
      "urlFallbackLabel": "If the button doesn't work, copy this URL into your browser:",
      "footer": "MiroFish — Multi-agent simulation platform with AI"
    },
    "invitation": {
      "subject": "You've been invited to MiroFish",
      "subtitle": "Multi-agent simulation platform",
      "greeting": "Hello, {name}!",
      "body1": "You have been invited to MiroFish, the multi-agent simulation platform with artificial intelligence.",
      "body2": "Click the button below to set your password and activate your account.",
      "cta": "Accept invitation",
      "ttlNotice": "This link is valid for {hours} hours.",
      "ignore": "If you were not expecting this invitation, you can ignore this message.",
      "plainBody": "You have been invited to MiroFish. To complete your registration, go to:"
    },
    "passwordReset": {
      "subject": "MiroFish — Password reset request",
      "greeting": "Hello, {email}!",
      "body": "We received a request to reset the password for your MiroFish account. If this was not you, you can ignore this email and your password will not change.",
      "cta": "Reset password",
      "ttlNotice": "This link is valid for {hours} hours.",
      "ignore": "If you did not request a password reset, you can ignore this message.",
      "plainCta": "To reset your password, go to:"
    }
  }
  ```

- [ ] **Pas 2: Verificar JSON vàlid**

  ```bash
  python3 -c "import json; json.load(open('locales/en.json')); print('OK')"
  ```
  Esperat: `OK`

- [ ] **Pas 3: Commit**

  ```bash
  git add locales/en.json
  git commit -m "feat(email): afegir claus email.* a en.json"
  ```

---

### Task 3: Afegir claus a `locales/es.json`

**Files:**
- Modify: `locales/es.json`

**Nota:** `es.json` no té `forgotPassword` ni `resetPassword` (a diferència de `ca.json` i `en.json`). Cal afegir-les totes tres: `email`, `forgotPassword` i `resetPassword`.

- [ ] **Pas 1: Verificar claus absents**

  ```bash
  python3 -c "
  import json
  d = json.load(open('locales/es.json'))
  print('forgotPassword' in d, 'resetPassword' in d, 'email' in d)
  "
  ```
  Esperat: `False False False`

- [ ] **Pas 2: Afegir les tres claus a `locales/es.json`**

  ```json
  "forgotPassword": {
    "title": "Contraseña olvidada",
    "subtitle": "Introduce tu correo y te enviaremos un enlace para restablecerla.",
    "submit": "Enviar enlace de restablecimiento",
    "sent": "Si existe una cuenta con ese correo, recibirás un enlace de restablecimiento en breve."
  },
  "resetPassword": {
    "title": "Restablecer contraseña",
    "newPassword": "Nueva contraseña",
    "confirmPassword": "Confirma la contraseña",
    "submit": "Establecer nueva contraseña",
    "done": "Contraseña actualizada. Ya puedes iniciar sesión.",
    "goToLogin": "Ir al inicio de sesión",
    "invalidToken": "Este enlace no es válido o ha caducado.",
    "passwordMismatch": "Las contraseñas no coinciden."
  },
  "email": {
    "common": {
      "urlFallbackLabel": "Si el botón no funciona, copia esta URL en tu navegador:",
      "footer": "MiroFish — Plataforma de simulación multi-agente con IA"
    },
    "invitation": {
      "subject": "Te han invitado a MiroFish",
      "subtitle": "Plataforma de simulación multi-agente",
      "greeting": "¡Hola, {name}!",
      "body1": "Has sido invitado/a a MiroFish, la plataforma de simulación multi-agente con inteligencia artificial.",
      "body2": "Haz clic en el botón para establecer tu contraseña y activar la cuenta.",
      "cta": "Aceptar invitación",
      "ttlNotice": "Este enlace es válido durante {hours} horas.",
      "ignore": "Si no esperabas esta invitación, puedes ignorar este mensaje.",
      "plainBody": "Has sido invitado/a a MiroFish. Para completar tu registro, accede a:"
    },
    "passwordReset": {
      "subject": "MiroFish — Solicitud de cambio de contraseña",
      "greeting": "¡Hola, {email}!",
      "body": "Hemos recibido una solicitud para cambiar la contraseña de tu cuenta de MiroFish. Si no has sido tú, puedes ignorar este correo y la contraseña no cambiará.",
      "cta": "Cambiar la contraseña",
      "ttlNotice": "Este enlace es válido durante {hours} horas.",
      "ignore": "Si no has solicitado ningún cambio de contraseña, puedes ignorar este mensaje.",
      "plainCta": "Para cambiar la contraseña, accede a:"
    }
  }
  ```

- [ ] **Pas 3: Verificar JSON vàlid**

  ```bash
  python3 -c "import json; json.load(open('locales/es.json')); print('OK')"
  ```
  Esperat: `OK`

- [ ] **Pas 4: Commit**

  ```bash
  git add locales/es.json
  git commit -m "feat(email): afegir claus email.* i traduccions manquants a es.json"
  ```

---

### Task 4: Escriure tests per a les funcions de construcció HTML

**Files:**
- Create: `backend/tests/test_email_service.py`

Els tests verifiquen les funcions privades de construcció directament, sense necessitat d'enviar emails reals. Fan servir el context d'aplicació Flask per tenir accés a `t()`.

- [ ] **Pas 1: Crear `backend/tests/test_email_service.py`**

  ```python
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
      html = _build_reset_html("user@example.com", "https://example.com/x", 2)
      assert "2" in html

  def test_reset_html_escapes_xss_in_email(app_ctx):
      from backend.app.services.email_service import _build_reset_html
      html = _build_reset_html("<b>bad</b>@example.com", "https://example.com/x", 1)
      assert "<b>" not in html

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
  ```

- [ ] **Pas 2: Executar tests per verificar que fallen (les funcions no existeixen encara)**

  ```bash
  cd /home/ubuntu/dev/MiroFish && uv run pytest backend/tests/test_email_service.py -v 2>&1 | head -40
  ```
  Esperat: errors d'importació (`ImportError` o `AttributeError`) — les funcions `_build_*` no existeixen encara.

- [ ] **Pas 3: Commit dels tests**

  ```bash
  git add backend/tests/test_email_service.py
  git commit -m "test(email): tests per a funcions build HTML/plain de email_service"
  ```

---

### Task 5: Implementar les funcions a `email_service.py`

**Files:**
- Modify: `backend/app/services/email_service.py`

- [ ] **Pas 1: Substituir completament `email_service.py` per la versió amb HTML**

  ```python
  """Email service: ACS REST API (HMAC-SHA256) amb dev fallback (log a consola)."""
  import base64
  import hashlib
  import hmac
  import json
  import logging
  import uuid
  from datetime import datetime, timezone
  from urllib.parse import urlparse
  from urllib.request import Request, urlopen

  from flask import current_app

  from ..utils.locale import t

  logger = logging.getLogger('mirofish.email')


  # ── Helpers ────────────────────────────────────────────────────────────────

  def _escape_html(s: str) -> str:
      return (
          s.replace('&', '&amp;')
           .replace('<', '&lt;')
           .replace('>', '&gt;')
           .replace('"', '&quot;')
           .replace("'", '&#39;')
      )


  # ── Templates: invitació ───────────────────────────────────────────────────

  def _build_invitation_html(name: str, accept_url: str, ttl_hours: int) -> str:
      safe_name = _escape_html(name)
      safe_url = _escape_html(accept_url)
      hours = str(ttl_hours)
      return f"""<!DOCTYPE html>
  <html lang="ca">
  <head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MiroFish</title>
  </head>
  <body style="margin:0;padding:0;background-color:#f4f4f5;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">
    <table width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color:#f4f4f5;padding:40px 0;">
      <tr>
        <td align="center">
          <table width="560" cellpadding="0" cellspacing="0" border="0" style="background-color:#ffffff;border-radius:8px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,0.1);">

            <!-- Header -->
            <tr>
              <td style="background-color:#27272a;padding:32px 40px;text-align:center;">
                <h1 style="margin:0;color:#ffffff;font-size:24px;font-weight:700;letter-spacing:-0.5px;">MiroFish</h1>
                <p style="margin:8px 0 0;color:#a1a1aa;font-size:13px;">{t('email.invitation.subtitle')}</p>
              </td>
            </tr>

            <!-- Body -->
            <tr>
              <td style="padding:40px 40px 32px;">
                <h2 style="margin:0 0 16px;color:#18181b;font-size:20px;font-weight:600;">{t('email.invitation.greeting', name=safe_name)}</h2>
                <p style="margin:0 0 24px;color:#52525b;font-size:15px;line-height:1.6;">
                  {t('email.invitation.body1')}
                </p>
                <p style="margin:0 0 32px;color:#52525b;font-size:15px;line-height:1.6;">
                  {t('email.invitation.body2')}
                </p>

                <!-- CTA -->
                <table cellpadding="0" cellspacing="0" border="0" width="100%">
                  <tr>
                    <td align="center">
                      <a href="{safe_url}"
                         style="display:inline-block;background-color:#27272a;color:#ffffff;text-decoration:none;font-size:15px;font-weight:600;padding:14px 32px;border-radius:6px;letter-spacing:0.2px;">
                        {t('email.invitation.cta')}
                      </a>
                    </td>
                  </tr>
                </table>

                <!-- TTL -->
                <p style="margin:32px 0 0;color:#a1a1aa;font-size:13px;text-align:center;">
                  {t('email.invitation.ttlNotice', hours=hours)}
                </p>
              </td>
            </tr>

            <!-- Fallback URL -->
            <tr>
              <td style="padding:0 40px 32px;">
                <div style="background-color:#f4f4f5;border-radius:6px;padding:16px;">
                  <p style="margin:0 0 8px;color:#71717a;font-size:12px;">{t('email.common.urlFallbackLabel')}</p>
                  <p style="margin:0;font-size:12px;word-break:break-all;">
                    <a href="{safe_url}" style="color:#27272a;">{safe_url}</a>
                  </p>
                </div>
              </td>
            </tr>

            <!-- Footer -->
            <tr>
              <td style="padding:24px 40px;border-top:1px solid #f4f4f5;text-align:center;">
                <p style="margin:0;color:#a1a1aa;font-size:12px;">{t('email.invitation.ignore')}</p>
                <p style="margin:8px 0 0;color:#a1a1aa;font-size:12px;">{t('email.common.footer')}</p>
              </td>
            </tr>

          </table>
        </td>
      </tr>
    </table>
  </body>
  </html>"""


  def _build_invitation_plain(name: str, accept_url: str, ttl_hours: int) -> str:
      hours = str(ttl_hours)
      return (
          f"{t('email.invitation.greeting', name=name)}\n\n"
          f"{t('email.invitation.plainBody')}\n"
          f"{accept_url}\n\n"
          f"{t('email.invitation.ttlNotice', hours=hours)}\n\n"
          f"{t('email.invitation.ignore')}\n\n"
          f"{t('email.common.footer')}\n"
      )


  # ── Templates: reset de contrasenya ───────────────────────────────────────

  def _build_reset_html(email: str, reset_url: str, ttl_hours: int) -> str:
      safe_email = _escape_html(email)
      safe_url = _escape_html(reset_url)
      hours = str(ttl_hours)
      return f"""<!DOCTYPE html>
  <html lang="ca">
  <head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MiroFish</title>
  </head>
  <body style="margin:0;padding:0;background-color:#f4f4f5;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">
    <table width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color:#f4f4f5;padding:40px 0;">
      <tr>
        <td align="center">
          <table width="560" cellpadding="0" cellspacing="0" border="0" style="background-color:#ffffff;border-radius:8px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,0.1);">

            <!-- Header -->
            <tr>
              <td style="background-color:#27272a;padding:32px 40px;text-align:center;">
                <h1 style="margin:0;color:#ffffff;font-size:24px;font-weight:700;letter-spacing:-0.5px;">MiroFish</h1>
              </td>
            </tr>

            <!-- Body -->
            <tr>
              <td style="padding:40px 40px 32px;">
                <h2 style="margin:0 0 16px;color:#18181b;font-size:20px;font-weight:600;">{t('email.passwordReset.greeting', email=safe_email)}</h2>
                <p style="margin:0 0 32px;color:#52525b;font-size:15px;line-height:1.6;">
                  {t('email.passwordReset.body')}
                </p>

                <!-- CTA -->
                <table cellpadding="0" cellspacing="0" border="0" width="100%">
                  <tr>
                    <td align="center">
                      <a href="{safe_url}"
                         style="display:inline-block;background-color:#27272a;color:#ffffff;text-decoration:none;font-size:15px;font-weight:600;padding:14px 32px;border-radius:6px;letter-spacing:0.2px;">
                        {t('email.passwordReset.cta')}
                      </a>
                    </td>
                  </tr>
                </table>

                <!-- TTL -->
                <p style="margin:32px 0 0;color:#a1a1aa;font-size:13px;text-align:center;">
                  {t('email.passwordReset.ttlNotice', hours=hours)}
                </p>
              </td>
            </tr>

            <!-- Fallback URL -->
            <tr>
              <td style="padding:0 40px 32px;">
                <div style="background-color:#f4f4f5;border-radius:6px;padding:16px;">
                  <p style="margin:0 0 8px;color:#71717a;font-size:12px;">{t('email.common.urlFallbackLabel')}</p>
                  <p style="margin:0;font-size:12px;word-break:break-all;">
                    <a href="{safe_url}" style="color:#27272a;">{safe_url}</a>
                  </p>
                </div>
              </td>
            </tr>

            <!-- Footer -->
            <tr>
              <td style="padding:24px 40px;border-top:1px solid #f4f4f5;text-align:center;">
                <p style="margin:0;color:#a1a1aa;font-size:12px;">{t('email.passwordReset.ignore')}</p>
                <p style="margin:8px 0 0;color:#a1a1aa;font-size:12px;">{t('email.common.footer')}</p>
              </td>
            </tr>

          </table>
        </td>
      </tr>
    </table>
  </body>
  </html>"""


  def _build_reset_plain(email: str, reset_url: str, ttl_hours: int) -> str:
      hours = str(ttl_hours)
      return (
          f"{t('email.passwordReset.greeting', email=email)}\n\n"
          f"{t('email.passwordReset.body')}\n\n"
          f"{t('email.passwordReset.plainCta')}\n"
          f"{reset_url}\n\n"
          f"{t('email.passwordReset.ttlNotice', hours=hours)}\n\n"
          f"{t('email.passwordReset.ignore')}\n\n"
          f"{t('email.common.footer')}\n"
      )


  # ── Funcions públiques ─────────────────────────────────────────────────────

  def send_invitation_email(to_email: str, to_name: str, accept_url: str) -> bool:
      ttl = current_app.config['ACS_INVITATION_TTL_HOURS']
      subject = t('email.invitation.subject')
      html = _build_invitation_html(to_name, accept_url, ttl)
      plain = _build_invitation_plain(to_name, accept_url, ttl)
      return _send(to_email, subject, plain, html=html)


  def send_reset_password_email(to_email: str, reset_url: str) -> bool:
      ttl = current_app.config.get('ACS_RESET_PASSWORD_TTL_HOURS', 1)
      subject = t('email.passwordReset.subject')
      html = _build_reset_html(to_email, reset_url, ttl)
      plain = _build_reset_plain(to_email, reset_url, ttl)
      return _send(to_email, subject, plain, html=html)


  # ── ACS internals ──────────────────────────────────────────────────────────

  def _build_acs_headers(endpoint: str, access_key: str, body_bytes: bytes) -> dict:
      content_hash = base64.b64encode(
          hashlib.sha256(body_bytes).digest()
      ).decode()

      date = datetime.now(timezone.utc).strftime('%a, %d %b %Y %H:%M:%S GMT')
      host = urlparse(endpoint).hostname
      path = '/emails:send?api-version=2023-03-31'

      string_to_sign = f"POST\n{path}\n{date};{host};{content_hash}"
      key_bytes = base64.b64decode(access_key)
      signature = base64.b64encode(
          hmac.new(key_bytes, string_to_sign.encode('utf-8'), hashlib.sha256).digest()
      ).decode()

      return {
          'x-ms-date': date,
          'x-ms-content-sha256': content_hash,
          'Content-Type': 'application/json',
          'Authorization': (
              f'HMAC-SHA256 SignedHeaders=x-ms-date;host;x-ms-content-sha256'
              f'&Signature={signature}'
          ),
          'repeatability-request-id': str(uuid.uuid4()),
          'repeatability-first-sent': date,
      }


  def _send(to_email: str, subject: str, body: str, html: str | None = None) -> bool:
      endpoint = current_app.config.get('ACS_ENDPOINT', '')
      access_key = current_app.config.get('ACS_ACCESS_KEY', '')
      sender = current_app.config.get('ACS_SENDER_ADDRESS', '')
      display_name = current_app.config.get('ACS_SENDER_DISPLAY_NAME', '')

      if not endpoint or not access_key:
          logger.warning(
              "[EMAIL DEV — ACS no configurat]\n"
              f"  To:      {to_email}\n"
              f"  Subject: {subject}\n"
              f"  Body:\n{body}"
          )
          return True

      content: dict = {"subject": subject, "plainText": body}
      if html is not None:
          content["html"] = html

      payload = {
          "senderAddress": sender,
          "displayName": display_name,
          "recipients": {"to": [{"address": to_email}]},
          "content": content,
      }
      body_bytes = json.dumps(payload).encode('utf-8')
      headers = _build_acs_headers(endpoint, access_key, body_bytes)
      url = f"{endpoint.rstrip('/')}/emails:send?api-version=2023-03-31"

      try:
          req = Request(url, data=body_bytes, headers=headers, method='POST')
          with urlopen(req) as resp:
              if resp.status != 202:
                  logger.error(f"ACS returned {resp.status} for {to_email}")
                  return False
          logger.info(f"Email enviat via ACS a {to_email}")
          return True
      except Exception as exc:
          logger.error(f"ACS send failed to {to_email}: {exc}")
          return False
  ```

- [ ] **Pas 2: Executar els tests i verificar que passen tots**

  ```bash
  cd /home/ubuntu/dev/MiroFish && uv run pytest backend/tests/test_email_service.py -v
  ```
  Esperat: tots els tests en verd (`PASSED`).

- [ ] **Pas 3: Executar la suite completa de tests per detectar regressions**

  ```bash
  cd /home/ubuntu/dev/MiroFish && uv run pytest backend/tests/ -v 2>&1 | tail -20
  ```
  Esperat: cap test que passava abans deixa de passar.

- [ ] **Pas 4: Commit**

  ```bash
  git add backend/app/services/email_service.py
  git commit -m "feat(email): plantilles HTML responsius per a invitació i reset contrasenya"
  ```

---

## Self-Review

**Cobertura del spec:**
- ✅ Plantilles HTML per invitació i reset
- ✅ Text pla alternatiu per ambdues
- ✅ Branding gris antracita `#27272a`
- ✅ `_escape_html()` amb protecció XSS
- ✅ `_send()` accepta `html` opcional
- ✅ Traduccions `ca.json`, `en.json`, `es.json`
- ✅ `es.json` rep també `forgotPassword` i `resetPassword` que li mancaven
- ✅ Idioma via `t()` / `get_locale()` del request en curs

**Consistència de signatures:**
- `_build_invitation_html(name, accept_url, ttl_hours)` — consistent a tests i implementació
- `_build_invitation_plain(name, accept_url, ttl_hours)` — consistent
- `_build_reset_html(email, reset_url, ttl_hours)` — consistent
- `_build_reset_plain(email, reset_url, ttl_hours)` — consistent
- `_send(to_email, subject, body, html=None)` — consistent amb les crides des de les funcions públiques

**Placeholders:** cap TBD ni TODO.
