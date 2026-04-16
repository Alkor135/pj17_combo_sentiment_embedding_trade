"""
Открывает HTML-отчёты pj17 в новом окне Google Chrome.
Собирает все html-файлы в rts/plots/ и открывает их одной командой.
"""

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PLOTS_DIR = ROOT / "rts" / "plots"

files = sorted(str(p) for p in PLOTS_DIR.glob("*.html"))

if not files:
    print(f"HTML-отчёты не найдены в {PLOTS_DIR}")
    raise SystemExit(0)

chrome = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
subprocess.Popen([chrome, "--new-window", *files])

for f in files:
    print(f"[OPEN] {f}")
