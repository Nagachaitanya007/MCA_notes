---
title: Clustering Scenarios: K-Means vs. DBSCAN vs. Hierarchical
date: 2026-07-16T04:33:24.701756
---

# Clustering Scenarios: K-Means vs. DBSCAN vs. Hierarchical

---

## 1. 🧱 The Core Concept

Clustering is the unsupervised task of partitioning a dataset into groups (clusters) such that data points within the same group are more similar to each other than to those in other groups. Choosing the wrong clustering algorithm can lead to misallocated cloud resources, degraded recommendation quality, or missed anomalies.

### Architectural & Complexity Comparison

| Dimension | K-Means | DBSCAN | Agglomerative Hierarchical |
| :--- | :--- | :--- | :--- |
| **Philosophy** | **Centroid-based**: Partitions space into Voronoi cells around $K$ central prototypes. | **Density-based**: Groups contiguous regions of high point density, separated by low-density regions. | **Connectivity-based**: Builds a bottom-up tree (dendrogram) based on pairwise distances. |
| **Time Complexity** | $O(I \cdot K \cdot N \cdot D)$<br><small>$I$: iterations, $K$: clusters, $N$: points, $D$: dimensions</small> | $O(N \log N)$ with spatial index (low $D$);<br>$O(N^2)$ worst-case / high $D$. | $O(N^3)$ naive;<br>$O(N^2 \log N)$ optimized;<br>$O(N^2)$ for specific linkages. |
| **Space Complexity** | $O((N + K) \cdot D)$<br><small>Memory footprint scales linearly with dataset size.</small> | $O(N)$ to store point states and neighborhood graphs. | $O(N^2)$ to store the pairwise distance (proximity) matrix. |
| **Primary Hyperparameters** | $K$ (number of clusters). | $\epsilon$ (eps: search radius),<br>$MinPts$ (density threshold). | $K$ (or distance threshold cut),<br>Linkage metric (Single, Complete, Average, Ward). |
| **Outlier Sensitivity** | **High**: Outliers pull centroids away from true density peaks. | **None / Low**: Explicitly labels outliers as "Noise" ($1$). | **Medium-High**: Outliers form isolated singleton branches late in the merge process. |
| **Non-Spherical Shapes** | **Fails**: Assumes isotropic (spherical) clusters of equal variance. | **Excellent**: Captures arbitrary manifold shapes (coaxial rings, spirals). | **Varies**: Single-linkage handles arbitrary shapes but suffers from chaining. |
| **Varying Densities** | **Fails**: Splits high-density clusters or merges low-density ones. | **Fails**: Single $\epsilon$ cannot resolve high and low density regions simultaneously. | **Good**: Ward’s/Average linkage can adapt to varying densities. |

---

### Distance Metrics & Coordinate Spaces

The choice of distance metric fundamentally changes the geometry of the cluster boundaries. 

```
Euclidean (L2)         Manhattan (L1)          Cosine Similarity
   d = √∑(x_i - y_i)²     d = ∑|x_i - y_i|        cos(θ) = (A·B) / (||A|| ||B||)
      
       \   /                  |                      \     /
        \ /                 --+--                     \ θ /
         x                    |                        x---
```

#### 1. Euclidean Distance ($L_2$ Norm)
$$d(\mathbf{x}, \mathbf{y}) = \sqrt{\sum_{i=1}^D (x_i - y_i)^2}$$
*   **Behavior:** Measures straight-line distance in Euclidean space. It is highly sensitive to extreme differences in a single dimension (due to squaring).
*   **Use Case:** Default for K-Means. Assumes continuous, isotropic, and normalized features.

#### 2. Manhattan Distance ($L_1$ Norm)
$$d(\mathbf{x}, \mathbf{y}) = \sum_{i=1}^D |x_i - y_i|$$
*   **Behavior:** Measures distance along axis-aligned paths ("taxicab" geometry). Less sensitive to extreme single-dimension outliers than $L_2$.
*   **Use Case:** Preferred in high-dimensional sparse spaces or when features represent directional grid coordinates.

#### 3. Cosine Distance
$$d(\mathbf{x}, \mathbf{y}) = 1 - \frac{\mathbf{x} \cdot \mathbf{y}}{\|\mathbf{x}\|_2 \|\mathbf{y}\|_2}$$
*   **Behavior:** Measures angular differences rather than magnitude.
*   **Use Case:** Highly effective for document clustering (TF-IDF vectors) and high-dimensional embedding spaces (e.g., user/item embeddings in recommendation engines) where the scale of the vector represents activity/frequency, but the orientation represents semantic meaning.

