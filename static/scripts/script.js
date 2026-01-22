let selectedFile = null;
let fileId = null;
let isSending = false;
let isUploading = false;
let isTyping = false;

const dropzone = document.getElementById("dropzone");
const fileInput = document.getElementById("fileInput");
const uploadBtn = document.getElementById("uploadBtn");
const cancelUploadBtn = document.getElementById("cancelUploadBtn");
const fileNameEl = document.getElementById("fileName");
const fileIdEl = document.getElementById("fileId");
const fileInfo = document.getElementById("fileInfo");
const progressBar = document.getElementById("progressBar");
const statusText = document.getElementById("statusText");
const kbBadge = document.getElementById("kbBadge");
const uploadPanel = document.getElementById("uploadPanel");
const uploadToggle = document.getElementById("uploadToggle");

const chatBody = document.getElementById("chatBody");
const promptInput = document.getElementById("promptInput");
const sendBtn = document.getElementById("sendBtn");
const resetBtn = document.getElementById("resetBtn");
const clearChatBtn = document.getElementById("clearChatBtn");

function setStatus(text) {
  statusText.textContent = text;
}

function scrollChat() {
  requestAnimationFrame(() => {
    chatBody.scrollTop = chatBody.scrollHeight;
  });
}

function renderMath() {
  if (window.renderMathInElement) {
    try {
      renderMathInElement(chatBody, {
        delimiters: [
          { left: "$$", right: "$$", display: true },
          { left: "\\[", right: "\\]", display: true },
          { left: "\\(", right: "\\)", display: false },
          { left: "$", right: "$", display: false },
        ],
        throwOnError: false,
        strict: false,
        trust: true,
        fleqn: false,
      });
    } catch (e) {
      console.error("Math rendering error:", e);
    }
  }
}

function escapeHTML(str) {
  const div = document.createElement('div');
  div.textContent = str || "";
  return div.innerHTML;
}

async function typewriterEffect(element, text, speed = 30) {
  if (isTyping) return;
  isTyping = true;
  
  element.innerHTML = '';
  
  let i = 0;
  const content = text || "";
  
  const tempDiv = document.createElement('div');
  tempDiv.style.display = 'none';
  if (window.marked) {
    tempDiv.innerHTML = marked.parse(content, {
      breaks: true,
      gfm: true
    });
  } else {
    tempDiv.textContent = content;
  }
  
  const htmlContent = tempDiv.innerHTML;
  
  const cursor = document.createElement('span');
  cursor.className = 'typewriter-cursor';
  cursor.innerHTML = '▌';
  
  element.appendChild(cursor);
  scrollChat();
  
  function typeChar() {
    if (i < htmlContent.length) {
      if (cursor.parentNode) {
        cursor.remove();
      }
      const chunkSize = Math.random() > 0.7 ? 3 : 1; 
      const end = Math.min(i + chunkSize, htmlContent.length);
      const chunk = htmlContent.substring(i, end);
      const chunkDiv = document.createElement('div');
      chunkDiv.innerHTML = element.innerHTML + chunk;
      element.innerHTML = chunkDiv.innerHTML;
      
      element.appendChild(cursor);
      
      i = end;
      scrollChat();
      
      let delay = speed;
      const nextChar = htmlContent.charAt(i);
      
      if (nextChar === '.' || nextChar === '!' || nextChar === '?') {
        delay = speed * 4;
      } else if (nextChar === ',' || nextChar === ';' || nextChar === ':') {
        delay = speed * 2;
      } else if (nextChar === '\n') {
        delay = speed * 1.5;
      }
      
      setTimeout(typeChar, delay);
    } else {
      if (cursor.parentNode) {
        cursor.remove();
      }
      isTyping = false;
      setTimeout(() => {
        renderMath();
      }, 100);
    }
  }
  setTimeout(typeChar, 200);
}

