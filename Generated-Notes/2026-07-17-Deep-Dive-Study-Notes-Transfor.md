---
title: 🧠 Deep-Dive Study Notes: Transformers, Attention, and Tokenization
date: 2026-07-17T04:31:58.927302
---

# 🧠 Deep-Dive Study Notes: Transformers, Attention, and Tokenization
**Target Audience:** L6+ (Senior / Staff) System Design & ML Engineering Candidates

---

## 🧱 1. The Core Concept (Basics Refresh)

To design, optimize, or debug large-scale NLP systems, you must understand the mathematical and systemic foundation of modern sequence transduction.

```
+---------------------------------------------------------------------------------+
|                               Transformer Architecture                          |
+---------------------------------------------------------------------------------+
|                                                                                 |
|   [ Input Tokens ] ---> [ Token Embeddings ] ---> [ Rotary Positional (RoPE) ]  |
|                                 |                                               |
|                                 v                                               |
|               +-----------------------------------+                             |
|               |       Pre-RMSNorm (Stabilization) |                             |
|               +-----------------------------------+                             |
|                                 |                                               |
|                                 v                                               |
|               +-----------------------------------+                             |
|       +-----> |     Multi-Head/Grouped Attention  | -----+ (Residual Add)       |
|       |       +-----------------------------------+      |                      |
|       |                         |                        |                      |
|       |                         v                        |                      |
|       |       +-----------------------------------+      |                      |
|       |       |       Pre-RMSNorm (Stabilization) |      |                      |
|       |       +-----------------------------------+      |                      |
|       |                         |                        |                      |
|       |                         v                        |                      |
|       |       +-----------------------------------+      |                      |
|       +-----> |     SwiGLU Feed-Forward Network   | <----+                      |
|               +-----------------------------------+                             |
|                                 |                                               |
|                                 v                                               |
|               [ Layer Outputs / Unembedded Logits ]                             |
+---------------------------------------------------------------------------------+
```

### Subword Tokenization: The Compression Engine
Models do not read characters or words; they read mathematical abstractions. The vocabulary ($V$) must balance two opposing forces:
1. **Sequence Length ($L$):** Small vocabularies (e.g., character-level) generate long sequences, causing memory consumption to balloon because attention scales quadratically ($O(L^2)$).
2. **Model Width ($d_{model}$):** Large vocabularies require massive projection matrices ($V \times d_{model}$), which wastes GPU memory on parameters for rare tokens.

Subword tokenizers (BPE, WordPiece, Unigram) resolve this conflict by breaking rare words into subword fragments while keeping common words intact.

### Attention: The $O(L^2)$ Memory Bottleneck
Standard scaled dot-product attention computes the routing matrix of how tokens relate to each other:

$$\text{Attention}(Q, K, V) = \text{softmax}\left(\frac{QK^T}{\sqrt{d_k}}\right)V$$

#### Why the scaling factor $\sqrt{d_k}$ is mathematically necessary
For large projection dimensions $d_k$, the dot product $QK^T$ grows large in magnitude. 

Assuming components of $q$ and $k$ are independent random variables with mean $0$ and variance $1$, their dot product has mean $0$ and variance $d_k$. 

If we do not scale it by $\frac{1}{\sqrt{d_k}}$, the variance of the dot product is $d_k$. For large $d_k$, this pushes the softmax function into regions with extremely small gradients (vanishing gradient problem), stalling training. Scaling pulls the variance back to $1$.

### Why Transformers Surpassed RNNs
Recurrent Neural Networks (RNNs/LSTMs) require sequential processing: step $t$ depends on step $t-1$. This sequential dependency prevents parallel execution across GPU cores during training. 

Transformers eliminate step-wise recurrence by processing the entire sequence simultaneously, using attention to resolve token dependencies in parallel.

---

## ⚙️ 2. Under the Hood (Internal Mechanics & Architecture)

