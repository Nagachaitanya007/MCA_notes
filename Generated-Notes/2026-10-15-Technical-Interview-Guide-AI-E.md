---
title: Technical Interview Guide: AI Ethics, Bias, and Explainable AI (XAI)
date: 2026-10-15T04:32:53.960945
---

# Technical Interview Guide: AI Ethics, Bias, and Explainable AI (XAI)

---

## 1. 🧱 The Core Concept

In production machine learning systems, ethics, fairness, and explainability are not philosophical goals; they are **hard engineering constraints** governed by mathematical bounds, optimization trade-offs, and regulatory requirements (e.g., EU AI Act, GDPR Article 22, US Equal Credit Opportunity Act).

### The Fairness Triad: The Impossibility Theorem

A binary classifier produces an output $\hat{Y} \in \{0, 1\}$ for an individual with features $X$, belonging to a protected group $A \in \{0, 1\}$, with ground-truth label $Y \in \{0, 1\}$.

```
              ┌────────────────────────────────────────────────────────┐
              │           The Fairness Impossibility Theorem           │
              │  You can simultaneously satisfy at most TWO of these   │
              │         (assuming base rates differ: P(Y=1|A=0) ≠ P(Y=1|A=1))       │
              └──────────────────────────┬─────────────────────────────┘
                                         │
         ┌───────────────────────────────┼───────────────────────────────┐
         ▼                               ▼                               ▼
┌──────────────────┐           ┌──────────────────┐           ┌──────────────────┐
│ Demographic      │           │ Equalized        │           │ Predictive       │
│ Parity           │           │ Odds             │           │ Parity           │
│ P(Ŷ=1|A=0) =     │           │ P(Ŷ=1|A=0, Y=y) =│           │ P(Y=1|A=0, Ŷ=1) =│
│ P(Ŷ=1|A=1)       │           │ P(Ŷ=1|A=1, Y=y)  │           │ P(Y=1|A=1, Ŷ=1)  │
└──────────────────┘           └──────────────────┘           └──────────────────┘
```

#### 1. Demographic Parity (Statistical Parity)
The acceptance rate is independent of the protected attribute:

$$P(\hat{Y}=1 \mid A=0) = P(\hat{Y}=1 \mid A=1)$$

* **Disparate Impact (DI) Ratio:**
  
  $$\text{DI} = \frac{P(\hat{Y}=1 \mid A=0)}{P(\hat{Y}=1 \mid A=1)}$$
  
  (The legal standard in US employment law is the 4/5ths rule: $\text{DI} \ge 0.8$).
* **Failure Mode:** Ignores true qualification distributions. If $P(Y=1 \mid A=0) \neq P(Y=1 \mid A=1)$, achieving demographic parity forces the model to select lower-confidence candidates from one group, maximizing false positives and degrading performance.

#### 2. Equalized Odds (Separation)
Predictions are conditionally independent of the protected attribute given the true label:

$$P(\hat{Y}=1 \mid A=0, Y=y) = P(\hat{Y}=1 \mid A=1, Y=y) \quad \forall y \in \{0, 1\}$$

* Enforces parity across both **True Positive Rates (TPR)** and **False Positive Rates (FPR)**.
* **Equal Opportunity:** A relaxed variant that constrains only the positive class ($y=1$):

  $$P(\hat{Y}=1 \mid A=0, Y=1) = P(\hat{Y}=1 \mid A=1, Y=1)$$

#### 3. Predictive Parity (Sufficiency / Calibration within Groups)
The true outcome is conditionally independent of the protected attribute given the prediction:

$$P(Y=1 \mid A=0, \hat{Y}=1) = P(Y=1 \mid A=1, \hat{Y}=1)$$

* Guarantees that a score of $s = 0.85$ translates to the exact same probability of default/churn/click, regardless of protected class membership.

#### The Mathematical Conflict (Chouldechova / Kleinberg Theorem)
If base rates differ across groups ($P(Y=1 \mid A=0) \neq P(Y=1 \mid A=1)$), and the classifier is imperfect, **Equalized Odds and Predictive Parity are mutually exclusive**. 

$$\text{FPR} = \frac{p}{1-p} \cdot \frac{1 - \text{PPV}}{\text{PPV}} \cdot \text{TPR}$$

Where $p = P(Y=1)$ is the base rate, and $\text{PPV}$ is the Positive Predictive Value. If $\text{PPV}$ (Predictive Parity) and $\text{TPR}$/$\text{FPR}$ (Equalized Odds) are held equal across groups, $p$ must be identical across both groups. If $p$ differs, you must choose which axiom to violate.

