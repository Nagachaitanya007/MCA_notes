---
title: Deep Learning: CNNs for Image Recognition & RNNs for Sequence Data
date: 2026-10-31T04:35:40.700440
---

# Deep Learning: CNNs for Image Recognition & RNNs for Sequence Data

---

## 1. 🧱 The Core Concept (Basics Refresh)

### Convolutional Neural Networks (CNNs)
Fully Connected (Dense) layers model interactions between all input features and all output units ($\mathcal{O}(N \times M)$ parameters). For a $1000 \times 1000 \times 3$ image feeding into a modest hidden layer of $10^4$ units, a single dense layer requires $3 \times 10^{10}$ weights—computationally intractable and prone to catastrophic overfitting.

CNNs solve this by embedding two strong architectural inductive biases tailored for grid-structured data:
1. **Spatial Locality:** Pixels close to each other are strongly correlated; distant pixels are weakly correlated. Features are extracted via localized receptive fields.
2. **Translation Equivariance:** If an input pattern shifts, its feature representation shifts identically: 
   $$f(g(x)) = g(f(x))$$
   where $g$ is a spatial translation operator. This is enforced via **weight sharing**: the same filter kernel slides across the entire spatial domain.

```
Dense Layer (No inductive bias):
[x_1, x_2, x_3, ..., x_N] ---> Fully Interconnected ---> [h_1, h_2, ..., h_M] 
Parameters: O(N * M)

Convolutional Layer (Spatial locality + Weight sharing):
[x_1, x_2, x_3, x_4, x_5] 
 \   |   /
  [w_1, w_2, w_3] (Sliding Kernel) ---> [h_1, h_2, h_3]
Parameters: O(K_h * K_w * C_in * C_out) << O(N * M)
```

### Recurrent Neural Networks (RNNs)
Dense layers and standard CNNs process inputs independently under an Identical and Independently Distributed (i.i.d.) assumption. Sequence processing requires modeling dynamic temporal context of arbitrary length without exploding parameter sizes.

RNNs introduce **Temporal Weight Sharing**: the exact same transition operator parameterized by matrices $W_{hh}$ and $W_{xh}$ is recursively applied at each discrete step $t$:
$$h_t = \sigma(W_{hh} h_{t-1} + W_{xh} x_t + b)$$

```
Unfolded Computational Graph:
       y_{t-1}             y_t             y_{t+1}
          ^                 ^                 ^
          | W_hy            | W_hy            | W_hy
       [h_{t-1}] --W_hh--> [h_t]  --W_hh--> [h_{t+1}]
          ^                 ^                 ^
          | W_xh            | W_xh            | W_xh
       x_{t-1}             x_t             x_{t+1}
```

The underlying inductive bias is the **Markovian Temporal Prior**: the latent representation $h_t$ forms a sufficient statistic of the historical sequence $\{x_1, \dots, x_t\}$, conditioning the next prediction exclusively on the current state and incoming observation.

---

## 2. ⚙️ Under the Hood (Internal Mechanics & Architecture)

### CNN Mechanics & Architectural Evolution

#### The Discrete 2D Cross-Correlation (Convolution in ML)
For input tensor $X \in \mathbb{R}^{H \times W \times C_{in}}$ and a bank of $C_{out}$ kernels $K \in \mathbb{R}^{K_h \times K_w \times C_{in} \times C_{out}}$:

$$Y(i, j, k) = b_k + \sum_{c=0}^{C_{in}-1} \sum_{m=0}^{K_h-1} \sum_{n=0}^{K_w-1} X(i \cdot s_h + m - p_h, \; j \cdot s_w + n - p_w, \; c) \cdot K(m, n, c, k)$$

*   **Spatial Output Dimensions:**
    $$H_{out} = \left\lfloor \frac{H_{in} - K_h + 2p_h}{s_h} \right\rfloor + 1$$
*   **Effective Receptive Field (ERF):**
    For layer $l$, receptive field size $RF_l$ grows recursively:
    $$RF_l = RF_{l-1} + (K_l - 1) \cdot \prod_{i=1}^{l-1} s_i = RF_{l-1} + (K_l - 1) \cdot S_{l-1}$$
    *Dilated Convolutions* expand the kernel spacing by dilation rate $d$, modifying the effective kernel footprint to:
    $$\hat{K} = K + (K - 1)(d - 1)$$
    This expands the ERF exponentially without incurring parameter or compute bloat.

