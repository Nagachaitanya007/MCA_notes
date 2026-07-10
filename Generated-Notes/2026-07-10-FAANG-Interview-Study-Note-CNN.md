---
title: FAANG Interview Study Note: CNNs & RNNs
date: 2026-07-10T04:32:08.405617
---

# FAANG Interview Study Note: CNNs & RNNs

---

## 1. 🧱 The Core Concept (Basics Refresh)

To design, optimize, and defend deep learning architectures in a FAANG-loop system design or ML-infra interview, you must understand the mathematical assumptions and structural priors (inductive biases) of these architectures.

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              INDUCTIVE BIASES                                  │
├─────────────────────────────────────────────────────────────────────────────────┤
│  CNNs: Spatial Locality & Translation Equivariance                               │
│  [Pixel (x,y) correlates with (x+1, y)] ──► Shared kernels sweep space          │
├─────────────────────────────────────────────────────────────────────────────────┤
│  RNNs: Temporal Invariance & Sequential Dependency                              │
│  [State at (t) depends on (t-1)] ──► Shared transition matrix sweeps time       │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Convolutional Neural Networks (CNNs)
*   **Target Domain**: High-dimensional grid-structured data (e.g., 2D images, 3D video volumes, 1D spectrograms).
*   **Key Inductive Biases**:
    1.  **Spatial Locality**: Nearby pixels are highly correlated; features are local (e.g., edges, textures) before they are global (e.g., objects).
    2.  **Translation Equivariance**: If an input feature shifts, its representation in the activation map shifts by the same amount: $f(g(x)) = g(f(x))$. This is achieved via **weight sharing** across the spatial grid.
*   **The Modern Paradigm**: While Vision Transformers (ViTs) relax these biases to achieve higher capacity on massive datasets ($>10^7$ images), CNNs remain the industry gold standard for resource-constrained edge systems, real-time robotics, and dense prediction tasks (e.g., segmentation, object detection) due to their sample efficiency and deterministic computational footprints.

### Recurrent Neural Networks (RNNs)
*   **Target Domain**: Unstructured, variable-length sequence data (e.g., natural language, financial time series, streaming audio).
*   **Key Inductive Biases**:
    1.  **Temporal Invariance**: The rules governing transition from step $t$ to step $t+1$ remain constant across the entire sequence.
    2.  **Sequential Dependency (Causality)**: The state at time $t$ is a direct function of the state at time $t-1$ and the current input $x_t$.
*   **The Modern Paradigm**: While self-attention (Transformers) has largely replaced RNNs for offline, massive-scale NLP due to training parallelization, RNN derivatives and modern State-Space Models (SSMs like Mamba) are critical for real-time, streaming, infinite-horizon sequence processing where $O(1)$ inference memory is required.

---

## 2. ⚙️ Under the Hood (Internal Mechanics & Architecture)

### 2.1 Convolutional Neural Networks (CNNs)

#### Mathematical Formulation of 2D Convolution
For an input tensor $X \in \mathbb{R}^{H \times W \times C_{in}}$ and a bank of $C_{out}$ filters where each filter $W \in \mathbb{R}^{K \times K \times C_{in}}$, the output activation map $Y \in \mathbb{R}^{H' \times W' \times C_{out}}$ (ignoring batch dimension and bias for clarity) at spatial position $(i, j)$ for a specific output channel $c_{out}$ is defined as:

$$Y(i, j, c_{out}) = \sum_{c_{in}=1}^{C_{in}} \sum_{m=- \lfloor \frac{K}{2} \rfloor}^{\lfloor \frac{K}{2} \rfloor} \sum_{n=- \lfloor \frac{K}{2} \rfloor}^{\lfloor \frac{K}{2} \rfloor} X(i \cdot s + m, j \cdot s + n, c_{in}) \cdot W(m + \lfloor \frac{K}{2} \rfloor, n + \lfloor \frac{K}{2} \rfloor, c_{in}, c_{out})$$

Where:
*   $s$ is the stride.
*   $K$ is the kernel size (typically odd, e.g., $3 \times 3$ or $5 \times 5$, to ensure symmetric padding).

