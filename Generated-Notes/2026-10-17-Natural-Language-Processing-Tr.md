---
title: Natural Language Processing: Transformers, Attention, and Tokenization
date: 2026-10-17T04:32:04.644903
---

# Natural Language Processing: Transformers, Attention, and Tokenization

---

## 1. 🧱 The Core Concept

### Subword Tokenization: BPE, WordPiece, and Unigram

Tokenization balances vocabulary size ($|\mathcal{V}|$) against sequence length ($T$). Character-level modeling minimizes $|\mathcal{V}|$ but inflates $T$, leading to quadratic attention costs ($O(T^2)$). Word-level modeling minimizes $T$ but results in an intractable $|\mathcal{V}|$ with heavy out-of-vocabulary (OOV) penalties. Modern NLP balances this trade-off using subword algorithms.

```
Tokenization Spectrum:
[Character-Level] ------------------ [Subword (BPE/Unigram)] ------------------ [Word-Level]
• Min Vocabulary Size (|V| ~ 256)    • Balanced |V| (32k - 128k)                • Massive |V| (> 1M)
• Max Sequence Length (High Latency) • Controlled Sequence Length               • Minimal Sequence Length
• Zero OOV                           • Subword Compositions                     • Severe OOV / Sparsity
```

#### Byte-Pair Encoding (BPE)
- **Training**: Starts with a character base vocabulary. Iteratively counts the most frequent adjacent pair of symbols $(c_i, c_j)$ across the corpus and merges them into a new symbol $c_{new}$. This repeats for $k$ merge operations until the target vocabulary size $|\mathcal{V}|$ is reached.
- **Inference**: Greedy, deterministic merge application matching the learned merge table order.
- **Byte-level Fallback (BBPE)**: Operates directly on raw UTF-8 bytes (vocabulary initialized to 256 bytes) rather than Unicode characters (e.g., GPT-2, LLaMA). This eliminates true OOV tokens completely, though non-ASCII languages consume disproportionately more tokens per word due to multi-byte UTF-8 representations.

#### WordPiece
- **Training**: Similar to BPE, but the merge selection metric is not raw frequency. Instead, it maximizes the likelihood of the training data under a unigram language model:

$$\text{Score}(x, y) = \frac{\text{Count}(xy)}{\text{Count}(x) \times \text{Count}(y)}$$

- Prioritizes merging pairs whose joint probability is significantly higher than their independent probabilities.
- **Inference**: Greedy longest-match-first matching from the start of each word (using prefix markers like `##`).

#### Unigram
- **Training**: Inverts the merge paradigm. Initializes a large candidate vocabulary $\mathcal{V}_{\text{init}}$ and iteratively prunes it. At each step, it computes the corpus marginal likelihood via the EM algorithm:

$$\mathcal{L} = \sum_{i=1}^{N} \log \left( \sum_{\mathbf{x} \in \mathcal{S}(w^{(i)})} P(\mathbf{x}) \right)$$

It drops the $p\%$ of tokens that cause the smallest decrease in $\mathcal{L}$.
- **Inference**: Non-deterministic. It finds the optimal segmentation using the Viterbi algorithm over token probabilities, enabling subword regularization (sampling segmentations during training to improve robustness).

---

### The Attention Mechanism

#### Scaled Dot-Product Attention
Given queries $Q \in \mathbb{R}^{N \times d_k}$, keys $K \in \mathbb{R}^{M \times d_k}$, and values $V \in \mathbb{R}^{M \times d_v}$:

$$\text{Attention}(Q, K, V) = \text{Softmax}\left(\frac{QK^T}{\sqrt{d_k}} + M\right)V$$

Where $M$ is an optional attention mask ($M_{ij} = -\infty$ to inhibit attention, $0$ otherwise).

```
        Q [N x d_k]           K^T [d_k x M]
             \                     /
              \                   /
               \                 /
                MatMul: QK^T [N x M]
                         |
                 Scale:  / sqrt(d_k)
                         |
                 Mask:   + M (e.g. Causal Mask)
                         |
                 Softmax (row-wise) -> Attention Map [N x M]
                         |
                         |           V [M x d_v]
                         \           /
                          \         /
                           MatMul: A * V
                                 |
                               Output [N x d_v]
```