```
Standard Kernel (3x3, d=1):       Dilated Kernel (3x3, d=2):
       [x][x][x]                         [x] . [x] . [x]
       [x][x][x]                         .   .   .   .   .
       [x][x][x]                         [x] . [x] . [x]
    Footprint = 3x3                      .   .   .   .   .
                                         [x] . [x] . [x]
                                         Footprint = 5x5
```

#### Architectural Lineage

```
AlexNet (2012)        VGG (2014)               ResNet (2015)                ConvNeXt (2022)
[11x11, 5x5 Conv] -> [Stack 3x3 Convs] ------> [Residual Blocks] ----------> [Depthwise-Separable]
Large Kernels         Factorized Receptive     Identity Shortcuts:           Large 7x7 Kernels,
Parameter-Heavy       Fields: 2x(3x3) = 5x5    x + F(x)                      Inverted Bottleneck
                      3x(3x3) = 7x7 ERF        Solves Vanishing Gradient     Transformer-inspired
```

*   **VGG Factorization:** Two stacked $3 \times 3$ filters have an ERF of $5 \times 5$, but use $2 \times (3^2 \cdot C^2) = 18C^2$ parameters versus $1 \times (5^2 \cdot C^2) = 25C^2$ (a $28\%$ parameter reduction), while introducing an extra intermediate non-linearity.
*   **ResNet & Residual Learning:** As depth increases, degradation occurs: deep networks exhibit higher *training* error than shallow counterparts (not overfitting, but optimization failure). ResNet reformulates the mapping as $\mathcal{H}(x) = \mathcal{F}(x, \{W_i\}) + x$.
    
    The gradient propagation through an addition operation guarantees direct signal paths:
    $$\frac{\partial \mathcal{E}}{\partial x} = \frac{\partial \mathcal{E}}{\partial \mathcal{H}} \frac{\partial \mathcal{H}}{\partial x} = \frac{\partial \mathcal{E}}{\partial \mathcal{H}} \left( \frac{\partial \mathcal{F}}{\partial x} + \mathbf{I} \right)$$
    Even if the learned Jacobian $\frac{\partial \mathcal{F}}{\partial x}$ vanishes, the term $\mathbf{I}$ preserves the gradient vector back to early layers:
    
    $$\frac{\partial \mathcal{E}}{\partial x_l} = \frac{\partial \mathcal{E}}{\partial x_L} \left( \mathbf{I} + \frac{\partial}{\partial x_l} \sum_{k=l}^{L-1} \mathcal{F}_k \right)$$

*   **Depthwise Separable Convolutions (MobileNet / ConvNeXt):**
    Splits standard convolution into:
    1. *Depthwise:* Spatial filtering per channel using $C_{in}$ distinct $K \times K \times 1$ filters.
    2. *Pointwise:* Channel-pooling linear projection using $C_{out}$ instances of $1 \times 1 \times C_{in}$ filters.

    $$\text{Compute Ratio} = \frac{K^2 \cdot C_{in} \cdot H \cdot W + C_{in} \cdot C_{out} \cdot H \cdot W}{K^2 \cdot C_{in} \cdot C_{out} \cdot H \cdot W} = \frac{1}{C_{out}} + \frac{1}{K^2} \approx \frac{1}{K^2}$$
    For $3 \times 3$ kernels, this yields an $\sim 8\times$ to $9\times$ reduction in multiply-accumulate operations (MACs).

---

### RNN, LSTM, and GRU Mechanics

#### The Backpropagation Through Time (BPTT) Bottleneck
Given sequence length $T$ and loss $\mathcal{L} = \sum_{t=1}^T \mathcal{L}_t$:

$$\frac{\partial \mathcal{L}_T}{\partial W_{hh}} = \sum_{k=1}^T \frac{\partial \mathcal{L}_T}{\partial h_T} \frac{\partial h_T}{\partial h_k} \frac{\partial h_k}{\partial W_{hh}}$$

Expanding the temporal chain rule through continuous Jacobian matrix multiplications:

$$\frac{\partial h_T}{\partial h_k} = \prod_{j=k+1}^T \frac{\partial h_j}{\partial h_{j-1}} = \prod_{j=k+1}^T \mathbf{diag}(1 - \tanh^2(a_j)) W_{hh}^T$$

