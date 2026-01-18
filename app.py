from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
import os, uuid, re, shutil
import logging
import google.generativeai as genai
import chromadb
from PIL import Image
from io import BytesIO
from concurrent.futures import ThreadPoolExecutor, as_completed
import fitz
from functools import lru_cache
import hashlib


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    raise RuntimeError("GOOGLE_API_KEY not set")
genai.configure(api_key=GOOGLE_API_KEY)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 1024 * 1024 * 1024

KB_PATH = "./aura_knowledgebase"
if os.path.exists(KB_PATH):
    shutil.rmtree(KB_PATH, ignore_errors=True)

chroma_client = chromadb.PersistentClient(path=KB_PATH)
collection = chroma_client.get_or_create_collection("aura_docs")

logging.info("Fresh session-based knowledge base initialized.")

system_prompt = """
        You are AURA — Academic Unified Research Agent.
        Core behavior:
            - Be direct and helpful. No greetings, no filler.
            - Always format output in Markdown with headings, bold, and bullet points.
            - Use LaTeX for equations using $$...$$.
            - If the user uploads context (PDF/image text), use it as the primary source.
            - If context is missing or insufficient, answer using general knowledge and clearly mention: "Answered using general knowledge (context insufficient)."
            - Do NOT repeat the uploaded text unless the user asks to extract it.
            - If the user asks to solve a question paper, solve it step-by-step and give final answers clearly.

        Capabilities:
            - Explain concepts
            - solve problems
            - summarize notes
            - evaluate answers
            - provide career roadmaps.

        Output rules:
            - Keep answers structured and readable.
            - For numericals: formula → substitution → final answer with unit.
"""

MODEL = genai.GenerativeModel("gemini-2.5-flash")
OCR_MODEL = genai.GenerativeModel("gemini-2.5-flash")   
EMBED_MODEL = "text-embedding-004"

def clean_text(t: str) -> str:
    if not t:
        return ""
    t = t.encode("utf-8", "ignore").decode("utf-8", "ignore")
    t = re.sub(r"[\x00-\x1F\x7F-\x9F]", " ", t)
    t = re.sub(r"[ \t]+", " ", t)
    return t.strip()

def chunk_text(text, chunk_size=900, overlap=150):
    words = text.split()
    chunks = []
    step = max(1, chunk_size - overlap)
    for i in range(0, len(words), step):
        chunks.append(" ".join(words[i:i + chunk_size]))
    return chunks


def encode_jpeg(img: Image.Image) -> bytes:
    if img.mode != "RGB":
        img = img.convert("RGB")
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=60, optimize=True)
    return buf.getvalue()

def _hash_text(text: str) -> str:
    return hashlib.sha1(text[:8000].encode("utf-8", "ignore")).hexdigest()


@lru_cache(maxsize=8000)
def _cached_embed_by_hash(text_hash: str, text: str):
    resp = genai.embed_content(model=EMBED_MODEL, content=[text[:8000]])
    return resp["embedding"][0]


def embed_texts(texts):
    vecs = []
    for t in texts:
        t = t or ""
        h = _hash_text(t)
        vecs.append(_cached_embed_by_hash(h, t))
    return vecs


@lru_cache(maxsize=256)
def _cached_embed_single(text: str):
    resp = genai.embed_content(model=EMBED_MODEL, content=[text[:8000]])
    return resp["embedding"][0]


def add_chunks_to_kb(chunks, filename, doc_id, page=None):
    ids = [f"{doc_id}_{uuid.uuid4().hex}" for _ in chunks]
    metas = [{"source": filename, "doc_id": doc_id, "page": page} for _ in chunks]
    vecs = embed_texts(chunks)
    collection.add(ids=ids, documents=chunks, metadatas=metas, embeddings=vecs)

def ocr_single_page(img_bytes):
    try:
        r = OCR_MODEL.generate_content([
            "Extract ALL handwritten or printed text EXACTLY as it appears. "
            "Preserve line breaks, spacing, equations, symbols and question numbers. "
            "Do NOT correct grammar or rewrite anything. "
            "If handwriting is unclear, guess only if 90% confidence and mark uncertain letters with (?)",
            {"mime_type": "image/jpeg", "data": img_bytes}
        ])
        return (getattr(r, "text", "") or "").strip()
    except Exception:
        logging.exception("OCR failed")
        return ""

