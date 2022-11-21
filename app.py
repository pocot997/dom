from os import getenv, urandom

from flask import Flask
from flask_httpauth import HTTPBasicAuth
from flask_sqlalchemy import SQLAlchemy

from utils import generate_password

DATABASE_URL = getenv("DOM_DB_URL", "sqlite:///dom.db")
SECRET_KEY = getenv("DOM_SECRET_KEY", "2137".hex())

USERNAME = getenv("DOM_USERNAME", "admin")
PASSWORD = getenv("DOM_PASSWORD") or generate_password()

app = Flask(__name__)
app.config["SECRET_KEY"] = SECRET_KEY
app.config["MAX_CONTENT_LENGTH"] = 20 * 1000 * 1000
app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)
auth = HTTPBasicAuth()


@auth.verify_password
def authenticate(username, password):
    if not (username and password):
        return False
    # TODO: sprawdzić z użytkownikiem z bazy + dodać haszowanie jak chcemy
    return (username == USERNAME) and (password == PASSWORD)


# TODO: tu zaimportować blueprinty (https://flask.palletsprojects.com/en/2.2.x/blueprints/)
from controller.credential import credentials
from controller.custom_operation import custom_operations
from controller.machine import machines

db.create_all()

app.register_blueprint(credentials)
app.register_blueprint(custom_operations)
app.register_blueprint(machines)

@app.route("/info/health")
def healthcheck():
    return "", 204


if __name__ == "__main__":
    app.run(debug=True)