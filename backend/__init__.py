"""Ghost backend — Flask API and database layer."""

"""
This module sets up the Flask API and database layer for the Ghost backend.
"""

from flask import Flask, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_marshmallow import Marshmallow

def create_flask_app() -> Flask:
    """
    Creates a new Flask application instance.

    Returns:
        Flask: The created Flask application instance.
    """
    app = Flask(__name__)
    return app

def configure_database(app: Flask) -> None:
    """
    Configures the database connection for the Flask application.

    Args:
        app (Flask): The Flask application instance.
    """
    # Define the database connection URL
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///ghost.db"

def initialize_db(app: Flask) -> None:
    """
    Initializes the SQLAlchemy and Marshmallow instances for the Flask application.

    Args:
        app (Flask): The Flask application instance.
    """
    # Initialize the SQLAlchemy instance
    db = SQLAlchemy(app)
    # Initialize the Marshmallow instance
    ma = Marshmallow(app)

def import_modules(app: Flask) -> None:
    """
    Imports the routes and models for the Flask application.

    Args:
        app (Flask): The Flask application instance.
    """
    # Import routes and models
    from . import routes, models

def main() -> None:
    """
    Main entry point for the Ghost backend module.
    """
    # Create a new Flask application instance
    app = create_flask_app()
    # Configure the database connection
    configure_database(app)
    # Initialize the database layer
    initialize_db(app)
    # Import routes and models
    import_modules(app)

if __name__ == "__main__":
    main()