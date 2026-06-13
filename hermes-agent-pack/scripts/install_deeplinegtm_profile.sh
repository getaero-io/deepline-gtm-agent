#!/usr/bin/env bash
set -euo pipefail

PROFILE_NAME="${1:-deeplinegtm}"
REPO_DIR="${2:-/home/sprite/deepline-hermes-repo}"

if ! command -v hermes >/dev/null 2>&1; then
  echo "hermes not found"
  exit 1
fi

if ! command -v "${PROFILE_NAME}" >/dev/null 2>&1; then
  hermes profile create "${PROFILE_NAME}" --clone --description "Deepline GTM operator with bounded subagent skills, split marketing specialists, Deepline-native execution, and Telegram workflows."
fi

"${PROFILE_NAME}" config set terminal.cwd "${REPO_DIR}"
"${PROFILE_NAME}" config set terminal.timeout 300
"${PROFILE_NAME}" config set agent.max_turns 50
"${PROFILE_NAME}" config set security.redact_secrets true
"${PROFILE_NAME}" config set display.tool_progress minimal || true
"${PROFILE_NAME}" config set display.interim_assistant_messages false || true

rm -rf "${REPO_DIR}/output/sales_agent"
rm -rf "${REPO_DIR}/output/marketing_agent"

mkdir -p "${REPO_DIR}/output/gtm_agent"
mkdir -p "${REPO_DIR}/output/marketing_content"
mkdir -p "${REPO_DIR}/output/marketing_campaigns"
mkdir -p "${REPO_DIR}/output/marketing_proof"
mkdir -p "${REPO_DIR}/output/account_research"
mkdir -p "${REPO_DIR}/context/source_notes"

rm -rf "$HOME/.hermes/profiles/${PROFILE_NAME}/skills/deepline-sales-agent"
rm -rf "$HOME/.hermes/profiles/${PROFILE_NAME}/skills/deepline-marketing-agent"

mkdir -p "$HOME/.hermes/profiles/${PROFILE_NAME}/skills/deepline-gtm-agent"
mkdir -p "$HOME/.hermes/profiles/${PROFILE_NAME}/skills/deepline-sales-workflows"
mkdir -p "$HOME/.hermes/profiles/${PROFILE_NAME}/skills/deepline-marketing-content-agent"
mkdir -p "$HOME/.hermes/profiles/${PROFILE_NAME}/skills/deepline-marketing-campaign-agent"
mkdir -p "$HOME/.hermes/profiles/${PROFILE_NAME}/skills/deepline-marketing-proof-agent"
mkdir -p "$HOME/.hermes/profiles/${PROFILE_NAME}/skills/deepline-agentmail-inbox"
mkdir -p "$HOME/.hermes/profiles/${PROFILE_NAME}/skills/deepline-proof-guard"
mkdir -p "$HOME/.hermes/profiles/${PROFILE_NAME}/skills/deepline-account-research"
mkdir -p "$HOME/.hermes/profiles/${PROFILE_NAME}/skills/deepline-crm-hygiene"
mkdir -p "$HOME/.hermes/profiles/${PROFILE_NAME}/skills/deepline-workflow-spec"
cp "${REPO_DIR}/skills/gtm-agent/SKILL.md" "$HOME/.hermes/profiles/${PROFILE_NAME}/skills/deepline-gtm-agent/SKILL.md"
cp "${REPO_DIR}/skills/sales-agent/SKILL.md" "$HOME/.hermes/profiles/${PROFILE_NAME}/skills/deepline-sales-workflows/SKILL.md"
cp "${REPO_DIR}/skills/marketing-content-agent/SKILL.md" "$HOME/.hermes/profiles/${PROFILE_NAME}/skills/deepline-marketing-content-agent/SKILL.md"
cp "${REPO_DIR}/skills/marketing-campaign-agent/SKILL.md" "$HOME/.hermes/profiles/${PROFILE_NAME}/skills/deepline-marketing-campaign-agent/SKILL.md"
cp "${REPO_DIR}/skills/marketing-proof-agent/SKILL.md" "$HOME/.hermes/profiles/${PROFILE_NAME}/skills/deepline-marketing-proof-agent/SKILL.md"
cp "${REPO_DIR}/skills/agentmail-inbox/SKILL.md" "$HOME/.hermes/profiles/${PROFILE_NAME}/skills/deepline-agentmail-inbox/SKILL.md"
cp "${REPO_DIR}/skills/proof-guard/SKILL.md" "$HOME/.hermes/profiles/${PROFILE_NAME}/skills/deepline-proof-guard/SKILL.md"
cp "${REPO_DIR}/skills/account-research/SKILL.md" "$HOME/.hermes/profiles/${PROFILE_NAME}/skills/deepline-account-research/SKILL.md"
cp "${REPO_DIR}/skills/crm-hygiene/SKILL.md" "$HOME/.hermes/profiles/${PROFILE_NAME}/skills/deepline-crm-hygiene/SKILL.md"
cp "${REPO_DIR}/skills/workflow-spec/SKILL.md" "$HOME/.hermes/profiles/${PROFILE_NAME}/skills/deepline-workflow-spec/SKILL.md"

cp "${REPO_DIR}/hermes/deeplinegtm_SOUL.md" "$HOME/.hermes/profiles/${PROFILE_NAME}/SOUL.md"

mkdir -p "$HOME/.local/bin"
cat > "$HOME/.local/bin/${PROFILE_NAME}" <<WRAPPER
#!/usr/bin/env bash
cd "${REPO_DIR}"
exec hermes -p "${PROFILE_NAME}" "\$@"
WRAPPER
chmod +x "$HOME/.local/bin/${PROFILE_NAME}"

echo
echo "Profile installed: ${PROFILE_NAME}"
"${PROFILE_NAME}" profile show "${PROFILE_NAME}" 2>/dev/null || hermes profile show "${PROFILE_NAME}"
echo
echo "Telegram still requires TELEGRAM_BOT_TOKEN and TELEGRAM_ALLOWED_USERS in:"
"${PROFILE_NAME}" config env-path
echo
echo "Verify Telegram after adding credentials:"
echo "  cd ${REPO_DIR} && bash scripts/verify_telegram_env.sh ${PROFILE_NAME}"