---

### Explainability Taxonomy

```
Explainability Approaches
├── Intrinsic (Interpretable by Design)
│   ├── Linear/Logistic Regression (coefficients, odds ratios)
│   ├── Generalized Additive Models (GAMs / EBMs: f(x) = ∑ f_i(x_i) + ∑ f_ij(x_i, x_j))
│   └── Shallow Decision Trees
└── Post-Hoc (Attribution on Black-Box Models)
    ├── Local (Instance-level explanation)
    │   ├── Perturbation-based: LIME, KernelSHAP
    │   ├── Gradient-based: Integrated Gradients, Grad-CAM
    │   └── Contrastive: Counterfactual Explanations
    └── Global (Model-level behavior)
        ├── TreeSHAP (mean |SHAP| values)
        ├── Partial Dependence Plots (PDP)
        └── Permutation Feature Importance (PFI)
```

---

## 2. ⚙️ Under the Hood

### Explainability Mathematics

#### 1. SHAP (SHapley Additive exPlanations)
Rooted in cooperative game theory. Let $N$ be the set of all features ($|N| = M$), and $S \subseteq N \setminus \{i\}$ be a subset of features excluding feature $i$. The unique attribution $\phi_i$ satisfying the four fundamental axioms is:

$$\phi_i(v) = \sum_{S \subseteq N \setminus \{i\}} \frac{|S|!(M - |S| - 1)!}{M!} \Big[ v(S \cup \{i\}) - v(S) \Big]$$

Where the characteristic function $v(S) = \mathbb{E}_{X_{\bar{S}}}[f(x_S, X_{\bar{S}})]$ marginalizes out features not in $S$.

##### The Four Axioms
1. **Efficiency:** $\sum_{i=1}^M \phi_i(f, x) = f(x) - \mathbb{E}[f(X)]$ (Attributions sum to the difference between model output and base value).
2. **Symmetry:** If $v(S \cup \{i\}) = v(S \cup \{j\})$ for all $S$, then $\phi_i = \phi_j$.
3. **Dummy (Null Player):** If $v(S \cup \{i\}) = v(S)$ for all $S$, then $\phi_i = 0$.
4. **Additivity:** For independent models $f$ and $g$, $\phi_i(f + g) = \phi_i(f) + \phi_i(g)$.

##### TreeSHAP vs. KernelSHAP

* **KernelSHAP:** Model-agnostic. Solves a weighted linear regression over perturbations of the input.
  * Complexity: $\mathcal{O}(2^M)$ without sampling; typically sampled with $K$ samples: $\mathcal{O}(K \cdot T_{\text{inference}})$.
  * Bottleneck: Ignores feature correlation when sampling from marginals $P(X_{\bar{S}})$, evaluating impossible feature combinations (e.g., `Age = 5` and `Years of Experience = 20`).
* **TreeSHAP:** Optimizes $v(S) = \mathbb{E}[f(x) \mid x_S]$ by pushing perturbations down decision paths simultaneously.
  * Complexity: Reduced from exponential to polynomial: $\mathcal{O}(T \cdot L \cdot D^2)$, where $T$ = number of trees, $L$ = maximum leaves, and $D$ = maximum tree depth.
  * Path-dependent TreeSHAP calculates the conditional expectation $\mathbb{E}[f(x) \mid x_S]$ directly from empirical coverage in the tree splits, preventing evaluations in non-support regions of the data manifold.

```
TreeSHAP Traversal Optimization:
Node: Split on Feature 1
├── Feature 1 ∈ S: Deterministically take split direction of instance x.
└── Feature 1 ∉ S: Recurse BOTH left and right branches;
                   weight contributions by fraction of background samples 
                   flowing down each path.
```

#### 2. LIME (Local Interpretable Model-agnostic Explanations)
Constructs an interpretable surrogate model $g \in G$ (e.g., ridge regression) within the local neighborhood of the query point $x$:

$$\xi(x) = \arg\min_{g \in G} \mathcal{L}(f, g, \pi_x) + \Omega(g)$$

Where $\pi_x(z) = \exp(-D(x, z)^2 / \sigma^2)$ is an exponential kernel measuring distance $D$ using an arbitrary metric (e.g., Euclidean, cosine), $\mathcal{L}$ is the squared loss of $g(z)$ against $f(z)$, and $\Omega(g)$ is the model complexity (e.g., $L_1$ penalty on weights).

