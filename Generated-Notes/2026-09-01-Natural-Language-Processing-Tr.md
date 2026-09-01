---
title: Natural Language Processing: Transformers, Attention, and Tokenization
date: 2026-09-01T04:32:49.491182
---

---
title: Natural Language Processing: Transformers, Attention, and Tokenization
date: 2026-07-31T04:32:33.367219
---

# Natural Language Processing: Transformers, Attention, and Tokenization

---

## 🧱 1. The Core Concept (Basics Refresh)

### Tokenization Algorithms: BPE, WordPiece, and Unigram

Tokenization bridges raw character sequences and numerical tensor inputs. Modern Large Language Models (LLMs) rely on **subword tokenization** to balance vocabulary size and sequence length while eliminating Out-Of-Vocabulary (OOV) tokens.

```
Raw Text: "unaffable"
             │
             ├── Byte-Pair Encoding (BPE)    ──> ["un", "aff", "able"]
             ├── WordPiece                   ──> ["un", "##aff", "##able"]
             └── Unigram (Subword Regulariz.) ──> Probabilistic sample over candidate splits
```

#### Byte-Pair Encoding (BPE)
* **Strategy**: Bottom-up (deterministic greedy merge).
* **Algorithm**:
  1. Initialize vocabulary with all individual base characters (or bytes) plus an end-of-word symbol.
  2. Count adjacent symbol pairs in the corpus.
  3. Iteratively merge the most frequent adjacent pair $(A, B) \to AB$ and add it to the vocabulary.
  4. Stop when the target vocabulary size $V$ or merge count limit is reached.
* **Used by**: GPT-2, GPT-3, GPT-4, Llama series, RoBERTa.

#### WordPiece
* **Strategy**: Bottom-up (likelihood-maximizing merge).
* **Algorithm**:
  1. Initialize vocabulary with individual characters, marking subwords with a prefix (e.g., `##`).
  2. Instead of picking the most frequent pair, pick the pair that maximizes the language model likelihood of the training data:
     $$\text{Score}(A, B) = \frac{\text{count}(AB)}{\text{count}(A) \times \text{count}(B)}$$
     This measures the **Mutual Information** between $A$ and $B$, penalizing merges of globally frequent individual tokens unless they co-occur with high probability.
* **Used by**: BERT, DistilBERT.

#### Unigram Language Model
* **Strategy**: Top-down (probabilistic entropy reduction).
* **Algorithm**:
  1. Initialize vocabulary with a very large set of substrings and characters.
  2. Train a unigram language model on the corpus to estimate marginal probabilities $P(x_i)$ for each token $x_i$.
  3. Compute the loss (negative log-likelihood) over the corpus.
  4. Evaluate how much the loss increases if a token $x_k$ is removed from the vocabulary.
  5. Drop the top $p\%$ of tokens that cause the smallest loss increase (typically 10–20%).
  6. Repeat until the target vocabulary size $V$ is reached.
* **Property**: Enables **Subword Regularization** by probabilistically sampling subword tokenizations during training according to $P(x_i)$.
* **Used by**: T5, ALBERT, SentencePiece (when set to Unigram mode).

#### Trade-Off Matrix

$$\begin{array}{lcccc}
\hline
\textbf{Tokenizer} & \textbf{Vocab Size Trade-Off} & \textbf{Seq Length Impact} & \textbf{OOV Handling} & \textbf{Primary Failure Mode} \\
\hline
\text{Character} & \text{Tiny } (\sim 256) & \text{Extremely Long } (\sim 4\text{--}5\times) & \text{Zero OOV} & \text{Vanishing context window; high compute} \\
\text{Word-level} & \text{Massive } (>500\text{k}) & \text{Shortest} & \text{High OOV rates} & \text{Parameter bloat in } E \in \mathbb{R}^{V \times d} \\
\text{Subword (BPE/WP)} & \text{Balanced } (32\text{k}\text{--}128\text{k}) & \text{Optimal } (\sim 1.3\text{--}1.5\times \text{ words}) & \text{Byte Fallback} & \text{Poor multilingual token allocation} \\
\hline
\end{array}$$

---

### Attention Mechanism: Scaled Dot-Product & Multi-Head Attention