### 2.1 Tokenization Algorithms in Production

| Algorithm | Merging / Splitting Criterion | Primary Users | Key Characteristics |
| :--- | :--- | :--- | :--- |
| **BPE (Byte-Pair Encoding)** | Frequency-driven. Starts with individual bytes/characters and iteratively merges the most frequent pairs. | GPT-4, LLaMA, RoBERTa | Robust against Out-Of-Vocabulary (OOV) tokens because it can fall back to raw byte representations. |
| **WordPiece** | Likelihood-driven. Merges pairs that maximize the likelihood of the training data according to a unigram language model. | BERT, DistilBERT | Uses an explicit prefix (e.g., `##`) to identify subwords. High focus on morphological cohesion. |
| **Unigram** | Entropy-driven. Starts with a huge vocabulary and iteratively prunes the least useful tokens based on validation loss. | T5, SentencePiece | Probabilistic tokenization. Enables tokenization sampling during training (regularization). |

#### Production Failure Modes of Tokenizers
* **Adversarial Tokens / Glitch Tokens:** Under-represented strings in the training set (e.g., `" SolidGoldMagikarp"` or `" RedditUser"` in early GPT-3/4 tokenizers) map to specific vector addresses that the model never learned to regularize. Prompting with these tokens causes erratic, unpredictable model behavior.
* **Digit Fragmentation:** Tokenizing `123456` as `[12, 34, 56]` or `[1, 234, 56]` breaks numerical representations, making basic arithmetic difficult for LLMs. Modern models (such as LLaMA 3) split digits individually (`[1, 2, 3, 4, 5, 6]`) to preserve consistent numerical representations.

---

### 2.2 The Attention Evolution: MHA $\rightarrow$ MQA $\rightarrow$ GQA

```
  Multi-Head (MHA)            Grouped-Query (GQA)           Multi-Query (MQA)
    
     Q   Q   Q   Q                Q   Q   Q   Q                Q   Q   Q   Q
     |   |   |   |                |   |   |   |                |   |   |   |
     V   V   V   V                \   /   \   /                \   |   /   /
    [K] [K] [K] [K]                [K]     [K]                  \ [K] /
    [V] [V] [V] [V]                [V]     [V]                    [V]
```

As sequence lengths grow, the **KV Cache** (storing key-value states to avoid recomputing them during autoregressive generation) dominates GPU memory. This shift from computer-bound to memory-bound execution led to these structural evolutions:

* **Multi-Head Attention (MHA):** Every query head has its own Key ($K$) and Value ($V$) head.
  $$\text{Memory Overhead} \propto H \times d_{head}$$
* **Multi-Query Attention (MQA):** All query heads share a single Key and Value head. While this reduces KV cache memory consumption by $H\times$, it degrades representation capacity, leading to lower quality on complex tasks.
* **Grouped-Query Attention (GQA):** Query heads are partitioned into $G$ groups. Each group shares a single KV head. GQA matches the speed of MQA while retaining most of the model capacity of MHA.

---

### 2.3 FlashAttention: Overcoming Memory Bandwidth Bottlenecks

Standard PyTorch implementation of Attention writes the $N \times N$ attention matrix to High Bandwidth Memory (HBM), reads it back for softmax, writes it back to HBM, reads it for multiplication with $V$, and writes again. 

Because GPU compute engines (SRAM) run much faster than memory buses (HBM), this constant reading and writing makes attention calculation **memory-bound, not compute-bound**.

```
Standard Attention (HBM BottleNeck):
  SRAM (Fast) <=======> HBM (Slow: Write QK^T) <=======> SRAM (Softmax) <=======> HBM (Write Softmax Output)

FlashAttention (Tiling in SRAM):
  HBM (Slow) ----[ Read Q, K, V Blocks ]----> SRAM (Compute Local Attention & Online Softmax) ----[ Write final block ]----> HBM
```

