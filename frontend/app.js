// Frontend estático servido pela própria API FastAPI (mesma origem), por isso
// os pedidos usam caminhos relativos ("/api/...") em vez de um URL absoluto.

const AGENT_TABS = ["evaluator", "analyst", "property", "location", "planner"];

const queryInput = document.getElementById("query-input");
const locationSuggestions = document.getElementById("location-suggestions");
const locationsDatalist = document.getElementById("locations-datalist");
const submitBtn = document.getElementById("submit-btn");
const inputError = document.getElementById("input-error");
const loadingSection = document.getElementById("loading");
const apiErrorSection = document.getElementById("api-error");
const needsInfoSection = document.getElementById("needs-info");
const needsInfoMessage = document.getElementById("needs-info-message");
const resultsSection = document.getElementById("results");

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

// Formatação "markdown-lite": escapa HTML primeiro (evita XSS), depois só
// permite **negrito** e quebras de linha — suficiente para o texto gerado
// pelos agentes, sem precisar de uma biblioteca de markdown.
function formatAgentText(text) {
  const escaped = escapeHtml(text);
  const bold = escaped.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  return bold.replace(/\n/g, "<br>");
}

function setHidden(el, hidden) {
  el.hidden = hidden;
}

function resetPanels() {
  setHidden(apiErrorSection, true);
  setHidden(needsInfoSection, true);
  setHidden(resultsSection, true);
  setHidden(inputError, true);
  apiErrorSection.textContent = "";
}

function renderAgentPanel(panelKey, agentOutput) {
  const panel = document.querySelector(`[data-panel="${panelKey}"]`);
  panel.innerHTML = "";

  if (!agentOutput) {
    const empty = document.createElement("p");
    empty.className = "agent-empty";
    empty.textContent = "Este agente não chegou a correr.";
    panel.appendChild(empty);
    return;
  }

  const final = document.createElement("div");
  final.className = "agent-final";
  final.innerHTML = formatAgentText(agentOutput.final);
  panel.appendChild(final);

  if (agentOutput.messages && agentOutput.messages.length > 1) {
    const details = document.createElement("details");
    details.className = "agent-history";

    const summary = document.createElement("summary");
    summary.textContent = `Ver histórico completo (${agentOutput.messages.length} mensagens)`;
    details.appendChild(summary);

    agentOutput.messages.forEach((msg) => {
      const msgEl = document.createElement("div");
      msgEl.className = "history-message";
      msgEl.innerHTML = formatAgentText(msg);
      details.appendChild(msgEl);
    });

    panel.appendChild(details);
  }
}

function renderResults(data) {
  AGENT_TABS.forEach((key) => renderAgentPanel(key, data[key]));
  setHidden(resultsSection, false);
}

function switchTab(tabKey) {
  document.querySelectorAll(".tab-btn").forEach((btn) => {
    const isActive = btn.dataset.tab === tabKey;
    btn.classList.toggle("active", isActive);
    btn.setAttribute("aria-selected", String(isActive));
  });
  document.querySelectorAll(".tab-panel").forEach((panel) => {
    panel.classList.toggle("active", panel.dataset.panel === tabKey);
  });
}

async function submitQuery() {
  const query = queryInput.value.trim();
  resetPanels();

  if (!query) {
    inputError.textContent = "Por favor, descreve o que procuras.";
    setHidden(inputError, false);
    return;
  }

  submitBtn.disabled = true;
  setHidden(loadingSection, false);

  try {
    const response = await fetch("/api/recommend", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query }),
    });

    const data = await response.json().catch(() => null);

    if (!response.ok) {
      const detail = data && data.detail ? data.detail : "Erro ao processar o pedido.";
      apiErrorSection.textContent = `❌ ${detail}`;
      setHidden(apiErrorSection, false);
      return;
    }

    if (data.needs_more_info) {
      needsInfoMessage.textContent = data.message || "É necessária mais informação para continuar.";
      setHidden(needsInfoSection, false);
      return;
    }

    renderResults(data);
    switchTab("evaluator");
  } catch (err) {
    apiErrorSection.textContent = "❌ Não foi possível contactar o servidor. Verifica se a API está a correr.";
    setHidden(apiErrorSection, false);
  } finally {
    submitBtn.disabled = false;
    setHidden(loadingSection, true);
  }
}

async function loadLocationSuggestions() {
  try {
    const response = await fetch("/api/locations");
    if (!response.ok) return;
    const locations = await response.json();
    locationsDatalist.innerHTML = locations
      .map((loc) => `<option value="${escapeHtml(loc.name)}"></option>`)
      .join("");
  } catch (err) {
    // Autocomplete é apenas um extra opcional; falhar aqui não deve impedir o resto da app.
  }
}

locationSuggestions.addEventListener("change", () => {
  const value = locationSuggestions.value.trim();
  if (!value) return;
  const current = queryInput.value.trim();
  queryInput.value = current ? `${current} ${value}` : value;
  locationSuggestions.value = "";
  queryInput.focus();
});

submitBtn.addEventListener("click", submitQuery);

document.querySelectorAll(".tab-btn").forEach((btn) => {
  btn.addEventListener("click", () => switchTab(btn.dataset.tab));
});

queryInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
    submitQuery();
  }
});

loadLocationSuggestions();
