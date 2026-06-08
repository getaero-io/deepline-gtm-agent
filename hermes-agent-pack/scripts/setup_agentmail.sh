#!/usr/bin/env bash
set -euo pipefail

PROFILE_NAME="${1:-deeplinegtm}"
HUMAN_EMAIL="${AGENTMAIL_HUMAN_EMAIL:-jai@deepline.ai}"
USERNAME="${AGENTMAIL_USERNAME:-deepline-gtm-agent}"
DISPLAY_NAME="${AGENTMAIL_DISPLAY_NAME:-Deepline GTM Agent}"
DOMAIN="${AGENTMAIL_DOMAIN:-agentmail.to}"

if ! command -v npm >/dev/null 2>&1; then
  echo "npm not found. Install Node/npm before setting up AgentMail."
  exit 1
fi

if ! command -v agentmail >/dev/null 2>&1; then
  npm install -g agentmail-cli
fi

ENV_PATH="$HOME/.hermes/profiles/${PROFILE_NAME}/.env"
mkdir -p "$(dirname "$ENV_PATH")"
touch "$ENV_PATH"
chmod 600 "$ENV_PATH"

set -a
source "$ENV_PATH"
set +a

upsert_env() {
  local key="$1"
  local value="$2"
  if grep -q "^${key}=" "$ENV_PATH"; then
    perl -0pi -e "s/^${key}=.*$/${key}=${value}/m" "$ENV_PATH"
  else
    printf '%s=%s\n' "$key" "$value" >> "$ENV_PATH"
  fi
}

echo "AgentMail CLI:"
agentmail --version || true
echo

if [ -z "${AGENTMAIL_API_KEY:-}" ]; then
  echo "Starting AgentMail agent sign-up."
  echo "Human verification email: ${HUMAN_EMAIL}"
  echo "Username: ${USERNAME}"
  echo
  agentmail agent sign-up \
    --human-email "${HUMAN_EMAIL}" \
    --username "${USERNAME}" \
    --format json
  echo
  echo "An OTP was sent to ${HUMAN_EMAIL}."
  echo "After receiving it, run:"
  echo
  echo "  AGENTMAIL_API_KEY=\"<api-key-from-sign-up>\" AGENTMAIL_OTP_CODE=\"<otp>\" bash scripts/setup_agentmail.sh ${PROFILE_NAME}"
  exit 0
fi

if [ -n "${AGENTMAIL_OTP_CODE:-}" ]; then
  agentmail agent verify --otp-code "${AGENTMAIL_OTP_CODE}" --api-key "${AGENTMAIL_API_KEY}"
fi

export AGENTMAIL_API_KEY

if [ -z "${AGENTMAIL_INBOX_ID:-}" ]; then
  INBOX_JSON="$(agentmail inboxes create \
    --display-name "${DISPLAY_NAME}" \
    --username "${USERNAME}" \
    --domain "${DOMAIN}" \
    --format json)"

  echo "$INBOX_JSON"

  AGENTMAIL_INBOX_ID="$(printf '%s' "$INBOX_JSON" | node -e 'let s=""; process.stdin.on("data",d=>s+=d); process.stdin.on("end",()=>{const j=JSON.parse(s); console.log(j.inbox_id || j.id || j.email || "")})')"
  AGENTMAIL_EMAIL="$(printf '%s' "$INBOX_JSON" | node -e 'let s=""; process.stdin.on("data",d=>s+=d); process.stdin.on("end",()=>{const j=JSON.parse(s); console.log(j.email || j.inbox_id || "")})')"
else
  AGENTMAIL_EMAIL="${AGENTMAIL_EMAIL:-$AGENTMAIL_INBOX_ID}"
  echo "Using existing AgentMail inbox: ${AGENTMAIL_EMAIL}"
fi

upsert_env AGENTMAIL_API_KEY "${AGENTMAIL_API_KEY}"
upsert_env AGENTMAIL_INBOX_ID "${AGENTMAIL_INBOX_ID}"
upsert_env AGENTMAIL_EMAIL "${AGENTMAIL_EMAIL}"

echo
echo "AgentMail env saved to:"
echo "$ENV_PATH"
echo
echo "First safe tests:"
echo "  agentmail inboxes list --api-key \"\$AGENTMAIL_API_KEY\" --format json"
echo "  agentmail inboxes:threads list --inbox-id \"\$AGENTMAIL_INBOX_ID\" --api-key \"\$AGENTMAIL_API_KEY\" --format json"
