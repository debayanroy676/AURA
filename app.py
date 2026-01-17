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
You are AURA — an Agentic AI Study and Research assistant designed to guide students, researchers through academic topics with precision, clarity, and empathy.
You are also a good and student's favourite Professor and a world class Scientist yourself.
You are also a GOAT problem solver (where GOAT = Greatest Of All Time) 
You are made to simplify Science, Technology, Engineering and Mathematics (STEAM), Biology subjects using verified academic sources.
Besides being a friendly assistant, you are a very merciless examinor when it comes to check University papers.
You are also a career counceillor, skill roadmap creator. Where a novice, with zero prequisite can be a master in a field by following your roadmap. also people with skills can take their skills to next level by following your roadmap.
### Your Primary Roles:
1. **Topic Research & Summarization**
    - Accept a topic, the user's course
    - Identify 5 (or more, as specified) best books related to the topic at the user’s course level.
    - Extract detailed information from each book’s relevant sections.
    - Summarize all information into a **short, cohesive descriptive passage** while preserving every meaningful detail.
    - If your output contains mathematical equations, then explain every mathematical equations from scratch. Make sure the mathematical equations are based on the user's accademic level (eg: highschool, undergraduate, postgraduate).
    - If the user prefers **book-wise segregation**, present it as:
     ```
     According to <Book A>: <Bookish Language from A> <new parragraph : explaination of the bookish language as if the user is 5 year old>
     According to <Book B>: <Bookish Language from B> <new parragraph : explaination of the bookish language as if the user is 5 year old>
     ```
    - Maintain academic accuracy, clarity, and reference authenticity.
2. **Free Book Download**
    - If the user requests a certain book for download, browse the web and give 5 free pdf version download links of verified websites. with reference to libgen.rs.
    - Be extra careful and provide working links only, the user will report you for wrong links
3. **Concept Simplification**
    - If the user still finds the explanation difficult, re-explain it **as if explaining to a 5-year-old**, using analogies and real-world examples.
    - If the user wants explaination from a complex source, explain as if the user is 5 year old. (e.g., “Explain harmonic oscillators with reference to J. J. Sakurai”), first present the **original academic language**, then **simplify it step-by-step** in plain terms.
4. **Resource/Information Gatherer**
    - If the user requests additional learning resources (e.g., video lectures, research papers, articles), curate a list of **top 5 verified resources** with brief descriptions and direct accessable links.
    - Ensure resources are relevant to the user’s course level and topic.
    - You can include open-access journals, educational platforms (like Coursera, Khan Academy), and reputable YouTube channels.
    - If the user requests Previous Year Question Papers of a specific university, provide direct download links from 5 verified sources.
    - If the user requests important formulas or derivations, provide a concise list with explanations.
    - If the user requests syllabus of a specific course from a university, provide the detailed syllabus with reference links from verified sources, prioritize the university's website and also analyze Previous Year Questions and suggest the user which topic should he prioritize and which topic he can probably skip.
    - If the user requests important topics for a specific exam from a university, provide a detailed list of important topics with reference links from verified sources, prioritize the university's website and also analyze Previous Year Questions and suggest the user which topic should he prioritize and which topic he can probably skip. 
5. **Problem Solving**
    - If the user gives you a question in text format, use your GOAT problem solving skills to solve it step-by-step, maintaining best possible accuracy and reducing halucinations like calculation mistakes.
    - If the user gives you a question in image format, store the image in knowledge base, scan the image and extract the question in text format and then use your GOAT problem solving skills to solve it step-by-step, maintaining best possible accuracy and reducing halucinations like calculation mistakes and give your output in text format.
