(() => {
  const statusEl = document.getElementById("status");
  const alertEl = document.getElementById("alert");
  const uploadForm = document.getElementById("upload-form");
  const btnConvert = document.getElementById("btn-convert");
  const convertWhy = document.getElementById("convert-why");
  const btnBrf = document.getElementById("btn-brf");
  const brfWhy = document.getElementById("brf-why");
  const btnDtbook = document.getElementById("btn-dtbook");
  const dtbookWhy = document.getElementById("dtbook-why");

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
    alertEl.focus?.();
  }

  function applyStatus(snapshot) {
    btnConvert.disabled = !snapshot.has_pdf;
    convertWhy.textContent = snapshot.has_pdf
      ? "업로드한 파일로 분석과 점역을 시작합니다."
      : "PDF를 먼저 업로드하세요.";

    const brfReady = !!snapshot.has_brf;
    btnBrf.setAttribute("aria-disabled", brfReady ? "false" : "true");
    btnBrf.tabIndex = brfReady ? 0 : -1;
    brfWhy.textContent = brfReady
      ? "변환된 BRF 파일을 받습니다."
      : "먼저 분석 및 변환을 실행하세요.";

    const dtReady = !!snapshot.dtbook_download_available;
    btnDtbook.setAttribute("aria-disabled", dtReady ? "false" : "true");
    btnDtbook.tabIndex = dtReady ? 0 : -1;
    dtbookWhy.textContent = dtReady
      ? "DAISY용 중간 구조 XML을 받습니다."
      : "DTBook XML 다운로드는 아직 준비 중입니다.";
  }

  async function refreshStatus() {
    const res = await fetch("/api/status");
    const data = await res.json();
    applyStatus(data);
  }

  uploadForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const fileInput = document.getElementById("pdf-file");
    if (!fileInput.files || !fileInput.files[0]) {
      setAlert("PDF 파일을 선택하세요.");
      return;
    }
    setStatus("PDF를 올리는 중…");
    const body = new FormData();
    body.append("file", fileInput.files[0]);
    try {
      const res = await fetch("/api/upload", { method: "POST", body });
      const data = await res.json();
      if (!data.ok) {
        setAlert(data.message || "업로드에 실패했습니다.");
        return;
      }
      applyStatus(data.status);
      setStatus(data.message);
      btnConvert.focus();
    } catch (err) {
      setAlert("업로드 중 오류가 발생했습니다.");
    }
  });

  btnConvert.addEventListener("click", async () => {
    setStatus("PDF 분석 및 점역 변환 중…");
    btnConvert.disabled = true;
    try {
      const res = await fetch("/api/convert", { method: "POST" });
      const data = await res.json();
      if (!data.ok) {
        applyStatus(await (await fetch("/api/status")).json());
        setAlert(data.message || "변환에 실패했습니다.");
        return;
      }
      applyStatus(data.status);
      setStatus(data.message);
      if (data.status.has_brf) {
        btnBrf.focus();
      }
    } catch (err) {
      await refreshStatus();
      setAlert("변환 중 오류가 발생했습니다.");
    }
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
