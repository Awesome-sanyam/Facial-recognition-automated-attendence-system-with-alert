#!/usr/bin/env bash
# run_rpa_bot.sh — Securely extract credentials from DB and execute RPA bot
# Usage:
#   bash run_rpa_bot.sh             # Visual headful mode (watch Chrome run)
#   bash run_rpa_bot.sh --headless  # Headless mode (runs in background/server)

set -e

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_ROOT"

# Check for headless flag
HEADLESS_MODE="False"
for arg in "$@"; do
    if [ "$arg" == "--headless" ] || [ "$arg" == "-h" ]; then
        HEADLESS_MODE="True"
    fi
done

# Activate virtualenv if not active
if [[ "$VIRTUAL_ENV" == "" ]]; then
    echo "Activating virtual environment..."
    source .venv/bin/activate
fi

echo ""
echo "========================================================"
echo "  STEP 1 — Reading secure credentials from Database"
echo "========================================================"

# Extract credentials via a temporary JSON payload without touching any source files on disk
CONFIG_FILE=$(mktemp /tmp/rpa_bot_config.XXXXXX.json)
python web_app/manage.py shell -c "
import json
from core.models import AlertConfiguration

configs = AlertConfiguration.objects.filter(gmail_address__isnull=False).exclude(gmail_address='').select_related('faculty__user')
if not configs.exists():
    print('ERROR: No alert configuration found in the database.')
    exit(1)

config = configs.first()
data = {
    'GMAIL_USER': config.gmail_address or '',
    'GMAIL_PASS': config.get_decrypted_gmail_password() or '',
    'TWILIO_SID': config.twilio_account_sid or '',
    'TWILIO_TOKEN': config.get_decrypted_twilio_token() or '',
    'TWILIO_FROM': config.twilio_from_number or '',
    'SMS_ENABLED': 'True' if config.sms_alerts_enabled else 'False',
    'THRESHOLD': str(float(config.alert_threshold)),
    'EMAIL_SUBJECT': config.alert_email_subject or 'URGENT: Low Attendance Warning — {student_name}',
    'EMAIL_BODY': config.alert_email_body or '',
    'SMS_BODY': config.sms_alert_body or '',
}
with open('$CONFIG_FILE', 'w') as f:
    json.dump(data, f)
"

if [ ! -s "$CONFIG_FILE" ]; then
    echo "❌ Failed to load credentials from database."
    rm -f "$CONFIG_FILE"
    exit 1
fi

# Parse variables from JSON payload
GMAIL_USER=$(python3 -c "import json; print(json.load(open('$CONFIG_FILE'))['GMAIL_USER'])")
GMAIL_PASS=$(python3 -c "import json; print(json.load(open('$CONFIG_FILE'))['GMAIL_PASS'])")
TWILIO_SID=$(python3 -c "import json; print(json.load(open('$CONFIG_FILE'))['TWILIO_SID'])")
TWILIO_TOKEN=$(python3 -c "import json; print(json.load(open('$CONFIG_FILE'))['TWILIO_TOKEN'])")
TWILIO_FROM=$(python3 -c "import json; print(json.load(open('$CONFIG_FILE'))['TWILIO_FROM'])")
SMS_ENABLED=$(python3 -c "import json; print(json.load(open('$CONFIG_FILE'))['SMS_ENABLED'])")
THRESHOLD=$(python3 -c "import json; print(json.load(open('$CONFIG_FILE'))['THRESHOLD'])")
EMAIL_SUBJECT=$(python3 -c "import json; print(json.load(open('$CONFIG_FILE'))['EMAIL_SUBJECT'])")
EMAIL_BODY=$(python3 -c "import json; print(json.load(open('$CONFIG_FILE'))['EMAIL_BODY'])")
SMS_BODY=$(python3 -c "import json; print(json.load(open('$CONFIG_FILE'))['SMS_BODY'])")

# Immediately remove temp config file from disk
rm -f "$CONFIG_FILE"

echo "  Gmail User : $GMAIL_USER"
echo "  SMS Enabled: $SMS_ENABLED"
echo "  Threshold  : ${THRESHOLD}%"
echo "  Headless   : $HEADLESS_MODE"
echo "  Status     : Ready (source files remain clean on disk)"

echo ""
echo "========================================================"
echo "  STEP 2 — Running Robot Framework RPA Bot"
echo "========================================================"
echo ""

cd rpa_bot

# Pass credentials dynamically into robot via CLI flags without modifying tasks.robot file
set +e
robot \
    --variable GMAIL_USER:"$GMAIL_USER" \
    --variable GMAIL_PASS:"$GMAIL_PASS" \
    --variable TWILIO_SID:"$TWILIO_SID" \
    --variable TWILIO_TOKEN:"$TWILIO_TOKEN" \
    --variable TWILIO_FROM:"$TWILIO_FROM" \
    --variable SMS_ENABLED:"$SMS_ENABLED" \
    --variable THRESHOLD:"$THRESHOLD" \
    --variable EMAIL_SUBJECT:"$EMAIL_SUBJECT" \
    --variable EMAIL_BODY:"$EMAIL_BODY" \
    --variable SMS_BODY:"$SMS_BODY" \
    --variable HEADLESS:"$HEADLESS_MODE" \
    --outputdir /tmp/rpa_results \
    tasks.robot

EXIT_CODE=$?
set -e

cd "$PROJECT_ROOT"

echo ""
echo "========================================================"
echo "  STEP 3 — Audit & Execution Summary"
echo "========================================================"
if [ $EXIT_CODE -eq 0 ]; then
    echo "  ✅ RPA Bot completed successfully!"
else
    echo "  ❌ RPA Bot finished with errors. Review HTML report below:"
fi
echo "  Report: open /tmp/rpa_results/report.html"
echo "  tasks.robot was NOT modified (zero git contamination)."
echo ""

# If not running in headless/CI, open the report
if [ "$HEADLESS_MODE" != "True" ] && command -v open &> /dev/null; then
    open /tmp/rpa_results/report.html 2>/dev/null || true
fi

exit $EXIT_CODE
