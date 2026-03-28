#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

info()  { echo -e "${CYAN}[INFO]${NC}  $*"; }
ok()    { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
err()   { echo -e "${RED}[ERROR]${NC} $*"; }

cleanup() {
    if [[ -n "${NGROK_PID:-}" ]]; then
        kill "$NGROK_PID" 2>/dev/null || true
    fi
}
trap cleanup EXIT

# ── Load environment ──────────────────────────────────────────────
ENV_FILE="$SCRIPT_DIR/.env"
if [[ ! -f "$ENV_FILE" ]]; then
    err ".env file not found at $ENV_FILE"
    exit 1
fi

set -a
source "$ENV_FILE"
set +a
ok "Loaded .env"

for var in TWILIO_ACCOUNT_SID TWILIO_API_KEY_SID TWILIO_API_KEY_SECRET TWILIO_PHONE_NUMBER; do
    if [[ -z "${!var:-}" ]]; then
        err "Missing required env var: $var"
        exit 1
    fi
done
ok "All required Twilio credentials present"

# ── Ensure ngrok is installed ─────────────────────────────────────
if ! command -v ngrok &>/dev/null; then
    warn "ngrok not found — installing via Homebrew..."
    if ! command -v brew &>/dev/null; then
        err "Homebrew is not installed. Install ngrok manually: https://ngrok.com/download"
        exit 1
    fi
    brew install ngrok
    if ! command -v ngrok &>/dev/null; then
        err "ngrok installation failed"
        exit 1
    fi
    ok "ngrok installed"
else
    ok "ngrok found at $(command -v ngrok)"
fi

# ── Kill existing ngrok processes ─────────────────────────────────
if pgrep -x ngrok &>/dev/null; then
    warn "Killing existing ngrok processes..."
    pkill -x ngrok || true
    sleep 1
fi
ok "No stale ngrok processes"

# ── Start ngrok tunnel on port 8000 ──────────────────────────────
info "Starting ngrok tunnel on port 8000..."
ngrok http 8000 --log=stdout > /dev/null 2>&1 &
NGROK_PID=$!
ok "ngrok started (pid $NGROK_PID)"

# ── Wait for ngrok API to be ready ────────────────────────────────
info "Waiting for ngrok to be ready..."
MAX_ATTEMPTS=30
for i in $(seq 1 $MAX_ATTEMPTS); do
    if curl -s http://127.0.0.1:4040/api/tunnels > /dev/null 2>&1; then
        break
    fi
    if ! kill -0 "$NGROK_PID" 2>/dev/null; then
        err "ngrok process died unexpectedly"
        exit 1
    fi
    if [[ $i -eq $MAX_ATTEMPTS ]]; then
        err "ngrok failed to start after ${MAX_ATTEMPTS}s"
        exit 1
    fi
    sleep 1
done
ok "ngrok API is ready"

# ── Extract public HTTPS URL ─────────────────────────────────────
NGROK_URL=$(curl -s http://127.0.0.1:4040/api/tunnels | python3 -c "
import sys, json
data = json.load(sys.stdin)
for t in data.get('tunnels', []):
    if t.get('proto') == 'https':
        print(t['public_url'])
        sys.exit(0)
# Fallback: first tunnel
tunnels = data.get('tunnels', [])
if tunnels:
    print(tunnels[0]['public_url'])
else:
    sys.exit(1)
")

if [[ -z "${NGROK_URL:-}" ]]; then
    err "Failed to extract ngrok public URL"
    exit 1
fi
ok "Tunnel URL: ${BOLD}${NGROK_URL}${NC}"

# ── Look up Twilio Phone Number SID ──────────────────────────────
ENCODED_NUMBER=$(python3 -c "import urllib.parse; print(urllib.parse.quote('${TWILIO_PHONE_NUMBER}'))")

info "Looking up Phone Number SID for ${TWILIO_PHONE_NUMBER}..."
PHONE_RESPONSE=$(curl -s \
    "https://api.twilio.com/2010-04-01/Accounts/${TWILIO_ACCOUNT_SID}/IncomingPhoneNumbers.json?PhoneNumber=${ENCODED_NUMBER}" \
    -u "${TWILIO_API_KEY_SID}:${TWILIO_API_KEY_SECRET}")

PHONE_SID=$(echo "$PHONE_RESPONSE" | python3 -c "
import sys, json
data = json.load(sys.stdin)
numbers = data.get('incoming_phone_numbers', [])
if numbers:
    print(numbers[0]['sid'])
else:
    print('')
")

if [[ -z "$PHONE_SID" ]]; then
    err "Could not find Phone Number SID. Twilio response:"
    echo "$PHONE_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$PHONE_RESPONSE"
    exit 1
fi
ok "Phone SID: ${PHONE_SID}"

# ── Update Twilio voice webhook ───────────────────────────────────
WEBHOOK_URL="${NGROK_URL}/twilio/voice"
info "Setting voice webhook to ${BOLD}${WEBHOOK_URL}${NC}"

UPDATE_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" \
    -X POST "https://api.twilio.com/2010-04-01/Accounts/${TWILIO_ACCOUNT_SID}/IncomingPhoneNumbers/${PHONE_SID}.json" \
    -u "${TWILIO_API_KEY_SID}:${TWILIO_API_KEY_SECRET}" \
    -d "VoiceUrl=${WEBHOOK_URL}" \
    -d "VoiceMethod=POST")

if [[ "$UPDATE_RESPONSE" -ge 200 && "$UPDATE_RESPONSE" -lt 300 ]]; then
    ok "Twilio webhook updated successfully (HTTP ${UPDATE_RESPONSE})"
else
    err "Twilio webhook update failed (HTTP ${UPDATE_RESPONSE})"
    exit 1
fi

# ── Summary ───────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}${BOLD}══════════════════════════════════════════════${NC}"
echo -e "${GREEN}${BOLD}  Tunnel ready!${NC}"
echo -e "${GREEN}${BOLD}══════════════════════════════════════════════${NC}"
echo -e "  ngrok URL  : ${CYAN}${NGROK_URL}${NC}"
echo -e "  Webhook    : ${CYAN}${WEBHOOK_URL}${NC}"
echo -e "  Phone      : ${YELLOW}${TWILIO_PHONE_NUMBER}${NC}"
echo -e "  Phone SID  : ${YELLOW}${PHONE_SID}${NC}"
echo -e "${GREEN}${BOLD}══════════════════════════════════════════════${NC}"
echo ""

# ── Start the backend server ──────────────────────────────────────
trap - EXIT
info "Starting uvicorn server..."
exec /Library/Frameworks/Python.framework/Versions/3.13/bin/python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
