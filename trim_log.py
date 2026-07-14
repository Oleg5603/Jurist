"""Обрезка разросшихся лог-файлов (cloudflared.log, ngrok.log, server.log).

ВАЖНО: пока процесс (cloudflared.exe/ngrok.exe/python.exe) держит лог-файл
открытым на запись, Windows не даёт ни переименовать, ни truncate'нуть файл
у него из-под ног (в отличие от Linux, где это штатно работает). Поэтому
этот скрипт — не автоматическая логротация в фоне, а ручная утилита:

    1. Останови процесс, который пишет в лог (или просто дождись, когда
       туннель/сервер перезапускается по другой причине).
    2. Запусти: python trim_log.py cloudflared.log
       (или без аргумента — обработает cloudflared.log, ngrok.log, server.log,
       если они существуют).
    3. Если файл больше порога (по умолчанию 5 МБ) — старое содержимое
       уезжает в cloudflared.log.old (перезаписывая предыдущий .old),
       и создаётся пустой файл с тем же именем для новых записей процесса
       после его перезапуска.

Ни cloudflared, ни ngrok на Windows не поддерживают встроенную ротацию логов
по размеру "из коробки" (это настройки вне этого репозитория — на стороне
самих бинарников/их обёртки-лаунчера). Если лог продолжает расти между
перезапусками, самый простой вариант — не писать лог в файл вовсе (убрать
`> cloudflared.log` при запуске) или направлять его через внешний ротатор
(например `logrotate`-подобный инструмент под Windows), что уже выходит за
рамки этого приложения.
"""

import sys
from pathlib import Path

THRESHOLD_BYTES = 5 * 1024 * 1024  # 5 МБ
DEFAULT_FILES = ["cloudflared.log", "ngrok.log", "server.log"]


def trim(path: Path) -> None:
    if not path.exists():
        print(f"{path.name}: не найден, пропуск.")
        return
    size = path.stat().st_size
    if size <= THRESHOLD_BYTES:
        print(f"{path.name}: {size} байт, ниже порога, не трогаю.")
        return
    old_path = path.with_suffix(path.suffix + ".old")
    try:
        if old_path.exists():
            old_path.unlink()
        path.rename(old_path)
        path.touch()
        print(f"{path.name}: было {size} байт, старое содержимое -> {old_path.name}, создан пустой файл.")
    except PermissionError:
        print(
            f"{path.name}: файл занят другим процессом (лог активно пишется) — "
            "останови процесс, который его пишет, и повтори."
        )


def main() -> None:
    targets = sys.argv[1:] or DEFAULT_FILES
    base = Path(__file__).parent
    for name in targets:
        trim(base / name)


if __name__ == "__main__":
    main()
