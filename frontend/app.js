document.addEventListener("DOMContentLoaded", () => {
  // API base URL — points to FastAPI server.
  // If the page is served by uvicorn on port 8000, use same-origin (empty string).
  // If the HTML is opened directly from disk or any other port, point to localhost:8000.
  const API_BASE =
    window.location.port === "8000"
      ? ""
      : "http://localhost:8000";

  // Elements
  const dropZone = document.getElementById("dropZone");
  const fileInput = document.getElementById("fileInput");
  const browseBtn = document.getElementById("browseBtn");
  const filePreview = document.getElementById("filePreview");
  const fileNameEl = document.getElementById("fileName");
  const fileSizeEl = document.getElementById("fileSize");
  const removeFileBtn = document.getElementById("removeFileBtn");

  const btnSummary = document.getElementById("btnSummary");
  const btnMCQs = document.getElementById("btnMCQs");

  const errorBanner = document.getElementById("errorBanner");
  const errorMessage = document.getElementById("errorMessage");
  const closeAlertBtn = document.getElementById("closeAlertBtn");

  const loadingCard = document.getElementById("loadingCard");
  const loadingTitle = document.getElementById("loadingTitle");
  const loadingDesc = document.getElementById("loadingDesc");

  const resultsContainer = document.getElementById("resultsContainer");
  const summaryCard = document.getElementById("summaryCard");
  const summaryContent = document.getElementById("summaryContent");
  const keyPointsList = document.getElementById("keyPointsList");
  const copySummaryBtn = document.getElementById("copySummaryBtn");

  const mcqCard = document.getElementById("mcqCard");
  const mcqList = document.getElementById("mcqList");
  const btnSubmitQuiz = document.getElementById("btnSubmitQuiz");
  const btnResetQuiz = document.getElementById("btnResetQuiz");
  const quizScoreBadge = document.getElementById("quizScoreBadge");
  const scoreValue = document.getElementById("scoreValue");
  const scoreTotal = document.getElementById("scoreTotal");
  const backendStatus = document.getElementById("backendStatus");

  let currentFile = null;
  let currentMCQs = [];

  // Check Backend Health
  async function checkHealth() {
    try {
      const res = await fetch(`${API_BASE}/health`);
      if (res.ok) {
        backendStatus.textContent = "Backend Connected";
      } else {
        backendStatus.textContent = "Backend Offline";
      }
    } catch {
      backendStatus.textContent = "Backend Offline";
    }
  }
  checkHealth();

  // Drag & Drop
  browseBtn.addEventListener("click", () => fileInput.click());
  dropZone.addEventListener("click", (e) => {
    if (e.target !== browseBtn) fileInput.click();
  });

  ["dragenter", "dragover"].forEach((eventName) => {
    dropZone.addEventListener(eventName, (e) => {
      e.preventDefault();
      dropZone.classList.add("dragover");
    });
  });

  ["dragleave", "drop"].forEach((eventName) => {
    dropZone.addEventListener(eventName, (e) => {
      e.preventDefault();
      dropZone.classList.remove("dragover");
    });
  });

  dropZone.addEventListener("drop", (e) => {
    const files = e.dataTransfer.files;
    if (files.length > 0) handleFile(files[0]);
  });

  fileInput.addEventListener("change", (e) => {
    if (e.target.files.length > 0) handleFile(e.target.files[0]);
  });

  function formatBytes(bytes, decimals = 2) {
    if (bytes === 0) return "0 Bytes";
    const k = 1024;
    const dm = decimals < 0 ? 0 : decimals;
    const sizes = ["Bytes", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + " " + sizes[i];
  }

  function handleFile(file) {
    if (!file.name.toLowerCase().endsWith(".pdf") && file.type !== "application/pdf") {
      showError("Please select a valid PDF file.");
      return;
    }
    currentFile = file;
    fileNameEl.textContent = file.name;
    fileSizeEl.textContent = formatBytes(file.size);

    dropZone.classList.add("hidden");
    filePreview.classList.remove("hidden");
    btnSummary.disabled = false;
    btnMCQs.disabled = false;
    hideError();
  }

  removeFileBtn.addEventListener("click", () => {
    currentFile = null;
    fileInput.value = "";
    filePreview.classList.add("hidden");
    dropZone.classList.remove("hidden");
    btnSummary.disabled = true;
    btnMCQs.disabled = true;
  });

  closeAlertBtn.addEventListener("click", hideError);

  function showError(msg) {
    errorMessage.textContent = msg;
    errorBanner.classList.remove("hidden");
  }

  function hideError() {
    errorBanner.classList.add("hidden");
  }

  function setLoading(isLoading, action = "summary") {
    if (isLoading) {
      hideError();
      btnSummary.disabled = true;
      btnMCQs.disabled = true;
      loadingCard.classList.remove("hidden");
      if (action === "summary") {
        loadingTitle.textContent = "Azure Foundry Agent is generating your summary...";
        loadingDesc.textContent = "Scanning concepts, formulas, and definitions from your notes.";
      } else {
        loadingTitle.textContent = "Azure Foundry Agent is crafting MCQs...";
        loadingDesc.textContent = "Synthesizing challenging questions with explanations.";
      }
    } else {
      btnSummary.disabled = !currentFile;
      btnMCQs.disabled = !currentFile;
      loadingCard.classList.add("hidden");
    }
  }

  // Action: Generate Summary
  btnSummary.addEventListener("click", () => triggerStudyAction("summary"));
  btnMCQs.addEventListener("click", () => triggerStudyAction("mcqs"));

  async function triggerStudyAction(action) {
    if (!currentFile) return;

    setLoading(true, action);

    const formData = new FormData();
    formData.append("file", currentFile);
    formData.append("action", action);

    try {
      const response = await fetch(`${API_BASE}/api/study`, {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `Server returned error (${response.status})`);
      }

      const data = await response.json();
      resultsContainer.classList.remove("hidden");

      if (action === "summary") {
        renderSummary(data);
      } else if (action === "mcqs") {
        renderMCQs(data);
      }
    } catch (err) {
      console.error(err);
      showError(err.message || "Failed to process the document with Azure Foundry Agent.");
    } finally {
      setLoading(false, action);
    }
  }

  // Render Summary
  function renderSummary(data) {
    summaryContent.textContent = data.summary || "No summary was generated.";
    keyPointsList.innerHTML = "";

    if (data.key_points && data.key_points.length > 0) {
      data.key_points.forEach((point) => {
        const li = document.createElement("li");
        li.textContent = point;
        keyPointsList.appendChild(li);
      });
      keyPointsList.parentElement.classList.remove("hidden");
    } else {
      keyPointsList.parentElement.classList.add("hidden");
    }

    summaryCard.classList.remove("hidden");
    summaryCard.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  // Copy Summary
  copySummaryBtn.addEventListener("click", () => {
    let textToCopy = summaryContent.textContent + "\n\nCore Takeaways:\n";
    keyPointsList.querySelectorAll("li").forEach((li) => {
      textToCopy += `• ${li.textContent}\n`;
    });

    navigator.clipboard.writeText(textToCopy).then(() => {
      const originalHtml = copySummaryBtn.innerHTML;
      copySummaryBtn.innerHTML = "<span>Copied!</span>";
      setTimeout(() => (copySummaryBtn.innerHTML = originalHtml), 2000);
    });
  });

  // Render MCQs
  function renderMCQs(data) {
    currentMCQs = data.mcqs || [];
    mcqList.innerHTML = "";
    quizScoreBadge.classList.add("hidden");
    btnResetQuiz.classList.add("hidden");
    btnSubmitQuiz.classList.remove("hidden");
    btnSubmitQuiz.disabled = false;

    if (currentMCQs.length === 0) {
      mcqList.innerHTML = "<p class='text-muted'>No questions returned by the agent.</p>";
      mcqCard.classList.remove("hidden");
      return;
    }

    currentMCQs.forEach((item, index) => {
      const itemEl = document.createElement("div");
      itemEl.className = "mcq-item";
      itemEl.dataset.index = index;

      const qTitle = document.createElement("div");
      qTitle.className = "mcq-question";
      qTitle.textContent = `${index + 1}. ${item.question}`;
      itemEl.appendChild(qTitle);

      const optGroup = document.createElement("div");
      optGroup.className = "mcq-options";

      item.options.forEach((opt, optIndex) => {
        const label = document.createElement("label");
        label.className = "mcq-option-label";

        const radio = document.createElement("input");
        radio.type = "radio";
        radio.name = `q_${index}`;
        radio.value = opt;

        radio.addEventListener("change", () => {
          optGroup.querySelectorAll(".mcq-option-label").forEach((l) => l.classList.remove("selected"));
          label.classList.add("selected");
        });

        const span = document.createElement("span");
        span.textContent = opt;

        label.appendChild(radio);
        label.appendChild(span);
        optGroup.appendChild(label);
      });

      itemEl.appendChild(optGroup);

      // Explanation container (hidden initially)
      const expDiv = document.createElement("div");
      expDiv.className = "mcq-explanation hidden";
      expDiv.textContent = `💡 Explanation: ${item.explanation}`;
      itemEl.appendChild(expDiv);

      mcqList.appendChild(itemEl);
    });

    mcqCard.classList.remove("hidden");
    mcqCard.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  // Quiz submission & scoring
  btnSubmitQuiz.addEventListener("click", () => {
    let score = 0;
    let total = currentMCQs.length;

    currentMCQs.forEach((item, index) => {
      const itemEl = mcqList.querySelector(`[data-index="${index}"]`);
      const selectedRadio = itemEl.querySelector(`input[name="q_${index}"]:checked`);
      const expDiv = itemEl.querySelector(".mcq-explanation");
      expDiv.classList.remove("hidden");

      const options = itemEl.querySelectorAll(".mcq-option-label");
      options.forEach((optLabel) => {
        const val = optLabel.querySelector("input").value;
        if (val === item.correct_answer) {
          optLabel.classList.add("correct");
        }
      });

      if (selectedRadio) {
        if (selectedRadio.value === item.correct_answer) {
          score++;
        } else {
          selectedRadio.parentElement.classList.add("incorrect");
        }
      }
    });

    scoreValue.textContent = score;
    scoreTotal.textContent = total;
    quizScoreBadge.classList.remove("hidden");
    btnSubmitQuiz.classList.add("hidden");
    btnResetQuiz.classList.remove("hidden");
  });

  // Reset Quiz
  btnResetQuiz.addEventListener("click", () => {
    renderMCQs({ mcqs: currentMCQs });
  });
});
