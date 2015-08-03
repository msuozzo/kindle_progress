"""Scrape Kindle Cloud Reader for information regarding the Kindle Library and
current reading progress.
"""
from credential_mgr import JSONCredentialManager

import sys
import os
from getpass import getuser

from selenium.webdriver.firefox.firefox_profile import FirefoxProfile
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver import Firefox, ActionChains
from selenium.webdriver.common.keys import Keys


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
        self._browser = Firefox(firefox_profile=profile)
        self._wait = WebDriverWait(self._browser, 10)
        self._manager = JSONCredentialManager(amz_login_credentials_path)
        self._action = ActionChains(self._browser)

    def _to_reader_home(self):
        """Navigate to the Cloud Reader library page
        """
        self._browser.get(KindleCloudReader.CLOUD_READER_URL)
        if self._browser.title == u'Problem loading page':
            raise ConnectionError
        elif self._browser.title == u'Amazon.com Sign In':
            self._login()

        # Wait for cloud reader to be loaded
        self._switch_to_frame('KindleLibraryIFrame')

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
        # Go to cloud reader home
        self._to_reader_home()

        self._wait.until(lambda br: br.find_element_by_id(book.id_))
        book_div = self._browser.find_element_by_id(book.id_)
        scroll_into_view(book_div)
        book_div.find_element_by_class_name('book_title').click()

        # Switch to Reader frame
        self._browser.switch_to_default_content()
        self._switch_to_frame('KindleReaderIFrame')

        # Sync page to furthest position if further position was found
        sync_btn_id = 'kindleReader_dialog_syncPosition_sync_btn'
        self._wait.until(lambda br: br.find_element_by_id(sync_btn_id))
        sync_btn = self._browser.find_element_by_id(sync_btn_id)
        if sync_btn.is_displayed():
            sync_btn.click()
        self._wait.until_not(lambda br: sync_btn.is_displayed())

        # Ensure header and footer are in view by bringing the search bar into
        # focus (presses CMD+f)
        self._action.key_down(Keys.COMMAND)\
                    .send_keys('f')\
                    .key_up(Keys.COMMAND)\
                    .perform()

        # Extract progress counters
        footer = self._browser.find_element_by_id('kindleReader_footer_message')
        progress_text = footer.text
        dummy_percent, page_text, loc_text = progress_text.split(u' \xb7 ')
        page_tuple = map(int, page_text.lstrip(u'Page ').split(u' of '))
        loc_tuple = map(int, loc_text.lstrip(u'Location ').split(u' of '))

        return page_tuple, loc_tuple

    def close(self):
        """End the browser session
        """
        self._browser.quit()


if __name__ == "__main__":
    if sys.platform != 'darwin':
        raise RuntimeError('Non-OS X platforms not supported')

    CREDENTIAL_PATH = '.credentials.json'
    READER = KindleCloudReader(CREDENTIAL_PATH, get_ff_profile_path())
    FIRST = READER.get_library()
    print READER.get_current_progress(FIRST[0])
    READER.close()
