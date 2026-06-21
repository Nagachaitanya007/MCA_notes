---
title: Deep Learning: CNNs for Image Recognition & RNNs for Sequence Data
date: 2026-06-21T04:32:09.344334
---

# Deep Learning: CNNs for Image Recognition & RNNs for Sequence Data

---

## 1. 🧱 The Core Concept

### The Curse of Dimensionality & The Failure of MLPs
Fully connected Multi-Layer Perceptrons (MLPs) scale poorly to spatial (images) and temporal (sequence) data. 

Consider an input image of size $224 \times 224 \times 3$ ($150,528$ features). If the first hidden layer has $1,024$ neurons, this single layer requires:

$$\text{Parameters} = (150,528 \times 1,024) + 1,024 \approx 154 \text{ Million Weights}$$

This parameter explosion causes:
1. **Overfitting**: High-capacity models easily memorize training noise.
2. **Computational Infeasibility**: High memory bandwidth and FLOP requirements.
3. **Loss of Topology**: Flattening an image ($2D \to 1D$) discards spatial locality. Treating a temporal sequence as a static $1D$ vector ignores causal order and variable length.

### Inductive Biases: CNNs vs. RNNs
To solve these issues, we inject domain-specific assumptions—**inductive biases**—into the network architectures.

```
       CONVOLUTIONAL (Spatial Bias)              RECURRENT (Temporal Bias)
      
       [Local Receptive Field]                   [Shared Transition Step]
          (x) (x) (x)  ...                        (x_t-1)   (x_t)   (x_t+1)
           \   |   /                                 |        |        |
            (Kernel)                             [h_t-1]-> [ h_t ]-> [h_t+1]
               |                                     |        |        |
            (y_ij)                               (y_t-1)   (y_t)   (y_t+1)
   "Features are local and translation-      "Temporal patterns are stationary and 
    invariant."                               causal."
```

#### 1. Convolutional Neural Networks (CNNs)
* **Translation Invariance**: If an object appears in the top-left of an image, its feature representation should be similar if it appears in the bottom-right. Formally, a function $f$ is translation invariant if $f(g(x)) = f(x)$, where $g$ is a translation operator. (Convolutions themselves are *equivariant*—the feature map shifts with the input—while pooling layers introduce *invariance*).
* **Spatial Locality (Weight Sharing)**: Nearby pixels are highly correlated. We apply small local kernels (e.g., $3 \times 3$) across the entire input. The same kernel weights are reused, dramatically reducing the parameter count.

Mathematical formulation of a $2D$ discrete convolution (cross-correlation) for input channel $C$ and kernel $K$:

$$S(i, j) = (I * K)(i, j) = \sum_{c=1}^{C} \sum_{m=-M}^{M} \sum_{n=-N}^{N} I(c, i+m, j+n) K(c, m, n)$$

#### 2. Recurrent Neural Networks (RNNs)
* **Temporal Invariance (Stationary Dynamics)**: The rules governing transitions from time $t$ to $t+1$ are invariant across the sequence.
* **Sequential Causal Ordering**: Future steps depend on past states. Information is processed sequentially using a hidden state $h_t$ that acts as a continuous lossy memory.

Mathematical formulation of a vanilla RNN hidden state update:

$$h_t = \tanh(W_{hh} h_{t-1} + W_{xh} x_t + b_h)$$

$$y_t = \text{softmax}(W_{hy} h_t + b_y)$$

### Structural Comparison Matrix

| Attribute | MLP | CNN | RNN |
| :--- | :--- | :--- | :--- |
| **Primary Inductive Bias** | None (Fully Connected) | Spatial Locality & Translation Equivariance | Temporal Stationarity & Causal Ordering |
| **Parameter Complexity** | $\mathcal{O}(D_{in} \times D_{out})$ | $\mathcal{O}(K^2 \times C_{in} \times C_{out})$ (Independent of spatial input size $H \times W$) | $\mathcal{O}(d_{in} \times d_{hid} + d_{hid}^2)$ (Independent of sequence length $T$) |
| **Receptive Field** | Global (entire input) | Local (grows linearly/exponentially with depth) | Technically Infinite (bounded in practice by gradient decay) |
| **Parallelizability** | High (Embarrassingly Parallel) | High (Grid operations run in parallel over GPUs) | Low (Sequential dependency step-by-step $t \to t+1$) |
| **Memory Footprint** | Static | Scaled by Spatial Output Resolution ($H \times W \times C$) | Scaled by sequence length $T$ during training (due to BPTT activation caching) |

