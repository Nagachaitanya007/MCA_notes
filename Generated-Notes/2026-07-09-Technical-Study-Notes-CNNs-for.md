---
title: Technical Study Notes: CNNs for Image Recognition & RNNs for Sequence Data
date: 2026-07-09T04:32:20.324264
---

# Technical Study Notes: CNNs for Image Recognition & RNNs for Sequence Data

---

## 🧱 1. The Core Concept (Basics Refresh)

To design high-throughput visual or sequential systems, you must understand the architectural inductive biases that make Convolutional Neural Networks (CNNs) and Recurrent Neural Networks (RNNs) fundamentally superior to Multi-Layer Perceptrons (MLPs).

```
   MLP (Fully Connected)                   CNN (Local Connectivity)              RNN (Temporal Weight Sharing)
   
     In       Out                         Input       Kernel      Output           Input       Hidden      Output
   [ x1 ] \ / [ y1 ]                     [ x1 ] \                              [ x_t-1 ] -> [ h_t-1 ]
           X                             [ x2 ] -- [ w1, w2 ] -> [ y1 ]                        |
   [ x2 ] / \ [ y2 ]                     [ x3 ] /                              [ x_t   ] -> [ h_t   ] -> [ y_t ]
                                         [ x4 ]                                                |
   (Every input connects                 (Weights slide over local regions;    [ x_t+1 ] -> [ h_t+1 ]
    to every output)                      translation-equivariant)             (Sequential state loops over time)
```

### Why MLPs Fail on Images and Sequences

1. **Dimensionality Explosion & Loss of Locality (Images):** 
   A modest $1024 \times 1024 \times 3$ image yields over $3$ million input features. A single fully connected layer with $1000$ hidden units requires **$3 \times 10^9$ parameters**. MLPs treat nearby pixels (spatial neighbors) and distant pixels identically, failing to exploit spatial correlations. They lack **translation invariance**: if a target object shifts by 3 pixels, an MLP must re-learn its features from scratch.
2. **Variable Input Lengths & Lost Context (Sequences):**
   MLPs require fixed-size inputs. If a system processes natural language sentences or streaming telemetry, zero-padding to a arbitrary maximum length ($T_{\max}$) wastes memory and compute. Crucially, MLPs cannot easily share learned temporal features; learning that the word "not" negates a verb at position 2 does not automatically transfer to position 15.

---

### Convolutional Networks: Spatial Inductive Biases

CNNs constrain the model search space using two key principles:

* **Local Connectivity (Receptive Fields):** Neurons in layer $l$ connect only to a localized spatial patch of layer $l-1$. This models the physical reality that pixels close to each other are highly correlated.
* **Parameter Sharing (Weight Sharing):** The same filter (kernel) is convolved across the entire input space. If a feature (e.g., a vertical edge) is useful at top-left, it is equally useful at bottom-right.
* **Translation Equivariance:** If the input shifts, the output feature map shifts by the same amount. Formally, let $f$ be the convolution operator and $g$ be the translation operator:
  $$f(g(x)) = g(f(x))$$

---

### Recurrent Networks: Temporal Inductive Biases

RNNs process variable-length inputs ($x_1, x_2, \dots, x_T$) by maintaining an internal recurrent hidden state ($h_t$).

* **Temporal Weight Sharing:** The transition parameters ($W_{hh}$, $W_{xh}$) are identical across all time steps $t$. This allows the network to generalize to sequences of arbitrary length.
* **Sequential Causality:** The state at time $t$ depends strictly on the current input $x_t$ and the historical hidden state $h_{t-1}$:
  $$h_t = f(h_{t-1}, x_t)$$

---

### Core Structural Trade-offs

| Dimension | Multi-Layer Perceptron (MLP) | Convolutional Neural Network (CNN) | Recurrent Neural Network (RNN) |
| :--- | :--- | :--- | :--- |
| **Spatial Inductive Bias** | None (isotropic connectivity) | High (local locality, translation equivariance) | None |
| **Temporal Inductive Bias**| None | Weak (can capture 1D sequence patterns locally) | High (strict causal order, sequence invariance) |
| **Computational Complexity** | $O(N \cdot M)$ per layer | $O(H \cdot W \cdot C_{in} \cdot C_{out} \cdot K_h \cdot K_w)$ | $O(T \cdot d^2)$ (where $T$ is time steps, $d$ is state dim) |
| **Parallelizability** | Extremely high (fully parallelizable) | Highly parallel (fully parallelizable across space) | Poor (sequential bottleneck over time step $T$) |
| **Memory Footprint** | Extremely large (scales with input spatial dim) | Highly efficient (determined by kernel size, not image size) | Small (shares parameters across time, but activations scale with $T$) |