**FlashAttention** rewrites this execution flow using **Tiling**:
1. It loads blocks of $Q, K, and V$ from slow HBM into fast, local on-chip SRAM.
2. It computes attention on these blocks.
3. It uses **online softmax** to track scaling factors without needing the entire attention matrix in memory:
   $$\tilde{m}(x) = \max(x), \quad \tilde{d}(x) = \sum e^{x_i - \tilde{m}(x)}$$
4. It updates the softmax normalization factor incrementally and writes the final output directly back to HBM. This reduces HBM accesses from $O(N^2)$ to $O(N)$, speeding up execution by $2\times$ to $4\times$.

---

### 2.4 Positional Encodings: From Absolute to Rotary

Without positional information, attention is permutation-invariant (it functions as a bag-of-words model).

* **Absolute Position Embeddings:** Adding a fixed vector (e.g., Sinusoidal) or a learned parameter directly to the token embedding: $\mathbf{x}_i = \mathbf{e}_i + \mathbf{p}_i$. This approach fails to generalize to sequences longer than those seen during training because the model has no mechanism to interpret unlearned position embeddings.
* **Rotary Position Embedding (RoPE):** Rather than adding a position vector, RoPE rotates the Query and Key projection vectors in the 2D complex plane at a rate proportional to their index position $m$:

$$\mathbf{R}_{\Theta, m}^{d} \mathbf{x} = \text{diag}\left( \mathbf{R}_{\theta_1, m}, \mathbf{R}_{\theta_2, m}, \dots, \mathbf{R}_{\theta_{d/2}, m} \right) \mathbf{x}$$

where $\mathbf{R}_{\theta_i, m}$ is a 2D rotation matrix:

$$\mathbf{R}_{\theta_i, m} = \begin{pmatrix} \cos(m\theta_i) & -\sin(m\theta_i) \\ \sin(m\theta_i) & \cos(m\theta_i) \end{pmatrix}$$

#### Why RoPE is the Industry Standard
RoPE embeds relative distance directly into the dot product. The inner product of rotated queries and keys depends only on their relative distance $m-n$:

$$\langle \mathbf{R}_m \mathbf{q}, \mathbf{R}_n \mathbf{k} \rangle = \mathbf{q}^T \mathbf{R}_{n-m} \mathbf{k}$$

This relative distance modeling allows you to scale context windows during inference using interpolation techniques (such as YaRN or RoPE scaling) without retraining the model from scratch.

---

### 2.5 Layer Normalization: Pre-LN vs. Post-LN vs. RMSNorm

```
Post-LN (Historically BERT):
  Input ---> [ Attention/FFN ] ---> [ Add ] ---> [ LayerNorm ] ---> Output
  (Prone to exploding/vanishing gradients at scale; requires warm-up)

Pre-LN (Modern Standard):
  Input ---> [ LayerNorm ] ---> [ Attention/FFN ] ---> [ Add ] ---> Output
  (Stable gradients; supports direct identity path)

RMSNorm (Optimized Pre-LN):
  Input ---> [ RootMeanSquareNorm ] ---> [ Attention/FFN ] ---> [ Add ] ---> Output
  (Saves 7-10% of element-wise execution time by skipping mean computation)
```

* **Post-LN:** Used in early models like BERT. Normalization occurs after the residual connection. This places the residual addition before the normalization layer, which can cause gradients to vanish or explode in deeper layers. This setup requires careful learning rate warmups.
* **Pre-LN:** Normalization occurs along the residual branches before the attention or FFN computations. This creates a clean, unimpeded gradient highway directly from the final layer to the initial embedding layer, which stabilizes training at scale.
* **RMSNorm:** A faster alternative to Pre-LN. Instead of calculating both the mean and variance to normalize, it normalizes using only the Root Mean Square:

$$\text{RMSNorm}(\mathbf{x}) = \frac{\mathbf{x}}{\text{RMS}(\mathbf{x})} \odot \mathbf{\gamma}, \quad \text{where } \text{RMS}(\mathbf{x}) = \sqrt{\frac{1}{d} \sum_{i=1}^d x_i^2}$$

