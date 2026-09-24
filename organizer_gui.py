#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Auto Downloader Organizer - GUI version (single file).

Features
--------
* Watches the browser Downloads folder and moves finished files into
  category subfolders (documents, tables, presentations, images, ...).
* Graphical interface: start/stop button, folder pickers, live event log.
* User-selectable UI language: English / Русский / 中文 (dropdown in the
  window). The choice is persisted in config.json; on first run it is
  auto-detected from the system locale.
* All source comments are written in English.

Run:      python organizer_gui.py
Build:    python -m PyInstaller --onefile --noconsole organizer_gui.py
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
# Translations. Every user-visible string lives here so the whole interface
# (including the generated category folder names) can be re-rendered at once.
# --------------------------------------------------------------------------- #
TRANSLATIONS = {
    "en": {
        "title": "Auto Downloader Organizer",
        "language_label": "Language:",
        "watch_label": "Downloads folder:",
        "dest_label": "Organize into:",
        "btn_start": "\u25b6 START",
        "btn_stop": "\u25a0 STOP",
        "log_header": "Event log:",
        "error": "Error",
        "folder_not_found": "Folder not found:\n{}",
        "started": "Sorting started: {} -> {}",
        "stopped": "Sorting stopped.",
        "moving": "Moved: {}  ->  {}/{}",
        "skipped": "Skipped (still downloading): {}",
        "error_move": "Could not move {}: {}",
        "busy": "File is busy, will retry: {}",
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
        "language_label": "Язык:",
        "watch_label": "Папка загрузок:",
        "dest_label": "Раскладывать в:",
        "btn_start": "\u25b6 ЗАПУСТИТЬ",
        "btn_stop": "\u25a0 ОСТАНОВИТЬ",
        "log_header": "Журнал событий:",
        "error": "Ошибка",
        "folder_not_found": "Папка не найдена:\n{}",
        "started": "Сортировка запущена: {} -> {}",
        "stopped": "Сортировка остановлена.",
        "moving": "Перемещён: {}  ->  {}/{}",
        "skipped": "Пропуск (ещё качается): {}",
        "error_move": "Не удалось переместить {}: {}",
        "busy": "Файл занят, повторю позже: {}",
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
        "language_label": "语言：",
        "watch_label": "下载文件夹：",
        "dest_label": "整理到：",
        "btn_start": "\u25b6 开始",
        "btn_stop": "\u25a0 停止",
        "log_header": "事件日志：",
        "error": "错误",
        "folder_not_found": "找不到文件夹：\n{}",
        "started": "整理已启动：{} -> {}",
        "stopped": "整理已停止。",
        "moving": "已移动：{}  ->  {}/{}",
        "skipped": "跳过（仍在下载）：{}",
        "error_move": "无法移动 {}：{}",
        "busy": "文件被占用，稍后重试：{}",
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


class AppLogic:
    """All non-GUI behaviour: configuration, classification, moving, watching."""

    def __init__(self):
        self.config = self.load_config()
        self.observer = None
        self.running = False
        self._handler = None  # set by start_watch(); used for retry scheduling
        self.lang = self.config.get("language") or detect_system_language()
        if self.lang not in TRANSLATIONS:
            self.lang = "en"
        # gui_callback receives a translated message string; set by the GUI layer.
        self.gui_callback = lambda msg: None

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

    def log(self, message: str):
        """Send a message to the GUI log (safe when there is no console)."""
        try:
            self.gui_callback(message)
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
            self.log(self.tr("moving", src.name, folder, dst.name))
            with LOG_FILE.open("a", encoding="utf-8") as f:
                f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')}\t{src}\t->\t{dst}\n")
        except PermissionError:
            # File is locked (browser/antivirus) - retry a bit later.
            self.log(self.tr("busy", src.name))
            if self._handler is not None:
                self._handler.pending[src] = time.time() - self.config["settle_seconds"] + 1
        except Exception as e:
            self.log(self.tr("error_move", src.name, e))

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
                    logic.log(logic.tr("skipped", path.name))
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
        self.log(self.tr("started", watch_dir, self.config["dest_dir"]))

    def stop_watch(self):
        if self.observer:
            self.observer.stop()
            self.observer.join()
            self.running = False
            self.log(self.tr("stopped"))


class GUI:
    """Tkinter window: language dropdown, folder pickers, start/stop, log."""

    def __init__(self, root: tk.Tk, logic: AppLogic):
        self.root = root
        self.logic = logic
        logic.gui_callback = self.append_log

        self.var_lang = tk.StringVar(value=LANGUAGE_NAMES[logic.lang])
        self.entries = {}
        self.labels = {}

        root.geometry("520x420")
        root.resizable(False, False)

        # --- top row: language selector ----------------------------------- #
        bar = tk.Frame(root)
        bar.pack(fill="x", padx=20, pady=(12, 0))
        self.lbl_lang = tk.Label(bar, text="")
        self.lbl_lang.pack(side="left")
        options = [LANGUAGE_NAMES[k] for k in ("en", "ru", "zh")]
        self.combo_lang = ttk.Combobox(bar, values=options, state="readonly", width=12)
        self.combo_lang.set(self.var_lang.get())
        self.combo_lang.pack(side="right")
        self.combo_lang.bind("<<ComboboxSelected>>", self.on_language_change)

        # --- folder pickers ------------------------------------------------ #
        frame_paths = tk.Frame(root)
        frame_paths.pack(fill="x", padx=20, pady=10)

        self.lbl_watch = tk.Label(frame_paths, text="")
        self.lbl_watch.grid(row=0, column=0, sticky="w")
        self.entry_watch = tk.Entry(frame_paths, width=38)
        self.entry_watch.grid(row=0, column=1, padx=5)
        self.entry_watch.insert(0, logic.config["watch_dir"])
        tk.Button(frame_paths, text="...", width=3,
                  command=self.browse_watch).grid(row=0, column=2)

        self.lbl_dest = tk.Label(frame_paths, text="")
        self.lbl_dest.grid(row=1, column=0, sticky="w", pady=5)
        self.entry_dest = tk.Entry(frame_paths, width=38)
        self.entry_dest.grid(row=1, column=1, padx=5)
        self.entry_dest.insert(0, logic.config["dest_dir"])
        tk.Button(frame_paths, text="...", width=3,
                  command=self.browse_dest).grid(row=1, column=2)

        # --- start / stop button ------------------------------------------ #
        self.btn_toggle = tk.Button(root, font=("Arial", 12, "bold"),
                                    height=2, width=22, command=self.toggle)
        self.btn_toggle.pack(pady=12)

        # --- event log ----------------------------------------------------- #
        txt_frame = tk.Frame(root)
        txt_frame.pack(fill="both", expand=True, padx=20, pady=(0, 15))
        self.lbl_log = tk.Label(txt_frame, anchor="w")
        self.lbl_log.pack(fill="x")
        self.txt_log = tk.Text(txt_frame, height=9, state="disabled",
                               bg="#f0f0f0", font=("Consolas", 9))
        scrollbar = tk.Scrollbar(txt_frame, command=self.txt_log.yview)
        self.txt_log.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.txt_log.pack(side="left", fill="both", expand=True)

        self.refresh_texts()

    # ------------------------- language handling --------------------------- #
    def refresh_texts(self):
        """Re-render every label according to the current language."""
        tr = self.logic.tr
        self.root.title(tr("title"))
        self.lbl_lang.config(text=tr("language_label"))
        self.lbl_watch.config(text=tr("watch_label"))
        self.lbl_dest.config(text=tr("dest_label"))
        self.lbl_log.config(text=tr("log_header"))
        self.btn_toggle.config(
            text=self.logic.tr("btn_stop") if self.logic.running
            else self.logic.tr("btn_start")
        )

    def on_language_change(self, _event=None):
        chosen = next(k for k, v in LANGUAGE_NAMES.items()
                      if v == self.combo_lang.get())
        self.logic.set_language(chosen)
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

    def append_log(self, message: str):
        """Thread-safe log line insertion (worker threads call this)."""
        def _append():
            self.txt_log.configure(state="normal")
            self.txt_log.insert(tk.END, message + "\n")
            self.txt_log.see(tk.END)
            self.txt_log.configure(state="disabled")
        self.root.after(0, _append)

    def toggle(self):
        if not self.logic.running:
            self.logic.config["watch_dir"] = self.entry_watch.get().strip()
            self.logic.config["dest_dir"] = self.entry_dest.get().strip()
            self.logic.save_config()
            try:
                self.logic.start_watch()
            except Exception as e:
                messagebox.showerror(self.logic.tr("error"), str(e))
                return
            self.btn_toggle.config(text=self.logic.tr("btn_stop"), bg="#f44336")
            self.entry_watch.config(state="disabled")
            self.entry_dest.config(state="disabled")
        else:
            self.logic.stop_watch()
            self.btn_toggle.config(text=self.logic.tr("btn_start"), bg="#4CAF50")
            self.entry_watch.config(state="normal")
            self.entry_dest.config(state="normal")


def main():
    root = tk.Tk()
    logic = AppLogic()
    GUI(root, logic)

    def on_closing():
        if logic.running:
            logic.stop_watch()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()


if __name__ == "__main__":
    main()
