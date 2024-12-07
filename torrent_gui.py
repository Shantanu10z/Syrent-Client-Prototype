#!/usr/bin/env python3

import argparse
import asyncio
import logging
import os
import sys
import subprocess
from contextlib import closing
from functools import partial, partialmethod
from math import floor
from typing import Dict, List, Optional

from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QIcon, QFont, QDropEvent
from PyQt5.QtWidgets import (
    QWidget, QListWidget, QAbstractItemView, QLabel, QVBoxLayout, QProgressBar,
    QListWidgetItem, QMainWindow, QApplication, QFileDialog, QMessageBox,
    QDialog, QDialogButtonBox, QTreeWidget, QTreeWidgetItem, QHeaderView,
    QHBoxLayout, QPushButton, QLineEdit, QAction, QInputDialog
)

from theme import get_stylesheet
from torrent_client.control import ControlManager, ControlServer, ControlClient
from torrent_client.models import TorrentState, TorrentInfo, FileTreeNode, FileInfo
from torrent_client.utils import humanize_speed, humanize_time, humanize_size

logging.basicConfig(format='%(levelname)s %(asctime)s %(name)-23s %(message)s', datefmt='%H:%M:%S')

ICON_DIRECTORY = os.path.join(os.path.dirname(__file__), 'icons')

def load_icon(name: str):
    return QIcon(os.path.join(ICON_DIRECTORY, name + '.svg'))

file_icon = load_icon('file')
directory_icon = load_icon('directory')

def get_directory(directory: Optional[str]):
    return directory if directory is not None else os.getcwd()

