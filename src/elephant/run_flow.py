"""CLI tool: trigger a flow on a running Elephant instance via HTTP."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Trigger an Elephant flow via the HTTP API",
    )
    parser.add_argument(
        "flow",
        help="Flow name (morning_digest, evening_checkin, question_manager)",
    )
    parser.add_argument(
        "-p",
        "--port",
        type=int,
        default=int(os.environ.get("PORT", "8080")),
        help="Port of the running app (default: $PORT or 8080)",
    )
    parser.add_argument(
        "--host",
        default=os.environ.get("HOST", "localhost"),
        help="Host of the running app (default: $HOST or localhost)",
    )
    args = parser.parse_args()

    url = f"http://{args.host}:{args.port}/api/run/{args.flow}"
    print(f"POST {url}")

    req = urllib.request.Request(url, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:  # noqa: S310
            data = json.loads(resp.read())
            print(json.dumps(data, indent=2))
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        try:
            data = json.loads(body)
            print(json.dumps(data, indent=2), file=sys.stderr)
        except json.JSONDecodeError:
            print(body, file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"Connection failed: {e.reason}", file=sys.stderr)
        print("Is the app running?", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
