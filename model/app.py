import os
import re
import sqlite3
from functools import wraps

import joblib
from flask import (Flask, flash, g, jsonify, redirect, render_template,
                   request, session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = BASE_DIR if os.path.basename(BASE_DIR) == "model" else os.path.join(BASE_DIR, "model")
PROJECT_DIR = os.path.dirname(BASE_DIR) if os.path.basename(BASE_DIR) == "model" else BASE_DIR
DB_PATH = os.path.join(BASE_DIR, "users.db")

app = Flask(
    __name__,
    template_folder=os.path.join(PROJECT_DIR, "templates"),
    static_folder=os.path.join(PROJECT_DIR, "static"),
)
# Used to sign the login session. Change this to any long random text.
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-me")


# ---------------------------------------------------------------
# 1. Load the model trained in Google Colab
# ---------------------------------------------------------------
try:
    model = joblib.load(os.path.join(MODEL_DIR, "genre_model.joblib"))
    vectorizer = joblib.load(os.path.join(MODEL_DIR, "tfidf_vectorizer.joblib"))
    label_binarizer = joblib.load(os.path.join(MODEL_DIR, "genre_labels.joblib"))
except FileNotFoundError as e:
    raise SystemExit(
        f"Model file missing: {e}\n"
        "Put the 3 .joblib files inside the 'model' folder."
    )

GENRES = list(label_binarizer.classes_)


# ---------------------------------------------------------------
# 2. Database (SQLite, no setup needed)
# ---------------------------------------------------------------
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(error):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS users (
                   id INTEGER PRIMARY KEY AUTOINCREMENT,
                   username TEXT UNIQUE NOT NULL COLLATE NOCASE,
                   password_hash TEXT NOT NULL
               )"""
        )


init_db()


# ---------------------------------------------------------------
# 3. Prediction helpers
# ---------------------------------------------------------------
def clean_text(text):
    """Same cleaning that was used for training in Colab."""
    text = text.lower()
    text = re.sub(r"[^a-z\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def predict_genres(plot, top_n=3):
    """Return the top genres for a plot summary, using the real model."""
    cleaned = clean_text(plot)
    features = vectorizer.transform([cleaned])
    probs = model.predict_proba(features)[0]      # one score per genre
    best = probs.argsort()[::-1][:top_n]          # indexes of highest scores
    return [
        {"genre": str(GENRES[i]), "score": round(float(probs[i]) * 100, 1)}
        for i in best
    ]


# ---------------------------------------------------------------
# 4. Login protection
# ---------------------------------------------------------------
def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in first.", "error")
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


# ---------------------------------------------------------------
# 5. Routes
# ---------------------------------------------------------------
@app.route("/")
def home():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")

        # Basic input validation
        if not re.fullmatch(r"[A-Za-z0-9_]{3,20}", username):
            flash("Username must be 3-20 characters: letters, numbers, underscore.", "error")
        elif len(password) < 6:
            flash("Password must be at least 6 characters.", "error")
        elif password != confirm:
            flash("Passwords do not match.", "error")
        else:
            db = get_db()
            exists = db.execute(
                "SELECT id FROM users WHERE username = ?", (username,)
            ).fetchone()
            if exists:
                flash("That username is already taken.", "error")
            else:
                db.execute(
                    "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                    (username, generate_password_hash(password)),
                )
                db.commit()
                flash("Account created. Please log in.", "success")
                return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if not username or not password:
            flash("Please enter username and password.", "error")
        else:
            user = get_db().execute(
                "SELECT * FROM users WHERE username = ?", (username,)
            ).fetchone()
            if user and check_password_hash(user["password_hash"], password):
                session.clear()
                session["user_id"] = user["id"]
                session["username"] = user["username"]
                return redirect(url_for("dashboard"))
            flash("Invalid username or password.", "error")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html", username=session["username"])


@app.route("/predict", methods=["POST"])
def predict():
    # The page sends the plot as JSON; we reply with JSON.
    if "user_id" not in session:
        return jsonify(error="Please log in first."), 401

    data = request.get_json(silent=True) or {}
    plot = (data.get("plot") or "").strip()

    # Input validation
    if not plot:
        return jsonify(error="Please enter a plot summary."), 400
    if len(plot) > 3000:
        return jsonify(error="Plot is too long (maximum 3000 characters)."), 400
    if len(clean_text(plot).split()) < 5:
        return jsonify(error="Please enter at least 5 words."), 400

    return jsonify(predictions=predict_genres(plot))


if __name__ == "__main__":
    app.run(debug=True)