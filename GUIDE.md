# Postmark — Project 2: start-to-finish guide

This guide follows the rubric you pasted. It covers all listed requirements, but
your instructor decides the grade. The app is supplied; you still need to run it
on your AWS account, capture evidence, personalize it, and submit the URL and code.

## 1. Get the course file and organize your evidence

1. Open the assignment in Canvas and download **Limerick (1).txt**. The actual file
   is not included here because its contents were not provided.
2. Create a `Project2_Evidence` folder on your Mac. Save screenshots there as you go.
3. Keep the source ZIP separate from the screenshots. Never put the `.pem` key in
   either submission or GitHub.
4. Confirm the exact due date in Canvas. The pasted page says “Due Sunday” and also
   lists a later availability closing date; these are different fields. Do not
   assume the availability date is the deadline.

## 2. Make the design yours

The supplied example is called **Postmark**: a warm ivory background, muted navy
buttons, and a saved-mail card with real file metadata.

Before deploying, open the source files in your editor:

- `templates/base.html`: change the site title/header/footer if desired.
- `templates/register.html`: change the opening line to something you would say.
- `static/style.css`: change `--paper`, `--ink`, `--blue`, and `--red` at the top.
- `templates/profile.html`: adjust the welcome message or file-card wording.

Keep the required field labels obvious. Do not rename the form `name=` attributes
unless you update `app.py` too. Do not remove login, logout, upload, word count,
or download while customizing. Use plain writing and your own screenshots; there
is no reliable promise that code will be unique or that an AI detector will label
it a certain way. Follow your course's rules on assistance and citations.

## 3. Launch the EC2 instance

In the AWS console:

1. Open **EC2**. Choose a region, for example **US East (Ohio), us-east-2**. Stay in
   that region so you can find the instance again.
2. Choose **Launch instance**.
3. Name it `nihal-project2`.
4. Choose **Ubuntu Server 24.04 LTS**, official Canonical image, 64-bit **x86**.
   Do not use Ubuntu 14.04 or Amazon Linux for these exact commands.
5. Choose a small compatible instance such as **t3.micro**, checking the eligibility
   and estimated charges shown for your account.
6. Create a key pair named `nihal-project2-key`, type **RSA**, format **.pem**.
   Download it and keep it on your Mac, preferably in Downloads for these commands.
7. Under Network settings, use the default VPC and a public/default subnet.
8. Set **Auto-assign public IP: Enable**.
9. Create a security group with the following inbound rules:

   | Type | Port | Source |
   |---|---:|---|
   | SSH | 22 | My IP (your current public IPv4 address, /32) |
   | HTTP | 80 | Anywhere-IPv4, 0.0.0.0/0 |

   Keep default outbound access. Port 5000 is unnecessary. SSH is for you; HTTP
   makes the website accessible to the grader.
10. Keep a small root disk, for example **8 GiB gp3**, if it satisfies the image's
    minimum and your account's limits.
11. Capture setup screenshots **before clicking Launch**: AMI, instance type,
    key-pair name/selection, public IP setting, inbound rules, and storage.
12. Launch. Wait for the instance to be running and all listed status checks to pass.
13. Copy the **Public IPv4 address** and **Public IPv4 DNS** from instance details.
    Capture the running instance and public address as another screenshot.

“Free tier eligible” is not a blanket promise of no charge. Eligibility depends on
your account age, plan, remaining credits, and usage. Check Billing/Free Tier before
launching and monitor it while the instance runs. A budget alert does not stop costs.
See [AWS Free Tier details](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-free-tier-usage.html).

AWS's launch reference is [Get started with EC2](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/EC2_GetStarted.html).
For the firewall rules, see [Create a security group](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/creating-security-group.html).

## 4. Connect from your Mac

Open **Terminal on your Mac**. Replace `YOUR_PUBLIC_IP` with the actual address
every time it appears below. Do not type the placeholder literally.

