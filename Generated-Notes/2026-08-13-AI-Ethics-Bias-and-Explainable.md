---
title: AI Ethics, Bias, and Explainable AI (XAI)
date: 2026-08-13T04:31:46.160870
---

# AI Ethics, Bias, and Explainable AI (XAI)

---

## 1. 🧱 The Core Concept (Basics Refresh)

### Definitions & Distinctions
*   **AI Ethics**: The normative framework of moral principles, legal mandates, and operational guardrails governing the development, deployment, and lifecycle management of machine learning systems.
*   **Bias (Statistical vs. Societal)**:
    *   *Statistical Bias*: An estimator's expected value differing from the true parameter value ($\mathbb{E}[\hat{\theta}] \neq \theta$). It is an algorithmic error in estimation.
    *   *Societal Bias*: Systematic, unfair discrimination against specific groups defined by protected attributes ($A \in \{0, 1\}$, e.g., race, gender, age) encoded into empirical data distributions $P(X, Y)$.
*   **Explainable AI (XAI)**: The suite of algorithms and methodologies designed to expose the internal mechanics, causal feature dependencies, and decision boundaries of machine learning models to human operators.

---

### Taxonomy of Bias
Bias enters an ML pipeline across five explicit data and modeling stages:

```
[ Real World ] ---> Historical Bias
      |
[ Sampling ]  ---> Sampling / Selection Bias
      |
[ Measurement ]---> Measurement / Proxy Bias
      |
[ Objective ] ---> Algorithmic Amplification
      |
[ Deployment ]---> Aggregation Bias
```

1.  **Historical Bias**: Occurs at the source. The ground truth labels $Y$ faithfully capture historical human bias (e.g., biased historical hiring patterns).
2.  **Sampling / Selection Bias**: $P_{sample}(X) \neq P_{target}(X)$. Non-representative sampling over- or under-indexes specific sub-populations (e.g., facial recognition trained on white male datasets).
3.  **Measurement / Proxy Bias**: Occurs when chosen features $X$ are imperfect proxies for target variable $Y$, where measurement error correlates with protected attribute $A$ (e.g., using "arrest records" as a proxy for "crime rates").
4.  **Algorithmic Amplification**: Optimization algorithms (e.g., empirical risk minimization) maximize global loss reduction, overriding minority class signals to reduce overall loss variance.
5.  **Aggregation Bias**: A single model parameters $\theta$ are optimized for a non-homogeneous population, failing to model distinct, non-overlapping underlying distributions across sub-groups $P(Y|X, A=0) \neq P(Y|X, A=1)$.

---

### Taxonomy of XAI
To evaluate interpretability frameworks, categorize along three axes:

```
                         XAI TAXONOMY
                              │
         ┌────────────────────┴────────────────────┐
       SCOPE                                   DEPENDENCY
   ┌─────┴─────┐                             ┌─────┴─────┐
Global       Local                     Agnostic       Specific
(Overall)   (Instance)                (Black-box)    (Architecture)
                                             │
                                          TIMING
                                     ┌───────┴───────┐
                                 Intrinsic        Post-hoc
                               (By Design)     (After Training)
```

1.  **Scope**:
    *   *Global*: Explains overall model mechanics across the entire domain space $\mathcal{X}$ (e.g., feature attribution variance, global decision trees).
    *   *Local*: Explains a specific prediction $\hat{y}_i = f(x_i)$ for a single input vector $x_i$ (e.g., LIME, SHAP local attributions).
2.  **Dependency**:
    *   *Model-Agnostic*: Treats the model $f(x)$ as a black box; relies purely on input perturbation and output observation (e.g., KernelSHAP, LIME).
    *   *Model-Specific*: Accesses model internals (weights, gradients, computation graphs) (e.g., Integrated Gradients, TreeSHAP, Grad-CAM).
3.  **Timing**:
    *   *Intrinsic*: Interpretable by design; simple functional forms (e.g., low-depth Decision Trees, Generalized Additive Models (GAMs), Linear Regression).
    *   *Post-hoc*: Explanations generated via a secondary process *after* full model optimization (e.g., SHAP, LIME, Integrated Gradients).

