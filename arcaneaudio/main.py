# Copyright (C) 2024–2026 Eric Hernandez
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

# --- Standard Library ---
import json
import os
import re
import shutil
import sys
import threading
import time
from io import BytesIO
from pathlib import Path
import platform
import random

# --- Third-Party Libraries ---
import numpy as np
import pyqtgraph as pg
import yt_dlp
from PIL import Image, ImageOps
from PIL.ImageQt import ImageQt
from mutagen.id3 import (
    APIC, ID3, ID3NoHeaderError, TALB, TCON, TDRC, TIT2,
    TPE1, TRCK, TSSE, error
)
from mutagen.mp3 import MP3

# --- PySide6 ---
from PySide6.QtCore import (
    Q_ARG, QCoreApplication, QEvent, QMetaObject, QMimeData, QObject,
    QPoint, QThread, QTimer, QUrl, QRect, QSize, Qt, Signal, QStandardPaths
)
from PySide6.QtGui import (
    QBrush, QColor, QCursor, QDrag, QIcon, QImage, QPainter,
    QPalette, QPen, QPixmap, QTextCursor, QTextDocument
)
from PySide6.QtMultimedia import (
    QAudioBufferOutput, QAudioFormat, QAudioOutput, QMediaPlayer
)
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QDialog, QFileDialog, QHBoxLayout,
    QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow,
    QMenu, QMessageBox, QPushButton, QProgressBar, QSlider, QSpacerItem,
    QSplitter, QStyle, QSizePolicy, QTextBrowser, QTextEdit, QToolButton,
    QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget, QInputDialog
)

# --- Project-Specific ---
from arcaneaudio.ui_mainwindow import Ui_MainWindow
from arcaneaudio import __version__
from arcaneaudio.about import AboutDialog

from importlib.resources import files, as_file
import arcaneaudio.resources as respkg

APP_DIRNAME = "ArcaneAudio"  # folder name under Documents
SETTINGS_NAME = "settings.json"
SETTINGS_FILE = None  # set in main() after QApplication exists

def user_data_root() -> Path:
    """Per-user writable data root in Documents/ArcaneAudio (cross-platform)."""
    docs = QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation)
    root = Path(docs) / APP_DIRNAME
    root.mkdir(parents=True, exist_ok=True)
    return root

def default_music_root() -> str:
    docs = QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation)
    if not docs:
        docs = str(Path.home() / "Documents")
    p = Path(docs) / "ArcaneAudio" / "music"
    p.mkdir(parents=True, exist_ok=True)
    return str(p)

def settings_path() -> Path:
    return user_data_root() / SETTINGS_NAME

def ensure_settings_file() -> None:
    """Create settings.json with defaults if it doesn't exist. Print what happened."""
    global SETTINGS_FILE

    if not SETTINGS_FILE:
        SETTINGS_FILE = str(settings_path())

    p = Path(SETTINGS_FILE)
    p.parent.mkdir(parents=True, exist_ok=True)

    if p.exists():
        print(f"[settings] Found existing settings file: {p}")
        return

    defaults = {
        "theme": "arcana",
        "working_dir": "",
        "h_splitter_sizes": None,
        "v_splitter_sizes": None,
        "window_size": None,
        "volume": 100,
        "selected_tab": 0,
    }

    p.write_text(json.dumps(defaults, indent=4), encoding="utf-8")
    print(f"[settings] Settings file NOT found.\n[settings] Created new settings file: {p}")

def res_path(name: str) -> str:
    """
    Resolve a resource file path (dev + PyInstaller + installed package).
    Files live in: arcaneaudio/resources/<name>
    """
    # A) PyInstaller: unpacked bundle
    if hasattr(sys, "_MEIPASS"):
        base = Path(sys._MEIPASS)

        # PyInstaller layouts vary by version/spec; try a few common spots
        for p in (
            base / "arcaneaudio" / "resources" / name,      # preferred (package-like)
            base / "_internal" / "arcaneaudio" / "resources" / name,  # some builds
            base / "resources" / name,                      # legacy
            base / name,                                    # last resort
        ):
            if p.exists():
                return str(p)

    # B) importlib.resources (works in dev + installed; sometimes works in frozen too)
    try:
        with as_file(files(respkg) / name) as p:
            return str(p)
    except Exception:
        pass

    # C) Dev fallback (run from source)
    return str(Path(__file__).resolve().parent / "resources" / name)


ICON_PATH        = res_path("icon.png")
SOUNDBARD_PATH   = res_path("soundbard.png")
DUEL_PATH        = res_path("duel.png")
FOLDER_ICON_PATH = res_path("folder.png")
FOLDER_YES_ICON_PATH = res_path("folder-yes.png")
FOLDER_NO_ICON_PATH = res_path("folder-no.png")
PLAYLIST_ICON_PATH = res_path("playlist.png")
PLAYLIST_YES_ICON_PATH = res_path("playlist-yes.png")
PLAYLIST_NO_ICON_PATH = res_path("playlist-no.png")


