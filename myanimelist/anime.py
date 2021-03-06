#!/usr/bin/python
# -*- coding: utf-8 -*-
import datetime
import re

import utilities
import media
from base import loadable


class MalformedAnimePageError(media.MalformedMediaPageError):
    """Indicates that an anime-related page on MAL has irreparably broken markup in some way.
    """
    pass


class InvalidAnimeError(media.InvalidMediaError):
    """Indicates that the anime requested does not exist on MAL.
    """
    pass


class Anime(media.Media):
    """Primary interface to anime resources on MAL.
    """
    _status_terms = [
        u'Unknown',
        u'Currently Airing',
        u'Finished Airing',
        u'Not yet aired'
    ]
    _consuming_verb = "watch"

    def __init__(self, session, anime_id):
        """Creates a new instance of Anime.

        :type session: :class:`myanimelist.session.Session`
        :param session: A valid MAL session
        :type anime_id: int
        :param anime_id: The desired anime's ID on MAL

        :raises: :class:`.InvalidAnimeError`

        """
        if not isinstance(anime_id, int) or int(anime_id) < 1:
            raise InvalidAnimeError(anime_id)
        super(Anime, self).__init__(session, anime_id)
        self._episodes = None
        self._aired = None
        self._producers = None
        self._duration = None
        self._rating = None
        self._voice_actors = None
        self._staff = None

    def parse_producers(self, anime_page):
        """Parse the DOM and returns anime producers.

        :type media_page: :class:`bs4.BeautifulSoup`
        :param media_page: MAL media page's DOM

        :rtype: list
        :return: anime produres.
        """
        producers_tag = [x for x in anime_page.find_all('span')
                         if 'Producers' in x.text][0].parent
        result = []
        for producer_link in producers_tag.find_all('a'):
            # e.g. http://myanimelist.net/anime/producer/23
            if '/anime/producer/' not in producer_link.get('href'):
                continue  # skip when not producer link
            producer_id = producer_link.get('href').split('/producer/')[-1].split('/')[0]
            producer_name = producer_link.text
            result.append(self
                          .session
                          .producer(int(producer_id))
                          .set({'name': producer_name}))
        return result

    def parse_sidebar(self, anime_page, anime_page_original=None):
        """Parses the DOM and returns anime attributes in the sidebar.

        :type anime_page: :class:`bs4.BeautifulSoup`
        :param anime_page: MAL anime page's DOM

        :type anime_page: :class:`bs4.BeautifulSoup`
        :param anime_page: MAL anime page's DOM uncleaned

        :rtype: dict
        :return: anime attributes

        :raises: :class:`.InvalidAnimeError`, :class:`.MalformedAnimePageError`
        """
        # if MAL says the series doesn't exist, raise an InvalidAnimeError.
        error_tag = anime_page.find(u'div', {'class': 'badresult'})
        if error_tag:
            raise InvalidAnimeError(self.id)

        title_tag = anime_page.find(u'div', {'id': 'contentWrapper'}).find(u'h1')
        if not title_tag.find(u'div'):
            # otherwise, raise a MalformedAnimePageError.
            try:
                title_tag = anime_page.select('h1.h1 span')[0].text
            except IndexError:
                raise MalformedAnimePageError(self.id, None, message="Could not find title div")

        anime_info = super(Anime, self).parse_sidebar(anime_page, anime_page_original)
        info_panel_first = anime_page.find(u'div', {'id': 'content'}).find(u'table').find(u'td')

        try:
            episode_tag = [x for x in anime_page_original.find_all('span')if 'Episodes:' in x.text][0].parent
            anime_info[u'episodes'] = int(episode_tag.text.split(':')[-1].strip()) if episode_tag.text.strip() != 'Unknown' else 0
        except:
            if not self.session.suppress_parse_exceptions:
                raise

        try:
            aired_tag = [x for x in anime_page_original.find_all('span')if 'Aired:' in x.text][0].parent
            aired_tag_text = aired_tag.text.split(':')[1]
            aired_parts = aired_tag_text.strip().split(u' to ')
            if len(aired_parts) == 1:
                # this aired once.
                try:
                    aired_date = utilities.parse_profile_date(aired_parts[0],
                                                              suppress=self.session.suppress_parse_exceptions)
                except ValueError:
                    raise MalformedAnimePageError(self.id, aired_parts[0], message="Could not parse single air date")
                anime_info[u'aired'] = (aired_date,)
            else:
                # two airing dates.
                try:
                    air_start = utilities.parse_profile_date(aired_parts[0],
                                                             suppress=self.session.suppress_parse_exceptions)
                except ValueError:
                    raise MalformedAnimePageError(self.id, aired_parts[0],
                                                  message="Could not parse first of two air dates")
                try:
                    air_end = utilities.parse_profile_date(aired_parts[1],
                                                           suppress=self.session.suppress_parse_exceptions)
                except ValueError:
                    raise MalformedAnimePageError(self.id, aired_parts[1],
                                                  message="Could not parse second of two air dates")
                anime_info[u'aired'] = (air_start, air_end)
        except:
            if not self.session.suppress_parse_exceptions:
                raise
        try:
            anime_info[u'producers'] = self.parse_producers(anime_page)
        except:
            if not self.session.suppress_parse_exceptions:
                raise

        try:
            duration_tag = [x for x in anime_page_original.find_all('span')if 'Duration:' in x.text][0].parent
            anime_info[u'duration'] = duration_tag.text.split(':')[1].strip()
            duration_parts = [part.strip() for part in anime_info[u'duration'].split(u'.')]
            duration_mins = 0
            for part in duration_parts:
                part_match = re.match(u'(?P<num>[0-9]+)', part)
                if not part_match:
                    continue
                part_volume = int(part_match.group(u'num'))
                if part.endswith(u'hr'):
                    duration_mins += part_volume * 60
                elif part.endswith(u'min'):
                    duration_mins += part_volume
            anime_info[u'duration'] = datetime.timedelta(minutes=duration_mins)
        except:
            if not self.session.suppress_parse_exceptions:
                raise

        try:
            rating_tag = [x for x in anime_page_original.find_all('span')if 'Rating:' in x.text][0].parent
            utilities.extract_tags(rating_tag.find_all(u'span', {'class': 'dark_text'}))
            anime_info[u'rating'] = rating_tag.text.strip()
        except:
            if not self.session.suppress_parse_exceptions:
                raise

        return anime_info

    def parse_staff(self, character_page):
        """Parse the DOM and returns anime staff.

        :type character_page: :class:`bs4.BeautifulSoup`
        :param character_page: MAL anime character page's DOM

        :rtype: dict
        :return: anime character attributes

        :raises: :class:`.InvalidAnimeError`, :class:`.MalformedAnimePageError`
        """
        # this contain list with 'staff' as text
        # staff_title = filter(lambda x: 'Staff' in x.text, character_page.find_all(u'h2'))
        staff_title = filter(lambda x: 'Staff' in x.text, character_page.find_all(u'h2'))
        result = {}
        if staff_title:
            staff_title = staff_title[0]
            staff_table = staff_title.nextSibling
            if staff_table.name != 'table':  # only change if staff_table dont have table tag
                staff_table = staff_title.nextSibling
            for row in staff_table.find_all(u'tr'):
                # staff info in second col.
                info = row.find_all(u'td')[1]
                staff_link = info.find(u'a')
                staff_name = ' '.join(reversed(staff_link.text.split(u', ')))
                link_parts = staff_link.get(u'href').split(u'/')
                # of the form /people/1870/Miyazaki_Hayao
                person = self.session.person(int(link_parts[2])).set({'name': staff_name})
                # staff role(s).
                result[person] = set(info.find(u'small').text.split(u', '))
        return result

    def parse_characters(self, character_page, character_page_original=None):
        """Parses the DOM and returns anime character attributes in the sidebar.

        :type character_page: :class:`bs4.BeautifulSoup`
        :param character_page: MAL anime character page's DOM

        :rtype: dict
        :return: anime character attributes

        :raises: :class:`.InvalidAnimeError`, :class:`.MalformedAnimePageError`

        """
        anime_info = self.parse_sidebar(character_page, character_page_original)

        try:
            # character_title = filter(lambda x: 'Characters & Voice Actors' in x.text, character_page.find_all(u'h2'))
            character_title = filter(lambda x: 'Characters & Voice Actors' in x.text, character_page_original.find_all(u'h2'))
            anime_info[u'characters'] = {}
            anime_info[u'voice_actors'] = {}
            if character_title:
                character_title = character_title[0]
                curr_elt = character_title.nextSibling
                while True:
                    if curr_elt.name != u'table':
                        break
                    curr_row = curr_elt.find(u'tr')
                    # character in second col, VAs in third.
                    (_, character_col, va_col) = curr_row.find_all(u'td', recursive=False)

                    character_link = character_col.find(u'a')
                    character_name = ' '.join(reversed(character_link.text.split(u', ')))
                    link_parts = character_link.get(u'href').split(u'/')
                    # of the form /character/7373/Holo
                    character = self.session.character(int(link_parts[2])).set({'name': character_name})
                    role = character_col.find(u'small').text
                    character_entry = {'role': role, 'voice_actors': {}}

                    va_table = va_col.find(u'table')
                    if va_table:
                        for row in va_table.find_all(u'tr'):
                            va_info_cols = row.find_all(u'td')
                            if not va_info_cols:
                                # don't ask me why MAL has an extra blank table row i don't know!!!
                                continue
                            va_info_col = va_info_cols[0]
                            va_link = va_info_col.find(u'a')
                            if va_link:
                                va_name = ' '.join(reversed(va_link.text.split(u', ')))
                                link_parts = va_link.get(u'href').split(u'/')
                                # of the form /people/70/Ami_Koshimizu
                                person = self.session.person(int(link_parts[2])).set({'name': va_name})
                                language = va_info_col.find(u'small').text
                                anime_info[u'voice_actors'][person] = {'role': role, 'character': character,
                                                                       'language': language}
                                character_entry[u'voice_actors'][person] = language
                    anime_info[u'characters'][character] = character_entry
                    curr_elt = curr_elt.nextSibling
        except:
            if not self.session.suppress_parse_exceptions:
                raise

        try:
            anime_info[u'staff'] = self.parse_staff(character_page_original)
        except:
            if not self.session.suppress_parse_exceptions:
                raise

        return anime_info

    @property
    @loadable(u'load')
    def episodes(self):
        """The number of episodes in this anime. If undetermined, is None, otherwise > 0.
        """
        return self._episodes

    @property
    @loadable(u'load')
    def aired(self):
        """A tuple(2) containing up to two :class:`datetime.date` objects representing the start and end dates of this anime's airing.

          Potential configurations:

            None -- Completely-unknown airing dates.

            (:class:`datetime.date`, None) -- Anime start date is known, end date is unknown.

            (:class:`datetime.date`, :class:`datetime.date`) -- Anime start and end dates are known.

        """
        return self._aired

    @property
    @loadable(u'load')
    def producers(self):
        """A list of :class:`myanimelist.producer.Producer` objects involved in this anime.
        """
        return self._producers

    @property
    @loadable(u'load')
    def duration(self):
        """The duration of an episode of this anime as a :class:`datetime.timedelta`.
        """
        return self._duration

    @property
    @loadable(u'load')
    def rating(self):
        """The MPAA rating given to this anime.
        """
        return self._rating

    @property
    @loadable(u'load_characters')
    def voice_actors(self):
        """A voice actors dict with :class:`myanimelist.person.Person` objects of the voice actors as keys, and dicts containing info about the roles played, e.g. {'role': 'Main', 'character': myanimelist.character.Character(1)} as values.
        """
        return self._voice_actors

    @property
    @loadable(u'load_characters')
    def staff(self):
        """A staff dict with :class:`myanimelist.person.Person` objects of the staff members as keys, and lists containing the various duties performed by staff members as values.
        """
        return self._staff
