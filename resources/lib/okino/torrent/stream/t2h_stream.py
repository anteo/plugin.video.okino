# -*- coding: utf-8 -*-

import logging
import time

from torrent2http import Error, State, Engine, MediaType
from okino.common import abort_requested, sleep
from okino.torrent import *
from okino.player import AbstractPlayer
from okino.progress import AbstractTorrentTransferProgress, DummyTorrentTransferProgress
from contextlib import closing, nested


class Torrent2HttpStreamError(TorrentStreamError):
    pass


class Torrent2HttpStream(TorrentStream):
    SLEEP_DELAY = 500

    def __init__(self, engine, buffering_progress=None, playing_progress=None, pre_buffer_bytes=0, log=None,
                 playback_start_timeout=5):
        """
        :type engine: Engine
        :type playing_progress: AbstractTorrentTransferProgress
        :type buffering_progress: AbstractTorrentTransferProgress
        """
        TorrentStream.__init__(self)
        self.engine = engine
        self.log = log or logging.getLogger(__name__)
        self.buffering_progress = buffering_progress or DummyTorrentTransferProgress()
        self.playing_progress = playing_progress or DummyTorrentTransferProgress()
        self.pre_buffer_bytes = pre_buffer_bytes
        self.playback_start_timeout = playback_start_timeout
        self._playing_aborted = False

    @staticmethod
    def _convert_engine_error(error):
        """
        :type error: Error
        """
        if error.code in [error.UNKNOWN_PLATFORM, error.XBMC_HOME_NOT_DEFINED]:
            return Torrent2HttpStreamError(33020, error.message, cause=error)
        elif error.code == error.NOEXEC_FILESYSTEM:
            return Torrent2HttpStreamError(33022, error.message, cause=error)
        elif error.code in [error.PROCESS_ERROR, error.BIND_ERROR, error.POPEN_ERROR]:
            return Torrent2HttpStreamError(33023, error.message, cause=error, check_settings=True)
        elif error.code in [error.REQUEST_ERROR, error.INVALID_FILE_INDEX]:
            return Torrent2HttpStreamError(33024, error.message, cause=error)
        elif error.code == error.INVALID_DOWNLOAD_PATH:
            return Torrent2HttpStreamError(33025, error.message, cause=error, check_settings=True)
        elif error.code == error.TIMEOUT:
            return Torrent2HttpStreamError(33026, error.message, cause=error)
        elif error.code == error.TORRENT_ERROR:
            return Torrent2HttpStreamError(33027, "Torrent error (%s)", error.kwargs['reason'], cause=error)

    @staticmethod
    def _convert_state(state):
        """
        :type state: State
        """
        if state == State.QUEUED_FOR_CHECKING:
            return TorrentStatus.CHECK_PENDING
        elif state == State.CHECKING_FILES:
            return TorrentStatus.CHECKING
        elif state == State.DOWNLOADING_METADATA:
            return TorrentStatus.DOWNLOADING_METADATA
        elif state == State.DOWNLOADING:
            return TorrentStatus.DOWNLOADING
        elif state == State.FINISHED:
            return TorrentStatus.SEEDING
        elif state == State.SEEDING:
            return TorrentStatus.SEEDING
        elif state == State.ALLOCATING:
            return TorrentStatus.ALLOCATING
        elif state == State.CHECKING_RESUME_DATA:
            return TorrentStatus.CHECK_PENDING

    def list(self, torrent):
        """
        :type torrent: Torrent
        """
        self.engine.uri = torrent.url
        files = []
        try:
            with closing(self.engine) as t2h:
                t2h.start()
                while not files:
                    files = t2h.list(media_types=[MediaType.VIDEO])
                    t2h.check_torrent_error()
                    sleep(self.SLEEP_DELAY)
        except Error as e:
            raise self._convert_engine_error(e)
        return [TorrentFile(path=f.name, length=f.size, md5sum=None, index=f.index) for f in files]

    def _aborted(self):
        return abort_requested() or self.buffering_progress.is_cancelled() or \
            self.playing_progress.is_cancelled()

    def play(self, player, torrent, list_item=None, file_id=None):
        """
        :type list_item: dict
        :type torrent: Torrent
        :type player: AbstractPlayer
        """
        list_item = list_item or {}

        try:
            with nested(closing(self.engine),
                        ):
                self.log.info("Starting torrent2http engine...")
                self.engine.uri = torrent.url
                self.engine.start(file_id or 0)
                ready = False
                subtitles = None
                status = None

                if self.pre_buffer_bytes:
                    with closing(self.buffering_progress):
                        self.log.info("Start prebuffering...")
                        self.buffering_progress.open()
                        while not self._aborted():
                            sleep(self.SLEEP_DELAY)
                            status = self.engine.status()
                            self.engine.check_torrent_error(status)
                            if file_id is None:
                                files = self.engine.list(media_types=[MediaType.VIDEO])
                                if files is None:
                                    continue
                                if not files:
                                    raise Torrent2HttpStreamError(33050, "No playable files detected")
                                file_id = files[0].index
                                file_status = files[0]
                                self.log.info("Detected video file: %s", file_status)
                                sub_files = self.engine.list(media_types=[MediaType.SUBTITLES])
                                if sub_files:
                                    self.log.info("Detected subtitles: %s", sub_files[0])
                                    subtitles = sub_files[0].url
                            else:
                                file_status = self.engine.file_status(file_id)
                                if not file_status:
                                    continue
                            if status.state == State.DOWNLOADING:
                                state = TorrentStatus.PREBUFFERING
                                self.buffering_progress.size = self.pre_buffer_bytes
                                if file_status.download >= self.pre_buffer_bytes:
                                    ready = True
                                    break
                            elif status.state in [State.FINISHED, State.SEEDING, State.CHECKING_FILES]:
                                ready = True
                                break
                            else:
                                self.buffering_progress.size = file_status.size
                                state = self._convert_state(status.state)

                            self.buffering_progress.name = status.name
                            self.buffering_progress.update_status(state, file_status.download, status.download_rate,
                                                                  status.upload_rate, status.num_seeds,
                                                                  status.num_peers)
                else:
                    while not self._aborted():
                        sleep(self.SLEEP_DELAY)
                        status = self.engine.status()
                        self.engine.check_torrent_error(status)
                        if status.state in [State.DOWNLOADING, State.FINISHED, State.SEEDING, State.CHECKING_FILES]:
                            ready = True
                            break
                if ready:
                    self.log.info("Starting playback...")
                    with nested(closing(self.playing_progress),
                                player.attached(player.PLAYBACK_PAUSED, self.playing_progress.open),
                                player.attached(player.PLAYBACK_RESUMED, self.playing_progress.close)):
                        list_item.setdefault('label', status.name)
                        file_status = self.engine.file_status(file_id)
                        list_item['path'] = file_status.url
                        self.playing_progress.name = status.name
                        self.playing_progress.size = file_status.size
                        player.play(list_item, subtitles)
                        start = time.time()
                        while not self._aborted() and (player.is_playing()
                                                       or time.time()-start < self.playback_start_timeout):
                            sleep(self.SLEEP_DELAY)
                            status = self.engine.status()
                            file_status = self.engine.file_status(file_id)
                            state = self._convert_state(status.state)
                            self.playing_progress.update_status(state, file_status.download, status.download_rate,
                                                                status.upload_rate, status.num_seeds, status.num_peers)
                            player.get_percent()

                        sleep(self.SLEEP_DELAY)

        except Error as err:
            raise self._convert_engine_error(err)
