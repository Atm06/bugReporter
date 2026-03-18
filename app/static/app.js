/* ===== Session Management ================================================ */

function getSession() {
    try { return JSON.parse(localStorage.getItem("bugbash_user") || "null"); } catch { return null; }
}

function setSession(name, email) {
    localStorage.setItem("bugbash_user", JSON.stringify({ name, email }));
    syncUserBar();
}

function clearSession() {
    localStorage.removeItem("bugbash_user");
    localStorage.removeItem("bugbash_admin_token");
    syncUserBar();
}

function getAdminToken() {
    return localStorage.getItem("bugbash_admin_token") || "";
}

function isAdmin() {
    return !!getAdminToken();
}

function canEditBug(bug) {
    if (isAdmin()) return true;
    const session = getSession();
    if (!session) return false;
    return (bug["Reporter Email"] || "").trim().toLowerCase() === session.email.trim().toLowerCase();
}

function canDeleteBug() {
    return isAdmin();
}

function canChangeStatus() {
    return isAdmin();
}

function authHeaders() {
    const h = {};
    const token = getAdminToken();
    const session = getSession();
    if (token) h["X-Admin-Token"] = token;
    if (session) h["X-User-Email"] = session.email;
    return h;
}

function syncUserBar() {
    const session = getSession();
    const loggedOut = document.getElementById("user-bar-logged-out");
    const loggedIn = document.getElementById("user-bar-logged-in");
    if (!loggedOut || !loggedIn) return;

    if (session) {
        loggedOut.classList.add("hidden");
        loggedIn.classList.remove("hidden");
        const nameEl = document.getElementById("user-bar-name");
        if (nameEl) nameEl.textContent = session.name;
        const badge = document.getElementById("admin-badge");
        if (isAdmin()) {
            if (badge) badge.classList.remove("hidden");
        } else {
            if (badge) badge.classList.add("hidden");
        }
    } else {
        loggedOut.classList.remove("hidden");
        loggedIn.classList.add("hidden");
    }

    prefillReporterFields();
}

function requireLogin() {
    if (!getSession()) {
        document.getElementById("login-modal").classList.remove("hidden");
        return false;
    }
    return true;
}

function prefillReporterFields() {
    const session = getSession();
    const nameField = document.getElementById("reporter_name");
    const emailField = document.getElementById("reporter_email");
    if (session && nameField && !nameField.value) nameField.value = session.name;
    if (session && emailField && !emailField.value) emailField.value = session.email;
}

/* ── Login modal ── */

let loginNeedsPassword = false;

function openLoginModal() {
    loginNeedsPassword = false;
    const pwGroup = document.getElementById("login-password-group");
    if (pwGroup) pwGroup.classList.add("hidden");
    const pwInput = document.getElementById("login-password");
    if (pwInput) { pwInput.value = ""; pwInput.removeAttribute("required"); }
    document.getElementById("login-modal").classList.remove("hidden");
}