function addBubble(text, who = "bot", useTypewriter = true) {
  const bubble = document.createElement("div");
  bubble.className = `bubble ${who}`;
  chatBody.appendChild(bubble);
  if (who === "bot" && useTypewriter) {
    bubble.innerHTML = '';
    setTimeout(() => {
      typewriterEffect(bubble, text);
    }, 100);
  } else {
    if (who === "bot" && window.marked) {
      bubble.innerHTML = marked.parse(text, {
        breaks: true,
        gfm: true
      });
      setTimeout(() => renderMath(), 50);
    } else {
      bubble.innerHTML = escapeHTML(text);
    }
  }
  
  scrollChat();
  return bubble;
}

function showTypingIndicator() {
  const bubble = document.createElement("div");
  bubble.className = "bubble bot";
  bubble.id = "typing-indicator";
  bubble.innerHTML = `
    <div class="typing-dots">
      <span></span>
      <span></span>
      <span></span>
    </div>
  `;
  chatBody.appendChild(bubble);
  scrollChat();
  return bubble;
}

function removeTypingIndicator() {
  const indicator = document.getElementById("typing-indicator");
  if (indicator) {
    indicator.remove();
  }
}

async function safeJson(res) {
  const raw = await res.text();
  let data = null;
  
  try {
    data = JSON.parse(raw);
  } catch (e) {
    console.error("JSON parse error:", e);
    console.error("Raw response:", raw);
    return {
      ok: false,
      status: res.status,
      message: "Server returned non-JSON response.\n\n```\n" +
        raw.slice(0, 800) +
        (raw.length > 800 ? "\n...(truncated)" : "") +
        "\n```",
    };
  }
  
  return {
    ok: res.ok,
    status: res.status,
    ...data,
  };
}

uploadToggle.addEventListener("click", () => {
  uploadPanel.classList.toggle("open");
});

if (dropzone) {
  dropzone.addEventListener("click", () => fileInput.click());
  
  dropzone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropzone.classList.add("dragover");
  });
  
  dropzone.addEventListener("dragleave", () => {
    dropzone.classList.remove("dragover");
  });
  
  dropzone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropzone.classList.remove("dragover");
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      setFile(e.dataTransfer.files[0]);
    }
  });
}

fileInput.addEventListener("change", (e) => {
  if (e.target.files && e.target.files[0]) {
    setFile(e.target.files[0]);
  }
});

function setFile(file) {
  selectedFile = file;
  fileNameEl.textContent = file.name;
  fileInfo.style.display = "block";
  progressBar.style.width = "0%";
  setStatus("File selected");
}

