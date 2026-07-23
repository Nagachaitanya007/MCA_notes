---
title: Deep Learning: CNNs for Image Recognition & RNNs for Sequence Data
date: 2026-07-23T04:31:59.772963
---

# Deep Learning: CNNs for Image Recognition & RNNs for Sequence Data

---

## 🧱 1. The Core Concept (Basics Refresh)

Architectural choices in deep learning are driven by **inductive biases**—the explicit structural assumptions a model makes about the underlying domain data. Standard Multi-Layer Perceptrons (MLPs) fail on high-dimensional spatial and temporal data due to parameter explosion and a complete lack of spatial/temporal awareness.

```
MLP (Dense):         Fully Connected -> O(N*M) parameters -> No spatial/temporal prior
CNN (Spatial):       Local Receptive Field + Weight Sharing -> Translation Invariance
RNN (Temporal):      Recurrent Hidden State + Shared Weights across Time -> Temporal Invariance
```

### Convolutional Neural Networks (CNNs)
Designed for grid-structured topology (1D audio, 2D images, 3D video/volumetric scans).

*   **Spatial Locality:** Assumes nearby pixels are highly correlated. Neurons receive input only from a local sub-region (Receptive Field).
*   **Translation Invariance / Equivariance:** A feature (edge, corner, texture) learned in one corner of an image is identically valid across the entire spatial domain.
*   **Parameter Sharing:** Convolving a single kernel ($K \times K \times C_{in}$) across the spatial grid drastically reduces parameter complexity from $O(H \cdot W \cdot C_{in} \times H' \cdot W' \cdot C_{out})$ to $O(K^2 \cdot C_{in} \cdot C_{out})$.

### Recurrent Neural Networks (RNNs)
Designed for variable-length sequential processing ($X = (x_1, x_2, \dots, x_T)$).

*   **Temporal Invariance:** The conditional distribution $P(x_t \mid x_{t-1}, \dots, x_1)$ operates under stationary transition dynamics. The weight matrices ($W_{hh}, W_{xh}$) are reused across all timesteps $t \in [1, T]$.
*   **Internal Stateful Memory:** Maintains a continuous hidden state $h_t = f(W_{hh} h_{t-1} + W_{xh} x_t + b_h)$ that dynamically encodes context over arbitrary sequence lengths.

### Modern Paradigm Architectural Matrix

| Metric / Dimension | CNNs (2D) | RNNs (LSTM/GRU) | Transformers (Context) |
| :--- | :--- | :--- | :--- |
| **Primary Inductive Bias** | Spatial Locality & Translation Equivariance | Sequential / Temporal Causality | Global Interaction via Content-Based Attention |
| **Training Parallelization** | **High** (Spatial grid computes concurrently) | **Low** ($O(T)$ sequential dependency bottleneck) | **High** (Masked self-attention matrix multiplication) |
| **Inference Time Complexity** | $O(H \cdot W \cdot K^2 \cdot C_{in} \cdot C_{out})$ | $O(T \cdot d^2)$ per sequence | $O(T^2 \cdot d)$ (Standard) / $O(T \cdot d)$ (Linear/KV-cached) |
| **Inference Space Complexity**| $O(\text{Layer Memory})$ | **$O(1)$** (State update only requires $h_{t-1}$) | $O(T)$ or $O(T^2)$ KV-Cache |
| **Receptive Field Growth** | Linear with depth ($O(L \cdot K)$) | Unbounded in theory; Exponential decay in practice | Global at Layer 1 ($O(1)$ spatial distance) |

---

## ⚙️ 2. Under the Hood (Internal Mechanics & Architecture)

### 2.1 Deep CNN Mechanics

#### Math of 2D Convolution

For an input tensor $X \in \mathbb{R}^{H \times W \times C_{in}}$ and a set of $C_{out}$ kernels $W \in \mathbb{R}^{K \times K \times C_{in} \times C_{out}}$:

$$Y_{i, j, k} = b_k + \sum_{m=0}^{K-1} \sum_{n=0}^{K-1} \sum_{c=0}^{C_{in}-1} X_{i \cdot S + m,\, j \cdot S + n,\, c} \cdot W_{m, n, c, k}$$

Where $S$ is the Stride, and Padding $P$ defines output spatial dimensions:

$$H_{out} = \left\lfloor \frac{H - K + 2P}{S} \right\rfloor + 1, \quad W_{out} = \left\lfloor \frac{W - K + 2P}{S} \right\rfloor + 1$$

