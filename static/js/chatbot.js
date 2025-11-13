document.addEventListener('DOMContentLoaded', () => {
    const chatbotToggler = document.querySelector(".chatbot-toggler");
    const closeBtn = document.querySelector(".close-btn");
    const chatbox = document.querySelector(".chatbox");
    const chatInput = document.querySelector(".chat-input textarea");
    const sendChatBtn = document.querySelector(".chat-input span");

    // 1. SOLIS: Izveidot mainīgo sarunas vēstures glabāšanai
    let chatHistory = [];

    const createChatLi = (message, className) => {
        const chatLi = document.createElement("li");
        chatLi.classList.add("chat", className);
        let chatContent = className === "outgoing" 
            ? `<p></p>` 
            : `<span class="material-symbols-outlined">smart_toy</span><p></p>`;
        chatLi.innerHTML = chatContent;
        chatLi.querySelector("p").textContent = message;
        return chatLi;
    }

    // 2. SOLIS: Implementēt funkciju, kas sazinās ar serveri
    const generateResponse = (incomingChatLi) => {
        const API_URL = "/chatbot";
        const messageElement = incomingChatLi.querySelector("p");

        // Sagatavot pieprasījuma opcijas
        const requestOptions = {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({
                message: chatHistory[chatHistory.length - 1].content,  // Pēdējā lietotāja ziņa
                history: chatHistory.slice(0, -1)  // Vēsture BEZ pēdējās ziņas
            })
        };

        console.log("DEBUG: Sending to API:", requestOptions.body);

        // Izsaukt servera endpoint
        fetch(API_URL, requestOptions)
            .then(res => {
                if (!res.ok) {
                    throw new Error(`HTTP error! status: ${res.status}`);
                }
                return res.json();
            })
            .then(data => {
                console.log("DEBUG: API response:", data);
                const botReply = data.response || 'No response from server.';
                messageElement.textContent = botReply;

                // 3. SOLIS: Pievienot bota atbildi sarunas vēsturei
                chatHistory.push({ 
                    role: 'assistant', 
                    content: botReply 
                });

                chatbox.scrollTo(0, chatbox.scrollHeight);
            })
            .catch(err => {
                messageElement.textContent = 'Error: Could not reach chatbot.';
                console.error('Chatbot fetch error:', err);
            });
    }

    const handleChat = () => {
        const userMessage = chatInput.value.trim();
        if (!userMessage) return;

        chatInput.value = "";
        chatInput.style.height = `auto`;

        // Parādīt lietotāja ziņu
        chatbox.appendChild(createChatLi(userMessage, "outgoing"));
        chatbox.scrollTo(0, chatbox.scrollHeight);

        // Pievienot lietotāja ziņu sarunas vēsturei
        chatHistory.push({ 
            role: 'user', 
            content: userMessage 
        });

        console.log("DEBUG: Chat history updated:", chatHistory);

        setTimeout(() => {
            const incomingChatLi = createChatLi("Thinking...", "incoming");
            chatbox.appendChild(incomingChatLi);
            chatbox.scrollTo(0, chatbox.scrollHeight);
            generateResponse(incomingChatLi);
        }, 600);
    }

    // Event listeners
    chatInput.addEventListener("input", () => {
        chatInput.style.height = `auto`;
        chatInput.style.height = `${chatInput.scrollHeight}px`;
    });

    chatInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && !e.shiftKey && window.innerWidth > 800) {
            e.preventDefault();
            handleChat();
        }
    });

    sendChatBtn.addEventListener("click", handleChat);
    closeBtn.addEventListener("click", () => {
        document.body.classList.remove("show-chatbot");
    });
    chatbotToggler.addEventListener("click", () => {
        document.body.classList.toggle("show-chatbot");
    });
});
