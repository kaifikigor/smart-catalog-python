"""Простое графическое окно для запуска Умного каталога без командной строки."""
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import webbrowser

from catalog_cleaner import process_catalogs

ROOT = Path(__file__).resolve().parent


def main() -> None:
    window = tk.Tk()
    window.title("Умный каталог · обработка таблиц")
    window.geometry("680x390")
    window.minsize(570, 350)
    input_var = tk.StringVar(value=str(ROOT / "example_input"))
    output_var = tk.StringVar(value=str(ROOT / "example_output"))
    status = tk.StringVar(value="Готово к обработке. Можно использовать демонстрационные данные.")

    frame = ttk.Frame(window, padding=24)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text="Умный каталог", font=("Arial", 23, "bold")).pack(anchor="w", pady=(0, 5))
    ttk.Label(frame, text="Соберем CSV-таблицы в единый каталог и проверим данные.").pack(anchor="w", pady=(0, 24))

    def chooser(var):
        directory = filedialog.askdirectory(initialdir=var.get() if Path(var.get()).exists() else str(ROOT))
        if directory:
            var.set(directory)

    for label, var in [("Папка с CSV-файлами", input_var), ("Папка для готового отчета", output_var)]:
        ttk.Label(frame, text=label).pack(anchor="w", pady=(0, 5))
        row = ttk.Frame(frame)
        row.pack(fill="x", pady=(0, 15))
        ttk.Entry(row, textvariable=var).pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="Выбрать...", command=lambda v=var: chooser(v)).pack(side="left", padx=(8, 0))

    def run():
        try:
            result = process_catalogs(input_var.get(), output_var.get())
        except Exception as exc:
            messagebox.showerror("Не удалось обработать", str(exc))
            status.set("Ошибка обработки. Проверьте исходные файлы.")
            return
        status.set(f"Готово! Товаров: {result['products']}, проблем: {result['issues']}.")
        if messagebox.askyesno("Отчет готов", f"Обработано файлов: {result['files']}\n"
                               f"Товаров: {result['products']}\nПроблемных строк: {result['issues']}\n\nОткрыть отчет в браузере?"):
            webbrowser.open((Path(output_var.get()) / "report.html").resolve().as_uri())

    ttk.Button(frame, text="Обработать таблицы", command=run).pack(anchor="w", pady=(2, 17))
    ttk.Label(frame, textvariable=status, foreground="#1d6853", wraplength=580).pack(anchor="w")
    window.mainloop()


if __name__ == "__main__":
    main()