---

## 2. ⚙️ Under the Hood

### Deep Dive: CNN Mechanics & Architecture

#### Strides, Padding, and Dilation
These hyperparameters control the spatial dimensions and receptive fields of convolutional layers. Let $W_{in}$ be input width, $K$ be kernel size, $P$ be padding, $S$ be stride, and $D$ be dilation rate.

$$\text{Output Width } (W_{out}) = \left\lfloor \frac{W_{in} - K_{eff} + 2P}{S} \right\rfloor + 1$$

Where the effective kernel size with dilation $D$ is:

$$K_{eff} = K + (K - 1)(D - 1)$$

```
  Dilation = 1 (Standard)                  Dilation = 2 (Atrous)
  [x] [x] [x]                              [x] [ ] [x] [ ] [x]
  [x] [x] [x]                              [ ] [ ] [ ] [ ] [ ]
  [x] [x] [x]                              [x] [ ] [x] [ ] [x]
                                           [ ] [ ] [ ] [ ] [ ]
                                           [x] [ ] [x] [ ] [x]
```

* **Dilation** inserts "spaces" into the kernel. This increases the receptive field exponentially without increasing parameter size or computation cost, which is critical for dense prediction tasks like semantic segmentation.

#### Receptive Field (RF) Calculation
The receptive field defines the local spatial region in the input image that influences a specific unit in layer $l$. Tracking this is critical for detecting large objects.
For any layer $l$:

$$R_l = R_{l-1} + (K_l - 1) \cdot j_{l-1}$$

Where the cumulative jump $j_l$ represents the stride step size in the input space:

$$j_l = j_{l-1} \cdot S_l \quad (\text{with } j_0 = 1, R_0 = 1)$$

* **Interview Signal**: If an interviewer asks you to design a network to detect bounding boxes of size $128 \times 128$ pixels, your network depth and strides must guarantee that the final feature map's receptive field $R_l \ge 128$.

#### Vectorized Gradient Flow in Backpropagation
How do gradients flow through a convolutional layer? Let $Y = X * W$. During backpropagation, we receive upstream gradient $\frac{\partial L}{\partial Y}$.

1. **Gradient with respect to weights $W$**:
   $$\frac{\partial L}{\partial W} = X * \frac{\partial L}{\partial Y}$$
   This is a cross-correlation between the input $X$ and the upstream gradients.
2. **Gradient with respect to inputs $X$ (to propagate back)**:
   $$\frac{\partial L}{\partial X} = \frac{\partial L}{\partial Y} *^T W$$
   This is a **transposed convolution** (or fractional-stride convolution) of the upstream gradient with a flipped version of the kernel $W$.

#### Pooling Layer Mechanics
* **Max Pooling**: Selects the maximum value in a window.
  * *Forward*: $y = \max(x_1, x_2, \dots, x_k)$
  * *Backward*: Gradients are routed *only* to the index of the maximum value (using an stored argmax mask). All other paths receive a gradient of $0$.
* **Average Pooling**: Computes the mean of the window.
  * *Forward*: $y = \frac{1}{k} \sum_i x_i$
  * *Backward*: The upstream gradient is scaled by $\frac{1}{k}$ and distributed equally to all input locations in the window.

---

### Deep Dive: RNN Mechanics & The Long-Range Dilemma

#### The Vanishing and Exploding Gradient Problem
To train an RNN, we unroll the computation graph over time $T$ and use **Backpropagation Through Time (BPTT)**.

```
x_1 ---> [ h_1 ] ---> x_2 ---> [ h_2 ] ---> ... ---> x_T ---> [ h_T ] ---> Loss (L)
            ^                     ^                              ^
            |                     |                              |
          h_0                   h_1                            h_T-1
```

The loss $L$ depends on $h_T$, which depends on $h_t$ via chain of dependencies:

