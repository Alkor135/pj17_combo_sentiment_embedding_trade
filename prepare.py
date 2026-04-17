"""
Подготовка к тестовому запуску пайплайна.

Удаляет результаты тестовых запусков, произошедших до 21:00:00 текущего дня:
  - Файлы предсказаний за сегодня (embedding, sentiment, combined)
  - Done-маркеры за сегодня (защита от повторной записи)

Если скрипт запущен после 21:00:00 — ничего не удаляет, чтобы защитить
рабочие результаты, созданные в официальное время запуска (21:00:05).

Логика:
  Текущее время < 21:00:00 → удалить файлы за сегодня
  Текущее время >= 21:00:00 → ничего не трогать

Используется в начале run_all.py как первый шаг (перед основным пайплайном).
"""

import logging
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LOG_DIR = ROOT / "rts" / "log"
LOG_DIR.mkdir(parents=True, exist_ok=True)

timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
log_file = LOG_DIR / f"prepare_{timestamp}.txt"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(log_file, encoding="utf-8"),
        logging.StreamHandler(),
    ],
    force=True,
)
logger = logging.getLogger("prepare")


def main() -> int:
    now = datetime.now()
    today_str = now.strftime("%Y-%m-%d")
    hour = now.hour
    minute = now.minute

    logger.info(f"=== prepare.py начат: {timestamp} ===")
    logger.info(f"Текущее время: {hour:02d}:{minute:02d}, дата: {today_str}")

    # Порог: 21:00:00 (21 час, начиная с минуты 0)
    cutoff_hour = 21
    is_before_cutoff = hour < cutoff_hour

    if not is_before_cutoff:
        logger.info(
            f"Текущее время >= 21:00:00 — это рабочее время. "
            f"Тестовые файлы не удаляются, защита рабочих результатов.\n"
        )
        return 0

    logger.info(f"Текущее время < 21:00:00 — дневное тестирование. Удаляем результаты за {today_str}...")

    # Пути для удаления
    files_to_delete = [
        ROOT / "rts" / "combined" / f"{today_str}.txt",
        Path("C:/Users/Alkor/gd/predict_ai/rts_embedding") / f"{today_str}.txt",
        Path("C:/Users/Alkor/gd/predict_ai/rts_sentiment") / f"{today_str}.txt",
        Path("C:/Users/Alkor/gd/predict_ai/rts_combined") / f"{today_str}.txt",
    ]

    done_markers = [
        ROOT / "trade" / "state" / f"rts_SPBFUT192yc_{today_str}.done",
        ROOT / "trade" / "state" / f"rts_SPBFUT16qg3_{today_str}.done",
    ]

    all_files = files_to_delete + done_markers

    deleted_count = 0
    for filepath in all_files:
        if filepath.exists():
            try:
                filepath.unlink()
                logger.info(f"  Удалён: {filepath}")
                deleted_count += 1
            except Exception as exc:
                logger.warning(f"  Не удалось удалить {filepath}: {exc}")

    # Очистка старых логов prepare (оставляем только 3 самых новых)
    for old in sorted(LOG_DIR.glob("prepare_*.txt"))[:-3]:
        try:
            old.unlink()
        except Exception:
            pass

    logger.info(f"\nУдалено файлов: {deleted_count}")
    logger.info("=== prepare.py завершён успешно ===\n")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
