document.querySelectorAll(".tab-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".tab-panel").forEach((p) => p.classList.remove("active"));
    btn.classList.add("active");
    document.getElementById("tab-" + btn.dataset.tab).classList.add("active");
  });
});

async function loadCases() {
  const resp = await fetch("/api/cases");
  const data = await resp.json();
  const list = document.getElementById("case-list");
  list.innerHTML = "";
  data.cases.forEach((c) => {
    const div = document.createElement("div");
    div.className = "list-item";
    div.textContent = `${c.name} — ${c.created_at}`;
    list.appendChild(div);
  });
  document.querySelectorAll(".case-select-target").forEach((select) => {
    const current = select.value;
    select.innerHTML = '<option value="">— без дела —</option>';
    data.cases.forEach((c) => {
      const opt = document.createElement("option");
      opt.value = c.id;
      opt.textContent = c.name;
      select.appendChild(opt);
    });
    select.value = current;
  });
  return data.cases;
}

document.getElementById("chat-case-select").classList.add("case-select-target");
document.getElementById("document-case-select").classList.add("case-select-target");
document.getElementById("contract-case-select").classList.add("case-select-target");

document.getElementById("case-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const errorEl = document.getElementById("case-error");
  errorEl.textContent = "";
  const form = new FormData(e.target);
  try {
    const resp = await fetch("/api/cases", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(Object.fromEntries(form.entries())),
    });
    if (!resp.ok) {
      const err = await resp.json();
      errorEl.textContent = err.detail || "Ошибка запроса";
      return;
    }
    e.target.reset();
    loadCases();
  } catch (err) {
    errorEl.textContent = "Сетевая ошибка: " + err.message;
  }
});

loadCases();

const CHAT_SESSION_ID = "session-" + Date.now();
const chatLog = document.getElementById("chat-log");
const chatError = document.getElementById("chat-error");

function appendMessage(role, content) {
  const div = document.createElement("div");
  div.className = "msg " + role;
  div.textContent = content;
  chatLog.appendChild(div);
  chatLog.scrollTop = chatLog.scrollHeight;
}

document.getElementById("chat-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  chatError.textContent = "";
  const input = document.getElementById("chat-input");
  const message = input.value.trim();
  if (!message) return;
  appendMessage("user", message);
  input.value = "";
  try {
    const caseId = document.getElementById("chat-case-select").value;
    const resp = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: CHAT_SESSION_ID, message, case_id: caseId || null }),
    });
    if (!resp.ok) {
      const err = await resp.json();
      chatError.textContent = err.detail || "Ошибка запроса";
      return;
    }
    const data = await resp.json();
    appendMessage("assistant", data.reply);
  } catch (err) {
    chatError.textContent = "Сетевая ошибка: " + err.message;
  }
});

async function loadDocumentList() {
  const resp = await fetch("/api/documents");
  const data = await resp.json();
  const list = document.getElementById("document-list");
  list.innerHTML = "";
  data.documents.forEach((doc) => {
    const div = document.createElement("div");
    div.className = "list-item";
    div.innerHTML = `${doc.doc_type} — ${doc.created_at} — <a href="/api/documents/${doc.id}/download">txt</a> / <a href="/api/documents/${doc.id}/download.docx">docx</a>`;
    list.appendChild(div);
  });
}

document.getElementById("document-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const errorEl = document.getElementById("document-error");
  const resultEl = document.getElementById("document-result");
  errorEl.textContent = "";
  resultEl.textContent = "";
  const form = new FormData(e.target);
  const payload = Object.fromEntries(form.entries());
  try {
    const resp = await fetch("/api/documents/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!resp.ok) {
      const err = await resp.json();
      errorEl.textContent = err.detail || "Ошибка запроса";
      return;
    }
    const data = await resp.json();
    resultEl.textContent = data.text;
    loadDocumentList();
  } catch (err) {
    errorEl.textContent = "Сетевая ошибка: " + err.message;
  }
});

loadDocumentList();

async function loadContractList() {
  const resp = await fetch("/api/contracts");
  const data = await resp.json();
  const list = document.getElementById("contract-list");
  list.innerHTML = "";
  data.contracts.forEach((c) => {
    const div = document.createElement("div");
    div.className = "list-item";
    div.textContent = `${c.source_filename} — ${c.created_at}`;
    list.appendChild(div);
  });
}

document.getElementById("contract-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const errorEl = document.getElementById("contract-error");
  const resultEl = document.getElementById("contract-result");
  errorEl.textContent = "";
  resultEl.textContent = "";
  const form = new FormData(e.target);
  try {
    const resp = await fetch("/api/contracts/analyze", { method: "POST", body: form });
    if (!resp.ok) {
      const err = await resp.json();
      errorEl.textContent = err.detail || "Ошибка запроса";
      return;
    }
    const data = await resp.json();
    resultEl.textContent = data.analysis;
    loadContractList();
  } catch (err) {
    errorEl.textContent = "Сетевая ошибка: " + err.message;
  }
});

loadContractList();
