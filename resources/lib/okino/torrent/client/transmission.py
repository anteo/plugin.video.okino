# -*- coding: utf-8 -*-

import logging
import base64
import json
import urllib2

from okino.torrent import *
from util.httpclient import HttpClient


class TransmissionError(TorrentClientError):
    pass


class TransmissionClient(TorrentClient):
    STATUS_MAPPING = {
        0: TorrentStatus.STOPPED,
        1: TorrentStatus.CHECK_PENDING,
        2: TorrentStatus.CHECKING,
        3: TorrentStatus.DOWNLOAD_PENDING,
        4: TorrentStatus.DOWNLOADING,
        5: TorrentStatus.SEED_PENDING,
        6: TorrentStatus.SEEDING
    }

    def __init__(self, login=None, password=None, host='127.0.0.1', port=9091,
                 path='/transmission', log=None, timeout=5):
        TorrentClient.__init__(self)
        self.log = log or logging.getLogger(__name__)
        self.login = login
        self.password = password
        self.url = 'http://' + host
        if port:
            self.url += ':' + str(port)
        if path[0] != '/':
            # noinspection PyAugmentAssignment
            path = '/' + path
        if path[-1] != '/':
            path += '/'
        self.url += path
        self.http = HttpClient(log=self.log, timeout=timeout)
        self.token = '0'

    def list(self):
        obj = self.action({
            'method': 'torrent-get',
            'arguments': {
                'fields': [
                    'id', 'status', 'name', 'totalSize', 'sizeWhenDone', 'leftUntilDone', 'downloadedEver',
                    'uploadedEver', 'uploadRatio', 'rateUpload', 'rateDownload', 'eta', 'peersConnected',
                    'peersFrom', 'addedDate', 'doneDate', 'downloadDir', 'peersConnected',
                    'peersGettingFromUs', 'peersSendingToUs'
                ]
            }
        })
        res = []
        for r in obj['arguments'].get('torrents', []):
            res.append(TorrentInfo(
                torrent_id=str(r['id']),
                status=self.get_status(r['status']),
                name=r['name'],
                size=r['totalSize'],
                progress=0 if not r['sizeWhenDone'] else int(100.0 * float(r['sizeWhenDone'] - r['leftUntilDone']) /
                                                             float(r['sizeWhenDone'])),
                downloaded=r['downloadedEver'],
                uploaded=r['uploadedEver'],
                upload_rate=r['rateUpload'],
                download_rate=r['rateDownload'],
                ratio=float(r['uploadRatio']),
                eta=r['eta'],
                peers=r['peersConnected'],
                seeds=r['peersSendingToUs'],
                leeches=r['peersGettingFromUs'],
                added=r['addedDate'],
                finished=r['doneDate'],
                download_dir=r['downloadDir']
            ))

        return res

    def add(self, torrent, download_dir, paused=False):
        """
        :type torrent: Torrent
        """
        if torrent.has_data() or torrent.has_file_name():
            self.log.info("Adding torrent from data")
            return self.action({
                'method': 'torrent-add',
                'arguments': {
                    'download-dir': download_dir,
                    'metainfo': base64.b64encode(torrent.data),
                    'paused': paused
                }})
        elif torrent.has_url():
            self.log.info("Adding torrent from url (%s)", torrent.url)
            return self.action({
                'method': 'torrent-add',
                'arguments': {
                    'download-dir': download_dir,
                    'filename': torrent.url,
                    'paused': paused
                }})

    def remove(self, torrent_id, delete_local_data=False):
        self.log.info("Removing torrent %r from queue", torrent_id)
        if not isinstance(torrent_id, list):
            torrent_id = [torrent_id]
        return self.action({
            'method': 'torrent-remove',
            'arguments': {
                'ids': torrent_id,
                'delete-local-data': delete_local_data
            }})

    def action(self, request):
        json_obj = json.dumps(request)

        while True:
            try:
                if self.login:
                    response = self.http.fetch(self.url+'rpc/',
                                               method='POST',
                                               params=json_obj,
                                               headers={'x-transmission-session-id': self.token},
                                               auth_username=self.login,
                                               auth_password=self.password)
                else:
                    response = self.http.fetch(self.url+'rpc/',
                                               method='POST',
                                               params=json_obj,
                                               headers={'x-transmission-session-id': self.token})
                try:
                    return json.loads(response.body)
                except ValueError, e:
                    raise TransmissionError(32010, "Invalid response from Transmission", cause=e)
            except urllib2.URLError, e:
                if isinstance(e, urllib2.HTTPError):
                    # требуется авторизация?
                    if e.code == 401:
                        self.get_auth()
                        continue
                    # требуется новый токен?
                    elif e.code == 409:
                        self.get_token(e.headers)
                        continue
                raise TransmissionError(32011, "Can't connect to Transmission", cause=e, check_settings=True)

    def get_auth(self):
        try:
            self.http.fetch(self.url, auth_username=self.login, auth_password=self.password)
        except urllib2.URLError, e:
            if isinstance(e, urllib2.HTTPError):
                if e.code == 409:
                    self.get_token(e.headers)
                    return
                else:
                    raise TransmissionError(32012, "Can't authenticate in Transmission", cause=e, check_settings=True)
            raise TransmissionError(32011, "Can't connect to Transmission", cause=e, check_settings=True)

    def get_token(self, headers):
        token = headers.get('x-transmission-session-id')
        if not token:
            return False
        self.token = token
        return True

    def get_status(self, code):
        return self.STATUS_MAPPING[code]
