import os
import sqlite3
import secrets
import string
import re
from datetime import datetime
from urllib.parse import urlsplit
from flask import Flask, render_template, request, redirect, abort

# --------------------
# Config
# --------------------
BASE_URL = "http://127.0.0.1:5000/"
CODE_LENGTH = 10
CODE_ALPHABET = string.ascii_letters + string.digits
ALLOWED_SCHEMES = {"http", "https"}
SAFE_NETLOC_RE = re.compile(r"^[A-Za-z0-9.-]+(:\d+)?$")

# --------------------
# Flask app
# --------------------
app = Flask(__name__)

# --------------------
# Database setup
# --------------------
def init_db():
    conn = sqlite3.connect("urls.db")
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS urls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            long_url TEXT NOT NULL,
            created_at TEXT NOT NULL,
            clicks INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()

init_db()

# --------------------
# Utilities
# --------------------
def generate_code():
    return ''.join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))

def normalize_and_validate_url(url: str) -> str:
    parts = urlsplit(url.strip())
    if parts.scheme.lower() not in ALLOWED_SCHEMES:
        abort(400, description="Only http(s) URLs are allowed")
    if not parts.netloc or not SAFE_NETLOC_RE.match(parts.netloc):
        abort(400, description="Invalid host")
    return url

def code_exists(code: str) -> bool:
    conn = sqlite3.connect("urls.db")
    c = conn.cursor()
    c.execute("SELECT 1 FROM urls WHERE code=?", (code,))
    exists = c.fetchone() is not None
    conn.close()
    return exists

# --------------------
# Routes
# --------------------
@app.route("/", methods=["GET"])
def home():
    return render_template("index.html", short_url=None)

@app.route("/shorten", methods=["POST"])
def shorten():
    long_url = request.form.get("long_url")
    custom_code = request.form.get("custom_code") or None

    if not long_url:
        return render_template("index.html", short_url=None, error="URL is required")

    try:
        normalized_url = normalize_and_validate_url(long_url)
    except Exception as e:
        return render_template("index.html", short_url=None, error=str(e))

    # Custom code handling
    if custom_code:
        if not re.match(r"^[A-Za-z0-9]{4,32}$", custom_code):
            return render_template("index.html", short_url=None, error="Invalid custom code format")
        if code_exists(custom_code):
            return render_template("index.html", short_url=None, error="Custom code already exists")
        code = custom_code
    else:
        while True:
            code = generate_code()
            if not code_exists(code):
                break

    # Insert into database
    conn = sqlite3.connect("urls.db")
    c = conn.cursor()
    c.execute(
        "INSERT INTO urls (code, long_url, created_at) VALUES (?, ?, ?)",
        (code, normalized_url, datetime.utcnow().isoformat())
    )
    conn.commit()
    conn.close()

    return render_template("index.html", short_url=BASE_URL + code, error=None)

@app.route("/<code>")
def redirect_to_url(code):
    conn = sqlite3.connect("urls.db")
    c = conn.cursor()
    c.execute("SELECT long_url, clicks FROM urls WHERE code=?", (code,))
    row = c.fetchone()
    if not row:
        conn.close()
        abort(404, description="URL not found")

    long_url, clicks = row
    c.execute("UPDATE urls SET clicks=? WHERE code=?", (clicks + 1, code))
    conn.commit()
    conn.close()

    return redirect(long_url, code=301)

# --------------------
# Run
# --------------------
if __name__ == "__main__":
    app.run(debug=True)
