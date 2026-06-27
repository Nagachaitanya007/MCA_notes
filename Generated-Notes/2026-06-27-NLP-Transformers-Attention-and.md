---
title: NLP: Transformers, Attention, and Tokenization
date: 2026-06-27T04:32:21.651999
---

# NLP: Transformers, Attention, and Tokenization

---

## 1. 🧱 The Core Concept

### Tokenization: The Information Bottleneck
Before a text sequence enters a neural network, it must be mapped to discrete numerical IDs. Modern NLP relies on subword tokenization to balance vocabulary size ($V$) against sequence length ($L$).

```
Raw Text: "unaffable"
       │
       ▼ (Subword Segmentation)
Tokens:   ["un", "##aff", "##able"]
       │
       ▼ (Vocabulary Mapping)
IDs:      [2103, 18241, 3085]
```

#### Byte-Pair Encoding (BPE)
*   **Algorithm**: Starts with character-level vocabulary. Iteratively counts the most frequent adjacent symbol pairs in the corpus and merges them into a new vocabulary token.
*   **Key Property**: Greedy, deterministic encoding.
*   **Used in**: GPT family, RoBERTa, LLaMA.

#### WordPiece
*   **Algorithm**: Similar to BPE but selects merges based on maximizing the likelihood of the training data according to a unigram language model (maximizing mutual information).
*   **Selection Criterion**: Bridges the gap by merging candidate pairs that maximize:
    $$\text{Score}_{(A, B)} = \frac{\text{count}(A, B)}{\text{count}(A) \times \text{count}(B)}$$
*   **Used in**: BERT, MobileBERT.

#### SentencePiece
*   **Algorithm**: Treats input as a raw byte stream, treating whitespace as a normal character (represented as `_`). It does not require a language-specific pre-tokenizer.
*   **Key Property**: Lossless tokenization (can reconstruct the exact original string including spaces).
*   **Used in**: T5, ALBERT, LLaMA (BPE-variant).

#### The Structural Trade-Off
A critical trade-off exists between vocabulary size $V$ and sequence length $L$:

$$\text{Total Memory} \propto (V \times d_{\text{model}}) + \mathcal{O}(L^2)$$

```
┌────────────────────────────────────────────────────────┐
│               THE TOKENIZATION BALANCE                 │
├───────────────────────────┬────────────────────────────┤
│   Large Vocabulary (V)    │    Small Vocabulary (V)    │
├───────────────────────────┼────────────────────────────┤
│ • Massive Embedding Table │ • Compact Embedding Table  │
│ • Shorter Seq Length (L)  │ • Longer Seq Length (L)    │
│ • Efficient Attention     │ • Quadratic Attention Cost │
│ • Risk of Under-trained   │ • OOV/Byte-level fallback  │
│   rare token embeddings   │   overhead                 │
└───────────────────────────┴────────────────────────────┘
```

---

### Why Self-Attention? (The Demise of LSTMs)
Recurrent Neural Networks (RNNs/LSTMs) process sequences sequentially, creating a temporal bottleneck.

```
LSTM (Sequential):      x₁ ──► h₁ ──► x₂ ──► h₂ ──► x₃ ──► h₃   (Path Length = O(N))

Transformer (Parallel): x₁ ───┐
                        x₂ ───┼──► All-to-all Self-Attention    (Path Length = O(1))
                        x₃ ───┘
```

#### 1. Computational Complexity & Parallelization
To compute hidden state $h_t$, an LSTM must wait for $h_{t-1}$:
$$\mathcal{O}(L) \text{ sequential operations}$$
This prevents parallelization across the sequence dimension on modern hardware (GPUs/TPUs). Transformers calculate attention representations for all tokens in parallel, reducing the sequential operation path complexity to $\mathcal{O}(1)$.

#### 2. Information Bottleneck & Path Length
In an LSTM, long-range dependencies must travel through a chain of sequential updates. The maximum path length between any two tokens is $\mathcal{O}(L)$, leading to gradient vanishing or representation washing. Self-attention guarantees a maximum path length of $\mathcal{O}(1)$ between any two tokens, regardless of their distance in the sequence.

---

## 2. ⚙️ Under the Hood

### Complete Transformer Architecture

