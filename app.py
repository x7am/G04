import os
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import smtplib
from email.mime.text import MIMEText
# reportlab (used for PDF generation)
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.styles import getSampleStyleSheet
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "templates"),
    static_folder=os.path.join(BASE_DIR, "static")
)

# ------------------------
# CONFIGURATION
# ------------------------
basedir = os.path.abspath(os.path.dirname(__file__))
instance_folder = os.path.join(basedir, "instance")
os.makedirs(instance_folder, exist_ok=True)

load_dotenv()  # loads variables from .env

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET", "supersecretkey")

# Choose local or online DB
USE_LOCAL_DB = os.getenv("USE_LOCAL_DB", "True") == "True"

if USE_LOCAL_DB:
    app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///rented.db"
else:
    DB_HOST = os.getenv("DB_HOST")
    DB_PORT = os.getenv("DB_PORT")
    DB_NAME = os.getenv("DB_NAME")
    DB_USER = os.getenv("DB_USER")
    DB_PASS = os.getenv("DB_PASS")
    app.config['SQLALCHEMY_DATABASE_URI'] = f"postgresql+psycopg2://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False


app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
# use an env var for secret in production
app.secret_key = os.getenv("FLASK_SECRET", "your-secret-key")

# Upload folders
UPLOAD_FOLDER = "static/profile_pics"
LISTING_FOLDER = "static/listing_images"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["LISTING_FOLDER"] = LISTING_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(LISTING_FOLDER, exist_ok=True)

# Email config (use environment variables for production)
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "miniit799@gmail.com")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "cldn gswl pyop reqw")  # ideally from env
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))

# Database - single instance (do not create multiple)
db = SQLAlchemy()
db.init_app(app)

# expose datetime utilities to Jinja
app.jinja_env.globals['datetime'] = datetime

# ------------------------
# TIME AGO HELPER
# ------------------------
def time_ago(dt):
    if not dt:
        return ""
    now = datetime.utcnow()
    if dt.tzinfo is not None:
        dt = dt.astimezone(tz=None).replace(tzinfo=None)
    diff = now - dt
    seconds = int(diff.total_seconds())
    if seconds < 0:
        seconds = 0
    minutes = seconds // 60
    hours = minutes // 60
    days = hours // 24
    weeks = days // 7
    months = days // 30
    years = days // 365
    if seconds < 60:
        return f"{seconds} seconds ago" if seconds != 1 else "1 second ago"
    if minutes < 60:
        return f"{minutes} minutes ago" if minutes != 1 else "1 minute ago"
    if hours < 24:
        return f"{hours} hours ago" if hours != 1 else "1 hour ago"
    if days < 7:
        return f"{days} days ago" if days != 1 else "1 day ago"
    if weeks < 5:
        return f"{weeks} weeks ago" if weeks != 1 else "1 week ago"
    if months < 12:
        return f"{months} months ago" if months != 1 else "1 month ago"
    return f"{years} years ago" if years != 1 else "1 year ago"

app.jinja_env.filters["timeago"] = time_ago
app.jinja_env.globals["time_ago"] = time_ago

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

class RentRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    days = db.Column(db.Integer, nullable=False)
    description = db.Column(db.Text)
    status = db.Column(db.String(50), default="Pending")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    listing_id = db.Column(db.Integer, db.ForeignKey('listing.id'))
    renter_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    listing = db.relationship("Listing", backref="requests")
    renter = db.relationship("User")

# ------------------------
# ROUTES
# ------------------------
@app.route("/")
def home():
    listings = Listing.query.order_by(Listing.created_at.desc()).all()
    # Mark listings that are rented (have any approved request)
    for listing in listings:
        listing.is_rented = any(req.status == "Approved" for req in listing.requests)
    return render_template("index.html", listings=listings)

