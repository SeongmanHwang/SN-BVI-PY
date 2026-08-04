"""계층 탐색 UI — ExamNavigator 포트에만 의존 (트리 중심)."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from korean_exam_braille.app.exam.models import ExamDocument, ExamNode
from korean_exam_braille.app.nav.index import node_label
from korean_exam_braille.app.nav.models import NavLocation
from korean_exam_braille.app.nav.ports import ExamNavigator


class NavSidePanel(QWidget):
    """도킹용 탐색 패널: 트리 = 주 UI, 단축키 = 주 조작, 버튼 = 보조.

    locationChanged(NavLocation): PDF/BRF 동기화용.
    """

    locationChanged = Signal(object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._nav: ExamNavigator | None = None
        self._exam: ExamDocument | None = None
        self._updating = False
        self._item_by_id: dict[str, QTreeWidgetItem] = {}
        self._build()

    def bind(self, navigator: ExamNavigator, exam: ExamDocument) -> None:
        self._nav = navigator
        self._exam = exam
        navigator.bind(exam)
        self._fill_tree()
        self.refresh(emit=True)

    def clear(self) -> None:
        self._nav = None
        self._exam = None
        self._item_by_id.clear()
        self.tree.clear()
        self.path_label.setText("PDF를 연 뒤 탐색을 켜세요")
        self.detail_label.setText("")

    def navigator(self) -> ExamNavigator | None:
        return self._nav

    def install_window_shortcuts(self, host: QWidget) -> None:
        """메인 창에 Alt/Ctrl 단축키 설치 (표·입력과 화살표 충돌 완화)."""
        pairs = [
            ("Alt+Left", lambda: self._run(lambda: self._nav and self._nav.prev_sibling())),
            ("Alt+Right", lambda: self._run(lambda: self._nav and self._nav.next_sibling())),
            ("Alt+Up", lambda: self._run(lambda: self._nav and self._nav.parent())),
            ("Alt+Down", lambda: self._run(lambda: self._nav and self._nav.first_child())),
            (
                "Ctrl+Left",
                lambda: self._run(
                    lambda: self._nav and self._nav.prev_of_type("Question")
                ),
            ),
            (
                "Ctrl+Right",
                lambda: self._run(
                    lambda: self._nav and self._nav.next_of_type("Question")
                ),
            ),
            (
                "Ctrl+Shift+Left",
                lambda: self._run(
                    lambda: self._nav and self._nav.prev_of_type("PassageGroup")
                ),
            ),
            (
                "Ctrl+Shift+Right",
                lambda: self._run(
                    lambda: self._nav and self._nav.next_of_type("PassageGroup")
                ),
            ),
            ("Ctrl+M", self._mark),
            (
                "Ctrl+Backspace",
                lambda: self._run(lambda: self._nav and self._nav.go_origin()),
            ),
            (
                "Alt+Home",
                lambda: self._run(lambda: self._nav and self._nav.reset_to_root()),
            ),
        ]
        for seq, slot in pairs:
            sc = QShortcut(QKeySequence(seq), host)
            sc.setContext(Qt.ShortcutContext.WindowShortcut)
            sc.activated.connect(slot)

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)

        self.path_label = QLabel("PDF를 연 뒤 탐색을 켜세요")
        self.path_label.setWordWrap(True)
        self.path_label.setStyleSheet("font-weight: 600;")
        self.detail_label = QLabel("")
        self.detail_label.setWordWrap(True)
        root.addWidget(self.path_label)
        root.addWidget(self.detail_label)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["구조", "미리보기"])
        self.tree.setColumnWidth(0, 120)
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tree.itemSelectionChanged.connect(self._on_tree_selection)
        self.tree.itemDoubleClicked.connect(self._on_tree_activated)
        root.addWidget(self.tree, stretch=1)

        hint = QLabel(
            "Alt+←→ 형제 · Alt+↑↓ 상위/하위\n"
            "Ctrl+←→ 문항 · Ctrl+Shift+←→ 지문묶음\n"
            "Ctrl+M 원위치 저장 · Ctrl+Backspace 복귀 · Alt+Home 처음"
        )
        hint.setStyleSheet("color: #555; font-size: 11px;")
        hint.setWordWrap(True)
        root.addWidget(hint)

        row = QHBoxLayout()
        self.btn_mark = QPushButton("원위치 저장")
        self.btn_origin = QPushButton("원위치로")
        self.btn_home = QPushButton("처음")
        self.btn_mark.clicked.connect(self._mark)
        self.btn_origin.clicked.connect(
            lambda: self._run(lambda: self._nav and self._nav.go_origin())
        )
        self.btn_home.clicked.connect(
            lambda: self._run(lambda: self._nav and self._nav.reset_to_root())
        )
        row.addWidget(self.btn_mark)
        row.addWidget(self.btn_origin)
        row.addWidget(self.btn_home)
        root.addLayout(row)

    def _fill_tree(self) -> None:
        self._updating = True
        self.tree.clear()
        self._item_by_id.clear()
        if not self._exam:
            self._updating = False
            return

        def add(node: ExamNode, parent: QTreeWidgetItem | None) -> None:
            if node.node_type == "ExamDocument":
                for child in node.children:
                    add(child, None)
                return
            label = node.node_type
            qn = node.metadata.get("question_number")
            if qn is not None:
                label = f"{node.node_type} #{qn}"
            item = QTreeWidgetItem([label, node_label(node, max_len=40)])
            item.setData(0, Qt.ItemDataRole.UserRole, node.id)
            if parent is None:
                self.tree.addTopLevelItem(item)
            else:
                parent.addChild(item)
            self._item_by_id[node.id] = item
            for child in node.children:
                add(child, item)

        add(self._exam.root, None)
        self.tree.expandToDepth(1)
        self._updating = False

    def _on_tree_selection(self) -> None:
        if self._updating or not self._nav:
            return
        items = self.tree.selectedItems()
        if not items:
            return
        node_id = items[0].data(0, Qt.ItemDataRole.UserRole)
        if not node_id:
            return
        loc = self._nav.go(str(node_id))
        self._update_labels(loc)
        if loc is not None:
            self.locationChanged.emit(loc)

    def _on_tree_activated(self, item: QTreeWidgetItem, _col: int) -> None:
        self.tree.setCurrentItem(item)

    def _mark(self) -> None:
        if self._nav:
            self._nav.mark_origin()
            self._update_labels(self._nav.location())

    def _run(self, fn) -> None:
        if not self._nav:
            return
        loc = fn()
        self.refresh(emit=False)
        if loc is not None:
            self.locationChanged.emit(loc)

    def refresh(self, *, emit: bool = False) -> None:
        loc = self._nav.location() if self._nav else None
        self._update_labels(loc)
        self._sync_tree_selection(loc)
        if emit and loc is not None:
            self.locationChanged.emit(loc)

    def _update_labels(self, loc: NavLocation | None) -> None:
        if loc is None:
            self.path_label.setText("위치 없음")
            self.detail_label.setText("")
            return
        crumbs = " › ".join(c.node_type for c in loc.breadcrumb)
        head = f"{crumbs} › " if crumbs else ""
        self.path_label.setText(
            f"{head}{loc.node_type}  ({loc.sibling_index + 1}/{loc.sibling_count})"
        )
        self.detail_label.setText(loc.label)

    def _sync_tree_selection(self, loc: NavLocation | None) -> None:
        if loc is None:
            return
        item = self._item_by_id.get(loc.node_id)
        if item is None:
            return
        self._updating = True
        self.tree.setCurrentItem(item)
        self.tree.scrollToItem(item)
        self._updating = False


# 하위 호환 이름
NavPanel = NavSidePanel


def format_location_status(loc: NavLocation | None) -> str:
    if loc is None:
        return "탐색: 없음"
    page = loc.metadata.get("page_number")
    page_s = f" · PDF면 {page}" if page else ""
    crumbs = " › ".join(c.node_type for c in loc.breadcrumb)
    prefix = f"{crumbs} › " if crumbs else ""
    return f"탐색: {prefix}{loc.node_type} · {loc.label[:36]}{page_s}"
