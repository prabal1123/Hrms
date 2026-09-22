# import os
# from pathlib import Path
# from cryptography.fernet import Fernet
# from django.core.exceptions import ImproperlyConfigured

# # Load local environment variables if python-dotenv is present
# try:
#     from dotenv import load_dotenv
#     load_dotenv()
# except ImportError:
#     pass

# BASE_DIR = Path(__file__).resolve().parent.parent

# SECRET_KEY = os.environ.get(
#     "DJANGO_SECRET_KEY",
#     "django-insecure-dev-fallback-key-replace-in-production"
# )

# DEBUG = os.environ.get("DJANGO_DEBUG", "True").lower() in ("true", "1", "t")

# # ENCRYPTION_KEY must be a stable, permanent value in every environment.
# # It is never auto-generated: a key that changes between runs makes all
# # previously encrypted data (email, phone, salary, PF, ESI, deductions)
# # permanently unreadable.
# ENCRYPTION_KEY = os.environ.get("ENCRYPTION_KEY", "").strip()
# if not ENCRYPTION_KEY:
#     raise ImproperlyConfigured(
#         "ENCRYPTION_KEY is not set. Generate one once with:\n"
#         "  python -c \"from cryptography.fernet import Fernet; "
#         "print(Fernet.generate_key().decode())\"\n"
#         "then add ENCRYPTION_KEY=<value> to your .env file (local) or your "
#         "environment (production), and back it up. If the key is lost, "
#         "encrypted data cannot be recovered. If you are using a .env file, "
#         "make sure python-dotenv is installed (pip install -r requirements.txt)."
#     )
# try:
#     Fernet(ENCRYPTION_KEY.encode())
# except (ValueError, TypeError) as exc:
#     raise ImproperlyConfigured(
#         "ENCRYPTION_KEY is not a valid Fernet key (it must be 32 url-safe "
#         "base64-encoded bytes). Generate a new one with Fernet.generate_key()."
#     ) from exc

# ALLOWED_HOSTS = [
#     host.strip()
#     for host in os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
#     if host.strip()
# ]

# INSTALLED_APPS = [
#     "django.contrib.admin",
#     "django.contrib.auth",
#     "django.contrib.contenttypes",
#     "django.contrib.sessions",
#     "django.contrib.messages",
#     "django.contrib.staticfiles",
#     "accounts",
#     "organizations",
#     "projects",
#     "employees",
# ]

# MIDDLEWARE = [
#     "django.middleware.security.SecurityMiddleware",
#     "django.contrib.sessions.middleware.SessionMiddleware",
#     "django.middleware.common.CommonMiddleware",
#     "django.middleware.csrf.CsrfViewMiddleware",
#     "django.contrib.auth.middleware.AuthenticationMiddleware",
#     "django.contrib.messages.middleware.MessageMiddleware",
#     "django.middleware.clickjacking.XFrameOptionsMiddleware",
# ]

# ROOT_URLCONF = "config.urls"

# TEMPLATES = [
#     {
#         "BACKEND": "django.template.backends.django.DjangoTemplates",
#         "DIRS": [BASE_DIR / "templates"],
#         "APP_DIRS": True,
#         "OPTIONS": {
#             "context_processors": [
#                 "django.template.context_processors.debug",
#                 "django.template.context_processors.request",
#                 "django.contrib.auth.context_processors.auth",
#                 "django.contrib.messages.context_processors.messages",
#                 "organizations.context_processors.user_organizations",
#             ],
#         },
#     },
# ]

# WSGI_APPLICATION = "config.wsgi.application"

# DATABASES = {
#     "default": {
#         "ENGINE": "django.db.backends.sqlite3",
#         "NAME": BASE_DIR / "db.sqlite3",
#     }
# }

# AUTH_PASSWORD_VALIDATORS = [
#     {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
#     {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 10}},
#     {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
#     {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
# ]

# LANGUAGE_CODE = "en-us"
# # In your settings.py:

# TIME_ZONE = 'Asia/Kolkata'
# USE_TZ = True

# # STATIC_URL = "static/"
# # STATIC_ROOT = BASE_DIR / 'static'
# # STATICFILES_DIRS = [BASE_DIR / "static"]