* **Pathologies:** 
  1. Highly sensitive to kernel bandwidth $\sigma$: Pick it too small, and you overfit local noise; pick it too large, and you violate the local linearity assumption.
  2. Non-deterministic due to random neighborhood sampling, producing inconsistent explanations across calls for the exact same sample.

#### 3. Integrated Gradients (Axiomatic Attribution for Neural Networks)
Standard gradient attribution ($\nabla_x f(x)$) suffers from the **gradient saturation problem** (e.g., a ReLU neuron saturated at maximum activation has a local gradient of 0, yielding an attribution of 0 despite the feature driving the prediction).

Integrated Gradients resolves this by integrating gradients along a straight line path from a neutral baseline $x'$ to input $x$:

$$\text{IG}_i(x) = (x_i - x'_i) \times \int_{0}^{1} \frac{\partial f(x' + \alpha(x - x'))}{\partial x_i} d\alpha$$

##### Axiomatic Guarantees
* **Completeness:** $\sum_i \text{IG}_i(x) = f(x) - f(x')$.
* **Implementation Invariance:** Two functionally identical networks yield the exact same attribution, irrespective of architecture (unlike basic backprop saliency).
* **Numerical Approximation:** Computed via Riemann summation over $m$ interpolation steps:

$$\text{IG}_i^{\text{approx}}(x) = (x_i - x'_i) \times \frac{1}{m} \sum_{k=1}^m \frac{\partial f\left(x' + \frac{k}{m}(x - x')\right)}{\partial x_i}$$

* **Production Pitfall:** Path-dependence and baseline selection. If explaining an image, selecting a black image baseline ($x'=0$) causes attribution to vanish for dark pixels because $(x_i - x'_i) \to 0$, regardless of their semantic importance.

---

### Algorithmic Bias Mitigation: Architecture & Interventions

```
ML PIPELINE BIAS MITIGATION POINTS
─────────────────────────────────────────────────────────────────────────
Raw Data ──► [Pre-Processing] ──► Training ──► [In-Processing] ──► Post-Processing ──► Output
                   │                                  │                   │
                   ▼                                  ▼                   ▼
           • Reweighing                      • Adversarial Debiasing • Reject Option
           • Disparate Impact Remover        • Fair Constraints/Lagr.  Classification
           • Optimized Preprocessing         • Minimax Optimization  • Group-Specific
                                                                       Thresholding
```

#### 1. Pre-Processing: Disparate Impact Remover
Edits feature values directly to balance marginal distributions across protected classes while preserving rank order within groups.
* Computes the cumulative distribution function (CDF) $F_A(x) = P(X \le x \mid A=a)$ for each group $A \in \{0, 1\}$.
* Maps features to a shared median distribution $F_{\text{target}}^{-1}$:

  $$\tilde{x} = F_{\text{target}}^{-1}(F_A(x))$$

* Eliminates indirect proxy leakage before features reach the model.

#### 2. In-Processing: Adversarial Debiasing (Minimax Game)
Jointly optimizes primary task loss while minimizing an adversary’s ability to predict the protected attribute from internal network representations:

$$\min_{\theta_P} \max_{\theta_A} \mathcal{L}_P(f(X; \theta_P), Y) - \lambda \mathcal{L}_A(g(Z; \theta_A), A)$$

Where $Z$ is the final hidden representation or the logit output, $\theta_P$ are the predictor parameters, $\theta_A$ are the adversary parameters, and $\lambda$ is a hyperparameter balancing accuracy against demographic invariance.

```
       ┌───────────┐      Logits (Z)      ┌──────────────┐
X ────►│ Predictor ├─────────────────────►│ Task Loss L_P├──► Update θ_P
       │  (θ_P)    │       │              └──────────────┘
       └───────────┘       │
                           ▼
                   ┌───────────────┐      ┌──────────────┐
                   │   Adversary   ├─────►│  Adv Loss L_A├──► Update θ_A
                   │     (θ_A)     │      └──────┬───────┘
                   └───────────────┘             │
                           ▲                     │
                           └─────────────────────┘
                             Gradient Reversal Layer (-λ)
```

#### 3. Post-Processing: Equalized Odds Threshold Optimizer
Accepts a frozen, pre-trained score function $R = f(X) \in [0, 1]$ and solves for group-specific decision thresholds $t_0, t_1$:

$$\hat{Y} = \mathbb{I}(R > t_A) \quad \text{where } A \in \{0, 1\}$$

By casting the problem as a linear program operating on the ROC convex hull of each group, it selects thresholds $(t_0, t_1)$ that equalize TPR and FPR across groups while maximizing total utility:

$$\begin{aligned}
\max_{t_0, t_1} \quad & \sum_{a \in \{0, 1\}} P(A=a) \cdot \text{Utility}(t_a) \\
\text{subject to} \quad & \text{TPR}_{A=0}(t_0) = \text{TPR}_{A=1}(t_1) \\
& \text{FPR}_{A=0}(t_0) = \text{FPR}_{A=1}(t_1)
\end{aligned}$$

---

### Low-Latency Production XAI Architecture

Generating Shapley attributions in an online inference path ($P99 < 20\text{ ms}$) is computationally prohibitive using standard KernelSHAP/Sampling methods.

```
ONLINE PATH (< 15ms)
┌──────────────┐      ┌───────────────┐      ┌─────────────────────────┐
│ Client Query ├─────►│ Inference API ├─────►│ Model (Triton / Torch)  │
└──────────────┘      └──────┬────────┘      └────────────┬────────────┘
                             │                            │ Prediction
                             │ Async Event                ▼
                             │ (ID, Features, Output) ┌────────────────┐
                             └───────────────────────►│  Kafka Stream  │
                                                      └────────┬───────┘
                                                               │
OFFLINE / ASYNC WORKER POOL                                    ▼
┌────────────────────────┐      ┌─────────────┐       ┌────────────────┐
│ DynamoDB / Redis Cache │◄─────┤ Worker Pool │◄──────┤ Consumer Group │
│ (Stores Precomputed    │      │ (TreeSHAP / │       └────────────────┘
│  Attributions)         │      │  FastSHAP)  │
└────────────────────────┘      └─────────────┘
```

#### Production Patterns
1. **FastSHAP (Amortized Explanations):** Train an explicit explainer neural network $g_\phi(x)$ parameterized by weights $\phi$ that directly outputs Shapley values for an arbitrary input with a single forward pass:

   $$\mathcal{L}(\phi) = \mathbb{E}_{x, S} \left[ \left( f(x) - \sum_{i \in S} g_{\phi, i}(x) \right)^2 \right]$$

   Inference cost: Drops from $\mathcal{O}(M \cdot K \cdot T_{\text{inference}})$ to a single forward pass $\mathcal{O}(1)$.

2. **Decoupled Asynchronous Explainability:**
   * Return the model prediction synchronously to respect client SLAs.
   * Emit an event `(Inference_ID, Features, Prediction)` to an Apache Kafka or AWS Kinesis topic.
   * Background workers execute TreeSHAP / Integrated Gradients asynchronously, persisting attributions into a low-latency key-value store (e.g., DynamoDB/Aerospike).
   * User-facing audit dashboards poll explanations asynchronously via `Inference_ID`.

3. **Background Baseline Caching for Integrated Gradients:**
   Precompute and cache path baselines ($x'$), storing them in shared memory (`shm` on Linux / IPC) to avoid re-generating baseline matrices per forward-backward pass.

---

## 3. ⚠️ The Interview Warzone

### Scenario 1: The Credit Decisioning Metric Clash
> **Interviewer:** "You are building a loan-default risk engine. The business requires the model to be well-calibrated so that credit risk translates directly to capital reserve requirements ($P(Y=1 \mid \hat{Y}=s) = s$). However, an internal compliance audit finds that the model's approval rate for a historically marginalized group is only 40%, compared to 75% for the majority group (Disparate Impact ratio = 0.53). The business demands an immediate increase of the acceptance rate to satisfy the 4/5ths rule ($DI \ge 0.8$) without recalibrating the model, because recalibration alters the expected loss calculation. How do you resolve this?"

#### Probing Strategy
* Can the candidate recognize the mathematical impossibility of satisfying both metrics when underlying base rates differ?
* Do they blindly suggest stripping protected attributes, ignoring proxy variables?
* Can they navigate business, legal, and engineering requirements concurrently?

#### The Ideal Response
1. **Establish the Mathematical Impasse:** 
   * "Under the Impossibility Theorem of Fairness, if the underlying default base rates differ between groups ($P(Y=1 \mid A=0) \neq P(Y=1 \mid A=1)$), it is mathematically impossible to simultaneously achieve Demographic Parity ($\text{DI} \ge 0.8$) and maintain Calibration across groups (Predictive Parity). If we force Demographic Parity via post-processing thresholds, the score will no longer represent the true probability of default for both groups. One group will have a higher actual default rate for the same predicted score, invalidating the downstream capital reserve calculations."
2. **Deconstruct the "Drop the Protected Attribute" Fallacy:**
   * "Simply dropping the protected attribute $A$ (Fairness through Unawareness) does not work. High-dimensional non-protected features (e.g., zip code, income variance, school district) act as proxies. The model will reconstruct the protected attribute via proxy features, maintaining disparate impact."
3. **Execute an Optimal Technical Path:**
   * **Separation of Concerns:** Keep the base core model calibrated to the true risk distribution using all uncorrupted features. Do not artificially distort the calibration curve globally.
   * **Constrained Optimization / Pareto Frontier Exploration:** Implement constrained optimization using a Lagrangian formulation:

     $$\min_\theta \mathcal{L}_{\text{Brier}}(\theta) \quad \text{s.t.} \quad \left| \frac{P(f_\theta(X)=1 \mid A=0)}{P(f_\theta(X)=1 \mid A=1)} - 0.8 \right| \le \epsilon$$

   * **Subsidized Threshold Optimization (Alternative):** If calibration must remain pure for risk modeling, recommend decoupling the score from the decision policy. Lower the decision threshold $t_0$ for the underserved group to satisfy the 80% rule, and price the associated excess default risk explicitly as a regulatory compliance cost or balance-sheet subsidy, rather than pretending the risk profiles are identical.

---

### Scenario 2: Real-time Ad Auction Explainability
> **Interviewer:** "We operate an ad ranking engine. A downstream compliance regulation dictates that we must provide localized explanations (the top 3 features that influenced the win/loss outcome) for ad impressions within 15 milliseconds at $100\text{k}$ QPS. Our primary ranker is a 50-tree Gradient Boosted Decision Tree (GBDT) coupled with a deep retrieval network. How do you architect this?"

#### Probing Strategy
* Does the candidate attempt to run standard TreeSHAP or LIME on the fly? (Instant failure: computational complexity will blow past the 15ms budget at $100\text{k}$ QPS).
* Can they differentiate between the retrieval stage and the ranking stage?
* Do they know how to scale or approximate feature attributions under ultra-low latency constraints?

#### The Ideal Response
1. **Eliminate Non-Viable Approaches:**
   * "Running LIME or standard KernelSHAP on the live inference path is non-viable. Sampling hundreds of perturbations per request at 100k QPS would require millions of forward passes per second, easily violating the 15ms P99 SLA. Even an optimized C++ implementation of TreeSHAP on a 50-tree GBDT requires traversing multiple trees per query, which will consume our compute budget at scale."
2. **Deconstruct the Architecture:**
   * The ad pipeline has two stages: Candidate Retrieval (Bi-encoder / ANN) and Ranking (GBDT / Cross-Network). The legal mandate applies to the final selection: the **Ranking stage**.
3. **Engineered Solutions:**
   * **Option A: Pre-computed Top Feature Combinations / Caching:** For categorical/binned feature spaces, precompute SHAP values for dominant feature bins and store them in an in-memory hash table (e.g., Redis cluster or local memory mapped files).
   * **Option B: Amortized Explanation Model (FastSHAP):** Train an explicit student explainer network running concurrently or embedded within the model scoring graph (TensorRT / ONNX Runtime engine). The explainer takes the feature vector and outputs the top-3 feature indices via an argmax over the predicted attribution vector in a single matrix multiplication step ($< 1\text{ ms}$).
   * **Option C: Asynchronous Decoupling (The Production Standard):** If the regulation allows the explanation to be delivered to an audit log rather than the real-time bid response payload:
     * Emit the inference context (features, weights, tree activation leaf indices) to a local ring buffer.
     * Use a zero-copy daemon to ship events to an Apache Kafka pipeline.
     * Consume downstream via a dedicated auto-scaling cluster running optimized multi-threaded TreeSHAP (e.g., using CUDA-accelerated GPUTreeExplainer), persisting the top 3 features to an indexed analytical store (e.g., ClickHouse/Cassandra) within minutes.

---

### Scenario 3: Adversarial Manipulation of Explainers
> **Interviewer:** "An engineer proposes using LIME to prove to an external regulator that our deep learning hiring model does not rely on gender. Can an adversary build a biased model that conceals its discrimination from LIME? How does that attack work, and how do you protect against it?"

#### Probing Strategy
* Is the candidate aware of the theoretical and empirical security vulnerabilities of perturbation-based post-hoc explainers (e.g., the Slack et al. scaffolding attack)?
* Do they understand the distribution shift inherent in synthetic neighborhood generation?

#### The Ideal Response
1. **Mechanics of the Scaffolding Attack:**
   * "Yes, LIME (and even KernelSHAP) can be fooled using an adversarial scaffolding wrapper. This exploits the fact that LIME generates synthetic perturbations around an instance $x$ by sampling from an isotropic Gaussian or uniform marginal distribution. These synthetic perturbation points almost always fall **off the true data manifold** (Out-of-Distribution, or OOD)."

```
          True Data Manifold
         (Dense support region)
          ●   ●   ●   ●   ●  
       ●    ●    ●   ●   ●
    ────────────────────────────────────────
      OOD Region (LIME Perturbations Fall Here)
          ▲         ▲         ▲
          │         │         │
          ×         ×         ×
        (Perturbed instances created by LIME)
```

2. **The Adversarial Classifier Logic:**
   * The attacker builds a composite model $f_{\text{adv}}(x)$:
   
   $$f_{\text{adv}}(x) = \begin{cases} 
   f_{\text{biased}}(x) & \text{if } x \text{ is In-Distribution (True Manifold)} \\
   f_{\text{fair}}(x) & \text{if } x \text{ is Out-of-Distribution (LIME Perturbation)} 
   \end{cases}$$
   
   * When evaluating real applicants, the model executes $f_{\text{biased}}(x)$, rejecting candidates based on gender.
   * When LIME explains the prediction on an applicant, it creates perturbed instances around that candidate. The model's discriminator detects that these perturbations are synthetic (OOD), dynamically switching its execution path to $f_{\text{fair}}(x)$ (which relies purely on legitimate features like `Years of Experience`).
   * LIME fits its surrogate model exclusively on these synthetic samples, generating a clean, unbiased explanation that passes the audit.

3. **Remediation & Defense:**
   * **Manifold-Constrained Perturbation:** Restrict sampling to the empirical data manifold using generative models (e.g., VAEs, normalizing flows) rather than raw Gaussian noise, ensuring perturbations mirror true data distributions.
   * **Intrinsic Explainability:** For high-stakes decisions, abandon post-hoc surrogates entirely in favor of inherently interpretable models, such as **Explainable Boosting Machines (EBMs / Generalized Additive Models)**:
     
     $$g(E[Y]) = \beta_0 + \sum f_i(x_i) + \sum f_{ij}(x_i, x_j)$$
     
     EBMs match tree-based ensembles in performance while remaining fully deterministic and immune to post-hoc adversarial scaffolding.
   * **Gradient-based Axiomatic Auditing:** Deploy Integrated Gradients across an array of randomized, verified baselines to eliminate reliance on localized point-perturbation. Check whether gradients with respect to sensitive attributes are strictly zero across the full integration path.

---

### Comparison of Key XAI Algorithms

| Dimension | LIME | KernelSHAP | TreeSHAP | Integrated Gradients |
| :--- | :--- | :--- | :--- | :--- |
| **Model Compatibility** | Strictly Model-Agnostic | Strictly Model-Agnostic | Tree ensembles only (XGBoost, LightGBM, CatBoost) | Differentiable Neural Networks |
| **Theoretical Guarantees** | None (heuristic local fit) | Game-theoretic (Efficiency, Symmetry, Dummy, Additivity) | Exact game-theoretic Shapley values | Axiomatic (Completeness, Implementation Invariance) |
| **Computational Complexity** | $\mathcal{O}(K \cdot T_{\text{infer}})$ | $\mathcal{O}(K \cdot T_{\text{infer}})$ | $\mathcal{O}(T \cdot L \cdot D^2)$ (Polynomial) | $\mathcal{O}(M \cdot T_{\text{backward}})$ |
| **Primary Weakness** | Sampling instability, kernel bandwidth sensitivity | Computationally expensive; assumes feature independence | Memory consumption on deep trees; restricted to tree architectures | Dependent on baseline ($x'$) selection; path integration artifacts |
| **Production Fit** | Prototyping / Local debugging | Offline batch evaluation | Online inference & offline pipelines | Deep Learning production audit layers |