---

## 2. ⚙️ Under the Hood

### A. K-Means / K-Means++

#### Lloyd's Algorithm (Expectation-Maximization Framework)
K-Means solves the non-convex optimization problem of minimizing the **Within-Cluster Sum of Squares (WCSS)**, also known as **Inertia**:
$$\arg\min_{\mathbf{S}} \sum_{i=1}^{K} \sum_{\mathbf{x} \in S_i} \|\mathbf{x} - \boldsymbol{\mu}_i\|^2$$

where $\boldsymbol{\mu}_i$ is the mean of points in cluster $S_i$. It operates via two alternating steps:

```
  [ Initialization ] (K-Means++)
         │
         ▼
┌─────────────────────────────────┐
│     E-Step (Assignment)         │◄────────┐
│  Assign x_i to closest μ_k      │         │
└─────────────────────────────────┘         │
         │                                  │ Iteration
         ▼                                  │ until convergence
┌─────────────────────────────────┐         │ (Inertia plateau)
│     M-Step (Update)             │         │
│  Recalculate μ_k as mean of S_k │─────────┘
└─────────────────────────────────┘
         │
         ▼
   [ Convergence ]
```

1.  **Expectation (E-step):** Assign each data point $\mathbf{x}_j$ to its nearest centroid $\boldsymbol{\mu}_i^{(t)}$:
    $$S_i^{(t)} = \left\{ \mathbf{x}_j : \left\| \mathbf{x}_j - \boldsymbol{\mu}_i^{(t)} \right\|^2 \le \left\| \mathbf{x}_j - \boldsymbol{\mu}_{i^*}^{(t)} \right\|^2 \, \forall i^* = 1, \dots, K \right\}$$
2.  **Maximization (M-step):** Recalculate the centroids as the arithmetic mean of all points assigned to that cluster:
    $$\boldsymbol{\mu}_i^{(t+1)} = \frac{1}{|S_i^{(t)}|} \sum_{\mathbf{x}_j \in S_i^{(t)}} \mathbf{x}_j$$

#### K-Means++ Initialization (Avoiding Poor Local Optima)
Standard random initialization can cause the algorithm to converge to poor local minima. K-Means++ addresses this by spreading out the initial centroids:

1.  Choose the first centroid $\boldsymbol{\mu}_1$ uniformly at random from the dataset $\mathbf{X}$.
2.  For each remaining point $\mathbf{x}$, compute $D(\mathbf{x})$, the shortest distance between $\mathbf{x}$ and the closest centroid already selected.
3.  Choose the next centroid $\boldsymbol{\mu}_i$ from $\mathbf{X}$ with a probability proportional to the squared distance:
    $$P(\mathbf{x}) = \frac{D(\mathbf{x})^2}{\sum_{\mathbf{y} \in \mathbf{X}} D(\mathbf{y})^2}$$
4.  Repeat steps 2 and 3 until $K$ centroids are chosen.

This initialization guarantees an approximation ratio of $O(\log K)$ relative to the optimal clustering solution.

---

### B. DBSCAN (Density-Based Spatial Clustering of Applications with Noise)

DBSCAN classifies points based on local density, defined by two parameters: $\epsilon$ (search radius) and $MinPts$ (minimum neighbors within $\epsilon$).

```
       ● Core Point (≥ MinPts inside ε-sphere)
      / \
     /   \
    /     ▼
   ●──────►● Border Point (< MinPts inside ε, but reachable from Core)
  Core

           o Noise Point (Not reachable from any Core)
```

#### Point Classification
For a point $\mathbf{p}$ and dataset $\mathbf{X}$, let $N_{\epsilon}(\mathbf{p}) = \{ \mathbf{q} \in \mathbf{X} \mid d(\mathbf{p}, \mathbf{q}) \le \epsilon \}$ be the $\epsilon$-neighborhood of $\mathbf{p}$.
*   **Core Point:** $|N_{\epsilon}(\mathbf{p})| \ge MinPts$.
*   **Border Point:** $|N_{\epsilon}(\mathbf{p})| < MinPts$, but $\exists \, \mathbf{c} \in \mathbf{X}$ such that $\mathbf{c}$ is a Core Point and $\mathbf{p} \in N_{\epsilon}(\mathbf{c})$.
*   **Noise Point:** Neither a Core nor a Border point.