$$\frac{\partial L}{\partial h_t} = \frac{\partial L}{\partial h_T} \frac{\partial h_T}{\partial h_t} = \frac{\partial L}{\partial h_T} \prod_{k=t+1}^{T} \frac{\partial h_k}{\partial h_{k-1}}$$

Let $h_k = \tanh(W_{hh} h_{k-1} + W_{xh} x_k + b)$. The Jacobian matrix of the transition step is:

$$\frac{\partial h_k}{\partial h_{k-1}} = \text{diag}(1 - \tanh^2(a_k)) W_{hh}^T$$

Where $a_k = W_{hh} h_{k-1} + W_{xh} x_k + b$. Taking the norm of the product:

$$\left\| \frac{\partial h_T}{\partial h_t} \right\| \le \prod_{k=t+1}^{T} \left\| \text{diag}(1 - \tanh^2(a_k)) \right\| \| W_{hh}^T \|$$

* Since $\tanh'(x) \in (0, 1]$, if the largest eigenvalue (spectral radius) of $W_{hh}$ is less than $1$, the gradient terms decay exponentially to $0$ as $T - t \to \infty$ (**Vanishing Gradient**). The network forgets long-term dependencies.
* If the spectral radius of $W_{hh}$ is greater than $1$, and the activations do not saturate, the gradients grow exponentially (**Exploding Gradient**), leading to numerical instability (`NaN` values).

#### The Solutions: LSTMs and GRUs
Gated architectures introduce a **Constant Error Carousel (CEC)** to keep the gradient flowing without exponential decay.

```
                       LSTM CELL STATE FLOW
                       
                      Constant Error Carousel
             +-----------------------------------------+
             |                                         v
   C_t-1 ----*-------------------+---------------------+---> C_t
             |                   ^                     |
             | (Forget Gate f_t) | (Input Gate i_t)    |
             |                   |                     |
   h_t-1 ----+--------[ Gates (f, i, o, g) ]-----------+---> h_t
             |                                         |
   x_t ------+-----------------------------------------+
```

##### 1. Long Short-Term Memory (LSTM)
The key to the LSTM is the **Cell State ($C_t$)**, which has an additive update path. This prevents gradients from vanishing.

$$\text{Forget Gate: } f_t = \sigma(W_f \cdot [h_{t-1}, x_t] + b_f) \quad \in [0, 1]$$

$$\text{Input Gate: } i_t = \sigma(W_i \cdot [h_{t-1}, x_t] + b_i) \quad \in [0, 1]$$

$$\text{Candidate Cell State: } \tilde{C}_t = \tanh(W_c \cdot [h_{t-1}, x_t] + b_c) \quad \in [-1, 1]$$

$$\text{Cell State Update: } C_t = f_t \odot C_{t-1} + i_t \odot \tilde{C}_t$$

$$\text{Output Gate: } o_t = \sigma(W_o \cdot [h_{t-1}, x_t] + b_o) \quad \in [0, 1]$$

$$\text{Hidden State Update: } h_t = o_t \odot \tanh(C_t) \quad \in [-1, 1]$$

Where $\odot$ represents the element-wise Hadamard product.

* **Why this solves vanishing gradients**:
  $$\frac{\partial C_t}{\partial C_{t-1}} = f_t + \dots \text{ (other terms dependent on gradients of gates)}$$
  If the network learns to keep the forget gate $f_t \approx 1.0$, the gradient $\frac{\partial C_t}{\partial C_{t-1}} \approx 1.0$. This allows error gradients to propagate back indefinitely over time without exponential decay.

##### 2. Gated Recurrent Unit (GRU)
A streamlined, computationally cheaper variant of the LSTM that merges the cell state and hidden state.

$$\text{Update Gate: } z_t = \sigma(W_z \cdot [h_{t-1}, x_t] + b_z)$$

$$\text{Reset Gate: } r_t = \sigma(W_r \cdot [h_{t-1}, x_t] + b_r)$$

$$\text{Candidate Hidden State: } \tilde{h}_t = \tanh(W \cdot [r_t \odot h_{t-1}, x_t] + b_h)$$

$$\text{Hidden State Update: } h_t = (1 - z_t) \odot h_{t-1} + z_t \odot \tilde{h}_t$$

