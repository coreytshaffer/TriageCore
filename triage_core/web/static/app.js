document.addEventListener('DOMContentLoaded', () => {
    const authForm = document.getElementById('auth-form');
    const authPanel = document.getElementById('auth-panel');
    const authError = document.getElementById('auth-error');
    const tokenInput = document.getElementById('mobile-token');
    const ledgerPanel = document.getElementById('ledger-panel');
    const connectionStatus = document.getElementById('connection-status');
    const modal = document.getElementById('review-modal');
    const btnClose = document.getElementById('close-modal');
    const reviewForm = document.getElementById('review-form');
    const decisionInput = document.getElementById('review-decision');
    const workloadInput = document.getElementById('review-workload');
    const btnSubmit = document.getElementById('submit-review');
    const reviewFeedback = document.getElementById('review-feedback');
    const reviewError = document.getElementById('review-error');
    const retryIds = new Map();

    let apiToken = '';
    let currentTask = null;
    let modalOpener = null;

    function showAuthentication(message = '') {
        apiToken = '';
        authError.textContent = message;
        connectionStatus.textContent = 'Not connected';
        authPanel.classList.remove('hidden');
        ledgerPanel.classList.add('hidden');
        closeModal();
        tokenInput.focus();
    }

    async function apiFetch(url, options = {}) {
        const headers = new Headers(options.headers || {});
        headers.set('Authorization', `Bearer ${apiToken}`);

        const response = await fetch(url, { ...options, headers });
        if (response.status === 401 || (response.status === 503 && url === '/api/tasks')) {
            showAuthentication('Authentication failed. Check the host token.');
        }
        return response;
    }

    function openModal(task) {
        if (currentTask || btnSubmit.disabled) return;
        currentTask = task;
        modalOpener = document.activeElement;
        document.getElementById('modal-task-title').textContent =
            `Task ${task.task_id.substring(0, 8)}`;
        document.getElementById('modal-task-runner').textContent = task.runner || 'unknown';
        document.getElementById('modal-task-status').textContent = task.status || 'unknown';
        document.getElementById('modal-review-status').textContent = reviewLabel(task);
        reviewForm.reset();
        reviewError.textContent = '';

        modal.classList.remove('hidden');
        ledgerPanel.inert = true;
        decisionInput.focus();
    }

    function closeModal() {
        modal.classList.add('hidden');
        currentTask = null;
        ledgerPanel.inert = false;
        modalOpener?.focus();
        modalOpener = null;
    }

    btnClose.addEventListener('click', closeModal);
    modal.addEventListener('keydown', event => {
        if (event.key === 'Escape' && !btnSubmit.disabled) closeModal();
        if (event.key !== 'Tab') return;
        if (btnSubmit.disabled) {
            event.preventDefault();
        } else if (event.shiftKey && document.activeElement === btnClose) {
            event.preventDefault();
            btnSubmit.focus();
        } else if (!event.shiftKey && document.activeElement === btnSubmit) {
            event.preventDefault();
            btnClose.focus();
        }
    });

    function reviewLabel(task) {
        const labels = {
            pending: 'Pending local confirmation',
            no_decision: 'No current decision',
            unpaired: 'No local review pairing',
            unavailable: 'Verification unavailable',
            evidence_changed: 'Evidence changed'
        };
        let label = labels[task.review_status] || 'Verification unavailable';
        if (task.review_status === 'verified' && task.review_decision) {
            label = `Verified: ${task.review_decision.replaceAll('_', ' ')}`;
        } else if (['unavailable', 'evidence_changed'].includes(task.review_status) && task.review_reason) {
            label += ` · ${task.review_reason.replaceAll('_', ' ')}`;
        }
        if (task.review_pending_count > 0 && task.review_status !== 'pending') {
            label += ` · ${task.review_pending_count} pending local requests`;
        }
        return label;
    }

    reviewForm.addEventListener('submit', async event => {
        event.preventDefault();
        if (!currentTask || btnSubmit.disabled) return;
        const taskId = currentTask.task_id;
        const decision = decisionInput.value;
        const workload = workloadInput.value === 'not_recorded' ? null : workloadInput.value;
        const retryKey = JSON.stringify([taskId, decision, workload]);
        modal.focus();
        btnSubmit.disabled = true;
        btnClose.disabled = true;
        decisionInput.disabled = true;
        workloadInput.disabled = true;
        reviewError.textContent = '';

        try {
            if (!retryIds.has(retryKey)) {
                const randomBytes = crypto.getRandomValues(new Uint8Array(16));
                const requestId = Array.from(randomBytes, byte => byte.toString(16).padStart(2, '0')).join('');
                retryIds.set(retryKey, requestId);
            }
            const body = { decision, request_id: retryIds.get(retryKey) };
            if (workload) body.workload = workload;
            const response = await apiFetch(`/api/tasks/${encodeURIComponent(taskId)}/review`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body)
            });
            if (![200, 202].includes(response.status)) {
                if ([404, 409, 422].includes(response.status)) retryIds.delete(retryKey);
                throw new Error('Review request unsuccessful');
            }
            const result = await response.json();
            const messages = {
                pending: 'pending local confirmation',
                committed: 'request already confirmed locally',
                cancelled: 'request was cancelled',
                expired: 'request expired'
            };
            if (!Object.hasOwn(messages, result.status) || typeof result.intent_id !== 'string' || !result.intent_id) {
                throw new Error('Unexpected review response');
            }
            retryIds.delete(retryKey);
            closeModal();
            reviewFeedback.textContent = `Task ${taskId.substring(0, 8)}: ${messages[result.status]}.`;
            reviewFeedback.focus();
            await loadTasks();
        } catch {
            reviewError.textContent = 'Review request could not be submitted. Try again.';
        } finally {
            btnSubmit.disabled = false;
            btnClose.disabled = false;
            decisionInput.disabled = false;
            workloadInput.disabled = false;
            if (currentTask) btnSubmit.focus();
        }
    });

    async function loadTasks() {
        try {
            const response = await apiFetch('/api/tasks');
            if (!response.ok) {
                throw new Error(`Task load failed with status ${response.status}`);
            }

            const data = await response.json();
            const list = document.getElementById('task-list');
            list.replaceChildren();

            data.tasks.forEach(task => {
                const card = document.createElement('button');
                const title = document.createElement('h3');
                const status = document.createElement('span');
                const review = document.createElement('span');

                card.className = 'task-card';
                card.type = 'button';
                title.textContent = `Task ${task.task_id.substring(0, 8)}`;
                status.className = 'badge';
                status.textContent = task.status || 'unknown';
                review.className = 'badge';
                review.textContent = reviewLabel(task);
                card.append(title, status, review);
                card.addEventListener('click', () => openModal(task));
                list.appendChild(card);
            });

            authError.textContent = '';
            authPanel.classList.add('hidden');
            ledgerPanel.classList.remove('hidden');
            connectionStatus.textContent = 'Connected';
        } catch (e) {
            if (apiToken) {
                document.getElementById('task-list').textContent =
                    'Failed to load tasks.';
            }
        }
    }

    authForm.addEventListener('submit', async event => {
        event.preventDefault();
        const suppliedToken = tokenInput.value.trim();
        tokenInput.value = '';
        if (!suppliedToken) {
            showAuthentication('A mobile token is required.');
            return;
        }

        apiToken = suppliedToken;
        connectionStatus.textContent = 'Connecting...';
        await loadTasks();
    });
});