uploadBtn.addEventListener("click", async () => {
  if (isUploading) return;
  if (!selectedFile) {
    setStatus("Choose a file first");
    return;
  }
  
  isUploading = true;
  uploadBtn.disabled = true;
  uploadBtn.textContent = "Uploading...";
  cancelUploadBtn.style.display = "inline-flex";
  
  setStatus("Uploading...");
  progressBar.style.width = "5%";
  
  const infoBubble = addBubble("Uploading and processing your document...", "bot", false);
  
  try {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", "/upload", true);
    
    xhr.upload.onprogress = (evt) => {
      if (evt.lengthComputable) {
        const pct = Math.min(90, Math.round((evt.loaded / evt.total) * 90));
        progressBar.style.width = pct + "%";
      }
    };
    
    xhr.onload = () => {
      try {
        if (xhr.status >= 200 && xhr.status < 300) {
          let data;
          try {
            data = JSON.parse(xhr.responseText);
          } catch (e) {
            console.error("Upload response JSON parse error:", e);
            console.error("Raw response:", xhr.responseText);
            infoBubble.innerHTML = marked.parse(
              "Upload failed (server returned invalid JSON)\n\n```\n" +
              xhr.responseText.slice(0, 800) +
              (xhr.responseText.length > 800 ? "\n...(truncated)" : "") +
              "\n```"
            );
            setStatus("Upload failed");
            progressBar.style.width = "0%";
            return;
          }
          
          if (!data.file_id) {
            console.error("Missing file_id in response:", data);
            infoBubble.innerHTML = marked.parse("Upload failed: Server response missing file_id");
            setStatus("Upload failed");
            progressBar.style.width = "0%";
            return;
          }
          
          fileId = data.file_id;
          fileIdEl.textContent = `file_id: ${fileId}`;
          kbBadge.textContent = "KB: Loaded";
          kbBadge.style.background = "rgba(39, 214, 255, 0.15)";
          kbBadge.style.borderColor = "rgba(39, 214, 255, 0.3)";
          progressBar.style.width = "100%";
          setStatus("Upload complete");
          
          infoBubble.innerHTML = marked.parse(
            `**Document processed successfully!**\n\n${data.message || "Document indexed into knowledge base. You can now ask questions about it."}`
          );
          renderMath();
          
          setTimeout(() => {
            uploadPanel.classList.remove("open");
          }, 2000);
          
        } else {
          setStatus("Upload failed");
          progressBar.style.width = "0%";
          let errorMsg = "Upload failed";
          try {
            const errorData = JSON.parse(xhr.responseText);
            errorMsg = errorData.message || errorData.error || xhr.responseText;
          } catch (e) {
            errorMsg = xhr.responseText;
          }
          infoBubble.innerHTML = marked.parse(`Upload failed:\n\n${errorMsg}`);
          renderMath();
        }
      } finally {
        isUploading = false;
        uploadBtn.disabled = false;
        uploadBtn.textContent = "Upload & Index";
        cancelUploadBtn.style.display = "none";
      }
    };
    
    xhr.onerror = () => {
      setStatus("Upload error");
      progressBar.style.width = "0%";
      infoBubble.innerHTML = marked.parse("Network error during upload. Please check your connection.");
      renderMath();
      isUploading = false;
      uploadBtn.disabled = false;
      uploadBtn.textContent = "Upload & Index";
      cancelUploadBtn.style.display = "none";
    };
    
    const formData = new FormData();
    formData.append("file", selectedFile);
    xhr.send(formData);
  } catch (err) {
    console.error("Upload exception:", err);
    setStatus("Upload error");
    progressBar.style.width = "0%";
    infoBubble.innerHTML = marked.parse(`Upload error:\n\n${String(err)}`);
    renderMath();
    isUploading = false;
    uploadBtn.disabled = false;
    uploadBtn.textContent = "Upload & Index";
    cancelUploadBtn.style.display = "none";
  }
});

async function sendMessage() {
  if (isSending || isTyping) return;
  const userText = (promptInput.value || "").trim();
  if (!userText) {
    setStatus("Type something");
    return;
  }
  
  isSending = true;
  sendBtn.disabled = true;
  sendBtn.textContent = "Sending...";
  
  addBubble(userText, "user", false);
  promptInput.value = "";
  promptInput.style.height = "auto";
  setStatus("Thinking...");
  
  // Show typing indicator
  const typingBubble = showTypingIndicator();
  
  try {
    const payload = {
      user_input: userText,
      file_id: fileId
    };
    
    console.log("Sending request with payload:", payload);
    
    const res = await fetch("/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    
    const data = await safeJson(res);
    console.log("Received response:", data);
    
    removeTypingIndicator();
    
    if (!data.ok) {
      addBubble(
        `**Error (${data.status})**\n\n${data.message || data.error || "Unknown server error"}`,
        "bot",
        false
      );
      setStatus("Error");
      isSending = false;
      sendBtn.disabled = false;
      sendBtn.textContent = "Send";
      return;
    }
    
    if (!data.message && !data.response) {
      console.error("Invalid response format:", data);
      addBubble(
        "**Error**: Server returned invalid response format",
        "bot",
        false
      );
      setStatus("Error");
      isSending = false;
      sendBtn.disabled = false;
      sendBtn.textContent = "Send";
      return;
    }
    
    addBubble(data.message || data.response || "No response", "bot", true);
    setStatus("Ready");
    
  } catch (e) {
    console.error("Send message error:", e);
    removeTypingIndicator();
    addBubble(`**Network Error**\n\n${String(e)}`, "bot", false);
    setStatus("Error");
  } finally {
    isSending = false;
    sendBtn.disabled = false;
    sendBtn.textContent = "Send";
  }
}

sendBtn.addEventListener("click", sendMessage);

promptInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});

