---
title: Technical Interview Guide: Vector Databases & RAG
date: 2026-05-10T04:31:34.729214
---

# Technical Interview Guide: Vector Databases & RAG
**Role:** Senior Staff Engineer / FAANG Interviewer  
**Topic:** Vector Databases & Retrieval-Augmented Generation (RAG)  
**Status:** Definitive Deep-Dive

---

## 🧱 1. The Core Concept (Basics Refresh)

In the FAANG circuit, we don't care if you know *what* RAG is; we care if you know *why* we don't just fine-tune models instead.

### The "Why" of RAG
LLMs suffer from three terminal flaws:
1.  **Knowledge Cutoff:** They are frozen in time (training end-date).
2.  **Hallucination:** They prioritize linguistic probability over factual accuracy.
3.  **Data Privacy:** You cannot easily "unlearn" a specific document from a model's weights.

**RAG** solves this by decoupling **Reasoning** (the LLM) from **Knowledge** (the Vector Database). Think of the LLM as a judge and the Vector DB as a massive, searchable law library.

### The Vector Database (VDB)
Unlike relational databases (B-Trees for exact matches) or Search Engines (Inverted Indices for keyword matches), a VDB stores **Embeddings**—high-dimensional mathematical representations of semantics.
*   **The Goal:** Find the "Nearest Neighbors" in a vector space of $N$ dimensions (usually 768 to 1536).
*   **Key Insight:** In vector space, "King" and "Queen" are geometrically closer than "King" and "Apple."

---

## ⚙️ 2. Under the Hood (Internal Mechanics)

To pass a Staff-level interview, you must explain the trade-offs between **Precision (Exact Search)** and **Scale (Approximate Nearest Neighbor - ANN).**

### A. The Embedding Pipeline
1.  **Chunking:** You can't embed a 500-page book as one vector (loss of signal). We use recursive character splitting or semantic chunking with overlaps (e.g., 512 tokens with 10% overlap) to maintain context.
2.  **Normalization:** Most models require vectors to be normalized to a unit length so that **Cosine Similarity** becomes a simple **Dot Product** calculation—drastically saving CPU cycles.

### B. Indexing Algorithms (The "Staff" Knowledge)
You cannot brute-force $O(N)$ distance checks for millions of vectors. We use **ANN** algorithms:

1.  **HNSW (Hierarchical Navigable Small World):**
    *   **Mechanism:** A multi-layered graph. The top layer has few nodes (long-distance jumps); the bottom layer has all nodes (short-distance refinement). 
    *   **Pros:** Incredible query speed and high recall.
    *   **Cons:** High memory (RAM) consumption because the graph structure is bulky.
2.  **IVF (Inverted File Index):**
    *   **Mechanism:** Uses K-Means clustering to partition the vector space into Voronoi cells. You only search the centroids closest to your query.
    *   **Pros:** Smaller footprint than HNSW.
    *   **Cons:** Lower accuracy if the query falls near a cluster boundary.
3.  **PQ (Product Quantization):**
    *   **Mechanism:** Lossy compression. It breaks a large vector into sub-vectors and replaces them with a short code (centroid ID).
    *   **Pros:** Can reduce memory usage by 90%+.

### C. Distance Metrics
*   **Cosine Similarity:** Measures the *angle* between vectors. Best for NLP where text length varies.
*   **L2 (Euclidean):** Measures the *distance* between points. Best for image recognition or fixed-scale data.
*   **Inner Product (IP):** Used if your embeddings are not normalized or if "magnitude" of the concept matters.

---

## ⚠️ 3. The Interview Warzone

### The Probing Pattern
As an interviewer, I will look for your "Breaking Point." I’ll start with "How do you build a chatbot?" and quickly pivot to **"How do you handle 100 million documents with 50ms latency?"**

#### Scenario: "Our RAG system is retrieving irrelevant chunks, causing the LLM to hallucinate. How do you fix the retrieval pipeline?"

**The "Junior" Response:** "I'll try a bigger LLM or change the prompt." (Fail: This ignores the data source).
**The "Senior" Response:** "I'll increase the top-k value." (Better, but expensive).

**The "Perfect" (Staff-Level) Response:**
"I would implement a **Two-Stage Retrieval** pipeline:
1.  **Hybrid Search:** Combine Dense Vector Search (semantic) with Sparse BM25 Search (keyword). This captures specific terms (like 'Error 404' or 'Project X-15') that vectors often wash out.
2.  **Re-ranking:** Retrieve the top 50 candidates using a fast ANN index, then pass them through a **Cross-Encoder model (e.g., BGE-Reranker)**. Unlike Bi-Encoders, Cross-Encoders look at the query and document simultaneously to produce a high-precision relevancy score.
3.  **Context Filtering:** I'd analyze if our chunking strategy is cutting off vital context. I might implement **Small-to-Big Retrieval**, where we search small chunks but feed the surrounding 'parent' context to the LLM."

---

### Critical Trade-off Questions

**Q: Should we use a dedicated VDB (Pinecone, Milvus, Weaviate) or a Vector Plugin (pgvector for Postgres)?**
*   **The Trade-off:**
    *   **pgvector:** Best for **Data Consistency**. If your metadata (user permissions, timestamps) changes constantly, you want ACID compliance. One less system to manage.
    *   **Dedicated VDB:** Best for **Extreme Scale/Latency**. They are purpose-built for high-throughput vector workloads and offer features like "Filtered Search" at the index level, which is often faster than a SQL `WHERE` clause + Vector join.

**Q: How do you handle "Stale Data" in a RAG system?**
*   **The Depth:** Vectors are immutable. If a document is updated, you must re-embed and re-index.
*   **The Solution:** Implement a **Change Data Capture (CDC)** pipeline. When a doc changes in the primary DB, trigger an async worker to re-chunk, re-embed, and perform an upsert in the VDB. Use **Metadata Filtering** (e.g., `version_id` or `is_active: true`) to ensure the LLM never sees outdated chunks.

---

### Key Metrics to Track (The "Evaluation" Piece)
If you don't mention evaluation, you haven't built this in production.
*   **Faithfulness:** Does the answer actually come from the retrieved context?
*   **Answer Relevance:** Does the answer address the query?
*   **Context Precision:** Are the retrieved chunks actually useful?
*   **Tooling:** Mention **RAGAS** or **TruLens** for automated evaluation of these metrics.

---
**Interviewer's Final Tip:** When designing RAG systems, always prioritize **Retrieval Quality** over **LLM Power**. A GPT-4 model fed garbage data will perform worse than a GPT-3.5 model fed perfectly curated, re-ranked context.