(function initLoginForm() {
    const form = document.getElementById("login-form");
    if (!form) return;

    const emailInput = document.getElementById("login-email");
    const pwGroup = document.getElementById("login-password-group");
    const pwInput = document.getElementById("login-password");
    let checkTimeout = null;

    emailInput.addEventListener("input", () => {
        clearTimeout(checkTimeout);
        const email = emailInput.value.trim();
        if (!email || !email.includes("@")) {
            pwGroup.classList.add("hidden");
            pwInput.removeAttribute("required");
            loginNeedsPassword = false;
            return;
        }
        checkTimeout = setTimeout(async () => {
            try {
                const res = await fetch("/api/auth/check-email", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ email }),
                });
                const data = await res.json();
                loginNeedsPassword = data.requires_password;
                pwGroup.classList.toggle("hidden", !loginNeedsPassword);
                if (loginNeedsPassword) {
                    pwInput.setAttribute("required", "");
                    pwInput.focus();
                } else {
                    pwInput.removeAttribute("required");
                    pwInput.value = "";
                }
            } catch { /* ignore */ }
        }, 400);
    });

    emailInput.addEventListener("change", () => emailInput.dispatchEvent(new Event("input")));

    form.addEventListener("submit", async (e) => {
        e.preventDefault();
        const name = document.getElementById("login-name").value.trim();
        const email = emailInput.value.trim();
        if (!name || !email) return;

        const btn = document.getElementById("login-submit-btn");
        btn.disabled = true;

        if (loginNeedsPassword) {
            const pw = pwInput.value;
            if (!pw) { btn.disabled = false; return; }
            try {
                const data = await api("/api/auth/admin", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ password: pw }),
                });
                localStorage.setItem("bugbash_admin_token", data.token);
            } catch (err) {
                showToast("Invalid admin password", "error");
                btn.disabled = false;
                return;
            }
        }

        setSession(name, email);
        document.getElementById("login-modal").classList.add("hidden");
        showToast(isAdmin() ? `Welcome, ${name}! (Admin)` : `Welcome, ${name}!`);
        if (typeof renderBugs === "function") renderBugs();
        btn.disabled = false;
    });
})();

function logoutUser() {
    clearSession();
    showToast("Signed out", "info");
    if (typeof renderBugs === "function") renderBugs();
    openLoginModal();
}

/* ── Boot: check session on every page load ── */
(function bootSession() {
    syncUserBar();
    const session = getSession();
    if (!session) {
        setTimeout(() => {
            document.getElementById("login-modal").classList.remove("hidden");
        }, 300);
    }
    if (getAdminToken()) {
        fetch("/api/auth/verify-admin", { headers: authHeaders() })
            .then(r => r.json())
            .then(d => { if (!d.ok) { localStorage.removeItem("bugbash_admin_token"); syncUserBar(); } })
            .catch(() => {});
    }
})();

/* ===== Utilities ========================================================= */

function showToast(message, type = "success") {
    const container = document.getElementById("toast-container");
    if (!container) return;
    const el = document.createElement("div");
    el.className = `toast toast-${type}`;
    el.textContent = message;
    container.appendChild(el);
    setTimeout(() => {
        el.style.opacity = "0";
        el.style.transition = "opacity 0.3s";
        setTimeout(() => el.remove(), 300);
    }, 3500);
}

async function api(path, opts = {}) {
    opts.headers = { ...authHeaders(), ...(opts.headers || {}) };
    const res = await fetch(path, opts);
    if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `HTTP ${res.status}`);
    }
    return res.json();
}

function severityClass(severity) {
    return `severity-${severity.toLowerCase()}`;
}

function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
}

function formatCategory(bug) {
    let cat = escapeHtml(bug.Category || "");
    if (bug.Subcategory) cat += ` <span class="text-gray-400">&middot;</span> ${escapeHtml(bug.Subcategory)}`;
    if (bug.Category === "Other" && bug["Page Title"]) cat += ` <span class="text-gray-400">&middot;</span> ${escapeHtml(bug["Page Title"])}`;
    return cat;
}

/* ===== Submit Form ======================================================= */

