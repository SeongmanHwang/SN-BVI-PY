(() => {
  const statusEl = document.getElementById("status");
  const alertEl = document.getElementById("alert");
  const modeABtn = document.getElementById("mode-a");
  const modeBBtn = document.getElementById("mode-b");
  const panelsA = document.getElementById("panels-a");
  const panelsB = document.getElementById("panels-b");
  const pageSelect = document.getElementById("page-select");
  const btnReload = document.getElementById("btn-reload");
  const pdfCacheEl = document.getElementById("pdf-cache");
  const pdfImgA = document.getElementById("pdf-img-a");
  const pdfImgB = document.getElementById("pdf-img-b");
  const pdfOverlayB = document.getElementById("pdf-overlay-b");
  const highlightStatus = document.getElementById("highlight-status");
  const examTreeEl = document.getElementById("exam-tree");
  const btnExpandAll = document.getElementById("btn-expand-all");
  const btnCollapseAll = document.getElementById("btn-collapse-all");

  /** @type {{
   *   pdfPages: Array<object>,
   *   braillePages: Array<object>,
   *   pageIndex: number,
   *   examTree: object|null,
   *   selectedNodeId: string|null,
   *   highlightBlockIds: string[],
   *   status: object|null,
   *   warnings: Array<string>,
   * } | null} */
  let cache = null;
  let mode = "a";
  const DEFAULT_EXPAND_DEPTH = 1;

  function setStatus(message, { focus = false } = {}) {
    alertEl.hidden = true;
    alertEl.textContent = "";
    statusEl.textContent = message;
    if (focus) statusEl.focus();
  }

  function setAlert(message) {
    alertEl.hidden = false;
    alertEl.textContent = message;
  }

  function setMode(next) {
    mode = next;
    const isA = next === "a";
    modeABtn.setAttribute("aria-pressed", isA ? "true" : "false");
    modeBBtn.setAttribute("aria-pressed", isA ? "false" : "true");
    panelsA.hidden = !isA;
    panelsB.hidden = isA;
    panelsA.setAttribute("aria-hidden", isA ? "false" : "true");
    panelsB.setAttribute("aria-hidden", isA ? "true" : "false");
    if (!isA) requestAnimationFrame(paintOverlay);
  }

  function fillPageSelect(pdfPages, selectedIndex) {
    pageSelect.innerHTML = "";
    pdfPages.forEach((p, i) => {
      const opt = document.createElement("option");
      opt.value = String(i);
      opt.textContent = String(p.page_number);
      if (i === selectedIndex) opt.selected = true;
      pageSelect.appendChild(opt);
    });
    pageSelect.disabled = pdfPages.length === 0;
  }

  function setExpanded(li, expanded) {
    const children = li.querySelector(":scope > ul");
    if (!children) return;
    li.setAttribute("aria-expanded", expanded ? "true" : "false");
    children.hidden = !expanded;
    const toggle = li.querySelector(":scope > .node-row .node-toggle");
    if (toggle) {
      toggle.textContent = expanded ? "▼" : "▶";
      toggle.setAttribute(
        "aria-label",
        expanded ? "하위 항목 접기" : "하위 항목 펼치기"
      );
    }
  }

  function expandAll(expanded) {
    examTreeEl.querySelectorAll('li[role="treeitem"]').forEach((li) => {
      if (li.querySelector(":scope > ul")) setExpanded(li, expanded);
    });
  }

  function renderTree(container, node) {
    container.innerHTML = "";
    if (!node) return;

    function makeNested(children, depth) {
      const ul = document.createElement("ul");
      ul.setAttribute("role", "group");
      children.forEach((child) => {
        const li = document.createElement("li");
        li.setAttribute("role", "treeitem");
        li.dataset.nodeId = child.id || "";
        if (child.page_number != null) {
          li.dataset.pageNumber = String(child.page_number);
        }
        if (child.block_ids && child.block_ids.length) {
          li.dataset.blockIds = child.block_ids.join(",");
        }

        const row = document.createElement("div");
        row.className = "node-row";

        const hasChildren = !!(child.children && child.children.length);
        if (hasChildren) {
          const toggle = document.createElement("button");
          toggle.type = "button";
          toggle.className = "node-toggle";
          toggle.textContent = "▼";
          toggle.addEventListener("click", (event) => {
            event.stopPropagation();
            const open = li.getAttribute("aria-expanded") !== "true";
            setExpanded(li, open);
          });
          row.appendChild(toggle);
        } else {
          const spacer = document.createElement("span");
          spacer.className = "node-toggle-spacer";
          spacer.setAttribute("aria-hidden", "true");
          row.appendChild(spacer);
        }

        const selectBtn = document.createElement("button");
        selectBtn.type = "button";
        selectBtn.className = "node-select";
        const label = document.createElement("span");
        label.className = "node-label";
        label.textContent = child.label || child.type;
        selectBtn.appendChild(label);
        if (child.text) {
          const text = document.createElement("span");
          text.className = "node-text";
          text.textContent = child.text;
          selectBtn.appendChild(text);
        }
        selectBtn.addEventListener("click", () => selectTreeNode(child, li));
        row.appendChild(selectBtn);
        li.appendChild(row);

        if (hasChildren) {
          const childUl = makeNested(child.children, depth + 1);
          li.appendChild(childUl);
          setExpanded(li, depth < DEFAULT_EXPAND_DEPTH);
        }
        ul.appendChild(li);
      });
      return ul;
    }

    const roots =
      node.children && node.children.length ? node.children : [node];
    container.appendChild(makeNested(roots, 0));
  }

  function clearTreeSelection() {
    examTreeEl
      .querySelectorAll(".node-select.is-selected")
      .forEach((el) => el.classList.remove("is-selected"));
  }

  function selectTreeNode(node, li) {
    if (!cache) return;
    clearTreeSelection();
    const btn = li.querySelector(":scope > .node-row .node-select");
    if (btn) btn.classList.add("is-selected");

    cache.selectedNodeId = node.id || null;
    cache.highlightBlockIds = Array.isArray(node.block_ids)
      ? node.block_ids.slice()
      : [];

    const pageNumber = node.page_number;
    if (pageNumber != null) {
      const idx = cache.pdfPages.findIndex((p) => p.page_number === pageNumber);
      if (idx >= 0 && idx !== cache.pageIndex) {
        showLinkedPage(idx);
      } else {
        paintOverlay();
      }
    } else {
      paintOverlay();
    }

    const label = node.label || node.type || "노드";
    if (cache.highlightBlockIds.length) {
      highlightStatus.textContent = `선택: ${label} · 블록 ${cache.highlightBlockIds.length}개 강조`;
    } else {
      highlightStatus.textContent = `선택: ${label} · 연결 블록 없음`;
    }
  }

  function paintOverlay() {
    if (!pdfOverlayB || !cache) return;
    const pdf = cache.pdfPages[cache.pageIndex];
    pdfOverlayB.innerHTML = "";
    if (!pdf) return;

    const width = Number(pdf.width) || 1;
    const height = Number(pdf.height) || 1;
    pdfOverlayB.setAttribute("viewBox", `0 0 ${width} ${height}`);
    pdfOverlayB.setAttribute("width", "100%");
    pdfOverlayB.setAttribute("height", "100%");

    const ids = new Set(cache.highlightBlockIds || []);
    if (!ids.size) return;

    (pdf.blocks || []).forEach((block) => {
      if (!ids.has(block.id)) return;
      const [x0, y0, x1, y1] = block.bbox || [];
      if ([x0, y0, x1, y1].some((v) => typeof v !== "number")) return;
      const rect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
      rect.setAttribute("x", String(x0));
      rect.setAttribute("y", String(y0));
      rect.setAttribute("width", String(Math.max(0, x1 - x0)));
      rect.setAttribute("height", String(Math.max(0, y1 - y0)));
      rect.setAttribute("class", "pdf-highlight");
      pdfOverlayB.appendChild(rect);
    });
  }

  function pdfUrl(pageNumber) {
    return `/api/dev/pdf-page/${pageNumber}`;
  }

  function braillePartsForPdf(pdfPageNumber) {
    if (!cache) return [];
    const key = String(pdfPageNumber);
    let indices =
      (cache.pdfToBraille && cache.pdfToBraille[key]) || [];
    if (!indices.length) {
      // 구버전 폴백: 같은 배열 인덱스
      const idx = cache.pdfPages.findIndex(
        (p) => p.page_number === pdfPageNumber
      );
      if (idx >= 0 && cache.braillePages[idx]) indices = [idx];
    }
    return indices
      .map((i) => cache.braillePages[i])
      .filter(Boolean);
  }

  function joinBrailleParts(parts, field) {
    if (!parts.length) return "";
    if (parts.length === 1) return parts[0][field] || "";
    return parts
      .map((p) => {
        const label = `── 점자 ${p.index}면 ──`;
        return `${label}\n${p[field] || ""}`;
      })
      .join("\n\n");
  }

  function showLinkedPage(pageIndex) {
    if (!cache || cache.pdfPages.length === 0) return;
    const idx = Math.max(0, Math.min(pageIndex, cache.pdfPages.length - 1));
    cache.pageIndex = idx;
    pageSelect.value = String(idx);

    const pdf = cache.pdfPages[idx];
    const parts = braillePartsForPdf(pdf.page_number);
    const url = pdfUrl(pdf.page_number);
    pdfImgA.src = url;
    pdfImgB.src = url;
    pdfImgA.alt = `원문 PDF ${pdf.page_number}면`;
    pdfImgB.alt = `원문 PDF ${pdf.page_number}면`;
    document.getElementById("pdf-text-a").textContent =
      pdf.text || "(텍스트 없음)";
    document.getElementById("pdf-text-b").textContent =
      pdf.text || "(텍스트 없음)";

    const brfMeta = document.getElementById("brf-page-meta");
    const revMeta = document.getElementById("reverse-page-meta");
    if (parts.length) {
      document.getElementById("brf-text").textContent = joinBrailleParts(
        parts,
        "unicode"
      );
      document.getElementById("reverse-text").textContent = joinBrailleParts(
        parts,
        "reverse"
      );
      const nums = parts.map((p) => p.index).join(", ");
      const meta =
        parts.length > 1
          ? `이 PDF 면에 점자 ${parts.length}면 (면 ${nums})`
          : `점자 ${parts[0].index}면`;
      if (brfMeta) brfMeta.textContent = meta;
      if (revMeta) revMeta.textContent = meta;
    } else {
      document.getElementById("brf-text").textContent =
        "(이 PDF 면에 대응하는 점자 없음)";
      document.getElementById("reverse-text").textContent =
        "(이 PDF 면에 대응하는 역점역 없음)";
      if (brfMeta) brfMeta.textContent = "";
      if (revMeta) revMeta.textContent = "";
    }

    if (pdfImgB.complete) paintOverlay();
    else pdfImgB.addEventListener("load", () => paintOverlay(), { once: true });
    updateStatusLine();
  }

  function updateStatusLine() {
    if (!cache) return;
    const name = (cache.status && cache.status.source_name) || "문서";
    const warn = (cache.warnings && cache.warnings.length) || 0;
    const pdf = cache.pdfPages[cache.pageIndex];
    const parts = pdf ? braillePartsForPdf(pdf.page_number) : [];
    setStatus(
      `${name} · 원문 ${cache.pdfPages.length}면` +
        (cache.braillePages.length !== cache.pdfPages.length
          ? ` · 점자 ${cache.braillePages.length}면`
          : "") +
        (parts.length > 1 ? ` · 현재 PDF에 점자 ${parts.length}면` : "") +
        (warn ? ` · 경고 ${warn}건` : "") +
        " · 읽기 전용 진단입니다."
    );
  }

  function prefetchPdfImages(pdfPages) {
    pdfCacheEl.innerHTML = "";
    return Promise.all(
      pdfPages.map(
        (p) =>
          new Promise((resolve) => {
            const img = new Image();
            img.onload = () => resolve(true);
            img.onerror = () => resolve(false);
            img.alt = "";
            img.src = pdfUrl(p.page_number);
            pdfCacheEl.appendChild(img);
          })
      )
    );
  }

  async function loadBundle() {
    setStatus("개발자 데이터를 불러오는 중…");
    try {
      const res = await fetch("/api/dev/bundle");
      const data = await res.json();
      if (!data.ok) {
        setAlert(data.message || "불러오기에 실패했습니다.");
        setStatus("사용자 모드에서 PDF를 올린 뒤 다시 오세요.");
        return;
      }

      const pdfPages = data.pdf_pages || [];
      const braillePages = data.braille_pages || [];
      let startIndex = 0;
      if (data.page_number != null && pdfPages.length) {
        const found = pdfPages.findIndex(
          (p) => p.page_number === data.page_number
        );
        if (found >= 0) startIndex = found;
      }

      cache = {
        pdfPages,
        braillePages,
        pdfToBraille: data.pdf_to_braille || {},
        pageIndex: startIndex,
        examTree: data.exam_tree || null,
        selectedNodeId: null,
        highlightBlockIds: [],
        status: data.status || null,
        warnings: data.warnings || [],
      };

      fillPageSelect(pdfPages, startIndex);
      highlightStatus.textContent = "";
      document.getElementById("exam-tree-text").textContent =
        data.exam_tree_text || "";
      document.getElementById("dtbook-xml").textContent = data.dtbook_xml || "";
      const tree = data.exam_tree || {};
      document.getElementById("tree-summary").textContent = tree.summary || "";
      renderTree(examTreeEl, tree.root);
      showLinkedPage(startIndex);
      updateStatusLine();
      prefetchPdfImages(pdfPages).catch(() => {});
    } catch (_err) {
      setAlert("개발자 모드를 불러오는 중 오류가 발생했습니다.");
    }
  }

  function initSplitters(root) {
    const MIN = 120;
    root.querySelectorAll(".splitter").forEach((splitter) => {
      const left = splitter.previousElementSibling;
      const right = splitter.nextElementSibling;
      if (!left || !right || !left.classList.contains("panel")) return;

      function applyWidths(leftPx, rightPx) {
        left.style.flex = `0 0 ${leftPx}px`;
        right.style.flex = `0 0 ${rightPx}px`;
        left.style.width = `${leftPx}px`;
        right.style.width = `${rightPx}px`;
      }

      function onPointerDown(event) {
        if (event.button != null && event.button !== 0) return;
        event.preventDefault();
        const startX = event.clientX;
        const leftStart = left.getBoundingClientRect().width;
        const rightStart = right.getBoundingClientRect().width;
        splitter.classList.add("is-dragging");
        document.body.classList.add("is-resizing");

        function onMove(ev) {
          const dx = ev.clientX - startX;
          let nextLeft = leftStart + dx;
          let nextRight = rightStart - dx;
          if (nextLeft < MIN) {
            nextRight -= MIN - nextLeft;
            nextLeft = MIN;
          }
          if (nextRight < MIN) {
            nextLeft -= MIN - nextRight;
            nextRight = MIN;
          }
          if (nextLeft < MIN || nextRight < MIN) return;
          applyWidths(nextLeft, nextRight);
        }

        function onUp() {
          splitter.classList.remove("is-dragging");
          document.body.classList.remove("is-resizing");
          window.removeEventListener("pointermove", onMove);
          window.removeEventListener("pointerup", onUp);
          paintOverlay();
        }

        window.addEventListener("pointermove", onMove);
        window.addEventListener("pointerup", onUp);
      }

      splitter.addEventListener("pointerdown", onPointerDown);
      splitter.addEventListener("keydown", (event) => {
        const step = event.shiftKey ? 40 : 16;
        let delta = 0;
        if (event.key === "ArrowLeft") delta = -step;
        if (event.key === "ArrowRight") delta = step;
        if (!delta) return;
        event.preventDefault();
        const leftStart = left.getBoundingClientRect().width;
        const rightStart = right.getBoundingClientRect().width;
        let nextLeft = leftStart + delta;
        let nextRight = rightStart - delta;
        if (nextLeft < MIN || nextRight < MIN) return;
        applyWidths(nextLeft, nextRight);
        paintOverlay();
      });
    });
  }

  modeABtn.addEventListener("click", () => setMode("a"));
  modeBBtn.addEventListener("click", () => setMode("b"));
  btnReload.addEventListener("click", () => loadBundle());
  pageSelect.addEventListener("change", () => {
    const n = Number(pageSelect.value);
    if (Number.isNaN(n)) return;
    if (cache) {
      cache.highlightBlockIds = [];
      cache.selectedNodeId = null;
      clearTreeSelection();
      highlightStatus.textContent = "";
    }
    showLinkedPage(n);
  });
  btnExpandAll.addEventListener("click", () => expandAll(true));
  btnCollapseAll.addEventListener("click", () => expandAll(false));
  window.addEventListener("resize", () => paintOverlay());

  initSplitters(panelsA);
  initSplitters(panelsB);
  setMode("a");
  loadBundle();
})();
