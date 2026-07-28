from flask import Flask, render_template, request, redirect, url_for
from models import db, Book

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///bookhub.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)


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


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/books")
def books():
    search = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()

    query = Book.query

    if search:
        like_pattern = f"%{search}%"
        query = query.filter(
            db.or_(Book.title.ilike(like_pattern), Book.author.ilike(like_pattern))
        )

    if category:
        query = query.filter(Book.category == category)

    all_books = query.all()
    categories = [
        row[0] for row in db.session.query(Book.category).distinct().order_by(Book.category).all()
    ]

    return render_template(
        "books.html",
        books=all_books,
        categories=categories,
        search=search,
        selected_category=category,
    )


@app.route("/book/<int:book_id>")
def book_details(book_id):
    book = Book.query.get_or_404(book_id)
    return render_template("book_details.html", book=book)


@app.route("/admin")
def admin():
    all_books = Book.query.all()
    return render_template("admin.html", books=all_books)


@app.route("/admin/add", methods=["GET", "POST"])
def add_book():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        author = request.form.get("author", "").strip()
        category = request.form.get("category", "").strip()
        price = request.form.get("price", "").strip()
        description = request.form.get("description", "").strip()
        image_url = request.form.get("image_url", "").strip()

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
def edit_book(book_id):
    book = Book.query.get_or_404(book_id)

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        author = request.form.get("author", "").strip()
        category = request.form.get("category", "").strip()
        price = request.form.get("price", "").strip()
        description = request.form.get("description", "").strip()
        image_url = request.form.get("image_url", "").strip()

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

        if errors:
            return render_template("edit_book.html", errors=errors, book=book, form=request.form)

        book.title = title
        book.author = author
        book.category = category
        book.price = price_value
        book.description = description
        book.image_url = image_url
        db.session.commit()
        return redirect(url_for("admin"))

    return render_template("edit_book.html", errors=None, book=book, form=None)


@app.route("/admin/delete/<int:book_id>", methods=["GET", "POST"])
def delete_book(book_id):
    book = Book.query.get_or_404(book_id)

    if request.method == "POST":
        if request.form.get("confirm") == "yes":
            db.session.delete(book)
            db.session.commit()
        return redirect(url_for("admin"))

    return render_template("delete_book.html", book=book)


if __name__ == "__main__":
    app.run(debug=True)
