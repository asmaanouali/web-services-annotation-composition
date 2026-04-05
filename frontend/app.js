// ============================================================
// Intelligent Web Service Composition System — Application JS
// ============================================================

// ============================================================
// SECURITY HELPERS
// ============================================================
/**
 * Escape HTML-special characters to prevent XSS when inserting
 * dynamic data into innerHTML.  Static literal HTML is safe — only
 * values originating from user input, server responses, or
 * untrusted sources must be escaped.
 */
function escapeHtml(str) {
    if (str === null || str === undefined) return '';
    const div = document.createElement('div');
    div.appendChild(document.createTextNode(String(str)));
    return div.innerHTML;
}

// ============================================================
// TOAST NOTIFICATION SYSTEM
// ============================================================
function showToast(message, type = 'info', title = '', duration = 4000) {
    const container = document.getElementById('toast-container');
    const icons = { success: '✓', error: '✕', warning: '⚠', info: 'ℹ' };
    const titles = { success: 'Success', error: 'Error', warning: 'Warning', info: 'Info' };
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.innerHTML = `
        <span class="toast-icon">${icons[type] || icons.info}</span>
        <div class="toast-body">
            <div class="toast-title">${escapeHtml(title || titles[type])}</div>
            <div class="toast-msg">${escapeHtml(message)}</div>
        </div>
        <button class="toast-close" onclick="dismissToast(this.parentElement)">&times;</button>
    `;
    container.appendChild(toast);
    if (duration > 0) {
        setTimeout(() => dismissToast(toast), duration);
    }
    return toast;
}
function dismissToast(toast) {
    if (!toast || toast.classList.contains('removing')) return;
    toast.classList.add('removing');
    setTimeout(() => toast.remove(), 300);
}

// ============================================================
// BUTTON LOADING HELPERS
// ============================================================
function btnLoading(btn, text) {
    if (!btn) return;
    btn._origHTML = btn.innerHTML;
    btn.classList.add('loading');
    btn.disabled = true;
    if (text) btn.innerHTML = text;
}
function btnReset(btn) {
    if (!btn) return;
    btn.classList.remove('loading');
    btn.disabled = false;
    if (btn._origHTML) btn.innerHTML = btn._origHTML;
}

// ============================================================
// SMOOTH SCROLL HELPER
// ============================================================
function scrollToEl(el) {
    if (!el) return;
    setTimeout(() => el.scrollIntoView({ behavior: 'smooth', block: 'start' }), 100);
}

// ============================================================
// GLOBAL STATE
// ============================================================
const API = window.location.hostname === 'localhost' && window.location.port !== '80'
    ? 'http://localhost:5000/api'
    : '/api';
let currentServices = [];
let currentRequests = [];
let classicResults = {};
let llmResults = {};
let selectedServiceIds = new Set();
let isUploading = false;
let annInterval = null;
let utilityChart = null;
let timeChart = null;

// ============================================================
// TAB NAVIGATION
// ============================================================
function showTab(idx) {
    document.querySelectorAll('.tab-btn').forEach((t,i) => {
        t.classList.toggle('active', i === idx);
        t.setAttribute('aria-selected', i === idx ? 'true' : 'false');
    });
    document.querySelectorAll('.tab-content').forEach((c,i) => {
        c.classList.toggle('active', i === idx);
    });
    window.scrollTo({ top: 0, behavior: 'smooth' });
    if (idx === 1) updateSelectionList();
    if (idx === 3) checkAnnotationForLLM();
}

// Tab completion badges
function markTabDone(idx) {
    const btn = document.querySelectorAll('.tab-btn')[idx];
    if (!btn || btn.querySelector('.tab-badge')) return;
    const badge = document.createElement('span');
    badge.className = 'tab-badge';
    badge.textContent = '✓';
    btn.appendChild(badge);
}

// ============================================================
// ALGORITHM DESCRIPTION UPDATER
// ============================================================
document.getElementById('algo-select').addEventListener('change', function() {
    const descs = {
        dijkstra: '<strong>Dijkstra:</strong> Explores all possible paths through the service graph to find the one with the best utility. Guarantees optimal solution but slower for large graphs.',
        astar: '<strong>A*:</strong> Uses a heuristic function to guide the search towards promising services. Combines Dijkstra\'s optimality with smart exploration. Often faster than Dijkstra.',
        greedy: '<strong>Greedy:</strong> At each step, picks the locally best service without backtracking. Very fast but may miss the global optimum. Good for real-time constraints.'
    };
    document.getElementById('algo-desc').innerHTML = descs[this.value] || '';
});

// ============================================================
// TRAINING
// ============================================================
function updateTrainingFile(type) {
    const map = {
        wsdl: ['training-wsdl-files', 'training-wsdl-count'],
        requests: ['training-requests-file', 'training-requests-name'],
        solutions: ['training-solutions-file', 'training-solutions-name'],
        best: ['training-best-solutions-file', 'training-best-name']
    };
    const [inputId, displayId] = map[type];
    const input = document.getElementById(inputId);
    const display = document.getElementById(displayId);
    if (type === 'wsdl') {
        const n = input.files.length;
        display.textContent = n > 0 ? `${n} file${n>1?'s':''} selected` : '0 files selected';
        display.style.color = n > 0 ? 'var(--success)' : 'var(--text-muted)';
    } else {
        display.textContent = input.files.length > 0 ? input.files[0].name : 'No file selected';
        display.style.color = input.files.length > 0 ? 'var(--success)' : 'var(--text-muted)';
    }
}