---

## ⚙️ 2. Under the Hood (Internal Mechanics & Architecture)

---

### CNN Mechanics

#### 2D Convolution Formulation
Let $X \in \mathbb{R}^{H \times W \times C_{in}}$ be the input tensor, and $W \in \mathbb{R}^{K \times K \times C_{in} \times C_{out}}$ be the kernel weight tensor. The value of a single output unit at spatial location $(i, j)$ in channel $c$ is:

$$Y_{i, j, c} = \sum_{k=1}^{C_{in}} \sum_{m=- \lfloor K/2 \rfloor}^{\lfloor K/2 \rfloor} \sum_{n=- \lfloor K/2 \rfloor}^{\lfloor K/2 \rfloor} X_{i \cdot S + m,\, j \cdot S + n,\, k} \cdot W_{m + \lfloor K/2 \rfloor,\, n + \lfloor K/2 \rfloor,\, k,\, c} + b_c$$

Where:
* $S$ is the stride (spatial step rate).
* $P$ is the padding (zero-padding added to boundary).
* $K$ is the kernel size (typically odd-valued, e.g., $3 \times 3$ or $5 \times 5$, to ensure symmetric padding).

#### Spatial Output Dimensions
The spatial dimensions of the output tensor ($H_{out}, W_{out}$) are calculated via:

$$H_{out} = \left\lfloor \frac{H_{in} - K + 2P}{S} \right\rfloor + 1$$

$$W_{out} = \left\lfloor \frac{W_{in} - K + 2P}{S} \right\rfloor + 1$$

#### Receptive Field (RF) Math
The receptive field defines the spatial window in the input image that influences a specific unit in layer $L$. Computing the RF of a deep layer is critical for verifying that the model has sufficient spatial context to make predictions.
Let $r_{l}$ be the RF of layer $l$, $s_l$ be the stride of layer $l$, and $k_l$ be the kernel size of layer $l$. 
The recursive formula (working from input to output) is:

$$r_l = r_{l-1} + (k_l - 1) \cdot j_{l-1}$$

Where $j_{l-1}$ is the cumulative stride (jump) of all preceding layers up to layer $l-1$:

$$j_{l-1} = \prod_{i=1}^{l-1} s_i \quad \text{with} \quad j_0 = 1, \quad r_0 = 1$$

#### Pooling Layers: Max vs. Average
* **Max Pooling:** Selects the maximum value in a window. It acts as an activation-driven downsampling step, extracting the most prominent features (e.g., sharp edges). It provides translation invariance but discards precise spatial localization.
* **Average Pooling:** Computes the mean value. It acts as a smoothing operation, preserving global background context but smoothing out high-frequency spatial features. Frequently used at the final layer (Global Average Pooling) to reduce spatial dimensions to $1 \times 1$ before classification.

```
Input (4x4)           Max Pooling (2x2, stride 2)        Average Pooling (2x2, stride 2)
[ 1  3 ] [ 2  9 ]                [ 3   9 ]                           [ 2.5   5.5 ]
[ 2  4 ] [ 3  8 ]   ========>    [ 6   5 ]             ========>     [ 4.5   3.0 ]
[ 5  6 ] [ 1  2 ]
[ 4  3 ] [ 4  5 ]
```

---

### Advanced CNN Blocks

#### Residual Connections (ResNet)
To train extremely deep architectures (e.g., 100+ layers), ResNets bypass layers using identity shortcuts:

$$H(x) = F(x) + x$$

```
             x ---> [ Identity Shortcut ] ----+
             |                                |
             +---> [ Conv ] -> [ ReLU ] -> [ Conv ] -> [ + ] -> [ Output ]
```

* **Why it solves vanishing gradients:** During backpropagation, the gradient of the loss $\mathcal{L}$ with respect to the input $x_l$ is:
  $$\frac{\partial \mathcal{L}}{\partial x_l} = \frac{\partial \mathcal{L}}{\partial x_{l+1}} \frac{\partial x_{l+1}}{\partial x_l} = \frac{\partial \mathcal{L}}{\partial x_{l+1}} \left( \frac{\partial F(x_l, W_l)}{\partial x_l} + I \right)$$
  The identity term $I$ ensures that gradients can flow directly back to earlier layers even if the weight-based path $\frac{\partial F(x_l, W_l)}{\partial x_l}$ approaches zero.