- **Why Dot-Product over Additive (Bahdanau)?** Additive attention ($v_a^T \tanh(W_q q + W_k k)$) yields comparable empirical accuracy, but scaled dot-product attention can be implemented via highly optimized General Matrix Multiplications (GEMMs) on modern tensor hardware.
- **The Scaling Factor ($\frac{1}{\sqrt{d_k}}$)**: For independent, zero-mean, unit-variance components $q_i, k_i \sim \mathcal{N}(0, 1)$, the dot product $q \cdot k = \sum_{i=1}^{d_k} q_i k_i$ has a mean of $0$ and a variance of $d_k$. As $d_k$ grows, large dot products push the $\text{Softmax}$ function into regions with near-zero gradients:

$$\frac{\partial \text{Softmax}(z)_i}{\partial z_j} = S_i(\delta_{ij} - S_j) \xrightarrow{|z_j| \gg 0} 0$$

Dividing by $\sqrt{d_k}$ enforces $\text{Var}\left(\frac{q \cdot k}{\sqrt{d_k}}\right) = 1$, preserving gradient flow.

#### Multi-Head Attention (MHA)
Rather than computing a single attention function with dimension $d_{\text{model}}$, MHA projects queries, keys, and values $h$ times with distinct learned linear projections:

$$\text{MHA}(Q, K, V) = \text{Concat}(\text{head}_1, \dots, \text{head}_h)W^O$$

$$\text{head}_i = \text{Attention}(Q W_i^Q, K W_i^K, V W_i^V)$$

Where $W_i^Q \in \mathbb{R}^{d_{\text{model}} \times d_k}$, $W_i^K \in \mathbb{R}^{d_{\text{model}} \times d_k}$, $W_i^V \in \mathbb{R}^{d_{\text{model}} \times d_v}$, and $W^O \in \mathbb{R}^{h d_v \times d_{\text{model}}}$. Typically, $d_k = d_v = d_{\text{model}} / h$.

*Why?* It allows the model to jointly attend to information from different representation subspaces at different positions. A single attention head averages these signals, washing out distinct positional and syntactic relationships.

---

### Architectural Paradigms

```
Encoder-Only (BERT)            Decoder-Only (GPT, LLaMA)         Encoder-Decoder (T5)
Bidirectional Visibility       Causal Autoregressive Mask        Bidirectional Enc + Causal Dec
[T1] <---> [T2] <---> [T3]     [T1] ---> [T2] ---> [T3]          [Enc] -> Cross-Attention -> [Dec]
Use: Classification, Extractive Use: Generative LLMs, Reasoning   Use: Translation, Summarization
```

| Dimension | Encoder-Only (e.g., BERT) | Decoder-Only (e.g., LLaMA, GPT) | Encoder-Decoder (e.g., T5) |
| :--- | :--- | :--- | :--- |
| **Masking Pattern** | Fully bidirectional ($M = 0$). | Strictly causal ($M_{ij} = -\infty$ for $j > i$). | Encoder: bidirectional; Decoder: causal + cross-attention over encoder. |
| **Inductive Bias** | Global contextual dependency. | Autoregressive left-to-right generation ($P(x_t \mid x_{<t})$). | Sequence-to-sequence conditional mapping ($P(Y \mid X)$). |
| **KV-Cache Utility** | None (processed in single parallel pass). | Critical for avoiding $O(T^2)$ recomputation at inference. | Critical within the auto-regressive decoder block. |
| **Optimal Tasks** | Classification, Named Entity Recognition (NER), semantic search embeddings. | Open-ended text generation, code synthesis, in-context zero/few-shot learning. | Conditional generation with discrete input/output separation (Translation, Summarization). |

---

## 2. ⚙️ Under the Hood

### Attention Computation: Numerical Stability and Causal Masking

Direct evaluation of $\text{Softmax}(X)$ suffers from numerical overflow for large positive inputs. In practice, attention operations use the safe Softmax formulation:

