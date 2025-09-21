from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
import os

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///rented.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL")  # e.g. yourproject@outlook.com
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")  # Outlook password or App Password
SMTP_HOST = "smtp.office365.com"
SMTP_PORT = 587
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)  # Admin flag
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<User {self.username}>"

@app.route("/")
def home():
    return render_template("index.html", title="Rented")

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        # Check if username exists
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            return "Username already exists!"

        new_user = User(username=username, password=password)
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for("login"))

    return render_template("signup.html", title="Sign Up")

@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        user = User.query.filter_by(username=username, password=password).first()
        if user:
            if user.is_admin:
                return redirect(url_for("admin_dashboard"))  # Admin goes to dashboard
            else:
                return redirect(url_for("home"))  # Regular user goes to home
        else:
            error = "Incorrect username or password!"

    return render_template("login.html", title="Login", error=error)

@app.route("/admin")
def admin_dashboard():
    users = User.query.all()
    return render_template("admin_dashboard.html", users=users, title="Admin Dashboard")

@app.route("/edit/<int:user_id>", methods=["GET", "POST"])
def edit_user(user_id):
    user = User.query.get_or_404(user_id)

    if request.method == "POST":
        user.username = request.form.get("username")
        user.password = request.form.get("password")
        db.session.commit()
        return redirect(url_for("admin_dashboard"))

    return render_template("edit_user.html", user=user, title="Edit User")

@app.route("/delete/<int:user_id>")
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()
    return redirect(url_for("admin_dashboard"))

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

        reply = MIMEText(f"Hello {name},\n\nThanks for contacting us! We received your message and will reply soon.\n\n- Rented Team")
        reply["Subject"] = "We received your message"
        reply["From"] = ADMIN_EMAIL
        reply["To"] = user_email

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(ADMIN_EMAIL, ADMIN_PASSWORD)
            server.send_message(reply)

        return "✅ Message sent and auto-reply delivered."
    except Exception as e:
        return f"❌ Error sending email: {e}"
if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "initdb":
        with app.app_context():
            db.create_all()
            print("Database initialized ✅")
    else:
        app.run(debug=True)
