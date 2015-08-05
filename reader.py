"""Scrape Kindle Cloud Reader for information regarding the Kindle Library and
current reading progress.
"""
from credential_mgr import JSONCredentialManager

import sys
import os
from getpass import getuser
import re

from selenium.webdriver.firefox.firefox_profile import FirefoxProfile
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver import Firefox, ActionChains
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import NoSuchElementException,\
                                        ElementNotVisibleException,\
                                        WebDriverException


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


def scroll_into_view(element):
    """Scroll a Selenium WebElement into view.

    Why is the syntax so un-Pythonic? The world may never know.
    """
    element.location_once_scrolled_into_view  #pylint: disable=pointless-statement


class KindleBook(object):
    """A book in a Kindle Library
    """
    def __init__(self, id_, title, author):
        self.id_ = unicode(id_)
        self.title = unicode(title)
        self.author = unicode(author) if author else None

    def __str__(self):
        if self.author is None:
            ret = u'"{}"'.format(self.title)
        else:
            ret = u'"{}" by {}'.format(self.title, self.author)
        return ret.encode('utf8')

    def __repr__(self):
        return u'Book(id={}, title="{}", author="{}")'\
                .format(self.id_, self.title, self.author)\
                .encode('utf8')


class KindleCloudReader(object):
    """An interface for extracting data from Kindle Cloud Reader

    Args:
        amz_login_credentials_path: The system path to a JSON file containing
            two keys:
                id: The email address associated with the Kindle account
                secret: The password associated with the Kindle account
        profile_path: The path to the Firefox profile directory to use for
            browsing. This enables existing cookies and add-ons to be used in
            the automation.
    """
    CLOUD_READER_URL = u'https://read.amazon.com'
    SIGNIN_URL = u'https://www.amazon.com/ap/signin'

    def __init__(self, amz_login_credentials_path, profile_path=None):
        if profile_path is not None:
            profile = FirefoxProfile(profile_path)
        else:
            profile = None
        self._browser = Firefox(firefox_profile=profile)
        self._wait = WebDriverWait(self._browser,
                timeout=10,
                ignored_exceptions=(NoSuchElementException,
                    ElementNotVisibleException))
        self._manager = JSONCredentialManager(amz_login_credentials_path)
        self._action = ActionChains(self._browser)

    def _to_reader_home(self):
        """Navigate to the Cloud Reader library page
        """
        # NOTE: Prevents QueryInterface error caused by getting a URL
        # while switched to an iframe
        self._browser.switch_to_default_content()
        self._browser.get(KindleCloudReader.CLOUD_READER_URL)

        if self._browser.title == u'Problem loading page':
            raise ConnectionError

        # Wait for either the login page or the reader to load
        login_or_reader_loaded = \
                lambda br: br.find_elements_by_id('amzn_kcr') or \
                    br.find_elements_by_id('KindleLibraryIFrame')
        self._wait.until(login_or_reader_loaded)

        # If the login page was loaded, log in
        if self._browser.title == u'Amazon.com Sign In':
            self._login()

        assert self._browser.title == u'Kindle Cloud Reader'

        self._switch_to_frame('KindleLibraryIFrame')
        self._sync_library()

    def _to_book_reader(self, book):
        """Navigate to the Cloud Reader page for `book`
        """
        # Go to cloud reader home
        self._to_reader_home()

        self._wait.until(lambda br: br.find_element_by_id(book.id_))

        def _find_and_click(browser):
            """Finds the book, scrolls it into view, and clicks on it
            """
            title_div = browser.find_element_by_id(book.id_)\
                                    .find_element_by_class_name('book_title')
            scroll_into_view(title_div)
            title_div.click()
            return True
        self._wait.until(_find_and_click)

        # Switch to Reader frame
        self._browser.switch_to_default_content()
        self._switch_to_frame('KindleReaderIFrame')
        self._sync_reader()

    def _sync_reader(self):
        """Sync the reader position to the furthest available
        """
        # Sync page to furthest position if further position was found
        # NOTE: book_container indicates the reader loaded without sync alert
        sync_btn_id = 'kindleReader_dialog_syncPosition_sync_btn'
        sync_or_read = lambda br: br.find_elements_by_id(sync_btn_id) or \
                br.find_elements_by_id('kindleReader_book_container')
        self._wait.until(sync_or_read)

        # Check whether sync is required
        sync_btn_elems = self._browser.find_elements_by_id(sync_btn_id)
        if sync_btn_elems:
            sync_btn = sync_btn_elems[0]
            if sync_btn.is_displayed():
                sync_btn.click()
            self._wait.until_not(lambda br: sync_btn.is_displayed())

    def _sync_library(self):
        """Sync the Kindle Cloud Library
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

    def _switch_to_frame(self, frame_id):
        """Switch the browser focus to the iframe with id `frame_id`

        Args:
            frame_id: The id string attached to the frame
        """
        self._wait.until(lambda br: br.find_element_by_id(frame_id))
        self._browser.switch_to.frame(frame_id)  #pylint: disable=no-member

    def get_library(self):
        """Return metadata on the books in the kindle library

        Returns:
            A list of `KindleBook` objects
        """
        # Go to cloud reader home
        self._to_reader_home()

        # Ensure iframe content has loaded
        # Then extract metadata from each book
        get_containers = lambda br: br.find_elements_by_class_name('book_container')
        self._wait.until(get_containers)
        containers = get_containers(self._browser)
        books = []
        for container in containers:
            id_ = container.get_attribute('id')
            title_elem = container.find_element_by_class_name('book_title')
            scroll_into_view(title_elem)
            title = title_elem.text
            author = container.find_element_by_class_name('book_author').text
            books.append(KindleBook(id_, title, author))

        return books

    def get_current_progress(self, book):
        """Return the current progress as 2 2-tuples:
            ((curr_page, total_pages), (curr_location, total_locations))
        NOTE: If either the page numbers or location information are not
            available, None will be returned in place of the corresponding
            tuple.
                e.g. (None, (curr_loc, total_loc))

        Notes on Progress Formats:

        Page Numbers:
            The page number measurement directly corresponds to the page
            numbers in a physical copy of the book. In other words, the page
            number N reported by the Kindle should correspond to that same
            page N in a hard copy.

        Locations:
            According to (http://www.amazon.com/forum/kindle/Tx2S4K44LSXEWRI)
            and various other online discussions, a single 'location' is
            equivalent to 128 bytes of code (in the azw3 file format).

            For normal books, this ranges from 3-4 locations per page with a
            large font to ~16 locs/pg with a small font. However, book
            elements such as images or charts may require a many more bytes
            and, thus, locations to represent.

            In spite of this extra noise, locations provide a more granular
            measurement of reading progress than page numbers.

        Args:
            read_cb: The callback to open the reader for the target book
        """
        # Go to the reader page for `book`
        self._to_book_reader(book)

        # Ensure header and footer are in view by bringing the search bar into
        # focus
        # NOTE: Wait required here because of intermittent errors raised by
        # nsIDOMWindowUtils.sendKeyEvent
        wait = WebDriverWait(self._browser,
                        timeout=10,
                        ignored_exceptions=(WebDriverException,))
        find_action = self._action.key_down(Keys.COMMAND)\
                        .send_keys('f')\
                        .key_up(Keys.COMMAND)
        wait.until_not(lambda br: find_action.perform())

        # Extract progress counters
        footer_id = 'kindleReader_footer_message'
        self._wait.until(lambda br: br.find_element_by_id(footer_id).text)
        progress_text = self._browser.find_element_by_id(footer_id).text
        def _extract_pairs(pair_regex, text):
            """If `pair_regex` matches `text`, return the pair of integers matched
            Else if not match is found, return None
            """
            match = re.search(pair_regex, text)
            return map(int, match.group(1, 2)) if match else None
        page_tuple = _extract_pairs(ur'Page (\d+) of (\d+)', progress_text)
        loc_tuple = _extract_pairs(ur'Location (\d+) of (\d+)', progress_text)

        # Return to the library page
        self._browser.find_element_by_id('kindleReader_button_close').click()

        return page_tuple, loc_tuple

    def close(self):
        """End the browser session
        """
        self._browser.quit()


if __name__ == "__main__":
    if sys.platform != 'darwin':
        raise RuntimeError('Non-OS X platforms not supported')

    CREDENTIAL_PATH = '.credentials.json'
    READER = KindleCloudReader(CREDENTIAL_PATH)
    BOOKS = READER.get_library()
    for BOOK in BOOKS:
        PGS, LOCS = READER.get_current_progress(BOOK)
        print PGS, BOOK.title
    READER.close()
