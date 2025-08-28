from flask import Flask, render_template, request
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime


app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///C:/Users/saeed/OneDrive/Desktop/Rented/rented.db"
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
    title = "Rented"
    return render_template("index.html", title=title)

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        return f"Hello, {username}! You tried to log in."
    return render_template("login.html", title="Login")

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        new_user = User(username=username, password=password)
        db.session.add(new_user)
        db.session.commit()
        return f"User {username} created!"
    return render_template("signup.html", title="Sign Up")

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
