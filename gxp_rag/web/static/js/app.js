/**
 * GxP Document Draft Agent - Web Application Client JS
 */

const state = {
  currentDraft: null,
  currentCompliance: null,
  activeTab: "studio",
  currentUser: {
    id: "qa_lead_01",
    name: "Dr. Eleanor Vance",
    role: "QA_SPECIALIST",
  },
  presets: [],
  selectedApproval: null,
};

document.addEventListener("DOMContentLoaded", () => {
  initTabs();
  loadPresets();
  loadStats();
  initUpload();
  initFormListeners();
  loadDocuments();
  loadApprovals();
  loadAuditLogs();
});

// Toast notification helper
function showToast(message, type = "info") {
  const container = document.getElementById("toast-container");
  const toast = document.createElement("div");
  toast.className = `toast toast-${type}`;
  toast.innerHTML = `<span>${type === "error" ? "❌" : type === "success" ? "✅" : "ℹ️"}</span> <span>${message}</span>`;
  container.appendChild(toast);
  setTimeout(() => {
    toast.remove();
  }, 4000);
}

// Tab Navigation
function initTabs() {
  document.querySelectorAll(".nav-tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      const target = tab.getAttribute("data-tab");
      switchTab(target);
    });
  });
}

function switchTab(tabId) {
  state.activeTab = tabId;
  document.querySelectorAll(".nav-tab").forEach((t) => {
    t.classList.toggle("active", t.getAttribute("data-tab") === tabId);
  });
  document.querySelectorAll(".tab-pane").forEach((pane) => {
    pane.classList.toggle("active", pane.id === `tab-${tabId}`);
  });

  if (tabId === "kb") {
    loadDocuments();
  } else if (tabId === "approvals") {
    loadApprovals();
  } else if (tabId === "audit") {
    loadAuditLogs();
  }
}

// User Role Switcher
document.getElementById("user-role-select")?.addEventListener("change", (e) => {
  state.currentUser.role = e.target.value;
  if (e.target.value === "QA_MANAGER") {
    state.currentUser.name = "Marcus Sterling";
    state.currentUser.id = "qa_mgr_01";
  } else if (e.target.value === "QA_SPECIALIST") {
    state.currentUser.name = "Dr. Eleanor Vance";
    state.currentUser.id = "qa_lead_01";
  } else if (e.target.value === "SME_REVIEWER") {
    state.currentUser.name = "James Robinson (Lead Scientist)";
    state.currentUser.id = "sme_01";
  } else {
    state.currentUser.name = "Sarah Jenkins";
    state.currentUser.id = "author_01";
  }
  showToast(`Active User Switched: ${state.currentUser.name} (${state.currentUser.role})`, "info");
});

// Load Presets
async function loadPresets() {
  try {
    const res = await fetch("/api/presets");
    const data = await res.json();
    state.presets = data.presets;
    const select = document.getElementById("model-select");
    if (select) {
      select.innerHTML = "";
      data.presets.forEach((p) => {
        const opt = document.createElement("option");
        opt.value = p.model_string;
        opt.textContent = p.display;
        if (p.model_string === data.default_model) {
          opt.selected = true;
        }
        select.appendChild(opt);
      });
    }
  } catch (err) {
    console.error("Failed to load presets:", err);
  }
}

// Load System Stats
async function loadStats() {
  try {
    const res = await fetch("/api/stats");
    const data = await res.json();
    const pill = document.getElementById("kb-status-badge");
    if (pill && data.qdrant) {
      pill.textContent = `Qdrant KB: ${data.qdrant.total_documents || 0} Docs (${data.qdrant.total_points || 0} Chunks)`;
    }
    const appBadge = document.getElementById("pending-approvals-badge");
    if (appBadge) {
      appBadge.textContent = data.pending_approvals || 0;
      appBadge.style.display = data.pending_approvals > 0 ? "inline-block" : "none";
    }
  } catch (err) {
    console.error("Failed to load stats:", err);
  }
}