Attention projects an input sequence $X \in \mathbb{R}^{N \times d_{\text{model}}}$ into three functional vector spaces via learned projection matrices $W_Q, W_K, W_V \in \mathbb{R}^{d_{\text{model}} \times d_k}$:
* **Query ($Q = XW_Q$)**: What the token is searching for.
* **Key ($K = XW_K$)**: What features the token offers to matching queries.
* **Value ($V = XW_V$)**: The information payload propagated if a match occurs.

```
       Query (Q)   Key (K)
           │          │
           └───┬──────┘
               ▼
         [ Q · Kᵀ ]  <-- Dot Product Alignment
               │
               ▼
          [ / √dₖ ]  <-- Variance Scaling
               │
               ▼
         [ Softmax ] <-- Probability Distribution (A)
               │
               ├──> [ Mask (Causal/Padding) ] (Optional)
               ▼
          Attention Scores
               │
               ├── Value (V)
               ▼
         [ A · V ]   <-- Weighted Vector Aggregation
```

#### Scaled Dot-Product Attention
$$\text{Attention}(Q, K, V) = \text{softmax}\left(\frac{QK^T}{\sqrt{d_k}}\right)V$$

#### Why Scale by $1/\sqrt{d_k}$?
Assume query components $q_i$ and key components $k_i$ are independent random variables with zero mean and unit variance: $\mathbb{E}[q_i] = 0, \text{Var}(q_i) = 1$. The dot product is:
$$q \cdot k = \sum_{i=1}^{d_k} q_i k_i$$
* Expectation: $\mathbb{E}[q \cdot k] = 0$
* Variance: $\text{Var}(q \cdot k) = \sum_{i=1}^{d_k} \text{Var}(q_i k_i) = \sum_{i=1}^{d_k} \text{Var}(q_i)\text{Var}(k_i) = d_k$

For large $d_k$ (e.g., $d_{\text{head}} = 128$), the variance of $QK^T$ reaches $128$, leading to standard deviations of $\sim 11.3$. Large input values push the $\text{softmax}$ function into regions with near-zero gradients:

$$\frac{\partial \text{softmax}(z)_i}{\partial z_j} = \text{softmax}(z)_i (\delta_{ij} - \text{softmax}(z)_j) \approx 0 \quad \text{for } |z_i - z_j| \gg 0$$

Scaling by $\frac{1}{\sqrt{d_k}}$ renormalizes the variance back to $1$, preventing gradient vanishing during backpropagation.

#### Multi-Head Attention (MHA)
Single-head attention averages vector features over the entire channel dimension, causing spatial information loss. Multi-Head Attention projects $Q, K, V$ into $h$ lower-dimensional subspaces ($d_k = d_{\text{model}} / h$):

$$\text{MHA}(Q, K, V) = \text{Concat}(\text{head}_1, \dots, \text{head}_h)W^O$$
$$\text{where } \text{head}_i = \text{Attention}(Q W_i^Q, K W_i^K, V W_i^V)$$

---

### Structural Paradigms: Architectures & Positional Encodings

```
Architectural Taxonomy
 ├── Encoder-Only (e.g., BERT)       --> Full Bidirectional Attention Matrix
 ├── Decoder-Only (e.g., Llama, GPT) --> Lower-Triangular Causal Attention Matrix
 └── Encoder-Decoder (e.g., T5)      --> Cross-Attention Interleaving
```

$$\begin{array}{lcccc}
\hline
\textbf{Architecture} & \textbf{Attention Mask} & \textbf{Primary Use Case} & \textbf{Generation Mode} \\
\hline
\text{Encoder-Only} & \text{Fully Unmasked } (N \times N) & \text{Classification, Extraction, Embeddings} & \text{Non-Autoregressive} \\
\text{Decoder-Only} & \text{Causal Mask } (L_{ij} = -\infty \text{ for } j > i) & \text{Generative LLMs, Code Generation} & \text{Autoregressive } (O(1) \text{ per step w/ KV Cache})} \\
\text{Encoder-Decoder} & \text{Unmasked Enc / Causal Dec / Cross-Attn} & \text{Translation, Abstractive Summarization} & \text{Autoregressive Decoder} \\
\hline
\end{array}$$

