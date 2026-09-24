#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Auto Downloader Organizer - GUI version (single file, modern flat theme).

Features
--------
* Watches the browser Downloads folder and moves finished files into
  category subfolders (documents, tables, presentations, images, ...).
* Modern dark UI: custom ttk theme, card layout, status pill, colored log.
* User-selectable UI language: English / Русский / 中文 (segmented buttons).
  The choice is persisted in config.json; on first run it is auto-detected
  from the system locale. Category folder names are localized too.
* System-tray mode: "minimize to tray" checkbox + "--hidden" command-line
  flag let the app start silently in the background and keep sorting even
  when the window is closed (tray icon: left-click opens the window,
  right-click menu has Show / Start / Stop / Exit).
* Windows autostart via HKCU\\...\\Run registry key (no admin rights needed).
* All source comments are written in English.

Run:          python organizer_gui.py
Run hidden:   python organizer_gui.py --hidden
Build:        python -m PyInstaller --onefile --noconsole organizer_gui.py
Dependencies: pip install watchdog pystray pillow
"""

import json
import os
import shutil
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

try:
    from watchdog.events import FileSystemEventHandler
    from watchdog.observers import Observer
except ImportError:
    sys.exit("Missing dependency 'watchdog'. Install it with:  pip install watchdog")

# Optional tray support. If pystray/pillow are missing (or there is no
# display yet) the app still works, but the tray options are not shown.
TRAY_AVAILABLE = False
try:
    import pystray
    from PIL import Image, ImageDraw
    TRAY_AVAILABLE = True
except Exception:
    pass

# --------------------------------------------------------------------------- #
# Paths. When frozen by PyInstaller we use the folder of the executable,
# otherwise the folder of this script. This keeps config.json next to the .exe.
# --------------------------------------------------------------------------- #
if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).resolve().parent
else:
    BASE_DIR = Path(__file__).resolve().parent

CONFIG_FILE = BASE_DIR / "config.json"
LOG_FILE = BASE_DIR / "history.log"

# --------------------------------------------------------------------------- #
# Color palette (dark "midnight" theme). One source of truth for all widgets.
# --------------------------------------------------------------------------- #
BG        = "#1e222d"   # window background
CARD      = "#262b38"   # raised card surface
FIELD     = "#191d26"   # input / log background (recessed)
BORDER    = "#3a4152"   # hairlines, widget borders
FG        = "#e8eaf0"   # main text
MUTED     = "#8b93a7"   # secondary text / captions
ACCENT    = "#4f8cff"   # brand blue (focus, links)
GREEN     = "#2ecc71"   # running state
GREEN_DK  = "#27ae60"
RED       = "#e74c3c"   # stop / error
RED_DK    = "#c0392b"
AMBER     = "#f1c40f"   # warnings / skipped lines

FONT         = "Segoe UI"           # falls back gracefully on other OSes
FONT_MONO    = "Consolas"

# --------------------------------------------------------------------------- #
# Translations. Every user-visible string lives here so the whole interface
# (including the generated category folder names) can be re-rendered at once.
# --------------------------------------------------------------------------- #
TRANSLATIONS = {
    "en": {
        "title": "Auto Downloader Organizer",
        "subtitle": "Keeps your Downloads folder clean automatically",
        "status_running": "RUNNING",
        "status_paused": "PAUSED",
        "section_folders": "FOLDERS",
        "watch_label": "Watched folder",
        "dest_label": "Organize into",
        "btn_start": "\u25b6  START SORTING",
        "btn_stop": "\u25a0  STOP",
        "log_header": "EVENT LOG",
        "error": "Error",
        "folder_not_found": "Folder not found:\n{}",
        "started": "Sorting started: {} -> {}",
        "stopped": "Sorting stopped.",
        "moving": "Moved: {}  ->  {}/{}",
        "skipped": "Skipped (still downloading): {}",
        "error_move": "Could not move {}: {}",
        "busy": "File is busy, will retry: {}",
        "give_up": "Giving up on {} after too many retries; leaving it in place",
        "in_list": "Still in the browser download list, waiting: {}",
        "opened_move": "Opened from the browser, sorting now: {}",
        "hint": "Tip: closing the window minimizes it to the tray and keeps sorting.",
        "grace_label": "Move after, sec",
        # Tray / startup options
        "opt_tray": "Minimize to system tray (keep running when window is closed)",
        "opt_autostart": "Start automatically with Windows",
        "opt_hidden": "Launch hidden in the tray on startup",
        "tray_show": "Show window",
        "tray_start": "Start sorting",
        "tray_stop": "Stop sorting",
        "tray_exit": "Exit",
        # Category folder names
        "cat_documents": "Documents",
        "cat_tables": "Spreadsheets",
        "cat_presentations": "Presentations",
        "cat_images": "Images",
        "cat_music": "Music",
        "cat_video": "Video",
        "cat_archives": "Archives",
        "cat_installers": "Installers",
        "cat_code": "Code",
        "cat_fonts": "Fonts",
        "cat_3d": "3D",
        "cat_books": "E-books",
        "cat_other": "Other",
    },
    "ru": {
        "title": "Авто-сортировщик загрузок",
        "subtitle": "Папка «Загрузки» всегда в порядке — автоматически",
        "status_running": "РАБОТАЕТ",
        "status_paused": "ПАУЗА",
        "section_folders": "ПАПКИ",
        "watch_label": "Наблюдать за папкой",
        "dest_label": "Раскладывать в",
        "btn_start": "\u25b6  ЗАПУСТИТЬ",
        "btn_stop": "\u25a0  ОСТАНОВИТЬ",
        "log_header": "ЖУРНАЛ СОБЫТИЙ",
        "error": "Ошибка",
        "folder_not_found": "Папка не найдена:\n{}",
        "started": "Сортировка запущена: {} -> {}",
        "stopped": "Сортировка остановлена.",
        "moving": "Перемещён: {}  ->  {}/{}",
        "skipped": "Пропуск (ещё качается): {}",
        "error_move": "Не удалось переместить {}: {}",
        "busy": "Файл занят, повторю позже: {}",
        "give_up": "Слишком много попыток для {}; оставляю файл на месте",
        "in_list": "Файл ещё в списке загрузок браузера, жду: {}",
        "opened_move": "Открыт из браузера, сортирую: {}",
        "hint": "Подсказка: закрытие окна сворачивает его в трей — сортировка продолжается.",
        "grace_label": "Переносить через, сек",
        # Tray / startup options
        "opt_tray": "Сворачивать в трей (работать при закрытом окне)",
        "opt_autostart": "Запускать автоматически вместе с Windows",
        "opt_hidden": "При запуске сразу сворачиваться в трей",
        "tray_show": "Открыть окно",
        "tray_start": "Запустить сортировку",
        "tray_stop": "Остановить сортировку",
        "tray_exit": "Выход",
        # Category folder names
        "cat_documents": "Документы",
        "cat_tables": "Таблицы",
        "cat_presentations": "Презентации",
        "cat_images": "Картинки",
        "cat_music": "Музыка",
        "cat_video": "Видео",
        "cat_archives": "Архивы",
        "cat_installers": "Установщики",
        "cat_code": "Код",
        "cat_fonts": "Шрифты",
        "cat_3d": "3D",
        "cat_books": "Книги",
        "cat_other": "Прочее",
    },
    "zh": {
        "title": "下载自动整理器",
        "subtitle": "自动保持下载文件夹整洁",
        "status_running": "运行中",
        "status_paused": "已暂停",
        "section_folders": "文件夹",
        "watch_label": "监视文件夹",
        "dest_label": "整理到",
        "btn_start": "\u25b6  开始整理",
        "btn_stop": "\u25a0  停止",
        "log_header": "事件日志",
        "error": "错误",
        "folder_not_found": "找不到文件夹：\n{}",
        "started": "整理已启动：{} -> {}",
        "stopped": "整理已停止。",
        "moving": "已移动：{}  ->  {}/{}",
        "skipped": "跳过（仍在下载）：{}",
        "error_move": "无法移动 {}：{}",
        "busy": "文件被占用，稍后重试：{}",
        "give_up": "{}重试次数过多，保留原位",
        "in_list": "文件仍在浏览器下载列表中，等待：{}",
        "opened_move": "已从浏览器打开，立即整理：{}",
        "hint": "提示：关闭窗口会最小化到托盘，整理继续进行。",
        "grace_label": "延迟移动（秒）",
        # Tray / startup options
        "opt_tray": "最小化到系统托盘（关闭窗口后继续运行）",
        "opt_autostart": "随 Windows 自动启动",
        "opt_hidden": "启动时直接隐藏到托盘",
        "tray_show": "显示窗口",
        "tray_start": "开始整理",
        "tray_stop": "停止整理",
        "tray_exit": "退出",
        # Category folder names
        "cat_documents": "文档",
        "cat_tables": "表格",
        "cat_presentations": "演示文稿",
        "cat_images": "图片",
        "cat_music": "音乐",
        "cat_video": "视频",
        "cat_archives": "压缩包",
        "cat_installers": "安装包",
        "cat_code": "代码",
        "cat_fonts": "字体",
        "cat_3d": "3D",
        "cat_books": "电子书",
        "cat_other": "其他",
    },
}

LANGUAGE_NAMES = {"en": "English", "ru": "Русский", "zh": "中文"}

# Extensions that mean "the browser is still writing this file".
PARTIAL_EXTENSIONS = {".part", ".crdownload", ".download", ".tmp"}

# Extension -> translation key of the destination category.
RULES = {
    # Documents
    ".pdf": "cat_documents", ".docx": "cat_documents", ".doc": "cat_documents",
    ".txt": "cat_documents", ".md": "cat_documents", ".rtf": "cat_documents",
    ".odt": "cat_documents", ".tex": "cat_documents", ".log": "cat_documents",
    # Spreadsheets
    ".xlsx": "cat_tables", ".xls": "cat_tables", ".xlsm": "cat_tables",
    ".csv": "cat_tables", ".tsv": "cat_tables", ".ods": "cat_tables",
    # Presentations
    ".pptx": "cat_presentations", ".ppt": "cat_presentations",
    ".pps": "cat_presentations", ".ppsx": "cat_presentations",
    ".odp": "cat_presentations", ".key": "cat_presentations",
    # Images
    ".jpg": "cat_images", ".jpeg": "cat_images", ".png": "cat_images",
    ".gif": "cat_images", ".webp": "cat_images", ".bmp": "cat_images",
    ".svg": "cat_images", ".tiff": "cat_images", ".ico": "cat_images",
    ".heic": "cat_images", ".raw": "cat_images", ".psd": "cat_images",
    # Music
    ".mp3": "cat_music", ".flac": "cat_music", ".wav": "cat_music",
    ".aac": "cat_music", ".ogg": "cat_music", ".m4a": "cat_music",
    ".wma": "cat_music", ".opus": "cat_music", ".mid": "cat_music",
    # Video
    ".mp4": "cat_video", ".mkv": "cat_video", ".avi": "cat_video",
    ".mov": "cat_video", ".wmv": "cat_video", ".flv": "cat_video",
    ".webm": "cat_video", ".m4v": "cat_video", ".mpg": "cat_video",
    ".mpeg": "cat_video", ".ts": "cat_video",
    # Archives
    ".zip": "cat_archives", ".rar": "cat_archives", ".7z": "cat_archives",
    ".tar": "cat_archives", ".gz": "cat_archives", ".bz2": "cat_archives",
    ".xz": "cat_archives", ".iso": "cat_archives",
    # Installers / executables
    ".exe": "cat_installers", ".msi": "cat_installers", ".apk": "cat_installers",
    ".bat": "cat_installers", ".cmd": "cat_installers", ".appimage": "cat_installers",
    ".deb": "cat_installers", ".rpm": "cat_installers",
    # Source code
    ".py": "cat_code", ".js": "cat_code", ".html": "cat_code", ".css": "cat_code",
    ".json": "cat_code", ".xml": "cat_code", ".java": "cat_code", ".cpp": "cat_code",
    ".c": "cat_code", ".h": "cat_code", ".cs": "cat_code", ".php": "cat_code",
    ".rb": "cat_code", ".go": "cat_code", ".rs": "cat_code", ".sh": "cat_code",
    ".sql": "cat_code", ".ipynb": "cat_code", ".yml": "cat_code", ".yaml": "cat_code",
    # Fonts
    ".ttf": "cat_fonts", ".otf": "cat_fonts", ".woff": "cat_fonts",
    ".woff2": "cat_fonts",
    # 3D / design
    ".blend": "cat_3d", ".fbx": "cat_3d", ".obj": "cat_3d", ".stl": "cat_3d",
    ".step": "cat_3d", ".dwg": "cat_3d",
    # E-books
    ".epub": "cat_books", ".mobi": "cat_books", ".azw3": "cat_books",
    ".djvu": "cat_books", ".fb2": "cat_books",
}


def detect_system_language() -> str:
    """Guess the initial UI language from the OS locale (used only on first run)."""
    try:
        import locale
        loc = (locale.getdefaultlocale()[0] or "").lower()
    except Exception:
        loc = ""
    if loc.startswith("ru"):
        return "ru"
    if loc.startswith("zh"):
        return "zh"
    return "en"

# --------------------------------------------------------------------------- #
# Windows autostart helpers. The entry lives in HKCU\...\Run, so no admin
# rights are required and it points either to the frozen .exe or to
# "pythonw.exe organizer_gui.py --hidden" for script runs.
# --------------------------------------------------------------------------- #
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_NAME = "AutoDownloaderOrganizer"


def current_launch_command() -> str:
    """Command line used to (re)launch this app hidden in the tray."""
    if getattr(sys, "frozen", False):                      # running as .exe
        return f'"{Path(sys.executable).resolve()}" --hidden'
    script = Path(__file__).resolve()
    return f'"{sys.executable}" "{script}" --hidden'       # pythonw.exe + script


def set_autostart(enable: bool) -> bool:
    """Write/remove the Run key. Returns True on success (no-op on non-Windows)."""
    if sys.platform != "win32":
        return False
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0,
                            winreg.KEY_SET_VALUE) as key:
            if enable:
                winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ,
                                  current_launch_command())
            else:
                try:
                    winreg.DeleteValue(key, APP_NAME)
                except FileNotFoundError:
                    pass
        return True
    except Exception:
        return False


def is_autostart_enabled() -> bool:
    if sys.platform != "win32":
        return False
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            winreg.QueryValueEx(key, APP_NAME)
        return True
    except Exception:
        return False


_single_instance_handle = None  # keep the mutex handle alive for the whole run

# Names of the cross-process IPC objects used for the single-instance logic:
# a Windows event that the FIRST instance waits on, and a memory-mapped flag
# that tells that instance whether it should also bring its window forward.
SHOW_EVENT_NAME = f"Global\\{APP_NAME}.ShowEvent"
FLAG_MAP_NAME = f"Global\\{APP_NAME}.ShowFlag"


def acquire_single_instance() -> bool:
    """Ensure only ONE copy of the app runs at a time (Windows named mutex).

    Multiple running copies is the main reason users see several identical
    tray icons. If another instance already holds the mutex, we return False
    and the caller asks the running instance to show its window
    (see raise_show_request) before exiting without any window or icon
    before exiting without creating any window or icon.
    On non-Windows systems the check is skipped (returns True).
    """
    global _single_instance_handle
    if sys.platform != "win32":
        return True
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        ERROR_ALREADY_EXISTS = 183
        handle = kernel32.CreateMutexW(None, False, f"Global\\{APP_NAME}.mutex")
        if not handle:
            return True  # cannot create - do not block startup
        if kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
            kernel32.CloseHandle(handle)
            return False
        _single_instance_handle = handle  # store so it is never garbage-collected
        return True
    except Exception:
        return True


def raise_show_request() -> None:
    """Called by a duplicate launch: ask the running instance to show its window.

    Two mechanisms are combined so it works even when the app starts hidden:

    1. A tiny global shared-memory flag (pagefile-backed section). The
       duplicate sets it to 1; the running instance reads it when the event
       fires and only un-minimizes if somebody really asked for the window.
       This lets autostart launches ("--hidden") stay silent while a plain
       double-click on the .exe always brings the window back.
    2. SetEvent on a named Windows event, which wakes up the waiting thread
       inside the running instance immediately (no polling, no CPU cost).
    """
    if sys.platform != "win32":
        return
    try:
        import ctypes
        from ctypes import wintypes
        kernel32 = ctypes.windll.kernel32
        FILE_MAP_WRITE = 0x0002
        PAGE_READWRITE = 0x04

        hmap = kernel32.OpenFileMappingW(FILE_MAP_WRITE, False, FLAG_MAP_NAME)
        if hmap:
            view = kernel32.MapViewOfFile(hmap, FILE_MAP_WRITE, 0, 0, 4)
            if view:
                ctypes.c_uint32.from_address(view).value = 1
                kernel32.UnmapViewOfFile(view)
            kernel32.CloseHandle(hmap)
    except Exception:
        pass  # best effort only
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        EVENT_MODIFY_STATE = 0x0002
        hevt = kernel32.OpenEventW(EVENT_MODIFY_STATE, False, SHOW_EVENT_NAME)
        if hevt:
            kernel32.SetEvent(hevt)
            kernel32.CloseHandle(hevt)
    except Exception:
        pass  # cosmetic only - never crash a duplicate launcher


class ShowEventListener(threading.Thread):
    """First-instance side: wait on the named event and show the window.

    Runs as a daemon thread with a single blocking WaitForSingleObject call,
    so it costs zero CPU while idle. Tk calls are marshalled back onto the
    main thread via root.after(), which is thread-safe.
    """

    def __init__(self, on_show_always: callable):
        super().__init__(daemon=True)
        self.on_show_always = on_show_always   # callback(bool bring_window)
        self._stop = threading.Event()
        self._handle = None
        if sys.platform == "win32":
            try:
                import ctypes
                kernel32 = ctypes.windll.kernel32
                EVENT_ALL_ACCESS = 0x1F0003
                # Create (or open) the event; keep the handle for our lifetime.
                self._handle = kernel32.CreateEventW(None, False, False,
                                                     SHOW_EVENT_NAME)
            except Exception:
                self._handle = None
        self.start()

    @staticmethod
    def _read_and_clear_flag() -> bool:
        """Return True (and reset) if a duplicate launch set the show flag."""
        if sys.platform != "win32":
            return True
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            FILE_MAP_WRITE = 0x0002
            hmap = kernel32.OpenFileMappingW(FILE_MAP_WRITE, False, FLAG_MAP_NAME)
            if not hmap:
                return True
            try:
                view = kernel32.MapViewOfFile(hmap, FILE_MAP_WRITE, 0, 0, 4)
                if not view:
                    return True
                try:
                    cell = ctypes.c_uint32.from_address(view)
                    value = cell.value
                    cell.value = 0
                    return bool(value)
                finally:
                    kernel32.UnmapViewOfFile(view)
            finally:
                kernel32.CloseHandle(hmap)
        except Exception:
            return True

    def run(self):
        if not self._handle:
            return
        import ctypes
        kernel32 = ctypes.windll.kernel32
        WAIT_OBJECT_0 = 0
        WAIT_TIMEOUT_MS = 500
        while not self._stop.is_set():
            rc = kernel32.WaitForSingleObject(ctypes.wintypes.HANDLE(self._handle),
                                              WAIT_TIMEOUT_MS)
            if self._stop.is_set():
                break
            if rc == WAIT_OBJECT_0:
                bring = self._read_and_clear_flag()
                try:
                    self.on_show_always(bring)
                except Exception:
                    pass

    def stop(self):
        self._stop.set()


def create_shared_flag() -> None:
    """Create the global memory-mapped flag once at startup (first instance)."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        PAGE_READWRITE = 0x04
        SEC_COMMIT = 0x08000000
        hsec = kernel32.CreateFileMappingW(
            ctypes.wintypes.HANDLE(-1), None, PAGE_READWRITE, 0, 4, FLAG_MAP_NAME)
        if hsec:
            # Keep the section handle alive for the whole process lifetime.
            globals()["_flag_section_handle"] = hsec
    except Exception:
        pass