// Drafting Form
function initFormListeners() {
  const form = document.getElementById("draft-form");
  if (form) {
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      await handleDraftSubmit();
    });
  }

  // Quick prompt templates
  document.querySelectorAll(".quick-prompt-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const prompt = btn.getAttribute("data-prompt");
      const docType = btn.getAttribute("data-type");
      const dept = btn.getAttribute("data-dept");
      document.getElementById("draft-prompt").value = prompt;
      if (docType) document.getElementById("doc-type-select").value = docType;
      if (dept) document.getElementById("dept-input").value = dept;
    });
  });

  // Seed sample data button
  document.getElementById("btn-seed-data")?.addEventListener("click", async () => {
    const btn = document.getElementById("btn-seed-data");
    btn.disabled = true;
    btn.innerHTML = `<span class="spinner"></span> Ingesting Sample Docs...`;
    try {
      const res = await fetch("/api/seed-sample-data", { method: "POST" });
      const data = await res.json();
      showToast(`Sample GxP documents ingested (${Object.keys(data.ingested_files).length} files)`, "success");
      await loadStats();
      await loadDocuments();
    } catch (err) {
      showToast("Error ingesting sample documents", "error");
    } finally {
      btn.disabled = false;
      btn.innerHTML = `<span>📥</span> Load Sample GxP Docs`;
    }
  });

  // Export Buttons
  document.getElementById("btn-export-md")?.addEventListener("click", () => {
    if (!state.currentDraft) return;
    downloadFile(`${state.currentDraft.doc_id}.md`, renderMarkdown(state.currentDraft));
  });

  document.getElementById("btn-export-json")?.addEventListener("click", () => {
    if (!state.currentDraft) return;
    downloadFile(`${state.currentDraft.doc_id}.json`, JSON.stringify(state.currentDraft, null, 2));
  });

  // Submit Draft for Human Approval button
  document.getElementById("btn-submit-approval")?.addEventListener("click", () => {
    if (!state.currentDraft) return;
    openCreateApprovalModal();
  });
}

async function handleDraftSubmit() {
  const btn = document.getElementById("btn-draft-submit");
  const prompt = document.getElementById("draft-prompt").value.trim();
  const docType = document.getElementById("doc-type-select").value;
  const dept = document.getElementById("dept-input").value.trim();
  const modelSpec = document.getElementById("model-select").value;

  if (!prompt) {
    showToast("Please enter requirements or context for drafting.", "error");
    return;
  }

  btn.disabled = true;
  btn.innerHTML = `<span class="spinner"></span> Querying Qdrant & Drafting with Pydantic AI...`;

  const outputContainer = document.getElementById("draft-output-container");
  const emptyState = document.getElementById("draft-empty-state");
  emptyState.style.display = "none";
  outputContainer.style.display = "block";
  outputContainer.innerHTML = `
    <div style="text-align: center; padding: 3rem;">
      <div class="spinner" style="width: 32px; height: 32px; margin-bottom: 1rem;"></div>
      <p style="font-weight: 600;">Pydantic AI Agent is performing semantic retrieval from Qdrant and structuring GxP requirements...</p>
      <p style="color: var(--text-muted); font-size: 0.85rem; margin-top: 0.5rem;">Validating ALCOA+ principles, CPPs, and 21 CFR Part 11 sign-off structure...</p>
    </div>
  `;

  try {
    const res = await fetch("/api/draft", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        prompt: prompt,
        doc_type: docType,
        department: dept,
        model_spec: modelSpec,
        user_id: state.currentUser.id,
        user_role: state.currentUser.role,
      }),
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Drafting request failed");
    }

    const data = await res.json();
    state.currentDraft = data.draft;
    state.currentCompliance = data.compliance;

    renderDraftView(data.draft, data.compliance);
    showToast(`Draft generated: ${data.draft.doc_id}`, "success");
    loadStats();
  } catch (err) {
    console.error(err);
    outputContainer.innerHTML = `
      <div style="padding: 2rem; background: var(--danger-bg); border: 1px solid var(--danger-border); border-radius: var(--radius-md); color: var(--danger-text);">
        <h4>Draft Generation Error</h4>
        <p>${err.message}</p>
      </div>
    `;
    showToast(err.message, "error");
  } finally {
    btn.disabled = false;
    btn.innerHTML = `<span>✨</span> Draft GxP Document`;
  }
}