---

### The Impossibility Theorem of Fairness (Kleinberg et al., 2016)
Let $Y \in \{0,1\}$ be the binary ground truth, $\hat{Y} \in \{0,1\}$ the binary prediction, and $A \in \{0,1\}$ a protected attribute.

If base prevalence rates differ across groups—meaning $P(Y=1 | A=0) \neq P(Y=1 | A=1)$—it is **mathematically impossible** to simultaneously satisfy all three of the following fairness metrics:

1.  **Demographic Parity**: $\hat{Y} \perp\!\!\!\perp A$
2.  **Equalized Odds**: $\hat{Y} \perp\!\!\!\perp A \mid Y$
3.  **Predictive Rate Parity (Calibration within Groups)**: $Y \perp\!\!\!\perp A \mid \hat{Y}$

**Engineering Implication**: You *cannot* optimize a system to satisfy equal acceptance rates, equal false positive/negative rates, and equal predictive precision concurrently across demographic groups unless the underlying target distributions are identical or the classifier achieves deterministic perfect accuracy ($100\%$ precision/recall).

---

### The Trade-off Trilemma
System design requires balancing three competing forces:

```
                   Accuracy / Performance
                            /\
                           /  \
                          /    \
                         /      \
                        /   *    \
                       /          \
  Interpretability / XAI ────────── Fairness / Parity
```

*   **Accuracy vs. Interpretability**: Highly parameterized non-linear models (e.g., Deep Transformers, Ensembles) yield superior generalization on complex high-dimensional manifolds, but lack closed-form, human-interpretable representations. Intrinsic models offer full transparency at the cost of statistical capacity.
*   **Accuracy vs. Fairness**: Constraining a parameter space $\Theta$ to satisfy parity metrics forces optimization away from the Bayes Optimal Classifier for $P(X,Y)$, yielding higher global risk $\mathbb{R}(f)$.
*   **Interpretability vs. Fairness**: Local black-box surrogate approximations (e.g., LIME) introduce explanation variance, which can mask algorithmic discrimination, creating a false perception of fairness.

---

## 2. ⚙️ Under the Hood (Internal Mechanics & Architecture)

### 1. Mathematical Foundations of Fairness Metrics

Assume binary classification where $S(x) \in [0, 1]$ is the continuous score output, $\hat{Y} = \mathbb{I}(S(x) \ge \tau)$ is the operational prediction at threshold $\tau$, and $A \in \{0, 1\}$ is the protected group attribute.

```
+------------------------------------------------------------------------------------------------+
| Metric                     | Formula                                                           |
+----------------------------+-------------------------------------------------------------------+
| Demographic Parity         | P(\hat{Y}=1 | A=0) = P(\hat{Y}=1 | A=1)                              |
+----------------------------+-------------------------------------------------------------------+
| Equalized Odds             | P(\hat{Y}=1 | A=0, Y=y) = P(\hat{Y}=1 | A=1, Y=y) \quad \forall y \in \{0,1\} |
+----------------------------+-------------------------------------------------------------------+
| Predictive Rate Parity     | P(Y=1 | A=0, \hat{Y}=1) = P(Y=1 | A=1, \hat{Y}=1)                     |
+----------------------------+-------------------------------------------------------------------+
```

#### Demographic Parity (Independence)
$$P(\hat{Y}=1 | A=0) = P(\hat{Y}=1 | A=1)$$
*   **Mechanics**: Evaluates raw output parity regardless of ground truth status $Y$.
*   **Failure Mode**: Ignores underlying true label distribution variances. Disincentivizes predictive accuracy; can reward selecting unqualified individuals in group $A=0$ to balance aggregate rates.

