import os
import re
import uuid
from datetime import datetime
from functools import wraps

from flask import Flask, abort, render_template, request, redirect, session, url_for
from sqlalchemy import event
from sqlalchemy.engine import Engine
from werkzeug.utils import secure_filename
from models import Admin, ContactMessage, db, Book, Order, OrderItem


@event.listens_for(Engine, "connect")
def _enable_sqlite_foreign_keys(dbapi_connection, connection_record):
    dbapi_connection.execute("PRAGMA foreign_keys=ON")

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
ORDER_STATUSES = ["Pending", "Processing", "Shipped", "Delivered", "Cancelled"]

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


@app.template_global()
def cart_item_count():
    cart = session.get("cart", {})
    return sum(cart.values())


@app.route("/cart/add/<int:book_id>", methods=["POST"])
def add_to_cart(book_id):
    Book.query.get_or_404(book_id)
    quantity = request.form.get("quantity", 1, type=int)
    if not quantity or quantity < 1:
        quantity = 1

    cart = session.get("cart", {})
    key = str(book_id)
    cart[key] = cart.get(key, 0) + quantity
    session["cart"] = cart

    next_url = _safe_next_path(request.form.get("next"))
    return redirect(next_url or url_for("books"))


def _get_cart_items():
    cart_data = session.get("cart", {})
    book_ids = [int(book_id) for book_id in cart_data]
    books_by_id = {book.id: book for book in Book.query.filter(Book.id.in_(book_ids)).all()}

    cart_items = []
    cart_total = 0.0
    for book_id_str, quantity in cart_data.items():
        book = books_by_id.get(int(book_id_str))
        if not book:
            continue
        subtotal = book.price * quantity
        cart_total += subtotal
        cart_items.append({"book": book, "quantity": quantity, "subtotal": subtotal})

    return cart_items, cart_total


@app.route("/cart")
def cart():
    cart_items, cart_total = _get_cart_items()
    return render_template("cart.html", cart_items=cart_items, cart_total=cart_total)


@app.route("/cart/update/<int:book_id>", methods=["POST"])
def update_cart_item(book_id):
    quantity = request.form.get("quantity", 1, type=int)
    cart = session.get("cart", {})
    key = str(book_id)
    if key in cart:
        if quantity and quantity > 0:
            cart[key] = quantity
        else:
            cart.pop(key)
        session["cart"] = cart
    return redirect(url_for("cart"))


@app.route("/cart/remove/<int:book_id>", methods=["POST"])
def remove_from_cart(book_id):
    cart = session.get("cart", {})
    cart.pop(str(book_id), None)
    session["cart"] = cart
    return redirect(url_for("cart"))


@app.route("/cart/clear", methods=["POST"])
def clear_cart():
    session["cart"] = {}
    return redirect(url_for("cart"))


@app.route("/checkout", methods=["GET", "POST"])
def checkout():
    cart_items, cart_total = _get_cart_items()

    if not cart_items:
        return redirect(url_for("cart"))

    errors = None
    form = {}
    submitted = request.args.get("submitted") == "1"

    if request.method == "POST":
        form = request.form
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip()
        phone = request.form.get("phone", "").strip()
        address_line1 = request.form.get("address_line1", "").strip()
        address_line2 = request.form.get("address_line2", "").strip()
        city = request.form.get("city", "").strip()
        state = request.form.get("state", "").strip()
        postal_code = request.form.get("postal_code", "").strip()
        country = request.form.get("country", "").strip()

        errors = []
        if not full_name:
            errors.append("Full name is required.")
        if not email:
            errors.append("Email address is required.")
        elif not EMAIL_PATTERN.match(email):
            errors.append("Please enter a valid email address.")
        if not phone:
            errors.append("Phone number is required.")
        if not address_line1:
            errors.append("Address is required.")
        if not city:
            errors.append("City is required.")
        if not state:
            errors.append("State/Province is required.")
        if not postal_code:
            errors.append("Postal/ZIP code is required.")
        if not country:
            errors.append("Country is required.")

        if errors:
            return render_template(
                "checkout.html",
                cart_items=cart_items,
                cart_total=cart_total,
                errors=errors,
                form=form,
                submitted=False,
            )

        session["checkout_info"] = {
            "full_name": full_name,
            "email": email,
            "phone": phone,
            "address_line1": address_line1,
            "address_line2": address_line2,
            "city": city,
            "state": state,
            "postal_code": postal_code,
            "country": country,
        }
        return redirect(url_for("checkout", submitted=1))

    if submitted:
        form = session.get("checkout_info", {})

    return render_template(
        "checkout.html",
        cart_items=cart_items,
        cart_total=cart_total,
        errors=errors,
        form=form,
        submitted=submitted,
    )