function renderDraftView(draft, compliance) {
  const container = document.getElementById("draft-output-container");
  
  // Render compliance header
  const score = compliance.compliance_score.toFixed(1);
  const scoreClass = compliance.overall_compliant ? "compliance-pass" : "compliance-fail";

  let citationsHtml = "";
  if (draft.citations && draft.citations.length > 0) {
    citationsHtml = `
      <div class="citations-box">
        <h4><span>🔗</span> Grounded Knowledge Citations (${draft.citations.length} Sources)</h4>
        ${draft.citations
          .map(
            (c) => `
          <div class="citation-item">
            <div class="citation-meta">
              <span>📄 [${c.source_doc_id}] ${c.source_title} (${c.doc_type})</span>
              <span>Relevance: ${c.relevance_score ? (c.relevance_score * 100).toFixed(1) + "%" : "Grounded"}</span>
            </div>
            <div><strong>Section:</strong> ${c.section || "General"}</div>
            <div class="citation-quote">"${c.exact_quote_or_summary}"</div>
          </div>
        `
          )
          .join("")}
      </div>
    `;
  }

  // ALCOA Checklist HTML
  const alcoaHtml = compliance.alcoa_checks
    .map(
      (chk) => `
    <div style="display: flex; align-items: flex-start; gap: 0.5rem; margin-bottom: 0.4rem; font-size: 0.85rem;">
      <span>${chk.compliant ? "✅" : "⚠️"}</span>
      <div>
        <strong>${chk.principle.split(" ")[0]}:</strong> ${chk.evidence}
        ${chk.remediation ? `<div style="color: #b91c1c; font-size: 0.78rem;">Remediation: ${chk.remediation}</div>` : ""}
      </div>
    </div>
  `
    )
    .join("");

  // Procedural steps HTML
  const proceduresHtml = (draft.procedure_sections || [])
    .map(
      (sec) => `
    <h4>${sec.section_id} ${sec.title}</h4>
    ${sec.content ? `<p>${sec.content}</p>` : ""}
    ${(sec.steps || [])
      .map(
        (st) => `
      <div style="margin-bottom: 1rem; padding: 0.75rem; background: #f8fafc; border-left: 3px solid var(--primary); border-radius: 0 4px 4px 0;">
        <div style="display: flex; justify-content: space-between; font-weight: 700; color: #1e293b;">
          <span>${st.step_number} ${st.action_title}</span>
          <span style="font-size: 0.78rem; background: #e2e8f0; padding: 0.1rem 0.4rem; border-radius: 4px;">Role: ${st.role_responsible}</span>
        </div>
        <p style="margin: 0.4rem 0 0.2rem 0;">${st.instruction_text}</p>
        ${
          st.critical_parameters && st.critical_parameters.length > 0
            ? `<div style="font-size: 0.8rem; color: #b45309;"><strong>⚠️ Critical Process Parameters:</strong> ${st.critical_parameters.join(", ")}</div>`
            : ""
        }
        ${
          st.acceptance_criteria
            ? `<div style="font-size: 0.8rem; color: #047857;"><strong>Acceptance Criteria:</strong> ${st.acceptance_criteria}</div>`
            : ""
        }
      </div>
    `
      )
      .join("")}
  `
    )
    .join("");

  container.innerHTML = `
    <div class="viewer-toolbar">
      <div style="display: flex; align-items: center; gap: 0.75rem;">
        <span class="compliance-summary-badge ${scoreClass}">
          ${compliance.overall_compliant ? "✅ GxP Compliant" : "⚠️ Compliance Issues"} (${score}%)
        </span>
        <span style="font-size: 0.82rem; color: var(--text-muted);">Status: <strong>${draft.status}</strong></span>
      </div>
      <div class="toolbar-actions">
        <button class="btn btn-secondary" id="btn-export-md" style="padding: 0.4rem 0.75rem; font-size: 0.8rem;">📥 Export MD</button>
        <button class="btn btn-secondary" id="btn-export-json" style="padding: 0.4rem 0.75rem; font-size: 0.8rem;">{ } JSON</button>
        <button class="btn btn-primary" id="btn-submit-approval" style="padding: 0.4rem 0.75rem; font-size: 0.8rem;">✍️ Submit for Approval</button>
      </div>
    </div>

    <!-- ALCOA+ Compliance Card -->
    <div class="card" style="margin-top: 1rem; border-color: ${compliance.overall_compliant ? "#bbf7d0" : "#fed7aa"};">
      <div class="card-header" style="background: ${compliance.overall_compliant ? "#f0fdf4" : "#fffbeb"};">
        <h3>🛡️ ALCOA+ & 21 CFR Part 11 Compliance Evaluation</h3>
        <span style="font-weight: 700; color: ${compliance.overall_compliant ? "#166534" : "#9a3412"};">Score: ${score}/100</span>
      </div>
      <div class="card-body">
        ${alcoaHtml}
      </div>
    </div>

    <!-- Document Paper -->
    <div class="doc-paper" style="margin-top: 1rem;">
      <h1>${draft.doc_id}: ${draft.title}</h1>
      <table style="margin-bottom: 1.5rem;">
        <tr><td><strong>Document Type</strong></td><td>${draft.doc_type}</td><td><strong>Version</strong></td><td>${draft.version}</td></tr>
        <tr><td><strong>Department</strong></td><td>${draft.department}</td><td><strong>Effective Date</strong></td><td>${draft.effective_date || "Pending Approval"}</td></tr>
        <tr><td><strong>Author</strong></td><td>${draft.author}</td><td><strong>Review Cycle</strong></td><td>${draft.review_period_months} Months</td></tr>
      </table>

      <h3>1.0 Purpose</h3>
      <p>${draft.purpose}</p>

      <h3>2.0 Scope</h3>
      <p>${draft.scope}</p>

      ${
        draft.regulatory_standards && draft.regulatory_standards.length > 0
          ? `<h3>3.0 Regulatory Standards</h3><ul>${draft.regulatory_standards.map((s) => `<li>${s}</li>`).join("")}</ul>`
          : ""
      }

      ${
        draft.responsibilities && Object.keys(draft.responsibilities).length > 0
          ? `<h3>4.0 Responsibilities</h3><table><tr><th>Role</th><th>Responsibility</th></tr>${Object.entries(
              draft.responsibilities
            )
              .map(([r, resp]) => `<tr><td><strong>${r}</strong></td><td>${resp}</td></tr>`)
              .join("")}</table>`
          : ""
      }

      <h3>8.0 Operating Procedures</h3>
      ${proceduresHtml}

      <h3>9.0 Acceptance Criteria Summary</h3>
      <ul>
        ${(draft.acceptance_criteria_summary || []).map((c) => `<li>${c}</li>`).join("")}
      </ul>

      <h3>10.0 Deviation & Anomaly Escalation</h3>
      <p>${draft.contingency_and_deviation_handling}</p>

      ${citationsHtml}
    </div>
  `;

  // Re-attach listeners to dynamic buttons
  document.getElementById("btn-export-md")?.addEventListener("click", () => {
    downloadFile(`${state.currentDraft.doc_id}.md`, renderMarkdown(state.currentDraft));
  });
  document.getElementById("btn-export-json")?.addEventListener("click", () => {
    downloadFile(`${state.currentDraft.doc_id}.json`, JSON.stringify(state.currentDraft, null, 2));
  });
  document.getElementById("btn-submit-approval")?.addEventListener("click", () => {
    openCreateApprovalModal();
  });
}

