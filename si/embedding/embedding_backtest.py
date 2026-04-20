"""
Бэктест торговой стратегии на основе эмбеддингов новостей.
Загружает дневные котировки и кэш эмбеддингов, объединяет по датам.
Для каждой даты перебирает окна k=3..30, находит наиболее похожий день
по косинусному сходству чанков и формирует P/L на основе совпадения направлений.
Выбирает лучшее k по скользящей сумме P/L за test_days дней.
Применяет зеркальное отображение P/L (инверсия стратегии).
Строит график кумулятивного P/L с наложенной диаграммой лучших k.
Сохраняет результаты в Excel.
Предсказание на следующую сессию формирует отдельный скрипт embedding_to_predict.py.
Конфигурация через si/settings.yaml (секция embedding), логирование с ротацией (3 файла).
"""

from pathlib import Path
from datetime import datetime
import pickle
import sqlite3
import logging
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
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

_CHUNK_MATRIX_CACHE = {}  # Кэш для матриц чанков

# ==== Параметры ====
ticker = settings['ticker']
ticker_lc = ticker.lower()
cache_file = Path(settings['cache_file'])
path_db_day = Path(settings['path_db_day'])
min_prev_files = settings.get('min_prev_files', 2)
test_days = settings.get('test_days', 23) + 1
START_DATE = settings.get('start_date_test', "2025-10-01")
model_name = settings.get('model_name', 'bge-m3')
provider = settings['provider']

# === Логирование ===
log_dir = TICKER_DIR / 'log'
log_dir.mkdir(parents=True, exist_ok=True)
timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
log_file = log_dir / f'embedding_backtest_{timestamp}.txt'

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler()
    ]
)

def cleanup_old_logs(log_dir: Path, max_files: int = 3):
    """Удаляет старые лог-файлы, оставляя max_files самых новых."""
    log_files = sorted(log_dir.glob("embedding_backtest_*.txt"))
    if len(log_files) > max_files:
        for old_file in log_files[:-max_files]:
            try:
                old_file.unlink()
                print(f"Удалён старый лог: {old_file.name}")
            except Exception as e:
                print(f"Не удалось удалить {old_file}: {e}")

# Вызываем очистку ПЕРЕД началом логирования
cleanup_old_logs(log_dir, max_files=3)
logging.info(f"🚀 Запуск скрипта. Лог-файл: {log_file}")

def load_quotes(path_db_quote):
    """Загрузка котировок и расчет NEXT_OPEN_TO_OPEN (open-to-open следующей сессии)."""
    with sqlite3.connect(path_db_quote) as conn:
        df = pd.read_sql_query(
            "SELECT TRADEDATE, OPEN FROM Futures",
            conn,
            parse_dates=['TRADEDATE']  # <-- Преобразуем TRADEDATE в datetime
        )
    df = df.set_index('TRADEDATE').sort_index()
    df['NEXT_OPEN_TO_OPEN'] = df['OPEN'].shift(-2) - df['OPEN'].shift(-1)
    df = df.dropna(subset=['NEXT_OPEN_TO_OPEN'])
    return df[['NEXT_OPEN_TO_OPEN']]

def load_cache(cache_file_path):
    """Загрузка кэша эмбеддингов."""
    with open(cache_file_path, 'rb') as f:
        df = pickle.load(f)
    df['TRADEDATE'] = pd.to_datetime(df['TRADEDATE'])
    return df.set_index('TRADEDATE').sort_index()

def chunks_to_matrix(chunks):
    key = id(chunks)
    if key not in _CHUNK_MATRIX_CACHE:
        _CHUNK_MATRIX_CACHE[key] = np.vstack(
            [c["embedding"] for c in chunks]
        ).astype(np.float32)
    return _CHUNK_MATRIX_CACHE[key]

def cosine(a: np.ndarray, b: np.ndarray) -> float:
    """Сравнение по косинусному сходству"""
    # эмбеддинги уже L2-нормализованы
    return float(np.dot(a, b))

