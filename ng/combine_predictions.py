"""
Объединяет прогнозы двух стратегий (embedding + sentiment) согласованным голосованием.

Для даты сегодня (date.today()) читает:
  <embedding.predict_path>/YYYY-MM-DD.txt
  <sentiment.predict_path>/YYYY-MM-DD.txt
Правило:
  up + up      → up
  down + down  → down
  любой конфликт, skip или отсутствие одного из файлов → skip
Результат пишется в <combined.predict_path>/YYYY-MM-DD.txt ВСЕГДА — с разбивкой
по источникам, чтобы легко контролировать вручную. Формат:
  Дата: YYYY-MM-DD
  Embedding: <up|down|skip|n/a>
  Sentiment: <up|down|skip|n/a>
  Предсказанное направление: <up|down|skip>
Оба исходных файла считаются уже «готовыми к исполнению» (инверсия применена при записи).
Если файл за сегодня уже есть и создан после time_start — пропуск;
если создан до time_start (тестовый прогон) — перезаписывается.
"""

from __future__ import annotations

import logging
import re
from datetime import date, datetime
from pathlib import Path

import yaml

TICKER_DIR = Path(__file__).resolve().parent


def load_settings_section(section: str) -> dict:
    """Читает TICKER_DIR/settings.yaml, мержит common + секцию, подставляет {ticker}/{ticker_lc}."""
    raw = yaml.safe_load((TICKER_DIR / "settings.yaml").read_text(encoding="utf-8"))
    merged = {**(raw.get("common") or {}), **(raw.get(section) or {})}
    t = merged.get("ticker", "")
    tl = merged.get("ticker_lc", t.lower())
    return {
        k: (v.replace("{ticker}", t).replace("{ticker_lc}", tl) if isinstance(v, str) else v)
        for k, v in merged.items()
    }


DIRECTION_RE = re.compile(r"Предсказанное направление:\s*(up|down|skip)", re.IGNORECASE)


def setup_logging() -> logging.Logger:
    log_dir = TICKER_DIR / "log"
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

    emb_settings = load_settings_section("embedding")
    sent_settings = load_settings_section("sentiment")
    combined_settings = load_settings_section("combined")

    today = date.today()
    date_str = today.strftime("%Y-%m-%d")

    emb_file = Path(emb_settings["predict_path"]) / f"{date_str}.txt"
    sent_file = Path(sent_settings["predict_path"]) / f"{date_str}.txt"
    combined_path = Path(combined_settings["predict_path"])
    out_file = combined_path / f"{date_str}.txt"

    combined_path.mkdir(parents=True, exist_ok=True)

    if out_file.exists():
        cutoff = datetime.combine(date.today(), datetime.strptime(combined_settings["time_start"], "%H:%M:%S").time())
        file_mtime = datetime.fromtimestamp(out_file.stat().st_mtime)
        if file_mtime < cutoff:
            logger.info(f"Файл {out_file} создан до {combined_settings['time_start']} (тестовый) — перезаписываем.")
        else:
            logger.info(f"Файл {out_file} уже существует — пропуск.")
            return 0

    emb_dir = read_direction(emb_file)
    sent_dir = read_direction(sent_file)

    logger.info(f"embedding: {emb_dir} ({emb_file})")
    logger.info(f"sentiment: {sent_dir} ({sent_file})")

    if emb_dir in ("up", "down") and emb_dir == sent_dir:
        direction = emb_dir
    else:
        direction = "skip"

    emb_label = emb_dir if emb_dir is not None else "n/a"
    sent_label = sent_dir if sent_dir is not None else "n/a"

    content = (
        f"Дата: {date_str}\n"
        f"Embedding: {emb_label}\n"
        f"Sentiment: {sent_label}\n"
        f"Предсказанное направление: {direction}\n"
    )

    tmp_file = out_file.with_suffix(out_file.suffix + ".tmp")
    tmp_file.write_text(content, encoding="utf-8")
    tmp_file.replace(out_file)

    logger.info(f"Записан комбинированный прогноз: {out_file} (direction={direction})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
