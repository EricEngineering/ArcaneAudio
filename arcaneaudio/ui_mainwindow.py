# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'mainwindow.ui'
##
## Created by: Qt User Interface Compiler version 6.10.2
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import (QCoreApplication, QDate, QDateTime, QLocale,
    QMetaObject, QObject, QPoint, QRect,
    QSize, QTime, QUrl, Qt)
from PySide6.QtGui import (QBrush, QColor, QConicalGradient, QCursor,
    QFont, QFontDatabase, QGradient, QIcon,
    QImage, QKeySequence, QLinearGradient, QPainter,
    QPalette, QPixmap, QRadialGradient, QTransform)
from PySide6.QtWidgets import (QApplication, QCheckBox, QHBoxLayout, QLabel,
    QLineEdit, QListWidget, QListWidgetItem, QPushButton,
    QSizePolicy, QSlider, QSpacerItem, QTabWidget,
    QTextBrowser, QToolButton, QVBoxLayout, QWidget)

from pyqtgraph import PlotWidget

class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        if not MainWindow.objectName():
            MainWindow.setObjectName(u"MainWindow")
        MainWindow.resize(675, 688)
        sizePolicy = QSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.MinimumExpanding)
        sizePolicy.setHorizontalStretch(1)
        sizePolicy.setVerticalStretch(1)
        sizePolicy.setHeightForWidth(MainWindow.sizePolicy().hasHeightForWidth())
        MainWindow.setSizePolicy(sizePolicy)
        self.verticalLayout_3 = QVBoxLayout(MainWindow)
        self.verticalLayout_3.setObjectName(u"verticalLayout_3")
        self.verticalLayout = QVBoxLayout()
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.horizontalLayout_4 = QHBoxLayout()
        self.horizontalLayout_4.setObjectName(u"horizontalLayout_4")
        self.horizontalLayout_4.setContentsMargins(-1, 0, -1, 0)
        self.verticalLayout_2 = QVBoxLayout()
        self.verticalLayout_2.setSpacing(4)
        self.verticalLayout_2.setObjectName(u"verticalLayout_2")
        self.horizontalLayout_8 = QHBoxLayout()
        self.horizontalLayout_8.setObjectName(u"horizontalLayout_8")
        self.horizontalLayout_8.setContentsMargins(-1, 0, -1, -1)
        self.settingsButton = QToolButton(MainWindow)
        self.settingsButton.setObjectName(u"settingsButton")
        self.settingsButton.setMaximumSize(QSize(16777215, 16777215))
        self.settingsButton.setIconSize(QSize(20, 20))
        self.settingsButton.setAutoRaise(True)

        self.horizontalLayout_8.addWidget(self.settingsButton)

        self.horizontalSpacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout_8.addItem(self.horizontalSpacer)


        self.verticalLayout_2.addLayout(self.horizontalLayout_8)

        self.horizontalLayout_9 = QHBoxLayout()
        self.horizontalLayout_9.setObjectName(u"horizontalLayout_9")
        self.horizontalLayout_9.setContentsMargins(-1, 0, -1, -1)
        self.label_volumetext = QLabel(MainWindow)
        self.label_volumetext.setObjectName(u"label_volumetext")

        self.horizontalLayout_9.addWidget(self.label_volumetext)

        self.volume_slider = QSlider(MainWindow)
        self.volume_slider.setObjectName(u"volume_slider")
        self.volume_slider.setMinimumSize(QSize(185, 0))
        self.volume_slider.setMaximumSize(QSize(185, 16777215))
        self.volume_slider.setOrientation(Qt.Orientation.Horizontal)

        self.horizontalLayout_9.addWidget(self.volume_slider)

        self.horizontalSpacer_4 = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout_9.addItem(self.horizontalSpacer_4)


        self.verticalLayout_2.addLayout(self.horizontalLayout_9)

        self.horizontalLayout_6 = QHBoxLayout()
        self.horizontalLayout_6.setObjectName(u"horizontalLayout_6")

        self.verticalLayout_2.addLayout(self.horizontalLayout_6)

        self.horizontalLayout = QHBoxLayout()
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.horizontalLayout.setContentsMargins(-1, 0, -1, -1)
        self.btn_play = QPushButton(MainWindow)
        self.btn_play.setObjectName(u"btn_play")
        self.btn_play.setMaximumSize(QSize(55, 16777215))

        self.horizontalLayout.addWidget(self.btn_play)

        self.btn_pause = QPushButton(MainWindow)
        self.btn_pause.setObjectName(u"btn_pause")
        self.btn_pause.setMaximumSize(QSize(55, 16777215))

        self.horizontalLayout.addWidget(self.btn_pause)

        self.btn_stop = QPushButton(MainWindow)
        self.btn_stop.setObjectName(u"btn_stop")
        self.btn_stop.setMaximumSize(QSize(55, 16777215))

        self.horizontalLayout.addWidget(self.btn_stop)

        self.verticalLayout_14 = QVBoxLayout()
        self.verticalLayout_14.setSpacing(0)
        self.verticalLayout_14.setObjectName(u"verticalLayout_14")
        self.verticalLayout_14.setContentsMargins(3, -1, -1, -1)
        self.repeat_checkBox = QCheckBox(MainWindow)
        self.repeat_checkBox.setObjectName(u"repeat_checkBox")

        self.verticalLayout_14.addWidget(self.repeat_checkBox)

        self.random_checkBox = QCheckBox(MainWindow)
        self.random_checkBox.setObjectName(u"random_checkBox")

        self.verticalLayout_14.addWidget(self.random_checkBox)


        self.horizontalLayout.addLayout(self.verticalLayout_14)

        self.horizontalSpacer_2 = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout.addItem(self.horizontalSpacer_2)


        self.verticalLayout_2.addLayout(self.horizontalLayout)


        self.horizontalLayout_4.addLayout(self.verticalLayout_2)

        self.horizontalLayout_7 = QHBoxLayout()
        self.horizontalLayout_7.setObjectName(u"horizontalLayout_7")
        self.cover_art_label = QLabel(MainWindow)
        self.cover_art_label.setObjectName(u"cover_art_label")
        sizePolicy1 = QSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        sizePolicy1.setHorizontalStretch(0)
        sizePolicy1.setVerticalStretch(0)
        sizePolicy1.setHeightForWidth(self.cover_art_label.sizePolicy().hasHeightForWidth())
        self.cover_art_label.setSizePolicy(sizePolicy1)
        self.cover_art_label.setMinimumSize(QSize(100, 100))
        self.cover_art_label.setAutoFillBackground(True)

        self.horizontalLayout_7.addWidget(self.cover_art_label)

        self.visualizationWidget = PlotWidget(MainWindow)
        self.visualizationWidget.setObjectName(u"visualizationWidget")
        sizePolicy2 = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        sizePolicy2.setHorizontalStretch(0)
        sizePolicy2.setVerticalStretch(0)
        sizePolicy2.setHeightForWidth(self.visualizationWidget.sizePolicy().hasHeightForWidth())
        self.visualizationWidget.setSizePolicy(sizePolicy2)
        self.visualizationWidget.setMinimumSize(QSize(200, 95))
        self.visualizationWidget.setMaximumSize(QSize(400, 95))
        self.visualizationWidget.setAutoFillBackground(True)

        self.horizontalLayout_7.addWidget(self.visualizationWidget)


        self.horizontalLayout_4.addLayout(self.horizontalLayout_7)

        self.horizontalLayout_4.setStretch(0, 1)
        self.horizontalLayout_4.setStretch(1, 1)

        self.verticalLayout.addLayout(self.horizontalLayout_4)

        self.horizontalLayout_3 = QHBoxLayout()
        self.horizontalLayout_3.setObjectName(u"horizontalLayout_3")
        self.horizontalLayout_3.setContentsMargins(-1, 0, -1, -1)
        self.label_seektimetext = QLabel(MainWindow)
        self.label_seektimetext.setObjectName(u"label_seektimetext")

        self.horizontalLayout_3.addWidget(self.label_seektimetext)

        self.label_remainingtimetext = QLabel(MainWindow)
        self.label_remainingtimetext.setObjectName(u"label_remainingtimetext")
        self.label_remainingtimetext.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.label_remainingtimetext.setAlignment(Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignTrailing|Qt.AlignmentFlag.AlignVCenter)

        self.horizontalLayout_3.addWidget(self.label_remainingtimetext)


        self.verticalLayout.addLayout(self.horizontalLayout_3)

        self.progress_slider = QSlider(MainWindow)
        self.progress_slider.setObjectName(u"progress_slider")
        self.progress_slider.setOrientation(Qt.Orientation.Horizontal)

        self.verticalLayout.addWidget(self.progress_slider)

        self.horizontalLayout_5 = QHBoxLayout()
        self.horizontalLayout_5.setObjectName(u"horizontalLayout_5")
        self.horizontalLayout_5.setContentsMargins(-1, 0, -1, -1)

        self.verticalLayout.addLayout(self.horizontalLayout_5)

        self.horizontalLayout_2 = QHBoxLayout()
        self.horizontalLayout_2.setObjectName(u"horizontalLayout_2")
        self.folder_view = QListWidget(MainWindow)
        self.folder_view.setObjectName(u"folder_view")

        self.horizontalLayout_2.addWidget(self.folder_view)

        self.mp3_list = QListWidget(MainWindow)
        self.mp3_list.setObjectName(u"mp3_list")

        self.horizontalLayout_2.addWidget(self.mp3_list)


        self.verticalLayout.addLayout(self.horizontalLayout_2)

        self.verticalLayout.setStretch(4, 1)

        self.verticalLayout_3.addLayout(self.verticalLayout)

        self.tabWidget = QTabWidget(MainWindow)
        self.tabWidget.setObjectName(u"tabWidget")
        self.tab = QWidget()
        self.tab.setObjectName(u"tab")
        self.verticalLayout_4 = QVBoxLayout(self.tab)
        self.verticalLayout_4.setObjectName(u"verticalLayout_4")
        self.verticalLayout_10 = QVBoxLayout()
        self.verticalLayout_10.setObjectName(u"verticalLayout_10")
        self.debugTextBrowser = QTextBrowser(self.tab)
        self.debugTextBrowser.setObjectName(u"debugTextBrowser")

        self.verticalLayout_10.addWidget(self.debugTextBrowser)


        self.verticalLayout_4.addLayout(self.verticalLayout_10)

        self.tabWidget.addTab(self.tab, "")
        self.tab_2 = QWidget()
        self.tab_2.setObjectName(u"tab_2")
        self.verticalLayout_5 = QVBoxLayout(self.tab_2)
        self.verticalLayout_5.setObjectName(u"verticalLayout_5")
        self.horizontalLayout_10 = QHBoxLayout()
        self.horizontalLayout_10.setObjectName(u"horizontalLayout_10")
        self.horizontalLayout_10.setContentsMargins(-1, 0, -1, -1)
        self.youtubeURL_lineEdit = QLineEdit(self.tab_2)
        self.youtubeURL_lineEdit.setObjectName(u"youtubeURL_lineEdit")

        self.horizontalLayout_10.addWidget(self.youtubeURL_lineEdit)

        self.download_pushButton = QPushButton(self.tab_2)
        self.download_pushButton.setObjectName(u"download_pushButton")

        self.horizontalLayout_10.addWidget(self.download_pushButton)


        self.verticalLayout_5.addLayout(self.horizontalLayout_10)

        self.horizontalLayout_11 = QHBoxLayout()
        self.horizontalLayout_11.setObjectName(u"horizontalLayout_11")
        self.horizontalLayout_11.setContentsMargins(-1, 0, -1, -1)
        self.downloadTextBrowser = QTextBrowser(self.tab_2)
        self.downloadTextBrowser.setObjectName(u"downloadTextBrowser")
        self.downloadTextBrowser.setStyleSheet(u"p {\n"
"    line-height: 1.0;\n"
"}")

        self.horizontalLayout_11.addWidget(self.downloadTextBrowser)

        self.horizontalLayout_11.setStretch(0, 1)

        self.verticalLayout_5.addLayout(self.horizontalLayout_11)

        self.tabWidget.addTab(self.tab_2, "")
        self.tab_3 = QWidget()
        self.tab_3.setObjectName(u"tab_3")
        self.verticalLayout_12 = QVBoxLayout(self.tab_3)
        self.verticalLayout_12.setObjectName(u"verticalLayout_12")
        self.verticalLayout_11 = QVBoxLayout()
        self.verticalLayout_11.setObjectName(u"verticalLayout_11")
        self.horizontalLayout_13 = QHBoxLayout()
        self.horizontalLayout_13.setObjectName(u"horizontalLayout_13")
        self.soundbard_label = QLabel(self.tab_3)
        self.soundbard_label.setObjectName(u"soundbard_label")
        sizePolicy3 = QSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        sizePolicy3.setHorizontalStretch(0)
        sizePolicy3.setVerticalStretch(0)
        sizePolicy3.setHeightForWidth(self.soundbard_label.sizePolicy().hasHeightForWidth())
        self.soundbard_label.setSizePolicy(sizePolicy3)
        self.soundbard_label.setScaledContents(False)
        self.soundbard_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.horizontalLayout_13.addWidget(self.soundbard_label)


        self.verticalLayout_11.addLayout(self.horizontalLayout_13)


        self.verticalLayout_12.addLayout(self.verticalLayout_11)

        self.tabWidget.addTab(self.tab_3, "")
        self.tab_4 = QWidget()
        self.tab_4.setObjectName(u"tab_4")
        self.verticalLayout_8 = QVBoxLayout(self.tab_4)
        self.verticalLayout_8.setObjectName(u"verticalLayout_8")
        self.verticalLayout_13 = QVBoxLayout()
        self.verticalLayout_13.setObjectName(u"verticalLayout_13")
        self.verticalLayout_13.setContentsMargins(-1, 0, -1, -1)
        self.horizontalLayout_12 = QHBoxLayout()
        self.horizontalLayout_12.setObjectName(u"horizontalLayout_12")
        self.horizontalLayout_12.setContentsMargins(-1, 0, -1, 0)
        self.duel_label = QLabel(self.tab_4)
        self.duel_label.setObjectName(u"duel_label")
        sizePolicy1.setHeightForWidth(self.duel_label.sizePolicy().hasHeightForWidth())
        self.duel_label.setSizePolicy(sizePolicy1)
        self.duel_label.setMinimumSize(QSize(100, 100))

        self.horizontalLayout_12.addWidget(self.duel_label)

        self.verticalLayout_7 = QVBoxLayout()
        self.verticalLayout_7.setSpacing(4)
        self.verticalLayout_7.setObjectName(u"verticalLayout_7")
        self.verticalLayout_7.setContentsMargins(-1, -1, -1, 0)
        self.duel_playing_text_label = QLabel(self.tab_4)
        self.duel_playing_text_label.setObjectName(u"duel_playing_text_label")

        self.verticalLayout_7.addWidget(self.duel_playing_text_label)

        self.horizontalLayout_14 = QHBoxLayout()
        self.horizontalLayout_14.setObjectName(u"horizontalLayout_14")
        self.horizontalLayout_14.setContentsMargins(-1, 0, -1, -1)
        self.label_duelvolumetext = QLabel(self.tab_4)
        self.label_duelvolumetext.setObjectName(u"label_duelvolumetext")

        self.horizontalLayout_14.addWidget(self.label_duelvolumetext)

        self.duel_volume_slider = QSlider(self.tab_4)
        self.duel_volume_slider.setObjectName(u"duel_volume_slider")
        self.duel_volume_slider.setMinimumSize(QSize(185, 0))
        self.duel_volume_slider.setMaximumSize(QSize(185, 16777215))
        self.duel_volume_slider.setOrientation(Qt.Orientation.Horizontal)

        self.horizontalLayout_14.addWidget(self.duel_volume_slider)

        self.horizontalSpacer_5 = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout_14.addItem(self.horizontalSpacer_5)


        self.verticalLayout_7.addLayout(self.horizontalLayout_14)

        self.horizontalLayout_16 = QHBoxLayout()
        self.horizontalLayout_16.setObjectName(u"horizontalLayout_16")
        self.horizontalLayout_16.setContentsMargins(-1, 0, -1, -1)
        self.btn_duel_play = QPushButton(self.tab_4)
        self.btn_duel_play.setObjectName(u"btn_duel_play")
        self.btn_duel_play.setMaximumSize(QSize(55, 16777215))

        self.horizontalLayout_16.addWidget(self.btn_duel_play)

        self.btn_duel_pause = QPushButton(self.tab_4)
        self.btn_duel_pause.setObjectName(u"btn_duel_pause")
        self.btn_duel_pause.setMaximumSize(QSize(55, 16777215))

        self.horizontalLayout_16.addWidget(self.btn_duel_pause)

        self.btn_duel_stop = QPushButton(self.tab_4)
        self.btn_duel_stop.setObjectName(u"btn_duel_stop")
        self.btn_duel_stop.setMaximumSize(QSize(55, 16777215))

        self.horizontalLayout_16.addWidget(self.btn_duel_stop)

        self.duelrepeat_checkBox = QCheckBox(self.tab_4)
        self.duelrepeat_checkBox.setObjectName(u"duelrepeat_checkBox")

        self.horizontalLayout_16.addWidget(self.duelrepeat_checkBox)

        self.horizontalSpacer_6 = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout_16.addItem(self.horizontalSpacer_6)


        self.verticalLayout_7.addLayout(self.horizontalLayout_16)

        self.horizontalLayout_18 = QHBoxLayout()
        self.horizontalLayout_18.setObjectName(u"horizontalLayout_18")
        self.horizontalLayout_18.setContentsMargins(-1, 0, -1, -1)
        self.label_duelseektimetext = QLabel(self.tab_4)
        self.label_duelseektimetext.setObjectName(u"label_duelseektimetext")

        self.horizontalLayout_18.addWidget(self.label_duelseektimetext)

        self.label_duelremainingtimetext = QLabel(self.tab_4)
        self.label_duelremainingtimetext.setObjectName(u"label_duelremainingtimetext")
        self.label_duelremainingtimetext.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.label_duelremainingtimetext.setAlignment(Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignTrailing|Qt.AlignmentFlag.AlignVCenter)

        self.horizontalLayout_18.addWidget(self.label_duelremainingtimetext)


        self.verticalLayout_7.addLayout(self.horizontalLayout_18)

        self.duel_progress_slider = QSlider(self.tab_4)
        self.duel_progress_slider.setObjectName(u"duel_progress_slider")
        self.duel_progress_slider.setOrientation(Qt.Orientation.Horizontal)

        self.verticalLayout_7.addWidget(self.duel_progress_slider)


        self.horizontalLayout_12.addLayout(self.verticalLayout_7)

        self.duel_cover_art_label = QLabel(self.tab_4)
        self.duel_cover_art_label.setObjectName(u"duel_cover_art_label")
        sizePolicy1.setHeightForWidth(self.duel_cover_art_label.sizePolicy().hasHeightForWidth())
        self.duel_cover_art_label.setSizePolicy(sizePolicy1)
        self.duel_cover_art_label.setMinimumSize(QSize(100, 100))
        self.duel_cover_art_label.setAutoFillBackground(True)

        self.horizontalLayout_12.addWidget(self.duel_cover_art_label)

        self.horizontalLayout_12.setStretch(1, 1)

        self.verticalLayout_13.addLayout(self.horizontalLayout_12)

        self.verticalSpacer = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.verticalLayout_13.addItem(self.verticalSpacer)


        self.verticalLayout_8.addLayout(self.verticalLayout_13)

        self.tabWidget.addTab(self.tab_4, "")
        self.tab_5 = QWidget()
        self.tab_5.setObjectName(u"tab_5")
        self.verticalLayout_9 = QVBoxLayout(self.tab_5)
        self.verticalLayout_9.setObjectName(u"verticalLayout_9")
        self.verticalLayout_6 = QVBoxLayout()
        self.verticalLayout_6.setObjectName(u"verticalLayout_6")
        self.fileMeta_textBrowser = QTextBrowser(self.tab_5)
        self.fileMeta_textBrowser.setObjectName(u"fileMeta_textBrowser")

        self.verticalLayout_6.addWidget(self.fileMeta_textBrowser)


        self.verticalLayout_9.addLayout(self.verticalLayout_6)

        self.tabWidget.addTab(self.tab_5, "")

        self.verticalLayout_3.addWidget(self.tabWidget)


        self.retranslateUi(MainWindow)

        self.tabWidget.setCurrentIndex(3)


        QMetaObject.connectSlotsByName(MainWindow)
    # setupUi

    def retranslateUi(self, MainWindow):
        MainWindow.setWindowTitle(QCoreApplication.translate("MainWindow", u"Form", None))
        self.settingsButton.setText(QCoreApplication.translate("MainWindow", u"Settings", None))
        self.label_volumetext.setText(QCoreApplication.translate("MainWindow", u"Volume: 100%", None))
        self.btn_play.setText(QCoreApplication.translate("MainWindow", u"Play", None))
        self.btn_pause.setText(QCoreApplication.translate("MainWindow", u"Pause", None))
        self.btn_stop.setText(QCoreApplication.translate("MainWindow", u"Stop", None))
        self.repeat_checkBox.setText(QCoreApplication.translate("MainWindow", u"Repeat Song", None))
        self.random_checkBox.setText(QCoreApplication.translate("MainWindow", u"Randomize", None))
        self.cover_art_label.setText(QCoreApplication.translate("MainWindow", u"Cover Art", None))
        self.label_seektimetext.setText(QCoreApplication.translate("MainWindow", u"Time: 0:00", None))
        self.label_remainingtimetext.setText(QCoreApplication.translate("MainWindow", u"Remaining: 0:00 of 0:00", None))
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.tab), QCoreApplication.translate("MainWindow", u"deCurse", None))
        self.youtubeURL_lineEdit.setText(QCoreApplication.translate("MainWindow", u"Enter Youtube URL Here", None))
        self.download_pushButton.setText(QCoreApplication.translate("MainWindow", u"Download", None))
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.tab_2), QCoreApplication.translate("MainWindow", u"Downlord", None))
        self.soundbard_label.setText("")
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.tab_3), QCoreApplication.translate("MainWindow", u"SoundBard", None))
        self.duel_label.setText(QCoreApplication.translate("MainWindow", u"TextLabel", None))
        self.duel_playing_text_label.setText(QCoreApplication.translate("MainWindow", u"Playing: Test_Name.mp3", None))
        self.label_duelvolumetext.setText(QCoreApplication.translate("MainWindow", u"Volume: 100%", None))
        self.btn_duel_play.setText(QCoreApplication.translate("MainWindow", u"Play", None))
        self.btn_duel_pause.setText(QCoreApplication.translate("MainWindow", u"Pause", None))
        self.btn_duel_stop.setText(QCoreApplication.translate("MainWindow", u"Stop", None))
        self.duelrepeat_checkBox.setText(QCoreApplication.translate("MainWindow", u"Repeat Song", None))
        self.label_duelseektimetext.setText(QCoreApplication.translate("MainWindow", u"Time: 0:00", None))
        self.label_duelremainingtimetext.setText(QCoreApplication.translate("MainWindow", u"Remaining: 0:00 of 0:00", None))
        self.duel_cover_art_label.setText(QCoreApplication.translate("MainWindow", u"Cover Art", None))
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.tab_4), QCoreApplication.translate("MainWindow", u"Duel Play", None))
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.tab_5), QCoreApplication.translate("MainWindow", u"File Lore", None))
    # retranslateUi