$$m = \max_{j}(x_j), \quad \text{Softmax}(x)_i = \frac{e^{x_i - m}}{\sum_{j} e^{x_j - m}}$$

For causal masking, the upper triangle of the pre-softmax attention logit matrix is populated with a large negative value:

$$S_{ij} = \begin{cases} 
\frac{q_i k_j^T}{\sqrt{d_k}} & \text{if } j \le i \\ 
-\infty \text{ (practically } -1e4 \text{ in FP16 / BF16)} & \text{if } j > i 
\end{cases}$$

Using `-inf` can cause `NaN` values during backpropagation if an entire row is masked out (resulting in $0/0$). Production kernels substitute dynamic minimum values based on the active floating-point precision:
- `FP32`: $-10^{9}$
- `FP16`: $-65504$ (or safely $-10^4$)
- `BF16`: $-3.3 \times 10^{38}$ (or safely $-10^4$)

```
Causal Logit Matrix (4x4 Context):
[  q1*k1   -inf     -inf     -inf  ]
[  q2*k1   q2*k2    -inf     -inf  ]
[  q3*k1   q3*k2    q3*k3    -inf  ]
[  q4*k1   q4*k2    q4*k3    q4*k4 ]
```

---

### Positional Representations

Because pure attention is permutation-equivariant:

$$\text{Attention}(P Q, P K, P V) = P \, \text{Attention}(Q, K, V)$$

(where $P$ is a permutation matrix), order information must be explicitly injected into the inputs.

```
Positional Embeddings Evolution:
1. Absolute Sinusoidal:   x_pos = x + PE(pos)             [No length extrapolation]
2. Learned Absolute:     x_pos = x + W_pos                [Hard-capped at context window]
3. Relative (T5):        Attn = QK^T + Bias(pos_i - pos_j)[High memory overhead]
4. RoPE:                 Rotate Q and K in complex plane  [Maintains relative inner products]
5. ALiBi:                Attn = QK^T - m * |i - j|        [Direct linear penalty, extrapolates well]
```

#### 1. Rotary Position Embedding (RoPE)
RoPE applies a structure-preserving rotation to the query and key vectors in the complex plane, guaranteeing that their dot product depends only on their relative distance $(m - n)$:

$$\langle R_{\Theta, m}^d q, R_{\Theta, n}^d k \rangle = g(q, k, m - n)$$

Where $R_{\Theta, m}^d$ is an orthogonal block-diagonal matrix constructed from 2D rotation matrices:

$$R_{\Theta, m}^d = \text{diag}\left( R_{\theta_1, m}, R_{\theta_2, m}, \dots, R_{\theta_{d/2}, m} \right)$$

$$R_{\theta_i, m} = \begin{pmatrix} \cos(m\theta_i) & -\sin(m\theta_i) \\ \sin(m\theta_i) & \cos(m\theta_i) \end{pmatrix}, \quad \theta_i = 10000^{-2(i-1)/d}$$

Rather than performing a full matrix multiplication $R_{\Theta, m}^d x$, RoPE is applied efficiently element-wise using complex vector arithmetic:

$$\begin{pmatrix} x^{(1)} \\ x^{(2)} \end{pmatrix} \mapsto \begin{pmatrix} x^{(1)} \cos(m\theta) - x^{(2)} \sin(m\theta) \\ x^{(1)} \sin(m\theta) + x^{(2)} \cos(m\theta) \end{pmatrix}$$

#### 2. Attention with Linear Biases (ALiBi)
ALiBi eliminates positional embeddings at the input layer. Instead, it adds a static, non-learned scalar bias directly to the attention logits:

$$A_{i,j} = \frac{q_i k_j^T}{\sqrt{d_k}} - m \cdot (i - j)$$

Where $m = 2^{-\frac{8}{h} \cdot k}$ is a head-specific geometric scaling constant. ALiBi provides strong zero-shot length extrapolation during inference, though it slightly degrades performance on tasks requiring arbitrary non-monotonic index operations.

---

### Normalization Mechanics: Post-LN vs. Pre-LN vs. RMSNorm