# --- Auth Routes ---
@app.route("/signup", methods=["GET", "POST"])
def signup():
    error = None
    if request.method == "POST":
        username = request.form.get("username")
        email = request.form.get("email")
        password = request.form.get("password")
        if User.query.filter_by(username=username).first():
            error = "Username already exists!"
        elif email and User.query.filter_by(email=email).first():
            error = "Email already exists!"
        else:
            hashed_password = generate_password_hash(password)
            new_user = User(username=username, email=email, password=hashed_password)
            db.session.add(new_user)
            db.session.commit()
            flash("Account created successfully!", "success")
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
            session["is_admin"] = user.is_admin
            flash(f"Welcome back, {user.username}!", "success")
            if user.is_admin:
                return redirect(url_for("admin_dashboard"))
            else:
                return redirect(url_for("home"))
        else:
            error = "Incorrect username or password!"
            flash(error, "error")
    return render_template("login.html", error=error)

@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully.", "success")
    return redirect(url_for("home"))

# --- Profile Routes ---
@app.route("/profile")
def profile():
    if "user_id" not in session:
        return redirect(url_for("login"))
    user = User.query.get(session["user_id"])
    return render_template("profile.html", user=user)

@app.route("/update-profile", methods=["POST"])
def update_profile():
    if "user_id" not in session:
        return redirect(url_for("login"))
    user = User.query.get(session["user_id"])
    username = request.form.get("username")
    email = request.form.get("email")
    profile_pic = request.files.get("profile_pic")
    if username:
        user.username = username
        session["username"] = username
    if email:
        existing_email_user = User.query.filter(User.email == email, User.id != user.id).first()
        if existing_email_user:
            flash("Email is already taken by another user.", "error")
            return redirect(url_for("profile"))
        user.email = email
    if profile_pic and profile_pic.filename:
        filename = secure_filename(profile_pic.filename)
        save_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        profile_pic.save(save_path)
        user.profile_pic = f"profile_pics/{filename}"
    db.session.commit()
    flash("Profile updated successfully!", "success")
    return redirect(url_for("profile"))

@app.route("/update-password", methods=["POST"])
def update_password():
    if "user_id" not in session:
        return redirect(url_for("login"))
    user = User.query.get(session["user_id"])
    current_password = request.form.get("current_password")
    new_password = request.form.get("new_password")
    confirm_password = request.form.get("confirm_password")
    if not check_password_hash(user.password, current_password):
        flash("Current password is incorrect.", "error")
        return redirect(url_for("profile"))
    if new_password != confirm_password:
        flash("New password and confirmation do not match.", "error")
        return redirect(url_for("profile"))
    user.password = generate_password_hash(new_password)
    db.session.commit()
    flash("Password updated successfully!", "success")
    return redirect(url_for("profile"))

@app.route("/delete-account", methods=["POST"])
def delete_account():
    if "user_id" not in session:
        return redirect(url_for("login"))
    user = User.query.get(session["user_id"])
    db.session.delete(user)
    db.session.commit()
    session.clear()
    flash("Your account has been deleted.", "success")
    return redirect(url_for("home"))

# --- Listing Routes ---
@app.route("/create_listing", methods=["GET", "POST"])
def create_listing():
    if "user_id" not in session:
        return redirect(url_for("login"))
    if request.method == "POST":
        title = request.form["title"]
        description = request.form["description"]
        price = request.form["price"]
        # try casting price to float; keep existing behaviour if invalid
        try:
            price_value = float(price)
        except Exception:
            price_value = 0.0
        image_file = request.files.get("image")
        image_filename = None
        if image_file and image_file.filename != "":
            filename = secure_filename(image_file.filename)
            save_path = os.path.join(app.config["LISTING_FOLDER"], filename)
            image_file.save(save_path)
            image_filename = filename
        image_to_store = image_filename if image_filename else "default_listing.png"
        new_listing = Listing(
            title=title,
            description=description,
            price=price_value,
            image=image_to_store,
            user_id=session["user_id"]
        )
        db.session.add(new_listing)
        db.session.commit()
        flash("Listing created successfully!", "success")
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
        price = request.form["price"]
        try:
            listing.price = float(price)
        except Exception:
            pass
        image_file = request.files.get("image")
        if image_file and image_file.filename != "":
            filename = secure_filename(image_file.filename)
            save_path = os.path.join(app.config["LISTING_FOLDER"], filename)
            image_file.save(save_path)
            listing.image = filename
        db.session.commit()
        flash("Listing updated successfully!", "success")
        return redirect(url_for("home"))
    return render_template("edit_listing.html", listing=listing)

