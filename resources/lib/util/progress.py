# -*- coding: utf-8 -*-

import logging


class AbstractProgress:
    def __init__(self):
        pass

    def open(self):
        raise NotImplemented

    def close(self):
        raise NotImplemented

    def is_cancelled(self):
        raise NotImplemented

    def update(self, percent):
        raise NotImplemented


class AbstractFileTransferProgress (AbstractProgress):
    def __init__(self, name=None, size=-1):
        AbstractProgress.__init__(self)
        self._transferred_bytes = 0
        self.name = name
        self.size = size

    def open(self):
        raise NotImplemented

    def close(self):
        raise NotImplemented

    def is_cancelled(self):
        raise NotImplemented

    def _get_percent(self, read_bytes):
        if self.size < 0:
            return 1
        else:
            return int(round(float(read_bytes) / (float(self.size) / 100.0)))

    @staticmethod
    def _human_size(size):
        human, factor = None, None
        for h, f in (('Kb', 1024), ('Mb', 1024 * 1024), ('Gb', 1024 * 1024 * 1024), ('Tb', 1024 * 1024 * 1024 * 1024)):
            if size / f > 0:
                human = h
                factor = f
            else:
                break
        if human is None:
            return ('%.1f%s' % (size, 'b')).replace('.0', '')
        else:
            return '%.2f%s' % (float(size) / float(factor), human)

    def update_transferred(self, bytes_count, progress=None):
        self._transferred_bytes = bytes_count
        self.update(progress or self._get_percent(bytes_count))


class LoggingFileTransferProgress(AbstractFileTransferProgress):
    def __init__(self, name=None, size=-1, log=None):
        AbstractFileTransferProgress.__init__(self, name, size)
        self.log = log or logging.getLogger(__name__)

    def open(self):
        self.log.info("Starting transfer of file"+(" '%s'" % self.name if self.name else "")+"...")

    def close(self):
        self.log.info("Finished transfer of file"+(" '%s'" % self.name if self.name else "")+".")

    def is_cancelled(self):
        return False

    def update(self, percent):
        self.log.info("File"+(" '%s'" % self.name if self.name else "")+" transfer progress: %d%% (%s / %s)",
                      percent, self._human_size(self._transferred_bytes), self._human_size(self.size))
