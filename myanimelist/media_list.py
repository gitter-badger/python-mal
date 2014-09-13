#!/usr/bin/python
# -*- coding: utf-8 -*-

import abc
import bs4
import decimal
import datetime
import urllib

import utilities
from base import Base, Error, loadable

class MalformedMediaListPageError(Error):
  def __init__(self, username, html, message=None):
    super(MalformedMediaListPageError, self).__init__(message=message)
    if isinstance(username, unicode):
      self.username = username
    else:
      self.username = str(username).decode(u'utf-8')
    if isinstance(html, unicode):
      self.html = html
    else:
      self.html = str(html).decode(u'utf-8')
  def __str__(self):
    return "\n".join([
      super(MalformedMediaListPageError, self).__str__(),
      "Username: " + unicode(self.username),
      "HTML: " + self.html
    ]).encode(u'utf-8')

class InvalidMediaListError(Error):
  def __init__(self, username, message=None):
    super(InvalidMediaListError, self).__init__(message=message)
    if isinstance(username, unicode):
      self.username = username
    else:
      self.username = str(username).decode(u'utf-8')
  def __str__(self):
    return "\n".join([
      super(InvalidMediaListError, self).__str__(),
      "Username: " + unicode(self.username)
    ])

class MediaList(Base):
  __metaclass__ = abc.ABCMeta

  __id_attribute = "username"
  def __init__(self, session, user_name):
    super(MediaList, self).__init__(session)
    self.username = user_name
    if not isinstance(self.username, unicode) or len(self.username) < 4:
      raise InvalidMediaListError(self.username)
    self._list = None
    self._stats = None

  # subclasses must define a list type, ala "anime" or "manga"
  @abc.abstractproperty
  def type(self):
    pass

  # a list verb ala "watch", "read", etc
  @abc.abstractproperty
  def verb(self):
    pass

  # a list with status ints as indices and status texts as values.
  @property
  def user_status_terms(self):
    return [
      u'Unknown',
      self.verb.capitalize() + u'ing',
      u'Completed',
      u'On-Hold',
      u'Dropped',
      u'Unknown',
      u'Plan to ' + self.verb.capitalize()
    ]

  def parse_entry_media_attributes(self, soup):
    """
      Given:
        soup: a bs4 element containing a row from the current media list
      Return a dict of attributes of the media the row is about.
    """
    try:
      start = utilities.parse_profile_date(soup.find('series_start').text)
    except ValueError:
      start = None
    try:
      end = utilities.parse_profile_date(soup.find('series_end').text)
    except ValueError:
      end = None

    # look up the given media type's status terms.
    status_terms = getattr(self.session, self.type)(1).status_terms
    return {
      'id': int(soup.find('series_' + self.type + 'db_id').text),
      'title': soup.find('series_title').text,
      'status': status_terms[int(soup.find('series_status').text)],
      'aired': (start,end),
      'picture': soup.find('series_image').text
    }

  def parse_entry(self, soup):
    """
      Given:
        soup: a bs4 element containing a row from the current media list
      Return a tuple:
        (media object, dict of this row's parseable attributes)
    """
    # parse the media object first.
    media_attrs = self.parse_entry_media_attributes(soup)
    media_id = media_attrs[u'id']
    del media_attrs[u'id']
    media = getattr(self.session, self.type)(media_id).set(media_attrs)

    entry_info = {}
    try:
      entry_info[u'started'] = utilities.parse_profile_date(soup.find(u'my_start_date').text)
    except ValueError:
      entry_info[u'started'] = None
    try:
      entry_info[u'finished'] = utilities.parse_profile_date(soup.find(u'my_finish_date').text)
    except ValueError:
      entry_info[u'finished'] = None

    entry_info[u'status'] = self.user_status_terms[int(soup.find(u'my_status').text)]

    entry_info[u'score'] = int(soup.find(u'my_score').text)
    # if user hasn't set a score, set it to None to indicate as such.
    if entry_info[u'score'] == 0:
      entry_info[u'score'] = None

    entry_info[u'last_updated'] = datetime.datetime.fromtimestamp(int(soup.find(u'my_last_updated').text))
    return media,entry_info

  def parse_stats(self, soup):
    """
      Given:
        soup: a bs4 element containing the current media list's stats
      Return a dict of this media list's stats.
    """
    stats = {}
    for row in soup.children:
      key = row.name.replace(u'user_', u'')
      if key == u'id':
        stats[key] = int(row.text)
      elif key == u'name':
        stats[key] = row.text
      elif key == self.verb + u'ing':
        stats[key] = int(row.text)
      elif key == u'completed':
        stats[key] = int(row.text)
      elif key == u'onhold':
        stats['on_hold'] = int(row.text)
      elif key == u'dropped':
        stats[key] = int(row.text)
      elif key == u'planto' + self.verb:
        stats[u'plan_to_' + self.verb] = int(row.text)
      # for some reason, MAL doesn't substitute 'read' in for manga for the verb here
      elif key == u'days_spent_watching':
        stats[u'days_spent'] = decimal.Decimal(row.text)
    return stats

  def parse(self, xml):
    list_info = {}
    list_page = bs4.BeautifulSoup(xml)

    primary_elt = list_page.find('myanimelist')
    if not primary_elt:
      raise MalformedMediaListPageError(self.username, xml, message="Could not find root XML element in " + self.type + " list")

    bad_username_elt = list_page.find('error')
    if bad_username_elt:
      raise InvalidMediaListError(self.username, message=u"Invalid username when fetching " + self.type + " list")

    stats_elt = list_page.find('myinfo')
    if not stats_elt:
      raise MalformedMediaListPageError(self.username, html, message="Could not find stats element in " + self.type + " list")

    list_info[u'stats'] = self.parse_stats(stats_elt)

    list_info[u'list'] = {}
    for row in list_page.find_all(self.type):
      (media, entry) = self.parse_entry(row)
      list_info[u'list'][media] = entry
    return list_info
  def load(self):

    media_list = self.session.session.get(u'http://myanimelist.net/malappinfo.php?' + urllib.urlencode({'u': self.username, 'status': 'all', 'type': self.type})).text
    self.set(self.parse(media_list))
    return self

  @property
  @loadable(u'load')
  def list(self):
    return self._list

  @property
  @loadable(u'load')
  def stats(self):
    return self._stats

  def section(self, status):
    return {k: self.list[k] for k in self.list if self.list[k][u'status'] == status}