function renderMarkdown(draft) {
  // Simple markdown renderer matching server format
  return `# ${draft.doc_id}: ${draft.title}\n\n## 1.0 Purpose\n${draft.purpose}\n\n## 2.0 Scope\n${draft.scope}\n\n`;
}

// Ingestion & Dropzone
function initUpload() {
  const dropzone = document.getElementById("upload-dropzone");
  const fileInput = document.getElementById("file-input");

  if (!dropzone || !fileInput) return;

  dropzone.addEventListener("click", () => fileInput.click());

  dropzone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropzone.classList.add("dragover");
  });

  dropzone.addEventListener("dragleave", () => {
    dropzone.classList.remove("dragover");
  });

  dropzone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropzone.classList.remove("dragover");
    if (e.dataTransfer.files.length > 0) {
      handleFileUpload(e.dataTransfer.files[0]);
    }
  });

  fileInput.addEventListener("change", (e) => {
    if (e.target.files.length > 0) {
      handleFileUpload(e.target.files[0]);
    }
  });

  // KB Search Sandbox
  document.getElementById("kb-search-btn")?.addEventListener("click", async () => {
    const query = document.getElementById("kb-search-query").value.trim();
    if (!query) return;
    const resBox = document.getElementById("kb-search-results");
    resBox.innerHTML = `<div style="padding: 1rem;"><span class="spinner"></span> Searching Qdrant...</div>`;
    try {
      const res = await fetch("/api/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: query, limit: 5 }),
      });
      const data = await res.json();
      if (!data.results || data.results.length === 0) {
        resBox.innerHTML = `<div class="empty-state">No chunks matched query in Qdrant.</div>`;
        return;
      }
      resBox.innerHTML = data.results
        .map(
          (r, i) => `
        <div style="padding: 0.85rem; border-bottom: 1px solid var(--border-subtle); background: white; margin-bottom: 0.5rem; border-radius: 6px;">
          <div style="display: flex; justify-content: space-between; font-weight: 700; color: #1e40af; font-size: 0.85rem;">
            <span>#${i + 1} [${r.doc_id}] ${r.doc_title} (${r.doc_type})</span>
            <span style="background: #dbeafe; padding: 0.1rem 0.4rem; border-radius: 4px;">Score: ${(r.score * 100).toFixed(1)}%</span>
          </div>
          <div style="font-size: 0.8rem; color: #475569; margin: 0.25rem 0;">Section: <strong>${r.section_heading || "General"}</strong></div>
          <div style="font-size: 0.82rem; color: #1e293b; background: #f8fafc; padding: 0.5rem; border-radius: 4px;">${r.text}</div>
        </div>
      `
        )
        .join("");
    } catch (err) {
      resBox.innerHTML = `<div style="color: red; padding: 1rem;">Search failed: ${err.message}</div>`;
    }
  });
}