#### Equalized Odds (Separation)
$$P(\hat{Y}=1 | A=0, Y=y) = P(\hat{Y}=1 | A=1, Y=y) \quad \forall y \in \{0,1\}$$
*   **Mechanics**: Requires equal True Positive Rates (TPR) *and* Equal False Positive Rates (FPR) across groups:
    $$\text{TPR}_{A=0} = \text{TPR}_{A=1} \quad \text{and} \quad \text{FPR}_{A=0} = \text{FPR}_{A=1}$$
*   **Equal Opportunity Relaxing**: Relaxes the constraint to force parity *only* on the positive class ($y=1$), enforcing $\text{TPR}_{A=0} = \text{TPR}_{A=1}$.

#### Predictive Rate Parity (Sufficiency)
$$P(Y=1 | A=0, \hat{Y}=1) = P(Y=1 | A=1, \hat{Y}=1)$$
*   **Mechanics**: Enforces equal Positive Predictive Value (PPV / Precision) across groups.
*   **Mathematical Conflict**: If $P(Y=1|A=0) \neq P(Y=1|A=1)$, Equalized Odds ($\text{FPR}_{A=0} = \text{FPR}_{A=1}, \text{TPR}_{A=0} = \text{TPR}_{A=1}$) mathematically guarantees that Predictive Rate Parity fails, derived directly via Bayes' Theorem:
    $$P(Y=1 | \hat{Y}=1, A=a) = \frac{\text{TPR}_a \cdot P(Y=1|A=a)}{\text{TPR}_a \cdot P(Y=1|A=a) + \text{FPR}_a \cdot (1 - P(Y=1|A=a))}$$

---

### 2. XAI Algorithmic Mechanics

#### SHAP (Shapley Additive exPlanations)
Rooted in cooperative game theory, SHAP computes feature attributions by evaluating the marginal contribution of feature $i$ across all possible feature sub-coalitions $S \subseteq M \setminus \{i\}$, where $M$ is the set of all features.

$$\phi_i(x) = \sum_{S \subseteq M \setminus \{i\}} \frac{|S|!(|M| - |S| - 1)!}{|M|!} \left[ f_x(S \cup \{i\}) - f_x(S) \right]$$

Where $f_x(S) = \mathbb{E}[f(x) \mid x_S]$ is the conditional expectation of the model given sub-coalition $S$.

```
Feature Space M = {x1, x2, x3}
Evaluating marginal contribution of x1 to coalition S = {x2}:

f(x1, x2) - f(x2)  --> Weighted by combinatorial coefficient: |S|!(|M|-|S|-1)! / |M|!
```

*   **Properties**: Uniquely satisfies four fundamental axioms:
    1.  *Efficiency*: $\sum_{i=1}^{|M|} \phi_i(x) = f(x) - \mathbb{E}[f(x)]$
    2.  *Symmetry*: If $f(S \cup \{i\}) = f(S \cup \{j\})$ for all $S$, then $\phi_i = \phi_j$.
    3.  *Dummy (Null Player)*: If $f(S \cup \{i\}) = f(S)$ for all $S$, then $\phi_i = 0$.
    4.  *Additivity*: For $f = g + h$, $\phi_i(f) = \phi_i(g) + \phi_i(h)$.

*   **KernelSHAP vs. TreeSHAP**:
    *   *KernelSHAP*: Model-agnostic. Approximates Shapley values via weighted linear regression in a binary feature-mask space. Highly computationally expensive: $\mathcal{O}(2^{|M|})$ theoretical, requiring sampling approximations.
    *   *TreeSHAP*: Model-specific optimization for decision trees. Recovers exact Shapley values by efficiently tracking conditional probabilities down tree paths in time complexity:
        $$\mathcal{O}(TLD^2)$$
        where $T$ is the number of trees, $L$ is maximum leaves, and $D$ is maximum depth.

```
TreeSHAP Traversal Path Mechanics:
Node (Feature x_j)
  ├─> In Coalition S ───> Follow split natively down left/right child
  └─> Not in S       ───> Compute weighted average of BOTH left & right subtrees 
                           based on empirical sample coverage (N_child / N_parent)
```

---

