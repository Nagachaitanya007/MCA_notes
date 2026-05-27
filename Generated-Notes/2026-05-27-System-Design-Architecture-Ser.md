---
title: System Design & Architecture Series: Vector Databases & RAG
date: 2026-05-27T04:31:51.764981
---

# System Design & Architecture Series: Vector Databases & RAG
**Author:** Senior Staff Engineer & Expert FAANG Interviewer  
**Target Audience:** L6+ (Staff+) System Design candidates and AI/Platform Engineers  

---

## 🧱 1. The Core Concept (Basics Refresh)

To design high-performance Retrieval-Augmented Generation (RAG) pipelines at scale, we must first understand the fundamental paradigms shift from traditional keyword search to semantic dense vector search.

```
+---------------------------------------------------------------------------------+
|                                 THE RAG TRIAD                                   |
+--------------------------+----------------------------+-------------------------+
|        RETRIEVAL         |        AUGMENTATION        |       GENERATION        |
|  Fetch relevant context  |   Inject context context   |  Generate output using  |
|   from Vector DB/BM25    |    into LLM Prompt Temp    |   augmented context     |
+--------------------------+----------------------------+-------------------------+
```

### Keyword (Sparse) vs. Semantic (Dense) Search

| Dimension | Sparse Search (e.g., BM25 / Elasticsearch) | Dense Search (Vector Search) |
| :--- | :--- | :--- |
| **Representation** | High-dimensional, highly sparse vectors ($V \approx 10^5$ to $10^6$ dimensions where most values are 0). | Low-dimensional, highly dense vectors ($d \approx 1536$ to $4096$ floats, all non-zero). |
| **Algorithm** | Term frequency-inverse document frequency (TF-IDF), BM25 scoring based on exact token matches. | Nearest Neighbor search ($k$-NN) in continuous vector spaces. |
| **Semantic Matching** | Fails on synonymy ("automobile" vs. "car") and polysemy ("bank" of a river vs. financial "bank") without extensive synonym mapping. | Captures semantic context, intent, and conceptual relationships encoded by the embedding model. |
| **Storage & Cost** | Inverted indices; highly optimized, cheap disk-bound storage with fast lookups. | RAM-heavy indices (e.g., graphs, trees); expensive memory footprint. |

### Parametric vs. Non-Parametric Memory
*   **Parametric Memory:** The internal weights of the LLM, frozen during pre-training/fine-tuning. It contains broad, static general knowledge but is prone to hallucinations, cannot access private data, and has a fixed knowledge cutoff.
*   **Non-Parametric Memory:** An external, dynamic, and queryable data store (e.g., Vector DB, relational database). RAG acts as the bridge, dynamically loading non-parametric data into the LLM's short-term working memory (the context window) at query time.

---

## ⚙️ 2. Under the Hood (Internal Mechanics & Architecture)

### A. Distance Metrics: The Mathematical Core
Vector search relies on measuring the distance or similarity between two vectors $\mathbf{u}, \mathbf{v} \in \mathbb{R}^d$.

```
           Cosine Similarity (θ)                   Euclidean Distance (L2)
                
                  ^  v                                     ^  v
                 / \                                      /| 
                /   \                                    / | 
               /  θ  \                                  /  | d(u,v)
              /_______\                                /   | 
             o         u                              o----+----> u
         (Measures Direction)                      (Measures Magnitude & Direction)
```

#### 1. Euclidean Distance ($L_2$)
$$d(\mathbf{u}, \mathbf{v}) = \sqrt{\sum_{i=1}^d (u_i - v_i)^2}$$
*   **Usage:** Best when vector magnitude is physically meaningful (e.g., physical coordinates, sensory data). Highly sensitive to scaling.

#### 2. Dot Product (Inner Product / IP)
$$\mathbf{u} \cdot \mathbf{v} = \sum_{i=1}^d u_i v_i$$
*   **Usage:** Best when vectors are normalized ($||\mathbf{u}|| = 1$). If normalized, Dot Product is equivalent to Cosine Similarity but avoids the division step, making it extremely fast to calculate.

