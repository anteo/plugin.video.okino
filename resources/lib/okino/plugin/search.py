# -*- coding: utf-8 -*-
from okino import container as container
from okino.common import lang, batch, abort_requested, notify
from okino.enumerations import Section
from okino.plugin import plugin
from okino.plugin.common import with_fanart, itemify_search_results, itemify_single_result
from okino.scraper import Details
from util.encoding import ensure_unicode
from xbmcswift2 import actions


@plugin.route('/search/clear')
def clear_search_history():
    storage = container.search_storage()
    del storage['search_recent']
    plugin.refresh()


@plugin.route('/search/delete/<name>')
def delete_search(name):
    storage = container.search_storage()
    if 'search_recent' in storage:
        recent = storage['search_recent']
        recent.remove(str(name))
        storage['search_recent'] = recent
    plugin.refresh()


@plugin.route('/search/<section>/new')
def new_search(section):
    storage = container.search_storage()
    if 'search_term' in storage:
        value = storage['search_term']
    else:
        value = plugin.keyboard(heading=lang(40310))
        if not value:
            return
        storage['search_term'] = value
    plugin.redirect(plugin.url_for('do_search', section=section, name=value, new=True))


@plugin.route('/search/<section>/do/<name>')
def do_search(section, name):
    plugin.set_content('movies')
    sections = [Section.find(section)] if section != '__ALL__' else list(Section)
    sf = container.search_filter(sections=sections, name=str(name))
    if not make_search(sf):
        notify(lang(40312) % ensure_unicode(name))
    elif plugin.request.arg('new'):
        storage = container.search_storage()
        recent = storage.get('search_recent', [])
        if name in recent:
            recent.remove(name)
        recent.append(name)
        storage['search_recent'] = recent
        count = plugin.get_setting('search-items-count', int)
        if len(recent) > count:
            del recent[:len(recent)-count]


@plugin.route('/search', name='global_search', options={'section': "__ALL__"})
@plugin.route('/search/<section>')
def search_index(section):
    storage = container.search_storage()
    if 'search_term' in storage:
        del storage['search_term']
    context_menu = [
        (lang(40309), actions.background(plugin.url_for('clear_search_history')))
    ]
    items = [{
        'label': lang(34009),
        'path': plugin.url_for('new_search', section=section),
        'context_menu': context_menu,
        'replace_context_menu': True,
    }, {
        'label': lang(34010),
        'path': plugin.url_for('advanced_search', section=section),
        'context_menu': context_menu,
        'replace_context_menu': True,
    }]
    if 'search_recent' in storage:
        items.extend([{
            'label': s,
            'path': plugin.url_for('do_search', section=section, name=s),
            'context_menu': context_menu + [
                (lang(40311), actions.background(plugin.url_for('delete_search', name=s)))
            ],
            'replace_context_menu': True,
        } for s in reversed(storage['search_recent'])])
    plugin.finish(with_fanart(items))


def make_search(sf, header=None, cache_to_disc=False, update_listing=False):
    skip = plugin.request.arg('skip')
    scraper = container.scraper()
    results = scraper.search_cached(sf, skip)
    if not results:
        return False
    if isinstance(results, Details):
        if header:
            plugin.add_items(with_fanart(header))
        item = itemify_single_result(results)
        plugin.finish(items=[item], cache_to_disc=cache_to_disc, update_listing=update_listing)
        return True

    total = len(results)
    items = []
    if skip:
        skip_prev = max(skip - sf.page_size, 0)
        total += 1
        items.append({
            'label': lang(34003),
            'path': plugin.request.url_with_params(skip=skip_prev)
        })
    elif header:
        items.extend(header)
        total += len(header)
    plugin.add_items(with_fanart(items), total)
    for batch_res in batch(results):
        if abort_requested():
            break
        items = itemify_search_results(batch_res)
        plugin.add_items(items, total)
    items = []
    if scraper.has_more:
        skip_next = (skip or 0) + sf.page_size
        items.append({
            'label': lang(34004),
            'path': plugin.request.url_with_params(skip=skip_next)
        })
    plugin.finish(items=with_fanart(items),
                  sort_methods=['unsorted', 'date', 'title', 'video_year', 'video_rating'],
                  cache_to_disc=cache_to_disc,
                  update_listing=update_listing or skip is not None)
    return True