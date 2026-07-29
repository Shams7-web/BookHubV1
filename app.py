import os
import re
import uuid
from functools import wraps

from flask import Flask, render_template, request, redirect, session, url_for
from werkzeug.utils import secure_filename
from models import Admin, ContactMessage, db, Book

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///bookhub.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024  # 5 MB max upload size

DEFAULT_ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
DEFAULT_ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")

ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png"}
ALLOWED_IMAGE_MIMETYPES = {"image/jpeg", "image/png"}
UPLOAD_FOLDER = os.path.join(app.root_path, "static", "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

db.init_app(app)


def login_required(view_func):
    @wraps(view_func)
    def wrapped_view(*args, **kwargs):
        if not session.get("admin_id"):
            return redirect(url_for("admin_login", next=request.path))
        return view_func(*args, **kwargs)
    return wrapped_view


def allowed_image_file(file_storage):
    filename = file_storage.filename or ""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return ext in ALLOWED_IMAGE_EXTENSIONS and file_storage.mimetype in ALLOWED_IMAGE_MIMETYPES


def save_uploaded_image(file_storage):
    original_name = secure_filename(file_storage.filename)
    ext = original_name.rsplit(".", 1)[-1].lower()
    stored_filename = f"{uuid.uuid4().hex}.{ext}"
    file_storage.save(os.path.join(UPLOAD_FOLDER, stored_filename))
    return stored_filename


def delete_uploaded_image(filename):
    if not filename or filename.startswith(("http://", "https://")):
        return
    file_path = os.path.join(UPLOAD_FOLDER, filename)
    if os.path.isfile(file_path):
        os.remove(file_path)


@app.template_global()
def cover_image_url(image_url):
    if not image_url:
        return url_for("static", filename="img/placeholder.svg")
    if image_url.startswith(("http://", "https://")):
        return image_url
    return url_for("static", filename=f"uploads/{image_url}")


def seed_admin():
    if Admin.query.count() > 0:
        return

    default_admin = Admin(username=DEFAULT_ADMIN_USERNAME)
    default_admin.set_password(DEFAULT_ADMIN_PASSWORD)
    db.session.add(default_admin)
    db.session.commit()
    print(
        f"Created default admin account -> username: '{DEFAULT_ADMIN_USERNAME}', "
        f"password: '{DEFAULT_ADMIN_PASSWORD}'. Please log in and change this password."
    )


def seed_books():
    if Book.query.count() > 0:
        return

    sample_books = [
        Book(title="The Hobbit", author="J.R.R. Tolkien", category="Fantasy",
             price=14.99, stock=25, description="A hobbit's unexpected journey.",
             image_url="https://covers.openlibrary.org/b/id/8323742-L.jpg", published_year=1937),
        Book(title="1984", author="George Orwell", category="Dystopian",
             price=9.99, stock=40, description="A dystopian vision of totalitarian control.",
             image_url="https://covers.openlibrary.org/b/id/7222246-L.jpg", published_year=1949),
        Book(title="To Kill a Mockingbird", author="Harper Lee", category="Classic",
             price=12.50, stock=30, description="A story of racial injustice in the American South.",
             image_url="https://covers.openlibrary.org/b/id/8231856-L.jpg", published_year=1960),
        Book(title="Harry Potter and the Sorcerer's Stone", author="J.K. Rowling", category="Fantasy",
             price=16.99, stock=50, description="A young wizard begins his magical education.",
             image_url="https://covers.openlibrary.org/b/id/7984916-L.jpg", published_year=1997),
        Book(title="The Great Gatsby", author="F. Scott Fitzgerald", category="Classic",
             price=10.99, stock=20, description="A tale of wealth and the American Dream.",
             image_url="https://covers.openlibrary.org/b/id/7222162-L.jpg", published_year=1925),
        Book(title="Dune", author="Frank Herbert", category="Science Fiction",
             price=15.99, stock=18, description="A epic saga set on the desert planet Arrakis.",
             image_url="https://covers.openlibrary.org/b/id/8314879-L.jpg", published_year=1965),
        Book(title="The Da Vinci Code", author="Dan Brown", category="Thriller",
             price=11.99, stock=35, description="A murder mystery involving secret societies.",
             image_url="https://covers.openlibrary.org/b/id/8231990-L.jpg", published_year=2003),
        Book(title="Pride and Prejudice", author="Jane Austen", category="Romance",
             price=8.99, stock=27, description="A romantic tale of manners and marriage.",
             image_url="https://covers.openlibrary.org/b/id/8091016-L.jpg", published_year=1813),
        Book(title="The Alchemist", author="Paulo Coelho", category="Fiction",
             price=13.99, stock=22, description="A shepherd's journey to find his personal legend.",
             image_url="https://covers.openlibrary.org/b/id/8225631-L.jpg", published_year=1988),
        Book(title="Sapiens", author="Yuval Noah Harari", category="Non-Fiction",
             price=18.99, stock=15, description="A brief history of humankind.",
             image_url="https://covers.openlibrary.org/b/id/8375324-L.jpg", published_year=2011),
    ]

    db.session.add_all(sample_books)
    db.session.commit()


with app.app_context():
    db.create_all()
    seed_books()
    seed_admin()


@app.route("/")
def home():
    return render_template("index.html")


BOOKS_PER_PAGE = 12


@app.route("/books")
def books():
    search = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()
    page = request.args.get("page", 1, type=int)

    query = Book.query

    if search:
        like_pattern = f"%{search}%"
        query = query.filter(
            db.or_(Book.title.ilike(like_pattern), Book.author.ilike(like_pattern))
        )

    if category:
        query = query.filter(Book.category == category)

    pagination = query.order_by(Book.id).paginate(page=page, per_page=BOOKS_PER_PAGE, error_out=False)
    categories = [
        row[0] for row in db.session.query(Book.category).distinct().order_by(Book.category).all()
    ]

    return render_template(
        "books.html",
        books=pagination.items,
        pagination=pagination,
        categories=categories,
        search=search,
        selected_category=category,
    )


@app.route("/book/<int:book_id>")
def book_details(book_id):
    book = Book.query.get_or_404(book_id)
    return render_template("book_details.html", book=book)


@app.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip()
        subject = request.form.get("subject", "").strip()
        message = request.form.get("message", "").strip()

        errors = []
        if not full_name:
            errors.append("Full name is required.")
        if not email:
            errors.append("Email address is required.")
        elif not EMAIL_PATTERN.match(email):
            errors.append("Please enter a valid email address.")
        if not subject:
            errors.append("Subject is required.")
        if not message:
            errors.append("Message is required.")

        if errors:
            return render_template("contact.html", errors=errors, form=request.form, success=False)

        new_message = ContactMessage(
            full_name=full_name,
            email=email,
            subject=subject,
            message=message,
        )
        db.session.add(new_message)
        db.session.commit()
        return redirect(url_for("contact", sent=1))

    success = request.args.get("sent") == "1"
    return render_template("contact.html", errors=None, form={}, success=success)


def _safe_next_path(path):
    if path and path.startswith("/") and not path.startswith("//"):
        return path
    return None


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if session.get("admin_id"):
        return redirect(url_for("admin"))

    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        admin_user = Admin.query.filter_by(username=username).first()
        if admin_user and admin_user.check_password(password):
            session.clear()
            session["admin_id"] = admin_user.id
            next_url = _safe_next_path(request.args.get("next"))
            return redirect(next_url or url_for("admin"))

        error = "Invalid username or password."

    return render_template("admin_login.html", error=error)


@app.route("/admin/logout")
def admin_logout():
    session.pop("admin_id", None)
    return redirect(url_for("admin_login"))


@app.route("/admin")
@login_required
def admin():
    all_books = Book.query.all()
    unread_message_count = ContactMessage.query.filter_by(is_read=False).count()
    return render_template("admin.html", books=all_books, unread_message_count=unread_message_count)


@app.route("/admin/add", methods=["GET", "POST"])
@login_required
def add_book():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        author = request.form.get("author", "").strip()
        category = request.form.get("category", "").strip()
        price = request.form.get("price", "").strip()
        description = request.form.get("description", "").strip()
        cover_image = request.files.get("cover_image")

        errors = []
        if not title:
            errors.append("Title is required.")
        if not author:
            errors.append("Author is required.")
        if not category:
            errors.append("Category is required.")

        price_value = None
        if not price:
            errors.append("Price is required.")
        else:
            try:
                price_value = float(price)
                if price_value < 0:
                    errors.append("Price must be a positive number.")
            except ValueError:
                errors.append("Price must be a valid number.")

        image_url = None
        if cover_image and cover_image.filename:
            if allowed_image_file(cover_image):
                image_url = save_uploaded_image(cover_image)
            else:
                errors.append("Cover image must be a JPG, JPEG, or PNG file.")

        if errors:
            return render_template("add_book.html", errors=errors, form=request.form)

        new_book = Book(
            title=title,
            author=author,
            category=category,
            price=price_value,
            description=description,
            image_url=image_url,
        )
        db.session.add(new_book)
        db.session.commit()
        return redirect(url_for("admin"))

    return render_template("add_book.html", errors=None, form={})


@app.route("/admin/edit/<int:book_id>", methods=["GET", "POST"])
@login_required
def edit_book(book_id):
    book = Book.query.get_or_404(book_id)

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        author = request.form.get("author", "").strip()
        category = request.form.get("category", "").strip()
        price = request.form.get("price", "").strip()
        description = request.form.get("description", "").strip()
        cover_image = request.files.get("cover_image")

        errors = []
        if not title:
            errors.append("Title is required.")
        if not author:
            errors.append("Author is required.")
        if not category:
            errors.append("Category is required.")

        price_value = None
        if not price:
            errors.append("Price is required.")
        else:
            try:
                price_value = float(price)
                if price_value < 0:
                    errors.append("Price must be a positive number.")
            except ValueError:
                errors.append("Price must be a valid number.")

        new_image_url = book.image_url
        if cover_image and cover_image.filename:
            if allowed_image_file(cover_image):
                new_image_url = save_uploaded_image(cover_image)
            else:
                errors.append("Cover image must be a JPG, JPEG, or PNG file.")

        if errors:
            return render_template("edit_book.html", errors=errors, book=book, form=request.form)

        if new_image_url != book.image_url:
            delete_uploaded_image(book.image_url)

        book.title = title
        book.author = author
        book.category = category
        book.price = price_value
        book.description = description
        book.image_url = new_image_url
        db.session.commit()
        return redirect(url_for("admin"))

    return render_template("edit_book.html", errors=None, book=book, form=None)


@app.route("/admin/delete/<int:book_id>", methods=["GET", "POST"])
@login_required
def delete_book(book_id):
    book = Book.query.get_or_404(book_id)

    if request.method == "POST":
        if request.form.get("confirm") == "yes":
            delete_uploaded_image(book.image_url)
            db.session.delete(book)
            db.session.commit()
        return redirect(url_for("admin"))

    return render_template("delete_book.html", book=book)


@app.route("/admin/messages")
@login_required
def admin_messages():
    messages = ContactMessage.query.order_by(ContactMessage.created_at.desc()).all()
    return render_template("admin_messages.html", messages=messages)


@app.route("/admin/messages/<int:message_id>")
@login_required
def message_details(message_id):
    message = ContactMessage.query.get_or_404(message_id)
    if not message.is_read:
        message.is_read = True
        db.session.commit()
    return render_template("message_details.html", message=message)


@app.route("/admin/messages/<int:message_id>/toggle-read", methods=["POST"])
@login_required
def toggle_message_read(message_id):
    message = ContactMessage.query.get_or_404(message_id)
    message.is_read = not message.is_read
    db.session.commit()
    next_url = _safe_next_path(request.form.get("next"))
    return redirect(next_url or url_for("admin_messages"))


@app.route("/admin/messages/<int:message_id>/delete", methods=["GET", "POST"])
@login_required
def delete_message(message_id):
    message = ContactMessage.query.get_or_404(message_id)

    if request.method == "POST":
        if request.form.get("confirm") == "yes":
            db.session.delete(message)
            db.session.commit()
        return redirect(url_for("admin_messages"))

    return render_template("delete_message.html", message=message)


if __name__ == "__main__":
    app.run(debug=True)
