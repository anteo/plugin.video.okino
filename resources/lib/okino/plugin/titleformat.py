# -*- coding: utf-8 -*-

from okino.scraper import Folder, Flag, File, Media, Details
from okino.common import lang
from okino.plugin import plugin


def declension_ru(n, s1, s2, s5):
    ns = n % 10
    n2 = n % 100

    if 10 <= n2 <= 19:
        return s5

    if ns == 1:
        return s1

    if 2 <= ns <= 4:
        return s2

    return s5


def color(title, color_val):
    return "[COLOR %s]%s[/COLOR]" % (color_val, title)


def bold(title):
    return "[B]%s[/B]" % title


def italics(title):
    return "[I]%s[/I]" % title

_color = color
_bold = bold
_italics = italics


# noinspection PyShadowingNames
def decorate(title, color=None, bold=False, italics=False):
    if color:
        title = _color(title, color)
    if bold:
        title = _bold(title)
    if italics:
        title = _italics(title)
    return title


def flag_label(flag):
    """
    :type flag: Flag
    """
    if flag == Flag.NEW_SERIES:
        return color(u"+", 'orange')
    elif flag == Flag.QUALITY_UPDATED:
        return color(u"^", 'yellow')
    elif flag == Flag.RECENTLY_ADDED:
        return color(u"*", 'lime')
    else:
        return u"  "


def years(start_year, end_year):
    if start_year == end_year:
        return "%d" % start_year
    elif not end_year:
        return "%d-..." % start_year
    else:
        return "%d-%d" % (start_year, end_year)


def media_title(media):
    """
    :type media: Media
    """
    return (flag_label(media.flag)) + \
           (" (%s)" % media.rating if media.rating and plugin.get_setting('show-rating', bool) else "") + \
           (" %s" % color(media.title, 'white')) + \
           (" / %s" % media.original_title if media.original_title and plugin.get_setting('show-original-title', bool) else "") + \
           (" / %s" % years(media.start_year, media.end_year)) + \
           (", %s" % ("/".join(g.localized for g in media.genres)) if plugin.get_setting('show-genre', bool) else "") + \
           (", %s" % ("/".join(c.localized for c in media.countries)) if plugin.get_setting('show-country', bool) else "") + \
           (", %s" % ("/".join(l.localized for l in media.languages)) if plugin.get_setting('show-language', bool) else "") + \
           (" [%s]" % ("/".join(l.format.localized for l in media.quality)) if plugin.get_setting('show-video-quality', bool) else "")


def bookmark_title(details, folders):
    """
    :type details: Details
    :type folders: list[Folder]
    """
    flag = next((f.flag for f in folders if f.flag), None)
    formats = list(set(f.fmt for f in folders))
    return (flag_label(flag)) + \
           (" (%s)" % details.ratings['imdb'] if 'imdb' in details.ratings and plugin.get_setting('show-rating', bool) else "") + \
           (" %s" % color(details.title, 'white')) + \
           (" / %s" % details.original_title if details.original_title and plugin.get_setting('show-original-title', bool) else "") + \
           (" / %s" % years(details.start_year, details.end_year)) + \
           (" / %s" % details.section.singular.localized) + \
           (", %s" % ("/".join(g.localized for g in details.genres)) if plugin.get_setting('show-genre', bool) else "") + \
           (", %s" % ("/".join(c.localized for c in details.countries)) if plugin.get_setting('show-country', bool) else "") + \
           (" [%s]" % ("/".join(f.localized for f in formats)) if plugin.get_setting('show-video-quality', bool) else "")


def folder_title(folder):
    """
    :type folder: Folder
    """
    return "%s %s / %d %s" % (flag_label(folder.flag), color(folder.title, 'white'), len(folder.files),
                              declension_ru(len(folder.files), lang(34005), lang(34006), lang(34007))) + \
           (", %s" % folder.quality.video.localized if folder.quality.video and plugin.get_setting('show-video-quality', bool) else "") + \
           (", %s" % folder.quality.audio.localized if folder.quality.audio and plugin.get_setting('show-audio-quality', bool) else "") + \
           (", %s" % human_size(folder.size) if plugin.get_setting('show-total-size', bool) else "") + \
           (" [%s]" % human_duration(folder.duration) if plugin.get_setting('show-duration', bool) else "")


def human_size(num, suffix='b'):
    for unit in ['', 'K', 'M', 'G', 'T', 'P', 'E', 'Z']:
        if abs(num) < 1024.0:
            return "%3.1f%s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.1f%s%s" % (num, 'Y', suffix)


def human_duration(total_seconds):
    seconds = total_seconds % 60
    minutes = (total_seconds / 60) % 60
    hours = total_seconds / 3600
    if hours > 0:
        return "%d:%02d:%02d" % (hours, minutes, seconds)
    else:
        return "%02d:%02d" % (minutes, seconds)


def file_title(f):
    """
    :type f: File
    """
    return "%s %s / %s" % (flag_label(f.flag), color(f.title, 'white'), f.file_format) + \
           (", %s" % human_size(f.size) if plugin.get_setting('show-total-size', bool) else "") + \
           (" [%s]" % human_duration(f.duration) if plugin.get_setting('show-duration', bool) else "")


def folder_file_title(folder, f):
    """
    :type folder: Folder
    :type f: File
    """
    return "%s %s / %s" % (flag_label(folder.flag), color(f.title, 'white'), f.file_format) + \
           (", %s" % folder.quality.video.localized if folder.quality.video and plugin.get_setting('show-video-quality', bool) else "") + \
           (", %s" % folder.quality.audio.localized if folder.quality.audio and plugin.get_setting('show-audio-quality', bool) else "") + \
           (", %s" % human_size(f.size) if plugin.get_setting('show-total-size', bool) else "") + \
           (" [%s]" % human_duration(f.duration) if plugin.get_setting('show-duration', bool) else "")
