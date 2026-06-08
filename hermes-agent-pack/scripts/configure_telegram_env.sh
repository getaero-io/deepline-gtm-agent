#!/usr/bin/env bash
set -euo pipefail

PROFILE_NAME="${1:-deeplinegtm}"
BOT_TOKEN="${TELEGRAM_BOT_TOKEN:-}"
ALLOWED_USERS="${TELEGRAM_ALLOWED_USERS:-}"

if [[ -z "$BOT_TOKEN" || -z "$ALLOWED_USERS" ]]; then
  cat <<'USAGE'
Usage:

  TELEGRAM_BOT_TOKEN="123:abc" TELEGRAM_ALLOWED_USERS="123456789" bash scripts/configure_telegram_env.sh

This writes Telegram credentials into the deeplinegtm Hermes profile env file.
Get the token from @BotFather and the numeric user ID from @userinfobot or @getmyid_bot.
USAGE
  exit 1
fi

if ! command -v "$PROFILE_NAME" >/dev/null 2>&1; then
  echo "Profile alias not found: $PROFILE_NAME"
  exit 1
fi

ENV_PATH="$("$PROFILE_NAME" config env-path)"
mkdir -p "$(dirname "$ENV_PATH")"
touch "$ENV_PATH"

python3 - "$ENV_PATH" "$BOT_TOKEN" "$ALLOWED_USERS" <<'PY'
import sys
from pathlib import Path

path = Path(sys.argv[1])
values = {
    "TELEGRAM_BOT_TOKEN": sys.argv[2],
    "TELEGRAM_ALLOWED_USERS": sys.argv[3],
    "GATEWAY_ALLOW_ALL_USERS": "false",
}

lines = path.read_text().splitlines()
seen = set()
out = []
for line in lines:
    key = line.split("=", 1)[0] if "=" in line else None
    if key in values:
        out.append(f"{key}={values[key]}")
        seen.add(key)
    else:
        out.append(line)
for key, value in values.items():
    if key not in seen:
        out.append(f"{key}={value}")
path.write_text("\n".join(out).rstrip() + "\n")
PY

echo "Telegram env configured for profile: $PROFILE_NAME"
echo "Start foreground test:"
echo "  $PROFILE_NAME gateway run"
echo "Install/start service:"
echo "  $PROFILE_NAME gateway install && $PROFILE_NAME gateway start"