* **GRU vs. LSTM Trade-off**: GRUs have ~33% fewer parameters, making them faster to train and less prone to overfitting on small datasets. However, LSTMs are strictly more expressive because they maintain separate cell and hidden states.

---

## 3. ⚠️ The Interview Warzone

### Scenario 1: Real-Time Edge Video Processing

```
                         EDGE SYSTEM PIPELINE
                         
   [ Camera Buffer ] ---> [ Pre-Processing ] ---> [ Depthwise Separable Conv ]
                                                           |
   [ Target Performance ] <--- [ INT8 Quantization ] <-----+ (FP32 Model)
    • latency <= 33ms
    • size <= 15MB
```

#### The Prompt
> "We are deploying an object-detection model on an edge device (e.g., drone camera). The video feed is $1080p$ at $30$ FPS. The hardware accelerator has strict thermal and memory limits ($15 \text{ MB}$ max model size, memory bandwidth capped, latency budget $\le 33\text{ ms}$ per frame). Your standard ResNet-50-based detector takes $120\text{ ms}$ and is $100\text{ MB}$. How do you redesign this architecture to fit these constraints without losing significant accuracy?"

#### The Probing Pattern
* *How do standard convolutions scale in computational cost?*
* *What is the difference between standard and depthwise-separable convolutions in terms of FLOPs and parameter count?*
* *How does memory access efficiency (arithmetic intensity) affect real-world speed on edge hardware?*

#### The Perfect Response
To fit these constraints, we need to optimize both the model architecture and its memory access patterns. We can do this using four main techniques:

##### 1. Depthwise Separable Convolutions (MobileNet-style)
A standard convolution of input size $H \times W \times C_{in}$ with kernel size $K \times K$ to output $C_{out}$ channels requires:

$$\text{FLOPs}_{\text{std}} = H \times W \times C_{in} \times C_{out} \times K^2$$

$$\text{Parameters}_{\text{std}} = K^2 \times C_{in} \times C_{out}$$

We can split this into a **Depthwise Convolution** (applying one $K \times K$ spatial filter per input channel) followed by a **Pointwise Convolution** (applying a $1 \times 1$ convolution to mix channels):

```
       STANDARD CONVOLUTION                DEPTHWISE SEPARABLE CONVOLUTION
  
    [Cin x H x W]   [Cin x Cout x K x K]    [Cin x H x W]     [Cin x 1 x K x K]
          \               /                       \                /
           \             /                         [Depthwise Conv Step]
            v           v                                   |
            [Cout x H x W]                            [Cin x H x W]   [Cout x Cin x 1 x 1]
                                                            \               /
                                                             [Pointwise Conv Step]
                                                                    |
                                                              [Cout x H x W]
```

$$\text{FLOPs}_{\text{sep}} = \underbrace{H \times W \times C_{in} \times K^2}_{\text{Depthwise}} + \underbrace{H \times W \times C_{in} \times C_{out} \times 1^2}_{\text{Pointwise}}$$

$$\text{Parameters}_{\text{sep}} = K^2 \times C_{in} + C_{in} \times C_{out}$$

The computational and parameter reduction ratio is:

$$\text{Ratio} = \frac{\text{FLOPs}_{\text{sep}}}{\text{FLOPs}_{\text{std}}} = \frac{K^2 \cdot C_{in} + C_{in} \cdot C_{out}}{K^2 \cdot C_{in} \cdot C_{out}} = \frac{1}{C_{out}} + \frac{1}{K^2}$$

For $K=3$, this reduces computations and parameters by roughly **$8$ to $9$ times** with only a minor drop in accuracy (typically $< 1\%$).

##### 2. Linear Bottlenecks & Inverted Residuals (MobileNetV2)
Standard ResNet blocks compress channels first, apply convolutions, and then expand them ($C_{in} \to \text{narrow} \to C_{out}$). 

For edge devices, we invert this process. We expand the channel dimension first using a $1 \times 1$ convolution to project the data into a higher-dimensional space. We then apply a $3 \times 3$ depthwise convolution, and finally project back to a lower-dimensional space using another $1 \times 1$ convolution. 

