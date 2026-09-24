# 📥 Auto Downloader Organizer

**EN** · [RU](#русский)

A small Windows-friendly app that keeps your **Downloads folder clean automatically**.
Your browser keeps downloading to `Downloads` as usual — the app watches the folder,
waits until a file is fully downloaded (handles `.part` / `.crdownload` temp files),
and moves it into a category subfolder: Documents, Spreadsheets, Presentations,
Images, Music, Video, Archives, Installers, Code, Fonts, 3D, E-books, Other.

## ✨ Features

- 🖥️ Modern dark GUI (Tkinter) — pick folders with buttons, no config editing
- 🌍 Multilingual interface: English / Русский / 中文 (switched instantly, saved in config)
- 🗂️ 90+ file extensions mapped to categories; folder names are localized too
- 🕒 Waits for downloads to finish before moving (never breaks an active download)
- 🔁 Safe renaming on name collisions (`file (1).pdf`, `file (2).zip`, ...)
- 🧩 System tray mode: keep sorting with the window closed
- 🚀 Windows autostart (registry `HKCU\...\Run`, no admin rights required)
- 📝 Undo journal — every move is logged to `history.log`

## 🚀 Quick start

### Run from source (Python 3.10+)

```bash
pip install -r requirements.txt
python organizer_gui.py
```

### Run as a standalone .exe (no Python needed)

Download the latest `organizer.exe` from the
[Releases](../../releases) page, put it anywhere (e.g. `C:\Tools\Organizer\`)
and double-click. On first launch choose your folders and press **START**.

### Build the .exe yourself

```bash
pip install pyinstaller
python -m PyInstaller --onefile --noconsole organizer_gui.py
# result: dist/organizer.exe
```

## ⚙️ Configuration

The app creates `config.json` next to the script / executable:

```json
{
    "language": "ru",
    "watch_dir": "C:\\Users\\you\\Downloads",
    "dest_dir": "D:\\Downloads",
    "settle_seconds": 3,
    "minimize_to_tray": true,
    "start_hidden": false,
    "autostart": false
}
```

Most options are available right in the GUI. `settle_seconds` controls how long
the file size must stay unchanged before the app considers the download finished.

## 🛠️ How it works

1. `watchdog` listens to filesystem events in the watched folder (near-zero CPU).
2. Browser temp files (`.part`, `.crdownload`, `.download`, `.tmp`) are ignored.
3. A file is moved when either:
   - the browser renames `file.pdf.part → file.pdf` (Chrome/Firefox behaviour), or
   - its size stops changing for `settle_seconds` seconds.
4. The destination subfolder is chosen by extension; each move is appended to `history.log`.

## 📄 License

[MIT](LICENSE) — free to use, modify and distribute.

---

# Русский

Небольшое приложение для Windows, которое автоматически наводит порядок в папке
**«Загрузки»**. Браузер качает файлы как обычно, а программа ждёт окончания
загрузки и раскладывает их по подпапкам: Документы, Таблицы, Презентации,
Картинки, Музыка, Видео, Архивы, Установщики, Код, Шрифты, 3D, Книги, Прочее.

## Возможности

- Современный тёмный интерфейс — папки выбираются кнопками, лезть в код не нужно
- Язык интерфейса на выбор: English / Русский / 中文 (переключается мгновенно)
- 90+ расширений файлов, имена папок-категорий тоже переводятся
- Файл перемещается только после полной докачки (временные файлы браузера игнорируются)
- Защита от перезаписи: при конфликте имён добавляется `(1)`, `(2)`...
- Режим трея: сортировка продолжается при закрытом окне
- Автозапуск с Windows через реестр (права администратора не требуются)
- Журнал всех перемещений в `history.log`

## Установка и запуск

```bash
pip install -r requirements.txt
python organizer_gui.py
```

Сборка exe-файла:

```bash
pip install pyinstaller
python -m PyInstaller --onefile --noconsole organizer_gui.py
# готовый файл: dist/organizer.exe
```

## Лицензия

MIT — свободное использование и модификация.
