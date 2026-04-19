# AGENTS.md Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a compact Russian-language `AGENTS.md` that becomes the primary AI-oriented guide for this repository and reflects the current project structure better than `CLAUDE.md`.

**Architecture:** Create a single repo-root documentation file with operational guidance only. Reuse verified repository facts from `CLAUDE.md`, `README.md`, `run_report.py`, and `buhinvest_analize/`, while avoiding stale or overly detailed narrative.

**Tech Stack:** Markdown, Python repository conventions, unittest-based verification

---

### Task 1: Create the repo-level AGENTS guide

**Files:**
- Create: `AGENTS.md`
- Reference: `CLAUDE.md`
- Reference: `README.md`
- Reference: `run_all.py`
- Reference: `run_report.py`
- Reference: `buhinvest_analize/README.md`

- [ ] **Step 1: Write the guide content**

```md
# AGENTS.md

Этот файл — основной репозиторный гайд для AI-ассистентов, работающих в
`pj17_combo_sentiment_embedding_trade`.

Если `AGENTS.md` расходится с `CLAUDE.md` или другими AI-заметками, ассистенту
следует опираться в первую очередь на `AGENTS.md`, а остальные файлы использовать
как дополнительный контекст.

## Что это за проект

Репозиторий состоит из нескольких активных зон:

- мульти-тиковый пайплайн для анализа и торговли фьючерсами MOEX;
- общий торговый слой в `trade/`;
- отдельное направление отчётности и аналитики в `buhinvest_analize/`;
- серверные и синхронизационные утилиты в `beget/`.

## Основные точки входа

- `run_all.py` — главный end-to-end пайплайн по тикерам;
- `prepare.py` — очистка дневных артефактов и housekeeping перед повторным прогоном;
- `run_report.py` — оркестрация генерации html-отчётов без торгового шага;
- `buhinvest_analize/pl_buhinvest_interactive.py` — интерактивная отчётность по счёту;
- `tests/test_prepare.py` и `tests/test_buhinvest_reports.py` — базовые локальные проверки.

## Карта проекта

### Тикерные ветки

Папки `rts/`, `mix/`, `br/`, `gold/`, `ng/`, `si/`, `spyf/` построены по похожему
шаблону и обычно содержат:

- `settings.yaml`;
- `rules.yaml`;
- `shared/`;
- `embedding/`;
- `sentiment/`;
- `combine_predictions.py`.

Не каждый тикер участвует в живой торговле. Часть веток используется только для
бэктеста, аналитики и сравнения моделей.

### Торговый слой

Папка `trade/` содержит общую механику исполнения:

- target-state торговые скрипты `trade_<ticker>_combo_<trade_account>_<key>.py`;
- `settings.yaml` с мульти-аккаунт структурой;
- чтение текущих позиций через `read_positions.py`;
- экспортёры QUIK и состояние в `state/`.

### Отчёты Buhinvest

Папка `buhinvest_analize/` — это отдельная активная часть репозитория, а не
случайный вспомогательный скрипт. Изменения в ней не должны автоматически
считаться изменениями ночного торгового пайплайна.

## Правила безопасной работы

- Не менять торговую семантику `run_all.py`, `combine_predictions.py` и
  `trade/*.py` без явной задачи на это.
- Не ломать target-state модель торговли без проверки всей цепочки:
  прогноз -> combined -> чтение позиции -> `.tri`.
- Сохранять конвенцию имён торговых скриптов:
  `trade_<ticker>_combo_<trade_account>_<key>.py`.
- Не выносить загрузку конфигурации в общий helper, если задача явно этого не требует:
  в проекте принят self-contained подход, и скрипты обычно читают свой YAML сами.
- Не трогать `beget/`, если задача не относится к RSS-скрапингу, серверной логике
  или синхронизации файлов.
- Если задача относится к `buhinvest_analize/`, держать изменения локальными и не
  притягивать в них торговый пайплайн без необходимости.

## Конфиги и соглашения

- Основные конфиги по тикерам хранятся в `<ticker>/settings.yaml` и `<ticker>/rules.yaml`.
- Во многих скриптах конфиг читается инлайн, с мержем `common` и профильной секции.
- Для торговых объёмов и путей используется `trade/settings.yaml`.
- Перед изменением логики важно проверить, участвует ли конкретный тикер в live-trade
  или только в offline-анализе.

## Предпочтительная проверка после изменений

Если затронуты только docs или локальная аналитика, предпочитать узкую проверку.

Базовая локальная команда:

`python -m unittest tests.test_prepare tests.test_buhinvest_reports`

Если изменения касаются только `buhinvest_analize`, сначала искать короткий
локальный сценарий проверки, а не запускать весь `run_all.py`.

Полный end-to-end прогон может зависеть от внешних систем и данных:

- Ollama;
- QUIK и `.tri`-интеграции;
- внешние Excel-файлы;
- локальные/серверные данные новостей и котировок.

Поэтому ассистент не должен заявлять о полной проверке пайплайна без явного
фактического запуска.
```

- [ ] **Step 2: Create `AGENTS.md` with the approved content**

Run: apply patch to add `AGENTS.md`
Expected: file exists at repo root

- [ ] **Step 3: Review the file after creation**

Run: `Get-Content AGENTS.md`
Expected: the file is readable, in Russian, and reflects the current repo areas

- [ ] **Step 4: Run focused verification**

Run: `python -m unittest tests.test_prepare tests.test_buhinvest_reports`
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add AGENTS.md docs/superpowers/specs/2026-04-19-agents-md-design.md docs/superpowers/plans/2026-04-19-agents-md-create.md
git commit -m "docs: add repo-level AGENTS guide"
```
