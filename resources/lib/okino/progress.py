# -*- coding: utf-8 -*-

import logging
from util.progress import AbstractFileTransferProgress
from okino.torrent import TorrentStatus


class AbstractTorrentTransferProgress(AbstractFileTransferProgress):
    def __init__(self, name=None, size=-1):
        AbstractFileTransferProgress.__init__(self, name, size)
        self.state = TorrentStatus.QUEUED
        self.download_rate = 0
        self.upload_rate = 0
        self.seeds = 0
        self.peers = 0

    def update_status(self, state, bytes_transferred=0, download_rate=0, upload_rate=0,
                      seeds=0, peers=0, progress=None):
        self.state = state
        self.download_rate = download_rate
        self.upload_rate = upload_rate
        self.seeds = seeds
        self.peers = peers
        self.update_transferred(bytes_transferred, progress=progress)

    @staticmethod
    def _human_rate(rate_kbps):
        human, factor = None, None
        for h, f in (('kB', 0), ('mB', 1024), ('gB', 1024 * 1024)):
            if rate_kbps >= f:
                human = h
                factor = f
            else:
                break
        if not factor:
            return '0'
        else:
            return '%.2f%s/s' % (float(rate_kbps) / float(factor), human)


class LoggingTorrentTransferProgress(AbstractTorrentTransferProgress):
    def __init__(self, name=None, size=-1, log=None):
        AbstractTorrentTransferProgress.__init__(self, name, size)
        self.log = log or logging.getLogger(__name__)

    def open(self):
        self.log.info("Starting transfer of torrent '%s'...", self.name)

    def close(self):
        self.log.info("Finished transfer of torrent '%s'", self.name)

    def is_cancelled(self):
        return False

    def update(self, percent):
        if self.state in [TorrentStatus.DOWNLOADING, TorrentStatus.CHECKING,
                          TorrentStatus.PREBUFFERING, TorrentStatus.SEEDING]:
            self.log.info("%s: %s %d%% (D:%s U:%s P:%d S:%d)", self.name,
                          self.state.localized, percent,
                          self._human_rate(self.download_rate),
                          self._human_rate(self.upload_rate),
                          self.peers, self.seeds)
        else:
            self.log.info("%s: %s %d%%", self.name, self.state.localized, percent)


class DummyTorrentTransferProgress(AbstractTorrentTransferProgress):
    def is_cancelled(self):
        return False

    def update(self, percent):
        pass

    def open(self):
        pass

    def close(self):
        pass
