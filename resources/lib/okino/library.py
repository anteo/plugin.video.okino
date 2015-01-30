# -*- coding: utf-8 -*-

import os
import logging
from xbmcswift2 import xbmcvfs, direxists
from okino.scraper import Folder, Details
from okino.enumerations import Section
from util.encoding import ensure_str
from plugin import plugin


class LibraryManager:
    def __init__(self, path, storage, log=None):
        self.path = path
        self.storage = storage
        self.log = log or logging.getLogger(__name__)
        self.create_folders()

    def create_folders(self):
        for s in list(Section):
            path = self.get_section_path(s)
            if not direxists(path):
                self.log.info("Creating directory: %s", path)
                xbmcvfs.mkdirs(path)

    def get_section_path(self, section):
        return os.path.join(self.path, section.folder_name)

    @staticmethod
    def clean_path_component(string):
        import re
        return re.sub(r'(?u)[^\w\-]+', ' ', string)

    def get_media_path(self, section, title):
        title = self.clean_path_component(title)
        return os.path.join(self.get_section_path(section), title)

    @staticmethod
    def get_file_name(folder_id, file_name):
        file_name = LibraryManager.clean_path_component(file_name)
        return "%s [%d].strm" % (file_name, folder_id)

    def update_folder(self, details, folder):
        """
        :type details: Details
        :type folder: Folder
        """
        media_path = self.get_media_path(details.section, details.title)
        if not direxists(media_path):
            self.log.info("Creating library folder: %s", media_path)
            xbmcvfs.mkdir(media_path)
        else:
            self.log.info("Updating library folder: %s", media_path)
        self.storage[folder.id] = (details.media_id, media_path)
        files = folder.files
        """ :type : list of File """
        for f in files:
            file_path = os.path.join(media_path, self.get_file_name(folder.id, f.title))
            if not xbmcvfs.exists(file_path):
                self.log.info("Adding file: %s", file_path)
                fp = xbmcvfs.File(file_path, 'w')
                can_mark_watched = len(files) == 1 and not details.section.is_series()
                url = plugin.url_for('play_file', media_id=details.media_id, url=f.link,
                                     title=f.title, can_mark_watched=int(can_mark_watched))
                fp.write(ensure_str(url))
                fp.close()
        return media_path

    def remove_folder(self, folder_id):
        if folder_id not in self.storage:
            return
        media_path = self.storage[folder_id][1]
        del self.storage[folder_id]
        if not direxists(media_path):
            return
        self.log.info("Removing from library folder: %s", media_path)
        files = xbmcvfs.listdir(media_path)[1]
        count_deleted = 0
        for f in files:
            if f.endswith("[%d].strm" % folder_id):
                path = os.path.join(media_path, f)
                self.log.info("Removing file: %s", path)
                xbmcvfs.delete(path)
                count_deleted += 1
        if len(files) == count_deleted:
            self.log.info("All files deleted, removing folder: %s", media_path)
            xbmcvfs.rmdir(media_path)

    def has_folder(self, folder_id):
        if folder_id in self.storage:
            if direxists(self.storage[folder_id][1]):
                return True
            else:
                del self.storage[folder_id]
        return False


def update_library():
    import okino.container as container
    from plugin import plugin
    from okino.common import lang, batch, abort_requested
    from xbmcswift2 import xbmcgui
    from contextlib import closing

    log = logging.getLogger(__name__)
    library_manager = container.library_manager()
    scraper = container.scraper()
    media_ids = []
    for folder_id, item in library_manager.storage.items():
        media_id = item[0]
        if not library_manager.has_folder(folder_id):
            continue
        if media_id not in media_ids:
            media_ids.append(media_id)
    if media_ids:
        log.info("Starting Okino.ru library update...")
        progress = xbmcgui.DialogProgressBG()
        with closing(progress):
            progress.create(lang(30000), lang(40322))
            processed = 0
            for ids in batch(media_ids):
                all_details = scraper.get_details_bulk(ids)
                all_folders = scraper.get_folders_bulk(ids)
                for media_id, details in all_details.items():
                    if media_id in all_folders:
                        for folder in all_folders[media_id]:
                            if library_manager.has_folder(folder.id):
                                library_manager.update_folder(details, folder)
                processed += len(ids)
                progress.update(processed*100/len(media_ids))
                if abort_requested():
                    break
        log.info("Okino.ru library update finished.")
    if plugin.get_setting('update-xbmc-library', bool):
        log.info("Starting XBMC library update...")
        plugin.update_library('video', library_manager.path)
