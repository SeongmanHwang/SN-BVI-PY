(() => {
  const statusEl = document.getElementById("status");
  const alertEl = document.getElementById("alert");
  const modeABtn = document.getElementById("mode-a");
  const modeBBtn = document.getElementById("mode-b");
  const modeCBtn = document.getElementById("mode-c");
  const panelsA = document.getElementById("panels-a");
  const panelsB = document.getElementById("panels-b");
  const panelsC = document.getElementById("panels-c");
  const pageSelect = document.getElementById("page-select");
  const btnReload = document.getElementById("btn-reload");
  const refBrfBox = document.getElementById("ref-brf-box");
  const refBrfFile = document.getElementById("ref-brf-file");
  const reviewSummary = document.getElementById("review-summary");
  const pdfCacheEl = document.getElementById("pdf-cache");
  const pdfImgA = document.getElementById("pdf-img-a");
  const pdfImgB = document.getElementById("pdf-img-b");
  const pdfOverlayB = document.getElementById("pdf-overlay-b");
  const highlightStatus = document.getElementById("highlight-status");
  const examTreeEl = document.getElementById("exam-tree");
  const btnExpandAll = document.getElementById("btn-expand-all");
  const btnCollapseAll = document.getElementById("btn-collapse-all");

  const reviewEls = {
    genBraille: document.getElementById("review-gen-braille"),
    refBraille: document.getElementById("review-ref-braille"),
    genReverse: document.getElementById("review-gen-reverse"),
    refReverse: document.getElementById("review-ref-reverse"),
  };

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
  /** @type {{
   *   reviewPages: Array<object>,
   *   compare: object|null,
   *   referenceName: string,
   *   pageIndex: number,
   * } | null} */
  let review = null;
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
    const isB = next === "b";
    const isC = next === "c";
    modeABtn.setAttribute("aria-pressed", isA ? "true" : "false");
    modeBBtn.setAttribute("aria-pressed", isB ? "true" : "false");
    modeCBtn.setAttribute("aria-pressed", isC ? "true" : "false");
    panelsA.hidden = !isA;
    panelsB.hidden = !isB;
    panelsC.hidden = !isC;
    panelsA.setAttribute("aria-hidden", isA ? "false" : "true");
    panelsB.setAttribute("aria-hidden", isB ? "false" : "true");
    panelsC.setAttribute("aria-hidden", isC ? "false" : "true");
    refBrfBox.hidden = !isC;

    if (isA || isB) {
      if (cache) fillPageSelectPdf(cache.pdfPages, cache.pageIndex);
      if (isB) requestAnimationFrame(paintOverlay);
      if (isA || isB) {
        if (cache) showLinkedPage(cache.pageIndex);
      }
    } else if (isC) {
      if (review) {
        fillPageSelectReview(review.reviewPages, review.pageIndex);
        showReviewPage(review.pageIndex);
      } else {
        pageSelect.innerHTML = "";
        pageSelect.disabled = true;
        clearReviewPanels("(참고 BRF를 올리면 생성본과 나란히 비교합니다.)");
        reviewSummary.textContent = "";
      }
    }
  }

  function fillPageSelectPdf(pdfPages, selectedIndex) {
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

  function fillPageSelectReview(pages, selectedIndex) {
    pageSelect.innerHTML = "";
    pages.forEach((p, i) => {
      const opt = document.createElement("option");
      opt.value = String(i);
      opt.textContent = String(p.index);
      if (i === selectedIndex) opt.selected = true;
      pageSelect.appendChild(opt);
    });
    pageSelect.disabled = pages.length === 0;
  }

  function escapeHtml(text) {
    return String(text)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  function renderAnnotated(el, lines, emptyMessage) {
    if (!lines || !lines.length) {
      el.textContent = emptyMessage || "(내용 없음)";
      return;
    }
    const parts = [];
    lines.forEach((line, idx) => {
      if (idx) parts.push("\n");
      const text = line.text || "";
      const mask = Array.isArray(line.mismatch) ? line.mismatch : [];
      if (!text.length) return;
      let i = 0;
      while (i < text.length) {
        const bad = !!mask[i];
        let j = i + 1;
        while (j < text.length && !!mask[j] === bad) j += 1;
        const chunk = escapeHtml(text.slice(i, j));
        if (bad) {
          parts.push(`<span class="diff">${chunk}</span>`);
        } else {
          parts.push(chunk);
        }
        i = j;
      }
    });
    el.innerHTML = parts.join("") || emptyMessage || "(빈 면)";
  }

  function clearReviewPanels(message) {
    Object.values(reviewEls).forEach((el) => {
      if (el) el.textContent = message;
    });
  }

  function showReviewPage(pageIndex) {
    if (!review || !review.reviewPages.length) return;
    const idx = Math.max(0, Math.min(pageIndex, review.reviewPages.length - 1));
    review.pageIndex = idx;
    pageSelect.value = String(idx);
    const page = review.reviewPages[idx];
    const gen = page.generated || {};
    const ref = page.reference || {};
    renderAnnotated(reviewEls.genBraille, gen.unicode_lines, "(생성 점자 없음)");
    renderAnnotated(reviewEls.refBraille, ref.unicode_lines, "(참고 점자 없음)");
    renderAnnotated(reviewEls.genReverse, gen.reverse_lines, "(생성 역점역 없음)");
    renderAnnotated(reviewEls.refReverse, ref.reverse_lines, "(참고 역점역 없음)");
  }

  function updateReviewSummary() {
    if (!review || !review.compare) {
      reviewSummary.textContent = "";
      return;
    }
    const c = review.compare;
    const name = review.referenceName || "참고 BRF";
    const pct = (n) =>
      typeof n === "number" ? `${Math.round(n * 1000) / 10}%` : "—";
    reviewSummary.textContent =
      `참고: ${name} · 행 일치 ${c.matched_lines}/${Math.max(c.generated_lines, c.reference_lines)}` +
      ` (${pct(c.line_match_ratio)}) · 셀 일치 ${c.cell_equal}/${c.cell_total}` +
      ` (${pct(c.cell_match_ratio)}) · 차이 ${c.diff_count}건` +
      " · 노란 음영은 불일치 구간입니다.";
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

    const blocks = pdf.blocks || [];
    blocks.forEach((block) => {
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

  function showLinkedPage(pageIndex) {
    if (!cache || cache.pdfPages.length === 0) return;
    const idx = Math.max(0, Math.min(pageIndex, cache.pdfPages.length - 1));
    cache.pageIndex = idx;
    if (mode !== "c") pageSelect.value = String(idx);

    const pdf = cache.pdfPages[idx];
    const brl = cache.braillePages[idx];

    const url = pdfUrl(pdf.page_number);
    pdfImgA.src = url;
    pdfImgB.src = url;
    pdfImgA.alt = `원문 PDF ${pdf.page_number}면`;
    pdfImgB.alt = `원문 PDF ${pdf.page_number}면`;
    document.getElementById("pdf-text-a").textContent =
      pdf.text || "(텍스트 없음)";
    document.getElementById("pdf-text-b").textContent =
      pdf.text || "(텍스트 없음)";

    if (brl) {
      document.getElementById("brf-text").textContent = brl.unicode;
      document.getElementById("reverse-text").textContent = brl.reverse;
    } else {
      document.getElementById("brf-text").textContent =
        "(이 면에 대응하는 점자 없음)";
      document.getElementById("reverse-text").textContent =
        "(이 면에 대응하는 역점역 없음)";
    }

    if (pdfImgB.complete) {
      paintOverlay();
    } else {
      pdfImgB.addEventListener("load", () => paintOverlay(), { once: true });
    }
  }

  function updateStatusLine() {
    if (!cache) return;
    const name = (cache.status && cache.status.source_name) || "문서";
    const warn = (cache.warnings && cache.warnings.length) || 0;
    const ref =
      cache.status && cache.status.has_reference_brf
        ? ` · 참고 BRF ${cache.status.reference_name || "있음"}`
        : "";
    setStatus(
      `${name} · 원문 ${cache.pdfPages.length}면` +
        (cache.braillePages.length !== cache.pdfPages.length
          ? ` · 점자 ${cache.braillePages.length}면`
          : "") +
        ref +
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

  async function loadReview({ quiet = false } = {}) {
    if (!quiet) setStatus("검토 데이터를 불러오는 중…");
    try {
      const res = await fetch("/api/dev/review");
      const data = await res.json();
      if (!data.ok) {
        review = null;
        if (mode === "c") {
          clearReviewPanels(data.message || "(참고 BRF를 먼저 올리세요.)");
          reviewSummary.textContent = "";
          pageSelect.innerHTML = "";
          pageSelect.disabled = true;
        }
        if (!quiet) setAlert(data.message || "검토 데이터를 만들 수 없습니다.");
        return false;
      }
      review = {
        reviewPages: data.review_pages || [],
        compare: data.compare || null,
        referenceName: data.reference_name || "reference.brf",
        pageIndex: 0,
      };
      updateReviewSummary();
      if (mode === "c") {
        fillPageSelectReview(review.reviewPages, 0);
        showReviewPage(0);
      }
      if (cache && cache.status) {
        cache.status.has_reference_brf = true;
        cache.status.reference_name = review.referenceName;
      }
      updateStatusLine();
      return true;
    } catch (_err) {
      if (!quiet) setAlert("검토 모드를 불러오는 중 오류가 발생했습니다.");
      return false;
    }
  }

  async function uploadReferenceBrf(file) {
    if (!file) return;
    setStatus("참고 BRF를 올리는 중…");
    const form = new FormData();
    form.append("file", file, file.name || "reference.brf");
    try {
      const res = await fetch("/api/dev/reference-brf", {
        method: "POST",
        body: form,
      });
      const data = await res.json();
      if (!data.ok) {
        setAlert(data.message || "참고 BRF를 올릴 수 없습니다.");
        return;
      }
      if (cache) cache.status = data.status || cache.status;
      setStatus(data.message || "참고 BRF를 올렸습니다.", { focus: true });
      await loadReview({ quiet: true });
    } catch (_err) {
      setAlert("참고 BRF 업로드 중 오류가 발생했습니다.");
    }
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
        pageIndex: startIndex,
        examTree: data.exam_tree || null,
        selectedNodeId: null,
        highlightBlockIds: [],
        status: data.status || null,
        warnings: data.warnings || [],
      };

      if (mode !== "c") fillPageSelectPdf(pdfPages, startIndex);
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

      if (data.status && data.status.has_reference_brf) {
        await loadReview({ quiet: true });
      } else {
        review = null;
        if (mode === "c") {
          clearReviewPanels("(참고 BRF를 올리면 생성본과 나란히 비교합니다.)");
          reviewSummary.textContent = "";
        }
      }
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
  modeCBtn.addEventListener("click", () => setMode("c"));
  btnReload.addEventListener("click", () => loadBundle());
  refBrfFile.addEventListener("change", () => {
    const file = refBrfFile.files && refBrfFile.files[0];
    uploadReferenceBrf(file);
  });
  pageSelect.addEventListener("change", () => {
    const n = Number(pageSelect.value);
    if (Number.isNaN(n)) return;
    if (mode === "c") {
      showReviewPage(n);
      return;
    }
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
  initSplitters(panelsC);
  setMode("a");
  loadBundle();
})();