#### Algorithmic Execution Flow
1.  **Labeling:** Mark all points as unvisited.
2.  **Neighborhood Query:** For each unvisited point $\mathbf{p}$, compute $N_{\epsilon}(\mathbf{p})$.
    *   If $|N_{\epsilon}(\mathbf{p})| < MinPts$, label $\mathbf{p}$ tentatively as Noise.
    *   If $|N_{\epsilon}(\mathbf{p})| \ge MinPts$, label $\mathbf{p}$ as a Core Point and initialize a new cluster $C$.
3.  **Density Expansion:** Expand $C$ by transitively adding all density-reachable points:
    *   For each point $\mathbf{q} \in N_{\epsilon}(\mathbf{p})$:
        *   If $\mathbf{q}$ was marked as Noise, relabel it as a Border Point of $C$.
        *   If $\mathbf{q}$ is unvisited, mark it visited, retrieve $N_{\epsilon}(\mathbf{q})$, and if $|N_{\epsilon}(\mathbf{q})| \ge MinPts$, append these neighbors to the queue of points to process for $C$.
4.  Repeat until all points are marked visited.

#### Complexity & Indexing Optimization
The baseline complexity of DBSCAN is dominated by finding the $\epsilon$-neighborhood for all $N$ points.
*   **Naive Approach:** Pairwise distance calculations for all points $\rightarrow O(N^2)$.
*   **Spatial Indexing (e.g., $K$-D Trees or Ball Trees):** Reduces neighbor search complexity to $O(\log N)$ per query. Total time complexity becomes **$O(N \log N)$**.
*   **The High-Dimensional Caveat:** The efficacy of $K$-D Trees degrades exponentially as dimensions increase ($D > 10$). Due to the **Curse of Dimensionality**, the search space cannot be partitioned efficiently, and spatial index searches collapse to a sequential scan ($O(N)$ per query), driving the total complexity back to **$O(N^2)$**.

---

### C. Hierarchical Agglomerative Clustering (HAC)

HAC builds a bottom-up binary tree (dendrogram) by iteratively merging the closest pair of clusters.

```
       [Root]           <-- Cut at threshold height h to yield K clusters
       /    \
     / \    / \
    A   B  C  D         <-- Individual data points (Singletons)
```

#### Linkage Criteria Formulation
Let $A$ and $B$ be two clusters. The distance between them, $d(A, B)$, is computed based on the selected linkage:

| Linkage | Mathematical Formulation | Architectural Properties / Failure Modes |
| :--- | :--- | :--- |
| **Single Linkage** (Minimum) | $$d(A, B) = \min_{\mathbf{a} \in A, \mathbf{b} \in B} d(\mathbf{a}, \mathbf{b})$$ | **Chaining Effect:** Merges distinct clusters if a thin line of intermediate noise points connects them. |
| **Complete Linkage** (Maximum) | $$d(A, B) = \max_{\mathbf{a} \in A, \mathbf{b} \in B} d(\mathbf{a}, \mathbf{b})$$ | **Compactness Bias:** Minimizes maximum cluster diameter, forcing compact, spherical clusters. Highly sensitive to outliers. |
| **Average Linkage** (UPGMA) | $$d(A, B) = \frac{1}{|A||B|} \sum_{\mathbf{a} \in A} \sum_{\mathbf{b} \in B} d(\mathbf{a}, \mathbf{b})$$ | **Robust Balance:** Less sensitive to noise; seeks clusters with similar variances. Computationally expensive due to all-pairs evaluation. |
| **Ward's Linkage** | $$\Delta E = \frac{|A||B|}{|A| + |B|} \|\boldsymbol{\mu}_A - \boldsymbol{\mu}_B\|^2$$ | **Variance Minimization:** Merges clusters that minimize the increase in total within-cluster variance. Strongly biased toward spherical shapes. |

#### Dendrogram Cutting
A dendrogram is a tree representing hierarchical relationships. To obtain flat clusters:
1.  **Height-Based Cut:** Set a static distance threshold $h$. Any horizontal line cut across the tree at height $h$ yields a partition.
2.  **Inconsistency Coefficient Cut:** Compare the height of a link with the average heights of links at lower levels. If a link height is significantly higher than its subordinates, it represents a natural boundary.