async function handleFileUpload(file) {
  const formData = new FormData();
  formData.append("file", file);

  showToast(`Uploading and embedding ${file.name}...`, "info");
  try {
    const res = await fetch("/api/documents/upload", {
      method: "POST",
      body: formData,
    });
    if (!res.ok) throw new Error("Upload failed");
    const data = await res.json();
    showToast(`Successfully indexed ${data.doc_id} (${data.chunks_count} chunks into Qdrant)`, "success");
    loadStats();
    loadDocuments();
  } catch (err) {
    showToast(err.message, "error");
  }
}

// Load Documents Table
async function loadDocuments() {
  const tbody = document.getElementById("kb-docs-table-body");
  if (!tbody) return;

  try {
    const res = await fetch("/api/documents");
    const data = await res.json();
    if (!data.documents || data.documents.length === 0) {
      tbody.innerHTML = `<tr><td colspan="6" class="empty-state">No documents indexed in Qdrant knowledge base yet. Click "Load Sample GxP Docs" to initialize.</td></tr>`;
      return;
    }

    tbody.innerHTML = data.documents
      .map(
        (doc) => `
      <tr>
        <td><strong>${doc.doc_id}</strong></td>
        <td>${doc.title}</td>
        <td><span class="status-pill compliance">${doc.doc_type}</span></td>
        <td>${doc.department}</td>
        <td><strong>${doc.chunk_count}</strong></td>
        <td>
          <button class="btn btn-secondary" style="padding: 0.25rem 0.5rem; font-size: 0.75rem;" onclick="viewDocumentChunks('${doc.doc_id}')">Inspect Chunks</button>
          <button class="btn btn-danger" style="padding: 0.25rem 0.5rem; font-size: 0.75rem;" onclick="deleteDocument('${doc.doc_id}')">Delete</button>
        </td>
      </tr>
    `
      )
      .join("");
  } catch (err) {
    console.error("Failed to load documents:", err);
  }
}

