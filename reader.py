"""Scrape Kindle Cloud Reader for information regarding the Kindle Library and
current reading progress.
"""
from time import sleep
import os

from selenium import webdriver
from selenium.webdriver.firefox.firefox_profile import FirefoxProfile


class TimeoutError(Exception):
    """Indicate that a timeout has occurred
    """
    pass


def _wait_for(condition, cargs=None, ckwargs=None, wait=.1, timeout=5.):
    """Waits for `condition` to be a non-false value

    Args:
        condition: The function on which to wait
        cargs: The positional arguments with which to call `condition`
        cargs: The keyword arguments with which to call `condition`
        wait: The number of seconds to sleep between evaluations of `condition`
        timeout: The total number of seconds waiting (NOTE: not including
            evaluation of `condition`) after which the function will timeout

    Raises:
        TimeoutError: if `timeout` threshold has been reached
    """
    args = [] if cargs is None else cargs
    kwargs = {} if ckwargs is None else ckwargs
    total_wait = 0
    while not condition(*args, **kwargs):  #pylint: disable=star-args
        sleep(wait)
        total_wait += wait
        if total_wait >= timeout:
            raise TimeoutError


#FIXME: OSX only. Look into getpass instead of relying on USER
def get_ff_profile_path():
    """Return a firefox profile path
    NOTE: OSX only
    """
    uname = os.environ['USER']
    prof_dir = '/Users/%s/Library/Application Support/Firefox/Profiles' % uname
    profiles = [s for s in os.listdir(prof_dir) if '.default' in s]

    return os.path.join(prof_dir, profiles[0])


def get_current_progress(dummy_book):
    """Return the current progress as a 2-tuple of locations: (current, total)
    """
    #TODO
    pass


def get_library():
    """Return the list of books in the kindle library
    """
    profile = FirefoxProfile(get_ff_profile_path())
    browser = webdriver.Firefox(firefox_profile=profile)
    browser.get('https://read.amazon.com/')
    _wait_for(browser.find_elements_by_id, cargs=['KindleLibraryIFrame'])
    browser.switch_to.frame('KindleLibraryIFrame')  #pylint: disable=no-member

    _wait_for(browser.find_elements_by_class_name, cargs=['book_container'])
    containers = browser.find_elements_by_class_name('book_container')
    entries = []
    for container in containers:
        title_elem = container.find_element_by_class_name('book_title')
        def _read_nav(elem=title_elem):
            """Navigates to the read page of the current book
            """
            elem.location_once_scrolled_into_view  #pylint: disable=pointless-statement
            elem.click()
        title_elem.location_once_scrolled_into_view  #pylint: disable=pointless-statement
        title = title_elem.text
        author = container.find_element_by_class_name('book_author').text
        entries.append((title, author, _read_nav))
    return entries


def login():
    """Log in to Kindle Cloud Reader
    """
    #TODO
    #email_id = 'ap_email'
    #password_id = 'ap_password'
    #submit_id = 'signInSubmit-input'
    pass


if __name__ == "__main__":
    import sys

    if sys.platform != 'darwin':
        raise RuntimeError('Non-OS X platforms not supported')
    get_library()
