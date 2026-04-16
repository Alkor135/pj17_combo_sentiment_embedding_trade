"""
Просмотр содержимого sentiment_scores.pkl в консоли.
Загружает DataFrame, выводит shape, колонки, диапазон дат и сам df.
"""

import pickle
import sys
from pathlib import Path

import pandas as pd

_PKG_ROOT = Path(__file__).resolve().parents[1]
if str(_PKG_ROOT) not in sys.path:
    sys.path.insert(0, str(_PKG_ROOT))
from shared.config import load_settings

settings = load_settings("sentiment")

pkl_path = Path(settings["sentiment_output_pkl"])

if not pkl_path.exists():
    print(f"Файл не найден: {pkl_path}")
    sys.exit(1)

with open(pkl_path, "rb") as f:
    df = pickle.load(f)

if not isinstance(df, pd.DataFrame):
    df = pd.DataFrame(df)

print(f"Файл: {pkl_path}")
print(f"Shape: {df.shape}")
print(f"Колонки: {list(df.columns)}")
if "source_date" in df.columns:
    print(f"Период: {df['source_date'].min()} .. {df['source_date'].max()}")

with pd.option_context(
    "display.width", 1000,
    "display.max_columns", 20,
    "display.max_colwidth", 60,
    "display.max_rows", 500,
    "display.float_format", "{:,.2f}".format,
):
    print()
    # print(df)
    print(df[['date', 'ticker', 'model', 'prompt_tokens', 'raw_response', 'sentiment', 'body', 'next_body']])