async function uploadAndTrainLLM() {
    const wsdlFiles = Array.from(document.getElementById('training-wsdl-files').files)
        .filter(f => f.name.endsWith('.wsdl') || f.name.endsWith('.xml'));
    const reqFile = document.getElementById('training-requests-file').files[0];
    const solFile = document.getElementById('training-solutions-file').files[0];
    const bestFile = document.getElementById('training-best-solutions-file').files[0];

    if (wsdlFiles.length === 0) { showToast('Please select training WSDL files.', 'warning'); return; }
    if (!reqFile) { showToast('Please select a training requests file.', 'warning'); return; }

    const trainBtn = document.querySelector('[onclick="uploadAndTrainLLM()"]');
    btnLoading(trainBtn, '&#x23F3; Training...');
    const sec = document.getElementById('training-progress-section');
    const bar = document.getElementById('training-progress');
    const txt = document.getElementById('training-progress-text');
    sec.style.display = 'block';
    bar.style.width = '0%'; bar.textContent = '0%';
    bar.className = 'progress-fill';

    try {
        // Step 1: Reset training WSDL
        txt.textContent = 'Resetting previous training data...';
        await fetch(`${API}/training/reset-wsdl`, { method: 'POST' });

        // Step 2: Upload WSDL in batches
        const BATCH = 200;
        const totalBatches = Math.ceil(wsdlFiles.length / BATCH);
        let totalServicesUploaded = 0;

        for (let i = 0; i < wsdlFiles.length; i += BATCH) {
            const batch = wsdlFiles.slice(i, i + BATCH);
            const batchNum = Math.floor(i / BATCH) + 1;
            const pct = Math.round((i / wsdlFiles.length) * 60);

            bar.style.width = pct + '%'; bar.textContent = pct + '%';
            txt.textContent = `Uploading WSDL batch ${batchNum}/${totalBatches} (${batch.length} files)...`;

            const fd = new FormData();
            batch.forEach(f => fd.append('wsdl_files', f));
            fd.append('batch_num', batchNum);

            const r = await fetch(`${API}/training/upload-wsdl-batch`, { method: 'POST', body: fd });
            const d = await r.json();

            if (!r.ok) throw new Error(d.error || `Batch ${batchNum} failed`);
            totalServicesUploaded = d.total_training_services;
            txt.textContent = `Batch ${batchNum}/${totalBatches} done — ${totalServicesUploaded} services total`;
        }

        // Step 3: Upload XML files (requests, solutions)
        bar.style.width = '65%'; bar.textContent = '65%';
        txt.textContent = 'Uploading XML files (requests, solutions)...';

        const xmlFd = new FormData();
        xmlFd.append('requests_file', reqFile);
        if (solFile) xmlFd.append('solutions_file', solFile);
        if (bestFile) xmlFd.append('best_solutions_file', bestFile);

        const xmlRes = await fetch(`${API}/training/upload-xml-files`, { method: 'POST', body: xmlFd });
        const xmlData = await xmlRes.json();
        if (!xmlRes.ok) throw new Error(xmlData.error);

        bar.style.width = '80%'; bar.textContent = '80%';
        txt.textContent = `XML uploaded: ${xmlData.training_requests} requests, ${xmlData.training_solutions} solutions. Training LLM...`;

        // Step 4: Start training
        const trRes = await fetch(`${API}/training/start`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        const trData = await trRes.json();
        if (!trRes.ok) throw new Error(trData.error);

        bar.style.width = '100%'; bar.textContent = '100%';
        bar.classList.add('success');
        txt.textContent = `Training complete! ${totalServicesUploaded} services, ${xmlData.training_requests} requests, ${trData.training_examples_count} examples learned.`;
        updateTrainingBadge(true, trData.training_examples_count);
        showToast(`${trData.training_examples_count} examples learned successfully`, 'success', 'Training Complete');
        loadMetrics();
        btnReset(trainBtn);

    } catch (e) {
        bar.style.width = '100%'; bar.textContent = 'Error';
        bar.classList.add('error');
        txt.textContent = `Error: ${e.message}`;
        showToast(e.message, 'error', 'Training Failed');
        btnReset(trainBtn);
    }
}

function updateTrainingBadge(trained, count) {
    const badge = document.getElementById('training-status-badge');
    const text = document.getElementById('training-status-text');
    const dot = document.getElementById('hdr-train-dot');
    const hdrText = document.getElementById('hdr-train-text');
    if (trained) {
        badge.style.background = 'var(--success-bg)';
        badge.style.borderColor = 'var(--success)';
        text.innerHTML = `&#x2705; LLM Trained &mdash; ${count} examples loaded`;
        text.style.color = 'var(--success)';
        dot.classList.remove('inactive');
        hdrText.textContent = `Trained (${count})`;
    } else {
        badge.style.background = 'var(--surface-alt)';
        text.innerHTML = '&#x26A0;&#xFE0F; LLM Not Trained';
        text.style.color = 'var(--text-muted)';
        dot.classList.add('inactive');
        hdrText.textContent = 'Not Trained';
    }
}

async function loadMetrics() {
    try {
        const r = await fetch(`${API}/training/status`);
        if (!r.ok) return;
        const d = await r.json();
        if (d.is_trained) {
            document.getElementById('learning-metrics').style.display = 'block';
            document.getElementById('m-total-comps').textContent = d.training_examples;
            const pm = d.performance_metrics;
            const coverage = pm.total_compositions > 0
                ? (pm.successful_compositions / pm.total_compositions * 100).toFixed(1) : '0';
            document.getElementById('m-success-rate').textContent = coverage + '%';
            document.getElementById('m-avg-utility').textContent = pm.average_utility.toFixed(2);
            document.getElementById('m-learning-rate').textContent = pm.learning_rate.toFixed(1) + '%';
            updateTrainingBadge(true, d.training_examples);

            const tq = d.training_quality;
            const detailsEl = document.getElementById('training-quality-details');
            if (tq && Object.keys(tq).length > 0 && detailsEl) {
                const parts = [];
                if (tq.patterns_learned !== undefined) parts.push(`<b>Patterns:</b> ${tq.patterns_learned}`);
                if (tq.unique_operations !== undefined) parts.push(`<b>Operations:</b> ${tq.unique_operations}`);
                if (tq.io_chains !== undefined) parts.push(`<b>I/O Chains:</b> ${tq.io_chains}`);
                if (tq.service_rankings !== undefined) parts.push(`<b>Rankings:</b> ${tq.service_rankings}`);
                if (parts.length > 0) {
                    detailsEl.innerHTML = parts.join(' &nbsp;|&nbsp; ');
                    detailsEl.style.display = 'block';
                }
            }
        }
    } catch(e) { /* server offline */ }
}

// ============================================================
// SERVICE UPLOAD
// ============================================================
async function uploadServices() {
    if (isUploading) return;
    const input = document.getElementById('wsdl-files');
    const files = Array.from(input.files).filter(f => f.name.endsWith('.wsdl') || f.name.endsWith('.xml'));
    if (!files.length) return;
    isUploading = true;
    const sec = document.getElementById('upload-progress-section');
    const bar = document.getElementById('upload-progress');
    const stat = document.getElementById('upload-status');
    const log = document.getElementById('batch-log');
    sec.style.display = 'block'; bar.style.width = '0%'; bar.textContent = '0%'; log.innerHTML = '';
    bar.className = 'progress-fill';

    const BATCH = 500;
    let total = 0, all = [...currentServices];
    const batches = Math.ceil(files.length / BATCH);
    log.innerHTML += `<div class="log-item">Processing ${files.length} files in ${batches} batch(es)...</div>`;

    try {
        for (let i = 0; i < files.length; i += BATCH) {
            const batch = files.slice(i, i + BATCH);
            const bn = Math.floor(i/BATCH)+1;
            stat.textContent = `Uploading batch ${bn}/${batches}...`;
            const fd = new FormData();
            batch.forEach(f => fd.append('files', f));
            const r = await fetch(`${API}/services/upload`, {method:'POST',body:fd});
            const d = await r.json();
            if (r.ok) {
                total += d.services.length;
                all = all.concat(d.services);
                const pct = Math.round((i+batch.length)/files.length*100);
                bar.style.width = pct+'%'; bar.textContent = pct+'%';
                log.innerHTML += `<div class="log-item ok">Batch ${bn}: ${d.services.length} services loaded</div>`;
            } else {
                log.innerHTML += `<div class="log-item err">Batch ${bn}: ${d.error}</div>`;
            }
            log.scrollTop = log.scrollHeight;
        }
        if (total > 0) {
            currentServices = all;
            bar.style.width = '100%'; bar.textContent = '100%'; bar.classList.add('success');
            stat.textContent = `${total} new services loaded. Total: ${all.length} services.`;
            document.getElementById('service-count').innerHTML = `Services loaded: <span style="font-size:20px;color:var(--success)">${all.length}</span>`;
            document.getElementById('hdr-svc-count').textContent = `${all.length} services`;
            displayServices(all);
            all.forEach(s => selectedServiceIds.add(s.id));
            showToast(`${total} services loaded successfully`, 'success');
            markTabDone(0);
        } else {
            bar.classList.add('error'); stat.textContent = 'No services loaded.';
        }
    } catch(e) {
        bar.classList.add('error'); stat.textContent = `Error: ${e.message}`;
    } finally {
        isUploading = false; input.value = '';
    }
}

function displayServices(services) {
    const el = document.getElementById('services-list');
    if (!services.length) { el.innerHTML = '<p style="text-align:center;color:var(--text-muted);padding:50px;font-style:italic">No services loaded.</p>'; return; }
    if (services.length > 500) {
        el.innerHTML = `<div style="text-align:center;padding:40px"><h3 style="color:var(--primary);margin-bottom:12px">${services.length} services loaded</h3><p style="color:var(--text-muted)">Too many to display. Services are available for annotation and composition.</p></div>`;
        return;
    }
    el.innerHTML = services.slice(0,300).map(s => `
        <div class="service-item" style="cursor:default">
            <div class="svc-id">${s.id}</div>
            <div class="svc-meta">
                <span class="tag tag-in">${s.inputs.length} in</span>
                <span class="tag tag-out">${s.outputs.length} out</span>
                <span class="tag tag-qos">RT:${s.qos.ResponseTime.toFixed(0)}</span>
                <span class="tag tag-qos">Rel:${s.qos.Reliability.toFixed(0)}%</span>
                <span class="tag tag-qos">Avl:${s.qos.Availability.toFixed(0)}%</span>
            </div>
        </div>
    `).join('') + (services.length > 300 ? `<div style="text-align:center;padding:20px;color:var(--text-muted)">+ ${services.length-300} more services</div>` : '');
}

// ============================================================
// ANNOTATION TAB
// ============================================================
function updateSelectionList() {
    const el = document.getElementById('services-selection-list');
    if (!currentServices.length) { el.innerHTML = '<p style="text-align:center;color:var(--text-muted);padding:40px;font-style:italic">Load services in Tab 1 first.</p>'; return; }
    el.innerHTML = currentServices.slice(0,500).map(s => `
        <div class="service-item" onclick="toggleSvc('${s.id}')">
            <input type="checkbox" id="svc-${s.id}" ${selectedServiceIds.has(s.id)?'checked':''} onclick="event.stopPropagation();toggleSvc('${s.id}')">
            <div class="svc-id">${s.id}</div>
            <div class="svc-meta"><span class="tag tag-in">${s.inputs.length} in</span><span class="tag tag-out">${s.outputs.length} out</span></div>
        </div>
    `).join('');
    updateCount();
    updateEstimation();
}

function toggleSvc(id) {
    selectedServiceIds.has(id) ? selectedServiceIds.delete(id) : selectedServiceIds.add(id);
    const cb = document.getElementById(`svc-${id}`);
    if (cb) cb.checked = selectedServiceIds.has(id);
    updateCount();
}
function selectAllServices() { selectedServiceIds = new Set(currentServices.map(s=>s.id)); updateSelectionList(); }
function deselectAllServices() { selectedServiceIds.clear(); updateSelectionList(); }
function updateCount() { document.getElementById('selected-count').textContent = `${selectedServiceIds.size} selected`; }

// Dynamic time estimation
let _estimationTimer = null;
function updateEstimation() {
    clearTimeout(_estimationTimer);
    _estimationTimer = setTimeout(_doUpdateEstimation, 250);
}
async function _doUpdateEstimation() {
    if (!currentServices.length || !selectedServiceIds.size) {
        document.getElementById('estimation-panel').innerHTML = '';
        return;
    }
    const types = getAnnotationTypes();
    if (!types.length) return;
    const useLLM = document.getElementById('use-llm-annotation').checked;
    const maxWorkers = parseInt(document.getElementById('ann-workers')?.value || '10');
    const batchSize = parseInt(document.getElementById('ann-batch-size')?.value || '5');
    try {
        const r = await fetch(`${API}/annotate/estimate`, {
            method: 'POST',
            headers: {'Content-Type':'application/json'},
            body: JSON.stringify({
                use_llm: useLLM,
                service_ids: Array.from(selectedServiceIds),
                annotation_types: types,
                max_workers: maxWorkers,
                batch_size: batchSize
            })
        });
        if (!r.ok) throw new Error('API error');
        const d = await r.json();
        renderEstimation(d);
    } catch(e) {
        const panel = document.getElementById('estimation-panel');
        if (panel.innerHTML) {
            panel.querySelectorAll('.est-total span:last-child')
                .forEach(el => el.textContent = '~…');
        }
    }
}

function formatTime(seconds) {
    if (seconds < 0.001) return '<1ms';
    if (seconds < 1) return (seconds * 1000).toFixed(0) + 'ms';
    if (seconds < 60) return seconds.toFixed(1) + 's';
    const mins = Math.floor(seconds / 60);
    const secs = Math.round(seconds % 60);
    return `${mins}m ${secs}s`;
}

function renderEstimation(d) {
    const timeStr = formatTime(d.estimated_time_seconds);

    let breakdownHTML = '';
    if (d.breakdown) {
        breakdownHTML = Object.values(d.breakdown).map(b =>
            `<div class="est-row"><span class="est-label">${escapeHtml(b.label)}</span><span class="est-value">${formatTime(b.time)}</span></div>`
        ).join('');
    }

    let statusHTML = '';
    if (d.status_note) {
        const isWarning = d.status_note.toLowerCase().includes('offline');
        statusHTML = `<div class="est-row" style="color:${isWarning ? 'var(--warning,#e67e22)' : 'var(--success,#27ae60)'};font-size:11px;font-style:italic"><span>${escapeHtml(d.status_note)}</span></div>`;
    }

    document.getElementById('estimation-panel').innerHTML = `
        <div class="estimation-panel">
            <h4>&#x23F1;&#xFE0F; Estimated Duration</h4>
            ${statusHTML}
            ${breakdownHTML}
            <div class="est-row"><span class="est-label">Complexity Factor</span><span class="est-value">${d.complexity_factor}x</span></div>
            <div class="est-row"><span class="est-label">Avg I/O per service</span><span class="est-value">${d.avg_io_per_service}</span></div>
            <div class="est-total"><span>Total (est.)</span><span>~${timeStr}</span></div>
        </div>
    `;
}

function getAnnotationTypes() {
    const t = [];
    if (document.getElementById('ann-interaction').checked) t.push('interaction');
    if (document.getElementById('ann-context').checked) t.push('context');
    if (document.getElementById('ann-policy').checked) t.push('policy');
    return t;
}

// Auto-update estimation when config changes
['ann-interaction','ann-context','ann-policy','use-llm-annotation','ann-skip-annotated'].forEach(id => {
    document.getElementById(id).addEventListener('change', updateEstimation);
});
['ann-workers','ann-batch-size'].forEach(id => {
    document.getElementById(id).addEventListener('input', updateEstimation);
});

// Show/hide performance controls based on LLM toggle
document.getElementById('use-llm-annotation').addEventListener('change', function() {
    const controls = document.getElementById('llm-perf-controls');
    if (controls) controls.style.display = this.checked ? 'block' : 'none';
});

async function startAnnotation() {
    if (!currentServices.length) { showToast('Load services first in Tab 1.', 'warning'); return; }
    if (!selectedServiceIds.size) { showToast('Select at least one service.', 'warning'); return; }
    const types = getAnnotationTypes();
    if (!types.length) { showToast('Select at least one annotation type.', 'warning'); return; }
    confirmAnnotation();
}
function closeModal() { document.getElementById('ann-modal').classList.remove('show'); }

async function confirmAnnotation() {
    const types = getAnnotationTypes();
    const useLLM = document.getElementById('use-llm-annotation').checked;
    const ids = Array.from(selectedServiceIds);
    const maxWorkers = parseInt(document.getElementById('ann-workers')?.value || '10');
    const batchSize = parseInt(document.getElementById('ann-batch-size')?.value || '5');
    const skipAnnotated = document.getElementById('ann-skip-annotated')?.checked || false;

    document.getElementById('ann-progress-card').style.display = 'block';
    document.getElementById('ann-results-card').style.display = 'none';
    const bar = document.getElementById('ann-progress');
    const stat = document.getElementById('ann-status');
    const log = document.getElementById('ann-log');
    bar.style.width = '0%'; bar.textContent = '0%'; bar.className = 'progress-fill';
    stat.textContent = 'Initializing...'; log.innerHTML = '';
    // Clear any previous polling interval to prevent leaks
    if (annInterval) { clearTimeout(annInterval); annInterval = null; }
    const batchInfo = useLLM ? ` | ${maxWorkers} workers, batch=${batchSize}${skipAnnotated ? ', skip annotated' : ''}` : '';
    log.innerHTML += `<div class="log-item">Starting annotation: ${ids.length} services, ${types.join(', ')}, method: ${useLLM?'LLM':'Classic'}${batchInfo}</div>`;

    try {
        const startResp = await fetch(`${API}/annotate/start`, {
            method:'POST', headers:{'Content-Type':'application/json'},
            body: JSON.stringify({
                use_llm: useLLM,
                service_ids: ids,
                annotation_types: types,
                max_workers: maxWorkers,
                batch_size: batchSize,
                skip_annotated: skipAnnotated
            })
        });

        if (!startResp.ok) {
            const errData = await startResp.json().catch(() => ({}));
            bar.classList.add('error');
            stat.textContent = `Error: ${errData.error || startResp.statusText}`;
            return;
        }

        let lastCurrent = -1;
        let pollErrors = 0;
        const maxPollErrors = 10;

        async function pollProgress() {
            try {
                const pr = await fetch(`${API}/annotate/progress`);
                if (!pr.ok) {
                    pollErrors++;
                    if (pollErrors >= maxPollErrors) {
                        stat.textContent = `Polling failed (HTTP ${pr.status}). Backend may be overloaded.`;
                        return;
                    }
                    annInterval = setTimeout(pollProgress, 1000);
                    return;
                }
                pollErrors = 0;
                const pd = await pr.json();
                if (pd.total > 0) {
                    const pct = Math.round(pd.current / pd.total * 100);
                    bar.style.width = pct + '%';
                    bar.textContent = `${pd.current} / ${pd.total}`;
                    stat.textContent = pd.current_service
                        ? `Service ${pd.current} / ${pd.total} — ${pd.current_service}`
                        : `Service ${pd.current} / ${pd.total}`;
                    if (pd.current !== lastCurrent && pd.current_service) {
                        lastCurrent = pd.current;
                        log.innerHTML += `<div class="log-item ok">&#x2714; ${escapeHtml(pd.current_service)} (${pd.current}/${pd.total})</div>`;
                        log.scrollTop = log.scrollHeight;
                    }
                }
                if (pd.completed) {
                    if (pd.error) {
                        bar.classList.add('error');
                        stat.textContent = `Error: ${pd.error}`;
                    } else if (pd.result) {
                        bar.style.width = '100%';
                        bar.textContent = `${pd.result.total_annotated} / ${pd.result.total_annotated}`;
                        bar.classList.add('success');
                        stat.textContent = `Annotation complete: ${pd.result.total_annotated} services annotated.`;
                        showAnnotationResults(pd.result);
                        showToast(`${pd.result.total_annotated} services annotated`, 'success', 'Annotation Complete');
                        markTabDone(1);
                        scrollToEl(document.getElementById('ann-results-card'));
                    }
                    return;
                }
                annInterval = setTimeout(pollProgress, 500);
            } catch(e) {
                pollErrors++;
                if (pollErrors >= maxPollErrors) {
                    stat.textContent = `Connection lost after ${maxPollErrors} retries. Check backend.`;
                    return;
                }
                annInterval = setTimeout(pollProgress, 1000);
            }
        }
        annInterval = setTimeout(pollProgress, 300);

    } catch(e) {
        clearTimeout(annInterval);
        bar.classList.add('error');
        stat.textContent = `Error: ${e.message}`;
    }
}

function showAnnotationResults(data) {
    document.getElementById('ann-results-card').style.display = 'block';
    const el = document.getElementById('ann-results');
    el.innerHTML = `
        <div class="result-box result-success"><strong>Annotation completed:</strong> ${data.total_annotated} services annotated using ${data.used_llm?'LLM':'classic'} method.</div>
        ${data.services ? `
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px;gap:8px;flex-wrap:wrap">
            <label style="display:flex;align-items:center;gap:6px;font-size:13px;cursor:pointer">
                <input type="checkbox" id="ann-select-all" onchange="toggleSelectAllAnnotated(this.checked)" style="width:15px;height:15px">
                <span id="ann-selection-label">Select all (${data.services.length})</span>
            </label>
            <div style="display:flex;gap:8px">
                <button class="btn btn-primary btn-sm" onclick="downloadAllAnnotated()">&#x1F4E6; Download All as ZIP</button>
                <button class="btn btn-sm" id="ann-download-selected-btn" onclick="downloadSelectedAnnotated()" disabled style="opacity:0.5">&#x1F4E5; Download Selected</button>
            </div>
        </div>
        <div style="max-height:350px;overflow-y:auto;border:1px solid var(--border);border-radius:var(--radius)">
            ${data.services.map(s => `
                <div style="display:flex;align-items:center;justify-content:space-between;padding:10px 16px;border-bottom:1px solid var(--border)">
                    <label style="display:flex;align-items:center;gap:10px;cursor:pointer;flex:1;min-width:0">
                        <input type="checkbox" class="ann-svc-cb" data-id="${escapeHtml(s.id)}" onchange="onAnnotatedCheckChange()" style="width:15px;height:15px;flex-shrink:0">
                        <span class="svc-id">${escapeHtml(s.id)}</span>
                        <span style="font-size:12px;color:var(--text-muted)">${s.inputs.length} in / ${s.outputs.length} out ${s.annotations ? '&bull; Annotated' : ''}</span>
                    </label>
                    <button class="btn btn-sm" onclick="downloadAnnotated('${escapeHtml(s.id)}')" style="flex-shrink:0;margin-left:8px">Download</button>
                </div>
            `).join('')}
        </div>` : ''}
    `;
    checkAnnotationForLLM();
}

function toggleSelectAllAnnotated(checked) {
    document.querySelectorAll('.ann-svc-cb').forEach(cb => cb.checked = checked);
    onAnnotatedCheckChange();
}

function onAnnotatedCheckChange() {
    const all = document.querySelectorAll('.ann-svc-cb');
    const checked = document.querySelectorAll('.ann-svc-cb:checked');
    const selectAllCb = document.getElementById('ann-select-all');
    const downloadBtn = document.getElementById('ann-download-selected-btn');
    const label = document.getElementById('ann-selection-label');
    if (selectAllCb) selectAllCb.indeterminate = checked.length > 0 && checked.length < all.length;
    if (selectAllCb) selectAllCb.checked = checked.length === all.length && all.length > 0;
    if (label) label.textContent = checked.length > 0
        ? `${checked.length} / ${all.length} selected`
        : `Select all (${all.length})`;
    if (downloadBtn) {
        downloadBtn.disabled = checked.length === 0;
        downloadBtn.style.opacity = checked.length === 0 ? '0.5' : '1';
    }
}

async function downloadSelectedAnnotated() {
    const checked = document.querySelectorAll('.ann-svc-cb:checked');
    if (!checked.length) return;
    const ids = Array.from(checked).map(cb => cb.dataset.id).join(',');
    try {
        const r = await fetch(`${API}/services/download-all?ids=${encodeURIComponent(ids)}&annotated_only=false`);
        if (r.ok) {
            const blob = await r.blob();
            const a = document.createElement('a'); a.href = URL.createObjectURL(blob);
            a.download = 'selected_annotated_services.zip'; a.click(); URL.revokeObjectURL(a.href);
        } else {
            const d = await r.json().catch(() => ({}));
            showToast(d.error || 'Download failed', 'error', 'Download Failed');
        }
    } catch(e) { showToast(e.message, 'error', 'Download Failed'); }
}

async function downloadAllAnnotated() {
    try {
        const r = await fetch(`${API}/services/download-all`);
        if (r.ok) {
            const blob = await r.blob();
            const a = document.createElement('a'); a.href = URL.createObjectURL(blob);
            a.download = 'annotated_services.zip'; a.click(); URL.revokeObjectURL(a.href);
        } else {
            const d = await r.json().catch(() => ({}));
            showToast(d.error || 'Download failed', 'error', 'Download Failed');
        }
    } catch(e) { showToast(e.message, 'error', 'Download Failed'); }
}

async function downloadAnnotated(id) {
    try {
        const r = await fetch(`${API}/services/${id}/download`);
        if (r.ok) {
            const blob = await r.blob();
            const a = document.createElement('a'); a.href = URL.createObjectURL(blob);
            a.download = `${id}_enriched.xml`; a.click(); URL.revokeObjectURL(a.href);
        }
    } catch(e) { showToast(e.message, 'error', 'Download Failed'); }
}

// ============================================================
// REQUESTS
// ============================================================
async function uploadRequests() {
    const fd = new FormData();
    fd.append('file', document.getElementById('requests-file').files[0]);
    try {
        const r = await fetch(`${API}/requests/upload`, {method:'POST',body:fd});
        const d = await r.json();
        if (r.ok) {
            currentRequests = d.requests || [];
            document.getElementById('requests-count').innerHTML = `Requests loaded: <span style="font-size:20px">${d.requests.length}</span>`;
            populateSelects(d.requests);
            showToast(d.message, 'success');
        } else { showToast(d.error, 'error'); }
    } catch(e) { showToast(e.message, 'error'); }
}

function populateSelects(reqs) {
    ['req-select-classic','req-select-llm'].forEach(id => {
        document.getElementById(id).innerHTML = '<option value="">-- Select a request --</option>' + reqs.map(r => `<option value="${r.id}">${r.id}</option>`).join('');
    });
}

function showReqDetails(type) {
    const reqId = document.getElementById(`req-select-${type}`).value;
    const el = document.getElementById(`req-details-${type}`);
    if (!reqId) { el.style.display = 'none'; return; }
    const req = currentRequests.find(r => r.id === reqId);
    if (!req) return;
    el.style.display = 'block';
    el.innerHTML = `
        <div class="card-grid" style="gap:10px">
            <div class="kpi-box" style="padding:12px"><div class="kpi-label">Provided</div><div class="kpi-value" style="font-size:20px">${req.provided.length} params</div></div>
            <div class="kpi-box" style="padding:12px"><div class="kpi-label">Resultant</div><div class="kpi-value" style="font-size:14px;font-family:Consolas,monospace">${req.resultant}</div></div>
        </div>
        <div class="qos-grid" style="margin-top:12px">
            ${Object.entries(req.qos_constraints).map(([k,v]) => `<div class="qos-item"><span class="qos-name">${k}</span><span class="qos-val">${typeof v === 'number' ? v.toFixed(1) : v}</span></div>`).join('')}
        </div>
    `;
}

// ============================================================
// CLASSIC COMPOSITION
// ============================================================
async function composeClassic() {
    const reqId = document.getElementById('req-select-classic').value;
    const algo = document.getElementById('algo-select').value;
    if (!reqId) { showToast('Select a request first.', 'warning'); return; }

    const compBtn = document.querySelector('[onclick="composeClassic()"]');
    btnLoading(compBtn, '&#x23F3; Computing...');
    document.getElementById('classic-viz-card').style.display = 'block';
    document.getElementById('classic-result-card').style.display = 'block';
    document.getElementById('algo-trace').innerHTML = '<div style="padding:20px;text-align:center"><div class="spinner"></div> Running algorithm...</div>';
    document.getElementById('algo-graph').innerHTML = '<div style="padding:20px;text-align:center"><div class="spinner"></div></div>';
    document.getElementById('classic-result').innerHTML = '<div style="padding:20px;text-align:center"><div class="spinner"></div> Computing...</div>';

    try {
        const r = await fetch(`${API}/compose/classic`, {
            method:'POST', headers:{'Content-Type':'application/json'},
            body: JSON.stringify({ request_id: reqId, algorithm: algo })
        });
        const d = await r.json();
        if (r.ok) {
            classicResults[reqId] = d;
            renderAlgoTrace(d.algorithm_trace || []);
            renderGraph(d.graph_data, d.workflow || []);
            renderClassicResult(d);
            markTabDone(2);
            scrollToEl(document.getElementById('classic-result-card'));
        } else {
            document.getElementById('classic-result').innerHTML = `<div class="result-box result-error"><strong>Error:</strong> ${escapeHtml(d.error)}</div>`;
            document.getElementById('algo-trace').innerHTML = '';
            document.getElementById('algo-graph').innerHTML = '';
        }
        btnReset(compBtn);
    } catch(e) {
        document.getElementById('classic-result').innerHTML = `<div class="result-box result-error"><strong>Error:</strong> ${escapeHtml(e.message)}</div>`;
        btnReset(compBtn);
    }
}

function renderAlgoTrace(trace) {
    const el = document.getElementById('algo-trace');
    if (!trace.length) { el.innerHTML = '<p style="padding:16px;color:var(--text-muted)">No trace available.</p>'; return; }
    el.innerHTML = trace.map(step => {
        let cls = 'trace-step';
        if (step.action === 'goal_found' || step.action === 'complete') cls += ' goal';
        else if (step.action === 'explore' || step.action === 'expand' || step.action === 'greedy_choice' || step.action === 'heuristic_boost') cls += ' explore';
        else if (step.action === 'failed' || step.action === 'dead_end') cls += ' failed';

        let extra = '';
        if (step.service_id) extra += `<span class="tag tag-qos" style="margin-left:8px">${step.service_id}</span>`;
        if (step.utility !== undefined) extra += `<span class="tag tag-in" style="margin-left:4px">U:${step.utility}</span>`;
        if (step.candidates_count !== undefined) extra += `<span class="tag" style="background:#f3e8ff;color:#7c3aed;margin-left:4px">${step.candidates_count} candidates</span>`;
        if (step.produces_goal) extra += `<span class="tag" style="background:#dcfce7;color:#166534;margin-left:4px">GOAL</span>`;

        let top3 = '';
        if (step.top_3) {
            top3 = '<div style="margin-top:6px;font-size:11px;color:var(--text-muted)">' +
                step.top_3.map((c,i) => `${i===0?'&#x2B50;':'&bull;'} ${c.id} (U:${c.utility})${c.produces_goal?' [GOAL]':''}`).join(' &nbsp; ') +
                '</div>';
        }

        return `<div class="${cls}"><div class="trace-num">${step.step}</div><div class="trace-desc">${step.description}${extra}${top3}</div></div>`;
    }).join('');
}

function renderGraph(graphData, path) {
    const el = document.getElementById('algo-graph');
    if (!graphData || !graphData.nodes || graphData.nodes.length === 0) {
        el.innerHTML = '<p style="padding:16px;color:var(--text-muted)">No graph data available.</p>';
        return;
    }

    const nodes = graphData.nodes;
    const edges = graphData.edges;
    const pathSet = new Set(path);
    const W = 700, H = 350;
    const margin = 50;

    const startNode = nodes.find(n => n.type === 'start');
    const endNode = nodes.find(n => n.type === 'end');
    const serviceNodes = nodes.filter(n => n.type === 'service');

    const positions = {};
    if (startNode) positions[startNode.id] = { x: margin, y: H/2 };
    if (endNode) positions[endNode.id] = { x: W - margin, y: H/2 };

    const inPath = serviceNodes.filter(n => pathSet.has(n.id));
    const notInPath = serviceNodes.filter(n => !pathSet.has(n.id));

    inPath.forEach((n, i) => {
        const x = margin + (W - 2*margin) * ((i+1) / (inPath.length+1));
        positions[n.id] = { x, y: H/2 };
    });

    const maxShow = Math.min(notInPath.length, 20);
    notInPath.slice(0, maxShow).forEach((n, i) => {
        const col = Math.floor(i / 4);
        const row = i % 4;
        const x = margin + 80 + col * 80;
        const y = (row < 2 ? 40 + row * 50 : H - 40 - (row - 2) * 50);
        positions[n.id] = { x, y };
    });

    let svg = `<svg width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" xmlns="http://www.w3.org/2000/svg">`;
    svg += '<defs><marker id="arrowhead" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto"><polygon points="0 0, 8 3, 0 6" fill="#94a3b8"/></marker>';
    svg += '<marker id="arrowhead-active" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto"><polygon points="0 0, 8 3, 0 6" fill="#3b82f6"/></marker></defs>';

    edges.forEach(e => {
        if (!positions[e.from] || !positions[e.to]) return;
        const {x:x1, y:y1} = positions[e.from];
        const {x:x2, y:y2} = positions[e.to];
        const isActive = e.in_path || (pathSet.has(e.from) && pathSet.has(e.to)) || (e.from === 'START' && pathSet.has(e.to)) || (pathSet.has(e.from) && e.to === 'END');
        const color = isActive ? '#3b82f6' : '#e2e8f0';
        const width = isActive ? 2.5 : 1;
        const marker = isActive ? 'url(#arrowhead-active)' : 'url(#arrowhead)';
        svg += `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="${color}" stroke-width="${width}" marker-end="${marker}" opacity="${isActive?1:0.4}"/>`;
    });

    nodes.forEach(n => {
        if (!positions[n.id]) return;
        const {x, y} = positions[n.id];
        const inP = pathSet.has(n.id) || n.type === 'start' || n.type === 'end';
        if (n.type === 'start') {
            svg += `<circle cx="${x}" cy="${y}" r="18" fill="#1e3a5f" stroke="#0f1f33" stroke-width="2"/>`;
            svg += `<text x="${x}" y="${y+4}" text-anchor="middle" fill="white" font-size="10" font-weight="700">START</text>`;
        } else if (n.type === 'end') {
            svg += `<circle cx="${x}" cy="${y}" r="18" fill="#059669" stroke="#047857" stroke-width="2"/>`;
            svg += `<text x="${x}" y="${y+4}" text-anchor="middle" fill="white" font-size="10" font-weight="700">END</text>`;
        } else {
            const fill = inP ? '#3b82f6' : '#f1f5f9';
            const stroke = inP ? '#2563eb' : '#cbd5e1';
            const textCol = inP ? 'white' : '#64748b';
            const r = inP ? 16 : 12;
            svg += `<circle cx="${x}" cy="${y}" r="${r}" fill="${fill}" stroke="${stroke}" stroke-width="${inP?2:1}"/>`;
            const label = n.id.replace('service','S').substring(0,8);
            svg += `<text x="${x}" y="${y+3}" text-anchor="middle" fill="${textCol}" font-size="${inP?9:7}" font-weight="${inP?700:400}">${label}</text>`;
            if (inP && n.utility) {
                svg += `<text x="${x}" y="${y+r+12}" text-anchor="middle" fill="#3b82f6" font-size="9" font-weight="600">U:${n.utility}</text>`;
            }
        }
    });

    svg += '</svg>';
    el.innerHTML = svg;
}

function renderClassicResult(r) {
    const el = document.getElementById('classic-result');
    el.innerHTML = `
        <div class="result-box ${r.success?'result-success':'result-error'}">
            <strong>${r.success?'Composition Successful':'Composition Failed'}</strong>
            <div style="margin-top:8px;white-space:pre-line">${r.explanation}</div>
        </div>
        ${r.success ? `
        <div class="card-grid-4" style="margin-top:20px">
            <div class="kpi-box"><div class="kpi-label">Services Used</div><div class="kpi-value">${r.services.length}</div></div>
            <div class="kpi-box"><div class="kpi-label">Utility Score</div><div class="kpi-value">${r.utility_value.toFixed(2)}</div></div>
            <div class="kpi-box"><div class="kpi-label">Computation Time</div><div class="kpi-value">${(r.computation_time*1000).toFixed(0)}ms</div></div>
            <div class="kpi-box"><div class="kpi-label">States Explored</div><div class="kpi-value">${r.states_explored||'N/A'}</div></div>
        </div>
        <h4 style="margin:20px 0 12px;font-size:13px;font-weight:700;color:var(--primary)">Composition Workflow</h4>
        <div class="workflow">
            <div class="wf-node wf-start">START</div>
            ${r.workflow.map(sid => `<div class="wf-arrow">&rarr;</div><div class="wf-node wf-service">${sid}</div>`).join('')}
            <div class="wf-arrow">&rarr;</div>
            <div class="wf-node wf-end">END</div>
        </div>
        <h4 style="margin:20px 0 12px;font-size:13px;font-weight:700;color:var(--primary)">Achieved QoS</h4>
        <div class="qos-grid">
            ${Object.entries(r.qos_achieved).map(([k,v]) => `<div class="qos-item"><span class="qos-name">${k}</span><span class="qos-val">${typeof v==='number'?v.toFixed(2):v}</span></div>`).join('')}
        </div>
        ` : ''}
    `;
}

// ============================================================
// LLM COMPOSITION
// ============================================================
async function checkAnnotationForLLM() {
    try {
        const r = await fetch(`${API}/annotation/status`);
        if (!r.ok) return;
        const d = await r.json();
        const warn = document.getElementById('llm-warning');
        const btn = document.getElementById('llm-compose-btn');
        if (!d.services_annotated || d.annotation_count === 0) {
            warn.style.display = 'block';
            document.getElementById('llm-warning-detail').textContent = `${d.annotation_count}/${d.total_services} annotated.`;
            btn.disabled = true;
        } else {
            warn.style.display = 'none';
            btn.disabled = false;
        }
    } catch(e) { /* offline */ }
}

async function composeLLM() {
    try {
        const sr = await fetch(`${API}/annotation/status`);
        const sd = await sr.json();
        if (!sd.services_annotated) { showToast('Annotate services first (Tab 2).', 'warning'); return; }
    } catch(e) { return; }

    const reqId = document.getElementById('req-select-llm').value;
    if (!reqId) { showToast('Select a request first.', 'warning'); return; }

    document.getElementById('llm-reasoning-card').style.display = 'block';
    document.getElementById('llm-result-card').style.display = 'block';
    const llmBtn = document.getElementById('llm-compose-btn');
    btnLoading(llmBtn, '&#x1F916; Processing...');
    const reasonEl = document.getElementById('llm-reasoning');
    reasonEl.innerHTML = '<div class="trace-step explore"><div class="trace-num">1</div><div class="trace-desc">Initializing reasoning...</div></div>';
    document.getElementById('llm-result').innerHTML = '<div style="padding:20px;text-align:center"><div class="spinner"></div> Processing...</div>';

    const steps = [
        'Analyzing request context and QoS constraints',
        'Identifying priorities from training knowledge',
        'Searching candidate services in repository',
        'Evaluating annotations and social properties',
        'LLM inference: selecting optimal service',
        'Generating explainability report'
    ];
    let si = 0;
    const iv = setInterval(() => {
        if (si < steps.length) {
            let html = '';
            for (let j = 0; j <= si; j++) {
                html += `<div class="trace-step ${j<si?'goal':'explore'}"><div class="trace-num">${j+1}</div><div class="trace-desc">${steps[j]}</div></div>`;
            }
            reasonEl.innerHTML = html;
            si++;
        } else { clearInterval(iv); }
    }, 700);

    try {
        const r = await fetch(`${API}/compose/llm`, {
            method:'POST', headers:{'Content-Type':'application/json'},
            body: JSON.stringify({
                request_id: reqId,
                enable_reasoning: document.getElementById('enable-reasoning').checked,
                enable_adaptation: document.getElementById('enable-adaptation').checked
            })
        });
        const d = await r.json();
        clearInterval(iv);

        if (r.ok) {
            llmResults[reqId] = d;
            reasonEl.innerHTML += '<div class="trace-step complete"><div class="trace-num">&#x2713;</div><div class="trace-desc"><strong>Composition completed successfully</strong></div></div>';
            renderLLMResult(d);
            markTabDone(3);
            scrollToEl(document.getElementById('llm-result-card'));
        } else {
            reasonEl.innerHTML += `<div class="trace-step failed"><div class="trace-num">!</div><div class="trace-desc">${escapeHtml(d.error || d.message)}</div></div>`;
            document.getElementById('llm-result').innerHTML = `<div class="result-box result-error"><strong>Error:</strong> ${escapeHtml(d.error || d.message)}</div>`;
        }
        btnReset(llmBtn);
    } catch(e) {
        clearInterval(iv);
        document.getElementById('llm-result').innerHTML = `<div class="result-box result-error"><strong>Error:</strong> ${escapeHtml(e.message)}</div>`;
        btnReset(llmBtn);
    }
}

function renderLLMResult(r) {
    document.getElementById('llm-result').innerHTML = `
        <div class="result-box ${r.success?'result-success':'result-error'}">
            <strong>${r.success?'Intelligent Composition Successful':'Composition Failed'}</strong>
        </div>
        ${r.success ? `
        <div class="card-grid-4" style="margin-top:20px">
            <div class="kpi-box"><div class="kpi-label">Selected Service</div><div class="kpi-value" style="font-size:14px;font-family:Consolas,monospace">${r.services[0]}</div></div>
            <div class="kpi-box"><div class="kpi-label">Utility Score</div><div class="kpi-value">${r.utility_value.toFixed(2)}</div></div>
            <div class="kpi-box"><div class="kpi-label">Computation Time</div><div class="kpi-value">${(r.computation_time*1000).toFixed(0)}ms</div></div>
            <div class="kpi-box"><div class="kpi-label">Algorithm</div><div class="kpi-value" style="font-size:14px">LLM</div></div>
        </div>
        <div style="margin-top:20px;padding:20px;background:var(--surface-alt);border:1px solid var(--border);border-radius:var(--radius)">
            <h4 style="font-size:13px;font-weight:700;color:var(--primary);margin-bottom:10px">Explanation &amp; Justification</h4>
            <div style="font-size:13px;line-height:1.7;color:var(--text);white-space:pre-line">${r.explanation}</div>
        </div>
        <h4 style="margin:20px 0 12px;font-size:13px;font-weight:700;color:var(--primary)">Achieved QoS</h4>
        <div class="qos-grid">
            ${Object.entries(r.qos_achieved).map(([k,v]) => `<div class="qos-item"><span class="qos-name">${k}</span><span class="qos-val">${typeof v==='number'?v.toFixed(2):v}</span></div>`).join('')}
        </div>
        ` : `<div style="margin-top:12px;white-space:pre-line">${r.explanation}</div>`}
    `;
}

// ============================================================
// CHAT
// ============================================================
async function sendChat() {
    const input = document.getElementById('chat-input');
    const msg = input.value.trim();
    if (!msg) return;
    const box = document.getElementById('chat-box');
    if (box.querySelector('p[style]')) box.innerHTML = '';
    box.innerHTML += `<div class="chat-msg chat-user">${escapeHtml(msg)}</div>`;
    input.value = '';
    box.scrollTop = box.scrollHeight;
    try {
        const r = await fetch(`${API}/llm/chat`, {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:msg})});
        const d = await r.json();
        box.innerHTML += `<div class="chat-msg chat-bot">${escapeHtml(r.ok ? d.response : d.error)}</div>`;
    } catch(e) {
        box.innerHTML += `<div class="chat-msg chat-bot" style="color:var(--error)">Error: ${escapeHtml(e.message)}</div>`;
    }
    box.scrollTop = box.scrollHeight;
}

