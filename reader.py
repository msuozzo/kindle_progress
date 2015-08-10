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
from selenium.common.exceptions import NoSuchElementException,\
                                        ElementNotVisibleException


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


class ReadingProgress(object):
    """A representation of far the reader is through a book

    Args:
        book: The book for which the progress is associated
        loc_pair: A 2-tuple (current_location, end_location)
        page_pair (optional): A 2-tuple (current_page, end_page)


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
        elements such as images or charts may require many more bytes and,
        thus, locations to represent.

        In spite of this extra noise, locations provide a more granular
        measurement of reading progress than page numbers.

        Additionally, _locations are always available_ while page numbers are
        frequently absent from Kindle metadata.
    """
    def __init__(self, book, loc_pair, page_pair=None):
        self.book = book
        self.current_loc, self.end_loc = loc_pair
        if page_pair:
            self.current_page, self.end_page = page_pair  #pylint: disable=unpacking-non-sequence
        else:
            self.current_page, self.end_page = (None, None)

    def has_page_progress(self):
        """Return whether page numbering is available in this object
        """
        return self.current_page is not None

    def __repr__(self):
        if self.has_page_progress():
            return 'Progress(Loc=(%d of %d), Page=(%d of %d))' % \
                    (self.current_loc, self.end_loc,
                            self.current_page, self.end_page)
        else:
            return 'Progress(Loc=(%d of %d))' % \
                    (self.current_loc, self.end_loc)


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

        When a Reader is launched, KCR will check to see whether a further
        reading position exists on any other Kindle devices/apps.
        If one is found, a 'load-in sync dialog' will be presented to user
        with the option to sync with this further position.

        Unfortunately, the book pane will usually load prior to a load-in sync
        dialog prompt (if there is one). I couldn't find a suitable event to
        wait for so one of the few alternatives would have been sleeping for a
        second or two. This was uncomfortably inexact.

        To make the process more deterministic, we immediately trigger a
        manual sync when the book pane loads. This way, regardless of whether
        or not a load-in sync dialog appears, we can process the sync.

        Basically:
            If the load-in sync dialog has loaded, we click through it.
            Else, we trigger the sync and click through it just the same.
        """
        self._wait.until(lambda br:\
                br.find_element_by_id('kindleReader_book_container'))

        self._reveal_reader_header_footer()

        sync_pane_class = 'ui-dialog'
        has_dialog = lambda br:\
            bool(br.find_elements_by_class_name(sync_pane_class))
        if not has_dialog(self._browser):
            self._browser.find_element_by_id('kindleReader_button_sync').click()
            self._wait.until(has_dialog)

        # Check whether sync is required
        sync_pane = self._browser.find_element_by_class_name(sync_pane_class)
        buttons = sync_pane.find_elements_by_tag_name('button')
        load_in_sync = len(buttons) == 3  # 3 buttons in load-in sync dialog
        if load_in_sync:
            dialogue_text = self._browser\
                    .find_element_by_id('kindleReader_dialog_syncPosition_label').text
            match = re.search(\
                        ur'currently at .+ (\d+)\. .+ furthest .+ is (\d+) from',
                        dialogue_text)
            current, furthest = map(int, match.group(1, 2))
            position_changed = current != furthest
        requires_sync = load_in_sync and position_changed

        # Record pre-sync progress
        get_progress_text = lambda br: br\
                    .find_element_by_id('kindleReader_footer_message').text
        progress_text = get_progress_text(self._browser)

        # If no sync available, buttons[0] will be the cancel button
        # If there is a sync, buttons[0] will be 'Sync to Furthest Position'
        self._wait.until_not(lambda br: buttons[0].click() or buttons[0].is_displayed())

        # Wait for position to change
        if requires_sync:
            self._wait.until(lambda br: progress_text != get_progress_text(br))

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

    def _reveal_reader_header_footer(self):
        """Bring the header and footer into view by transferring focus to the
        search bar.
        """
        def _set_active_and_check(browser):
            """Set the searchbox as active and return whether the footer is
            visible.
            """
            browser.execute_script('this.KindleReaderSearchBox.setActive(!0);')
            footer = browser.find_element_by_id('kindleReader_footer_message')
            return bool(footer.text)
        self._wait.until(_set_active_and_check)

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
        """Return a `ReadingProgress` object containing the available progress

        data.
        NOTE: A summary of the two progress formats can be found in the


        Args:
            read_cb: The callback to open the reader for the target book
        """
        # Go to the reader page for `book`
        self._to_book_reader(book)

        # Ensure footer is visible
        self._reveal_reader_header_footer()

        # Extract progress counters from the footer
        progress_text = self._browser\
                .find_element_by_id('kindleReader_footer_message').text
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

        return ReadingProgress(book, loc_tuple, page_tuple)

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
        PROG = READER.get_current_progress(BOOK)
        print PROG, BOOK.title
    READER.close()
