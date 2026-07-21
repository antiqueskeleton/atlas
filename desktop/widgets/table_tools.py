"""
App-wide table ergonomics (user request 2026-07-21):
- every column user-resizable (former Stretch columns become draggable with
  an initial width; the last section stretches to fill leftover space)
- clicking a header sorts A-Z, clicking again Z-A (indicator arrow shown)
- numeric-aware ordering: cells that read as numbers ("1,234", "95%",
  "$1,399.99", "144/144", "4.7 ★") sort by VALUE — 2 before 100, never
  the lexical "1, 100, 101, 2" ordering. Blanks and "—" always sort last.

Deliberately NOT Qt's setSortingEnabled: that mode re-sorts DURING
programmatic repopulation (scrambling setItem row targets at every refresh
call site in the app) and compares by display text only. A manual
header-click reorder needs zero changes at any populate site.
"""
import re

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHeaderView, QTableWidget

_NUM_RE = re.compile(r"^-?\d+(?:\.\d+)?")


def sort_key(text) -> tuple:
    """(group, number, text): group 0 = numeric cells (by value),
    group 1 = text cells (case-insensitive), group 2 = blank/em-dash last.
    Pure and separately testable."""
    t = (str(text) if text is not None else "").strip()
    if t in ("", "—", "-"):
        return (2, 0.0, "")
    clean = t.replace(",", "").replace("$", "").replace("%", "") \
             .replace("★", "").strip()
    m = _NUM_RE.match(clean)
    if m:
        rest = clean[m.end():]
        # a pure number, or number-led cells like "144/144" / "4.7 (10,902)"
        if rest == "" or rest[0] in "/ (":
            return (0, float(m.group(0)), t.lower())
    return (1, 0.0, t.lower())


def make_sortable(table: QTableWidget):
    """Make one table's columns resizable and its headers click-to-sort."""
    header = table.horizontalHeader()
    for col in range(table.columnCount()):
        if header.sectionResizeMode(col) != QHeaderView.Interactive:
            width = max(header.sectionSize(col), 90)
            header.setSectionResizeMode(col, QHeaderView.Interactive)
            table.setColumnWidth(col, width)
    header.setStretchLastSection(True)
    header.setSectionsClickable(True)
    header.setSortIndicatorShown(True)

    state = {"col": -1, "order": Qt.AscendingOrder}

    def on_clicked(col):
        order = (Qt.DescendingOrder
                 if state["col"] == col and state["order"] == Qt.AscendingOrder
                 else Qt.AscendingOrder)
        state["col"], state["order"] = col, order
        _sort_rows(table, col, order == Qt.DescendingOrder)
        header.setSortIndicator(col, order)

    header.sectionClicked.connect(on_clicked)


def make_page_tables_sortable(page):
    """Apply make_sortable to every QTableWidget under a page — one call at
    the end of a page's __init__ covers all its tabs."""
    for table in page.findChildren(QTableWidget):
        make_sortable(table)


def _sort_rows(table: QTableWidget, col: int, reverse: bool):
    """Reorder rows in place by the clicked column. Vertical header items
    (e.g. the Matrix tab's brand-name rows) travel with their row — sorting
    must never desync a row from its row label."""
    rows = []
    for r in range(table.rowCount()):
        cells = [table.takeItem(r, c) for c in range(table.columnCount())]
        rows.append((cells, table.takeVerticalHeaderItem(r)))
    rows.sort(key=lambda entry: sort_key(entry[0][col].text()
                                         if entry[0][col] else ""),
              reverse=reverse)
    for r, (cells, vheader) in enumerate(rows):
        for c, item in enumerate(cells):
            if item is not None:
                table.setItem(r, c, item)
        if vheader is not None:
            table.setVerticalHeaderItem(r, vheader)
