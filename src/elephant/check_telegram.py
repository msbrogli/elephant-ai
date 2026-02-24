"""Diagnostic tool: show Telegram webhook status and pending updates."""

from __future__ import annotations

import argparse
import os
import sys

from elephant.config import load_config
from elephant.telegram_api import (
    build_webhook_url,
    delete_webhook,
    get_me,
    get_updates,
    get_webhook_info,
    set_webhook,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Check Telegram bot status")
    parser.add_argument(
        "-c",
        "--config",
        default=os.environ.get("CONFIG_PATH", "config.yaml"),
        help="Path to config.yaml",
    )
    parser.add_argument(
        "--set-webhook",
        action="store_true",
        help="Register the webhook URL from config with Telegram",
    )
    parser.add_argument(
        "--clear-webhook",
        action="store_true",
        help="Remove the current webhook from Telegram (needed for polling mode)",
    )
    args = parser.parse_args()

    config = load_config(args.config)
    tg = config.messaging.telegram

    if not tg.bot_token:
        print("ERROR: No bot_token in config")
        sys.exit(1)

    # 1. Check bot identity
    me = get_me(tg.bot_token)
    if me.get("ok"):
        bot = me["result"]
        print(f"Bot: @{bot.get('username')} ({bot.get('first_name')})")
    else:
        print(f"ERROR: getMe failed: {me.get('description')}")
        sys.exit(1)

    # 2a. Handle --set-webhook
    if args.set_webhook:
        if not tg.webhook_url:
            print("ERROR: webhook_url is not set in config")
            sys.exit(1)
        url = build_webhook_url(tg)
        print(f"\nSetting webhook to: {url}")
        result = set_webhook(tg.bot_token, url)
        if result.get("ok"):
            print("OK: webhook registered successfully")
        else:
            print(f"ERROR: {result.get('description')}")
            sys.exit(1)
        return

    # 2b. Handle --clear-webhook
    if args.clear_webhook:
        print("\nClearing webhook...")
        result = delete_webhook(tg.bot_token)
        if result.get("ok"):
            print("OK: webhook removed successfully")
        else:
            print(f"ERROR: {result.get('description')}")
            sys.exit(1)
        return

    # 3. Show mode
    print(f"\nMode: {tg.mode}")

    if tg.mode == "polling":
        print("  Polling mode active — no webhook needed")

        # Fetch pending updates
        print()
        try:
            updates = get_updates(tg.bot_token)
            if updates.get("ok"):
                results = updates.get("result", [])
                if not results:
                    print("Pending updates: none")
                else:
                    print(f"Pending updates: {len(results)}")
                    for u in results:
                        msg = u.get("message", {})
                        chat = msg.get("chat", {})
                        text = msg.get("text", "")
                        chat_id = chat.get("id", "?")
                        username = chat.get("username", "")
                        first_name = chat.get("first_name", "")
                        who = f"@{username}" if username else first_name
                        print(f"  [{u.get('update_id')}] {who} (chat_id={chat_id}): {text}")
            else:
                print(f"getUpdates failed: {updates.get('description', '')}")
        except Exception as e:
            print(f"getUpdates error: {e}")
        return

    # 4. Show webhook status (webhook mode)
    info = get_webhook_info(tg.bot_token)
    wh = info.get("result", {})
    wh_url = wh.get("url", "")
    print()
    if wh_url:
        print(f"Webhook URL: {wh_url}")
        print(f"  pending_update_count: {wh.get('pending_update_count', 0)}")
        if wh.get("last_error_date"):
            print(f"  last_error: {wh.get('last_error_message')}")
        if wh.get("has_custom_certificate"):
            print("  has_custom_certificate: true")
    else:
        print("Webhook: NOT SET  <-- this is why the bot doesn't answer")

    # 5. Compare registered vs configured
    if tg.webhook_url:
        expected = build_webhook_url(tg)
        print()
        if wh_url == expected:
            print(f"Config match: OK (both are {expected})")
        else:
            print("Config MISMATCH:")
            print(f"  registered: {wh_url or '(not set)'}")
            print(f"  expected:   {expected}")
            print("  Fix with: make set-webhook")
    elif not wh_url:
        print("  Hint: set webhook_url in config, then run: make set-webhook")

    # 6. Fetch pending updates (only works when webhook is not set)
    print()
    if wh_url:
        print(f"Pending updates: {wh.get('pending_update_count', 0)} (via webhook info)")
    else:
        try:
            updates = get_updates(tg.bot_token)
            if updates.get("ok"):
                results = updates.get("result", [])
                if not results:
                    print("Pending updates: none")
                else:
                    print(f"Pending updates: {len(results)}")
                    for u in results:
                        msg = u.get("message", {})
                        chat = msg.get("chat", {})
                        text = msg.get("text", "")
                        chat_id = chat.get("id", "?")
                        username = chat.get("username", "")
                        first_name = chat.get("first_name", "")
                        who = f"@{username}" if username else first_name
                        print(f"  [{u.get('update_id')}] {who} (chat_id={chat_id}): {text}")
            else:
                print(f"getUpdates failed: {updates.get('description', '')}")
        except Exception as e:
            print(f"getUpdates error: {e}")


if __name__ == "__main__":
    main()
