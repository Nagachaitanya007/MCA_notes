---
title: Technical Interview Guide: Vector Databases & RAG
date: 2026-05-09T04:31:32.027498
---

# Technical Interview Guide: Vector Databases & RAG
**Role Context:** Senior Staff Engineer / FAANG Interviewer  
**Topic:** Vector DBs, Neural Search, and Retrieval-Augmented Generation (RAG)

---

## 🧱 1. The Core Concept (Basics Refresh)

In a traditional RDBMS, we query for **exact matches**. In a Vector Database, we query for **semantic intent**.

### The RAG Flywheel
Retrieval-Augmented Generation (RAG) solves the two primary failures of LLMs: **Hallucination** and **Knowledge Cutoffs**. 

1.  **Ingestion:** Documents are broken into **Chunks**.
2.  **Embedding:** A neural network (e.g., `text-embedding-3-small`) transforms chunks into high-dimensional vectors (arrays of floats).
3.  **Storage:** Vectors are stored in a specialized index.
4.  **Retrieval:** At query time, the user prompt is embedded. We perform an **Approximate Nearest Neighbor (ANN)** search to find the most similar vectors.
5.  **Augmentation:** The retrieved text is stuffed into the LLM prompt as "Context."
6.  **Generation:** The LLM synthesizes an answer based *only* on the provided context.

### The Math of Similarity
*   **Cosine Similarity:** Measures the angle between vectors. Preferred when magnitude doesn't matter (common in NLP).
*   **Euclidean Distance (L2):** Measures the straight-line distance. Sensitive to magnitude.
*   **Dot Product:** Faster to compute; used if vectors are normalized.

---

## ⚙️ 2. Under the Hood (Internal Mechanics)

As a Senior Engineer, you aren't just "using" a Vector DB; you are optimizing its retrieval performance and memory footprint.

### Indexing Algorithms (The "Magic")
Brute force $O(N)$ search is impossible at scale. We use **ANN (Approximate Nearest Neighbor)**:

1.  **HNSW (Hierarchical Navigable Small Worlds):** The industry gold standard. It creates a multi-layered graph where the top layers have fewer nodes (long-distance "express" jumps) and the bottom layers have all nodes (short-distance "local" hops).
    *   *Trade-off:* High memory consumption (graph pointers) but extremely fast $O(\log N)$ search.
2.  **IVF (Inverted File Index):** Segments the vector space into Voronoi cells using k-means clustering. You only search the centroids closest to your query.
    *   *Trade-off:* Smaller memory footprint than HNSW, but "Boundary Effects" can lead to lower recall.
3.  **PQ (Product Quantization):** A compression technique that breaks high-dimensional vectors into sub-vectors and quantizes them.
    *   *Why it matters:* Can reduce a 100GB index to 10GB with minimal accuracy loss.

### The "Hybrid Search" Imperative
Pure vector search often fails on **Product IDs, Acronyms, or Specific Names**. 
*   **Keyword Search (BM25):** Good for exact term matching.
*   **Vector Search:** Good for semantic meaning.
*   **Reciprocal Rank Fusion (RRF):** A mathematical way to combine results from both to get the "Best of both worlds."

---

## ⚠️ 3. The Interview Warzone

### Scenario: "Our RAG system is retrieving the wrong information. How do you debug it?"
**The Probing Pattern:** I look for your ability to isolate the **Retrieval** vs. **Generation** stages.

*   **The Perfect Response:** "First, I decouple the pipeline. I'd calculate **Precision@K** and **Recall@K** for the retrieval step using a 'Golden Dataset.' If retrieval is fine but the answer is wrong, it’s a **Context Window** or **LLM hallucination** issue. If retrieval is poor, I’d investigate:
    1.  **Chunking Strategy:** Are chunks too small (losing context) or too large (noise)? 
    2.  **Embedding Mismatch:** Is the model used for indexing the same as the one used for the query?
    3.  **Lack of Domain Adaptation:** Generic embeddings (OpenAI) often fail on niche medical or legal jargon. I might need to fine-tune an embedding model or use a **Cross-Encoder** for re-ranking."

### Scenario: "How do you handle 'Data Freshness' in a Vector DB with 100M documents?"
**The Probing Pattern:** Can you handle the architectural pain of HNSW?

*   **The Technical Deep-Dive:** "HNSW indexes are notoriously difficult to update incrementally because deleting nodes breaks graph links. To handle 100M documents with high churn:
    *   I’d implement a **Lambda Architecture** for vectors: A small, high-speed 'Fresh Index' (Flat/Exact) for recent writes, merged periodically into a large 'Static Index' (HNSW/IVF).
    *   I’d use **Metadata Filtering** to ensure deleted documents are filtered out at query time even if they still exist in the index."

### Scenario: "We are running out of RAM on our Vector nodes. What's your move?"
**The Probing Pattern:** Cost-optimization and scaling.

*   **The Perfect Response:** "I have three levers:
    1.  **Quantization:** Move from `float32` to `int8` or use Product Quantization (PQ). This can reduce memory by 4x.
    2.  **Dimensionality Reduction:** Use PCA (Principal Component Analysis) to reduce a 1536-dim vector to 768-dim if the loss in variance is acceptable.
    3.  **Storage Tiers:** Move to a Vector DB that supports **Disk-based Indexing** (like DiskANN). We keep the graph in memory but the actual vectors on NVMe SSDs."

---

## 💡 Pro-Tips for FAANG Interviews
1.  **Don't ignore Chunking:** Everyone talks about models; Senior engineers talk about chunking strategies (Sliding window, Semantic chunking, Recursive character splitting).
2.  **Mention Re-ranking:** A common pattern is to retrieve 100 candidates with a fast "Bi-Encoder" (Vector DB) and then use a slow, expensive "Cross-Encoder" to re-rank the top 10 for maximum accuracy.
3.  **Know your Evaluation:** Mention **RAGAS** (Faithfulness, Answer Relevance, Context Precision) or **TruLens**. You cannot improve what you cannot measure.
4.  **Multi-Vector Strategy:** Explain that storing one vector per document is often worse than storing multiple vectors per document (e.g., one for the summary, one for each paragraph).