#### 3. Cosine Similarity
$$\text{sim}(\mathbf{u}, \mathbf{v}) = \frac{\mathbf{u} \cdot \mathbf{v}}{\|\mathbf{u}\| \|\mathbf{v}\|}$$
*   **Usage:** Standard when document lengths vary. It measures only the angle between vectors, ignoring magnitude differences.

---

### B. Indexing Algorithms (The Core Bottleneck)
Exact $k$-Nearest Neighbor ($k$-NN) search requires $O(N \cdot d)$ computations, where $N$ is corpus size and $d$ is dimensionality. At scale ($N > 10^7$), this latency is unacceptable ($>1$ second). We bypass this with **Approximate Nearest Neighbor (ANN)** search algorithms, trading small accuracy drops for $O(\log N)$ or $O(1)$ search latencies.

```
       [FLAT]                  [IVF]                    [HNSW]                    [PQ]
  Linear Scan (O(N))       Inverted File           Hierarchical Graph          Quantization
   ________________     ___  ___  ___  ___        Layer 2: o----o          Original: [3.1, -1.2, 0.5, 9.4]
  | *  *  *  *  *  |   | o || o || o || o |       Layer 1: o--o--o--o                 | (Split & Match)
  | *  *  (q) *  * |   |___||___||___||___|       Layer 0: o-o-o-o-o-o     Compressed: [ 0x1A, 0xF4 ] (2 bytes)
  |_*__*__*__*__*__|     Cluster Buckets
```

---

#### 1. IVF (Inverted File Index)
IVF partitions the vector space into Voronoi cells using $K$-Means clustering.

```
            +-------------------------+
            |      Voronoi Cell A     |
            |     x      x            |
            |         * (Centroid A)  |
            |     x       x           |
            +------------+------------+
                         /
     Query (q) -------->/  (Distance evaluated only against Centroids)
                        \
            +------------+------------+
            |      Voronoi Cell B     |
            |  y      y               |
            |       * (Centroid B)    |
            |    y       y            |
            +-------------------------+
```

*   **How it works:**
    1.  At index construction, run $K$-means to define $C$ centroids.
    2.  Map every database vector to its nearest centroid, creating an *inverted list* (bucket) for each centroid.
    3.  At query time, calculate the distance between query $q$ and all $C$ centroids.
    4.  Select the closest $n_{probe}$ centroids, and perform an exact scan *only* on the vectors inside those specific buckets.
*   **Trade-off parameter ($n_{probe}$):** Higher $n_{probe}$ increases recall (accuracy) but increases latency. Lower $n_{probe}$ is faster but risks missing the true nearest neighbors if they fall just across a Voronoi boundary.

---

#### 2. HNSW (Hierarchical Navigable Small World)
The gold standard for production vector search. HNSW is a multi-layer graph-based index inspired by skip-lists.

```
Layer 2 (Express)      [Entry]---------------------------> (Node B)
                                                            |
                                                            v
Layer 1 (Local)        [Node A]-------------> (Node C)---> (Node B)
                                               |            |
                                               v            v
Layer 0 (All Nodes)    [Node A]-> (Node D)-> (Node C)->   (Node B)
```

*   **How it works:**
    1.  **Layer Hierarchy:** The top layers have sparse connections and long-distance links. The bottom layer (Layer 0) contains all vectors with short-distance connections.
    2.  **Greedy Routing:** Query starts at an entry point in the top layer. It greedily traverses the graph (moving to neighbors closer to the query) until it reaches a local minimum. It then drops down to the next layer and resumes the search from that node.
*   **Key Construction Parameters:**
    *   $M$: The maximum number of bidirectional outgoing links per node. High $M$ improves recall on high-dimensional data but increases index memory consumption exponentially.
    *   $efConstruction$: The size of the dynamic candidate list evaluated during index construction. Higher values increase build time but yield optimal graph connectivity.
    *   $efSearch$: The size of the dynamic candidate list evaluated during query execution. Raising $efSearch$ at runtime increases recall at the cost of latency.