// ============================================================
// BEST SOLUTIONS
// ============================================================
async function uploadBestSolutions() {
    const fd = new FormData();
    fd.append('file', document.getElementById('best-sol-file').files[0]);
    try {
        const r = await fetch(`${API}/best-solutions/upload`, {method:'POST',body:fd});
        const d = await r.json();
        showToast(d.message, r.ok ? 'success' : 'error');
    } catch(e) { showToast(e.message, 'error'); }
}

// ============================================================
// COMPARATIVE ANALYSIS
// ============================================================
async function loadComparison() {
    if (!currentRequests.length) { showToast('Load composition requests first (Tab 3).', 'warning'); return; }

    const btn = document.querySelector('#tab-4 .btn-primary');
    const origText = btn.innerHTML;
    btn.innerHTML = '<span class="spinner" style="width:16px;height:16px;border-width:2px"></span> Running comparisons...';
    btn.disabled = true;

    try {
        if (currentServices.length > 0) {
            try {
                const batchResp = await fetch(`${API}/compose/batch`, {
                    method:'POST', headers:{'Content-Type':'application/json'},
                    body: JSON.stringify({ request_ids: currentRequests.map(r => r.id), algorithm: 'dijkstra' })
                });
                if (!batchResp.ok) console.warn('Batch composition returned error');
            } catch(e) {
                console.warn('Batch endpoint unavailable, falling back to sequential', e);
                for (const req of currentRequests) {
                    try {
                        await fetch(`${API}/compose/classic`, {
                            method:'POST', headers:{'Content-Type':'application/json'},
                            body: JSON.stringify({ request_id: req.id, algorithm: 'dijkstra' })
                        });
                    } catch(e2) { console.warn(e2); }
                    try {
                        await fetch(`${API}/compose/llm`, {
                            method:'POST', headers:{'Content-Type':'application/json'},
                            body: JSON.stringify({ request_id: req.id })
                        });
                    } catch(e2) { /* skip */ }
                }
            }
        }

        const r = await fetch(`${API}/comparison`);
        const d = await r.json();
        if (r.ok) {
            renderComparison(d);
            markTabDone(4);
            scrollToEl(document.getElementById('comparison-kpis'));
        } else { showToast(d.error, 'error'); }
    } catch(e) { showToast(e.message, 'error'); }
    finally {
        btn.innerHTML = origText;
        btn.disabled = false;
    }
}