def load_app_icon():
    """Load app.png / app.ico from the exe folder (or next to this script).

    Returns an RGBA PIL image or None when no icon file is found. This keeps
    the tray icon visually identical to the taskbar/exe icon produced by
    PyInstaller --icon=app.ico.
    """
    for cand in (BASE_DIR / "app.png", BASE_DIR / "app.ico"):
        try:
            if cand.exists():
                return Image.open(cand).convert("RGBA")
        except Exception:
            pass
    return None


def make_tray_image(running: bool):
    """Tray icon: the real app artwork + a small status dot.

    Green dot = sorting on, gray dot = paused. If app.png/app.ico is missing
    we fall back to a simple drawn badge so the app never crashes on startup.
    """
    base = load_app_icon()
    if base is not None:
        img = base.resize((64, 64), Image.LANCZOS).copy()
    else:
        img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        d0 = ImageDraw.Draw(img)
        d0.rounded_rectangle((2, 2, 62, 62), radius=14, fill=(30, 34, 45, 255))
        d0.ellipse((12, 12, 52, 52), fill=(79, 140, 255, 255))
        d0.polygon([(32, 44), (20, 26), (44, 26)], fill=(255, 255, 255, 255))
    d = ImageDraw.Draw(img)
    color = (46, 204, 113, 255) if running else (139, 147, 167, 255)
    # Status dot in the bottom-right corner with a dark ring for contrast.
    d.ellipse((40, 40, 62, 62), fill=color, outline=(30, 34, 45, 255), width=3)
    return img