*   **Pros/Cons:** Extremely low latency ($<5$ms) and exceptional recall. However, it is **highly memory intensive** because the graph pointers must reside in RAM to maintain speed.

---

#### 3. PQ (Product Quantization)
A lossy compression technique that dramatically reduces memory footprint by compressing high-dimensional vectors.

```
Original Vector (1024 dimensions, FP32 = 4096 bytes)
[ v_1, v_2, ..., v_128 | v_129, ..., v_256 | ... | v_897, ..., v_1024 ]
  \_________________/    \_______________/         \________________/
     Sub-vector 1           Sub-vector 2              Sub-vector 8

Each sub-vector is mapped to the index of its nearest Centroid (Codebook)
  [   Centroid #42   ]    [  Centroid #101 ]         [  Centroid #12  ]
        (1 byte)               (1 byte)                  (1 byte)

Compressed Representation (8 bytes total - 512x compression)
[ 0x2A, 0x65, ..., 0x0C ]
```

*   **How it works:**
    1.  Divide a $D$-dimensional vector space into $m$ orthogonal sub-spaces of dimension $d' = D/m$.
    2.  For each sub-space, run $K$-means clustering to generate a codebook containing $K^*$ centroids (typically $K^*=256$, so each centroid ID fits in 1 byte / 8 bits).
    3.  Represent any vector as an $m$-byte array, where each byte is the index of the nearest centroid in that sub-space.
*   **Asymmetric Distance Computation (ADC):** At query time, the query vector $q$ is *not* compressed. The distance from the uncompressed query $q$ to all compressed database vectors is computed efficiently using lookup tables populated on-the-fly, avoiding costly decompression steps.

---

### C. Hybrid Search & Re-ranking
Production systems rarely rely solely on vector search. To achieve high precision, modern architectures leverage **Hybrid Search**:

```
                  +-----------------+
                  |   User Query    |
                  +--------+--------+
                           |
           +---------------+---------------+
           |                               |
           v                               v
  +------------------+           +------------------+
  | Dense Retrieval  |           | Sparse Retrieval |
  |   (Vector DB)    |           |   (Elastic/BM25) |
  +--------+---------+           +---------+--------+
           |                               |
  Top-K Dense Results             Top-K Sparse Results
           |                               |
           +---------------+---------------+
                           |
                           v
              +-------------------------+
              | Reciprocal Rank Fusion  |
              |         (RRF)           |
              +------------+------------+
                           |
                     Fused Top-M
                           |
                           v
              +-------------------------+
              |      Cross-Encoder      |
              |       (Re-ranker)       |
              +------------+------------+
                           |
                     Top-N Results
                           v
                     To LLM Prompt
```

1.  **Reciprocal Rank Fusion (RRF):** An algorithm that merges the ranked lists of sparse and dense retrievers without requiring calibrated scores.
    $$RRF(d) = \sum_{m \in M} \frac{1}{k + r_m(d)}$$
    Where $M$ is the set of retrievers, $r_m(d)$ is the rank of document $d$ in retriever $m$, and $k$ is a constant (typically $\approx 60$) that smooths the impact of low-ranked items.
2.  **Cross-Encoder Re-ranking:** Bi-encoders (used to generate embeddings) output separate representations for query and document, optimizing for retrieval speed. A **Cross-Encoder** feeds the query and document *simultaneously* into a deep Transformer, calculating full self-attention across both. This is computationally too expensive for millions of docs, but ideal for re-scoring the top 50–100 candidate documents returned by the hybrid search layer.

---