This works because the activation function (like ReLU) can destroy information in low dimensions, but projecting the data into higher dimensions first preserves more of that signal.

```
                  INVERTED RESIDUAL BLOCK WITH LINEAR BOTTLENECK
                  
       In (Narrow) ---> [ 1x1 Expansion (ReLU6) ] ---> [ 3x3 Depthwise (ReLU6) ]
         |                                                      |
         +------------- (Skip Connection) -------------> [ 1x1 Projection (Linear) ] ---> Out
```

* **Linear Bottleneck**: The final projection layer does *not* use a non-linear activation (like ReLU). Removing the non-linearity at this step prevents it from destroying valuable feature information.

##### 3. Optimize Arithmetic Intensity & Memory Access Cost (MAC)
FLOPs count alone does not determine run-time latency. Memory bandwidth is often the main bottleneck on edge hardware.

$$\text{Arithmetic Intensity} = \frac{\text{FLOPs}}{\text{Memory Access Cost (MAC)}}$$

For a convolution layer:

$$\text{MAC} = \underbrace{H \times W \times (C_{in} + C_{out})}_{\text{Input & Output Tensors}} + \underbrace{K^2 \times C_{in} \times C_{out}}_{\text{Kernel Weights}}$$

* To optimize memory bandwidth on edge chips, we avoid too many small, fragmented operations. This maximizes the reuse of weights in cache memory.

##### 4. Quantization-Aware Training (QAT) to 8-bit Integer (INT8)
Edge hardware accelerators run INT8 math much faster than FP32. Converting model weights and activations to INT8 reduces the model size by **4x** (from 32-bit floats to 8-bit integers) and significantly increases throughput.
* Instead of Post-Training Quantization (PTQ), which can hurt accuracy, we use **Quantization-Aware Training (QAT)**. 
* During the forward pass of training, we simulate quantization rounding errors using fake-quantization nodes. During the backward pass, we use a Straight-Through Estimator (STE) to copy gradients past these rounding operations, allowing the model weights to adapt to the quantization limits.

---

### Scenario 2: Processing Extremely Long Sequences ($T \ge 10,000$)

```
             DILEMMA: SEQUENTIAL STEP VS. PARALLEL RECEPTIVE FIELD
             
   Vanilla RNN / LSTM (O(T) Sequential Step):
   h_0 -> h_1 -> h_2 -> ... -> h_10,000  (Backpropagation must step sequentially)
   
   Dilated Causal 1D CNN (O(1) Parallel Step):
   y_t  [ ]     [ ]     [ ]     [ ]  (Receptive field spans 10,000 steps with O(log T) depth)
         \       /       \       /
   y_t-1   [ ] [ ]         [ ] [ ]
             \ /             \ /
   x_t     [ ][ ][ ][ ][ ][ ][ ][ ]
```

#### The Prompt
> "We are building an anomaly detection system for industrial IoT sensors. The sensors stream continuous data at $100\text{ Hz}$. We need to model dependencies across sequences of length $T \ge 10,000$ steps to identify slow-developing physical failures. Our prototype LSTM model is taking days to train, runs out of GPU memory during backpropagation, and struggles to capture patterns over these long sequences. How do you resolve this?"

#### The Probing Pattern
* *Why do LSTMs struggle to parallelize during training?*
* *How does the GPU memory footprint scale with sequence length during Backpropagation Through Time (BPTT)?*
* *What alternatives exist that provide parallel training while still capturing long-range temporal patterns?*

#### The Perfect Response
This issue highlights the fundamental limitations of standard RNN architectures: **sequential computation bottlenecks** and **$O(T)$ memory scaling**.

##### 1. Why the LSTM is Failing
* **Sequential Training Bottleneck**: An LSTM requires computing hidden state $h_t$ before starting $h_{t+1}$. Because of this sequential dependency, we cannot parallelize the training process across the time dimension on GPUs.
* **$O(T)$ Activation Storage**: During backpropagation, the GPU must store all intermediate cell states $C_t$ and hidden states $h_t$ for all $10,000$ steps to compute the gradients. This causes out-of-memory (OOM) errors.
* **Effective Horizon Limits**: Even with the Constant Error Carousel (CEC), LSTMs struggle to retain memory across more than $500$ to $1,000$ steps due to the continuous blending of information in the state vector.