```
Post-LN (Original Transformer):
x_{l+1} = LayerNorm(x_l + SubLayer(x_l))
- Issue: Backpropagating through LayerNorm scales gradients by 1/Var. Gradients vanish near early layers.
- Symptom: Requires warm-up phases and small learning rates; highly sensitive to initialization.

Pre-LN (Modern Standard):
x_{l+1} = x_l + SubLayer(LayerNorm(x_l))
- Benefit: The residual stream acts as an uninhibited highway: d(x_L)/d(x_l) contains an identity term.
- Result: Stable training, warm-up can be shortened or removed.

RMSNorm (LLaMA, Gemma):
y = (x / RMS(x)) * gamma,   where RMS(x) = sqrt( (1/d) * sum(x_i^2) + epsilon )
- Optimization: Discards mean-centering (LayerNorm computes both mean and variance).
- Result: Reduces memory transfers across the GPU memory bus; yields a 5-10% speedup per layer without quality loss.
```

---

### FlashAttention: Memory-Bound Optimization

Standard Attention executes three memory roundtrips to GPU High Bandwidth Memory (HBM) for intermediate states ($QK^T$, $\text{Softmax}$, Attention Probabilities), running at memory-bandwidth-bound speeds ($O(N^2)$ memory reads/writes):

```
Standard Attention Memory Bottleneck:
SRAM (Fast, Small):    [ Load Q, K ] -> Compute S = QK^T -> [ Write S to HBM ]
HBM  (Slow, Large):    ------------------------------------> [ S: O(N^2) bytes ]
SRAM:                  [ Load S from HBM ] -> Softmax(S) -> [ Write P to HBM ]
HBM:                   ------------------------------------> [ P: O(N^2) bytes ]
SRAM:                  [ Load P, V ] -> Compute O = P * V -> [ Write O to HBM ]
```

**FlashAttention (Dao et al.)** uses GPU SRAM tiling, online softmax normalization, and backward-pass recomputation to execute attention in a single pass without materializing the $N \times N$ attention matrix to HBM.

```
FlashAttention Tiling Execution:
Split inputs Q, K, V into blocks that fit entirely within on-chip SRAM (~100-256 KB).

Iterate through SRAM blocks:
For each block of Q:
    For each block of K, V:
        1. Load Q_i, K_j, V_j into SRAM.
        2. Compute local dot products: S_ij = Q_i * (K_j)^T
        3. Update running row-max and row-sum using the Online Softmax trick.
        4. Accumulate partial output vector O_i directly in registers.
5. Write final Output O back to HBM once per query block.

Total HBM accesses: O(N^2 / SRAM_Size) vs O(N^2) -> Reduces memory overhead from O(N^2) to O(N).
```

#### Online Softmax Formulation
Standard softmax requires seeing all entries before computing the denominator:

$$m = \max(x_1, \dots, x_N), \quad d = \sum_{i=1}^N e^{x_i - m}$$

Online softmax tracks and corrects intermediate values over sub-vectors. Given two sub-vectors $A$ and $B$ with local maximums $m_A, m_B$ and partial sums $d_A, d_B$:

$$m_{new} = \max(m_A, m_B)$$

$$d_{new} = d_A e^{m_A - m_{new}} + d_B e^{m_B - m_{new}}$$

$$O_{new} = O_A \left(\frac{d_A e^{m_A - m_{new}}}{d_{new}}\right) + O_B \left(\frac{e^{m_B - m_{new}}}{d_{new}}\right)$$

This allows updating the running values block by block without global intermediate storage.

---

### KV-Cache Architecture: MHA vs. MQA vs. GQA

In autoregressive generation, past keys and values are retained in GPU memory to avoid recomputing past token representations. The memory required scales linearly with batch size, context length, layer count, and hidden dimensions:

$$\text{KV Cache Size per Token} = 2 \times 2 \times L \times n_{\text{heads}} \times d_{\text{head}} \text{ bytes (for FP16/BF16)}$$

