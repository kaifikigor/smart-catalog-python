"""Умный каталог: объединение и проверка CSV-таблиц из Excel.

Используются только модули стандартной библиотеки Python.
"""
from __future__ import annotations

import argparse
import csv
import html
import json
import re
from collections import Counter
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path

FIELDS = ["артикул", "наименование", "категория", "цена", "остаток"]
ALIASES = {
    "артикул": {"артикул", "sku", "код", "код товара"},
    "наименование": {"наименование", "название", "товар", "наименование товара"},
    "категория": {"категория", "группа", "категория товара"},
    "цена": {"цена", "стоимость", "цена руб", "цена, руб"},
    "остаток": {"остаток", "количество", "остаток шт", "кол-во"},
}


@dataclass
class Product:
    sku: str
    name: str
    category: str
    price: Decimal
    stock: int
    source: str


def normalize_header(name: str) -> str:
    return re.sub(r"\s+", " ", name.strip().replace("ё", "е").lower())


def canonical_columns(headers: list[str]) -> dict[str, str]:
    detected: dict[str, str] = {}
    for h in headers:
        key = normalize_header(h)
        for standard, aliases in ALIASES.items():
            if key in aliases and standard not in detected:
                detected[standard] = h
    missing = [field for field in FIELDS if field not in detected]
    if missing:
        raise ValueError("Отсутствуют обязательные колонки: " + ", ".join(missing))
    return detected


def read_csv(path: Path) -> tuple[list[dict[str, str]], dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        sample = f.read(4096)
        f.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=";,")
            delimiter = dialect.delimiter
        except csv.Error:
            delimiter = ";" if sample.count(";") >= sample.count(",") else ","
        reader = csv.DictReader(f, delimiter=delimiter)
        if reader.fieldnames is None:
            raise ValueError("Файл пустой или не содержит заголовков")
        mapping = canonical_columns(reader.fieldnames)
        return list(reader), mapping


def parse_money(raw: str) -> Decimal:
    value = str(raw).strip().replace("\u00a0", "").replace(" ", "").replace("₽", "").replace("руб.", "").replace("руб", "")
    if "," in value and "." in value:
        if value.rfind(",") > value.rfind("."):
            value = value.replace(".", "").replace(",", ".")
        else:
            value = value.replace(",", "")
    else:
        value = value.replace(",", ".")
    try:
        amount = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError("Некорректная цена") from exc
    if not amount.is_finite() or amount <= 0:
        raise ValueError("Цена должна быть больше нуля")
    return amount.quantize(Decimal("0.01"))


def parse_stock(raw: str) -> int:
    text = str(raw).strip().replace(" ", "")
    if not re.fullmatch(r"\d+", text):
        raise ValueError("Остаток должен быть целым неотрицательным числом")
    return int(text)


def csv_safe(value: object) -> str:
    text = str(value)
    # При открытии CSV в Excel запрещаем исполнение формул, пришедших из сторонних данных.
    if text.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + text
    return text