#### Positional Encodings Evolution

Transformers are permutation-invariant by default because attention treats input sequences as unordered sets of vectors. Positional encodings restore token order information.

* **Absolute Sinusoidal Encodings (Original Transformer)**:
  $$PE_{(pos, 2i)} = \sin\left(\frac{pos}{10000^{2i/d_{\text{model}}}}\right), \quad PE_{(pos, 2i+1)} = \cos\left(\frac{pos}{10000^{2i/d_{\text{model}}}}\right)$$
  * *Limitation*: Fails to extrapolate beyond the maximum training sequence length.

* **Rotary Position Embeddings (RoPE)**:
  Rotates the Query and Key vectors in 2D two-plane subspaces proportional to absolute position $m$:
  $$R_{\Theta, m}^d = \text{diag}\left(R_{\theta_1, m}, R_{\theta_2, m}, \dots, R_{\theta_{d/2}, m}\right), \quad R_{\theta_i, m} = \begin{pmatrix} \cos m\theta_i & -\sin m\theta_i \\ \sin m\theta_i & \cos m\theta_i \end{pmatrix}$$
  The inner product preserves relative distance:
  $$\langle R_{\Theta, m}^d q_m, R_{\Theta, n}^d k_n \rangle = q_m^T R_{\Theta, n-m}^d k_n$$

* **Attention with Linear Biases (ALiBi)**:
  Adds a static penalty proportional to the distance between tokens directly to the attention matrix:
  $$A_{ij} = q_i k_j^T - m \cdot |i - j|$$
  Where $m$ is a head-specific fixed slope scaling factor ($m = 2^{-\frac{8}{h} \cdot k}$).
  * *Advantage*: Enables strong sequence length extrapolation without modifying positional embeddings.

---

## ⚙️ 2. Under the Hood (Internal Mechanics & Architecture)

### Mathematical Derivation of Attention & Softmax Numerical Stability

The baseline full attention step proceeds as follows:

```
Inputs: X ∈ ℝ^(N × d_model)
Step 1: Compute Projections -> Q = X W_Q, K = X W_K, V = X W_V
Step 2: Raw Attention Scores -> S = (Q Kᵀ) / √d_k   ∈ ℝ^(N × N)
Step 3: Causal Masking -> S_ij = -∞ for j > i
Step 4: Softmax Normalization -> P = Softmax(S)     ∈ ℝ^(N × N)
Step 5: Output Projection -> O = P V W_O             ∈ ℝ^(N × d_model)
```

#### Softmax Numerical Instability Problem
Directly computing $e^{S_{ij}}$ causes overflow in floating-point representations (FP16/BF16) when $S_{ij} > 88.7$ (FP16 max before overflow). 

#### Safe Softmax Trick
Subtract the maximum logit value along the sequence dimension:

$$m_i = \max_{j}(S_{ij})$$
$$P_{ij} = \frac{e^{S_{ij} - m_i}}{\sum_{k=1}^N e^{S_{ik} - m_i}}$$

Mathematically:
$$\frac{e^{S_{ij} - m_i}}{\sum_k e^{S_{ik} - m_i}} = \frac{e^{S_{ij}} \cdot e^{-m_i}}{\sum_k e^{S_{ik}} \cdot e^{-m_i}} = \frac{e^{S_{ij}}}{\sum_k e^{S_{ik}}}$$

This maintains numerical equivalence while bounding exponent arguments to $(-\infty, 0]$, completely preventing numeric overflow.

---

### Attention Memory & Compute Complexity Bottlenecks

#### High Bandwidth Memory (HBM) vs SRAM IO Complexity
In GPU architectures (e.g., NVIDIA H100/A100), memory access is split across tiers:
* **HBM (High Bandwidth Memory)**: Large size (40–80GB), limited bandwidth ($\sim 2\text{--}3\text{ TB/s}$).
* **SRAM (On-chip Cache per Streaming Multiprocessor)**: Small size ($\sim 108\text{KB/SM}$, tens of MB total), massive bandwidth ($\sim 19\text{ TB/s}$).

