"""
App-wide table sorting/resizing (2026-07-21 user request): numeric-aware
sort keys (the "1, 100, 101, 2" complaint), row reordering that keeps
vertical header labels attached (the Matrix tab's brand rows), and the
Add-Brands domain normalization.
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from desktop.widgets.table_tools import make_sortable, sort_key


def test_numbers_sort_by_value_not_lexically():
    """The user's exact example: 1..105 must order 1,2,3…, never 1,100,101,2."""
    values = [str(n) for n in range(1, 106)]
    ordered = sorted(values, key=sort_key)
    assert ordered == [str(n) for n in range(1, 106)]


def test_formatted_numbers_and_text_and_blanks():
    cells = ["Champion", "1,234", "$1,399.99", "95%", "144/144", "—", "", "atlas", "12"]
    ordered = sorted(cells, key=sort_key)
    # numbers first by value, then text case-insensitively, blanks last
    assert ordered == ["12", "95%", "144/144", "1,234", "$1,399.99",
                       "atlas", "Champion", "—", ""]


def test_click_to_sort_reorders_rows_and_keeps_row_labels(qt_app=None):
    from PySide6.QtWidgets import QApplication, QTableWidget, QTableWidgetItem
    QApplication.instance() or QApplication([])

    t = QTableWidget(3, 2)
    t.setVerticalHeaderLabels(["RowA", "RowB", "RowC"])
    for r, (name, num) in enumerate([("Honda", "100"), ("WEN", "2"), ("CAT", "33")]):
        t.setItem(r, 0, QTableWidgetItem(name))
        t.setItem(r, 1, QTableWidgetItem(num))
    make_sortable(t)

    t.horizontalHeader().sectionClicked.emit(1)          # sort numeric asc
    assert [t.item(r, 1).text() for r in range(3)] == ["2", "33", "100"]
    # vertical header labels travelled with their rows (Matrix-tab guarantee)
    assert [t.verticalHeaderItem(r).text() for r in range(3)] == ["RowB", "RowC", "RowA"]

    t.horizontalHeader().sectionClicked.emit(1)          # second click -> desc
    assert [t.item(r, 1).text() for r in range(3)] == ["100", "33", "2"]

    t.horizontalHeader().sectionClicked.emit(0)          # text column A-Z
    assert [t.item(r, 0).text() for r in range(3)] == ["CAT", "Honda", "WEN"]


def test_columns_become_user_resizable():
    from PySide6.QtWidgets import QApplication, QHeaderView, QTableWidget
    QApplication.instance() or QApplication([])
    t = QTableWidget(1, 3)
    t.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
    make_sortable(t)
    hdr = t.horizontalHeader()
    for col in range(3):
        assert hdr.sectionResizeMode(col) == QHeaderView.Interactive
    assert hdr.stretchLastSection()


def test_normalize_domain_dedupe_key():
    from desktop.pages.knowledge_page import KnowledgePage
    n = KnowledgePage._normalize_domain
    assert n("https://www.FirmanPower.com/pages/x") == "firmanpower.com"
    assert n("http://firmanpower.com") == "firmanpower.com"
    assert n("www.firmanpower.com/") == "firmanpower.com"
    assert n("firmanpower.com") == "firmanpower.com"
    assert n("") == "" and n(None) == ""