Let $\gamma$ be the upper bound of the spectral norm of $W_{hh}^T$:
*   **If $\rho(W_{hh}) < 1$ and $|1 - \tanh^2(\cdot)| < 1$:** The product contracts exponentially toward $0$ as $(T - k) \to \infty$ (**Vanishing Gradient**).
*   **If $\rho(W_{hh}) > 1$:** The product expands exponentially to $\infty$ (**Exploding Gradient**).

```
Vanilla RNN Temporal Path:
h_0 ---> h_1 ---> h_2 ---> ... ---> h_T  [Repeated matrix multiplication by W_hh]
  Gradient: (W_hh^T * diag(1 - tanh^2))^T  ===> Explodes or Vanishes exponentially!

LSTM Constant Error Carousel (CEC):
c_0 =================================> c_T  [Additive updates via Forget/Input gates]
  Gradient: c_{t-1} = c_t * f_t             ===> Linear highway preserves gradients!
```

#### The LSTM Solution: The Constant Error Carousel (CEC)
The Long Short-Term Memory network eliminates vanishing gradients along the sequence by isolating internal memory accumulation within an additive cell state $C_t$:

$$\begin{aligned}
f_t &= \sigma(W_f [h_{t-1}, x_t] + b_f) \quad &&\text{(Forget Gate: what to purge)} \\
i_t &= \sigma(W_i [h_{t-1}, x_t] + b_i) \quad &&\text{(Input Gate: what to update)} \\
\tilde{C}_t &= \tanh(W_c [h_{t-1}, x_t] + b_c) \quad &&\text{(Candidate Cell State)} \\
C_t &= f_t \odot C_{t-1} + i_t \odot \tilde{C}_t \quad &&\text{(Cell State Update: additive linear highway)} \\
o_t &= \sigma(W_o [h_{t-1}, x_t] + b_o) \quad &&\text{(Output Gate: exposure filter)} \\
h_t &= o_t \odot \tanh(C_t) \quad &&\text{(Hidden State)}
\end{aligned}$$

The gradient update along the cell state is:

$$\frac{\partial C_t}{\partial C_{t-1}} = f_t$$

If the forget gate saturates near $1.0$ ($f_t \to 1$), the gradient flows across arbitrary temporal spans without exponential decay:
$$\frac{\partial \mathcal{L}}{\partial C_k} = \frac{\partial \mathcal{L}}{\partial C_T} \prod_{j=k+1}^T f_j \approx \frac{\partial \mathcal{L}}{\partial C_T}$$

#### GRU: Computational Optimization
The Gated Recurrent Unit collapses $C_t$ and $h_t$ into a single state vector, eliminating one gate:

$$\begin{aligned}
z_t &= \sigma(W_z [h_{t-1}, x_t]) \quad &&\text{(Update Gate)} \\
r_t &= \sigma(W_r [h_{t-1}, x_t]) \quad &&\text{(Reset Gate)} \\
\tilde{h}_t &= \tanh(W [r_t \odot h_{t-1}, x_t]) \quad &&\text{(Candidate Hidden State)} \\
h_t &= (1 - z_t) \odot h_{t-1} + z_t \odot \tilde{h}_t \quad &&\text{(Linear Interpolation)}
\end{aligned}$$

*Trade-off Profile:* GRU exposes $\approx 25\%$ fewer parameters than an LSTM (3 sets of gates vs. 4), yields higher cache locality, trains faster, and matches LSTM empirical performance on all but exceptionally long horizons with complex state-tracking demands.

---

### Hardware, FLOPs, and Execution Profiling

| Architecture Primitive | Parameter Complexity | Arithmetic Complexity (FLOPs) | Memory Access Characteristics |
| :--- | :--- | :--- | :--- |
| **Standard 2D Conv** | $\mathcal{O}(K^2 \cdot C_{in} \cdot C_{out})$ | $\mathcal{O}(H \cdot W \cdot K^2 \cdot C_{in} \cdot C_{out})$ | **Compute-Bound:** High arithmetic intensity (FLOPs/byte). Reuses weights across spatial patches. Ideal for Tensor Cores. |
| **Depthwise Conv** | $\mathcal{O}(K^2 \cdot C_{in})$ | $\mathcal{O}(H \cdot W \cdot K^2 \cdot C_{in})$ | **Memory-Bound:** Low arithmetic intensity. High data movement overhead (SRAM $\leftrightarrow$ DRAM) relative to compute. |
| **Vanilla RNN Step** | $\mathcal{O}(D_{in} H + H^2)$ | $\mathcal{O}(D_{in} H + H^2)$ per step | **Memory-Bound:** Vector-matrix operations limit performance. Hidden states must serialize across time. Low hardware utilization. |
| **LSTM Step** | $\mathcal{O}(4(D_{in} H + H^2))$ | $\mathcal{O}(4(D_{in} H + H^2))$ per step | **Sequential Bottleneck:** Inability to parallelize temporal dimension during forward training pass (unlike Transformers/TCNs). |

