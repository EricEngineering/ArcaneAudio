# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

ArcaneAudio — **"Arcane Audio – Cast Your Playlist"** — is a PySide6 (Qt for Python) desktop **MP3 player / music-library manager** with an arcana/magic theme, aimed at tabletop-RPG Game Masters (ambient tracks, a second simultaneous "duel" track, a soundboard, a live audio visualizer). The window title is set in `MP3Player.__init__` ([main.py:198](arcaneaudio/main.py#L198)). It is a **sibling project to ArcaneAtlas** (the battle-map app) — same author, same PySide6 + PyInstaller + Inno Setup stack, same `Documents/<App>/` data convention.

It manages a folder tree of music + `.m3u` playlists, plays MP3s with cover art from ID3 tags, downloads audio from YouTube (`yt-dlp` + ffmpeg), and shows a 16-bar FFT spectrum visualizer.

## Naming
- Product name and repo: **ArcaneAudio** (CamelCase, one word)
- Python package, `.spec`, `.iss`: **arcaneaudio** (lowercase)
- Human-facing display text: **"Arcane Audio"** (two words)

## Commands

Run from source:
```bash
python -m arcaneaudio          # from repo root, with .venv active
```
- **Windows**: `runwin.bat` (prefers `.venv\Scripts\python.exe`, kills any running `ArcaneAudio.exe` first; optional logging to `logs\`).
- **Linux**: `runlin.sh` (sources `.venv/bin/activate`, runs `python3 -m arcaneaudio`).

Regenerate the Qt UI after editing `arcaneaudio/mainwindow.ui` (required — `ui_mainwindow.py` is generated):
```bash
pyside6-uic mainwindow.ui -o ui_mainwindow.py
```
There is **no `build_ui` script** — this command lives only in `README.md`. Run it from inside `arcaneaudio/`.

Build the Windows app + installer (Windows only):
```bash
build_exe.bat          # clean PyInstaller build -> dist\ArcaneAudio\
build_installer.bat    # downloads ffmpeg if missing, builds EXE, compiles arcaneaudio.iss -> installer\output\
```
`build_installer.bat` **auto-downloads a static ffmpeg** from gyan.dev into `third_party/ffmpeg/ffmpeg.exe` if absent (git-ignored, never committed); the `.spec` bundles it as a binary. It passes `/DMyAppVersion=<VERSION>` (currently `1.0.1`) to Inno.

There is **no test suite, linter, CI, `requirements.txt`, or `pyproject.toml`** — dependencies exist only in the `.venv`. See Dependencies below.

## Dependencies

No manifest file exists; these are the actual runtime imports ([main.py:15-50](arcaneaudio/main.py#L15-L50)):

- **PySide6** (Qt6) — GUI + `QtMultimedia` (`QMediaPlayer` + `QAudioOutput` for playback; `QAudioBufferOutput` to feed the visualizer — see Audio visualizer)
- **pyqtgraph** — the spectrum bar graph (`visualizationWidget`, a promoted `PlotWidget`)
- **numpy** — FFT / signal math
- **yt-dlp** — YouTube audio download (Downlord tab)
- **mutagen** — ID3 read/write, cover-art (APIC) embedding
- **Pillow (PIL)** — cover-art crop/scale + `ImageQt` conversion
- **ffmpeg** (external binary) — audio extraction for yt-dlp; on PATH in dev, bundled in the frozen build

## Architecture

### Module layout (package `arcaneaudio/`)
This is a **monolith** — nearly everything lives in one file. There is no MVC separation and no shallow-split like ArcaneAtlas has.

- **`main.py`** (~2,476 lines) — the entire app: all classes + `main()`.
- **`ui_mainwindow.py`** (generated) — `Ui_MainWindow` from `pyside6-uic`. **Never hand-edit**; change `mainwindow.ui` and regenerate.
- **`__main__.py`** — `from .main import main; sys.exit(main())` (enables `python -m arcaneaudio`).
- **`__init__.py`** — `__version__ = "1.0.0"`, `__author__ = "Eric Hernandez"`.
- **`resources/__init__.py`** — makes `resources` importable for `importlib.resources`.
- **`hooks/runtime_path.py`** (repo root, not in package) — PyInstaller runtime hook that prepends the bundle dir + `_internal/` to `PATH` so the bundled `ffmpeg.exe` resolves at runtime.

### Key classes (all in `main.py`)
- **`MP3Player(QWidget)`** ([main.py:143](arcaneaudio/main.py#L143)) — the main window / god-object (~1,560 lines of methods). `__init__` builds the whole UI, sets up stdout/stderr redirection, the gear/settings menu (themes, change/reset music folder, About), the `QSplitter` layout, the primary player, the pyaudio stream + visualizer, then `load_settings()`. Owns all playback, download, file-management, and duel logic.
- **`MP3ListWidget(QListWidget)`** ([main.py:1708](arcaneaudio/main.py#L1708)) — right-hand track list; custom drag-drop (private mime `application/x-mp3-song`), context menu (Remove-from-playlist / Delete-MP3 / Send-to-Duel).
- **`FolderTreeWidget(QTreeWidget)`** ([main.py:1864](arcaneaudio/main.py#L1864)) — left library tree (folders + `.m3u`); populates from disk, moves files on folder-drop, appends to playlists on playlist-drop, mirrors reordering to the filesystem.
- **`ClickSliderWidget(QSlider)`** ([main.py:2129](arcaneaudio/main.py#L2129)) — click-to-seek slider (progress + volume sliders are promoted to this).
- **`DownloadThread(QThread)`** ([main.py:2179](arcaneaudio/main.py#L2179)) — the **only real background thread**: runs `yt-dlp` off the UI thread, extracts to 192 kbps MP3 via ffmpeg, embeds the thumbnail as APIC art, uniquifies the filename. Emits `progress`/`finished`/`error`. `YTDLPLogger` ([main.py:2140](arcaneaudio/main.py#L2140)) pipes yt-dlp logs to the GUI via signals.
- **`SelectAllLineEdit(QLineEdit)`** ([main.py:2401](arcaneaudio/main.py#L2401)) — URL field that selects-all on focus.
- **`StreamRedirector`** ([main.py:2409](arcaneaudio/main.py#L2409)) — redirects `sys.stdout`/`sys.stderr` into the in-app "deCurse" debug console (thread-safe, routes lines by `[downlord]`/`[append]`/`[yt_dlp]` tags). This is why logs are visible even though the frozen build is `--noconsole`.

### The two players ("Duel Play")
The **primary** player (`self.player` / `self.audio_output`) is created eagerly at [main.py:411-418](arcaneaudio/main.py#L411-L418) and always present. The **second** player (`self.player2` / `self.audio_output2`) is a placeholder (`None`) until `send_mp3_duel` lazily creates it ([main.py:1529](arcaneaudio/main.py#L1529)), and it's fully torn down (`deleteLater`, reset to `None`) on `duel_stop` ([main.py:1578](arcaneaudio/main.py#L1578)) — so two tracks (e.g. ambient + combat sting) can play at once, each with its own progress/volume/repeat controls. Both paths include `QTimer.singleShot` "play hacks" to force position 0, working around `QMediaPlayer` not auto-starting some MP3s with embedded art (see comments near [main.py:894-897](arcaneaudio/main.py#L894-L897) and [main.py:1554-1571](arcaneaudio/main.py#L1554-L1571)).

### UI tabs
Five tabs, defined in the generated UI ([ui_mainwindow.py:473-490](arcaneaudio/ui_mainwindow.py#L473-L490)): **deCurse** (debug console, index 0), **Downlord** (YouTube downloader), **SoundBard** (soundboard — **placeholder**, only a banner image; the logic is an unimplemented TODO), **Duel Play**, **File Lore** (ID3 metadata display). The `.ui`'s default `setCurrentIndex` is overridden at runtime.

### Audio visualizer (driven by playback, not a microphone)
The 16-bar FFT spectrum visualizer is fed by **`QAudioBufferOutput`** (Qt 6.8+, FFmpeg backend), which taps the decoded PCM buffers the media player produces *as it plays* — so the bars react to the actual music, cross-platform (Win/Mac/Linux), with **no microphone capture and no OS mic-permission prompt**.

- `_attach_visualizer(player, key)` creates a `QAudioBufferOutput`, connects its `audioBufferReceived` signal, calls `player.setAudioBufferOutput(...)`, and **stores the object in `self._viz_buffer_outputs[key]` so it isn't garbage-collected** (dropping the Python ref silently stops capture). Called for the main player in `__init__` (key `"main"`) and for the duel player when it's created (key `"duel"`).
- `_on_viz_buffer(key, buf)` → `_viz_extract_mono(buf)` decodes the `QAudioBuffer` to a mono float32 window (`constData()` is a **transient memoryview** — the `.astype()`/reshape copies detach it before the callback returns; handles Int16/Int32/Float/UInt8 sample formats and averages channels to mono) and stashes the latest window in `self._viz_sources[key]`.
- `update_spectrograph()` (100 ms `QTimer`) **mixes all currently-playing sources** (main + duel) into one window, removes DC bias, normalizes by peak (bars fall to rest on silence rather than amplifying noise), FFTs, maps to 16 log-spaced bands, EMA-smooths (`previous_bar_heights`), and redraws the purple bars.
- `_update_viz_timer()` runs the redraw timer only while the main *or* duel player is `PlayingState`, and **drops a source's stashed samples when it stops** so the mix reflects only what's audible. It's invoked from `handle_playback_state` (main) and `player2.playbackStateChanged` (duel); `duel_stop` disconnects that signal, calls `_detach_visualizer("duel")`, and re-checks the timer.

There is **no input- or output-device selection UI**; playback output uses Qt's default device. (History: the visualizer previously used PyAudio to capture the *microphone*, which triggered the OS mic prompt and made the bars react to ambient room sound instead of the music — that whole `init_audio_stream()` path was removed.) `QAudioBufferOutput` requires the FFmpeg multimedia backend, which is the default in the PyPI PySide6 wheels — don't force a native backend (`QT_MEDIA_BACKEND`) or buffer delivery stops.

## Persistence & file layout

- **User data root**: `Documents/ArcaneAudio/` via `QStandardPaths.DocumentsLocation` ([main.py:56-61](arcaneaudio/main.py#L56-L61)).
- **Music library**: `Documents/ArcaneAudio/music/` by default (`working_dir`, user-changeable via the gear menu). Downloads → `<working_dir>/downloads/`. Deletes move to `<working_dir>/.trash/` (with an empty-trash action).
- **Settings**: `Documents/ArcaneAudio/settings.json` (JSON). Keys: `theme`, `working_dir`, `h_splitter_sizes`, `v_splitter_sizes`, `window_size`, `volume`, `selected_tab`. Created by `ensure_settings_file` ([main.py:74](arcaneaudio/main.py#L74)), loaded in `load_settings` ([main.py:1416](arcaneaudio/main.py#L1416)), saved on folder-change and in `closeEvent` ([main.py:1486](arcaneaudio/main.py#L1486)). The module global `SETTINGS_FILE` is computed **after** `QApplication` exists (needs `QStandardPaths`).
- **Playlists** are plain `.m3u` (`#EXTM3U` + working-dir-relative paths). `update_playlist_paths` ([main.py:589](arcaneaudio/main.py#L589)) rewrites references when files/folders are renamed or moved.
- **Themes**: Arcana (purple, default), Dark, Default-OS — applied via stylesheet in the gear menu.

## Resource loading (dev vs frozen)
Use `res_path(name)` ([main.py:101-128](arcaneaudio/main.py#L101-L128)) for any bundled asset. It resolves across three modes: PyInstaller `_MEIPASS` (trying several layouts incl. `_internal/`), `importlib.resources` over `arcaneaudio.resources`, then a dev source fallback. Resources live in `arcaneaudio/resources/` (app/cover icon `icon.png`/`icon.ico`, `gear_icon.png`, tree-state icons `folder[-yes/-no].png` / `playlist[-yes/-no].png`, banners `soundbard.png` / `duel.png`, `installer.ico`, and `AGPL_V3.txt`). The `.spec` ships them via `Tree("arcaneaudio/resources", prefix="arcaneaudio/resources")` (`Analysis.datas` is empty) — keep resource bundling there.

## Packaging
- **`arcaneaudio.spec`** — one-folder PyInstaller build, `console=False`, UPX on. Entry `arcaneaudio/main.py`; `hiddenimports = collect_submodules("arcaneaudio")`; **bundles `third_party/ffmpeg/ffmpeg.exe`** as a binary; `runtime_hooks=["hooks/runtime_path.py"]` (so bundled ffmpeg is found); EXE icon `resources/icon.ico`.
- **`arcaneaudio.iss`** (repo root; the build copies it into `installer/` so `SourcePath == installer\`) — machine-wide admin install to `{autopf}\ArcaneAudio`, AGPLv3 license page (`resources/AGPL_V3.txt`), Start-menu + optional desktop shortcut. **Display name vs. folder**: `MyAppName = "Arcane Audio"` (with a space — user-visible name/shortcuts) while `MyAppDirName = "ArcaneAudio"` drives `DefaultDirName` (space-free path). **`AppId` is now a real permanent GUID** (`B9EB3FEB-…`) — it was previously the `{{PUT-A-NEW-GUID-HERE}}` placeholder. `MyAppVersion` is `#ifndef`-guarded (derived from `__init__.py`), and the DEBUG `#pragma message` lines were removed.

## Release automation (GitHub Actions)
`.github/workflows/release.yml` builds the **Windows installer + Linux tarball + macOS `.dmg`** and publishes them to a GitHub Release, code-signed. It is a **sibling copy of ArcaneAtlas's workflow** — see ArcaneAtlas `CLAUDE.md` → "Release automation (GitHub Actions)" for the full mechanics (trigger via tag or `workflow_dispatch`, idempotent re-runs, the asset-name contract, `az login --service-principal` Windows auth, macOS import-cert → build → notarize → staple → `spctl` verify, and the secret list). **Keep the three apps' workflows in sync; only the `env:` block and per-app quirks differ.** ArcaneAudio specifics:
- **Assets** (the `arcanetools.org/_redirects` contract): `ArcaneAudio-Setup-windows.exe`, `ArcaneAudio-linux.tar.gz`, `ArcaneAudio-macos.dmg`.
- **macOS is a universal2 (arm64 + x86_64) build** — same as ArcaneAtlas: built on the `macos-14` arm64 runner via a **python.org universal2 Python** (replacing arch-specific `setup-python`) + universal2 PySide6 wheels + `target_arch='universal2'` in the spec, so the `.dmg` runs on both Apple Silicon and Intel Macs without ever touching the Intel `macos-13` runner.
- **ffmpeg is bundled on ALL platforms** (for the yt-dlp YouTube→MP3 "Downlord" feature — playback/visualizer/local MP3 need none of it). CI fetches the right static build into `third_party/ffmpeg/` before the build (Windows: **BtbN** GitHub `.exe`; Linux: johnvansickle; macOS: **fat** = arm64 + amd64 martin-riedl builds `lipo`'d together for universal2), each verified to have `--enable-libmp3lame`. The spec's `binaries` picks `ffmpeg.exe`/`ffmpeg` by `sys.platform`. Because ffmpeg is an **`a.binaries`** entry (not Tree data like ArcaneAtlas), PyInstaller signs it during the macOS build — and the workflow's *Re-sign bundled ffmpeg* step additionally re-signs each nested `ffmpeg` Mach-O with a hardened runtime and re-seals the `.app`, guaranteeing notarization accepts it (belt-and-suspenders vs. the unsigned-nested-binary rejection ArcaneAtlas hit).
- **Version = single source of truth** in `arcaneaudio/__init__.py` (0.8.0). This **reconciled a prior mismatch** — `__init__.py` said 1.0.0 while the `.iss`/`.bat` said 1.0.1; all now derive from `__init__.py`.
- **Signing infra added**: macOS `BUNDLE` + `codesign_identity`/`entitlements_file` in the spec (platform-guarded), `packaging/entitlements.mac.plist`, and a `requirements.txt` (`PySide6, pyqtgraph, numpy, yt-dlp, mutagen, Pillow, pyinstaller`) — none existed before. **Signing reuses Atlas's secrets** (one Trusted Signing account + one Apple Developer ID cover all three apps): paste the identical 6 `AZURE_*`/`TRUSTED_SIGNING_*` + 7 `MACOS_*` secrets into this repo.

## Conventions / gotchas
- **`ui_mainwindow.py` is generated** — never hand-edit; change `mainwindow.ui` and rerun `pyside6-uic`.
- **The frozen build is `--noconsole`**, so `print()` output only appears in the in-app "deCurse" tab via `StreamRedirector`. The code uses heavy tagged `print()` diagnostics (`[downlord]`, `[settings]`, `✅`/`❌`).
- **ffmpeg is never committed** — `build_installer.bat` downloads it into `third_party/ffmpeg/` (git-ignored) at build time; in dev it must be on `PATH` for yt-dlp extraction.
- **The visualizer taps playback via `QAudioBufferOutput`, not a microphone** (see Audio visualizer) — the app no longer opens any audio *input*, so there's no OS mic-permission prompt. `pyaudio` is no longer imported.
- **Known dead code / cruft** (flag, don't rely on): `arcaneaudio/last_working.py` (~2,029-line stale backup of an earlier `main.py`, not imported anywhere); the `__init__.py` docstring and `build_exe.bat` process-kill filter still reference the **old project name "gmsnipe" / "Game Master Snip Tool"**; `save_folder_order` ([main.py:864](arcaneaudio/main.py#L864)) is dormant (`folder_settings_path` stays `None`). An end-of-file TODO list lives at [main.py:2467-2476](arcaneaudio/main.py#L2467-L2476).
- **No networking** except `yt-dlp` fetching user-supplied YouTube URLs and the build script downloading ffmpeg.
- Sibling project **ArcaneAtlas** (`c:\Workspaces\Python\ArcaneAtlas`) shares the toolchain and has a much more detailed CLAUDE.md — useful reference for the shared PyInstaller/Inno/`res_path`/`Documents/<App>/` patterns.
