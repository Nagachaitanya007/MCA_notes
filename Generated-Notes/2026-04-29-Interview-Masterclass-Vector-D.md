---
title: Interview Masterclass: Vector Databases & RAG
date: 2026-04-29T04:31:26.796997
---

# Interview Masterclass: Vector Databases & RAG
**Role:** Senior Staff Engineer / Hiring Committee Lead  
**Topic:** Vector Databases & Retrieval-Augmented Generation (RAG)

---

## 🧱 1. The Core Concept (Basics Refresh)

In the FAANG context, we don't care if you can call an API. We care if you understand the **information theory** and **system trade-offs** behind the buzzwords.

### What is RAG?
RAG solves the "Static Knowledge" and "Hallucination" problems of LLMs. Instead of relying solely on the model's weights (parametric memory), we provide it with a "closed-book" exam turned "open-book" by injecting relevant context into the prompt (non-parametric memory).

### The Lifecycle of a Vector
1.  **Chunking:** Breaking a 100MB PDF into manageable pieces (e.g., 512 tokens).
2.  **Embedding:** Passing text through an Encoder (like BERT or OpenAI `text-embedding-3`) to produce a high-dimensional vector (e.g., 1536 dimensions). This vector represents the **semantic essence** of the text.
3.  **Indexing:** Storing these vectors in a specialized database.
4.  **Retrieval:** At query time, the user’s question is embedded into the same vector space. We find the "nearest neighbors" (most similar chunks).
5.  **Generation:** The LLM receives the chunks + the user question and synthesizes an answer.

---

## ⚙️ 2. Under the Hood (Internal Mechanics & Architecture)

As a Staff Engineer, you must look past the "wrapper." You need to understand how we search across millions of 1536-dimensional vectors in sub-100ms.

### A. Approximate Nearest Neighbor (ANN) Algorithms
Brute-force (K-Nearest Neighbors) is $O(N \cdot D)$. At scale, this is a death sentence. We use **ANN** to trade a tiny bit of accuracy (recall) for massive speed.

*   **HNSW (Hierarchical Navigable Small World):** The current gold standard. It creates a multi-layered graph where the top layers are "expressways" (long distances) and bottom layers are "local streets." Search is $O(\log N)$.
*   **IVF (Inverted File Index):** Uses K-Means clustering to partition the vector space into Voronoi cells. We only search the closest clusters.
*   **Product Quantization (PQ):** A compression technique. It breaks a large vector into sub-vectors and quantizes them, reducing memory footprint by 90% at the cost of precision.

### B. Similarity Metrics
Choose your weapon based on your embedding model:
*   **Cosine Similarity:** Measures the angle between vectors. Ignores magnitude. Best for NLP where text length varies.
*   **Euclidean Distance (L2):** Measures the straight-line distance. Sensitive to magnitude.
*   **Dot Product:** Faster to calculate; if vectors are normalized, it's equivalent to Cosine.

### C. The "Metadata Filtering" Problem
One of the hardest engineering challenges in Vector DBs.
*   **Pre-filtering:** Filter by metadata (e.g., `user_id=123`) then search vectors. *Risk:* You might filter out so many results that the ANN graph becomes disconnected.
*   **Post-filtering:** Search vectors then filter. *Risk:* You might find 100 neighbors, but none belong to `user_id=123`.
*   **Modern Solution:** **Filtered HNSW/Single-stage filtering**. Maintaining a bitmask during the graph traversal.

---

## ⚠️ 3. The Interview Warzone

In a Senior/Staff interview, I will push you on **failure modes** and **scale**.

### Scenario: "Our RAG system is retrieving the wrong documents. Walk me through your debugging stack."

#### 🛑 The "Junior" Response:
"I would try a better embedding model or increase the `k` value in my search."

#### ✅ The "Staff" (Perfect) Response:
"I would analyze the failure at three distinct layers:
1.  **The Embedding/Retrieval Gap:** Are the queries and documents in the same semantic space? I’d implement **HyDE (Hypothetical Document Embeddings)**—where the LLM generates a fake answer first, and we use *that* to search, reducing the 'question-to-statement' distance.
2.  **Chunking Strategy:** Is the context being cut off mid-sentence? I’d move to **Recursive Character Splitting** with overlap or **Semantic Chunking**.
3.  **The Precision vs. Recall Trade-off:** I’d introduce a **Two-Stage Retrieval** pipeline. Use a fast, low-precision Vector Search to get the top 100, then use a **Cross-Encoder Re-ranker** (like BGE-Reranker) to select the top 5. Cross-encoders are too slow for the whole DB but incredibly accurate for a small set."

---

### Probing Question: "When should we use a Vector DB vs. just adding a vector plugin to Postgres (pgvector)?"

**The Trade-off Analysis:**
*   **Choose PGVector/ElasticSearch if:** You already have the data there. You need strong ACID compliance. Your scale is < 1M vectors. You need complex relational joins + vector search in one query.
*   **Choose a Dedicated Vector DB (Pinecone, Milvus, Weaviate) if:** You are at 'Internet Scale' (>10M+ vectors). You need sub-50ms latency for specialized ANN indexes (HNSW) that Postgres might struggle to optimize under high concurrency. You need features like automatic index sharding and separation of compute/storage.

---

### The "Curveball" Question: "How do you handle 'Data Freshness' in a high-throughput RAG system?"

**Key points to hit:**
1.  **Consistency:** Vector indexes (especially HNSW) are expensive to rebuild. Explain the "Buffer and Merge" strategy—storing new vectors in a small flat index (SSTable style) and merging them into the HNSW graph asynchronously.
2.  **TTL (Time to Live):** How do you expire old data without leaving "holes" in the graph that degrade search performance?
3.  **Versioning:** Ensuring the embedding model version used for the index matches the one used for the incoming query.

---

### Final Pro-Tip for the Candidate:
Always mention **Observability**. Talk about tracking **"Context Precision"** and **"Context Recall."** Use the **RAGAS framework** or **TruLens** as keywords. It shows you've actually shipped these systems to production, not just played with a Jupyter notebook.