# -*- coding: utf-8 -*-
from okino import container as container
from okino.common import lang, filter_dict, date_to_str
from okino.plugin import plugin
from okino.plugin.contextmenu import search_result_context_menu, toggle_watched_context_menu, \
    refresh_context_menu, download_torrent_context_menu, library_context_menu
from okino.scraper import Details, Media, Folder, File
import titleformat as tf


def with_fanart(item, url=None):
    if isinstance(item, list):
        return [with_fanart(i, url) for i in item]
    elif isinstance(item, dict):
        properties = item.setdefault("properties", {})
        if not properties.get("fanart_image"):
            if not url:
                properties["fanart_image"] = plugin.addon.getAddonInfo("fanart")
            else:
                properties["fanart_image"] = url
        return item


def itemify_library_folder(d, f):
    item = itemify_folder(f)
    item['label'] = tf.library_folder_title(d, f)
    item['info']['title'] = d.title
    return item


def itemify_folder(f):
    """
    :type f: Folder
    """
    item = {
        'label': tf.folder_title(f),
        'path': plugin.url_for('show_files', media_id=f.media_id, folder_id=f.id),
        'context_menu':
            refresh_context_menu(f.media_id) +
            download_torrent_context_menu(f.link) +
            library_context_menu(f.media_id, f.id),
        'info': {
            'size': f.size,
        },
        'stream_info': {
            'video': {
                'width': f.fmt.width,
                'height': f.fmt.height,
                'duration': f.duration,
            },
        }
    }
    return with_fanart(item)


def itemify_file(f, **kwargs):
    """
    :type f: File
    """
    item = {
        'label': tf.file_title(f),
        'context_menu':
            refresh_context_menu(f.media_id) +
            toggle_watched_context_menu() +
            download_torrent_context_menu(f.link),
        'info': {
            'size': f.size,
        },
        'stream_info': [],
        'is_playable': True,
        'path': plugin.url_for('play_file', media_id=f.media_id, url=f.link, title=f.title, **kwargs)
    }
    item['stream_info'].extend(('video', {
        'codec': stream.codec,
        'width': stream.width,
        'height': stream.height,
        'duration': f.duration,
    }) for stream in f.video_streams)
    item['stream_info'].extend(('audio', filter_dict({
        'codec': stream.codec,
        'language': stream.language.name if stream.language else None,
        'channels': stream.channels
    })) for stream in f.audio_streams)
    item['stream_info'].extend(('subtitles', {
        'language': sub.name
    }) for sub in f.subtitles)
    return with_fanart(item)


def itemify_details(details):
    """
    :type details: Details
    """
    item = {
        'thumbnail': details.poster,
        'path': plugin.url_for('show_folders', media_id=details.media_id),
        'info': filter_dict({
            'plot': details.plot,
            'title': details.title,
            'rating': details.ratings.get('imdb', None),
            'cast': details.actors,
            'director': u" / ".join(details.directors),
            'studio': u" / ".join(details.studios),
            'writer': u" / ".join(details.writers),
            'premiered': details.world_release,
            'genre': u" / ".join([g.localized for g in details.genres]),
            'year': details.start_year,
            'votes': details.votes.get('imdb', None),
            'status': lang(34008) if details.continuing else None,
            'originaltitle': details.original_title,
            'mpaa': details.mpaa_rating.localized if details.mpaa_rating else None,
            'duration': details.duration
        })
    }
    return with_fanart(item)


def itemify_single_result(result, folders=None):
    """
    :type result: Details
    """
    media_id = result.media_id
    scraper = container.scraper()
    folders = folders or scraper.get_folders_cached(media_id)
    watched_items = container.watched_items()
    total_size = sum(f.size for f in folders)
    is_series = result.section.is_series()
    watched = watched_items.is_watched(media_id, total_size=total_size if is_series else None)
    meta_cache = container.meta_cache()
    meta = meta_cache.setdefault(media_id, {})
    meta.update({
        'total_size': total_size,
        'is_series': is_series,
    })
    item = itemify_details(result)
    item.update({
        'label': tf.bookmark_title(result, folders),
        'context_menu': search_result_context_menu(result, total_size=total_size),
    })
    item['info'].update({
        'playcount': int(watched),
    })
    return item


def itemify_search_results(results):
    """
    :type results: list[Media]
    """
    ids = [result.id for result in results]
    scraper = container.scraper()
    meta_cache = container.meta_cache()
    all_details = scraper.get_details_bulk(ids)
    watched_items = container.watched_items()
    items = []
    for media in results:
        details = all_details[media.id]
        is_series = details.section.is_series()
        watched = watched_items.is_watched(media.id, date_added=media.date if is_series else None)
        meta = meta_cache.setdefault(media.id, {})
        meta.update({
            'date_added': media.date,
            'is_series': is_series,
        })
        item = itemify_details(details)
        item.update({
            'label': tf.media_title(media),
            'label2': date_to_str(media.date),
            'context_menu': search_result_context_menu(details, media.date),
        })
        item['info'].update({
            'date': date_to_str(media.date),
            'playcount': int(watched),
        })
        items.append(item)
    return items


def itemify_bookmarks(ids):
    scraper = container.scraper()
    details = scraper.get_details_bulk(ids)
    folders = scraper.get_folders_bulk(ids)
    return [itemify_single_result(details[media_id], folders[media_id]) for media_id in ids]