#### Dilated (Atrous) Convolutions
To expand the receptive field without increasing parameters or downsampling spatial resolution (critical for semantic segmentation), a dilation rate $D$ is introduced:

$$Y_{i, j, k} = \sum_{m, n, c} X_{i \cdot S + m \cdot D,\, j \cdot S + n \cdot D,\, c} \cdot W_{m, n, c, k}$$

Effective Kernel Size: $K_{eff} = K + (K - 1)(D - 1)$.

```
Dilation D=1 (Standard 3x3):     Dilation D=2 (Sparse 3x3, Receptive Field = 5x5):
x  x  x                          x  .  x  .  x
x  x  x                          .  .  .  .  .
x  x  x                          x  .  x  .  x
                                 .  .  .  .  .
                                 x  .  x  .  x
```

#### Analytical Receptive Field Derivation
The receptive field $RF_l$ of a unit at layer $l$ relative to input layer $0$ is calculated recursively:

$$RF_l = RF_{l-1} + (K_l - 1) \cdot J_{l-1}$$

Where the cumulative stride (jump) up to layer $l-1$ is:

$$J_{l-1} = \prod_{i=1}^{l-1} S_i \quad \text{with } RF_0 = 1, J_0 = 1$$

#### Structural Evolution

```
[LeNet-5] (5x5 Conv, AvgPool) 
   └──► [AlexNet] (11x11/5x5, ReLU, Dropout, MaxPool)
           └──► [VGG-16/19] (Factorized 3x3 Convs: Two 3x3s = 5x5 RF with fewer params)
                   └──► [ResNet] (Residual Skip Connections: Overcomes Degeneration Problem)
                           └──► [EfficientNet] (Compound Scaling: Depth + Width + Resolution)
```

##### ResNet Residual Block
Instead of fitting $H(x)$, optimize $F(x) := H(x) - x$, yielding $H(x) = F(x) + x$.

$$\frac{\partial \mathcal{L}}{\partial x} = \frac{\partial \mathcal{L}}{\partial H} \cdot \left( \frac{\partial F(x)}{\partial x} + 1 \right)$$

The explicit $+1$ term forms a "gradient highway," enabling identity gradients back to earlier layers even if $\frac{\partial F(x)}{\partial x} \to 0$.

```
           x ──┬──────────────────────┐ (Identity Shortcut)
               │                      │
               ▼                      │
         ┌───────────┐                │
         │  Conv 3x3 │                │
         └─────┬─────┘                │
               ▼                      │
         ┌───────────┐                │
         │ BatchNorm │                │
         └─────┬─────┘                │
               ▼                      │
         ┌───────────┐                │
         │   ReLU    │                │
         └─────┬─────┘                │
               ▼                      │
         ┌───────────┐                │
         │  Conv 3x3 │                │
         └─────┬─────┘                │
               ▼                      │
         ┌───────────┐                │
         │ BatchNorm │                │
         └─────┬─────┘                │
               ▼                      │
             ( + ) ◄──────────────────┘
               │
               ▼
             ReLU
```

---

### 2.2 Deep RNN Mechanics & The Vanishing/Exploding Gradient Mathematical Proof

#### Vanilla RNN Formulation
Given hidden state $h_t \in \mathbb{R}^d$ and input $x_t \in \mathbb{R}^p$:

$$h_t = \tanh(W_{hh} h_{t-1} + W_{hx} x_t + b_h)$$

$$y_t = \text{softmax}(W_{hy} h_t + b_y)$$

#### Mathematical Proof of Vanishing/Exploding Gradients in BPTT
Total loss for a sequence of length $T$: $\mathcal{L} = \sum_{t=1}^T \mathcal{L}_t$.

The gradient of loss at timestep $T$ with respect to recurrent weight $W_{hh}$:

$$\frac{\partial \mathcal{L}_T}{\partial W_{hh}} = \sum_{k=1}^T \frac{\partial \mathcal{L}_T}{\partial h_T} \cdot \frac{\partial h_T}{\partial h_k} \cdot \frac{\partial h_k}{\partial W_{hh}}$$

Focusing on the Jacobian vector product path $\frac{\partial h_T}{\partial h_k}$:

$$\frac{\partial h_T}{\partial h_k} = \prod_{j=k+1}^T \frac{\partial h_j}{\partial h_{j-1}}$$

Where the single-step Jacobian is:

$$\frac{\partial h_j}{\partial h_{j-1}} = \operatorname{diag}\left(1 - \tanh^2(a_j)\right) \cdot W_{hh}^T \quad \text{where } a_j = W_{hh} h_{j-1} + W_{hx} x_j + b_h$$

Taking the matrix norm bounded by upper bounds $\gamma_x$ (activation derivative bound) and $\gamma_w$ (largest singular value / spectral radius $\rho(W_{hh})$):

$$\left\| \frac{\partial h_j}{\partial h_{j-1}} \right\| \le \gamma_x \gamma_w$$

Extending to sequence length $T-k$:

$$\left\| \frac{\partial h_T}{\partial h_k} \right\| \le (\gamma_x \gamma_w)^{T-k}$$

*   **If $\gamma_x \gamma_w < 1$:** Exponential decay to 0 as $(T-k) \to \infty$ (**Vanishing Gradient**). The model forgets early history.
*   **If $\gamma_x \gamma_w > 1$:** Exponential growth to $\infty$ as $(T-k) \to \infty$ (**Exploding Gradient**). Triggers numerical overflow (`NaN` loss).

#### The Mitigation: Gated Architectures (LSTM & GRU)

##### Long Short-Term Memory (LSTM) Architecture
LSTMs decouple internal persistent memory ($C_t$, Cell State) from exposed activation ($h_t$, Hidden State).

```
                      Cell State Highway (C_{t-1} -> C_t)
         C_{t-1} ───────────( x )────────────────────(+)───────────► C_t
                             ▲                        ▲
                             │  ┌──────────────────┐  │
                             │  │   tanh (C_tilde)  │  │
                             │  └────────┬─────────┘  │
                             │           │            │
                             │         ( x ) ◄────────┘ (Input Gate i_t)
                             │           ▲
                             │           │
                     (Forget Gate f_t)   │
                             │           │
  h_{t-1} ──┬──────────────►[ f ]       [ i ]       [ o ] (Output Gate o_t)
            │                 ▲           ▲           ▲
   x_t   ───┴─────────────────┴───────────┴───────────┴────► h_t
```

##### Equations:
1. **Forget Gate:** Controls what context to purge from the cell state:
   $$f_t = \sigma(W_f \cdot [h_{t-1}, x_t] + b_f)$$
2. **Input Gate & Candidate Cell State:** Controls what new information to store:
   $$i_t = \sigma(W_i \cdot [h_{t-1}, x_t] + b_i)$$
   $$\tilde{C}_t = \tanh(W_c \cdot [h_{t-1}, x_t] + b_c)$$
3. **Cell State Update:** Additive updates eliminate multiplying weight Jacobians repeatedly:
   $$C_t = f_t \odot C_{t-1} + i_t \odot \tilde{C}_t$$
4. **Output Gate & Hidden State:**
   $$o_t = \sigma(W_o \cdot [h_{t-1}, x_t] + b_o)$$
   $$h_t = o_t \odot \tanh(C_t)$$

**Why LSTMs prevent vanishing gradients:**
The path from $C_{t-1}$ to $C_t$ is linear ($C_t = f_t \odot C_{t-1} + \dots$). The Jacobian $\frac{\partial C_t}{\partial C_{t-1}} = f_t$. If $f_t \to 1$ (gate is fully open), the gradient flows backward through arbitrary timesteps without exponential decay ($1^{T-k} = 1$). This is the **Constant Error Carousel**.

---

## ⚠️ 3. The Interview Warzone

### Scenario 1: Low-Latency Edge Vision Pipeline (CNNs)

#### The Question
"Your team is deploying a real-time object detection system on an edge device (e.g., automated delivery drone camera) processing 4K streams. Frame drops are non-negotiable. You cannot drop input spatial resolution because micro-objects (e.g., power lines) drop below sub-pixel limits. However, standard ResNet-50 inference takes 180ms per frame (Budget: <= 15ms). How do you redesign the architecture for real-time edge processing?"

#### Interviewer Intent
Assesses mastery of FLOP reduction techniques, structural decomposition, receptive field retention, and hardware-level operational arithmetic beyond naive hyperparameter tuning.

#### Probing Follow-up Patterns
*   *“Why not just run standard max-pooling downsampling to increase throughput?”*
*   *“How do depthwise separable convolutions mathematically alter parameter count and memory bandwidth requirements?”*
*   *“How do you maintain high receptive field without deep kernel stacking?”*

#### Perfect Senior Staff Response