function renderComparison(data) {
    const stats = data.statistics;

    document.getElementById('comparison-kpis').style.display = 'grid';
    document.getElementById('comparison-charts-card').style.display = 'block';
    document.getElementById('comparison-metrics-card').style.display = 'block';
    document.getElementById('comparison-table-card').style.display = 'block';
    document.getElementById('training-impact-card').style.display = 'block';

    document.getElementById('kpi-classic-utility').textContent = stats.classic.avg_utility.toFixed(2);
    document.getElementById('kpi-llm-utility').textContent = stats.llm.avg_utility.toFixed(2);
    const gap = stats.comparison.avg_utility_gap;
    document.getElementById('kpi-improvement').textContent = `${gap>=0?'+':''}${gap.toFixed(2)}`;
    document.getElementById('kpi-improvement').style.color = gap >= 0 ? 'var(--success)' : 'var(--error)';

    document.getElementById('metrics-classic').innerHTML = renderMetricList(stats.classic, 'classic');
    document.getElementById('metrics-llm').innerHTML = renderMetricList(stats.llm, 'llm');

    renderTrainingImpact(data.training_impact);
    renderComparisonTable(data.comparisons);
    renderCharts(data.comparisons, stats);

    // Analytical Discussion (Requirement 2c)
    if (data.discussion) {
        renderDiscussion(data.discussion);
    }
}