def chunks_similarity_fast(
    chunks_a: list,
    chunks_b: list,
    top_k: int = 5
) -> float:
    """    Быстрое retriever-grade similarity через матричное умножение    """

    if not chunks_a or not chunks_b:
        return 0.0

    A = chunks_to_matrix(chunks_a)  # (Na, D)
    B = chunks_to_matrix(chunks_b)  # (Nb, D)

    # Все cosine similarity сразу
    S = A @ B.T  # (Na, Nb)

    # top-k по всем значениям
    flat = S.ravel()

    if flat.size <= top_k:
        return float(flat.mean())

    # быстрее чем sort
    top = np.partition(flat, -top_k)[-top_k:]
    return float(top.mean())

def compute_max_k(
    df: pd.DataFrame,
    start_date: pd.Timestamp,
    k: int,
    col_chunks: str = "CHUNKS",
    col_body: str = "NEXT_OPEN_TO_OPEN",
    top_k_chunks: int = 5
) -> pd.Series:

    result = pd.Series(index=df.index, dtype=float)

    dates = df.index
    start_pos = dates.get_loc(start_date)

    for i in range(start_pos, len(df)):
        # Сдвиг окна на 2 дня: ищем аналог в [i-2-k, i-3] вместо [i-k, i-1].
        # Причина: в момент реального predict (21:00:05) у дней j=i-1 и j=i-2
        # NEXT_OPEN_TO_OPEN = NaN (нет 2 будущих OPEN в day DB). Бэктест имитирует
        # ту же информационную отсечку, что и predict.
        if i < k + 2:
            continue

        chunks_cur = df.iloc[i][col_chunks]
        body_cur = df.iloc[i][col_body]

        similarities = []
        indices = []

        # быстрые симы для выбора best_j
        for j in range(i - 2 - k, i - 2):
            chunks_prev = df.iloc[j][col_chunks]

            sim = chunks_similarity_fast(
                chunks_cur,
                chunks_prev,
                top_k=top_k_chunks
            )

            similarities.append(sim)
            indices.append(j)

        # индекс самой похожей строки
        best_idx = int(np.argmax(similarities))
        best_j = indices[best_idx]
        body_prev = df.iloc[best_j][col_body]

        if np.sign(body_cur) == np.sign(body_prev):
            result.iloc[i] = abs(body_cur)
        else:
            result.iloc[i] = -abs(body_cur)

    return result

