# -*- coding: utf-8 -*-


from collections import namedtuple


class WatchedItems:
    def __init__(self, storage):
        """
        :type storage: dict
        """
        self.watched = storage

    def mark(self, media_id, watched=True, date_added=None, total_size=None):
        if not watched:
            del self.watched[media_id]
        else:
            d = self.watched.get(media_id, {})
            if date_added:
                d['date_added'] = date_added
            if total_size:
                d['total_size'] = total_size
            self.watched[media_id] = d

    def is_watched(self, media_id, date_added=None, total_size=None):
        if media_id not in self.watched:
            return False
        d = self.watched[media_id]
        if date_added:
            if 'date_added' not in d:
                d['date_added'] = date_added
            elif date_added != d['date_added']:
                del self.watched[media_id]
                return False
        if total_size:
            if 'total_size' not in d:
                d['total_size'] = total_size
            elif total_size != d['total_size']:
                del self.watched[media_id]
                return False
        self.watched[media_id] = d
        return True

    def __contains__(self, media_id):
        return self.is_watched(media_id)


Bookmark = namedtuple('Bookmark', ['media_id', 'section'])


class Bookmarks:
    def __init__(self, storage):
        """
        :type storage: dict
        """
        self.storage = storage
        self.bookmarks = storage.get('bookmarks', [])

    def save(self):
        self.storage['bookmarks'] = self.bookmarks

    def add(self, media_id, section):
        self.bookmarks.append(Bookmark(media_id, section))
        self.save()

    def delete(self, media_id):
        for b in self.bookmarks:
            if b.media_id == media_id:
                self.bookmarks.remove(b)
                self.save()
                break

    def get(self, section=None):
        return [b.media_id for b in self.bookmarks if not section or b.section == section]

    def __contains__(self, media_id):
        return any(media_id == b.media_id for b in self.bookmarks)


HistoryItem = namedtuple('HistoryItem', ['media_id', 'section', 'title', 'path', 'url', 'poster'])


class HistoryItems:
    def __init__(self, storage, max_items):
        """
        :type storage: dict
        """
        self.storage = storage
        self.items = storage.get('history_items', [])
        self.max_items = max_items

    def save(self):
        self.storage['history_items'] = self.items

    def add(self, media_id, section, title, path, url, poster):
        old = next((item for item in self.items if item.path == path), None)
        if old:
            self.items.remove(old)
        self.items.append(HistoryItem(media_id, section, title, path, url, poster))
        items = self.get(section)
        old_count = len(items) - self.max_items
        if old_count > 0:
            for item in items[:old_count]:
                self.items.remove(item)
        self.save()

    def get(self, section=None):
        """
        :rtype : list[HistoryItem]
        """
        res = [item for item in self.items if not section or item.section == section]
        if section:
            return res
        else:
            return res[-self.max_items:]

    def clear(self):
        del self.items[:]
        self.save()
