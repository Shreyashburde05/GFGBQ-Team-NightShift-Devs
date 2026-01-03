```javascript
console.log("TrustGuard AI Content Script Loaded");

// Inject Custom Styles for the Modal and Button
const style = document.createElement('style');
style.textContent = `
    .tg - verify - btn {
    position: absolute;
    display: none;
    z - index: 2147483647;
    background: #0f172a;
    color: white;
    border: 1px solid #38bdf8;
    border - radius: 6px;
    padding: 6px 12px;
    cursor: pointer;
    font - family: 'Inter', system - ui, sans - serif;
    font - size: 13px;
    font - weight: 500;
    box - shadow: 0 4px 6px - 1px rgba(0, 0, 0, 0.1), 0 2px 4px - 1px rgba(0, 0, 0, 0.06);
    transition: all 0.2s;
    backdrop - filter: blur(8px);
}
    .tg - verify - btn:hover {
    background: #1e293b;
    transform: translateY(-1px);
    box - shadow: 0 10px 15px - 3px rgba(0, 0, 0, 0.1);
}
    
    .tg - modal - overlay {
    position: fixed;
    top: 0;
    left: 0;
    width: 100 %;
    height: 100 %;
    background: rgba(15, 23, 42, 0.6);
    backdrop - filter: blur(4px);
    z - index: 2147483646;
    display: flex;
    justify - content: center;
    align - items: center;
    opacity: 0;
    transition: opacity 0.3s;
}
    
    .tg - modal {
    background: #0f172a;
    border: 1px solid #334155;
    border - radius: 12px;
    width: 90 %;
    max - width: 500px;
    max - height: 80vh;
    overflow - y: auto;
    color: #f8fafc;
    font - family: 'Inter', system - ui, sans - serif;
    box - shadow: 0 20px 25px - 5px rgba(0, 0, 0, 0.1), 0 10px 10px - 5px rgba(0, 0, 0, 0.04);
    transform: scale(0.95);
    transition: transform 0.3s;
}
    
    .tg - modal - header {
    padding: 16px;
    border - bottom: 1px solid #1e293b;
    display: flex;
    justify - content: space - between;
    align - items: center;
    background: #1e293b;
    border - radius: 12px 12px 0 0;
}
    
    .tg - modal - title {
    font - weight: 600;
    font - size: 16px;
    color: #f8fafc;
    display: flex;
    align - items: center;
    gap: 8px;
}
    
    .tg - close - btn {
    background: none;
    border: none;
    color: #94a3b8;
    cursor: pointer;
    padding: 4px;
    border - radius: 4px;
    transition: color 0.2s;
}
    .tg - close - btn:hover { color: #f8fafc; background: #334155; }
    
    .tg - modal - body {
    padding: 16px;
}

    .tg - claim - card {
    background: #1e293b;
    border: 1px solid #334155;
    border - radius: 8px;
    padding: 12px;
    margin - bottom: 12px;
}
    
    .tg - status {
    display: inline - block;
    padding: 2px 8px;
    border - radius: 12px;
    font - size: 11px;
    font - weight: 600;
    text - transform: uppercase;
    margin - bottom: 8px;
}
    
    .tg - status - verified { background: rgba(34, 197, 94, 0.1); color: #4ade80; border: 1px solid rgba(34, 197, 94, 0.2); }
    .tg - status - misleading { background: rgba(234, 179, 8, 0.1); color: #facc15; border: 1px solid rgba(234, 179, 8, 0.2); }
    .tg - status - hallucination { background: rgba(239, 68, 68, 0.1); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.2); }
    .tg - status - unverifiable { background: rgba(148, 163, 184, 0.1); color: #cbd5e1; border: 1px solid rgba(148, 163, 184, 0.2); }

    .tg - claim - text {
    font - size: 14px;
    line - height: 1.5;
    margin - bottom: 8px;
    color: #e2e8f0;
}

    .tg - source - link {
    font - size: 12px;
    color: #38bdf8;
    text - decoration: none;
    display: block;
    margin - top: 5px;
    overflow: hidden;
    text - overflow: ellipsis;
    white - space: nowrap;
}
    
    .tg - source - link:hover { text - decoration: underline; }
`;
document.head.appendChild(style);

// Create Floating Button
const verifyBtn = document.createElement("button");
verifyBtn.className = "tg-verify-btn";
verifyBtn.innerHTML = `
    < span style = "font-size: 14px; vertical-align: middle;" >🛡️</span >
        <span style="vertical-align: middle;">Verify with AI</span>
`;
document.body.appendChild(verifyBtn);

// Setup Modal Container (Hidden by default)
const modalOverlay = document.createElement("div");
modalOverlay.className = "tg-modal-overlay";
modalOverlay.innerHTML = `
    < div class="tg-modal" >
        <div class="tg-modal-header">
            <div class="tg-modal-title">
                <span>🛡️</span> TrustGuard Analysis
            </div>
            <button class="tg-close-btn">✕</button>
        </div>
        <div class="tg-modal-body" id="tg-results-container">
            <!-- Results will be injected here -->
            <div style="text-align: center; color: #94a3b8; padding: 20px;">
                Analyzing content...
            </div>
        </div>
    </div >
    `;
document.body.appendChild(modalOverlay);

// Close Modal Logic
modalOverlay.querySelector('.tg-close-btn').addEventListener('click', () => {
    modalOverlay.style.opacity = '0';
    setTimeout(() => { modalOverlay.style.display = 'none'; }, 300);
});

let selectedText = "";

document.addEventListener("mouseup", (e) => {
    const selection = window.getSelection();
    selectedText = selection.toString().trim();

    if (selectedText.length > 5) {
        const range = selection.getRangeAt(0);
        const rect = range.getBoundingClientRect();
        
        verifyBtn.style.top = `${ window.scrollY + rect.bottom + 8 } px`;
        verifyBtn.style.left = `${ window.scrollX + rect.left } px`;
        verifyBtn.style.display = "block";
    } else {
        // Only hide if we aren't clicking the button itself
        // (Handled by mousedown check usually, but kept simple here)
    }
});

document.addEventListener("mousedown", (e) => {
    if (e.target !== verifyBtn && !verifyBtn.contains(e.target)) {
        verifyBtn.style.display = "none";
    }
    if (e.target === modalOverlay) {
        modalOverlay.style.opacity = '0';
        setTimeout(() => { modalOverlay.style.display = 'none'; }, 300);
    }
});

verifyBtn.addEventListener("click", async () => {
    // Show Modal immediately in Loading State
    modalOverlay.style.display = 'flex';
    // Force reflow
    modalOverlay.offsetHeight;
    modalOverlay.style.opacity = '1';
    
    const resultsContainer = document.getElementById('tg-results-container');
    resultsContainer.innerHTML = `
    < div style = "text-align: center; padding: 30px;" >
            <div style="display: inline-block; width: 24px; height: 24px; border: 3px solid rgba(56, 189, 248, 0.3); border-radius: 50%; border-top-color: #38bdf8; animation: spin 1s linear infinite;"></div>
            <p style="margin-top: 10px; color: #94a3b8; font-size: 13px;">Agents extracting claims & verifying sources...</p>
        </div >
    <style>@keyframes spin {to {transform: rotate(360deg); } }</style>
`;

    try {
        const response = await fetch("http://localhost:8000/api/verify", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ text: selectedText })
        });
        
        const data = await response.json();
        
        if (data.length === 0) {
            resultsContainer.innerHTML = `< p style = "text-align:center; color:#94a3b8;" > No verifiable claims found in selected text.</p > `;
            return;
        }

        let html = '';
        data.forEach(item => {
            const statusClass = `tg - status - ${ item.status.toLowerCase() } `;
            html += `
    < div class="tg-claim-card" >
                    <div class="tg-status ${statusClass}">${item.status.replace('_', ' ')}</div>
                    <div class="tg-claim-text">"${item.claim}"</div>
                    ${ item.reasoning ? `<div style="font-size: 12px; color: #94a3b8; margin-top: 4px;">Why: ${item.reasoning}</div>` : '' }
                    ${ item.source ? `<a href="${item.source.match(/URL: (.*)\)$/) ? item.source.match(/URL: (.*)\)$/)[1] : '#'}" target="_blank" class="tg-source-link">🔗 Source: ${item.source}</a>` : '' }
                </div >
    `;
        });
        resultsContainer.innerHTML = html;

    } catch (error) {
        resultsContainer.innerHTML = `
    < div style = "text-align: center; color: #f87171; padding: 20px;" >
                <p><strong>Connection Failed</strong></p>
                <p style="font-size: 12px; margin-top: 5px;">Is the local backend running on port 8000?</p>
            </div >
    `;
    }
    
    verifyBtn.style.display = "none";
});
```
