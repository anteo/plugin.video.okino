# -*- coding: utf-8 -*-

from okino.plugin import plugin
from search import make_search
from common import with_fanart, lang
from okino.enumerations import Section, Format, Genre, Country, Language, AudioQuality, \
    VideoQuality, MPAA, Order, OrderDirection
from okino.common import notify
from xbmcswift2 import xbmcgui

import titleformat as tf
import okino.container as container


@plugin.route('/advanced_search/clear')
def clear_advanced_search():
    storage = container.search_storage()
    storage['search_filter'] = container.search_filter()


@plugin.route('/advanced_search/<section>/do')
def do_advanced_search(section):
    plugin.set_content('movies')
    storage = container.search_storage()
    sf = storage['search_filter']
    """:type : AbstractSearchFilter"""
    sf.sections = [Section.find(section)] if section != '__ALL__' else list(Section)
    if not make_search(sf):
        notify(lang(40313))
        plugin.finish(succeeded=False)


@plugin.route('/advanced_search/edit/<param>')
def edit_advanced_search(param):
    storage = container.search_storage()
    sf = storage['search_filter']
    """:type : AbstractSearchFilter"""
    if param == 'format':
        formats = [Format.SD, Format.HD]
        res = xbmcgui.Dialog().select(lang(34100), [lang(34101)] + [f.localized for f in formats])
        sf.format = formats[res-1] if res else None
    elif param == 'genre':
        genres = sorted(Genre.all())
        res = xbmcgui.Dialog().select(lang(34103), [lang(34101)] + [g.localized for g in genres])
        sf.genres = [genres[res-1]] if res else []
    elif param == 'country':
        countries = sorted(Country.all())
        res = xbmcgui.Dialog().select(lang(34104), [lang(34101)] + [g.localized for g in countries])
        sf.countries = [countries[res-1]] if res else []
    elif param == 'language':
        languages = sorted(Language.all())
        res = xbmcgui.Dialog().select(lang(34105), [lang(34101)] + [g.localized for g in languages])
        sf.languages = [languages[res-1]] if res else []
    elif param == 'audio_quality':
        qualities = AudioQuality.all()
        res = xbmcgui.Dialog().select(lang(34106), [lang(34101)] + [g.localized for g in qualities])
        sf.audio_quality = qualities[res-1] if res else None
    elif param == 'video_quality':
        qualities = VideoQuality.all()
        res = xbmcgui.Dialog().select(lang(34107), [lang(34101)] + [g.localized for g in qualities])
        sf.video_quality = qualities[res-1] if res else None
    elif param == 'mpaa_rating':
        ratings = MPAA.all()
        ratings.remove(MPAA.ANY)
        res = xbmcgui.Dialog().select(lang(34108), [lang(34101)] + [g.localized for g in ratings])
        sf.mpaa_rating = ratings[res-1] if res else None
    elif param == 'year_min':
        res = xbmcgui.Dialog().numeric(0, lang(34109))
        sf.year_min = int(res) if res else None
    elif param == 'year_max':
        res = xbmcgui.Dialog().numeric(0, lang(34110))
        sf.year_max = int(res) if res else None
    elif param == 'rating_min':
        res = xbmcgui.Dialog().numeric(0, lang(34112))
        if res and int(res) > 99:
            res = 99
        sf.rating_min = float(res)/10.0 if res else None
    elif param == 'rating_max':
        res = xbmcgui.Dialog().numeric(0, lang(34113))
        if res and int(res) > 99:
            res = 99
        sf.rating_max = float(res)/10.0 if res else None
    elif param == 'order_by':
        orders = Order.all()
        res = xbmcgui.Dialog().select(lang(34114), [lang(34101)] + [g.localized for g in orders])
        sf.order_by = orders[res-1] if res else None
    elif param == 'order_dir':
        dirs = OrderDirection.all()
        res = xbmcgui.Dialog().select(lang(34115), [g.localized for g in dirs])
        sf.order_dir = OrderDirection.DESC if res == 1 else None


@plugin.route('/advanced_search/<section>')
def advanced_search(section):
    storage = container.search_storage()
    sf = storage.setdefault('search_filter', container.search_filter())
    """:type : AbstractSearchFilter"""
    items = [{
        'label': lang(34102),
        'path': plugin.url_for('do_advanced_search', section=section),
    }, {
        'label': lang(34111),
        'path': plugin.url_for('clear_advanced_search'),
    }, {
        'label': tf.color(lang(34100), 'white') + ": " + (sf.format.localized if sf.format else lang(34101)),
        'path': plugin.url_for('edit_advanced_search', param='format')
    }, {
        'label': tf.color(lang(34103), 'white') + ": " + (sf.genres[0].localized if sf.genres else lang(34101)),
        'path': plugin.url_for('edit_advanced_search', param='genre')
    }, {
        'label': tf.color(lang(34104), 'white') + ": " + (sf.countries[0].localized if sf.countries else lang(34101)),
        'path': plugin.url_for('edit_advanced_search', param='country')
    }, {
        'label': tf.color(lang(34105), 'white') + ": " + (sf.languages[0].localized if sf.languages else lang(34101)),
        'path': plugin.url_for('edit_advanced_search', param='language')
    }, {
        'label': tf.color(lang(34106), 'white') + ": " + (sf.audio_quality.localized if sf.audio_quality else lang(34101)),
        'path': plugin.url_for('edit_advanced_search', param='audio_quality')
    }, {
        'label': tf.color(lang(34107), 'white') + ": " + (sf.video_quality.localized if sf.video_quality else lang(34101)),
        'path': plugin.url_for('edit_advanced_search', param='video_quality')
    }, {
        'label': tf.color(lang(34108), 'white') + ": " + (sf.mpaa_rating.localized if sf.mpaa_rating else lang(34101)),
        'path': plugin.url_for('edit_advanced_search', param='mpaa_rating')
    }, {
        'label': tf.color(lang(34109), 'white') + ": " + (str(sf.year_min) if sf.year_min else lang(34101)),
        'path': plugin.url_for('edit_advanced_search', param='year_min')
    }, {
        'label': tf.color(lang(34110), 'white') + ": " + (str(sf.year_max) if sf.year_max else lang(34101)),
        'path': plugin.url_for('edit_advanced_search', param='year_max')
    }, {
        'label': tf.color(lang(34112), 'white') + ": " + (str(sf.rating_min) if sf.rating_min else lang(34101)),
        'path': plugin.url_for('edit_advanced_search', param='rating_min')
    }, {
        'label': tf.color(lang(34113), 'white') + ": " + (str(sf.rating_max) if sf.rating_max else lang(34101)),
        'path': plugin.url_for('edit_advanced_search', param='rating_max')
    }, {
        'label': tf.color(lang(34114), 'white') + ": " + (sf.order_by.localized if sf.order_by else lang(34101)),
        'path': plugin.url_for('edit_advanced_search', param='order_by')
    }, {
        'label': tf.color(lang(34115), 'white') + ": " + (OrderDirection.DESC.localized if sf.order_dir else OrderDirection.ASC.localized),
        'path': plugin.url_for('edit_advanced_search', param='order_dir')
    }]
    plugin.finish(with_fanart(items), cache_to_disc=False)