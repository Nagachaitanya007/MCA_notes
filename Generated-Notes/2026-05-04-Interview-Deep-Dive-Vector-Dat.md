---
title: Interview Deep Dive: Vector Databases & RAG
date: 2026-05-04T04:31:23.518227
---

# Interview Deep Dive: Vector Databases & RAG
**Level:** Senior Staff / Principal Engineer (FAANG Focus)

---

## 🧱 1. The Core Concept (Basics Refresh)

In a FAANG-level interview, "basics" isn't just defining terms; it’s understanding the *raison d'être* of the technology.

### Retrieval Augmented Generation (RAG)
LLMs have two types of knowledge:
1.  **Parametric:** Knowledge learned during training (baked into weights). High cost to update (fine-tuning).
2.  **Non-Parametric:** Knowledge provided at inference time (context window). Low cost to update.

**RAG** is the architecture that bridges these two. It retrieves relevant document chunks from an external corpus and injects them into the LLM's prompt. This solves three critical LLM failures: **Hallucinations**, **Stale Data**, and **Lack of Private/Internal Context.**

### Vector Databases
A Vector DB is not just a storage layer; it is a **Similarity Search Engine**. Unlike relational databases (B-Trees for exact matches) or Search Engines (Inverted Indices for keyword matches), Vector DBs operate on **Approximate Nearest Neighbor (ANN)** search in high-dimensional embeddings.

---

## ⚙️ 2. Under the Hood (Internal Mechanics)

As a Senior Engineer, you must explain the transition from $O(N)$ brute-force search to $O(\log N)$ or $O(1)$ approximation.

### The Embedding Pipeline
Text is transformed into a vector (e.g., 768 or 1536 dimensions) using a model like `text-embedding-3-small`. 
*   **The Goal:** Position semantically similar items close together in vector space.
*   **The Metric:** Cosine Similarity (angle), Euclidean Distance (L2), or Inner Product. *Note: For normalized vectors, Cosine and L2 are mathematically equivalent in ranking.*

### The Indexing Algorithms (The "Secret Sauce")
This is where 90% of technical interviews drill down.

1.  **IVF (Inverted File Index):**
    *   **Mechanism:** Uses K-Means to partition the vector space into Voronoi cells.
    *   **Search:** Only searches the centroids closest to the query vector.
    *   **Trade-off:** High memory efficiency, but "boundary effects" can lead to lower recall.

2.  **HNSW (Hierarchical Navigable Small World):**
    *   **Mechanism:** A multi-layered graph where the top layer has few nodes (long-distance "express" links) and bottom layers have many nodes (short-distance "local" links).
    *   **Search:** Greedy traversal from top to bottom.
    *   **Trade-off:** The industry gold standard. Fastest retrieval and highest recall, but extremely memory-intensive (graph pointers take up massive RAM).

3.  **PQ (Product Quantization):**
    *   **Mechanism:** Compression. It breaks a high-dimensional vector into sub-vectors and quantizes them into a "codebook."
    *   **Trade-off:** Drastically reduces memory footprint (e.g., 10x-20x), but introduces "precision loss" in distance calculation.

---

## ⚠️ 3. The Interview Warzone

### Scenario A: "Our RAG system is hallucinating even though the data is in the DB. How do you fix it?"
**Probing Pattern:** The interviewer is testing your understanding of the "Retrieval Gap."

*   **The Perfect Response:** "I’d audit the pipeline in three stages: **Chunking, Retrieval, and Ranking.**"
    *   **Chunking:** Are we cutting off mid-sentence? I'd implement *Semantic Chunking* or *Recursive Character Splitting* with overlap.
    *   **Retrieval:** Is the embedding model aligned with the domain? I’d check if the Top-K results are actually relevant.
    *   **Re-ranking:** Vector search is good at 'broad' similarity but bad at 'precision.' I’d introduce a **Cross-Encoder Re-ranker** (like Cohere or BGE) to re-evaluate the Top-50 results from the vector search before passing them to the LLM.

### Scenario B: "How do you handle 'Hybrid Search' at scale?"
**Probing Pattern:** Do you understand that vectors aren't a silver bullet?

*   **The Perfect Response:** "Pure vector search fails on specific keyword queries (e.g., 'Project code XJ-99'). I would implement a **Hybrid Search** architecture combining **Dense Embeddings** (HNSW) and **Sparse Embeddings** (BM25/inverted index). I’d then use **Reciprocal Rank Fusion (RRF)** to merge the scores from both systems into a single ranked list."

### Scenario C: "We have 1 billion vectors. We can't afford the RAM for HNSW. What now?"
**Probing Pattern:** Testing cost-engineering and architectural trade-offs.

*   **The Perfect Response:** "At billion-scale, HNSW on RAM is economically unviable. I’d suggest:
    1.  **Disk-based Indexing:** Using algorithms like **DiskANN** which use VOD (Vector on Disk) techniques, keeping only the graph structure in RAM and vectors on NVMe.
    2.  **Scalar Quantization (SQ):** Moving from `float32` to `int8` to reduce memory by 4x with minimal recall loss.
    3.  **Sharding:** Partitioning the index by metadata (e.g., `user_id` or `org_id`) so we only search a subset of the billion vectors."

---

## 💡 Senior Staff Pro-Tips

*   **Metadata Filtering:** Don't forget that most RAG queries involve filters (e.g., "Find docs from *2023*"). Explain the difference between **Pre-filtering** (brute force on metadata first), **Post-filtering** (search first, then filter—risks returning 0 results), and **In-index filtering** (the modern standard).
*   **The "Lost in the Middle" Problem:** Mention that LLMs struggle with very long contexts. If you provide 50 chunks, the LLM ignores the ones in the middle. The solution is better **Context Distillation** or **Long-Context models**.
*   **Evaluation:** Never finish an interview without mentioning metrics. Use **RAGAS** (Faithfulness, Answer Relevance, Context Precision) or **TruLens** to quantify performance rather than "vibes."

---

**Summary for the Board:** 
*"A Vector DB is a trade-off engine. If you want speed, you sacrifice RAM (HNSW). If you want scale, you sacrifice precision (PQ). If you want accuracy, you sacrifice latency (Re-ranking)."*