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

logger = logging.getLogger('mirofish.email')


def send_invitation_email(to_email: str, to_name: str, accept_url: str) -> bool:
    subject = "Invitació a MiroFish"
    body = (
        f"Hola {to_name},\n\n"
        f"Has estat convidat/da a MiroFish.\n\n"
        f"Estableix la teva contrasenya accedint a:\n{accept_url}\n\n"
        f"Aquest enllaç caduca en {current_app.config['ACS_INVITATION_TTL_HOURS']} hores.\n"
    )
    return _send(to_email, subject, body)


def send_reset_password_email(to_email: str, reset_url: str) -> bool:
    subject = "Restabliment de contrasenya MiroFish"
    body = (
        f"Has sol·licitat restablir la contrasenya de MiroFish.\n\n"
        f"Accedeix a:\n{reset_url}\n\n"
        f"Aquest enllaç caduca en {current_app.config['ACS_RESET_PASSWORD_TTL_HOURS']} hora/es.\n"
        f"Si no has fet aquesta sol·licitud, ignora aquest missatge.\n"
    )
    return _send(to_email, subject, body)


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


def _send(to_email: str, subject: str, body: str) -> bool:
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

    payload = {
        "senderAddress": sender,
        "displayName": display_name,
        "recipients": {"to": [{"address": to_email}]},
        "content": {"subject": subject, "plainText": body},
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
