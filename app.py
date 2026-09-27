"""Postmark: a personal literary postbox backed by SQLite."""
import io
import os
import re
import secrets
import sqlite3
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path

import click
from flask import (
    Flask, abort, flash, g, redirect, render_template, request,
    send_file, session, url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        DATABASE=str(Path(app.instance_path) / "postmark.db"),
        SECRET_KEY=os.environ.get("POSTMARK_SECRET_KEY"),
        MAX_CONTENT_LENGTH=2 * 1024 * 1024,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
    )
    if test_config:
        app.config.update(test_config)

    if not app.config.get("SECRET_KEY"):
        if os.environ.get("POSTMARK_ENV") == "production":
            raise RuntimeError("Set POSTMARK_SECRET_KEY in the deployment environment.")
        # Local development keeps a random key across restarts; deployment uses the environment.
        Path(app.instance_path).mkdir(parents=True, exist_ok=True)
        key_file = Path(app.instance_path) / "secret.key"
        try:
            fd = os.open(str(key_file), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            pass
        else:
            with os.fdopen(fd, "w") as handle:
                handle.write(secrets.token_hex(32))
        app.config["SECRET_KEY"] = key_file.read_text().strip()
        if not app.config["SECRET_KEY"]:
            raise RuntimeError("The session key file is empty.")

    def get_db():
        if "db" not in g:
            g.db = sqlite3.connect(app.config["DATABASE"])
            g.db.row_factory = sqlite3.Row
        return g.db

    @app.teardown_appcontext
    def close_db(error=None):
        db = g.pop("db", None)
        if db is not None:
            db.close()

    @app.cli.command("init-db")
    def init_db():
        """Create the table without removing existing accounts."""
        Path(app.config["DATABASE"]).parent.mkdir(parents=True, exist_ok=True)
        get_db().executescript(Path(app.root_path, "schema.sql").read_text())
        click.echo("Database ready.")

    @app.context_processor
    def template_helpers():
        if "csrf_token" not in session:
            session["csrf_token"] = secrets.token_hex(32)
        return {"csrf_token": session["csrf_token"]}

    @app.before_request
    def check_form_token():
        if request.method == "POST":
            expected = session.get("csrf_token", "")
            supplied = request.form.get("csrf_token", "")
            if not expected or not secrets.compare_digest(expected.encode(), supplied.encode()):
                abort(400, description="This form expired. Reload the page and try again.")

    @app.after_request
    def response_headers(response):
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        return response

    def login_required(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not session.get("user_id"):
                return redirect(url_for("login"))
            return view(*args, **kwargs)
        return wrapped

    @app.route("/")
    def index():
        return redirect(url_for("profile" if session.get("user_id") else "register"))

    @app.route("/register", methods=["GET", "POST"])
    def register():
        values = {}
        error = None
        if request.method == "POST":
            fields = ("username", "first_name", "last_name", "email", "address")
            values = {field: request.form.get(field, "").strip() for field in fields}
            password = request.form.get("password", "")
            upload = request.files.get("document")
            content = b""
            filename = ""
            word_count = 0

            if not all(values.values()):
                error = "Please fill in all fields."
            elif not re.fullmatch(r"[A-Za-z0-9_.-]{3,30}", values["username"]):
                error = "Use 3–30 letters, numbers, dots, dashes, or underscores for your username."
            elif not 8 <= len(password) <= 128:
                error = "Use a password between 8 and 128 characters."
            elif len(values["first_name"]) > 80 or len(values["last_name"]) > 80:
                error = "Keep each name under 81 characters."
            elif len(values["address"]) > 300:
                error = "Keep your address under 301 characters."
            elif len(values["email"]) > 254 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", values["email"]):
                error = "Enter an email address such as name@example.com."
            elif not upload or not upload.filename:
                error = "Please choose a text file."
            else:
                # Keep the original basename, including spaces. Never use it as a disk path.
                filename = upload.filename.replace("\\", "/").rsplit("/", 1)[-1]
                if not filename.lower().endswith(".txt"):
                    error = "Only .txt files can be uploaded."
                elif (not filename[:-4].strip(". ") or len(filename) > 255
                      or any(ord(char) < 32 or ord(char) == 127 for char in filename)):
                    error = "Please use a valid filename."
                else:
                    content = upload.read(1024 * 1024 + 1)
                    if len(content) > 1024 * 1024:
                        error = "Please choose a text file up to 1 MB."
                    else:
                        try:
                            text = content.decode("utf-8-sig")
                        except UnicodeDecodeError:
                            error = "Save the file as UTF-8 text, then upload it again."
                        else:
                            if any(ord(char) < 32 and char not in "\t\n\r" for char in text):
                                error = "Please choose a plain text file."
                            elif not text.strip():
                                error = "The text file is empty."
                            else:
                                word_count = len(text.split())

            if error is None:
                db = get_db()
                try:
                    cursor = db.execute(
                        """INSERT INTO users
                        (username, password_hash, first_name, last_name, email,
                         address, file_name, file_data, word_count)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (values["username"], generate_password_hash(password, method="pbkdf2:sha256:600000"),
                         values["first_name"], values["last_name"], values["email"],
                         values["address"], filename, content, word_count),
                    )
                    db.commit()
                except sqlite3.IntegrityError:
                    db.rollback()
                    error = "That username is already in use."
                else:
                    session.clear()
                    session["user_id"] = cursor.lastrowid
                    flash("Record saved.")
                    return redirect(url_for("profile"))
            flash(error)
        return render_template("register.html", values=values)

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")
            user = get_db().execute(
                "SELECT id, password_hash FROM users WHERE username = ?", (username,)
            ).fetchone()
            if user and check_password_hash(user["password_hash"], password):
                session.clear()
                session["user_id"] = user["id"]
                return redirect(url_for("profile"))
            flash("Username or password is incorrect.")
        return render_template("login.html")

    @app.route("/profile")
    @login_required
    def profile():
        user = get_db().execute(
            """SELECT id, username, first_name, last_name, email, address,
                      file_name, file_data, word_count, created_at,
                      length(file_data) AS file_size
               FROM users WHERE id = ?""", (session["user_id"],)
        ).fetchone()
        if user is None:
            session.clear()
            return redirect(url_for("login"))
        saved_at = datetime.fromisoformat(user["created_at"]).replace(tzinfo=timezone.utc)
        return render_template(
            "profile.html", user=user, record_number=f"PM-{user['id']:04d}",
            saved_at=saved_at, preview=user["file_data"].decode("utf-8-sig"),
        )

    @app.route("/download")
    @login_required
    def download_file():
        user = get_db().execute(
            "SELECT file_name, file_data FROM users WHERE id = ?", (session["user_id"],)
        ).fetchone()
        if user is None:
            abort(404)
        return send_file(io.BytesIO(user["file_data"]), mimetype="text/plain",
                         as_attachment=True, download_name=user["file_name"])

    @app.route("/logout", methods=["POST"])
    def logout():
        session.clear()
        return redirect(url_for("login"))

    @app.errorhandler(400)
    def bad_request(error):
        return render_template("error.html", message=error.description), 400

    @app.errorhandler(413)
    def too_large(error):
        return render_template("error.html", message="That upload is too large. Choose a .txt file up to 1 MB."), 413

    return app