class MP3Player(QWidget):
    # Define a signal that carries a string
    add_decurse_text_sig = Signal(str)
    add_dl_text_sig = Signal(str)
    append_dl_text_sig = Signal(str)

    def __init__(self):
        super().__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        # First thing, set up redirector, it requires "gui ready", meaning, we need self.ui.setupUi(self)
        #   ran asap. self.player.add_decurse_text_sig.emit to not crash, and our 2 append connects done
        #   immediately. This allows our stdout to display to our gui as soon as we can without missing
        #   messages with pyinstaller --noconsole
        self.redirector = StreamRedirector(self)

        # Connect the signals to the slots
        self.add_decurse_text_sig.connect(self.add_decurse_text)
        self.add_dl_text_sig.connect(self.add_download_text)
        self.append_dl_text_sig.connect(self.append_download_text)

        # now redirect stdout/stderr
        sys.stdout = self.redirector  # Optional: capture tracebacks too
        sys.stderr = self.redirector  # Optional: capture tracebacks too

        # Initialize other components...
        self.currentDownloadThread = None

        # maintain a variable with the current path opened in mp3 list
        self.current_mp3list_path = ""

        # Test the output
        print("If you can read this, the stdout Redirector was successful.")
        print("Welcome to ArcaneAudio - Cast Your Playlist, this is the debug console")

        # Settings path MUST be computed after QApplication exists (QStandardPaths)
        global SETTINGS_FILE
        SETTINGS_FILE = str(settings_path())
        ensure_settings_file()
        print(f"[settings] using: {SETTINGS_FILE}")

        self.working_dir = default_music_root()

        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                s = json.load(f)
            wd = (s.get("working_dir") or "").strip()
            if wd and os.path.isdir(wd):
                self.working_dir = wd
        except Exception as e:
            print("[settings] working_dir load failed, using default:", e)

        print("Creating Player")

        self.setWindowTitle("Arcane Audio - Cast Your Playlist")
        self.setWindowIcon(QIcon(ICON_PATH))

        # Set the default cover art to the app icon at start
        pixmap = QPixmap(ICON_PATH)
        pixmap = pixmap.scaled(self.ui.cover_art_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.ui.cover_art_label.setPixmap(pixmap)
        self.ui.duel_cover_art_label.setStyleSheet("background: transparent;")
        self.ui.duel_cover_art_label.setPixmap(pixmap)

        # Store the default os system's palette at startup 
        self.original_palette = QApplication.palette()

        # Settings button — a bordered text button "⚙ Settings" that matches the
        # other buttons (Play/Pause/Stop). The gear is a text glyph so it inherits
        # the theme's text color (no purple PNG). It opens a dropdown menu
        # (InstantPopup); the menu arrow signals that, so no "…".
        self.ui.settingsButton.setPopupMode(QToolButton.InstantPopup)
        self.ui.settingsButton.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self.ui.settingsButton.setText("⚙ Settings")
        self.ui.settingsButton.setAutoRaise(False)  # bordered, like the other buttons
        # Match the transport buttons' height, and keep the width just wide enough
        # for the glyph + label (the row's spacer absorbs the leftover space).
        self.ui.settingsButton.setFixedHeight(self.ui.btn_play.sizeHint().height())
        self.ui.settingsButton.setStyleSheet("QToolButton { padding: 0px 6px; }")

        # Create the settings menu
        settings_menu = QMenu(self.ui.settingsButton)
        # Theme submenu
        theme_menu = QMenu("Theme", self.ui.settingsButton)
        
        self.theme_arcana_action = theme_menu.addAction("Arcana")
        self.theme_default_action = theme_menu.addAction("Default OS")
        self.theme_dark_action = theme_menu.addAction("Dark")

        for action, name in [
            (self.theme_default_action, "default"),
            (self.theme_dark_action, "dark"),
            (self.theme_arcana_action, "arcana"),
        ]:
            action.setCheckable(True)
            action.triggered.connect(lambda checked, n=name: self.set_theme(n))
        
        # Add the submenu to the gear menu
        settings_menu.addMenu(theme_menu)

        # ---- Music folder actions ----
        settings_menu.addSeparator()

        change_music_action = settings_menu.addAction("Change Music Folder…")
        change_music_action.triggered.connect(self.change_music_folder)

        reset_music_action = settings_menu.addAction("Reset Music Folder to Default")
        reset_music_action.triggered.connect(self.reset_music_folder)

        # ---- About ----
        settings_menu.addSeparator()
        settings_menu.addAction("About", self.show_about_dialog)

        self.ui.settingsButton.setMenu(settings_menu)



        self.MP3ListisPlaylist = False

        self.ui.download_pushButton.clicked.connect(self.download_from_youtube)

        # Create splitter
        self.splitter = QSplitter(Qt.Horizontal)

        # New custom widgets
        self.ui.folder_view = FolderTreeWidget(self)
        self.ui.mp3_list = MP3ListWidget(self)

        self.folder_text_label = QLabel(self)
        self.playing_text_label = QLabel(self)
        self.folder_text_label.setMinimumWidth(1)
        self.playing_text_label.setMinimumWidth(1)

        print(f"[music] Root folder: {self.working_dir}")
        self.open_folder(from_load_last_directory=True)  # or however your function triggers “open current”

        # Add to splitter
        # Left panel: folder label + folder view
        folder_panel = QWidget()
        folder_layout = QVBoxLayout(folder_panel)
        folder_layout.setContentsMargins(0, 0, 0, 0)
        folder_layout.setSpacing(2)
        folder_layout.addWidget(self.folder_text_label)
        folder_layout.addWidget(self.ui.folder_view)

        # Right panel: playing label + mp3 list
        mp3_panel = QWidget()
        mp3_layout = QVBoxLayout(mp3_panel)
        mp3_layout.setContentsMargins(0, 0, 0, 0)
        mp3_layout.setSpacing(2)
        mp3_layout.addWidget(self.playing_text_label)
        mp3_layout.addWidget(self.ui.mp3_list)

        # Add panels to the splitter
        self.splitter.addWidget(folder_panel)
        self.splitter.addWidget(mp3_panel)

        self.splitter.setStretchFactor(0, 0)  # folder_view stays fixed
        self.splitter.setStretchFactor(1, 1)  # mp3_list expands/contracts
        #self.splitter.setSizes([400, 400])  # Optional: adjust initial split

        # Duel Play Widgets Init
        self.ui.duel_playing_text_label.setMinimumWidth(1)
        self.ui.duelrepeat_checkBox.setChecked(True)

        # Replace the original layout
        layout = self.ui.horizontalLayout_2 #this is the layout holding the 2 widgets I want a splitter for
        for i in reversed(range(layout.count())):
            widget_item = layout.itemAt(i)
            widget = widget_item.widget()
            if widget:
                widget.setParent(None)

        # Create vertical splitter between folder/mp3 lists and tabbed outputs
        self.mainSplitter = QSplitter(Qt.Vertical)
        # Add the existing layout/widget that contains the folder view and mp3 list
        self.mainSplitter.addWidget(self.splitter)  # self.splitter should be your existing splitter for the folder and mp3 list
        # Add the tab widget
        self.mainSplitter.addWidget(self.ui.tabWidget)
        # Adjust splitter proportions if needed
        self.mainSplitter.setStretchFactor(0, 1)  # More space for the folder/mp3 list
        self.mainSplitter.setStretchFactor(1, 0)  # Less space for the tabs
        # Replace the main layout or add splitter to the main window layout
        self.layout().addWidget(self.mainSplitter, 1) #dynamically add with stretch factor 1
        
        self.ui.tabWidget.setCurrentIndex(0)  # Assuming Decurse tab is the first tab (index 0)

        # Example initial sizes, adjust these numbers based on your UI needs
        self.mainSplitter.setSizes([30, 200])  # More space for the upper widget initially

        # Ensure both views support drag/drop reordering and custom drag
        self.ui.folder_view.setSelectionMode(QListWidget.SingleSelection)
        self.ui.folder_view.setDragEnabled(True)
        self.ui.folder_view.setAcceptDrops(True)
        self.ui.folder_view.setDragDropMode(QListWidget.InternalMove)
        self.ui.folder_view.setDefaultDropAction(Qt.MoveAction)
        self.ui.folder_view.setDropIndicatorShown(True)

        self.ui.folder_view.model().rowsMoved.connect(self.save_folder_order)
        self.ui.folder_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.ui.folder_view.customContextMenuRequested.connect(self.show_folder_context_menu)
        self.ui.folder_view.itemChanged.connect(self.rename_folder_or_playlist)

        # use the itemselectionchanged signal instead of itemclicked, so that if the selected item
        #   changes for a different reason, i.e. item deleted, we still refresh the mp3list
        #self.ui.folder_view.itemClicked.connect(self.selected_tree_item)
        self.ui.folder_view.itemSelectionChanged.connect(self.selected_tree_item)

        self.ui.mp3_list.setDragEnabled(True)
        self.ui.mp3_list.setAcceptDrops(True)
        self.ui.mp3_list.setDragDropMode(QListWidget.InternalMove)
        self.ui.mp3_list.setDefaultDropAction(Qt.MoveAction)
        self.ui.mp3_list.setDropIndicatorShown(True)

        self.ui.mp3_list.itemClicked.connect(self.play_selected_mp3)

        # Main Player Controls
        self.ui.btn_play.clicked.connect(self.play)
        self.ui.btn_pause.clicked.connect(self.pause)
        self.ui.btn_stop.clicked.connect(self.stop)

        # Duel Play Controls
        self.duel_selected_mp3path = ""
        self.ui.btn_duel_stop.clicked.connect(self.duel_stop)
        self.ui.btn_duel_play.clicked.connect(self.duel_play)
        self.ui.btn_duel_pause.clicked.connect(self.duel_pause)

        # Upgrade the main progress slider clickslider class and connect
        self.ui.progress_slider = self.promote_widget_to_newclass(self.ui.progress_slider, ClickSliderWidget)
        self.ui.progress_slider.setRange(0, 100)
        self.ui.progress_slider.sliderMoved.connect(self.seek)
        self.ui.progress_slider.sliderPressed.connect(self.slider_pressed)
        self.ui.progress_slider.sliderReleased.connect(self.seek)
        self.ui.progress_slider.sliderReleased.connect(self.slider_released)
        self.slider_being_moved = False

        # Upgrade the duel progress slider to clickslider class and connect
        self.ui.duel_progress_slider = self.promote_widget_to_newclass(self.ui.duel_progress_slider, ClickSliderWidget)
        self.ui.duel_progress_slider.setRange(0, 100)
        self.ui.duel_progress_slider.sliderMoved.connect(self.duel_seek)
        self.ui.duel_progress_slider.sliderPressed.connect(self.duel_slider_pressed)
        self.ui.duel_progress_slider.sliderReleased.connect(self.duel_seek)
        self.ui.duel_progress_slider.sliderReleased.connect(self.duel_slider_released)
        self.duel_slider_being_moved = False

        # Upgrade the volume slider to clickslider class and connect
        self.ui.volume_slider = self.promote_widget_to_newclass(self.ui.volume_slider, ClickSliderWidget)
        self.ui.volume_slider.setRange(0, 100)
        self.ui.volume_slider.setValue(100)
        self.ui.volume_slider.sliderReleased.connect(self.set_volume)
        self.ui.volume_slider.sliderMoved.connect(self.set_volume)

        # Upgrade the duel volume slider to clickslider class and connect
        self.ui.duel_volume_slider = self.promote_widget_to_newclass(self.ui.duel_volume_slider, ClickSliderWidget)
        self.ui.duel_volume_slider.setRange(0, 100)
        self.ui.duel_volume_slider.setValue(100)
        self.ui.duel_volume_slider.sliderReleased.connect(self.duel_set_volume)
        self.ui.duel_volume_slider.sliderMoved.connect(self.duel_set_volume)

        self.ui.visualizationWidget.setBackground(None)
        self.ui.visualizationWidget.enableAutoRange(axis='y')
        self.ui.visualizationWidget.getPlotItem().hideAxis('left')
        self.num_bars = 16
        x = np.linspace(0, np.pi * 2, self.num_bars)
        self.previous_bar_heights = (np.sin(x * 2) + 1.2) * 4  # Nice default curve

        # Visualizer state — driven by the decoded playback audio (see _attach_visualizer),
        # not a microphone. _viz_sources maps a source key ("main"/"duel") to its latest
        # mono window; _viz_buffer_outputs keeps the QAudioBufferOutput objects alive.
        self._viz_fft_size = 1024
        self._viz_rate = 44100
        self._viz_sources = {}
        self._viz_buffer_outputs = {}

        # Main Player
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)
        self.audio_output.setVolume(1.0)
        self._attach_visualizer(self.player, "main")
        self.player.positionChanged.connect(self.update_progress)
        self.player.durationChanged.connect(self.set_progress_range)
        self.player.playbackStateChanged.connect(self.handle_playback_state)
        self.player.mediaStatusChanged.connect(self.handle_media_status)
        self.player.errorOccurred.connect(lambda error, errorString: print(f"Error occurred: {errorString}"))

        # Duel Play Player placeholder, Don't create objects until we actually use it
        self.player2 = None
        self.audio_output2 = None

        old_lineEdit = self.ui.youtubeURL_lineEdit
        self.ui.youtubeURL_lineEdit = SelectAllLineEdit(self)
        self.ui.youtubeURL_lineEdit.setText("Enter Youtube URL Here")
        self.ui.horizontalLayout_10.replaceWidget(old_lineEdit, self.ui.youtubeURL_lineEdit)
        layout.replaceWidget(old_lineEdit, self.ui.youtubeURL_lineEdit)
        old_lineEdit.deleteLater()

        self.playlist_paths = []

        self.current_mp3_folder = ""

        self.timer = QTimer()
        self.folder_settings_path = None
        self.timer.timeout.connect(self.update_spectrograph)        
        
        self.ui.soundbard_label.setScaledContents(False)
        self.og_soundbard_pixmap = QPixmap(SOUNDBARD_PATH)
        ogWidth = self.og_soundbard_pixmap.width()
        ogHeight = self.og_soundbard_pixmap.height()
        newheight = 100#self.ui.soundbard_label.height()
        newWidth = (ogWidth * newheight) / ogHeight
        resizedPixmap = QPixmap()
        resizedPixmap = self.og_soundbard_pixmap.scaled(newWidth, newheight, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.ui.soundbard_label.setPixmap(resizedPixmap)

        self.duel_pixmap = QPixmap(DUEL_PATH)
        self.duel_pixmap = self.duel_pixmap.scaled(100, 100, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.ui.duel_label.setPixmap(self.duel_pixmap)

        self.init_visualization()
        self.load_settings()

    def promote_widget_to_newclass(self, objecttopromote, newclass):
        layout = objecttopromote.parent().layout()
        # grab old settings
        style = objecttopromote.styleSheet()
        orientation = objecttopromote.orientation()
        minwidth = objecttopromote.minimumWidth()
        maxwidth = objecttopromote.maximumWidth()
        # create new object
        newobject = newclass(self)
        newobject.setStyleSheet(style)
        newobject.setOrientation(orientation)
        newobject.setMinimumWidth(minwidth)
        newobject.setMaximumWidth(maxwidth)
        layout.replaceWidget(objecttopromote, newobject)
        objecttopromote.deleteLater()
        return newobject

    def add_decurse_text(self, text):
        # Move the cursor to the end before inserting text
        cursor = self.ui.debugTextBrowser.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        # Insert plain text
        cursor.insertText(text)
        # Set the cursor back to the QTextBrowser
        self.ui.debugTextBrowser.setTextCursor(cursor)
        # Scroll to the bottom
        # Scroll the QTextBrowser's scrollbar to the bottom
        scroll_bar = self.ui.debugTextBrowser.verticalScrollBar()
        scroll_bar.setValue(scroll_bar.maximum())

    def add_download_text(self, text):
        # Print each instance of text on a newline
        # Strip all "\n" found anywhere in text
        text = text.replace('\n', '').replace('\r', '')
        text = '\n' + text # Add back in one "\n" at the beginning

        # Move the cursor to the end before inserting text
        cursor = self.ui.downloadTextBrowser.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        
        # Insert text
        cursor.insertText(text)

        # Set the cursor back to the QTextBrowser
        self.ui.downloadTextBrowser.setTextCursor(cursor)

        # Scroll the QTextBrowser's scrollbar to the bottom
        scroll_bar = self.ui.downloadTextBrowser.verticalScrollBar()
        scroll_bar.setValue(scroll_bar.maximum())

    def append_download_text(self, text):
        # Print each instance of text on a newline
        # Strip all "\n" found anywhere in text
        
        # Move the cursor to the end before inserting text
        cursor = self.ui.downloadTextBrowser.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        
        # Insert text
        cursor.insertText(text)

        # Set the cursor back to the QTextBrowser
        self.ui.downloadTextBrowser.setTextCursor(cursor)

        # Scroll the QTextBrowser's scrollbar to the bottom
        scroll_bar = self.ui.downloadTextBrowser.verticalScrollBar()
        scroll_bar.setValue(scroll_bar.maximum())

    def set_theme(self, theme_name):
        if theme_name == "dark":
            QApplication.setStyle("Fusion")
            dark_palette = QPalette()
            dark_palette.setColor(QPalette.Window, QColor(53, 53, 53))
            dark_palette.setColor(QPalette.WindowText, Qt.white)
            dark_palette.setColor(QPalette.Base, QColor(35, 35, 35))
            dark_palette.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
            dark_palette.setColor(QPalette.ToolTipBase, Qt.white)
            dark_palette.setColor(QPalette.ToolTipText, Qt.white)
            dark_palette.setColor(QPalette.Text, Qt.white)
            dark_palette.setColor(QPalette.Button, QColor(53, 53, 53))
            dark_palette.setColor(QPalette.ButtonText, Qt.white)
            dark_palette.setColor(QPalette.BrightText, Qt.red)
            dark_palette.setColor(QPalette.Link, QColor(42, 130, 218))
            dark_palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
            dark_palette.setColor(QPalette.HighlightedText, Qt.black)
            QApplication.setPalette(dark_palette)
            for widget in QApplication.allWidgets():
                widget.setPalette(dark_palette)
                widget.style().polish(widget)
                widget.repaint()
            print("Theme set to: dark")
        elif theme_name == "arcana":
            #Arcana Colors - Taken from Endeavour OS KDE Breeze (I just like these)
            QApplication.setStyle("Fusion")
            arcana_palette = QPalette()
            arcana_palette.setColor(QPalette.Window, QColor(42, 46, 50))
            arcana_palette.setColor(QPalette.WindowText, QColor(252, 252, 252))
            arcana_palette.setColor(QPalette.Base, QColor(27, 30, 32))
            arcana_palette.setColor(QPalette.AlternateBase, QColor(35, 38, 41))
            arcana_palette.setColor(QPalette.ToolTipBase, QColor(49, 54, 59))
            arcana_palette.setColor(QPalette.ToolTipText, QColor(252, 252, 252))
            arcana_palette.setColor(QPalette.Text, QColor(252, 252, 252))
            arcana_palette.setColor(QPalette.Button, QColor(49, 54, 59))
            arcana_palette.setColor(QPalette.ButtonText, QColor(252, 252, 252))
            arcana_palette.setColor(QPalette.BrightText, QColor(75, 75, 75))
            arcana_palette.setColor(QPalette.Link, QColor(209, 199, 242))
            arcana_palette.setColor(QPalette.Highlight, QColor(110, 86, 169))
            arcana_palette.setColor(QPalette.HighlightedText, QColor(255, 255, 255))
            QApplication.setPalette(arcana_palette)
            for widget in QApplication.allWidgets():
                widget.setPalette(arcana_palette)
                widget.style().polish(widget)
                widget.repaint()
            print("Theme set to: arcana")
        else:  # Default OS style
            #This loads the one that was set by the OS at app startup before we messed with it
            QApplication.setStyle(QApplication.style().objectName())  # Optional
            QApplication.setPalette(self.original_palette)
            # Force all widgets to update their palette
            for widget in QApplication.allWidgets():
                widget.setPalette(self.original_palette)
                widget.style().polish(widget)
                widget.repaint()
            print("Theme set to: default os")

        # Update the visualization background explicitly
        bg_color = QApplication.palette().color(QPalette.Window)
        self.ui.visualizationWidget.setBackground(bg_color)

        self.save_theme_to_settings(theme_name)
        self.update_theme_menu_checkmarks(theme_name)

    def update_playlist_paths(self, old_path, new_path):
        print("update_playlist_paths")
        """
        Update all .m3u playlists to replace references to old_path with new_path.
        Both paths should be absolute or relative to self.working_dir.
        """
        if not os.path.isdir(self.working_dir):
            return

        # Normalize both to relative Unix-style paths
        old_rel = os.path.relpath(old_path, self.working_dir).replace("\\", "/")
        new_rel = os.path.relpath(new_path, self.working_dir).replace("\\", "/")

        for root, dirs, files in os.walk(self.working_dir):
            for file in files:
                if not file.endswith(".m3u"):
                    continue

                m3u_path = os.path.join(root, file)
                try:
                    with open(m3u_path, "r", encoding="utf-8") as f:
                        lines = f.readlines()

                    updated = False
                    new_lines = []

                    for line in lines:
                        line_strip = line.strip()
                        if line_strip.startswith("#") or not line_strip:
                            new_lines.append(line)
                            continue

                        normalized_line = line_strip.replace("\\", "/")
                        norm_old = old_rel.replace("\\", "/")
                        norm_new = new_rel.replace("\\", "/")

                        if os.path.isfile(old_path):
                            # We're moving a specific file
                            if normalized_line == norm_old:
                                print(f"✅ File match — replacing with: {norm_new}")
                                new_lines.append(norm_new + "\n")
                                updated = True
                            else:
                                new_lines.append(line)
                        else:
                            if normalized_line.startswith(norm_old + "/"):
                                # Create full absolute paths to compute the suffix correctly
                                abs_old = os.path.normpath(os.path.join(self.working_dir, norm_old))
                                abs_line = os.path.normpath(os.path.join(self.working_dir, normalized_line))
                                
                                # ✅ Compute the part of the line *after* the old folder path
                                suffix = os.path.relpath(abs_line, abs_old).replace("\\", "/")

                                # ✅ Build the new relative path correctly
                                new_line = os.path.join(norm_new, suffix).replace("\\", "/")
                                print(f"✅ Folder match — replacing with: {new_line}")
                                new_lines.append(new_line + "\n")
                                updated = True
                                print(f"  [Debug] normalized_line = {normalized_line}")
                                print(f"  [Debug] norm_old        = {norm_old}")
                                print(f"  [Debug] abs_line        = {abs_line}")
                                print(f"  [Debug] abs_old         = {abs_old}")
                                print(f"  [Debug] suffix          = {suffix}")
                            else:
                                new_lines.append(line)

                    if updated:
                        with open(m3u_path, "w", encoding="utf-8") as f:
                            f.writelines(new_lines)
                        print(f"✅ Updated playlist paths in: {m3u_path}")

                except Exception as e:
                    print(f"❌ Failed to update playlist {m3u_path}: {e}")

    def update_theme_menu_checkmarks(self, selected):
        self.theme_arcana_action.setChecked(selected == "arcana")
        self.theme_dark_action.setChecked(selected == "dark")
        self.theme_default_action.setChecked(selected == "default")

    def save_theme_to_settings(self, theme_name):
        try:
            settings = {}
            if os.path.exists(SETTINGS_FILE):
                with open(SETTINGS_FILE, 'r') as f:
                    settings = json.load(f)
            settings["theme"] = theme_name
            with open(SETTINGS_FILE, 'w') as f:
                json.dump(settings, f)
        except Exception as e:
            print("Failed to save theme:", e)

    def print_palette_colors(self, palette):
        role_names = {
            QPalette.Window: "Window",
            QPalette.WindowText: "WindowText",
            QPalette.Base: "Base",
            QPalette.AlternateBase: "AlternateBase",
            QPalette.ToolTipBase: "ToolTipBase",
            QPalette.ToolTipText: "ToolTipText",
            QPalette.Text: "Text",
            QPalette.Button: "Button",
            QPalette.ButtonText: "ButtonText",
            QPalette.BrightText: "BrightText",
            QPalette.Link: "Link",
            QPalette.Highlight: "Highlight",
            QPalette.HighlightedText: "HighlightedText",
        }
        print("🎨 Palette Colors:")
        for role, name in role_names.items():
            color = palette.color(role)
            print(f"{name:<16}: {color.name()} (RGB: {color.red()}, {color.green()}, {color.blue()})")

    def show_about_dialog(self):
        AboutDialog(
            parent=self,
            app_name="Arcane Audio",
            version=__version__,
            icon_path=ICON_PATH,
            tagline="Point it at your folders — instant music and ambience "
                    "for your table.",
            license_path=res_path("AGPL_V3.txt"),
        ).exec()

    def save_current_playlist_order(self):
        selected = self.ui.folder_view.currentItem()
        if not selected:
            return

        path = selected.data(0, Qt.UserRole)
        if not path or not path.endswith(".m3u"):
            return

        try:
            print(f"opening:{path}")
            with open(path, "w", encoding="utf-8") as f:
                f.write("#EXTM3U\n")
                for i in range(self.ui.mp3_list.count()):
                    mp3_path = self.ui.mp3_list.item(i).data(Qt.UserRole)
                    print(f"mp3_path:{mp3_path}")
                    rel_path = os.path.relpath(mp3_path, self.working_dir)
                    print(f"rel_path:{rel_path}")
                    f.write(rel_path + "\n")
        except Exception as e:
            QMessageBox.critical(self, "Save Failed", f"Could not save playlist:\n{e}")

    def selected_tree_item(self):
        # only triggered on clicking on tree item
        # sets a global var to the path and calls load_mp3list_from_path
        item = self.ui.folder_view.currentItem()
        if not item:
            print("No item selected in the folder view.")
            return

        column = 0  # Typically, if only one column is used, this is 0
        full_path = item.data(0, Qt.UserRole)
        if not full_path:
            print("Selected item has no path data.")
            return

        self.current_mp3list_path = full_path
        self.load_mp3list_from_path()

    def load_mp3list_from_path(self):
        full_path = self.current_mp3list_path
        self.ui.mp3_list.clear()
        self.playlist_paths = []

        if full_path.endswith(".m3u"):
            try:
                with open(full_path, 'r') as f:
                    self.MP3ListisPlaylist = True
                    lines = [line.strip() for line in f if line.strip() and not line.startswith('#')]
                    for file in lines:
                        item = QListWidgetItem(os.path.basename(file))
                        full_path_item = os.path.join(self.working_dir, file)
                        item.setData(Qt.UserRole, full_path_item)
                        self.ui.mp3_list.addItem(item)
                        self.playlist_paths.append(full_path_item)
            except Exception as e:
                print("Failed to load playlist:", e)
        elif os.path.isdir(full_path):
            self.MP3ListisPlaylist = False
            self.current_mp3_folder = full_path
            for file in os.listdir(full_path):
                if file.endswith(".mp3"):
                    item = QListWidgetItem(file)
                    full_path_item = os.path.join(full_path, file)
                    item.setData(Qt.UserRole, full_path_item)
                    self.ui.mp3_list.addItem(item)

    def get_current_mp3list_path(self):
        return self.current_mp3list_path

    def seek(self):
        if self.player.duration() > 0:
            self.player.setPosition(self.ui.progress_slider.value())

    def slider_pressed(self):
        self.slider_being_moved = True

    def slider_released(self):
        self.slider_being_moved = False
        self.seek()

    def update_progress(self, position):
        if not self.slider_being_moved:
            self.ui.progress_slider.setValue(position)

        song_seconds = self.ui.progress_slider.maximum() // 1000
        current_seconds = position // 1000
        current_min = current_seconds // 60
        current_sec = current_seconds % 60
        self.ui.label_seektimetext.setText(f"Time: {current_min:02d}:{current_sec:02d}")
        rem_min = (song_seconds - current_seconds) // 60
        rem_sec = (song_seconds - current_seconds) % 60
        song_min = song_seconds // 60
        song_sec = song_seconds % 60
        self.ui.label_remainingtimetext.setText(f"Remaining: {rem_min:02d}:{rem_sec:02d} of {song_min:02d}:{song_sec:02d}")

    def handle_media_status(self, status):
        if status == QMediaPlayer.EndOfMedia:
            if self.ui.repeat_checkBox.isChecked():
                # Repeat
                current_item = self.ui.mp3_list.currentItem()
                if current_item:
                    self.play_selected_mp3(current_item)
            elif self.ui.random_checkBox.isChecked():
                # Choose random
                    count = self.ui.mp3_list.count()
                    if count == 0:
                        return
                    random_index = random.randint(0, count - 1)
                    random_item = self.ui.mp3_list.item(random_index)
                    self.ui.mp3_list.setCurrentItem(random_item)
                    self.play_selected_mp3(random_item)
            else:
                # Go to the next
                current_row = self.ui.mp3_list.currentRow()
                next_row = current_row + 1
                if next_row < self.ui.mp3_list.count():
                    next_item = self.ui.mp3_list.item(next_row)
                    self.ui.mp3_list.setCurrentItem(next_item)
                    self.play_selected_mp3(next_item)
                elif self.ui.mp3_list.count() > 0:
                    # Go back to the 1st
                    first_item = self.ui.mp3_list.item(0)
                    self.ui.mp3_list.setCurrentItem(first_item)
                    self.play_selected_mp3(first_item)

    def set_volume(self):
        volume = self.ui.volume_slider.value() / 100.0
        self.audio_output.setVolume(volume)
        self.ui.label_volumetext.setText(f"Volume: {int(volume * 100)}%")

    def handle_playback_state(self, state):
        # Visualizer runs while either the main or duel player is playing.
        self._update_viz_timer()

    def open_folder(self, from_load_last_directory=False):
        self.folder_settings_path = None
        folder_path = self.working_dir if from_load_last_directory else QFileDialog.getExistingDirectory(self, "Open Folder", self.working_dir or "")
        if folder_path and os.path.isdir(folder_path):
            self.working_dir = folder_path
            self.folder_text_label.setText(f"Opened: {folder_path}")

            self.ui.folder_view.populate_from_path(folder_path)
            self.save_working_dir()

    def change_music_folder(self):
        """Open the folder picker and set the root music folder."""
        # Reuse your existing dialog-driven path
        self.open_folder(from_load_last_directory=False)

    def reset_music_folder(self):
        """Reset root folder back to Documents/ArcaneAudio/music and reload."""
        self.working_dir = default_music_root()
        self.save_working_dir()
        print(f"[music] Root folder reset to default: {self.working_dir}")
        self.open_folder(from_load_last_directory=True)

    def save_folder_order(self):
        if not self.folder_settings_path:
            return
        try:
            order = [self.ui.folder_view.item(i).text() for i in range(self.ui.folder_view.count())]
            with open(self.folder_settings_path, 'w') as f:
                json.dump(order, f)
        except Exception as e:
            print("Failed to save folder order:", e)

    def play_selected_mp3(self, item):
        row = self.ui.mp3_list.row(item)
        if self.playlist_paths:
            if row < len(self.playlist_paths):
                selected_file = self.playlist_paths[row]
            else:
                print("Invalid index in playlist.")
                return
        else:
            selected_file = os.path.join(self.current_mp3_folder, item.text())

        if os.path.isfile(selected_file):
            self.update_title_art(selected_file, self.playing_text_label, self.ui.cover_art_label)

            # Extract and display metadata and other info to filelore
            self.update_filelore(selected_file)

            self.player.setSource(QUrl.fromLocalFile(selected_file))
            self.play()

            # hack, this forces the mp3 to play and give the message:
            # Media status changed: MediaStatus.LoadedMedia. I need it to force the playing
            # of media with embedded images... really? I must be doing something wrong
            QTimer.singleShot(100, lambda: self.player.setPosition(0))  
            # print(f"Media state after attempting to play: {self.player.mediaStatus()}") #this always prints before the player signals, why?

    def update_filelore(self, file_path):
        # Extract and display metadata and other info
        try:
            audio = MP3(file_path, ID3=ID3)
            filesize_bytes = os.path.getsize(file_path)
            meta_info = (
                f"Title: {audio.tags.get('TIT2').text[0] if audio.tags.get('TIT2') else 'Unknown Title'}, "
                f"Artist: {audio.tags.get('TPE1').text[0] if audio.tags.get('TPE1') else 'Unknown Artist'}\n"
                f"Album: {audio.tags.get('TALB').text[0] if audio.tags.get('TALB') else 'Unknown Album'}, "
                f"Track: {audio.tags.get('TRCK').text[0] if audio.tags.get('TRCK') else 'Unknown Track '}\n"
                f"Genre: {audio.tags.get('TCON').text[0] if audio.tags.get('TCON') else 'Unknown Genre'}, "
                f"Date: {audio.tags.get('TDRC').text[0] if audio.tags.get('TDRC') else 'Unknown Date'}\n"
                f"Encoder: {audio.tags.get('TSSE').text[0] if audio.tags.get('TSSE') else 'Unknown Encoder'}, "
                f"Bitrate: {int(audio.info.bitrate / 1000)} kbps\n"
                f"Duration: {int(audio.info.length)} seconds, "
                f"Filesize: {filesize_bytes / (1024 * 1024):.2f} MB"
            )
            self.ui.fileMeta_textBrowser.setText(meta_info)

        except Exception as e:
            msg = f"Failed to read metadata from {file_path}: {e}"
            self.ui.fileMeta_textBrowser.clear
            self.ui.fileMeta_textBrowser.append(msg)
            print(msg)
            return

    def play(self):
        if self.player.source().isEmpty():
            print("No file selected to play.")
            return
        x = np.linspace(0, np.pi * 2, self.num_bars)
        self.previous_bar_heights = (np.sin(x * 2) + 1.2) * 4
        self.player.play()

    def pause(self):
        self.player.pause()

    def stop(self):
        self.player.stop()
        self.ui.progress_slider.setValue(0)

    def _attach_visualizer(self, player, key):
        """Route a player's decoded playback audio into the spectrum visualizer.

        Uses QAudioBufferOutput (Qt 6.8+, FFmpeg backend) to tap the PCM buffers the
        media player decodes as it plays, so the bars react to the actual music. This
        replaces the old PyAudio microphone capture — no mic access, no OS permission
        prompt, and the visualizer reflects what's playing instead of ambient sound.
        """
        out = QAudioBufferOutput()
        out.audioBufferReceived.connect(lambda buf, k=key: self._on_viz_buffer(k, buf))
        player.setAudioBufferOutput(out)
        # Keep a Python reference so the capture object isn't garbage-collected.
        self._viz_buffer_outputs[key] = out

    def _detach_visualizer(self, key):
        """Drop a source's capture object + last samples (when a player is torn down)."""
        self._viz_sources.pop(key, None)
        self._viz_buffer_outputs.pop(key, None)

    def _viz_extract_mono(self, buf):
        """Decode a QAudioBuffer into a mono float32 array in [-1, 1]."""
        try:
            fmt = buf.format()
            sf = fmt.sampleFormat()
            data = buf.constData()  # memoryview over Qt-owned memory (valid only now)
            SF = QAudioFormat.SampleFormat
            if sf == SF.Int16:
                arr = np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0
            elif sf == SF.Int32:
                arr = np.frombuffer(data, dtype=np.int32).astype(np.float32) / 2147483648.0
            elif sf == SF.Float:
                arr = np.frombuffer(data, dtype=np.float32).astype(np.float32)
            elif sf == SF.UInt8:
                arr = (np.frombuffer(data, dtype=np.uint8).astype(np.float32) - 128.0) / 128.0
            else:
                return None
            # astype() above already copied the data out of the transient Qt buffer.
            channels = fmt.channelCount()
            if channels > 1:
                usable = (arr.size // channels) * channels
                arr = arr[:usable].reshape(-1, channels).mean(axis=1)
            return np.ascontiguousarray(arr, dtype=np.float32)
        except Exception as e:
            print(f"[viz] buffer decode failed: {e}")
            return None

    def _on_viz_buffer(self, key, buf):
        """Stash the most recent decoded window for a playing source."""
        mono = self._viz_extract_mono(buf)
        if mono is None or mono.size == 0:
            return
        rate = buf.format().sampleRate()
        if rate > 0:
            self._viz_rate = rate
        n = self._viz_fft_size
        self._viz_sources[key] = mono[-n:] if mono.size >= n else mono

    def _update_viz_timer(self, *args):
        """Run the redraw timer only while something is actually playing.

        Also drops the stashed samples of any source that has stopped, so the mixed
        spectrum reflects only what's currently audible.
        """
        main_playing = self.player.playbackState() == QMediaPlayer.PlayingState
        if not main_playing:
            self._viz_sources.pop("main", None)

        player2 = getattr(self, "player2", None)
        duel_playing = (
            player2 is not None
            and player2.playbackState() == QMediaPlayer.PlayingState
        )
        if not duel_playing:
            self._viz_sources.pop("duel", None)

        if main_playing or duel_playing:
            if not self.timer.isActive():
                self.timer.start(100)
        else:
            self.timer.stop()

    def init_visualization(self):
        num_bars = self.num_bars
        self.ui.visualizationWidget.clear()
        
        brushes = []
        for i in range(self.num_bars):
            # Create a gradient from darker to lighter purple
            base = 100 + int((i / self.num_bars) * 100)   # 100–200
            alpha = 150 + int((i / self.num_bars) * 105)  # 150–255
            brushes.append(pg.mkBrush(base, 0, base + 55, alpha))

        x = np.arange(num_bars)
        for i in range(num_bars):
            bar = pg.BarGraphItem(x=[x[i]], height=[self.previous_bar_heights[i]], width=0.8, brush=brushes[i])
            #bar = pg.BarGraphItem(x=[x[i]], height=[dummy_bar_heights[i]], width=0.8, brush=brushes[i])
            self.ui.visualizationWidget.addItem(bar)

    def update_spectrograph(self):
        # Mix the latest decoded window from every currently-playing source (main + duel).
        sources = [s for s in self._viz_sources.values() if s is not None and s.size]
        if not sources:
            return

        n = self._viz_fft_size
        waveform = np.zeros(n, dtype=np.float32)
        for s in sources:
            if s.size >= n:
                waveform += s[-n:]
            else:
                waveform[-s.size:] += s

        waveform -= np.mean(waveform)  # Remove DC bias
        peak = np.max(np.abs(waveform))
        if peak < 1e-4:
            # Effectively silent — let the bars fall to rest instead of amplifying noise.
            bar_heights = np.zeros(self.num_bars, dtype=np.float32)
        else:
            waveform = waveform / (peak + 1e-8)  # Normalize
            spectrum = np.abs(np.fft.rfft(waveform))
            freqs = np.fft.rfftfreq(len(waveform), 1 / self._viz_rate)
            log_freqs = np.logspace(np.log10(20), np.log10(20000), num=self.num_bars + 1)[:self.num_bars]
            bar_heights = np.interp(log_freqs, freqs, spectrum)

        num_bars = self.num_bars
        smooth = 0.5
        self.previous_bar_heights = (1 - smooth) * self.previous_bar_heights + smooth * bar_heights

        brushes = []
        for i in range(self.num_bars):
            # Create a gradient from darker to lighter purple
            base = 100 + int((i / self.num_bars) * 100)   # 100–200
            bar_alpha = 150 + int((i / self.num_bars) * 105)  # 150–255
            brushes.append(pg.mkBrush(base, 0, base + 55, bar_alpha))

        self.ui.visualizationWidget.clear()
        x = np.arange(num_bars)
        for i in range(num_bars):
            bar = pg.BarGraphItem(x=[x[i]], height=[self.previous_bar_heights[i]], width=0.8, brush=brushes[i])
            self.ui.visualizationWidget.addItem(bar)

    def download_from_youtube(self):
        if self.currentDownloadThread and self.currentDownloadThread.isRunning():
            print("[downlord] Download in Progress... Please wait for the current download to finish.")
            return

        url = self.ui.youtubeURL_lineEdit.text().strip()
        pattern = re.compile(r"^(https?:\/\/)?([\w\.-]+)\.([a-z\.]{2,20})([\/\w \.-]*)(\?[\w=&\.;%-]*)?$")
        if not pattern.match(url):
            print("[downlord] Error... Please enter a valid URL.")
            return

        download_path = os.path.join(self.working_dir, 'downloads')
        #os.makedirs(download_path, exist_ok=True)
        # Check if the directory already exists
        if not os.path.exists(download_path):
            print("[downlord] Directory: download does not exist, creating now...")
            os.makedirs(download_path, exist_ok=True)
            # if the directory didn't exist then it is not in the tree
            self.ui.folder_view.populate_from_path(self.working_dir)
        else:
            print("[downlord] Directory: download already exists.")

        self.currentDownloadThread = DownloadThread(url, download_path, self)
        #self.currentDownloadThread.progress.connect(self.update_progress) #update_progress is used by progress slider
        self.currentDownloadThread.finished.connect(self.download_finished)
        self.currentDownloadThread.error.connect(self.download_error)
        self.currentDownloadThread.start()

    def download_finished(self, message):
        self.ui.youtubeURL_lineEdit.setText("Enter Youtube URL Here")
        print("[downlord] Download Finished")
        #refresh the mp3list after a download incase we are viewing
        self.load_mp3list_from_path()

    def download_error(self, message):
        print("[downlord] Download Error")

    def set_progress_range(self, duration):
        if duration > 0:
            self.ui.progress_slider.setRange(0, duration)

    def show_folder_context_menu(self, position):
        item = self.ui.folder_view.itemAt(position)
        menu = QMenu()

        new_folder_action = menu.addAction("Create New Folder")
        create_action = menu.addAction("Create New Playlist")
        rename_action = None
        delete_action = None

        if item:
            full_path = item.data(0, Qt.UserRole)
            if os.path.basename(full_path) == ".trash":
                empty_trash_action = menu.addAction("Empty Trash")
            if full_path.endswith(".m3u"):
                rename_action = menu.addAction("Rename Playlist")
                delete_action = menu.addAction("Delete Playlist")
                view_file_action = menu.addAction("View File")
            elif os.path.isdir(full_path):
                rename_action = menu.addAction("Rename Folder")
                delete_action = menu.addAction("Delete Folder")

        action = menu.exec(self.ui.folder_view.mapToGlobal(position))

        if 'view_file_action' in locals() and action == view_file_action:
            self.view_playlist_file(full_path)
            return

        if 'empty_trash_action' in locals() and action == empty_trash_action:
            self.empty_trash(full_path)
            return

        if action == new_folder_action:
            self.create_new_folder(item)

        elif action == create_action:
            self.create_new_playlist(item)

        elif rename_action and action == rename_action:
            item.setFlags(item.flags() | Qt.ItemIsEditable)
            self.ui.folder_view.editItem(item, 0)

        elif delete_action and action == delete_action:
            full_path = item.data(0, Qt.UserRole)
            if not full_path:
                return

            confirm = QMessageBox.question(
                self,
                "Confirm Delete",
                f"Are you sure you want to delete:\n{full_path}?",
                QMessageBox.Yes | QMessageBox.No
            )

            if confirm == QMessageBox.Yes:
                try:
                    # Define .trash path inside working folder
                    trash_dir = os.path.join(self.working_dir, ".trash")
                    os.makedirs(trash_dir, exist_ok=True)

                    name = os.path.basename(full_path)
                    trash_path = os.path.join(trash_dir, name)

                    # Prevent overwrite in trash
                    index = 1
                    base_name, ext = os.path.splitext(name)
                    while os.path.exists(trash_path):
                        trash_path = os.path.join(trash_dir, f"{base_name}_{index}{ext}")
                        index += 1

                    # Move file or folder to .trash
                    self.move_file_or_folder(full_path, trash_path)

                    # Remove from UI tree
                    parent = item.parent() or self.ui.folder_view.invisibleRootItem()
                    parent.removeChild(item)

                    print(f"Moved to trash: {trash_path}")

                    #refresh mp3list... lets see if this works, seems to work
                    self.load_mp3list_from_path()

                except Exception as e:
                    QMessageBox.critical(self, "Delete Failed", f"Could not move to trash:\n{e}")

    def empty_trash(self, trash_path):
        confirm = QMessageBox.question(
            self,
            "Confirm Empty Trash",
            "Are you sure you want to permanently delete all files in the trash?",
            QMessageBox.Yes | QMessageBox.No
        )

        if confirm != QMessageBox.Yes:
            return

        try:
            for filename in os.listdir(trash_path):
                file_path = os.path.join(trash_path, filename)
                if os.path.isfile(file_path):
                    os.remove(file_path)
                else:
                    shutil.rmtree(file_path)
            print(f"✅ Emptied trash: {trash_path}")
            self.ui.folder_view.populate_from_path(self.working_dir)
        except Exception as e:
            QMessageBox.critical(self, "Empty Trash Failed", f"Could not empty trash:\n{e}")

    def view_playlist_file(self, filepath):
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Viewing: {os.path.basename(filepath)}")
        dialog.setMinimumSize(500, 400)

        layout = QVBoxLayout(dialog)
        text_edit = QTextEdit(dialog)

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                text_edit.setPlainText(f.read())
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to read file:\n{e}")
            return

        layout.addWidget(text_edit)

        button_layout = QHBoxLayout()
        save_btn = QPushButton("Save")
        cancel_btn = QPushButton("Cancel")
        button_layout.addWidget(save_btn)
        button_layout.addWidget(cancel_btn)
        layout.addLayout(button_layout)

        def save_and_close():
            try:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(text_edit.toPlainText())
                print(f"✅ Saved: {filepath}")
                self.load_mp3list_from_path()  # Refresh the MP3 list
                dialog.accept()
            except Exception as e:
                QMessageBox.critical(self, "Save Failed", f"Could not save file:\n{e}")

        def cancel_and_close():
            dialog.reject()

        save_btn.clicked.connect(save_and_close)
        cancel_btn.clicked.connect(cancel_and_close)

        dialog.exec()
    
    def move_file_or_folder(self, filefolderpath, topath, event=None):
        print("move_file_or_folder called")
        player = self.window().player
        currently_playing = player.source().toLocalFile()
        release_needed = False

        # Normalize paths for comparison (case-insensitive on Windows)
        def norm(path):
            return os.path.normcase(os.path.abspath(path))

        filefolderpath_norm = norm(filefolderpath)
        currently_playing_norm = norm(currently_playing)

        # 🔎 Check if moving the file currently being played
        if filefolderpath_norm == currently_playing_norm:
            release_needed = True
        elif os.path.isdir(filefolderpath) and currently_playing_norm.startswith(filefolderpath_norm + os.sep):
            # 🔎 Check if folder contains the playing file
            release_needed = True

        # 🛑 Stop and unload media if needed
        if release_needed:
            print("⏹ Releasing media that is currently playing before moving.")
            player.stop()
            player.setSource(QUrl())
            QCoreApplication.processEvents()
            time.sleep(0.1)

        # ✅ Try the move
        try:
            shutil.move(filefolderpath, topath)
            print(f"✅ Moved {filefolderpath} to {topath}")

            self.window().update_playlist_paths(filefolderpath, topath)

            self.window().load_mp3list_from_path()

            if event:
                event.acceptProposedAction()
        except Exception as e:
            print(f"❌ Move failed: {e}")
            QMessageBox.warning(self, "Move Failed", f"Could not move the file or folder:\n{e}")
        
    def update_tree_item_paths_recursive(self, item, old_base, new_base):
        """
        Recursively update paths stored in UserRole for this tree item and its children.
        """
        old_path = item.data(0, Qt.UserRole)
        if not old_path:
            return

        if old_path.startswith(old_base):
            relative_tail = os.path.relpath(old_path, old_base)
            new_path = os.path.join(new_base, relative_tail)
            item.setData(0, Qt.UserRole, new_path)
            print(f"Updated tree item path: {old_path} → {new_path}")

        for i in range(item.childCount()):
            self.update_tree_item_paths_recursive(item.child(i), old_base, new_base)

    def rename_folder_or_playlist(self, item, column):
        old_path = item.data(0, Qt.UserRole)
        if not old_path:
            return

        is_playlist = old_path.endswith(".m3u")
        parent_dir = os.path.dirname(old_path)

        new_name = item.text(0).strip()
        current_name = os.path.splitext(os.path.basename(old_path))[0] if is_playlist else os.path.basename(old_path)

        # ✅ Ignore if the text didn't actually change
        if new_name == current_name:
            return

        # Continue as before...
        new_name_full = new_name + ".m3u" if is_playlist else new_name
        new_path = os.path.join(parent_dir, new_name_full)

        if new_path == old_path:
            return

        if os.path.exists(new_path):
            QMessageBox.warning(self, "Rename Failed", "A file or folder with that name already exists.")
            item.setText(0, current_name)
            return

        try:
            os.rename(old_path, new_path)
            item.setData(0, Qt.UserRole, new_path)
            print(f"Renamed: {old_path} → {new_path}")
            self.update_tree_item_paths_recursive(item, old_path, new_path)

            if not is_playlist and os.path.isdir(new_path):
                self.update_playlist_paths(old_path, new_path)

        except Exception as e:
            QMessageBox.critical(self, "Rename Failed", f"Could not rename:\n{e}")
            item.setText(0, current_name)
                                        
    def create_new_playlist(self, parent_item=None):
        if parent_item and os.path.isdir(parent_item.data(0, Qt.UserRole)):
            base_path = parent_item.data(0, Qt.UserRole)
        else:
            base_path = self.working_dir

        playlist_name = "New Playlist"
        new_playlist_path = os.path.join(base_path, f"{playlist_name}.m3u")
        index = 1
        while os.path.exists(new_playlist_path):
            new_playlist_path = os.path.join(base_path, f"{playlist_name} {index}.m3u")
            index += 1

        try:
            with open(new_playlist_path, "w", encoding="utf-8") as f:
                f.write("#EXTM3U\n")

            # Create tree item
            new_item = QTreeWidgetItem()
            new_item.setText(0, os.path.splitext(os.path.basename(new_playlist_path))[0])
            new_item.setData(0, Qt.UserRole, new_playlist_path)
            new_item.setIcon(0, QIcon(PLAYLIST_ICON_PATH))
            new_item.setFlags(new_item.flags() | Qt.ItemIsEditable)

            # Insert into correct folder in tree
            if parent_item and os.path.isdir(parent_item.data(0, Qt.UserRole)):
                parent_item.addChild(new_item)
                parent_item.setExpanded(True)
            else:
                root = self.ui.folder_view.topLevelItem(0)
                if root:
                    root.addChild(new_item)
                    root.setExpanded(True)
                else:
                    self.ui.folder_view.addTopLevelItem(new_item)

            self.ui.folder_view.setCurrentItem(new_item)
            self.ui.folder_view.editItem(new_item, 0)
            # update the mp3 list since a new playlist was just created
            # we have to trigger this manually
            self.load_mp3list_from_path()
            

            print(f"Created playlist: {new_playlist_path}")
        except Exception as e:
            QMessageBox.critical(self, "Playlist Creation Failed", f"Could not create playlist:\n{e}")

    def create_new_folder(self, parent_item):
        # Determine base path
        if parent_item and os.path.isdir(parent_item.data(0, Qt.UserRole)):
            base_path = parent_item.data(0, Qt.UserRole)
        else:
            base_path = self.working_dir

        folder_name = "New Folder"
        new_folder_path = os.path.join(base_path, folder_name)
        index = 1
        while os.path.exists(new_folder_path):
            new_folder_path = os.path.join(base_path, f"{folder_name} {index}")
            index += 1

        try:
            os.makedirs(new_folder_path)

            # Create QTreeWidgetItem
            new_item = QTreeWidgetItem()
            new_item.setText(0, os.path.basename(new_folder_path))
            new_item.setData(0, Qt.UserRole, new_folder_path)
            new_item.setIcon(0, QIcon(FOLDER_ICON_PATH))
            new_item.setFlags(new_item.flags() | Qt.ItemIsEditable)

            # Insert into tree
            if parent_item and os.path.isdir(parent_item.data(0, Qt.UserRole)):
                parent_item.addChild(new_item)
                parent_item.setExpanded(True)
            else:
                root = self.ui.folder_view.topLevelItem(0)
                if root:
                    root.addChild(new_item)
                    root.setExpanded(True)
                else:
                    self.ui.folder_view.addTopLevelItem(new_item)

            self.ui.folder_view.setCurrentItem(new_item)
            self.ui.folder_view.editItem(new_item, 0)

            print(f"Created folder: {new_folder_path}")
            #refresh mp3list... lets see if this works
            self.load_mp3list_from_path()
        except Exception as e:
            QMessageBox.critical(self, "Folder Creation Failed", f"Could not create folder:\n{e}")

    def load_settings(self):

        #define a safe default
        theme = "arcana"

        try:
            with open(SETTINGS_FILE, 'r') as f:
                settings = json.load(f)

                # Restore window size
                window_size = settings.get("window_size")
                if window_size and isinstance(window_size, list) and len(window_size) == 2:
                    self.resize(window_size[0], window_size[1])

                # Restore Horizontal splitter settings
                splitter_sizes = settings.get("h_splitter_sizes")
                if splitter_sizes:
                    self.splitter.setSizes(splitter_sizes)

                # Restore splitter sizes
                splitter_sizes = settings.get("v_splitter_sizes")
                if splitter_sizes:
                    self.mainSplitter.setSizes(splitter_sizes)

                # Restore theme or set default to arcana
                theme = settings.get("theme")
                if theme is None:
                    theme = "arcana"
                self.set_theme(theme)

                # Restore volume settings
                volume = settings.get("volume")
                if isinstance(volume, int):
                    self.audio_output.setVolume(volume / 100)
                    self.ui.volume_slider.setValue(volume)  # sync the slider UI
                    self.set_volume()

                # Restore selected tab
                selected_tab = settings.get("selected_tab")
                if isinstance(selected_tab, int) and 0 <= selected_tab < self.ui.tabWidget.count():
                    self.ui.tabWidget.setCurrentIndex(selected_tab)
                else:
                    self.ui.tabWidget.setCurrentIndex(0)  # Default to Decurse tab

            
        except Exception as e:
            print("Error Loading Settings File:", e)
            self.set_theme(theme)

    def save_working_dir(self):
        """
        Persist the root music folder (working_dir) immediately.
        We keep this separate so changing the folder doesn't depend on a clean shutdown.
        """
        try:
            if os.path.exists(SETTINGS_FILE):
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    settings = json.load(f)
            else:
                settings = {}

            settings["working_dir"] = self.working_dir

            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(settings, f, indent=4)

            print(f"[settings] Saved working_dir: {self.working_dir}")
        except Exception as e:
            print("[settings] Failed to save working_dir:", e)

    def closeEvent(self, event):
        print("Close Event Detected")
        try:
            # Save playlist order if needed
            #if self.playlist_paths:
            #    self.save_current_playlist_order()

            settings = {}
            if os.path.exists(SETTINGS_FILE):
                with open(SETTINGS_FILE, 'r') as f:
                    settings = json.load(f)

            settings["working_dir"] = self.working_dir
            settings["h_splitter_sizes"] = self.splitter.sizes()
            settings["window_size"] = [self.width(), self.height()]
            settings["v_splitter_sizes"] = self.mainSplitter.sizes()
            settings["volume"] = int(self.audio_output.volume() * 100)
            settings["selected_tab"] = self.ui.tabWidget.currentIndex()


            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(settings, f, indent=4)
            print("[settings] Settings saved.")
        except Exception as e:
            print("Failed to save settings:", e)
        super().closeEvent(event)

    def remove_mp3_from_playlist(self, playlist_path, mp3_name):
        with open(playlist_path, 'r') as file:
            lines = file.readlines()
        with open(playlist_path, 'w') as file:
            for line in lines:
                if not line.strip().endswith(mp3_name):
                    file.write(line)

    def move_to_trash(self, file_path):
        trash_dir = os.path.join(self.working_dir, ".trash")
        os.makedirs(trash_dir, exist_ok=True)
        base_name = os.path.basename(file_path)
        trash_path = os.path.join(trash_dir, base_name)
        #shutil.move(file_path, trash_path)
        self.move_file_or_folder(file_path, trash_path)

    def send_mp3_duel(self, filepath):
        if not hasattr(self, "player2") or self.player2 is None:
            # Init all the Duel Play QMedia and AudioOutput
            self.player2 = QMediaPlayer()
            self.audio_output2 = QAudioOutput()
            self.player2.setAudioOutput(self.audio_output2)
            # Assign the volume from the duel volume slider
            volume = self.ui.duel_volume_slider.value() / 100.0
            self.audio_output2.setVolume(volume)
            # Route duel audio into the visualizer + keep the timer alive while it plays
            self._attach_visualizer(self.player2, "duel")
            self.player2.playbackStateChanged.connect(self._update_viz_timer)
            # Connect progress and volume slider
            self.player2.positionChanged.connect(self.duel_update_progress)
            self.player2.durationChanged.connect(self.set_duel_progress_range)
            self.player2.mediaStatusChanged.connect(self.handle_duel_media_status)
            self.duel_slider_being_moved = False
            self.ui.duel_progress_slider.sliderMoved.connect(self.duel_seek)
            self.ui.duel_progress_slider.sliderReleased.connect(self.duel_seek)
            self.ui.duel_progress_slider.sliderPressed.connect(self.duel_slider_pressed)
            self.ui.duel_progress_slider.sliderReleased.connect(self.duel_slider_released)

        self.update_title_art(filepath, self.ui.duel_playing_text_label, self.ui.duel_cover_art_label)        

        def try_play(status):
            if status == QMediaPlayer.MediaStatus.LoadedMedia:
                print("Duel Play: Play started by mediaStatusChanged signal")
                self.player2.play()
                # Another Play Hack
                QTimer.singleShot(100, lambda: self.player2.setPosition(0))
                self.player2.mediaStatusChanged.disconnect(try_play)

        def fallback_play():
            if self.player2.playbackState() != QMediaPlayer.PlayingState:
                print("Duel Play: Fallback play triggered by timer")
                self.player2.play()
                # Another Play Hack
                QTimer.singleShot(100, lambda: self.player2.setPosition(0))

        # Connect signal before setting the source
        self.player2.mediaStatusChanged.connect(try_play)
        self.player2.setSource(QUrl.fromLocalFile(filepath))
        self.duel_selected_mp3path = filepath;

        # Final fallback: timer after 500ms
        QTimer.singleShot(500, fallback_play)

    def handle_duel_media_status(self, status):
        if status == QMediaPlayer.EndOfMedia:
            if self.ui.duelrepeat_checkBox.isChecked():
                    self.send_mp3_duel(self.duel_selected_mp3path)

    def duel_stop(self):
        print("Duel Play: Stop and unload the player")
        self.player2.stop()
        self.player2.playbackStateChanged.disconnect(self._update_viz_timer)
        self.player2.positionChanged.disconnect(self.duel_update_progress)
        self.player2.durationChanged.disconnect(self.set_duel_progress_range)
        self.player2.mediaStatusChanged.disconnect(self.handle_duel_media_status)
        self.ui.duel_progress_slider.sliderReleased.disconnect(self.duel_seek)
        self.ui.duel_progress_slider.sliderMoved.disconnect(self.duel_seek)
        self.duel_slider_being_moved = False
        self.ui.duel_progress_slider.sliderPressed.disconnect(self.duel_slider_pressed)
        self.ui.duel_progress_slider.sliderReleased.disconnect(self.duel_slider_released)
        #duel_update_progress
        self._detach_visualizer("duel")
        self.player2.deleteLater()
        self.audio_output2.deleteLater()
        self.player2 = None
        self.audio_output2 = None
        # Stop the visualizer timer if the main player isn't playing either.
        self._update_viz_timer()

    def duel_play(self):
        if self.player2 is None:
            # was previously stopped and unloaded, need to send_mp3_duel again
            self.send_mp3_duel(self.duel_selected_mp3path)
        else:
            # was previously paused, safe to just hit play on qmediaplayer
            print("Duel Play: MP3 already loaded")
            if self.player2.source().isEmpty():
                print("Duel Play: No file selected to play.")
                return
            self.player2.play()

    def duel_pause(self):
        self.player2.pause()

    def set_duel_progress_range(self, duration):
        if duration > 0:
            self.ui.duel_progress_slider.setRange(0, duration)

    def duel_seek(self):
        if self.player2 is not None:
            if self.player2.duration() > 0:
                self.player2.setPosition(self.ui.duel_progress_slider.value())

    def duel_slider_pressed(self):
        if self.player2 is not None:
            self.duel_slider_being_moved = True

    def duel_slider_released(self):
        if self.player2 is not None:
            self.duel_slider_being_moved = False
            self.duel_seek()

    def duel_update_progress(self, position):
        if not self.duel_slider_being_moved:
            self.ui.duel_progress_slider.setValue(position)

        song_seconds = self.ui.duel_progress_slider.maximum() // 1000
        current_seconds = position // 1000
        current_min = current_seconds // 60
        current_sec = current_seconds % 60
        self.ui.label_duelseektimetext.setText(f"Time: {current_min:02d}:{current_sec:02d}")
        rem_min = (song_seconds - current_seconds) // 60
        rem_sec = (song_seconds - current_seconds) % 60
        song_min = song_seconds // 60
        song_sec = song_seconds % 60
        self.ui.label_duelremainingtimetext.setText(f"Remaining: {rem_min:02d}:{rem_sec:02d} of {song_min:02d}:{song_sec:02d}")

    def duel_set_volume(self):
        volume = self.ui.duel_volume_slider.value() / 100.0
        self.ui.label_duelvolumetext.setText(f"Volume: {int(volume * 100)}%")
        # Only attempt to change audio_output2 if it exists
        if self.audio_output2 is not None:
            self.audio_output2.setVolume(volume)

    def update_title_art(self, fullpath, titlelabel, artlabel):
        title = os.path.basename(fullpath)
        titlelabel.setText(f"Playing: {title}")
        artlabel.clear()
        artlabel.setStyleSheet("background: transparent;")
        artlabel.setAlignment(Qt.AlignCenter)

        try:
            tags = ID3(fullpath)
            for tag in tags.values():
                if tag.FrameID == "APIC":
                    image_data = tag.data
                    image = Image.open(BytesIO(image_data)).convert("RGBA")
                    pixmap = self.cropscale_coverart(image, artlabel)
                    artlabel.setPixmap(pixmap)
                    print("Duel Play: Displaying Found CoverArt")
                    return  # Stop after displaying the first APIC image

            # No APIC image was found, now try to display the icon
            if os.path.exists(ICON_PATH):
                image = Image.open(ICON_PATH)
                pixmap = self.cropscale_coverart(image, artlabel)
                artlabel.setPixmap(pixmap)
            else:
                # Display Text as a last resort
                artlabel.setStyleSheet("background-color: transparent; color: white; text-align: center;")
                artlabel.setText("No Artwork")

        except Exception as e:
            print(f"Error Displaying Cover Art: {e}")
        
    def cropscale_coverart(self, image, artlabel):
        # Process CoverArt and apply to CoverArt Label
        target_width = artlabel.width()
        target_height = artlabel.height()
        
        # Determine the aspect ratio of the QLabel and the image
        label_aspect_ratio = target_width / target_height
        image_aspect_ratio = image.width / image.height
        
        # Crop the image to match the QLabel's aspect ratio
        if image_aspect_ratio > label_aspect_ratio:
            # Image is too wide
            new_width = int(image.height * label_aspect_ratio)
            crop_area = (image.width - new_width) // 2
            image = image.crop((crop_area, 0, image.width - crop_area, image.height))
        elif image_aspect_ratio < label_aspect_ratio:
            # Image is too tall
            new_height = int(image.width / label_aspect_ratio)
            crop_area = (image.height - new_height) // 2
            image = image.crop((0, crop_area, image.width, image.height - crop_area))

        # Convert to QPixmap to display in QLabel
        qt_image = ImageQt(image)  # Correctly use ImageQt to convert PIL image to QImage
        pixmap = QPixmap.fromImage(qt_image)
        pixmap = pixmap.scaled(artlabel.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        return pixmap

class MP3ListWidget(QListWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setDragEnabled(True)
        self.setDropIndicatorShown(False)
        self.setDragDropMode(QAbstractItemView.DragDrop)
        self.setDragDropMode(QAbstractItemView.InternalMove)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        connected = self.customContextMenuRequested.connect(self.show_custom_context_menu) #change custom to mp3list or similar
        self.placeholder = None  # Placeholder for the visual indicator
        self.placeholderIndex = -1  # Track the index of the placeholder
        self.draggedItemText = None  # Text of the item being dragged

    #needed for dropevent to be able to trigger even though we aren't using it
    def dragEnterEvent(self, event):
        #super().dragEnterEvent(event)
        if event.mimeData().hasFormat("application/x-mp3-song") or event.source() == self:
            event.accept()
        else:
            super().dragEnterEvent(event)

    # Event Triggered when starting a drag from within QListWidget Window
    def startDrag(self, supportedActions):
        print("mp3list - startDrag")
        item = self.currentItem()
        if not item:
            return

        self.draggedItemText = self.currentItem().text() if self.currentItem() else None
        print(f"mp3list startDrag text:{self.draggedItemText}")

        mime_data = QMimeData()
        full_path = os.path.join(self.window().current_mp3_folder, item.text())
        mime_data.setData("application/x-mp3-song", full_path.encode("utf-8"))

        drag = QDrag(self)
        drag.setMimeData(mime_data)
        drag.exec(Qt.CopyAction | Qt.MoveAction)
            
    def dragMoveEvent(self, event):
        if event.mimeData().hasFormat("application/x-mp3-song") or event.source() == self:
            event.setDropAction(Qt.MoveAction)
            if self.window().MP3ListisPlaylist == True:
                target_index = self.indexAt(event.pos()).row()
                if target_index != self.placeholderIndex:
                    self.updatePlaceholder(target_index)          
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dragLeaveEvent(self, event):
        self.removePlaceholder()
        super().dragLeaveEvent(event)

    def dropEvent(self, event):
        #event.acceptProposedAction()  # Explicitly accept the event
        print("mp3list - drop event")
        if self.window().MP3ListisPlaylist == True and event.source() == self:
            super().dropEvent(event) #do the original function which allows the reorder
            self.removePlaceholder()
            self.draggedItemText = None  # Clear the dragged item text
            
            # Revalidate or reattach data to items if necessary
            #for i in range(self.count()):
            #    item = self.item(i)
            #    # Reattach the path or update it as needed
            #    item.setData(Qt.UserRole, compute_new_path_based_on_order(i, item.text()))
            
            #self.window().save_current_playlist_order()
            
            event.accept()
            
            parent = self.window()
            if hasattr(parent, "playlist_paths") and parent.playlist_paths:
                parent.save_current_playlist_order()
        else:
            event.ignore()

    def updatePlaceholder(self, index):
        self.removePlaceholder()
        if index == -1:  # Append to the end if no valid index
            index = self.count()
        #self.placeholder = QListWidgetItem("Dropping here...")
        print(f"updatePlaceholder text:{self.draggedItemText}")
        self.placeholder = QListWidgetItem(self.draggedItemText if self.draggedItemText else "Dropping here...")
        self.placeholder.setFlags(Qt.NoItemFlags)  # Make the placeholder not selectable or interactable
        self.placeholder.setForeground(QBrush(QColor(150, 150, 150)))  # Gray color
        self.insertItem(index, self.placeholder)
        self.placeholderIndex = index

    def removePlaceholder(self):
        if self.placeholder:
            self.takeItem(self.row(self.placeholder))
        self.placeholder = None
        self.placeholderIndex = -1

    def show_custom_context_menu(self, position):
        print("Show MP3List Right-Click Menu")
        menu = QMenu()
        current_path = self.window().get_current_mp3list_path()
        if current_path.endswith('.m3u'):
            remove_action = menu.addAction("Remove From Playlist")
            remove_action.triggered.connect(self.remove_from_playlist)
        else:
            delete_action = menu.addAction("Delete MP3")
            delete_action.triggered.connect(self.delete_mp3)
        sendduel_action = menu.addAction("Send MP3 to Duel")
        sendduel_action.triggered.connect(self.send_mp3_duel)

        menu.exec(self.mapToGlobal(position))

    def remove_from_playlist(self):
        item = self.currentItem()
        if item:
            playlist_path = self.window().get_current_mp3list_path()
            # Remove the item from the .m3u file
            self.window().remove_mp3_from_playlist(playlist_path, item.text())
            # Refresh the mp3 list
            self.window().load_mp3list_from_path()

    def send_mp3_duel(self):
        try:
            item = self.currentItem()
            # Catch if item exists
            if not item:
                raise ValueError("No valid item selected")
            
            mp3_path = os.path.join(self.window().current_mp3_folder, item.text())
            # Catch is valid path
            if not os.path.isfile(mp3_path):
                raise FileNotFoundError(f"File not found: {mp3_path}")
            
            if not mp3_path.lower().endswith(".mp3"):
                raise ValueError("Selected file is not a valid MP3.")            
            
            print(f"Sending {mp3_path} to Duel")
            self.window().send_mp3_duel(mp3_path)

        except Exception as e:
            print(f"⚠️ [Duel] Error: {e}")
            

    def delete_mp3(self):
        item = self.currentItem()
        if item:
            confirm = QMessageBox.question(self, "Confirm Delete", "Are you sure you want to delete this MP3?",
                                           QMessageBox.Yes | QMessageBox.No)
            if confirm == QMessageBox.Yes:
                mp3_path = os.path.join(self.window().current_mp3_folder, item.text())
                # Move the file to the trash
                self.window().move_to_trash(mp3_path)
                # Refresh the mp3 list
                self.window().load_mp3list_from_path()

class FolderTreeWidget(QTreeWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.player = parent
        self.setHeaderHidden(True)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QTreeWidget.InternalMove)
        self.setDefaultDropAction(Qt.MoveAction)
        self._hovered_item = None  # Track hovered item during drag
    
    # In FolderTreeWidget
    def startDrag(self, supportedActions):
        #This was definitely needed. I think I had issues where moving would cause the name to change and then
        # the logic inside the rename_folder_or_playlist would accidentally trigger the rename
        try:
            self.itemChanged.disconnect(self.player.rename_folder_or_playlist)
        except TypeError:
            pass
        super().startDrag(supportedActions)

    def populate_from_path(self, base_path):
        self.clear()

        def add_items(parent_item, path):
            try:
                for item in sorted(os.listdir(path)):
                    full_path = os.path.join(path, item)
                    if os.path.isdir(full_path) or item.endswith(".m3u"):
                        tree_item = QTreeWidgetItem()
                        tree_item.setFlags(tree_item.flags() | Qt.ItemIsEditable)
                        display_name = item[:-4] if item.endswith(".m3u") else item
                        tree_item.setText(0, display_name)
                        tree_item.setData(0, Qt.UserRole, full_path)
                        icon = QIcon(PLAYLIST_ICON_PATH) if item.endswith(".m3u") else QIcon(FOLDER_ICON_PATH)
                        tree_item.setIcon(0, icon)
                        parent_item.addChild(tree_item)
                        if os.path.isdir(full_path):
                            add_items(tree_item, full_path)
            except Exception as e:
                print("Error reading folder:", path, e)

        root = QTreeWidgetItem()
        root.setText(0, os.path.basename(base_path))
        root.setData(0, Qt.UserRole, base_path)
        root.setIcon(0, QIcon(FOLDER_ICON_PATH))
        self.addTopLevelItem(root)
        self.expandItem(root)
        add_items(root, base_path)

      
    def dropEvent(self, event):
        # reconnect itemChanged in dropEvent or dragLeaveEvent
        QTimer.singleShot(0, lambda: self.itemChanged.connect(self.player.rename_folder_or_playlist))
        print("drop event triggering")
        
        # Clear the highlight on drop
        if self._hovered_item:
            original_path = self._hovered_item.data(0, Qt.UserRole)
            original_icon = QIcon(PLAYLIST_ICON_PATH) if original_path.endswith(".m3u") else QIcon(FOLDER_ICON_PATH)
            self._hovered_item.setBackground(0, Qt.transparent)
            self._hovered_item.setIcon(0, original_icon)
            self._hovered_item = None

        # Prevent a Playlist/Folder from the Tree from getting dropped on a Playlist in the Tree
        pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
        target_item = self.itemAt(pos)
        target_path = target_item.data(0, Qt.UserRole) if target_item else None
        source_widget = event.source()

        # Reject folder/playlist drops onto playlists
        if source_widget == self and (target_path.endswith(".m3u") and self.dropIndicatorPosition() == QAbstractItemView.OnItem) : 
            print("Invalid Move", "You cannot move Folders/Playlists from Tree into a Playlist.")
            event.ignore()
            return

        if event.mimeData().hasFormat("application/x-mp3-song") and self.window().MP3ListisPlaylist == False:
            pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
            target_item = self.itemAt(pos)
           
            if target_item:
                target_path = target_item.data(0, Qt.UserRole)
                song_path = bytes(event.mimeData().data("application/x-mp3-song")).decode("utf-8").strip()

                if target_path.endswith('.m3u'):
                    # Adding to a playlist, update with a relative path
                    relative_path = os.path.relpath(song_path, self.window().working_dir)
                    with open(target_path, 'a', encoding='utf-8') as f:
                        f.write(f"{relative_path}\n")
                    print(f"Added {relative_path} to playlist {target_path}")
                    ##self.window().ui.mp3_list.addItem(os.path.basename(song_path))  # Update the list view
                    event.acceptProposedAction()

                elif os.path.isdir(target_path):
                    # Physically moving the MP3 to another folder
                    new_song_path = os.path.join(target_path, os.path.basename(song_path))

                    # ✅ Safety check: make sure file still exists
                    if not os.path.exists(song_path):
                        print(f"❌ Dragged file no longer exists on disk: {song_path}")
                        QMessageBox.warning(self, "File Not Found", f"The file could not be found:\n{song_path}")
                        event.ignore()
                        return

                    ##testing new logic that should work on windows and linux to stop the file if playing for a move
                    
                    print("about to call move file")
                    self.player.move_file_or_folder(song_path, new_song_path)


                    self.window().update_playlist_paths(os.path.dirname(song_path), target_path)  # Update playlists that might reference this file
                    # Refresh the MP3list
                    self.window().load_mp3list_from_path()            
                    print(f"Moved {song_path} to {new_song_path}")
                    event.acceptProposedAction()
                return
        
        super().dropEvent(event)

        # ✅ Only sync if drag originated from this tree widget
        if event.source() == self:
            QTimer.singleShot(0, self.sync_tree_to_disk)

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat("application/x-mp3-song"):
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        source_widget = event.source()
        pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
        target_item = self.itemAt(pos)
        target_path = target_item.data(0, Qt.UserRole) if target_item else None

        # This would be nice to not draw the rectangle around a playlist when the drag was a playlist but...
        #  it's causing too much bugginess sometimes drawing the rectangle anyways, qt still draws it and it would
        #  require overriding the drawdropindicator. and also the line above and below still doesn't always draw
        #  not only this but i ended up using the presence of the rectangle box to help with not allowing items to
        #  be dropped onto playlist
                
        # Drag came from MP3List
        if event.mimeData().hasFormat("application/x-mp3-song"):
            #print("hover event: has format application/x-mp3-song")
            event.acceptProposedAction()
            if target_item != self._hovered_item:
                # Reset previous hover item
                if self._hovered_item:
                    prev_path = self._hovered_item.data(0, Qt.UserRole)
                    if isinstance(prev_path, str):
                        prev_icon = QIcon(PLAYLIST_ICON_PATH) if prev_path.endswith(".m3u") else QIcon(FOLDER_ICON_PATH)
                        self._hovered_item.setBackground(0, Qt.transparent)
                        self._hovered_item.setIcon(0, prev_icon)
                self._hovered_item = target_item
            if self._hovered_item:
                full_path = self._hovered_item.data(0, Qt.UserRole)
                if isinstance(full_path, str):
                    self._hovered_item.setBackground(0, QColor(110, 86, 169, 80))  # Light purple
                    if self.window().MP3ListisPlaylist:
                        # MP3 list is showing a playlist
                        if full_path.endswith(".m3u"):
                            icon = QIcon(PLAYLIST_NO_ICON_PATH)
                        else:
                            icon = QIcon(FOLDER_NO_ICON_PATH)
                    else:
                        # MP3 list is showing a folder
                        if full_path.endswith(".m3u"):
                            icon = QIcon(PLAYLIST_YES_ICON_PATH)
                        else:
                            icon = QIcon(FOLDER_YES_ICON_PATH)
                    self._hovered_item.setIcon(0, icon)

        # Drag came from Tree
        elif source_widget == self:
            event.acceptProposedAction()
            # Lets not do Icons or Hover Shading with Tree Moves because it doesn't Line Up or match with
            #  the default super().dragMoveEvent(event) behavior we are relying on
            # Perform the default handler for Tree events
            super().dragMoveEvent(event)


    def dragLeaveEvent(self, event):

        QTimer.singleShot(0, lambda: self.itemChanged.connect(self.player.rename_folder_or_playlist))

        if self._hovered_item:
            original_path = self._hovered_item.data(0, Qt.UserRole)
            original_icon = QIcon(PLAYLIST_ICON_PATH) if original_path.endswith(".m3u") else QIcon(FOLDER_ICON_PATH)
            self._hovered_item.setBackground(0, Qt.transparent)
            self._hovered_item.setIcon(0, original_icon)
            self._hovered_item = None
        super().dragLeaveEvent(event)

    def sync_tree_to_disk(self):
        def walk_items(parent):
            for i in range(parent.childCount()):
                child = parent.child(i)
                yield parent, child
                yield from walk_items(child)

        moved_anything = False
        for parent, item in walk_items(self.invisibleRootItem()):
            old_path = item.data(0, Qt.UserRole)
            if not old_path:
                continue

            parent_path = parent.data(0, Qt.UserRole)
            if not parent_path or not os.path.isdir(parent_path):
                continue

            # Don't allow moving into a .m3u file
            if parent_path.endswith(".m3u"):
                QMessageBox.warning(self, "Invalid Move", "You can't move a folder or playlist into a playlist.")
                self.populate_from_path(self.window().working_dir)
                return

            name = os.path.basename(old_path)
            new_path = os.path.join(parent_path, name)

            # Skip if nothing changed
            if self.paths_equal(old_path, new_path):
                continue

            # Skip if parent already moved this item
            if not os.path.exists(old_path):
                print(f"⏩ Skipping move for {old_path} — already moved with parent.")
                continue

            # Prevent overwriting something that isn't the same path
            if os.path.exists(new_path) and not self.paths_equal(old_path, new_path):
                print("❗️Path collision detected — triggering warning dialog")
                QMessageBox.warning(self, "Move Failed", f"A file or folder with that name already exists:\n{new_path}")
                self.populate_from_path(self.window().working_dir)
                return

            print("🔍 Sync Check")
            print(f"  old_path: {old_path}")
            print(f"  new_path: {new_path}")
            print(f"  exists(new_path): {os.path.exists(new_path)}")
            print(f"  paths_equal(old, new): {self.paths_equal(old_path, new_path)}")

            try:
                self.player.move_file_or_folder(old_path, new_path)
            except Exception as e:
                QMessageBox.critical(self, "Move Failed", f"Could not move:\n{e}")
                self.populate_from_path(self.window().working_dir)
                return

            # ✅ Only update internal state if the move was successful
            item.setData(0, Qt.UserRole, new_path)
            moved_anything = True

            if not old_path.endswith(".m3u") and os.path.isdir(new_path):
                self.window().update_playlist_paths(old_path, new_path)

        if moved_anything:
            print("✅ Folder tree sync complete.")

    def paths_equal(self, path1, path2):
        """Cross-platform comparison of two paths."""
        if platform.system() == "Windows":
            return os.path.normcase(os.path.abspath(path1)) == os.path.normcase(os.path.abspath(path2))
        return os.path.abspath(path1) == os.path.abspath(path2)

class ClickSliderWidget(QSlider):
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            value = QStyle.sliderValueFromPosition(
                self.minimum(), self.maximum(),
                event.position().x(), self.width()
            )
            self.setValue(value)
            self.sliderMoved.emit(value)
        super().mousePressEvent(event)

class YTDLPLogger:
    def __init__(self, player=None, thread=None):
        self.player = player
        self.thread = thread

    def debug(self, msg):
        print(f"[yt_dlp] {msg}")

        # ✅ Send to GUI if available
        if self.player:
            try:
                self.player.add_dl_text_sig.emit(f"[yt_dlp] {msg}")
            except Exception:
                pass

        # ✅ Detect extraction start and trigger thread-based feedback
        if "[ExtractAudio]" in msg and "Destination" in msg:
            if self.thread:
                try:
                    self.thread.start_extract_feedback()
                except Exception:
                    pass

    def warning(self, msg):
        print(f"[yt_dlp][Warning] {msg}")
        if self.player:
            try:
                self.player.add_dl_text_sig.emit(f"[yt_dlp][Warning] {msg}")
            except Exception:
                pass

    def error(self, msg):
        print(f"[yt_dlp][Error] {msg}")
        if self.player:
            try:
                self.player.add_dl_text_sig.emit(f"[yt_dlp][Error] {msg}")
            except Exception:
                pass

class DownloadThread(QThread):
    progress = Signal(int)
    finished = Signal(str)
    error = Signal(str)

    def __init__(self, url, download_path, player_instance):
        super().__init__()
        self.url = url
        self.download_path = Path(download_path)
        self.player_instance = player_instance

    def run(self):
        print("[downlord] Download Task started")

        # ✅ Clean up old download.* files before starting
        for ext in ['.mp3', '.webm', '.webp', '.jpg', '.jpeg', '.png']:
            candidate = self.download_path / f'download{ext}'
            if candidate.exists():
                try:
                    candidate.unlink()
                    print(f"[downlord] Deleted leftover file: {candidate}")
                except Exception as e:
                    print(f"[downlord] Failed to delete {candidate}: {e}")

        logger = YTDLPLogger(player=self.player_instance, thread=self)

        try:
            def progress_hook(d):
                if d['status'] == 'downloading':
                    progress = float(d['_percent_str'].strip('%'))
                    self.progress.emit(progress)
                elif d['status'] == 'finished':
                    self.finished.emit(f"Downloaded: {d['filename']}")
                elif d['status'] == 'error':
                    self.error.emit("Download failed.")

            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': os.path.join(self.download_path, 'download.%(ext)s'),
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
                'writethumbnail': True,
                'noplaylist': True,
                'progress_hooks': [progress_hook],  # ✅ This was missing
                'logger': logger,  # ✅ This is what fixes the error
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info_dict = ydl.extract_info(self.url, download=True)
                video_title = info_dict.get('title', 'downloaded_audio')
                audio_file = f"download.mp3"

                # 🔍 Look for downloaded thumbnail (any known format)
                thumbnail_file = None
                for ext in ['.webp', '.jpg', '.jpeg', '.png']:
                    candidate = os.path.join(self.download_path, f"download{ext}")
                    if os.path.exists(candidate):
                        thumbnail_file = f"download{ext}"
                        break

                if thumbnail_file is None:
                    print("[downlord] ❌ No thumbnail found.")
                    self.error.emit("No thumbnail was found after download.")
                    return

            # Embed the thumbnail into the MP3 file
            mp3path = Path(self.download_path) / audio_file
            imagepath = Path(self.download_path) / thumbnail_file

            print(f"[downlord] MP3 File:{mp3path}")
            print(f"[downlord] Thumbnail:{imagepath}")

            self.embed_thumbnail_in_mp3(str(mp3path), str(imagepath))

            #sanitize the filename
            filename = f"{self.sanitize_filename(video_title)}.mp3"
            #filename = f"{video_title}.mp3"

            self._extracting = False
            #rename the file
            final_path = self.get_unique_filename(Path(self.download_path) / filename)
            mp3path.rename(final_path)

            #print(f"[downlord] Renaming: download.mp3 to {filename}")
            print(f"[downlord] Renaming: download.mp3 to {final_path}")

        except Exception as e:
            print(f"[downlord] Exception in Download Task: {e}")
            self.error.emit(str(e))

        # ✅ Clean up download.* files after
        for ext in ['.mp3', '.webm', '.webp', '.jpg', '.jpeg', '.png']:
            candidate = self.download_path / f'download{ext}'
            if candidate.exists():
                try:
                    candidate.unlink()
                    print(f"[downlord] Deleted leftover file: {candidate}")
                except Exception as e:
                    print(f"[downlord] Failed to delete {candidate}: {e}")

        print(f"[downlord] {filename} Done!")
        print("[downlord] Download Task completed")
        self.finished.emit("NA")

    def start_extract_feedback(self):
        self._extracting = True
        self._extract_count = 0
        print(f"[downlord] Extracting Audio")

        def feedback_loop():
            while self._extracting: #and self._extract_count < 20:
                dots = '.' * (self._extract_count % 4)
                print("[append] . ")
                self._extract_count += 1
                time.sleep(0.15)
            if self._extracting:
                print("[downlord] ✅ Extraction complete")

        threading.Thread(target=feedback_loop, daemon=True).start()

    def get_unique_filename(self, path: Path) -> Path:
        """Return a non-conflicting path by appending (1), (2), etc. if needed."""
        if not path.exists():
            return path
        base = path.stem
        suffix = path.suffix
        parent = path.parent
        index = 1
        while True:
            new_path = parent / f"{base} ({index}){suffix}"
            if not new_path.exists():
                return new_path
            index += 1

    def embed_thumbnail_in_mp3(self, audio_file, thumbnail_file):
        # Load the MP3 file, or create an ID3 tag if none exists
        audio = MP3(audio_file, ID3=ID3)

        # Ensure there is an ID3 tag
        if audio.tags is None:
            audio.add_tags()

        # Open the image file to embed
        with open(thumbnail_file, 'rb') as img_file:
            img_data = img_file.read()

        # MIME type of the image, change 'image/webp' to match your actual image type
        mime_type = 'image/jpeg' if thumbnail_file.lower().endswith('.jpg') else 'image/webp' if thumbnail_file.lower().endswith('.webp') else 'image/png'

        # Add or update the APIC frame
        # If an APIC frame already exists, it will be replaced
        audio.tags.add(
            APIC(
                encoding=3,  # 3 is for UTF-8
                mime=mime_type,  # MIME type
                type=3,  # 3 is for cover image
                desc='Cover',
                data=img_data
            )
        )

        # Save changes
        audio.save()

    def sanitize_filename(self, title):
        """
        Sanitizes a string to be safe for use as a filename by removing special characters,
        and limits the length of the filename to be safe for most file systems.
        """
        # Remove any character that is not a word character, space, or hyphen
        sanitized = re.sub(r'[^\w\s-]', '', title)
        
        # Replace spaces or consecutive hyphens with a single hyphen
        sanitized = re.sub(r'[-\s]+', '-', sanitized)
        
        # Strip leading/trailing hyphens
        sanitized = sanitized.strip('-')
        
        # Optionally, truncate the filename to avoid length issues on certain file systems
        max_length = 255
        if len(sanitized) > max_length:
            # Limit to max_length, ensuring we don't cut off in the middle of a character
            sanitized = sanitized[:max_length].rsplit('-', 1)[0]

        return sanitized

    def embed_thumbnail_in_mp32(self, audio_file, thumbnail_file):
        try:
            audio = MP3(audio_file, ID3=ID3)
        except Exception as e:
            raise Exception(f"[downlord] Failed to load MP3 file: {e}")

        # Add ID3 tag if it does not exist
        try:
            audio.add_tags()
        except ID3NoHeaderError:  # Correct usage of ID3NoHeaderError
            print("[downlord] Adding ID3 header;")

        # Open the image file to embed
        try:
            with open(thumbnail_file, 'rb') as img:
                audio.tags.add(
                    APIC(
                        encoding=3,  # UTF-8
                        mime='image/webp',  # Adjust MIME-type if your image is not webp
                        type=3,  # Cover (front)
                        desc='Cover',
                        data=img.read()
                    )
                )
        except Exception as e:
            raise Exception(f"[downlord] Failed to embed thumbnail: {e}")

        # Save changes
        try:
            audio.save()
        except Exception as e:
            raise Exception(f"[downlord] Failed to save MP3 file: {e}")

class SelectAllLineEdit(QLineEdit):
    def __init__(self, parent=None):
        super().__init__(parent)

    def focusInEvent(self, event):
        super().focusInEvent(event)
        QTimer.singleShot(0, self.selectAll) ##needed this delay

class StreamRedirector:
    def __init__(self, player_instance):
        self.player_instance = player_instance
        self.original_stdout = sys.__stdout__  # Safe fallback
        self.lock = threading.Lock()
        self.buffer = ""

    def write(self, text):
        if not text:
            return

        with self.lock:
            self.buffer += text
            while "\n" in self.buffer:
                line, self.buffer = self.buffer.split("\n", 1)
                line += "\n"

                # Also write to real terminal if running with console (or debugging)
                try:
                    self.original_stdout.write(line)
                    self.original_stdout.flush()
                except Exception:
                    pass

                # Send to GUI
                if self.player_instance:
                    dltag = "[downlord]"
                    appenddltag = "[append]"
                    ignore = "[yt_dlp]"
                    try:
                        if dltag in line:
                            self.player_instance.add_dl_text_sig.emit(line)
                        elif appenddltag in line:
                            line = line.replace(appenddltag,"").strip('\n\r')
                            self.player_instance.append_dl_text_sig.emit(line)
                        elif not ignore in line: # don't send yt_dlp msgs to decurse
                            self.player_instance.add_decurse_text_sig.emit(line)
                    except Exception:
                        pass

    def flush(self):
        with self.lock:
            try:
                self.original_stdout.flush()
            except Exception:
                pass

def main() -> int:
    app = QApplication(sys.argv)

    window = MP3Player()
    window.show()
    return app.exec()

if __name__ == "__main__":
    raise SystemExit(main())


#### Features & Issues ####
# make duel coverart label transparent
# save last showed tab
# systray icon
# prevent the user from adding trashed items to playlists
# delete unused code and cleanup in general
# Folder Reorder and preserving needs testing
# change download to .download maybe... ???
# visualization look wonky in windows, maybe needs a new mp3 audio stream method
# soundbard
# duel play