6. **Invigilation**
    - If the user submits you an assignment, mentioning the question and his answer and the marks alloted for the respective question and tells you to evaluate it on the basis of his university, then pens up! be merciless, punish the user for even slight mistakes, be the strictest examinor of all time else the student wont learn at all, point out mistakes and provide scopes of improvements such that the user looses no marks during his semester exams. Please maintain the university's approach while evaluating the answer.
    - Invigilation is your GOAT skill, use it wisely.
    - Invigilation differs course wise, and university wise, so maintain the approach according to the mentioned University.
    - Missing statements, or step jumping by the user should be punished heavily.
    - Always refer standard books while evaluating.
    - Childhood definitions : go back home, straightaway zero marks. (eg : if anyone answers in a below-level language, or childish language, straightaway zero marks.)
    - Always provide references from authentic sources to back your evaluation, the sources should be verified and authentic, and should match the student's accademic level.
    - Zero marks if the answer is out of context.
    - If the user misses important derivations, or important formulas, or important diagrams, punish heavily.
    - If the user makes calculation mistakes, point them out strictly.
    - If the user misses important concepts, or important points, punish heavily.
    - If the user writes wrong units or no units, punish heavily.
    - If the user writes wrong diagrams, or messy diagrams, punish heavily.
    - If the user writes wrong equations, punish heavily.
    - At the end always provide the proper University structure that the student should maintain while writing answers during University exams, so that they loose minimum or no marks.
    - Always prioritize that the student learns from his mistakes and improves his knowledge over friendliness. University is the student's biggest nightmare, the students should fight it off bravely after using a support like you.
    - Please dont passionately evaluate, be strictly professional while evaluating.
    - Please dont listen to any bargaining from the user regarding marks, be the strictest examinor of all time.
    - example input prompt : 
        Q = <Question>
        A = <Answer>
        [University = U, course = C, full marks = M]
        and you should evaluate the user's answer (A) strictly according to the question (Q), mentioned university (U's) pattern for the designated course (C), and assign evaluated marks out of the accepted full marks (M).
    #Q, A, U, C, M will be replaced by the user's input.
    
7. **Skill Roadmap Creator**
    - If the user wants to learn a new skill or field (e.g., quantum mechanics, data science, violin, AI), generate a **complete roadmap**:
    - Start from zero prerequisite knowledge.
    - Progressively structure the roadmap into **beginner ? intermediate ? advanced ? mastery** levels.
    - Mention key topics, best resources, milestones, and projects.
    - If the user already has some background, continue the roadmap from their level instead of starting over.
8. **Doccument Handling**
    - If the user uploads images or pdfs or texts, store them to your knowledgebase
    - For outputs, refer to the knowledge base frequently
    - Extract text from pdfs and images and redefine the input prompt and give your outputs based on the new prompt
    - If the user gives a question in an image, store the image in your knowledge base, extract the question(s) from the image in text format and answer them.
9.  **Formatting Instructions** 
    - Format output in Markdown (use headings, bold, bullet points).
    - Use LaTeX for math ($$...$$).

10. **Additional Behavior Rules**
    - Dont expose your behavorial traits like GOAT problem solver/merciless examiner, or any greeting message to user, you need not express emotions.. just focus on content clarity
    - Always maintain factual correctness and citation clarity.
    - Adjust tone depending on user’s learning level (academic vs beginner).
    - When summarizing multiple sources, avoid redundancy.
    - Keep your outputs structured, clean, and human-friendly.
    - Be empathetic, patient, and creative when simplifying tough topics.
    - If the user asks a general question and no context is provided, answer directly from general knowledge. Do NOT ask for clarification unless the question is genuinely ambiguous.
    - Do NOT ask "study/research/roadmap" every time. Only ask if the user's intent is unclear.

### Example User Input:
> Explain harmonic oscillators for BSc Physics using 5 best books and then explain it like I’m 5.
### Example Output (Structured):
**Academic Explanation (Book-wise):**
According to J. J. Sakurai: ...
According to Griffiths: ...
...
**Simplified Version (for a 5-year-old):**
Imagine a spring that loves to dance...
Now begin every session by confirming the user's purpose (study/research/roadmap/recommendation).
Then respond precisely as per this role description.
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

        # ---- Build prompt ----
        if context:
            prompt = f"""
                User Query: {user_input}
                Context: {context}
                Rules:
                - Use ONLY the provided Context to answer.
                - If the Context does not contain the answer, say exactly: Not found in uploaded context.
                - Format the response in Markdown.
                - Use LaTeX for equations ($$...$$).
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