(function initSubmitForm() {
    const form = document.getElementById("bug-form");
    if (!form) return;

    const categoriesWithPages = window.CATEGORIES_WITH_PAGES || [];
    let uploadedFilename = "";

    const categorySelect = document.getElementById("category");
    const subcategoryGroup = document.getElementById("subcategory-group");
    const otherFieldsGroup = document.getElementById("other-fields-group");
    const pageTitleInput = document.getElementById("page_title");

    categorySelect.addEventListener("change", () => {
        const val = categorySelect.value;
        const hasPages = categoriesWithPages.includes(val);
        const isOther = val === "Other";

        subcategoryGroup.classList.toggle("hidden", !hasPages);
        otherFieldsGroup.classList.toggle("hidden", !isOther);

        if (hasPages) {
            document.getElementById("subcategory-label-detail").textContent = `${val} Detail`;
            document.getElementById("subcategory-label-search").textContent = `${val} Search`;
        } else {
            form.querySelectorAll('input[name="subcategory"]').forEach(r => r.checked = false);
        }

        if (!isOther && pageTitleInput) pageTitleInput.value = "";
    });

    const dropZone = document.getElementById("drop-zone");
    const fileInput = document.getElementById("screenshot-input");
    const dropText = document.getElementById("drop-zone-text");
    const dropPreview = document.getElementById("drop-zone-preview");
    const previewImg = document.getElementById("preview-img");
    const previewName = document.getElementById("preview-name");
    const removeBtn = document.getElementById("remove-screenshot");
    const filenameInput = document.getElementById("screenshot-filename");

    dropZone.addEventListener("click", () => fileInput.click());
    dropZone.addEventListener("dragover", (e) => {
        e.preventDefault();
        dropZone.classList.add("drag-over");
    });
    dropZone.addEventListener("dragleave", () => dropZone.classList.remove("drag-over"));
    dropZone.addEventListener("drop", (e) => {
        e.preventDefault();
        dropZone.classList.remove("drag-over");
        if (e.dataTransfer.files.length) handleFile(e.dataTransfer.files[0]);
    });
    fileInput.addEventListener("change", () => {
        if (fileInput.files.length) handleFile(fileInput.files[0]);
    });
    removeBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        clearScreenshot();
    });

    async function handleFile(file) {
        if (!file.type.startsWith("image/")) {
            showToast("Only image files are allowed", "error");
            return;
        }
        if (file.size > 10 * 1024 * 1024) {
            showToast("File too large (max 10 MB)", "error");
            return;
        }

        previewImg.src = URL.createObjectURL(file);
        previewName.textContent = file.name;
        dropText.classList.add("hidden");
        dropPreview.classList.remove("hidden");

        const fd = new FormData();
        fd.append("file", file);
        try {
            const data = await api("/api/upload", { method: "POST", body: fd });
            uploadedFilename = data.filename;
            filenameInput.value = uploadedFilename;
        } catch (err) {
            showToast("Upload failed: " + err.message, "error");
            clearScreenshot();
        }
    }

    function clearScreenshot() {
        uploadedFilename = "";
        filenameInput.value = "";
        fileInput.value = "";
        dropText.classList.remove("hidden");
        dropPreview.classList.add("hidden");
        previewImg.src = "";
    }

    form.addEventListener("submit", async (e) => {
        e.preventDefault();
        if (!requireLogin()) return;

        const btn = document.getElementById("submit-btn");
        const cat = categorySelect.value;
        const hasPages = categoriesWithPages.includes(cat);
        const isOther = cat === "Other";

        if (hasPages) {
            const checked = form.querySelector('input[name="subcategory"]:checked');
            if (!checked) {
                showToast("Please select a page type (Detail or Search)", "error");
                return;
            }
        }
        if (isOther && !pageTitleInput.value.trim()) {
            showToast("Please enter the page title for 'Other' category", "error");
            return;
        }

        btn.disabled = true;
        btn.textContent = "Submitting...";

        const subcatRadio = form.querySelector('input[name="subcategory"]:checked');
        const payload = {
            title: form.title.value.trim(),
            description: form.description.value.trim(),
            severity: form.severity.value,
            category: cat,
            subcategory: hasPages && subcatRadio ? subcatRadio.value : "",
            steps: form.steps.value.trim(),
            screenshot: filenameInput.value,
            reporter_name: form.reporter_name.value.trim(),
            reporter_email: form.reporter_email.value.trim(),
            page_url: form.page_url.value.trim(),
            page_title: isOther ? pageTitleInput.value.trim() : "",
        };

        try {
            await api("/api/bugs", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
            });
            showToast("Bug report submitted!", "success");
            form.reset();
            clearScreenshot();
            subcategoryGroup.classList.add("hidden");
            otherFieldsGroup.classList.add("hidden");
            form.classList.add("hidden");
            document.getElementById("submit-success").classList.remove("hidden");
        } catch (err) {
            showToast("Error: " + err.message, "error");
        } finally {
            btn.disabled = false;
            btn.textContent = "Submit Bug Report";
        }
    });
})();

