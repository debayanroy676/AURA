# 🚀 AURA - Academic Unified Research Agent

## 📋 Overview

AURA (Academic Unified Research Agent) is an intelligent AI-powered academic assistant built with Flask and Google's Gemini AI. It helps students solve problems, understand concepts, summarize notes, and navigate their academic journey with context-aware responses powered by RAG (Retrieval Augmented Generation).

---

## ✨ Key Features

### 🧠 Intelligent Document Processing
- **PDF Processing**: Extract and index content from academic PDFs with automatic OCR fallback
- **Image OCR**: Extract text from images of notes, question papers, and handwritten content
- **Smart Chunking**: Optimized text chunking with overlap for better context retrieval
- **Fast Processing**: Multi-threaded processing for up to 10 pages with configurable limits

### 🔍 Advanced RAG System
- **ChromaDB Integration**: Persistent vector database for efficient semantic search
- **Embedding Caching**: LRU cache for embeddings to reduce API calls and improve performance
- **Context-Aware Responses**: Retrieve relevant context from uploaded documents
- **Document-Specific Queries**: Filter results by specific uploaded documents

### 💬 Academic AI Assistant
- **Multiple Use Cases**:
  - Solve question papers step-by-step
  - Explain complex concepts
  - Summarize lengthy notes
  - Provide career roadmaps and guidance
  - Evaluate answers
- **LaTeX Support**: Properly formatted mathematical equations using $$...$$ syntax
- **Markdown Output**: Clean, structured responses with headings and bullet points

### 🛠️ Technical Excellence
- **Gemini 2.5 Flash**: Latest Google AI model for fast, accurate responses
- **Text Embedding 004**: State-of-the-art embeddings for semantic search
- **Concurrent Processing**: ThreadPoolExecutor for parallel PDF/image processing
- **Error Handling**: Robust error handling and logging throughout
- **Resource Optimization**: Image compression, text cleaning, and memory-efficient processing

---

## 🏗️ Architecture

```
AURA
├── Flask Web Server (Port 5000)
├── Google Gemini AI (gemini-2.5-flash)
├── ChromaDB Vector Database
├── Text Embedding (text-embedding-004)
└── Multi-threaded Processing Pipeline
```

### Core Components

1. **Document Ingestion**: PDF/Image → Text Extraction → Chunking → Embedding → Storage
2. **Query Processing**: User Query → Embedding → Semantic Search → Context Retrieval
3. **Response Generation**: Context + Query + System Prompt → Gemini AI → Formatted Response

---

### Processing Limits
```python
# Maximum pages to process per PDF = 10 (free tier allows 10 requests per minuite)
# Chunk size and overlap
chunk_size=900
overlap=150
```

---

## 📡 API Endpoints

### Health Check
```http
GET /health
```
Returns service status and component health.

**Response:**
```json
{
  "status": "healthy",
  "service": "AURA",
  "chromadb": "connected",
  "gemini": "enabled"
}
```

### Upload Document
```http
POST /upload
Content-Type: multipart/form-data

file: <PDF or Image file>
```

**Supported Formats:**
- PDF: `.pdf`
- Images: `.jpg`, `.jpeg`, `.png`, `.webp`, `.bmp`

**Response:**
```json
{
  "message": "PDF processed",
  "file_id": "abc123def456"
}
```

### Query / Chat
```http
POST /
Content-Type: application/json

{
  "user_input": "Explain Newton's laws of motion",
  "file_id": "abc123def456"  // Optional: Query specific document
}
```

**Response:**
```json
{
  "message": "# Newton's Laws of Motion\n\n..."
}
```

### Reset Knowledge Base
```http
POST /reset
```
Clears all stored documents and embeddings.

**Response:**
```json
{
  "message": "Knowledge base reset"
}
```

---

## 🎯 Use Cases

### 1. **Question Paper Solver**
Upload a question paper (PDF/Image) and ask AURA to solve specific questions or the entire paper.

```
User: "Solve question 3 from the uploaded paper"
AURA: [Step-by-step solution with formulas and final answer]
```

### 2. **Concept Explainer**
Get detailed explanations of complex topics with examples.

```
User: "Explain quantum entanglement"
AURA: [Structured explanation with analogies and key points]
```

### 3. **Note Summarizer**
Upload lengthy lecture notes and get concise summaries.

```
User: "Summarize the uploaded notes on machine learning"
AURA: [Key concepts, formulas, and important points]
```

### 4. **Career Guide**
Ask for career roadmaps and skill recommendations.

```
User: "How do I become a machine learning engineer?"
AURA: [Roadmap with skills, resources, and timeline]
```

---

## 🚀 Performance Optimizations

### Caching Strategy
- **Embedding Cache**: LRU cache (8000 entries) for text embeddings
- **Query Cache**: LRU cache (256 entries) for single-text embeddings
- **Hash-based Deduplication**: SHA-1 hashing for duplicate detection

### Concurrent Processing
- **PDF Text Extraction**: 6 parallel workers
- **OCR Processing**: 2 parallel workers
- **Image Processing**: Thumbnail generation and compression

### Memory Management
- Image compression (JPEG, quality=60)
- Image resizing (max 2000px, OCR max 1600px)
- Text truncation (8000 chars for embeddings)
- Chunk size limits (900 words, 150 overlap)

---

## ⚠️ Known Limitations

1. **PDF Page Limit**: processes only first 10 pages (free tier limit)
2. **File Size**: Maximum 10MB upload size
3. **OCR Quality**: Depends on image quality and text clarity
4. **Concurrent Workers**: Multiple Gunicorn workers may cause ChromaDB lock issues
5. **API Rate Limits**: Subject to Google Gemini API quotas

---

## 🐛 Bug Fixes in v1.0.0

- Fixed ChromaDB initialization race condition with retry logic
- Added proper error handling for empty files and unsupported formats
- Improved text cleaning for special characters and encoding issues
- Fixed image processing pipeline for various image formats
- Added thread-safe ChromaDB initialization with locks
- Enhanced logging for better debugging

---



## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- **Google Gemini AI**: For providing the powerful AI models
- **ChromaDB**: For the excellent vector database
- **Flask**: For the lightweight web framework
- **PyMuPDF**: For PDF processing capabilities
- **Pillow**: For image processing

---

## 📞 Contact & Support

- **GitHub**: [@debayanroy676](https://github.com/debayanroy676)
- **LinkedIn**: [Debayan Roy](https://www.linkedin.com/in/debayan-roy-3814a4300)

For issues and feature requests, please use the [GitHub Issues](https://github.com/debayanroy676/aura/issues) page.

---

## 📊 Project Stats

- **Lines of Code**: ~500+
- **Dependencies**: 10+ Python packages
- **Supported Formats**: PDF, JPG, PNG, WEBP, BMP
- **Processing Speed**: ~1-2 pages/second (with OCR)
- **Max File Size**: 1GB
- **Embedding Dimension**: 768 (text-embedding-004)

---

## 🎓 Credits

**Developed by**: Debayan Roy  
**Institution**: Government College of Engineering and Textile Technology, Serampore    

---

<p align="center">
  <strong>⭐ If you find AURA helpful, please consider giving it a star on GitHub! ⭐</strong>
</p>

<p align="center">
  Made with ❤️ by Debayan Roy
</p>
