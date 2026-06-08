const specInput = document.querySelector("#specInput");
const logInput = document.querySelector("#logInput");
const runButton = document.querySelector("#runAnalysis");
const sampleButton = document.querySelector("#loadSample");
const exportMarkdown = document.querySelector("#exportMarkdown");
const exportHtml = document.querySelector("#exportHtml");
const emptyTemplate = document.querySelector("#emptyState");

let latestResult = null;

sampleButton.addEventListener("click", loadSample);
runButton.addEventListener("click", runAnalysis);
exportMarkdown.addEventListener("click", () => {
  if (latestResult) {
    downloadText("ai-test-engineer-report.md", latestResult.report.markdown, "text/markdown");
  }
});
exportHtml.addEventListener("click", () => {
  if (latestResult) {
    downloadText("ai-test-engineer-report.html", latestResult.report.html, "text/html");
  }
});

async function loadSample() {
  setBusy(true);
  try {
    const response = await fetch("/api/sample");
    const sample = await response.json();
    specInput.value = sample.spec;
    logInput.value = sample.logs;
  } finally {
    setBusy(false);
  }
}

async function runAnalysis() {
  setBusy(true);
  try {
    const response = await fetch("/api/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ spec: specInput.value, logs: logInput.value })
    });
    latestResult = await response.json();
    renderResult(latestResult);
    exportMarkdown.disabled = false;
    exportHtml.disabled = false;
  } finally {
    setBusy(false);
  }
}

function setBusy(isBusy) {
  runButton.disabled = isBusy;
  sampleButton.disabled = isBusy;
  runButton.textContent = isBusy ? "Running..." : "Run Analysis";
}

function renderResult(result) {
  document.querySelector("#confidenceValue").textContent = `${Math.round(result.log_analysis.confidence * 100)}%`;
  document.querySelector("#testCount").textContent = result.test_plan.length;
  document.querySelector("#riskCount").textContent = result.failure_predictions.length;
  document.querySelector("#toolCount").textContent = result.mcp_observations.length;
  document.querySelector("#llmStatus").textContent = result.llm_insight.enabled ? "ON" : "OFF";
  document.querySelector("#rootCause").textContent = result.debugging.consensus_root_cause;

  renderTestPlan(result.test_plan);
  renderFailurePredictions(result.failure_predictions);
  renderLogAnalysis(result.log_analysis, result.mcp_observations);
  renderDebugging(result.debugging);
  renderLLMReview(result.llm_insight);
  updateBoard(result);
}

function renderTestPlan(cases) {
  const container = document.querySelector("#testPlan");
  container.replaceChildren();
  if (!cases.length) {
    container.append(emptyTemplate.content.cloneNode(true));
    return;
  }

  for (const testCase of cases) {
    const item = createItem(`${testCase.id}: ${testCase.title}`, testCase.objective);
    item.append(createBadgeRow([testCase.priority, testCase.expected_result]));
    container.append(item);
  }
}

function renderFailurePredictions(predictions) {
  const container = document.querySelector("#failurePredictions");
  container.replaceChildren();
  if (!predictions.length) {
    container.append(emptyTemplate.content.cloneNode(true));
    return;
  }

  for (const risk of predictions) {
    const item = createItem(risk.component, risk.failure_mode);
    item.append(createBadgeRow([risk.severity, `${Math.round(risk.confidence * 100)}% confidence`]));
    const list = document.createElement("ul");
    for (const indicator of risk.indicators.slice(0, 4)) {
      const li = document.createElement("li");
      li.textContent = indicator;
      list.append(li);
    }
    item.append(list);
    container.append(item);
  }
}

function renderLogAnalysis(analysis, observations) {
  const container = document.querySelector("#logAnalysis");
  container.replaceChildren();
  const root = createItem("Root Cause", analysis.root_cause);
  root.append(createBadgeRow([`${Math.round(analysis.confidence * 100)}% confidence`, ...analysis.affected_components]));
  container.append(root);

  for (const evidence of analysis.evidence.slice(0, 6)) {
    container.append(createItem(`Line ${evidence.line} [${evidence.severity}]`, evidence.message));
  }

  for (const observation of observations) {
    container.append(createItem(observation.tool, observation.summary));
  }
}

