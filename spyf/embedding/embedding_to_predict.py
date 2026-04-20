"""
Формирует файл предсказания направления для следующей торговой сессии на основе эмбеддингов новостей.

Использует cache_file (эмбеддинги) и embedding_backtest_results.xlsx (выбранное k на каждую дату из embedding_backtest.py).
Для последней даты из кэша эмбеддингов:
  1) Берёт best k из embedding_backtest_results.xlsx (колонка 'max' последней строки).
  2) Считает косинусное сходство чанков текущей сессии с каждой из k предыдущих.
  3) Для наиболее похожей исторической сессии берёт её NEXT_OPEN_TO_OPEN.
  4) Направление raw = sign(open_to_open_next): > 0 → "up", < 0 → "down", == 0 или NaN → "skip".
  5) Если settings['invert_signal'] == true — инвертирует (up↔down); skip остаётся skip.

Файл <predict_path>/YYYY-MM-DD.txt (YYYY-MM-DD = date.today()) пишется ВСЕГДА,
включая нештатные ситуации — направление=skip, причина в поле Status, детали в Note.

Возможные значения Status:
  ok                     — нормальная запись направления (up/down)
  backtest_xlsx_missing  — нет embedding_backtest_results.xlsx
  backtest_xlsx_invalid  — в xlsx нет колонки 'max' или он пуст
  cache_too_small        — в кэше эмбеддингов меньше best_k+1 строк
  cache_stale            — последняя дата в кэше эмбеддингов ≠ сегодня
  no_similar_day         — не удалось найти похожий день
  open_to_open_nan       — NEXT_OPEN_TO_OPEN у похожего дня = NaN
  open_to_open_zero      — NEXT_OPEN_TO_OPEN у похожего дня = 0
  error                  — необработанное исключение (traceback — в Note)

Если файл за сегодня уже есть и создан после time_start — пропуск;
если создан до time_start (тестовый прогон) — перезаписывается.

Скрипт всегда возвращает 0, чтобы сбой по одному тикеру не останавливал
run_all.py и не блокировал обработку остальных тикеров.
"""

from __future__ import annotations

import logging
import pickle
import sqlite3
from datetime import date, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

# --- Загрузка настроек из {ticker}/settings.yaml (common + embedding) ---
TICKER_DIR = Path(__file__).resolve().parents[1]
_raw = yaml.safe_load((TICKER_DIR / "settings.yaml").read_text(encoding="utf-8"))
settings = {**(_raw.get("common") or {}), **(_raw.get("embedding") or {})}
_ticker = settings.get("ticker", "")
_ticker_lc = settings.get("ticker_lc", _ticker.lower())
for _k, _v in list(settings.items()):
    if isinstance(_v, str):
        settings[_k] = _v.replace("{ticker}", _ticker).replace("{ticker_lc}", _ticker_lc)

cache_file = Path(settings['cache_file'])
path_db_day = Path(settings['path_db_day'])
predict_path = Path(settings['predict_path'])
invert_signal = bool(settings.get('invert_signal', False))

log_dir = TICKER_DIR / 'log'
log_dir.mkdir(parents=True, exist_ok=True)
timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
log_file = log_dir / f'embedding_to_predict_{timestamp}.txt'

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler()
    ],
    force=True,
)


def cleanup_old_logs(log_dir: Path, max_files: int = 3) -> None:
    log_files = sorted(log_dir.glob("embedding_to_predict_*.txt"))
    for old in log_files[:-max_files]:
        try:
            old.unlink()
        except Exception as exc:
            print(f"Не удалось удалить {old}: {exc}")


cleanup_old_logs(log_dir)


def load_quotes(db_path: Path) -> pd.DataFrame:
    with sqlite3.connect(db_path) as conn:
        df = pd.read_sql_query(
            "SELECT TRADEDATE, OPEN FROM Futures",
            conn,
            parse_dates=["TRADEDATE"],
        )
    df = df.set_index("TRADEDATE").sort_index()
    df["NEXT_OPEN_TO_OPEN"] = df["OPEN"].shift(-2) - df["OPEN"].shift(-1)
    return df


def load_cache(pkl_path: Path) -> pd.DataFrame:
    with pkl_path.open("rb") as f:
        df = pickle.load(f)
    df["TRADEDATE"] = pd.to_datetime(df["TRADEDATE"])
    return df.set_index("TRADEDATE").sort_index()


def chunks_to_matrix(chunks: list) -> np.ndarray:
    return np.vstack([c["embedding"] for c in chunks]).astype(np.float32)


def similarity(chunks_a: list, chunks_b: list, top_k: int = 5) -> float:
    if not chunks_a or not chunks_b:
        return 0.0
    A = chunks_to_matrix(chunks_a)
    B = chunks_to_matrix(chunks_b)
    S = A @ B.T
    flat = S.ravel()
    if flat.size <= top_k:
        return float(flat.mean())
    return float(np.partition(flat, -top_k)[-top_k:].mean())


def read_best_k(xlsx_path: Path) -> int:
    df = pd.read_excel(xlsx_path)
    if "max" not in df.columns or df.empty:
        raise ValueError(f"В {xlsx_path} нет колонки 'max' или файл пуст")
    return int(df["max"].iloc[-1])


