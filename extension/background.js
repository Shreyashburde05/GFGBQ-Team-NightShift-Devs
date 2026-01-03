chrome.runtime.onInstalled.addListener(() => {
    chrome.contextMenus.create({
        id: "verifySelection",
        title: "Verify with TrustGuard AI",
        contexts: ["selection"]
    });
});

chrome.contextMenus.onClicked.addListener((info, tab) => {
    if (info.menuItemId === "verifySelection") {
        chrome.tabs.sendMessage(tab.id, { action: "openModalWithText", text: info.selectionText });
    }
});

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === "verifyText") {
        fetch("http://localhost:8000/api/verify", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({ text: request.text }),
        })
        .then(response => response.json())
        .then(data => sendResponse({ success: true, data }))
        .catch(error => {
            console.error("Background Fetch Error:", error);
            sendResponse({ success: false, error: error.message });
        });
        return true; // Keep the message channel open for async response
    }
});
