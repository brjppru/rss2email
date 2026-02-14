# Copyright (C) 2012-2022 Amir Yalon <git@please.nospammail.net>
#                         Etienne Millon <me@emillon.org>
#                         Faye Duxovni <duxovni@duxovni.org>
#                         Gregory Soutade <gregory@soutade.fr>
#                         Kaashif Hymabaccus <kaashif@kaashif.co.uk>
#                         Karthikeyan Singaravelan <tir.karthi@gmail.com>
#                         Léo Gaspard <leo@gaspard.io>
#                         Martin Monperrus <monperrus@users.noreply.github.com>
#                         Nicolas KAROLAK <nicolas@karolak.fr>
#                         Profpatsch <mail@profpatsch.de>
#                         Timendum <timedum@gmail.com>
#                         W. Trevor King <wking@tremily.us>
#                         auouymous <au@qzx.com>
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

"""rss2email commands
"""

import os as _os
import re as _re
import sys as _sys
import xml.dom.minidom as _minidom
import xml.sax.saxutils as _saxutils
import urllib as _urllib
import time as _time
import requests as _requests
import email.message as _email_message
from datetime import datetime as _datetime

from . import LOG as _LOG
from . import error as _error

def _is_rss_or_atom_content(content):
    """Check if content appears to be RSS or Atom feed."""
    if not content:
        return False
    
    content_str = content.decode('utf-8', errors='ignore').lower()
    
    # Check for RSS indicators
    rss_indicators = [
        '<rss',
        '<rdf:rdf',
        'xmlns:rss',
        'xmlns:rdf'
    ]
    
    # Check for Atom indicators
    atom_indicators = [
        '<feed',
        'xmlns:atom',
        'xmlns="http://www.w3.org/2005/atom"'
    ]
    
    # Check for either RSS or Atom
    for indicator in rss_indicators + atom_indicators:
        if indicator in content_str:
            return True
    
    return False

def new(feeds, args):
    "Create a new feed database."
    if args.email:
        _LOG.info('set the default target email to {}'.format(args.email))
        feeds.config['DEFAULT']['to'] = args.email
    if _os.path.exists(feeds.configfiles[-1]):
        raise _error.ConfigAlreadyExistsError(feeds=feeds)
    feeds.save_config()

def email(feeds, args):
    "Update the default target email address"
    if not args.email:
        _LOG.info('unset the default target email')
    else:
        _LOG.info('set the default target email to {}'.format(args.email))
    feeds.config['DEFAULT']['to'] = args.email
    feeds.save_config()

def add(feeds, args):
    "Add a new feed to the database"
    feed = feeds.new_feed(name=args.name, url=args.url, to=args.email)
    _LOG.info('add new feed {}'.format(feed))
    if not feed.to:
        raise _error.NoToEmailAddress(feed=feed, feeds=feeds)
    if args.only_new:
        feed.run(send=False, clean=False)
    feeds.save_config()
    feeds.save_feeds()

def run(feeds, args):
    "Fetch feeds and send entry emails."
    if not args.index:
        args.index = range(len(feeds))
    try:
        # How long (in seconds) to sleep between running feeds with
        # the same server.
        interval = float(feeds.config['DEFAULT']['same-server-fetch-interval'])

        # We use the domain name to determine if we are fetching from
        # the same server twice in a row.
        last_server = "example.com"
        for index in args.index:
            feed = feeds.index(index)
            # to debug feeds that timeout, run "r2e -VV run"
            _LOG.info('refreshing feed {}'.format(feed))
            if feed.active:
                current_server = _urllib.parse.urlparse(feed.url).netloc
                try:
                    if last_server == current_server:
                        _LOG.info('fetching from server {current_server} again, sleeping for {interval}s'.format(
                            current_server = current_server,
                            interval = interval
                        ))
                        _time.sleep(interval)
                    feed.run(send=args.send, clean=args.clean)
                except _error.RSS2EmailError as e:
                    e.log()
                last_server = current_server
    finally:
        feeds.save_feeds()

def list(feeds, args):
    "List all the feeds in the database"
    for i,feed in enumerate(feeds):
        if feed.active:
            active_char = '*'
        else:
            active_char = ' '
        print('{}: [{}] {}'.format(i, active_char, feed))

def _set_active(feeds, args, active=True):
    "Shared by `pause` and `unpause`."
    if active:
        action = 'unpause'
    else:
        action = 'pause'
    if not args.index:
        args.index = range(len(feeds))
    for index in args.index:
        feed = feeds.index(index)
        _LOG.info('{} feed {}'.format(action, feed))
        feed.active = active
    feeds.save_config()

def pause(feeds, args):
    "Pause a feed (disable fetching)"
    _set_active(feeds=feeds, args=args, active=False)

