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

from ..utils.locale import t, get_locale

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
    lang = get_locale()
    return f"""<!DOCTYPE html>
<html lang="{lang}">
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
    lang = get_locale()
    return f"""<!DOCTYPE html>
<html lang="{lang}">
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
              <p style="margin:8px 0 0;color:#a1a1aa;font-size:13px;">{t('email.passwordReset.subtitle')}</p>
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
    ttl = current_app.config.get('ACS_INVITATION_TTL_HOURS', 48)
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
