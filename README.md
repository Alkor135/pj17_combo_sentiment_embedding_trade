# pj17_combo_sentiment_embedding_trade

Автоматизированная торговля фьючерсами MOEX (**RTS** и **MIX**), объединяющая две
независимые стратегии в один сигнал через **согласованное голосование**:

- **Embedding** — векторные эмбеддинги новостей (Ollama: `embeddinggemma` /
  `bge-m3` / `qwen3-embedding`) + поиск похожего исторического дня и предсказание
  направления по его `open→open`.
- **Sentiment** — оценка новостей локальной LLM (Ollama: `gemma3:12b`), перевод в
  сигнал по правилам `rules.yaml` (follow / invert / skip).

Итоговое направление рождается только при согласии обеих стратегий (`up+up` → up,
`down+down` → down, иначе skip). На его основе target-state торговый скрипт пишет
заявки в QUIK через `.tri`-файл.

## Пайплайн одним запуском

```bash
python run_all.py
```

`run_all.py` — единственная точка входа. Регистрируется в Windows Task Scheduler
на 21:00:05 ежедневно (сразу после открытия новой сессии MOEX):

```cmd
schtasks /Create /SC DAILY /ST 21:00:05 /TN "pj17_run_all" ^
  /TR "python C:\Users\Alkor\VSCode\pj17_combo_sentiment_embedding_trade\run_all.py"
```

Этапы идут парами RTS→MIX. До и включая торговые скрипты — hard-fail (авария
останавливает пайплайн). Аналитика после торговли — soft-fail.

## Структура

- `run_all.py` — основной оркестратор (RTS + MIX), точка входа для ежедневного запуска.
- `run_other.py` — оркестратор «не основных» тикеров (BR, GOLD, NG, Si, SPYF) —
  только бэктест и аналитика, без торговли.
- `run_report.py` — оркестратор построения HTML-отчётов поверх уже готовых
  минуток/дневок/md (этапы 4–9 hard-fail, торговые скрипты не запускаются).
- `prepare.py` — очистка сегодняшних прогнозов и done-маркеров при тестовом
  прогоне до 21:00, плюс housekeeping: `trade/state/*.done` (хранит не более
  10 календарных дней и не более 10 файлов) и `log/prepare_*.txt` (оставляет
  3 самых свежих).
- `beget/` — сбор RSS-новостей с удалённого сервера.
- `rts/`, `mix/` — ветки по тикерам, каждая самодостаточна:
  - `settings.yaml` — единый конфиг с секциями `common / embedding / sentiment /
    combined`.
  - `rules.yaml` — правила перевода sentiment→сигнал.
  - `shared/` — загрузка котировок, генерация markdown-сводок новостей.
  - `embedding/` — кэш эмбеддингов, бэктест, прогноз, аналитика.
  - `sentiment/` — LLM-оценка, прогноз, бэктест, сравнение стратегий.
  - `combine_predictions.py` — согласованное голосование.
- `trade/` — общий торговый модуль:
  - `trade_<ticker>_combo_<trade_account>_<key>.py` — target-state скрипт на QUIK для combo-стратегии.
  - `read_positions.py` — чтение текущих позиций (lua-экспорт + yaml-override).
  - `quik_export_*.lua` — минутные котировки и позиции из QUIK.
  - `settings.yaml` — мульти-счёт (`accounts.iis`, `accounts.ebs`).
- `html_open.py` — открытие всех HTML-отчётов в Chrome одним окном.
- `buhinvest_analize/` — анализ реального P/L из выгрузки брокера Buhinvest
  (XLSX → PNG/HTML). Независимо от торгового пайплайна.
- `tests/` — unit-тесты (`prepare.py`, `buhinvest_reports.py`).
- `log/` — логи корневых оркестраторов (`run_all`, `run_other`, `run_report`, `prepare`).
- `requirements.txt` — зависимости обоих пайплайнов.

## Установка

```bash
pip install -r requirements.txt
```

Дополнительно: установленный и запущенный **Ollama**
(`http://localhost:11434`) с моделями `embeddinggemma` (или другой embedding-моделью
из `settings.yaml`) и `gemma3:12b` (или другой моделью из `sentiment_model`).
QUIK с доступом к `algotrade/input.tri` и включёнными lua-скриптами
`quik_export_minutes.lua` / `quik_export_positions.lua`.

## Запуск тестового прогона днём

До 21:00 можно безопасно запускать `run_all.py` вручную — `prepare.py` удалит
сегодняшние прогнозы и done-маркеры, чтобы пайплайн отработал заново. Реальные
результаты создаются только после 21:00:00 (ночной регламент защищён). Старые
`.done`-маркеры в `trade/state/` также автоматически подчищаются.

## Документация для ИИ-ассистента

Подробности архитектуры, конвенций именования и правил изменения кода — в
[`CLAUDE.md`](CLAUDE.md).