```bash
chmod 400 "$HOME/Downloads/nihal-project2-key.pem"
ssh -i "$HOME/Downloads/nihal-project2-key.pem" ubuntu@YOUR_PUBLIC_IP
```

If your key is in another location, change the path. On the first connection,
confirm you are connecting to the instance you just launched and accept its host
key prompt. You should get a prompt similar to `ubuntu@ip-...:~$`.

**From this point, commands in this terminal run on EC2**, not your Mac. Capture
a screenshot of the successful SSH prompt. Do not display the contents of the key.

If SSH times out, verify the public IP, running state, and port 22 source. If your
Wi-Fi/network changes, update the SSH rule to your new **My IP**. If you see
`Permission denied (publickey)`, check the `.pem` file and the username `ubuntu`.

## 5. Install the web server and Python packages

In the **EC2 terminal**:

```bash
sudo apt update
sudo apt install -y apache2 libapache2-mod-wsgi-py3 python3 python3-pip python3-flask sqlite3 unzip
sudo systemctl enable --now apache2
```

Verify the installation:

```bash
python3 --version
pip3 --version
python3 -c "import importlib.metadata; print('Flask', importlib.metadata.version('Flask'))"
sqlite3 --version
apache2 -v
sudo apache2ctl -M | grep wsgi
sudo systemctl status apache2 --no-pager
```

Take screenshots of the install output and version/module checks. `wsgi_module`
should appear and Apache should say `active (running)`.

Open `http://YOUR_PUBLIC_IP` in your Mac browser. You should see Apache's default
page. This proves the instance can serve traffic on port 80. Capture a screenshot.
Use explicit `http://`; this setup does not configure HTTPS.