promptInput.addEventListener("input", () => {
  promptInput.style.height = "auto";
  promptInput.style.height = Math.min(promptInput.scrollHeight, 120) + "px";
});


resetBtn.addEventListener("click", async () => {
  if (isTyping) return;
  if (!confirm("Are you sure you want to reset the knowledge base? This will delete all uploaded documents.")) {
    return;
  }
  
  setStatus("Resetting...");
  const bubble = addBubble("Resetting knowledge base...", "bot", true);
  
  try {
    const res = await fetch("/reset", { method: "POST" });
    const data = await safeJson(res);
    
    if (!data.ok) {
      bubble.innerHTML = marked.parse(
        `**Reset failed (${data.status})**\n\n${data.message || data.error || "Unknown error"}`
      );
      renderMath();
      setStatus("Error");
      return;
    }
    
    bubble.innerHTML = marked.parse(`${data.message || "Knowledge base reset successfully"}`);
    renderMath();
    fileId = null;
    fileIdEl.textContent = "file_id: —";
    kbBadge.textContent = "KB: Empty";
    kbBadge.style.background = "rgba(180, 92, 255, 0.1)";
    kbBadge.style.borderColor = "rgba(180, 92, 255, 0.2)";
    progressBar.style.width = "0%";
    fileInfo.style.display = "none";
    selectedFile = null;
    setStatus("Ready");
  } catch (e) {
    console.error("Reset error:", e);
    bubble.innerHTML = marked.parse(`**Reset failed**\n\n${String(e)}`);
    renderMath();
    setStatus("Error");
  }
});

clearChatBtn.addEventListener("click", () => {
  if (isTyping) return;
  if (!confirm("Clear all chat messages?")) return;
  chatBody.innerHTML = "";
  addBubble("Chat cleared. How can I help you?", "bot", true);
  setStatus("Ready");
});

window.addEventListener("load", () => {
  addBubble("**Welcome to AURA!**\n\nI'm Academic Unified Research Agent. Upload a PDF document or ask me anything about academics, research, or problem-solving.", "bot", true);
  renderMath();
});

const style = document.createElement('style');
style.textContent = `
  .typewriter-cursor {
    display: inline;
    animation: blink 1s infinite;
    color: rgba(39, 214, 255, 0.9);
    font-weight: bold;
  }
  
  @keyframes blink {
    0%, 50% { opacity: 1; }
    51%, 100% { opacity: 0; }
  }
  
  .typing-dots {
    display: flex;
    gap: 4px;
    padding: 4px 0;
  }
  
  .typing-dots span {
    width: 6px;
    height: 6px;
    background: rgba(180, 92, 255, 0.7);
    border-radius: 50%;
    display: inline-block;
    animation: typingBounce 1.4s ease-in-out infinite;
  }
  
  .typing-dots span:nth-child(2) { animation-delay: 0.2s; }
  .typing-dots span:nth-child(3) { animation-delay: 0.4s; }
  
  @keyframes typingBounce {
    0%, 60%, 100% { transform: translateY(0); }
    30% { transform: translateY(-6px); }
  }
`;
document.head.appendChild(style);

let touchStartY = 0;
document.addEventListener('touchstart', (e) => {
  touchStartY = e.touches[0].clientY;
}, { passive: true });

document.addEventListener('touchmove', (e) => {
  const touchY = e.touches[0].clientY;
  const touchDiff = touchY - touchStartY;
  
  if (touchDiff > 0 && window.scrollY === 0) {
    e.preventDefault();
  }
}, { passive: false });