This saves computational steps by omitting the mean calculation, which speeds up element-wise operations by $7\%\text{ to }10\%$.

---

## ⚠️ 3. The Interview Warzone

This section presents high-stakes scenario questions common in FAANG ML System Design and Engineering loops.

### Scenario 1: The KV Cache Memory Bottleneck during Scale-out

#### Interviewer
> "We are deploying a LLaMA-3-8B model with a 128k context window to production. Our current serving stack is running out of GPU memory (OOM) during the generation phase, even at a batch size of 2. 
>
> Walk me through the mathematical formulation of the KV Cache size for this configuration. Identify where the memory bottleneck lies, and propose a concrete system-level mitigation plan."

```
+---------------------------------------------------------------------------------------+
|                              KV Cache Memory Allocation Map                           |
+---------------------------------------------------------------------------------------+
|  Model Weights (FP16 / Int8)  |                   KV Cache Space                      |
|                               |  [Batch 1, Layer 1] Key [s1, s2, ..., s128k]          |
|  ~16 GB (Static Overhead)     |  [Batch 1, Layer 1] Val [s1, s2, ..., s128k]          |
|                               |                     ...                               |
|                               |  [Batch 2, Layer 32] Key [s1, s2, ..., s128k]         |
|                               |  🚀 Dynamic Size: OOM Risk with long contexts         |
+---------------------------------------------------------------------------------------+
```

#### Candidate Analysis (The Math)
First, let's calculate the size of the model parameters. An 8-billion parameter model using 16-bit precision (FP16/BF16, which is 2 bytes per parameter) requires:

$$\text{Static Parameter Weight Memory} = 8 \times 10^9 \text{ parameters} \times 2 \text{ bytes} \approx 16 \text{ GB}$$

Now let's compute the size of the Key-Value (KV) cache. LLaMA-3-8B has the following architecture:
* **Number of Layers ($n_{layers}$):** $32$
* **Query Heads:** $32$
* **Key/Value Heads ($n_{heads\_kv}$):** $8$ (Using GQA with a group ratio of 4:1)
* **Head Dimension ($d_{head}$):** $128$
* **Context Window ($L$):** $131,072$ tokens
* **Precision ($\text{Bytes per element}$):** $2$ (FP16)
* **Batch Size ($B$):** $2$

For every token generated, we must cache both the Key and Value vectors across all layers for active sessions. The memory required for the KV Cache is:

$$\text{Memory}_{\text{KVCache}} = 2 \times n_{layers} \times n_{heads\_kv} \times d_{head} \times B \times L \times \text{Bytes per element}$$

Let's plug in the numbers:

$$\text{Memory}_{\text{KVCache}} = 2 \times 32 \times 8 \times 128 \times 2 \times 131,072 \times 2 \text{ bytes}$$

$$\text{Memory}_{\text{KVCache}} = 65,536 \times 2 \times 131,072 \times 2 \text{ bytes}$$

$$\text{Memory}_{\text{KVCache}} = 34,359,738,368 \text{ bytes} \approx 34.36 \text{ GB}$$

#### The Bottleneck
While the model weights require a static **$16\text{ GB}$**, the dynamic KV Cache requires **$34.36\text{ GB}$** at a batch size of 2 with full context. 

This brings the total memory footprint to **$50.36\text{ GB}$**, which exceeds the capacity of an NVIDIA A10G (24 GB) or a standard A100 (40 GB) GPU, resulting in an Out-Of-Memory (OOM) error.

```
Total Memory (50.36 GB) = Model Weights (16 GB) + Dynamic KV Cache (34.36 GB)
                                                       |
                                            🚨 Exceeds 40 GB GPU Capacity!
```

---

#### Candidate System Design Proposal