```
                       ENCODER                                                DECODER
             ┌─────────────────────────┐                            ┌─────────────────────────┐
             │       Input Tokens      │                            │      Target Tokens      │
             └────────────┬────────────┘                            └────────────┬────────────┘
                          ▼                                                      ▼
             ┌─────────────────────────┐                            ┌─────────────────────────┐
             │     Token Embedding     │                            │     Token Embedding     │
             └────────────┬────────────┘                            └────────────┬────────────┘
                          ▼                                                      ▼
             ┌─────────────────────────┐                            ┌─────────────────────────┐
             │    Positional Encoding  │                            │    Positional Encoding  │
             └────────────┬────────────┘                            └────────────┬────────────┘
                          ▼                                                      ▼
                  ┌───────┴───────┐                                      ┌───────┴───────┐
                  ▼               │ (Residual)                           ▼               │ (Residual)
           ┌─────────────┐        │                               ┌─────────────┐        │
           │   Pre-LN    │        │                               │   Pre-LN    │        │
           └──────┬──────┘        │                               └──────┬──────┘        │
                  ▼               │                                      ▼               │
           ┌─────────────┐        │                               ┌─────────────┐        │
           │  Multi-Head │        │                               │Masked Multi-│        │
           │  Attention  │        │                               │Head Attend  │        │
           └──────┬──────┘        │                               └──────┬──────┘        │
                  ▼               │                                      ▼               │
                  ├◄──────────────┘                                      ├◄──────────────┘
                  ▼                                                      ▼
           ┌─────────────┐                                        ┌─────────────┐
           │     Add     │                                        │     Add     │
           └──────┬──────┘                                        └──────┬──────┘
                  ▼                                                      ▼
                  ├──────────────────┐ (Residual)                        ├───────┬───────┐ (Residual)
                  ▼                  │                                   ▼       │       │
           ┌─────────────┐           │                            ┌─────────────┐│       │
           │   Pre-LN    │           │                            │   Pre-LN    ││       │
           └──────┬──────┘           │                            └──────┬──────┘│       │
                  ▼                  │                                   ▼       │       │
           ┌─────────────┐           │                            ┌─────────────┐│       │
           │ FeedForward │           │                            │  Cross-Head ││       │
           │   (FFN)     │           │                            │  Attention  ││       │
           └──────┬──────┘           │                            └──────┬──────┘│       │
                  ▼                  │                                   ▼       │       │
                  ├◄─────────────────┘                                   ├◄──────┘       │
                  ▼                                                      ▼               │
           ┌─────────────┐                                        ┌─────────────┐        │
           │     Add     │                                        │     Add     │        │
           └──────┬──────┘                                        └──────┬──────┘        │
                  ▼                                                      ▼               │
                  └──────────────┬───────────────────────────────────────┼───────────────┘
                                 │                                       ▼
                                 │                                ┌─────────────┐
                                 │                                │   Pre-LN    │
                                 │                                └──────┬──────┘
                                 │                                       ▼
                                 │                                ┌─────────────┐
                                 │                                │ FeedForward │
                                 └───────────────────────────────►│   (FFN)     │
                                                                  └──────┬──────┘
                                                                         ▼
                                                                  ┌─────────────┐
                                                                  │     Add     │
                                                                  └──────┬──────┘
                                                                         ▼
                                                                  ┌─────────────┐
                                                                  │ Linear Out  │
                                                                  └──────┬──────┘
                                                                         ▼
                                                                  ┌─────────────┐
                                                                  │   Softmax   │
                                                                  └─────────────┘
```

---

### Mathematical Breakdown of Scaled Dot-Product Attention

Given an input matrix $H \in \mathbb{R}^{L \times d_{\text{model}}}$, we project it to Queries ($Q$), Keys ($K$), and Values ($V$) using weight matrices $W_Q, W_K, W_V \in \mathbb{R}^{d_{\text{model}} \times d_k}$:

$$Q = H W_Q, \quad K = H W_K, \quad V = H W_V$$

The attention equation is defined as:

$$\text{Attention}(Q, K, V) = \text{softmax}\left(\frac{Q K^T}{\sqrt{d_k}}\right) V$$

#### Why the scaling factor $\sqrt{d_k}$ is critical
Consider two independent random vectors $q, k \in \mathbb{R}^{d_k}$ with elements of mean 0 and variance 1. Their dot product $q \cdot k = \sum_{i=1}^{d_k} q_i k_i$ has:

$$\mathbb{E}[q \cdot k] = 0, \quad \text{Var}(q \cdot k) = d_k$$

For large values of $d_k$, the dot product yields values with large magnitudes. Passing these unscaled values into the $\text{softmax}$ function pushes it into regions with extremely small gradients (vanishing gradient problem):

$$\lim_{x_i \to \infty} \frac{\partial \text{softmax}(x)_i}{\partial x_j} = 0$$

Dividing the dot product by $\sqrt{d_k}$ scales the variance of the dot product back to 1, preserving stable gradients during backpropagation.

---

### Attention Evolution: MHA vs. MQA vs. GQA

Modern LLM scaling has driven optimizations in attention mechanisms to mitigate the GPU memory bandwidth bottleneck caused by caching Key-Value tensors (KV Cache).

```
Multi-Head Attention (MHA)      Multi-Query Attention (MQA)     Grouped-Query Attention (GQA)
    Q Head    K/V Head               Q Head    K/V Head              Q Head    K/V Head
    ┌───┐      ┌───┐                 ┌───┐      ┌───┐                ┌───┐      ┌───┐
    │ Q1│ ───► │ KV1│                │ Q1│ ──┐   │   │                │ Q1│ ──┐   │   │
    ├───┤      ├───┤                 ├───┤   │   │   │                ├───┤   ├──►│KV1│
    │ Q2│ ───► │ KV2│                │ Q2│ ──┼──►│KV1│                │ Q2│ ──┘   │   │
    ├───┤      ├───┤                 ├───┤   │   │   │                ├───┤      ├───┤
    │ Q3│ ───► │ KV3│                │ Q3│ ──┘   │   │                │ Q3│ ──┐   │   │
    ├───┤      ├───┤                 ├───┤       │   │                ├───┤   ├──►│KV2│
    │ Q4│ ───► │ KV4│                │ Q4│ ──────┘   │                │ Q4│ ──┘   │   │
    └───┘      └───┘                 └───┘       └───┘                └───┘      └───┘
```

#### Multi-Head Attention (MHA)
*   **Structure**: Independent Query, Key, and Value projections for each head.
*   **Formula**:
    $$\text{MultiHead}(Q, K, V) = \text{Concat}(\text{head}_1, \dots, \text{head}_h)W^O$$
*   **Trade-off**: High representational capacity, but high memory footprint during autoregressive generation due to large KV Cache.

#### Multi-Query Attention (MQA)
*   **Structure**: Queries maintain multi-head projections, but Keys and Values are shared across a single head.
*   **Trade-off**: Reduces KV cache memory footprint by a factor of $h$ (number of heads), significantly boosting decoding throughput. However, it can lead to capacity loss and training instability on downstream tasks.

#### Grouped-Query Attention (GQA)
*   **Structure**: A generalization of MQA. Queries are grouped into $g$ partitions; each partition shares a single Key and Value head.
*   **Trade-off**: Interpolates between MHA and MQA. It achieves near-MHA quality with near-MQA speed.

---

### Positional Encodings: Absolute vs. Relative vs. RoPE

Because self-attention is permutation-invariant, positional information must be explicitly injected.

#### Sinusoidal Absolute Position Encodings (Original Transformer)
Adds fixed high-frequency and low-frequency sinusoidal waves directly to the input embeddings:

$$PE_{(pos, 2i)} = \sin\left(\frac{pos}{10000^{2i/d_{\text{model}}}}\right)$$
$$PE_{(pos, 2i+1)} = \cos\left(\frac{pos}{10000^{2i/d_{\text{model}}}}\right)$$

*   **Limitation**: Does not scale well to sequences longer than those seen during training (poor extrapolation).

#### Rotary Position Embedding (RoPE)
Instead of adding positional vectors to embeddings, RoPE rotates the Query and Key vectors in 2D planes by an angle proportional to their sequence position.

Given a 2D vector $x = (x_1, x_2)^T$ at position $m$, we apply:

$$R_{\Theta, m}^2 x = \begin{pmatrix} \cos m\theta & -\sin m\theta \\ \sin m\theta & \cos m\theta \end{pmatrix} \begin{pmatrix} x_1 \\ x_2 \end{pmatrix}$$

