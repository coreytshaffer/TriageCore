document.addEventListener('DOMContentLoaded', () => {
    const authForm = document.getElementById('auth-form');
    const authPanel = document.getElementById('auth-panel');
    const authError = document.getElementById('auth-error');
    const tokenInput = document.getElementById('mobile-token');
    const ledgerPanel = document.getElementById('ledger-panel');
    const connectionStatus = document.getElementById('connection-status');
    const modal = document.getElementById('review-modal');
    const btnClose = document.getElementById('close-modal');
    const btnReject = document.getElementById('btn-reject');
    const btnAccept = document.getElementById('btn-accept');

    let apiToken = '';
    let currentTask = null;

    function showAuthentication(message = '') {
        apiToken = '';
        authError.textContent = message;
        connectionStatus.textContent = 'Not connected';
        authPanel.classList.remove('hidden');
        ledgerPanel.classList.add('hidden');
        tokenInput.focus();
    }

    async function apiFetch(url, options = {}) {
        const headers = new Headers(options.headers || {});
        headers.set('Authorization', `Bearer ${apiToken}`);

        const response = await fetch(url, { ...options, headers });
        if (response.status === 401 || response.status === 503) {
            showAuthentication('Authentication failed. Check the host token.');
        }
        return response;
    }

    function openModal(task) {
        currentTask = task;
        document.getElementById('modal-task-title').textContent =
            `Task ${task.task_id.substring(0, 8)}`;
        document.getElementById('modal-task-runner').textContent = task.runner || 'unknown';
        document.getElementById('modal-task-status').textContent = task.status || 'unknown';
        document.getElementById('review-workload').value = 'not_recorded';

        modal.classList.remove('hidden');
    }

    function closeModal() {
        modal.classList.add('hidden');
        currentTask = null;
    }

    btnClose.addEventListener('click', closeModal);

    async function submitReview(decision) {
        if (!currentTask) return;
        const workload = document.getElementById('review-workload').value;

        try {
            const response = await apiFetch(`/api/tasks/${currentTask.task_id}/review`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ decision, workload })
            });
            if (!response.ok) {
                throw new Error(`Review failed with status ${response.status}`);
            }
            closeModal();
            await loadTasks();
        } catch (e) {
            alert('Failed to submit review');
        }
    }

    btnReject.addEventListener('click', () => submitReview('rejected'));
    btnAccept.addEventListener('click', () => submitReview('accepted'));

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
                const card = document.createElement('div');
                const title = document.createElement('h3');
                const status = document.createElement('span');
                const metadata = document.createElement('div');

                card.className = 'task-card';
                title.textContent = `Task ${task.task_id.substring(0, 8)}`;
                status.className = 'badge';
                status.textContent = task.status || 'unknown';
                metadata.appendChild(status);
                card.appendChild(title);
                card.appendChild(metadata);
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