These are Python 3 Ubuntu packages, matching your instructor's updated instructions.
Do not run `sudo pip install` or the obsolete `python-pip` command. Ubuntu confirms
the [Python 3 mod_wsgi package for 24.04](https://packages.ubuntu.com/en/noble/libapache2-mod-wsgi-py3).

## 6. Copy the source to EC2

The source folder and ZIP are already in your local Cloud Computing workspace.
If you changed the source files, rebuild the archive so it contains your changes.

Open a **second Terminal window on your Mac** and run:

```bash
cd "$HOME/Documents/ChatGPT/Cloud Computing"
python3 - <<'PY'
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
root = Path('Project2_AWS')
files = [root / name for name in (
    'app.py', 'schema.sql', 'requirements.txt', 'README.md', 'GUIDE.md',
    '.gitignore', 'postmark.wsgi',
)]
for folder, suffix in [('templates', '.html'), ('static', '.css'),
                       ('deploy', '.conf'), ('tests', '.py')]:
    files.extend((root / folder).rglob('*' + suffix))
with ZipFile('Project2_AWS_Source.zip', 'w', ZIP_DEFLATED) as archive:
    for path in sorted(files):
        archive.write(path, str(path))
print('Source ZIP rebuilt.')
PY
scp -i "$HOME/Downloads/nihal-project2-key.pem" Project2_AWS_Source.zip ubuntu@YOUR_PUBLIC_IP:/home/ubuntu/
```

Back in the **EC2 terminal**:

```bash
cd /home/ubuntu
unzip -o Project2_AWS_Source.zip
sudo mkdir -p /var/www/postmark
sudo cp -r /home/ubuntu/Project2_AWS/. /var/www/postmark/
sudo chown -R root:root /var/www/postmark
sudo find /var/www/postmark -type d -exec chmod 755 {} +
sudo find /var/www/postmark -type f -exec chmod 644 {} +
sudo install -d -o www-data -g www-data -m 750 /var/www/postmark/instance
sudo chown -R www-data:www-data /var/www/postmark/instance
```

Set the production secret on **EC2**, without printing it or putting it in the
source. The following generates it once and adds the source line to Apache's
environment file only if it is missing. Re-running keeps the existing secret.

```bash
sudo python3 - <<'PYSECRET'
import os
from pathlib import Path
import secrets

secret_file = Path('/etc/postmark.env')
if not secret_file.exists():
    fd = os.open(str(secret_file), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as handle:
        handle.write('export POSTMARK_SECRET_KEY=' + secrets.token_hex(32) + '\n')
        handle.write('export POSTMARK_ENV=production\n')
secret_file.chmod(0o600)
envvars = Path('/etc/apache2/envvars')
source_line = '. /etc/postmark.env'
if source_line not in envvars.read_text().splitlines():
    with envvars.open('a') as handle:
        handle.write('\n' + source_line + '\n')
print('Postmark environment configured; secret value not displayed.')
PYSECRET
cd /var/www/postmark
sudo sh -c '. /etc/postmark.env; exec runuser -u www-data -- python3 -m flask --app app:create_app init-db'
sudo chmod 640 /var/www/postmark/instance/postmark.db
ls -la /var/www/postmark
```

`runuser` runs initialization as Apache's account while inheriting the exported
Postmark variables. The production entry point requires `POSTMARK_SECRET_KEY`;
Apache reads it when started through its normal Ubuntu service scripts. Do not
screenshot or publish `/etc/postmark.env`, and do not replace this with an Apache
`SetEnv` directive: those are request variables, not Python process variables.

Expected message: **Database ready.** Screenshot the project files and that output.
Only `instance/` needs to be writable by Apache. Do not use `chmod 777`.
These are fresh-deployment commands; back up existing instance data before
replacing an installation. No database reset is needed for normal updates.

The app lives under `/var/www/postmark`, so changing `/home/ubuntu` permissions
as in the older tutorial is unnecessary.

## 7. Confirm the database table

In the **EC2 terminal**:

```bash
sudo -u www-data sqlite3 /var/www/postmark/instance/postmark.db '.tables'
sudo -u www-data sqlite3 /var/www/postmark/instance/postmark.db '.schema users'
```

Screenshot the table schema. It contains username, password hash, first name, last
name, email, address, filename, file bytes, word count, and creation time.

The file bytes use a **BLOB** column: SQLite stores the actual uploaded file, not
just its name. No separate upload directory or S3 bucket is needed for this small app.

## 8. Connect Apache to Flask

In the **EC2 terminal**:

```bash
sudo cp /var/www/postmark/deploy/postmark.conf /etc/apache2/sites-available/postmark.conf
sudo a2enmod wsgi
sudo a2ensite postmark
sudo a2dissite 000-default
sudo apache2ctl configtest
```

Continue only when the final result says **Syntax OK**. If it reports an error,
resolve it first using the file/line in the message.

```bash
sudo systemctl restart apache2
sudo systemctl status apache2 --no-pager
curl -I http://127.0.0.1/
```

A `302` response redirecting `/` to `/register` is expected. Open
`http://YOUR_PUBLIC_IP` again: the Postmark registration form should replace
Apache's default page. Screenshot the configuration test and your app in the browser.

`postmark.wsgi` exposes `application`; the virtual host sends requests to that
application in a mod_wsgi daemon process. Apache keeps serving it after you close
SSH. This is the assignment deployment; do not use Flask's development server as
the public server. See [Flask deployment guidance](https://flask.palletsprojects.com/en/stable/deploying/)
and [mod_wsgi daemon configuration](https://modwsgi.readthedocs.io/en/latest/user-guides/embedded-and-daemon-mode.html).

## 9. Test the complete grading flow

Use invented personal information and a password used only for this demo. HTTP
does not encrypt submitted data, even though passwords are hashed in storage.

1. Open the registration page and capture it with all field labels visible.
2. Enter a unique username, password, first name, last name, email, and address.
3. Click the file picker and choose the **actual Canvas Limerick (1).txt** file.
4. Capture the filled form with the selected filename; the password must stay masked.
5. Click **Create postbox**.
6. Confirm the browser redirects to `/profile` and shows all four personal-detail
   fields, original filename, word count, byte size, saved time (UTC), Postmark
   number, and download button. Capture this page. The number is derived from the
   actual SQLite ID. Expand **Read text** to check that line breaks are preserved.
7. Download the file, open it, and compare it to the original. Spaces in the
   original basename are preserved. Both files must contain identical bytes.
8. Click **Log out**. Capture the login page.
9. Enter the original username and password and log in. Confirm the same details,
   filename, and word count return. Capture the returned profile.
10. Log out, try an incorrect password, and confirm you get a helpful error rather
    than someone else's information. Capture the error.
11. Try registering the same username again. Confirm it is rejected without
    overwriting the original account.
12. Try a `.pdf` or empty `.txt` upload and verify the error message. Some browsers
    hide non-text files in the picker; choose “all files” if necessary for this test.
13. Open `/profile` and `/download` in a private/incognito window with no login.
    Both should redirect to login.
14. Register a second account with different details and a different text file.
    Confirm each account retrieves its own file and information when logging in.
15. Test a narrow browser window to check that fields and buttons remain usable.
16. Open the public AWS URL from your phone on cellular data. This checks access
    from outside your current network.

Do not claim an exact word count until you upload the supplied course file. The
app counts whitespace-separated words, including words separated by tabs or new
lines. It does not count punctuation as additional words. For example,
`Hello, world!` is two words.

Save the downloaded copy into a separate `Downloads/postmark-download` folder
so it is easy to compare without overwriting the original. You can verify the
count and file bytes on your **Mac**, adjusting these paths if needed:

```bash
python3 - <<'PY'
from pathlib import Path
original = Path.home() / 'Downloads' / 'Limerick (1).txt'
downloaded = Path.home() / 'Downloads' / 'postmark-download' / 'Limerick (1).txt'
print('Expected word count:', len(original.read_bytes().decode('utf-8-sig').split()))
print('Downloaded contents match:', original.read_bytes() == downloaded.read_bytes())
PY
```

## 10. Show that the data is really stored

After registering a demo account, run in **EC2**:

```bash
sudo -u www-data sqlite3 -header -column /var/www/postmark/instance/postmark.db "SELECT id, username, first_name, last_name, email, address, file_name, word_count, length(file_data) AS saved_bytes, created_at FROM users;"
```

Screenshot the result with invented data. It should agree with the profile page.
Do not use `SELECT *` for screenshots because it prints hashes and raw file content.

Then restart **Apache** (not the EC2 instance) to check persistence:

```bash
sudo systemctl restart apache2
```

Log in again and verify the saved record and file remain. Closing SSH should also
leave the site working.

Run the automated checks as another verification:

```bash
cd /var/www/postmark
python3 -m unittest discover -s tests -v
```

The tests use temporary databases and do not modify the real accounts. Screenshot
your own output if you want to include it; do not substitute it for browser evidence.

## 11. Troubleshoot common issues

| Symptom | What to check |
|---|---|
| SSH times out | Instance running; correct public IP; port 22 allows your current My IP. |
| Website times out | Port 80 allows 0.0.0.0/0; public IPv4 exists; public subnet has an internet-gateway route; Apache is active. |
| Browser tries HTTPS and fails | Type `http://` explicitly. This guide only configures HTTP. |
| Apache default page remains | Confirm postmark is enabled and 000-default disabled; restart Apache; refresh. |
| 500 Internal Server Error | Read the dedicated app error log below; check Flask package, paths, database, and permissions. |
| SQLite says readonly/unable to open | `instance/` must belong to www-data and be writable; the directory needs write permission for SQLite journal files too. |
| “No module named flask” | Run `sudo apt install python3-flask`; this guide uses system Python packages, not a personal virtual environment on EC2. |
| Form expired | Reload the form so it gets a new token; keep browser cookies enabled. |
| Missing POSTMARK_SECRET_KEY | Complete the secret setup in step 6; confirm the source line is in `/etc/apache2/envvars`, then restart Apache. Do not print the key. |
| HTTP 413 | Use the small original `.txt` file; the app allows a file up to 1 MB. |
| Site broke after a stop/start | Copy the new public IP/DNS from EC2 and retest; update the submitted URL if it changed. |

Useful **EC2** commands:

```bash
sudo tail -n 60 /var/log/apache2/postmark-error.log
sudo tail -n 60 /var/log/apache2/error.log
sudo apache2ctl -S
sudo systemctl status apache2 --no-pager
```

After changing Python files or Apache configuration, restart Apache and test again.
After changing CSS, a hard refresh may help. Re-run relevant tests after changes.

## 12. Package your evidence and code

Your source ZIP fulfills the “GitHub or attachment” requirement. A GitHub repository
is optional. If using GitHub, upload only source/templates/static/config/tests/docs;
exclude `instance/`, `.venv/`, `.pem` files, and caches. Confirm the grader can access
the repository and that the uploaded source matches the version running on AWS.

Suggested screenshot order:

1. EC2 launch settings: Ubuntu AMI, instance type, and storage.
2. Key-pair selection (never private key contents).
3. Public IP and security-group rules.
4. Running instance with public IPv4/DNS.
5. Successful SSH login.
6. Package installation and Python/Pip/Flask/SQLite/mod_wsgi versions.
7. Project files and database initialization.
8. SQLite schema.
9. Apache virtual host/config test.
10. Registration with required fields and selected course file.
11. Profile with details, word count, and download button.
12. Downloaded file and comparison result.
13. Re-login form and the restored profile.
14. Saved database row and error handling.

Put these in a Word/Google Docs report and export to PDF if desired. A simple title
page can contain your name, course, assignment, AWS URL, and code link or attachment
name. Give each screenshot a short caption explaining what it proves. Use real
observations, for example:

> This shows the security group I used. Port 80 lets visitors open the website,
> and port 22 is limited to my IP for SSH.

Only include statements that match what you actually did. A short closing note can
answer: What did I build? Where is the data saved? How did I verify re-login? What
issue did I actually encounter and how did I resolve it? If there was no issue,
do not invent one. Attribute tools or sources as required by your course.

## 13. Submit and keep the app reachable

The URL should look like `http://YOUR_PUBLIC_DNS/` or `http://YOUR_PUBLIC_IP/`.
Do not submit localhost, an AWS console link, or only the GitHub URL.

The pasted instructions require the URL plus code and screenshots, but Canvas may
only expose one submission type at a time. Prepare all three before submitting:

- If file upload is available, upload the evidence report and source ZIP, putting
  the AWS URL prominently in the report and submission comment if available.
- If you choose Website URL, enter the live AWS URL and provide the code/evidence
  via an allowed attachment or a clearly linked accessible repository/report.
- Preview the final submission. Do not assume an earlier attempt's attachments
  remain attached when you switch submission type. If neither method accommodates
  all required evidence, clarify the submission format with the instructor.

Keep EC2 running through the grading period and monitor billing. Stopping the
instance makes the site unavailable; a later start normally assigns a new public
IPv4 address. See [EC2 IP addressing](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/using-instance-addressing.html).
After grading, save what you need and remove unneeded AWS resources to avoid
ongoing charges, including any retained volumes or allocated Elastic IPs.

## Final rubric check

| Requirement | Evidence | Points |
|---|---|---:|
| Internet-accessible EC2 | Public URL, launch/network screenshots | 1 |
| Web server and SQLite | Apache/Flask setup, schema, stored row | 1 |
| Shared code | Source ZIP or accessible GitHub repository | 1 |
| Registration stored | Username/password form and saved account | 1 |
| Basic details stored | First/last name, email, address in SQLite | 1 |
| Redirect and display | Profile after successful registration | 1 |
| Re-login retrieves details | Logout, login, same saved profile | 2 |
| Upload, store, count, download | Actual Limerick file, saved bytes, count, successful download | 2 |
| Total | All items verified on the live AWS URL | 10 |
