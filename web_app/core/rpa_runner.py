"""
rpa_runner.py  — Django-side RPA Bot Runner
==========================================

This module contains the Django views and Python utility functions that
act as the bridge between the Faculty Dashboard UI and the 5 Robot Framework bots.

Each view:
  1. Validates the request (POST-only, faculty auth).
  2. Reads credentials from the AlertConfiguration model.
  3. Injects them securely as --variable flags into the Robot Framework CLI.
  4. Creates an RPABotLog entry for audit purposes.
  5. Returns a user-friendly flash message.

SECURITY NOTE:
  Credentials are NEVER written to disk — they are injected via subprocess
  environment or --variable CLI flags which live only in process memory.

PATTERN:
  All bot views follow the same decorator/structure for consistency
  and academic presentation clarity.
"""

import os
import subprocess
import logging
from datetime import datetime

from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.shortcuts import redirect
from django.utils import timezone

from .models import AlertConfiguration, FacultyProfile, RPABotLog

logger = logging.getLogger(__name__)

# ── Project root — one level above web_app/ ───────────────────────────────────
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RPA_BOT_DIR  = os.path.join(PROJECT_ROOT, 'rpa_bot')
REPORTS_DIR  = os.path.join(RPA_BOT_DIR, 'reports')
BACKUPS_DIR  = os.path.join(PROJECT_ROOT, 'backups')
VENV_ROBOT   = os.path.join(PROJECT_ROOT, '.venv', 'bin', 'robot')


def is_approved_faculty(user):
    """Guard predicate — re-imported to avoid circular dependency."""
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return (
        user.is_staff
        and hasattr(user, 'faculty_profile')
        and user.faculty_profile.is_approved
    )


def _get_config_and_creds(request):
    """
    Helper: fetches AlertConfiguration + decrypted credentials for the
    current faculty user. Returns (config, gmail_pass) or raises ValueError.
    """
    profile = getattr(request.user, 'faculty_profile', None)
    if profile is None:
        raise ValueError("No faculty profile found.")
    config, _ = AlertConfiguration.objects.get_or_create(faculty=profile)
    gmail_pass = config.get_decrypted_gmail_password()
    if not config.gmail_address or not gmail_pass:
        raise ValueError("Gmail credentials not configured. Set them in Alert Configuration first.")
    return config, gmail_pass


def _run_robot(bot_file, extra_vars=None, log_prefix="bot"):
    """
    Core helper: launches a Robot Framework bot as a subprocess.

    Args:
        bot_file    (str): Filename of the .robot file in rpa_bot/
        extra_vars  (list): List of strings in format 'KEY:VALUE'
                           passed as --variable flags.
        log_prefix  (str): Prefix for the RF log/report output files.

    Returns:
        (returncode, stdout, stderr)
    """
    robot_exe = VENV_ROBOT if os.path.exists(VENV_ROBOT) else 'robot'
    bot_path  = os.path.join(RPA_BOT_DIR, bot_file)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    cmd = [
        robot_exe,
        '--outputdir', RPA_BOT_DIR,
        '--output',  f'{log_prefix}_output_{timestamp}.xml',
        '--log',     f'{log_prefix}_log_{timestamp}.html',
        '--report',  f'{log_prefix}_report_{timestamp}.html',
    ]

    # Inject credential variables securely — no disk writes
    for var in (extra_vars or []):
        cmd += ['--variable', var]

    cmd.append(bot_path)

    logger.info("Running RF bot: %s", ' '.join(cmd))

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=RPA_BOT_DIR,
        timeout=300,   # 5-minute hard timeout for any single bot
    )
    return result.returncode, result.stdout, result.stderr


# ─────────────────────────────────────────────────────────────────────────────
# VIEW: Run Bot 1 — Auto-Leave Processor
# ─────────────────────────────────────────────────────────────────────────────

@user_passes_test(is_approved_faculty, login_url='/faculty/login/')
def run_leave_processor_bot(request):
    """
    Triggers Bot 1: Auto-Leave Processor.
    No credentials needed — DB-only operation.
    """
    if request.method != 'POST':
        return redirect('/faculty/dashboard/?tab=rpa_bots')

    log_entry = RPABotLog.objects.create(
        bot_name='leave_processor',
        status='running',
        triggered_by=request.user
    )

    try:
        rc, stdout, stderr = _run_robot('bot1_leave_processor.robot', log_prefix='bot1')
        if rc == 0:
            log_entry.mark_done('success', 'Auto-Leave Processor completed successfully.', errors='')
            messages.success(request, "✅ Bot 1: Auto-Leave Processor completed. Pending leaves processed.")
        else:
            err_snippet = stderr[-500:] if stderr else 'No stderr'
            log_entry.mark_done('failed', 'Bot failed.', errors=err_snippet)
            messages.error(request, f"❌ Bot 1 failed. Check RF log. Error: {err_snippet[:200]}")
    except subprocess.TimeoutExpired:
        log_entry.mark_done('failed', 'Bot timed out after 300s.', errors='TimeoutExpired')
        messages.error(request, "❌ Bot 1 timed out. The bot took longer than 5 minutes.")
    except Exception as e:
        log_entry.mark_done('failed', str(e), errors=str(e))
        messages.error(request, f"❌ Bot 1 error: {e}")
        logger.exception("Bot 1 unexpected error")

    return redirect('/faculty/dashboard/?tab=rpa_bots')


