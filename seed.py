"""
Creates the first admin account and default settings.
Run once after initial setup: python seed.py
"""
from app import create_app, db
from app.models import User, Transaction, Setting


def seed():
    app = create_app()
    with app.app_context():
        # Default configurable settings
        defaults = {
            'max_books_per_user': '3',
            'max_loan_days': '60',
            'default_loan_rate': '0.50',
        }
        for key, value in defaults.items():
            if not db.session.get(Setting, key):
                db.session.add(Setting(key=key, value=value))

        # Default admin — only if no admin exists yet
        if not User.query.filter_by(is_admin=1).first():
            admin = User(
                username='admin',
                is_admin=1,
                setup_required=1,
                guthaben=10.00,
            )
            admin.set_pin('0000')
            db.session.add(admin)
            db.session.flush()

            db.session.add(Transaction(
                user_id=admin.id,
                amount=10.00,
                type='entry_fee',
                description='Entry fee added on account creation.',
            ))
            print('Admin account created:  username=admin  PIN=0000')
            print('Log in and change your PIN immediately!')
        else:
            print('Admin already exists — skipping.')

        # dmn admin user — only if not exists yet
        if not User.query.filter_by(username='dmn').first():
            dmn = User(
                username='dmn',
                is_admin=1,
                setup_required=0,
                guthaben=10.00,
            )
            dmn.set_pin('0099')
            db.session.add(dmn)
            db.session.flush()

            db.session.add(Transaction(
                user_id=dmn.id,
                amount=10.00,
                type='entry_fee',
                description='Entry fee added on account creation.',
            ))
            print('Admin account created:  username=dmn  PIN=0099')
        else:
            print('User dmn already exists — skipping.')

        db.session.commit()
        print('Seed complete.')


if __name__ == '__main__':
    seed()