def write_predict(
    out_file: Path,
    date_str: str,
    direction: str,
    status: str,
    best_k: int | None = None,
    best_date: str | None = None,
    best_sim: float | None = None,
    open_to_open_next_label: str | None = None,
    note: str = "",
) -> None:
    """Атомарно пишет файл предсказания. direction — итоговое направление (up/down/skip)."""
    lines = [
        f"Дата: {date_str}",
        f"Best k: {best_k if best_k is not None else 'n/a'}",
        f"Похожий день: {best_date if best_date is not None else 'n/a'}",
        f"Similarity: {f'{best_sim:.4f}' if best_sim is not None else 'n/a'}",
        f"open_to_open_next: {open_to_open_next_label if open_to_open_next_label is not None else 'n/a'}",
        "(open_to_open_next — движение OPEN→OPEN сессии, наступившей после похожего дня; знак задаёт прогноз: >0 → up, <0 → down, 0/NaN → skip)",
        f"Invert signal: {invert_signal}",
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
    today = date.today()
    date_str = today.strftime("%Y-%m-%d")
    out_file = predict_path / f"{date_str}.txt"

    try:
        if out_file.exists():
            cutoff = datetime.combine(today, datetime.strptime(settings["time_start"], "%H:%M:%S").time())
            file_mtime = datetime.fromtimestamp(out_file.stat().st_mtime)
            if file_mtime < cutoff:
                logging.info(f"Файл {out_file} создан до {settings['time_start']} (тестовый) — перезаписываем.")
            else:
                logging.info(f"Файл {out_file} уже существует — пропуск.")
                return 0

        xlsx_path = Path(__file__).parent / "embedding_backtest_results.xlsx"
        if not xlsx_path.exists():
            msg = f"Нет {xlsx_path} — запусти embedding_backtest.py перед предсказанием."
            logging.error(msg)
            write_predict(out_file, date_str, "skip", "backtest_xlsx_missing", note=msg)
            return 0

        try:
            best_k = read_best_k(xlsx_path)
        except ValueError as exc:
            logging.error(f"backtest_xlsx_invalid: {exc}")
            write_predict(out_file, date_str, "skip", "backtest_xlsx_invalid", note=str(exc))
            return 0

        logging.info(f"Best k из embedding_backtest_results.xlsx: {best_k}")

        df_bar = load_quotes(path_db_day)
        df_emb = load_cache(cache_file)
        df = df_emb[["CHUNKS"]].join(df_bar[["NEXT_OPEN_TO_OPEN"]], how="left").sort_index()

        if len(df) < best_k + 1:
            msg = f"В кэше эмбеддингов {len(df)} строк — недостаточно для k={best_k}."
            logging.error(msg)
            write_predict(out_file, date_str, "skip", "cache_too_small",
                          best_k=best_k, note=msg)
            return 0

        prediction_date = df.index[-1]
        if prediction_date.date() != today:
            msg = (f"последняя дата в кэше эмбеддингов = {prediction_date.strftime('%Y-%m-%d')}, "
                   f"не совпадает с сегодня ({date_str})")
            logging.error(f"cache_stale: {msg}")
            write_predict(out_file, date_str, "skip", "cache_stale",
                          best_k=best_k, note=msg)
            return 0

        chunks_cur = df.iloc[-1]["CHUNKS"]

        best_sim = -np.inf
        best_j = None
        for j in range(len(df) - 1 - best_k, len(df) - 1):
            sim = similarity(chunks_cur, df.iloc[j]["CHUNKS"])
            if sim > best_sim:
                best_sim = sim
                best_j = j

        if best_j is None:
            msg = "не удалось найти похожий день"
            logging.error(msg)
            write_predict(out_file, date_str, "skip", "no_similar_day",
                          best_k=best_k, note=msg)
            return 0

        open_to_open_next = df.iloc[best_j]["NEXT_OPEN_TO_OPEN"]
        best_date = df.index[best_j].strftime("%Y-%m-%d")
        logging.info(
            f"prediction_date={date_str}, best_j={best_date}, sim={best_sim:.4f}, open_to_open_next={open_to_open_next}"
        )

        if pd.isna(open_to_open_next):
            write_predict(out_file, date_str, "skip", "open_to_open_nan",
                          best_k=best_k, best_date=best_date, best_sim=float(best_sim),
                          open_to_open_next_label="n/a",
                          note="NEXT_OPEN_TO_OPEN у похожего дня = NaN (нет данных по следующим сессиям)")
            return 0

        if open_to_open_next == 0:
            write_predict(out_file, date_str, "skip", "open_to_open_zero",
                          best_k=best_k, best_date=best_date, best_sim=float(best_sim),
                          open_to_open_next_label=f"{open_to_open_next:.2f}",
                          note="NEXT_OPEN_TO_OPEN у похожего дня = 0")
            return 0

        raw_direction = "up" if open_to_open_next > 0 else "down"
        if invert_signal:
            direction = "down" if raw_direction == "up" else "up"
        else:
            direction = raw_direction

        logging.info(f"raw={raw_direction}, invert_signal={invert_signal}, итог={direction}")

        write_predict(out_file, date_str, direction, "ok",
                      best_k=best_k, best_date=best_date, best_sim=float(best_sim),
                      open_to_open_next_label=f"{open_to_open_next:.2f}")
        logging.info(f"Записан файл предсказания: {out_file}")
        return 0

    except Exception as exc:
        logging.exception("Необработанная ошибка embedding_to_predict")
        try:
            write_predict(out_file, date_str, "skip", "error",
                          note=f"{type(exc).__name__}: {exc}")
        except Exception as write_exc:
            logging.error(f"Не удалось записать файл предсказания с ошибкой: {write_exc}")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
