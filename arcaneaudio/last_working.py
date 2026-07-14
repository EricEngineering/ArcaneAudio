# Test Commit
# Test Commit from laptop
# --- Standard Library ---
import os
import sys
import json
import shutil
import struct
import threading
import time
import re
from io import BytesIO
from pathlib import Path
import platform

# --- Third-Party Libraries ---
import numpy as np
from PIL import Image, ImageOps
from PIL.ImageQt import ImageQt
import yt_dlp
import pyaudio
import pyqtgraph as pg
from mutagen.mp3 import MP3
from mutagen.id3 import (
    ID3, TIT2, TALB, TPE1, TRCK, TCON, TDRC, TSSE, APIC,
    error, ID3NoHeaderError
)

# --- PySide6 ---
from PySide6.QtCore import (
    Qt, QTimer, QUrl, QPoint, QMimeData, QEvent, QSize, QMetaObject,
    Q_ARG, QObject, QThread, Signal, QRect, QRunnable, Slot, QCoreApplication
)
from PySide6.QtGui import (
    QImage, QPixmap, QIcon, QDrag, QPalette, QColor, QFontMetrics,
    QStandardItem, QTextCursor, QTextDocument, QPainter, QPen, QCursor,
    QBrush
)
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QFileDialog,
    QLabel, QListWidget, QListWidgetItem, QSlider, QTreeWidget, QTreeWidgetItem,
    QSplitter, QMenu, QStyle, QToolButton, QSizePolicy, QMessageBox, QSpacerItem,
    QAbstractItemView, QInputDialog, QTextBrowser, QProgressBar, QLineEdit,
    QGraphicsView, QGraphicsScene, QMainWindow
)
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput

# --- Project-Specific ---
from arcaneaudio.ui_mainwindow import Ui_MainWindow

SETTINGS_FILE = "mp3_player_settings.json"


