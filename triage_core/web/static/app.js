document.addEventListener('DOMContentLoaded', () => {
    // TABS
    const tabBtns = document.querySelectorAll('.tab-btn');
    const tabPanes = document.querySelectorAll('.tab-pane');
    
    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            tabBtns.forEach(b => b.classList.remove('active'));
            tabPanes.forEach(p => p.classList.remove('active'));
            
            btn.classList.add('active');
            document.getElementById(`${btn.dataset.tab}-tab`).classList.add('active');
            
            if (btn.dataset.tab === 'logs') loadLogs();
        });
    });

    // MODAL
    const modal = document.getElementById('review-modal');
    const btnClose = document.getElementById('close-modal');
    const btnReject = document.getElementById('btn-reject');
    const btnAccept = document.getElementById('btn-accept');
    
    let currentTask = null;

    function openModal(task) {
        currentTask = task;
        document.getElementById('modal-task-title').textContent = task.title || task.task_id.substring(0,8);
        document.getElementById('modal-task-desc').textContent = task.description || '';
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
            await fetch(`/api/tasks/${currentTask.task_id}/review`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ decision, workload })
            });
            closeModal();
            loadTasks();
        } catch (e) {
            alert('Failed to submit review');
        }
    }

    btnReject.addEventListener('click', () => submitReview('rejected'));
    btnAccept.addEventListener('click', () => submitReview('accepted'));

    // TASKS
    async function loadTasks() {
        try {
            const res = await fetch('/api/tasks');
            const data = await res.json();
            const list = document.getElementById('task-list');
            list.innerHTML = '';
            
            data.tasks.forEach(task => {
                const card = document.createElement('div');
                card.className = 'task-card';
                card.innerHTML = `
                    <h3>${task.title || task.task_id.substring(0,8)}</h3>
                    <p>${task.description || ''}</p>
                    <div><span class="badge">${task.status}</span></div>
                `;
                card.addEventListener('click', () => openModal(task));
                list.appendChild(card);
            });
        } catch (e) {
            document.getElementById('task-list').innerHTML = 'Failed to load tasks.';
        }
    }

    // LOGS
    async function loadLogs() {
        try {
            const res = await fetch('/api/logs');
            const data = await res.json();
            const consoleEl = document.getElementById('log-console');
            consoleEl.innerHTML = data.logs.join('');
            consoleEl.scrollTop = consoleEl.scrollHeight;
        } catch (e) {
            document.getElementById('log-console').innerHTML = 'Failed to load logs.';
        }
    }

    document.getElementById('refresh-logs').addEventListener('click', loadLogs);

    // INIT
    loadTasks();
});