```
MHA (Multi-Head Attention)     MQA (Multi-Query Attention)    GQA (Grouped-Query Attention)
Keys/Values per Query Head:    All Queries share 1 KV Pair:    Queries grouped into buckets:

Q1  Q2  Q3  Q4  Q5  Q6  Q7  Q8   Q1  Q2  Q3  Q4  Q5  Q6  Q7  Q8   Q1  Q2  Q3  Q4  Q5  Q6  Q7  Q8
|   |   |   |   |   |   |   |     \   \   \   \   /   /   /   /     \   /   \   /   \   /   \   /
K1  K2  K3  K4  K5  K6  K7  K8                 K1                         K1      K2      K3      K4
V1  V2  V3  V4  V5  V6  V7  V8                 V1                         V1      V2      V3      V4
[Memory: 1.0x]                  [Memory: 1/H (e.g. 0.125x)]     [Memory: G/H (e.g. 0.25x)]
```

- **MHA**: Every query head has an independent key and value head ($H_Q = H_{KV}$).
  - *Bottleneck*: Saturates GPU memory bandwidth during decoding, bounding maximum throughput.
- **MQA (Multi-Query Attention)**: A single key head and value head are shared across all query heads ($H_{KV} = 1$).
  - *Result*: Drastic KV-cache size reduction (by factor of $H_Q$), but can lead to stability and quality degradation on fine-grained reasoning tasks.
- **GQA (Grouped-Query Attention)**: Balances quality and footprint. It groups query heads into $G$ partitions; each partition shares a single key and value head ($1 < H_{KV} = G < H_Q$). For example, LLaMA-3-70B uses 64 query heads and 8 KV heads (an 8:1 ratio), slashing decode memory bandwidth pressure by 8x with negligible quality loss.

---

## 3. ⚠️ The Interview Warzone

### Scenario 1: Mitigating Latency and Memory Bottlenecks in Production Decoding
**Interviewer Prompt**: "We're serving a 70B parameter dense model (LLaMA-3-70B with GQA: 64 Q-heads, 8 KV-heads, $d_{\text{head}} = 128$, 80 layers, FP16). The Time-To-First-Token (TTFT) meets our SLA, but during peak load, our Inter-Token Latency (ITL) jumps from 25ms to 180ms, and we see frequent Out-Of-Memory (OOM) errors. Walk me through your diagnostic process and production remediation plan."

#### Candidate Response:
1. **Root Cause Analysis (Memory-Bound Decode)**:
   - High TTFT is compute-bound (prefill stage processes all context tokens simultaneously using compute-dense matrix multiplications). High ITL is **memory-bandwidth bound** (the decode stage reads weights and the KV cache from HBM to SRAM for every single generated token: Batch size $\times 1$ GEMV operations).
   - *Quantifying the Footprint*: For a context length $S = 8192$ and batch size $B = 32$:

$$\text{KV Cache Size} = 2 \times 2 \times 80 \times 8 \times 128 \times 8192 \times 32 \approx 85.9 \text{ GB}$$

This footprint quickly leads to OOM errors and forces the GPU into thrashing. Under high concurrency, decoding spends its time waiting on memory transfers from HBM rather than running tensor operations.

2. **Remediation 1: PagedAttention and Dynamic Memory Management**:
   - Standard allocations reserve a continuous block of virtual memory for maximum sequence lengths ($S_{\text{max}}$), causing up to 60–80% internal and external memory fragmentation.
   - Introduce **PagedAttention (vLLM)**: Partition the KV cache into fixed-size physical blocks (e.g., 16 or 32 tokens). Map logical sequence spaces dynamically using a block lookup table, eliminating external fragmentation and capping internal fragmentation strictly at the final block boundaries.

3. **Remediation 2: KV-Cache Compression via FP8 / INT4 Quantization**:
   - The KV cache can be cast from FP16 to FP8 (E4M3 or E5M2) or group-wise INT4 without retraining.
   - Reducing FP16 to FP8 instantly halves required memory bandwidth per token read:

$$\text{Bandwidth Demand} = \frac{\text{Weights Footprint} + \text{KV Cache Footprint}}{\text{Memory Bandwidth (HBM3)}}$$

Halving the KV cache footprint doubles the decoding operational intensity ($\text{FLOPs/byte}$), bringing ITL back within SLA.