```
                        DEPTHWISE SEPARABLE CONVOLUTION
                       
 Spatial Step (Depthwise)                  Channel Step (Pointwise)
 Spatial Filtering Per Channel             1x1 Cross-Channel Linear Combination

[ Input: H x W x C_in ]                  [ Spatial Out: H x W x C_in ]
         │                                        │
         ▼                                        ▼
┌──────────────────┐                     ┌──────────────────┐
│ K x K Kernel     │ (C_in Filters)      │ 1 x 1 Kernel     │ (C_out Filters)
└──────────────────┘                     └──────────────────┘
         │                                        │
         ▼                                        ▼
[ Spatial Out: H x W x C_in ]            [ Final Output: H x W x C_out ]
```

##### 1. Mathematical Convolution Decomposition (MobileNet V2 / ShuffleNet Paradigm)
Replace standard 2D convolutions with **Depthwise Separable Convolutions** consisting of Depthwise (spatial filtering) and Pointwise ($1 \times 1$ channel projection) layers.

*   *Standard Conv FLOPs:* $H \cdot W \cdot K^2 \cdot C_{in} \cdot C_{out}$
*   *Depthwise Separable FLOPs:* $H \cdot W \cdot K^2 \cdot C_{in} + H \cdot W \cdot 1^2 \cdot C_{in} \cdot C_{out}$
*   *Computation Reduction Ratio:*
    $$\frac{\text{Depthwise Separable}}{\text{Standard}} = \frac{K^2 \cdot C_{in} + C_{in} \cdot C_{out}}{K^2 \cdot C_{in} \cdot C_{out}} = \frac{1}{C_{out}} + \frac{1}{K^2}$$
    For $K=3$, this provides an immediate **~8x to 9x FLOP reduction** with negligible drop in top-1 accuracy.

##### 2. Structural Receptive Field Optimization via Dilated Convolutions
To retain context on high-resolution streams without deep spatial downsampling:
*   Incorporate **Dilated (Atrous) Convolutions** in later feature extraction layers ($D=2, 4$). This expands the spatial receptive field quadratically without introducing parameters or downsampling fine spatial features.
*   Deploy a **Feature Pyramid Network (FPN)** or **BiFPN** structure: extract high-resolution features early, process lower-resolution abstract paths concurrently, and fuse multi-scale features via lateral connections.

##### 3. Channel-Shuffle & Bottleneck Redesign
*   Use Inverted Bottlenecks (Expanding channels via $1 \times 1$, applying $3 \times 3$ Depthwise, contracting via $1 \times 1$) with **Linear Bottlenecks** (removing non-linearities like ReLU in low-dimensional output projections to avoid destroying feature manifold representations).

##### 4. Inference-Time Fusion & Hardware Quantization
*   **Conv-Batch Normalization Fusion:** Fuse $W_{BN}$ parameters into convolution weight matrix $W_{conv}$ during compiled inference graphs to remove BN execution overhead.
*   **INT8 Post-Training Quantization (PTQ) or Quantization-Aware Training (QAT):** Quantize FP32 parameters to INT8 using symmetric scalar quantization with TensorRT optimization, leveraging hardware INT8 Tensor Cores/NEON execution blocks for a 4x reduction in memory bandwidth demands.

---

### Scenario 2: Real-Time High-Throughput Time-Series Engine (RNN vs. TCN vs. Transformer)

#### The Question
"You are architecting a real-time high-throughput algorithm for real-time financial high-frequency trading (10,000 sub-second events/sec per symbol stream). A team member recommends an LSTM; another suggests a Temporal Convolutional Network (TCN); a third wants a small Vision-style Transformer (Swin/PatchTST). Evaluate the architectural trade-offs across Latency, Training Parallelization, Memory Footprint, and Causality constraints. Defend your choice."

#### Interviewer Intent
Evaluates whether the candidate understands real-world production engineering trade-offs (inference memory, sequential execution bounds) versus blind high-accuracy model adoption.

#### Probing Follow-up Patterns
*   *“How does the memory footprint of an LSTM inference loop scale relative to a TCN or Transformer over a 10,000 temporal context window?”*
*   *“How do you enforce non-causal leakage prevention in TCN architectures?”*

#### Perfect Senior Staff Response

