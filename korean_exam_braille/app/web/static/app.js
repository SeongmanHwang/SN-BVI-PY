(() => {
  const statusEl = document.getElementById("status");
  const alertEl = document.getElementById("alert");
  const fileInput = document.getElementById("pdf-file");
  const fileNameEl = document.getElementById("file-name");
  const btnBrf = document.getElementById("btn-brf");
  const brfWhy = document.getElementById("brf-why");
  const btnDtbook = document.getElementById("btn-dtbook");
  const dtbookWhy = document.getElementById("dtbook-why");
  const fileButton = document.querySelector(".file-button");

  if (!fileInput || !statusEl || !alertEl || !btnBrf || !btnDtbook) {
    console.error("사용자 모드 UI 요소를 찾지 못했습니다. 페이지를 새로고침하세요.");
    return;
  }

  function setStatus(message, { focus = true } = {}) {
    alertEl.hidden = true;
    alertEl.textContent = "";
    statusEl.textContent = message;
    if (focus) {
      statusEl.focus();
    }
  }

  function setAlert(message) {
    alertEl.hidden = false;
    alertEl.textContent = message;
    try {
      alertEl.focus();
    } catch (_) {
      /* ignore */
    }
  }

  function setBusy(busy) {
    fileInput.disabled = busy;
    if (fileButton) {
      fileButton.classList.toggle("is-busy", busy);
      fileButton.setAttribute("aria-busy", busy ? "true" : "false");
    }
  }

  function applyStatus(snapshot) {
    const brfReady = !!snapshot.has_brf;
    btnBrf.setAttribute("aria-disabled", brfReady ? "false" : "true");
    btnBrf.tabIndex = brfReady ? 0 : -1;
    if (brfWhy) {
      brfWhy.textContent = brfReady
        ? "변환된 BRF 파일을 받습니다."
        : "먼저 PDF를 선택해 변환하세요.";
    }

    const dtReady = !!snapshot.dtbook_download_available;
    btnDtbook.setAttribute("aria-disabled", dtReady ? "false" : "true");
    btnDtbook.tabIndex = dtReady ? 0 : -1;
    if (dtbookWhy) {
      dtbookWhy.textContent = dtReady
        ? "DAISY 제작용 중간 구조(DTBook 2005-3) XML을 받습니다."
        : "먼저 PDF를 선택해 변환하세요.";
    }
  }

  async function refreshStatus() {
    const res = await fetch("/api/status");
    const data = await res.json();
    applyStatus(data);
  }

  async function uploadAndConvert(file) {
    setBusy(true);
    if (fileNameEl) {
      fileNameEl.textContent = `선택한 파일: ${file.name}`;
    }
    setStatus("PDF를 올리고 분석·점역하는 중…");
    const body = new FormData();
    body.append("file", file);
    try {
      const res = await fetch("/api/upload-and-convert", {
        method: "POST",
        body,
      });
      let data;
      try {
        data = await res.json();
      } catch (_) {
        setAlert(
          res.status === 404
            ? "서버 API를 찾을 수 없습니다. 웹 서버를 다시 시작해 주세요."
            : "서버 응답을 읽지 못했습니다."
        );
        await refreshStatus().catch(() => {});
        return;
      }
      if (!data.ok) {
        await refreshStatus().catch(() => {});
        setAlert(data.message || "변환에 실패했습니다.");
        return;
      }
      applyStatus(data.status);
      setStatus(data.message);
      if (data.status && data.status.has_brf) {
        btnBrf.focus();
      }
    } catch (err) {
      await refreshStatus().catch(() => {});
      setAlert("업로드·변환 중 오류가 발생했습니다.");
    } finally {
      setBusy(false);
      fileInput.value = "";
    }
  }

  fileInput.addEventListener("change", () => {
    const file = fileInput.files && fileInput.files[0];
    if (!file) {
      return;
    }
    uploadAndConvert(file);
  });

  btnBrf.addEventListener("click", (event) => {
    if (btnBrf.getAttribute("aria-disabled") === "true") {
      event.preventDefault();
    }
  });
  btnDtbook.addEventListener("click", (event) => {
    if (btnDtbook.getAttribute("aria-disabled") === "true") {
      event.preventDefault();
    }
  });

  refreshStatus().catch(() => {});
})();