```
+------------------------------------------------------------------------------------+
|                         PagedAttention Memory Architecture                         |
+------------------------------------------------------------------------------------+
|                                                                                    |
|  Virtual Memory Space (Logical Tokens)                                             |
|  [Block 0: Tokens 0-3] ---> [Block 1: Tokens 4-7] ---> [Block 2: Tokens 8-11]      |
|                                                                                    |
|  Page Table Map                                                                    |
|  Logical Block 0 ---> Physical Page 14                                             |
|  Logical Block 1 ---> Physical Page 2                                              |
|  Logical Block 2 ---> Physical Page 89                                             |
|                                                                                    |
|  Physical Memory Space (GPU VRAM)                                                  |
|  +-------------------------------------+-------------------------------------+     |
|  | Page 2 (Logical Block 1)            | Page 14 (Logical Block 0)           |     |
|  +-------------------------------------+-------------------------------------+     |
|  | Page 89 (Logical Block 2)           | Free Space                          |     |
|  +-------------------------------------+-------------------------------------+     |
|                                                                                    |
+------------------------------------------------------------------------------------+
```

1. **PagedAttention (vLLM implementation):**
   * *The Problem:* Traditional engines pre-allocate contiguous memory blocks for the maximum context length ($128\text{k}$), which leads to internal fragmentation. This pre-allocation wastes up to $60\%\text{ to }80\%$ of KV cache memory on unused future tokens.
   * *The Solution:* Decouple the logical token sequences from physical memory allocations. Store KV parameters in non-contiguous physical pages (e.g., block size of 16 tokens). Use an operating-system-style Page Table to map logical sequence steps to physical GPU memory addresses. This reduces memory waste from fragmentation to less than $4\%$, freeing up space to support higher batch sizes.

2. **KV Cache Quantization (FP8 / INT4):**
   * Quantize the Key and Value vectors in the cache from FP16 (2 bytes) to FP8 (1 byte) or INT4 (0.5 bytes) during execution. This reduces the cache's memory footprint by $2\times$ or $4\times$, respectively.
   * *Mitigation of Quantization Loss:* Implement per-channel or per-token scale factors to preserve generation quality and prevent degradation in perplexity.

3. **Context Window Partitioning with Tensor Parallelism (TP):**
   * Partition the query, key, and value attention projections across multiple GPUs (e.g., using Megatron-LM Tensor Parallelism). For a system with TP=2, the key-value heads are divided among the GPUs ($n_{heads\_kv} = 4$ per GPU), which cuts the KV cache memory footprint per device in half.

---

### Scenario 2: Tokenization-Induced Numerical and Context Drift

#### Interviewer
> "We are operating an automated financial analytics platform. Users query our RAG (Retrieval-Augmented Generation) system with prompts like:
> `"Calculate the difference in net income between 1204500 and 1201100"`
>
> We notice that the model frequently outputs incorrect calculations. Additionally, if there are trailing whitespaces in our prompt templates, such as:
> `"...Calculate the difference between: "` (with an end space),
> the generation quality degrades significantly compared to:
> `"...Calculate the difference between:"` (no end space).
>
> Why does this happen, and how do we resolve these issues at the API and systemic level?"

#### Candidate Response (The Breakdown)

These anomalies stem from the design of subword tokenizers (such as BPE) rather than issues with the model's core parameter logic.

```
Example Word: " 1204500" 

Case A (Default BPE Tokenization):
  Tokens: [" 120", "45", "00"] ---> Loss of mathematical scale and semantic cohesion

Case B (Enforced Digit Splitting):
  Tokens: ["1", "2", "0", "4", "5", "0", "0"] ---> Preserves digit positions for calculation
```

#### Cause 1: Digit Subword Tokenization Failure
In standard BPE tokenizers (like the one used in GPT-3.5), numbers are tokenized based on their frequency in the training corpus, not their mathematical values:
* `"1204500"` might be tokenized as `["120", "45", "00"]`.
* `"1201100"` might be tokenized as `["12", "011", "00"]`.