class AppLogic:
    """All non-GUI behaviour: configuration, classification, moving, watching."""

    def __init__(self):
        self.config = self.load_config()
        self.observer = None
        self.running = False
        self._handler = None  # set by start_watch(); used for retry scheduling
        # Anti-duplication bookkeeping (see _schedule_retry / move_file):
        # per-file retry counters and a guard against concurrent processing.
        self._retries: dict[str, int] = {}   # path-key -> retry attempts left
        self._timers: dict[str, float] = {}  # path-key -> epoch of next retry
        self._max_retries = 200          # hard cap -> no infinite loops ever
        self._moving: set[str] = set()   # paths currently being moved
        self._moving_lock = threading.Lock()
        # Paths that were ALREADY moved away successfully during this session.
        # Any later event for the same source path is ignored outright - this
        # is what finally kills the photo.jpg / photo (1).jpg / ... loop.
        self._moved_done: set[str] = set()
        # Files that are waiting for their grace period / browser unlock.
        # A file enters this set when it is first seen in the watch folder
        # and leaves it once it has been successfully moved or abandoned.
        # Without this guard a second "created" event (e.g. the browser
        # touching the file again, antivirus scans, OneDrive sync) re-armed
        # the pending queue and produced photo.jpg, photo (1).jpg, ... copies
        # in the destination folder.
        self._awaiting: set[str] = set()

        # Callbacks are wired up by the GUI / tray layer.
        self.gui_callback = lambda msg, kind="info": None  # log line -> window
        self.state_callback = lambda: None                 # running-state changed
        self.lang = self.config.get("language") or detect_system_language()
        if self.lang not in TRANSLATIONS:
            self.lang = "en"

    # ---------------------------- configuration ---------------------------- #
    def load_config(self) -> dict:
        if CONFIG_FILE.exists():
            try:
                return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            except Exception:
                pass  # corrupted config -> fall back to defaults
        return {
            "language": None,  # None means "auto-detect on first run"
            "watch_dir": str(Path.home() / "Downloads"),
            "dest_dir": str(Path.home() / "Downloads" / "Sorted"),
            "settle_seconds": 3,
            # How long we wait for the browser to finish with a file before
            # moving it anyway (seconds). Prevents breaking "Show in folder"
            # links in the browser's own downloads list.
            "grace_seconds": 300,
            # Tray mode: minimize-to-tray is ON by default; autostart is OFF
            # until the user ticks the checkbox (it writes to the registry).
            "minimize_to_tray": True,
            "start_hidden": False,
            "autostart": False,
        }

    def save_config(self):
        CONFIG_FILE.write_text(
            json.dumps(self.config, indent=4, ensure_ascii=False), encoding="utf-8"
        )

    # ------------------------------- helpers ------------------------------- #
    @staticmethod
    def _key(path) -> str:
        """Canonical string key for a path (case-folded on Windows)."""
        return os.path.normcase(str(path))

    def tr(self, key: str, *args) -> str:
        text = TRANSLATIONS[self.lang].get(key, key)
        return text.format(*args) if args else text

    def set_language(self, lang: str):
        """Switch UI language at runtime and remember the choice."""
        if lang in TRANSLATIONS:
            self.lang = lang
            self.config["language"] = lang
            self.save_config()

    def category_for(self, name: str) -> str:
        ext = Path(name).suffix.lower()
        key = RULES.get(ext, "cat_other")
        return self.tr(key)

    @staticmethod
    def unique_path(dst: Path) -> Path:
        """Return a free file name, adding ' (1)', ' (2)' ... on collisions."""
        if not dst.exists():
            return dst
        stem, suffix = dst.stem, dst.suffix
        i = 1
        while True:
            cand = dst.with_name(f"{stem} ({i}){suffix}")
            if not cand.exists():
                return cand
            i += 1

    def log(self, message: str, kind: str = "info"):
        """Send a message to the GUI log (safe when there is no console)."""
        try:
            self.gui_callback(message, kind)
        except Exception:
            pass

    # --------------------- browser download-list awareness ------------------ #
    def _browser_history_files(self):
        """Yield History/History.sqlite files of Chromium and Firefox profiles.

        The browser's own downloads list ("Ctrl+J" page) lives in these
        databases. Reading them lets us detect downloads that are finished on
        disk but still listed as active/clickable in the browser UI - moving
        such a file would break the "show in folder" link there.
        """
        local = os.environ.get("LOCALAPPDATA", "")
        roaming = os.environ.get("APPDATA", "")
        chrome_user = Path(local) / "Google" / "Chrome" / "User Data" if local else None
        if chrome_user and chrome_user.is_dir():
            for prof in sorted(chrome_user.iterdir()):
                hist = prof / "History"
                if hist.is_file():
                    yield hist
        ff_root = Path(roaming) / "Mozilla" / "Firefox" / "Profiles" if roaming else None
        if ff_root and ff_root.is_dir():
            for prof in sorted(ff_root.iterdir()):
                hist = prof / "places.sqlite"
                if hist.is_file():
                    yield hist

    def _file_in_browser_list(self, name: str) -> bool:
        """True if `name` still appears as an unfinished download in any
        browser history database. Fail-open: any error means 'not found'."""
        deadline = time.time() + 0.5   # never block the mover thread long
        try:
            import sqlite3
        except Exception:
            return False
        like = "%" + name.replace("\\", "\\\\").replace("%", r"\%").replace("_", r"\_") + "%"
        queries = [
            # Chrome/Edge: state 0=in progress, 1=complete, 2=cancelled,
            # 3=interrupted, 4=warning. Anything not fully complete counts.
            ("SELECT COUNT(*) FROM downloads WHERE current_path LIKE ? AND state != 1",),
            ("SELECT COUNT(*) FROM downloads WHERE target_path LIKE ? AND state != 1",),
            # Firefox places.sqlite: use a read-only URI copy approach below.
            ("SELECT COUNT(*) FROM moz_annos WHERE content LIKE ?",),
        ]
        for hist in self._browser_history_files():
            if time.time() > deadline:
                break
            try:
                uri = f"file:{hist.as_posix()}?mode=ro&immutable=1"
                con = sqlite3.connect(uri, timeout=0.2, uri=True)
                try:
                    cur = con.cursor()
                    for (sql,) in queries:
                        try:
                            cur.execute(sql, (like,))
                            if cur.fetchone()[0] > 0:
                                return True
                        except sqlite3.Error:
                            continue  # table missing in this DB - try next
                finally:
                    con.close()
            except Exception:
                continue  # locked / not readable - just skip this profile
        return False

    def _file_opened_in_browser(self, name: str) -> bool:
        """True if the user already opened this download from the browser UI.

        Detection is heuristic but cheap and read-only:
        * Chromium-based browsers write a small "open" annotation into their
          History database (downloads file counts / last access). We simply
          check whether the file's atime changed after it was written to disk
          (mtime): opening a file from Explorer or the browser updates atime.
        * Additionally we look for a matching entry in the browser history DB
          marked as finished (state = 1) whose record was touched recently -
          that usually means the user clicked "Open file".
        Any error => False (fail-open: normal grace-period behaviour applies).
        """
        try:
            # Fast path: file accessed after being fully written.
            st = None
            for cand in Path(self.config["watch_dir"]).glob(name):
                st = cand.stat()
                break
            if st is not None and st.st_atime > st.st_mtime + 1:
                return True
        except Exception:
            pass
        # Slow path: completed-but-recently-touched entries in Chrome history.
        deadline = time.time() + 0.5
        local = os.environ.get("LOCALAPPDATA", "")
        if not local:
            return False
        try:
            import sqlite3
            hist = Path(local) / "Google" / "Chrome" / "User Data"
            if not hist.is_dir():
                return False
            like = "%" + name.replace("\\", "\\\\").replace("%", r"\%").replace("_", r"\_") + "%"
            for prof in sorted(hist.iterdir()):
                db = prof / "History"
                if not db.is_file() or time.time() > deadline:
                    continue
                try:
                    uri = f"file:{db.as_posix()}?mode=ro&immutable=1"
                    con = sqlite3.connect(uri, timeout=0.2, uri=True)
                    try:
                        cur = con.cursor()
                        # last_access_time updated when the user opens the file
                        # from the downloads page; stored as microseconds since
                        # 1601-01-01 (Chrome epoch). We only need existence of
                        # a finished row whose record was modified very recently.
                        cur.execute(
                            "SELECT COUNT(*) FROM downloads "
                            "WHERE current_path LIKE ? AND state = 1", (like,))
                        if cur.fetchone()[0] > 0:
                            # The DB file itself changes on open-clicks; use its
                            # mtime as a proxy for "something just happened".
                            if time.time() - db.stat().st_mtime < 10:
                                return True
                    except sqlite3.Error:
                        pass
                    finally:
                        con.close()
                except Exception:
                    continue
        except Exception:
            return False
        return False

    # ------------------------------ file moving ---------------------------- #
    def _file_is_free(self, path: Path) -> bool:
        """True when no other process (browser/antivirus) holds the file open.

        On Windows an exclusive open() fails with a sharing violation while
        the browser still keeps the just-downloaded file locked; on Linux/macOS
        files are not locked this way, so we always report 'free'.
        """
        if os.name != "nt":
            return True
        try:
            import msvcrt
            fh = os.open(str(path), os.O_RDWR | os.O_BINARY)
            try:
                # Try to lock the first byte exclusively for 0 attempts.
                msvcrt.locking(fh, msvcrt.LK_NBLCK, 1)
            except OSError:
                return False          # someone else holds the lock
            try:
                msvcrt.locking(fh, msvcrt.LK_UNLCK, 1)
            except OSError:
                pass
            return True
        except OSError:
            return False              # cannot even open it -> treat as busy
        except Exception:
            return True               # unexpected error -> don't block sorting

    def _schedule_retry(self, src: Path, delay: float):
        """Register a future retry of `src` in the dedicated timers dict.

        IMPORTANT: retries live in their OWN structure (`self._timers`), NOT
        in the watchdog pending queue. Putting them back into `pending` was
        the root cause of the infinite duplication bug: any on_modified /
        on_created event (antivirus scan, browser touching the file, cloud
        sync) refreshed the queue entry and re-triggered move_file(), while
        unique_path() kept creating 'photo (1).jpg', 'photo (2).jpg' ...
        A timer-based retry can only fire from itself, never from events.
        """
        if not src.exists():
            return
        key = self._key(src)
        with self._moving_lock:
            # Already moved away earlier -> never schedule anything for it.
            if key not in self._awaiting:
                return
            tries = self._retries.get(key, 0)
            if tries >= self._max_retries:
                self.log(self.tr("give_up", src.name), "warn")
                self._retries.pop(key, None)
                self._timers.pop(src, None)
                self._awaiting.discard(key)   # stop tracking for good
                return
            self._retries[key] = tries + 1
            # Keyed by the original Path object so sweep_loop can retry it.
            self._timers[src] = time.time() + max(1.0, delay)

    def move_file(self, src_path: Path):
        src = Path(src_path)
        if not src.exists() or not src.is_file():
            return
        # Hard guard against double-processing the same file concurrently
        # (event thread + sweeper can both call us for one path).
        key = self._key(src)
        with self._moving_lock:
            if key in self._moving:
                return
            # THE anti-duplication guard: a file that was already successfully
            # moved away earlier must never be processed again. If some event
            # (antivirus scan, browser re-touch, cloud sync, OneDrive) wakes
            # this path up later, we simply ignore it instead of creating
            # photo.jpg / photo (1).jpg / photo (2).jpg ... in the destination.
            if key in self._moved_done:
                return
            self._moving.add(key)
            # A file we already moved away earlier must never be re-queued:
            # this is the real anti-duplication guard. If a browser/antivirus
            # re-touches an old file in Downloads (or the user re-downloads a
            # fresh copy), that new file gets a NEW mtime and is handled
            # normally; but a stale duplicate of an already-moved name cannot
            # silently pile up photo.jpg / photo (1).jpg ... forever.
            if key in self._awaiting:
                pass  # still waiting for its grace period -> allowed to proceed
            else:
                self._awaiting.add(key)
        try:
            self._move_file_inner(src)
        finally:
            with self._moving_lock:
                self._moving.discard(key)

    def _finish_awaiting(self, src: Path):
        """Remove a file from the awaiting set once it is truly done."""
        with self._moving_lock:
            self._awaiting.discard(self._key(src))

    def _mark_done(self, src: Path):
        """Remember that this source path was successfully moved away.

        From now on every event for this exact path is ignored (see the
        `_moved_done` guard in move_file). The key is dropped after 1 hour
        so the set never grows unbounded during very long sessions; by then
        any stale duplicate event would have fired already.
        """
        key = self._key(src)
        with self._moving_lock:
            self._moved_done.add(key)
            self._retries.pop(key, None)
            self._timers.pop(key, None)
        t = threading.Timer(3600, lambda: self._moved_done.discard(key))
        t.daemon = True
        t.start()

    def _move_file_inner(self, src: Path):
        try:
            age = time.time() - src.stat().st_mtime
        except OSError:
            age = 0.0
        grace = float(self.config.get("grace_seconds", 300))
        retry_in = float(self.config.get("settle_seconds", 3)) + 2

        # Rule 1: never touch a file that is still being written / locked by
        # the browser. Retry shortly (bounded number of times).
        if not self._file_is_free(src):
            self.log(self.tr("busy", src.name), "warn")
            self._schedule_retry(src, retry_in)
            return

        # Rule 2 (user request): keep the file in Downloads until either
        #   a) the user has opened it from the browser's download list
        #      (detected via the browser history DBs), or
        #   b) `grace` seconds have passed since the download finished.
        # This way the browser's "Show in folder" link never breaks.
        if age < grace:
            opened = self._file_opened_in_browser(src.name)
            if opened:
                self.log(self.tr("opened_move", src.name), "info")
            else:
                # Wait until the grace period expires; re-check every few
                # seconds so an "open" click moves the file promptly.
                remaining = grace - age
                self._schedule_retry(src, min(max(remaining, 2.0), 5.0))
                return
        folder = self.category_for(src.name)
        dst_dir = Path(self.config["dest_dir"]) / folder
        dst_dir.mkdir(parents=True, exist_ok=True)
        dst = self.unique_path(dst_dir / src.name)
        try:
            shutil.move(str(src), str(dst))
        except FileNotFoundError:
            # The file vanished (user deleted/moved it) - nothing to do and,
            # crucially, NO duplicate was created.
            self._finish_awaiting(src)
            self._mark_done(src)
            return
        except PermissionError:
            self.log(self.tr("busy", src.name), "warn")
            self._schedule_retry(src, retry_in)
            return
        except Exception as e:
            self.log(self.tr("error_move", src.name, e), "error")
            # Do not spam retries on real errors: stop tracking the file.
            self._finish_awaiting(src)
            return
        # Success: clear retry counters and log the move. _mark_done() also
        # records this path as "handled for good" so no later event can make
        # us create photo (1).jpg / photo (2).jpg ... duplicates again.
        self._finish_awaiting(src)         # done with this file for good
        self._mark_done(src)
        self.log(self.tr("moving", src.name, folder, dst.name), "move")
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')}\t{src}\t->\t{dst}\n")

    # ------------------------------- watching ------------------------------ #
    def start_watch(self):
        if self.running:
            return

        logic = self

        class Handler(FileSystemEventHandler):
            """Track file activity and act once a download has settled down."""

            def __init__(self):
                self.pending = {}   # path -> timestamp of last activity

            def on_created(self, event):
                if event.is_directory:
                    return
                path = Path(event.src_path)
                if path.parent != watch_dir:
                    return
                if path.suffix.lower() in PARTIAL_EXTENSIONS:
                    logic.log(logic.tr("skipped", path.name), "warn")
                    return
                self.pending[path] = time.time()

            def on_modified(self, event):
                if event.is_directory:
                    return
                path = Path(event.src_path)
                if path in self.pending:
                    self.pending[path] = time.time()

            def on_moved(self, event):
                if event.is_directory:
                    return
                dest = Path(event.dest_path)
                src = Path(event.src_path)
                # Chrome/Firefox rename report.pdf.part -> report.pdf when done.
                if dest.parent == watch_dir and dest.suffix.lower() not in PARTIAL_EXTENSIONS:
                    self.pending.pop(src, None)
                    self.pending.pop(dest, None)
                    logic.move_file(dest)

        watch_dir = Path(self.config["watch_dir"])
        if not watch_dir.exists():
            raise FileNotFoundError(self.tr("folder_not_found", watch_dir))

        handler = Handler()
        self._handler = handler

        # Background sweeper: moves files whose size stopped changing.
        def sweep_loop():
            while self.running:
                now = time.time()
                # 1) Freshly-seen files whose activity has settled down.
                for path, last in list(handler.pending.items()):
                    if not path.exists():
                        handler.pending.pop(path, None)
                        continue
                    if now - last >= float(self.config["settle_seconds"]):
                        handler.pending.pop(path, None)
                        self.move_file(path)
                # 2) Scheduled retries (grace period / busy file). These live
                #    in their own timer dict so filesystem events can never
                #    re-arm them -> no infinite duplicate loop.
                # The timer dict keeps the ORIGINAL Path as its key (see
                # _schedule_retry), so we can retry it directly.
                for path, when in list(self._timers.items()):
                    if now < when:
                        continue
                    self._timers.pop(path, None)
                    if path.parent == watch_dir and path.exists():
                        self.move_file(path)
                time.sleep(1)

        self.observer = Observer()
        self.observer.schedule(handler, str(watch_dir), recursive=False)
        self.observer.start()
        self.running = True
        threading.Thread(target=sweep_loop, daemon=True).start()
        self.log(self.tr("started", watch_dir, self.config["dest_dir"]), "ok")
        self.state_callback()  # let GUI/tray refresh button + status pill

    def stop_watch(self):
        if self.observer:
            self.observer.stop()
            self.observer.join()
            self.running = False
            self.log(self.tr("stopped"), "info")
            self.state_callback()


