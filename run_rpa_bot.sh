#!/usr/bin/env bash
# run_rpa_bot.sh — Inject credentials from DB and run the RPA bot
# Usage:  bash run_rpa_bot.sh
# Must be run from the project root with the venv active OR it will activate it.

set -e

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_ROOT"

# Activate venv if not already active
if [[ "$VIRTUAL_ENV" == "" ]]; then
    echo "Activating virtual environment..."
    source .venv/bin/activate
fi

echo ""
echo "========================================================"
echo "  STEP 1 — Injecting credentials from DB into bot"
echo "========================================================"
python web_app/manage.py shell -c "
from core.models import AlertConfiguration
from django.contrib.auth.models import User
import re

# Find the first faculty/admin user with a configured alert setup
configs = AlertConfiguration.objects.filter(gmail_address__isnull=False).exclude(gmail_address='').select_related('faculty__user')
if not configs.exists():
    print('ERROR: No alert configuration found in the database.')
    print('Please go to the Faculty Dashboard → Alert Configuration and save your credentials first.')
    exit(1)

config = configs.first()
robot_path = 'rpa_bot/tasks.robot'
with open(robot_path) as f:
    content = f.read()

replacements = {
    r'(?m)^(\\\${GMAIL_USER})[ \t]+.*':   rf'\1     {config.gmail_address}',
    r'(?m)^(\\\${GMAIL_PASS})[ \t]+.*':   rf'\1     {config.gmail_app_password}',
    r'(?m)^(\\\${TWILIO_SID})[ \t]+.*':   rf'\1     {config.twilio_account_sid}',
    r'(?m)^(\\\${TWILIO_TOKEN})[ \t]+.*': rf'\1     {config.twilio_auth_token}',
    r'(?m)^(\\\${TWILIO_FROM})[ \t]+.*':  rf'\1     {config.twilio_from_number}',
    r'(?m)^(\\\${SMS_ENABLED})[ \t]+.*':  rf'\1     {str(config.sms_alerts_enabled)}',
}
for pat, repl in replacements.items():
    content = re.sub(pat, repl, content)

with open(robot_path, 'w') as f:
    f.write(content)

print(f'  Gmail:     {config.gmail_address}')
print(f'  SMS:       {config.sms_alerts_enabled}')
print(f'  Threshold: {config.alert_threshold}%')
print('  Credentials injected OK')
" 2>&1 | grep -v "^$\|imported\|^\s*$"

echo ""
echo "========================================================"
echo "  STEP 2 — Running Robot Framework RPA Bot"
echo "========================================================"
echo ""

cd rpa_bot
robot --outputdir /tmp/rpa_results tasks.robot
EXIT_CODE=$?

echo ""
echo "========================================================"
echo "  STEP 3 — Resetting credentials in file (security)"
echo "========================================================"
cd "$PROJECT_ROOT"
python3 -c "
import re
robot_path = 'rpa_bot/tasks.robot'
with open(robot_path) as f:
    content = f.read()
placeholders = {
    r'(?m)^(\\\${GMAIL_USER})[ \t]+.*':   r'\1     CONFIGURE_VIA_FACULTY_DASHBOARD',
    r'(?m)^(\\\${GMAIL_PASS})[ \t]+.*':   r'\1     CONFIGURE_VIA_FACULTY_DASHBOARD',
    r'(?m)^(\\\${TWILIO_SID})[ \t]+.*':   r'\1     CONFIGURE_VIA_FACULTY_DASHBOARD',
    r'(?m)^(\\\${TWILIO_TOKEN})[ \t]+.*': r'\1     CONFIGURE_VIA_FACULTY_DASHBOARD',
    r'(?m)^(\\\${TWILIO_FROM})[ \t]+.*':  r'\1     CONFIGURE_VIA_FACULTY_DASHBOARD',
    r'(?m)^(\\\${SMS_ENABLED})[ \t]+.*':  r'\1     False',
}
for pat, repl in placeholders.items():
    content = re.sub(pat, repl, content)
with open(robot_path, 'w') as f:
    f.write(content)
print('  Credentials cleared from tasks.robot (safe to commit)')
"

echo ""
if [ $EXIT_CODE -eq 0 ]; then
    echo "  ✅ RPA Bot completed successfully!"
else
    echo "  ❌ RPA Bot finished with errors. Check report:"
fi
echo "  Report: open /tmp/rpa_results/report.html"
echo ""
open /tmp/rpa_results/report.html 2>/dev/null || true
exit $EXIT_CODE
