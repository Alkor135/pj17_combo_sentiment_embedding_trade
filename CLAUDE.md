# CLAUDE.md — pj17_combo_sentiment_embedding_trade

Самодостаточный проект по торговле фьючерсами Московской биржи, объединяющий две
стратегии (эмбеддинги новостей + sentiment-анализ через Ollama) в один сигнал через
**согласованное голосование**. Работает одновременно по нескольким тикерам — **RTS**,
**MIX**, **BR**, **GOLD**, **NG**, **Si**, **SPYF** — с единым оркестратором и общим
торговым модулем. Тикеры BR, GOLD, NG, Si, SPYF пока используются только для
бэктеста и анализа (без торговли и без включения в `run_all.py`).

## Запуск

Пайплайн целиком запускается одним оркестратором `run_all.py` из Windows Task
Scheduler **ежедневно в 21:00:05** (сразу после открытия новой сессии MOEX):

```cmd
schtasks /Create /SC DAILY /ST 21:00:05 /TN "pj17_run_all" ^
  /TR "python C:\Users\Alkor\VSCode\pj17_combo_sentiment_embedding_trade\run_all.py"
```

`run_all.py` выполняет шаги **парами RTS → MIX** на каждом этапе, чтобы оба `.tri`
попали в QUIK с минимальным лагом. До и включая торговые скрипты — hard-fail (при
ошибке `sys.exit`). После — soft-fail, чтобы сбой в аналитике не сорвал торговлю
завтра. Последний шаг всегда `mix/sentiment/sentiment_compare.py`.

## Структура

```
pj17_combo_sentiment_embedding_trade/
├── beget/                              # RSS-скрапер и sync_files.py (не трогаем)
├── rts/                                # ветка тикера RTS
│   ├── settings.yaml                   # секции common / embedding / sentiment / combined
│   ├── rules.yaml                      # правила для sentiment (follow/invert/skip)
│   ├── shared/
│   │   ├── download_minutes_to_db.py
│   │   ├── convert_minutes_to_days.py
│   │   ├── create_markdown_files.py
│   │   └── check_pkl.py
│   ├── embedding/
│   │   ├── create_embedding.py
│   │   ├── embedding_backtest.py       # бэктест + выбор лучшего k + инверсия P/L в xlsx
│   │   ├── embedding_to_predict.py     # ПИШЕТ ИНВЕРТИРОВАННЫЙ прогноз на today
│   │   └── embedding_analysis.py
│   ├── sentiment/
│   │   ├── sentiment_analysis.py
│   │   ├── sentiment_to_predict.py     # пишет прогноз по rules.yaml (на skip — файла нет)
│   │   ├── sentiment_group_stats.py
│   │   ├── sentiment_backtest.py
│   │   └── sentiment_compare.py
│   ├── combine_predictions.py          # согласованное голосование → combined/*.txt
│   ├── log/                            # логи всех скриптов rts/*
│   ├── plots/                          # HTML+PNG отчёты
│   └── group_stats/                    # xlsx от sentiment_group_stats.py
├── mix/                                # ветка тикера MIX — зеркало rts/
│   └── (такое же дерево, settings.yaml ticker: MIX)
├── br/                                 # ветка тикера BR — зеркало rts/ (только бэктест/анализ)
│   └── (такое же дерево, settings.yaml ticker: BR, фьючерс BRM6)
├── gold/                               # ветка тикера GOLD — зеркало rts/ (только бэктест/анализ)
│   └── (такое же дерево, settings.yaml ticker: GOLD, фьючерс GDM6)
├── ng/                                 # ветка тикера NG — зеркало rts/ (только бэктест/анализ)
│   └── (такое же дерево, settings.yaml ticker: NG, фьючерс NGM6)
├── si/                                 # ветка тикера Si — зеркало rts/ (только бэктест/анализ)
│   └── (такое же дерево, settings.yaml ticker: Si, фьючерс SiM6)
├── spyf/                               # ветка тикера SPYF — зеркало rts/ (только бэктест/анализ)
│   └── (такое же дерево, settings.yaml ticker: SPYF, фьючерс SFM6)
├── trade/
│   ├── settings.yaml                   # accounts.{iis,ebs}.{rts,mix}.quantity_{open,close}
│   ├── trade_rts_tri_SPBFUT192yc_ebs.py  # суффикс _<trade_account>_<key> — НЕ переименовывать
│   ├── trade_mix_tri_SPBFUT192yc_ebs.py
│   ├── read_positions.py               # читает позиции из QUIK (json) или yaml-override
│   ├── quik_export_minutes.lua
│   ├── quik_export_positions.lua       # QUIK-экспортёр позиций → quik_export/positions.json
│   ├── quik_export/                    # minutes.csv + positions.json от lua-экспортёров
│   ├── state/                          # *.done маркеры + positions.yaml (ручной override)
│   └── log/
├── prepare.py                          # очистка сегодняшних результатов при тестовом запуске (до 21:00)
├── run_all.py                          # оркестратор (Task Scheduler, 21:00:05)
├── html_open.py                        # открывает rts/plots/*.html + mix/plots/*.html в Chrome
├── requirements.txt
├── CLAUDE.md
└── README.md
```

