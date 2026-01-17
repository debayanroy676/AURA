let selectedFile = null;
let fileId = null;

const dropzone = document.getElementById("dropzone");
const fileInput = document.getElementById("fileInput");
const uploadBtn = document.getElementById("uploadBtn");
const fileNameEl = document.getElementById("fileName");
const fileIdEl = document.getElementById("fileId");
const bar = document.getElementById("bar");
const statusText = document.getElementById("statusText");
const kbBadge = document.getElementById("kbBadge");

const chatBody = document.getElementById("chatBody");
const promptEl = document.getElementById("prompt");
const sendBtn = document.getElementById("sendBtn");

const resetBtn = document.getElementById("resetBtn");
const clearChatBtn = document.getElementById("clearChatBtn");

function setStatus(t) {
    statusText.textContent = t;
}

function scrollChat() {
    chatBody.scrollTop = chatBody.scrollHeight;
}

function renderMath() {
    if (window.renderMathInElement) {
        try {
            renderMathInElement(chatBody, {
                delimiters: [
                    { left: "$$", right: "$$", display: true },
                    { left: "$", right: "$", display: false },
                ]
            });
        } catch (e) { }
    }
}

function escapeHTML(str){
  return str.replace(/[&<>"']/g, (m) => ({
    "&":"&amp;",
    "<":"&lt;",
    ">":"&gt;",
    '"':"&quot;",
    "'":"&#039;"
  }[m]));
}

function addBubble(text, who="bot"){
  const b = document.createElement("div");
  b.className = "bubble " + who;

  if (who === "bot") {
    if (window.marked) {
      b.innerHTML = marked.parse(text || "");
    } else {
      b.textContent = text;
    }
  } else {
    b.innerHTML = escapeHTML(text || "");
  }

  chatBody.appendChild(b);
  scrollChat();
  renderMath();
  return b;
}


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

fileInput.addEventListener("change", (e) => {
    if (e.target.files && e.target.files[0]) {
        setFile(e.target.files[0]);
    }
});

function setFile(f) {
    selectedFile = f;
    fileNameEl.textContent = f.name;
    bar.style.width = "0%";
    setStatus("File selected");
}

uploadBtn.addEventListener("click", async () => {
    if (!selectedFile) {
        setStatus("Choose a file first");
        return;
    }

    setStatus("Uploading...");
    bar.style.width = "8%";

    const formData = new FormData();
    formData.append("file", selectedFile);

    try {
        const xhr = new XMLHttpRequest();
        xhr.open("POST", "/upload", true);

        xhr.upload.onprogress = (evt) => {
            if (evt.lengthComputable) {
                const pct = Math.min(90, Math.round((evt.loaded / evt.total) * 90));
                bar.style.width = pct + "%";
            }
        };

        xhr.onload = () => {
            if (xhr.status === 200) {
                const data = JSON.parse(xhr.responseText);
                fileId = data.file_id;
                fileIdEl.textContent = "file_id: " + fileId;
                kbBadge.textContent = "KB: loaded";
                bar.style.width = "100%";
                setStatus("Upload done");
                addBubble("Uploaded & indexed. Now ask your question.", "bot");
            } else {
                setStatus("Upload failed");
                addBubble("Upload failed: " + xhr.responseText, "bot");
                bar.style.width = "0%";
            }
        };

        xhr.onerror = () => {
            setStatus("Upload error");
            addBubble("Upload error. Check console/logs.", "bot");
            bar.style.width = "0%";
        };

        xhr.send(formData);

    } catch (err) {
        setStatus("Upload error");
        addBubble("Upload error: " + err, "bot");
        bar.style.width = "0%";
    }
});

async function sendMessage() {
    const userText = (promptEl.value || "").trim();
    if (!userText) {
        setStatus("Type something");
        return;
    }

    addBubble(userText, "user");
    promptEl.value = "";
    setStatus("Thinking...");

    const loading = addBubble("Processing…", "bot");

    try {
        const res = await fetch("/", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                user_input: userText,
                file_id: fileId
            })
        });

        const data = await res.json();

        if (window.marked) {
            loading.innerHTML = marked.parse(data.message || "No response");
        } else {
            loading.textContent = data.message || "No response";
        }

        setStatus("Ready");
        renderMath();
        scrollChat();
    } catch (e) {
        loading.textContent = "Error: " + e;
        setStatus("Error");
    }
}


sendBtn.addEventListener("click", sendMessage);

promptEl.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});

resetBtn.addEventListener("click", async () => {
    setStatus("Resetting...");
    try {
        const res = await fetch("/reset", { method: "POST" });
        const raw = await res.text();
        let data;
        try {
            data = JSON.parse(raw);
        } catch (e) {
            loading.textContent = "Server returned non-JSON:\n\n" + raw;
            setStatus("Error");
            return;
        }

        addBubble(data.message || "KB reset", "bot");
        fileId = null;
        fileIdEl.textContent = "file_id: —";
        kbBadge.textContent = "KB: empty";
        bar.style.width = "0%";
        setStatus("Ready");
    } catch (e) {
        addBubble("Reset failed: " + e, "bot");
        setStatus("Error");
    }
});

clearChatBtn.addEventListener("click", () => {
    chatBody.innerHTML = "";
    addBubble("Chat cleared. Upload again or ask a new question.", "bot");
    setStatus("Ready");
});

window.addEventListener("load", () => {
    renderMath();
});

const kbToggleBtn = document.getElementById("kbToggleBtn");
const kbPanel = document.getElementById("kbPanel");

if (kbToggleBtn && kbPanel) {
  kbToggleBtn.addEventListener("click", () => {
    kbPanel.classList.toggle("open");
  });
}