function resetSubmitForm() {
    document.getElementById("submit-success").classList.add("hidden");
    document.getElementById("bug-form").classList.remove("hidden");
    prefillReporterFields();
    window.scrollTo({ top: 0, behavior: "smooth" });
}

/* ===== Dashboard ========================================================= */

let allBugs = [];
let dashboardInterval = null;

function initDashboard(statuses) {
    loadBugs(false);
    dashboardInterval = setInterval(() => loadBugs(false), 30000);

    document.getElementById("filter-search").addEventListener("input", renderBugs);
    document.getElementById("filter-severity").addEventListener("change", renderBugs);
    document.getElementById("filter-category").addEventListener("change", renderBugs);
    document.getElementById("filter-status").addEventListener("change", renderBugs);
    document.getElementById("filter-reporter").addEventListener("change", renderBugs);

    window._statuses = statuses;

    document.getElementById("edit-form").addEventListener("submit", handleEditSave);

    document.getElementById("edit-category").addEventListener("change", () => {
        const cat = document.getElementById("edit-category").value;
        document.getElementById("edit-subcategory-group").classList.toggle("hidden", !(window.CATEGORIES_WITH_PAGES || []).includes(cat));
        document.getElementById("edit-page-title-group").classList.toggle("hidden", cat !== "Other");
    });
}

async function loadBugs(manual) {
    try {
        allBugs = await api("/api/bugs");
        populateReporterFilter();
        updateSummaryCards();
        renderBugs();
        if (manual) showToast("Refreshed", "info");
    } catch (err) {
        showToast("Failed to load bugs: " + err.message, "error");
    }
}

function populateReporterFilter() {
    const sel = document.getElementById("filter-reporter");
    const current = sel.value;
    const reporters = [...new Set(allBugs.map(b => b["Reporter Name"]).filter(Boolean))].sort();
    sel.innerHTML = '<option value="">All Reporters</option>';
    reporters.forEach(r => {
        const opt = document.createElement("option");
        opt.value = r;
        opt.textContent = r;
        sel.appendChild(opt);
    });
    sel.value = current;
}

function updateSummaryCards() {
    document.getElementById("card-total").textContent = allBugs.length;
    document.getElementById("card-critical").textContent = allBugs.filter(b => b.Severity === "Critical").length;
    document.getElementById("card-high").textContent = allBugs.filter(b => b.Severity === "High").length;
    document.getElementById("card-open").textContent = allBugs.filter(b => b.Status === "Open").length;
    document.getElementById("card-in-progress").textContent = allBugs.filter(b => b.Status === "In Progress").length;
    document.getElementById("card-fixed").textContent = allBugs.filter(b => b.Status === "Fixed").length;
}

function getFilteredBugs() {
    const search = document.getElementById("filter-search").value.toLowerCase();
    const severity = document.getElementById("filter-severity").value;
    const category = document.getElementById("filter-category").value;
    const status = document.getElementById("filter-status").value;
    const reporter = document.getElementById("filter-reporter").value;

    return allBugs.filter(b => {
        if (search && !(b.Title || "").toLowerCase().includes(search) && !(b.Description || "").toLowerCase().includes(search)) return false;
        if (severity && b.Severity !== severity) return false;
        if (category && b.Category !== category) return false;
        if (status && b.Status !== status) return false;
        if (reporter && b["Reporter Name"] !== reporter) return false;
        return true;
    });
}

