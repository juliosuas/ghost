"""
Ghost Test Suite
================

A comprehensive test suite for the Ghost application.
"""

import unittest
from unittest.mock import patch
from ghost import Ghost
from ghost.test.utils import get_test_url

class TestGhost(unittest.TestCase):
    """
    Test suite for the Ghost application.
    """

    def setUp(self):
        """
        Set up the test environment.
        """
        self.ghost = Ghost()

    @patch('ghost.Ghost.open')
    def test_open(self, mock_open):
        """
        Test the open method of the Ghost class.
        """
        mock_open.return_value.__enter__.return_value.read.return_value = 'test'
        self.assertEqual(self.ghost.open(get_test_url()).read(), 'test')

    @patch('ghost.Ghost.open')
    def test_open_with_options(self, mock_open):
        """
        Test the open method of the Ghost class with options.
        """
        mock_open.return_value.__enter__.return_value.read.return_value = 'test'
        self.assertEqual(self.ghost.open(get_test_url(), options={'timeout': 10}).read(), 'test')

    @patch('ghost.Ghost.open')
    def test_open_with_user_agent(self, mock_open):
        """
        Test the open method of the Ghost class with a custom user agent.
        """
        mock_open.return_value.__enter__.return_value.read.return_value = 'test'
        self.assertEqual(self.ghost.open(get_test_url(), user_agent='test_user_agent').read(), 'test')

    def test_get(self):
        """
        Test the get method of the Ghost class.
        """
        self.assertEqual(self.ghost.get(get_test_url()).status_code, 200)

    def test_get_with_options(self):
        """
        Test the get method of the Ghost class with options.
        """
        self.assertEqual(self.ghost.get(get_test_url(), options={'timeout': 10}).status_code, 200)

    def test_get_with_user_agent(self):
        """
        Test the get method of the Ghost class with a custom user agent.
        """
        self.assertEqual(self.ghost.get(get_test_url(), user_agent='test_user_agent').status_code, 200)

    def test_post(self):
        """
        Test the post method of the Ghost class.
        """
        self.assertEqual(self.ghost.post(get_test_url()).status_code, 200)

    def test_post_with_options(self):
        """
        Test the post method of the Ghost class with options.
        """
        self.assertEqual(self.ghost.post(get_test_url(), options={'timeout': 10}).status_code, 200)

    def test_post_with_user_agent(self):
        """
        Test the post method of the Ghost class with a custom user agent.
        """
        self.assertEqual(self.ghost.post(get_test_url(), user_agent='test_user_agent').status_code, 200)

    def test_head(self):
        """
        Test the head method of the Ghost class.
        """
        self.assertEqual(self.ghost.head(get_test_url()).status_code, 200)

    def test_head_with_options(self):
        """
        Test the head method of the Ghost class with options.
        """
        self.assertEqual(self.ghost.head(get_test_url(), options={'timeout': 10}).status_code, 200)

    def test_head_with_user_agent(self):
        """
        Test the head method of the Ghost class with a custom user agent.
        """
        self.assertEqual(self.ghost.head(get_test_url(), user_agent='test_user_agent').status_code, 200)

    def test_delete(self):
        """
        Test the delete method of the Ghost class.
        """
        self.assertEqual(self.ghost.delete(get_test_url()).status_code, 200)

    def test_delete_with_options(self):
        """
        Test the delete method of the Ghost class with options.
        """
        self.assertEqual(self.ghost.delete(get_test_url(), options={'timeout': 10}).status_code, 200)

    def test_delete_with_user_agent(self):
        """
        Test the delete method of the Ghost class with a custom user agent.
        """
        self.assertEqual(self.ghost.delete(get_test_url(), user_agent='test_user_agent').status_code, 200)

if __name__ == '__main__':
    unittest.main()