async function viewDocumentChunks(docId) {
  try {
    const res = await fetch(`/api/documents/${docId}/chunks`);
    const data = await res.json();
    const modal = document.getElementById("chunk-modal");
    const body = document.getElementById("chunk-modal-body");
    const title = document.getElementById("chunk-modal-title");

    title.textContent = `Indexed Qdrant Chunks for ${docId} (${data.chunks.length} Chunks)`;
    body.innerHTML = data.chunks
      .map(
        (c) => `
      <div style="border: 1px solid var(--border-subtle); padding: 0.75rem; margin-bottom: 0.75rem; border-radius: 6px; background: white;">
        <div style="font-weight: 700; color: var(--primary); font-size: 0.85rem; margin-bottom: 0.35rem;">
          Chunk #${c.chunk_index + 1}: ${c.section_heading || "General"}
        </div>
        <div style="font-size: 0.82rem; white-space: pre-wrap; font-family: inherit; color: #1e293b;">${c.text}</div>
      </div>
    `
      )
      .join("");

    modal.classList.add("open");
  } catch (err) {
    showToast("Failed to load document chunks", "error");
  }
}

async function deleteDocument(docId) {
  if (!confirm(`Are you sure you want to delete ${docId} and all its vectors from Qdrant?`)) return;
  try {
    await fetch("/api/documents/delete", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ doc_id: docId }),
    });
    showToast(`Deleted ${docId}`, "success");
    loadStats();
    loadDocuments();
  } catch (err) {
    showToast("Failed to delete document", "error");
  }
}

// Approvals Tab
async function loadApprovals() {
  const container = document.getElementById("approvals-list-container");
  if (!container) return;

  try {
    const res = await fetch("/api/approvals");
    const data = await res.json();
    if (!data.approvals || data.approvals.length === 0) {
      container.innerHTML = `<div class="empty-state"><div class="empty-state-icon">✍️</div><p>No Human-in-the-Loop approval requests pending.</p></div>`;
      return;
    }

    container.innerHTML = data.approvals
      .map((appr) => {
        let statusBadge = `<span class="status-pill" style="background: #fef3c7; color: #92400e;">PENDING</span>`;
        if (appr.status === "APPROVED") {
          statusBadge = `<span class="status-pill" style="background: #d1fae5; color: #065f46;">✅ APPROVED</span>`;
        } else if (appr.status === "REJECTED") {
          statusBadge = `<span class="status-pill" style="background: #fee2e2; color: #991b1b;">❌ REJECTED</span>`;
        } else if (appr.status === "REVISION_REQUESTED") {
          statusBadge = `<span class="status-pill" style="background: #ffedd5; color: #9a3412;">🔄 REVISION REQUESTED</span>`;
        }

        const sigsHtml = (appr.signatures || [])
          .map(
            (s) => `
          <div class="signature-chip" title="SHA-256: ${s.signature_digest}">
            <span>🔏</span> <strong>${s.signer_name}</strong> (${s.signer_role}) - ${new Date(s.timestamp).toLocaleString()}
          </div>
        `
          )
          .join("");

        return `
        <div class="card" style="margin-bottom: 1rem;">
          <div class="card-header">
            <div>
              <h3>[${appr.request_id}] ${appr.doc_title} (${appr.doc_id} v${appr.doc_version})</h3>
              <div style="font-size: 0.78rem; color: var(--text-muted);">Author: ${appr.author_id} | Created: ${new Date(appr.created_at).toLocaleString()}</div>
            </div>
            <div>${statusBadge}</div>
          </div>
          <div class="card-body">
            <p><strong>Justification / Change Rationale:</strong> ${appr.justification}</p>
            ${sigsHtml ? `<div style="margin-top: 0.5rem; display: flex; flex-wrap: wrap; gap: 0.4rem;">${sigsHtml}</div>` : ""}
            ${appr.review_comments ? `<div style="margin-top: 0.5rem; font-size: 0.85rem; padding: 0.5rem; background: #f8fafc; border-radius: 4px;"><strong>Reviewer Comments:</strong> ${appr.review_comments}</div>` : ""}
            
            <div style="margin-top: 1rem; display: flex; gap: 0.5rem; justify-content: flex-end;">
              <button class="btn btn-secondary" style="padding: 0.35rem 0.75rem; font-size: 0.82rem;" onclick="viewApprovalDraft('${appr.doc_id}')">👁️ Review Full Draft</button>
              ${
                appr.status === "PENDING"
                  ? `
                <button class="btn btn-success" style="padding: 0.35rem 0.75rem; font-size: 0.82rem;" onclick="openESigModal('${appr.request_id}', 'approve')">✍️ Sign & Approve (21 CFR Part 11)</button>
                <button class="btn btn-secondary" style="padding: 0.35rem 0.75rem; font-size: 0.82rem; color: #9a3412;" onclick="openESigModal('${appr.request_id}', 'revise')">🔄 Request Revision</button>
                <button class="btn btn-danger" style="padding: 0.35rem 0.75rem; font-size: 0.82rem;" onclick="openESigModal('${appr.request_id}', 'reject')">❌ Reject</button>
              `
                  : ""
              }
            </div>
          </div>
        </div>
      `;
      })
      .join("");
  } catch (err) {
    console.error("Failed to load approvals:", err);
  }
}

