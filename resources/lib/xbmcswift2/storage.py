"""
    xbmcswift2.storage
    ~~~~~~~~~~~~~~~~~~

    This module contains persistent storage classes.

    :copyright: (c) 2012 by Jonathan Beluch
    :license: GPLv3, see LICENSE for more details.
"""
import sys
import sqlite3
import os

from xbmcswift2.common import ensure_fs_encoding
from xbmcswift2.logger import log
from UserDict import DictMixin

try:
    from cPickle import dumps, loads
except ImportError:
    from pickle import dumps, loads


def encode(obj):
    """Serialize an object using pickle to a binary format accepted by SQLite."""
    return sqlite3.Binary(dumps(obj))


def decode(obj):
    """Deserialize objects retrieved from SQLite."""
    return loads(bytes(obj))


class Storage(DictMixin):
    """A dict with the ability to persist to disk and TTL for items."""

    CREATE_TABLE = 'CREATE TABLE IF NOT EXISTS %s (key TEXT PRIMARY KEY, value BLOB, expire DATETIME)'
    CREATE_INDEX = 'CREATE INDEX IF NOT EXISTS expire ON %s (expire)'
    GET_LEN = 'SELECT COUNT(*) FROM %s WHERE (expire IS NULL OR expire >= DATETIME("NOW"))'
    GET_MAX = 'SELECT MAX(ROWID) FROM %s WHERE (expire IS NULL OR expire >= DATETIME("NOW"))'
    GET_KEYS = 'SELECT key FROM %s WHERE (expire IS NULL OR expire >= DATETIME("NOW")) ORDER BY rowid'
    GET_VALUES = 'SELECT value FROM %s WHERE (expire IS NULL OR expire >= DATETIME("NOW")) ORDER BY rowid'
    GET_ITEMS = 'SELECT key, value FROM %s WHERE (expire IS NULL OR expire >= DATETIME("NOW")) ORDER BY rowid '
    HAS_ITEM = 'SELECT 1 FROM %s WHERE key = ? AND (expire IS NULL OR expire >= DATETIME("NOW"))'
    GET_ITEM = 'SELECT value FROM %s WHERE key = ? AND (expire IS NULL OR expire >= DATETIME("NOW"))'
    ADD_ITEM_NO_TTL = 'REPLACE INTO %s (key, value, expire) VALUES (?, ?, NULL)'
    ADD_ITEM_TTL = 'REPLACE INTO %s (key, value, expire) VALUES (?, ?, DATETIME("NOW", "+%d SECONDS"))'
    DEL_ITEM = 'DELETE FROM %s WHERE key = ?'
    CLEAR_ALL = 'DELETE FROM %s'
    PURGE_ALL = 'DELETE FROM %s WHERE expire < DATETIME("NOW")'

    def __init__(self, filename, tablename="unnamed", flag="c", ttl=None):
        """
        Initialize a thread-safe sqlite-backed dictionary. The dictionary will
        be a table `tablename` in database file `filename`. A single file (=database)
        may contain multiple tables.
        If no `filename` is given, a random file in temp will be used (and deleted
        from temp once the dict is closed/deleted).
        If you enable `autocommit`, changes will be committed after each operation
        (more inefficient but safer). Otherwise, changes are committed on `self.commit()`,
        `self.clear()` and `self.close()`.
        Set `journal_mode` to 'OFF' if you're experiencing sqlite I/O problems
        or if you need performance and don't care about crash-consistency.
        The `flag` parameter:
          'c': default mode, open for read/write, creating the db/table if necessary.
          'w': open for r/w, but drop `tablename` contents first (start with empty table)
          'n': create a new database (erasing any existing tables, not just `tablename`!).

        TTL if provided should be in seconds.
        """
        self.ttl = ttl
        self.filename = filename
        filename = ensure_fs_encoding(filename)
        if flag == 'n':
            if os.path.exists(filename):
                os.remove(filename)

        dirname = os.path.dirname(filename)
        if dirname and not os.path.exists(dirname):
            raise RuntimeError('Error! The directory does not exist, %s' % self.filename)

        self.tablename = tablename

        log.debug("Opening Sqlite table %r in %s" % (tablename, self.filename))
        self.conn = sqlite3.connect(self.filename)
        try:
            self._execute(self.CREATE_TABLE % self.tablename)
            self._execute(self.CREATE_INDEX % self.tablename)
            self.conn.commit()
            if flag == 'w':
                self.clear()
        except sqlite3.DatabaseError:
            self.close()
            raise

    def _execute(self, sql, params=()):
        c = self.conn.cursor()
        if params:
            log.debug("%s ? %s", sql, params)
        else:
            log.debug(sql)
        c.execute(sql, params)
        return c

    def __enter__(self):
        return self

    # noinspection PyUnusedLocal
    def __exit__(self, *exc_info):
        self.close()

    def __str__(self):
        return "Storage(%s)" % self.filename

    def __repr__(self):
        return str(self)  # no need of something complex

    def __len__(self):
        # `select count (*)` is super slow in sqlite (does a linear scan!!)
        # As a result, len() is very slow too once the table size grows beyond trivial.
        # We could keep the total count of rows ourselves, by means of triggers,
        # but that seems too complicated and would slow down normal operation
        # (insert/delete etc).
        sql = self.GET_LEN % self.tablename
        c = self._execute(sql)
        rows = c.fetchone()
        return rows[0] if rows is not None else 0

    def __nonzero__(self):
        # No elements is False, otherwise True
        sql = self.GET_MAX % self.tablename
        c = self._execute(sql)
        m = c.fetchone()[0]
        # Explicit better than implicit and bla bla
        return True if m is not None else False

    def keys(self):
        sql = self.GET_KEYS % self.tablename
        c = self._execute(sql)
        return [key[0] for key in c]

    def values(self):
        sql = self.GET_VALUES % self.tablename
        c = self._execute(sql)
        return [decode(value[0]) for value in c]

    def items(self):
        sql = self.GET_ITEMS % self.tablename
        c = self._execute(sql)
        return [(key, decode(value)) for key, value in c]

    def iterkeys(self):
        for k in self.keys():
            yield k

    def itervalues(self):
        for v in self.values():
            yield v

    def iteritems(self):
        for kv in self.iteritems():
            yield kv

    def __contains__(self, key):
        sql = self.HAS_ITEM % self.tablename
        c = self._execute(sql, (key,))
        return c.fetchone() is not None

    def __getitem__(self, key):
        sql = self.GET_ITEM % self.tablename
        c = self._execute(sql, (key,))
        item = c.fetchone()
        if item is None:
            raise KeyError(key)
        return decode(item[0])

    def __setitem__(self, key, value):
        if self.ttl:
            sql = self.ADD_ITEM_TTL % (self.tablename, self.ttl)
        else:
            sql = self.ADD_ITEM_NO_TTL % self.tablename
        self._execute(sql, (key, encode(value)))

    def __delitem__(self, key):
        if key not in self:
            raise KeyError(key)
        sql = self.DEL_ITEM % self.tablename
        self._execute(sql, (key,))

    def update(self, items=(), **kwds):
        try:
            items = [(k, encode(v)) for k, v in items.items()]
        except AttributeError:
            pass

        if self.ttl:
            sql = self.ADD_ITEM_TTL % (self.tablename, self.ttl)
        else:
            sql = self.ADD_ITEM_NO_TTL % self.tablename
        log.info("%s (%s)", sql, items)
        self.conn.executemany(sql, items)
        if kwds:
            self.update(kwds)

    def __iter__(self):
        return iter(self.keys())

    def clear(self):
        # avoid VACUUM, as it gives "OperationalError: database schema has changed"
        sql = self.CLEAR_ALL % self.tablename
        self.conn.commit()
        self._execute(sql)
        self.conn.commit()

    def purge(self):
        sql = self.PURGE_ALL % self.tablename
        self.conn.commit()
        self._execute(sql)
        self.conn.commit()

    def commit(self):
        if self.conn is not None:
            self.conn.commit()
    sync = commit

    def close(self):
        log.debug("Closing %s" % self)
        if self.conn is not None:
            self.conn.close()
            self.conn = None

    def terminate(self):
        """Delete the underlying database file. Use with care."""
        self.close()

        if self.filename == ':memory:':
            return

        log.info("Deleting %s" % self.filename)
        try:
            os.remove(self.filename)
        except IOError:
            _, e, _ = sys.exc_info()  # python 2.5: "Exception as e"
            log.warning("Failed to delete %s: %s" % (self.filename, str(e)))

    def __del__(self):
        # like close(), but assume globals are gone by now (such as the logger)
        # noinspection PyBroadException
        try:
            if self.conn is not None:
                self.conn.close()
                self.conn = None
        except:
            pass