# ─────────────────────────────────────────────────────────────────────────────
# VIEW: Run Bot 2 — Monthly HOD PDF Report
# ─────────────────────────────────────────────────────────────────────────────

@user_passes_test(is_approved_faculty, login_url='/faculty/login/')
def run_hod_report_bot(request):
    """
    Triggers Bot 2: Monthly HOD PDF Report Generator.
    Requires Gmail credentials and Dean email from AlertConfiguration.
    """
    if request.method != 'POST':
        return redirect('/faculty/dashboard/?tab=rpa_bots')

    log_entry = RPABotLog.objects.create(
        bot_name='hod_report',
        status='running',
        triggered_by=request.user
    )

    try:
        config, gmail_pass = _get_config_and_creds(request)

        dean_email = config.dean_email
        if not dean_email:
            messages.warning(request, "⚠️ Dean email not configured. Set it in Alert Configuration.")
            log_entry.mark_done('failed', 'Dean email not configured.', errors='Missing dean_email')
            return redirect('/faculty/dashboard/?tab=alerts')

        os.makedirs(REPORTS_DIR, exist_ok=True)

        extra_vars = [
            f'GMAIL_USER:{config.gmail_address}',
            f'GMAIL_PASS:{gmail_pass}',
            f'DEAN_EMAIL:{dean_email}',
            f'HOD_THRESHOLD:{config.hod_report_threshold}',
        ]
        rc, stdout, stderr = _run_robot('bot2_hod_report.robot', extra_vars=extra_vars, log_prefix='bot2')

        if rc == 0:
            log_entry.mark_done('success', f'HOD Report generated and emailed to {dean_email}.', errors='')
            messages.success(request, f"✅ Bot 2: HOD PDF Report generated and emailed to {dean_email}.")
        else:
            err_snippet = stderr[-500:] if stderr else 'No stderr'
            log_entry.mark_done('failed', 'Bot failed.', errors=err_snippet)
            messages.error(request, f"❌ Bot 2 failed. Error: {err_snippet[:200]}")
    except ValueError as e:
        log_entry.mark_done('failed', str(e), errors=str(e))
        messages.error(request, f"❌ Configuration error: {e}")
    except subprocess.TimeoutExpired:
        log_entry.mark_done('failed', 'Bot timed out.', errors='TimeoutExpired')
        messages.error(request, "❌ Bot 2 timed out.")
    except Exception as e:
        log_entry.mark_done('failed', str(e), errors=str(e))
        messages.error(request, f"❌ Bot 2 error: {e}")
        logger.exception("Bot 2 unexpected error")

    return redirect('/faculty/dashboard/?tab=rpa_bots')


# ─────────────────────────────────────────────────────────────────────────────
# VIEW: Run Bot 3 — Holiday Sync
# ─────────────────────────────────────────────────────────────────────────────

@user_passes_test(is_approved_faculty, login_url='/faculty/login/')
def run_holiday_sync_bot(request):
    """
    Triggers Bot 3: Holiday Sync.
    Reads academic_calendar.xlsx from the project root and syncs
    holidays into the HolidayCalendar model.
    """
    if request.method != 'POST':
        return redirect('/faculty/dashboard/?tab=rpa_bots')

    log_entry = RPABotLog.objects.create(
        bot_name='holiday_sync',
        status='running',
        triggered_by=request.user
    )

    calendar_path = os.path.join(PROJECT_ROOT, 'academic_calendar.xlsx')
    if not os.path.exists(calendar_path):
        msg = f"academic_calendar.xlsx not found at {calendar_path}. Please upload it to the project root."
        log_entry.mark_done('failed', msg, errors=msg)
        messages.error(request, f"❌ {msg}")
        return redirect('/faculty/dashboard/?tab=rpa_bots')

    try:
        rc, stdout, stderr = _run_robot('bot3_holiday_sync.robot', log_prefix='bot3')
        if rc == 0:
            log_entry.mark_done('success', 'Holiday Sync completed. academic_calendar.xlsx synced.', errors='')
            messages.success(request, "✅ Bot 3: Holiday Sync completed. Academic calendar updated.")
        else:
            err_snippet = stderr[-500:] if stderr else 'No stderr'
            log_entry.mark_done('failed', 'Bot failed.', errors=err_snippet)
            messages.error(request, f"❌ Bot 3 failed. Error: {err_snippet[:200]}")
    except subprocess.TimeoutExpired:
        log_entry.mark_done('failed', 'Bot timed out.', errors='TimeoutExpired')
        messages.error(request, "❌ Bot 3 timed out.")
    except Exception as e:
        log_entry.mark_done('failed', str(e), errors=str(e))
        messages.error(request, f"❌ Bot 3 error: {e}")
        logger.exception("Bot 3 unexpected error")

    return redirect('/faculty/dashboard/?tab=rpa_bots')