class TorrentAddingDialog(QDialog):
    SELECTION_LABEL_FORMAT = 'Selected {} files ({})'

    def _traverse_file_tree(self, name: str, node: FileTreeNode, parent: QWidget):
        item = QTreeWidgetItem(parent)
        item.setCheckState(0, Qt.Checked)
        item.setText(0, name)
        if isinstance(node, FileInfo):
            item.setText(1, humanize_size(node.length))
            item.setIcon(0, file_icon)
            self._file_items.append((node, item))
            return

        item.setIcon(0, directory_icon)
        for name, child in node.items():
            self._traverse_file_tree(name, child, item)

    def _get_directory_browse_widget(self):
        widget = QWidget()
        hbox = QHBoxLayout(widget)
        hbox.setContentsMargins(0, 0, 0, 0)

        self._path_edit = QLineEdit(self._download_dir)
        self._path_edit.setReadOnly(True)
        hbox.addWidget(self._path_edit, 3)

        browse_button = QPushButton('Browse...')
        browse_button.clicked.connect(self._browse)
        hbox.addWidget(browse_button, 1)

        widget.setLayout(hbox)
        return widget

    def _browse(self):
        new_download_dir = QFileDialog.getExistingDirectory(self, 'Select download directory', self._download_dir)
        if not new_download_dir:
            return

        self._download_dir = new_download_dir
        self._path_edit.setText(new_download_dir)

    def __init__(self, parent: QWidget, filename: str, torrent_info: TorrentInfo,
                 control_thread: 'ControlManagerThread'):
        super().__init__(parent)
        self._torrent_info = torrent_info
        download_info = torrent_info.download_info
        self._control_thread = control_thread
        self._control = control_thread.control

        vbox = QVBoxLayout(self)

        self._download_dir = get_directory(self._control.last_download_dir)
        vbox.addWidget(QLabel('Download directory:'))
        vbox.addWidget(self._get_directory_browse_widget())

        vbox.addWidget(QLabel('Announce URLs:'))

        url_tree = QTreeWidget()
        url_tree.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        url_tree.header().close()
        vbox.addWidget(url_tree)
        for i, tier in enumerate(torrent_info.announce_list):
            tier_item = QTreeWidgetItem(url_tree)
            tier_item.setText(0, 'Tier {}'.format(i + 1))
            for url in tier:
                url_item = QTreeWidgetItem(tier_item)
                url_item.setText(0, url)
        url_tree.expandAll()
        vbox.addWidget(url_tree, 1)

        file_tree = QTreeWidget()
        file_tree.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        file_tree.setHeaderLabels(('Name', 'Size'))
        file_tree.header().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self._file_items = []
        self._traverse_file_tree(download_info.suggested_name, download_info.file_tree, file_tree)
        file_tree.sortItems(0, Qt.AscendingOrder)
        file_tree.expandAll()
        file_tree.itemClicked.connect(self._update_checkboxes)
        vbox.addWidget(file_tree, 3)

        self._selection_label = QLabel(TorrentAddingDialog.SELECTION_LABEL_FORMAT.format(
            len(download_info.files), humanize_size(download_info.total_size)))
        vbox.addWidget(self._selection_label)

        self._button_box = QDialogButtonBox(self)
        self._button_box.setOrientation(Qt.Horizontal)
        self._button_box.setStandardButtons(QDialogButtonBox.Cancel | QDialogButtonBox.Ok)
        self._button_box.button(QDialogButtonBox.Ok).clicked.connect(self.submit_torrent)
        self._button_box.button(QDialogButtonBox.Cancel).clicked.connect(self.close)
        vbox.addWidget(self._button_box)

        self.setFixedSize(450, 550)
        self.setWindowTitle('Adding "{}"'.format(filename))

    def _set_check_state_to_tree(self, item: QTreeWidgetItem, check_state: Qt.CheckState):
        for i in range(item.childCount()):
            child = item.child(i)
            child.setCheckState(0, check_state)
            self._set_check_state_to_tree(child, check_state)

    def _update_checkboxes(self, item: QTreeWidgetItem, column: int):
        if column != 0:
            return

        new_check_state = item.checkState(0)
        self._set_check_state_to_tree(item, new_check_state)

        while True:
            item = item.parent()
            if item is None:
                break

            has_checked_children = False
            has_partially_checked_children = False
            has_unchecked_children = False
            for i in range(item.childCount()):
                state = item.child(i).checkState(0)
                if state == Qt.Checked:
                    has_checked_children = True
                elif state == Qt.PartiallyChecked:
                    has_partially_checked_children = True
                else:
                    has_unchecked_children = True

            if not has_partially_checked_children and not has_unchecked_children:
                new_state = Qt.Checked
            elif has_checked_children or has_partially_checked_children:
                new_state = Qt.PartiallyChecked
            else:
                new_state = Qt.Unchecked
            item.setCheckState(0, new_state)

        self._update_selection_label()

    def _update_selection_label(self):
        selected_file_count = 0
        selected_size = 0
        for node, item in self._file_items:
            if item.checkState(0) == Qt.Checked:
                selected_file_count += 1
                selected_size += node.length

        ok_button = self._button_box.button(QDialogButtonBox.Ok)
        if not selected_file_count:
            ok_button.setEnabled(False)
            self._selection_label.setText('Nothing to download')
        else:
            ok_button.setEnabled(True)
            self._selection_label.setText(TorrentAddingDialog.SELECTION_LABEL_FORMAT.format(
                selected_file_count, humanize_size(selected_size)))

    def submit_torrent(self):
        self._torrent_info.download_dir = self._download_dir
        self._control.last_download_dir = os.path.abspath(self._download_dir)

        file_paths = []
        for node, item in self._file_items:
            if item.checkState(0) == Qt.Checked:
                file_paths.append(node.path)
        if not self._torrent_info.download_info.single_file_mode:
            self._torrent_info.download_info.select_files(file_paths, 'whitelist')

        self._control_thread.loop.call_soon_threadsafe(self._control.add, self._torrent_info)

        self.close()

