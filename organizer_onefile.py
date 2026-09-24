#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Downloader Organizer (однофайловая версия) — авто-организатор папки «Загрузки».

Схема работы:
  1. Браузер продолжает скачивать файлы в C:\\Users\\user\\Downloads — ничего менять не надо.
  2. Программа следит за этой папкой "вживую" (watchdog), почти не нагружая CPU.
  3. Когда файл ДОКАЧАН (исчезло расширение .part/.crdownload или размер перестал
     меняться несколько секунд), он ПЕРЕМЕЩАЕТСЯ на D:\\Downloads в подпапку по типу файла
     (Документы, Картинки, Архивы, Установщики, Музыка, Видео, Код, Прочее).
  4. Все перемещения пишутся в журнал history.log рядом с этим файлом,
     есть команда отмены последнего перемещения:  --undo
     и проверка правил без перемещения:            --dry-run имя_файла

Настройки можно менять прямо в словаре CONFIG ниже (или создать рядом config.json —
тогда значения возьмутся из него).

Запуск:      python organizer_onefile.py
Остановка:   Ctrl+C
"""

import json
import logging
import os
import shutil
import sys
import time
from pathlib import Path

try:
    from watchdog.events import FileSystemEventHandler
    from watchdog.observers import Observer
except ImportError:
    sys.exit("Нужен модуль watchdog:  pip install watchdog")

BASE = Path(__file__).resolve().parent
CONFIG_FILE = BASE / "config.json"          # необязательный: если есть — переопределит CONFIG
HISTORY_FILE = BASE / "history.log"

# ============================ НАСТРОЙКИ =====================================
CONFIG = {
    # Откуда браузер скачивает файлы (наблюдаем за этой папкой)
    "watch_dir": r"C:\Users\user\Downloads",
    # Куда программа раскладывает докачанные файлы
    "dest_dir": r"D:\Downloads",
    # Сколько секунд размер файла не должен меняться, чтобы считать его докачанным
    "settle_seconds": 3,
    # Расширения, означающие "файл ещё качается" — их не трогаем
    "partial_extensions": [".part", ".crdownload", ".download", ".tmp"],
    # Правила: расширение -> подпапка внутри dest_dir. Неизвестное -> fallback_folder
    "rules": {
        ".pdf": "Документы", ".docx": "Документы", ".txt": "Документы",
        ".md": "Документы", ".rtf": "Документы",
        ".xlsx": "Таблицы", ".csv": "Таблицы",
        ".jpg": "Картинки", ".jpeg": "Картинки", ".png": "Картинки",
        ".gif": "Картинки", ".webp": "Картинки",
        ".mp3": "Музыка", ".flac": "Музыка", ".wav": "Музыка",
        ".mp4": "Видео", ".mkv": "Видео", ".avi": "Видео", ".mov": "Видео",
        ".zip": "Архивы", ".rar": "Архивы", ".7z": "Архивы",
        ".tar": "Архивы", ".gz": "Архивы",
        ".exe": "Установщики", ".msi": "Установщики", ".apk": "Установщики",
        ".py": "Код", ".js": "Код", ".html": "Код", ".json": "Код",
    },
    "fallback_folder": "Прочее",
}
# ===========================================================================

log = logging.getLogger("organizer")


def load_config() -> dict:
    cfg = dict(CONFIG)
    if CONFIG_FILE.exists():                      # необязательный внешний конфиг
        try:
            cfg.update(json.loads(CONFIG_FILE.read_text(encoding="utf-8")))
        except Exception as e:
            log.error("Не удалось прочитать %s: %s", CONFIG_FILE, e)
    cfg["watch_dir"] = str(Path(cfg["watch_dir"]).expanduser())
    cfg["dest_dir"] = str(Path(cfg["dest_dir"]).expanduser())
    return cfg


def unique_path(dst: Path) -> Path:
    """Если файл с таким именем уже есть — добавляем ' (1)', ' (2)' и т.д."""
    if not dst.exists():
        return dst
    stem, suffix = dst.stem, dst.suffix
    for i in range(1, 1000):
        cand = dst.with_name(f"{stem} ({i}){suffix}")
        if not cand.exists():
            return cand
    raise RuntimeError(f"Не удалось найти свободное имя для {dst}")


def classify(name: str, cfg: dict) -> str:
    ext = Path(name).suffix.lower()
    return cfg["rules"].get(ext, cfg["fallback_folder"])


def move_file(src: Path, cfg: dict) -> Path | None:
    folder = classify(src.name, cfg)
    dst_dir = Path(cfg["dest_dir"]) / folder
    dst_dir.mkdir(parents=True, exist_ok=True)
    dst = unique_path(dst_dir / src.name)
    shutil.move(str(src), str(dst))               # между дисками C: -> D: копирование + удаление
    with HISTORY_FILE.open("a", encoding="utf-8") as f:
        f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')}\t{src}\t->\t{dst}\n")
    log.info("✔ %s  →  %s\\%s", src.name, folder, dst.name)
    return dst


class DownloadWatcher(FileSystemEventHandler):
    """Копим файлы, у которых меняется размер, и переносим, когда они 'успокоятся'."""

    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.watch = Path(cfg["watch_dir"])
        self.pending: dict[Path, float] = {}      # файл -> время последней активности
        self.partial_ext = set(cfg["partial_extensions"])

    def _looks_partial(self, path: Path) -> bool:
        return path.suffix.lower() in self.partial_ext

    def on_created(self, event):
        if not event.is_directory:
            self._touch(Path(event.src_path))

    def on_modified(self, event):
        if not event.is_directory:
            self._touch(Path(event.src_path))

    def on_moved(self, event):
        # Браузер переименовал report.pdf.part -> report.pdf : файл готов
        if not event.is_directory:
            dest = Path(event.dest_path)
            if not self._looks_partial(dest) and dest.parent == self.watch:
                self.pending.pop(Path(event.src_path), None)
                self._finish(dest)

    def _touch(self, path: Path):
        if path.parent != self.watch or self._looks_partial(path):
            return
        self.pending[path] = time.time()

    def _finish(self, path: Path):
        if path.exists() and path.is_file():
            try:
                move_file(path, self.cfg)
            except PermissionError:
                log.warning("Файл %s занят другой программой — повторю позже", path.name)
                self.pending[path] = time.time() - self.cfg["settle_seconds"] + 1
            except Exception as e:                # не роняем программу из-за одного файла
                log.error("Не удалось перенести %s: %s", path.name, e)

    def sweep(self):
        """Раз в секунду проверяем: файлы, молчащие дольше settle_seconds, готовы к переносу."""
        now = time.time()
        for path, last in list(self.pending.items()):
            if not path.exists():
                self.pending.pop(path, None)
                continue
            if now - last >= self.cfg["settle_seconds"]:
                self.pending.pop(path, None)
                self._finish(path)


def undo_last():
    if not HISTORY_FILE.exists():
        print("Журнал пуст — отменять нечего.")
        return
    lines = HISTORY_FILE.read_text(encoding="utf-8").splitlines()
    last = lines[-1].split("\t")
    src, dst = Path(last[1]), Path(last[3])
    if dst.exists():
        shutil.move(str(dst), str(unique_path(src)))
        log.info("↩ Файл возвращён на место: %s", src)
    HISTORY_FILE.write_text("\n".join(lines[:-1]) + "\n", encoding="utf-8")


def main():
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    cfg = load_config()
    watch = Path(cfg["watch_dir"])

    if "--dry-run" in sys.argv:                   # проверка правил без перемещения
        sep = "\\" if os.name == "nt" else "/"     # разделитель под вашу ОС
        for name in sys.argv[sys.argv.index("--dry-run") + 1:]:
            print(f"{name:30s} → {cfg['dest_dir']}{sep}{classify(name, cfg)}")
        return
    if "--undo" in sys.argv:
        undo_last()
        return

    if not watch.exists():
        sys.exit(f"Папка {watch} не найдена. Проверьте путь в настройках CONFIG.")
    Path(cfg["dest_dir"]).mkdir(parents=True, exist_ok=True)

    log.info("Слежу за папкой:  %s", watch)
    log.info("Раскладываю в:    %s\\<категория>", cfg["dest_dir"])
    log.info("Остановка: Ctrl+C\n")

    watcher = DownloadWatcher(cfg)
    observer = Observer()
    observer.schedule(watcher, str(watch), recursive=False)
    observer.start()
    try:
        while True:
            watcher.sweep()
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        log.info("\nОстановлено.")
    observer.join()


if __name__ == "__main__":
    main()