#### Depthwise Separable Convolutions (MobileNet)
Standard convolutions perform spatial filtering and channel cross-correlation simultaneously. Depthwise separable convolutions split this into two distinct steps:

```
Standard Convolution:
[ Input: H x W x M ] ---> [ Conv Kernel: K x K x M x N ] ---> [ Output: H x W x N ]

Depthwise Separable Convolution:
1. Depthwise Step (Spatial Filtering):
[ Input: H x W x M ] ---> [ M independent K x K x 1 Kernels ] ---> [ Intermediate: H x W x M ]
2. Pointwise Step (Channel Mixing):
[ Intermediate: H x W x M ] ---> [ Conv Kernel: 1 x 1 x M x N ] ---> [ Output: H x W x N ]
```

* **Computational Efficiency Analysis:**
  * **Standard Conv Cost:** $H \times W \times M \times N \times K \times K$
  * **Separable Conv Cost:** $(H \times W \times M \times K \times K) + (H \times W \times M \times N)$
  * **Ratio of savings:**
    $$\frac{\text{Separable Cost}}{\text{Standard Cost}} = \frac{M \cdot H \cdot W \cdot (K^2 + N)}{M \cdot N \cdot H \cdot W \cdot K^2} = \frac{1}{N} + \frac{1}{K^2}$$
    For a $3 \times 3$ kernel ($K=3$), this yields an approximate **8-fold reduction** in computational complexity with a negligible loss in accuracy.

---

### RNN Mechanics

```
Vanilla RNN Cell                    LSTM Cell                           GRU Cell

     h_t-1                           c_t-1     h_t-1                     h_t-1
       |                               |         |                         |
       v                               v         v                         v
  +----+----+                     +----+---------+----+               +----+----+
  |  [tanh] | <--- x_t            |  Forget, In, Out  | <--- x_t      | Reset,  | <--- x_t
  +----+----+                     |  Gates & tanh     |               | Update  |
       |                          +----+---------+----+               +----+----+
       v                               |         |                         |
      h_t                             c_t       h_t                       h_t
```

#### Vanilla RNN Math
The recurrence relation of a vanilla RNN is:

$$h_t = \tanh(W_{hh} h_{t-1} + W_{xh} x_t + b_h)$$

$$y_t = \text{softmax}(W_{hy} h_t + b_y)$$

#### The Vanishing and Exploding Gradient Problem
When training an RNN over long sequences using Backpropagation Through Time (BPTT), we compute the gradient of the loss $\mathcal{L}_T$ at time $T$ with respect to the hidden state $h_t$ at some early time $t < T$:

$$\frac{\partial \mathcal{L}_T}{\partial h_t} = \frac{\partial \mathcal{L}_T}{\partial h_T} \frac{\partial h_T}{\partial h_t} = \frac{\partial \mathcal{L}_T}{\partial h_T} \prod_{k=t+1}^{T} \frac{\partial h_k}{\partial h_{k-1}}$$

The Jacobian matrix for a single step transition is:

$$\frac{\partial h_k}{\partial h_{k-1}} = \text{diag}(1 - \tanh^2(W_{hh} h_{k-1} + W_{xh} x_k + b_h)) \cdot W_{hh}^T$$

If the largest eigenvalue (spectral radius) of $W_{hh}$ is less than 1, the product $\prod_{k=t+1}^{T} \frac{\partial h_k}{\partial h_{k-1}}$ decays exponentially toward zero as $T - t$ increases (Vanishing Gradient). 

If the spectral radius is greater than 1, the product grows exponentially, leading to numerical overflow (Exploding Gradient).

---

### Advanced Sequential Units

#### LSTM (Long Short-Term Memory)
LSTMs solve the vanishing gradient problem by introducing a **Cell State ($C_t$)** that acts as an additive gradient highway, regulated by three non-linear gating mechanisms.

$$\begin{aligned}
\text{Forget Gate:} \quad f_t &= \sigma(W_f \cdot [h_{t-1}, x_t] + b_f) \\
\text{Input Gate:} \quad i_t &= \sigma(W_i \cdot [h_{t-1}, x_t] + b_i) \\
\text{Candidate Cell State:} \quad \tilde{C}_t &= \tanh(W_c \cdot [h_{t-1}, x_t] + b_c) \\
\text{Cell State Update:} \quad C_t &= f_t \odot C_{t-1} + i_t \odot \tilde{C}_t \\
\text{Output Gate:} \quad o_t &= \sigma(W_o \cdot [h_{t-1}, x_t] + b_o) \\
\text{Hidden State Update:} \quad h_t &= o_t \odot \tanh(C_t)
\end{aligned}$$