---

## 3. ⚠️ The Interview Warzone

### Scenario 1: E-Commerce Customer Segmentation at Scale

#### The Interview Setup
> **Interviewer:** "We want to segment 100 million active customers for personalized marketing campaigns. The features include total spend (continuous), geographical location (continuous), primary category interest (categorical), and transaction frequency (discrete). How do you approach clustering this dataset?"

#### The Candidate's Strategy (How to Structure the Response)
1.  **Deconstruct the Scale:** Flag that 100M rows immediately rules out Agglomerative Hierarchical clustering ($O(N^2)$ space/time is impossible at scale). Standard DBSCAN is also impractical without extensive spatial partitioning or distributed architectures.
2.  **Address Feature Heterogeneity:** Highlight that standard distance metrics ($L_2$) are invalid on mixed data types (e.g., categorical variables cannot be treated as continuous without projection).
3.  **Propose an Architectural Pipeline:**

```
Raw Data (100M Rows)
     │
     ▼
[ Pipeline: One-Hot + Numeric Scale ]
     │
     ▼
[ Dimension Reduction: UMAP / PCA ] (Reduce to D ≤ 10)
     │
     ▼
[ Engine: Mini-Batch K-Means ] ──► Evaluate K via Silhouette / Elbow
```

#### Detailed Solution Steps

*   **Step 1: Feature Transformation & Dimensionality Reduction**
    *   One-hot encode categorical variables. Standardize continuous variables using a robust scaler to mitigate outlier influence.
    *   Since K-Means scales with dimensions $D$, use linear projection (PCA) or non-linear manifold learning (UMAP/t-SNE, though t-SNE does not preserve global distances well for clustering) to project the features down to a lower-dimensional manifold (e.g., $D \approx 5-10$).
*   **Step 2: Core Engine Selection (Mini-Batch K-Means)**
    *   Propose **Mini-Batch K-Means** instead of standard Lloyd's K-Means.
    *   *Mathematical optimization:* Standard K-Means reads the entire 100M dataset into memory to compute the E-step. Mini-Batch K-Means uses random mini-batches $\mathcal{B} \subset \mathbf{X}$ (e.g., $|\mathcal{B}| = 10,000$) to update centroids.
    *   *Centroid update formulation for batch $\mathcal{B}$:*
        $$\mathbf{v}[\mathbf{x}] = \text{closest centroid } \boldsymbol{\mu}_c$$
        $$\text{For each } \mathbf{x} \in \mathcal{B}: \quad \eta = \frac{1}{\text{count}(\boldsymbol{\mu}_c) + 1}, \quad \boldsymbol{\mu}_c \leftarrow (1 - \eta)\boldsymbol{\mu}_c + \eta \mathbf{x}$$
        This achieves $O(I \cdot K \cdot |\mathcal{B}| \cdot D)$ per step, reducing memory footprint to $O(|\mathcal{B}|)$.
*   **Step 3: Determining $K$**
    *   Run parallel evaluations on a scaled-down, representative sample (e.g., $100,000$ points) to plot the **Elbow Method** (WCSS vs. $K$) and compute the **Silhouette Coefficient**:
        $$s(\mathbf{x}) = \frac{b(\mathbf{x}) - a(\mathbf{x})}{\max(a(\mathbf{x}), b(\mathbf{x}))}$$
        where $a(\mathbf{x})$ is the mean intra-cluster distance and $b(\mathbf{x})$ is the mean nearest-cluster distance. Choose $K$ that maximizes $s(\mathbf{x})$.

---

### Scenario 2: Real-time Geolocation Anomaly Detection (IP / GPS Streams)

#### The Interview Setup
> **Interviewer:** "We are building an intrusion detection system. We receive streaming coordinate data (lat/lon, IP-based locations) of connection requests. We want to identify tight spatial clusters of legit traffic and isolate single anomalous requests. High-velocity bursts can happen at any coordinate. What clustering framework do you use, and how do you deploy it?"