class TorrentListWidgetItem(QWidget):
    _name_font = QFont()
    _name_font.setBold(True)

    _stats_font = QFont()
    _stats_font.setPointSize(10)

    def __init__(self):
        super().__init__()
        vbox = QVBoxLayout(self)

        self._name_label = QLabel()
        self._name_label.setFont(TorrentListWidgetItem._name_font)
        vbox.addWidget(self._name_label)

        self._upper_status_label = QLabel()
        self._upper_status_label.setFont(TorrentListWidgetItem._stats_font)
        vbox.addWidget(self._upper_status_label)

        self._progress_bar = QProgressBar()
        self._progress_bar.setFixedHeight(15)
        self._progress_bar.setMaximum(1000)
        vbox.addWidget(self._progress_bar)

        self._lower_status_label = QLabel()
        self._lower_status_label.setFont(TorrentListWidgetItem._stats_font)
        vbox.addWidget(self._lower_status_label)

        self._state = None
        self._waiting_control_action = False

    @property
    def state(self) -> TorrentState:
        return self._state

    @state.setter
    def state(self, state: TorrentState):
        self._state = state
        self._update()

    @property
    def waiting_control_action(self) -> bool:
        return self._waiting_control_action

    @waiting_control_action.setter
    def waiting_control_action(self, value: bool):
        self._waiting_control_action = value
        self._update()

    def _update(self):
        state = self._state

        self._name_label.setText(state.suggested_name)

        if state.downloaded_size < state.selected_size:
            status_text = '{} of {}'.format(humanize_size(state.downloaded_size), humanize_size(state.selected_size))
        else:
            status_text = '{} (complete)'.format(humanize_size(state.selected_size))
        status_text += ', Ratio: {:.1f}'.format(state.ratio)
        self._upper_status_label.setText(status_text)

        self._progress_bar.setValue(floor(state.progress * 1000))

        if self.waiting_control_action:
            status_text = 'Waiting'
        elif state.paused:
            status_text = 'Paused'
        elif state.complete:
            status_text = 'Uploading to {} of {} peers'.format(state.uploading_peer_count, state.total_peer_count)
            if state.upload_speed:
                status_text += ' on {}'.format(humanize_speed(state.upload_speed))
        else:
            status_text = 'Downloading from {} of {} peers'.format(
                state.downloading_peer_count, state.total_peer_count)
            if state.download_speed:
                status_text += ' on {}'.format(humanize_speed(state.download_speed))
            eta_seconds = state.eta_seconds
            if eta_seconds is not None:
                status_text += ', {} remaining'.format(humanize_time(eta_seconds) if eta_seconds is not None else None)
        self._lower_status_label.setText(status_text)

class TorrentListWidget(QListWidget):
    files_dropped = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.setAcceptDrops(True)

    def drag_handler(self, event: QDropEvent, drop: bool = False):
        if event.mimeData().hasUrls():
            event.setDropAction(Qt.CopyAction)
            event.accept()
            if drop:
                self.files_dropped.emit([url.toLocalFile() for url in event.mimeData().urls()])
        else:
            event.ignore()

    dragEnterEvent = drag_handler
    dragMoveEvent = drag_handler
    dropEvent = partialmethod(drag_handler, drop=True)