## Ключевые принципы

### 1. Единый settings.yaml с секциями, загрузка инлайном в каждом скрипте
`<ticker>/settings.yaml` содержит `common` + `embedding` + `sentiment` + `combined`.
Каждый скрипт сам читает YAML в ~7 строк инлайн-блоком: `common` + нужная секция
плоско мержатся (секция переопределяет одноимённые ключи common), плейсхолдеры
`{ticker}` / `{ticker_lc}` подставляются в строковых значениях. Общего хелпера
(`shared/config.py`) нет — каждый скрипт самодостаточен. Образец блока — в любом из
`rts/shared/*.py`.

### 2. Инверсия эмбеддинг-прогноза — в файле прогноза, а не в торговом скрипте
`embedding_to_predict.py` применяет `invert_signal: true` ПРИ ЗАПИСИ файла. Это
делает файл прогноза симметричным с sentiment-файлом — оба «готовы к исполнению».
Торговый скрипт никакой инверсии НЕ делает, только читает итоговое направление.
`embedding_backtest.py` инвертирует P/L уже в xlsx (`df_rez["P/L"] *= -1` перед
записью), поэтому `embedding_analysis.py` и `sentiment_compare.py` работают с
уже-инвертированной кривой.

### 3. Согласованное голосование
`combine_predictions.py` читает `<embedding.predict_path>/YYYY-MM-DD.txt` и
`<sentiment.predict_path>/YYYY-MM-DD.txt`. Правило:
- `up + up` → `up`
- `down + down` → `down`
- любой конфликт или отсутствие одного из файлов → `skip`

Итоговый файл `<combined.predict_path>/YYYY-MM-DD.txt` пишется **ВСЕГДА** (включая
случай `skip`), с разбивкой по источникам (Embedding / Sentiment / итоговое
направление) — удобно для ручного контроля. Если файл за эту дату уже есть —
пропуск. Торговый скрипт читает ТОЛЬКО `<combined.predict_path>/YYYY-MM-DD.txt` и
на `skip` выходит в «вне рынка» (target_position = 0).

Важный нюанс: `sentiment_to_predict.py` на `skip` файл НЕ создаёт (намеренно),
`embedding_to_predict.py` пишет ВСЕГДА (включая `skip`). Для `combine_predictions`
оба случая сводятся к `direction = skip` — эффект одинаков.

### 4. Target-state торговая модель
Торговый скрипт (`trade_<ticker>_tri_<trade_account>_<key>.py`):
1. Читает combined-прогноз на сегодня, вычисляет целевую позицию
   (`up` → +qty, `down` → −qty, `skip` → 0).
2. Текущую позицию берёт из `read_positions.py`: сначала пробует
   `trade/state/positions.yaml` (ручной override), затем `trade/quik_export/positions.json`
   (экспорт `quik_export_positions.lua` из QUIK). Если нигде нет — позиция = 0.
3. Считает дельту = цель − текущая, пишет в `<trade_path>/input.tri` пару заявок:
   закрытие противоположной позиции + открытие нужной.
