# Import necessary modules
import os
import re
import json
from datetime import datetime

class User:
    """
    Represents a user with a unique id and name.
    """

    def __init__(self, user_id, name):
        """
        Initializes a User instance.

        Args:
            user_id (int): Unique identifier for the user.
            name (str): Name of the user.
        """
        self.user_id = user_id
        self.name = name

class UserRepository:
    """
    Handles user data storage and retrieval.
    """

    def __init__(self, data_file):
        """
        Initializes a UserRepository instance.

        Args:
            data_file (str): Path to the data file.
        """
        self.data_file = data_file

    def load_users(self):
        """
        Loads user data from the data file.

        Returns:
            list[User]: List of User instances.
        """
        if not os.path.exists(self.data_file):
            return []

        with open(self.data_file, 'r') as file:
            data = json.load(file)
            return [User(user['id'], user['name']) for user in data]

    def save_users(self, users):
        """
        Saves user data to the data file.

        Args:
            users (list[User]): List of User instances.
        """
        data = [{'id': user.user_id, 'name': user.name} for user in users]
        with open(self.data_file, 'w') as file:
            json.dump(data, file, indent=4)

class UserService:
    """
    Provides user-related functionality.
    """

    def __init__(self, repository):
        """
        Initializes a UserService instance.

        Args:
            repository (UserRepository): UserRepository instance.
        """
        self.repository = repository

    def get_user(self, user_id):
        """
        Retrieves a user by their id.

        Args:
            user_id (int): Unique identifier for the user.

        Returns:
            User: User instance if found, None otherwise.
        """
        users = self.repository.load_users()
        for user in users:
            if user.user_id == user_id:
                return user
        return None

    def create_user(self, name):
        """
        Creates a new user with a unique id.

        Args:
            name (str): Name of the user.

        Returns:
            User: User instance with a unique id.
        """
        users = self.repository.load_users()
        max_id = max(user.user_id for user in users) if users else 0
        user_id = max_id + 1
        user = User(user_id, name)
        self.repository.save_users([user] + users)
        return user

def main():
    """
    Demonstrates user service functionality.
    """
    repository = UserRepository('users.json')
    service = UserService(repository)

    # Create a new user
    user = service.create_user('John Doe')
    print(f'Created user with id {user.user_id} and name {user.name}')

    # Retrieve a user by id
    retrieved_user = service.get_user(user.user_id)
    print(f'Retrieved user with id {retrieved_user.user_id} and name {retrieved_user.name}')

if __name__ == '__main__':
    main()