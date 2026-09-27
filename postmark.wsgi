import os

from app import create_app

os.environ["POSTMARK_ENV"] = "production"
application = create_app()
