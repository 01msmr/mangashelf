"""
Nightly overdue job — runs once per day at 01:00 local time.

For every active loan whose due_date has passed and whose overdue_fee
has not yet been charged, debit the borrower 10.00 € (entry-fee amount)
and record a Transaction of type 'overdue'.
"""
from datetime import datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

OVERDUE_FEE = 10.00


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
    scheduler.start()
    return scheduler