# ─────────────────────────────────────────────────────────────────────────────
# VIEW: Run Bot 4 — PTM Escalation
# ─────────────────────────────────────────────────────────────────────────────

@user_passes_test(is_approved_faculty, login_url='/faculty/login/')
def run_ptm_escalation_bot(request):
    """
    Triggers Bot 4: PTM Escalation.
    Finds all students < 50% and emails PTM invitations to parents.
    """
    if request.method != 'POST':
        return redirect('/faculty/dashboard/?tab=rpa_bots')

    log_entry = RPABotLog.objects.create(
        bot_name='ptm_escalation',
        status='running',
        triggered_by=request.user
    )

    try:
        config, gmail_pass = _get_config_and_creds(request)

        extra_vars = [
            f'GMAIL_USER:{config.gmail_address}',
            f'GMAIL_PASS:{gmail_pass}',
        ]
        rc, stdout, stderr = _run_robot('bot4_ptm_escalation.robot', extra_vars=extra_vars, log_prefix='bot4')

        if rc == 0:
            log_entry.mark_done('success', 'PTM Escalation emails sent to all critical students.', errors='')
            messages.success(request, "✅ Bot 4: PTM Escalation completed. Invite emails sent to parents.")
        else:
            err_snippet = stderr[-500:] if stderr else 'No stderr'
            log_entry.mark_done('failed', 'Bot failed.', errors=err_snippet)
            messages.error(request, f"❌ Bot 4 failed. Error: {err_snippet[:200]}")
    except ValueError as e:
        log_entry.mark_done('failed', str(e), errors=str(e))
        messages.error(request, f"❌ Configuration error: {e}")
    except subprocess.TimeoutExpired:
        log_entry.mark_done('failed', 'Bot timed out.', errors='TimeoutExpired')
        messages.error(request, "❌ Bot 4 timed out.")
    except Exception as e:
        log_entry.mark_done('failed', str(e), errors=str(e))
        messages.error(request, f"❌ Bot 4 error: {e}")
        logger.exception("Bot 4 unexpected error")

    return redirect('/faculty/dashboard/?tab=rpa_bots')


# ─────────────────────────────────────────────────────────────────────────────
# VIEW: Run Bot 5 — Nightly DB Backup
# ─────────────────────────────────────────────────────────────────────────────

@user_passes_test(is_approved_faculty, login_url='/faculty/login/')
def run_db_backup_bot(request):
    """
    Triggers Bot 5: Nightly DB Backup & IT Health Report.
    Creates a timestamped backup and emails an IT health report.
    """
    if request.method != 'POST':
        return redirect('/faculty/dashboard/?tab=rpa_bots')

    log_entry = RPABotLog.objects.create(
        bot_name='db_backup',
        status='running',
        triggered_by=request.user
    )

    try:
        config, gmail_pass = _get_config_and_creds(request)

        it_email = request.POST.get('it_admin_email', config.dean_email or config.gmail_address)
        os.makedirs(BACKUPS_DIR, exist_ok=True)

        extra_vars = [
            f'GMAIL_USER:{config.gmail_address}',
            f'GMAIL_PASS:{gmail_pass}',
            f'IT_ADMIN_EMAIL:{it_email}',
        ]
        rc, stdout, stderr = _run_robot('bot5_db_backup.robot', extra_vars=extra_vars, log_prefix='bot5')

        if rc == 0:
            log_entry.mark_done('success', f'Nightly DB Backup completed. IT report emailed to {it_email}.', errors='')
            messages.success(request, f"✅ Bot 5: DB Backup completed. IT health report emailed to {it_email}.")
        else:
            err_snippet = stderr[-500:] if stderr else 'No stderr'
            log_entry.mark_done('failed', 'Bot failed.', errors=err_snippet)
            messages.error(request, f"❌ Bot 5 failed. Error: {err_snippet[:200]}")
    except ValueError as e:
        log_entry.mark_done('failed', str(e), errors=str(e))
        messages.error(request, f"❌ Configuration error: {e}")
    except subprocess.TimeoutExpired:
        log_entry.mark_done('failed', 'Bot timed out.', errors='TimeoutExpired')
        messages.error(request, "❌ Bot 5 timed out.")
    except Exception as e:
        log_entry.mark_done('failed', str(e), errors=str(e))
        messages.error(request, f"❌ Bot 5 error: {e}")
        logger.exception("Bot 5 unexpected error")

    return redirect('/faculty/dashboard/?tab=rpa_bots')
