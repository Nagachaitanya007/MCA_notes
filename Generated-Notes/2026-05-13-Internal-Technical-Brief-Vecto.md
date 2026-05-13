---
title: Internal Technical Brief: Vector Databases & RAG
date: 2026-05-13T04:31:37.116323
---

# Internal Technical Brief: Vector Databases & RAG
**To:** Engineering Candidates (L6/L7)  
**From:** Senior Staff Engineer / Interview Panel Lead  
**Subject:** Mastering Vector-Based Architectures and Retrieval Augmented Generation

---

## 🧱 1. The Core Concept (Basics Refresh)

In traditional systems, we query data using **exact matches** (SQL) or **keyword frequency** (BM25). In the era of LLMs, we query based on **semantic intent**.

### The Vector Database (VDB)
A VDB doesn't store data in tables; it stores data as **embeddings**—mathematical representations of meaning in high-dimensional space (typically 768 to 1536 dimensions). 
*   **The Goal:** To find the "Nearest Neighbors" of a query vector.
*   **The Shift:** We move from "Does this document contain the word 'Apple'?" to "Is this document semantically close to the concept of 'consumer electronics'?"

### RAG (Retrieval Augmented Generation)
LLMs have two major flaws: **Knowledge Cutoffs** and **Hallucinations**. 
RAG solves this by decoupling the **Knowledge Base** from the **Reasoning Engine**.
1.  **Retrieval:** Fetch relevant context from a VDB based on the user query.
2.  **Augmentation:** Prepended the retrieved text to the user's prompt.
3.  **Generation:** The LLM synthesizes an answer based *only* on the provided context.

---

## ⚙️ 2. Under the Hood (Internal Mechanics)

As a Senior Engineer, you must understand the trade-offs in **Indexing** and **Retrieval**.

### A. Approximate Nearest Neighbor (ANN) Algorithms
Searching through 100 million vectors linearly ($O(N)$) is too slow for production. We use ANN to trade a tiny bit of accuracy for massive speed gains ($O(\log N)$).

1.  **HNSW (Hierarchical Navigable Small World):**
    *   **Mechanism:** Creates a multi-layered graph. The top layer has few nodes (long-distance jumps); bottom layers have many nodes (short-distance precision).
    *   **Trade-off:** High memory consumption (stores the graph in RAM) but extremely fast and high recall.
2.  **IVF (Inverted File Index):**
    *   **Mechanism:** Uses K-Means clustering to partition the vector space into Voronoi cells. It only searches the most relevant clusters.
    *   **Trade-off:** Lower memory footprint than HNSW, but slower query speeds and potential for "missing" the best result if it's on a cluster boundary.
3.  **PQ (Product Quantization):**
    *   **Mechanism:** Compresses vectors by breaking them into sub-vectors and quantizing them.
    *   **Trade-off:** Reduces memory usage by 90%, but introduces "lossy" precision.

### B. Distance Metrics: Choosing the Ruler
*   **Cosine Similarity:** Measures the *angle* between vectors. Standard for NLP because it ignores document length/magnitude.
*   **L2 (Euclidean):** Measures the *straight-line distance*. Useful for image search or normalized embeddings.
*   **Inner Product:** Used if the magnitude of the vector conveys importance (e.g., recommendation systems).

### C. The RAG Pipeline Architecture
*   **Chunking Strategy:** You cannot embed a 100-page PDF as one vector. You must use **Recursive Character Splitting** or **Semantic Chunking**.
*   **Overlapping:** Chunks should overlap (e.g., 512 tokens with a 50-token overlap) to ensure context isn't lost at the "seam" of a cut.

---

## ⚠️ 3. The Interview Warzone

In a FAANG interview, I won't ask "What is RAG?" I will ask "Why is your RAG system failing in production?"

### Scenario 1: The "Irrelevant Context" Problem
**Interviewer:** "Your RAG system is retrieving chunks, but the LLM is still hallucinating or saying 'I don't know.' How do you debug this?"

*   **The Probing Pattern:** They are testing if you understand the difference between **Retrieval Failure** and **Generation Failure**.
*   **The Perfect Response:** "I would first decouple the evaluation. 
    1.  **Check Retrieval (Recall):** Did the top-k results actually contain the answer? If not, I need to look at my **embedding model** or **chunking strategy**. I might implement **Hybrid Search** (combining Vector + Keyword/BM25) because vector search is poor at finding specific serial numbers or acronyms.
    2.  **Check Generation:** If the context was correct but the answer was wrong, I need to look at the **Prompt Engineering**, **Context Window limits**, or use a **Re-ranker** (like Cohere) to ensure the most relevant context is at the top, avoiding the 'Lost in the Middle' phenomenon."

### Scenario 2: Scaling to 1 Billion Vectors
**Interviewer:** "We need to build a semantic search for every public tweet. How do you handle the scale?"

*   **The Probing Pattern:** Testing knowledge of distributed systems and memory management.
*   **The Perfect Response:** "At billion-scale, raw HNSW will bankrupt us on RAM costs. I would implement:
    1.  **IVF-PQ Indexing:** Cluster the space and compress the vectors to keep the index size manageable.
    2.  **Horizontal Sharding:** Partition the index by user ID or timestamp across multiple nodes.
    3.  **Tiered Storage:** Keep the most frequently accessed vectors in memory (hot) and move older ones to disk-based indices like **DiskANN**."

### Scenario 3: The Multi-Tenancy/Security Trap
**Interviewer:** "How do you ensure User A doesn't retrieve User B’s private documents in a RAG system?"

*   **The Probing Pattern:** Testing your understanding of Metadata Filtering.
*   **The Perfect Response:** "Vector databases support **Metadata Filtering**. Every vector should be stored with an `org_id` or `user_id` attribute. We apply a 'Hard Filter' during the ANN search so the algorithm only traverses nodes matching the authorized ID. Doing this *post-retrieval* is a security risk and inefficient; it must be done *during* the search."

### Key Trade-offs to Mention (The "Senior" Signal):
*   **Freshness vs. Speed:** Real-time upserts in HNSW are expensive because you have to rebuild graph edges. For high-velocity data, consider a 'Buffer' index.
*   **Embedding Model Drift:** If you upgrade your embedding model, you **must** re-index your entire database. You cannot compare vectors generated by different models.

---

**Final Tip for the Candidate:** When in doubt, talk about **Data Quality**. A RAG system is only as good as its chunks. If the data is garbage, the embeddings will be garbage, and the LLM will provide "confident garbage."