#### LIME (Local Interpretable Model-agnostic Explanations)
LIME trains a local, intrinsically interpretable surrogate model $g \in G$ (e.g., sparse linear regression) by perturbing input vector $x$ in the local neighborhood, observing black-box model predictions $f(z)$, and weighting instances via proximity kernel $\pi_x(z)$.

$$\xi(x) = \arg\min_{g \in G} \mathcal{L}(f, g, \pi_x) + \Omega(g)$$

Where:
*   $\mathcal{L}(f, g, \pi_x) = \sum_{z, z' \in \mathcal{Z}} \pi_x(z) \left( f(z) - g(z') \right)^2$
*   Proximity Kernel: $\pi_x(z) = \exp\left( -\frac{D(x,z)^2}{\sigma^2} \right)$ using distance metric $D$ (e.g., Cosine/Euclidean) in converted binary feature space $z'$.
*   $\Omega(g)$ penalizes complexity (e.g., controlling L1 regularization $K$ top features).

```
          Non-Linear Black-Box Decision Boundary
        ─────────────────────────────────────────
             *    +     +  |  -
               *   +  (x)  |    -   <- Local Linear
             *   +     +   |  -        Surrogate g(x)
        ─────────────────────────────────────────
        (x) Target Instance  (+) Local Perturbations
```

*   **Failure Modes & Instability**:
    1.  *Sampling Variance*: Random draw perturbations cause non-deterministic explanations for identical inputs $x$.
    2.  *Kernel Width ($\sigma$) Sensitivity*: Extremely sensitive to hyperparameter choices; an overly large $\sigma$ violates local linear assumptions, while an overly small $\sigma$ leads to localized over-fitting.
    3.  *Out-of-Distribution (OOD) Artifacts*: Random perturbations generate synthetic points outside the valid data manifold, forcing model evaluation on non-physical inputs.

---

#### Integrated Gradients (IG)
Designed specifically for differentiable neural networks $F: \mathbb{R}^n \to [0, 1]$, IG computes attributions by integrating path gradients from a pre-defined neutral baseline vector $x'$ to input vector $x$.

