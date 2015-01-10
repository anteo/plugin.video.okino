# -*- coding: utf-8 -*-

from base64 import encodestring
from util.phpserialize import dumps, phpobject


class AbstractSearchFilter:
    # noinspection PyShadowingBuiltins
    def __init__(self, sections=None, extended_search=False, format=None, genres=None, countries=None, languages=None,
                 audio_quality=None, video_quality=None, rating_min=None, rating_max=None, year_min=None, year_max=None,
                 mpaa_rating=None, page_size=None, order_by=None, order_dir=None, name=None):
        self.sections = sections or []
        self.extended_search = extended_search
        self.format = format
        self.genres = genres or []
        self.countries = countries or []
        self.languages = languages or []
        self.audio_quality = audio_quality
        self.video_quality = video_quality
        self.rating_min = rating_min
        self.rating_max = rating_max
        self.year_min = year_min
        self.year_max = year_max
        self.mpaa_rating = mpaa_rating
        self.page_size = page_size
        self.order_by = order_by
        self.order_dir = order_dir
        self.name = name

    def as_tuple(self):
        return (tuple(self.sections), self.extended_search, self.format, tuple(self.genres), tuple(self.countries),
                tuple(self.languages), self.audio_quality, self.video_quality, self.rating_min, self.rating_max,
                self.year_min,  self.year_max, self.mpaa_rating, self.page_size, self.order_by, self.order_dir,
                self.name)

    def __hash__(self):
        return hash(self.as_tuple())

    def __eq__(self, other):
        return self.as_tuple() == other.as_tuple()


class OkinoSearchFilter(AbstractSearchFilter):
    def get_data(self):
        data = {}
        if self.sections:
            data['section_filter'] = dict([("\\'"+i.filter_val+"\\'", i.filter_val) for i in self.sections])
        if self.extended_search:
            data['extSearch'] = True
        if self.format:
            data['Format'] = self.format.filter_val
        if self.genres:
            data['Genre'] = [[i.filter_val] for i in self.genres]
        if self.countries:
            data['Country'] = [[i.filter_val] for i in self.countries]
        if self.languages:
            data['Lang'] = [i.filter_val for i in self.languages]
        if self.audio_quality:
            data['audio_quality'] = self.audio_quality.filter_val
        if self.video_quality:
            data['video_quality'] = self.video_quality.filter_val
        if self.rating_min or self.rating_max:
            rating = {}
            if self.rating_min:
                rating['min'] = self.rating_min
            if self.rating_max:
                rating['max'] = self.rating_max
            data['rating'] = rating
        if self.year_min or self.year_max:
            year = {}
            if self.year_min:
                year['min'] = str(self.year_min)
            if self.year_max:
                year['max'] = str(self.year_max)
            data['Year'] = year
        if self.mpaa_rating:
            data['mpaa'] = self.mpaa_rating.filter_val
        if self.page_size:
            data['pagesize'] = self.page_size
        if self.order_by:
            data['orderName'] = self.order_by.filter_val
        if self.order_dir:
            data['orderType'] = self.order_dir.filter_val
        return data

    data = property(get_data)

    def state(self):
        php_object = phpobject('amorphous', {'\0amorphous\0_properties': self.get_data()})
        serialized = dumps(php_object)
        return encodestring(serialized)

    def __str__(self):
        return repr(self.data)
