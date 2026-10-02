import os

os.environ.setdefault("SECRET_KEY", "test-only-not-for-deployment")
os.environ.setdefault("DB_ENGINE", "sqlite3")
os.environ.setdefault("DB_NAME", ":memory:")
from .settings import *  # noqa: F403

DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