### D. CRUD Operations in Vector Databases
Handling dynamic updates in graph-based indices (like HNSW) is a major engineering bottleneck:
*   **Writes/Inserts:** New vectors must be linked into the multi-layer graph. This requires running a localized nearest-neighbor query for each write to determine optimal edge connections, making bulk writes slow.
*   **Deletes:** Removing a node directly breaks graph connectivity (leaving orphan nodes or disconnected sub-graphs).
    *   *Solution:* Most production vector DBs use **Tombstoning** (logical deletes). The node is flagged as deleted and ignored in search passes.
    *   *Garbage Collection:* During periodic asynchronous **Compaction**, tombstoned nodes are purged, and neighboring nodes are re-wired using specialized heuristics.

---

## ⚠️ 3. The Interview Warzone (Scenario-Based Questions)

This section maps directly to real-world System Design interview prompts. 

---

### Scenario 1: Memory Constraints at Scale
> **Interviewer:** *"We have $10^9$ (1 billion) vectors of size $d=1536$ (FP32). Our target latency is $<50\text{ms}$ at p99. How do you design the vector index? What is the cost and hardware profile?"*

#### 1. Probing & Math Check (Show your L6+ caliber)
First, calculate the raw vector payload size before indexing overhead.
$$\text{Raw Data Size} = 10^9 \times 1536 \text{ dimensions} \times 4 \text{ bytes (FP32)} = 6.144 \times 10^{12} \text{ bytes} \approx 6.14 \text{ TB}$$

*   If we use **pure HNSW**, the memory overhead is $\approx 1.2\times$ to $2\times$ the raw data size due to graph pointers (dependent on $M$). We would need **$12$ to $18\text{ TB}$ of RAM**.
*   At standard cloud pricing ($16\text{GB}$ RAM costs $\approx \$0.10/\text{hr}$), a $15\text{TB}$ RAM cluster would cost **$>\$90,000/\text{month}$** in memory costs alone.
*   **Conclusion:** Pure HNSW in RAM is cost-prohibitive. We must use quantization or disk-backed architectures.

#### 2. The Architectural Strategy (The Solution)
We will implement an **IVF-PQ (Inverted File with Product Quantization) index backed by SSDs (using a DiskANN-style pattern)**.

```
+---------------------------------------------------------------------------------+
|                                 IVF-PQ INDEX                                    |
|                                                                                 |
|   RAM (Fast Cache)                                                              |
|   +---------------------------------------+                                     |
|   | Centroids (coarse quantizer)          |                                     |
|   | PQ Codebooks                          |                                     |
|   +---------------------------------------+                                     |
|                                                                                 |
|   NVMe SSD (Persistent Store)                                                   |
|   +---------------------------------------+                                     |
|   | Inverted Lists (Compressed PQ vectors)| ----> [Asymmetric Distance Lookup]  |
|   | Raw Vectors (FP32)                    | ----> [Re-scoring of Top K]         |
|   +---------------------------------------+                                     |
+---------------------------------------------------------------------------------+
```

1.  **Quantization Strategy:** Compress vectors using PQ with $m=96$ sub-vectors. This reduces each vector from 1536 dimensions (6144 bytes) to 96 bytes (a **$64\times$ reduction**).
    *   Compressed dataset size: $10^9 \times 96 \text{ bytes} = 96 \text{ GB}$.
2.  **Indexing Strategy (IVF):** Build an IVF index with $C = 2^{16} = 65,536$ centroids. Keep the coarse centroid representation in RAM.
3.  **Physical Storage Engine:** Use a persistent SSD engine (like RocksDB or custom block files) to host the inverted lists containing the compressed PQ codes.
4.  **Optimized Retrieval Pipeline:**
    *   **Phase 1 (RAM):** Match query vector $q$ against the $65,536$ centroids to find the top $n_{probe} = 64$ closest buckets.
    *   **Phase 2 (SSD Direct I/O):** Fetch only the PQ-compressed arrays of vectors in those 64 buckets from SSD using highly concurrent asynchronous direct I/O.
    *   **Phase 3 (CPU):** Compute asymmetric distances using PQ lookups to extract the top $K=100$ candidate matches.
    *   **Phase 4 (Refinement - Optional):** Fetch the original uncompressed FP32 vectors for only these 100 candidates from SSD to perform exact L2/Cosine re-ranking.
