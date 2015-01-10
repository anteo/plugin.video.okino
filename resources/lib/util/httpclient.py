# -*- coding: utf-8 -*-

import time
import locale
import os
import re
import logging
import urllib
import urllib2
import cookielib
import base64
import mimetools
import itertools
import gzip

from StringIO import StringIO
from contextlib import closing
from progress import LoggingFileTransferProgress


class HttpClient:
    USER_AGENT = "Mozilla/5.0 (Windows NT 6.2; Win64; x64; rv:16.0.1) Gecko/20121011 Firefox/16.0.1"
    RECOVERABLE_CODES = [500, 502, 503, 504]
    CONTENT_DISPOSITION_RE = re.compile('attachment;\sfilename="*([^"\s]+)"|\s')
    DOWNLOAD_BUFFER_SIZE = 1024 * 128

    def __init__(self, log=None, progress=None, cookie_jar=None, **request_params):
        self.log = log or logging.getLogger(__name__)
        self.progress = progress or LoggingFileTransferProgress(log=self.log)
        self.cookie_jar = self._cookie_jar(cookie_jar)
        self.request_params = request_params

    @staticmethod
    def _cookie_jar(cookie_jar):
        if isinstance(cookie_jar, basestring):
            cookie_jar = cookielib.MozillaCookieJar(cookie_jar)
        if isinstance(cookie_jar, cookielib.FileCookieJar) and os.path.exists(cookie_jar.filename):
            cookie_jar.load()
        return cookie_jar

    def fetch(self, request, **request_params):
        if not isinstance(request, HttpRequest):
            params = self.request_params
            params.update(request_params)
            request = HttpRequest(request, **params)

        opener = self._build_opener(request)
        response = HttpResponse(request)
        tries = request.tries

        while tries > 0:
            tries -= 1
            self.log.info('Making %r', request)
            try:
                self._fetch(opener, request, response)
                break
            except urllib2.HTTPError, e:
                if e.code in self.RECOVERABLE_CODES and tries > 0:
                    self.log.info("%s, retrying in %d second(s)...", e, request.retry_timeout)
                    time.sleep(request.retry_timeout)
                    continue
                raise
            except urllib2.URLError, e:
                self._decode_reason(e)
                raise

        response.time = time.time() - response.time
        self.log.debug("Returned %r", response)
        return response

    @staticmethod
    def _decode_reason(e):
        if e.reason:
            os_encoding = locale.getpreferredencoding()
            e.reason = str(e.reason).decode(os_encoding)

    def _build_opener(self, request):
        """
        :type request: HttpRequest
        :rtype: urllib2.OpenerDirector
        """

        handlers = [urllib2.HTTPHandler()]
        if request.handle_redirects:
            handlers.append(urllib2.HTTPRedirectHandler())

        if request.proxy_host and request.proxy_port:
            handlers.append(
                urllib2.ProxyHandler({request.proxy_protocol or 'http': request.proxy_host + ':' +
                                     str(request.proxy_port)}))

            if request.proxy_username:
                proxy_auth_handler = urllib2.ProxyBasicAuthHandler()
                proxy_auth_handler.add_password('realm', 'uri', request.proxy_username, request.proxy_password)
                handlers.append(proxy_auth_handler)

        if self.cookie_jar is not None:
            handlers.append(urllib2.HTTPCookieProcessor(self.cookie_jar))

        return urllib2.build_opener(*handlers)

    def _fetch(self, opener, request, response):
        """
        :type opener: urllib2.OpenerDirector
        :type request: HttpRequest
        :type response: HttpResponse
        """
        params = request.params or {}

        if request.upload_files:
            boundary, upload = self._upload(request.upload_files, params)
            req = urllib2.Request(request.url)
            req.add_data(upload)
            req.add_header('Content-type', 'multipart/form-data; boundary=%s' % boundary)
            req.add_header('Content-length', len(upload))
        else:
            if request.method == 'POST':
                if isinstance(params, dict) or isinstance(params, list):
                    params = urllib.urlencode(params)
                req = urllib2.Request(request.url, params)
            else:
                req = urllib2.Request(request.url)

        req.add_header('User-Agent', request.user_agent or self.USER_AGENT)
        if request.use_gzip:
            req.add_header('Accept-encoding', 'gzip')
        if request.headers:
            for key, value in request.headers.iteritems():
                req.add_header(key, value)

        if request.auth_username and request.auth_password:
            auth_str = ':'.join([request.auth_username, request.auth_password])
            req.add_header('Authorization', 'Basic %s' % base64.encodestring(auth_str).strip())

        with closing(opener.open(req, timeout=request.timeout)) as conn:
            response.headers = self._headers(conn.info())

            if conn.geturl() != request.url:
                response.redirected_to = conn.geturl()

            if request.download_path:
                self._download(request.download_path, conn, response)
            else:
                response.body = conn.read()
                if 'content-encoding' in response.headers and response.headers['content-encoding'] == 'gzip':
                    buf = StringIO(response.body)
                    f = gzip.GzipFile(fileobj=buf)
                    response.body = f.read()

        if isinstance(self.cookie_jar, cookielib.FileCookieJar):
            self.cookie_jar.save()

    def _download(self, download_path, conn, response):
        """
        :type download_path: str
        :type conn:
        :param response:
        :return:
        """
        download_path = os.path.abspath(download_path)
        fd = open(download_path, 'wb')

        bs = self.DOWNLOAD_BUFFER_SIZE
        size = -1
        read = 0
        name = None
        progress = self.progress

        if 'content-length' in response.headers:
            size = int(response.headers['content-length'])
        if 'content-disposition' in response.headers:
            r = self.CONTENT_DISPOSITION_RE.search(response.headers['content-disposition'])
            if r:
                name = urllib.unquote(r.group(1))
        name = name or os.path.basename(download_path)
        self.log.info("Starting download of '%s' to %s", name, download_path)

        aborted = False
        if progress:
            with closing(progress):
                progress.file_name = name
                progress.size = size
                progress.open()

                while not aborted:
                    buf = conn.read(bs)
                    if not len(buf):
                        break
                    read += len(buf)
                    fd.write(buf)

                    progress.update_transferred(read)
                    if progress.is_cancelled():
                        aborted = True
        else:
            while True:
                buf = conn.read(bs)
                if not len(buf):
                    break
                read += len(buf)
                fd.write(buf)

        if aborted:
            self.log.info("File '%s' transfer aborted!", name)
            response.filename = None
        else:
            self.log.info("File '%s' successfully downloaded.", name)
            response.filename = download_path

    def _upload(self, upload_files, params):
        res = []
        boundary = mimetools.choose_boundary()
        part_boundary = '--' + boundary

        if params:
            for name, value in params.iteritems():
                res.append([part_boundary, 'Content-Disposition: form-data; name="%s"' % name, '', value])

        self.log.info("Uploading files: %r", [i['name'] for i in upload_files])
        for obj in upload_files:
            name = obj.get('name')
            filename = obj.get('filename', 'default')
            content_type = obj.get('content-type')

            try:
                body = obj['body'].read()
            except AttributeError:
                body = obj['body']

            if content_type:
                res.append([part_boundary,
                            'Content-Disposition: file; name="%s"; filename="%s"' % (name, urllib.quote(filename)),
                            'Content-Type: %s' % content_type, '', body])
            else:
                res.append([part_boundary,
                            'Content-Disposition: file; name="%s"; filename="%s"' % (name, urllib.quote(filename)), '',
                            body])

        result = list(itertools.chain(*res))
        result.append('--' + boundary + '--')
        result.append('')
        return boundary, '\r\n'.join(result)

    @staticmethod
    def _headers(raw):
        headers = {}
        for line in raw.headers:
            pair = line.split(':', 1)
            if len(pair) == 2:
                tag = pair[0].lower().strip()
                value = pair[1].strip()
                if tag and value:
                    headers[tag] = value
        return headers


