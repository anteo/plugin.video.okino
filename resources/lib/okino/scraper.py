# -*- coding: utf-8 -*-

from __future__ import unicode_literals
from collections import namedtuple
from base64 import decodestring
from urlparse import urlparse, parse_qs
from okino.enumerations import *
from okino.common import LocalizedError, str_to_date
from util.phpserialize import loads, phpobject
from util.timer import Timer
from util.htmldocument import HtmlDocument
from util.httpclient import HttpClient
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError

import re
import urllib
import urllib2
import logging
import socket


Media = namedtuple('Media', ['id', 'title', 'original_title', 'date', 'flag', 'quality', 'genres',
                             'languages', 'countries', 'start_year', 'end_year', 'continuing', 'rating', 'user_rating'])

Details = namedtuple('Details', ['title', 'original_title', 'countries', 'start_year', 'world_release',
                                 'russian_release', 'duration', 'studios', 'mpaa_rating', 'keywords', 'genres', 'plot',
                                 'directors', 'writers', 'producers', 'actors', 'ratings', 'votes', 'poster',
                                 'media_id', 'section', 'continuing', 'end_year'])

Folder = namedtuple('Folder', ['id', 'media_id', 'title', 'flag', 'link', 'quality', 'languages', 'fmt',
                               'embedded_subtitles', 'external_subtitles', 'duration', 'size', 'files'])

File = namedtuple('File', ['id', 'media_id', 'folder_id', 'title', 'flag', 'link', 'file_format', 'subtitles',
                           'duration', 'size', 'video_streams', 'audio_streams'])

Quality = namedtuple('Quality', ['format', 'video', 'audio'])

VideoStreamInfo = namedtuple('VideoStreamInfo', ['width', 'height', 'codec', 'kbps'])

AudioStreamInfo = namedtuple('AudioStreamInfo', ['language', 'codec', 'kbps', 'channels'])


class ScraperError(LocalizedError):
    pass


class AbstractScraper:
    def __init__(self, log=None, http_params=None, http_client=None, max_workers=10, timeout=30,
                 details_cache=None, folders_cache=None, search_cache=None):
        self.log = log or logging.getLogger(__name__)
        self.http_client = http_client or HttpClient()
        self.http_params = http_params or {}
        self.timeout = timeout
        self.details_cache = details_cache if details_cache is not None else {}
        self.folders_cache = folders_cache if folders_cache is not None else {}
        self.search_cache = search_cache if search_cache is not None else {}
        self.max_workers = max_workers
        self.http_response = None
        self.has_more = False

    def fetch_page(self, url):
        try:
            self.http_response = self.http_client.fetch(url, timeout=self.timeout, **self.http_params)
            return self.http_response.body
        except urllib2.URLError, e:
            if isinstance(e.reason, socket.timeout):
                raise ScraperError(32000, "Timeout while fetching URL: %s" % url, cause=e)
            else:
                raise ScraperError(32001, "Can't fetch URL: %s" % url, cause=e)

    def search(self, search_filter=None, skip=None):
        raise NotImplementedError()

    def get_details(self, media_id):
        raise NotImplementedError()

    def get_folders(self, media_id):
        raise NotImplementedError()

    def get_files(self, media_id, folder_id):
        raise NotImplementedError()

    def search_cached(self, search_filter=None, skip=None):
        key = hash((search_filter, skip))
        if key not in self.search_cache:
            self.search_cache[key] = (self.search(search_filter, skip), self.has_more)
        res, self.has_more = self.search_cache[key]
        return res

    def get_details_bulk(self, media_ids):
        """
        :rtype : dict[int, Details]
        """
        cached_details = self.details_cache.keys()
        not_cached_ids = [_id for _id in media_ids if _id not in cached_details]
        results = dict((_id, self.details_cache[_id]) for _id in media_ids if _id in cached_details)
        with Timer(logger=self.log, name="Bulk fetching"):
            try:
                with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                    futures = [executor.submit(self.get_details, _id) for _id in not_cached_ids]
                    for future in as_completed(futures, self.timeout):
                        result = future.result()
                        _id = result.media_id
                        self.details_cache[_id] = results[_id] = result
            except TimeoutError as e:
                raise ScraperError(32000, "Timeout while fetching URLs", cause=e)
        return results

    def get_details_cached(self, media_id):
        """
        :rtype : Details
        """
        return self.get_details_bulk([media_id])[media_id]

    def get_folders_bulk(self, media_ids):
        """
        :rtype : dict[int, list[Folder]]
        """
        cached_folders = self.folders_cache.keys()
        not_cached_ids = [_id for _id in media_ids if _id not in cached_folders]
        results = dict((_id, self.folders_cache[_id]) for _id in media_ids if _id in cached_folders)
        with Timer(logger=self.log, name="Bulk fetching"):
            try:
                with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                    folder_futures = dict((executor.submit(self.get_folders, _id), _id) for _id in not_cached_ids)
                    files_futures = {}
                    for future in as_completed(folder_futures, self.timeout):
                        result = future.result()
                        _id = folder_futures[future]
                        results[_id] = result
                        if len(result) > 1:
                            files_futures.update(dict((executor.submit(self.get_files, _id, f.id), (_id, i))
                                                      for i, f in enumerate(result)))
                        else:
                            self.folders_cache[_id] = result

                    for future in as_completed(files_futures, self.timeout):
                        result = future.result()
                        _id, i = files_futures[future]
                        results[_id][i].files.extend(result)
                        self.folders_cache[_id] = results[_id]
            except TimeoutError as e:
                raise ScraperError(32000, "Timeout while fetching URLs", cause=e)
        return results

    def get_folders_cached(self, media_id):
        """
        :rtype : list[Folder]
        """
        return self.get_folders_bulk([media_id])[media_id]

    def get_folder_cached(self, media_id, folder_id):
        folders = self.get_folders_cached(media_id)
        return next((folder for folder in folders if folder.id == folder_id), None)

    def get_files_cached(self, media_id, folder_id):
        folder = self.get_folder_cached(media_id, folder_id)
        return folder and folder.files or []