async function viewApprovalDraft(docId) {
  try {
    const res = await fetch(`/api/drafts/${docId}`);
    if (!res.ok) throw new Error("Draft not found");
    const data = await res.json();
    state.currentDraft = data.draft;
    state.currentCompliance = data.compliance;
    switchTab("studio");
    renderDraftView(data.draft, data.compliance);
  } catch (err) {
    showToast("Failed to load draft content", "error");
  }
}

// Create Approval Modal
function openCreateApprovalModal() {
  if (!state.currentDraft) return;
  const modal = document.getElementById("create-approval-modal");
  document.getElementById("create-appr-doc-id").textContent = `${state.currentDraft.doc_id} - ${state.currentDraft.title}`;
  document.getElementById("create-appr-justification").value = `Initial formal GxP review and sign-off for ${state.currentDraft.doc_type} (${state.currentDraft.doc_id}).`;
  modal.classList.add("open");
}

document.getElementById("btn-confirm-create-approval")?.addEventListener("click", async () => {
  if (!state.currentDraft) return;
  const justification = document.getElementById("create-appr-justification").value.trim();
  if (!justification) {
    showToast("Justification is required for GxP audit trail compliance.", "error");
    return;
  }

  try {
    const res = await fetch("/api/approvals/create", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        doc_id: state.currentDraft.doc_id,
        justification: justification,
        author_id: state.currentUser.id,
      }),
    });
    const data = await res.json();
    showToast(`Approval Request Created: ${data.approval_request.request_id}`, "success");
    document.getElementById("create-approval-modal").classList.remove("open");
    loadStats();
    switchTab("approvals");
  } catch (err) {
    showToast("Failed to create approval request", "error");
  }
});

// Electronic Signature Modal (21 CFR Part 11)
function openESigModal(requestId, action) {
  state.selectedApproval = { requestId, action };
  const modal = document.getElementById("esig-modal");
  const title = document.getElementById("esig-modal-title");
  const meaningInput = document.getElementById("esig-meaning");

  document.getElementById("esig-signer-name").value = state.currentUser.name;
  document.getElementById("esig-user-id").value = state.currentUser.id;
  document.getElementById("esig-role").value = state.currentUser.role;

  if (action === "approve") {
    title.textContent = "✍️ 21 CFR Part 11 Electronic Signature Approval";
    meaningInput.value = "I confirm that I have reviewed this GxP document and approve its scientific, technical, and regulatory compliance.";
  } else if (action === "reject") {
    title.textContent = "❌ Reject GxP Document Draft";
    meaningInput.value = "Document Rejected due to regulatory non-conformance or technical inaccuracies.";
  } else if (action === "revise") {
    title.textContent = "🔄 Request Revisions on Draft";
    meaningInput.value = "Document returned for revision and updates per comments.";
  }

  modal.classList.add("open");
}