```
Standard Attention IO Flow (HBM Bound):
  Q, K, V (HBM) ──> [ Load ] ──> Compute S = Q·Kᵀ ──> [ Write S to HBM ] (O(N²))
  S (HBM)       ──> [ Load ] ──> Compute P = Softmax(S) ──> [ Write P to HBM ] (O(N²))
  P, V (HBM)    ──> [ Load ] ──> Compute O = P·V ──> [ Write O to HBM ] (O(N))
  
  Total DRAM/HBM Read/Write Footprint: O(N²)
```

#### FlashAttention Mechanics
FlashAttention eliminates the $O(N^2)$ memory bandwidth bottleneck by avoiding materialization of the intermediate $N \times N$ attention matrix $S$ or $P$ to HBM.

```
FlashAttention Flow (SRAM Tiling):
  Q, K, V (HBM) ──> Block Loading into SRAM Cache (Block Size B_r, B_c)
                    │
                    ├──> Compute Tiled MatMul in SRAM
                    ├──> Compute Online Softmax
                    └──> Update Running Numerator/Denominator Accumulators
                    │
  Output O (HBM) <── Output written directly to HBM (Skip N×N intermediate state)
  
  Total HBM Memory Access Footprint: O(N² d / M)   [where M = SRAM Size]
```

#### Tiling & Online Softmax Algorithm
Online Softmax decomposes the global normalization factor into incremental block updates. Given two blocks $A$ and $B$, we merge their softmax statistics without recalculating prior sequences from scratch:

$$m_{\text{new}} = \max(m_A, m_B)$$
$$d_{\text{new}} = d_A \cdot e^{m_A - m_{\text{new}}} + d_B \cdot e^{m_B - m_{\text{new}}}$$
$$O_{\text{new}} = O_A \cdot \left(\frac{d_A e^{m_A - m_{\text{new}}}}{d_{\text{new}}}\right) + O_B \cdot \left(\frac{d_B e^{m_B - m_{\text{new}}}}{d_{\text{new}}}\right)$$

* **Training Recomputation**: Instead of storing the $N \times N$ matrix $P$ for the backward pass, FlashAttention recomputes attention blocks locally on-chip during the backward pass using stored scaling statistics $(m, d)$, trading cheap FLOPs for slow memory I/O.

---

### The KV Cache: State Maintenance & Memory Footprint

During autoregressive generation, generating token $t_N$ requires key-value projections for all previous tokens $t_1, \dots, t_{N-1}$. The KV Cache stores $K$ and $V$ tensors from earlier steps to avoid $O(N^3)$ recomputation costs over context generation.

```
Autoregressive Inference Step (Without KV Cache):  Compute Cost = O(N³)
Autoregressive Inference Step (With KV Cache):     Compute Cost = O(N²)  [O(N) per token step]
```

#### KV Cache Exact Memory Sizing Equation
$$\text{Memory}_{\text{KVCache}} = 2 \times b \times L \times H_{\text{KV}} \times d_{\text{head}} \times S \times P_{\text{bytes}}$$

Where:
* $2$: Storing two distinct matrix tables (Key and Value tensors).
* $b$: Batch size.
* $L$: Number of transformer layers.
* $H_{\text{KV}}$: Number of Key/Value attention heads.
* $d_{\text{head}}$: Head dimension size ($d_{\text{model}} / H_Q$).
* $S$: Sequence context length (prompt tokens + generated tokens).
* $P_{\text{bytes}}$: Bytes per parameter (FP16/BF16 = 2, FP8 = 1, INT4 = 0.5).

#### Worked Example: Llama-3-70B KV Cache Footprint
* Parameters: $L = 80$, $H_Q = 64$, $H_{\text{KV}} = 8$ (using Grouped-Query Attention), $d_{\text{head}} = 128$.
* Execution State: FP16 precision ($P_{\text{bytes}} = 2$), Batch Size $b = 16$, Context Length $S = 8192$.

$$\text{Memory} = 2 \times 16 \times 80 \times 8 \times 128 \times 8192 \times 2 \text{ bytes}$$
$$\text{Memory} = 2 \times 16 \times 80 \times 8 \times 128 \times 8192 \times 2 = 42,949,672,960 \text{ Bytes} \approx 42.95 \text{ GB}$$

