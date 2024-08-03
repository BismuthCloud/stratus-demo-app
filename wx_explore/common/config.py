import os


class Config():
    SECRET_KEY = os.environ.get('SECRET_KEY', os.urandom(32))

    POSTGRES_USER = "bismuth"
    POSTGRES_PASS = os.environ['BISMUTH_AUTH']
    POSTGRES_HOST = "169.254.169.254"
    POSTGRES_PORT = 5432
    POSTGRES_DB   = "bismuth"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    DATA_PROVIDER = os.environ['DATA_PROVIDER']

    if DATA_PROVIDER == "S3":
        INGEST_S3_ACCESS_KEY = os.environ['INGEST_S3_ACCESS_KEY']
        INGEST_S3_SECRET_KEY = os.environ['INGEST_S3_SECRET_KEY']
        INGEST_S3_REGION     = os.environ['INGEST_S3_REGION']
        INGEST_S3_BUCKET     = os.environ['INGEST_S3_BUCKET']
        INGEST_S3_ENDPOINT   = os.environ.get('INGEST_S3_ENDPOINT')
    elif DATA_PROVIDER == "AZURE_TABLES":
        INGEST_AZURE_TABLE_ACCOUNT_NAME = os.environ['INGEST_AZURE_TABLE_ACCOUNT_NAME']
        INGEST_AZURE_TABLE_ACCOUNT_KEY  = os.environ['INGEST_AZURE_TABLE_ACCOUNT_KEY']
        INGEST_AZURE_TABLE_NAME         = os.environ['INGEST_AZURE_TABLE_NAME']
    elif DATA_PROVIDER == "MONGO":
        INGEST_MONGO_SERVER_URI = os.environ['INGEST_MONGO_SERVER_URI']
        INGEST_MONGO_DATABASE   = os.environ['INGEST_MONGO_DATABASE']
        INGEST_MONGO_COLLECTION = os.environ['INGEST_MONGO_COLLECTION']
    else:
        raise ValueError(f"Unsupported DATA_PROVIDER {DATA_PROVIDER}")

    SENTRY_ENDPOINT = os.environ.get('SENTRY_ENDPOINT')

    TRACE_EXPORTER = os.environ.get('TRACE_EXPORTER')

    JAEGER_HOST = os.environ.get('JAEGER_HOST', 'jaeger')
    HONEYCOMB_API_KEY = os.environ.get('HONEYCOMB_API_KEY')
    HONEYCOMB_DATASET = os.environ.get('HONEYCOMB_DATASET')


Config.SQLALCHEMY_DATABASE_URI = f"postgresql://{Config.POSTGRES_USER}:{Config.POSTGRES_PASS}@{Config.POSTGRES_HOST}:{Config.POSTGRES_PORT}/{Config.POSTGRES_DB}"
