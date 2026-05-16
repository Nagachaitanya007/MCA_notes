---
title: Technical Interview Guide: Transformers, Attention, and Tokenization
date: 2026-05-16T04:31:23.860136
---

# Technical Interview Guide: Transformers, Attention, and Tokenization
**Role:** Senior Staff Engineer / FAANG Interviewer  
**Topic:** Modern NLP Architectures

---

## 🧱 1. The Core Concept (Basics Refresh)

In the "Pre-Transformer" era (roughly before 2017), we relied on **Recurrent Neural Networks (RNNs)** and **LSTMs**. These processed text sequentially, like a human reading left to right. 

**The Fatal Flaw:** Sequential processing is an $O(n)$ bottleneck that prevents parallelization on GPUs and leads to "vanishing gradients" over long sequences. You can't remember the beginning of a 1,000-word essay by the time you reach the end.

### The Paradigm Shift
The Transformer (introduced in *Attention is All You Need*) replaced recurrence with **Global Attention**. 
- **Parallelization:** Every token in a sequence "looks" at every other token simultaneously.
- **Constant Path Length:** The distance between any two tokens is $O(1)$, making long-range dependencies easy to learn.

---

## ⚙️ 2. Under the Hood (Internal Mechanics)

### A. Tokenization: The Gatekeeper
You don't feed raw text into a model. You feed integers.
1.  **Byte-Pair Encoding (BPE) / WordPiece:** These are the industry standards. They solve the **OOV (Out of Vocabulary)** problem by breaking rare words into sub-word units (e.g., "unaffable" $\rightarrow$ ["un", "aff", "able"]).
2.  **The Vocabulary Trade-off:** A larger vocab captures more nuance but increases the size of the embedding matrix (memory cost). A smaller vocab forces the model to use more tokens per sentence (compute cost).

### B. Scaled Dot-Product Attention
This is the "Engine." For a sequence of embeddings, we derive three vectors for each token: **Query (Q)**, **Key (K)**, and **Value (V)**.

$$\text{Attention}(Q, K, V) = \text{softmax}\left(\frac{QK^T}{\sqrt{d_k}}\right)V$$

*   **Query:** What I’m looking for.
*   **Key:** What I contain.
*   **Value:** If I am relevant, what information do I provide?
*   **The $\sqrt{d_k}$ Scaling:** Why is it there? At high dimensions, dot products grow large, pushing the softmax into regions with tiny gradients. Scaling keeps the gradients healthy.

### C. Multi-Head Attention (MHA)
We don't do attention once; we do it $N$ times in parallel. 
*   **Why?** One head might focus on syntax (which verb follows this noun?), while another focuses on semantics (is this "bank" a river bank or a financial bank?).

### D. Positional Encodings
Since Transformers have no inherent sense of order (they are permutation invariant), we must manually inject position.
*   **Classic:** Sinusoidal encodings.
*   **Modern (FAANG Favorite):** **RoPE (Rotary Positional Embeddings)** or **ALiBi**. These allow for better extrapolation to sequence lengths longer than the training data.

---

## ⚠️ 3. The Interview Warzone

As an interviewer, I don’t care if you can define "Attention." I want to know if you can build and scale it.

### Scenario 1: The Context Window Crisis
**Interviewer:** *"Your model performs great on 512 tokens, but accuracy collapses at 4k tokens, and inference is too slow. What do you do?"*

*   **The Probing Pattern:** I'm testing your knowledge of the $O(n^2)$ complexity of self-attention.
*   **The Perfect Response:** "The bottleneck is the $QK^T$ matrix, which is $L \times L$. To scale, I’d look into:
    1.  **KV Caching:** In inference, we don't need to recompute Keys and Values for past tokens.
    2.  **Flash Attention:** An IO-aware algorithm that uses tiling to reduce memory reads/writes between GPU HBM and SRAM.
    3.  **Sparse Attention/Sliding Windows:** (Like Longformer or Mistral's implementation) where tokens only attend to a local neighborhood."

### Scenario 2: Tokenization Sabotage
**Interviewer:** *"We are building a multilingual model for English and Korean. Users complain the model is 'slower' and 'dumber' in Korean. Why?"*

*   **The Probing Pattern:** Testing your understanding of "Token Efficiency."
*   **The Perfect Response:** "This is likely a **Tokenization Imbalance**. If the tokenizer was trained mostly on English, it might represent a single Korean word with 5-10 sub-tokens, whereas an English word is 1 token. This eats up the context window and increases compute per 'unit of meaning.' I would retrain the BPE tokenizer on a balanced, representative corpus or move to a byte-level tokenizer like BBPE."

### Scenario 3: Training Stability (The "Vanishing Gradient" Trap)
**Interviewer:** *"Should we put Layer Normalization before or after the Attention block? (Pre-Norm vs. Post-Norm)"*

*   **The Probing Pattern:** Testing if you've actually trained models at scale.
*   **The Perfect Response:** "The original Transformer used **Post-Norm**, but almost all modern LLMs (GPT-3, Llama) use **Pre-Norm**. Pre-Norm places the LayerNorm inside the residual branch. This makes the identity path cleaner, leading to much more stable training at high learning rates, though it sometimes requires a slightly deeper stack to match the representational power of Post-Norm."

### Scenario 4: Architectural Choice
**Interviewer:** *"I need to build a system to classify legal documents into 50 categories. Should I use GPT-4 or a BERT-base model?"*

*   **The Probing Pattern:** Testing cost-benefit analysis and Encoder vs. Decoder knowledge.
*   **The Perfect Response:** "For pure classification, **BERT (Encoder-only)** is significantly more efficient. Since you only need a single label, a 110M parameter BERT model can be fine-tuned to outperform a massive Decoder-only model like GPT-4 on a specific domain, with 1/100th the latency and cost. Decoders are optimized for generation; Encoders are optimized for representation."

---

## 🚀 Summary Checklist for the Candidate
- [ ] **Complexity:** Know that Attention is $O(n^2 \cdot d)$, while Feed-Forward is $O(n \cdot d^2)$.
- [ ] **Normalization:** Be ready to discuss **RMSNorm** (cheaper than LayerNorm).
- [ ] **Activation:** Know **GeLU** or **SwiGLU** over ReLU.
- [ ] **Softmax:** Understand that it's the "information bottleneck" and the most expensive operation besides the matmuls.
- [ ] **Hardware:** Mention **H100/A100 constraints**—memory bandwidth is usually the bottleneck, not TFLOPS.