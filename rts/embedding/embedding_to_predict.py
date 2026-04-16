"""
Формирует файл предсказания направления для следующей торговой сессии на основе эмбеддингов новостей.

Использует cache_file (эмбеддинги) и df_rez_output.xlsx (выбранное k на каждую дату из embedding_backtest.py).
Для последней даты из кэша эмбеддингов:
  1) Берёт best k из df_rez_output.xlsx (колонка 'max' последней строки).
  2) Считает косинусное сходство чанков текущей сессии с каждой из k предыдущих.
  3) Для наиболее похожей исторической сессии берёт её NEXT_OPEN_TO_OPEN.
  4) Направление raw = sign(body_prev): > 0 → "up", < 0 → "down", == 0 → skip.
  5) Если settings['invert_signal'] == true — инвертирует (up↔down).
Пишет <predict_path>/YYYY-MM-DD.txt (YYYY-MM-DD — дата только что закрывшейся сессии).
Если файл за эту дату уже есть — пропуск. На skip файл не создаётся.
"""

from __future__ import annotations

import logging
import pickle
import sqlite3
from datetime import datetime
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


def main() -> int:
    xlsx_path = Path(__file__).parent / "df_rez_output.xlsx"
    if not xlsx_path.exists():
        logging.error(f"Нет {xlsx_path} — запусти embedding_backtest.py перед предсказанием.")
        return 1

    best_k = read_best_k(xlsx_path)
    logging.info(f"Best k из df_rez_output.xlsx: {best_k}")

    df_bar = load_quotes(path_db_day)
    df_emb = load_cache(cache_file)

    df = df_emb[["CHUNKS"]].join(df_bar[["NEXT_OPEN_TO_OPEN"]], how="left")
    df = df.sort_index()

    if len(df) < best_k + 1:
        logging.error(f"В кэше эмбеддингов {len(df)} строк — недостаточно для k={best_k}.")
        return 1

    prediction_date = df.index[-1]
    date_str = prediction_date.strftime("%Y-%m-%d")
    out_file = predict_path / f"{date_str}.txt"

    if out_file.exists():
        logging.info(f"Файл {out_file} уже существует — пропуск.")
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
        logging.error("Не удалось найти похожий день.")
        return 1

    body_prev = df.iloc[best_j]["NEXT_OPEN_TO_OPEN"]
    best_date = df.index[best_j].strftime("%Y-%m-%d")
    logging.info(
        f"prediction_date={date_str}, best_j={best_date}, sim={best_sim:.4f}, body_prev={body_prev}"
    )

    if pd.isna(body_prev) or body_prev == 0:
        logging.info("body_prev пустой/нулевой — skip, файл не создаётся.")
        return 0

    raw_direction = "up" if body_prev > 0 else "down"
    if invert_signal:
        direction = "down" if raw_direction == "up" else "up"
    else:
        direction = raw_direction

    logging.info(
        f"raw={raw_direction}, invert_signal={invert_signal}, итог={direction}"
    )

    content = (
        f"Дата: {date_str}\n"
        f"Best k: {best_k}\n"
        f"Похожий день: {best_date}\n"
        f"Similarity: {best_sim:.4f}\n"
        f"body_prev: {body_prev:.2f}\n"
        f"Invert signal: {invert_signal}\n"
        f"Предсказанное направление: {direction}\n"
    )

    predict_path.mkdir(parents=True, exist_ok=True)
    tmp_file = out_file.with_suffix(out_file.suffix + ".tmp")
    tmp_file.write_text(content, encoding="utf-8")
    tmp_file.replace(out_file)
    logging.info(f"Записан файл предсказания: {out_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