---

## 3. ⚠️ The Interview Warzone (Scenarios, Probing, & Responses)

### Scenario 1: Ultra-Low Latency Inference on Edge Devices
> **Interviewer:** "You are deploying a pedestrian-detection CNN to an embedded chip on an autonomous vehicle. The pipeline is memory-bandwidth constrained. The current model (a vanilla ResNet-50) runs at 28 FPS. Your target is 120 FPS with minimal loss in mAP. How do you re-architect the network, and what low-level hardware factors dictate your choices?"

#### The Candidate Response
1. **Factorize Convolutions via Inverted Bottleneck Blocks:**
   Replace the standard $3 \times 3$ bottleneck blocks with Depthwise Separable convolutions with expansion ratios of 4 to 6 (MobileNetV2/ConvNeXt style). This cuts down compute complexity by nearly $\frac{1}{K^2} \approx 8\times$ to $9\times$.

2. **Diagnose Arithmetic Intensity & Memory Access Cost (MAC):**
   Simply reducing FLOPs does not guarantee lower latency. On embedded silicon, inference latency is often bounded by memory access, not arithmetic operations:
   $$\text{MAC} = \sum (\text{Input Size} + \text{Output Size} + \text{Weight Footprint})$$
   Depthwise convolutions have a very low arithmetic intensity ($\text{FLOPs} / \text{Byte}$). Without operator fusion, they spend most of their execution cycles waiting on DRAM data transfers. 

3. **Concrete Architecture Adjustments:**
   * **Kernel Fusion:** Fuse `Conv2D + BatchNorm + ReLU/SiLU` into single execution kernels to preserve feature maps inside fast on-chip registers/SRAM, avoiding DRAM roundtrips.
   * **Channel Balance:** Equalize input and output channels where possible. By the AM-GM inequality, given computational budget $B = H \cdot W \cdot C_{in} \cdot C_{out}$, MAC is minimized when $C_{in} = C_{out}$:
     $$\text{MAC} \ge 2\sqrt{B \cdot H \cdot W} + \text{Weight Buffer}$$
   * **Downsample Sparingly:** Avoid large spatial dimensions deep in the network. Apply a stride-2 convolution early (e.g., rapid $4\times$ spatial downsampling in the stem) to shrink intermediate activation footprints.

```
Standard ResNet Block:
[1x1 Conv, Reduce] -> [3x3 Conv] -> [1x1 Conv, Expand]
(High FLOPs, high arithmetic intensity)

Optimized Edge Block (Inverted Bottleneck):
[1x1 Conv, Expand] -> [Fused 3x3 Depthwise Conv + Activation] -> [1x1 Conv, Linear Projection]
(Low FLOPs, engineered for high SRAM cache residency)
```

4. **Quantization Strategy:**
   Run Post-Training Quantization (PTQ) to INT8. If the activation distribution exhibits severe outliers in depthwise layers, switch to Quantization-Aware Training (QAT). INT8 delivers a $4\times$ reduction in bandwidth pressure and unlocks high-throughput INT8 Tensor Core / NPU vector pipelines.

---

### Scenario 2: Long-Horizon Temporal Sensor Telemetry
> **Interviewer:** "You're building an engine anomaly detection system. Sensor data arrives at 100 Hz, and anomalies correlate across temporal windows spanning 15,000 steps. Your predecessor trained an LSTM that plateaus at poor performance and frequently diverges during training. How do you fix this?"

#### The Candidate Response

1. **Root-Cause Analysis:**
   * **BPTT Numerical Instability:** Even though LSTM gates contain a Constant Error Carousel, backpropagating through 15,000 steps causes vanishing components via gate evaluations and exploding values in $W_h$ projections.
   * **Memory Wall:** Standard BPTT over $T=15,000$ requires storing all intermediate cell and hidden states for backward pass calculations:
     $$\text{Memory} = \mathcal{O}(T \cdot B \cdot H)$$
     This quickly triggers CUDA Out-Of-Memory (OOM) errors at realistic batch sizes.
   * **Loss of Long-Horizon Information:** LSTMs realistically preserve information across roughly a few hundred steps. A horizon of 15,000 steps exceeds the memory retention limits of soft gating mechanisms.