function renderDebugging(debugging) {
  const container = document.querySelector("#debugging");
  container.replaceChildren();

  for (const opinion of debugging.opinions) {
    const item = createItem(opinion.agent, opinion.hypothesis);
    item.append(createBadgeRow([`${Math.round(opinion.confidence * 100)}% confidence`]));
    container.append(item);
  }

  const actions = document.createElement("div");
  actions.className = "item";
  const title = document.createElement("h3");
  title.textContent = "Recommended Actions";
  actions.append(title);
  const list = document.createElement("ul");
  for (const action of debugging.recommended_actions) {
    const li = document.createElement("li");
    li.textContent = action;
    list.append(li);
  }
  actions.append(list);
  container.append(actions);
}

function renderLLMReview(insight) {
  const container = document.querySelector("#llmReview");
  container.replaceChildren();

  if (!insight.enabled) {
    container.append(createItem("LLM Disabled", insight.confidence_note));
    return;
  }

  const summary = createItem(`${insight.provider} / ${insight.model}`, insight.executive_summary);
  summary.append(createBadgeRow(["LLM enabled"]));
  container.append(summary);
  container.append(createItem("Root Cause Rationale", insight.root_cause_rationale));

  const tests = document.createElement("div");
  tests.className = "item";
  const testTitle = document.createElement("h3");
  testTitle.textContent = "Additional Tests";
  tests.append(testTitle);
  const testList = document.createElement("ul");
  for (const test of insight.additional_tests) {
    const li = document.createElement("li");
    li.textContent = test;
    testList.append(li);
  }
  tests.append(testList);
  container.append(tests);

  const fixes = document.createElement("div");
  fixes.className = "item";
  const fixTitle = document.createElement("h3");
  fixTitle.textContent = "Recommended Fix Order";
  fixes.append(fixTitle);
  const fixList = document.createElement("ul");
  for (const fix of insight.recommended_fix_order) {
    const li = document.createElement("li");
    li.textContent = fix;
    fixList.append(li);
  }
  fixes.append(fixList);
  container.append(fixes);
}

function createItem(title, body) {
  const item = document.createElement("article");
  item.className = "item";
  const heading = document.createElement("h3");
  heading.textContent = title;
  const paragraph = document.createElement("p");
  paragraph.textContent = body;
  item.append(heading, paragraph);
  return item;
}

function createBadgeRow(values) {
  const row = document.createElement("div");
  row.className = "badge-row";
  for (const value of values.filter(Boolean)) {
    const badge = document.createElement("span");
    badge.className = "badge";
    const lowered = String(value).toLowerCase();
    if (lowered.includes("critical")) {
      badge.classList.add("critical");
    } else if (lowered.includes("high") || lowered.includes("p0") || lowered.includes("p1")) {
      badge.classList.add("high");
    }
    badge.textContent = value;
    row.append(badge);
  }
  return row;
}

function updateBoard(result) {
  const components = document.querySelectorAll(".component");
  for (const component of components) {
    component.classList.remove("risk-high", "risk-critical", "active-root");
  }

  for (const risk of result.failure_predictions) {
    const node = document.querySelector(`[data-component="${CSS.escape(risk.component)}"]`);
    if (!node) {
      continue;
    }
    node.classList.add(risk.severity === "Critical" ? "risk-critical" : "risk-high");
  }

  const root = result.debugging.consensus_root_cause.toLowerCase();
  for (const component of components) {
    const name = component.dataset.component.toLowerCase();
    if (
      root.includes(name.split(" ")[0].toLowerCase()) ||
      (name.includes("pcie") && root.includes("dma")) ||
      (name.includes("buffer") && root.includes("queue")) ||
      (name.includes("thermal") && root.includes("thermal"))
    ) {
      component.classList.add("active-root");
    }
  }
}

function downloadText(filename, text, type) {
  const blob = new Blob([text], { type });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}