class OkinoScraper(AbstractScraper):
    base_url = "http://okino.ru"

    @staticmethod
    def extract_state(url):
        res = urlparse(url)
        qs = parse_qs(res.query)
        if 'state' not in qs:
            return None
        decoded = decodestring(qs['state'][0])
        state = loads(decoded, object_hook=phpobject)
        state = getattr(state, '_properties')
        return state

    def search(self, search_filter=None, skip=None):
        """
        Search media

        :type search_filter: SearchFilter
        :param search_filter: Use SearchFilter
        :param skip: How many results to skip (for paging)
        """
        url = self.base_url + "/films/results"
        query = {}
        if search_filter.name:
            query['search'] = urllib.quote(search_filter.name)
        if search_filter:
            query['state'] = search_filter.state()
        if skip:
            query['skip'] = skip
        if query:
            url += "?" + urllib.urlencode(query)

        if search_filter:
            self.log.info('Using search filter: %s', search_filter)

        with Timer(logger=self.log, name='Fetching URL'):
            html = self.fetch_page(url)

        if self.http_response.redirected_to:
            match = re.search('/film/details/(\d+)', self.http_response.redirected_to)
            if match:
                return self._parse_details(html, int(match.group(1)))
            else:
                raise ScraperError(32002, "Malformed answer (invalid redirect)")
        results = []
        with Timer(logger=self.log, name='Parsing'):
            document = HtmlDocument.from_string(html)
            self.has_more = False
            grid_no_message = document.find('div', {'class': 'grid_no_message'})
            if grid_no_message:
                self.log.info("No results found.")
                return []
            grid = document.find('table', {'class': 'grid'})
            if not grid:
                raise ScraperError(32002, "Malformed answer (no result grid)")
            pager = document.find('div', {'class': 'simple_pager'})
            page_links = pager.find('span|a')
            self.has_more = 'disable' not in page_links.last.classes
            rows = grid.find('tr')
            warnings = 0
            for row in rows:
                try:
                    title_td = row.find('td', {'class': 'title'})
                    if not title_td:
                        continue

                    link = title_td.find('a').attr('href')
                    media_id = int(link.split('/')[-1])
                    title = title_td.find('nobr').text
                    original_title = title_td.find('span').text

                    years = row.find('td', {'class': 'year'}).text.split("-", 2)
                    if len(years) > 1:
                        start_year = int(years[0])
                        end_year = int(years[1]) if years[1] else None
                        continuing = not years[1]
                    else:
                        start_year = end_year = int(years[0])
                        continuing = False

                    rating = row.find('td', {'class': 'rating'})[0].text
                    user_rating = row.find('td', {'class': 'rating'})[1].text

                    date_td = row.find('td', {'class': 'date'}).text
                    added_date = str_to_date(date_td)

                    icon_class = row.find('td', {'class': 'icon'}).find('span').attr('class')
                    flag = Flag.find(icon_class)

                    quality = []
                    for span in row.find('td', {'class': 'quality'}).find('span'):
                        t = span.text.split("/")
                        fmt = Format.find(span.attr('title'))
                        quality.append(Quality(fmt, t[0], t[1]))

                    genres = []
                    for a in row.find('td', {'class': 'genre'}).find('a'):
                        url, name = a.attr('href'), a.text
                        genre = Genre.find(name)
                        if not genre:
                            self.log.warn('Unknown genre: %s', name)
                            self.log.warn('State: %r', self.extract_state(url))
                            genre = Genre.OTHER
                            genre.localized_title = name
                            warnings += 1
                        genres.append(genre)

                    languages = []
                    for a in row.find('td', {'class': 'lang'}).find('a'):
                        url, name = a.attr('href'), a.attr('title')
                        language = Language.find(name)
                        if not language:
                            self.log.warn('Unknown language: %s', name)
                            self.log.warn('State: %r', self.extract_state(url))
                            language = Language.OTHER
                            language.localized_title = name
                            warnings += 1
                        languages.append(language)

                    countries = []
                    for a in row.find('td', {'class': 'country'}).find('a'):
                        url, name = a.attr('href'), a.text
                        country = Country.find(name)
                        if not country:
                            self.log.warn('Unknown country: %s', name)
                            self.log.warn('State: %r', self.extract_state(url))
                            country = Country.OTHER
                            country.localized_title = name
                            warnings += 1
                        countries.append(country)

                    media = Media(media_id, title, original_title, added_date, flag, quality, genres, languages,
                                  countries, start_year, end_year, continuing, rating, user_rating)

                    self.log.debug(repr(media).decode("unicode-escape"))
                    results.append(media)
                except Exception as e:
                    self.log.exception(e)
                    warnings += 1

            self.log.info("Found %d result(s), %d warning(s).", len(results), warnings)

        return results

    def _parse_details(self, html, media_id):
        details = None
        warnings = 0
        with Timer(logger=self.log, name='Parsing'):
            document = HtmlDocument.from_string(html)
            title_h1 = document.find('H1', {'class': 'movie_title'})
            if not title_h1:
                raise ScraperError(32003, "No media found with ID %d" % media_id)

            nav = document.find('td', {'class': 'nav'})
            nav_selected = nav.find('li', {'class': 'selected( first)?'})
            section_name = nav_selected.find('a').attr('class')
            if section_name == 'movies':
                section_name = 'movie'
            section = Section.find(section_name)

            title = title_h1.before_text
            title_span = title_h1.find('span')
            original_title = title_span[0].text if title_span else None

            countries = []
            studios = []
            keywords = []
            genres = []
            directors = []
            writers = []
            producers = []
            actors = []
            ratings = {}
            votes = {}
            start_year = end_year = duration = mpaa_rating = plot = poster = None
            world_release = russian_release = None
            continuing = False

            description_blocks = document.find('div', {'class': 'description_block.*?'})
            for description_block in description_blocks:
                try:
                    label = description_block.find('div', {'class': 'label'})
                    description = description_block.find('div', {'class': 'description'})
                    description_para = description.find('p')
                    label = label.text.rstrip(":")

                    if label == 'Страны производители':
                        for elem in description_para.find('a'):
                            name = elem.text
                            url = elem.attr('href')
                            country = Country.find(name)
                            if not country:
                                self.log.warn('Unknown country: %s', name)
                                self.log.warn('Url: %s', url)
                                country = Country.OTHER
                                country.localized_title = name
                                warnings += 1
                            countries.append(country)
                    elif label == 'Год':
                        years = description_para.text.split("-", 2)
                        if len(years) > 1:
                            start_year = int(years[0])
                            end_year = int(years[1]) if years[1] else None
                            continuing = not years[1]
                        else:
                            start_year = end_year = int(years[0])
                            continuing = False
                    elif label == 'Дата выхода':
                        if len(description_para) > 0 and description_para[0]:
                            world_release = description_para[0].text.split(' ')[0]
                        if len(description_para) > 1 and description_para[1]:
                            russian_release = description_para[1].text.split(' ')[0]
                    elif label == 'Продолжительность':
                        if len(description_para) > 0:
                            duration = int(description_para.text.split(" ")[0])
                    elif label == 'Студии':
                        studios = [item.text for item in description_para.find('a')]
                    elif label == 'Возрастной рейтинг':
                        mpaa_title = description_para.find('span', {'class': 'age_rating'}).text
                        mpaa_rating = MPAA.find(mpaa_title)
                        if not mpaa_rating:
                            self.log.warn('Unknown MPAA rating: %s', mpaa_title)
                            mpaa_rating = MPAA.OTHER
                            mpaa_rating.localized_title = mpaa_title
                            warnings += 1
                    elif label == 'Ключевые слова':
                        keywords = description_para.find('a').strings
                    elif label == 'Жанр':
                        for elem in description.find('a'):
                            name = elem.text
                            url = elem.attr('href')
                            genre = Genre.find(name)
                            if not genre:
                                self.log.warn('Unknown genre: %s', name)
                                self.log.warn('Url: %s', url)
                                genre = Genre.OTHER
                                genre.localized_title = name
                                warnings += 1
                            genres.append(genre)
                    elif label == 'Описание':
                        plot = "\n\n".join(description_para.strings)
                    elif label == 'Режиссеры':
                        directors = description_para.find('a').strings
                    elif label == 'Сценаристы':
                        writers = description_para.find('a').strings
                    elif label == 'Продюссеры':
                        producers = description_para.find('a').strings
                    elif label == 'Актеры':
                        actors = description.find('a').strings
                        if actors and actors[-1] == 'Все участники':
                            actors = actors[:-1]
                    else:
                        self.log.warn('Unknown description block: %s', label)
                        warnings += 1
                except Exception as e:
                    self.log.exception(e)
                    warnings += 1

            rating_div = document.find("p", {'class': 'rating'})
            rating_spans = rating_div.find('span')
            for span in rating_spans:
                name = span.before_text.split(" ")[-1].rstrip(":")
                name = name.lower()
                rating_str = span.find('a').text
                rating_re = re.match('^(\d+(?:.\d+)?)(?:\s+\((\d+)\))?$', rating_str)
                if not rating_re:
                    continue
                rating = float(rating_re.group(1))
                if name == 'кинопоиска':
                    name = 'kinopoisk'
                ratings[name] = rating
                if rating_re.group(2):
                    votes_num = int(rating_re.group(2))
                    votes[name] = votes_num

            poster_span = document.find("span", {'class': 'poster'})
            poster_href = poster_span.find("a").attr('href')
            if poster_href:
                poster = poster_href

            details = Details(title, original_title, countries, start_year, world_release, russian_release, duration,
                              studios, mpaa_rating, keywords, genres, plot, directors, writers, producers, actors,
                              ratings, votes, poster, media_id, section, continuing, end_year)
        self.log.info("Got details successfully, %d warning(s)." % warnings)
        self.log.debug(repr(details).decode("unicode-escape"))

        return details

    def get_details(self, media_id):
        """
        Get media details by media ID

        :param media_id: Media ID
        """
        url = "%s/film/details/%d" % (self.base_url, media_id)

        with Timer(logger=self.log, name='Fetching URL'):
            html = self.fetch_page(url)

        return self._parse_details(html, media_id)

    def get_folders(self, media_id):
        """
        Get media folders by media ID

        :param media_id: Media ID
        """
        url = "%s/film/content/%d" % (self.base_url, media_id)

        with Timer(logger=self.log, name='Fetching URL'):
            html = self.fetch_page(url)
        folders = []
        warnings = 0
        with Timer(logger=self.log, name='Parsing folders'):
            document = HtmlDocument.from_string(html)
            blocks = document.find("div", {'class': 'block_files.*?'})
            if not blocks:
                if "Полномасштабный поиск" in unicode(document):
                    raise ScraperError(32019, "Service 'Extended search' is not enabled", dialog=True)
                self.log.warn("No folders found.")
                return []
            for block in blocks:
                try:
                    folder_id = int(block.attr('id')[3:])
                    header = block.find("div", {'class': 'block_header.*?'})
                    icon_class = header.find('span', {'class': 'files_.*?'}).attr('class')
                    flag = Flag.find(icon_class)
                    title = header.find('span', {'title': '.*?'}).text
                    left_div = block.find('div', {'class': 'l'})
                    right_div = block.find('div', {'class': 'r'})
                    fmt_name = left_div.find('img', {'src': '.*?format.*?'}).attr('title')
                    fmt = Format.find(fmt_name)
                    if not fmt:
                        self.log.warn('Format is unknown: %s', fmt_name)
                        warnings += 1
                    link = left_div.find('a', {'class': 'torrent'}).attr('href')
                    if link:
                        # noinspection PyAugmentAssignment
                        link = self.base_url+link
                    else:
                        self.log.warn('Torrent link is undefined')
                        warnings += 1
                    languages = None
                    video_quality = audio_quality = None
                    embedded_subtitles = external_subtitles = None
                    size = duration = None
                    for p in right_div.find('p'):
                        name = p.find('span').text.rstrip(':')
                        if name == 'Языки звуковых дорожек':
                            titles = p.find('a').attrs('title')
                            if titles:
                                languages = []
                                for lang in titles:
                                    language = Language.find(lang)
                                    if not language:
                                        self.log.warn('Unknown audio language: %s', lang)
                                        language = Language.OTHER
                                        language.localized_title = lang
                                        warnings += 1
                                    languages.append(language)
                        elif name == 'Качество звука':
                            val = p.after_text
                            audio_quality = AudioQuality.find(val)
                            if not audio_quality:
                                self.log.warn('Unknown audio quality: %s', val)
                                audio_quality = AudioQuality.UNKNOWN
                                audio_quality.localized_title = val
                                warnings += 1
                        elif name == 'Качество изображения':
                            val = p.after_text
                            video_quality = VideoQuality.find(val)
                            if not video_quality:
                                self.log.warn('Unknown video quality: %s', val)
                                video_quality = VideoQuality.UNKNOWN
                                video_quality.localized_title = val
                                warnings += 1
                        elif name == 'Встроенные субтитры':
                            titles = p.find('a').attrs('title')
                            if titles:
                                embedded_subtitles = []
                                for lang in titles:
                                    language = Language.find(lang)
                                    if not language:
                                        self.log.warn('Unknown embedded subtitles language: %s', lang)
                                        language = Language.OTHER
                                        language.localized_title = lang
                                        warnings += 1
                                    embedded_subtitles.append(language)
                        elif name == 'Внешние субтитры':
                            titles = p.find('a').attrs('title')
                            if titles:
                                external_subtitles = []
                                for lang in titles:
                                    language = Language.find(lang)
                                    if not language:
                                        self.log.warn('Unknown external subtitles language: %s', lang)
                                        language = Language.OTHER
                                        language.localized_title = lang
                                        warnings += 1
                                    external_subtitles.append(language)
                        elif name == 'Размер файлов':
                            val = p.after_text
                            size = self._parse_size(val)
                            if size is None:
                                self.log.warn("Can't parse size: %s", val)
                                warnings += 1
                        elif name == 'Длительность':
                            val = p.after_text
                            duration = self._parse_duration(val)
                            if duration is None:
                                self.log.warn("Can't parse duration: %s", val)
                                warnings += 1
                        else:
                            self.log.warn("Unknown folder property: %s", name)
                            warnings += 1

                    quality = Quality(fmt, video_quality, audio_quality)
                    files_tbl = document.find('table', {'id': 'files_tbl'})
                    files = self._parse_files(files_tbl, media_id, folder_id) if files_tbl else []
                    folder = Folder(folder_id, media_id, title, flag, link, quality, languages, fmt,
                                    embedded_subtitles, external_subtitles, duration, size, files)
                    self.log.debug(repr(folder).decode("unicode-escape"))
                    folders.append(folder)
                except Exception as e:
                    self.log.exception(e)
                    warnings += 1

            self.log.info("Got %d folder(s) successfully, %d warning(s)." % (len(folders), warnings))
        return folders

    def get_files(self, media_id, folder_id):
        """
        Get media files by folder ID

        :param media_id: Media ID
        :param folder_id: Folder ID
        """
        url = "%s/film/filelist/%d?fid=%d" % (self.base_url, media_id, folder_id)

        with Timer(logger=self.log, name='Fetching URL'):
            html = self.fetch_page(url)

        document = HtmlDocument.from_string(html)
        files_tbl = document.find('table', {'id': 'files_tbl'})
        return self._parse_files(files_tbl, media_id, folder_id)

    def _parse_files(self, doc, media_id, folder_id):
        files = []
        warnings = 0
        with Timer(logger=self.log, name='Parsing files'):
            rows = doc.find('tr')[1:]
            if not rows:
                self.log.warn("No files found.")
                return []
            for row in rows:
                try:
                    icon_class = row.find('td', {'class': 'icon'}).find('span').attr('class')
                    flag = Flag.find(icon_class)
                    link = row.find('td', {'class': 'file_torrent_link'}).find('a').attr('href')
                    if not link:
                        self.log.warn("No link to torrent file found, skipping...")
                        warnings += 1
                        continue
                    file_id = re.search(r'file=(\d+)', link)
                    if not file_id:
                        self.log.warn("Invalid torrent link: %s", link)
                        warnings += 1
                        continue
                    file_id = file_id.group(1)
                    # noinspection PyAugmentAssignment
                    link = self.base_url + link
                    title = row.find('td', {'class': 'file_title'}).find('a').text
                    file_fmt = row.find('td', {'class': 'format'}).text
                    duration = self._parse_duration(row.find('td', {'class': 'size'})[0].text)
                    size = self._parse_size(row.find('td', {'class': 'size'})[1].text)
                    subtitles = []
                    for lang in row.find('td', {'class': 'sub'}).find('IMG').attrs('title'):
                        language = Language.find(lang)
                        if not language:
                            self.log.warn('Unknown subtitles language: %s', lang)
                            language = Language.OTHER
                            language.localized_title = lang
                            warnings += 1
                        subtitles.append(language)
                    props = row.find('td', {'class': 'videoprop'}).find('ul')
                    video_streams = []
                    audio_streams = []
                    if len(props) != 2:
                        self.log.warn("Can't parse audio/video stream properties")
                        warnings += 1
                    else:
                        for li in props[0].find('li'):
                            li = li.text
                            parts = re.split(",\s*", li)
                            if len(parts) == 3:
                                resolution, codec, kbps = parts
                            elif len(parts) == 4:
                                resolution, codec, bits, kbps = parts
                            else:
                                self.log.warn("Can't parse video stream properties: %s", li)
                                warnings += 1
                                continue
                            width, height = resolution.split("x")
                            kbps = float(kbps.split(" ")[0])
                            video_streams.append(VideoStreamInfo(width, height, codec, kbps))
                        for li in props[1].find('li'):
                            lang_title = li.find('img').attr('title')
                            language = Language.find(lang_title.upper()) if lang_title else None
                            li = li.text
                            parts = re.split(",\s*", li)
                            if len(parts) != 3:
                                self.log.warn("Can't parse audio stream properties: %s", li)
                                warnings += 1
                                continue
                            codec = parts[0]
                            channels = int(parts[1]) or None
                            kbps = float(parts[2].split(" ")[0])
                            audio_streams.append(AudioStreamInfo(language, codec, kbps, channels))
                    f = File(file_id, media_id, folder_id, title, flag, link, file_fmt, subtitles, duration, size,
                             video_streams, audio_streams)
                    self.log.debug(repr(f).decode("unicode-escape"))
                    files.append(f)
                except Exception as e:
                    self.log.exception(e)
                    warnings += 1
        self.log.info("Got %d file(s) successfully, %d warning(s)." % (len(files), warnings))
        return files

    @staticmethod
    def _parse_size(size):
        size = size.strip(" \t\xa0")
        if size.isdigit():
            return long(size)
        else:
            num, qua = size[:-2].rstrip(), size[-2:].lower()
            if qua == 'mb' or qua == 'мб':
                return long(float(num)*1024*1024)
            elif qua == 'gb' or qua == 'гб':
                return long(float(num)*1024*1024*1024)
            elif qua == 'tb' or qua == 'тб':
                return long(float(num)*1024*1024*1024*1024)

    @staticmethod
    def _parse_duration(duration):
        duration = duration.strip(" \t\xa0")
        parts = duration.split(":")
        if len(parts) == 1:
            return int(duration)
        elif len(parts) == 2:
            return int(parts[0])*60+int(parts[1])
        elif len(parts) == 3:
            return int(parts[0])*3600+int(parts[1])*60+int(parts[2])
        elif len(parts) == 4:
            return int(parts[0])*86400+int(parts[1])*3600+int(parts[2])*60+int(parts[3])
