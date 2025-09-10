from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///rented.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
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
            return redirect(url_for("admin_dashboard"))
        else:
            error = "Incorrect username or password!"

    return render_template("login.html", title="Login", error=error)


@app.route("/admin")
def admin_dashboard():
    users = User.query.all()  # fetch all users from the database
    return render_template("admin_dashboard.html", users=users, title="Admin Dashboard")


@app.route("/delete/<int:user_id>")
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()
    return redirect(url_for("admin_dashboard"))

@app.route("/edit/<int:user_id>", methods=["GET", "POST"])
def edit_user(user_id):
    user = User.query.get_or_404(user_id)
    if request.method == "POST":
        new_username = request.form.get("username")
        new_password = request.form.get("password")

        if new_username:
            user.username = new_username
        if new_password:
            user.password = new_password

        db.session.commit()
        return redirect(url_for("admin_dashboard"))

    return render_template("edit_user.html", user=user)


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "initdb":
        with app.app_context():
            db.create_all()
            print("Database initialized ✅")
    else:
        app.run(debug=True)