@app.route("/listing/<int:id>/delete", methods=["POST", "GET"])
def delete_listing(id):
    if "user_id" not in session:
        flash("You must be logged in to delete a listing.", "error")
        return redirect(url_for("login"))
    listing = Listing.query.get_or_404(id)
    if listing.user_id != session["user_id"] and not session.get("is_admin"):
        flash("You don’t have permission to delete this listing.", "error")
        return redirect(url_for("view_listing", id=id))
    db.session.delete(listing)
    db.session.commit()
    flash("Listing deleted successfully.", "success")
    return redirect(url_for("home"))

# --- Rent Request ---
@app.route("/listing/<int:id>", methods=["GET", "POST"])
def view_listing(id):
    listing = Listing.query.get_or_404(id)

    # Check if there is any approved request
    approved_request = next((req for req in listing.requests if req.status == "Approved"), None)

    if request.method == "POST":
        # If already rented, prevent new requests
        if approved_request:
            flash("This listing is already rented. You cannot send a request.", "error")
            return redirect(url_for("view_listing", id=listing.id))

        if "user_id" not in session:
            flash("You must be logged in to send a request.", "error")
            return redirect(url_for("login"))

        existing_request = RentRequest.query.filter_by(
            listing_id=listing.id,
            renter_id=session["user_id"]
        ).first()
        if existing_request:
            flash("You already have a request for this listing. You can edit or delete it.", "warning")
            return redirect(url_for("view_listing", id=listing.id))

        days = request.form.get("days")
        description = request.form.get("description")
        new_request = RentRequest(
            days=int(days) if days else 1,
            description=description,
            listing_id=listing.id,
            renter_id=session["user_id"]
        )
        db.session.add(new_request)
        db.session.commit()
        flash("Your rental request has been sent!", "success")
        return redirect(url_for("view_listing", id=listing.id))

    return render_template(
        "view_listing.html",
        listing=listing,
        requests=listing.requests,
        approved_request=approved_request,  # pass to template
        current_time=datetime.utcnow()       # so templates can compute timeago
    )

@app.route("/edit_request/<int:request_id>", methods=["GET", "POST"])
def edit_request(request_id):
    rent_request = RentRequest.query.get_or_404(request_id)
    if "user_id" not in session or rent_request.renter_id != session["user_id"]:
        return "Unauthorized", 403

    if request.method == "POST":
        rent_request.days = int(request.form.get("days", rent_request.days))
        rent_request.description = request.form.get("description", rent_request.description)
        rent_request.status = "Pending"  # Reset status on edit
        db.session.commit()
        flash("Request updated and reset to Pending.", "success")
        return redirect(url_for("view_listing", id=rent_request.listing_id))

    return render_template("edit_request.html", rent_request=rent_request)


@app.route("/delete_request/<int:request_id>", methods=["POST"])
def delete_request(request_id):
    rent_request = RentRequest.query.get_or_404(request_id)
    if "user_id" not in session or rent_request.renter_id != session["user_id"]:
        return "Unauthorized", 403
    listing_id = rent_request.listing_id
    db.session.delete(rent_request)
    db.session.commit()
    flash("Your rental request has been deleted.", "info")
    return redirect(url_for("view_listing", id=listing_id))