Where $\odot$ represents the Hadamard (element-wise) product.

```
LSTM Gradient Highway:
           C_t-1 ------------------[+]-------------------> C_t
                                    ^
                                    | (additive update avoids vanishing gradients)
           h_t-1 ---> [ Gates ] ----+---> [ tanh ] ---> h_t
```

* **Why LSTM Prevents Vanishing Gradients:** The derivative of the current cell state with respect to the previous cell state is:
  $$\frac{\partial C_t}{\partial C_{t-1}} = f_t + \dots$$
  If the forget gate $f_t$ is active (near 1), the gradient is preserved and can flow backward across arbitrary time distances without exponential decay.

#### GRU (Gated Recurrent Unit)
GRUs are a streamlined variant of LSTMs that merge the cell state and hidden state, reducing parameter count and computational complexity.

$$\begin{aligned}
\text{Reset Gate:} \quad r_t &= \sigma(W_r \cdot [h_{t-1}, x_t] + b_r) \\
\text{Update Gate:} \quad z_t &= \sigma(W_z \cdot [h_{t-1}, x_t] + b_z) \\
\text{Candidate Hidden State:} \quad \tilde{h}_t &= \tanh(W \cdot [r_t \odot h_{t-1}, x_t] + b) \\
\text{Hidden State Update:} \quad h_t &= (1 - z_t) \odot h_{t-1} + z_t \odot \tilde{h}_t
\end{aligned}$$

* **Performance vs. Size Trade-off:** GRUs have ~33% fewer parameters than LSTMs ($3$ gating calculations vs. $4$ in LSTM). They train faster and can generalize better on low-resource datasets, whereas LSTMs are more expressive and perform better on highly complex, long-range sequential tasks.

---

## ⚠️ 3. The Interview Warzone (Scenario-based questions)

### Scenario 1 (Computer Vision/CNNs): Optimizing a CNN for Low-Latency, Resource-Constrained Edge Devices (e.g., Autonomous Vehicle Obstacle Detection)

#### 💬 The Interviewer's Prompt
> *"We need to deploy a real-time object detection model on an embedded ARM CPU inside an autonomous delivery vehicle. The input camera feed is $1080\text{p}$ ($1920 \times 1080 \times 3$) at $30\text{ fps}$. Our current baseline model is ResNet-50, which is running at a latency of over $250\text{ ms}$ per frame and using $100\text{ MB}$ of memory—this is way too slow and power-hungry. You have a budget of $30\text{ ms}$ maximum per frame and must keep the model size under $15\text{ MB}$. How do you re-architect and optimize this network?"*

---

#### 🎯 The Interviewer's Probing Pattern
* *How does the candidate handle the high-resolution input? (Will they suggest downsampling or progressive pooling?)*
* *Do they understand the arithmetic of parameter reduction?*
* *Are they aware of hardware bottlenecks (e.g., memory access costs vs. arithmetic intensity)?*
* *Can they design practical deployment strategies beyond architecture changes?*

---

#### 🏆 The Perfect Response

##### 1. Input Spatial Reduction (Addressing the $1080\text{p}$ Bottleneck)
Processing $1920 \times 1080$ images directly through a standard ResNet-50 is a computational bottleneck. The first layer alone requires:

$$\text{FLOPs} \approx 2 \times H_{out} \times W_{out} \times C_{in} \times C_{out} \times K_h \times K_w$$

To fix this:
* **Resolution Downsampling:** Crop or downsample the input resolution to $448 \times 448$ or $224 \times 224$ using bilinear interpolation, provided the target objects (obstacles) do not become smaller than a $5 \times 5$ pixel area (the limit for spatial detection).
* **Early Strided Convolutions (The "Stem" Layer):** Use a $7 \times 7$ kernel with a stride of 2, followed immediately by a $2 \times 2$ max pooling layer with a stride of 2. This reduces the spatial dimensions by a factor of 4 ($1080\text{p} \to 270\text{p}$) in the first two operations, drastically lowering the computational workload of downstream layers.