#### The Candidate's Strategy (How to Structure the Response)
1.  **Rule out K-Means:** K-Means cannot handle anomalies. It forces every outlier into a cluster, pulling centroids toward noise. Additionally, we do not know $K$ beforehand.
2.  **Rule out Agglomerative Hierarchical:** Too slow for streaming/real-time use cases.
3.  **Propose DBSCAN (or its hierarchical variant, HDBSCAN):** DBSCAN natively defines noise (points where density is low) and accommodates arbitrary shapes.
4.  **Resolve the Latency/Streaming Challenge:** Standard DBSCAN is offline. Propose spatial partitioning or streaming density algorithms (like Core-Micro-Cluster tracking).

#### Detailed Solution Steps

*   **Step 1: Metric and Parameter Selection**
    *   Coordinates are spherical. Using Euclidean distance introduces projection distortion. We must use the **Haversine Distance**:
        $$d = 2R \arcsin\left(\sqrt{\sin^2\left(\frac{\Delta \phi}{2}\right) + \cos(\phi_1)\cos(\phi_2)\sin^2\left(\frac{\Delta \lambda}{2}\right)}\right)$$
    *   Set $MinPts$ based on a domain-specific threshold (e.g., $MinPts = 5$ requests within a window represents legitimate traffic).
    *   Determine $\epsilon$ using the **$k$-distance plot**: calculate the distance to the $k$-nearest neighbor (where $k = MinPts$) for all points, sort them, and find the "knee" of the curve.
*   **Step 2: Mitigation of the Density Variation Problem**
    *   If some legitimate locations (e.g., New York City) have massive density, while others (e.g., rural areas) have sparse density, a static $\epsilon$ fails.
    *   *Propose HDBSCAN* (Hierarchical DBSCAN). HDBSCAN varies $\epsilon$ continuously. It converts the dataset into a distance scale space using the **mutual reachability distance**:
        $$d_{\text{mreach-}k}(\mathbf{p}, \mathbf{q}) = \max\{\text{core}_k(\mathbf{p}), \text{core}_k(\mathbf{q}), d(\mathbf{p}, \mathbf{q})\}$$
        It then builds a minimum spanning tree, extracts a cluster hierarchy, and condenses the tree based on cluster stability (excess of mass), avoiding the need to select a single $\epsilon$.

```
     HDBSCAN Dendrogram Stability Extraction
     
     │    ┌───────┐
     │    │       │     <-- unstable branch (low lifetime) -> pruned
     │  ┌─┴─┐   ┌─┴─┐
     │  │   │   │   │   <-- stable branch (high lifetime)   -> kept
     └──┴───┴───┴───┴──
```

*   **Step 3: Real-Time Stream Ingestion Architecture**
    *   To execute this at scale with sub-second latency, map incoming streams into a **Geohash** grid or an **S2 geometry** cell index.
    *   Instead of re-running DBSCAN globally, apply it inside a sliding temporal window over active spatial cells and their immediate boundary neighbors.

---

### Scenario 3: Automated Taxonomy Generation for a Knowledge Graph

#### The Interview Setup
> **Interviewer:** "We have 50,000 unique skills extracted from LinkedIn profiles (e.g., 'PyTorch', 'TensorFlow', 'Deep Learning', 'React', 'Vue'). We want to construct a visual, tree-like taxonomy of these skills for recruiters. How do you design this?"

#### The Candidate's Strategy (How to Structure the Response)
1.  **Deconstruct the Goal:** The requirement is explicitly "tree-like" and "hierarchical." This points directly to **Agglomerative Hierarchical Clustering**.
2.  **Representing Textual Data:** Skill strings need high-dimensional vector representations. Use dense sentence embeddings (e.g., MiniLM or Ada2 from OpenAI) rather than tf-idf, to capture semantic meaning (so 'TensorFlow' is close to 'PyTorch').
3.  **Algorithmic Selection & Linkage Analysis:** Explain the choice of linkage criteria and its direct impact on the taxonomy quality.

#### Detailed Solution Steps

*   **Step 1: Embedding and Proximity Representation**
    *   Pass the 50,000 skill strings through an embedding model to generate vectors $\mathbf{v} \in \mathbb{R}^{384}$.
    *   Construct a cosine similarity matrix. Since Agglomerative Clustering in `scipy`/`scikit-learn` uses distance, convert this to cosine distance: $D_{\text{cosine}} = 1 - S_{\text{cosine}}$.