def unpause(feeds, args):
    "Unpause a feed (enable fetching)"
    _set_active(feeds=feeds, args=args, active=True)

def delete(feeds, args):
    "Remove a feed from the database"
    to_remove = []
    for index in args.index:
        feed = feeds.index(index)
        to_remove.append(feed)
    for feed in to_remove:
        _LOG.info('deleting feed {}'.format(feed))
        feeds.remove(feed)
    feeds.save_config()
    feeds.save_feeds()

def reset(feeds, args):
    "Forget dynamic feed data (e.g. to re-send old entries)"
    if not args.index:
        args.index = range(len(feeds))
    for index in args.index:
        feed = feeds.index(index)
        _LOG.info('resetting feed {}'.format(feed))
        feed.reset()
    feeds.save_feeds()

def opmlimport(feeds, args):
    "Import configuration from OPML."
    if args.file:
        _LOG.info('importing feeds from {}'.format(args.file))
        f = open(args.file, 'rb')
    else:
        _LOG.info('importing feeds from stdin')
        f = _sys.stdin
    try:
        dom = _minidom.parse(f)
        new_feeds = dom.getElementsByTagName('outline')
    except Exception as e:
        raise _error.OPMLReadError() from e
    if args.file:
        f.close()
    name_slug_regexp = _re.compile(r'[^\w\d.-]+')
    for feed in new_feeds:
        if feed.hasAttribute('xmlUrl'):
            url = _saxutils.unescape(feed.getAttribute('xmlUrl'))
            name = None
            if feed.hasAttribute('text'):
                text = _saxutils.unescape(feed.getAttribute('text'))
                if text != url:
                    name = name_slug_regexp.sub('-', text)
            feed = feeds.new_feed(name=name, url=url)
            _LOG.info('add new feed {}'.format(feed))
    feeds.save_config()
    feeds.save_feeds()

def opmlexport(feeds, args):
    "Export configuration to OPML."
    if args.file:
        _LOG.info('exporting feeds to {}'.format(args.file))
        f = open(args.file, 'wb')
    else:
        _LOG.info('exporting feeds to stdout')
        f = _sys.stdout.buffer
    f.write(
        b'<?xml version="1.0" encoding="UTF-8"?>\n'
        b'<opml version="1.0">\n'
        b'<head>\n'
        b'<title>rss2email OPML export</title>\n'
        b'</head>\n'
        b'<body>\n')
    for feed in feeds:
        if not feed.url:
            _LOG.debug('dropping {}'.format(feed))
            continue
        name = _saxutils.escape(feed.name)
        url = _saxutils.escape(feed.url)
        f.write('<outline type="rss" text="{}" xmlUrl="{}"/>\n'.format(
                name, url).encode())
    f.write(
        b'</body>\n'
        b'</opml>\n')
    if args.file:
        f.close()