function renderMetricList(s, type) {
    return `
        <div class="qos-grid">
            <div class="qos-item"><span class="qos-name">Success Rate</span><span class="qos-val">${s.success_rate.toFixed(1)}%</span></div>
            <div class="qos-item"><span class="qos-name">Avg Utility</span><span class="qos-val">${s.avg_utility.toFixed(2)}</span></div>
            <div class="qos-item"><span class="qos-name">Max Utility</span><span class="qos-val">${s.max_utility.toFixed(2)}</span></div>
            <div class="qos-item"><span class="qos-name">Avg Time</span><span class="qos-val">${(s.avg_time*1000).toFixed(0)}ms</span></div>
            <div class="qos-item"><span class="qos-name">Composed</span><span class="qos-val">${s.total_composed}</span></div>
            <div class="qos-item"><span class="qos-name">Avg Services</span><span class="qos-val">${s.avg_services_used?.toFixed(1)||'N/A'}</span></div>
            ${type==='classic' ? `<div class="qos-item"><span class="qos-name">Avg States</span><span class="qos-val">${(s.avg_states_explored||0).toFixed(0)}</span></div>` : ''}
        </div>
    `;
}

function renderTrainingImpact(ti) {
    const el = document.getElementById('training-impact-content');
    if (ti.is_trained) {
        el.innerHTML = `
            <div class="result-box result-success"><strong>LLM is trained</strong> with ${ti.training_examples} examples.</div>
            <div class="card-grid-4" style="margin-top:16px">
                <div class="kpi-box"><div class="kpi-label">Training Examples</div><div class="kpi-value">${ti.training_examples}</div></div>
                <div class="kpi-box"><div class="kpi-label">Compositions Done</div><div class="kpi-value">${ti.performance_metrics.total_compositions}</div></div>
                <div class="kpi-box"><div class="kpi-label">Success Rate</div><div class="kpi-value">${ti.performance_metrics.total_compositions>0?(ti.performance_metrics.successful_compositions/ti.performance_metrics.total_compositions*100).toFixed(1):'0'}%</div></div>
                <div class="kpi-box"><div class="kpi-label">Avg Utility</div><div class="kpi-value">${ti.performance_metrics.average_utility.toFixed(2)}</div></div>
            </div>
            <div class="info-box info" style="margin-top:16px">
                Training provides the LLM with ${ti.training_examples} example compositions to learn from. The LLM uses few-shot learning and pattern matching from these examples to make better selection decisions. The composition history (${ti.composition_history} records) enables continuous improvement.
            </div>
        `;
    } else {
        el.innerHTML = `
            <div class="result-box result-warning"><strong>LLM is not trained.</strong> Training data improves LLM composition quality through few-shot learning and pattern recognition. Upload training data in Tab 1 for better results.</div>
        `;
    }
}

