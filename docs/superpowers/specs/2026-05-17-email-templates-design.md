# Disseny: Plantilles HTML per a emails de MiroFish

**Data:** 2026-05-17
**Estat:** Aprovat

## Context

Els emails de registre (invitació) i de canvi de contrasenya de MiroFish envien text pla sense format. L'objectiu és substituir-los per plantilles HTML responsius amb branding propi, text pla alternatiu, i suport multiidioma via el sistema de traduccions existent.

## Abast

- `backend/app/services/email_service.py` — afegir funcions de construcció HTML i text pla
- `locales/ca.json`, `locales/en.json`, `locales/es.json` — afegir claus `email.*`

Cap canvi a models, migracions, ni API.

## Decisions de disseny

### Enfocament: plantilles inline a `email_service.py`

Les funcions `_build_*_html()` i `_build_*_plain()` s'escriuen directament al fitxer existent, seguint el patró d'OpenMAIC. Les cadenes de text s'externalitzen al sistema `t()` de `utils/locale.py` (ja existent). Cap fitxer nou ni dependència addicional.

Alternatives descartades: fitxers Jinja2 separats (overhead innecessari per dues plantilles) i text hardcoded (incompatible amb requisit multiidioma).

### Idioma

- Email d'**invitació**: `get_locale()` del context del request, que llegeix `Accept-Language` del navegador de l'admin que crea l'usuari.
- Email de **reset de contrasenya**: `get_locale()` del context del request `/forgot-password`, que llegeix `Accept-Language` del navegador de qui fa la sol·licitud.

`UserModel` no té camp `locale`; no s'afegeix en aquest àmbit.

### Branding

Estil minimalista/neutre:
- Capçalera: fons `#27272a` (gris antracita), nom "MiroFish" en blanc, subtítol en gris
- Botó CTA: fons `#27272a`, text blanc
- Fons general: `#f4f4f5`
- Targeta central: `#ffffff`, border-radius 8px, max-width 560px

## Estructura HTML

Idèntica per als dos tipus d'email:

```
┌─────────────────────────────────────────┐
│  Capçalera #27272a                      │
│    MiroFish  (blanc, negreta)           │
│    Subtítol (gris, mida petita)         │
├─────────────────────────────────────────┤
│  Cos (blanc, padding 40px)              │
│    Salutació h2                         │
│    Paràgraf(s) de cos                   │
│    [  Botó CTA  ]  (fons #27272a)       │
│    Nota TTL (gris petit)                │
├─────────────────────────────────────────┤
│  URL fallback (fons #f4f4f5)            │
│    "Si el botó no funciona..."          │
│    URL completa clicable                │
├─────────────────────────────────────────┤
│  Footer (línia separadora)              │
│    "Si no esperaves..." + peu de pàgina │
└─────────────────────────────────────────┘
```

## Canvis a `email_service.py`

### Funcions noves (privades)

```python
def _escape_html(s: str) -> str
    # Escapa &, <, >, ", ' per evitar XSS

def _build_invitation_html(name: str, accept_url: str, ttl_hours: int) -> str
def _build_invitation_plain(name: str, accept_url: str, ttl_hours: int) -> str

def _build_reset_html(email: str, reset_url: str, ttl_hours: int) -> str
def _build_reset_plain(email: str, reset_url: str, ttl_hours: int) -> str
```

### Modificació de funcions existents

`send_invitation_email(to_email, to_name, accept_url)`:
- Crida `_build_invitation_html()` i `_build_invitation_plain()`
- Passa `html=` a `_send()`

`send_reset_password_email(to_email, reset_url)`:
- Crida `_build_reset_html()` i `_build_reset_plain()`
- Passa `html=` a `_send()`

`_send(to_email, subject, body, html=None)`:
- Si `html` no és None, l'inclou al payload ACS: `content.html`
- Signatura: `_send(to_email: str, subject: str, body: str, html: str | None = None) -> bool`

### Seguretat

- `_escape_html()` s'aplica a totes les variables interpolades dins el HTML (`name`, `email`, URLs)
- Les URLs no s'escapen per al text pla (han de ser clicables)

## Claus de traducció noves

### Estructura als fitxers `ca.json`, `en.json`, `es.json`

```json
"email": {
  "common": {
    "urlFallbackLabel": "...",
    "footer": "MiroFish — Plataforma de simulació multi-agent amb IA"
  },
  "invitation": {
    "subject": "T'han convidat a MiroFish",
    "subtitle": "Plataforma de simulació multi-agent",
    "greeting": "Hola, {name}!",
    "body1": "...",
    "body2": "...",
    "cta": "Acceptar invitació",
    "ttlNotice": "Aquest enllaç és vàlid durant {hours} hores.",
    "ignore": "...",
    "plainBody": "..."
  },
  "passwordReset": {
    "subject": "MiroFish — Sol·licitud de canvi de contrasenya",
    "greeting": "Hola, {email}!",
    "body": "...",
    "cta": "Canviar la contrasenya",
    "ttlNotice": "Aquest enllaç és vàlid durant {hours} hores.",
    "ignore": "...",
    "plainCta": "Per canviar la contrasenya, accedeix a:"
  }
}
```

Les cadenes exactes s'adapten per a `en.json` i `es.json`.

## Fitxers afectats

| Fitxer | Tipus de canvi |
|--------|---------------|
| `backend/app/services/email_service.py` | Modificació (afegir funcions) |
| `locales/ca.json` | Modificació (afegir claus `email.*`) |
| `locales/en.json` | Modificació (afegir claus `email.*`) |
| `locales/es.json` | Modificació (afegir claus `email.*`) |

## Fora d'abast

- Camp `locale` a `UserModel`
- Canvis a l'API ni als endpoints d'auth
- Tests automatitzats (no n'hi ha per al servei d'email)