4. **Remediation 3: Speculative Decoding**:
   - Deploy a lightweight draft model (e.g., LLaMA-3-8B) alongside the 70B target model. The draft model generates $K$ speculative tokens cheaply. The 70B model evaluates all $K$ tokens concurrently within a single prefill-style forward pass:

$$\text{Target Speedup} = \frac{1 - \beta}{1 - \alpha} + \text{Overhead}$$

Given an acceptance rate $\alpha \approx 0.7-0.8$, speculative decoding yields a $2-3\times$ reduction in ITL without modifying downstream output distributions.

---

### Scenario 2: Context Extrapolation Beyond the Pretraining Window
**Interviewer Prompt**: "We pretrained a model with RoPE on an 8k context window. Downstream customers need it to process 64k documents. If we evaluate zero-shot on 64k, perplexity explodes to infinity. We cannot afford full pretraining from scratch. How do you resolve this?"

#### Candidate Response:
1. **Mathematical Diagnosis of Failure**:
   - RoPE associates each head dimension with an angular velocity $\theta_i = b^{-2i/d}$. For tokens at positions $m > 8192$, the rotation values $m\theta_i$ enter regimes never encountered during pretraining.
   - The network's high-frequency dimensions fail to generalize to these out-of-distribution rotation arguments, breaking the relative attention mapping.

```
Positional Interpolation (PI) vs Extrapolation:
Pretrained Range:  [0 ..................... 8192]
Extrapolation:     [0 ..................... 8192] -> [8193 ......... 65536] (OOD: Explodes)
PI (Scaling s=8):  [0 .... 1024 .... 2048 .... 4096 .... 5120 .... 6144 .... 7168 .... 8192]
                   (Mapped uniformly over the actual 65536 input tokens)
```

2. **Phase 1: Position Interpolation (PI)**:
   - Scale down the position indices to match the original range:

$$\tilde{m} = m \cdot \frac{L_{\text{train}}}{L_{\text{target}}} = \frac{m}{8}$$

- This bounds the rotation values within the pre-trained distribution $[0, 8192]$. While effective, it compresses high-frequency positional representations too closely, degrading the model's ability to discriminate between directly adjacent tokens.

3. **Phase 2: YaRN (Yet another RoPE extensioN)**:
   - Split the head dimensions into three functional bands based on the ratio of wavelength $\lambda_i = 2\pi / \theta_i$ to sequence length $L$:

```
Wavelength Scale:
Low Frequencies (λ > L):      Interpolate fully (YaRN applies linear scaling)
Intermediate Frequencies:     Ramp blend between interpolation and extrapolation
High Frequencies (λ << L):    Do NOT interpolate; extrapolate (preserves local order)
```

- Apply a temperature scaling factor $t$ directly to the Softmax computation to counteract entropy increases caused by larger context windows:

$$\text{Softmax}\left(\frac{QK^T}{t \sqrt{d_k}}\right), \quad t \approx 1 + 0.1 \log(s)$$

4. **Targeted Adaptation Plan**:
   - Initialize with the YaRN-scaled RoPE base frequencies.
   - Fine-tune on $\approx 1$ billion tokens with sequence lengths up to 64k, using mixed-length packing to prevent catastrophic forgetting of short-context patterns. Compute costs remain minimal compared to pretraining from scratch.

---

### Scenario 3: Tokenization Edge Cases and Security Exploits
**Interviewer Prompt**: "Can tokenizers cause critical system vulnerabilities or silent failure modes in large production setups? Give concrete examples from real systems."

#### Candidate Response:

#### 1. The Token Healing Problem
- Greedy tokenization resolves character chunks from left to right based on the longest matching entry in the vocabulary.
- *Failure Case*: An input prompt ends with trailing whitespace or an incomplete prefix:
  - Input: `URL: http://raw.githubuser`
  - Normal tokenizer outputs: `['URL', ':', ' http', '://', 'raw', '.', 'github', 'user']`
  - Without trailing characters, `githubuser` might be tokenized as `github` and `user`. But if the full string were `githubusercontent`, the optimal subword might have been `githubusercontent`. 
  - *Consequence*: The model's continuation generation is skewed because the subword lookup was forced to break early at the boundary.