function renderBugs() {
    const tbody = document.getElementById("bugs-table-body");
    const bugs = getFilteredBugs().slice().reverse();
    const admin = isAdmin();

    if (!bugs.length) {
        tbody.innerHTML = '<tr><td colspan="8" class="px-4 py-12 text-center text-gray-400">No bugs match your filters</td></tr>';
        return;
    }

    tbody.innerHTML = bugs.map(b => {
        const id = escapeHtml(b.ID);
        const pageUrlHtml = b["Page URL"]
            ? `<div class="font-semibold text-gray-700 mb-1 mt-3">Page URL</div><a href="${escapeHtml(b["Page URL"])}" target="_blank" class="text-brand-600 underline text-sm break-all">${escapeHtml(b["Page URL"])}</a>`
            : "";

        const showEdit = canEditBug(b);
        const showDelete = canDeleteBug();
        const showStatusDropdown = admin;

        const statusCell = showStatusDropdown
            ? `<select onchange="updateStatus('${id}', this.value); event.stopPropagation();"
                       class="text-xs rounded-lg border border-gray-300 px-2 py-1 bg-white focus:ring-2 focus:ring-brand-500 outline-none">
                   ${(window._statuses || []).map(s => `<option value="${s}" ${s === b.Status ? "selected" : ""}>${s}</option>`).join("")}
               </select>`
            : `<span class="inline-block px-2 py-0.5 rounded-full text-xs font-semibold status-${(b.Status || 'Open').toLowerCase().replace(/[' ]/g, '-')}">${escapeHtml(b.Status)}</span>`;

        let actionsHtml = "";
        if (showEdit) {
            actionsHtml += `<button onclick="event.stopPropagation(); openEditModal('${id}')" class="inline-flex items-center gap-1 text-xs text-brand-600 hover:text-brand-800 font-medium mr-2" title="Edit">
                <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"/></svg>
                Edit
            </button>`;
        }
        if (showDelete) {
            actionsHtml += `<button onclick="event.stopPropagation(); openDeleteModal('${id}')" class="inline-flex items-center gap-1 text-xs text-red-600 hover:text-red-800 font-medium" title="Delete">
                <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/></svg>
                Delete
            </button>`;
        }
        if (!actionsHtml) actionsHtml = '<span class="text-gray-300 text-xs">&mdash;</span>';

        return `
            <tr class="hover:bg-gray-50 cursor-pointer" onclick="toggleExpand('expand-${id}')">
                <td class="px-4 py-3 font-mono text-xs text-gray-500">#${id}</td>
                <td class="px-4 py-3 font-medium">${escapeHtml(b.Title)}</td>
                <td class="px-4 py-3"><span class="${severityClass(b.Severity)}">${escapeHtml(b.Severity)}</span></td>
                <td class="px-4 py-3 text-gray-600">${formatCategory(b)}</td>
                <td class="px-4 py-3 text-gray-600">${escapeHtml(b["Reporter Name"])}</td>
                <td class="px-4 py-3">${statusCell}</td>
                <td class="px-4 py-3 text-xs text-gray-500 whitespace-nowrap">${escapeHtml(b["Created At"])}</td>
                <td class="px-4 py-3 text-center whitespace-nowrap">${actionsHtml}</td>
            </tr>
            <tr class="expand-row" id="expand-${id}">
                <td colspan="8" class="px-4 py-4 bg-gray-50 border-t border-gray-100">
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
                        <div>
                            <div class="font-semibold text-gray-700 mb-1">Description</div>
                            <p class="text-gray-600 whitespace-pre-wrap">${escapeHtml(b.Description)}</p>
                            ${b["Steps to Reproduce"] ? `
                            <div class="font-semibold text-gray-700 mb-1 mt-3">Steps to Reproduce</div>
                            <p class="text-gray-600 whitespace-pre-wrap">${escapeHtml(b["Steps to Reproduce"])}</p>` : ""}
                            ${pageUrlHtml}
                        </div>
                        ${b["Screenshot Path"] ? `
                        <div>
                            <div class="font-semibold text-gray-700 mb-1">Screenshot</div>
                            <a href="/uploads/${escapeHtml(b["Screenshot Path"])}" target="_blank">
                                <img src="/uploads/${escapeHtml(b["Screenshot Path"])}" class="max-h-48 rounded-lg border border-gray-200" alt="Screenshot">
                            </a>
                        </div>` : ""}
                    </div>
                </td>
            </tr>
        `;
    }).join("");
}

