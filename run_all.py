"""
Оркестратор pj17 для ежедневного запуска из Windows Task Scheduler в 21:00:05.

Порядок подобран так, чтобы .tri попал в QUIK максимально рано, а аналитика шла в хвосте:
  0) prepare.py (удаляет тестовые результаты, если запуск до 21:00)
  1) beget/sync_files.py
  2) rts/shared: download_minutes_to_db, convert_minutes_to_days, create_markdown_files
  3) rts/embedding: create_embedding, embedding_backtest, embedding_to_predict (пишет инвертир.)
  4) rts/sentiment: sentiment_analysis, sentiment_to_predict
  5) rts/combine_predictions.py (согласованное голосование)
  6) trade/trade_rts_tri_SPBFUT192yc_ebs.py  ← критично по времени
  7) Аналитика (soft-fail): embedding_analysis, sentiment_group_stats, sentiment_backtest,
     sentiment_compare (идёт последним).

Hard-fail (exit с кодом ошибки) до и включая trade-скрипт — чтобы при сбое на торговом этапе
сразу поднять алерт. После trade-скрипта ошибки — warning, пайплайн продолжается.

Регистрация в планировщике Windows:
  schtasks /Create /SC DAILY /ST 21:00:05 /TN "pj17_run_all" ^
      /TR "python C:\\Users\\Alkor\\VSCode\\pj17_combo_sentiment_embedding_trade\\run_all.py"
"""

from __future__ import annotations

import logging
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LOG_DIR = ROOT / "rts" / "log"
LOG_DIR.mkdir(parents=True, exist_ok=True)

timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
log_file = LOG_DIR / f"run_all_{timestamp}.txt"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(log_file, encoding="utf-8"),
        logging.StreamHandler(),
    ],
    force=True,
)
logger = logging.getLogger("run_all")

for old in sorted(LOG_DIR.glob("run_all_*.txt"))[:-3]:
    try:
        old.unlink()
    except Exception:
        pass


HARD_STEPS: list[Path] = [
    ROOT / "prepare.py",  # удаление тестовых файлов, если запуск до 21:00:00 (защита рабочих результатов)
    ROOT / "beget" / "sync_files.py",  # синхронизация файлов с удалённого сервера (включая .tri для QUIK)
    ROOT / "rts" / "shared" / "download_minutes_to_db.py",  # загрузка минутных данных в БД (для последующей обработки)
    ROOT / "rts" / "shared" / "convert_minutes_to_days.py",  # агрегация минутных данных в дневные (для обучения эмбеддингов)
    ROOT / "rts" / "shared" / "create_markdown_files.py",  # создание .md файлов с текстами для эмбеддингов и сентимента
    ROOT / "rts" / "embedding" / "create_embedding.py",  # обучение эмбеддингов и сохранение в БД
    ROOT / "rts" / "embedding" / "embedding_backtest.py",  # бэктест эмбеддингов на исторических данных
    ROOT / "rts" / "embedding" / "embedding_to_predict.py",  # преобразование эмбеддингов в предикты (инвертир. для удобства)
    ROOT / "rts" / "sentiment" / "sentiment_analysis.py",  # анализ сентимента с помощью LLM и сохранение в БД
    ROOT / "rts" / "sentiment" / "sentiment_to_predict.py",  # преобразование сентимента в предикты (без инвертирования, т.к. уже в нужной форме)
    ROOT / "rts" / "combine_predictions.py",  # согласованное голосование между эмбеддингами и сентиментом для получения финального сигнала
    ROOT / "trade" / "trade_rts_tri_SPBFUT192yc_ebs.py",  # торговый скрипт, который читает финальный сигнал и выставляет .tri в QUIK (критично по времени)
]

SOFT_STEPS: list[Path] = [
    ROOT / "rts" / "embedding" / "embedding_analysis.py",
    ROOT / "rts" / "sentiment" / "sentiment_group_stats.py",
    ROOT / "rts" / "sentiment" / "sentiment_backtest.py",
    ROOT / "rts" / "sentiment" / "sentiment_compare.py",  # последний
]


def run(script: Path, hard: bool) -> int:
    if not script.exists():
        msg = f"СКРИПТ НЕ НАЙДЕН: {script}"
        logger.error(msg)
        if hard:
            sys.exit(2)
        logger.warning(msg)
        return 2

    logger.info(f"▶ {'HARD' if hard else 'soft'}: {script.relative_to(ROOT)}")
    start = datetime.now()
    try:
        proc = subprocess.run(
            [sys.executable, str(script)],
            cwd=str(ROOT),
            check=False,
        )
        rc = proc.returncode
    except Exception as exc:
        logger.error(f"Исключение при запуске {script.name}: {exc}")
        if hard:
            sys.exit(3)
        return 3

    elapsed = (datetime.now() - start).total_seconds()
    if rc == 0:
        logger.info(f"✓ {script.name} — OK ({elapsed:.1f} сек)")
    else:
        if hard:
            logger.error(
                f"✗ {script.name} упал с кодом {rc} ({elapsed:.1f} сек). Останов пайплайна."
            )
            sys.exit(rc)
        logger.warning(
            f"⚠ {script.name} упал с кодом {rc} ({elapsed:.1f} сек). Продолжаем (soft-fail)."
        )
    return rc


def main() -> int:
    logger.info(f"=== pj17 run_all.py начат: {timestamp} ===")
    logger.info(f"Python: {sys.executable}")
    logger.info(f"ROOT: {ROOT}")

    for step in HARD_STEPS:
        run(step, hard=True)

    logger.info("--- Торговля завершена, переходим к аналитике (soft-fail) ---")

    for step in SOFT_STEPS:
        run(step, hard=False)

    logger.info("=== pj17 run_all.py завершён успешно ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
