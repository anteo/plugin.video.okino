# -*- coding: utf-8 -*-
from okino import container as container
from okino.plugin import plugin
from okino.common import lang, save_path
from util.encoding import ensure_str
from okino.torrent.client import *
from xbmcswift2 import actions, xbmcgui, xbmc


@plugin.route('/mark/watched/<media_id>')
def mark_watched(media_id):
    meta_cache = container.meta_cache()
    watched_items = container.watched_items()
    meta = meta_cache.get(media_id, {})
    total_size = meta.get('total_size')
    date_added = meta.get('date_added')
    if total_size is None:
        scraper = container.scraper()
        folders = scraper.get_folders_cached(media_id)
        total_size = sum(f.size for f in folders)
        meta['total_size'] = total_size
        meta_cache[media_id] = meta
    watched_items.mark(media_id, True, date_added=date_added, total_size=total_size)
    plugin.refresh()


@plugin.route('/refresh')
def refresh_all():
    container.details_cache().clear()
    container.folders_cache().clear()
    container.meta_cache().clear()
    container.search_cache().clear()
    plugin.refresh()


@plugin.route('/mark/unwatched/<media_id>')
def mark_unwatched(media_id):
    watched_items = container.watched_items()
    watched_items.mark(media_id, False)
    plugin.refresh()


@plugin.route('/refresh/<media_id>')
def refresh(media_id):
    details_cache = container.details_cache()
    folders_cache = container.folders_cache()
    meta_cache = container.meta_cache()
    if media_id in details_cache:
        del(details_cache[media_id])
    if media_id in folders_cache:
        del(folders_cache[media_id])
    if media_id in meta_cache:
        del(meta_cache[media_id])
    plugin.refresh()


@plugin.route('/bookmarks/<section>/add/<media_id>/<title>')
def add_bookmark(section, media_id, title):
    bookmarks = container.bookmarks()
    bookmarks.add(media_id, section)
    # notify(lang(40308) % (Section.find(section).singular.localized, ensure_unicode(title)))
    plugin.refresh()


@plugin.route('/bookmarks/delete/<media_id>')
def delete_bookmark(media_id):
    bookmarks = container.bookmarks()
    bookmarks.delete(media_id)
    plugin.refresh()


@plugin.route('/library/add/<media_id>/<folder_id>')
def add_to_library(media_id, folder_id):
    scraper = container.scraper()
    details = scraper.get_details_cached(media_id)
    folder = scraper.get_folder_cached(media_id, folder_id)
    library_manager = container.library_manager()
    library_manager.update_folder(details, folder)
    plugin.refresh()
    if plugin.get_setting('update-xbmc-library', bool):
        plugin.update_library('video', library_manager.path)


@plugin.route('/library/remove/<folder_id>')
def remove_from_library(folder_id):
    container.library_manager().remove_folder(folder_id)
    plugin.refresh()
    if plugin.get_setting('clean-xbmc-library', bool):
        plugin.clean_library('video', False)


def info_context_menu():
    return [(lang(40300), "Action(Info)")]


def toggle_watched_context_menu():
    return [(lang(40305), actions.toggle_watched())]


def refresh_context_menu(media_id):
    return [(lang(40304), actions.update_view(plugin.url_for('refresh', media_id=media_id)))]


def refresh_all_context_menu():
    return [(lang(40303), actions.update_view(plugin.url_for('refresh_all')))]


def bookmark_context_menu(media_id, section, title):
    bookmarks = container.bookmarks()
    if media_id in bookmarks:
        return [(lang(40307), actions.background(plugin.url_for('delete_bookmark', media_id=media_id,
                                                                section=section)))]
    else:
        return [(lang(40306), actions.background(plugin.url_for('add_bookmark', media_id=media_id,
                                                                section=section,
                                                                title=ensure_str(title))))]


def mark_watched_context_menu(media_id, date_added=None, total_size=None):
    watched_items = container.watched_items()
    if media_id in watched_items:
        return [(lang(40302), actions.background(plugin.url_for('mark_unwatched', media_id=media_id)))]
    else:
        return [(lang(40301), actions.background(plugin.url_for('mark_watched', media_id=media_id,
                                                                date_added=date_added,
                                                                total_size=total_size)))]


def search_result_context_menu(details, date_added=None, total_size=None):
    """
    :type details: Details
    """
    media_id = details.media_id
    return info_context_menu() + \
        refresh_all_context_menu() + \
        refresh_context_menu(media_id) + \
        mark_watched_context_menu(media_id, date_added, total_size) + \
        bookmark_context_menu(media_id, details.section.name, details.title)


@plugin.route('/download/<url>')
def download_torrent(url):
    client = container.torrent_client()
    client.add(container.torrent(url), save_path(local=True))
    if isinstance(client, TransmissionClient):
        name = 'Transmission'
        addon_id = 'script.transmission'
    elif isinstance(client, UTorrentClient):
        name = 'UTorrent'
        addon_id = 'plugin.program.utorrent'
    else:
        return

    if xbmcgui.Dialog().yesno(lang(40316), *(lang(40317) % name).split("|")):
        xbmc.executebuiltin('XBMC.RunAddon(%s)' % addon_id)


def download_torrent_context_menu(url):
    if container.torrent_client() and url:
        return [(lang(40314), actions.background(plugin.url_for('download_torrent', url=url)))]
    else:
        return []


def clear_history_context_menu():
    return [(lang(40315), actions.background(plugin.url_for('clear_history')))]


def library_context_menu(media_id, folder_id):
    library_manager = container.library_manager()
    if library_manager.has_folder(folder_id):
        return [(lang(40321), actions.background(plugin.url_for('remove_from_library',
                                                                folder_id=folder_id)))]
    else:
        return [(lang(40320), actions.background(plugin.url_for('add_to_library',
                                                                media_id=media_id,
                                                                folder_id=folder_id)))]