function toggleExpand(id) {
    const row = document.getElementById(id);
    if (row) row.classList.toggle("show");
}

async function updateStatus(bugId, newStatus) {
    try {
        await api(`/api/bugs/${bugId}/status`, {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ status: newStatus }),
        });
        const bug = allBugs.find(b => b.ID === bugId);
        if (bug) bug.Status = newStatus;
        updateSummaryCards();
        showToast(`Bug #${bugId} updated to ${newStatus}`, "info");
    } catch (err) {
        showToast("Status update failed: " + err.message, "error");
        loadBugs(false);
    }
}

/* ── Edit modal ── */

function openEditModal(bugId) {
    const bug = allBugs.find(b => b.ID === bugId);
    if (!bug) return;

    document.getElementById("edit-bug-id").value = bugId;
    document.getElementById("edit-modal-id").textContent = `#${bugId}`;
    document.getElementById("edit-title").value = bug.Title || "";
    document.getElementById("edit-description").value = bug.Description || "";
    document.getElementById("edit-severity").value = bug.Severity || "Medium";
    document.getElementById("edit-category").value = bug.Category || "Other";
    document.getElementById("edit-status").value = bug.Status || "Open";
    document.getElementById("edit-steps").value = bug["Steps to Reproduce"] || "";
    document.getElementById("edit-reporter_name").value = bug["Reporter Name"] || "";
    document.getElementById("edit-reporter_email").value = bug["Reporter Email"] || "";
    document.getElementById("edit-page_url").value = bug["Page URL"] || "";
    document.getElementById("edit-page_title").value = bug["Page Title"] || "";
    document.getElementById("edit-subcategory").value = bug.Subcategory || "";

    const cat = bug.Category || "";
    document.getElementById("edit-subcategory-group").classList.toggle("hidden", !(window.CATEGORIES_WITH_PAGES || []).includes(cat));
    document.getElementById("edit-page-title-group").classList.toggle("hidden", cat !== "Other");

    document.getElementById("edit-modal").classList.remove("hidden");
}

function closeEditModal() {
    document.getElementById("edit-modal").classList.add("hidden");
}

async function handleEditSave(e) {
    e.preventDefault();
    const bugId = document.getElementById("edit-bug-id").value;
    const btn = document.getElementById("edit-save-btn");
    btn.disabled = true;

    const cat = document.getElementById("edit-category").value;
    const payload = {
        title: document.getElementById("edit-title").value.trim(),
        description: document.getElementById("edit-description").value.trim(),
        severity: document.getElementById("edit-severity").value,
        category: cat,
        subcategory: (window.CATEGORIES_WITH_PAGES || []).includes(cat)
            ? document.getElementById("edit-subcategory").value
            : "",
        status: document.getElementById("edit-status").value,
        steps: document.getElementById("edit-steps").value.trim(),
        reporter_name: document.getElementById("edit-reporter_name").value.trim(),
        reporter_email: document.getElementById("edit-reporter_email").value.trim(),
        page_url: document.getElementById("edit-page_url").value.trim(),
        page_title: cat === "Other" ? document.getElementById("edit-page_title").value.trim() : "",
        screenshot: (allBugs.find(b => b.ID === bugId) || {})["Screenshot Path"] || "",
    };

    try {
        await api(`/api/bugs/${bugId}`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        });
        showToast(`Bug #${bugId} updated`);
        closeEditModal();
        await loadBugs(false);
    } catch (err) {
        showToast("Update failed: " + err.message, "error");
    } finally {
        btn.disabled = false;
    }
}