@app.route("/approve_request/<int:request_id>", methods=["POST"])
def approve_request(request_id):
    rent_request = RentRequest.query.get_or_404(request_id)
    listing = rent_request.listing

    if "user_id" not in session or session["user_id"] != listing.user_id:
        return "Unauthorized", 403

    # Decline all other requests
    for r in listing.requests:
        if r.id != rent_request.id:
            r.status = "Declined"

    rent_request.status = "Approved"
    db.session.commit()
    flash("Request approved! PDF now available.", "success")
    return redirect(url_for("view_listing", id=listing.id))



@app.route("/request_pdf/<int:request_id>")
def request_pdf(request_id):
    rent_request = RentRequest.query.get_or_404(request_id)
    listing = rent_request.listing

    # Only renter or owner can access
    user_id = session.get("user_id")
    if not user_id or (user_id != rent_request.renter_id and user_id != listing.user_id):
        return "Unauthorized", 403

    if rent_request.status != "Approved":
        flash("PDF is only available for approved requests.", "error")
        return redirect(url_for("view_listing", id=listing.id))

    pdf_filename = f"rental_request_{rent_request.id}.pdf"
    pdf_path = os.path.join("instance", pdf_filename)

    # --- PDF Generation ---
    doc = SimpleDocTemplate(pdf_path, pagesize=letter)
    styles = getSampleStyleSheet()
    elements = []

    # Title
    elements.append(Paragraph("<b>Rental Confirmation</b>", styles["Title"]))
    elements.append(Spacer(1, 20))

    # Logo (optional)
    logo_path = os.path.join("static", "images", "logo.png")
    if os.path.exists(logo_path):
        elements.append(Image(logo_path, width=120, height=60))
        elements.append(Spacer(1, 20))

    # Rental details
    data = [
        ["Listing", listing.title],
        ["Renter", rent_request.renter.username],
        ["Owner", listing.user.username],
        ["Days", str(rent_request.days)],
        ["Notes", rent_request.description or "N/A"],
        ["Price per day", f"RM {listing.price:.2f}"],
        ["Total", f"RM {listing.price * rent_request.days:.2f}"],
    ]

    table = Table(data, colWidths=[150, 350])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4CAF50")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
        ("GRID", (0, 0), (-1, -1), 1, colors.black),
    ]))

    elements.append(table)
    elements.append(Spacer(1, 30))

    # Footer
    elements.append(Paragraph(
        "Thank you for using Rented! Please keep this document as proof of your rental agreement.",
        styles["Normal"]
    ))

    doc.build(elements)
    return send_file(pdf_path, as_attachment=True)

@app.route("/decline_request/<int:request_id>", methods=["POST"])
def decline_request(request_id):
    rent_request = RentRequest.query.get_or_404(request_id)
    listing = rent_request.listing

    if "user_id" not in session or session["user_id"] != listing.user_id:
        return "Unauthorized", 403

    rent_request.status = "Declined"
    db.session.commit()
    flash("Request declined. Approve/Decline buttons are now hidden.", "info")
    return redirect(url_for("view_listing", id=listing.id))



# --- Admin Routes ---
@app.route("/admin")
def admin_dashboard():
    if "user_id" not in session:
        return redirect(url_for("login"))
    user = User.query.get(session["user_id"])
    if not user.is_admin:
        return "Access denied", 403
    users = User.query.all()
    return render_template("admin_dashboard.html", users=users, title="Admin Dashboard")

@app.route("/create_user", methods=["GET", "POST"])
def create_user():
    if "user_id" not in session:
        return redirect(url_for("login"))
    admin_user = User.query.get(session["user_id"])
    if not admin_user.is_admin:
        return "Unauthorized", 403
    if request.method == "POST":
        username = request.form.get("username")
        email = request.form.get("email")
        password = request.form.get("password")
        is_admin = bool(request.form.get("is_admin"))
        if User.query.filter_by(username=username).first():
            flash("Username already exists!", "error")
        elif email and User.query.filter_by(email=email).first():
            flash("Email already exists!", "error")
        else:
            hashed_password = generate_password_hash(password)
            new_user = User(username=username, email=email, password=hashed_password, is_admin=is_admin)
            db.session.add(new_user)
            db.session.commit()
            flash("User created successfully!", "success")
            return redirect(url_for("admin_dashboard"))
    return render_template("create_user.html", title="Create User")