Because the numbers are split into different subword structures, the model cannot easily map them to consistent numerical concepts. The attention mechanism fails to align corresponding decimal places, which causes calculation errors during the auto-regressive generation phase.

#### Cause 2: Trailing Space Tokenization Discontinuity
Tokenizers handle words differently depending on whether they are preceded by a space. This leads to distinct token representations:
* `" difference"` (preceded by a space) might map to token ID `4103`.
* `"difference"` (no preceding space) might map to token ID `15403`.

```
Case A: Template ends with "between: " (trailing space)
  The model tokenizes "between:" as [Token 1903] and " " as [Token 220].
  During generation, the next token must follow a raw space, which restricts the model's output options.

Case B: Template ends with "between:" (no trailing space)
  The next word (e.g., " 1204500") is tokenized as [" 120"] (including the leading space).
  This aligns with the model's training data, preserving standard generation quality.
```

If your prompt template ends with a trailing space (`"between: "`), the space is tokenized as its own token (e.g., Token `220`). This prevents the subsequent text from being merged with the space during tokenization, breaking the token patterns the model learned during training. This mismatch degrades prompt performance and increases output instability.

---

#### Concrete Production System Fixes

```
+---------------------------------------------------------------------------------------+
|                       Production Tokenization Pipeline Patches                        |
+---------------------------------------------------------------------------------------+
|  User Input Prompt                                                                    |
|         |                                                                             |
|         v                                                                             |
|  [ Regex & Whitespace Normalization Sanitizer ] ---> Strip trailing whitespace       |
|         |                                                                             |
|         v                                                                             |
|  [ Custom Digit Token Pre-Processor ]            ---> Force "1204500" to "1 2 0 4 5 0 0"|
|         |                                                                             |
|         v                                                                             |
|  [ Tokenizer (BPE / WordPiece) ]                 ---> Aligned, reliable token IDs     |
+---------------------------------------------------------------------------------------+
```

1. **Prompt Stripping and Sanitization Layer:**
   Add a normalization layer to your API gateway to strip trailing whitespaces from prompts before they are tokenized:
   ```python
   # Production Prompt Sanitizer API
   def sanitize_prompt(prompt_template: str) -> str:
       return prompt_template.rstrip()
   ```

2. **Enforce Character-Level/Digit Tokenization Splitting:**
   If you train a custom model, configure the tokenizer's pre-segmentation rules to prevent digits from being grouped into multi-digit tokens:
   ```python
   # Example pre-tokenization regex pattern
   # Splits arbitrary numbers into individual digit tokens
   import re
   def split_digits(text: str) -> str:
       return re.sub(r'(\d)', r' \1 ', text)
   ```

3. **Incorporate Decoder-Side Bias / Native Math Operations:**
   For business-critical calculations, do not rely on the language model's internal arithmetic. Instead, use a regex-based routing layer to extract numerical expressions and evaluate them using a secure sandboxed python execution engine or a library like `NumPy`. You can then return the calculated result directly to the user or feed it back into the model's context.

---

### Scenario 3: Real-Time Tokenizer Hot-Patching for Dynamic Entities

#### Interviewer
> "We run a global e-commerce search service. Overnight, a new brand named `'ZyloraCorp'` launched, but our LLM tokenizer maps this word to `['Zy', 'lora', 'Corp']`. 
>
> Our search engine needs to match this brand as a single token to maintain precise downstream vector routing and structured logging.
>
> If you dynamically add `'ZyloraCorp'` to the tokenizer's vocabulary, what are the architectural consequences for the token embedding layer and the vocabulary classification layer of a pre-trained model? How would you solve this without retraining the entire model?"