```
                          TEMPORAL CONVOLUTIONAL NETWORK (TCN)
                              (Dilated Causal Convolutions)

Layer L=2 (D=4)    o               o               o               o (Output t)
                   │╲              │╲              │╲              │
                   │ ╲             │ ╲             │ ╲             │
Layer L=1 (D=2)    o  │            o  │            o  │            o
                  ╱|  │           ╱|  │           ╱|  │           ╱|
                 ╱ |  │          ╱ |  │          ╱ |  │          ╱ |
Layer L=0 (D=1) o  o  o  o      o  o  o  o      o  o  o  o      o  o  o  o (Input)
                t-3    t-2      t-1      t
```

##### Architectural Comparison Analysis

```
                              TCN
                 ┌───────────────────────────┐
                 │ Causal Dilated Conv 1D    │
                 │ Receptive Field = O(2^L)  │
                 └─────────────┬─────────────┘
                               │
            ┌──────────────────┴──────────────────┐
            ▼                                     ▼
     Training Phase                        Inference Phase
┌──────────────────────────┐             ┌──────────────────────────┐
│ Parallel O(1) Time Steps │             │ Fixed-Size Ring Buffer   │
│ No Recurrent Loop        │             │ Cache State O(K*L) Space │
└──────────────────────────┘             └──────────────────────────┘
```

| Criterion | Recurrent (LSTM) | Temporal Convolutional Network (TCN) | Transformer (Patch/Causal) |
| :--- | :--- | :--- | :--- |
| **Training Parallelization** | **Bad:** $O(T)$ sequential step dependency | **Excellent:** $O(1)$ parallel 1D Conv across sequence | **Excellent:** $O(1)$ parallel matrix multiplication |
| **Inference Step Latency** | **Extremely Low:** Single step update | **Low:** Short causal kernel operations | **High:** $O(T)$ or $O(T^2)$ attention computation |
| **Inference Memory Footprint**| **$O(1)$ constant:** Only requires hidden state $h_{t-1}$ and cell state $C_{t-1}$ | **$O(K \cdot L)$ bounded:** Requires rolling ring buffer of historical inputs | **$O(T)$ or $O(T^2)$ unbounded:** Requires full KV-Cache scaling with context length |
| **Long-Term Context Capture**| Degrades over large context ($T > 1000$) due to state compression | Excellent via Dilated Convolutions: $RF = 1 + \sum (K_l - 1) \cdot D_l$ | Global receptive field at cost of severe compute scaling |

##### Production Decision & Justification
**Selected Architecture: Temporal Convolutional Network (TCN) or Hybrid Low-Layer Causal TCN.**

1.  **Elimination of Vanilla LSTMs:** LSTMs are bottlenecked during training due to the sequential time-step execution dependency $h_t = f(h_{t-1})$, preventing scalable GPU utilization on large datasets.
2.  **Elimination of Transformers:** Transformers require a growing Key-Value (KV) cache for streaming inference. Under 10,000 events/sec per stream, maintaining KV-caches for millions of concurrent streams leads to memory thrashing and unbounded tail latency ($p99$).
3.  **The TCN Advantage:**
    *   **Training Phase:** Employs Causal 1D Dilated Convolutions. Computes across all timesteps simultaneously using standard 1D CNN GEMM operations.
    *   **Causality Guarantee:** Zero future information leakage ensured via **Causal Padding** (padding input strictly on the left by $(K - 1) \cdot D$).
    *   **Inference Phase:** Replaced with a **Fixed-Size Ring-Buffer Convolution Cache**. Since receptive fields are statically bounded by depth $L$, dilation $D$, and kernel size $K$, inference requires a constant-size ring-buffer memory pool, delivering deterministic $O(1)$ step execution without tail latency spikes.

---

### Scenario 3: Deep Technical Debugging & Numerical Instability

#### The Question
"You are training a deep 8-layer stacked LSTM on multi-variate high-frequency financial sequence data. At epoch 42, the training loss suddenly collapses to `NaN`. You inspect the pipeline: Gradient Clipping was already enabled with `max_norm=1.0`, input data contains zero `NaN`s, and Batch Normalization is applied between recurrent layers. Walk me through the root mathematical cause of this failure and your systematic remediation steps."

#### Interviewer Intent
Filters candidates who understand the mathematical breakdown of recurrent operations under backpropagation, activation landscape behaviors, and the specific limitations of normalization techniques on sequential hidden states.

#### Probing Follow-up Patterns
*   *“Why does standard Batch Normalization fail or destabilize inside Recurrent Hidden State transitions over time?”*
*   *“How can an explosion occur inside the LSTM cell state $C_t$ even when hidden state activation gradient norm $\frac{\partial \mathcal{L}}{\partial h_t}$ is bounded by clipping?”*

