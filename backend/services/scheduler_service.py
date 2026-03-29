"""
Background task scheduler for case expiration checks and follow-up automation.
Uses APScheduler (lightweight alternative to Celery for hackathon).
"""
import os
from datetime import datetime, timezone, timedelta
import logging

from apscheduler.schedulers.background import BackgroundScheduler

from database import SessionLocal
from models import Case, FollowUpSchedule, CountryPermission
from config import DOCTOR_RESPONSE_TIMEOUT_HOURS, FOLLOWUP_HOURS

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()


def check_case_expiration():
    """
    Runs every 15 min. Escalates cases that have been assigned
    but not responded to within DOCTOR_RESPONSE_TIMEOUT_HOURS.
    """
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(hours=DOCTOR_RESPONSE_TIMEOUT_HOURS)

        stale_cases = (
            db.query(Case)
            .filter(
                Case.status == "assigned",
                Case.assigned_at != None,
                Case.assigned_at < cutoff,
            )
            .all()
        )

        for case in stale_cases:
            logger.warning(
                f"Case {case.id} expired — no doctor response in {DOCTOR_RESPONSE_TIMEOUT_HOURS}h"
            )
            case.status = "escalated"
            case.triage_level = "RED"
            case.escalated_at = now
            case.assigned_doctor_id = None

        if stale_cases:
            db.commit()
            logger.info(f"Escalated {len(stale_cases)} expired cases")

    except Exception as e:
        logger.error(f"Error in case expiration check: {e}")
        db.rollback()
    finally:
        db.close()


def check_pending_followups():
    """
    Runs every 15 min. Marks follow-ups as 'sent' when their scheduled time arrives.
    In production, this would trigger actual SMS via Twilio.
    """
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)

        due_followups = (
            db.query(FollowUpSchedule)
            .filter(
                FollowUpSchedule.status == "pending",
                FollowUpSchedule.scheduled_at <= now,
            )
            .all()
        )

        for fu in due_followups:
            fu.status = "sent"
            fu.sent_at = now
            logger.info(f"Follow-up {fu.id} for case {fu.case_id} marked as sent")

        if due_followups:
            db.commit()
            logger.info(f"Processed {len(due_followups)} due follow-ups")

    except Exception as e:
        logger.error(f"Error in follow-up check: {e}")
        db.rollback()
    finally:
        db.close()


def schedule_case_followups(case_id: str):
    """
    Schedule follow-up checks at 24h and 48h for a resolved case.
    Called when a case is resolved.
    """
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        for hours in FOLLOWUP_HOURS:
            fu = FollowUpSchedule(
                case_id=case_id,
                scheduled_at=now + timedelta(hours=hours),
                channel="sms",
            )
            db.add(fu)
        db.commit()
        logger.info(f"Scheduled {len(FOLLOWUP_HOURS)} follow-ups for case {case_id}")
    except Exception as e:
        logger.error(f"Error scheduling follow-ups: {e}")
        db.rollback()
    finally:
        db.close()


def purge_expired_case_records():
    """
    Daily-style retention: delete closed cases older than country max_retention_days.
    Enable with DATA_PURGE_ENABLED=1 (destructive).
    """
    if os.environ.get("DATA_PURGE_ENABLED", "").lower() not in ("1", "true", "yes"):
        return
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        perms = db.query(CountryPermission).all()
        removed = 0
        for perm in perms:
            days = perm.max_retention_days or 90
            cutoff = now - timedelta(days=days)
            stale = (
                db.query(Case)
                .filter(
                    Case.country_code == perm.country_code,
                    Case.status == "closed",
                    Case.closed_at.isnot(None),
                    Case.closed_at < cutoff,
                )
                .all()
            )
            for c in stale:
                db.delete(c)
                removed += 1
        if removed:
            db.commit()
            logger.info("Data retention purge removed %s closed cases", removed)
    except Exception as e:
        logger.error("Retention purge error: %s", e)
        db.rollback()
    finally:
        db.close()


def start_scheduler():
    """Initialize and start the background scheduler."""
    scheduler.add_job(
        check_case_expiration,
        "interval",
        minutes=15,
        id="check_case_expiration",
        replace_existing=True,
    )
    scheduler.add_job(
        check_pending_followups,
        "interval",
        minutes=15,
        id="check_pending_followups",
        replace_existing=True,
    )
    scheduler.add_job(
        purge_expired_case_records,
        "interval",
        hours=24,
        id="purge_expired_case_records",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Background scheduler started with 15-min interval jobs")


def stop_scheduler():
    """Gracefully shut down the scheduler."""
    if scheduler.running:
        scheduler.shutdown()
        logger.info("Background scheduler stopped")
