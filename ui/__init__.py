"""Ghost UI — CLI and web dashboard."""

"""
This module serves as the main entry point for the Ghost UI application.
It handles CLI and web dashboard functionality.
"""

import os
import logging
from logging.handlers import RotatingFileHandler
from flask import Flask, render_template
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField
from wtforms.validators import InputRequired, Email, Length

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        RotatingFileHandler("ghost_ui.log", maxBytes=100000, backupCount=1),
        logging.StreamHandler(),
    ],
)

# Create Flask application instance
app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY")


# Define a form for user authentication
class LoginForm(FlaskForm):
    """Form for user login."""

    username = StringField(
        "Username", validators=[InputRequired(), Length(min=4, max=15)]
    )
    password = PasswordField("Password", validators=[InputRequired(), Length(min=8)])


# Define a route for the web dashboard
@app.route("/")
def index():
    """Render the web dashboard."""
    return render_template("index.html")


# Define a route for user login
@app.route("/login", methods=["GET", "POST"])
def login():
    """Handle user login."""
    form = LoginForm()
    if form.validate_on_submit():
        # Login logic goes here
        pass
    return render_template("login.html", form=form)


if __name__ == "__main__":
    app.run(debug=True)