class Pill(tk.Canvas):
    """Small rounded status badge: colored dot + uppercase state text."""

    def __init__(self, master, **kw):
        super().__init__(master, width=130, height=26, bg=CARD,
                         highlightthickness=0, **kw)
        self._text = ""
        self._color = MUTED

    def set_state(self, text: str, color: str):
        self._text, self._color = text.upper(), color
        self._redraw()

    def _redraw(self):
        self.delete("all")
        w, h = int(self["width"]), int(self["height"])
        r = h // 2
        # Rounded background (two ellipses + rectangle).
        self.create_oval(1, 1, 2 * r, h - 1, fill=self._color, outline="")
        self.create_oval(w - 2 * r, 1, w - 1, h - 1, fill=self._color, outline="")
        self.create_rectangle(r, 1, w - r, h - 1, fill=self._color, outline="")
        self.create_text(w // 2, h // 2, text=self._text, fill="#ffffff",
                         font=(FONT, 9, "bold"))


class GUI:
    """Tkinter window: language selector, folder pickers, start/stop, log, tray."""

    def __init__(self, root: tk.Tk, logic: AppLogic, start_hidden: bool = False):
        self.root = root
        self.logic = logic
        self.tray_icon = None       # pystray icon, created lazily
        self.exiting = False        # set True only via the real "Exit" action
        logic.gui_callback = self.append_log
        logic.state_callback = lambda: root.after(0, self.refresh_texts)

        self.entries = {}
        self.buttons_lang = {}

        self._build_theme(root)
        root.title(logic.tr("title"))
        root.geometry("560x520")
        root.resizable(False, False)
        root.configure(bg=BG)
        try:
            root.tk.call("tk", "scaling", 1.25)  # consistent paddings on HiDPI
        except Exception:
            pass

        # Window/taskbar icon: prefer app.ico (same artwork as the exe icon).
        for ico in (BASE_DIR / "app.ico", BASE_DIR / "app.png"):
            if ico.exists():
                try:
                    if ico.suffix == ".ico":
                        root.iconbitmap(str(ico))
                    else:
                        root.iconphoto(True, tk.PhotoImage(file=str(ico)))
                    break
                except Exception:
                    pass  # cosmetic only - never crash over an icon

        # ================= header card ================= #
        header = tk.Frame(root, bg=CARD)
        header.pack(fill="x", padx=16, pady=(16, 8))
        inner = tk.Frame(header, bg=CARD)
        inner.pack(fill="x", padx=16, pady=14)

        left = tk.Frame(inner, bg=CARD)
        left.pack(side="left", fill="x", expand=True)
        self.lbl_title = tk.Label(left, text="", font=(FONT, 15, "bold"),
                                  bg=CARD, fg=FG, anchor="w")
        self.lbl_title.pack(fill="x")
        self.lbl_subtitle = tk.Label(left, text="", font=(FONT, 9),
                                     bg=CARD, fg=MUTED, anchor="w")
        self.lbl_subtitle.pack(fill="x")

        self.pill = Pill(inner)
        self.pill.pack(side="right", padx=(10, 0))

        # Language segmented buttons (under the title inside the same card).
        lang_row = tk.Frame(header, bg=CARD)
        lang_row.pack(fill="x", padx=16, pady=(0, 12))
        for code in ("en", "ru", "zh"):
            b = tk.Button(lang_row, text=LANGUAGE_NAMES[code], bd=0, relief="flat",
                          activebackground=BORDER, cursor="hand2",
                          font=(FONT, 9, "bold"), width=9,
                          command=lambda c=code: self.on_language_change(c))
            b.pack(side="left", padx=(0, 6))
            self.buttons_lang[code] = b

        # ================= folders card ================= #
        card = tk.Frame(root, bg=CARD)
        card.pack(fill="x", padx=16, pady=8)
        cin = tk.Frame(card, bg=CARD)
        cin.pack(fill="x", padx=16, pady=14)

        lbl_sec = tk.Label(cin, text="", font=(FONT, 9, "bold"),
                           bg=CARD, fg=ACCENT, anchor="w")
        lbl_sec.grid(row=0, column=0, columnspan=3, sticky="w")
        self.lbl_section = lbl_sec

        def add_path_row(row, label_key, initial, command):
            lbl = tk.Label(cin, text="", font=(FONT, 10), bg=CARD, fg=FG,
                           anchor="w", width=16)
            lbl.grid(row=row + 1, column=0, sticky="w", pady=(10, 0))
            ent = tk.Entry(cin, font=(FONT, 10), bg=FIELD, fg=FG,
                           insertbackground=FG, relief="flat",
                           disabledbackground="#141821", disabledforeground=MUTED)
            ent.grid(row=row + 1, column=1, sticky="we", padx=8, pady=(10, 0), ipady=6)
            ent.insert(0, initial)
            btn = tk.Button(cin, text="\u22ef", width=3, bd=0, relief="flat",
                            bg=BORDER, fg=FG, activebackground=ACCENT,
                            activeforeground="#ffffff", cursor="hand2",
                            font=(FONT, 10, "bold"), command=command)
            btn.grid(row=row + 1, column=2, pady=(10, 0))
            # Hover effect for the browse button (same helper as other buttons).
            self._style_button(btn, BORDER, FG)
            return lbl, ent

        self.lbl_watch, self.entry_watch = add_path_row(
            0, "watch_label", logic.config["watch_dir"], self.browse_watch)
        self.lbl_dest, self.entry_dest = add_path_row(
            1, "dest_label", logic.config["dest_dir"], self.browse_dest)

        # Third row: delay before moving a finished download (seconds).
        self.lbl_grace = tk.Label(cin, text="", font=(FONT, 10), bg=CARD, fg=FG,
                                  anchor="w", width=16)
        self.lbl_grace.grid(row=3, column=0, sticky="w", pady=(10, 0))
        self.entry_grace = tk.Entry(cin, font=(FONT, 10), bg=FIELD, fg=FG,
                                    insertbackground=FG, relief="flat", width=8,
                                    disabledbackground="#141821", disabledforeground=MUTED)
        self.entry_grace.grid(row=3, column=1, sticky="w", padx=8, pady=(10, 0), ipady=6)
        self.entry_grace.insert(0, str(logic.config.get("grace_seconds", 300)))
        cin.columnconfigure(1, weight=1)

        # ================= big start/stop button ================= #
        self.btn_toggle = tk.Button(root, bd=0, relief="flat", cursor="hand2",
                                    font=(FONT, 12, "bold"), height=2,
                                    activeforeground="#ffffff",
                                    command=self.toggle)
        self.btn_toggle.pack(fill="x", padx=16, pady=(8, 4), ipady=4)

        # ================= log card ================= #
        logcard = tk.Frame(root, bg=CARD)
        logcard.pack(fill="both", expand=True, padx=16, pady=8)
        lin = tk.Frame(logcard, bg=CARD)
        lin.pack(fill="both", expand=True, padx=16, pady=12)

        self.lbl_log = tk.Label(lin, text="", font=(FONT, 9, "bold"),
                                bg=CARD, fg=ACCENT, anchor="w")
        self.lbl_log.pack(fill="x", pady=(0, 6))

        lframe = tk.Frame(lin, bg=FIELD)
        lframe.pack(fill="both", expand=True)
        self.txt_log = tk.Text(lframe, height=8, state="disabled", bd=0,
                               bg=FIELD, fg=FG, insertbackground=FG,
                               font=(FONT_MONO, 9), selectbackground=ACCENT,
                               padx=10, pady=8, wrap="word",
                               yscrollcommand=lambda *a: None)
        scroll = ttk.Scrollbar(lframe, command=self.txt_log.yview)
        self.txt_log.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.txt_log.pack(side="left", fill="both", expand=True)
        # Log line color tags.
        self.txt_log.tag_configure("info",  foreground=MUTED)
        self.txt_log.tag_configure("move",  foreground=GREEN)
        self.txt_log.tag_configure("ok",    foreground=ACCENT)
        self.txt_log.tag_configure("warn",  foreground=AMBER)
        self.txt_log.tag_configure("error", foreground=RED)

        # ================= options row ================= #
        opts = tk.Frame(root, bg=BG)
        opts.pack(fill="x", padx=20, pady=(0, 4))

        def make_check(key: str, command):
            var = tk.BooleanVar(value=bool(logic.config.get(key, False)))
            cb = tk.Checkbutton(opts, text="", variable=var, command=command,
                                bg=BG, fg=MUTED, selectcolor=FIELD,
                                activebackground=BG, activeforeground=FG,
                                font=(FONT, 9), anchor="w", bd=0,
                                highlightthickness=0, cursor="hand2")
            cb.pack(anchor="w", pady=1)
            return cb, var

        self.cb_tray, self.var_tray = make_check("minimize_to_tray", self.on_tray_option)
        self.cb_hidden, self.var_hidden = make_check("start_hidden", self.on_hidden_option)
        if TRAY_AVAILABLE:
            self.cb_autostart, self.var_autostart = make_check("autostart", self.on_autostart_option)
            self.var_autostart.set(is_autostart_enabled())  # trust the registry
        else:
            self.cb_autostart, self.var_autostart = None, None

        self.lbl_hint = tk.Label(root, text="", font=(FONT, 8, "italic"),
                                 bg=BG, fg=MUTED, anchor="w")
        self.lbl_hint.pack(fill="x", padx=20, pady=(0, 10))

        # --- window close behaviour & tray icon ----------------------------- #
        root.protocol("WM_DELETE_WINDOW", self.on_close)
        # Bind to the real widget destruction so paths are always flushed.
        root.bind("<Destroy>", self.on_destroy, add="+")
        self.refresh_texts()

        if start_hidden or logic.config.get("start_hidden", False):
            # Autostart mode: no window at all, sorting runs from the tray.
            self.hide_to_tray()
            if not logic.running:
                try:
                    logic.start_watch()
                except Exception as e:
                    messagebox.showerror(logic.tr("error"), str(e))
                    self.show_window()
        elif TRAY_AVAILABLE:
            self.ensure_tray_icon()  # icon appears right away for convenience

    # ------------------------------ theming -------------------------------- #
    def _build_theme(self, root):
        """Create the custom dark ttk theme + hover bindings helpers."""
        style = ttk.Style(root)
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure("Vertical.TScrollbar", background=CARD,
                        troughcolor=FIELD, bordercolor=FIELD, arrowcolor=MUTED,
                        relief="flat")
        style.map("Vertical.TScrollbar",
                  background=[("active", BORDER)])

    def _style_button(self, btn, bg_color, fg_color="#ffffff"):
        """Apply flat colors to a tk.Button (also stores hover shades)."""
        hover = self._shade(bg_color, 18)
        pressed = self._shade(bg_color, -18)
        btn.configure(bg=bg_color, fg=fg_color, activebackground=hover,
                      disabledforeground="#ffffff")
        btn.bind("<Enter>", lambda e: btn["state"] != "disabled" and
                 btn.configure(bg=hover))
        btn.bind("<Leave>", lambda e: btn.configure(bg=btn._base_bg))
        btn.bind("<ButtonPress>", lambda e: btn.configure(bg=pressed))
        btn.bind("<ButtonRelease>", lambda e: btn.configure(bg=btn._base_bg))
        btn._base_bg = bg_color

    @staticmethod
    def _shade(hex_color: str, amount: int) -> str:
        """Lighten (amount>0) or darken (amount<0) a hex color."""
        hex_color = hex_color.lstrip("#")
        rgb = [max(0, min(255, int(hex_color[i:i + 2], 16) + amount))
               for i in (0, 2, 4)]
        return "#{:02x}{:02x}{:02x}".format(*rgb)

    # ------------------------- language handling --------------------------- #
    def refresh_texts(self):
        """Re-render every label according to the current language/state."""
        tr = self.logic.tr
        self.root.title(tr("title"))
        self.lbl_title.config(text=tr("title"))
        self.lbl_subtitle.config(text=tr("subtitle"))
        self.lbl_section.config(text=tr("section_folders"))
        self.lbl_watch.config(text=tr("watch_label"))
        self.lbl_dest.config(text=tr("dest_label"))
        self.lbl_grace.config(text=tr("grace_label"))
        self.lbl_log.config(text=tr("log_header"))
        self.lbl_hint.config(text=tr("hint"))
        self.cb_tray.config(text=tr("opt_tray"))
        self.cb_hidden.config(text=tr("opt_hidden"))
        if self.cb_autostart is not None:
            self.cb_autostart.config(text=tr("opt_autostart"))

        running = self.logic.running
        # Status pill.
        self.pill.set_state(tr("status_running") if running else tr("status_paused"),
                            GREEN if running else MUTED)
        # Main toggle button.
        self._style_button(self.btn_toggle, RED_DK if running else GREEN_DK)
        self.btn_toggle.config(text=tr("btn_stop") if running else tr("btn_start"))
        # Language buttons: active one filled with accent, others muted.
        for code, btn in self.buttons_lang.items():
            if code == self.logic.lang:
                self._style_button(btn, ACCENT)
            else:
                self._style_button(btn, BORDER, FG)
        if self.tray_icon is not None:
            try:
                self.tray_icon.title = tr("title")
                self.tray_icon.icon = make_tray_image(running)
            except Exception:
                pass  # tray may be mid-shutdown; ignore cosmetic failures

    def on_language_change(self, code: str):
        self.logic.set_language(code)
        self.refresh_texts()

    # ----------------------------- callbacks ------------------------------- #
    def browse_watch(self):
        path = filedialog.askdirectory(initialdir=self.entry_watch.get() or str(Path.home()))
        if path:
            self.entry_watch.delete(0, tk.END)
            self.entry_watch.insert(0, path)
            # Save immediately so the choice survives closing the app.
            self.save_dirs()

    def browse_dest(self):
        path = filedialog.askdirectory(initialdir=self.entry_dest.get() or str(Path.home()))
        if path:
            self.entry_dest.delete(0, tk.END)
            self.entry_dest.insert(0, path)
            self.save_dirs()

    def append_log(self, message: str, kind: str = "info"):
        """Thread-safe log line insertion (worker threads call this)."""
        stamp = time.strftime("%H:%M:%S")
        def _append():
            self.txt_log.configure(state="normal")
            self.txt_log.insert(tk.END, f"[{stamp}] ", "info")
            self.txt_log.insert(tk.END, message + "\n", kind)
            self.txt_log.see(tk.END)
            self.txt_log.configure(state="disabled")
        self.root.after(0, _append)

    def toggle(self):
        if not self.logic.running:
            self.save_dirs()
            try:
                self.logic.start_watch()
            except Exception as e:
                messagebox.showerror(self.logic.tr("error"), str(e))
                return
            self.entry_watch.config(state="disabled")
            self.entry_dest.config(state="disabled")
            # The delay stays editable while running: save_dirs() pushes it
            # to config on Stop, and move_file() reads it live each time.
        else:
            # Stop first, then save (save_dirs rewrites the grace field).
            self.logic.stop_watch()
            self.save_dirs()
            self.entry_watch.config(state="normal")
            self.entry_dest.config(state="normal")

    def save_dirs(self):
        """Persist the two folder paths and the delay into config.json."""
        self.logic.config["watch_dir"] = self.entry_watch.get().strip()
        self.logic.config["dest_dir"] = self.entry_dest.get().strip()
        # Delay before moving: accept any number, clamp to 10..3600 seconds.
        try:
            grace = float(self.entry_grace.get().strip())
        except ValueError:
            grace = 300.0
        grace = min(max(grace, 10.0), 3600.0)
        self.logic.config["grace_seconds"] = int(grace)
        self.entry_grace.delete(0, tk.END)
        self.entry_grace.insert(0, str(int(grace)))
        self.logic.save_config()

    def on_destroy(self, event=None):
        """Last safety net: whenever the window is destroyed (Exit from tray,
        task-manager kill of Tk loop, etc.) write the current paths to disk."""
        try:
            self.save_dirs()
        except Exception:
            pass

    # --------------------------- option handlers --------------------------- #
    def on_tray_option(self):
        self.logic.config["minimize_to_tray"] = self.var_tray.get()
        self.logic.save_config()

    def on_hidden_option(self):
        self.logic.config["start_hidden"] = self.var_hidden.get()
        self.logic.save_config()

    def on_autostart_option(self):
        enable = self.var_autostart.get()
        self.save_dirs()  # keep folders saved before registering autostart
        if set_autostart(enable):
            self.logic.config["autostart"] = enable
            self.logic.save_config()
        else:
            self.var_autostart.set(is_autostart_enabled())
            messagebox.showwarning(self.logic.tr("error"),
                                   "Could not write the Windows autostart registry key.")

    # ------------------------------ tray logic ----------------------------- #
    def _refresh_tray_area(self):
        """Ask the taskbar to refresh the notification area (safe, no hacks).

        This is the officially supported trick: broadcasting TaskbarCreated
        makes explorer rebuild the tray, which drops "ghost" icons left by
        processes that died without cleaning up. It is read-only for other
        apps and cannot crash the shell.
        """
        if sys.platform != "win32":
            return
        try:
            import ctypes
            user32 = ctypes.windll.user32
            hwnd = user32.RegisterWindowMessageW("TaskbarCreated")
            if hwnd:
                # HWND_BROADCAST = 0xFFFF, WM_USER-less broadcast, no wait.
                user32.PostMessageW(0xFFFF, hwnd, 0, 0)
        except Exception:
            pass  # purely cosmetic - never break startup over it

    def ensure_tray_icon(self):
        """Create the pystray icon once (runs its own daemon thread).

        IMPORTANT (performance/stability): we must NEVER touch other
        processes' memory here. An earlier version enumerated the tray
        toolbar via ReadProcessMemory/WriteProcessMemory; SendMessage calls
        into the shell hung the UI thread and could even bring down
        explorer.exe. Now icon creation is a plain local operation and the
        only shell interaction is a single PostMessage broadcast.
        """
        if not TRAY_AVAILABLE or self.tray_icon is not None or self.exiting:
            return
        # Sweep visual ghosts left by previous crashed runs (non-blocking).
        self._refresh_tray_area()
        # NOTE: pystray evaluates the *text* of a menu item by calling it with
        # the MenuItem instance as argument (text(item)), while *visible* is
        # called the same way. Callbacks receive (icon, item). Lambdas below
        # must therefore accept those arguments explicitly.
        def _txt(key):
            return lambda _item=None: self.logic.tr(key)

        def _vis(running_value):
            return lambda _item=None: self.logic.running == running_value

        menu = pystray.Menu(
            pystray.MenuItem(_txt("tray_show"),
                             lambda icon, item: self.root.after(0, self.show_window),
                             default=True),
            pystray.MenuItem(_txt("tray_start"),
                             lambda icon, item: self.root.after(0, self.tray_start),
                             visible=_vis(False)),
            pystray.MenuItem(_txt("tray_stop"),
                             lambda icon, item: self.root.after(0, self.tray_stop),
                             visible=_vis(True)),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(_txt("tray_exit"),
                             lambda icon, item: self.root.after(0, self.exit_app)),
        )
        self.tray_icon = pystray.Icon(
            APP_NAME, make_tray_image(self.logic.running),
            self.logic.tr("title"), menu)
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def hide_to_tray(self):
        self.ensure_tray_icon()
        self.root.withdraw()

    def show_window(self):
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def tray_start(self):
        """Start sorting from the tray menu while the window is hidden."""
        if self.logic.running:
            return
        try:
            self.logic.start_watch()
        except Exception as e:
            self.show_window()
            messagebox.showerror(self.logic.tr("error"), str(e))

    def tray_stop(self):
        self.logic.stop_watch()

    def on_close(self):
        """Window 'X': minimize to tray (if enabled) instead of quitting."""
        if TRAY_AVAILABLE and self.logic.config.get("minimize_to_tray", True):
            self.hide_to_tray()
        else:
            self.exit_app()

    def exit_app(self):
        """Real shutdown: stop watching, remove tray icon, close Tk."""
        self.exiting = True
        if self.logic.running:
            self.logic.stop_watch()
        if self.tray_icon is not None:
            try:
                self.tray_icon.stop()
            except Exception:
                pass
            self.tray_icon = None
        self.root.destroy()


def main():
    # Guard against launching several copies (each copy adds its own tray icon).
    if not acquire_single_instance():
        # Another copy is already running: ask it to bring its window forward,
        # then exit silently (no second window, no second tray icon).
        raise_show_request()
        sys.exit(0)
    start_hidden = "--hidden" in sys.argv
    root = tk.Tk()
    logic = AppLogic()
    gui = GUI(root, logic, start_hidden=start_hidden)

    # A duplicate launch signals us through a named event + shared flag.
    # When the user simply double-clicks the .exe again, the flag is set and
    # we un-minimize; hidden autostart launches do not touch the flag.
    create_shared_flag()
    listener = ShowEventListener(
        lambda bring: root.after(0, gui.show_window) if bring else None)

    root.protocol("WM_DELETE_WINDOW", gui.on_close)  # ensure clean shutdown
    root.mainloop()
    listener.stop()


if __name__ == "__main__":
    main()
