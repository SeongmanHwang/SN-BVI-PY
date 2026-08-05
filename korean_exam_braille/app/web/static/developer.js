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

  /** @type {{
   *   pdfPages: Array<{page_number:number, text:string}>,
   *   braillePages: Array<{index:number, unicode:string, reverse:string}>,
   *   pageIndex: number,
   *   status: object|null,
   *   warnings: Array<string>,
   * } | null} */
  let cache = null;
  let mode = "a";

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

  function renderTree(container, node) {
    container.innerHTML = "";
    if (!node) return;

    function makeNested(children) {
      const ul = document.createElement("ul");
      ul.setAttribute("role", "group");
      children.forEach((child) => {
        const li = document.createElement("li");
        li.setAttribute("role", "treeitem");
        const label = document.createElement("span");
        label.className = "node-label";
        label.textContent = child.label || child.type;
        li.appendChild(label);
        if (child.text) {
          const text = document.createElement("div");
          text.className = "node-text";
          text.textContent = child.text;
          li.appendChild(text);
        }
        if (child.children && child.children.length) {
          li.setAttribute("aria-expanded", "true");
          li.appendChild(makeNested(child.children));
        }
        ul.appendChild(li);
      });
      return ul;
    }

    const roots =
      node.children && node.children.length ? node.children : [node];
    container.appendChild(makeNested(roots));
  }

  function pdfUrl(pageNumber) {
    return `/api/dev/pdf-page/${pageNumber}`;
  }

  function showLinkedPage(pageIndex) {
    if (!cache || cache.pdfPages.length === 0) return;
    const idx = Math.max(0, Math.min(pageIndex, cache.pdfPages.length - 1));
    cache.pageIndex = idx;
    pageSelect.value = String(idx);

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
  }

  function updateStatusLine() {
    if (!cache) return;
    const name = (cache.status && cache.status.source_name) || "문서";
    const warn = (cache.warnings && cache.warnings.length) || 0;
    setStatus(
      `${name} · 원문 ${cache.pdfPages.length}면` +
        (cache.braillePages.length !== cache.pdfPages.length
          ? ` · 점자 ${cache.braillePages.length}면`
          : "") +
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
        pageIndex: startIndex,
        status: data.status || null,
        warnings: data.warnings || [],
      };

      fillPageSelect(pdfPages, startIndex);

      document.getElementById("exam-tree-text").textContent =
        data.exam_tree_text || "";
      document.getElementById("dtbook-xml").textContent = data.dtbook_xml || "";
      const tree = data.exam_tree || {};
      document.getElementById("tree-summary").textContent = tree.summary || "";
      renderTree(document.getElementById("exam-tree"), tree.root);

      // 먼저 현재 면을 그린 뒤, 나머지는 백그라운드 프리로드
      showLinkedPage(startIndex);
      updateStatusLine();
      prefetchPdfImages(pdfPages).catch(() => {});
    } catch (err) {
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
      });
    });
  }

  modeABtn.addEventListener("click", () => setMode("a"));
  modeBBtn.addEventListener("click", () => setMode("b"));
  btnReload.addEventListener("click", () => loadBundle());
  pageSelect.addEventListener("change", () => {
    const n = Number(pageSelect.value);
    if (!Number.isNaN(n)) showLinkedPage(n);
  });

  initSplitters(panelsA);
  initSplitters(panelsB);
  setMode("a");
  loadBundle();
})();
