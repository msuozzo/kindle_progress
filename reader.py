"""Scrape Kindle Cloud Reader for information regarding the Kindle Library and
current reading progress.
"""
from credential_mgr import JSONCredentialManager

import sys
import os
from getpass import getuser

from selenium import webdriver
from selenium.webdriver.firefox.firefox_profile import FirefoxProfile
from selenium.webdriver.support.wait import WebDriverWait


class ConnectionError(Exception):
    """Indicate a problem with the internet connection
    """
    pass


def get_ff_profile_path():
    """Return a firefox profile path
    NOTE: OSX only
    """
    uname = getuser()
    if sys.platform == 'darwin':
        prof_dir = '/Users/%s/Library/Application Support/Firefox/Profiles' % uname
        profiles = [s for s in os.listdir(prof_dir) if '.default' in s]

        return os.path.join(prof_dir, profiles[0])
    else:
        #TODO
        raise NotImplementedError


class KindleCloudReader(object):
    """An interface for extracting data from Kindle Cloud Reader

    Args:
        profile_path: The path to the Firefox profile directory to use for
            browsing. This enables existing cookies and add-ons to be used in
            the automation.
    """
    CLOUD_READER_URL = u'https://read.amazon.com'
    SIGNIN_URL = u'https://www.amazon.com/ap/signin'

    def __init__(self, credential_path, profile_path=None):
        if profile_path is not None:
            profile = FirefoxProfile(profile_path)
        self._browser = webdriver.Firefox(firefox_profile=profile)
        self._wait = WebDriverWait(self._browser, 10)
        self._manager = JSONCredentialManager(credential_path)

    def _to_reader_home(self):
        """Navigate to the Cloud Reader library page
        """
        self._browser.get(KindleCloudReader.CLOUD_READER_URL)
        if self._browser.title == u'Problem loading page':
            raise ConnectionError
        elif self._browser.title == u'Amazon.com Sign In':
            self._login()

        # Wait for cloud reader to be loaded
        self._wait.until(lambda br: br.find_element_by_id('KindleLibraryIFrame'))
        self._browser.switch_to.frame('KindleLibraryIFrame')  #pylint: disable=no-member

        # Sync Cloud Reader
        self._sync()

    def _sync(self):
        """Sync the cloud reader
        """
        if not self._browser.current_url.startswith(KindleCloudReader.CLOUD_READER_URL):
            raise RuntimeError('current url "%s" is not a cloud reader url ("%s")' %
                    (self._browser.current_url, KindleCloudReader.CLOUD_READER_URL))

        # Wait for sync button to exist and then click it
        get_sync_btn = lambda br: br.find_element_by_id('kindleLibrary_button_sync')
        self._wait.until(get_sync_btn)
        get_sync_btn(self._browser).click()

        # Wait for sync to complete
        has_spinner = lambda br: br.find_element_by_id('loading_spinner')
        self._wait.until(has_spinner)
        self._wait.until_not(has_spinner)

    def _login(self):
        """Log in to Kindle Cloud Reader
        """
        if not self._browser.current_url.startswith(KindleCloudReader.SIGNIN_URL):
            raise RuntimeError('current url "%s" is not a signin url ("%s")' %
                    (self._browser.current_url, KindleCloudReader.SIGNIN_URL))
        uname, pword = self._manager.get_creds()
        self._browser.find_element_by_id('ap_email').send_keys(uname)
        self._browser.find_element_by_id('ap_password').send_keys(pword)
        self._browser.find_element_by_id('signInSubmit-input').click()

    def get_library(self):
        """Return metadata on the books in the kindle library
        """
        # Go to cloud reader home
        self._to_reader_home()

        # Ensure iframe content has loaded
        # Then extract metadata from each book
        get_containers = lambda br: br.find_elements_by_class_name('book_container')
        self._wait.until(get_containers)
        containers = get_containers(self._browser)
        entries = []
        for container in containers:
            title_elem = container.find_element_by_class_name('book_title')
            def _read_nav(elem=title_elem):
                """Navigates to the read page of the book represented by
                `container`
                """
                elem.location_once_scrolled_into_view  #pylint: disable=pointless-statement
                elem.click()
            title_elem.location_once_scrolled_into_view  #pylint: disable=pointless-statement
            title = title_elem.text
            author = container.find_element_by_class_name('book_author').text
            entries.append((title, author, _read_nav))
        return entries

    def get_current_progress(self):
        """Return the current progress as a 2-tuple of locations: (current, total)
        """
        #TODO
        pass


if __name__ == "__main__":
    if sys.platform != 'darwin':
        raise RuntimeError('Non-OS X platforms not supported')

    CREDENTIAL_PATH = '.credentials.json'
    READER = KindleCloudReader(CREDENTIAL_PATH, get_ff_profile_path())
    print READER.get_library()
