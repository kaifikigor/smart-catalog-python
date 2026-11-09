import csv
import tempfile
import unittest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from catalog_cleaner import parse_money, parse_stock, process_catalogs, csv_safe


class CatalogCleanerTests(unittest.TestCase):
    def test_price(self):
        self.assertEqual(str(parse_money('1 200,50')), '1200.50')
        self.assertEqual(str(parse_money('1,200.50')), '1200.50')
        with self.assertRaises(ValueError):
            parse_money('-20')

    def test_stock(self):
        self.assertEqual(parse_stock('12'), 12)
        with self.assertRaises(ValueError):
            parse_stock('-1')

    def test_excel_formula_safety(self):
        self.assertEqual(csv_safe('=2+3'), "'=2+3")
        self.assertEqual(csv_safe('@test'), "'@test")

    def test_process_with_duplicate_and_bad_price(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            src, dest = root / 'in', root / 'out'
            src.mkdir()
            def save(name, rows):
                with (src / name).open('w', encoding='utf-8-sig', newline='') as f:
                    writer = csv.writer(f, delimiter=';')
                    writer.writerows(rows)
            heads = ['Артикул','Наименование','Категория','Цена','Остаток']
            save('a.csv', [heads, ['X1','Товар A','Группа','100','2'], ['X2','Товар B','Группа','0','3']])
            save('b.csv', [heads, ['X1','Товар A','Группа','100','2'], ['X3','Товар C','Группа','45,50','4']])
            result = process_catalogs(src, dest)
            self.assertEqual((result['products'], result['issues'], result['duplicates']), (2,2,1))
            self.assertTrue((dest/'report.html').exists())
            self.assertIn('Товаров в каталоге', (dest/'report.html').read_text(encoding='utf-8'))

    def test_reject_same_directory(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)
            (path/'test.csv').write_text('Артикул;Наименование;Категория;Цена;Остаток\n', encoding='utf-8')
            with self.assertRaises(ValueError):
                process_catalogs(path,path)

if __name__ == '__main__':
    unittest.main()
