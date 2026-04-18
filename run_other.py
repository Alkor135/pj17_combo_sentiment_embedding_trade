"""
Оркестратор pj17 для анализа не основных тикеров
"""

from __future__ import annotations

import logging
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LOG_DIR = ROOT / "log"
LOG_DIR.mkdir(parents=True, exist_ok=True)

timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
log_file = LOG_DIR / f"run_other_{timestamp}.txt"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(log_file, encoding="utf-8"),
        logging.StreamHandler(),
    ],
    force=True,
)
logger = logging.getLogger("run_other")

for old in sorted(LOG_DIR.glob("run_other_*.txt"))[:-3]:
    try:
        old.unlink()
    except Exception:
        pass


HARD_STEPS: list[Path] = [
    # Этап 1: загрузка минутных котировок в БД (у каждого тикера своя БД)
    ROOT / "br" / "shared" / "download_minutes_to_db.py",
    ROOT / "ng" / "shared" / "download_minutes_to_db.py",
    ROOT / "si" / "shared" / "download_minutes_to_db.py",
    ROOT / "gold" / "shared" / "download_minutes_to_db.py",
    ROOT / "spyf" / "shared" / "download_minutes_to_db.py",

    # Этап 2: агрегация минут → дневные свечи
    ROOT / "br" / "shared" / "convert_minutes_to_days.py",
    ROOT / "ng" / "shared" / "convert_minutes_to_days.py",
    ROOT / "si" / "shared" / "convert_minutes_to_days.py",
    ROOT / "gold" / "shared" / "convert_minutes_to_days.py",
    ROOT / "spyf" / "shared" / "convert_minutes_to_days.py",

    # Этап 4: эмбеддинги (тяжёлый — Ollama)
    ROOT / "br" / "embedding" / "create_embedding.py",
    ROOT / "ng" / "embedding" / "create_embedding.py",
    ROOT / "si" / "embedding" / "create_embedding.py",
    ROOT / "gold" / "embedding" / "create_embedding.py",
    ROOT / "spyf" / "embedding" / "create_embedding.py",

    # Этап 5: бэктест эмбеддингов + выбор лучшего k
    ROOT / "br" / "embedding" / "embedding_backtest.py",
    ROOT / "ng" / "embedding" / "embedding_backtest.py",
    ROOT / "si" / "embedding" / "embedding_backtest.py",
    ROOT / "gold" / "embedding" / "embedding_backtest.py",
    ROOT / "spyf" / "embedding" / "embedding_backtest.py",

    # Этап 7: sentiment-анализ через LLM (тяжёлый — Ollama)
    ROOT / "br" / "sentiment" / "sentiment_analysis.py",
    ROOT / "ng" / "sentiment" / "sentiment_analysis.py",
    ROOT / "si" / "sentiment" / "sentiment_analysis.py",
    ROOT / "gold" / "sentiment" / "sentiment_analysis.py",
    ROOT / "spyf" / "sentiment" / "sentiment_analysis.py",
]

SOFT_STEPS: list[Path] = [
    ROOT / "br" / "embedding" / "embedding_analysis.py",
    ROOT / "ng" / "embedding" / "embedding_analysis.py",
    ROOT / "si" / "embedding" / "embedding_analysis.py",
    ROOT / "gold" / "embedding" / "embedding_analysis.py",
    ROOT / "spyf" / "embedding" / "embedding_analysis.py",

    ROOT / "br" / "sentiment" / "sentiment_group_stats.py",
    ROOT / "ng" / "sentiment" / "sentiment_group_stats.py",
    ROOT / "si" / "sentiment" / "sentiment_group_stats.py",
    ROOT / "gold" / "sentiment" / "sentiment_group_stats.py",
    ROOT / "spyf" / "sentiment" / "sentiment_group_stats.py",

    ROOT / "br" / "sentiment" / "sentiment_backtest.py",
    ROOT / "ng" / "sentiment" / "sentiment_backtest.py",
    ROOT / "si" / "sentiment" / "sentiment_backtest.py",
    ROOT / "gold" / "sentiment" / "sentiment_backtest.py",
    ROOT / "spyf" / "sentiment" / "sentiment_backtest.py",

    ROOT / "br" / "sentiment" / "sentiment_compare.py",
    ROOT / "ng" / "sentiment" / "sentiment_compare.py",
    ROOT / "si" / "sentiment" / "sentiment_compare.py",
    ROOT / "gold" / "sentiment" / "sentiment_compare.py",
    ROOT / "spyf" / "sentiment" / "sentiment_compare.py",  # последний
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

    logger.info("=== pj17 run_other.py завершён успешно ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
