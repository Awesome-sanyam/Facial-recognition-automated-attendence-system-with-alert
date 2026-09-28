#!/usr/bin/env bash
# run_all_automations.sh — Master RPA Automation Suite Runner
# Executes all 6 enterprise RPA bots and displays execution status.
# Usage:
#   bash run_all_automations.sh             # Visual headful mode
#   bash run_all_automations.sh --headless  # Headless mode for CI/Background

set -e

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_ROOT"

# Check headless flag
HEADLESS_FLAG=""
for arg in "$@"; do
    if [ "$arg" == "--headless" ] || [ "$arg" == "-h" ]; then
        HEADLESS_FLAG="--headless"
    fi
done

if [[ "$VIRTUAL_ENV" == "" ]]; then
    source .venv/bin/activate
fi

RESULTS_DIR="/tmp/rpa_all_results"
mkdir -p "$RESULTS_DIR"

echo ""
echo "======================================================================"
echo "    🚀 UNIVERSITY ATTENDANCE & ALERT SYSTEM — RPA AUTOMATION SUITE"
echo "======================================================================"
echo " Mode: $([ -n "$HEADLESS_FLAG" ] && echo "Headless (Server/CI)" || echo "Interactive / Headful")"
echo " Time: $(date)"
echo "======================================================================"
echo ""

# Ensure Django is accessible if running web bot
SERVER_RUNNING=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/faculty/login/ 2>/dev/null || echo "000")
if [ "$SERVER_RUNNING" != "200" ]; then
    echo "⚡ Starting background Django dev server on port 8000..."
    python web_app/manage.py runserver 127.0.0.1:8000 &> /tmp/django_rpa_test.log &
    DJANGO_PID=$!
    sleep 3
else
    DJANGO_PID=""
fi

PASSED=0
FAILED=0
declare -a BOT_STATUSES

run_bot() {
    local bot_id="$1"
    local bot_title="$2"
    local bot_file="$3"
    shift 3
    local extra_args=("$@")

    echo "──────────────────────────────────────────────────────────────────────"
    echo " ▶ [$bot_id] $bot_title"
    echo "──────────────────────────────────────────────────────────────────────"

    local out_dir="$RESULTS_DIR/$bot_id"
    mkdir -p "$out_dir"

    set +e
    if [ -n "$extra_args" ]; then
        robot "${extra_args[@]}" --outputdir "$out_dir" "$bot_file"
    else
        robot --outputdir "$out_dir" "$bot_file"
    fi
    local code=$?
    set -e

    if [ $code -eq 0 ]; then
        echo " ✅ $bot_title: PASSED"
        PASSED=$((PASSED + 1))
        BOT_STATUSES+=("✅ PASS | $bot_title")
    else
        echo " ❌ $bot_title: FAILED (Exit Code: $code)"
        FAILED=$((FAILED + 1))
        BOT_STATUSES+=("❌ FAIL | $bot_title (code $code)")
    fi
    echo ""
}

# 1. Main Selenium Web Portal Attendance Alert Bot
echo "──────────────────────────────────────────────────────────────────────"
echo " ▶ [Bot 0] Faculty Portal Attendance Scraper & Alert Bot (Selenium)"
echo "──────────────────────────────────────────────────────────────────────"
set +e
bash run_rpa_bot.sh $HEADLESS_FLAG
CODE0=$?
set -e
if [ $CODE0 -eq 0 ]; then
    PASSED=$((PASSED + 1))
    BOT_STATUSES+=("✅ PASS | Faculty Portal Attendance Scraper & Alert Bot")
else
    FAILED=$((FAILED + 1))
    BOT_STATUSES+=("❌ FAIL | Faculty Portal Attendance Scraper & Alert Bot")
fi
echo ""

# 2. Bot 1 — Auto-Leave Processor
run_bot "bot1" "Auto-Leave Processor Bot (>80% Attendance)" "rpa_bot/bot1_leave_processor.robot"

# 3. Bot 2 — Monthly HOD Attendance Risk PDF Report
run_bot "bot2" "Monthly HOD PDF Attendance Report Bot (<75% Threshold)" "rpa_bot/bot2_hod_report.robot"

# 4. Bot 3 — Holiday Sync
run_bot "bot3" "Academic Calendar Excel Holiday Sync Bot" "rpa_bot/bot3_holiday_sync.robot"

# 5. Bot 4 — PTM Escalation
run_bot "bot4" "PTM Escalation Alerts Bot (<50% Critical Students)" "rpa_bot/bot4_ptm_escalation.robot"

# 6. Bot 5 — Nightly DB Backup & IT Health
run_bot "bot5" "Nightly Database Backup & IT Health Bot" "rpa_bot/bot5_db_backup.robot"

# Cleanup background Django server if we started it
if [ -n "$DJANGO_PID" ]; then
    kill "$DJANGO_PID" 2>/dev/null || true
fi

echo "======================================================================"
echo "                       AUTOMATION AUDIT SUMMARY"
echo "======================================================================"
for status in "${BOT_STATUSES[@]}"; do
    echo "  $status"
done
echo "──────────────────────────────────────────────────────────────────────"
echo " Total Executed : $((PASSED + FAILED)) | Passed: $PASSED | Failed: $FAILED"
echo " Results Folder : $RESULTS_DIR"
echo "======================================================================"
echo ""

if [ $FAILED -gt 0 ]; then
    exit 1
fi
exit 0