```
        Embedding Matrix (V x d_model)              Unembedding LM-Head (d_model x V)
     +----------------------------------+          +----------------------------------+
     |   Token 0                        |          |   Token 0                        |
     |   ...                            |          |   ...                            |
     |   Token 50000 (Last Original)    |          |   Token 50000 (Last Original)    |
     |----------------------------------|          |----------------------------------|
🆕  |   Token 50001 (ZyloraCorp)       |  🆕      |   Token 50001 (ZyloraCorp)       |
     +----------------------------------+          +----------------------------------+
          (No pre-trained weights!)                     (No pre-trained weights!)
```

#### Candidate Analysis (The Structural Conflict)
Adding a new token to the vocabulary changes the vocabulary size from $V$ to $V+1$. This expansion impacts two primary parts of the model's architecture:
1. **The Input Embedding Matrix ($\mathbf{W}_{emb} \in \mathbb{R}^{V \times d_{model}}$):** A new row must be appended to map the new token ID to a $d_{model}$-dimensional vector.
2. **The Output Unembedding Projection / Language Model Head ($\mathbf{W}_{LM\_Head} \in \mathbb{R}^{d_{model} \times V}$):** A new column must be appended to project hidden states to the logit distribution for the new token.

Because these new parameters were not present during pre-training, their weights are uninitialized (typically containing random values or zeros). If the model encounters the new token, it will output unstable embeddings or fail to generate the token correctly.

---

#### Proposed Architectures

```
Option A: Smart Initialization
  Initialize the "ZyloraCorp" embedding by averaging its subword components:
  Embed("ZyloraCorp") = Mean( Embed("Zy") + Embed("lora") + Embed("Corp") )

Option B: Dual-Stage Hybrid Pipeline
  User Query ---> [ Entity Extractor (NER) ] ---> Replaces "ZyloraCorp" with ID "<BRAND_1>"
                                                  (Using a pre-allocated entity placeholder)
```

##### Solution A: Smart Parameter Initialization (Low-Latency Patching)
If we must add the token directly to the vocabulary, we can estimate its initial weights by averaging the embeddings of its subword components:

$$\mathbf{W}_{emb}[V_{new}] = \frac{1}{3} \left( \mathbf{W}_{emb}[\text{"Zy"}] + \mathbf{W}_{emb}[\text{"lora"}] + \mathbf{W}_{emb}[\text{"Corp"}] \right)$$

This approach places the new embedding vector in a semantically relevant region of the vector space, reducing generation errors while bypassing the need for full retraining.

##### Solution B: Dynamic Placeholder Slot Allocation (Production Best Practice)
To avoid modifying the model's weight matrices in production, pre-allocate generic placeholder tokens (e.g., `<BRAND_1>`, `<BRAND_2>`, etc.) during the model's initial pre-training.

During preprocessing, keep an in-memory map (e.g., in Redis) to swap dynamic brand names with these placeholder tokens:
$$\text{"ZyloraCorp is launching"} \longrightarrow \text{"<BRAND_1> is launching"}$$

This approach keeps the model's vocabulary and parameters static, preventing weight instability while supporting real-time brand and entity updates.

---

## 🚀 Cheat Sheet for FAANG Interview Preparation

### Top Optimization Rules
* **$O(L^2)$ Attention Bottleneck:** If context length $L$ scales up, optimize using **GQA** to reduce KV Cache size, **FlashAttention** to optimize memory bandwidth, and **RoPE** for relative position scaling.
* **FP16 Memory Calculation:** Calculate KV Cache memory consumption using:
  $$2 \times n_{layers} \times n_{heads\_kv} \times d_{head} \times B \times L \times 2 \text{ bytes}$$
* **RMSNorm over Pre-LN:** Choose **RMSNorm** for faster performance, as it avoids calculating the mean during normalization, saving element-wise GPU execution time.
* **Avoid Tokenizer Inconsistencies:** Prevent numerical and trailing space errors by stripping whitespaces in the API gateway and splitting digits individually (`[1, 2, 3]`) for numerical tasks.