4. При ролловере (`ticker_close ≠ ticker_open`) дополнительно закрывает остаток в
   старом контракте.
5. Защита от двойной записи — маркер
   `trade/state/{ticker_lc}_{trade_account}_{YYYY-MM-DD}.done` (в имени есть счёт,
   так что два счёта на одном тикере не конфликтуют).

### 5. Имена торговых скриптов — с суффиксом счёта
`trade_rts_tri_SPBFUT192yc_ebs.py` — суффикс кодирует номер торгового счёта
(`SPBFUT192yc`) и ключ аккаунта в `trade/settings.yaml` (`ebs` →
`accounts.ebs`). Это позволяет держать параллельные скрипты под разные счета без
рефакторинга. **Не переименовывать.**

### 6. Multi-account trade/settings.yaml
```yaml
accounts:
  iis: { trade_path: ..., trade_account: ..., rts: {quantity_*}, mix: {...} }
  ebs: { trade_path: ..., trade_account: ..., rts: {...}, mix: {...} }
```
Конкретный скрипт читает свой `account = trade_cfg['accounts']['<key>']`. Сохранять
эту структуру, даже если сейчас используется один счёт.

### 7. Защита тестовых прогонов через `prepare.py`
`prepare.py` — первый шаг `run_all.py`. Если текущее время < 21:00:00, он удаляет
за сегодня: файлы прогнозов (`<ticker>_embedding`, `<ticker>_sentiment`,
`<ticker>_combined`) и done-маркеры `trade/state/*.done`. Это позволяет
перезапустить пайплайн днём без лишних «уже существует — пропуск». После 21:00:00
скрипт ничего не трогает — это защита официальных рабочих результатов.

## Порядок в `run_all.py`

Hard-fail (останов пайплайна при ошибке):
0. `prepare.py`
1. `beget/sync_files.py`
2. `{rts,mix}/shared/download_minutes_to_db.py`
3. `{rts,mix}/shared/convert_minutes_to_days.py`
4. `{rts,mix}/shared/create_markdown_files.py`
5. `{rts,mix}/embedding/create_embedding.py`
6. `{rts,mix}/embedding/embedding_backtest.py`
7. `{rts,mix}/embedding/embedding_to_predict.py` ← инверсия применяется здесь
8. `{rts,mix}/sentiment/sentiment_analysis.py`
9. `{rts,mix}/sentiment/sentiment_to_predict.py`
10. `{rts,mix}/combine_predictions.py`
11. `trade/trade_rts_tri_SPBFUT192yc_ebs.py` ← встык
12. `trade/trade_mix_tri_SPBFUT192yc_ebs.py` ← встык, критично по времени

Soft-fail (логируется, пайплайн продолжается):
13. `{rts,mix}/embedding/embedding_analysis.py`
14. `{rts,mix}/sentiment/sentiment_group_stats.py`
15. `{rts,mix}/sentiment/sentiment_backtest.py`
16. `{rts,mix}/sentiment/sentiment_compare.py` ← последний блок, `mix/sentiment_compare.py` замыкает пайплайн

## Что НЕ переносим из pj14/pj16

- `analyze_explain.py` (pj14) — не нужен.
- `sentiment_walk_forward.py`, `sentiment_walk_forward_analysis.py` (pj16) — не нужны.

## Добавление нового тикера

Копируем `rts/` → `<new>/`, правим `<new>/settings.yaml` (`ticker`, `ticker_lc`,
пути котировок/md и фьючерсы в `ticker_close`/`ticker_open`) и `<new>/rules.yaml`.
В `trade/` добавляем копию торгового скрипта с новым префиксом тикера и суффиксом
счёта, например `trade_<new>_tri_<trade_account>_<key>.py`, соблюдая конвенцию
имени. В `trade/settings.yaml` добавляем секцию `<new>` в каждый `accounts.*`
(`quantity_open`, `quantity_close`). В `run_all.py` добавляем шаги нового тикера в
`HARD_STEPS` и `SOFT_STEPS` парно с уже существующими.