```
Long Sequence Problem (15,000 Steps):
x_1 -> x_2 -> ... -> x_15000 (Forward)
[Memory stores 15,000 activation states for backward pass]
x_1 <- x_2 <- ... <- x_15000 (Backward: vanishing/exploding gradients)

Solution Strategy:
1. Truncate BPTT to chunks of k_1=128, passing detached h_t forward.
2. Replace or augment LSTM with Dilated Temporal Convolutions (TCN) or State Space Models (Mamba).
```

2. **Immediate Remediation (Fixing the RNN Pipeline):**
   * **Truncated BPTT (TBPTT):** Forward-pass across the full sequence, but truncate the backward pass to a window $k_1$ (e.g., 128 steps). Detach the gradient graph at chunk boundaries:
     $$h_{chunk\_end} = h_{chunk\_end}.\text{detach}()$$
   * **Forget Gate Bias Initialization:** Initialize the forget gate bias to a high value ($b_f \sim [1.0, 2.0]$). This forces $f_t \approx 1$ early in training, maintaining gradient highways through the CEC by default.
   * **Gradient Clipping:** Clip gradients by $L_2$ norm:
     $$g \leftarrow g \cdot \min\left(1, \frac{\text{threshold}}{\|g\|_2}\right)$$
     This prevents single erratic updates from corrupting the parameter manifold.

3. **Architectural Redesign:**
   * **Temporal Convolutional Network (TCN):** Replace the RNN with causal, dilated 1D convolutions. Stacking layers with exponentially increasing dilation factors ($d = 2^0, 2^1, 2^2, \dots$) scales the receptive field exponentially:
     $$\text{RF} = 1 + \sum_{l=0}^{L-1} (K_l - 1) \cdot d_l$$
     This achieves a receptive field of 15,000+ using only $\sim 14$ layers without sequential step dependencies, unlocking full GPU parallelization during training.
   * **State Space Models (SSMs / S4 / Mamba):** If strict $\mathcal{O}(1)$ step-inference latency is required, deploy an SSM. SSMs maintain long-range dependencies over tens of thousands of tokens while mapping computationally to a continuous parallelizable convolution during training:
     $$h'(t) = \mathbf{A}h(t) + \mathbf{B}x(t), \quad y(t) = \mathbf{C}h(t) + \mathbf{D}x(t)$$
     Discretizing this linear time-invariant system yields stable gradient propagation over extensive contexts where LSTMs fail.

---

### Scenario 3: CNN Equivariance vs. Invariance Failures
> **Interviewer:** "A common textbook claim is that CNNs are completely shift, scale, and rotation invariant. Prove why this claim is technically false, and describe how you would build true geometric invariance into an image recognition pipeline."

#### The Candidate Response

1. **Deconstructing the Misconception:**
   * **Equivariance $\neq$ Invariance:** Standard convolutions are *translation equivariant*, not translation invariant. If the input shifts by $\Delta$, the feature map shifts by $\Delta$:
     $$f(T_\Delta(x)) = T_\Delta(f(x))$$
     Invariance means the output remains unchanged under transformations:
     $$f(T_\Delta(x)) = f(x)$$
   * **Subsampling Breaks Equivariance:** Downsampling layers (strided convolutions, max/average pooling) break translation equivariance. Subsampling violates the Nyquist-Shannon sampling theorem; high-frequency components alias when shifted by an arbitrary sub-stride distance. A 1-pixel shift in the input can drastically alter activations after several pooling stages.
   * **Rotations and Scale Variations:** Standard orthogonal grid filters have zero inductive bias for rotation or scale transformations:
     $$f(R_\theta(x)) \neq R_\theta(f(x)) \quad \text{and} \quad f(R_\theta(x)) \neq f(x)$$
     A standard kernel trained exclusively on upright objects will fail to register the same features when the inputs are rotated $90^\circ$.

