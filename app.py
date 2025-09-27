import os
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import smtplib
from email.mime.text import MIMEText
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

app = Flask(__name__)

# ------------------------
# CONFIGURATION
# ------------------------
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

# Email config
ADMIN_EMAIL = "miniit799@gmail.com"
ADMIN_PASSWORD = "cldn gswl pyop reqw"  # Gmail app password

# Gmail SMTP settings
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587

# Database
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

class RentRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    days = db.Column(db.Integer, nullable=False)
    description = db.Column(db.Text)
    status = db.Column(db.String(50), default="Pending")  # Pending, Approved, Rejected
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
        elif User.query.filter_by(email=email).first():
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
        listing.price = request.form["price"]

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

@app.route("/delete-listing/<int:id>", methods=["POST"])
def delete_listing(id):
    listing = Listing.query.get_or_404(id)
    if "user_id" not in session:
        return redirect(url_for("login"))

    user = User.query.get(session["user_id"])
    if listing.user_id != session["user_id"] and not user.is_admin:
        return redirect(url_for("home"))

    db.session.delete(listing)
    db.session.commit()
    flash("Listing deleted successfully!", "success")
    return redirect(url_for("home"))

# --- Rent Request ---
@app.route("/listing/<int:id>", methods=["GET", "POST"])
def view_listing(id):
    listing = Listing.query.get_or_404(id)

    if request.method == "POST":
        if "user_id" not in session:
            flash("You must be logged in to send a request.", "error")
            return redirect(url_for("login"))

        days = request.form.get("days")
        description = request.form.get("description")

        new_request = RentRequest(
            days=days,
            description=description,
            listing_id=listing.id,
            renter_id=session["user_id"]
        )
        db.session.add(new_request)
        db.session.commit()
        flash("Your rental request has been sent!", "success")
        return redirect(url_for("view_listing", id=listing.id))

    requests = RentRequest.query.filter_by(listing_id=listing.id).all()
    return render_template("view_listing.html", listing=listing, requests=requests)

@app.route("/approve_request/<int:request_id>")
def approve_request(request_id):
    rent_request = RentRequest.query.get_or_404(request_id)

    if "user_id" not in session:
        return redirect(url_for("login"))

    listing = rent_request.listing
    if session["user_id"] != listing.user_id:
        return "Unauthorized", 403

    rent_request.status = "Approved"
    db.session.commit()

    # Generate PDF confirmation
    pdf_filename = f"rental_request_{rent_request.id}.pdf"
    pdf_path = os.path.join("instance", pdf_filename)

    c = canvas.Canvas(pdf_path, pagesize=letter)
    c.drawString(100, 750, f"Rental Confirmation for {listing.title}")
    c.drawString(100, 720, f"Renter: {rent_request.renter.username}")
    c.drawString(100, 700, f"Owner: {listing.user.username}")
    c.drawString(100, 680, f"Days: {rent_request.days}")
    c.drawString(100, 660, f"Notes: {rent_request.description or 'N/A'}")
    c.drawString(100, 640, f"Price per day: RM {listing.price}")
    c.drawString(100, 620, f"Total: RM {listing.price * int(rent_request.days)}")
    c.save()

    flash("Request approved. PDF generated!", "success")
    return send_file(pdf_path, as_attachment=True)

@app.route("/decline_request/<int:request_id>")
def decline_request(request_id):
    rent_request = RentRequest.query.get_or_404(request_id)

    if "user_id" not in session:
        return redirect(url_for("login"))

    listing = rent_request.listing
    if session["user_id"] != listing.user_id:
        return "Unauthorized", 403

    rent_request.status = "Rejected"
    db.session.commit()
    flash("Request declined.", "info")
    return redirect(url_for("view_listing", id=listing.id))

# --- Email Route ---
@app.route("/send_email", methods=["POST"])
def send_email():
    name = request.form.get("name")
    email = request.form.get("email")
    subject = request.form.get("subject")
    message_body = request.form.get("message")

    if not name or not email or not subject or not message_body:
        return render_template("contact.html", message="Please fill in all fields.", success=False)

    try:
        # --- Message to Admin ---
        admin_msg = MIMEText(f"From: {name} <{email}>\n\n{message_body}")
        admin_msg["Subject"] = f"Contact Form: {subject}"
        admin_msg["From"] = ADMIN_EMAIL
        admin_msg["To"] = ADMIN_EMAIL

        # --- Automated Reply to Sender ---
        auto_reply = MIMEText(
            f"Hello {name},\n\n"
            "Thank you for contacting us! We have received your message and will get back to you shortly.\n\n"
            "Best regards,\nRented Team"
        )
        auto_reply["Subject"] = "Thank you for contacting Rented!"
        auto_reply["From"] = ADMIN_EMAIL
        auto_reply["To"] = email

        # --- Send both emails ---
        server = smtplib.SMTP(SMTP_HOST, SMTP_PORT)
        server.starttls()
        server.login(ADMIN_EMAIL, ADMIN_PASSWORD)
        server.sendmail(ADMIN_EMAIL, ADMIN_EMAIL, admin_msg.as_string())  # Send to admin
        server.sendmail(ADMIN_EMAIL, email, auto_reply.as_string())       # Send automated reply
        server.quit()

        return render_template("contact.html", message="Your message has been sent successfully!", success=True)

    except Exception as e:
        print("Email error:", e)
        return render_template("contact.html", message="Failed to send email. Please try again later.", success=False)



# --- Admin + Contact + Misc ---
@app.route("/admin")
def admin_dashboard():
    if "user_id" not in session:
        return redirect(url_for("login"))

    user = User.query.get(session["user_id"])
    if not user.is_admin:
        return "Access denied", 403

    users = User.query.all()
    return render_template("admin_dashboard.html", users=users, title="Admin Dashboard")

@app.route("/contact")
def contact():
    return render_template("contact.html", title="Contact Us")

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
        db.all()

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

    app.run(debug=True)
