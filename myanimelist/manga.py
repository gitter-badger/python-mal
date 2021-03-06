#!/usr/bin/python
# -*- coding: utf-8 -*-
import utilities
from base import loadable
import media


class MalformedMangaPageError(media.MalformedMediaPageError):
    """Indicates that a manga-related page on MAL has irreparably broken markup in some way.
    """
    pass


class InvalidMangaError(media.InvalidMediaError):
    """Indicates that the manga requested does not exist on MAL.
    """
    pass


class Manga(media.Media):
    """Primary interface to manga resources on MAL.
    """
    _status_terms = [
        u'Unknown',
        u'Publishing',
        u'Finished',
        u'Not yet published'
    ]
    _consuming_verb = "read"

    def __init__(self, session, manga_id):
        """Creates a new instance of Manga.

        :type session: :class:`myanimelist.session.Session`
        :param session: A valid MAL session
        :type manga_id: int
        :param manga_id: The desired manga's ID on MAL

        :raises: :class:`.InvalidMangaError`

        """
        if not isinstance(manga_id, int) or int(manga_id) < 1:
            raise InvalidMangaError(manga_id)
        super(Manga, self).__init__(session, manga_id)
        self._volumes = None
        self._chapters = None
        self._published = None
        self._authors = None
        self._serialization = None

    def parse_serialization(self, manga_page):
        """Parse the DOM and returns manga serialization.

        :type manga_page: :class:`bs4.BeautifulSoup`
        :param manga_page: MAL manga page's DOM

        :return: publication obj
        """
        result = None
        info_panel_first = manga_page.find(u'div', {'id': 'content'}).find(u'table').find(u'td')
        serialization_tag = info_panel_first.find(text=u'Serialization:').parent.parent
        publication_link = serialization_tag.find('a')
        if publication_link:
            link_parts = publication_link.get('href').split('mid=')
            # of the form /manga.php?mid=1
            # e.g. link_parts
            # [u'/manga/magazine/1/Big_Comic_Original']
            pub_id = int(link_parts[0].split('/')[-2])
            pub_dict = {'name': publication_link.text}
            result = self.session.publication(pub_id).set(pub_dict)
        return result

    def parse_sidebar(self, manga_page, manga_page_original=None):
        """Parses the DOM and returns manga attributes in the sidebar.

        :type manga_page: :class:`bs4.BeautifulSoup`
        :param manga_page: MAL manga page's DOM

        :type manga_page: :class:`bs4.BeautifulSoup`
        :param manga_page: MAL manga page's DOM

        :rtype: dict
        :return: manga attributes

        :raises: :class:`.InvalidMangaError`, :class:`.MalformedMangaPageError`
        """
        # if MAL says the series doesn't exist, raise an InvalidMangaError.
        error_tag = manga_page.find(u'div', {'class': 'badresult'})
        if error_tag:
            raise InvalidMangaError(self.id)

        try:
            title_tag = manga_page.find(u'span', {'itemprop': 'name'})
            if not title_tag:
                # otherwise, raise a MalformedMangaPageError.
                raise MalformedMangaPageError(self.id, manga_page, message="Could not find title")
        except:
            if not self.session.suppress_parse_exceptions:
                raise

        # otherwise, begin parsing.
        manga_info = super(Manga, self).parse_sidebar(manga_page, manga_page_original)

        info_panel_first = manga_page.find(u'div', {'id': 'content'}).find(u'table').find(u'td')

        try:
            volumes_tag = info_panel_first.find(text=u'Volumes:').parent.parent
            utilities.extract_tags(volumes_tag.find_all(u'span', {'class': 'dark_text'}))
            manga_info[u'volumes'] = int(volumes_tag.text.strip()) if volumes_tag.text.strip() != 'Unknown' else None
        except:
            if not self.session.suppress_parse_exceptions:
                raise

        try:
            chapters_tag = info_panel_first.find(text=u'Chapters:').parent.parent
            utilities.extract_tags(chapters_tag.find_all(u'span', {'class': 'dark_text'}))
            manga_info[u'chapters'] = int(chapters_tag.text.strip()) if chapters_tag.text.strip() != 'Unknown' else None
        except:
            if not self.session.suppress_parse_exceptions:
                raise

        try:
            published_tag = info_panel_first.find(text=u'Published:').parent.parent
            utilities.extract_tags(published_tag.find_all(u'span', {'class': 'dark_text'}))
            published_parts = published_tag.text.strip().split(u' to ')
            if len(published_parts) == 1:
                # this published once.
                try:
                    published_date = utilities.parse_profile_date(published_parts[0])
                except ValueError:
                    raise MalformedMangaPageError(self.id, published_parts[0],
                                                  message="Could not parse single publish date")
                manga_info[u'published'] = (published_date,)
            else:
                # two publishing dates.
                try:
                    publish_start = utilities.parse_profile_date(published_parts[0])
                except ValueError:
                    raise MalformedMangaPageError(self.id, published_parts[0],
                                                  message="Could not parse first of two publish dates")
                if published_parts == u'?':
                    # this is still publishing.
                    publish_end = None
                else:
                    try:
                        publish_end = utilities.parse_profile_date(published_parts[1])
                    except ValueError:
                        raise MalformedMangaPageError(self.id, published_parts[1],
                                                      message="Could not parse second of two publish dates")
                manga_info[u'published'] = (publish_start, publish_end)
        except:
            if not self.session.suppress_parse_exceptions:
                raise

        try:
            authors_tag = info_panel_first.find(text=u'Authors:').parent.parent
            utilities.extract_tags(authors_tag.find_all(u'span', {'class': 'dark_text'}))
            manga_info[u'authors'] = {}
            for author_link in authors_tag.find_all('a'):
                link_parts = author_link.get('href').split('/')
                # of the form /people/1867/Naoki_Urasawa
                person = self.session.person(int(link_parts[2])).set({'name': author_link.text})
                role = author_link.nextSibling.replace(' (', '').replace(')', '')
                manga_info[u'authors'][person] = role
        except:
            if not self.session.suppress_parse_exceptions:
                raise

        try:
            manga_info[u'serialization'] = self.parse_serialization(manga_page)
        except:
            if not self.session.suppress_parse_exceptions:
                raise

        return manga_info

    @property
    @loadable(u'load')
    def volumes(self):
        """The number of volumes in this manga.
        """
        return self._volumes

    @property
    @loadable(u'load')
    def chapters(self):
        """The number of chapters in this manga.
        """
        return self._chapters

    @property
    @loadable(u'load')
    def published(self):
        """A tuple(2) containing up to two :class:`datetime.date` objects representing the start and end dates of this manga's publishing.

          Potential configurations:

            None -- Completely-unknown publishing dates.

            (:class:`datetime.date`, None) -- Manga start date is known, end date is unknown.

            (:class:`datetime.date`, :class:`datetime.date`) -- Manga start and end dates are known.
        """
        return self._published

    @property
    @loadable(u'load')
    def authors(self):
        """An author dict with :class:`myanimelist.person.Person` objects of the authors as keys, and strings describing the duties of these authors as values.
        """
        return self._authors

    @property
    @loadable(u'load')
    def serialization(self):
        """The :class:`myanimelist.publication.Publication` involved in the first serialization of this manga.
        """
        return self._serialization
