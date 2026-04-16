"""
Объединяет прогнозы двух стратегий (embedding + sentiment) согласованным голосованием.

Для даты сегодня (date.today()) читает:
  <embedding.predict_path>/YYYY-MM-DD.txt
  <sentiment.predict_path>/YYYY-MM-DD.txt
Правило:
  up + up      → up
  down + down  → down
  любой конфликт или отсутствие одного из файлов → skip (файл не создаётся)
Результат пишется в <combined.predict_path>/YYYY-MM-DD.txt.
Оба исходных файла считаются уже «готовыми к исполнению» (инверсия применена при записи).
"""

from __future__ import annotations

import logging
import re
import sys
from datetime import date, datetime
from pathlib import Path

_PKG_ROOT = Path(__file__).resolve().parent
if str(_PKG_ROOT) not in sys.path:
    sys.path.insert(0, str(_PKG_ROOT))
from shared.config import load_settings


DIRECTION_RE = re.compile(r"Предсказанное направление:\s*(up|down|skip)", re.IGNORECASE)


def setup_logging() -> logging.Logger:
    log_dir = _PKG_ROOT / "log"
    log_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_file = log_dir / f"combine_predictions_{timestamp}.txt"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(),
        ],
        force=True,
    )
    for old in sorted(log_dir.glob("combine_predictions_*.txt"))[:-3]:
        try:
            old.unlink()
        except Exception:
            pass
    return logging.getLogger(__name__)


def read_direction(file_path: Path) -> str | None:
    if not file_path.exists():
        return None
    text = file_path.read_text(encoding="utf-8", errors="replace")
    match = DIRECTION_RE.search(text)
    if not match:
        return None
    return match.group(1).lower()


def main() -> int:
    logger = setup_logging()

    emb_settings = load_settings("embedding")
    sent_settings = load_settings("sentiment")
    combined_settings = load_settings("combined")

    today = date.today()
    date_str = today.strftime("%Y-%m-%d")

    emb_file = Path(emb_settings["predict_path"]) / f"{date_str}.txt"
    sent_file = Path(sent_settings["predict_path"]) / f"{date_str}.txt"
    combined_path = Path(combined_settings["predict_path"])
    out_file = combined_path / f"{date_str}.txt"

    if out_file.exists():
        logger.info(f"Файл {out_file} уже существует — пропуск.")
        return 0

    emb_dir = read_direction(emb_file)
    sent_dir = read_direction(sent_file)

    logger.info(f"embedding: {emb_dir} ({emb_file})")
    logger.info(f"sentiment: {sent_dir} ({sent_file})")

    if emb_dir in ("up", "down") and emb_dir == sent_dir:
        direction = emb_dir
    else:
        logger.info("Нет согласия или одного из прогнозов нет — skip, файл не создаётся.")
        return 0

    content = (
        f"Дата: {date_str}\n"
        f"Embedding: {emb_dir}\n"
        f"Sentiment: {sent_dir}\n"
        f"Предсказанное направление: {direction}\n"
    )

    combined_path.mkdir(parents=True, exist_ok=True)
    tmp_file = out_file.with_suffix(out_file.suffix + ".tmp")
    tmp_file.write_text(content, encoding="utf-8")
    tmp_file.replace(out_file)

    logger.info(f"Записан комбинированный прогноз: {out_file} (direction={direction})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
