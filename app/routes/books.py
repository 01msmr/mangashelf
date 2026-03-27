from functools import wraps
from datetime import datetime, timezone
from flask import (Blueprint, render_template, redirect, url_for,
                   request, flash, abort, jsonify)
from flask_login import login_required, current_user
from app import db
from app.models import Book, Copy, Loan, User, RebuyItem
from app.services.finance import can_borrow as _can_borrow
from app.services.isbn_lookup import lookup_isbn
from app.services.cover_cache import get_cover_path

books_bp = Blueprint('books', __name__)



def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_admin:
            flash('Admin access required.', 'error')
            return redirect(url_for('books.scan'))
        return f(*args, **kwargs)
    return decorated


# ── Scan landing ─────────────────────────────────────────────────────────────

@books_bp.route('/')
@login_required
def scan():
    return render_template('scan.html')


# ── Book list ─────────────────────────────────────────────────────────────────

@books_bp.route('/books')
@login_required
def book_list():
    q = request.args.get('q', '').strip()
    query = Book.query
    if q:
        like = f'%{q}%'
        query = query.filter(
            db.or_(Book.title.ilike(like), Book.author.ilike(like))
        )
    books = query.order_by(Book.title).all()

    # Pre-compute loan status per book
    book_status = {}
    for book in books:
        available    = len(book.available_copies)
        loaned_cps   = book.loaned_copies
        latest_due   = None
        borrowers    = []
        for copy in loaned_cps:
            loan = Loan.query.filter_by(copy_id=copy.id).first()
            if loan:
                if latest_due is None or loan.due_date > latest_due:
                    latest_due = loan.due_date
                if current_user.is_admin:
                    borrowers.append(loan.user.username)
        book_status[book.id] = {
            'available':  available,
            'loaned':     len(loaned_cps),
            'latest_due': latest_due,
            'borrowers':  borrowers,
        }

    return render_template('books/list.html',
                           books=books,
                           book_status=book_status,
                           search=q)


# ── Book detail ───────────────────────────────────────────────────────────────

@books_bp.route('/book/<isbn>')
@login_required
def book_detail(isbn):
    book = Book.query.filter_by(isbn=isbn).first_or_404()

    loans_info = []
    for copy in book.copies:
        if copy.status == 'loaned':
            loan = Loan.query.filter_by(copy_id=copy.id).first()
            if loan:
                info = {'copy_id': copy.id, 'copy_num': copy.copy_num,
                        'due_date': loan.due_date}
                if current_user.is_admin:
                    info['borrower'] = loan.user.username
                loans_info.append(info)

    # Copies available to mark as broken (admin only)
    breakable = [c for c in book.copies if c.status in ('available', 'loaned')]

    # Current user's active loan for this book (for Return button)
    user_loan = (
        Loan.query
        .join(Copy)
        .filter(Copy.book_id == book.id, Loan.user_id == current_user.id)
        .first()
    )

    borrow_allowed, borrow_reason = _can_borrow(current_user)

    return render_template('books/detail.html',
                           book=book,
                           loans_info=loans_info,
                           breakable=breakable,
                           user_loan=user_loan,
                           borrow_allowed=borrow_allowed,
                           borrow_reason=borrow_reason)


# ── Admin: ISBN metadata fetch (JSON/AJAX) ────────────────────────────────────

@books_bp.route('/admin/book/fetch-isbn')
@login_required
@admin_required
def fetch_isbn_api():
    isbn = request.args.get('isbn', '').strip()
    if not isbn:
        return jsonify({'error': 'ISBN required'}), 400
    meta = lookup_isbn(isbn)
    if not meta or not meta.get('title'):
        return jsonify({'error': 'Not found in OpenLibrary or Google Books'}), 404
    return jsonify(meta)


# ── Admin: add new book ───────────────────────────────────────────────────────

@books_bp.route('/admin/book/add', methods=['GET', 'POST'])
@login_required
@admin_required
def book_add():
    if request.method == 'GET':
        isbn = request.args.get('isbn', '').strip()

        if isbn and Book.query.filter_by(isbn=isbn).first():
            flash(f'ISBN {isbn} is already in the library.', 'info')
            return redirect(url_for('books.book_detail', isbn=isbn))

        meta  = lookup_isbn(isbn) if isbn else {}
        users = User.query.filter_by(active=1).order_by(User.username).all()

        return render_template('books/add.html',
                               isbn=isbn,
                               meta=meta or {},
                               users=users)

    # ── POST ─────────────────────────────────────────────────────────────────
    isbn_val  = request.form.get('isbn',      '').strip()
    title     = request.form.get('title',     '').strip()
    author    = request.form.get('author',    '').strip() or None
    publisher = request.form.get('publisher', '').strip() or None
    published = request.form.get('published', '').strip() or None
    cover_url = request.form.get('cover_url', '').strip() or None
    donor_id  = request.form.get('donor_id')  or None

    if not isbn_val or not title:
        flash('ISBN and title are required.', 'error')
        users = User.query.filter_by(active=1).order_by(User.username).all()
        return render_template('books/add.html',
                               isbn=isbn_val,
                               meta={'title': title, 'author': author,
                                     'publisher': publisher, 'published': published,
                                     'cover_url': cover_url},
                               users=users)

    if Book.query.filter_by(isbn=isbn_val).first():
        flash('A book with this ISBN already exists.', 'error')
        return redirect(url_for('books.book_detail', isbn=isbn_val))

    cover_path = get_cover_path(isbn_val, cover_url) if cover_url else None

    book = Book(
        isbn=isbn_val,
        title=title,
        author=author,
        publisher=publisher,
        published=published,
        cover_path=cover_path,
        added_by=current_user.id,
    )
    db.session.add(book)
    db.session.flush()

    copy = Copy(
        book_id=book.id,
        copy_num=1,
        donated_by=int(donor_id) if donor_id else None,
    )
    db.session.add(copy)
    db.session.commit()

    flash(f'"{title}" added to the library.', 'success')
    return redirect(url_for('books.book_detail', isbn=isbn_val))


# ── Admin: mark copy as broken ────────────────────────────────────────────────

@books_bp.route('/admin/copy/<int:copy_id>/broken', methods=['POST'])
@login_required
@admin_required
def copy_mark_broken(copy_id):
    copy = db.session.get(Copy, copy_id)
    if not copy:
        abort(404)

    note = request.form.get('broken_note', '').strip() or None

    copy.status     = 'broken'
    copy.broken_at  = datetime.now(timezone.utc).isoformat()
    copy.broken_note = note

    db.session.add(RebuyItem(
        book_id=copy.book_id,
        copy_id=copy.id,
        reason=note or 'Marked as broken/unusable',
    ))

    book     = copy.book
    book_isbn = book.isbn
    book_title = book.title

    # Delete book if this was the last active copy
    remaining = [c for c in book.copies if c.id != copy.id and c.status in ('available', 'loaned')]
    if not remaining:
        db.session.delete(book)
        db.session.commit()
        flash(f'Copy #{copy.copy_num} of "{book_title}" marked broken — last copy, book removed from library.', 'warning')
        return redirect(url_for('books.book_list'))

    db.session.commit()
    flash(f'Copy #{copy.copy_num} of "{book_title}" marked broken — added to rebuy list.', 'warning')
    return redirect(url_for('books.book_detail', isbn=book_isbn))