#### Perfect Senior Staff Response

```
                     EXPLODING CELL STATE IN UNBOUNDED HIGH-STEP BPTT

       Grad Clip bounds (dh_t) ───►  [ o_t * tanh(C_t) ]  ───► Output Normal
                                           ▲
                                           │  Unbounded Cell State Growth!
                                           │  C_t = f_t * C_{t-1} + i_t * C_tilde_t
                                     [  C_t Accumulation  ]
                                     (If f_t ~ 1 and i_t * C_tilde_t > 0 continuously)
```

##### 1. Root Cause Diagnostics

*   **Failure of Batch Normalization in RNNs:** Batch Normalization calculates statistics ($\mu_B, \sigma_B$) across the current spatial mini-batch. In sequence models, sequence lengths vary, and hidden states $h_t$ exhibit non-stationary population statistics across time step $t$. Applying standard BN across time steps forces historical states into inappropriate population statistics, leading to scaling instability or gradient explosion during BPTT.
*   **The Unbounded Cell State ($C_t$) Explosion:** Standard Gradient Clipping bounds $\left\| \frac{\partial \mathcal{L}}{\partial h_t} \right\|_2$. However, the internal LSTM cell state update is **additive**:
    $$C_t = f_t \odot C_{t-1} + i_t \odot \tilde{C}_t$$
    If forget gates $f_t \approx 1.0$ continuously while candidate vectors $i_t \odot \tilde{C}_t$ retain positive mean bias over hundreds of timesteps, $C_t$ grows unbounded in magnitude ($C_t \to \infty$). When $C_t$ passes into $\tanh(C_t)$, the derivative $\frac{\partial \tanh(C_t)}{\partial C_t} = 1 - \tanh^2(C_t)$ vanishes to $0$. However, extreme float values in $C_t$ cause floating-point representation overflow during FP16 dynamic loss scaling before backprop can clip the gradient, leading to `Inf` $\to$ `NaN`.

##### 2. Systematic Remediation Strategy

1.  **Replace Batch Normalization with Layer Normalization (LayerNorm):**
    Switch from spatial/batch dimensions to normalizing across feature channels *per timestep independently*:
    $$\mu_t = \frac{1}{d} \sum_{i=1}^d h_{t, i}, \quad \sigma_t^2 = \frac{1}{d} \sum_{i=1}^d (h_{t, i} - \mu_t)^2$$
    This stabilizes hidden state variance at timestep $t$ without temporal leakage or dependence on mini-batch sizes.

2.  **Enforce Cell State Bounds via Weight Regularization / Projection:**
    Apply explicit soft bounding or clamping directly on the internal cell state scalar path:
    $$C_t = \text{clip}\left( f_t \odot C_{t-1} + i_t \odot \tilde{C}_t, \, -C_{\text{max}}, \, +C_{\text{max}} \right)$$
    Alternatively, inject an explicit weight decay ($L_2$ penalty) targeted specifically at input projection matrices ($W_c, b_c$) to suppress continuous directional bias in candidate generation $\tilde{C}_t$.

3.  **Forget Gate Bias Initialization Trick:**
    Ensure initial forget gate biases $b_f$ are initialized to small positive values (e.g., $+1.0$ or $+2.0$) to prevent early gradient vanishing, but initialize input gate biases $b_i$ neutral or slightly negative to prevent explosive early accumulation into $C_t$.

4.  **Mixed-Precision Precision Casts (FP32 Guarding):**
    If running under mixed-precision (`torch.cuda.amp`), cast internal recurrent state updates ($C_t, h_t$) explicitly to **FP32 Master Precision** while maintaining FP16/BF16 matrix multiplications ($W \cdot x$). FP16 dynamic range ($\sim 65,504$) overflows quickly under unbounded state dynamics, whereas BF16 or FP32 prevents immediate scale overflow.

---

### Candidate Strategy Checklist

*   **Math First:** Derive shapes, parameters, FLOPs, and gradients quantitatively.
*   **Acknowledge Modern Context:** Know why transformers superseded RNNs for context, but maintain sharp awareness of where CNNs/RNNs remain superior (Edge processing, memory-constrained streaming, constant-time inference).
*   **System Awareness:** Frame architecture choices in terms of real-world deployment metrics: memory bandwidth bounds, FLOP efficiency, hardware quantization compatibility, and execution tail latency.