function renderComparisonTable(comparisons) {
    const tbody = document.getElementById('comparison-tbody');
    tbody.innerHTML = comparisons.map(c => {
        const bestU = c.best_known?.utility || 0;
        const cU = c.classic?.utility_value || 0;
        const cT = c.classic?.computation_time || 0;
        const lU = c.llm?.utility_value || 0;
        const lT = c.llm?.computation_time || 0;

        let winner = '<span class="badge badge-primary">--</span>';
        if (c.classic?.success && c.llm?.success) {
            winner = cU > lU ? '<span class="badge badge-warning">Classic</span>' : (lU > cU ? '<span class="badge badge-success">LLM</span>' : '<span class="badge badge-primary">Tie</span>');
        } else if (c.classic?.success) {
            winner = '<span class="badge badge-warning">Classic</span>';
        } else if (c.llm?.success) {
            winner = '<span class="badge badge-success">LLM</span>';
        }

        return `<tr>
            <td style="font-family:Consolas,monospace;font-size:12px">${c.request_id}</td>
            <td>${bestU?bestU.toFixed(2):'--'}</td>
            <td>${c.classic?.success?cU.toFixed(2):'--'}</td>
            <td>${c.classic?.success?(cT*1000).toFixed(0)+'ms':'--'}</td>
            <td>${c.llm?.success?lU.toFixed(2):'--'}</td>
            <td>${c.llm?.success?(lT*1000).toFixed(0)+'ms':'--'}</td>
            <td>${winner}</td>
        </tr>`;
    }).join('');
}