document.getElementById("btn-confirm-esig")?.addEventListener("click", async () => {
  if (!state.selectedApproval) return;
  const signerName = document.getElementById("esig-signer-name").value.trim();
  const userId = document.getElementById("esig-user-id").value.trim();
  const role = document.getElementById("esig-role").value;
  const comments = document.getElementById("esig-comments").value.trim();
  const meaning = document.getElementById("esig-meaning").value.trim();

  if (!signerName || !comments) {
    showToast("Signer name and comments/reason are mandatory for 21 CFR Part 11 compliance.", "error");
    return;
  }

  try {
    const res = await fetch("/api/approvals/action", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        request_id: state.selectedApproval.requestId,
        action: state.selectedApproval.action,
        signer_name: signerName,
        user_id: userId,
        role: role,
        comments_or_reason: comments,
        signature_meaning: meaning,
      }),
    });

    if (!res.ok) throw new Error("Approval action failed");
    const data = await res.json();
    showToast(`Action '${state.selectedApproval.action.toUpperCase()}' completed successfully with e-signature.`, "success");
    document.getElementById("esig-modal").classList.remove("open");
    loadStats();
    loadApprovals();
  } catch (err) {
    showToast(err.message, "error");
  }
});

// Audit Trail Tab
async function loadAuditLogs() {
  const tbody = document.getElementById("audit-table-body");
  const integrityBadge = document.getElementById("audit-integrity-badge");
  if (!tbody) return;

  try {
    const res = await fetch("/api/audit");
    const data = await res.json();

    if (integrityBadge && data.integrity) {
      if (data.integrity.valid) {
        integrityBadge.className = "status-pill compliance";
        integrityBadge.innerHTML = `🔒 SHA-256 Hash Chain Verified (${data.integrity.total_records} Records)`;
      } else {
        integrityBadge.className = "status-pill";
        integrityBadge.style.background = "#fee2e2";
        integrityBadge.style.color = "#991b1b";
        integrityBadge.innerHTML = `⚠️ Chain Tampering Detected!`;
      }
    }

    if (!data.records || data.records.length === 0) {
      tbody.innerHTML = `<tr><td colspan="6" class="empty-state">No audit trail records logged yet.</td></tr>`;
      return;
    }

    tbody.innerHTML = data.records
      .slice()
      .reverse()
      .map((r) => {
        let sigText = "-";
        if (r.signature) {
          sigText = `<strong>${r.signature.signer_name}</strong> (${r.signature.signer_role})<br><span style="font-family: var(--font-mono); font-size: 0.72rem;">${r.signature.signature_digest.substring(0, 16)}...</span>`;
        }

        return `
        <tr>
          <td><span style="font-family: var(--font-mono); font-size: 0.75rem;">${new Date(r.timestamp).toISOString()}</span></td>
          <td><span class="status-pill compliance">${r.event_type}</span></td>
          <td>${r.user_id} (${r.user_role || "SYSTEM"})</td>
          <td><strong>${r.doc_id || "-"}</strong></td>
          <td style="font-size: 0.8rem;">${JSON.stringify(r.action_details)}</td>
          <td>${sigText}</td>
        </tr>
      `;
      })
      .join("");
  } catch (err) {
    console.error("Failed to load audit logs:", err);
  }
}

// Modal Close Handlers
document.querySelectorAll(".modal-close-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".modal-backdrop").forEach((m) => m.classList.remove("open"));
  });
});

function downloadFile(filename, text) {
  const element = document.createElement("a");
  element.setAttribute("href", "data:text/plain;charset=utf-8," + encodeURIComponent(text));
  element.setAttribute("download", filename);
  element.style.display = "none";
  document.body.appendChild(element);
  element.click();
  document.body.removeChild(element);
}
