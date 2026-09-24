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
        "hint": "Tip: closing the window minimizes it to the tray and keeps sorting.",
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
        "hint": "Подсказка: закрытие окна сворачивает его в трей — сортировка продолжается.",
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
        "hint": "提示：关闭窗口会最小化到托盘，整理继续进行。",
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


def make_tray_image(running: bool):
    """Draw a simple 64x64 icon: green circle = sorting on, gray = paused."""
    color = (46, 204, 113, 255) if running else (139, 147, 167, 255)
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((2, 2, 62, 62), radius=14, fill=(30, 34, 45, 255))
    d.ellipse((12, 12, 52, 52), fill=color)
    # White down-arrow symbolizing "downloads sorted into folders".
    d.polygon([(32, 44), (20, 26), (44, 26)], fill=(255, 255, 255, 255))
    return img


class AppLogic:
    """All non-GUI behaviour: configuration, classification, moving, watching."""

    def __init__(self):
        self.config = self.load_config()
        self.observer = None
        self.running = False
        self._handler = None  # set by start_watch(); used for retry scheduling
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

    # ------------------------------ file moving ---------------------------- #
    def move_file(self, src_path: Path):
        src = Path(src_path)
        if not src.exists() or not src.is_file():
            return
        folder = self.category_for(src.name)
        dst_dir = Path(self.config["dest_dir"]) / folder
        dst_dir.mkdir(parents=True, exist_ok=True)
        dst = self.unique_path(dst_dir / src.name)
        try:
            shutil.move(str(src), str(dst))
            self.log(self.tr("moving", src.name, folder, dst.name), "move")
            with LOG_FILE.open("a", encoding="utf-8") as f:
                f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')}\t{src}\t->\t{dst}\n")
        except PermissionError:
            # File is locked (browser/antivirus) - retry a bit later.
            self.log(self.tr("busy", src.name), "warn")
            if self._handler is not None:
                self._handler.pending[src] = time.time() - self.config["settle_seconds"] + 1
        except Exception as e:
            self.log(self.tr("error_move", src.name, e), "error")

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
                for path, last in list(handler.pending.items()):
                    if not path.exists():
                        handler.pending.pop(path, None)
                        continue
                    if now - last >= float(self.config["settle_seconds"]):
                        handler.pending.pop(path, None)
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

        def add_path_row(row, label_key, initial):
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
                            font=(FONT, 10, "bold"))
            btn.grid(row=row + 1, column=2, pady=(10, 0))
            return lbl, ent

        self.lbl_watch, self.entry_watch = add_path_row(0, "watch_label",
                                                        logic.config["watch_dir"])
        self.lbl_dest, self.entry_dest = add_path_row(1, "dest_label",
                                                      logic.config["dest_dir"])
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

    def browse_dest(self):
        path = filedialog.askdirectory(initialdir=self.entry_dest.get() or str(Path.home()))
        if path:
            self.entry_dest.delete(0, tk.END)
            self.entry_dest.insert(0, path)

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
        else:
            self.logic.stop_watch()
            self.entry_watch.config(state="normal")
            self.entry_dest.config(state="normal")

    def save_dirs(self):
        """Persist the two folder paths into config.json."""
        self.logic.config["watch_dir"] = self.entry_watch.get().strip()
        self.logic.config["dest_dir"] = self.entry_dest.get().strip()
        self.logic.save_config()

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
    def ensure_tray_icon(self):
        """Create the pystray icon once (runs its own daemon thread)."""
        if not TRAY_AVAILABLE or self.tray_icon is not None:
            return
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
    start_hidden = "--hidden" in sys.argv
    root = tk.Tk()
    logic = AppLogic()
    GUI(root, logic, start_hidden=start_hidden)
    root.mainloop()


if __name__ == "__main__":
    main()
