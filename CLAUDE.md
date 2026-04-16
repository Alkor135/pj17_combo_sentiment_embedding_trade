# CLAUDE.md — pj17_combo_sentiment_embedding_trade

Самодостаточный проект по торговле фьючерсами Московской биржи, объединяющий две стратегии
(эмбеддинги новостей + сентимент-анализ через Ollama) в один сигнал через **согласованное
голосование**. Первый тикер — RTS; после проверки план размножить на MIX.

## Запуск

Пайплайн целиком запускается одним оркестратором `run_all.py` из Windows Task Scheduler
**ежедневно в 21:00:05** (сразу после открытия новой сессии MOEX):

```cmd
schtasks /Create /SC DAILY /ST 21:00:05 /TN "pj17_run_all" ^
  /TR "python C:\Users\Alkor\VSCode\pj17_combo_sentiment_embedding_trade\run_all.py"
```

`run_all.py` выполняет шаги по порядку: загрузка котировок → markdown → embedding-ветка →
sentiment-ветка → комбинатор → торговля → аналитика (в хвосте). До и включая торговый
скрипт — hard-fail. После — soft-fail, чтобы сбой в аналитике не сорвал торговлю завтра.
`sentiment_compare.py` идёт самым последним.

## Структура

```
pj17_combo_sentiment_embedding_trade/
├── beget/                              # RSS-скрапер, не трогаем
├── rts/
│   ├── settings.yaml                   # секции common / embedding / sentiment / combined
│   ├── rules.yaml                      # правила для sentiment (follow/invert/skip)
│   ├── shared/
│   │   ├── download_minutes_to_db.py
│   │   ├── convert_minutes_to_days.py
│   │   ├── create_markdown_files.py
│   │   └── check_pkl.py
│   ├── embedding/
│   │   ├── create_embedding.py
│   │   ├── embedding_backtest.py       # бэктест + выбор лучшего k + P/L *= -1 на виджете
│   │   ├── embedding_to_predict.py     # ПИШЕТ ИНВЕРТИРОВАННЫЙ прогноз на today
│   │   └── embedding_analysis.py
│   ├── sentiment/
│   │   ├── sentiment_analysis.py
│   │   ├── sentiment_to_predict.py     # пишет прогноз по rules.yaml
│   │   ├── sentiment_group_stats.py
│   │   ├── sentiment_backtest.py
│   │   └── sentiment_compare.py        # ПОСЛЕДНИЙ в run_all.py
│   ├── combine_predictions.py          # согласованное голосование → combined/*.txt
│   ├── log/                            # логи всех скриптов rts/*
│   ├── plots/                          # HTML+PNG отчёты
│   └── group_stats/                    # xlsx от sentiment_group_stats.py
├── trade/
│   ├── settings.yaml                   # accounts.{iis,ebs}.{rts,mix}.quantity_{open,close}
│   ├── trade_rts_tri_SPBFUT192yc_ebs.py  # суффикс _<account>_ebs — НЕ переименовывать
│   ├── quik_export_minutes.lua
│   ├── quik_export/, state/, log/
├── run_all.py                          # оркестратор (Task Scheduler, 21:00:05)
├── html_open.py                        # открывает rts/plots/*.html в Chrome
├── requirements.txt                    # объединённые зависимости
├── CLAUDE.md
└── README.md
```

## Ключевые принципы

### 1. Единый settings.yaml с секциями, загрузка инлайном в каждом скрипте
`rts/settings.yaml` содержит `common` + `embedding` + `sentiment` + `combined`. Каждый
скрипт сам читает YAML в ~7 строк инлайн-блоком: `common` + нужная секция плоско мержатся
(секция переопределяет одноимённые ключи common), плейсхолдеры `{ticker}` / `{ticker_lc}`
подставляются в строковых значениях. Общего хелпера (`shared/config.py`) нет — каждый
скрипт самодостаточен. Образец блока — в любом из `rts/shared/*.py`.

### 2. Инверсия эмбеддинг-прогноза — в файле прогноза, а не в торговом скрипте
`embedding_to_predict.py` применяет `invert_signal: true` ПРИ ЗАПИСИ файла. Это делает файл
прогноза симметричным с sentiment-файлом — оба «готовы к исполнению». Торговый скрипт
никакой инверсии НЕ делает, только читает итоговое направление.

### 3. Согласованное голосование
`combine_predictions.py` читает `<embedding.predict_path>/YYYY-MM-DD.txt` и
`<sentiment.predict_path>/YYYY-MM-DD.txt`. Правило:
- `up + up` → `up`
- `down + down` → `down`
- любой конфликт или отсутствие одного из файлов → **skip** (файл не создаётся)

Торговый скрипт читает ТОЛЬКО `<combined.predict_path>/YYYY-MM-DD.txt`.

### 4. Имена торговых скриптов — с суффиксом счёта
`trade_rts_tri_SPBFUT192yc_ebs.py` — суффикс кодирует торговый счёт и ключ аккаунта
(`ebs` → `accounts.ebs` в `trade/settings.yaml`). Это позволяет держать параллельные
скрипты под разные счета без рефакторинга. **Не переименовывать.**

### 5. Multi-account trade/settings.yaml
```yaml
accounts:
  iis: { trade_path: ..., trade_account: ..., rts: {quantity_*}, mix: {...} }
  ebs: { trade_path: ..., trade_account: ..., rts: {...}, mix: {...} }
```
Конкретный скрипт читает свой `account = trade_cfg['accounts']['<key>']`. Сохранять эту
структуру, даже если сейчас используется один счёт.

## Порядок в `run_all.py`

Hard-fail (останов пайплайна при ошибке):
1. `beget/sync_files.py`
2. `rts/shared/download_minutes_to_db.py`
3. `rts/shared/convert_minutes_to_days.py`
4. `rts/shared/create_markdown_files.py`
5. `rts/embedding/create_embedding.py`
6. `rts/embedding/embedding_backtest.py`
7. `rts/embedding/embedding_to_predict.py` ← инверсия применяется здесь
8. `rts/sentiment/sentiment_analysis.py`
9. `rts/sentiment/sentiment_to_predict.py`
10. `rts/combine_predictions.py`
11. `trade/trade_rts_tri_SPBFUT192yc_ebs.py` ← критично по времени

Soft-fail (логируется, пайплайн продолжается):
12. `rts/embedding/embedding_analysis.py`
13. `rts/sentiment/sentiment_group_stats.py`
14. `rts/sentiment/sentiment_backtest.py`
15. `rts/sentiment/sentiment_compare.py` ← ПОСЛЕДНИЙ

## Что НЕ переносим из pj14/pj16

- `analyze_explain.py` (pj14) — не нужен.
- `sentiment_walk_forward.py`, `sentiment_walk_forward_analysis.py` (pj16) — не нужны.

## Размножение на MIX

Копируем `rts/` → `mix/`, правим `mix/settings.yaml` (`ticker: MIX`, `ticker_lc: mix`,
соответствующие пути котировок и фьючерсы) и `mix/rules.yaml`. В `trade/` добавляем копию
торгового скрипта с новым суффиксом счёта, например `trade_mix_tri_<account>_<key>.py`,
соблюдая конвенцию имени.