class MainWindow(QMainWindow):
    def __init__(self, control_thread: 'ControlManagerThread'):
        super().__init__()
        self._control_thread = control_thread
        control = control_thread.control

        self.dark_mode = False
        self.setStyleSheet(get_stylesheet(self.dark_mode))

        toolbar = self.addToolBar('Main Toolbar')
        toolbar.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        toolbar.setMovable(False)

        self._add_action = toolbar.addAction(load_icon('add'), 'Add')
        self._add_action.triggered.connect(self._add_torrents_triggered)

        self._pause_action = toolbar.addAction(load_icon('pause'), 'Pause')
        self._pause_action.setEnabled(False)
        self._pause_action.triggered.connect(partial(self._control_action_triggered, control.pause))

        self._resume_action = toolbar.addAction(load_icon('resume'), 'Resume')
        self._resume_action.setEnabled(False)
        self._resume_action.triggered.connect(partial(self._control_action_triggered, control.resume))

        self._remove_action = toolbar.addAction(load_icon('remove'), 'Remove')
        self._remove_action.setEnabled(False)
        self._remove_action.triggered.connect(partial(self._control_action_triggered, control.remove))

        self._magnet_action = QAction(load_icon("magnet"), "Magnet Link", self)
        self._magnet_action.triggered.connect(self.open_magnet_to_torrent)
        toolbar.addAction(self._magnet_action)

        self._theme_action = QAction(load_icon("theme"), "Switch Theme", self)
        self._theme_action.triggered.connect(self.toggle_theme)
        toolbar.addAction(self._theme_action)

        self._about_action = toolbar.addAction(load_icon('about'), 'About')
        self._about_action.triggered.connect(self._show_about)

        self._list_widget = TorrentListWidget()
        self._list_widget.itemSelectionChanged.connect(self._update_control_action_state)
        self._list_widget.files_dropped.connect(self.add_torrent_files)
        self._torrent_to_item = {}

        self.setCentralWidget(self._list_widget)
        self.setMinimumSize(600, 500)
        self.resize(800, 600)
        self.setWindowTitle('Syrent')

        control_thread.error_happened.connect(self._error_happened)
        control.torrents_suggested.connect(self.add_torrent_files)
        control.torrent_added.connect(self._add_torrent_item)
        control.torrent_changed.connect(self._update_torrent_item)
        control.torrent_removed.connect(self._remove_torrent_item)

        self.show()

    def open_magnet_to_torrent(self):
        magnet_link, ok = QInputDialog.getText(self, 'Magnet Link', 'Enter Magnet Link:')
        if not ok or not magnet_link:
            return

        output_dir = QFileDialog.getExistingDirectory(self, 'Select Output Directory')
        if not output_dir:
            return

        command = [
            sys.executable,
            os.path.join(os.path.dirname(__file__), 'magnet_to_torrent.py'),
            magnet_link,
            output_dir
        ]

        try:
            result = subprocess.run(command, capture_output=True, text=True, check=True)
            QMessageBox.information(self, "Success", result.stdout)
        except subprocess.CalledProcessError as e:
            QMessageBox.critical(self, "Error", e.stderr)

    def toggle_theme(self):
        self.dark_mode = not self.dark_mode
        self.setStyleSheet(get_stylesheet(self.dark_mode))
        mode = "Light Theme" if self.dark_mode else "Dark Theme"
        self._theme_action.setToolTip(f"Switch to {mode}")

    def _add_torrent_item(self, state: TorrentState):
        widget = TorrentListWidgetItem()
        widget.state = state

        item = QListWidgetItem()
        item.setIcon(file_icon if state.single_file_mode else directory_icon)
        item.setSizeHint(widget.sizeHint())
        item.setData(Qt.UserRole, state.info_hash)

        items_upper = 0
        for i in range(self._list_widget.count()):
            prev_item = self._list_widget.item(i)
            if self._list_widget.itemWidget(prev_item).state.suggested_name > state.suggested_name:
                break
            items_upper += 1
        self._list_widget.insertItem(items_upper, item)

        self._list_widget.setItemWidget(item, widget)
        self._torrent_to_item[state.info_hash] = item

    def _update_torrent_item(self, state: TorrentState):
        if state.info_hash not in self._torrent_to_item:
            return

        widget = self._list_widget.itemWidget(self._torrent_to_item[state.info_hash])
        if widget.state.paused != state.paused:
            widget.waiting_control_action = False
        widget.state = state

        self._update_control_action_state()

    def _remove_torrent_item(self, info_hash: bytes):
        item = self._torrent_to_item[info_hash]
        self._list_widget.takeItem(self._list_widget.row(item))
        del self._torrent_to_item[info_hash]

        self._update_control_action_state()

    def _update_control_action_state(self):
        self._pause_action.setEnabled(False)
        self._resume_action.setEnabled(False)
        self._remove_action.setEnabled(False)
        for item in self._list_widget.selectedItems():
            widget = self._list_widget.itemWidget(item)
            if widget.waiting_control_action:
                continue

            if widget.state.paused:
                self._resume_action.setEnabled(True)
            else:
                self._pause_action.setEnabled(True)
            self._remove_action.setEnabled(True)

    def _error_happened(self, description: str, err: Exception):
        QMessageBox.critical(self, description, str(err))

    def add_torrent_files(self, paths: List[str]):
        for path in paths:
            try:
                torrent_info = TorrentInfo.from_file(path, download_dir=None)
                self._control_thread.control.last_torrent_dir = os.path.abspath(os.path.dirname(path))

                if torrent_info.download_info.info_hash in self._torrent_to_item:
                    raise ValueError('This torrent is already added')
            except Exception as err:
                self._error_happened('Failed to add "{}"'.format(path), err)
                continue

            TorrentAddingDialog(self, path, torrent_info, self._control_thread).exec()

    def _add_torrents_triggered(self):
        paths, _ = QFileDialog.getOpenFileNames(self, 'Add torrents', self._control_thread.control.last_torrent_dir,
                                                'Torrent file (*.torrent);;All files (*)')
        self.add_torrent_files(paths)

    @staticmethod
    async def _invoke_control_action(action, info_hash: bytes):
        try:
            result = action(info_hash)
            if asyncio.iscoroutine(result):
                await result
        except ValueError:
            pass

    def _control_action_triggered(self, action):
        for item in self._list_widget.selectedItems():
            widget = self._list_widget.itemWidget(item)
            if widget.waiting_control_action:
                continue

            info_hash = item.data(Qt.UserRole)
            asyncio.run_coroutine_threadsafe(MainWindow._invoke_control_action(action, info_hash),
                                             self._control_thread.loop)
            widget.waiting_control_action = True

        self._update_control_action_state()

    def _show_about(self):
        QMessageBox.about(self, 'About', '<p><b>Python Based Torrent Client Prototype</b></p>'
                                         '<p>Created by GitHub ID: Shantanu10z</p>'
                                         '<p>GitHub Link: <a href="https://github.com/Shantanu10z">https://github.com/Shantanu10z</a></p>'
                                         '<p>Icons are taken from '
                                         '<a href="https://uxwing.com/">https://uxwing.com/</a></p>')