*   **Step 2: Choosing the Linkage Criterion**
    *   *Analyze tradeoffs:*
        *   **Single Linkage:** Avoid. It will create a "chain" where unrelated skills are merged step-by-step through loose connections (e.g., PyTorch $\rightarrow$ Python $\rightarrow$ Django $\rightarrow$ React).
        *   **Complete Linkage:** Creates small, overly-compact skill groups, but separates related sub-fields too early.
        *   **Ward’s Linkage:** Ideal for constructing balanced hierarchies. It minimizes intra-cluster variance, generating a highly structured dendrogram.
*   **Step 3: Evaluating Dendrogram Quality**
    *   To verify that our hierarchical tree preserves the true pairwise distances of the original vector space, calculate the **Cophenetic Correlation Coefficient ($c$)**:
        $$c = \frac{\sum_{i < j} (x(i, j) - \bar{x})(t(i, j) - \bar{t})}{\sqrt{\sum_{i < j} (x(i, j) - \bar{x})^2 \sum_{i < j} (t(i, j) - \bar{t})^2}}$$
        where $x(i, j)$ is the actual Euclidean distance between points $i$ and $j$, and $t(i, j)$ is the dendrogrammatic distance (the height of the link where $i$ and $j$ are first merged). A value $c > 0.7$ indicates a high-fidelity hierarchy.

---

## 4. 🎛️ Advanced Interview Trade-offs & Deep-Dives

To stand out in a Staff-level loop, you must be able to discuss performance trade-offs, scaling limits, and failure modes under stress.

### A. The Curse of Dimensionality in Clustering

As the number of dimensions $D$ increases, the volume of space grows exponentially, causing the data points to become extremely sparse. 

In high-dimensional spaces, the ratio between the distance to the nearest neighbor and the distance to the farthest neighbor approaches 1:
$$\lim_{D \to \infty} \frac{D_{\max} - D_{\min}}{D_{\min}} = 0$$

#### Impact on Algorithms
*   **K-Means:** Conceptually, $L_2$ distance loses its contrast. Every point becomes almost equidistant from every other point. The centroids collapse toward the global mean.
*   **DBSCAN:** $\epsilon$-spheres become mostly empty. To capture points, $\epsilon$ must be set so large that it encompasses almost the entire dataset, merging distinct clusters.

#### Mitigation Strategy
Always apply linear (PCA) or non-linear (UMAP/t-SNE) dimensionality reduction *prior* to clustering in high dimensions, or utilize subspace clustering algorithms (like CLIQUE) which find clusters in localized projections of the feature space.

---

### B. Scalability Bottlenecks & Distributed Clustering (MapReduce/Spark)

When datasets exceed a single machine's RAM, clustering must be distributed.

```
       [ Driver / Master ] ───► Broadcasts Centroids {μ_1, ..., μ_K}
             │
      ┌──────┼──────┐
      ▼      ▼      ▼
   [Worker] [Worker] [Worker]  <-- Local E-step: Assign chunks to nearest μ_c
      │      │      │              Calculate local sums & counts
      └──────┼──────┘
             ▼
       [ Driver / Master ] ───► M-step: Global reduce & update centroids
```

#### Distributed K-Means ($K$-Means||)
In a Spark (MapReduce) environment, standard K-Means++ is sequential and slow because it requires $K$ passes over the dataset to initialize centroids.
*   **$K$-Means|| (Parallel K-Means):** Instead of selecting 1 centroid per pass, it samples $O(K)$ candidate centroids in each of the $O(\log N)$ passes.
*   **MapReduce Step:**
    *   **Map:** Each mapper holds a subset of data points, assigns them to the nearest centroid, and outputs the local sum and count of points for each cluster.
    *   **Reduce:** The reducer aggregates these local sums and counts, computes the global updated centroids, and broadcasts them back to the mappers.

#### Distributed DBSCAN Challenge
DBSCAN is inherently difficult to parallelize because density connectivity is a global property. Merging border points across partitions requires spatial coordination.
*   **Partitioning Solution:** Use a spatial partitioning strategy (e.g., BSP - Binary Space Partitioning) to split space into bounding boxes with overlapping guard bands (halos) of width $\epsilon$.
*   **Local Run:** Run DBSCAN locally on each partition.
*   **Merge Step:** Merge clusters that share core points within the overlapping halos using a Disjoint-Set (Union-Find) data structure across partition boundaries.