*Note: In standard Multi-Head Attention ($H_{\text{KV}} = 64$), this KV Cache footprint reaches $343.6\text{ GB}$, exceeding the VRAM capacity of four standard 80GB A100 GPUs for cache storage alone.*

```
Structural Attention Variations for KV Cache Optimization:

Multi-Head Attention (MHA)    Grouped-Query Attention (GQA)    Multi-Query Attention (MQA)
    Q Q Q Q  K K K K              Q Q Q Q  K K                    Q Q Q Q  K
    │ │ │ │  │ │ │ │              │ │ │ │  │ │                    │ │ │ │  │
    ▼ ▼ ▼ ▼  ▼ ▼ ▼ ▼              ▼ ▼ ▼ ▼  ▼ ▼                    ▼ ▼ ▼ ▼  ▼
    [1:1 Q-to-K Heads]           [G Query Heads per KV]          [All Queries share 1 KV]
```

---

## ⚠️ 3. The Interview Warzone (Scenarios, Probing Patterns, & Perfect Responses)

### Scenario 1: System Design / ML Infra
**Interviewer**: *"We are deploying a 70B parameter model with a 32k context window. During multi-tenant peak usage, our latency spikes non-linearly, and GPUs trigger Out-Of-Memory (OOM) errors during generation, even when average VRAM utilization shows 30% available capacity. Diagnose the root cause and detail your mitigation plan."*

#### Candidate Response Framework:

1. **Root Cause Analysis (Staff-level Precision)**:
   * **Internal Fragmentation**: Standard allocators reserve contiguous physical memory chunks based on maximum sequence allocations ($S_{\max}$). Non-uniform request completion lengths create severe internal dynamic memory fragmentation in VRAM.
   * **KV Cache Volatility**: At sequence length 32k, KV cache requirements scale linearly with generated length $S$, competing directly with intermediate activation tensors. 
   * **Compute-to-Memory Boundary Switch**: Short lengths are compute-bound (GEMM operations). Long context lengths switch generation to memory-bandwidth-bound operations, causing GPU Streaming Multiprocessor (SM) stall times.

```
       UNALLOCATED GAP (Internal Fragmentation Loss)
      ┌─────────────┬───────────┬─────────────┬───────────┐
      │ Cache Req 1 │  UNUSED   │ Cache Req 2 │  UNUSED   │
      └─────────────┴───────────┴─────────────┴───────────┘
```

2. **Remediation & Architecture Plan**:
   * **Step 1: PagedAttention Engine Implementation (vLLM Pattern)**: Virtualize KV Cache allocations by mapping non-contiguous, dynamic fixed-size physical memory pages (e.g., page size = 16 tokens) to virtual logical sequence indexes. This reduces unallocated dynamic cache overhead from $>60\%$ to $<1\%$.

```
Virtual Memory Pages:   [ Block 0 ] [ Block 1 ] [ Block 2 ]
                             │           │           │
Page Table Mapping:          ▼           ▼           ▼
Physical GPU Memory:    [ Frame 87 ] [ Frame 12 ] [ Frame 204 ] (Non-Contiguous)
```

   * **Step 2: Attention Decoupling**: Implement **FlashDecoding**. Traditional FlashAttention parallelizes over batch and head dimensions but runs sequentially over the context length dimension $S$. FlashDecoding splits the historical key/value context across multiple thread blocks, using atomic reduction operations to parallelize over context length, drastically reducing memory-bound stall times for long sequence prompts.
   * **Step 3: KV Cache Compression**: Apply FP8 or INT4 quantization to stored KV Cache channels. Compute dynamic scaling factors along the head channels:
     $$\hat{K} = \text{Quantize}_{\text{INT8}}(K), \quad \text{Memory Reduction} \approx 50\%$$

---

### Scenario 2: Algorithmic / Deep Mathematical Debugging
**Interviewer**: *"You scale an internal LLM from a 2k to a 16k context window using absolute sinusoidal positional encodings. During evaluation, loss explodes near step 2048. Why does absolute sinusoidal encoding fail here? How do RoPE and ALiBi mathematically resolve this, and how do they differ during length extrapolation?"*

#### Candidate Response Framework:

