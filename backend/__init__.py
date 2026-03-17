"""Ghost backend — Flask API and database layer."""
"""
This module sets up the Flask API and database layer for the Ghost backend.
"""

from flask import Flask, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_marshmallow import Marshmallow

# Create a new Flask application instance
app = Flask(__name__)

# Define the database connection URL
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///ghost.db'

# Initialize the SQLAlchemy and Marshmallow instances
db = SQLAlchemy(app)
ma = Marshmallow(app)

# Import routes and models
from . import routes, models