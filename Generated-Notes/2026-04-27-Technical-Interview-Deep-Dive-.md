---
title: Technical Interview Deep-Dive: Transformers, Attention, and Tokenization
date: 2026-04-27T04:31:25.211177
---

# Technical Interview Deep-Dive: Transformers, Attention, and Tokenization

This guide is written from the perspective of a Senior Staff Engineer. In a FAANG interview, we don't just want to hear that you know what a Transformer is; we want to see if you understand the **mathematical bottlenecks**, the **hardware implications**, and the **architectural trade-offs**.

---

## 🧱 1. The Core Concept (Basics Refresh)

### Tokenization: Beyond String Splitting
Tokenization is the bridge between raw text and numerical tensors. Modern NLP avoids word-level (too many Out-Of-Vocabulary terms) and character-level (sequences become too long) tokenization.
*   **Subword Tokenization (BPE, WordPiece, Unigram):** These algorithms balance vocabulary size and sequence length. They break rare words into meaningful sub-units (e.g., "transforming" $\rightarrow$ "transform", "##ing").
*   **The Trade-off:** A smaller vocabulary increases sequence length (increasing $O(N^2)$ attention costs), while a larger vocabulary increases the embedding layer's memory footprint.

### The Death of Recurrence
Before Transformers, RNNs/LSTMs dominated. Their fatal flaw? **Sequential dependency.** You couldn't compute $h_t$ until $h_{t-1}$ was done. 
*   **Transformers** replaced recurrence with **Global Attention**, allowing for massive parallelization during training, which is why we can now train on the entire internet.

---

## ⚙️ 2. Under the Hood (Internal Mechanics)

### The Attention Mechanism: $Attention(Q, K, V)$
The core formula: $\text{softmax}\left(\frac{QK^T}{\sqrt{d_k}}\right)V$

1.  **The "Search" Analogy:** 
    *   **Query ($Q$):** What I am looking for.
    *   **Key ($K$):** What I contain.
    *   **Value ($V$):** The information I actually provide.
2.  **The Scaling Factor ($\sqrt{d_k}$):** Without this, the dot product $QK^T$ grows large in high dimensions. This pushes the softmax into regions with extremely small gradients, leading to the **vanishing gradient problem**.
3.  **Multi-Head Attention (MHA):** Instead of one attention pass, we run $h$ passes in parallel over different subspaces. This allows the model to simultaneously focus on "Who" (subject) and "What" (action) in a sentence.

### Architecture Nuances
*   **Layer Normalization:** Most modern LLMs use **Pre-Norm** (LayerNorm happens *before* the attention/FFN blocks) rather than the original **Post-Norm**. Pre-Norm is significantly more stable for training very deep networks.
*   **Feed-Forward Networks (FFN):** After attention, every token passes through the same FFN. This is where the "knowledge" is arguably stored. It usually consists of two linear layers with a non-linearity (ReLU, GeLU, or SwiGLU).
*   **Positional Encodings:** Since attention is permutation-invariant (it doesn't care about order), we must inject position.
    *   *Absolute:* Sinusoidal or learned embeddings.
    *   *Relative/Rotary (RoPE):* Used in Llama; encodes position by rotating the Query and Key vectors, allowing for better context window extrapolation.

---

## ⚠️ 3. The Interview Warzone

### Scenario A: The Quadratic Bottleneck
**Interviewer:** "Your model's inference is too slow for 10k token documents. The client wants 32k. What do you do?"
*   **The Trap:** Don't just say "Get more GPUs."
*   **The Pro Response:** Identify that Attention is $O(N^2)$ in time and space.
    *   **Optimization 1: KV Caching.** During decoding, we don't need to recompute the Keys and Values for past tokens. We store them. This turns $O(N^2)$ generation into $O(N)$.
    *   **Optimization 2: Flash Attention.** Mention IO-awareness. Standard attention is bottlenecked by Memory Bandwidth (SRAM vs HBM). Flash Attention reorders the computation to reduce memory reads/writes.
    *   **Optimization 3: Linear/Sparse Attention.** Mention Longformer or BigBird, which use sliding windows or global "anchor" tokens to reduce complexity to $O(N)$.

### Scenario B: Tokenizer Sabotage
**Interviewer:** "Your model performs poorly on medical jargon and code, even though the base model was trained on it. Why?"
*   **The Pro Response:** Check the **Tokenizer**. If the tokenizer was trained on Wikipedia, "Laparoscopic" might be split into 6 meaningless tokens. 
    *   **Solution:** Re-train the tokenizer or use a "Byte-level BPE" (like GPT-2/3) which ensures no "unknown" tokens by falling back to raw bytes, preserving the semantic structure of rare technical terms.

### Scenario C: Probing Questions (Quick-fire)
1.  **Q: Why do we use Multi-Head instead of one big head?**
    *   *A:* To allow the model to attend to different types of relationships (e.g., syntactic vs. semantic) in parallel. It prevents the model from "averaging" out all information into a single distribution.
2.  **Q: What is the difference between Encoder-only (BERT) and Decoder-only (GPT)?**
    *   *A:* **Masking.** Encoders use bidirectional attention (can see future tokens). Decoders use **Causal Masking** (can only see past tokens) to prevent "cheating" during next-token prediction.
3.  **Q: Why did we move from ReLU to GeLU or SwiGLU?**
    *   *A:* Smoothness. GeLU provides a non-zero gradient for small negative values, which helps with vanishing gradients and leads to better convergence in large-scale Transformers.

### The "Perfect Response" Template
When asked to design a system (e.g., "Build a legal document summarizer"):
1.  **Define the Constraints:** Mention the context length (Legal docs are long). 
2.  **Choose the Architecture:** "I'd use a Decoder-only architecture with **RoPE** for better context handling."
3.  **Address Efficiency:** "To handle the $O(N^2)$ cost, I'd implement **Flash Attention 2** and **KV Caching**."
4.  **Tokenization Strategy:** "I'd use a custom BPE tokenizer trained on legal corpora to avoid excessive fragmentation of legal terminology."
5.  **Refinement:** "I'd use **Grouped-Query Attention (GQA)** to reduce memory overhead during inference, balancing the performance of MHA and the speed of MQA (Multi-Query Attention)."

---
**Senior Staff Tip:** In interviews, always mention **Hardware-Awareness**. Mentioning things like "Memory Bandwidth Bottlenecks" or "SRAM utilization" separates a Research Scientist from a Senior Engineer who can actually deploy these models at scale.