def check_subscribe(feeds, args):
    "Check the availability of all subscribed feeds and send email report."
    headers = {
        'User-Agent': 'rss2email/{} (https://github.com/rss2email/rss2email)'.format(
            feeds.config['DEFAULT'].get('user-agent', 'rss2email'))
    }
    timeout_seconds = 15
    
    _LOG.info('Checking availability of {} feeds'.format(len(feeds)))
    
    if not args.index:
        args.index = range(len(feeds))
    
    # Store results for email report
    problem_feeds = []
    successful_feeds = []
    
    for index in args.index:
        feed = feeds.index(index)
        if not feed.url:
            _LOG.warning('[{}] No URL configured'.format(feed.name))
            problem_feeds.append({
                'name': feed.name,
                'url': 'No URL configured',
                'status': 'No URL',
                'message': 'No URL configured'
            })
            continue
            
        _LOG.info('Checking feed: {} ({})'.format(feed.name, feed.url))
        
        try:
            response = _requests.get(
                feed.url, 
                headers=headers, 
                timeout=timeout_seconds, 
                allow_redirects=True
            )
            
            # Check for redirects
            if response.history:
                final_url = response.url
                _LOG.info('[{}] {} -> REDIRECT TO: {}'.format(
                    feed.name, feed.url, final_url))
            
            # Check response status
            if response.status_code == 200:
                if response.content:
                    # Check if content is actually RSS/Atom
                    if _is_rss_or_atom_content(response.content):
                        _LOG.info('[{}] OK - Status 200, RSS/Atom content available'.format(feed.name))
                        successful_feeds.append({
                            'name': feed.name,
                            'url': feed.url,
                            'status': '200',
                            'message': 'OK - Status 200, RSS/Atom content available'
                        })
                    else:
                        _LOG.warning('[{}] WARNING - Status 200, but content is not RSS/Atom'.format(feed.name))
                        problem_feeds.append({
                            'name': feed.name,
                            'url': feed.url,
                            'status': '200',
                            'message': 'WARNING - Status 200, but content is not RSS/Atom format'
                        })
                else:
                    _LOG.warning('[{}] WARNING - Status 200, but content is empty'.format(feed.name))
                    problem_feeds.append({
                        'name': feed.name,
                        'url': feed.url,
                        'status': '200',
                        'message': 'WARNING - Status 200, but content is empty'
                    })
            else:
                _LOG.error('[{}] ERROR - Status {}: {}'.format(
                    feed.name, response.status_code, response.reason))
                problem_feeds.append({
                    'name': feed.name,
                    'url': feed.url,
                    'status': str(response.status_code),
                    'message': 'ERROR - Status {}: {}'.format(response.status_code, response.reason)
                })
                    
        except _requests.exceptions.Timeout:
            error_msg = 'ERROR - Request timeout ({} seconds)'.format(timeout_seconds)
            _LOG.error('[{}] {}'.format(feed.name, error_msg))
            problem_feeds.append({
                'name': feed.name,
                'url': feed.url,
                'status': 'Timeout',
                'message': error_msg
            })
        except _requests.exceptions.TooManyRedirects:
            error_msg = 'ERROR - Too many redirects'
            _LOG.error('[{}] {}'.format(feed.name, error_msg))
            problem_feeds.append({
                'name': feed.name,
                'url': feed.url,
                'status': 'TooManyRedirects',
                'message': error_msg
            })
        except _requests.exceptions.ConnectionError as e:
            error_msg = 'ERROR - Connection error: {}'.format(e)
            _LOG.error('[{}] {}'.format(feed.name, error_msg))
            problem_feeds.append({
                'name': feed.name,
                'url': feed.url,
                'status': 'ConnectionError',
                'message': error_msg
            })
        except _requests.exceptions.RequestException as e:
            error_msg = 'ERROR - Request error: {}'.format(e)
            _LOG.error('[{}] {}'.format(feed.name, error_msg))
            problem_feeds.append({
                'name': feed.name,
                'url': feed.url,
                'status': 'RequestError',
                'message': error_msg
            })
        except Exception as e:
            error_msg = 'ERROR - Unexpected error: {} - {}'.format(type(e).__name__, e)
            _LOG.error('[{}] {}'.format(feed.name, error_msg))
            problem_feeds.append({
                'name': feed.name,
                'url': feed.url,
                'status': 'UnexpectedError',
                'message': error_msg
            })
    
    # Send email report if there are problems
    if problem_feeds:
        _send_availability_report(feeds, problem_feeds, [])
    
    _LOG.info('Feed availability check completed')
    _LOG.info('Found {} problematic feeds, {} successful feeds'.format(
        len(problem_feeds), len(successful_feeds)))

def _send_availability_report(feeds, problem_feeds, successful_feeds):
    """Send email report about feed availability issues."""
    try:
        # Get current timestamp
        now = _datetime.now()
        timestamp = now.strftime('%Y-%m-%d %H:%M:%S')
        
        # Create email message
        message = _email_message.EmailMessage()
        
        # Set subject with timestamp
        subject = 'RSS Feed Availability Report - {}'.format(timestamp)
        message['Subject'] = subject
        
        # Set From header
        from_addr = feeds.config['DEFAULT'].get('from', 'rss2email@rss2email.invalid')
        message['From'] = from_addr
        
        # Set To header (use default email)
        to_addr = feeds.config['DEFAULT'].get('to', '')
        if to_addr:
            message['To'] = to_addr
        
        # Create email body
        body_lines = []
        body_lines.append('RSS Feed Availability Report')
        body_lines.append('Generated: {}'.format(timestamp))
        body_lines.append('')
        body_lines.append('PROBLEMATIC FEEDS ({}):'.format(len(problem_feeds)))
        body_lines.append('=' * 50)
        
        for feed in problem_feeds:
            body_lines.append('')
            body_lines.append('Feed: {}'.format(feed['name']))
            body_lines.append('URL: {}'.format(feed['url']))
            body_lines.append('Status: {}'.format(feed['status']))
            body_lines.append('Message: {}'.format(feed['message']))
            body_lines.append('-' * 30)
        
        body_lines.append('')
        body_lines.append('End of report')
        
        # Set email body
        message.set_content('\n'.join(body_lines))
        
        # Send email using the same method as regular feeds
        _LOG.info('Sending availability report email to {}'.format(to_addr))
        
        # Use the same email sending mechanism as regular feeds
        from . import email as _email_module
        _email_module.send(recipient=to_addr, message=message, config=feeds.config)
        
        _LOG.info('Availability report email sent successfully')
        
    except Exception as e:
        _LOG.error('Failed to send availability report email: {}'.format(e))
