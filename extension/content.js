/**
 * TrustGuard AI - Content Script
 * Handles text selection, UI injection, and communication with background script.
 */

(function() {
    console.log("TrustGuard AI: Content Script Initialized");

    // 1. Inject Styles
    if (!document.getElementById('tg-styles')) {
        const style = document.createElement('style');
        style.id = 'tg-styles';
        style.textContent = `
            .tg-verify-btn {
                position: absolute;
                display: none;
                z-index: 2147483647;
                background: #0f172a;
                color: white;
                border: 1px solid #38bdf8;
                border-radius: 6px;
                padding: 8px 14px;
                cursor: pointer;
                font-family: system-ui, -apple-system, sans-serif;
                font-size: 13px;
                font-weight: 600;
                box-shadow: 0 4px 12px rgba(0,0,0,0.3);
                transition: transform 0.2s, background 0.2s;
                line-height: 1;
            }
            .tg-verify-btn:hover {
                background: #1e293b;
                transform: scale(1.05);
            }
            .tg-modal-overlay {
                position: fixed;
                top: 0; left: 0; width: 100%; height: 100%;
                background: rgba(0,0,0,0.7);
                backdrop-filter: blur(4px);
                z-index: 2147483646;
                display: none;
                justify-content: center;
                align-items: center;
                opacity: 0;
                transition: opacity 0.3s;
            }
            .tg-modal {
                background: #0f172a;
                border: 1px solid #334155;
                border-radius: 12px;
                width: 90%;
                max-width: 450px;
                max-height: 80vh;
                overflow-y: auto;
                color: #f8fafc;
                font-family: system-ui, sans-serif;
                box-shadow: 0 20px 25px -5px rgba(0,0,0,0.5);
            }
            .tg-modal-header {
                padding: 16px;
                border-bottom: 1px solid #1e293b;
                display: flex;
                justify-content: space-between;
                align-items: center;
                background: #1e293b;
            }
            .tg-close-btn {
                background: none; border: none; color: #94a3b8;
                cursor: pointer; font-size: 20px;
            }
            .tg-modal-body { padding: 20px; }
            .tg-claim-card {
                background: #1e293b;
                border: 1px solid #334155;
                border-radius: 8px;
                padding: 12px;
                margin-bottom: 12px;
            }
            .tg-status {
                display: inline-block;
                padding: 2px 8px;
                border-radius: 10px;
                font-size: 10px;
                font-weight: 700;
                text-transform: uppercase;
                margin-bottom: 8px;
            }
            .tg-status-verified { background: #064e3b; color: #34d399; }
            .tg-status-uncertain { background: #451a03; color: #fbbf24; }
            .tg-status-hallucinated { background: #450a0a; color: #f87171; }
            .tg-spinner {
                width: 30px; height: 30px;
                border: 3px solid rgba(56, 189, 248, 0.2);
                border-top-color: #38bdf8;
                border-radius: 50%;
                animation: tg-spin 0.8s linear infinite;
                margin: 20px auto;
            }
            @keyframes tg-spin { to { transform: rotate(360deg); } }
        `;
        document.head.appendChild(style);
    }

    // 2. Create UI Elements
    const verifyBtn = document.createElement("button");
    verifyBtn.className = "tg-verify-btn";
    verifyBtn.textContent = "🛡️ Verify with TrustGuard";
    document.body.appendChild(verifyBtn);

    const modalOverlay = document.createElement("div");
    modalOverlay.className = "tg-modal-overlay";
    
    const modal = document.createElement("div");
    modal.className = "tg-modal";
    
    const header = document.createElement("div");
    header.className = "tg-modal-header";
    
    const title = document.createElement("div");
    title.style.cssText = "font-weight:bold; display:flex; align-items:center; gap:8px;";
    title.textContent = "🛡️ TrustGuard Analysis";
    
    const closeBtn = document.createElement("button");
    closeBtn.className = "tg-close-btn";
    closeBtn.textContent = "✕";
    
    header.appendChild(title);
    header.appendChild(closeBtn);
    
    const resultsContainer = document.createElement("div");
    resultsContainer.className = "tg-modal-body";
    resultsContainer.id = "tg-results";
    
    modal.appendChild(header);
    modal.appendChild(resultsContainer);
    modalOverlay.appendChild(modal);
    document.body.appendChild(modalOverlay);

    // 3. Logic
    let selectedText = "";

    const hideModal = function() {
        modalOverlay.style.opacity = "0";
        setTimeout(function() { modalOverlay.style.display = "none"; }, 300);
    };

    closeBtn.onclick = hideModal;
    modalOverlay.onclick = function(e) { if (e.target === modalOverlay) hideModal(); };

    document.addEventListener("mouseup", function() {
        const selection = window.getSelection();
        const text = selection.toString().trim();
        
        if (text.length > 10) {
            selectedText = text;
            try {
                const range = selection.getRangeAt(0);
                const rect = range.getBoundingClientRect();
                
                verifyBtn.style.display = "block";
                verifyBtn.style.top = (window.scrollY + rect.bottom + 10) + "px";
                verifyBtn.style.left = (window.scrollX + rect.left) + "px";
            } catch(e) {
                console.log("TrustGuard: Could not position button", e);
            }
        } else {
            verifyBtn.style.display = "none";
        }
    });

    document.addEventListener("mousedown", function(e) {
        if (e.target !== verifyBtn) verifyBtn.style.display = "none";
    });

    verifyBtn.addEventListener("click", function() {
        verifyBtn.style.display = "none";
        modalOverlay.style.display = "flex";
        modalOverlay.offsetHeight;
        modalOverlay.style.opacity = "1";
        
        resultsContainer.innerHTML = '<div style="text-align:center;"><div class="tg-spinner"></div><p style="color:#94a3b8; font-size:13px;">Analyzing claims...</p></div>';

        chrome.runtime.sendMessage({ action: "verifyText", text: selectedText }, function(response) {
            if (chrome.runtime.lastError || !response || !response.success) {
                var errMsg = "Backend unreachable. Is it running on localhost:8000?";
                if (chrome.runtime.lastError) errMsg = chrome.runtime.lastError.message;
                else if (response && response.error) errMsg = response.error;
                
                resultsContainer.innerHTML = '<div style="text-align:center; color:#f87171; padding:10px;"><p><strong>Verification Failed</strong></p><p style="font-size:12px;">' + errMsg + '</p></div>';
                return;
            }

            var data = response.data;
            var html = '<div style="text-align:center; margin-bottom:20px;"><div style="font-size:32px; font-weight:bold; color:#38bdf8;">' + data.overallScore + '%</div><div style="font-size:12px; color:#94a3b8; text-transform:uppercase; letter-spacing:1px;">Trust Score</div></div>';

            if (data.claims && data.claims.length > 0) {
                data.claims.forEach(function(c) {
                    html += '<div class="tg-claim-card">';
                    html += '<div class="tg-status tg-status-' + c.status.toLowerCase() + '">' + c.status + '</div>';
                    html += '<div style="font-size:14px; margin-bottom:8px;">"' + c.text + '"</div>';
                    if (c.explanation) {
                        html += '<div style="font-size:12px; color:#94a3b8; margin-bottom:8px;">' + c.explanation + '</div>';
                    }
                    if (c.sourceUrl) {
                        html += '<a href="' + c.sourceUrl + '" target="_blank" style="color:#38bdf8; font-size:12px; text-decoration:none;">🔗 Source: ' + (c.source || 'View Evidence') + '</a>';
                    }
                    html += '</div>';
                });
            }

            if (data.citations && data.citations.length > 0) {
                html += '<div style="margin:15px 0 10px; font-weight:bold; font-size:13px; color:#94a3b8;">CITATIONS</div>';
                data.citations.forEach(function(cit) {
                    var color = cit.exists ? '#34d399' : '#f87171';
                    var label = cit.exists ? '✓ Found' : '✗ Not Found';
                    html += '<div style="font-size:12px; padding:8px; border-left:2px solid ' + color + '; background:rgba(255,255,255,0.03); margin-bottom:5px;">';
                    html += '<div style="font-weight:bold; color:' + color + ';">' + label + '</div>';
                    html += '<div>' + cit.text + '</div>';
                    html += '</div>';
                });
            }

            resultsContainer.innerHTML = html;
        });
    });
})();

