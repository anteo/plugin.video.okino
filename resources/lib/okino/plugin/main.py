# -*- coding: utf-8 -*-

from okino.plugin import plugin
from okino.common import lang, batch, abort_requested, save_files, purge_temp_dir, log
from okino.plugin.common import with_fanart, itemify_file, itemify_folder, \
    itemify_details, itemify_bookmarks
from okino.enumerations import Section, Genre
from okino.plugin.search import make_search
from okino.plugin.contextmenu import toggle_watched_context_menu, bookmark_context_menu, \
    download_torrent_context_menu, clear_history_context_menu
from util.encoding import ensure_unicode

import titleformat as tf
import okino.container as container


@plugin.route('/play/<media_id>/<url>/<title>')
def play_file(media_id, url, title):
    stream = container.torrent_stream()
    scraper = container.scraper()
    history = container.history()
    meta_cache = container.meta_cache()
    meta = meta_cache.setdefault(media_id, {})
    details = scraper.get_details_cached(media_id)
    item = itemify_details(details)
    title = u"%s / %s" % (ensure_unicode(title), item['info']['title'])
    item['info']['title'] = title
    history.add(media_id, details.section.name, title, plugin.request.url, url, details.poster)
    torrent = container.torrent(url=url)
    player = container.player()

    def check_and_mark_watched(event):
        log.info("Playback event: %s, current player progress: %d", event, player.get_percent())
        if player.get_percent() >= 90 and 'can_mark_watched' in plugin.request.args:
            watched_items = container.watched_items()
            watched_items.mark(media_id, date_added=meta.get('date_added'),
                               total_size=meta.get('total_size'))

    player.attach([player.PLAYBACK_STOPPED, player.PLAYBACK_ENDED], check_and_mark_watched)
    temp_files = stream.play(player, torrent, item)
    if temp_files:
        save_files(temp_files, rename=not stream.saved_files_needed, on_finish=purge_temp_dir)
    else:
        purge_temp_dir()


@plugin.route('/files/<media_id>/<folder_id>')
def show_files(media_id, folder_id):
    scraper = container.scraper()
    plugin.set_content('movies')
    files = scraper.get_files_cached(media_id, folder_id)
    plugin.add_items(itemify_file(f) for f in files)
    plugin.finish(sort_methods=['unsorted', 'title', 'duration', 'size'])


@plugin.route('/folders/<media_id>')
def show_folders(media_id):
    scraper = container.scraper()
    meta_cache = container.meta_cache()
    meta = meta_cache.setdefault(media_id, {})
    plugin.set_content('movies')
    folders = scraper.get_folders_cached(media_id)
    total_size = sum(f.size for f in folders)
    meta['total_size'] = total_size
    for f in folders:
        if len(f.files) == 1 and not meta.get('is_series'):
            item = itemify_file(f.files[0], can_mark_watched=1)
            item['label'] = tf.folder_file_title(f, f.files[0])
            plugin.add_item(item)
        else:
            plugin.add_item(itemify_folder(f))
    plugin.finish(sort_methods=['unsorted', 'title', 'duration', 'size'])


@plugin.route('/explore/<section>')
def explore(section):
    plugin.set_content('movies')
    sf = container.search_filter(sections=[Section[section]])
    header = [
        {'label': lang(34000), 'path': plugin.url_for('search_index', section=section)},
        {'label': lang(34001), 'path': plugin.url_for('genre_index', section=section)},
        {'label': lang(34002), 'path': plugin.url_for('bookmarks_index', section=section)},
        {'label': lang(34011), 'path': plugin.url_for('history_index', section=section)},
    ]
    make_search(sf, header)


@plugin.route('/genre/<section>')
def genre_index(section):
    return with_fanart([{'label': g.localized, 'path': plugin.url_for('by_genre', section=section, genre=g.name)}
                       for g in sorted(Genre.all())])


@plugin.route('/genre/<section>/<genre>')
def by_genre(section, genre):
    plugin.set_content('movies')
    sf = container.search_filter(sections=[Section[section]], genres=[Genre[genre]])
    make_search(sf)


@plugin.route('/bookmarks', options={'section': None}, name='global_bookmarks')
@plugin.route('/bookmarks/<section>')
def bookmarks_index(section):
    plugin.set_content('movies')
    bookmarks = container.bookmarks()
    media_ids = bookmarks.get(section)
    total = len(media_ids)
    for ids in batch(reversed(media_ids)):
        if abort_requested():
            break
        items = itemify_bookmarks(ids)
        plugin.add_items(items, total)
    plugin.finish(sort_methods=['unsorted', 'title', 'video_year', 'video_rating'], cache_to_disc=False)


@plugin.route('/history/clear')
def clear_history():
    history = container.history()
    history.clear()
    plugin.refresh()


@plugin.route('/history', options={'section': None}, name='global_history')
@plugin.route('/history/<section>')
def history_index(section):
    plugin.set_content('movies')
    history = container.history()
    items = []
    for item in reversed(history.get(section)):
        items.append({
            'label': item.title,
            'thumbnail': item.poster,
            'path': item.path,
            'is_playable': True,
            'context_menu':
                toggle_watched_context_menu() +
                bookmark_context_menu(item.media_id, item.section, item.title) +
                download_torrent_context_menu(item.url) +
                clear_history_context_menu()
        })
    return with_fanart(items)


@plugin.route('/')
def index():
    items = [
        {'label': lang(34000), 'path': plugin.url_for('global_search')},
        {'label': lang(34002), 'path': plugin.url_for('global_bookmarks')},
        {'label': lang(34011), 'path': plugin.url_for('global_history')},
    ]
    items.extend({
        'label': tf.decorate(s.localized, bold=True, color='white'),
        'path': plugin.url_for('explore', section=s.name)
    } for s in Section)
    return with_fanart(items)