/* ── Delete modal ── */

let pendingDeleteId = null;

function openDeleteModal(bugId) {
    pendingDeleteId = bugId;
    document.getElementById("delete-modal-id").textContent = `#${bugId}`;
    document.getElementById("delete-modal").classList.remove("hidden");
    document.getElementById("delete-confirm-btn").onclick = confirmDelete;
}

function closeDeleteModal() {
    document.getElementById("delete-modal").classList.add("hidden");
    pendingDeleteId = null;
}

async function confirmDelete() {
    if (!pendingDeleteId) return;
    const bugId = pendingDeleteId;
    try {
        await api(`/api/bugs/${bugId}`, { method: "DELETE" });
        allBugs = allBugs.filter(b => b.ID !== bugId);
        updateSummaryCards();
        renderBugs();
        showToast(`Bug #${bugId} deleted`);
        closeDeleteModal();
        await loadBugs(false);
    } catch (err) {
        showToast("Delete failed: " + err.message, "error");
    }
}

/* ===== Leaderboard ======================================================= */

let leaderboardInterval = null;

function initLeaderboard() {
    loadLeaderboard();
    leaderboardInterval = setInterval(loadLeaderboard, 60000);
}

async function loadLeaderboard() {
    try {
        const data = await api("/api/leaderboard");
        renderLeaderboard(data);
    } catch (err) {
        showToast("Failed to load leaderboard: " + err.message, "error");
    }
}

function renderLeaderboard(entries) {
    const tbody = document.getElementById("leaderboard-body");
    const podium = document.getElementById("podium");
    const noData = document.getElementById("no-data-msg");

    if (!entries.length) {
        tbody.closest("div").classList.add("hidden");
        podium.classList.add("hidden");
        noData.classList.remove("hidden");
        return;
    }

    noData.classList.add("hidden");
    tbody.closest("div").classList.remove("hidden");

    if (entries.length >= 1) {
        podium.classList.remove("hidden");
        for (let i = 1; i <= 3; i++) {
            const el = document.getElementById(`podium-${i}`);
            if (entries[i - 1]) {
                el.classList.remove("hidden");
                document.getElementById(`podium-${i}-name`).textContent = entries[i - 1].name;
                document.getElementById(`podium-${i}-pts`).textContent = `${entries[i - 1].points} pts / ${entries[i - 1].total_bugs} bugs`;
            } else {
                el.classList.add("hidden");
            }
        }
    } else {
        podium.classList.add("hidden");
    }

    tbody.innerHTML = entries.map(e => {
        const rankBadge = e.rank <= 3
            ? `<span class="inline-flex items-center justify-center w-7 h-7 rounded-full text-white text-xs font-bold podium-${e.rank}">${e.rank}</span>`
            : `<span class="text-gray-500 font-medium">${e.rank}</span>`;
        return `
            <tr class="${e.rank <= 3 ? 'bg-yellow-50/40' : ''} hover:bg-gray-50">
                <td class="px-4 py-3">${rankBadge}</td>
                <td class="px-4 py-3">
                    <span class="font-medium">${escapeHtml(e.name)}</span>
                    ${e.email ? `<span class="text-gray-400 text-xs ml-1">${escapeHtml(e.email)}</span>` : ""}
                </td>
                <td class="px-4 py-3 text-center font-bold text-brand-700">${e.points}</td>
                <td class="px-4 py-3 text-center">${e.total_bugs}</td>
                <td class="px-4 py-3 text-center text-red-600 font-medium">${e.critical || 0}</td>
                <td class="px-4 py-3 text-center text-orange-600 font-medium">${e.high || 0}</td>
                <td class="px-4 py-3 text-center text-yellow-600 font-medium">${e.medium || 0}</td>
                <td class="px-4 py-3 text-center text-green-600 font-medium">${e.low || 0}</td>
            </tr>
        `;
    }).join("");
}