class MP3Player(QWidget):
    # Define a signal that carries a string
    add_decurse_text_sig = Signal(str)
    add_dl_text_sig = Signal(str)

    def __init__(self):
        super().__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        # Initialize other components...
        self.currentDownloadThread = None

        # Connect the signal to the slot
        self.add_decurse_text_sig.connect(self.append_debug_text)
        self.add_dl_text_sig.connect(self.append_download_text)

        # Redirect stdout to the text browser and keep output in the console
        sys.stdout = StreamRedirector(self)

        # maintain a variable with the current path opened in mp3 list
        self.current_mp3list_path = ""

        # Test the output
        print("This message will appear in both the console and the QTextBrowser.")

        self.setWindowTitle("Arcane Audio - Cast Your Playlist")
        self.setWindowIcon(QIcon("art/icon.png"))

        # Set the default cover art to the app icon at start
        pixmap = QPixmap("art/icon.png")
        pixmap = pixmap.scaled(self.ui.cover_art_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.ui.cover_art_label.setPixmap(pixmap)

        # Store the default os system's palette at startup 
        self.original_palette = QApplication.palette()

        # Create gear settings button
        self.ui.settingsButton.setPopupMode(QToolButton.InstantPopup)
        # it seems because of the icon size I need to programmatically match
        # the settings button height to the select folder
        height = self.ui.btn_open.sizeHint().height()
        self.ui.settingsButton.setFixedHeight(height)
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
        self.splitter.setSizes([400, 400])  # Optional: adjust initial split

        # Replace the original layout
        layout = self.ui.horizontalLayout_2 #this is the layout holding the 2 widgets I want a splitter for
        for i in reversed(range(layout.count())):
            widget_item = layout.itemAt(i)
            widget = widget_item.widget()
            if widget:
                widget.setParent(None)

        # Create vertical splitter between folder/mp3 lists and tabbed outputs
        ##
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


        # Example initial sizes, adjust these numbers based on your UI needs
        self.mainSplitter.setSizes([100, 200])  # More space for the upper widget initially

        self.ui.btn_open.clicked.connect(self.open_folder)

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

        self.ui.btn_play.clicked.connect(self.play)
        self.ui.btn_pause.clicked.connect(self.pause)
        self.ui.btn_stop.clicked.connect(self.stop)

        layout_progress_slider = self.ui.progress_slider.parent().layout()
        old_progress_slider = self.ui.progress_slider
        old_style = old_progress_slider.styleSheet()
        self.ui.progress_slider = ClickSliderWidget(self)
        self.ui.progress_slider.setStyleSheet(old_style)
        self.ui.progress_slider.setOrientation(Qt.Horizontal)
        layout_progress_slider.replaceWidget(old_progress_slider, self.ui.progress_slider)
        old_progress_slider.deleteLater()

        self.ui.progress_slider.setRange(0, 100)
        self.ui.progress_slider.sliderReleased.connect(self.seek)
        self.ui.progress_slider.sliderMoved.connect(self.seek)
        self.slider_being_moved = False
        self.ui.progress_slider.sliderPressed.connect(self.slider_pressed)
        self.ui.progress_slider.sliderReleased.connect(self.slider_released)

        layout_volume_slider = self.ui.volume_slider.parent().layout()
        old_volume_slider = self.ui.volume_slider
        old_style = old_volume_slider.styleSheet()
        self.ui.volume_slider = ClickSliderWidget(self)
        self.ui.volume_slider.setStyleSheet(old_style)
        self.ui.volume_slider.setOrientation(Qt.Horizontal)
        self.ui.volume_slider.setMinimumWidth(185)
        self.ui.volume_slider.setMaximumWidth(185)
        layout_volume_slider.replaceWidget(old_volume_slider, self.ui.volume_slider)
        old_volume_slider.deleteLater()

        self.ui.visualizationWidget.setBackground(None)
        self.ui.visualizationWidget.enableAutoRange(axis='y')
        self.ui.visualizationWidget.getPlotItem().hideAxis('left')
        self.num_bars = 16
        x = np.linspace(0, np.pi * 2, self.num_bars)
        self.previous_bar_heights = (np.sin(x * 2) + 1.2) * 4  # Nice default curve

        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)
        self.audio_output.setVolume(1.0)

        self.ui.volume_slider.setRange(0, 100)
        self.ui.volume_slider.setValue(100)
        self.ui.volume_slider.sliderReleased.connect(self.set_volume)
        self.ui.volume_slider.sliderMoved.connect(self.set_volume)

        self.player.positionChanged.connect(self.update_progress)
        self.player.durationChanged.connect(self.set_progress_range)
        self.player.playbackStateChanged.connect(self.handle_playback_state)
        self.player.mediaStatusChanged.connect(self.handle_media_status)

        old_lineEdit = self.ui.youtubeURL_lineEdit
        self.ui.youtubeURL_lineEdit = SelectAllLineEdit(self)
        self.ui.youtubeURL_lineEdit.setText("Enter Youtube URL Here")
        self.ui.horizontalLayout_10.replaceWidget(old_lineEdit, self.ui.youtubeURL_lineEdit)
        layout.replaceWidget(old_lineEdit, self.ui.youtubeURL_lineEdit)
        old_lineEdit.deleteLater()

        self.playlist_paths = []

        self.working_dir = ""
        self.current_mp3_folder = ""

        self.timer = QTimer()
        self.folder_settings_path = None
        self.timer.timeout.connect(self.update_spectrograph)        
        
        self.ui.soundbard_label.setScaledContents(False)
        self.og_soundbard_pixmap = QPixmap("art/soundbard.png")
        ogWidth = self.og_soundbard_pixmap.width()
        ogHeight = self.og_soundbard_pixmap.height()
        newheight = 100#self.ui.soundbard_label.height()
        newWidth = (ogWidth * newheight) / ogHeight
        resizedPixmap = QPixmap()
        resizedPixmap = self.og_soundbard_pixmap.scaled(newWidth, newheight, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.ui.soundbard_label.setPixmap(resizedPixmap)

        self.duel_pixmap = QPixmap("art/duel.png")
        self.duel_pixmap = self.duel_pixmap.scaled(100, 100, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.ui.duel_label.setPixmap(self.duel_pixmap)

        self.init_audio_stream()
        self.init_visualization()
        self.load_settings()

    def append_debug_text(self, text):
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

    def append_download_text(self, text):
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
        QMessageBox.information(self, "About", "Your MP3 player v1.0")

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

    # only triggered on clicking on tree item
    # sets a global var to the path and calls load_mp3list_from_path
    def selected_tree_item(self):
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

    def seek(self):
        if self.player.duration() > 0:
            self.player.setPosition(self.ui.progress_slider.value())

    def handle_media_status(self, status):
        if status == QMediaPlayer.EndOfMedia:
            if self.ui.repeat_checkBox.isChecked():
                # Repeat current song
                current_item = self.ui.mp3_list.currentItem()
                if current_item:
                    self.play_selected_mp3(current_item)
            else:
                current_row = self.ui.mp3_list.currentRow()
                next_row = current_row + 1
                if next_row < self.ui.mp3_list.count():
                    next_item = self.ui.mp3_list.item(next_row)
                    self.ui.mp3_list.setCurrentItem(next_item)
                    self.play_selected_mp3(next_item)
                elif self.ui.mp3_list.count() > 0:
                    # Loop back to the first item
                    first_item = self.ui.mp3_list.item(0)
                    self.ui.mp3_list.setCurrentItem(first_item)
                    self.play_selected_mp3(first_item)

    def set_volume(self):
        volume = self.ui.volume_slider.value() / 100.0
        self.audio_output.setVolume(volume)
        self.ui.label_volumetext.setText(f"Volume: {int(volume * 100)}%")

    def handle_playback_state(self, state):
        if state == QMediaPlayer.PlayingState:
            if not self.timer.isActive():
                self.timer.start(100)
        else:
            self.timer.stop()

    def open_folder(self, from_load_last_directory=False):
        self.folder_settings_path = None
        folder_path = self.working_dir if from_load_last_directory else QFileDialog.getExistingDirectory(self, "Open Folder", self.working_dir or "")
        if folder_path and os.path.isdir(folder_path):
            self.working_dir = folder_path
            self.folder_text_label.setText(f"Opened: {folder_path}")

            self.ui.folder_view.populate_from_path(folder_path)
            self.save_last_directory()

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
            self.update_now_playing(item.text(), selected_file)

            # Extract and display metadata
            metadata = self.get_mp3_metadata(selected_file)
            meta_info = (
                f"Title: {metadata['title']}, "
                f"Artist: {metadata['artist']}\n"
                f"Album: {metadata['album']}, "
                f"Track: {metadata['track']}\n"
                f"Date: {metadata['date']}\n"
                f"Encoder: {metadata['encoder']}\n"
                f"Duration: {metadata['duration']}\n"
                f"Bitrate: {metadata['bitrate']}"
            )
            self.ui.fileMeta_textBrowser.setText(meta_info)

            self.player.setSource(QUrl.fromLocalFile(selected_file))
            self.play()

            # hack, this forces the mp3 to play and give the message:
            # Media status changed: MediaStatus.LoadedMedia. I need it to force the playing
            # of media with embedded images... really? I must be doing something wrong
            QTimer.singleShot(100, lambda: self.player.setPosition(0))  
            # print(f"Media state after attempting to play: {self.player.mediaStatus()}") #this always prints before the player signals, why?
    
    def update_now_playing(self, title, path):
        self.playing_text_label.setText(f"Playing: {title}")
        self.ui.cover_art_label.clear()
        self.ui.cover_art_label.setStyleSheet("background: transparent;")

        try:
            tags = ID3(path)
            for tag in tags.values():
                if tag.FrameID == "APIC":
                    image_data = tag.data
                    image = Image.open(BytesIO(image_data)).convert("RGBA")
                    self.process_display_coverart(image)
                    print("displaying an image")
                    return  # Stop after displaying the first APIC image
            # No APIC image was found, now try to display the icon
            icon_path = "art/icon.png"
            if os.path.exists(icon_path):
                image = Image.open(icon_path)
                self.process_display_coverart(image)
            else:
                # Display Text as a last resort
                self.ui.cover_art_label.setStyleSheet("background-color: transparent; color: white; text-align: center;")
                self.ui.cover_art_label.setText("No Artwork")
        except Exception as e:
            print(f"Error Displaying Cover Art: {e}")
                        
    def process_display_coverart(self, image):
        """Process an Image object and display it in the QLabel."""
        target_width = self.ui.cover_art_label.width()
        target_height = self.ui.cover_art_label.height()

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
        pixmap = pixmap.scaled(self.ui.cover_art_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.ui.cover_art_label.setPixmap(pixmap)
        self.ui.cover_art_label.setAlignment(Qt.AlignCenter)

    def get_mp3_metadata(self, file_path):
        try:
            audio = MP3(file_path, ID3=ID3)
            metadata = {
                'title': audio.tags.get('TIT2').text[0] if audio.tags.get('TIT2') else 'Unknown Title',
                'artist': audio.tags.get('TPE1').text[0] if audio.tags.get('TPE1') else 'Unknown Artist',
                'album': audio.tags.get('TALB').text[0] if audio.tags.get('TALB') else 'Unknown Album',
                'track': audio.tags.get('TRCK').text[0] if audio.tags.get('TRCK') else 'Unknown Track Number',
                'genre': audio.tags.get('TCON').text[0] if audio.tags.get('TCON') else 'Unknown Genre',
                'date': audio.tags.get('TDRC').text[0] if audio.tags.get('TDRC') else 'Unknown Date',
                'encoder': audio.tags.get('TSSE').text[0] if audio.tags.get('TSSE') else 'Unknown Encoder',
                'duration': str(int(audio.info.length)) + " seconds",
                'bitrate': str(int(audio.info.bitrate / 1000)) + " kbps"
            }
            return metadata
        except Exception as e:
            print(f"Failed to read metadata from {file_path}: {e}")
            return {}

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

    def init_audio_stream(self):
        self.chunk = 1024
        self.audio = pyaudio.PyAudio()
        self.stream = None
        self.player.mediaStatusChanged.connect(lambda status: print(f"Media status changed: {status}"))
        self.player.errorOccurred.connect(lambda error, errorString: print(f"Error occurred: {errorString}"))

        input_device_index = None
        for i in range(self.audio.get_device_count()):
            dev_info = self.audio.get_device_info_by_index(i)
            if dev_info.get("maxInputChannels", 0) > 0:
                input_device_index = i
                break


        if input_device_index is None:
            print("No valid input device found. Spectrogram will not work.")
            return

        # Try safe sample rates
        for rate in [44100, 48000, 22050, 16000, 11025]:
            try:
                self.stream = self.audio.open(
                    format=pyaudio.paInt16,
                    channels=1,
                    rate=rate,
                    input=True,
                    input_device_index=input_device_index,
                    frames_per_buffer=self.chunk
                )
                self.sample_rate = rate
                print(f"Audio stream opened at {rate} Hz")
                dev_info = self.audio.get_device_info_by_index(input_device_index)
                print(f"Using input device: {dev_info.get('name')}")
                return
            except Exception as e:
                print(f"Rate {rate} Hz not supported: {e}")

        print("Failed to initialize audio stream with any sample rate.")

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
        if not hasattr(self, 'stream'):
            return

        data = self.stream.read(self.chunk, exception_on_overflow=False)
        data_int = struct.unpack('<' + 'h' * self.chunk, data)
        waveform = np.array(data_int, dtype=np.float32) / 32768.0
        
        waveform -= np.mean(waveform)  # Remove DC bias #added to try and make windows look right
        waveform /= np.max(np.abs(waveform)) + 1e-8  # Normalize safely #added to try and make windows look right

        spectrum = np.abs(np.fft.rfft(waveform))
        freqs = np.fft.rfftfreq(len(waveform), 1 / self.sample_rate)

        num_bars = self.num_bars
        log_freqs = np.logspace(np.log10(20), np.log10(20000), num=num_bars + 1)[:num_bars]
        bar_heights = np.interp(log_freqs, freqs, spectrum)

        alpha = 0.5
        #alpha = 0.3
        self.previous_bar_heights = (1 - alpha) * self.previous_bar_heights + alpha * bar_heights

        ##brushes = [pg.mkBrush((128 + int(h * 500), 0, 128 + int(h * 1000), int(100 + h * 155))) for h in self.previous_bar_heights]
        brushes = []
        for i in range(self.num_bars):
            # Create a gradient from darker to lighter purple
            base = 100 + int((i / self.num_bars) * 100)   # 100–200
            alpha = 150 + int((i / self.num_bars) * 105)  # 150–255
            brushes.append(pg.mkBrush(base, 0, base + 55, alpha))

        self.ui.visualizationWidget.clear()
        x = np.arange(num_bars)
        for i in range(num_bars):
            bar = pg.BarGraphItem(x=[x[i]], height=[self.previous_bar_heights[i]], width=0.8, brush=brushes[i])
            self.ui.visualizationWidget.addItem(bar)

    def download_from_youtube(self):
        if self.currentDownloadThread and self.currentDownloadThread.isRunning():
            print("[yt_dlp] Download in Progress... Please wait for the current download to finish.")
            return

        url = self.ui.youtubeURL_lineEdit.text().strip()
        pattern = re.compile(r"^(https?:\/\/)?([\w\.-]+)\.([a-z\.]{2,20})([\/\w \.-]*)(\?[\w=&\.;%-]*)?$")
        if not pattern.match(url):
            print("[yt_dlp] Error... Please enter a valid URL.")
            return

        download_path = os.path.join(self.working_dir, 'downloads')
        #os.makedirs(download_path, exist_ok=True)
        # Check if the directory already exists
        if not os.path.exists(download_path):
            print("Directory: download does not exist, creating now...")
            os.makedirs(download_path, exist_ok=True)
            # if the directory didn't exist then it is not in the tree
            self.ui.folder_view.populate_from_path(self.working_dir)
        else:
            print("Directory already exists.")

        self.currentDownloadThread = DownloadThread(url, download_path)
        #self.currentDownloadThread.progress.connect(self.update_progress) #update_progress is used by progress slider
        self.currentDownloadThread.finished.connect(self.download_finished)
        self.currentDownloadThread.error.connect(self.download_error)
        self.currentDownloadThread.start()

    def download_finished(self, message):
        self.ui.youtubeURL_lineEdit.setText("Enter Youtube URL Here")
        print("[yt_dlp] Download Finished")
        #refresh the mp3list after a download incase we are viewing
        self.load_mp3list_from_path()

    def download_error(self, message):
        print("[yt_dlp] Download Error")

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
                    ####shutil.move(full_path, trash_path)
                    ##testing new logic that should work on windows and linux to stop the file if playing for a move
                    self.move_file_or_folder(full_path, trash_path)
                    ####End New Logic

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
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QTextEdit, QHBoxLayout, QPushButton

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
            new_item.setIcon(0, QIcon("art/playlist.png"))
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
            new_item.setIcon(0, QIcon("art/folder.png"))
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
        try:
            with open(SETTINGS_FILE, 'r') as f:
                settings = json.load(f)

                # Restore window size
                window_size = settings.get("window_size", [800, 600])
                self.resize(window_size[0], window_size[1])

                #Load Last Used Directory as the Working Directory
                last_dir = settings.get("last_directory", "")
                if os.path.isdir(last_dir):
                    self.working_dir = last_dir
                    self.open_folder(from_load_last_directory=True)

                splitter_sizes = settings.get("h_splitter_sizes")
                if splitter_sizes:
                    self.splitter.setSizes(splitter_sizes)

                # Restore splitter sizes
                splitter_sizes = settings.get("v_splitter_sizes")
                if splitter_sizes:
                    self.mainSplitter.setSizes(splitter_sizes)

                theme = settings.get("theme")
                if theme is None:
                    theme = "arcana"
                self.set_theme(theme)
        except FileNotFoundError:
            print("No Settings Found, Default Settings")
            self.set_theme("arcana")
        except Exception as e:
            print("Error Loading Settings File:", e)
            self.set_theme(theme)

    ## CloseEvent is doing similar things as save_last_directory,
    ##   find a better to merge this functionality while preserving
    ##   settings as they change instead of losing those settings
    ##   if the program crashes

    def save_last_directory(self):
        try:
            settings = {}
            if os.path.exists(SETTINGS_FILE):
                with open(SETTINGS_FILE, 'r') as f:
                    settings = json.load(f)

            settings["last_directory"] = self.working_dir

            with open(SETTINGS_FILE, 'w') as f:
                json.dump(settings, f, indent=4)

            print("Saved last directory:", self.working_dir)
        except Exception as e:
            print("Failed to save last directory:", e)

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

            settings["last_directory"] = self.working_dir
            settings["h_splitter_sizes"] = self.splitter.sizes()
            settings["window_size"] = [self.width(), self.height()]
            settings["v_splitter_sizes"] = self.mainSplitter.sizes()

            with open(SETTINGS_FILE, 'w') as f:
                json.dump(settings, f)
            print("Settings saved.")
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

class MP3ListWidget(QListWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        print("MP3ListWidget Constructor")
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

        menu.exec(self.mapToGlobal(position))

    def remove_from_playlist(self):
        item = self.currentItem()
        if item:
            playlist_path = self.window().get_current_mp3list_path()
            # Remove the item from the .m3u file
            self.window().remove_mp3_from_playlist(playlist_path, item.text())
            # Refresh the mp3 list
            self.window().load_mp3list_from_path()
            

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
                        icon = QIcon("art/playlist.png") if item.endswith(".m3u") else QIcon("art/folder.png")
                        tree_item.setIcon(0, icon)
                        parent_item.addChild(tree_item)
                        if os.path.isdir(full_path):
                            add_items(tree_item, full_path)
            except Exception as e:
                print("Error reading folder:", path, e)

        root = QTreeWidgetItem()
        root.setText(0, os.path.basename(base_path))
        root.setData(0, Qt.UserRole, base_path)
        root.setIcon(0, QIcon("art/folder.png"))
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
            original_icon = QIcon("art/playlist.png") if original_path.endswith(".m3u") else QIcon("art/folder.png")
            self._hovered_item.setBackground(0, Qt.transparent)
            self._hovered_item.setIcon(0, original_icon)
            self._hovered_item = None

        # Prevent a Playlist/Folder from the Tree from getting dropped on a Playlist in the Tree
        pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
        target_item = self.itemAt(pos)
        target_path = target_item.data(0, Qt.UserRole) if target_item else None
        source_widget = event.source()
        # ❌ Reject folder/playlist drops onto playlists
        if source_widget == self and (target_path.endswith(".m3u") and self.dropIndicatorPosition() == QAbstractItemView.OnItem) : #isinstance(target_path, str) and 
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

                #elif os.path.isdir(target_path):
                #    # Physically moving the MP3 to another folder
                #    new_song_path = os.path.join(target_path, os.path.basename(song_path))
                #    ####shutil.move(song_path, new_song_path)
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
        #print("dragMoveEvent i.e. hovering over items")
        source_widget = event.source()
        pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
        target_item = self.itemAt(pos)
        target_path = target_item.data(0, Qt.UserRole) if target_item else None

        # This would be nice to not draw the rectangle around a playlist when the drag was a playlist but...
        #  it's causing too much bugginess sometimes drawing the rectangle anyways, qt still draws it and it would
        #  require overriding the drawdropindicator. and also the line above and below still doesn't always draw
        #  not only this but i ended up using the presence of the rectangle box to help with not allowing items to
        #  be dropped onto playlist
        """
        # Prevent a Playlist/Folder from the Tree from highlighting on a Playlist in the Tree
        if (source_widget == self and isinstance(target_path, str) and target_path.endswith(".m3u") and self.dropIndicatorPosition() == QAbstractItemView.OnItem):
            print("Invalid Hover: Don't show Highlighting Box")
            event.ignore()
            return
        """
        
        # Drag came from MP3List
        if event.mimeData().hasFormat("application/x-mp3-song"):
            #print("hover event: has format application/x-mp3-song")
            event.acceptProposedAction()
            if target_item != self._hovered_item:
                # Reset previous hover item
                if self._hovered_item:
                    prev_path = self._hovered_item.data(0, Qt.UserRole)
                    if isinstance(prev_path, str):
                        prev_icon = QIcon("art/playlist.png") if prev_path.endswith(".m3u") else QIcon("art/folder.png")
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
                            icon = QIcon("art/playlist-no.png")
                        else:
                            icon = QIcon("art/folder-no.png")
                    else:
                        # MP3 list is showing a folder
                        if full_path.endswith(".m3u"):
                            icon = QIcon("art/playlist-yes.png")
                        else:
                            icon = QIcon("art/folder-yes.png")
                    self._hovered_item.setIcon(0, icon)
        # Drag came from Tree
        elif source_widget == self:
            event.acceptProposedAction()
            # Lets not do Icons or Hover Shading with Tree Moves because it doesn't Line Up or match with
            #  the default super().dragMoveEvent(event) behavior we are relying on
            # Perform the default handler for Tree events
            super().dragMoveEvent(event)
        # I don't think an else default handler is necessary here
        #else:
            # fallback to default handler
            #super().dragMoveEvent(event)


    def dragLeaveEvent(self, event):

        QTimer.singleShot(0, lambda: self.itemChanged.connect(self.player.rename_folder_or_playlist))

        if self._hovered_item:
            original_path = self._hovered_item.data(0, Qt.UserRole)
            original_icon = QIcon("art/playlist.png") if original_path.endswith(".m3u") else QIcon("art/folder.png")
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

class DownloadThread(QThread):
    progress = Signal(int)
    finished = Signal(str)
    error = Signal(str)

    def __init__(self, url, download_path, parent=None):
        super().__init__(parent)
        self.url = url
        self.download_path = download_path

    def run(self):


        print("[yt_dlp] Download Task started")
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
                #'outtmpl': os.path.join(self.download_path, '%(title)s.%(ext)s'),
                'outtmpl': os.path.join(self.download_path, 'download.%(ext)s'),
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
                'writethumbnail': True,  # Download thumbnail
                'noplaylist': True,
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
                    print("[yt_dlp] ❌ No thumbnail found.")
                    self.error.emit("No thumbnail was found after download.")
                    return

            # Embed the thumbnail into the MP3 file
            ##mp3path = os.path.join(self.download_path, audio_file)
            ##imagepath = os.path.join(self.download_path, thumbnail_file)
            mp3path = Path(self.download_path) / audio_file
            imagepath = Path(self.download_path) / thumbnail_file

            print(f"[yt_dlp] MP3 File:{mp3path}")
            print(f"[yt_dlp] Thumbnail:{imagepath}")

            time.sleep(2) #wait 2sec
            #self.embed_thumbnail_in_mp3(mp3path, imagepath)
            self.embed_thumbnail_in_mp3(str(mp3path), str(imagepath))
            #QTimer.singleShot(1000, lambda: self.embed_thumbnail_in_mp3(mp3path, imagepath)) ##needed this delay

            #sanitize the filename
            filename = f"{self.sanitize_filename(video_title)}.mp3"
            #filename = f"{video_title}.mp3"

            #rename the file
            #os.rename(mp3path, os.path.join(self.download_path, filename))
            mp3path.rename(Path(self.download_path) / filename)

            # remove the image file when done
            if imagepath.exists():
                try:
                    imagepath.unlink()
                    print(f"[yt_dlp] Deleted thumbnail: {imagepath}")
                except Exception as e:
                    print(f"[yt_dlp] Failed to delete thumbnail: {e}")

        except Exception as e:
            print(f"[yt_dlp] Exception in Download Task: {e}")
            self.error.emit(str(e))

        print("[yt_dlp] Download Task completed")
        self.finished.emit("NA")

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
        #mime_type = 'image/jpeg' if thumbnail_file.endswith('.jpg') else 'image/png'
        #mime_type = 'image/jpeg'
        # Determine MIME type based on file extension
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
            raise Exception(f"Failed to load MP3 file: {e}")

        # Add ID3 tag if it does not exist
        try:
            audio.add_tags()
        except ID3NoHeaderError:  # Correct usage of ID3NoHeaderError
            print("Adding ID3 header;")

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
            raise Exception(f"Failed to embed thumbnail: {e}")

        # Save changes
        try:
            audio.save()
        except Exception as e:
            raise Exception(f"Failed to save MP3 file: {e}")


#redirect the standard print outputs to my debugTextBrowser
class StreamRedirector:
    def __init__(self, player_instance):
        self.player_instance = player_instance
        self.original_stdout = sys.stdout  # Save the original stdout here
        self.lock = threading.Lock()  # Create a lock for thread-safe stdout access

    def write(self, text):
        with self.lock:
            # use these keywords to differentiate youtube downloader specific text from the stdout
            # I tried tracebacks but that didn't work too well
            yt_dlp_strings = ["[yt_dlp]", "[youtube","[download", "[ExtractAudio]", "[info]", "Deleting original"]

            # Write to the original stdout
            self.original_stdout.write(text)

            # check if message is likely from yt_dlp
            if any(yt_dlp_string in text for yt_dlp_string in yt_dlp_strings):
                self.player_instance.add_dl_text_sig.emit(text)
            else:
                self.player_instance.add_decurse_text_sigsig.emit(text)
                
            self.original_stdout.flush()

    def flush(self):
        with self.lock:
            # Flush the original stdout
            self.original_stdout.flush()

class SelectAllLineEdit(QLineEdit):
    def __init__(self, parent=None):
        super().__init__(parent)

    def focusInEvent(self, event):
        super().focusInEvent(event)
        QTimer.singleShot(0, self.selectAll) ##needed this delay

if __name__ == "__main__":
    app = QApplication(sys.argv)
    print("Creating Player")
    player = MP3Player()

    player.show()
    sys.exit(app.exec())


#### Features & Issues ####
# systray icon
# prevent the user from adding trashed items to playlists
# delete unused code and cleanup in general
# Folder Reorder and preserving needs testing
# change download to .download maybe... ???
# visualization look wonky in windows, maybe needs a new mp3 audio stream method
# soundbard
# duel play


