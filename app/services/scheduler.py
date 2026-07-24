"""
Nightly overdue job — runs once per day at 01:00 local time.

For every active loan whose due_date has passed and whose overdue_fee
has not yet been charged, debit the borrower 10.00 € (entry-fee amount)
and record a Transaction of type 'overdue'.
"""
import hashlib
import os
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

OVERDUE_FEE = 10.00


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run_backup(kind: str, retention_days: int):
    """Online SQLite backup into backups/<kind>/, skipped if unchanged
    since the last snapshot of that kind, pruned by retention_days."""
    from app.database import LIVE_DB_PATH, BACKUPS_DIR

    backup_dir = BACKUPS_DIR / kind
    backup_dir.mkdir(parents=True, exist_ok=True)

    # Written directly into backup_dir (not the system tempdir) so the final
    # rename stays on the same filesystem — /tmp is the container's own
    # overlay fs, while backups/ is a bind-mounted host volume; renaming
    # across the two fails with "Invalid cross-device link".
    fd, tmp_name = tempfile.mkstemp(suffix='.db', dir=backup_dir)
    os.close(fd)
    tmp_path = Path(tmp_name)
    try:
        src = sqlite3.connect(str(LIVE_DB_PATH))
        dst = sqlite3.connect(str(tmp_path))
        src.backup(dst)
        dst.close()
        src.close()

        new_hash = _file_hash(tmp_path)
        existing = sorted(backup_dir.glob('mangashelf-*.db'))
        if existing and _file_hash(existing[-1]) == new_hash:
            return

        dest = backup_dir / f"mangashelf-{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.db"
        tmp_path.replace(dest)
    finally:
        tmp_path.unlink(missing_ok=True)

    cutoff = datetime.now(timezone.utc).timestamp() - retention_days * 86400
    for f in backup_dir.glob('mangashelf-*.db'):
        if f.stat().st_mtime < cutoff:
            f.unlink()


def _charge_overdue():
    """Called by APScheduler — uses a fresh SQLAlchemy session."""
    from app.database import SessionLocal
    from app.models import Loan, Transaction

    db = SessionLocal()
    try:
        now_iso = datetime.now(timezone.utc).isoformat()
        due_loans = (
            db.query(Loan)
            .filter(Loan.due_date < now_iso, Loan.overdue_fee == 0)
            .all()
        )
        if not due_loans:
            return

        for loan in due_loans:
            user = loan.user
            book_title = loan.copy.book.title if loan.copy and loan.copy.book else 'Unknown'

            debit = min(OVERDUE_FEE, user.guthaben)
            user.guthaben = round(user.guthaben - debit, 2)
            loan.overdue_fee = OVERDUE_FEE

            db.add(Transaction(
                user_id=user.id,
                amount=-debit,
                type='overdue',
                description=f'Overdue fee: {book_title}',
            ))

        db.commit()
    finally:
        db.close()


def start_scheduler():
    """Create and start the APScheduler background scheduler."""
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        func=_charge_overdue,
        trigger=CronTrigger(hour=1, minute=0),
        id='overdue_check',
        replace_existing=True,
        misfire_grace_time=3600,
    )
    scheduler.add_job(
        func=_run_backup,
        args=['daily', 28],
        trigger=CronTrigger(hour=3, minute=0),
        id='backup_daily',
        replace_existing=True,
        misfire_grace_time=3600,
    )
    scheduler.add_job(
        func=_run_backup,
        args=['weekly', 52 * 7],
        trigger=CronTrigger(day_of_week='sun', hour=3, minute=15),
        id='backup_weekly',
        replace_existing=True,
        misfire_grace_time=3600,
    )
    scheduler.start()
    return scheduler
