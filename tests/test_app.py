import io
import os
import runpy
import secrets
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from werkzeug.test import EnvironBuilder

from app import create_app


class PostmarkTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.config = {"TESTING": True, "SECRET_KEY": "only-for-tests",
                       "DATABASE": str(Path(self.temp.name) / "test.db")}
        self.app = create_app(self.config)
        result = self.app.test_cli_runner().invoke(args=["init-db"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.client = self.app.test_client()

    def tearDown(self):
        self.temp.cleanup()

    def token(self, client=None):
        client = client or self.client
        client.get("/login")
        with client.session_transaction() as session:
            return session["csrf_token"]

    def register(self, username="nihal_test", content=b"One two\nthree  four\tfive.", filename="Limerick (1).txt", follow_redirects=True, **changes):
        data = dict(username=username, password="class-demo-123",
                    first_name="Nihal", last_name="Patel", email="demo@example.com",
                    address="123 Example Street", csrf_token=self.token(),
                    document=(io.BytesIO(content), filename))
        data.update(changes)
        builder = EnvironBuilder(path="/register", method="POST", data=data)
        environ = builder.get_environ()
        try:
            return self.client.open(environ, follow_redirects=follow_redirects)
        finally:
            environ["wsgi.input"].close()
            builder.close()

    def logout(self):
        return self.client.post("/logout", data={"csrf_token": self.token()})

    def test_register_display_download_and_password_hash(self):
        content = b"One two\nthree  four\tfive."
        response = self.register(content=content)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"My Postbox", response.data)
        for value in (b"Nihal", b"Patel", b"demo@example.com", b"123 Example Street",
                      b'Limerick (1).txt', b'class="word-count">5</dd>'):
            self.assertIn(value, response.data)
        download = self.client.get("/download")
        self.assertEqual(download.data, content)
        self.assertIn("attachment", download.headers["Content-Disposition"])
        self.assertIn('filename="Limerick (1).txt"', download.headers["Content-Disposition"])
        with sqlite3.connect(self.config["DATABASE"]) as db:
            hashed, stored = db.execute("SELECT password_hash, file_data FROM users").fetchone()
        self.assertNotEqual(hashed, "class-demo-123")
        self.assertTrue(hashed.startswith("pbkdf2:"))
        self.assertEqual(stored, content)

    def test_login_persists_after_app_restarts(self):
        self.register()
        self.logout()
        new_client = create_app(self.config).test_client()
        response = new_client.post("/login", data={"username": "NIHAL_TEST", "password": "class-demo-123",
                                                  "csrf_token": self.token(new_client)}, follow_redirects=True)
        for value in (b"My Postbox", b"Nihal", b"Patel", b"demo@example.com", b"123 Example Street",
                      b"Limerick (1).txt", b"PM-0001", b'class="word-count">5</dd>'):
            self.assertIn(value, response.data)
        self.assertEqual(new_client.get("/download").data, b"One two\nthree  four\tfive.")

    def test_wrong_password_and_anonymous_routes(self):
        self.register()
        self.logout()
        response = self.client.post("/login", data={"username": "nihal_test", "password": "incorrect",
                                                   "csrf_token": self.token()})
        self.assertIn(b"Username or password is incorrect.", response.data)
        for path in ("/profile", "/download"):
            self.assertEqual(self.client.get(path).status_code, 302)

    def test_duplicate_username_does_not_overwrite(self):
        self.register()
        self.logout()
        response = self.register(username="NIHAL_TEST", content=b"different file")
        self.assertIn(b"That username is already in use.", response.data)
        with sqlite3.connect(self.config["DATABASE"]) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM users").fetchone()[0], 1)
            self.assertEqual(db.execute("SELECT file_data FROM users").fetchone()[0], b"One two\nthree  four\tfive.")

    def test_accounts_only_download_their_own_file(self):
        self.register(content=b"First account file")
        self.logout()
        self.register(username="another_user", content=b"Second account file")
        self.assertEqual(self.client.get("/download?user_id=1").data, b"Second account file")

    def test_invalid_uploads_and_fields_are_rejected(self):
        cases = [({"filename": "bad.pdf"}, b"Only .txt files"),
                 ({"content": b"   "}, b"file is empty"),
                 ({"content": b"\xff\xfe"}, b"UTF-8"),
                 ({"content": b"\x00binary"}, b"plain text file"),
                 ({"content": b"\x01binary"}, b"plain text file"),
                 ({"content": b"a" * (1024 * 1024 + 1)}, b"1 MB"),
                 ({"email": "not-an-email"}, b"email address"),
                 ({"address": ""}, b"Please fill in all fields")]
        for changes, message in cases:
            with self.subTest(changes=list(changes)):
                response = self.register(**changes)
                self.assertIn(message, response.data)
        with sqlite3.connect(self.config["DATABASE"]) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM users").fetchone()[0], 0)

    def test_csrf_and_total_request_size(self):
        self.assertEqual(self.client.post("/logout").status_code, 400)
        response = self.register(content=b"a" * (3 * 1024 * 1024))
        self.assertEqual(response.status_code, 413)

    def test_profile_escapes_html_and_bom_word_count(self):
        response = self.register(first_name="<script>alert(1)</script>", content=b"\xef\xbb\xbfOne\n two")
        self.assertNotIn(b"<script>alert(1)</script>", response.data)
        self.assertIn(b"&lt;script&gt;", response.data)
        self.assertIn(b'class="word-count">2</dd>', response.data)

    def test_registration_page_and_required_fields(self):
        response = self.client.get("/", follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Create your postbox", response.data)
        self.assertIn(b"A personal literary postbox.", response.data)
        for field in ("username", "password", "first_name", "last_name", "email", "address", "document"):
            self.assertIn(('name="' + field + '"').encode(), response.data)
        self.assertIn(b'enctype="multipart/form-data"', response.data)

    def test_registration_redirects_after_saving(self):
        response = self.register(follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/profile")
        with sqlite3.connect(self.config["DATABASE"]) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM users").fetchone()[0], 1)

    def test_postmark_number_size_and_timestamp_come_from_record(self):
        content = "A café by the river.\r\n".encode("utf-8")
        response = self.register(content=content)
        with sqlite3.connect(self.config["DATABASE"]) as db:
            row = db.execute("SELECT id, file_name, length(file_data), created_at FROM users").fetchone()
        user_id, filename, size, created_at = row
        self.assertEqual(filename, "Limerick (1).txt")
        self.assertEqual(size, len(content))
        self.assertIn(f"PM-{user_id:04d}".encode(), response.data)
        self.assertIn(f"{len(content)} bytes".encode(), response.data)
        saved_at = datetime.fromisoformat(created_at).replace(tzinfo=timezone.utc)
        self.assertLess(abs((datetime.now(timezone.utc) - saved_at).total_seconds()), 30)
        self.assertIn(saved_at.isoformat().encode(), response.data)
        self.assertIn(saved_at.strftime("%b %d, %Y at %I:%M %p UTC").encode(), response.data)

    def test_saved_time_does_not_change_on_login(self):
        self.register()
        with sqlite3.connect(self.config["DATABASE"]) as db:
            db.execute("UPDATE users SET created_at = ?", ("2024-02-03 14:05:00",))
        self.logout()
        response = self.client.post("/login", data={"username": "nihal_test", "password": "class-demo-123",
                                                   "csrf_token": self.token()}, follow_redirects=True)
        self.assertIn(b"Feb 03, 2024 at 02:05 PM UTC", response.data)

    def test_logout_clears_session_and_access(self):
        self.register()
        response = self.logout()
        self.assertEqual(response.headers["Location"], "/login")
        with self.client.session_transaction() as session:
            self.assertNotIn("user_id", session)
        for path in ("/profile", "/download"):
            self.assertEqual(self.client.get(path).headers["Location"], "/login")

    def test_missing_file_selection(self):
        for changes in ({"document": None}, {"filename": ""}):
            with self.subTest(changes=changes):
                response = self.register(**changes)
                self.assertIn(b"Please choose a text file.", response.data)

    def test_zero_byte_upload(self):
        response = self.register(content=b"")
        self.assertIn(b"The text file is empty.", response.data)

    def test_preserves_utf8_bom_and_line_endings_in_download(self):
        content = b"\xef\xbb\xbf" + "Café notes\r\nNext line\n".encode("utf-8")
        self.register(content=content, filename="Café notes.TXT")
        download = self.client.get("/download")
        self.assertEqual(download.data, content)
        self.assertIn("filename*=UTF-8''Caf%C3%A9%20notes.TXT", download.headers["Content-Disposition"])

    def test_upload_name_is_a_basename_not_a_path(self):
        for index, filename in enumerate(("../../letter.txt", r"C:\fakepath\letter.txt")):
            with self.subTest(filename=filename):
                response = self.register(username=f"person_{index}", filename=filename)
                self.assertIn(b'class="file-name">letter.txt</p>', response.data)
                self.assertIn("filename=letter.txt", self.client.get("/download").headers["Content-Disposition"])

    def test_invalid_filename_rejected(self):
        for filename in (".txt", "a" * 256 + ".txt"):
            with self.subTest(filename=filename):
                self.assertIn(b"Please use a valid filename.", self.register(filename=filename).data)

    def test_duplicate_form_preserves_details_not_password(self):
        self.register()
        self.logout()
        response = self.register()
        for value in (b'value="Nihal"', b'value="Patel"', b'value="demo@example.com"', b"123 Example Street"):
            self.assertIn(value, response.data)
        self.assertNotIn(b"class-demo-123", response.data)

    def test_preview_preserves_lines_and_escapes_html(self):
        response = self.register(content=b"First line\n<script>alert('x')</script>\nThird line")
        self.assertIn(b"<summary>Read text</summary>", response.data)
        self.assertIn(b"<pre>First line\n&lt;script&gt;", response.data)
        self.assertNotIn(b"<script>", response.data)

    def test_init_db_keeps_existing_records(self):
        self.register()
        result = self.app.test_cli_runner().invoke(args=["init-db"])
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(self.client.get("/download").data, b"One two\nthree  four\tfive.")

    def test_wrong_and_unknown_user_have_same_message(self):
        self.register()
        self.logout()
        for username in ("nihal_test", "does_not_exist", "' OR 1=1 --"):
            response = self.client.post("/login", data={"username": username, "password": "incorrect",
                                                       "csrf_token": self.token()})
            self.assertIn(b"Username or password is incorrect.", response.data)
            self.assertEqual(self.client.get("/profile").status_code, 302)

    def test_non_ascii_csrf_is_rejected_cleanly(self):
        self.token()
        self.assertEqual(self.client.post("/logout", data={"csrf_token": "é"}).status_code, 400)

    def test_profile_does_not_expose_password_or_hash(self):
        response = self.register()
        self.assertNotIn(b"class-demo-123", response.data)
        self.assertNotIn(b"pbkdf2:", response.data)
        self.assertEqual(response.headers["Cache-Control"], "no-store")

    def test_production_key_comes_from_environment(self):
        key = secrets.token_hex(32)
        with patch.dict(os.environ, {"POSTMARK_ENV": "production", "POSTMARK_SECRET_KEY": key}):
            app = create_app({"DATABASE": self.config["DATABASE"]})
            self.assertEqual(app.secret_key, key)

    def test_production_refuses_missing_key(self):
        with patch.dict(os.environ, {"POSTMARK_ENV": "production", "POSTMARK_SECRET_KEY": ""}):
            with self.assertRaisesRegex(RuntimeError, "POSTMARK_SECRET_KEY"):
                create_app()

    def test_wsgi_entry_point_loads_with_deployment_key(self):
        with patch.dict(os.environ, {"POSTMARK_SECRET_KEY": secrets.token_hex(32)}):
            namespace = runpy.run_path(str(Path(__file__).resolve().parents[1] / "postmark.wsgi"))
            response = namespace["application"].test_client().get("/register")
            self.assertEqual(response.status_code, 200)


if __name__ == "__main__":
    unittest.main()