#### Receptive Field (RF) Propagation
A critical interviewer question is: *"What is the effective receptive field of layer $L$ in your network?"*
The receptive field $RF_l$ of a unit in layer $l$ is calculated recursively from the input layer ($RF_0 = 1$) forward:

$$RF_l = RF_{l-1} + (K_l - 1) \cdot J_{l-1}$$

Where the jump/stride accumulator $J_{l-1}$ represents the cumulative stride of all preceding layers:

$$J_{l-1} = \prod_{i=1}^{l-1} s_i$$

*Takeaway*: To build deep architectures that capture global context without rapidly downsampling spatial resolution, you must use **Dilated Convolutions**. Dilation introduces spaces into the kernel, expanding the receptive field to $K_{dilated} = K + (K-1)(d-1)$ without adding parameters.

#### Classic Architecture: Residual Connections (ResNet)
As networks grew deeper, they encountered the **Degradation Problem**: accuracy saturates and then degrades rapidly, caused not by overfitting, but by the difficulty of propagating gradients through dozens of unconstrained parameterized layers.

```
          x 
          │ ──┐ Residual Connection (Identity map: dx/dx = 1)
          ▼   │
     ┌────────┐
     │ Weight │
     └────────┘
          ▼
     ┌────────┐
     │ Weight │
     └────────┘
          ▼   │
          + ◄─┘ (Addition)
          ▼
        F(x)+x
```

ResNet solves this by reformulating layers to learn a residual mapping $F(x) = H(x) - x$ rather than the direct mapping $H(x)$.
*   **Forward Pass**: $H(x) = F(x) + x$
*   **Backward Pass (Gradient Flow)**: 
    $$\frac{\partial L}{\partial x} = \frac{\partial L}{\partial H} \frac{\partial H}{\partial x} = \frac{\partial L}{\partial H} \left( \frac{\partial F}{\partial x} + I \right)$$
    The term $+ I$ (identity matrix) ensures that even if the weights of the parameterized layer $F(x)$ vanish towards zero, the gradient $\frac{\partial L}{\partial H}$ can propagate backward directly to earlier layers without attenuation.

#### Modern Edge Optimization: Depthwise Separable Convolutions
Used in MobileNet, this decomposes a standard convolution into two distinct steps to drastically reduce compute (FLOPs) and parameters:

```
Standard Convolution:
[Input: H x W x C_in] ──► [Conv: K x K x C_in x C_out] ──► [Output: H x W x C_out]

Depthwise Separable Convolution:
[Input: H x W x C_in] ──► [Depthwise Conv: K x K x 1 per channel] ──► [Pointwise Conv: 1 x 1 x C_in x C_out]
```

1.  **Depthwise Convolution**: Applies a single spatial filter per input channel.
2.  **Pointwise Convolution**: Applies a $1 \times 1$ convolution to project the channel outputs to $C_{out}$.

**Computational & Parameter Savings**:
*   **Standard Conv Parameter Count**: $K^2 \cdot C_{in} \cdot C_{out}$
*   **Depthwise Separable Parameter Count**: $K^2 \cdot C_{in} + C_{in} \cdot C_{out}$
*   **FLOP Reduction Ratio**:
    $$\frac{\text{Separable Cost}}{\text{Standard Cost}} = \frac{H \cdot W \cdot C_{in} \cdot (K^2 + C_{out})}{H \cdot W \cdot C_{in} \cdot K^2 \cdot C_{out}} = \frac{1}{C_{out}} + \frac{1}{K^2}$$
    For a $3 \times 3$ kernel ($K=3$), this yields an approximate **$8\times$ to $9\times$ reduction** in computational complexity with minimal loss in representation accuracy.

---

### 2.2 Recurrent Neural Networks (RNNs)

#### The Vanilla RNN & The Mathematical Origin of Vanishing/Exploding Gradients
In a vanilla RNN, the hidden state $h_t$ at step $t$ is computed as:

$$h_t = \tanh(W_{hh} h_{t-1} + W_{xh} x_t + b_h)$$