5.  **Cost/Performance Impact:** Reduces RAM requirements from $12\text{ TB}$ to $<128\text{ GB}$ (fitting on a single standard cloud node), dropping infrastructure costs by over $90\%$ while keeping p99 latency around $25\text{-}40\text{ms}$.

---

### Scenario 2: The Hallucination & Citation Dilemma
> **Interviewer:** *"We deployed a production RAG system for internal financial records. Users report that the LLM is citing the correct source document but returning completely fabricated numbers that contradict the cited source. How do you systemically diagnose and resolve this?"*

#### 1. Systemic Diagnostics
This failure mode points to a breakdown in the **Augmentation & Generation** stages, or a failure in chunk structural integrity.

```
                    DIAGNOSTIC PATHWAY FOR RAG FAILURES
                    
     Is retrieval working? 
     [Compute Mean Reciprocal Rank (MRR) or NDCG on golden dataset]
               |
               +---> Bad Retrieval? 
               |     - Fix chunking strategy (overlapping, parent-child)
               |     - Implement metadata filtering (pre-filtering)
               |
               v (Yes, correct documents retrieved)
     Is the context corrupted/lost?
               |
               +---> Yes: "Lost in the Middle" phenomenon.
               |     - Re-order context: place high-relevance docs at outer edges.
               |     - Prune context: use LLM-Lingua/summarizers to decrease noise.
               |
               v (No, context is highly clean)
     Is the LLM ignoring context (Parametric Override)?
               |
               +---> Yes: Adjust Temperature to 0, harden prompt with strict instructions.
                     Deploy guardrails (NeMo, LlamaGuard) & RAG tri-evaluation.
```

#### 2. Architectural Remediation Plan

*   **Implement Parent-Child Chunking:** Do not pass raw embedding chunks directly to the LLM. Keep semantic vector chunks small (e.g., 256 tokens) to optimize retrieval accuracy, but map each chunk to its parent document (e.g., 2048 tokens containing the full financial table). Pass the larger parent context to the LLM to preserve structural coherence and numerical context.

```
  Parent Document (Full context / Tables / 2048 tokens)
  +-----------------------------------------------------------+
  |  Quarterly Report Q3 ... Revenue: $4.2B ... EBITDA: $1.2B |
  |  +------------------+  +------------------+               |
  |  | Chunk 1 (256 t)  |  | Chunk 2 (256 t)  |   ...         |
  |  +--------+---------+  +--------+---------+               |
  +-----------|---------------------|-------------------------+
              |                     |
              v (Retrieved)         v (Ignored during retrieval)
      Vector DB Search Matches Chunk 1 
      -> Fetch Parent Document 
      -> Send FULL Parent Context to LLM
```

*   **Mitigate "Lost in the Middle" Effect:** Deep learning architectures often focus on the beginning and end of input contexts, ignoring the middle. Structure the retrieved context such that the most critical chunks are injected at the absolute top and bottom of the context window, leaving less relevant chunks in the middle.
*   **Construct a Strict Evaluation Guardrail (The RAG Triad):** Instrument an evaluation engine (e.g., `Ragas` or custom LLM-as-a-judge pipelines) running asynchronously over user query logs to continuously monitor:
    1.  **Faithfulness:** Is the generated answer derived *solely* from the retrieved context? (Measures hallucination rate).
    2.  **Answer Relevance:** Does the generated answer address the user query?
    3.  **Context Precision:** Did the retrieval system fetch only relevant information, minimizing context noise?
*   **Enforce Hard Prompt Engineering & Schema Extraction:** Shift the LLM prompt from conversational to extraction-oriented:
    ```text
    You are a strict financial extraction system.
    Instructions:
    1. Answer the query ONLY using the provided Context.
    2. If the answer cannot be directly derived from the Context, output "ERROR: Context Insufficient".
    3. For every number you output, append an exact substring quote from the Context as a citation.
    ```

