(() => {
  const statusEl = document.getElementById("status");
  const alertEl = document.getElementById("alert");
  const genFile = document.getElementById("gen-brf-file");
  const refFile = document.getElementById("ref-brf-file");
  const genNameEl = document.getElementById("gen-brf-name");
  const refNameEl = document.getElementById("ref-brf-name");
  const btnCompare = document.getElementById("btn-compare");
  const summaryEl = document.getElementById("review-summary");
  const pageSelect = document.getElementById("page-select");
  const pageMeta = document.getElementById("page-meta");
  const progressWrap = document.getElementById("progress-wrap");
  const progressBar = document.getElementById("progress-bar");
  const progressFill = document.getElementById("progress-fill");
  const progressLabel = document.getElementById("progress-label");
  const views = {
    genBraille: document.getElementById("review-gen-braille"),
    refBraille: document.getElementById("review-ref-braille"),
    genReverse: document.getElementById("review-gen-reverse"),
    refReverse: document.getElementById("review-ref-reverse"),
  };

  /** @type {object|null} */
  let bundle = null;

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

  function showProgress(current, total, message) {
    progressWrap.hidden = false;
    const pctVal = total > 0 ? Math.min(100, Math.round((current / total) * 100)) : 0;
    progressFill.style.width = `${pctVal}%`;
    progressBar.setAttribute("aria-valuenow", String(pctVal));
    progressBar.setAttribute("aria-valuetext", `${pctVal}퍼센트. ${message}`);
    progressLabel.textContent = `${message} (${pctVal}%)`;
  }

  function hideProgress() {
    progressWrap.hidden = true;
    progressFill.style.width = "0%";
    progressBar.setAttribute("aria-valuenow", "0");
    progressLabel.textContent = "";
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
      if (line.page_break) {
        parts.push(`<span class="page-break">${escapeHtml(text)}</span>`);
        return;
      }
      const mask = Array.isArray(line.mismatch) ? line.mismatch : [];
      if (!text.length) return;
      let i = 0;
      while (i < text.length) {
        const bad = !!mask[i];
        let j = i + 1;
        while (j < text.length && !!mask[j] === bad) j += 1;
        const chunk = escapeHtml(text.slice(i, j));
        parts.push(bad ? `<span class="diff">${chunk}</span>` : chunk);
        i = j;
      }
    });
    el.innerHTML = parts.join("") || emptyMessage || "(빈 면)";
  }

  function pct(n) {
    return typeof n === "number" ? `${Math.round(n * 1000) / 10}%` : "—";
  }

  function fillPageSelect(pages, selectedIndex) {
    pageSelect.innerHTML = "";
    pages.forEach((p, i) => {
      const opt = document.createElement("option");
      opt.value = String(i);
      const mark = p.matched ? "" : " (미배정)";
      opt.textContent = `${p.index}${mark}`;
      if (i === selectedIndex) opt.selected = true;
      pageSelect.appendChild(opt);
    });
    pageSelect.disabled = pages.length === 0;
  }

  function showPage(pageIndex) {
    if (!bundle || !bundle.review_pages || !bundle.review_pages.length) return;
    const pages = bundle.review_pages;
    const idx = Math.max(0, Math.min(pageIndex, pages.length - 1));
    pageSelect.value = String(idx);
    const page = pages[idx];
    const gen = page.generated || {};
    const ref = page.reference || {};
    renderAnnotated(views.genBraille, gen.unicode_lines, "(생성 점자 없음)");
    renderAnnotated(
      views.refBraille,
      ref.unicode_lines,
      page.matched ? "(참고 구간 없음)" : "(이 면에 대응하는 참고 구간 없음)"
    );
    renderAnnotated(views.genReverse, gen.reverse_lines, "(생성 역점역 없음)");
    renderAnnotated(
      views.refReverse,
      ref.reverse_lines,
      page.matched ? "(참고 역점역 없음)" : "(이 면에 대응하는 참고 구간 없음)"
    );

    if (page.matched) {
      const clip = page.clipped ? " · 창 잘림" : "";
      pageMeta.textContent =
        `참고 오프셋 ${page.ref_start}–${page.ref_end}` +
        ` · 창 ${page.window_len}자 · 면 앵커 ${page.anchor_size}자` +
        ` · 면내 앵커 ${(page.anchors && page.anchors.unicode && page.anchors.unicode.length) || 0}개` +
        clip;
    } else {
      pageMeta.textContent = "참고에서 충분한 최장 일치를 찾지 못했습니다.";
    }
  }

  function showBundle(data) {
    bundle = data;
    const pages = data.review_pages || [];
    fillPageSelect(pages, 0);
    showPage(0);

    const s = data.assignment_summary || {};
    const c = data.compare || {};
    const gaps = data.unassigned_reference || [];
    summaryEl.textContent =
      `생성 ${data.generated_name || "—"} · 참고 ${data.reference_name || "—"}` +
      ` · 면 배정 ${s.matched_pages || 0}/${s.generated_pages || 0}` +
      ` · 미배정 생성 면 ${s.unmatched_pages || 0}` +
      ` · 참고 누락 ${s.unassigned_spans || 0}구간/${s.unassigned_chars || 0}자` +
      ` (최소 일치 ${s.min_match || 16}자 · 면내 앵커 최대 ${s.max_anchors || 5})` +
      ` · 셀 일치 ${c.cell_equal}/${c.cell_total} (${pct(c.cell_match_ratio)})` +
      (gaps.length
        ? ` · 누락 예: “${String(gaps[0].preview || "").replace(/\s+/g, " ").slice(0, 40)}…”`
        : "") +
      " · 노란 음영은 면내 앵커 밖 불일치입니다.";
  }

  async function uploadBrf(side, file) {
    if (!file) return;
    const form = new FormData();
    form.append("file", file, file.name || `${side}.brf`);
    const path =
      side === "generated"
        ? "/api/review/generated-brf"
        : "/api/review/reference-brf";
    setStatus(`${side === "generated" ? "생성" : "참고"} BRF를 올리는 중…`);
    const res = await fetch(path, { method: "POST", body: form });
    const data = await res.json();
    if (!data.ok) {
      setAlert(data.message || "BRF를 올릴 수 없습니다.");
      return null;
    }
    setStatus(data.message || "올렸습니다.", { focus: true });
    return data;
  }

  async function loadBundle() {
    setStatus("생성 면마다 참고 구간을 배정·비교하는 중…");
    btnCompare.disabled = true;
    showProgress(0, 1, "비교 준비 중…");
    try {
      const res = await fetch("/api/review/bundle-stream");
      if (!res.ok || !res.body) {
        const fallback = await fetch("/api/review/bundle");
        const data = await fallback.json();
        hideProgress();
        btnCompare.disabled = false;
        if (!data.ok) {
          setAlert(data.message || "비교할 수 없습니다.");
          return;
        }
        showBundle(data);
        setStatus(
          `비교 완료 — 생성 ${data.generated_name} · 참고 ${data.reference_name}`,
          { focus: true }
        );
        return;
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let buffer = "";
      let finished = false;

      while (!finished) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";
        for (const line of lines) {
          if (!line.trim()) continue;
          let event;
          try {
            event = JSON.parse(line);
          } catch (_err) {
            continue;
          }
          if (event.type === "progress") {
            showProgress(
              Number(event.current) || 0,
              Number(event.total) || 1,
              event.message || "비교 중…"
            );
            setStatus(event.message || "비교 중…");
          } else if (event.type === "done") {
            finished = true;
            hideProgress();
            if (!event.ok) {
              setAlert(event.message || "비교할 수 없습니다.");
              break;
            }
            showBundle(event);
            setStatus(
              `비교 완료 — 생성 ${event.generated_name} · 참고 ${event.reference_name}`,
              { focus: true }
            );
          } else if (event.type === "error") {
            finished = true;
            hideProgress();
            setAlert(event.message || "비교할 수 없습니다.");
          }
        }
      }
      if (buffer.trim() && !finished) {
        try {
          const event = JSON.parse(buffer);
          if (event.type === "done" && event.ok) {
            hideProgress();
            showBundle(event);
            setStatus(
              `비교 완료 — 생성 ${event.generated_name} · 참고 ${event.reference_name}`,
              { focus: true }
            );
          } else if (event.type === "error") {
            hideProgress();
            setAlert(event.message || "비교할 수 없습니다.");
          }
        } catch (_err) {
          /* ignore trailing partial */
        }
      }
    } catch (_err) {
      hideProgress();
      setAlert("검토 데이터를 불러오는 중 오류가 발생했습니다.");
    } finally {
      btnCompare.disabled = false;
    }
  }

  async function refreshNamesFromStatus() {
    try {
      const res = await fetch("/api/status");
      const st = await res.json();
      if (st.has_generated_brf && st.generated_name) {
        genNameEl.textContent = `사용 중: ${st.generated_name}`;
      }
      if (st.has_reference_brf && st.reference_name) {
        refNameEl.textContent = `사용 중: ${st.reference_name}`;
      }
      if (st.has_generated_brf && st.has_reference_brf) {
        setStatus(
          "세션에 생성·참고 BRF가 있습니다. 비교하기를 누르거나 파일을 다시 올리세요."
        );
      } else if (st.has_generated_brf) {
        setStatus("생성 BRF가 준비되어 있습니다. 참고 BRF를 올리세요.");
      } else if (st.has_reference_brf) {
        setStatus("참고 BRF가 준비되어 있습니다. 생성 BRF를 올리세요.");
      }
    } catch (_err) {
      /* ignore */
    }
  }

  genFile.addEventListener("change", async () => {
    const file = genFile.files && genFile.files[0];
    const data = await uploadBrf("generated", file);
    if (data) genNameEl.textContent = `사용 중: ${data.meta.name}`;
  });

  refFile.addEventListener("change", async () => {
    const file = refFile.files && refFile.files[0];
    const data = await uploadBrf("reference", file);
    if (data) refNameEl.textContent = `사용 중: ${data.meta.name}`;
  });

  btnCompare.addEventListener("click", () => loadBundle());
  pageSelect.addEventListener("change", () => {
    const n = Number(pageSelect.value);
    if (!Number.isNaN(n)) showPage(n);
  });

  let syncing = false;
  function linkScroll(a, b) {
    a.addEventListener("scroll", () => {
      if (syncing) return;
      syncing = true;
      const ratio = a.scrollTop / Math.max(1, a.scrollHeight - a.clientHeight);
      b.scrollTop = ratio * Math.max(0, b.scrollHeight - b.clientHeight);
      syncing = false;
    });
  }
  linkScroll(views.genBraille, views.refBraille);
  linkScroll(views.refBraille, views.genBraille);
  linkScroll(views.genReverse, views.refReverse);
  linkScroll(views.refReverse, views.genReverse);

  refreshNamesFromStatus();
})();
