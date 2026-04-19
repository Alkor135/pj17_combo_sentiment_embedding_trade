# Trade Script Combo Rename Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rename the RTS and MIX trade scripts from `tri` to `combo` and update all repository references so the trading pipeline keeps working unchanged.

**Architecture:** Keep the trading logic intact and limit the change surface to filenames, direct path references, and human-facing naming strings tied to the strategy label. Verify success by searching for old filenames after the rename and confirming the new filenames are present in orchestrator and docs.

**Tech Stack:** Python, PowerShell, ripgrep, Markdown documentation

---

### Task 1: Rename runtime entrypoints and update internal naming

**Files:**
- Modify: `trade/trade_rts_combo_SPBFUT192yc_ebs.py`
- Modify: `trade/trade_mix_combo_SPBFUT192yc_ebs.py`

- [ ] **Step 1: Rename the two trade entrypoint files**

```powershell
Move-Item -LiteralPath trade\trade_rts_tri_SPBFUT192yc_ebs.py -Destination trade\trade_rts_combo_SPBFUT192yc_ebs.py
Move-Item -LiteralPath trade\trade_mix_tri_SPBFUT192yc_ebs.py -Destination trade\trade_mix_combo_SPBFUT192yc_ebs.py
```

- [ ] **Step 2: Update log filename prefixes from `tri` to `combo` inside both scripts**

```python
log_file = log_path / f"trade_{ticker_lc}_combo_{timestamp}.txt"
cleanup_old_logs(log_path, prefix=f"trade_{ticker_lc}_combo")
```

- [ ] **Step 3: Keep the trading behavior unchanged**

```python
account = trade_cfg['accounts']['ebs']
trade_account = account['trade_account']
quantity_open = int(account[ticker_lc].get('quantity_open', 1))
```

### Task 2: Update orchestrator and documentation references

**Files:**
- Modify: `run_all.py`
- Modify: `CLAUDE.md`
- Modify: `README.md`

- [ ] **Step 1: Replace runtime paths in the orchestrator**

```python
ROOT / "trade" / "trade_rts_combo_SPBFUT192yc_ebs.py",
ROOT / "trade" / "trade_mix_combo_SPBFUT192yc_ebs.py",
```

- [ ] **Step 2: Update explanatory text to reflect the `combo` strategy label**

```text
trade/trade_rts_combo_SPBFUT192yc_ebs.py
trade/trade_mix_combo_SPBFUT192yc_ebs.py
trade_<ticker>_combo_<trade_account>_<key>.py
```

- [ ] **Step 3: Preserve the account suffix convention in docs**

```text
Суффикс _<trade_account>_<key> по-прежнему кодирует номер торгового счёта и ключ аккаунта.
```

### Task 3: Verify the rename

**Files:**
- Test: `trade/trade_rts_combo_SPBFUT192yc_ebs.py`
- Test: `trade/trade_mix_combo_SPBFUT192yc_ebs.py`
- Test: `run_all.py`
- Test: `CLAUDE.md`
- Test: `README.md`

- [ ] **Step 1: Search for stale `tri` trade-script references**

Run: `rg -n --glob '!/.venv/**' --glob '!/.tmp/**' --glob '!**/__pycache__/**' "trade_(rts|mix)_tri_SPBFUT192yc_ebs|trade_<ticker>_tri_<trade_account>_<key>.py|trade_\{ticker\}_tri_\{trade_account\}_\{key\}\.py" run_all.py CLAUDE.md README.md trade`
Expected: no matches

- [ ] **Step 2: Search for the new `combo` references**

Run: `rg -n --glob '!/.venv/**' --glob '!/.tmp/**' --glob '!**/__pycache__/**' "trade_(rts|mix)_combo_SPBFUT192yc_ebs|trade_<ticker>_combo_<trade_account>_<key>.py|trade_\{ticker\}_combo_\{trade_account\}_\{key\}\.py" run_all.py CLAUDE.md README.md trade`
Expected: matches in `run_all.py`, `CLAUDE.md`, `README.md`, and the renamed trade scripts

- [ ] **Step 3: Review git status for the expected rename-only change set**

Run: `git status --short`
Expected: two renamed trade scripts plus the intended doc/code edits
