# -*- coding: utf-8 -*-
#
# This file is part of rss2email.
#
# rss2email is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, either version 2 of the License, or (at your option) version 3 of
# the License.
#
# rss2email is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# rss2email.  If not, see <http://www.gnu.org/licenses/>.

"""Test for the check-subscribe command
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import configparser

from rss2email.command import check_subscribe, _is_rss_or_atom_content

class TestCheckSubscribe(unittest.TestCase):
    def setUp(self):
        # Create a mock feeds object
        self.feeds = Mock()
        self.feeds.config = configparser.ConfigParser()
        self.feeds.config['DEFAULT'] = {
            'user-agent': 'rss2email/3.14',
            'email-protocol': 'sendmail',
            'from': 'test@example.com',
            'to': 'recipient@example.com',
            'sendmail': '/usr/sbin/sendmail'
        }
        
        # Create mock feed objects
        self.feed1 = Mock()
        self.feed1.name = 'Test Feed 1'
        self.feed1.url = 'https://example.com/feed1.rss'
        
        self.feed2 = Mock()
        self.feed2.name = 'Test Feed 2'
        self.feed2.url = 'https://example.com/feed2.rss'
        
        self.feed3 = Mock()
        self.feed3.name = 'Test Feed 3'
        self.feed3.url = 'https://example.com/feed3.rss'
        
        self.feeds.index = Mock(side_effect=lambda x: [self.feed1, self.feed2, self.feed3][x])
        self.feeds.__len__ = Mock(return_value=3)
        
        # Create mock args
        self.args = Mock()
        self.args.index = [0, 1, 2]
    
    @patch('rss2email.command._requests.get')
    def test_check_subscribe_success(self, mock_get):
        """Test successful feed checking with valid RSS content"""
        # Mock successful response with valid RSS content
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b'<rss version="2.0"><channel><title>Test Feed</title></channel></rss>'
        mock_response.history = []
        mock_get.return_value = mock_response
        
        # Run the command
        check_subscribe(self.feeds, self.args)
        
        # Verify requests.get was called with correct parameters
        self.assertEqual(mock_get.call_count, 3)
        # Check that requests.get was called with the correct URL
        calls = mock_get.call_args_list
        urls = [call[0][0] for call in calls]
        self.assertIn('https://example.com/feed1.rss', urls)
        self.assertIn('https://example.com/feed2.rss', urls)
        self.assertIn('https://example.com/feed3.rss', urls)
    
    @patch('rss2email.command._requests.get')
    def test_check_subscribe_redirect(self, mock_get):
        """Test feed checking with redirect"""
        # Mock redirect response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b'<rss>test content</rss>'
        mock_response.url = 'https://example.com/redirected.rss'
        mock_response.history = [Mock(url='https://example.com/feed1.rss')]
        mock_get.return_value = mock_response
        
        # Run the command
        check_subscribe(self.feeds, self.args)
        
        # Verify redirect was detected
        self.assertEqual(mock_get.call_count, 3)
    
    @patch('rss2email.command._requests.get')
    def test_check_subscribe_404(self, mock_get):
        """Test feed checking with 404 error"""
        # Mock 404 response
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.reason = 'Not Found'
        mock_response.history = []
        mock_get.return_value = mock_response
        
        # Run the command
        check_subscribe(self.feeds, self.args)
        
        # Verify error was handled
        self.assertEqual(mock_get.call_count, 3)
    
    @patch('rss2email.command._requests.get')
    def test_check_subscribe_timeout(self, mock_get):
        """Test feed checking with timeout"""
        # Mock timeout exception
        import requests
        mock_get.side_effect = requests.exceptions.Timeout()
        
        # Run the command
        check_subscribe(self.feeds, self.args)
        
        # Verify timeout was handled
        self.assertEqual(mock_get.call_count, 3)
    
    @patch('rss2email.command._requests.get')
    def test_check_subscribe_connection_error(self, mock_get):
        """Test feed checking with connection error"""
        # Mock connection error
        import requests
        mock_get.side_effect = requests.exceptions.ConnectionError("Connection failed")
        
        # Run the command
        check_subscribe(self.feeds, self.args)
        
        # Verify connection error was handled
        self.assertEqual(mock_get.call_count, 3)
    
    def test_check_subscribe_no_url(self):
        """Test feed checking with no URL configured"""
        # Create feed without URL
        feed_no_url = Mock()
        feed_no_url.name = 'No URL Feed'
        feed_no_url.url = None
        
        self.feeds.index = Mock(return_value=feed_no_url)
        self.args.index = [0]
        
        # Run the command
        check_subscribe(self.feeds, self.args)
        
        # Should handle missing URL gracefully
        self.feeds.index.assert_called_once_with(0)
    
    def test_check_subscribe_all_feeds(self):
        """Test checking all feeds when no index specified"""
        self.args.index = None
        
        with patch('rss2email.command._requests.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.content = b'<rss>test content</rss>'
            mock_response.history = []
            mock_get.return_value = mock_response
            
            # Run the command
            check_subscribe(self.feeds, self.args)
            
        # Should check all feeds
        self.assertEqual(mock_get.call_count, 3)
    
    @patch('rss2email.command._send_availability_report')
    @patch('rss2email.command._requests.get')
    def test_check_subscribe_sends_email_on_problems(self, mock_get, mock_send_report):
        """Test that email is sent when there are problematic feeds"""
        # Mock one successful and two failed responses
        def side_effect(url, **kwargs):
            response = Mock()
            if 'feed1' in url:
                response.status_code = 200
                response.content = b'<rss>test content</rss>'
                response.history = []
            else:
                response.status_code = 404
                response.reason = 'Not Found'
                response.history = []
            return response
        
        mock_get.side_effect = side_effect
        
        # Run the command
        check_subscribe(self.feeds, self.args)
        
        # Should send email report because there are problems
        mock_send_report.assert_called_once()
        
        # Check that the call was made with the right arguments
        call_args = mock_send_report.call_args[0]
        self.assertEqual(len(call_args), 3)  # feeds, problem_feeds, successful_feeds
        self.assertEqual(len(call_args[1]), 2)  # two problematic feeds
        self.assertEqual(len(call_args[2]), 0)  # no successful feeds in email
    
    @patch('rss2email.command._send_availability_report')
    @patch('rss2email.command._requests.get')
    def test_check_subscribe_no_email_on_success(self, mock_get, mock_send_report):
        """Test that no email is sent when all feeds are successful"""
        # Mock all successful responses
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b'<rss>test content</rss>'
        mock_response.history = []
        mock_get.return_value = mock_response
        
        # Run the command
        check_subscribe(self.feeds, self.args)
        
        # Should not send email report because all feeds are successful
        mock_send_report.assert_not_called()
    
    @patch('rss2email.command._send_availability_report')
    @patch('rss2email.command._requests.get')
    def test_check_subscribe_non_rss_content(self, mock_get, mock_send_report):
        """Test that non-RSS content is detected as problematic"""
        # Mock response with HTML content (not RSS/Atom)
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b'<html><head><title>Test Page</title></head><body>Hello World</body></html>'
        mock_response.history = []
        mock_get.return_value = mock_response
        
        # Run the command
        check_subscribe(self.feeds, self.args)
        
        # Should send email report because content is not RSS/Atom
        mock_send_report.assert_called_once()
        
        # Check that the call was made with the right arguments
        call_args = mock_send_report.call_args[0]
        self.assertEqual(len(call_args), 3)  # feeds, problem_feeds, successful_feeds
        self.assertEqual(len(call_args[1]), 3)  # three problematic feeds (non-RSS content)
        self.assertEqual(len(call_args[2]), 0)  # no successful feeds
    
    @patch('rss2email.command._send_availability_report')
    @patch('rss2email.command._requests.get')
    def test_check_subscribe_atom_content(self, mock_get, mock_send_report):
        """Test that Atom content is recognized as valid"""
        # Mock response with Atom content
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b'<feed xmlns="http://www.w3.org/2005/atom"><title>Test Feed</title></feed>'
        mock_response.history = []
        mock_get.return_value = mock_response
        
        # Run the command
        check_subscribe(self.feeds, self.args)
        
        # Should not send email report because Atom content is valid
        mock_send_report.assert_not_called()
    
    @patch('rss2email.command._send_availability_report')
    @patch('rss2email.command._requests.get')
    def test_check_subscribe_empty_content(self, mock_get, mock_send_report):
        """Test that empty content is detected as problematic"""
        # Mock response with empty content
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b''
        mock_response.history = []
        mock_get.return_value = mock_response
        
        # Run the command
        check_subscribe(self.feeds, self.args)
        
        # Should send email report because content is empty
        mock_send_report.assert_called_once()
        
        # Check that the call was made with the right arguments
        call_args = mock_send_report.call_args[0]
        self.assertEqual(len(call_args), 3)  # feeds, problem_feeds, successful_feeds
        self.assertEqual(len(call_args[1]), 3)  # three problematic feeds (empty content)
        self.assertEqual(len(call_args[2]), 0)  # no successful feeds
    
    @patch('rss2email.command._send_availability_report')
    @patch('rss2email.command._requests.get')
    def test_check_subscribe_sends_single_email_for_multiple_problems(self, mock_get, mock_send_report):
        """Test that only one email is sent at the end, not per problematic feed"""
        # Mock responses: one successful, two problematic
        def side_effect(url, **kwargs):
            response = Mock()
            if 'feed1' in url:
                # Successful RSS feed
                response.status_code = 200
                response.content = b'<rss version="2.0"><channel><title>Test</title></channel></rss>'
                response.history = []
            elif 'feed2' in url:
                # Problematic feed - 404
                response.status_code = 404
                response.reason = 'Not Found'
                response.history = []
            else:
                # Another problematic feed - non-RSS content
                response.status_code = 200
                response.content = b'<html><body>Not RSS</body></html>'
                response.history = []
            return response
        
        mock_get.side_effect = side_effect
        
        # Run the command
        check_subscribe(self.feeds, self.args)
        
        # Should send email report only once, not per problematic feed
        mock_send_report.assert_called_once()
        
        # Check that the call was made with the right arguments
        call_args = mock_send_report.call_args[0]
        self.assertEqual(len(call_args), 3)  # feeds, problem_feeds, successful_feeds
        self.assertEqual(len(call_args[1]), 2)  # two problematic feeds
        self.assertEqual(len(call_args[2]), 0)  # no successful feeds in email

class TestContentValidation(unittest.TestCase):
    def test_is_rss_content(self):
        """Test RSS content detection"""
        # Valid RSS content
        rss_content = b'<rss version="2.0"><channel><title>Test</title></channel></rss>'
        self.assertTrue(_is_rss_or_atom_content(rss_content))
        
        # RSS with RDF
        rdf_content = b'<rdf:rdf xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"></rdf:rdf>'
        self.assertTrue(_is_rss_or_atom_content(rdf_content))
    
    def test_is_atom_content(self):
        """Test Atom content detection"""
        # Valid Atom content
        atom_content = b'<feed xmlns="http://www.w3.org/2005/atom"><title>Test</title></feed>'
        self.assertTrue(_is_rss_or_atom_content(atom_content))
        
        # Atom with xmlns:atom
        atom_ns_content = b'<feed xmlns:atom="http://www.w3.org/2005/atom"></feed>'
        self.assertTrue(_is_rss_or_atom_content(atom_ns_content))
    
    def test_is_not_feed_content(self):
        """Test non-feed content detection"""
        # HTML content
        html_content = b'<html><head><title>Test</title></head><body>Hello</body></html>'
        self.assertFalse(_is_rss_or_atom_content(html_content))
        
        # Plain text
        text_content = b'This is just plain text'
        self.assertFalse(_is_rss_or_atom_content(text_content))
        
        # Empty content
        empty_content = b''
        self.assertFalse(_is_rss_or_atom_content(empty_content))
        
        # JSON content
        json_content = b'{"title": "Test", "items": []}'
        self.assertFalse(_is_rss_or_atom_content(json_content))

if __name__ == '__main__':
    unittest.main()