##### 2. Alternative Architecture: Dilated Causal 1D CNNs (WaveNet-style)
To bypass the sequential training bottleneck, we can replace the RNN with a **Dilated Causal 1D Convolutional Network (TCN)**.

```
                             Dilated Causal Convolution (dilation=4)
                             
   Layer 3 (d=4)  o---------------------------------------o (Output)
                 /                                       /
   Layer 2 (d=2)  o-------------------o                   o
                 /                   /                   /
   Layer 1 (d=1)  o---------o         o---------o         o
                 /         /         /         /         /
   Input          x_t-4     x_t-3     x_t-2     x_t-1     x_t
```

* **Causal**: The prediction at time $t$ only depends on inputs from time $t$ and earlier. This is enforced by padding the input's left side with zeros.
* **Dilated**: By exponentially increasing the dilation rate $D = 2^l$ at each layer $l$, the network's receptive field grows exponentially with depth:

$$\text{Receptive Field} = 1 + \sum_{l=0}^{L-1} (K_l - 1) \cdot D_l$$

For a kernel size $K = 3$ and $L = 12$ layers with dilation doubling at each layer ($1, 2, 4, \dots, 2048$), we get:

$$\text{Receptive Field} = 1 + 2 \times (1 + 2 + 4 + \dots + 2048) = 1 + 2 \times (4095) = 8191 \text{ steps}$$

* **Why this is better**:
  * **Parallel Training**: During training, we have access to the entire ground-truth sequence. Because convolutions do not rely on a sequential state loop, we can process all $10,000$ time steps in parallel. This significantly speeds up GPU training.
  * **No Vanishing Gradients**: Gradients propagate back through a fixed, shallow tree of convolutional layers ($\mathcal{O}(\log T)$ depth) rather than a sequential chain of $10,000$ steps ($\mathcal{O}(T)$ depth).

##### 3. Scalable Training Tactics for RNNs (If we *must* use LSTMs)
If business logic or streaming inference constraints require us to use an LSTM, we can use these optimization techniques:

* **Truncated BPTT (TBPTT)**:
  Instead of backpropagating across all $10,000$ steps, we split the input sequence into smaller sub-sequences of length $k_1$ (e.g., $100$ steps). We run the forward pass through the entire sequence, but only run backpropagation across $k_2$ steps (where $k_2 \le k_1$). This caps the GPU memory footprint at $O(k_2)$ instead of $O(T)$.

```
   [---- Forward Pass (t=0 to 10,000) ---->]
   [-- BPTT Block 1 --]  [-- BPTT Block 2 --]  [-- BPTT Block 3 --]
     (Backprop 100)        (Backprop 100)        (Backprop 100)
```

* **Activation Checkpointing (Gradient Checkpointing)**:
  Instead of caching all $10,000$ hidden states during the forward pass, we only save a subset of states (e.g., every $100$th state, which we call "checkpoints"). During the backward pass, we recompute the missing intermediate states on the fly from the nearest checkpoint. This reduces the memory footprint from $O(T)$ to $O(\sqrt{T})$ at the cost of an extra forward pass computation (roughly 33% overhead).

---

### High-Signal Code Implementation: Custom LSTM-Step & Spatial-Attention Block

Here is a clean PyTorch implementation of a custom **LSTM Cell Step** alongside a **Spatial Attention Block** to demonstrate deep mathematical and architectural understanding.

