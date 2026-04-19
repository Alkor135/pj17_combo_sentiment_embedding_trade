"""
Генерация двух HTML-отчетов по данным Buhinvest:
- Plotly-отчет с расширенной аналитикой
- QuantStats tearsheet на реальной доходности счета
"""

from pathlib import Path

try:
    from buhinvest_analize.buhinvest_reports import generate_reports
except ModuleNotFoundError:
    from buhinvest_reports import generate_reports


SAVE_PATH = Path(__file__).parent
FILE_PATH = Path(r"C:\Users\Alkor\gd\ВТБ_ЕБС_SPBFUT192yc.xlsx")


def main() -> None:
    plotly_output, qs_output = generate_reports(FILE_PATH, SAVE_PATH)
    print(f"Интерактивный отчёт сохранён: {plotly_output}")
    print(f"QuantStats отчёт сохранён: {qs_output}")


if __name__ == "__main__":
    main()