function renderCharts(comparisons, stats) {
    const labels = comparisons.filter(c => c.classic?.success || c.llm?.success).map(c => c.request_id).slice(0,20);
    const classicUtils = labels.map(id => { const c = comparisons.find(x=>x.request_id===id); return c?.classic?.utility_value || 0; });
    const llmUtils = labels.map(id => { const c = comparisons.find(x=>x.request_id===id); return c?.llm?.utility_value || 0; });
    const classicTimes = labels.map(id => { const c = comparisons.find(x=>x.request_id===id); return (c?.classic?.computation_time || 0)*1000; });
    const llmTimes = labels.map(id => { const c = comparisons.find(x=>x.request_id===id); return (c?.llm?.computation_time || 0)*1000; });

    if (utilityChart) utilityChart.destroy();
    if (timeChart) timeChart.destroy();

    utilityChart = new Chart(document.getElementById('chart-utility'), {
        type: 'bar',
        data: {
            labels: labels.map(l => l.length > 12 ? l.substring(0,12)+'...' : l),
            datasets: [
                { label: 'Classic (A)', data: classicUtils, backgroundColor: 'rgba(30,58,95,0.8)', borderRadius: 4 },
                { label: 'LLM (B)', data: llmUtils, backgroundColor: 'rgba(59,130,246,0.8)', borderRadius: 4 }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { position: 'top' } },
            scales: { y: { beginAtZero: true, title: { display: true, text: 'Utility' } } }
        }
    });

    timeChart = new Chart(document.getElementById('chart-time'), {
        type: 'bar',
        data: {
            labels: labels.map(l => l.length > 12 ? l.substring(0,12)+'...' : l),
            datasets: [
                { label: 'Classic (A)', data: classicTimes, backgroundColor: 'rgba(30,58,95,0.8)', borderRadius: 4 },
                { label: 'LLM (B)', data: llmTimes, backgroundColor: 'rgba(59,130,246,0.8)', borderRadius: 4 }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { position: 'top' } },
            scales: { y: { beginAtZero: true, title: { display: true, text: 'Time (ms)' } } }
        }
    });
}

