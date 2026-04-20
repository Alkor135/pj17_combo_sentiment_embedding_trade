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
по источникам и полем Status, чтобы утром сразу было видно причину любого skip.

Возможные значения Status:
  ok              — embedding и sentiment согласованно дали up или down
  agree_skip      — оба источника = skip
  conflict        — направления различаются (up vs down)
  emb_skip        — embedding = skip, sentiment = up/down
  sent_skip       — sentiment = skip, embedding = up/down
  emb_missing     — файла предсказания embedding нет
  sent_missing    — файла предсказания sentiment нет
  both_missing    — нет ни того, ни другого
  emb_unparsed    — файл embedding есть, но направление не распознано
  sent_unparsed   — файл sentiment есть, но направление не распознано
  error           — необработанное исключение (детали в Note)

Оба исходных файла считаются уже «готовыми к исполнению» (инверсия применена при записи).
Если файл за сегодня уже есть и создан после time_start — пропуск;
если создан до time_start (тестовый прогон) — перезаписывается.

Скрипт всегда возвращает 0, чтобы сбой по одному тикеру не останавливал run_all.py.
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


def read_direction(file_path: Path) -> tuple[str | None, bool]:
    """Возвращает (direction, file_exists). direction=None если файла нет ИЛИ регэксп не нашёл."""
    if not file_path.exists():
        return None, False
    text = file_path.read_text(encoding="utf-8", errors="replace")
    match = DIRECTION_RE.search(text)
    if not match:
        return None, True
    return match.group(1).lower(), True


def classify(emb_dir: str | None, emb_exists: bool,
             sent_dir: str | None, sent_exists: bool) -> tuple[str, str, str]:
    """Возвращает (direction, status, note)."""
    if not emb_exists and not sent_exists:
        return "skip", "both_missing", "ни одного исходного файла прогноза не найдено"
    if not emb_exists:
        return "skip", "emb_missing", "нет файла прогноза embedding за сегодня"
    if not sent_exists:
        return "skip", "sent_missing", "нет файла прогноза sentiment за сегодня"
    if emb_dir is None:
        return "skip", "emb_unparsed", "в файле embedding не найдено 'Предсказанное направление:'"
    if sent_dir is None:
        return "skip", "sent_unparsed", "в файле sentiment не найдено 'Предсказанное направление:'"
    if emb_dir == "skip" and sent_dir == "skip":
        return "skip", "agree_skip", "оба источника = skip"
    if emb_dir == "skip":
        return "skip", "emb_skip", f"embedding=skip, sentiment={sent_dir}"
    if sent_dir == "skip":
        return "skip", "sent_skip", f"sentiment=skip, embedding={emb_dir}"
    if emb_dir == sent_dir:
        return emb_dir, "ok", ""
    return "skip", "conflict", f"embedding={emb_dir}, sentiment={sent_dir}"


def write_combined(
    out_file: Path,
    date_str: str,
    direction: str,
    status: str,
    emb_label: str,
    sent_label: str,
    note: str = "",
) -> None:
    lines = [
        f"Дата: {date_str}",
        f"Embedding: {emb_label}",
        f"Sentiment: {sent_label}",
        f"Status: {status}",
    ]
    if note:
        lines.append(f"Note: {note}")
    lines.append(f"Предсказанное направление: {direction}")
    content = "\n".join(lines) + "\n"

    out_file.parent.mkdir(parents=True, exist_ok=True)
    tmp_file = out_file.with_suffix(out_file.suffix + ".tmp")
    tmp_file.write_text(content, encoding="utf-8")
    tmp_file.replace(out_file)


def main() -> int:
    logger = setup_logging()

    today = date.today()
    date_str = today.strftime("%Y-%m-%d")

    try:
        emb_settings = load_settings_section("embedding")
        sent_settings = load_settings_section("sentiment")
        combined_settings = load_settings_section("combined")

        emb_file = Path(emb_settings["predict_path"]) / f"{date_str}.txt"
        sent_file = Path(sent_settings["predict_path"]) / f"{date_str}.txt"
        combined_path = Path(combined_settings["predict_path"])
        out_file = combined_path / f"{date_str}.txt"

        combined_path.mkdir(parents=True, exist_ok=True)

        if out_file.exists():
            cutoff = datetime.combine(today, datetime.strptime(combined_settings["time_start"], "%H:%M:%S").time())
            file_mtime = datetime.fromtimestamp(out_file.stat().st_mtime)
            if file_mtime < cutoff:
                logger.info(f"Файл {out_file} создан до {combined_settings['time_start']} (тестовый) — перезаписываем.")
            else:
                logger.info(f"Файл {out_file} уже существует — пропуск.")
                return 0

        emb_dir, emb_exists = read_direction(emb_file)
        sent_dir, sent_exists = read_direction(sent_file)

        logger.info(f"embedding: exists={emb_exists} direction={emb_dir} ({emb_file})")
        logger.info(f"sentiment: exists={sent_exists} direction={sent_dir} ({sent_file})")

        direction, status, note = classify(emb_dir, emb_exists, sent_dir, sent_exists)

        emb_label = emb_dir if emb_dir is not None else ("unparsed" if emb_exists else "n/a")
        sent_label = sent_dir if sent_dir is not None else ("unparsed" if sent_exists else "n/a")

        write_combined(out_file, date_str, direction, status, emb_label, sent_label, note)
        logger.info(f"Записан комбинированный прогноз: {out_file} (direction={direction}, status={status})")
        return 0

    except Exception as exc:
        logger.exception("Необработанная ошибка combine_predictions")
        try:
            combined_settings = load_settings_section("combined")
            out_file = Path(combined_settings["predict_path"]) / f"{date_str}.txt"
            write_combined(out_file, date_str, "skip", "error", "n/a", "n/a",
                           note=f"{type(exc).__name__}: {exc}")
        except Exception as write_exc:
            logger.error(f"Не удалось записать combined с ошибкой: {write_exc}")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
