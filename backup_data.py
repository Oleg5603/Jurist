"""Простой бэкап data/ (JSON-хранилище чатов/документов/договоров).

Использование:
    python backup_data.py

Складывает zip-архив текущего содержимого data/ в backups/data-YYYYMMDD-HHMMSS.zip
и хранит только последние KEEP_LAST архивов (старые удаляет).

Как запускать регулярно (hobby-scale, без демонов/cron-зависимостей):
    - Вручную перед важными изменениями/экспериментами.
    - Или через Планировщик заданий Windows: создать задачу, которая раз в
      день запускает `python C:\\Users\\HP\\Jurist\\backup_data.py`
      (Task Scheduler -> Create Basic Task -> Trigger: Daily ->
      Action: Start a program -> Program: python.exe ->
      Arguments: C:\\Users\\HP\\Jurist\\backup_data.py ->
      Start in: C:\\Users\\HP\\Jurist).

backups/ не в git (см. .gitignore) — это рантайм-данные, не код.
"""

import shutil
import time
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
BACKUPS_DIR = Path(__file__).parent / "backups"
KEEP_LAST = 14  # хранить последние N архивов


def main() -> None:
    if not DATA_DIR.exists():
        print(f"data/ не найдена ({DATA_DIR}), нечего бэкапить.")
        return

    BACKUPS_DIR.mkdir(exist_ok=True)
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    archive_base = BACKUPS_DIR / f"data-{timestamp}"
    archive_path = shutil.make_archive(str(archive_base), "zip", root_dir=str(DATA_DIR))
    print(f"Бэкап создан: {archive_path}")

    existing = sorted(BACKUPS_DIR.glob("data-*.zip"), key=lambda p: p.stat().st_mtime)
    stale = existing[:-KEEP_LAST] if len(existing) > KEEP_LAST else []
    for old in stale:
        old.unlink()
        print(f"Удалён старый бэкап: {old.name}")


if __name__ == "__main__":
    main()
