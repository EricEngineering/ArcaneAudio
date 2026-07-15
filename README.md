<img src="arcaneaudio/resources/icon.png" alt="Arcane Audio logo" width="150">

# Arcane Audio

**Music & ambience for in-person TTRPGs** — part of the [Arcane Tools](https://arcanetools.org) suite.

Point it at folders of your own MP3s and go, or build a playlist to score a
scripted battle scene. Either way, when you rename, move, or reorganize tracks, the
playlists follow and repair their own paths, so they never break. Layer two tracks
at once for a rain loop under a tavern tune. No browser tab, no subscription, no
internet connection required.

**[⬇ Download for Windows, macOS & Linux →](https://arcanetools.org)**

## Support

The software is free, forever — open-source (AGPLv3), no paywall, no account, no
upsell. A few things still cost money, though: code-signing certificates run about
$250 a year (Apple's Developer Program to notarize the macOS builds, and Microsoft
Trusted Signing for Windows), and domain names and hosting are another $50. If these
tools are useful to you, your support on [Patreon](https://www.patreon.com/EricEngineering)
helps cover the cost and keeps development going. Thank you!

## Building

Rebuild the UI:

```
pyside6-uic mainwindow.ui -o ui_mainwindow.py
```

Windowed build with PyInstaller:

```
pyinstaller arcaneaudio.spec
```

## License

Arcane Audio is licensed under the GNU Affero General Public License v3.0 (AGPLv3). See [arcaneaudio/resources/AGPL_V3.txt](arcaneaudio/resources/AGPL_V3.txt).