def process_pdf_fast(pdf_bytes, filename, doc_id):
    pdf = fitz.open(stream=pdf_bytes, filetype="pdf")
    total_pages = pdf.page_count
    total = min(total_pages, 10)

    logging.info(f"📘 Processing {total}/{total_pages} pages")

    def extract_text(i):
        try:
            return i, (pdf[i].get_text("text") or "")
        except:
            return i, ""

    all_text = [""] * total

    with ThreadPoolExecutor(max_workers=6) as exe:
        futures = [exe.submit(extract_text, i) for i in range(total)]
        for f in as_completed(futures):
            i, txt = f.result()
            all_text[i] = txt

    has_text_layer = any(t.strip() for t in all_text)

    if not has_text_layer:
        logging.info("⚠ No text layer → Running OCR (FAST MODE)")

        def ocr_page(i):
            page = pdf[i]
            pix = page.get_pixmap(dpi=120)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            img.thumbnail((1600, 1600))
            return i, clean_text(ocr_single_page(encode_jpeg(img)))

        ocr_results = [""] * total
        with ThreadPoolExecutor(max_workers=2) as exe:
            futures = [exe.submit(ocr_page, i) for i in range(total)]
            for f in as_completed(futures):
                i, txt = f.result()
                ocr_results[i] = txt

        merged = "\n".join(ocr_results)

    else:
        merged = "\n".join(clean_text(t) for t in all_text if t.strip())

    final_text = clean_text(merged)
    chunks = [clean_text(c) for c in chunk_text(final_text) if clean_text(c)]
    chunks = [c for c in chunks if len(c.split()) >= 30]

    if not chunks:
        logging.warning("No valid chunks extracted from document.")
        return

    ids = [f"{doc_id}_{uuid.uuid4().hex}" for _ in chunks]
    metas = [{"source": filename, "doc_id": doc_id} for _ in chunks]
    vecs = embed_texts(chunks)

    collection.add(ids=ids, documents=chunks, metadatas=metas, embeddings=vecs)

@app.route("/upload", methods=["POST"])
def upload_file():
    file = request.files.get("file")
    if not file:
        return jsonify({"error": "No file uploaded"}), 400

    filename = file.filename.lower()
    ext = os.path.splitext(filename)[1]

    ALLOWED_IMAGES = {".jpg", ".jpeg", ".png", ".webp"}
    ALLOWED_PDF = {".pdf"}

    doc_id = uuid.uuid4().hex
    file_bytes = file.read()


    if ext in ALLOWED_IMAGES:
        try:
            img = Image.open(BytesIO(file_bytes))
        except:
            return jsonify({"error": "Invalid image"}), 400

        img = img.convert("RGB")

        pdf_buffer = BytesIO()
        img.save(pdf_buffer, format="PDF")
        pdf_bytes = pdf_buffer.getvalue()

        process_pdf_fast(pdf_bytes, filename + ".pdf", doc_id)

        return jsonify({
            "message": "Image converted to PDF and processed",
            "file_id": doc_id
        })

    elif ext in ALLOWED_PDF:
        try:
            pdf = fitz.open(stream=file_bytes, filetype="pdf")
        except:
            return jsonify({"error": "Invalid PDF"}), 400

        if pdf.page_count > 10:
            return jsonify({"error": "PDF > 10 pages"}), 400

        process_pdf_fast(file_bytes, filename, doc_id)

        return jsonify({
            "message": "PDF processed",
            "file_id": doc_id
        })

    else:
        return jsonify({"error": "Unsupported file type"}), 400


@app.route("/", methods=["GET", "POST"])
def home():
    if request.method == "POST":
        data = request.get_json(silent=True) or {}

        user_input = (data.get("user_input") or "").strip()
        doc_id = (data.get("file_id") or "").strip() or None

        if not user_input:
            return jsonify({"message": "Please enter a valid question."})
        try:
            qvec = _cached_embed_single(user_input)
        except Exception as e:
            logging.exception("Embedding failed")
            return jsonify({"message": f"Embedding error: {str(e)}"}), 500
        try:
            if doc_id:
                res = collection.query(
                    query_embeddings=[qvec],
                    n_results=6,
                    where={"doc_id": {"$eq": doc_id}}
                )
            else:
                res = collection.query(query_embeddings=[qvec], n_results=6)

            docs = []
            if res.get("documents") and res["documents"]:
                docs = res["documents"][0][:4]

            context = "\n\n".join(d[:6000] for d in docs).strip()
        except Exception as e:
            logging.exception("Chroma query failed")
            return jsonify({"message": f"KB query error: {str(e)}"}), 500

        if context:
            prompt = f"""
                User Query: {user_input}
                Context: {context}
                Rules:
                - The Context contains the question paper / notes.
                - Your job is to ANSWER/SOLVE the questions provided.
                - If the Context is a question paper, solve each question step-by-step and give final answers clearly.
                - If a question is missing required data, state what is missing and still provide the general method/formula.
                - Format the response in Markdown with headings and numbering.
                - Use LaTeX for equations like $$...$$.
            """

        else:
            prompt = f"""
                User Query: {user_input}
                Rules:
                - No uploaded context is available.
                - Answer from general knowledge.
                - Format in Markdown with headings, bullet points, and practical steps.
                - If it's a career question, give a roadmap and skills list.
                - Use LaTeX for equations ($$...$$) if needed.
            """
        try:
            r = MODEL.generate_content([system_prompt, prompt])

            msg = ""
            if getattr(r, "candidates", None):
                cand = r.candidates[0]
                content = getattr(cand, "content", None)
                if content and getattr(content, "parts", None):
                    out = []
                    for p in content.parts:
                        t = getattr(p, "text", None)
                        if t:
                            out.append(t)
                    msg = "\n".join(out).strip()

            if not msg:
                msg = "No response text returned by the model (possibly blocked or empty output)."

            return jsonify({"message": msg})

        except Exception as e:
            logging.exception("MODEL.generate_content failed")
            return jsonify({"message": f"Model error: {str(e)}"}), 500

    return render_template("index.html")

@app.route("/reset", methods=["POST"])
def reset():
    chroma_client.delete_collection("aura_docs")
    global collection
    collection = chroma_client.get_or_create_collection("aura_docs")
    return jsonify({"message": "Knowledge base reset"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