def main(path_db_day, cache_file):
    df_bar = load_quotes(path_db_day)  # Загрузка DF с дневными котировками (с 21:00 пред. сессии)
    df_emb = load_cache(cache_file)  # Загрузка DF с векторами новостей

    # Объединение датафреймов по индексу TRADEDATE
    df_combined = df_bar.join(df_emb[['CHUNKS']], how='inner')  # 'inner' — только общие даты

    # Генерация колонок MAX_3 … MAX_30
    start_date = pd.to_datetime(START_DATE)
    for k in range(3, 31):
        col_name = f"MAX_{k}"
        logging.info(f"📊 Расчёт {col_name}")
        df_combined[col_name] = compute_max_k(
            df=df_combined,
            start_date=start_date,
            k=k
        )

    # === Замена NaN на 0.0 во всех MAX_ колонках ===
    max_cols = [f"MAX_{k}" for k in range(3, 31)]
    df_combined[max_cols] = df_combined[max_cols].fillna(0.0)

    # === Расчёт PL_ колонок ===
    for k in range(3, 31):
        max_col = f"MAX_{k}"
        pl_col = f"PL_{k}"

        df_combined[pl_col] = (
            df_combined[max_col]
            .shift(1)  # исключаем текущую строку
            .rolling(window=test_days, min_periods=1)
            .sum()
        )

    # Отладочный вывод
    with pd.option_context(
        "display.width", 1000,
        "display.max_columns", 10,
        "display.max_colwidth", 90
    ):
        print("\ndf_bar:")
        print(df_bar)
        print("\ndf_emb:")
        print(df_emb)
        print('\ndf_combined[["NEXT_OPEN_TO_OPEN", "CHUNKS"]]:')
        print(df_combined[["NEXT_OPEN_TO_OPEN", "CHUNKS"]])
        print("\ndf_combined:")
        print(df_combined)

    # === Замена NaN на 0.0 во всех колонках ===
    df_combined = df_combined.fillna(0.0)

    # === ОСТАВИТЬ ТОЛЬКО НУЖНЫЕ КОЛОНКИ ===
    final_cols = [f"MAX_{k}" for k in range(3, 31)] + [f"PL_{k}" for k in range(3, 31)]
    df_combined = df_combined[final_cols].copy()

    # Опционально: сортировка по индексу (по дате)
    df_combined.sort_index(inplace=True)

    # Отладочный вывод
    with pd.option_context(
        "display.width", 1000,
        "display.max_columns", 30,
        "display.max_colwidth", 120,
        "display.min_rows", 30
    ):
        print("\nКомбинированный DataFrame (df_combined) с MAX_ и PL_ колонками:")
        print(df_combined[[f"PL_{k}" for k in range(3, 31)]])

    # ===============================
    # Формирование df_rez
    # ===============================

    pl_cols = [f"PL_{k}" for k in range(3, 31)]
    max_cols = [f"MAX_{k}" for k in range(3, 31)]

    rows = []

    for idx, row in df_combined.iterrows():
        trade_date = idx

        # максимальное значение среди PL_3 ... PL_30
        pl_values = row[pl_cols]
        pl_max = pl_values.max()

        pl_result = 0.0

        # ---
        # if pl_max > 0.0:
        # имя колонки с максимальным PL
        best_pl_col = pl_values.idxmax()  # например "PL_7"
        n = int(best_pl_col.split("_")[1])  # -> 7

        # соответствующая колонка MAX_n
        max_col = f"MAX_{n}"
        pl_result = row[max_col]
        # ---

        rows.append({
            "TRADEDATE": trade_date,
            "P/L": pl_result,
            "max": n
        })

    df_rez = pd.DataFrame(rows).set_index("TRADEDATE")

    # ===============================
    # Вывод df_rez в консоль
    # ===============================
    with pd.option_context(
            "display.width", 1000,
            "display.max_columns", 10,
            "display.max_colwidth", 120
    ):
        print("\nРезультирующий DataFrame (df_rez):")
        print(df_rez)

    # --- ЗЕРКАЛЬНОЕ ОТОБРАЖЕНИЕ (инверсия стратегии) ---
    df_rez["P/L"] *= -1
    # ---------------------------------------------------

    # Сохранение DataFrame в Excel файл (уже с инверсией P/L)
    df_rez.to_excel(Path(__file__).parent / 'embedding_backtest_results.xlsx', index=True)

    # ===============================
    # График cumulative P/L + наложенная столбчатая диаграмма max
    # ===============================

    df_rez["CUM_P/L"] = df_rez["P/L"].cumsum()

    fig, ax1 = plt.subplots(figsize=(12, 7))

    # Основной график: Cumulative P/L (справа)
    ax1.plot(
        df_rez.index, df_rez["CUM_P/L"],
        marker='o',
        markersize=4,
        color='tab:blue',
        label='Cumulative P/L'
    )
    ax1.set_ylabel("Cumulative P/L", color='tab:blue')
    ax1.tick_params(axis='y', labelcolor='tab:blue')
    ax1.set_xlabel("Date")
    ax1.grid(True, axis='y', alpha=0.3)
    ax1.set_title(
        f"{ticker} Cumulative P/L & Best Window (k) "
        f"{model_name.split(':')[0]} {provider} {timestamp}"
        )

    # Вторая ось Y для столбчатой диаграммы (слева)
    ax2 = ax1.twinx()
    ax2.bar(
        df_rez.index, df_rez["max"],
        alpha=0.5,
        color='tab:green',
        width=0.5,
        label="Best Window (k)"
    )
    ax2.set_ylabel("Best Window (k)", color='tab:green')
    ax2.tick_params(axis='y', labelcolor='tab:green')
    ax2.set_ylim(df_rez["max"].min() - 1, df_rez["max"].max() + 1)

    # Объединение легенды
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper left')

    # Оформление оси X
    plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45)
    fig.tight_layout()

    # Сохранение графика
    plot_dir = TICKER_DIR / 'plots'
    plot_dir.mkdir(parents=True, exist_ok=True)
    plot_path = plot_dir / f'embedding_backtest_{model_name.split(":")[0]}_{provider}.png'
    plt.savefig(plot_path)
    logging.info(f"📊 График сохранён: {plot_path}")

    plt.close()  # Освобождаем память

if __name__ == "__main__":
    main(path_db_day, cache_file)