```
[ 1920x1080x3 Input ]
        │
        ▼  (Bilinear Interpolation Downsample)
[  448x448x3 Image  ]
        │
        ▼  (Stem: 7x7 Conv, Stride=2, Pad=3)
[  224x224x64 Tensor]
        │
        ▼  (Max Pool, 3x3, Stride=2)
[  112x112x64 Tensor]  <-- 16x reduction in spatial points from raw camera feed
```

##### 2. Architectural Redesign (Replacing the Backbone)
We must replace the standard residual bottlenecks with **Inverted Residual Blocks** (from MobileNetV2) featuring **Depthwise Separable Convolutions** and **Squeeze-and-Excitation (SE) attention**:

```
Inverted Residual Block with SE Attention:

             [ Input: H x W x C ]
                      │
                      ▼
             [ 1x1 Expansion Conv (C -> 6C) ] + [ BatchNorm + ReLU6 ]
                      │
                      ▼
             [ 3x3 Depthwise Conv (Stride=S) ] + [ BatchNorm + ReLU6 ]
                      │
                      ▼
             [ Squeeze-and-Excitation Block ]  <-- (Low-overhead attention)
                      │
                      ▼
             [ 1x1 Linear Projection (6C -> C') ] + [ BatchNorm ] (No ReLU)
                      │
                      ├─── (If S=1 and C==C') ─── [ Add Input Residual ]
                      ▼
             [ Output: H' x W' x C' ]
```

* **Expansion Ratio:** We project low-dimensional channels to a higher-dimensional space ($1 \times 1$ conv) to allow the depthwise convolution to extract expressive spatial features without losing information through non-linear activations (ReLU6) in low-dimensional spaces.
* **Linear Bottlenecks:** Removing the non-linearity (ReLU) after the final projection convolution prevents the activation function from destroying valuable feature information in low-dimensional states.

##### 3. Hardware-Aware Hardware-Software Co-Design
* **Channel Alignments:** ARM CPUs and GPU vector engines utilize SIMD (Single Instruction Multiple Data) registers. We must align all channel counts ($C$) to multiples of 8 or 16 (e.g., 32, 64, 128) to ensure optimal hardware utilization and prevent memory bank conflicts.
* **Kernel Fusion:** Group consecutive `Conv2D -> BatchNorm -> ReLU` layers into a single fused operation. This avoids writing intermediate activation matrices back to the slow external system RAM (DDR), keeping the data in the fast L1/L2 cache instead.

```
Standard execution:   [ Conv ] ──(DDR RAM)──> [ BatchNorm ] ──(DDR RAM)──> [ ReLU ]
Fused execution:      [ Conv -> BatchNorm -> ReLU ] ──(DDR RAM)──> (Only write final activation)
```

##### 4. Quantization-Aware Training (QAT)
To reduce the footprint from $100\text{ MB}$ to under $15\text{ MB}$, we must transition from FP32 (32-bit floating-point) to INT8 (8-bit integer precision).
* We insert simulated quantization noise during the forward pass of training, allowing the weights to adapt to the lower precision:
  $$x_{quant} = \text{clip}\left(\text{round}\left(\frac{x}{scale}\right) + zero\_point, -128, 127\right)$$
* **Impact:** This reduces the model size by **4x** (from $40\text{ MB}$ FP32 to $10\text{ MB}$ INT8) and unlocks ARM NEON assembly acceleration, boosting throughput on edge CPUs.

---

### Scenario 2 (Sequence Data/RNNs): Designing a Real-Time, Variable-Length Clickstream Fraud Detection Pipeline

#### 💬 The Interviewer's Prompt
> *"We are building an online fraud detection system that analyzes user clickstream sequences in real time. The length of click histories varies wildly: some users have only 3 clicks, while others have over 10,000. Our target throughput is $10,000\text{ queries per second (QPS)}$ with a latency of less than $10\text{ ms}$ at $p99$. A candidate proposed a multi-layer bidirectional LSTM, but during load testing, it crashed due to out-of-memory (OOM) errors and struggled with long inference latencies. How do you analyze these bottlenecks and redesign the system?"*

---

#### 🎯 The Interviewer's Probing Pattern
* *Does the candidate recognize why bidirectional LSTMs are unsuitable for real-time streaming systems (causality issues)?*
* *Can they address the $O(T)$ sequential processing bottleneck of RNNs?*
* *Do they know how to handle variable-length sequences efficiently in production (bucketing, truncation)?*
* *How do they manage GPU/CPU memory consumption under extreme sequence lengths ($T=10,000$)?*

---

#### 🏆 The Perfect Response

