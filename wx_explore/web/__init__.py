from flask import Flask
from flask_sqlalchemy import SQLAlchemy
import os

from wx_explore.web import config

app = Flask(__name__)
app.config.from_object(os.environ.get('CONFIG') or config.DevConfig)
app.config['SQLALCHEMY_DATABASE_URI'] = f"postgres://{app.config.get('POSTGRES_USER')}:{app.config.get('POSTGRES_PASS')}@{app.config.get('POSTGRES_HOST')}/{app.config.get('POSTGRES_DB')}"

from wx_explore.common.models import Base
db = SQLAlchemy(app, model_class=Base)

from flask_bootstrap import Bootstrap
Bootstrap(app)

from wx_explore.web.data.controller import api
app.register_blueprint(api)

db.create_all()
