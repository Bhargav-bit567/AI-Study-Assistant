document.addEventListener("DOMContentLoaded", () => {
  const API_BASE = "";

  // ── State ──────────────────────────────────────────────────────────────────
  let currentFile = null;
  let currentMCQs = [];
  let currentResultId = null;
  let authToken = localStorage.getItem("auth_token") || null;
  let currentUser = JSON.parse(localStorage.getItem("auth_user") || "null");

  // ── Element refs ───────────────────────────────────────────────────────────
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
  const guestNote = document.getElementById("guestNote");

  // Auth elements
  const authButtons = document.getElementById("authButtons");
  const userMenu = document.getElementById("userMenu");
  const userEmail = document.getElementById("userEmail");
  const btnShowSignIn = document.getElementById("btnShowSignIn");
  const btnShowSignUp = document.getElementById("btnShowSignUp");
  const btnSignOut = document.getElementById("btnSignOut");
  const btnHistory = document.getElementById("btnHistory");
  const authModal = document.getElementById("authModal");
  const closeAuthModal = document.getElementById("closeAuthModal");
  const signInForm = document.getElementById("signInForm");
  const signUpForm = document.getElementById("signUpForm");
  const signInError = document.getElementById("signInError");
  const signUpError = document.getElementById("signUpError");
  const switchToSignUp = document.getElementById("switchToSignUp");
  const switchToSignIn = document.getElementById("switchToSignIn");
  const btnSignIn = document.getElementById("btnSignIn");
  const btnSignUp = document.getElementById("btnSignUp");
  const signInPrompt = document.getElementById("signInPrompt");

  // History elements
  const historyPanel = document.getElementById("historyPanel");
  const closeHistory = document.getElementById("closeHistory");
  const historyList = document.getElementById("historyList");
  const quizHistoryList = document.getElementById("quizHistoryList");
  const tabBtns = document.querySelectorAll(".tab-btn");

  // ── Health check ───────────────────────────────────────────────────────────
  async function checkHealth() {
    try {
      const res = await fetch(`${API_BASE}/health`);
      backendStatus.textContent = res.ok ? "Backend Connected" : "Backend Offline";
    } catch {
      backendStatus.textContent = "Backend Offline";
    }
  }
  checkHealth();

  // ── Auth UI state ──────────────────────────────────────────────────────────
  function updateAuthUI() {
    if (authToken && currentUser) {
      authButtons.classList.add("hidden");
      userMenu.classList.remove("hidden");
      userEmail.textContent = currentUser.email;
      guestNote.classList.add("hidden");
    } else {
      authButtons.classList.remove("hidden");
      userMenu.classList.add("hidden");
      if (currentFile) guestNote.classList.remove("hidden");
    }
  }
  updateAuthUI();

  // ── Auth modal ─────────────────────────────────────────────────────────────
  function openAuthModal(mode = "signin") {
    authModal.classList.remove("hidden");
    if (mode === "signup") {
      signInForm.classList.add("hidden");
      signUpForm.classList.remove("hidden");
    } else {
      signUpForm.classList.add("hidden");
      signInForm.classList.remove("hidden");
    }
  }

  btnShowSignIn.addEventListener("click", () => openAuthModal("signin"));
  btnShowSignUp.addEventListener("click", () => openAuthModal("signup"));
  signInPrompt.addEventListener("click", () => openAuthModal("signin"));
  closeAuthModal.addEventListener("click", () => authModal.classList.add("hidden"));
  authModal.addEventListener("click", (e) => { if (e.target === authModal) authModal.classList.add("hidden"); });
  switchToSignUp.addEventListener("click", () => { signInForm.classList.add("hidden"); signUpForm.classList.remove("hidden"); });
  switchToSignIn.addEventListener("click", () => { signUpForm.classList.add("hidden"); signInForm.classList.remove("hidden"); });

  // Sign In
  btnSignIn.addEventListener("click", async () => {
    const email = document.getElementById("signInEmail").value.trim();
    const password = document.getElementById("signInPassword").value;
    signInError.classList.add("hidden");
    btnSignIn.textContent = "Signing in...";
    try {
      const res = await fetch(`${API_BASE}/api/auth/signin`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Sign in failed");
      authToken = data.access_token;
      currentUser = { email: data.email, id: data.user_id };
      localStorage.setItem("auth_token", authToken);
      localStorage.setItem("auth_user", JSON.stringify(currentUser));
      authModal.classList.add("hidden");
      updateAuthUI();
    } catch (err) {
      signInError.textContent = err.message;
      signInError.classList.remove("hidden");
    } finally {
      btnSignIn.textContent = "Sign In";
    }
  });

  // Sign Up
  btnSignUp.addEventListener("click", async () => {
    const full_name = document.getElementById("signUpName").value.trim();
    const email = document.getElementById("signUpEmail").value.trim();
    const password = document.getElementById("signUpPassword").value;
    signUpError.classList.add("hidden");
    btnSignUp.textContent = "Creating account...";
    try {
      const res = await fetch(`${API_BASE}/api/auth/signup`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password, full_name }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Sign up failed");

      if (data.confirmation_required) {
        signUpError.textContent = `Account created. Please check ${data.email} to confirm your email before signing in.`;
        signUpError.classList.remove("hidden");
        return;
      }

      authToken = data.access_token;
      currentUser = { email: data.email, id: data.user_id };
      localStorage.setItem("auth_token", authToken);
      localStorage.setItem("auth_user", JSON.stringify(currentUser));
      authModal.classList.add("hidden");
      updateAuthUI();
    } catch (err) {
      signUpError.textContent = err.message;
      signUpError.classList.remove("hidden");
    } finally {
      btnSignUp.textContent = "Create Account";
    }
  });

  // Sign Out
  btnSignOut.addEventListener("click", () => {
    authToken = null;
    currentUser = null;
    localStorage.removeItem("auth_token");
    localStorage.removeItem("auth_user");
    updateAuthUI();
  });

  // ── History panel ──────────────────────────────────────────────────────────
  btnHistory.addEventListener("click", async () => {
    historyPanel.classList.remove("hidden");
    loadHistory();
    loadStats();
  });
  closeHistory.addEventListener("click", () => historyPanel.classList.add("hidden"));
  historyPanel.addEventListener("click", (e) => { if (e.target === historyPanel) historyPanel.classList.add("hidden"); });

  tabBtns.forEach(btn => {
    btn.addEventListener("click", () => {
      tabBtns.forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      document.querySelectorAll(".tab-content").forEach(t => t.classList.add("hidden"));
      document.getElementById(btn.dataset.tab).classList.remove("hidden");
      if (btn.dataset.tab === "quizTab") loadQuizHistory();
    });
  });

  async function loadStats() {
    try {
      const res = await fetch(`${API_BASE}/api/stats`, {
        headers: { Authorization: `Bearer ${authToken}` },
      });
      if (!res.ok) return;
      const data = await res.json();
      document.getElementById("statDocs").textContent = data.documents_count;
      document.getElementById("statResults").textContent = data.results_count;
      document.getElementById("statQuizzes").textContent = data.quiz_attempts_count;
      document.getElementById("statScore").textContent = data.average_score_pct + "%";
    } catch {}
  }

  async function loadHistory() {
    historyList.innerHTML = "<p class='text-muted'>Loading...</p>";
    try {
      const res = await fetch(`${API_BASE}/api/history/results`, {
        headers: { Authorization: `Bearer ${authToken}` },
      });
      const data = await res.json();
      if (!data.length) { historyList.innerHTML = "<p class='text-muted'>No results yet. Upload a PDF to get started.</p>"; return; }
      historyList.innerHTML = data.map(r => `
        <div class="history-item" data-id="${r.id}" data-action="${r.action}">
          <div class="history-meta">
            <span class="pill ${r.action === 'summary' ? 'pill-cyan' : 'pill-purple'}">${r.action === 'summary' ? 'Summary' : 'MCQs'}</span>
            <span class="history-filename">${r.documents?.filename || 'Unknown file'}</span>
          </div>
          <span class="history-date">${new Date(r.created_at).toLocaleDateString()}</span>
          <button class="btn btn-ghost btn-sm load-result-btn" data-id="${r.id}" data-action="${r.action}">Load</button>
        </div>
      `).join("");

      historyList.querySelectorAll(".load-result-btn").forEach(btn => {
        btn.addEventListener("click", async () => {
          const resultId = btn.dataset.id;
          const action = btn.dataset.action;
          const res2 = await fetch(`${API_BASE}/api/history/results/${resultId}`, {
            headers: { Authorization: `Bearer ${authToken}` },
          });
          const result = await res2.json();
          historyPanel.classList.add("hidden");
          resultsContainer.classList.remove("hidden");
          currentResultId = resultId;
          if (action === "summary") {
            renderSummary(result);
          } else {
            renderMCQs(result);
          }
        });
      });
    } catch {
      historyList.innerHTML = "<p class='text-muted'>Failed to load history.</p>";
    }
  }

  async function loadQuizHistory() {
    quizHistoryList.innerHTML = "<p class='text-muted'>Loading...</p>";
    try {
      const res = await fetch(`${API_BASE}/api/history/quiz`, {
        headers: { Authorization: `Bearer ${authToken}` },
      });
      const data = await res.json();
      if (!data.length) { quizHistoryList.innerHTML = "<p class='text-muted'>No quiz attempts yet.</p>"; return; }
      quizHistoryList.innerHTML = data.map(a => `
        <div class="history-item">
          <div class="history-meta">
            <span class="history-filename">${a.results?.documents?.filename || 'Unknown file'}</span>
          </div>
          <div class="quiz-score-inline">
            <span class="score-num">${a.score}/${a.total}</span>
            <span class="score-pct">${Math.round((a.score/a.total)*100)}%</span>
          </div>
          <span class="history-date">${new Date(a.attempted_at).toLocaleDateString()}</span>
        </div>
      `).join("");
    } catch {
      quizHistoryList.innerHTML = "<p class='text-muted'>Failed to load quiz history.</p>";
    }
  }

  // ── File handling ──────────────────────────────────────────────────────────
  browseBtn.addEventListener("click", () => fileInput.click());
  dropZone.addEventListener("click", (e) => { if (e.target !== browseBtn) fileInput.click(); });

  ["dragenter", "dragover"].forEach(e => dropZone.addEventListener(e, (ev) => { ev.preventDefault(); dropZone.classList.add("dragover"); }));
  ["dragleave", "drop"].forEach(e => dropZone.addEventListener(e, (ev) => { ev.preventDefault(); dropZone.classList.remove("dragover"); }));
  dropZone.addEventListener("drop", (e) => { if (e.dataTransfer.files.length > 0) handleFile(e.dataTransfer.files[0]); });
  fileInput.addEventListener("change", (e) => { if (e.target.files.length > 0) handleFile(e.target.files[0]); });

  function formatBytes(bytes, decimals = 2) {
    if (bytes === 0) return "0 Bytes";
    const k = 1024, dm = decimals < 0 ? 0 : decimals;
    const sizes = ["Bytes", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + " " + sizes[i];
  }

  function handleFile(file) {
    if (!file.name.toLowerCase().endsWith(".pdf") && file.type !== "application/pdf") {
      showError("Please select a valid PDF file."); return;
    }
    currentFile = file;
    fileNameEl.textContent = file.name;
    fileSizeEl.textContent = formatBytes(file.size);
    dropZone.classList.add("hidden");
    filePreview.classList.remove("hidden");
    btnSummary.disabled = false;
    btnMCQs.disabled = false;
    hideError();
    if (!authToken) guestNote.classList.remove("hidden");
  }

  removeFileBtn.addEventListener("click", () => {
    currentFile = null;
    fileInput.value = "";
    filePreview.classList.add("hidden");
    dropZone.classList.remove("hidden");
    btnSummary.disabled = true;
    btnMCQs.disabled = true;
    guestNote.classList.add("hidden");
  });

  closeAlertBtn.addEventListener("click", hideError);
  function showError(msg) { errorMessage.textContent = msg; errorBanner.classList.remove("hidden"); }
  function hideError() { errorBanner.classList.add("hidden"); }

  function setLoading(isLoading, action = "summary") {
    if (isLoading) {
      hideError();
      btnSummary.disabled = true;
      btnMCQs.disabled = true;
      loadingCard.classList.remove("hidden");
      loadingTitle.textContent = action === "summary"
        ? "Azure Foundry Agent is generating your summary..."
        : "Azure Foundry Agent is crafting MCQs...";
      loadingDesc.textContent = action === "summary"
        ? "Scanning concepts, formulas, and definitions."
        : "Synthesizing challenging questions with explanations.";
    } else {
      btnSummary.disabled = !currentFile;
      btnMCQs.disabled = !currentFile;
      loadingCard.classList.add("hidden");
    }
  }

  // ── Study actions ──────────────────────────────────────────────────────────
  btnSummary.addEventListener("click", () => triggerStudyAction("summary"));
  btnMCQs.addEventListener("click", () => triggerStudyAction("mcqs"));

  async function triggerStudyAction(action) {
    if (!currentFile) return;
    setLoading(true, action);
    const formData = new FormData();
    formData.append("file", currentFile);
    formData.append("action", action);

    try {
      const headers = {};
      if (authToken) headers["Authorization"] = `Bearer ${authToken}`;

      const response = await fetch(`${API_BASE}/api/study`, {
        method: "POST",
        headers,
        body: formData,
      });
      if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        throw new Error(err.detail || `Server error (${response.status})`);
      }
      const data = await response.json();
      currentResultId = data.result_id || null;
      resultsContainer.classList.remove("hidden");
      if (action === "summary") renderSummary(data);
      else renderMCQs(data);
    } catch (err) {
      showError(err.message || "Failed to process the document.");
    } finally {
      setLoading(false, action);
    }
  }

  // ── Render summary ─────────────────────────────────────────────────────────
  function renderSummary(data) {
    summaryContent.innerHTML = "";

    // ── 1. Narrative Overview ──────────────────────────────────────────────
    const overviewText = data.summary || "No summary was generated.";
    const overviewBlock = document.createElement("div");
    overviewBlock.className = "summary-overview";
    overviewText.split(/\n{2,}/).forEach(para => {
      if (!para.trim()) return;
      const p = document.createElement("p");
      p.textContent = para.trim();
      overviewBlock.appendChild(p);
    });
    summaryContent.appendChild(overviewBlock);

    // ── 2. Detailed Sections ───────────────────────────────────────────────
    const sections = data.sections || [];
    if (sections.length > 0) {
      const sectionsWrap = document.createElement("div");
      sectionsWrap.className = "summary-sections";
      const sectLabel = document.createElement("h4");
      sectLabel.className = "summary-section-group-label";
      sectLabel.textContent = "Detailed Breakdown";
      sectionsWrap.appendChild(sectLabel);
      sections.forEach(sec => {
        const secEl = document.createElement("div");
        secEl.className = "summary-section";
        const titleEl = document.createElement("div");
        titleEl.className = "summary-section-title";
        titleEl.innerHTML = `<span class="section-dot"></span>${sec.title || "Section"}`;
        const bodyEl = document.createElement("p");
        bodyEl.className = "summary-section-body";
        bodyEl.textContent = sec.content || "";
        secEl.appendChild(titleEl);
        secEl.appendChild(bodyEl);
        sectionsWrap.appendChild(secEl);
      });
      summaryContent.appendChild(sectionsWrap);
    }

    // ── 3. Key Points ──────────────────────────────────────────────────────
    keyPointsList.innerHTML = "";
    const kps = data.key_points || [];
    if (kps.length > 0) {
      kps.forEach((p, i) => {
        const li = document.createElement("li");
        li.innerHTML = `<span class="kp-badge">${i + 1}</span><span>${p}</span>`;
        keyPointsList.appendChild(li);
      });
      keyPointsList.parentElement.classList.remove("hidden");
    } else {
      keyPointsList.parentElement.classList.add("hidden");
    }

    // ── 4. Key Terms Glossary ──────────────────────────────────────────────
    const existingGlossary = summaryContent.parentElement.querySelector(".key-terms-section");
    if (existingGlossary) existingGlossary.remove();

    const keyTerms = data.key_terms || [];
    if (keyTerms.length > 0) {
      const glossarySection = document.createElement("div");
      glossarySection.className = "key-terms-section";
      const glossLabel = document.createElement("h4");
      glossLabel.className = "key-points-heading";
      glossLabel.textContent = "Key Terms Glossary";
      glossarySection.appendChild(glossLabel);
      const grid = document.createElement("div");
      grid.className = "key-terms-grid";
      keyTerms.forEach(kt => {
        const card = document.createElement("div");
        card.className = "key-term-card";
        const chip = document.createElement("div");
        chip.className = "term-chip";
        chip.textContent = kt.term || "";
        const def = document.createElement("p");
        def.className = "term-def";
        def.textContent = kt.definition || "";
        card.appendChild(chip);
        card.appendChild(def);
        grid.appendChild(card);
      });
      glossarySection.appendChild(grid);
      summaryCard.querySelector(".key-points-section").after(glossarySection);
    }

    // ── 5. Study Tips ──────────────────────────────────────────────────────
    const existingTips = summaryContent.parentElement.querySelector(".study-tips-section");
    if (existingTips) existingTips.remove();

    const tips = data.study_tips || [];
    if (tips.length > 0) {
      const tipsSection = document.createElement("div");
      tipsSection.className = "study-tips-section";
      const tipsLabel = document.createElement("h4");
      tipsLabel.className = "key-points-heading study-tips-heading";
      tipsLabel.innerHTML = "<span>💡</span> Study Tips";
      tipsSection.appendChild(tipsLabel);
      const tipsList = document.createElement("ul");
      tipsList.className = "study-tips-list";
      tips.forEach(tip => {
        const li = document.createElement("li");
        li.className = "study-tip-item";
        li.textContent = tip;
        tipsList.appendChild(li);
      });
      tipsSection.appendChild(tipsList);
      // Append after glossary if present, otherwise after key-points
      const afterEl = summaryCard.querySelector(".key-terms-section") ||
                      summaryCard.querySelector(".key-points-section");
      if (afterEl) afterEl.after(tipsSection);
      else summaryCard.appendChild(tipsSection);
    }

    summaryCard.classList.remove("hidden");
    summaryCard.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  copySummaryBtn.addEventListener("click", () => {
    let text = "=== SUMMARY ===\n" + (summaryContent.querySelector(".summary-overview")?.innerText || "") + "\n\n";

    summaryContent.querySelectorAll(".summary-section").forEach(s => {
      const title = s.querySelector(".summary-section-title")?.innerText || "";
      const body = s.querySelector(".summary-section-body")?.innerText || "";
      text += `--- ${title} ---\n${body}\n\n`;
    });

    text += "=== KEY POINTS ===\n";
    keyPointsList.querySelectorAll("li").forEach(li => { text += `• ${li.querySelector("span:last-child")?.textContent}\n`; });

    const glossaryCards = summaryCard.querySelectorAll(".key-term-card");
    if (glossaryCards.length) {
      text += "\n=== KEY TERMS ===\n";
      glossaryCards.forEach(c => {
        text += `${c.querySelector(".term-chip")?.textContent}: ${c.querySelector(".term-def")?.textContent}\n`;
      });
    }

    const tipItems = summaryCard.querySelectorAll(".study-tip-item");
    if (tipItems.length) {
      text += "\n=== STUDY TIPS ===\n";
      tipItems.forEach(t => { text += `• ${t.textContent}\n`; });
    }

    navigator.clipboard.writeText(text).then(() => {
      const orig = copySummaryBtn.innerHTML;
      copySummaryBtn.innerHTML = "<span>Copied!</span>";
      setTimeout(() => (copySummaryBtn.innerHTML = orig), 2000);
    });
  });

  // ── Render MCQs ────────────────────────────────────────────────────────────
  function renderMCQs(data) {
    currentMCQs = data.mcqs || [];
    mcqList.innerHTML = "";
    quizScoreBadge.classList.add("hidden");
    btnResetQuiz.classList.add("hidden");
    btnSubmitQuiz.classList.remove("hidden");
    btnSubmitQuiz.disabled = false;

    if (!currentMCQs.length) {
      mcqList.innerHTML = "<p class='text-muted'>No questions returned.</p>";
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

      item.options.forEach(opt => {
        const label = document.createElement("label");
        label.className = "mcq-option-label";
        const radio = document.createElement("input");
        radio.type = "radio";
        radio.name = `q_${index}`;
        radio.value = opt;
        radio.addEventListener("change", () => {
          optGroup.querySelectorAll(".mcq-option-label").forEach(l => l.classList.remove("selected"));
          label.classList.add("selected");
        });
        const span = document.createElement("span");
        span.textContent = opt;
        label.appendChild(radio);
        label.appendChild(span);
        optGroup.appendChild(label);
      });

      itemEl.appendChild(optGroup);
      const expDiv = document.createElement("div");
      expDiv.className = "mcq-explanation hidden";
      expDiv.textContent = `💡 ${item.explanation}`;
      itemEl.appendChild(expDiv);
      mcqList.appendChild(itemEl);
    });

    mcqCard.classList.remove("hidden");
    mcqCard.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  // ── Quiz scoring ───────────────────────────────────────────────────────────
  btnSubmitQuiz.addEventListener("click", async () => {
    let score = 0;
    const answers = [];

    currentMCQs.forEach((item, index) => {
      const itemEl = mcqList.querySelector(`[data-index="${index}"]`);
      const selected = itemEl.querySelector(`input[name="q_${index}"]:checked`);
      itemEl.querySelector(".mcq-explanation").classList.remove("hidden");

      itemEl.querySelectorAll(".mcq-option-label").forEach(opt => {
        if (opt.querySelector("input").value === item.correct_answer) opt.classList.add("correct");
      });

      const isCorrect = selected && selected.value === item.correct_answer;
      if (isCorrect) score++;
      else if (selected) selected.parentElement.classList.add("incorrect");

      answers.push({ question: item.question, selected: selected?.value || null, correct: item.correct_answer, is_correct: isCorrect });
    });

    scoreValue.textContent = score;
    scoreTotal.textContent = currentMCQs.length;
    quizScoreBadge.classList.remove("hidden");
    btnSubmitQuiz.classList.add("hidden");
    btnResetQuiz.classList.remove("hidden");

    // Save attempt if authenticated and we have a result_id
    if (authToken && currentResultId) {
      try {
        await fetch(`${API_BASE}/api/history/quiz`, {
          method: "POST",
          headers: { "Content-Type": "application/json", Authorization: `Bearer ${authToken}` },
          body: JSON.stringify({ result_id: currentResultId, score, total: currentMCQs.length, answers }),
        });
      } catch {}
    }
  });

  btnResetQuiz.addEventListener("click", () => renderMCQs({ mcqs: currentMCQs }));
});