---

### Scenario 3: Real-Time Vector Updates
> **Interviewer:** *"We operate an e-commerce platform with 50 million products. Product prices, inventory status, and user ratings update continuously (thousands of writes per second). Our hybrid search must return fresh, in-stock products, reflecting current metadata in <30ms. How do you design the write path and metadata filtering?"*

#### 1. Probing & Bottleneck Analysis
*   **The Conflict:** High-write rates are the natural enemy of graph-based indexes (HNSW). If we update a product vector (e.g., because a price drop changed its embedding) directly in the HNSW index in real-time, we will bottleneck our write throughput and trigger constant, expensive CPU-intensive re-indexing loops.
*   **Metadata Filtering (Pre- vs. Post-Filtering):**
    *   *Post-Filtering (Bad):* Fetch Top-K vectors from HNSW, then discard out-of-stock items. If the top 100 matches are all out of stock, we return 0 results (known as the *search collapse* problem).
    *   *Pre-Filtering (Slow):* Match metadata constraints first (SQL `WHERE stock > 0`), but then we lose the ability to efficiently use our vector index if we have to scan the filtered subset linearly.

#### 2. The Architectural Strategy (The Solution)

```
                            THE WRITE PATH
                            
  [Update Event]
        |
        +---> Write-Ahead Log (WAL)
        |
        +---> Write to In-Memory MemTable (LSM-Tree Style Segment)
                   |
                   v (Saves immediate indexing penalty)
        [In-Memory Segment (Temporary Flat Index)]
```

We will build a **Segment-Based Lambda Architecture with Multi-Index Single-Query (Single-Searcher) execution, utilizing In-Engine Metadata Filtering**.

```
                           THE QUERY PATH

                         +----------------+
                         |  Search Query  |
                         +--------+-------+
                                  |
            +---------------------+---------------------+
            |                                           |
            v                                           v
   +------------------+                       +-------------------+
   |  In-Memory Seg.  |                       | Persistent Seg.   |
   | (Unindexed/Flat) |                       | (Immutable HNSW)  |
   +--------+---------+                       +---------+---------+
            |                                           |
            v                                           v
    Exact Filter & Scan                         Bitmap Pre-filtered 
      (Fast for <10K docs)                         HNSW Search
            |                                           |
            +---------------------+---------------------+
                                  |
                                  v
                            Merged Results
```

1.  **Segmented Storage Architecture (LSM-Tree Inspired):**
    *   Do not maintain a single monolithic HNSW graph. Instead, partition the index into multiple read-only **immutable segments** and one active **mutable in-memory segment**.
    *   Incoming writes are written to a Write-Ahead Log (WAL) and stored in-memory (unindexed, raw vectors).
    *   Once the in-memory segment reaches a size threshold (e.g., 50,000 vectors), it is frozen, and an asynchronous worker builds a local HNSW index for it in the background, flushing it to disk as a new immutable segment.
2.  **On-the-Fly Merging during Queries:**
    *   Queries run across both the immutable segments (via HNSW) and the active in-memory segment (via linear scan/FLAT, which is fast because the in-memory segment size is constrained).
    *   A final merge/deduplication layer combines the results.
3.  **In-Engine Pre-Filtering (Structured Index Integration):**
    *   To prevent the "search collapse" of post-filtering and the high cost of pre-filtering, we use **Single-Stage Filtering**.
    *   Maintain parallel attribute indexes (e.g., Roaring Bitmaps for categoricals like `in_stock = True`, or B-Trees for ranges like `price < 50`).
    *   Modify the HNSW graph traversal algorithm: When exploring neighbor nodes, look up the node’s ID in the pre-computed Roaring Bitmap of valid/in-stock product IDs. If the node fails the filter, skip it during graph traversal without evaluating its vector distance. This guarantees that only valid candidates are returned without breaking the $O(\log N)$ traversal complexity.