// Simple health check for the backend
fetch('http://localhost:8000/')
    .then(() => {
        const statusEl = document.getElementById('backend-status');
        if (statusEl) {
            statusEl.innerText = "Connected ⚡";
            statusEl.style.color = "#38bdf8";
        }
    })
    .catch(() => {
        const statusEl = document.getElementById('backend-status');
        if (statusEl) {
            statusEl.innerText = "Disconnected ❌";
            statusEl.style.color = "#ef4444";
        }
    });