# STATIC_URL = "static/"
# STATIC_ROOT = BASE_DIR / "staticfiles"
# STATICFILES_DIRS = [BASE_DIR / "static"]

# DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# LOGIN_URL = "login"
# LOGIN_REDIRECT_URL = "home"
# LOGOUT_REDIRECT_URL = "login"

# # Email. In development the message is printed in the terminal running
# # runserver. Azure (or SMTP) will replace this backend in production.
# EMAIL_BACKEND = os.environ.get(
#     "EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend"
# )
# DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "OrgManager <no-reply@localhost>")

# # Session & Cookie Security
# SESSION_COOKIE_HTTPONLY = True
# CSRF_COOKIE_HTTPONLY = True
# SESSION_COOKIE_SAMESITE = "Lax"
# CSRF_COOKIE_SAMESITE = "Lax"
# SESSION_COOKIE_AGE = 43200  # 12 hours
# SESSION_EXPIRE_AT_BROWSER_CLOSE = True

# if not DEBUG:
#     SESSION_COOKIE_SECURE = True
#     CSRF_COOKIE_SECURE = True
#     SECURE_SSL_REDIRECT = True
#     SECURE_HSTS_SECONDS = 31536000
#     SECURE_HSTS_INCLUDE_SUBDOMAINS = True
#     SECURE_HSTS_PRELOAD = True
#     SECURE_BROWSER_XSS_FILTER = True
#     SECURE_CONTENT_TYPE_NOSNIFF = True
#     X_FRAME_OPTIONS = "DENY"


import os
from pathlib import Path
from cryptography.fernet import Fernet
from django.core.exceptions import ImproperlyConfigured

# Load local environment variables if python-dotenv is present
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "django-insecure-dev-fallback-key-replace-in-production"
)

DEBUG = os.environ.get("DJANGO_DEBUG", "True").lower() in ("true", "1", "t")

# ENCRYPTION_KEY must be a stable, permanent value in every environment.
# It is never auto-generated: a key that changes between runs makes all
# previously encrypted data permanently unreadable.
ENCRYPTION_KEY = os.environ.get("ENCRYPTION_KEY", "").strip()
if not ENCRYPTION_KEY:
    raise ImproperlyConfigured(
        "ENCRYPTION_KEY is not set. Generate one once with:\n"
        "  python -c \"from cryptography.fernet import Fernet; "
        "print(Fernet.generate_key().decode())\"\n"
        "then add ENCRYPTION_KEY=<value> to your .env file (local) or your "
        "environment (production), and back it up. If the key is lost, "
        "encrypted data cannot be recovered. If you are using a .env file, "
        "make sure python-dotenv is installed (pip install -r requirements.txt)."
    )
try:
    Fernet(ENCRYPTION_KEY.encode())
except (ValueError, TypeError) as exc:
    raise ImproperlyConfigured(
        "ENCRYPTION_KEY is not a valid Fernet key (it must be 32 url-safe "
        "base64-encoded bytes). Generate a new one with Fernet.generate_key()."
    ) from exc

ALLOWED_HOSTS = [
    host.strip()
    for host in os.environ.get(
        "DJANGO_ALLOWED_HOSTS", 
        "localhost,127.0.0.1,18.61.200.14"
    ).split(",")
    if host.strip()
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "accounts",
    "organizations",
    "projects",
    "employees",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "organizations.context_processors.user_organizations",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 10}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kolkata"
USE_TZ = True

# Static files management
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "home"
LOGOUT_REDIRECT_URL = "login"

# Email backend fallback
EMAIL_BACKEND = os.environ.get(
    "EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend"
)
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "OrgManager <no-reply@localhost>")

# Session & Cookie Security
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = 43200  # 12 hours
SESSION_EXPIRE_AT_BROWSER_CLOSE = True

# Detect reverse proxy protocol headers from Nginx
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Production flags adapted for raw IP / non-SSL deployment
if not DEBUG:
    # Set to False to permit plain HTTP access without browser timeout loops
    SECURE_SSL_REDIRECT = False
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False

    # Disable HSTS while running on raw IP without an SSL cert
    SECURE_HSTS_SECONDS = 0
    SECURE_HSTS_INCLUDE_SUBDOMAINS = False
    SECURE_HSTS_PRELOAD = False

    # Security headers that remain active over plain HTTP
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = "DENY"