class HttpRequest:
    METHOD_GET = "GET"
    METHOD_POST = "POST"

    def __init__(self, url, method='GET', headers=None, params=None, upload_files=None,
                 download_path=None, auth_username=None, auth_password=None, proxy_protocol=None, proxy_host=None,
                 proxy_port=None, proxy_username=None, proxy_password=None, timeout=None, handle_redirects=True,
                 user_agent=None, tries=1, retry_timeout=1, use_gzip=True):

        self.url = url
        self.method = method
        self.headers = headers

        self.params = params

        if isinstance(upload_files, dict):
            upload_files = [upload_files]

        self.upload_files = upload_files
        self.download_path = download_path

        self.auth_username = auth_username
        self.auth_password = auth_password

        self.proxy_protocol = proxy_protocol
        self.proxy_host = proxy_host
        self.proxy_port = proxy_port
        self.proxy_username = proxy_username
        self.proxy_password = proxy_password

        self.timeout = timeout

        self.handle_redirects = handle_redirects

        self.tries = tries
        self.retry_timeout = retry_timeout
        self.user_agent = user_agent
        self.use_gzip = use_gzip

    def __repr__(self):
        args = ','.join('%s=%r' % i for i in self.__dict__.iteritems() if i[1] is not None and i[0] != 'upload_files')
        if self.upload_files:
            upload_files = [dict(i, body='<body>') for i in self.upload_files]
            args += ",upload_files=%r" % upload_files
        return '%s(%s)' % (self.__class__.__name__, args)


class HttpResponse:
    def __init__(self, request):
        self.request = request
        self.headers = {}
        self.body = None
        self.filename = None
        self.redirected_to = None
        self.time = time.time()

    def __repr__(self):
        args = ','.join('%s=%r' % i for i in self.__dict__.iteritems()
                        if i[0] != 'body' and i[0] != 'request' and i[1] is not None)
        return '%s(%s)' % (self.__class__.__name__, args)