def write_csv(path: Path, columns: list[str], rows: list[list[object]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(columns)
        for row in rows:
            writer.writerow([csv_safe(v) for v in row])


def money_str(v: Decimal) -> str:
    return f"{v:.2f}"


def make_html(result: dict, products: list[Product], errors: list[dict]) -> str:
    def escape(text: object) -> str:
        return html.escape(str(text))
    total_value = sum((p.price * p.stock for p in products), Decimal("0"))
    by_cat: dict[str, list[Product]] = {}
    for p in products:
        by_cat.setdefault(p.category, []).append(p)
    cat_rows = "\n".join(
        f"<tr><td>{escape(cat)}</td><td>{len(items)}</td><td>{sum(p.stock for p in items)}</td>"
        f"<td>{escape(money_str(sum((p.price * p.stock for p in items), Decimal('0'))))} ₽</td></tr>"
        for cat, items in sorted(by_cat.items())
    ) or '<tr><td colspan="4">Нет подходящих товаров</td></tr>'
    error_rows = "\n".join(
        f"<tr><td>{escape(e['файл'])}</td><td>{escape(e['строка'])}</td><td>{escape(e['артикул'])}</td>"
        f"<td>{escape(e['причина'])}</td></tr>" for e in errors[:40]
    ) or '<tr><td colspan="4">Ошибок не найдено</td></tr>'
    return f'''<!DOCTYPE html>
<html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Умный каталог — отчет по данным</title>
<style>
:root {{font-family:Inter,Arial,sans-serif;color:#18302d;background:#f6f8f7;}}
*{{box-sizing:border-box}} body{{margin:0}} .wrap{{max-width:1050px;margin:auto;padding:42px 22px 80px}}
.top{{display:flex;align-items:center;gap:12px;margin-bottom:38px}} .logo{{width:39px;height:39px;border-radius:12px;background:#16665c;color:white;display:grid;place-items:center;font-weight:800;font-size:24px}}
small,.muted{{color:#71847e}} h1{{font-size:clamp(30px,4vw,46px);letter-spacing:-.045em;margin:0 0 10px}} h2{{font-size:22px;margin:30px 0 17px}}
.lead{{color:#657973;margin:0 0 34px;line-height:1.6}}.kpis{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px}}
.kpi,.panel{{background:#fff;border:1px solid #e4ebe8;border-radius:18px;box-shadow:0 6px 25px rgba(22,60,49,.035)}}
.kpi{{padding:24px 20px}}.kpi strong{{display:block;font-size:30px;letter-spacing:-.03em;margin-top:10px}}.kpi .name{{font-size:13px;color:#72817c}}
.panel{{padding:22px;overflow-x:auto}}table{{width:100%;border-collapse:collapse;text-align:left;font-size:14px;min-width:540px}}
th{{background:#f4f7f5;color:#52675e;font-weight:650}} td,th{{padding:15px 13px;border-bottom:1px solid #edf1ef}}tr:last-child td{{border-bottom:0}}
.pill{{display:inline-block;border-radius:8px;background:#e0f4ec;color:#116a50;padding:7px 11px;font-size:12px;font-weight:700}}
.foot{{margin-top:30px;font-size:13px;color:#7b8985;line-height:1.7}}.accent{{color:#167364}}
@media(max-width:720px){{.wrap{{padding-top:28px}}.kpis{{grid-template-columns:repeat(2,1fr)}}.kpi{{padding:18px 15px}}.kpi strong{{font-size:25px}}}}
</style></head><body><main class="wrap"><div class="top"><span class="logo">✓</span><div><b>УМНЫЙ КАТАЛОГ</b><br><small>Python · обработка таблиц</small></div></div>
<div class="pill">Демонстрационный отчет</div><h1>Порядок в данных.<br><span class="accent">Без ручной проверки.</span></h1>
<p class="lead">Объединение CSV-файлов, проверка ошибок и повторяющихся артикулов. Все расчеты выполнены программой.</p>
<section class="kpis"><div class="kpi"><span class="name">Исходных файлов</span><strong>{result['files']}</strong></div>
<div class="kpi"><span class="name">Товаров в каталоге</span><strong>{len(products)}</strong></div>
<div class="kpi"><span class="name">Найдено ошибок и дублей</span><strong>{len(errors)}</strong></div>
<div class="kpi"><span class="name">Стоимость остатков</span><strong>{money_str(total_value)} ₽</strong></div></section>
<h2>Категории товаров</h2><div class="panel"><table><thead><tr><th>Категория</th><th>Позиций</th><th>Остаток, шт.</th><th>Стоимость остатков</th></tr></thead><tbody>{cat_rows}</tbody></table></div>
<h2>Обнаруженные проблемы</h2><div class="panel"><table><thead><tr><th>Файл</th><th>Строка</th><th>Артикул</th><th>Описание ошибки</th></tr></thead><tbody>{error_rows}</tbody></table></div>
<p class="foot">Отчет создан локально, без передачи данных сторонним сервисам. Цены и остатки в примере вымышлены.\n<br>Стоимость остатков рассчитывается как цена × количество; это не бухгалтерская оценка запасов.</p>
</main></body></html>'''


def process_catalogs(input_dir: str | Path, output_dir: str | Path) -> dict:
    src, dest = Path(input_dir), Path(output_dir)
    if not src.is_dir():
        raise ValueError("Папка с исходными файлами не найдена")
    dest.mkdir(parents=True, exist_ok=True)
    files = sorted(src.glob("*.csv"), key=lambda p: p.name.casefold())
    if not files:
        raise ValueError("В выбранной папке нет CSV-файлов")
    # Запрещаем записывать результаты в исходную папку, чтобы не обработать их снова.
    if src.resolve() == dest.resolve():
        raise ValueError("Папка результата должна отличаться от папки исходных файлов")
    products: dict[str, Product] = {}
    errors: list[dict] = []
    total_rows = 0
    for path in files:
        try:
            records, mapping = read_csv(path)
        except (ValueError, UnicodeError, csv.Error) as exc:
            errors.append({"файл": path.name, "строка": "—", "артикул": "—", "причина": f"Ошибка файла: {exc}"})
            continue
        for line, row in enumerate(records, start=2):
            if not row or all(not str(v or "").strip() for v in row.values()):
                continue
            total_rows += 1
            def cell(col: str) -> str:
                return str(row.get(mapping[col], "") or "").strip()
            sku = re.sub(r"\s+", "", cell("артикул")).upper()
            try:
                if not sku:
                    raise ValueError("Пустой артикул")
                name, category = cell("наименование"), cell("категория")
                if not name or not category:
                    raise ValueError("Нет наименования или категории")
                price = parse_money(cell("цена"))
                stock = parse_stock(cell("остаток"))
                if sku in products:
                    other = products[sku]
                    raise ValueError(f"Повтор артикула: уже встречался в файле {other.source}")
                products[sku] = Product(sku, name, category, price, stock, path.name)
            except ValueError as exc:
                errors.append({"файл": path.name, "строка": line, "артикул": sku or "—", "причина": str(exc)})
    selected = sorted(products.values(), key=lambda p: (p.category.casefold(), p.name.casefold(), p.sku))
    write_csv(dest / "catalog.csv", ["Артикул", "Наименование", "Категория", "Цена, руб.", "Остаток, шт.", "Источник"],
              [[p.sku, p.name, p.category, money_str(p.price), p.stock, p.source] for p in selected])
    write_csv(dest / "errors.csv", ["Файл", "Строка", "Артикул", "Причина"],
              [[e["файл"], e["строка"], e["артикул"], e["причина"]] for e in errors])
    summary = {"files": len(files), "input_rows": total_rows, "products": len(selected), "issues": len(errors),
               "duplicates": sum("Повтор артикула" in e["причина"] for e in errors),
               "stock_value_rub": money_str(sum((p.price * p.stock for p in selected), Decimal("0")))}
    (dest / "report.html").write_text(make_html(summary, selected, errors), encoding="utf-8")
    (dest / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def main() -> None:
    root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description="Объединяет CSV-каталоги, ищет дубли и ошибки")
    parser.add_argument("--input", default=str(root / "example_input"), help="Папка с CSV-файлами")
    parser.add_argument("--output", default=str(root / "example_output"), help="Папка с отчетом")
    args = parser.parse_args()
    result = process_catalogs(args.input, args.output)
    print("Готово!", json.dumps(result, ensure_ascii=False, indent=2))
    print("Результаты:", Path(args.output).resolve())


if __name__ == "__main__":
    main()
