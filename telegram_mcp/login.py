"""Log in to a file session (TELEGRAM_SESSION_NAME) interactively.

Fork addition (sgorblex/telegram-mcp). Upstream's generator prints a session
string for an .env file; a server holding a persistent SQLite session would then
need ``telegram-mcp-migrate-session`` and the string would sit in the env file in
between. This writes the file session directly, reusing the generator's QR and
phone flows.

    telegram-mcp-login [--phone]
"""

from __future__ import annotations

import argparse
import os
import sys

from telethon.sync import TelegramClient

from session_string_generator import _harden_stdio, _phone_login, _qr_login
from telegram_mcp.client_identity import client_identity_kwargs


def main() -> None:
    _harden_stdio()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--phone", action="store_true", help="Phone + code instead of QR")
    args = parser.parse_args()

    session_name = os.getenv("TELEGRAM_SESSION_NAME")
    api_id = os.getenv("TELEGRAM_API_ID")
    api_hash = os.getenv("TELEGRAM_API_HASH")
    if not session_name or not api_id or not api_hash:
        sys.exit("TELEGRAM_SESSION_NAME, TELEGRAM_API_ID and TELEGRAM_API_HASH are required")

    client = TelegramClient(session_name, int(api_id), api_hash, **client_identity_kwargs())
    client.connect()
    try:
        if client.is_user_authorized():
            print(f"{session_name}.session is already logged in.")
        else:
            (_phone_login if args.phone else _qr_login)(client)
        me = client.get_me()
        print(f"Logged in as {me.first_name} (@{me.username}, id {me.id}).")
    finally:
        client.disconnect()


if __name__ == "__main__":
    main()