1. **Mathematical Failure Analysis**:
   * Sinusoidal positions map fixed frequency vectors: $PE_{(pos, 2i)} = \sin(pos / 10000^{2i/d})$. As relative offsets $|m - n|$ grow larger than those seen during training, inner product scalar magnitudes $\langle PE_m, PE_n \rangle$ produce out-of-distribution logit magnitudes.
   * Softmax normalizations force these unexpected scalar magnitudes into extreme ranges, causing output probabilities to collapse into standard high-entropy uniform noise distributions or extreme standard basis vectors, producing exploding loss values.

2. **Mathematical Mechanics of Solutions**:
   * **RoPE (Rotary Position Embeddings)**:
     Rotates $Q$ and $K$ via block-diagonal rotation matrix $R_{\Theta, m}^d$. The dot product incorporates distance algebraically:
     $$\langle R_{\Theta, m}^d q, R_{\Theta, n}^d k \rangle = q^T R_{\Theta, n-m}^d k$$
     To extrapolate past original lengths, scale frequencies using **YaRN** (Yet another RoPE extensioN) or **NTK-aware Interpolation**:
     $$\theta_i' = b \cdot a^{\frac{-2i}{d}} \implies \text{Scale base frequency } \theta \text{ dynamically: } \theta_{\text{new}} = \theta \cdot \beta$$

```
RoPE Vector Rotation in 2D Plane Subspace:

        q_rotated (pos = m)
          ^
          │   / q_unrotated
          │  /
          │ / ) θ·m
          └───────>
```

   * **ALiBi (Attention with Linear Biases)**:
     Injects position information directly into attention scores without embedding vectors:
     $$A_{ij} = \frac{q_i k_j^T}{\sqrt{d_k}} - m \cdot |i - j|$$
     As sequence distance $|i - j|$ increases, $A_{ij}$ approaches $-\infty$, forcing $\text{softmax}(A_{ij}) \to 0$. Out-of-bounds context positions receive near-zero attention scores, preventing exploding gradients without requiring modifications to parameter layers.

---

### Scenario 3: Edge Cases & Practical NLP Failures
**Interviewer**: *"Your company deploys a multi-lingual support bot using BPE. Production reports show that queries in non-Latin scripts (e.g., Hindi, Arabic) suffer $4\times$ higher inference latency, significantly higher cost per query, and frequent context truncation errors compared to English inputs of equal word length. What is happening, and how do you fix it?"*

#### Candidate Response Framework:

1. **Root Cause Analysis**:
   * **Subword Fragmentation (Byte Fallback Overhead)**:
     BPE tokenizers built predominantly on English text allocate most of their $V$-sized vocabulary to Latin-based character sequences. Unseen non-Latin characters (e.g., Devanagari script) cannot be mapped to dedicated vocabulary tokens.
   * The tokenizer drops back to single-byte UTF-8 tokenization. A single non-Latin character can require 3 to 4 UTF-8 bytes, mapping to 3–4 individual tokens per character.
   * A 100-word English prompt might map to $\sim 130$ tokens, whereas an equivalent 100-word Hindi prompt might tokenize into $\sim 600$ tokens. This drastically inflates generation latency (due to autoregressive sequence steps) and operational cost.

```
Tokenization Disparity Example:
Input: "Hello"  ──> Tokenizer ──> ["Hello"]           (1 Token)
Input: "नमस्ते" ──> Tokenizer ──> [0xE0, 0xA4, 0xA8,  (Multi-Byte Fallback Splits:
                                  0xE0, 0xA4, 0xAE,   9+ Tokens)
                                  0xE0, 0xA5, ...]
```

2. **Mitigation Strategy**:
   * **Vocabulary Retraining / Expansion**:
     Train a native multi-lingual subword tokenizer using Unigram/BPE over a balanced multi-lingual corpus (e.g., increasing vocabulary size from $32\text{k} \to 128\text{k}$, as seen in Llama-3).
   * **Embedding Layer Resizing Algorithm**:
     Preserve pre-trained weights for existing overlap tokens, while appending newly trained script subword embeddings initialized using target distribution statistics:
     $$E_{\text{new}} \sim \mathcal{N}\left(\mu(E_{\text{base}}), \sigma^2(E_{\text{base}})\right)$$
   * Finetune the updated embedding matrix using masked language modeling or target instruction tuning to align representation spaces across scripts.