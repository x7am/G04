from flask import Flask, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.utils import secure_filename
import os

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///C:/Users/saeed/OneDrive/Desktop/Rented/rented.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.secret_key = "your-secret-key"

# Folders for uploads
UPLOAD_FOLDER = "static/profile_pics"
LISTING_FOLDER = "static/listing_images"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["LISTING_FOLDER"] = LISTING_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(LISTING_FOLDER, exist_ok=True)

db = SQLAlchemy(app)

# --------- Models ---------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=True)
    password = db.Column(db.String(150), nullable=False)
    profile_pic = db.Column(db.String(300), default="default.png")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<User {self.username}>"

class Listing(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=False)
    price = db.Column(db.Float, nullable=False)
    image = db.Column(db.String(300), default="default_listing.png")
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", backref="listings")

# --------- Routes ---------
@app.route("/")
def home():
    listings = Listing.query.order_by(Listing.created_at.desc()).all()
    return render_template("index.html", listings=listings)

# ---- Signup/Login/Profile ----
@app.route("/signup", methods=["GET", "POST"])
def signup():
    error = None
    if request.method == "POST":
        username = request.form.get("username")
        email = request.form.get("email")
        password = request.form.get("password")

        if User.query.filter_by(username=username).first():
            error = "Username already exists!"
        elif User.query.filter_by(email=email).first():
            error = "Email already exists!"
        else: 
            new_user = User(username=username, email=email, password=password)
            db.session.add(new_user)
            db.session.commit()
            return redirect(url_for("login"))

    return render_template("signup.html", error=error)

@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        user = User.query.filter_by(username=username, password=password).first()
        if user:
            session["user_id"] = user.id
            session["username"] = user.username
            return redirect(url_for("home"))
        else:
            error = "Incorrect username or password!"
    return render_template("login.html", error=error)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))

@app.route("/profile", methods=["GET", "POST"])
def profile():
    if "user_id" not in session:
        return redirect(url_for("login"))
    user = User.query.get(session["user_id"])

    if request.method == "POST":
        new_username = request.form.get("username")
        new_email = request.form.get("email")
        new_password = request.form.get("password")
        file = request.files.get("profile_pic")

        if new_username:
            user.username = new_username
            session["username"] = new_username
        if new_email:
            user.email = new_email
        if new_password:
            user.password = new_password
        if file and file.filename:
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
            user.profile_pic = filename

        db.session.commit()
        return redirect(url_for("profile"))

    return render_template("profile.html", user=user)

# ---- Listings CRUD ----
@app.route("/create-listing", methods=["GET", "POST"])
def create_listing():
    if "user_id" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        title = request.form.get("title")
        description = request.form.get("description")
        price = float(request.form.get("price") or 0)
        file = request.files.get("image")
        filename = "default_listing.png"

        if file and file.filename:
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config["LISTING_FOLDER"], filename))

        new_listing = Listing(title=title, description=description, price=price,
                              image=filename, user_id=session["user_id"])
        db.session.add(new_listing)
        db.session.commit()
        return redirect(url_for("home"))

    return render_template("create_listing.html")

@app.route("/edit-listing/<int:id>", methods=["GET", "POST"])
def edit_listing(id):
    listing = Listing.query.get_or_404(id)
    if "user_id" not in session or listing.user_id != session["user_id"]:
        return redirect(url_for("home"))

    if request.method == "POST":
        listing.title = request.form.get("title")
        listing.description = request.form.get("description")
        listing.price = float(request.form.get("price") or listing.price)
        file = request.files.get("image")
        if file and file.filename:
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config["LISTING_FOLDER"], filename))
            listing.image = filename
        db.session.commit()
        return redirect(url_for("home"))

    return render_template("edit_listing.html", listing=listing)

@app.route("/delete-listing/<int:id>", methods=["POST"])
def delete_listing(id):
    listing = Listing.query.get_or_404(id)
    if "user_id" not in session or listing.user_id != session["user_id"]:
        return redirect(url_for("home"))
    db.session.delete(listing)
    db.session.commit()
    return redirect(url_for("home"))

# ---- Context processor ----
@app.context_processor
def inject_user():
    if "user_id" in session:
        user = User.query.get(session["user_id"])
        return dict(user=user)
    return dict(user=None)

# -------- Run App --------
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
