# Downloader Organizer

Авто-организатор папки «Загрузки»: браузер качает файлы как обычно, а программа
сама раскладывает докачанные файлы по подпапкам (Документы, Картинки, Архивы...).

## 1. Установка (нужен Python 3.10+)
```bash
python3 -m pip install -r requirements.txt      # или: pip install watchdog
```

## 2. Настройка
При первом запуске рядом со скриптом создаётся `config.json`:
```json
{
  "downloads_dir": "~/Downloads",
  "settle_seconds": 3,
  "partial_extensions": [".part", ".crdownload", ".download", ".tmp"],
  "rules": { ".pdf": "Документы", ".jpg": "Картинки", ".zip": "Архивы" },
  "fallback_folder": "Прочее"
}
```
Путь на Windows можно задать прямо в конфиге: `"downloads_dir": "C:/Users/Вася/Downloads"`.

## 3. Запуск
```bash
python3 downloader_organizer.py            # режим слежения (остановка Ctrl+C)
python3 downloader_organizer.py --dry-run report.pdf photo.png   # показать, куда попадёт файл
python3 downloader_organizer.py --undo     # вернуть последний перемещённый файл обратно
```

### Фоновый запуск
Linux/macOS: `nohup python3 downloader_organizer.py > organizer.log 2>&1 &`
Windows (без чёрного окна): `pythonw downloader_organizer.py`

### Автозапуск при входе в систему
- **Windows:** `Win+R` → `shell:startup` → создать ярлык командой:
  `schtasks /create /tn "DownloaderOrganizer" /tr "pythonw C:\path\downloader_organizer.py" /sc onlogon`
- **Linux:** `~/.config/autostart/downloader-organizer.desktop` с `Exec=python3 /path/downloader_organizer.py`
- **macOS:** `launchctl load ~/Library/LaunchAgents/com.user.downloader.plist`

## 4. Как это работает
1. `watchdog` слушает события файловой системы (не грузит CPU опросами).
2. Файлы с `.part`/`.crdownload` игнорируются — они ещё качаются.
3. Файл переносится, когда браузер переименовал его из `*.part` в нормальное имя
   **или** когда его размер не меняется дольше `settle_seconds`.
4. Конфликты имён решаются как в браузере: `report (1).pdf`, `report (2).pdf`.
5. Каждое перемещение пишется в `history.log` — отсюда работает `--undo`.

## 5. Сборка в .exe (по желанию)
```bash
pip install pyinstaller
pyinstaller --onefile --noconsole downloader_organizer.py   # dist/downloader_organizer.exe
```

## Ограничения текущей версии
- Нет иконки в системном трее (только консоль/лог) — добавляется библиотекой `pystray`.
- Не следит за вложенными подпапками (`recursive=False`).
- Классификация только по расширению; сортировка фото по EXIF-дате — в планах.