By structuring the rotation this way, the inner product of Query $q$ at position $m$ and Key $k$ at position $n$ becomes:

$$\langle R_{\Theta, m}^d q, R_{\Theta, n}^d k \rangle = g(q, k, m - n)$$

*   **Why it's superior**:
    1.  **Relative Distance Preservation**: The attention score naturally depends only on the relative distance $m-n$.
    2.  **Decay with Distance**: The boundary of the inner product decays as distance increases, matching natural language priors.
    3.  **Extrapolation**: Enables out-of-distribution context window expansion (e.g., using techniques like YaRN or RoPE scaling).

---

### Layer Normalization: Pre-LN vs. Post-LN

```
Post-LN (Original):  x ──► SubLayer ──► Add ──► LayerNorm ──► NextLayer
                      │                  ▲
                      └──────────────────┘

Pre-LN (Modern):     x ──► LayerNorm ──► SubLayer ──► Add ──► NextLayer
                      │                                ▲
                      └────────────────────────────────┘
```

#### Post-LN
*   **Equation**: $x_{l+1} = \text{LayerNorm}(x_l + \text{SubLayer}(x_l))$
*   **Characteristics**: The scale of gradients near the output layer is significantly larger than near the input layer. This requires a strict learning rate warm-up phase to prevent gradient explosion at the start of training.

#### Pre-LN
*   **Equation**: $x_{l+1} = x_l + \text{SubLayer}(\text{LayerNorm}(x_l))$
*   **Characteristics**: Gradients flow freely through the residual connection shortcut, bypassing the normalization layers. This provides superior training stability, allows training without warm-up, and enables scaling to deep (>100 layers) network architectures.

---

## 3. ⚠️ The Interview Warzone

### Scenario 1: Scaling Context Length to 100k+ Tokens
**Interviewer**: *"We are training an LLM with a 128k context window. Standard attention out-of-memory (OOM) errors instantly, even on H100s. How do you design around this computational bottleneck?"*

#### The Deep Dive & Probing Patterns
An expert candidate must show that they understand how GPU memory hierarchies operate, specifically comparing **High-Bandwidth Memory (HBM)** and **SRAM**.

```
                           ┌───────────────────────────┐
                           │    GPU HBM (High-Bandwd)  │
                           └─────────────┬─────────────┘
                                         ▲ Read Q, K
                                         ▼ Write Attention Matrix (O(L²)) -- Slow!
                           ┌───────────────────────────┐
                           │      GPU SRAM (Fast)      │
                           └─────────────┬─────────────┘
                                         ▲
                                         │ Compute softmax block-by-block
                                         ▼
                           ┌───────────────────────────┐
                           │     Tensor Core Execution │
                           └───────────────────────────┘
```

#### The Perfect Response
To resolve this bottleneck, we must address the $\mathcal{O}(L^2)$ memory footprint of the attention matrix. The solution requires a multi-tiered approach:

##### 1. FlashAttention (IO-Aware Exact Attention)
The bottleneck in standard attention is not compute, but **memory bandwidth** (constantly writing and reading the $L \times L$ attention matrix between slow GPU HBM and fast GPU SRAM).

*   **How it works**:
    1.  **Tiling**: We load blocks of $Q, K, V$ from HBM to SRAM.
    2.  **Online Softmax**: We compute softmax block-by-block without storing the intermediate $L \times L$ attention matrix. Standard softmax requires seeing all elements to compute the denominator:
        $$m(x) = \max_i x_i, \quad f(x) = e^{x_i - m(x)}, \quad d(x) = \sum_i f(x)_i$$
        We can update the softmax normalization scales incrementally:
        $$m_{\text{new}} = \max(m_{\text{old}}, m_{\text{block}})$$
        $$d_{\text{new}} = d_{\text{old}} \cdot e^{m_{\text{old}} - m_{\text{new}}} + d_{\text{block}} \cdot e^{m_{\text{block}} - m_{\text{new}}}$$
    3.  **Recomputation**: During the backward pass, we do not store the activation attention matrix. Instead, we recompute it on the fly in SRAM from the tiled $Q, K, V$ blocks, trading compute (flops are cheap) for memory bandwidth (IO is expensive).

