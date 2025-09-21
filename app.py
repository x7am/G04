import os
from flask import Flask, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import smtplib
from email.mime.text import MIMEText
from flask import redirect, url_for, flash



app = Flask(__name__)

# Database setup
basedir = os.path.abspath(os.path.dirname(__file__))
instance_folder = os.path.join(basedir, "instance")
os.makedirs(instance_folder, exist_ok=True)

db_path = os.path.join(instance_folder, "rented.db")
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + db_path
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.secret_key = "your-secret-key"

# Upload folders
UPLOAD_FOLDER = "static/profile_pics"
LISTING_FOLDER = "static/listing_images"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["LISTING_FOLDER"] = LISTING_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(LISTING_FOLDER, exist_ok=True)

# Email setup
ADMIN_EMAIL = "miniit799@gmail.com"
ADMIN_PASSWORD = "cldn gswl pyop reqw"  # ⚠️ app password (not normal Gmail password)
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587

# Database instance
db = SQLAlchemy(app)
app.jinja_env.globals['datetime'] = datetime


# ------------------------
# MODELS
# ------------------------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=True)
    password = db.Column(db.String(150), nullable=False)
    profile_pic = db.Column(db.String(300), default="profile_pics/default.png")
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Listing(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=False)
    price = db.Column(db.Float, nullable=False)
    image = db.Column(db.String(300), default="default_listing.png")
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", backref="listings")


# ------------------------
# ROUTES
# ------------------------
@app.route("/")
def home():
    listings = Listing.query.order_by(Listing.created_at.desc()).all()
    return render_template("index.html", listings=listings)


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
            hashed_password = generate_password_hash(password)
            new_user = User(username=username, email=email, password=hashed_password)
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

        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            session["user_id"] = user.id
            session["username"] = user.username
            if user.is_admin:
                return redirect(url_for("admin_dashboard"))
            else:
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
            user.password = generate_password_hash(new_password)
        if file and file.filename:
            filename = secure_filename(file.filename)
            save_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            file.save(save_path)
            user.profile_pic = f"profile_pics/{filename}"

        db.session.commit()
        return redirect(url_for("profile"))

    return render_template("profile.html", user=user)


@app.route("/create_listing", methods=["GET", "POST"])
def create_listing():
    if "user_id" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        title = request.form["title"]
        description = request.form["description"]
        price = request.form["price"]

        image_file = request.files.get("image")
        image_filename = None
        if image_file and image_file.filename != "":
            filename = secure_filename(image_file.filename)
            save_path = os.path.join(app.config["LISTING_FOLDER"], filename)
            image_file.save(save_path)
            image_filename = filename

        new_listing = Listing(
            title=title,
            description=description,
            price=price,
            image=image_filename,
            user_id=session["user_id"]
        )
        db.session.add(new_listing)
        db.session.commit()
        return redirect(url_for("home"))

    return render_template("create_listing.html")


@app.route("/edit_listing/<int:id>", methods=["GET", "POST"])
def edit_listing(id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    listing = Listing.query.get_or_404(id)
    user = User.query.get(session["user_id"])

    if listing.user_id != session["user_id"] and not user.is_admin:
        return "Unauthorized", 403

    if request.method == "POST":
        listing.title = request.form["title"]
        listing.description = request.form["description"]
        listing.price = request.form["price"]

        image_file = request.files.get("image")
        if image_file and image_file.filename != "":
            filename = secure_filename(image_file.filename)
            save_path = os.path.join(app.config["LISTING_FOLDER"], filename)
            image_file.save(save_path)
            listing.image = filename

        db.session.commit()
        return redirect(url_for("home"))

    return render_template("edit_listing.html", listing=listing)



@app.route("/delete-listing/<int:id>", methods=["POST"])
def delete_listing(id):
    listing = Listing.query.get_or_404(id)
    if "user_id" not in session:
        return redirect(url_for("login"))

    user = User.query.get(session["user_id"])

    # Allow owner OR admin
    if listing.user_id != session["user_id"] and not user.is_admin:
        return redirect(url_for("home"))

    db.session.delete(listing)
    db.session.commit()
    return redirect(url_for("home"))


from flask import redirect, url_for, flash

@app.route("/admin")
def admin_dashboard():
    if "user_id" not in session:
        return redirect(url_for("login"))

    user = User.query.get(session["user_id"])
    if not user.is_admin:  # check if user is not admin
        return "Access denied", 403

    users = User.query.all()
    return render_template("admin_dashboard.html", users=users, title="Admin Dashboard")




@app.route("/edit/<int:user_id>", methods=["GET", "POST"])
def edit_user(user_id):
    user = User.query.get_or_404(user_id)
    if request.method == "POST":
        user.username = request.form.get("username")
        password = request.form.get("password")
        if password:
            user.password = generate_password_hash(password)
        db.session.commit()
        return redirect(url_for("admin_dashboard"))

    return render_template("edit_user.html", user=user, title="Edit User")


@app.route("/delete/<int:user_id>")
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()
    return redirect(url_for("admin_dashboard"))


# ------------------------
# CREATE USER (ADMIN ONLY)
# ------------------------
@app.route("/create_user", methods=["GET", "POST"])
def create_user():
    if "user_id" not in session:
        return redirect(url_for("login"))

    admin = User.query.get(session["user_id"])
    if not admin.is_admin:
        return "Unauthorized", 403

    if request.method == "POST":
        username = request.form.get("username")
        email = request.form.get("email")
        password = request.form.get("password")

        # Email must be unique
        if User.query.filter_by(username=username).first():
            return "Username already exists!"
        if email and User.query.filter_by(email=email).first():
            return "Email already exists!"

        hashed_password = generate_password_hash(password)
        new_user = User(username=username, email=email, password=hashed_password, is_admin=False)
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for("admin_dashboard"))

    return render_template("create_user.html", title="Create User")


@app.route("/contact")
def contact():
    return render_template("contact.html", title="Contact Us")


@app.route("/send", methods=["POST"])
def send_email():
    name = request.form["name"]
    user_email = request.form["email"]
    subject = request.form["subject"]
    message = request.form["message"]

    body = f"Name: {name}\nEmail: {user_email}\n\nMessage:\n{message}"
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = ADMIN_EMAIL
    msg["To"] = ADMIN_EMAIL

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(ADMIN_EMAIL, ADMIN_PASSWORD)
            server.send_message(msg)

            reply = MIMEText(
                f"Hello {name},\n\nThanks for contacting us! "
                "We received your message and will reply soon.\n\n- Rented Team"
            )
            reply["Subject"] = "We received your message"
            reply["From"] = ADMIN_EMAIL
            reply["To"] = user_email
            server.send_message(reply)

        return "✅ Message sent and auto-reply delivered."
    except Exception as e:
        return f"❌ Error sending email: {e}"


# ------------------------
# CONTEXT PROCESSOR
# ------------------------
@app.context_processor
def inject_user():
    if "user_id" in session:
        user = User.query.get(session["user_id"])
        return dict(user=user)
    return dict(user=None)


if __name__ == "__main__":
    with app.app_context():
        db.create_all()

        if not User.query.filter_by(is_admin=True).first():
            admin = User(
                username="Admin",
                email="admin@example.com",
                password=generate_password_hash("123"),
                is_admin=True
            )
            db.session.add(admin)
            db.session.commit()
            print("Default admin created: username=Admin, password=admin123")

        print(f"Database created at: {db_path}")

    app.run(debug=True)