class ControlManagerThread(QThread):
    error_happened = pyqtSignal(str, Exception)

    def __init__(self):
        super().__init__()
        self._loop = None
        self._control = ControlManager()
        self._control_server = ControlServer(self._control, None)
        self._stopping = False

    @property
    def loop(self) -> asyncio.AbstractEventLoop:
        return self._loop

    @property
    def control(self) -> ControlManager:
        return self._control

    def run(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        with closing(self._loop):
            self._loop.run_until_complete(self._control.start())
            self._loop.run_until_complete(self._control_server.start())

            try:
                self._control.load_state()
            except Exception as err:
                self.error_happened.emit('Failed to load program state', err)
            self._control.invoke_state_dumps()

            self._loop.run_forever()

    async def async_stop(self):
        await asyncio.gather(self._control_server.stop(), self._control.stop())

    def stop(self):
        if self._stopping:
            return
        self._stopping = True

        stop_fut = asyncio.run_coroutine_threadsafe(self.async_stop(), self._loop)
        stop_fut.add_done_callback(lambda fut: self._loop.stop())
        self.wait()

def suggest_torrents(manager: ControlManager, filenames: List[str]):
    manager.torrents_suggested.emit(filenames)

async def find_another_daemon(filenames: List[str]) -> bool:
    try:
        async with ControlClient() as client:
            if filenames:
                await client.execute(partial(suggest_torrents, filenames=filenames))
        return True
    except RuntimeError:
        return False

def main():
    parser = argparse.ArgumentParser(description='A prototype of Syrent (Python-based Torrent Client)')
    parser.add_argument('--debug', action='store_true', help='Show debug messages')
    parser.add_argument('filenames', nargs='*', help='Torrent file names')
    args = parser.parse_args()

    if not args.debug:
        logging.disable(logging.INFO)

    app = QApplication(sys.argv)
    app.setWindowIcon(load_icon('logo'))

    control_thread = ControlManagerThread()
    main_window = MainWindow(control_thread)

    control_thread.start()
    app.lastWindowClosed.connect(control_thread.stop)

    if args.filenames:
        asyncio.run(find_another_daemon(args.filenames))

    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
