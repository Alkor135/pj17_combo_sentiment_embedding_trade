"""
Открывает HTML-отчёты проекта pj17 в новом окне Google Chrome.
Собирает все html-файлы из rts/plots/ и mix/plots/ и других папок и открывает их одной командой.
"""

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PLOTS_DIRS = [
    ROOT / "rts" / "plots",
    ROOT / "mix" / "plots",
    ROOT / "br" / "plots",
    ROOT / "ng" / "plots",
    ROOT / "si" / "plots",
    ROOT / "gold" / "plots",
    ROOT / "spyf" / "plots",
]

files = []
for plots_dir in PLOTS_DIRS:
    files.extend(sorted(str(p) for p in plots_dir.glob("*.html")))

if not files:
    print("HTML-отчёты не найдены в указанных папках")
    raise SystemExit(0)

chrome = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
subprocess.Popen([chrome, "--new-window", *files])

for f in files:
    print(f"[OPEN] {f}")
