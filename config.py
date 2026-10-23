
import os
from datetime import timedelta

from dotenv import load_dotenv

load_dotenv()


class Config:
    APP_ENV = os.getenv('APP_ENV', 'development')
    SECRET_KEY = os.getenv('SECRET_KEY')

    # Database: Neon PostgreSQL in production, SQLite locally by default.
    SQLALCHEMY_DATABASE_URI = os.getenv(
        'DATABASE_URL',
        'sqlite:///portfolio.db',
    )

    if SQLALCHEMY_DATABASE_URI.startswith('postgres://'):
        SQLALCHEMY_DATABASE_URI = (
            'postgresql+psycopg://'
            + SQLALCHEMY_DATABASE_URI[len('postgres://'):]
        )
    elif SQLALCHEMY_DATABASE_URI.startswith('postgresql://'):
        SQLALCHEMY_DATABASE_URI = (
            'postgresql+psycopg://'
            + SQLALCHEMY_DATABASE_URI[len('postgresql://'):]
        )

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
    }

    MAX_CONTENT_LENGTH = 16 * 1024 * 1024

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_SECURE = APP_ENV == 'production'
    REMEMBER_COOKIE_SECURE = APP_ENV == 'production'
    PERMANENT_SESSION_LIFETIME = timedelta(hours=2)
    WTF_CSRF_TIME_LIMIT = 7200

    # No separate Redis service required for the basic deployment.
    RATELIMIT_STORAGE_URI = os.getenv(
        'RATELIMIT_STORAGE_URI',
        'memory://',
    )

    # Production can use repository-managed files in static/.
    # S3 is optional, not required for the free setup.
    STORAGE_BACKEND = os.getenv('STORAGE_BACKEND', 'local')

    S3_BUCKET = os.getenv('S3_BUCKET')
    S3_REGION = os.getenv('S3_REGION', 'us-east-1')
    S3_ENDPOINT_URL = os.getenv('S3_ENDPOINT_URL') or None
    S3_ACCESS_KEY_ID = os.getenv('S3_ACCESS_KEY_ID')
    S3_SECRET_ACCESS_KEY = os.getenv('S3_SECRET_ACCESS_KEY')

    SITE_URL = os.getenv(
        'SITE_URL',
        'http://127.0.0.1:5000',
    ).rstrip('/')

    TRUST_PROXY = (
        os.getenv('TRUST_PROXY', 'false').lower() == 'true'
    )