- *System Fix*: Implement **Token Healing** (e.g., Guidance). During generation, back up the prompt by one token, convert it back into raw text, and constrain the first step of autoregressive generation to only pick tokens that continue that prefix.

#### 2. Glitched Tokens (Undelimited Embedding Anomalies)
- *Origin*: Scraping web-scale corpora generates frequent clusters of repetitive strings (e.g., Reddit usernames like `/u/SolidGoldMagikarp`, backend UUIDs, or long blocks of repeated whitespace).
- *Failure Case*: If a token is added to the vocabulary during BPE tokenization, but downstream fine-tuning dataset filters strip those strings out, that token never receives gradient updates.
- Its embedding vector remains stuck at random initialization (or drifts due to weight decay).
- In production, feeding this token into the model yields erratic behavior, hallucinatory loops, or model crashes, because the vector lies far outside the learned manifold.

```
Vocabulary Index Space:
[ Token 4210: "apple"   ] -> High usage in fine-tuning -> Stable embedding
[ Token 4211: "SolidGold" ] -> ZERO occurrences in fine-tuning -> Random un-normalized vector
                                                                 (Triggers garbage generation)
```

- *Mitigation*: Prune untuned tokens, recalculate vocabulary usage distributions post-filtering, or normalize zero-frequency embeddings back onto the active representation manifold before deployment.

#### 3. BPE Boundary Injections and Normalization Attacks
- *Vulnerability*: Naive security guardrails running regex matching or string comparisons *after* or *before* tokenization.
- *Attack Vector*: Inserting zero-width spaces (`\u200B`), soft hyphens (`\u00AD`), or altering NFKC/NFKD Unicode normalizations.
- A user input of `d\u200Be\u200Bl\u200Be\u200Bt\u200Be` evades a regex scanning for `delete`.
- If the model's tokenizer strips control characters *prior* to tokenization, the downstream model still executes the un-sanitized instruction:

$$\text{User String} \xrightarrow{\text{Regex Cleared}} \text{Tokenizer Sanitization} \xrightarrow{\text{Compiles to:}} \text{"delete"}$$

- *System Fix*: Tokenizer preprocessing and system safety evaluation layers must share an identical, strictly validated normalization pipeline. Never separate safety parsing from the tokenizer's internal byte-handling flow.

---

### Probing Matrix (Quick-Fire Questions)

| Question | Senior Answer | Staff+ Answer |
| :--- | :--- | :--- |
| **Why does Transformers use Pre-LN instead of Post-LN?** | Pre-LN prevents gradients from vanishing during backpropagation through earlier layers. | Post-LN puts the normalization directly on the residual path, causing the gradient norm to scale inversely with depth ($1/\prod \sigma_l$). Pre-LN preserves identity gradient routing through the residual path ($\frac{\partial x_L}{\partial x_l} = I + \dots$), removing the need for delicate warm-up phases. |
| **Can we replace Softmax with a linear activation in Attention?** | Yes, linear attention simplifies the math and drops the complexity to $O(N)$. | Yes, by exploiting the associative property of matrix multiplication: $(Q K^T) V = Q (K^T V)$. However, unrestricted kernel formulations (e.g., Performer, Katharopoulos) struggle to maintain sharp attention distributions, which degrades performance on retrieval-heavy tasks. |
| **Why not run full FP8 training end-to-end?** | Small numbers underflow and large values saturate the dynamic range. | FP8 requires split formats (E4M3 for forward activations/weights to maximize precision; E5M2 for backward gradients to maximize dynamic range). Softmax, normalization reductions, and positional rotations must remain in FP32 or BF16 to prevent catastrophic cancellation. |
| **What is the difference between SentencePiece and standard BPE?** | SentencePiece works on raw text without requiring language-specific pre-tokenization. | SentencePiece treats the input stream as a continuous byte sequence, explicitly encoding whitespace as a distinct character (e.g., `_` / `U+2581`). This avoids language-dependent heuristics and keeps the tokenization fully reversible without information loss: $\text{Decode}(\text{Encode}(S)) \equiv S$. |