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
