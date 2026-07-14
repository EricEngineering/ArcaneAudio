# arcaneaudio.spec
import os, sys
from pathlib import Path
from PyInstaller.building.build_main import Analysis, PYZ, EXE, COLLECT
from PyInstaller.building.datastruct import Tree
from PyInstaller.utils.hooks import collect_submodules

APP_NAME = "ArcaneAudio"
ENTRY = "arcaneaudio/main.py"   # runs main() via __main__.py

hiddenimports = collect_submodules("arcaneaudio")

# Optional icon (.ico) for EXE (safe if missing)
ico_path = Path("arcaneaudio/resources/icon.ico")
icon_arg = str(ico_path) if ico_path.exists() else None

# macOS code signing (single source of truth = the CI secrets). When
# MACOS_SIGN_IDENTITY is set (signed CI path only), PyInstaller signs the
# collected binaries with a hardened runtime + our entitlements during the
# build. Empty/unset → an ordinary unsigned build. See CLAUDE.md.
_is_mac = sys.platform == "darwin"
_is_win = sys.platform.startswith("win")
codesign_identity = (os.environ.get("MACOS_SIGN_IDENTITY") or None) if _is_mac else None
entitlements_file = "packaging/entitlements.mac.plist" if codesign_identity else None
# Universal2 (arm64 + x86_64) macOS binary so the app runs on both Apple Silicon
# and Intel Macs. CI provides a universal2 Python + universal2 wheels + a fat
# ffmpeg. None elsewhere (Windows/Linux are single-arch).
target_arch = "universal2" if _is_mac else None

# ffmpeg (for the yt-dlp YouTube→MP3 feature) is bundled on ALL platforms. CI
# fetches the right static build into third_party/ffmpeg/ before the build
# (ffmpeg.exe on Windows, ffmpeg on macOS/Linux). Because it's an a.binaries
# entry, PyInstaller signs it during the macOS build; the workflow additionally
# re-signs it with a hardened runtime to guarantee notarization. See CLAUDE.md.
_ffmpeg_name = "ffmpeg.exe" if _is_win else "ffmpeg"
_ffmpeg_src = f"third_party/ffmpeg/{_ffmpeg_name}"
binaries = [(_ffmpeg_src, ".")] if Path(_ffmpeg_src).exists() else []

a = Analysis(
    [ENTRY],
    pathex=["."],
    binaries=binaries,
    datas=[],
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=["hooks/runtime_path.py"],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon=icon_arg,
    codesign_identity=codesign_identity,   # macOS signing; None elsewhere
    entitlements_file=entitlements_file,
    target_arch=target_arch,               # 'universal2' on macOS, None elsewhere
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    Tree("arcaneaudio/resources", prefix="arcaneaudio/resources"),
    strip=False,
    upx=True,
    name=APP_NAME,
)

# macOS: wrap the collected app in a .app bundle so it can be shipped in a .dmg.
# Platform-guarded, so Windows/Linux builds are unaffected.
if _is_mac:
    from PyInstaller.building.osx import BUNDLE
    icns_path = Path("arcaneaudio/resources/icon.icns")
    app = BUNDLE(
        coll,
        name=f"{APP_NAME}.app",
        icon=str(icns_path) if icns_path.exists() else None,
        bundle_identifier="org.arcanetools.arcaneaudio",
    )
