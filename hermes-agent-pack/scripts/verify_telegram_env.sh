#!/usr/bin/env bash
set -euo pipefail

PROFILE_NAME="${1:-deeplinegtm}"

if ! command -v "$PROFILE_NAME" >/dev/null 2>&1; then
  echo "Profile alias not found: $PROFILE_NAME"
  exit 1
fi

ENV_PATH="$("$PROFILE_NAME" config env-path)"
if [ ! -f "$ENV_PATH" ]; then
  echo "Profile env file not found: $ENV_PATH"
  exit 1
fi

set -a
source "$ENV_PATH"
set +a

if [ -z "${TELEGRAM_BOT_TOKEN:-}" ]; then
  echo "TELEGRAM_BOT_TOKEN is not set."
  echo "Create it with @BotFather, then run scripts/configure_telegram_env.sh."
  exit 1
fi

if [ -z "${TELEGRAM_ALLOWED_USERS:-}" ]; then
  echo "TELEGRAM_ALLOWED_USERS is not set."
  echo "Get Jai's numeric Telegram user ID from @userinfobot or @getmyid_bot."
  exit 1
fi

python3 - <<'PY'
import json
import os
import urllib.request

token = os.environ["TELEGRAM_BOT_TOKEN"]
url = f"https://api.telegram.org/bot{token}/getMe"
with urllib.request.urlopen(url, timeout=15) as resp:
    data = json.loads(resp.read().decode("utf-8"))
if not data.get("ok"):
    raise SystemExit(f"Telegram getMe failed: {data}")
result = data["result"]
print(f"Telegram bot OK: @{result.get('username')} ({result.get('id')})")
PY

echo "Allowed users: ${TELEGRAM_ALLOWED_USERS}"
echo "Gateway foreground test:"
echo "  $PROFILE_NAME gateway run --no-supervise -v"
