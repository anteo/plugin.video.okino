# -*- coding: utf-8 -*-

from xbmcswift2 import xbmc, xbmcgui
from okino.player import AbstractPlayer
from okino.gui import InfoOverlay, Align
from util.callbacks import Callbacks
from util.progress import AbstractProgress, AbstractFileTransferProgress
from okino.progress import AbstractTorrentTransferProgress
from okino.torrent import TorrentStatus
from okino.common import lang
from okino.plugin import plugin


class XbmcProgress(AbstractProgress):
    def __init__(self, heading):
        AbstractProgress.__init__(self)
        self.dialog = xbmcgui.DialogProgress()
        self.opened = False
        self.heading = heading
        xbmc.sleep(500)

    def open(self):
        if not self.opened:
            self.dialog.create(self.heading)
            self.opened = True

    def close(self):
        if self.opened:
            self.dialog.close()
            self.opened = False

    def is_cancelled(self):
        return self.opened and self.dialog.iscanceled()

    def update(self, percent, *lines):
        self.dialog.update(percent, *lines)


class XbmcFileTransferProgress(AbstractFileTransferProgress):
    def __init__(self, name=None, size=-1, heading=None):
        AbstractFileTransferProgress.__init__(self, name, size)
        self.heading = heading or lang(33000)
        self.handler = XbmcProgress(heading)

    def open(self):
        self.handler.open()

    def close(self):
        self.handler.close()

    def is_cancelled(self):
        return self.handler.is_cancelled()

    def update(self, percent):
        lines = []
        if self.name:
            lines.append(lang(33001) % {'name': self.name})
        size = self._human_size(self.size) if self.size >= 0 else lang(33003)
        lines.append(lang(33002) % ({'transferred': self._human_size(self._transferred_bytes),
                                         'total': size}))
        return self.handler.update(percent, *lines)


class XbmcPlayer(AbstractPlayer):
    # noinspection PyPep8Naming
    class XbmcPlayerWithCallbacks(xbmc.Player, Callbacks):
        def __init__(self, *args, **kwargs):
            xbmc.Player.__init__(self, *args, **kwargs)
            self.duration = 0
            Callbacks.__init__(self)

        def onPlayBackStarted(self):
            self.duration = self.getTotalTime()
            self.run_callbacks('playback_started', duration=self.duration)

        def onPlayBackEnded(self):
            self.run_callbacks('playback_ended')

        def onPlayBackStopped(self):
            self.run_callbacks('playback_stopped')

        def onPlayBackPaused(self):
            self.run_callbacks('playback_paused')

        def onPlayBackResumed(self):
            self.run_callbacks('playback_resumed')

        def onPlayBackSeek(self, time, seekOffset):
            self.run_callbacks('playback_seek', time, seekOffset)

        def onPlayBackSeekChapter(self, chapter):
            self.run_callbacks('playback_seek_chapter', chapter)

        def onPlayBackSpeedChanged(self, speed):
            self.run_callbacks('playback_speed_changed', speed)

        def onQueueNextItem(self):
            self.run_callbacks('queue_next_item')

    def __init__(self):
        super(XbmcPlayer, self).__init__()
        self.player = self.XbmcPlayerWithCallbacks()
        self.time = 0

    def stop(self):
        self.player.stop()

    def pause(self):
        self.player.pause()

    def play(self, item=None, subtitles=None):
        if item is None:
            self.player.play()
        else:
            plugin.set_resolved_url(item, subtitles)

    def is_playing(self):
        return self.player.isPlaying()

    def run_callbacks(self, event, *args, **kwargs):
        self.player.run_callbacks(event, *args, **kwargs)

    def detach(self, event=None, callback=None):
        self.player.detach(event, callback)

    def attach(self, event, callback):
        self.player.attach(event, callback)

    def get_total_time(self):
        return self.player.duration

    def get_time(self):
        try:
            self.time = self.player.getTime()
        except RuntimeError:
            pass
        return self.time


class XbmcTorrentTransferProgress(AbstractTorrentTransferProgress):
    def __init__(self, name=None, size=-1, heading=None):
        AbstractTorrentTransferProgress.__init__(self, name, size)
        heading = heading or lang(33010)
        self.handler = XbmcProgress(heading)

    def open(self):
        self.handler.open()

    def close(self):
        self.handler.close()

    def is_cancelled(self):
        return self.handler.is_cancelled()

    def update(self, percent):
        lines = []
        if self.name is not None:
            lines.append(lang(33011) % {'name': self.name})
        if self.state in [TorrentStatus.DOWNLOADING, TorrentStatus.SEEDING,
                          TorrentStatus.CHECKING, TorrentStatus.PREBUFFERING]:
            size = self._human_size(self.size) if self.size >= 0 else lang(33015)
            lines.append(lang(33013) % {'transferred': self._human_size(self._transferred_bytes),
                                            'total': size,
                                            'state': self.state.localized})
            if self.state != TorrentStatus.CHECKING:
                lines.append(lang(33014) % {'download_rate': self._human_rate(self.download_rate),
                                                'upload_rate': self._human_rate(self.upload_rate),
                                                'peers': self.peers,
                                                'seeds': self.seeds})
        else:
            lines.append(lang(33012) % {'state': self.state.localized})
        return self.handler.update(percent, *lines)


class XbmcOverlayTorrentTransferProgress(AbstractTorrentTransferProgress):
    def __init__(self, name=None, size=-1, overlay=None, window_id=-1):
        """
        :type overlay: InfoOverlay
        """
        AbstractTorrentTransferProgress.__init__(self, name, size)
        self.overlay = overlay or InfoOverlay(window_id, Align.CENTER, 0.8, 0.3)
        self.heading = self.overlay.addLabel(Align.CENTER_X, offsetY=0.05, font="font16")
        self.title = self.overlay.addLabel(Align.CENTER_X, offsetY=0.3, font="font30_title", label=name)
        self.label = self.overlay.addLabel(Align.BOTTOM | Align.CENTER_X, height=0.4)

    def open(self):
        self.overlay.show()

    def close(self):
        self.overlay.hide()

    def is_cancelled(self):
        return False

    def update(self, percent):
        if not self.overlay.visible:
            return
        heading = "%s - %d%%" % (self.state.localized, percent)
        self.heading.setLabel(heading)
        self.title.setLabel(self.name)
        lines = []
        if self.state in [TorrentStatus.DOWNLOADING, TorrentStatus.CHECKING,
                          TorrentStatus.SEEDING, TorrentStatus.PREBUFFERING]:
            size = self._human_size(self.size) if self.size >= 0 else lang(33015)
            lines.append(lang(33016) % {'transferred': self._human_size(self._transferred_bytes),
                                            'total': size})
            if self.state != TorrentStatus.CHECKING:
                lines.append(lang(33014) % {'download_rate': self._human_rate(self.download_rate),
                                                'upload_rate': self._human_rate(self.upload_rate),
                                                'peers': self.peers,
                                                'seeds': self.seeds})
        self.label.setLabel("\n".join(lines))