##### 1. Identifying the Root Bottlenecks of Bidirectional LSTMs
* **The Causality Problem:** A bidirectional LSTM processes sequences in both directions (forward and backward). To compute the backward pass, **the entire sequence up to step $T$ must be known**. For a real-time stream, we cannot wait for a user to finish their session (which could take hours) before evaluating their early clicks for fraud.
* **The Memory and Computation Bottleneck ($O(T)$):** Processing a user session with $T = 10,000$ clicks using a recurrent cell requires $10,000$ sequential step updates. The step updates cannot be parallelized because step $t$ depends on step $t-1$:

```
Sequential dependency (cannot parallelize):
h_0 ---> h_1 ---> h_2 ---> ... ---> h_9999 ---> h_10000
```

This leads to high inference latency and causes memory consumption to scale linearly with sequence length ($O(T)$) during training, resulting in Out-Of-Memory (OOM) crashes.

##### 2. Redesigning the Architecture: Gated Recurrent Unit (GRU) with Dual Temporal Resolution
To handle both very short and very long sequences within our latency budget, we can transition from a bidirectional LSTM to a **Single-Directional GRU with Sequence Bucketing and Truncation**.

```
Input Sequence ───────► [ Sliding Window / Truncation (Max T=256) ]
                                 │
                                 ▼
                        [ Linear Projection ]
                                 │
                                 ▼
                        [ Gated Recurrent Unit (GRU) ]
                                 │
                                 ▼
                        [ Temporal Attention Pooling ] ──► [ Fraud Score (Sigmoid) ]
```

* **Causal Windowing & Truncation:** We truncate sequences to a maximum length of $T_{\max} = 256$. For fraud detection, the most recent context is what matters most; user activity from hours ago can be summarized in static aggregated metadata features rather than being processed step-by-step through an RNN.
* **GRU Transition:** We replace the LSTM with a single-directional GRU to reduce the gate count from 4 to 3, immediately cutting parameter count and execution time by roughly 25-30%.

##### 3. Optimized Production Serving Pipeline
To scale the system to $10,000\text{ QPS}$ with a $p99$ latency under $10\text{ ms}$:

* **Dynamic Tensor Padding with Bucketing:** If we pad all batches to $T_{\max} = 256$, a sequence of length 3 spends 98% of its compute cycles processing meaningless zero-padding tokens. We implement **dynamic bucketing** in our inference engine (e.g., using Triton Inference Server):

```
Incoming Request Queue:
  Req 1 (len: 5), Req 2 (len: 200), Req 3 (len: 12), Req 4 (len: 195)

Step 1: Bucket by Sequence Length
  Bucket A (Short): [ Req 1 (len: 5),  Req 3 (len: 12)  ]  --> Pad to max len 12
  Bucket B (Long):  [ Req 2 (len: 200), Req 4 (len: 195) ]  --> Pad to max len 200

Step 2: Dispatch separate batched runs. Saves ~50% of redundant padding operations.
```

* **Pre-computable Embeddings:** We split click features into categorical tokens (e.g., page type, element ID) and use an embedding lookup layer. These embedding weights are stored in pinned GPU memory to eliminate CPU-GPU host transfer latency.

##### 4. Alternative Architectural Paradigm: Dilated 1D Temporal CNNs (TCNs)
If the sequential nature of the GRU remains a latency bottleneck, we can pivot to a **Temporal Convolutional Network (TCN)** using dilated 1D convolutions:

$$y_t = (x * _d f)_t = \sum_{i=0}^{K-1} f_i \cdot x_{t - d \cdot i}$$

Where $d$ is the dilation factor. By exponentially increasing $d$ at each layer (e.g., $d = 1, 2, 4, 8$), we achieve a wide receptive field with very few layers:

```
Dilated Convolution (Dilation d=4, Kernel K=2):
Layer 2:  O     O     O     O     O     O     O     O (Receptive Field covers 8 steps)
          |    /      |    /      |    /      |    /
Layer 1:  O   O   O   O   O   O   O   O   O   O   O   O (Dilation d=2, Kernel K=2)
          |  /    |  /    |  /    |  /    |  /    |  /
Input:    O O O O O O O O O O O O O O O O O O O O O O (Raw sequence steps)
```

* **Why TCN outperforms RNNs at Scale:** 
  During training and offline evaluation, 1D convolutions do not depend on previous time steps to compute subsequent states. The entire sequence can be processed in parallel across GPU threads, reducing the execution time of long sequences from $O(T)$ to $O(1)$ relative to the temporal dimension.