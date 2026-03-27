"""
Simple in-app translations for en / de / schwaebisch.
Usage in templates:  {{ _t('key') }}
"""

_STRINGS = {
    # ── Navigation & header ──────────────────────────────────────────────
    'nav.books':        {'en': 'All Books',       'de': 'Alle Bücher',      'schwaebisch': 'All Büecher'},
    'nav.account':      {'en': 'My Account',      'de': 'Mein Konto',       'schwaebisch': 'Moi Konto'},
    'nav.scan':         {'en': 'Scan',             'de': 'Scannen',          'schwaebisch': 'Scannä'},
    'nav.admin':        {'en': 'Admin Section',    'de': 'Admin-Bereich',    'schwaebisch': 'Admin-Bereich'},
    'nav.logout':       {'en': 'Logout',           'de': 'Abmelden',         'schwaebisch': 'Abmelde'},
    'nav.back':         {'en': '← Back',           'de': '← Zurück',         'schwaebisch': '← Zrück'},

    # ── Auth ─────────────────────────────────────────────────────────────
    'auth.welcome':     {'en': 'Welcome to',       'de': 'Willkommen bei',   'schwaebisch': 'Willkomme bei'},
    'auth.subtitle':    {'en': 'Enter your username and PIN to continue.',
                         'de': 'Benutzername und PIN eingeben.',
                         'schwaebisch': 'Benutzername ond PIN eigebe.'},
    'auth.username':    {'en': 'Username',          'de': 'Benutzername',     'schwaebisch': 'Benutzername'},
    'auth.pin':         {'en': 'PIN',               'de': 'PIN',              'schwaebisch': 'PIN'},
    'auth.login':       {'en': 'Log In',            'de': 'Anmelden',         'schwaebisch': 'Ei logga'},
    'auth.no_account':  {'en': 'No account yet?',  'de': 'Noch kein Konto?', 'schwaebisch': 'No koi Konto?'},
    'auth.create':      {'en': 'Create one',        'de': 'Registrieren',     'schwaebisch': 'Eins machet'},
    'auth.hint_user':   {'en': 'Your library account name',
                         'de': 'Dein Bibliotheks-Login',
                         'schwaebisch': 'Doi Bibliotheks-Name'},
    'auth.hint_pin':    {'en': '4-digit number',   'de': '4-stellige Zahl',  'schwaebisch': '4-stelligi Zahl'},

    # ── Scan page ────────────────────────────────────────────────────────
    'scan.title':       {'en': 'Scan a Book',       'de': 'Buch scannen',     'schwaebisch': 'Buech scannä'},
    'scan.instruction': {'en': 'Point the scanner at any book\'s barcode to borrow or return it.',
                         'de': 'Scanner auf den Barcode halten — zum Ausleihen oder Zurückgeben.',
                         'schwaebisch': 'Scanner uff de Barcode halde — zum Ausleihä oder Zrückgebe.'},
    'scan.camera':      {'en': 'Scan barcode',      'de': 'Barcode scannen',  'schwaebisch': 'Barcode scannä'},
    'scan.add_book':    {'en': '+ Add Book',        'de': '+ Buch hinzufügen','schwaebisch': '+ Buech dazuetue'},

    # ── Account page ─────────────────────────────────────────────────────
    'acct.balance':     {'en': 'Balance',           'de': 'Guthaben',         'schwaebisch': 'Guthabe'},
    'acct.can_borrow':  {'en': 'You can borrow books.',
                         'de': 'Du kannst Bücher ausleihen.',
                         'schwaebisch': 'Du kannsch Büecher ausleihä.'},
    'acct.warn_funds':  {'en': 'Add funds — you need more than 10.00 € to borrow.',
                         'de': 'Guthaben aufladen — du brauchst mehr als 10,00 € zum Ausleihen.',
                         'schwaebisch': 'Geld nacheege — du bruachsch mehr als 10,00 € zum Ausleihä.'},
    'acct.empty':       {'en': 'Account empty — please contact an admin.',
                         'de': 'Konto leer — bitte einen Admin kontaktieren.',
                         'schwaebisch': 'Konto leer — bitte an Admin bescheid sage.'},
    'acct.add_funds':   {'en': 'Add Funds',         'de': 'Guthaben aufladen','schwaebisch': 'Geld nacheege'},
    'acct.topup_hint':  {'en': 'Put the cash in the box, then tap the amount above.',
                         'de': 'Geld in die Box legen, dann Betrag antippen.',
                         'schwaebisch': 'Schmeiß\'s Geld nei, dann drück de Betrag.'},
    'acct.qr_hint':     {'en': 'Scan with your phone to use its camera as a barcode scanner',
                         'de': 'Mit dem Handy scannen, um die Kamera als Barcode-Scanner zu nutzen',
                         'schwaebisch': 'Mit\'m Handy scannä — als Barcode-Scanner bnutzä'},
    'acct.active_loans':{'en': 'Active Loans',      'de': 'Aktive Ausleihen', 'schwaebisch': 'Aktivi Ausleihä'},
    'acct.activity':    {'en': 'Recent Activity',   'de': 'Letzte Aktivität', 'schwaebisch': 'Letschti Aktivität'},
    'acct.no_loans':    {'en': 'No books currently borrowed.',
                         'de': 'Derzeit keine ausgeliehenen Bücher.',
                         'schwaebisch': 'Grad koi Büecher ausgeliehä.'},
    'acct.no_txns':     {'en': 'No transactions yet.',
                         'de': 'Noch keine Transaktionen.',
                         'schwaebisch': 'No koi Transaktionä.'},
    'acct.change_pin':  {'en': 'Change PIN',        'de': 'PIN ändern',       'schwaebisch': 'PIN ändere'},
    'acct.language':    {'en': 'Language',          'de': 'Sprache',          'schwaebisch': 'Sprach'},

    # ── Loans ────────────────────────────────────────────────────────────
    'loan.borrow':      {'en': 'Take Out',          'de': 'Ausleihen',        'schwaebisch': 'Ausleihä'},
    'loan.return':      {'en': 'Return',            'de': 'Zurückgeben',      'schwaebisch': 'Zrückgebe'},
    'loan.due':         {'en': 'Due',               'de': 'Fällig',           'schwaebisch': 'Fällig'},
    'loan.overdue':     {'en': 'Overdue',           'de': 'Überfällig',       'schwaebisch': 'Überfällig'},

    # ── Books ────────────────────────────────────────────────────────────
    'book.available':   {'en': 'Available',         'de': 'Verfügbar',        'schwaebisch': 'No do'},
    'book.add':         {'en': '+ Add',             'de': '+ Hinzufügen',     'schwaebisch': '+ Dazuetue'},

    # ── Admin ────────────────────────────────────────────────────────────
    'admin.section':    {'en': 'Admin Section',     'de': 'Admin-Bereich',    'schwaebisch': 'Admin-Bereich'},
    'admin.users':      {'en': 'Users',             'de': 'Benutzer',         'schwaebisch': 'Leit'},
    'admin.overdue':    {'en': 'Overdue',           'de': 'Überfällig',       'schwaebisch': 'Überfällig'},
    'admin.settings':   {'en': 'Settings',          'de': 'Einstellungen',    'schwaebisch': 'Einstellunge'},
    'admin.rebuy':      {'en': 'Rebuy',             'de': 'Nachkauf',         'schwaebisch': 'Nachkaufe'},

    # ── Buttons / common ─────────────────────────────────────────────────
    'btn.save':         {'en': 'Save',              'de': 'Speichern',        'schwaebisch': 'Speichera'},
    'btn.go':           {'en': 'Go',                'de': 'Los',              'schwaebisch': 'Los'},
    'btn.add':          {'en': 'Add',               'de': 'Hinzufügen',       'schwaebisch': 'Dazuetue'},
    'btn.confirm':      {'en': 'Confirm',           'de': 'Bestätigen',       'schwaebisch': 'Bestätige'},
    'btn.cancel':       {'en': 'Cancel',            'de': 'Abbrechen',        'schwaebisch': 'Abbrechä'},
}

SUPPORTED_LANGS = ['en', 'de', 'schwaebisch']
LANG_LABELS     = {'en': 'EN', 'de': 'DE', 'schwaebisch': 'SCHWÄB'}
DEFAULT_LANG    = 'en'


def get_translator(lang: str):
    """Return a _t() function bound to the given language."""
    if lang not in SUPPORTED_LANGS:
        lang = DEFAULT_LANG

    def _t(key: str) -> str:
        entry = _STRINGS.get(key)
        if not entry:
            return key  # fallback: return the key itself
        return entry.get(lang) or entry.get(DEFAULT_LANG) or key

    return _t