def _generate_order_number():
    while True:
        candidate = f"ORD-{datetime.utcnow():%Y%m%d}-{uuid.uuid4().hex[:6].upper()}"
        if not Order.query.filter_by(order_number=candidate).first():
            return candidate


@app.route("/place-order", methods=["POST"])
def place_order():
    cart_items, cart_total = _get_cart_items()
    checkout_info = session.get("checkout_info")

    if not cart_items:
        return redirect(url_for("cart"))
    if not checkout_info:
        return redirect(url_for("checkout"))

    order = Order(
        order_number=_generate_order_number(),
        full_name=checkout_info["full_name"],
        email=checkout_info["email"],
        phone=checkout_info["phone"],
        address_line1=checkout_info["address_line1"],
        address_line2=checkout_info.get("address_line2", ""),
        city=checkout_info["city"],
        state=checkout_info["state"],
        postal_code=checkout_info["postal_code"],
        country=checkout_info["country"],
        total=cart_total,
        status="Pending",
    )

    for item in cart_items:
        order.items.append(OrderItem(
            book_id=item["book"].id,
            book_title=item["book"].title,
            unit_price=item["book"].price,
            quantity=item["quantity"],
            subtotal=item["subtotal"],
        ))

    db.session.add(order)
    db.session.commit()

    session["cart"] = {}
    session.pop("checkout_info", None)

    order_history = session.get("order_history", [])
    if order.order_number not in order_history:
        order_history.append(order.order_number)
    session["order_history"] = order_history

    return redirect(url_for("order_confirmation", order_number=order.order_number))


@app.route("/order/confirmation/<order_number>")
def order_confirmation(order_number):
    order = Order.query.filter_by(order_number=order_number).first_or_404()
    return render_template("order_confirmation.html", order=order)


@app.route("/orders")
def order_history():
    order_numbers = session.get("order_history", [])
    orders = []
    if order_numbers:
        orders = (
            Order.query.filter(Order.order_number.in_(order_numbers))
            .order_by(Order.created_at.desc())
            .all()
        )
    return render_template("order_history.html", orders=orders)


@app.route("/orders/<order_number>")
def order_details(order_number):
    if order_number not in session.get("order_history", []):
        abort(404)
    order = Order.query.filter_by(order_number=order_number).first_or_404()
    return render_template("order_details.html", order=order)


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


@app.route("/admin/orders")
@login_required
def admin_orders():
    search = request.args.get("q", "").strip()
    status_filter = request.args.get("status", "").strip()

    query = Order.query

    if search:
        like_pattern = f"%{search}%"
        query = query.filter(
            db.or_(
                Order.order_number.ilike(like_pattern),
                Order.full_name.ilike(like_pattern),
                Order.email.ilike(like_pattern),
            )
        )

    if status_filter:
        query = query.filter(Order.status == status_filter)

    orders = query.order_by(Order.created_at.desc()).all()

    return render_template(
        "admin_orders.html",
        orders=orders,
        statuses=ORDER_STATUSES,
        search=search,
        selected_status=status_filter,
    )


@app.route("/admin/orders/<int:order_id>")
@login_required
def admin_order_details(order_id):
    order = Order.query.get_or_404(order_id)
    return render_template("admin_order_details.html", order=order, statuses=ORDER_STATUSES)


@app.route("/admin/orders/<int:order_id>/status", methods=["POST"])
@login_required
def update_order_status(order_id):
    order = Order.query.get_or_404(order_id)
    new_status = request.form.get("status", "").strip()
    if new_status in ORDER_STATUSES:
        order.status = new_status
        db.session.commit()
    next_url = _safe_next_path(request.form.get("next"))
    return redirect(next_url or url_for("admin_orders"))


if __name__ == "__main__":
    app.run(debug=True)