If we backpropagate the loss $L$ computed at the final step $T$ to update the recurrent weights $W_{hh}$, we must compute $\frac{\partial L}{\partial h_1}$ via the chain rule:

$$\frac{\partial L}{\partial h_1} = \frac{\partial L}{\partial h_T} \frac{\partial h_T}{\partial h_1} = \frac{\partial L}{\partial h_T} \prod_{t=2}^{T} \frac{\partial h_t}{\partial h_{t-1}}$$

The Jacobian matrix of the hidden state transition is:

$$\frac{\partial h_t}{\partial h_{t-1}} = \text{diag}(1 - \tanh^2(W_{hh} h_{t-1} + W_{xh} x_t + b_h)) \cdot W_{hh}^T$$

Let $J_t = \frac{\partial h_t}{\partial h_{t-1}}$. When we multiply these Jacobians over $T$ steps:
*   If the largest eigenvalue of $W_{hh}$ is greater than $1$, and the activations do not saturate, the gradient norm explodes exponentially: $\| \frac{\partial L}{\partial h_1} \| \to \infty$ as $T \to \infty$.
*   If the largest eigenvalue of $W_{hh}$ is less than $1$, or if the state activations saturate (where $\tanh' \to 0$), the gradient norm vanishes exponentially: $\| \frac{\partial L}{\partial h_1} \| \to 0$ as $T \to \infty$.

This prevents Vanilla RNNs from learning long-range temporal dependencies.

#### Long Short-Term Memory (LSTM) Architecture
LSTMs mitigate vanishing gradients by introducing a **Cell State** ($C_t$) that acts as an "information superhighway," updated via linear, additive operations rather than continuous multiplicative ones.

```
                 Cell State (C_t-1) ─────────── [x] ──────────────────── (+) ────────► Cell State (C_t)
                                                 ▲                       ▲
                                            Forget Gate (f_t)       Input Gate * Candidate (i_t * ~C_t)
                                                 │                       │
  Hidden State (h_t-1) ──┐                       │                       │
                         ├──► [ Sigmoid / Tanh ] ┴───────────────────────┴──► [x] ──► Hidden State (h_t)
  Input Vector (x_t)  ───┘                                                    ▲
                                                                        Output Gate (o_t)
```

The exact mathematical gating equations are:

$$\begin{aligned}
f_t &= \sigma(W_f \cdot [h_{t-1}, x_t] + b_f) && \text{(Forget Gate: what to drop)} \\
i_t &= \sigma(W_i \cdot [h_{t-1}, x_t] + b_i) && \text{(Input Gate: what to write)} \\
\tilde{C}_t &= \tanh(W_c \cdot [h_{t-1}, x_t] + b_c) && \text{(Candidate Cell State: new candidate information)} \\
C_t &= f_t \odot C_{t-1} + i_t \odot \tilde{C}_t && \text{(Cell State Update: additive update)} \\
o_t &= \sigma(W_o \cdot [h_{t-1}, x_t] + b_o) && \text{(Output Gate: what to reveal)} \\
h_t &= o_t \odot \tanh(C_t) && \text{(Hidden State Update: final representation)}
\end{aligned}$$

Where $\sigma(z) = \frac{1}{1 + e^{-z}}$ and $\odot$ represents the element-wise Hadamard product.

##### Why LSTMs Prevent Vanishing Gradients:
Consider the derivative of the cell state at step $t$ with respect to step $t-1$:

$$\frac{\partial C_t}{\partial C_{t-1}} = f_t + \text{terms involving } \frac{\partial f_t}{\partial C_{t-1}}, \frac{\partial i_t}{\partial C_{t-1}}, \frac{\partial \tilde{C}_t}{\partial C_{t-1}}$$

If the forget gate $f_t$ is active ($f_t \approx 1$), the gradient flows back through the cell state nearly unchanged: $\frac{\partial C_t}{\partial C_{t-1}} \approx 1$. The error can propagate back infinitely over time without exponential decay, depending on the state of the forget gate.

#### Gated Recurrent Unit (GRU)
GRU is a streamlined variant designed to reduce computational overhead by combining the hidden and cell states and using fewer gates:

$$\begin{aligned}
z_t &= \sigma(W_z \cdot [h_{t-1}, x_t] + b_z) && \text{(Update Gate: balances past vs. present)} \\
r_t &= \sigma(W_r \cdot [h_{t-1}, x_t] + b_r) && \text{(Reset Gate: determines how much of past to forget)} \\
\tilde{h}_t &= \tanh(W \cdot [r_t \odot h_{t-1}, x_t] + b) && \text{(Candidate Hidden State)} \\
h_t &= (1 - z_t) \odot h_{t-1} + z_t \odot \tilde{h}_t && \text{(Hidden State Update)}
\end{aligned}$$

*Comparison Trade-off*: GRU has $\approx 25\%$ fewer parameters than LSTM, making it faster to train and less prone to overfitting on smaller datasets. However, LSTM has higher expressive capacity and remains superior for long-term tracking or complex sequence parsing tasks.

---

## 3. ⚠️ The Interview Warzone

### Scenario: Real-Time Edge Video Anomaly Detection
An interviewer asks you to design an on-device, real-time video anomaly detection system for a home security camera. The budget is highly constrained: **max 15 FPS, $<500\text{MB}$ memory footprint, and low latency**.

#### Probing Pattern 1: Compute and Parameter Scaling
> **Interviewer**: *"You chose a 3D CNN (like I3D) to capture spatio-temporal features. How does the FLOP count of a 3D CNN scale with video length, and how will your chosen edge hardware handle that?"*

*   **The Trap**: Suggesting a deep, vanilla 3D CNN. It scales quadratically/cubically with spatial and temporal resolutions, exceeding the compute limits of typical edge devices.
*   **The Pivot**: Decouple spatial and temporal processing. Use a highly optimized 2D CNN (such as MobileNetV3 or ResNet-18) frame-by-frame to extract a compact $d$-dimensional feature vector, then feed these vectors into a temporal aggregator (like a GRU or a light Bi-LSTM).

#### Probing Pattern 2: Memory & Hardware Bandwidth Bottlenecks
> **Interviewer**: *"You chose a GRU to aggregate temporal features over a window of 100 frames. How does this recurrent architecture affect hardware utilization on an accelerator like an Edge TPU, and why is it slower than a 1D Temporal CNN?"*

*   **The Trap**: Relying purely on theoretical FLOP counts. You must address memory bandwidth.
*   **The Critical Staff-level Distinction**: 
    *   **RNNs** are sequential: state $h_t$ must be computed before $h_{t+1}$ can begin. This sequential dependency prevents parallel execution. At each step, weights must be fetched from off-chip DRAM to on-chip SRAM cache. This is a **memory-bandwidth bound** operation characterized by a very low Arithmetic Intensity (FLOPs per byte of memory transfer).
    *   **CNNs** (or 1D Temporal Convolutions over the temporal window) can parallelize computations across the entire time dimension simultaneously. This allows high data reuse inside local registers, transforming it into a **compute-bound** operation that fully saturates hardware accelerators (Tensor Cores/TPU systolic arrays).
*   **The Architectural Trade-off**: If strict real-time sequential processing is needed with zero lookahead, we must use a GRU, but we should apply Group/Layer Normalization and limit hidden dimensions to fit within SRAM. If we can tolerate a small delay (sliding temporal window), a **1D Temporal Convolutional Network (TCN)** is structurally superior for hardware acceleration.

---

### The Perfect Response Architecture

Below is a complete, production-grade PyTorch implementation and system design for the optimal hybrid spatial-temporal architecture: **MobileNetV3-style Depthwise Separable Spatial Extractor coupled with a bidirectional Gated Recurrent Unit (Bi-GRU)**.

```
       [Video Frame Stream: T x C x H x W]
                       │
                       ▼
 ┌───────────────────────────────────────────┐
 │       Spatial Feature Extractor           │
 │ (Depthwise Separable + Pointwise Convs)   │
 └───────────────────────────────────────────┘
                       │
                       ▼
          [Feature Map: T x D_spatial]
                       │
                       ▼
 ┌───────────────────────────────────────────┐
 │          Bidirectional GRU                │
 │  (Processes sequential context forwards/  │
 │          backwards in time)               │
 └───────────────────────────────────────────┘
                       │
                       ▼
 ┌───────────────────────────────────────────┐
 │          Anomaly Output Head              │
 │          (FC + Sigmoid Activation)        │
 └───────────────────────────────────────────┘
```

```python
import torch
import torch.nn as nn
import torch.nn.functional as F

class DepthwiseSeparableConv2d(nn.Module):
    """
    Highly optimized spatial feature extractor module.
    Reduces parameter count and computational complexity by decoupling spatial filtering from channel mixing.
    """
    def __init__(self, in_channels: int, out_channels: int, kernel_size: int = 3, stride: int = 1, padding: int = 1):
        super().__init__()
        # Depthwise phase: applies a single spatial filter per input channel
        self.depthwise = nn.Conv2d(
            in_channels=in_channels,
            out_channels=in_channels,
            kernel_size=kernel_size,
            stride=stride,
            padding=padding,
            groups=in_channels, # Crucial: links each input channel to its own filter
            bias=False
        )
        # Pointwise phase: linear combination of channels to project to out_channels
        self.pointwise = nn.Conv2d(
            in_channels=in_channels,
            out_channels=out_channels,
            kernel_size=1,
            stride=1,
            padding=0,
            bias=False
        )
        self.bn = nn.BatchNorm2d(out_channels)
        self.relu = nn.ReLU6(inplace=True) # ReLU6 is highly stable on edge hardware (fixed FP16 range)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.depthwise(x)
        x = self.pointwise(x)
        x = self.bn(x)
        return self.relu(x)


class VideoTemporalClassifier(nn.Module):
    """
    Hybrid Architecture:
    1. 2D Depthwise Separable CNN extracts spatial features frame-by-frame.
    2. Bidirectional GRU models temporal dynamics over a sequential window.
    Designed for real-time edge execution with highly constrained memory budgets.
    """
    def __init__(self, num_classes: int = 1, spatial_embed_dim: int = 256, temporal_hidden_dim: int = 128):
        super().__init__()
        
        # Spatial Encoder: Reducer pipeline from (3, 112, 112) -> (spatial_embed_dim, 1, 1)
        self.spatial_encoder = nn.Sequential(
            DepthwiseSeparableConv2d(3, 32, stride=2),   # Output: (32, 56, 56)
            DepthwiseSeparableConv2d(32, 64, stride=2),  # Output: (64, 28, 28)
            DepthwiseSeparableConv2d(64, 128, stride=2), # Output: (128, 14, 14)
            DepthwiseSeparableConv2d(128, spatial_embed_dim, stride=2), # Output: (spatial_embed_dim, 7, 7)
            nn.AdaptiveAvgPool2d((1, 1))                # Output: (spatial_embed_dim, 1, 1)
        )
        
        # Temporal Aggregator: Bidirectional GRU
        # Bi-directional models past and future sequence context simultaneously
        self.temporal_gru = nn.GRU(
            input_size=spatial_embed_dim,
            hidden_size=temporal_hidden_dim,
            num_layers=2,
            batch_first=True,
            bidirectional=True,
            dropout=0.3
        )
        
        # Classification Head: Map bidirectional hidden states to predictions
        self.classifier = nn.Linear(temporal_hidden_dim * 2, num_classes)

    def forward(self, video_tensor: torch.Tensor) -> torch.Tensor:
        """
        Forward Pass.
        Args:
            video_tensor (Tensor): Input of shape (B, T, C, H, W)
                B = Batch Size
                T = Temporal sequence length (number of frames)
                C = Channels (3 for RGB)
                H, W = Frame dimensions (112, 112)
        Returns:
            logits (Tensor): Predicted anomaly probability trajectory (B, T, num_classes)
        """
        B, T, C, H, W = video_tensor.size()
        
        # Collapse batch and time dimensions to feed frames sequentially through spatial encoder
        flat_frames = video_tensor.view(B * T, C, H, W)
        
        # Extract spatial features: Shape -> (B*T, spatial_embed_dim, 1, 1)
        spatial_features = self.spatial_encoder(flat_frames)
        
        # Reshape to sequence representation: Shape -> (B, T, spatial_embed_dim)
        spatial_seq = spatial_features.view(B, T, -1)
        
        # Pass features through the recurrent temporal model
        # gru_out shape: (B, T, temporal_hidden_dim * 2)
        gru_out, _ = self.temporal_gru(spatial_seq)
        
        # Project representation to anomaly prediction logit for each time step
        # output shape: (B, T, num_classes)
        logits = self.classifier(gru_out)
        
        return logits


if __name__ == "__main__":
    # verification pass
    model = VideoTemporalClassifier(num_classes=1).eval()
    
    # Simulate a streaming video sequence: Batch=2, Time=16 frames, 3 Channels, 112x112 resolution
    dummy_video = torch.randn(2, 16, 3, 112, 112)
    
    with torch.no_grad():
        predictions = model(dummy_video)
    
    print(f"Input Shape:  {dummy_video.shape} (B, T, C, H, W)")
    print(f"Output Shape: {predictions.shape} (B, T, Classes)")
    assert predictions.shape == (2, 16, 1), "Incorrect shape propagation."
    print("Execution verification succeeded!")
```

---

### Step-by-Step Defense of the Design

When defending this design to a senior interviewer, address these four operational axes:

#### 1. Optimization of Spatial Complexity
The design uses custom **Depthwise Separable Convolutions** rather than standard convolutional layers. This reduces the feature extractor's parameter footprint by approximately $85\%$. This ensures the model weights easily fit within the L1/L2 cache of edge devices, avoiding expensive off-chip DRAM memory transfers during inference.

#### 2. Resolving Recurrent Gradients with GRUs
A Bidirectional GRU is used instead of a standard RNN to eliminate the vanishing gradient problem over long sequences (e.g., 32+ frames). This is achieved through the GRU's multiplicative update gates:

$$h_t = (1 - z_t) \odot h_{t-1} + z_t \odot \tilde{h}_t$$

These gates allow the network to dynamically preserve historical information over long horizons, while keeping the parameter footprint significantly lower than a standard LSTM.

#### 3. Efficient Hardware Compilation
Rather than utilizing arbitrary operations, the spatial extractor uses **ReLU6** and **BatchNorm2d** sequences. ReLU6 limits activations to a ceiling of $6.0$, which prevents quantization precision loss during dynamic FP16 or INT8 compilation. This guarantees low-latency execution on edge accelerators like the EdgeTPU or Apple Neural Engine.

#### 4. System Bottleneck and Trade-off Analysis
```
┌───────────────────────────┬───────────────────────────────────┬───────────────────────────────────┐
│ Metric                    │ Bidirectional GRU (Current)       │ 1D Temporal CNN (Alternative)     │
├───────────────────────────┼───────────────────────────────────┼───────────────────────────────────┤
│ Spatial-Temporal Latency  │ O(T) due to sequential dependency │ O(1) parallel execution step      │
├───────────────────────────┼───────────────────────────────────┼───────────────────────────────────┤
│ Parameter Footprint       │ Very low (highly compact)         │ Higher (due to receptive dilated) │
├───────────────────────────┼───────────────────────────────────┼───────────────────────────────────┤
│ Streaming Support         │ Ideal (holds state step-by-step)  │ Poor (requires sliding window)    │
└───────────────────────────┴───────────────────────────────────┴───────────────────────────────────┘
```
If the edge device uses a custom TPU accelerator, the GRU sequential latency can be a bottleneck. In this case, we can substitute the Bi-GRU with a **1D Dilated Temporal Convolutional Network (TCN)**. This swaps sequential temporal operations for parallel 1D convolutional sweeps over the time dimension, maximizing GPU/TPU utilization.