```
Shift Sensitivity in Max Pooling (Stride 2):
Input A: [0, 8, 1, 0]  ---> Max Pool ---> [8]
Input B: [8, 0, 0, 1] (Shifted 1 step left)
Input B: [8, 0, 0, 1]  ---> Max Pool ---> [8, 1]  <-- Activation vector completely changed!
```

2. **Engineering Geometric Invariance:**

```
Input Image 
     |
     v
[Spatial Transformer Network (STN)]
  ├── Localization Net: Predicts affine matrix \theta
  ├── Grid Generator: Evaluates sampling grid
  └── Sampler: Bilinear interpolation
     |
     v
Canonical Transformed Image (Normalized orientation/scale)
     |
     v
[Standard CNN Backbone] ---> Fully Invariant Predictions
```

*   **Spatial Transformer Networks (STNs):**
    Introduce a dynamic localization network that learns spatial transformation parameters $\theta$:
    $$\begin{pmatrix} x_i^s \\ y_i^s \end{pmatrix} = \begin{bmatrix} \theta_{11} & \theta_{12} & \theta_{13} \\ \theta_{21} & \theta_{22} & \theta_{23} \end{bmatrix} \begin{pmatrix} x_i^t \\ y_i^t \\ 1 \end{pmatrix}$$
    The module applies a differentiable bilinear interpolation sampler to the input tensor, warping it into a canonical, normalized pose before feeding it into downstream convolution layers.
*   **Anti-Aliased Downsampling:**
    Replace naive Strided Conv / Max-Pooling with low-pass filtered operations (BlurPool). Decouple pooling into two steps:
    1. Dense evaluation of features (stride 1).
    2. Blurring with an anti-aliasing filter (e.g., a normalized Gaussian/binomial kernel) followed by sub-sampling. This restores shift-invariance to the network.
*   **Group Equivariant CNNs (G-CNNs):**
    Expand the domain of convolutions from spatial translations ($\mathbb{R}^2$) to symmetry transformation groups (e.g., the $p4$ group, which includes discrete translations and $90^\circ$ rotations). Kernels are explicitly rotated across the group during the forward pass, establishing guaranteed mathematical equivariance across orientations.

---

### Deep-Dive Probing Questions & Follow-ups

#### Q: "Why is Batch Normalization universally applied in CNNs, but rarely successful in traditional RNNs? What do we use instead?"
*   **Answer:**
    *   *CNNs:* Channel-wise spatial statistics are consistent across images. Batch Normalization computes statistics across the mini-batch and spatial dimensions $(N, H, W)$ for each channel $C$. Feature distributions remain relatively stable across spatial activations.
    *   *RNNs:* Temporal activations vary widely because sequences have dynamic lengths, and variance accumulates over unrolled steps. Computing mini-batch statistics per time step $t$ fails when sequences have variable lengths (few samples populate long steps $T$), leading to noisy, unstable running statistics. Furthermore, tracking separate running statistics $(\mu_t, \sigma_t)$ for thousands of time steps is computationally inefficient and damages generalization across different sequence lengths.
    *   *The Fix:* Use **Layer Normalization (LN)**. LN computes mean and variance along the feature dimension $H$ independently for each sample at each individual time-step $t$:
        $$\mu_t = \frac{1}{H}\sum_{i=1}^H x_{t, i}, \quad \sigma_t^2 = \frac{1}{H}\sum_{i=1}^H (x_{t, i} - \mu_t)^2$$
        This makes normalization independent of batch size, sequence length, and interactions between unrelated sequences.

#### Q: "What determines whether you should use a 1x1 convolution versus a linear layer?"
*   **Answer:**
    Computationally, a $1 \times 1$ convolution with $C_{in}$ inputs and $C_{out}$ outputs applied to a tensor of shape $(B, C_{in}, H, W)$ is mathematically identical to flattening the spatial dimensions to $(B \cdot H \cdot W, C_{in})$ and applying a Linear layer ($W \in \mathbb{R}^{C_{out} \times C_{in}}$). 
    
    The choice comes down to memory layout and hardware performance:
    *   $1 \times 1$ convolutions operate natively on 4D tensors (NCHW or NHWC format) using highly tuned GEMM libraries (e.g., cuDNN, TensorRT). This avoids explicit memory permutations or tensor reshaping overheads.
    *   Linear layers operate on 2D matrices $(M, K)$. Reshaping a non-contiguous NCHW tensor to feed a linear layer forces a memory copy/permutation across DRAM, degrading runtime efficiency on hardware accelerators.