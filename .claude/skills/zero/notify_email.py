#!/usr/bin/env python3
"""Send a plain-text notification email for zero's PR watch.

Standalone (no Django needed) so it works inside the watch loop regardless of the
app runtime. Credentials come from the environment or the project's gitignored
`.env` (auto-loaded) — never hardcode a secret here; this file is git-tracked.
The body comes from a CLI arg or stdin.

Config keys (env var, or a line in the project `.env`):
  ZERO_SMTP_HOST       default "smtp.gmail.com"
  ZERO_SMTP_PORT       default 587 (STARTTLS)
  ZERO_SMTP_USER       SMTP login; falls back to "user_email"
  ZERO_SMTP_PASSWORD   SMTP password / app password; falls back to "user_password"
  ZERO_NOTIFY_TO       recipient; default "bijay.shrestha2@maitriservices.com"

Usage:
  python notify_email.py "Subject line" "Body text"
  echo "Body text" | python notify_email.py "Subject line"

Exit codes:
  0  sent
  2  no SMTP credentials configured (caller should fall back to desktop-only)
  1  send failed (network/auth/etc.)
"""

import os
import smtplib
import sys
from email.message import EmailMessage
from pathlib import Path

# Project root: notify_email.py -> zero -> skills -> .claude -> <root>
PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _load_dotenv(path: Path) -> None:
    """Populate os.environ from a gitignored `.env` (real env always wins).

    Tolerant of the project's `key = value` spacing and surrounding quotes.
    """
    if not path.is_file():
        return
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def _first_env(*names: str, default: str | None = None) -> str | None:
    """Return the first set value among the given env-var NAMES, else default."""
    for name in names:
        value = os.environ.get(name)
        if value:
            return value
    return default


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: notify_email.py <subject> [body]", file=sys.stderr)
        return 1

    _load_dotenv(PROJECT_ROOT / ".env")

    subject = sys.argv[1]
    body = sys.argv[2] if len(sys.argv) > 2 else sys.stdin.read()

    host = _first_env("ZERO_SMTP_HOST", default="smtp.gmail.com")
    port = int(_first_env("ZERO_SMTP_PORT", default="587") or "587")
    user = _first_env("ZERO_SMTP_USER", "user_email")
    password = _first_env("ZERO_SMTP_PASSWORD", "user_password")
    to_addr = _first_env("ZERO_NOTIFY_TO", default="bijay.shrestha2@maitriservices.com")

    if not user or not password:
        print(
            "No SMTP credentials. Set ZERO_SMTP_USER/ZERO_SMTP_PASSWORD (or "
            "user_email/user_password) in the environment or .env. Skipping email.",
            file=sys.stderr,
        )
        return 2

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = user
    msg["To"] = to_addr
    msg.set_content(body)

    try:
        with smtplib.SMTP(host, port, timeout=30) as server:
            server.starttls()
            server.login(user, password)
            server.send_message(msg)
    except Exception as exc:  # noqa: BLE001 - report and let caller fall back
        print(f"Email send failed: {exc}", file=sys.stderr)
        return 1

    print(f"Notification emailed to {to_addr}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
