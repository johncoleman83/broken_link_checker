#!/usr/bin/env python3
"""
Scrapes urls from file for email addresses & social media
while scraping, it also looks for new urls to add to the queue of urls
"""
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from modules.errors import insert
from modules.file_io import io
from modules.urls import helpers
import queue
import re
import os
import requests
import datetime
import random

# url helpers
url_is_new = helpers.url_is_new
url_is_image_or_css_link = helpers.url_is_image_or_css_link
url_is_valid = helpers.url_is_valid
do_social_media_checks = helpers.do_social_media_checks

# Storage
all_links = set()
all_social_links = set()
all_emails = set()
links_to_scrape_q = queue.Queue()

# Requests
TIMEOUT = (3, 10)
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36'
}

# FILES
FILE_HASH = str(random.random()).split('.')[1]
ALL_OUTPUT_FILE = './file_storage/email_social_links_' + FILE_HASH
NEWLY_FOUND_URLS = './file_storage/newly_found_urls_' + FILE_HASH

# REGEX
EMAIL_PATH_PATTERN = re.compile('about|affiliations|board|departments|directory|governance|leadership|staff|team', re.IGNORECASE|re.DOTALL)

def url_could_contain_email_link(original_domain, parsed_url_object, url):
    """
    checks if input url could contian a link with emails
    """
    if not original_domain or original_domain not in url:    return False
    if url_could_be_social_media(url):                       return False
    query = parsed_url_object.query
    if query.__class__.__name__ == 'str' and len(query) > 0: return False
    path = parsed_url_object.path
    if path.__class__.__name__ != 'str' or len(path) < 4:    return False
    path = path.lower()
    m = re.search(EMAIL_PATH_PATTERN, path)
    return m is not None

def get_original_domain_from_url(parsed_url_object):
    """
    gets the original domain
    """
    original_domain = parsed_url_object.netloc
    if original_domain.__class__.__name__ != 'str' or len(original_domain) == 0:
        return None
    return original_domain

def parse_response_for_emails(r):
    """
    looks for emails in response
    """
    emails = set(re.findall(r"[a-z0-9\.\-+_]+@[a-z0-9\.\-+_]+\.[a-z]+", r.text, re.I)) - all_emails
    valid_emails = set()
    for e in emails:
        if not url_is_image_or_css_link(e):
            valid_emails.add(e)
    if len(valid_emails) > 0:
        all_emails.update(valid_emails)
    return valid_emails

def parse_response(original_domain, r):
    """
    parses response text for new links to add to queue
    """
    soup = BeautifulSoup(r.text, 'html.parser')
    pattern = re.compile('(http.*\:\/\/.*\.+.*\/.*)', re.IGNORECASE)
    social_links = set()
    for link in soup.find_all('a'):
        new_url = link.get('href', None)
        if new_url.__class__.__name__ != 'str' or len(new_url) == 0: continue
        url_lowered = new_url.lower()
        parsed_url_object = urlparse(url_lowered)
        m = re.search(pattern, new_url)
        if m is None or not url_is_valid(url_lowered, all_links):
            continue
        if do_social_media_checks(url_lowered, all_social_links):
            social_links.add(new_url)
            all_social_links.add(url_lowered)
        if url_could_contain_email_link(original_domain, parsed_url_object, url_lowered):
            with open(NEWLY_FOUND_URLS, "a", encoding="utf-8") as open_file:
                open_file.write("{}\n".format(new_url))
            all_links.add(new_url)
            links_to_scrape_q.put(new_url)
    emails = parse_response_for_emails(r)
    return emails, social_links

def scrape_url(url):
    """
    makes request to input url and passes the response to be scraped and parsed
    if it is not an error code response
    """
    try:
        r = requests.get(url, allow_redirects=True, timeout=TIMEOUT)
    except Exception as e:
        print('ERROR with URL: {}'.format(url))
        return
    status_code = r.status_code
    if r and r.headers:
        content_type = r.headers.get('Content-Type', 'None')
    else:
        return
    if (status_code >= 300 or content_type.__class__.__name__ != 'str' or 'text/html' not in content_type.lower()):
        print('ERROR with URL: {}, status: {}, content-type: {}'.format(url, status_code, content_type))
        return
    parsed_original_url_object = urlparse(url)
    original_domain = get_original_domain_from_url(parsed_original_url_object)
    emails, social_links = parse_response(original_domain, r)
    io.temp_write_updates_to_files(url, emails, social_links)

def loop_all_links():
    """
    loops through and makes request for all queue'd url's
    """
    while links_to_scrape_q.empty() is False:
        url = links_to_scrape_q.get()
        scrape_url(url)


def write_results_to_file():
    """
    final writing of results
    """
    FIRST_LINE = "TIME: {}\n".format(str(datetime.datetime.now()))
    with open(ALL_OUTPUT_FILE, "w", encoding="utf-8") as open_file:
        open_file.write(FIRST_LINE)
        for url, meta in all_links.items():

            if meta.__class__.__name__ == 'dict':
                line = "url: {}\n".format(url)
                if len(meta.get('emails', 0)) > 0:
                    line += "emails: {}\n".format(meta.get('emails', 0))
                if len(meta.get('social_media', 0)) > 0:
                    line += "social_media: {}\n".format(meta.get('social_media', 0))
                open_file.write(line)

def execute(INPUT_FILE):
    """
    completes all tasks of the application
    """
    io.read_file_add_to_queue(INPUT_FILE, all_links, links_to_scrape_q)
    io.initial_files([
        io.TEMP_EMAIL_OUTPUT_FILE, io.TEMP_SOCIAL_OUTPUT_FILE, io.CHECKED_URLS, NEWLY_FOUND_URLS
    ])
    loop_all_links()
    # No need anymore for this
    # write_results_to_file()

if __name__ == "__main__":
    """
    MAIN APP
    """
    print('usage: import this')