##### 2. Linear/Sparse Attention Alternatives
*   **Sliding Window Attention (SWA)**: Restricts attention to a local window $W$ around each token. This reduces the complexity to $\mathcal{O}(L \times W)$, which can be stacked across layers to achieve a receptive field of $D \times W$ (where $D$ is depth).
*   **Linear Attention**: Decouples the softmax computation by leveraging the kernel trick:
    $$\text{Attention}(Q, K, V) = \phi(Q) \left(\phi(K)^T V\right)$$
    This changes the computation order to $(L \times d) \times (d \times L) \implies L \times L$, resulting in $\mathcal{O}(L)$ complexity.

---

### Scenario 2: KV Cache Optimization during Inference
**Interviewer**: *"Walk me through the exact memory footprint of the KV Cache during autoregressive decoding. How do we calculate its size, and how do we resolve the fragmentation bottleneck in production?"*

#### The Calculation (Show Your Math)
During decoding, the model generates one token at a time. To avoid recalculating Key and Value vectors for historical tokens at every step, we store them in the **KV Cache**.

$$\text{Memory}_{\text{KVCache}} = 2 \times B \times L \times n_{\text{layers}} \times n_{\text{kv\_heads}} \times d_{\text{head}} \times \text{BytesPerPrecision}$$

Let's calculate this footprint for a **LLaMA-3-8B** model in **FP16** precision ($2\text{ bytes}$), with a batch size of $16$ and a sequence length of $8192$:
*   $n_{\text{layers}} = 32$
*   $n_{\text{kv\_heads}} = 8$ (Grouped-Query Attention)
*   $d_{\text{head}} = 128$

$$\text{Memory} = 2 \times 16 \times 8192 \times 32 \times 8 \times 128 \times 2\text{ bytes}$$
$$\text{Memory} = 2 \times 16 \times 8192 \times 32 \times 8 \times 128 \times 2 = 17,179,869,184\text{ bytes} \approx \mathbf{17.18\text{ GB}}$$

This indicates that storing the KV cache for just 16 active users consumes more memory than the model's parameters themselves (~16 GB in FP16).

```
                      KV CACHE ALLOCATION COMPARISON
                      
Traditional Contiguous Allocation:
┌───────────────┬───────────────────────────────┬─────────────────┐
│ User 1 (200)  │  Wasted / Unused Space (7800) │ User 2 (50) ... │ (Static Pre-allocation)
└───────────────┴───────────────────────────────┴─────────────────┘

PagedAttention (Virtual Memory):
┌───────────────┬───────────────┬───────────────┬─────────────────┐
│ Page A (User1)│ Page B (User2)│ Page C (User1)│ Free Page Block │ (Dynamic Mapping)
└───────┬───────┴───────┬───────┴───────┬───────┴────────┬────────┘
        │               │               │                │
        ▼               ▼               ▼                ▼
     [Block 0]       [Block 1]       [Block 2]       [Block 3]  (Physical GPU Memory)
```

#### Solving the Fragmentation Bottleneck (PagedAttention)
Traditional serving systems allocate contiguous memory blocks for the maximum possible sequence length (e.g., 8k tokens) up front. This leads to severe memory waste:
1.  **Internal Fragmentation**: Allocating memory for 8k tokens when the current generation is only at 100 tokens.
2.  **External Fragmentation**: Memory allocations of varying sizes preventing cohesive memory utilization.

##### The Solution: PagedAttention (vLLM)
We can resolve this bottleneck by borrowing virtual memory paging principles from operating systems:
*   **How it works**:
    1.  The KV Cache for a request is partitioned into fixed-size **physical blocks** (e.g., 16 tokens per block).
    2.  Instead of contiguous allocation, blocks are mapped dynamically to non-contiguous physical memory locations via a **Page Table**.
    3.  During attention computation, the GPU kernels fetch the keys and values by resolving block addresses through the lookup table.
*   **Impact**: Eliminates nearly all memory waste (reducing it to under 4% for the final, partially filled block), which allows serving systems to increase batch sizes by 2x to 4x.

---

### Scenario 3: Vectorized PyTorch Implementation of Multi-Head Attention
**Interviewer**: *"I need you to write a clean, production-grade PyTorch implementation of Multi-Head Attention. Do not use loops over the attention heads. Ensure you handle the batch dimension and support an optional causal mask."*

