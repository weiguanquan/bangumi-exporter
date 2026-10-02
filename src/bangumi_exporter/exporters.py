# -*- coding: utf-8 -*-
"""五种导出格式实现：CSV / JSON / Excel(.xlsx) / Markdown / HTML。"""

import csv
import html as _html_mod
import json
import zipfile

from .constants import FIELD_NAMES


def export_csv(rows, path):
    # flatten_item 会额外带上「封面 / 条目链接」两个展示用字段，
    # 它们不在 FIELD_NAMES 中；DictWriter 默认会对多余字段抛 ValueError，
    # 因此这里显式忽略多余键，只写出 FIELD_NAMES 定义的列。
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=FIELD_NAMES,
                                extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def export_json(rows, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)


def export_markdown(rows, path):
    with open(path, "w", encoding="utf-8") as f:
        f.write("| " + " | ".join(FIELD_NAMES) + " |\n")
        f.write("|" + "---|" * len(FIELD_NAMES) + "\n")
        for r in rows:
            cells = [
                str(r.get(k, "")).replace("|", "\\|").replace("\n", "<br>")
                for k in FIELD_NAMES
            ]
            f.write("| " + " | ".join(cells) + " |\n")


def _is_number(v):
    if isinstance(v, bool):
        return False
    if isinstance(v, (int, float)):
        return True
    if isinstance(v, str):
        s = v.strip()
        if not s:
            return False
        try:
            float(s)
            return True
        except ValueError:
            return False
    return False


def _xml_escape(s):
    s = str(s)
    s = "".join(ch for ch in s if ch in "\t\n\r" or ord(ch) >= 0x20)
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;").replace("'", "&apos;"))


def export_xlsx(rows, path):
    """纯标准库生成 .xlsx（zip + XML），无需 openpyxl。"""
    def col_name(idx):
        n = idx + 1
        s = ""
        while n:
            n, rem = divmod(n - 1, 26)
            s = chr(65 + rem) + s
        return s

    def cell(ref, value):
        if _is_number(value):
            return f'<c r="{ref}"><v>{_xml_escape(value)}</v></c>'
        return (f'<c r="{ref}" t="inlineStr">'
                f'<is><t>{_xml_escape(value)}</t></is></c>')

    rows_xml = []
    header_cells = "".join(cell(col_name(i), h) for i, h in enumerate(FIELD_NAMES))
    rows_xml.append(f'<row r="1">{header_cells}</row>')
    for ri, r in enumerate(rows, start=2):
        cells = "".join(cell(col_name(i), r.get(k, ""))
                        for i, k in enumerate(FIELD_NAMES))
        rows_xml.append(f'<row r="{ri}">{cells}</row>')
    sheet_data = "".join(rows_xml)

    sheet_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<sheetData>{sheet_data}</sheetData></worksheet>'
    )
    workbook_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheets><sheet name="收藏" sheetId="1" r:id="rId1"/></sheets></workbook>'
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        '</Types>'
    )
    rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="xl/workbook.xml"/>'
        '</Relationships>'
    )
    wb_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
        'Target="worksheets/sheet1.xml"/>'
        '</Relationships>'
    )

    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", content_types)
        z.writestr("_rels/.rels", rels)
        z.writestr("xl/workbook.xml", workbook_xml)
        z.writestr("xl/_rels/workbook.xml.rels", wb_rels)
        z.writestr("xl/worksheets/sheet1.xml", sheet_xml)


def _cell_text(key, value):
    """表格单元格的显示文本。

    数据本身不改（CSV / JSON / Excel 仍是原始值），只在 HTML 展示层：
      - 「看到第几集」为 0 / 空 显示成 `-`（0 表示还没记录进度，
        不是「看了 0 集」，直接写 0 会让人以为程序算错了）
      - 其它空值也显示成 `-`，避免出现整片空白单元格
    """
    s = "" if value is None else str(value).strip()
    if key == "看到第几集":
        if not s or s in ("0", "0.0"):
            return "-"
        return s
    return s if s else "-"


def export_html(rows, path, title="Bangumi 收藏导出"):
    """带关键字过滤与点击表头排序的 HTML 表格。"""
    title_esc = _html_mod.escape(title)
    thead = "".join(f"<th>{_html_mod.escape(k)}</th>" for k in FIELD_NAMES)
    body_rows = []
    for r in rows:
        tds = "".join(
            f"<td>{_html_mod.escape(_cell_text(k, r.get(k, '')))}</td>"
            for k in FIELD_NAMES)
        body_rows.append(f"<tr>{tds}</tr>")
    body = "\n".join(body_rows)

    css = """
 body { font-family: -apple-system, "Segoe UI", "Microsoft YaHei", sans-serif; margin: 16px; }
 table { border-collapse: collapse; width: 100%; font-size: 14px; }
 th, td { border: 1px solid #ddd; padding: 6px 8px; text-align: left; }
 th { background: #f5f5f5; cursor: pointer; position: sticky; top: 0; user-select: none; }
 tr:nth-child(even) { background: #fafafa; }
 tr:hover { background: #eef5ff; }
 input { margin: 8px 0; padding: 6px; width: 260px; }
"""
    js = """
(function () {
  var q = document.getElementById('q');
  var tbl = document.getElementById('tbl');
  var tbody = tbl.tBodies[0];
  q.addEventListener('input', function () {
    var v = q.value.toLowerCase();
    for (var i = 0; i < tbody.rows.length; i++) {
      tbody.rows[i].style.display =
        tbody.rows[i].textContent.toLowerCase().indexOf(v) >= 0 ? '' : 'none';
    }
  });
  var ths = tbl.querySelectorAll('th');
  ths.forEach(function (th, idx) {
    th.addEventListener('click', function () {
      var rows = Array.prototype.slice.call(tbody.rows);
      var asc = th.getAttribute('data-asc') !== '1';
      ths.forEach(function (h) { h.removeAttribute('data-asc'); });
      th.setAttribute('data-asc', asc ? '1' : '0');
      rows.sort(function (a, b) {
        var av = a.cells[idx].textContent.trim();
        var bv = b.cells[idx].textContent.trim();
        var an = parseFloat(av), bn = parseFloat(bv);
        if (!isNaN(an) && !isNaN(bn)) { av = an; bv = bn; }
        return (av < bv ? -1 : (av > bv ? 1 : 0)) * (asc ? 1 : -1);
      });
      rows.forEach(function (r) { tbody.appendChild(r); });
    });
  });
})();
"""
    doc = (
        "<!DOCTYPE html>\n<html lang=\"zh\"><head><meta charset=\"utf-8\">"
        f"<title>{title_esc}</title><style>{css}</style></head><body>"
        f"<h2>{title_esc}</h2>"
        '<input id="q" placeholder="输入关键字过滤...">'
        f'<table id="tbl"><thead><tr>{thead}</tr></thead><tbody>{body}</tbody></table>'
        f"<script>{js}</script></body></html>"
    )
    with open(path, "w", encoding="utf-8") as f:
        f.write(doc)


EXPORTERS = {
    "csv": export_csv,
    "json": export_json,
    "excel": export_xlsx,
    "markdown": export_markdown,
    "html": export_html,
}