@app.route("/edit/<int:user_id>", methods=["GET", "POST"])
def edit_user(user_id):
    if "user_id" not in session:
        return redirect(url_for("login"))
    admin_user = User.query.get(session["user_id"])
    if not admin_user.is_admin:
        return "Unauthorized", 403
    user = User.query.get_or_404(user_id)
    if request.method == "POST":
        user.username = request.form.get("username", user.username)
        password = request.form.get("password")
        if password:
            user.password = generate_password_hash(password)
        db.session.commit()
        flash("User updated successfully!", "success")
        return redirect(url_for("admin_dashboard"))
    return render_template("edit_user.html", user=user, title="Edit User")

@app.route("/delete/<int:user_id>", methods=["GET", "POST"])
def delete_user(user_id):
    if "user_id" not in session:
        return redirect(url_for("login"))
    admin_user = User.query.get(session["user_id"])
    if not admin_user.is_admin:
        return "Unauthorized", 403
    user = User.query.get_or_404(user_id)
    if request.method in ["POST", "GET"]:
        db.session.delete(user)
        db.session.commit()
        flash("User deleted successfully!", "success")
        return redirect(url_for("admin_dashboard"))
    return redirect(url_for("admin_dashboard"))

# --- Contact & Email ---
@app.route("/contact")
def contact():
    return render_template("contact.html", title="Contact Us")

@app.route("/send", methods=["POST"])
@app.route("/send_email", methods=["POST"])
def send_email():
    name = request.form.get("name")
    email = request.form.get("email")
    subject = request.form.get("subject")
    message_body = request.form.get("message")
    if not name or not email or not subject or not message_body:
        return render_template("contact.html", message="Please fill in all fields.", success=False)
    try:
        admin_msg = MIMEText(f"From: {name} <{email}>\n\n{message_body}")
        admin_msg["Subject"] = f"Contact Form: {subject}"
        admin_msg["From"] = ADMIN_EMAIL
        admin_msg["To"] = ADMIN_EMAIL
        auto_reply = MIMEText(
            f"Hello {name},\n\n"
            "Thank you for contacting us! We have received your message and will get back to you shortly.\n\n"
            "Best regards,\nRented Team"
        )
        auto_reply["Subject"] = "Thank you for contacting Rented!"
        auto_reply["From"] = ADMIN_EMAIL
        auto_reply["To"] = email
        server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10)
        server.starttls()
        server.login(ADMIN_EMAIL, ADMIN_PASSWORD)
        server.sendmail(ADMIN_EMAIL, ADMIN_EMAIL, admin_msg.as_string())
        server.sendmail(ADMIN_EMAIL, email, auto_reply.as_string())
        server.quit()
        return render_template("contact.html", message="Your message has been sent successfully!", success=True)
    except Exception as e:
        print("Email error:", e)
        return render_template("contact.html", message="Failed to send email. Please try again later.", success=False)

# --- Misc ---
@app.route("/about")
def about():
    return render_template("about.html")

@app.context_processor
def inject_user():
    if "user_id" in session:
        user = User.query.get(session["user_id"])
        return dict(user=user)
    return dict(user=None)

# ------------------------
# RUN
# ------------------------
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        # print a useful DB path message
        db_path = app.config.get('SQLALCHEMY_DATABASE_URI')
        # create default admin if missing
        if not User.query.filter_by(is_admin=True).first():
            admin = User(
                username="Admin",
                email="admin@example.com",
                password=generate_password_hash("123"),
                is_admin=True
            )
            db.session.add(admin)
            db.session.commit()
            print("Default admin created: username=Admin, password=123")
        print(f"Database created/loaded at: {db_path}")
    app.run(debug=True)