$$\text{IntegratedGrads}_i(x) = (x_i - x'_i) \times \int_{0}^{1} \frac{\partial F(x' + \alpha(x - x'))}{\partial x_i} d\alpha$$

```
Baseline Vector x' ─────────── Path α ∈ [0,1] ───────────> Input Vector x
(e.g., all black image / zero embedding)
```

*   **Axiomatic Foundations**:
    1.  *Completeness*: Sum of attributions strictly equals network output delta relative to baseline:
        $$\sum_{i=1}^n \text{IntegratedGrads}_i(x) = F(x) - F(x')$$
    2.  *Implementation Invariance*: Attributions for functionally identical models $F_1(x) = F_2(x)$ are guaranteed to be identical regardless of execution graphs.
*   **Riemann Approximation**: Computed empirically via discrete summation over $m$ steps:
    $$\text{IntegratedGrads}_i^{\text{approx}}(x) = (x_i - x'_i) \times \frac{1}{m} \sum_{k=1}^m \frac{\partial F\left(x' + \frac{k}{m}(x - x')\right)}{\partial x_i}$$
*   **Baseline Selection Strategy**:
    *   Image Data: Uniform black ($0$), uniform white ($1$), or Gaussian noise baselines.
    *   NLP / Embeddings: All-zero embeddings, `[PAD]` token vectors, or average text corpus embeddings. Incorrect baselines can introduce non-informative attribution noise.

---

### 3. Bias Mitigation Pipelines

Mitigation techniques must be integrated strategically across the training lifecycle:

```
┌────────────────────────┐      ┌────────────────────────┐      ┌────────────────────────┐
│     PRE-PROCESSING     │      │     IN-PROCESSING      │      │    POST-PROCESSING     │
├────────────────────────┤      ├────────────────────────┤      ├────────────────────────┤
│ • Data Re-weighing     │ ---> │ • Adversarial Debiasing│ ---> │ • Reject Option        │
│ • Disparate Impact     │      │ • Loss Constraints     │      │   Classification       │
│   Remover              │      │   (Lagrangian)         │      │ • Equalized Odds       │
│ • Fair Representations │      │ • Regularization Terms │      │   Threshold Tuning     │
└────────────────────────┘      └────────────────────────┘      └────────────────────────┘
```

#### A. Pre-processing: Data Re-weighing
Adjusts loss weights prior to optimization to neutralize empirical probability imbalances:

$$W(A=a, Y=y) = \frac{P(A=a) \cdot P(Y=y)}{P(A=a \cap Y=y)}$$

Modifies Empirical Risk Minimization objective:

$$\theta^* = \arg\min_{\theta} \sum_{i=1}^N W(A_i, Y_i) \cdot \mathcal{L}\left( f(x_i; \theta), y_i \right)$$

#### B. In-processing: Adversarial Debiasing
Simultaneously optimizes a primary predictor $f_{\theta}$ and an adversarial discriminator $g_{\phi}$. Predictor aims to minimize main task loss while maximizing discriminator loss (preventing baseline attribute prediction).

```
Input X ───> Predictor f_θ ───> Prediction Y_hat ───> Task Loss L_pred(Y, Y_hat)
                                      │
                                      ▼
                               Adversary g_φ ───────> Predicted Attribute A_hat
                                                      (Loss L_adv(A, A_hat))
```

$$\min_{\theta} \max_{\phi} \left[ \mathcal{L}_{\text{pred}}(f_{\theta}(X), Y) - \lambda \mathcal{L}_{\text{adv}}\left( g_{\phi}(f_{\theta}(X)), A \right) \right]$$

#### C. Post-processing: Equalized Odds Threshold Optimization
Keeps parameters $\theta$ frozen. Adjusts decision thresholds $\tau_a$ individually across protected groups $A \in \{0, 1\}$.

$$\hat{Y} = \mathbb{I}(f(x) \ge \tau_A)$$

Solves linear program to find group-specific thresholds $(\tau_0, \tau_1)$ or probabilistic decision boundaries that equalize TPR/FPR vectors without retraining the underlying model architecture.

---

## 3. ⚠️ The Interview Warzone

### Scenario 1: High-Stakes Deployment
> **Interviewer**: "We are deploying an automated loan underwriting and credit scoring model ($N \approx 50\text{M}$ inference calls/day). Regulators demand compliance with the Fair Credit Reporting Act (FCRA) and EU AI Act. Specifically, we must provide real-time explanations ('Adverse Action notices') detailing the top 4 causal factors for rejection, maintain sub-20ms latency SLAs, and prove zero adverse impact against protected demographics. Walk me through the end-to-end architecture and algorithmic trade-offs."

#### 1. System Architecture
To handle $50\text{M}$ calls/day within a $<20\text{ms}$ budget, inline model-agnostic explanations (like KernelSHAP or LIME) are non-viable due to high computational overhead ($\mathcal{O}(\text{samples} \cdot \text{evals})$).

```
                      INFERENCE ENGINE (<20ms SLA)
                     ┌────────────────────────────┐
Input Features X ──> │ GBDT (LightGBM/XGBoost)    │ ──> Score S(X)
                     │ Fast TreeSHAP C++ Runtime  │ ──> Local Feature Attribution ϕ
                     └────────────────────────────┘
                                   │
                                   ▼
                      POST-PROCESSING & AUDIT HOOKS
                     ┌────────────────────────────┐
                     │ 1. Dynamic Group Thresholds│ ──> Final Decision Binary Y_hat
                     │ 2. Adverse Action Generator│ ──> Top-4 Neg Attributions
                     │ 3. Async Kafka Telemetry   │ ──> Storage / Audit Pipeline
                     └────────────────────────────┘
```

*   **Model Selection**: Optimized Gradient Boosted Decision Trees (GBDTs)—such as LightGBM or XGBoost—paired with a compiled C++ TreeSHAP runtime. TreeSHAP execution scales at $\mathcal{O}(TLD^2)$, executing feature attributions in $<2\text{ms}$ per request.
*   **Adverse Action Generation**: Compute local Shapley value matrix $\phi_i(x)$. Filter for negative attributions pushing the score below threshold $\tau_A$. Sort in ascending order:
    $$\text{Top Factors} = \text{TopK}_{k=4}\left( \phi_i(x) \mid \phi_i(x) < 0 \right)$$
    Map feature keys to human-readable templates (e.g., `feature_revolving_utilization_ratio` $\to$ "High credit line usage relative to total limits").

#### 2. Fairness Architecture & Trade-Offs
*   **Proxy Scrubbing**: Dropping $A$ (e.g., zip code, age) explicitly is insufficient due to non-linear combination proxies. Apply Disparate Impact Remover on proxies to ensure marginal distributions match across groups:
    $$\bar{X} = F^{-1}_0(F_A(X))$$
*   **Optimization**: Implement In-Processing constrained optimization via Fairlearn / Exponential Gradient methods. Formulate loss bound:
    $$\min_{\theta} \mathcal{L}(\theta) \quad \text{subject to} \quad |\text{TPR}_{A=0}(\theta) - \text{TPR}_{A=1}(\theta)| \le \epsilon$$
*   **Post-processing Thresholding**: Run group-specific optimal decision thresholding $\tau_{A=0}, \tau_{A=1}$ to satisfy Equalized Odds without total predictive collapse.

#### 3. Trade-offs & Production Risks
*   **Causal vs. Correlation**: Explainability tools like SHAP quantify model feature reliance, not structural real-world causation. Inform regulatory bodies that feature attributions reflect mathematical contributions within the model boundary, not real-world interventions (e.g., lowering credit usage may not instantly raise scores if underlying financial factors persist).
*   **Model Drift & Auditing**: Pipeline exports continuous prediction telemetry asynchronously via Apache Kafka into a persistent store (e.g., Iceberg/Clickhouse). Calculate rolling Population Stability Index (PSI) and Disparate Impact Ratio ($DIR$) continuously:
    $$DIR = \frac{P(\hat{Y}=1 | A=\text{unprivileged})}{P(\hat{Y}=1 | A=\text{privileged})}$$
    Trigger automated alerts if $DIR < 0.80$ (4/5ths Rule threshold).

---

### Scenario 2: Debugging Black-Box LLMs / Multimodal Architectures
> **Interviewer**: "You are leading a multi-modal RAG system powered by an LLM that powers enterprise customer support. In production, users report the system exhibits gender-biased stereotyping when analyzing resumes, and its embedded RAG attribution output hallucinated an explanation referencing nonexistent system documentation. How do you systematically debug, isolate, and remediate both the bias and attribution failure at the model architecture level?"

#### 1. Isolating and Remediating Bias in LLM / Embedding Space
*   **Localization (Mechanistic Interpretability)**:
    Use **Activation Patching** or **Sparse Autoencoders (SAEs)** on the internal residual stream representations to locate localized "bias directions" in early-to-mid attention heads:
    $$v_{\text{gender}} = \mathbb{E}[h(\text{"She is a nurse"})] - \mathbb{E}[h(\text{"He is a nurse"})]$$

```
                    ACTIVATION PATCHING / DEBIASING
                                
  Residual Stream h_l ───> [ SAE Dictionary ] ───> Latent Features
                                                           │
                                                           ▼
  Cleaned Output    <─── Nullspace Projection ◄─── Zero-out Gender Direction
                         (P_null = I - v v^T)       Vector v_gender
```

*   **Intervention**:
    1.  *Representation Layer*: Apply Nullspace Projection ($P_{\text{null}} = I - v_{\text{gender}}v_{\text{gender}}^T$) directly onto hidden residual states $h_l$ at projection layers to isolate task semantics from demographic directions.
    2.  *Preference Alignment*: Fine-tune via **Direct Preference Optimization (DPO)** using debiased dataset pairs $(y_w, y_l)$, where $y_w$ contains non-stereotypical responses and $y_l$ contains biased outputs:
        $$\mathcal{L}_{\text{DPO}}(\theta) = -\mathbb{E}_{(x, y_w, y_l)} \left[ \log \sigma \left( \beta \log \frac{\pi_{\theta}(y_w|x)}{\pi_{\text{ref}}(y_w|x)} - \beta \log \frac{\pi_{\theta}(y_l|x)}{\pi_{\text{ref}}(y_l|x)} \right) \right]$$

#### 2. Debugging Attributions & Hallucinated Explanations
*   **Root Cause Diagnosis**: Integrated Gradients or Attention Map explanations in LLMs suffer from non-faithfulness (attention weights $\neq$ true causal explanations). Hallucinated attributions occur when generation probabilities decouple from the context vector returned by the RAG retriever.
*   **Mechanistic Remediation via Integrated Gradients / Input Saliency**:
    Evaluate true token attributions using Gradient-weighted saliency across retrieved context tokens $C = \{c_1, c_2, \dots, c_k\}$ relative to generated token outputs $y_t$:
    $$\text{Attribution}(c_i) = \sum_{e \in c_i} \left| e \odot \nabla_e P(y_t \mid C, x) \right|$$
*   **Systemic Verification Layer**:
    Implement an inline **Attribution Verification Hook**:
    1. Extract source context spans via **Faithfulness Cross-Encoder** ($f_{\text{cross}}(C, \text{Response})$).
    2. Compute **RAG Triad Metrics**: Context Relevance, Groundedness (Grounded in context $C$), and Answer Relevance.
    3. If Groundedness score $< \tau_{\text{groundedness}}$, truncate generation and fall back to strict context-constrained responses, bypassing the raw model generation output.

```
                  ATTRIBUTION VERIFICATION HOOK
                                
  Retrieved Context C ──┐
                        ├──> Generation Engine ──> Output Y
  Prompt X ─────────────┘                              │
                                                       ▼
                                         Faithfulness Cross-Encoder
                                         • Compute Context Saliency
                                         • Check Groundedness Metric
                                                       │
                                  ┌────────────────────┴────────────────────┐
                          Groundedness ≥ τ                         Groundedness < τ
                                  │                                         │
                                  ▼                                         ▼
                            Return Output                         Fallback: Enforce Strict
                                                                  Context-Constrained Template
```

---

### Staff-Level Trade-Off Summary Matrix

```
+--------------------------+-----------------------+-----------------------+---------------------------------+
| Strategy                 | Primary Benefit       | Production Bottleneck | Architectural Trade-off          |
+--------------------------+-----------------------+-----------------------+---------------------------------+
| TreeSHAP (XAI)           | Exact, fast local     | Memory footprint for  | Constrains model architecture   |
|                          | attributions          | deep ensemble trees   | strictly to tree structures.     |
+--------------------------+-----------------------+-----------------------+---------------------------------+
| Integrated Gradients     | Axiomatic guarantees, | Compute overhead;     | Sensitive to choice of          |
|                          | continuous spaces     | m steps per forward   | zero-reference baseline vector. |
|                          |                       | pass gradient loop    |                                 |
+--------------------------+-----------------------+-----------------------+---------------------------------+
| Adversarial Debiasing    | In-processing joint   | Minimax training      | Potential performance degradation|
|                          | optimization          | instability/collapse  | on primary prediction accuracy. |
+--------------------------+-----------------------+-----------------------+---------------------------------+
| Equalized Odds Tuning    | Post-hoc non-invasive | May require random-   | Requires explicit runtime access|
|                          | metric alignment      | ized decision boundaries| to protected demographic tags. |
+--------------------------+-----------------------+-----------------------+---------------------------------+
| Direct Preference        | Direct policy-level   | Alignment tax; risk of| Requires curated pairwise       |
| Optimization (DPO)       | debiasing for LLMs    | reward hacking        | preference data manifolds.       |
+--------------------------+-----------------------+-----------------------+---------------------------------+
```