# Postmark

**A personal literary postbox.**

Postmark is a small Flask application that lets a user create an account, save
basic contact information, upload a text file, view its word count, and retrieve
the same information after logging back in. It uses SQLite and is designed to run
on AWS EC2 with Apache and mod_wsgi.

## Run locally

From the `Project2_AWS` folder:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m flask --app app:create_app init-db
python -m flask --app app:create_app run --port 5050
```

Open http://127.0.0.1:5050. Press Control+C to stop. On later runs, activate the
virtual environment and run the last command again. `init-db` creates missing
tables without deleting accounts; the local database is `instance/postmark.db`.

## Assignment flow

Register + upload → save → profile → download → logout → login → retrieve.

The form accepts ordinary UTF-8 `.txt` files, including the instructor's
`Limerick (1).txt`, up to 1 MB. Download that file from Canvas for your final test.
Empty files, invalid text, and other extensions are rejected. All required
contact fields appear on the saved page. A native **Read text** disclosure shows
the stored text with its line breaks; it does not require JavaScript.

## Storage

One `users` table contains:

| Column | Purpose |
|---|---|
| `id` | SQLite primary key; displayed as `PM-0001`, etc. |
| `username` | Unique, case-insensitive account name |
| `password_hash` | Werkzeug password hash |
| `first_name`, `last_name`, `email`, `address` | Saved contact information |
| `file_name` | Original uploaded basename, including spaces and Unicode |
| `file_data` | Original bytes stored as a BLOB |
| `word_count` | `len(text.split())` on UTF-8 text, ignoring an optional BOM |
| `created_at` | SQLite creation timestamp in UTC |

Path components and invalid filename control characters are not accepted as part
of the saved basename. The filename is never used as a disk path. Downloads retain
the original bytes, including a UTF-8 BOM and line endings. The profile calculates
file size from the stored BLOB and labels the saved time **UTC**. It derives the
Postmark number from `id`; there is no separate tracking number or mail service.

`init-db` leaves existing accounts and their saved timestamps intact.

Passwords are hashed, SQL uses parameters, and profile/download access requires a
session for the account that owns the record. Forms include CSRF tokens. The
source contains no production credentials.

## Files

- `app.py`, `schema.sql`: Flask routes and SQLite initialization.
- `templates/`, `static/style.css`: Postmark pages and responsive styles.
- `postmark.wsgi`: Apache entry point using `create_app()`.
- `deploy/postmark.conf`: port 80 site at `/var/www/postmark`.
- `tests/test_app.py`: integration tests with temporary databases.
- `GUIDE.md`: AWS setup, troubleshooting, screenshot checkpoints, and submission.

## Tests

```bash
python -m unittest discover -s tests -v
```

Tests cover registration, redirects, saved fields and metadata, original file
bytes, re-login after an app restart, logout, duplicate usernames, invalid uploads,
account separation, escaped previews, deployment key settings, and WSGI loading.
Tests use invented data and do not modify the local user database.

## Deployment and secret key

Follow **GUIDE.md** for Ubuntu 24.04, Apache, mod_wsgi, system Python 3/Flask, and
SQLite. The guide configures `/var/www/postmark`, `postmark.conf`, and
`postmark-error.log`. Only port 80 needs public access; SSH is restricted to your IP.

Deployment must supply `POSTMARK_SECRET_KEY` as an environment variable. The guide
generates it on EC2 in a root-only `/etc/postmark.env` file and loads that file from
Apache's `envvars` before Apache starts. `postmark.wsgi` selects production mode
and refuses to start without the key. Apache `SetEnv` alone is not used for this:
its request variables are distinct from Python's process environment.
See the [mod_wsgi configuration guidance](https://www.modwsgi.org/en/latest/user-guides/configuration-guidelines.html).

For local development only, the app generates a random persistent key in
`instance/secret.key` when no environment key is supplied. Keep `instance/`, `.env`
files, private keys, caches, and virtual environments out of submissions and Git.

Use invented contact details and a unique demo password for the HTTP course demo.
The AWS deployment and the actual course-file test still need to be performed;
no AWS success or screenshot evidence is claimed by this repository.
