// पेज लोड होते ही पुरानी चैट ले आओ
window.onload = async function() {
    try {
        const response = await fetch("/get_history");
        const history = await response.json();
        history.forEach(chat => {
            const className = chat.sender === "CP" ? "user-message" : "nikita-message";
            appendMessage(chat.message, className);
        });
    } catch (error) {
        console.error("History load error:", error);
    }
};

async function sendMessage() {
    const inputField = document.getElementById("user-input");
    const message = inputField.value.trim();
    if (!message) return;

    appendMessage(message, "user-message");
    inputField.value = "";

    try {
        const response = await fetch("/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ message: message })
        });
        
        const data = await response.json();
        appendMessage(data.reply, "nikita-message");
    } catch (error) {
        appendMessage("Mera net slow hai yaar...", "nikita-message");
    }
}

function appendMessage(text, className) {
    const chatBox = document.getElementById("chat-box");
    const msgDiv = document.createElement("div");
    msgDiv.className = `message ${className}`;
    msgDiv.innerText = text;
    chatBox.appendChild(msgDiv);
    chatBox.scrollTop = chatBox.scrollHeight;
}

document.getElementById("user-input").addEventListener("keypress", function(event) {
    if (event.key === "Enter") sendMessage();
});

// पोलिंग (Polling): हर 10 सेकंड में चेक करो कि निकिता ने कोई रैंडम मैसेज तो नहीं भेजा
setInterval(async function() {
    try {
        const response = await fetch("/poll_messages");
        const data = await response.json();
        
        if (data.new_messages && data.new_messages.length > 0) {
            data.new_messages.forEach(msg => {
                appendMessage(msg, "nikita-message");
            });
        }
    } catch (error) {
        console.error("Polling error:", error);
    }
}, 10000); // 10000 मिलीसेकंड = 10 सेकंड