```python
import torch
import torch.nn as nn
import torch.nn.functional as F

class CustomLSTMCell(nn.Module):
    def __init__(self, input_size: int, hidden_size: int):
        super(CustomLSTMCell, self).__init__()
        self.input_size = input_size
        self.hidden_size = hidden_size
        
        # We combine all four gate projections into a single weight matrix
        # for maximum hardware utilization on the GPU.
        # Gates: Forget (f), Input (i), Candidate Cell (g), Output (o)
        self.weight_ih = nn.Parameter(torch.randn(4 * hidden_size, input_size))
        self.weight_hh = nn.Parameter(torch.randn(4 * hidden_size, hidden_size))
        self.bias_ih = nn.Parameter(torch.zeros(4 * hidden_size))
        self.bias_hh = nn.Parameter(torch.zeros(4 * hidden_size))
        
        self.reset_parameters()

    def reset_parameters(self):
        # Xavier initialization is used to prevent early gradient explosion/vanishing
        nn.init.xavier_uniform_(self.weight_ih)
        nn.init.xavier_uniform_(self.weight_hh)
        nn.init.zeros_(self.bias_ih)
        nn.init.zeros_(self.bias_hh)

    def forward(self, x: torch.Tensor, init_states: tuple[torch.Tensor, torch.Tensor]) -> tuple[torch.Tensor, torch.Tensor]:
        """
        Args:
            x: Input tensor of shape (batch_size, input_size)
            init_states: Tuple of (h_prev, c_prev), each of shape (batch_size, hidden_size)
        Returns:
            h_next, c_next: Updated states, shape (batch_size, hidden_size)
        """
        h_prev, c_prev = init_states
        
        # Linear projection step
        gates = (F.linear(x, self.weight_ih, self.bias_ih) + 
                 F.linear(h_prev, self.weight_hh, self.bias_hh))
        
        # Split the combined projection into individual gates
        f_gate, i_gate, g_gate, o_gate = torch.chunk(gates, 4, dim=-1)
        
        # Apply gate activations
        f = torch.sigmoid(f_gate)
        i = torch.sigmoid(i_gate)
        g = torch.tanh(g_gate)  # Candidate cell state
        o = torch.sigmoid(o_gate)
        
        # Additive cell state update
        c_next = (f * c_prev) + (i * g)
        
        # Hidden state projection
        h_next = o * torch.tanh(c_next)
        
        return h_next, c_next


class SpatialAttentionCNN(nn.Module):
    """
    A Spatial Attention Block that can be inserted into CNNs (e.g., ResNet)
    to focus on salient regions of an image.
    """
    def __init__(self, kernel_size: int = 7):
        super(SpatialAttentionCNN, self).__init__()
        assert kernel_size in [3, 7], "Kernel size must be 3 or 7"
        padding = 3 if kernel_size == 7 else 1
        
        # We compress channels using channel-wise MaxPool and AvgPool, 
        # then apply a standard 2D convolution to learn the spatial attention map.
        self.conv = nn.Conv2d(2, 1, kernel_size=kernel_size, padding=padding, bias=False)
        self.sigmoid = nn.Sigmoid()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Args:
            x: Input feature map of shape (batch_size, channels, height, width)
        Returns:
            Spatially-attended feature map of same shape.
        """
        # Compress channels: Max pool and Average pool along the channel dimension (dim=1)
        max_out, _ = torch.max(x, dim=1, keepdim=True)
        avg_out = torch.mean(x, dim=1, keepdim=True)
        
        # Concatenate pool outputs to create a 2-channel spatial descriptor map
        spatial_features = torch.cat([max_out, avg_out], dim=1)
        
        # Generate spatial attention weights (values normalized between 0 and 1)
        attention_weights = self.sigmoid(self.conv(spatial_features))
        
        # Scale the original feature map by the learned attention weights
        return x * attention_weights


# Verification script to test shape matching
if __name__ == "__main__":
    # Test Custom LSTM Cell
    batch_size, input_dim, hidden_dim = 32, 64, 128
    lstm_cell = CustomLSTMCell(input_dim, hidden_dim)
    
    dummy_x = torch.randn(batch_size, input_dim)
    h0 = torch.zeros(batch_size, hidden_dim)
    c0 = torch.zeros(batch_size, hidden_dim)
    
    h1, c1 = lstm_cell(dummy_x, (h0, c0))
    print(f"LSTM Output Shapes -> h1: {h1.shape}, c1: {c1.shape}")
    assert h1.shape == (batch_size, hidden_dim)
    
    # Test Spatial Attention Block
    attention_block = SpatialAttentionCNN(kernel_size=7)
    dummy_fm = torch.randn(4, 64, 32, 32)  # B, C, H, W
    attended_fm = attention_block(dummy_fm)
    print(f"Spatial Attention Output Shape -> {attended_fm.shape}")
    assert attended_fm.shape == dummy_fm.shape
```