```
                              SHAPE TRANSFORMATION FLOW
                              
  Input: [B, L, D]
     │
     ▼ (Linear Projections)
  Q, K, V: [B, L, D]
     │
     ▼ (Reshape & Transpose)
  Q, K, V: [B, H, L, d_k]
     │
     ├──────────────────────────────────────────┐
     ▼ (MatMul Q @ K^T)                         │
  Scores: [B, H, L, L]                          │
     │                                          │
     ▼ (Scale & Apply Causal Mask)              │
  Softmax Scores: [B, H, L, L]                  │
     │                                          │
     ├──────────────────────────────────────────┘
     ▼ (MatMul Scores @ V)
  Context: [B, H, L, d_k]
     │
     ▼ (Transpose & Reshape)
  Output: [B, L, D]
```

#### The Code Implementation

```python
import torch
import torch.nn as nn
import torch.nn.functional as F
import math

class MultiHeadAttention(nn.Module):
    def __init__(self, d_model: int, n_heads: int):
        super().__init__()
        assert d_model % n_heads == 0, "d_model must be divisible by n_heads"
        
        self.d_model = d_model
        self.n_heads = n_heads
        self.d_k = d_model // n_heads
        
        # Combined projection weights for parallel calculation
        self.q_proj = nn.Linear(d_model, d_model, bias=False)
        self.k_proj = nn.Linear(d_model, d_model, bias=False)
        self.v_proj = nn.Linear(d_model, d_model, bias=False)
        
        self.out_proj = nn.Linear(d_model, d_model, bias=False)
        
    def forward(self, x: torch.Tensor, mask: torch.Tensor = None) -> torch.Tensor:
        """
        Args:
            x: Input tensor of shape [Batch_Size (B), Seq_Len (L), d_model (D)]
            mask: Optional binary mask [B, 1, L, L] or [1, 1, L, L] indicating elements 
                  to ignore (-inf) in softmax.
        Returns:
            Attention output of shape [B, L, D]
        """
        B, L, D = x.shape
        
        # 1. Project inputs to Q, K, V
        # Shape: [B, L, D] -> [B, L, D]
        q = self.q_proj(x)
        k = self.k_proj(x)
        v = self.v_proj(x)
        
        # 2. Reshape and transpose to split into heads
        # Shape: [B, L, D] -> [B, L, H, d_k] -> [B, H, L, d_k]
        q = q.view(B, L, self.n_heads, self.d_k).transpose(1, 2)
        k = k.view(B, L, self.n_heads, self.d_k).transpose(1, 2)
        v = v.view(B, L, self.n_heads, self.d_k).transpose(1, 2)
        
        # 3. Calculate Scaled Dot-Product Attention Scores
        # [B, H, L, d_k] x [B, H, d_k, L] -> [B, H, L, L]
        scores = torch.matmul(q, k.transpose(-2, -1)) / math.sqrt(self.d_k)
        
        # 4. Apply optional mask (e.g., Causal Masking)
        if mask is not None:
            # Mask should fill 0 positions with a large negative value
            scores = scores.masked_fill(mask == 0, -1e9)
            
        # 5. Softmax along the last dimension (the key dimension)
        attn_probs = F.softmax(scores, dim=-1)
        
        # 6. Weight values by attention probabilities
        # [B, H, L, L] x [B, H, L, d_k] -> [B, H, L, d_k]
        context = torch.matmul(attn_probs, v)
        
        # 7. Concatenate heads and project output
        # [B, H, L, d_k] -> [B, L, H, d_k] -> [B, L, D]
        context = context.transpose(1, 2).contiguous().view(B, L, D)
        
        return self.out_proj(context)

# Quick Sanity Check Execution
if __name__ == "__main__":
    B, L, D, H = 2, 8, 512, 8
    x = torch.randn(B, L, D)
    mha = MultiHeadAttention(d_model=D, n_heads=H)
    
    # Create an upper-triangular causal mask
    causal_mask = torch.tril(torch.ones(L, L)).view(1, 1, L, L)
    
    out = mha(x, mask=causal_mask)
    print(f"Input Shape: {x.shape}")
    print(f"Output Shape: {out.shape}")
    assert out.shape == (B, L, D), "Output shape mismatch!"
```