from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
import os
import google.generativeai as genai
import chromadb
from chromadb.utils import embedding_functions
from PyPDF2 import PdfReader
from PIL import Image
import pytesseract
from io import BytesIO
import uuid

# === Load Environment Variables ===
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
HF_API_KEY = os.getenv("HF_API_KEY")
if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)

# === Initialize Flask ===
app = Flask(__name__)

# === Initialize Chroma Vector Database ===
chroma_client = chromadb.PersistentClient(path="./aura_knowledgebase")
# If HF_API_KEY is None the embedding function may still work depending on your environment.
embedding_fn = embedding_functions.HuggingFaceEmbeddingFunction(
    api_key=HF_API_KEY,
    model_name="all-MiniLM-L6-v2"
)
collection = chroma_client.get_or_create_collection(
    "aura_docs", embedding_function=embedding_fn
)

# === In-memory Chat History ===
chat_history = []  # stores tuples of (user_message, model_response)
MAX_HISTORY = 100  # retain only last 100 messages

# === Text Preprocessing and Embedding ===
def chunk_text(text, chunk_size=1000, overlap=200):
    """Split long text into overlapping chunks for better retrieval."""
    words = text.split()
    chunks = []
    start = 0
    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunk = " ".join(words[start:end])
        chunks.append(chunk)
        start += chunk_size - overlap
    return chunks

def add_to_knowledge_base(text, source_name):
    """Add processed text chunks to the Chroma knowledge base safely."""
    chunks = chunk_text(text)
    docs = []
    metas = []
    ids = []
    for chunk in chunks:
        docs.append(chunk)
        metas.append({"source": source_name})
        ids.append(f"{source_name}_{uuid.uuid4().hex}")
    try:
        collection.add(documents=docs, metadatas=metas, ids=ids)
    except Exception as e:
        # If Chroma fails, raise a readable exception
        raise RuntimeError(f"Chroma add failed: {e}")

def retrieve_relevant_chunks(query, k=3):
    """Retrieve top-k relevant document chunks based on query similarity."""
    try:
        results = collection.query(query_texts=[query], n_results=k)
        docs = results.get("documents", [])
        if not docs or not docs[0]:
            return ""
        return "\n\n".join(docs[0])
    except Exception:
        # If retrieval fails, return empty context (fail gracefully)
        return ""

# === System Prompt ===
system_prompt = """
You are AURA — an Agentic AI Study and Research assistant designed to guide students and researchers...
(keep the rest of your long system prompt here exactly as you had)
"""

# === Initialize Gemini Model ===
# Note: We will *not* pass complex history objects to start_chat; instead we'll send one combined prompt.
model = genai.GenerativeModel(
    model_name="gemini-2.5-flash",
    system_instruction=system_prompt
)

# === Flask Routes ===
@app.route("/", methods=["GET", "POST"])
def home():
    global chat_history
    response = ""

    if request.method == "POST":
        user_input = request.form.get("user_input", "").strip()
        if not user_input:
            return render_template("index.html", response="Please enter a query.")

        # Check API key presence early
        if not GOOGLE_API_KEY:
            return render_template("index.html", response="Server error: GOOGLE_API_KEY not configured.")

        # Step 1: Retrieve relevant context from vector DB
        doc_context = retrieve_relevant_chunks(user_input)

        # Step 2: Build a single prompt that includes system + a textual short chat history + KB + user query
        # Keep history short to avoid very long prompts
        short_hist = chat_history[-10:]  # last 10 interactions only in prompt
        history_text = ""
        for u, b in short_hist:
            # sanitize to strings
            history_text += f"User: {u}\nAI: {b}\n"

        full_prompt = f"{system_prompt}\n\n{history_text}\nKnowledge Base Context:\n{doc_context}\n\nUser Query:\n{user_input}"

        try:
            # Use empty start_chat() and send the single combined prompt.
            chat = model.start_chat()  # no history parameter
            response_obj = chat.send_message(full_prompt)

            # Safely retrieve text (some SDK objects may or may not have .text)
            ai_response = getattr(response_obj, "text", None)
            if ai_response is None:
                # fallback to string conversion
                ai_response = str(response_obj)

        except Exception as e:
            # Provide a helpful error message rather than crash
            err_text = str(e)
            # Common cause: API returning HTML error page due to bad API key or rate limits
            if "401" in err_text or "403" in err_text or "Unauthorized" in err_text or "Forbidden" in err_text:
                ai_response = "⚠️ Model API returned an authorization error. Check GOOGLE_API_KEY and billing."
            elif "JSONDecodeError" in err_text or "Expecting value" in err_text or err_text.strip().startswith("<"):
                ai_response = "⚠️ Model response could not be decoded (server returned non-JSON). Try again or check API key."
            else:
                ai_response = f"Error: {err_text}"

        # Step 3: Update in-memory chat log
        chat_history.append((user_input, ai_response))
        if len(chat_history) > MAX_HISTORY:
            chat_history = chat_history[-MAX_HISTORY:]

        response = ai_response.replace("\n", "<br>")
        return render_template("index.html", response=response)

    return render_template("index.html", response=response)


# === Optional route to clear chat history ===
@app.route("/clear_history", methods=["POST"])
def clear_history():
    global chat_history
    chat_history.clear()
    return jsonify({"message": "Chat history cleared."})


@app.route("/upload", methods=["POST"])
def upload():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]
    filename = file.filename or ""

    if filename == "":
        return jsonify({"error": "Empty filename"}), 400

    text = ""
    try:
        file_bytes = file.read()
        if filename.lower().endswith(".pdf"):
            # Use BytesIO to ensure PdfReader reads from bytes
            reader = PdfReader(BytesIO(file_bytes))
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"

        elif filename.lower().endswith((".png", ".jpg", ".jpeg")):
            # Use BytesIO and ensure RGB
            image = Image.open(BytesIO(file_bytes)).convert("RGB")
            text = pytesseract.image_to_string(image)

        else:
            return jsonify({"error": "Unsupported file type"}), 400

        # --- Store Text in Knowledge Base ---
        if text.strip():
            try:
                add_to_knowledge_base(text, filename)
            except Exception as e:
                return jsonify({"error": f"Failed to add to knowledge base: {e}"}), 500
            return jsonify({"message": f"File '{filename}' processed and added to knowledge base."}), 200
        else:
            return jsonify({"error": "No extractable text found in file"}), 400

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True)