// ============================================================
// DISCUSSION RENDERER (Requirement 2c)
// ============================================================
function renderDiscussion(discussion) {
    const card = document.getElementById('discussion-card');
    const content = document.getElementById('discussion-content');
    const summaryEl = document.getElementById('discussion-summary');
    card.style.display = 'block';

    let html = '';
    (discussion.sections || []).forEach((section, idx) => {
        html += `<div class="discussion-section">`;
        html += `<h4 class="discussion-heading"><span class="discussion-num">${idx + 1}</span>${escapeHtml(section.title)}</h4>`;
        (section.paragraphs || []).forEach(p => {
            html += `<p class="discussion-paragraph">${escapeHtml(p)}</p>`;
        });
        html += `</div>`;
    });
    content.innerHTML = html;

    if (discussion.summary) {
        summaryEl.style.display = 'block';
        summaryEl.innerHTML = `<span style="font-size:18px;margin-right:8px">&#x1F3C6;</span> ${escapeHtml(discussion.summary)}`;
    }
}

// ============================================================
// DRAG-AND-DROP SUPPORT
// ============================================================
function setupDragDrop() {
    document.querySelectorAll('.upload-area').forEach(area => {
        const fileInput = area.querySelector('input[type="file"]');
        if (!fileInput) return;

        area.addEventListener('dragover', e => {
            e.preventDefault();
            area.classList.add('drag-over');
        });
        area.addEventListener('dragleave', e => {
            e.preventDefault();
            area.classList.remove('drag-over');
        });
        area.addEventListener('drop', e => {
            e.preventDefault();
            area.classList.remove('drag-over');
            if (e.dataTransfer.files.length) {
                fileInput.files = e.dataTransfer.files;
                fileInput.dispatchEvent(new Event('change'));
            }
        });
    });
}

// ============================================================
// SERVICE SEARCH/FILTER
// ============================================================
function filterServices() {
    const query = (document.getElementById('service-search-input')?.value || '').toLowerCase().trim();
    const countEl = document.getElementById('service-search-count');
    if (!currentServices.length) return;

    if (!query) {
        displayServices(currentServices);
        if (countEl) countEl.textContent = '';
        return;
    }

    const filtered = currentServices.filter(s =>
        s.id.toLowerCase().includes(query) ||
        s.inputs.some(inp => inp.toLowerCase().includes(query)) ||
        s.outputs.some(out => out.toLowerCase().includes(query))
    );
    displayServices(filtered);
    if (countEl) countEl.textContent = `${filtered.length} / ${currentServices.length}`;
}

// ============================================================
// INITIALIZATION
// ============================================================
async function init() {
    try {
        const r = await fetch(`${API}/health`);
        if (r.ok) {
            const d = await r.json();
            document.getElementById('hdr-server-dot').classList.remove('inactive');
            document.getElementById('hdr-server-text').textContent = 'Online';
            if (d.services_loaded > 0) {
                document.getElementById('hdr-svc-count').textContent = `${d.services_loaded} services`;
                // Restore services from backend so all tabs have access
                try {
                    const sr = await fetch(`${API}/services`);
                    if (sr.ok) {
                        const sd = await sr.json();
                        currentServices = sd.services || [];
                        selectedServiceIds = new Set(currentServices.map(s => s.id));
                        document.getElementById('service-count').innerHTML = `Services loaded: <span style="font-size:20px;color:var(--success)">${currentServices.length}</span>`;
                        displayServices(currentServices);
                        markTabDone(0);
                    }
                } catch(e) { /* services fetch failed, not critical */ }
            }
            if (d.is_trained) {
                updateTrainingBadge(true, d.training_examples);
            }
        }
    } catch(e) {
        document.getElementById('hdr-server-dot').classList.add('inactive');
        document.getElementById('hdr-server-text').textContent = 'Offline';
    }
    loadMetrics();
    setupDragDrop();
}

init();
setInterval(loadMetrics, 30000);
