---
title: System Design & Engineering Notes: AI Ethics, Bias, & Explainable AI (XAI)
date: 2026-07-29T04:31:59.724131
---

# System Design & Engineering Notes: AI Ethics, Bias, & Explainable AI (XAI)

---

## 🧱 1. The Core Concept (Basics Refresh)

In high-stakes production systems (e.g., automated credit underwriting, real-time ad targeting, fraud detection, candidate screening), ML models do not operate in a vacuum. "Ethics, Bias, and Explainability" are not philosophical nice-to-haves; they are strict engineering constraints, compliance requirements (e.g., EU AI Act, US Fair Credit Reporting Act), and key metrics for operational safety.

### Mathematical Foundations of Fairness

Fairness is mathematically non-trivial because **you cannot optimize for all fairness definitions simultaneously**.

Let:
* $X$: Input features
* $A$: Sensitive/Protected attribute (e.g., gender, race, age; where $A \in \{0, 1\}$)
* $Y$: Ground truth binary label ($Y \in \{0, 1\}$)
* $\hat{Y} = R(X, A)$: Predictor model's binary output decision ($\hat{Y} \in \{0, 1\}$)
* $S = P(\hat{Y}=1 | X, A)$: Continuous score output by the model

```
                       ┌────────────────┐
                       │  Input (X, A)  │
                       └───────┬────────┘
                               │
                               ▼
                       ┌────────────────┐
                       │ Model R(X, A)  │
                       └───────┬────────┘
                               │
                  ┌────────────┴────────────┐
                  ▼                         ▼
            Continuous Score S      Binary Decision Ŷ
```

#### 1. Demographic Parity (Independence)
Selection rate must be identical across protected groups. The outcome $\hat{Y}$ is independent of the protected attribute $A$.
$$P(\hat{Y} = 1 \mid A = 0) = P(\hat{Y} = 1 \mid A = 1)$$
* **Metric**: Disparate Impact Ratio ($DIR$) = $\frac{P(\hat{Y}=1 \mid A=0)}{P(\hat{Y}=1 \mid A=1)}$. (US legal baseline often uses the 80% rule: $DIR < 0.8$ indicates adverse impact).
* **Flaw**: Ignores base-rate differences in ground truth $Y$ across groups. Can force a model to select unqualified candidates to satisfy equality of outcome.

#### 2. Equalized Odds (Separation)
Predictor $\hat{Y}$ is conditionally independent of $A$ given ground truth label $Y$. Requires equal True Positive Rates (TPR) *and* equal False Positive Rates (FPR) across groups.
$$P(\hat{Y} = 1 \mid Y = y, A = 0) = P(\hat{Y} = 1 \mid Y = y, A = 1) \quad \forall y \in \{0, 1\}$$
* **TPR Parity (Equal Opportunity)**: $P(\hat{Y}=1 \mid Y=1, A=0) = P(\hat{Y}=1 \mid Y=1, A=1)$
* **FPR Parity**: $P(\hat{Y}=1 \mid Y=0, A=0) = P(\hat{Y}=1 \mid Y=0, A=1)$

#### 3. Predictive Parity (Sufficiency)
Ground truth $Y$ is conditionally independent of $A$ given the prediction $\hat{Y}$. Requires equal Positive Predictive Value (PPV/Precision) across groups.
$$P(Y = 1 \mid \hat{Y} = 1, A = 0) = P(Y = 1 \mid \hat{Y} = 1, A = 1)$$

#### The Impossibility Theorem of Fairness (Chouldechova, 2017; Kleinberg et al., 2016)
If baseline prevalence rates $P(Y=1 \mid A=0) \neq P(Y=1 \mid A=1)$, **you cannot simultaneously satisfy Demographic Parity, Equalized Odds, and Predictive Parity**, unless the model exhibits perfect prediction accuracy (AUC = 1.0).

---

### Taxonomy of Bias

```
┌────────────────────────────────────────────────────────────────────────┐
│                        Data Generation Pipeline                        │
├───────────────────┬──────────────────────┬─────────────────────────────┤
│ Historical Bias   │ Representation Bias  │ Measurement Bias            │
│ (World state is   │ (Sampling fails to   │ (Proxies encode systemic    │
│ biased)           │ reflect population)  │ errors/disparities)         │
└─────────┬─────────┴──────────┬───────────┴──────────────┬──────────────┘
          │                    │                          │
          ▼                    ▼                          ▼
┌────────────────────────────────────────────────────────────────────────┐
│                        ML System Life-Cycle                            │
├──────────────────────────────────────────┬─────────────────────────────┤
│ Aggregation Bias                         │ Algorithmic Bias            │
│ (One-size-fits-all model for distinct    │ (Objective function optimizes  │
│ sub-populations)                         │ average loss, ignoring minority)│
└──────────────────────────────────────────┴─────────────────────────────┘
```

---

### Taxonomy of Explainable AI (XAI)

| Axis | Classification | Description | Typical Algorithms |
| :--- | :--- | :--- | :--- |
| **Scope** | **Global** | Explains total model behavior across the dataset. | Feature Importance, Partial Dependence Plots (PDP) |
| | **Local** | Explains individual predictions for a single inference instance. | SHAP, LIME, Integrated Gradients |
| **Model Dependency**| **Model-Agnostic** | Treats model as a black box; evaluates input/output perturbations. | LIME, KernelSHAP |
| | **Model-Specific** | Leverages internal parameters (gradients, tree nodes). | TreeSHAP, Integrated Gradients, Grad-CAM |
| **Timing** | **Intrinsic** | Self-interpretable architectures by design. | Linear Models, Decision Trees (shallow), EBMs |
| | **Post-hoc** | Explanations calculated after model training. | SHAP, LIME, Counterfactuals |

---

## ⚙️ 2. Under the Hood (Internal Mechanics & Architecture)

### 1. SHAP (Shapley Additive exPlanations)

SHAP calculates feature contributions using cooperative game theory (Shapley Values). The model features are "players" in a game, and the prediction is the "payoff".

#### Mathematical Definition
The Shapley value $\phi_i$ for feature $i$ is calculated as the weighted marginal contribution of feature $i$ across all possible feature subsets $S \subseteq N \setminus \{i\}$:

$$\phi_i(v) = \sum_{S \subseteq N \setminus \{i\}} \frac{|S|!(|N|-|S|-1)!}{|N|!} \left[ v(S \cup \{i\}) - v(S) \right]$$

Where:
* $N$ is the set of all input features.
* $S$ is a subset of features excluding $i$.
* $v(S)$ is the marginal expectation function: $E[f(x) \mid x_S]$.

```
All Features N = {x1, x2, x3}

Subset S = {}         ─► Marginal Contribution of x1: f({x1}) - f({})
Subset S = {x2}       ─► Marginal Contribution of x1: f({x1, x2}) - f({x2})
Subset S = {x3}       ─► Marginal Contribution of x1: f({x1, x3}) - f({x3})
Subset S = {x2, x3}   ─► Marginal Contribution of x1: f({x1, x2, x3}) - f({x2, x3})

Weighted Average of Contributions = Shapley Value (ϕ1)
```

#### Efficiency Mechanics
* **Exact KernelSHAP**: Naive complexity is $\mathcal{O}(2^M)$ where $M$ is the number of features. Computationally infeasible for real-time inference when $M > 15$.
* **TreeSHAP**: Optimizes exact evaluation for Tree Ensembles (XGBoost, LightGBM) by recursively tracking feature split paths down the tree nodes.
  * Time Complexity reduced from exponential to $\mathcal{O}(T \cdot L \cdot D^2)$, where $T$ = trees, $L$ = maximum leaves, $D$ = maximum depth.

---

### 2. LIME (Local Interpretable Model-agnostic Explanations)

LIME approximates the decision boundary of a complex model locally around a specific instance $x$ using an interpretable surrogate model $g \in G$ (e.g., Sparse Linear Regression).

#### Optimization Objective
$$\text{Explanation}(x) = \arg\min_{g \in G} \mathcal{L}(f, g, \pi_x) + \Omega(g)$$

Where:
* $f(x)$: Black-box complex model.
* $g(z')$: Simple interpretable model operating on binary presence/absence representation $z'$.
* $\pi_x(z) = \exp\left(-\frac{D(x, z)^2}{\sigma^2}\right)$: Exponential kernel defining the local distance neighborhood around $x$.
* $\mathcal{L}$: Squared loss measuring fidelity of $g$ to $f$ weighted by $\pi_x$.
* $\Omega(g)$: Model complexity penalty (e.g., $L_1$ regularization penalizing non-zero weights).

```
   Complex Boundary f(x)               LIME Local Linear Model g(x)
      (Global View)                        (Zoomed-in at Point X)

    \       /   + +                    +   + 
     \     /   + + +                   + + | +
  - - \   /   + + +                  ------+-------  <-- Local Decision
 - - - \_/   + + +                   - - - | +           Surrogate Linear Boundary
- - - - - - + + +                   - - -  |
```

#### Failure Modes of LIME vs. SHAP
* **Instability/Non-Determinism**: LIME uses stochastic random sampling around $x$. Running LIME twice on the same point can yield different top features.
* **Adversarial Vulnerability**: Slack et al. (2020) demonstrated that models can be constructed to detect LIME perturbations, serving unbiased predictions on synthetic samples while maintaining biased predictions on real inputs.

---

### 3. Integrated Gradients (Deep Learning)

For differentiable models (e.g., PyTorch/TensorFlow Neural Nets, Transformers), Integrated Gradients computes the path integral of gradients along the straight line from a neutral baseline input $x'$ (e.g., black image or zero-embedding) to input $x$.

#### Mathematical Definition
$$\text{IG}_i(x) = (x_i - x'_i) \times \int_{0}^{1} \frac{\partial F(x' + \alpha(x - x'))}{\partial x_i} d\alpha$$

Approximated via Riemann sums over $m$ discrete steps:

$$\text{IG}_i^{\text{approx}}(x) = (x_i - x'_i) \times \frac{1}{m} \sum_{k=1}^{m} \frac{\partial F\left(x' + \frac{k}{m}(x - x')\right)}{\partial x_i}$$

#### Key Axioms Satisfied
* **Completeness**: Sum of attribution scores equals the net difference in prediction between baseline and input: $\sum_i \text{IG}_i(x) = F(x) - F(x')$.
* **Implementation Invariance**: Attribution is identical for functionally equivalent models, regardless of structural implementation differences.

---

### 4. Technical Mitigation Approaches for Bias

```
 Raw Data  ──► [ PRE-PROCESSING ] ──► Training ──► [ IN-PROCESSING ] ──► Inference ──► [ POST-PROCESSING ]
               • Re-weighing                       • Adversarial Debiasing             • Equalized Odds Processor
               • Disparate Impact Remover          • Minimax Loss Constraints          • Reject Option Classification
```

#### In-Processing: Adversarial Debiasing Architecture

```
                       ┌─────────────────────────┐
                       │       Input Feature     │
                       │        Vector (X)       │
                       └────────────┬────────────┘
                                    │
                                    ▼
                       ┌─────────────────────────┐
                       │     Predictor Network   │
                       │          (θ_P)          │
                       └────────────┬────────────┘
                                    │
                  ┌─────────────────┴─────────────────┐
                  ▼                                   ▼
       ┌─────────────────────┐             ┌─────────────────────┐
       │ Prediction Loss L_Y │             │ Logits / Hidden (Z) │
       └─────────────────────┘             └──────────┬──────────┘
                                                      │
                                                      ▼
                                           ┌─────────────────────┐
                                           │ Adversary Network   │
                                           │       (θ_A)         │
                                           └──────────┬──────────┘
                                                      │
                                                      ▼
                                           ┌─────────────────────┐
                                           │ Adversary Loss L_A  │
                                           │  (Predicts Dep. A)  │
                                           └─────────────────────┘
```

The objective function optimizes a saddle-point problem via Minimax optimization:

$$\min_{\theta_P} \max_{\theta_A} \quad \mathcal{L}_Y(f_{\theta_P}(X), Y) - \alpha \cdot \mathcal{L}_A(g_{\theta_A}(f_{\theta_P}(X)), A)$$

* Predictor $\theta_P$ tries to minimize task classification loss $\mathcal{L}_Y$.
* Adversary $\theta_A$ tries to predict protected attribute $A$ from the predictor's output or latent embeddings $Z$.
* Gradient Reversal Layer (GRL) scales and flips the sign of gradients back-propagated from $\theta_A$ to $\theta_P$, stripping demographic information from intermediate embeddings.

---

### 5. Architectural Production Integration (MLOps Systems Design)

```
                 [ Low-Latency Online Path (<20ms) ]
                                 │
 Client Request  ────────┐       │
                         ▼       ▼
                  ┌────────────────────┐
                  │ API Gateway / Router│
                  └──────────┬─────────┘
                             │
            ┌────────────────┴────────────────┐
            │                                 │
            ▼                                 ▼
┌──────────────────────┐          ┌────────────────────────┐
│ Scoring Engine       │          │ Explainability Engine   │
│ (XGBoost/ONNX Model) │          │ (Asynchronous / Cache) │
└──────────┬───────────┘          └───────────┬────────────┘
           │                                  │
           ▼                                  ▼
┌──────────────────────┐          ┌────────────────────────┐
│ Online Predictions   │          │ Feature Attributions   │
│ Store                │          │ Cache (Redis)          │
└──────────┬───────────┘          └───────────┬────────────┘
           │                                  │
           └────────────────┬─────────────────┘
                            │
                            ▼
           [ Asynchronous MLOps Offline Path ]
                            │
                            ▼
               ┌──────────────────────────┐
               │ Streaming Bus (Kafka)    │
               └────────────┬─────────────┘
                            │
            ┌───────────────┴───────────────┐
            ▼                               ▼
┌──────────────────────┐        ┌──────────────────────────┐
│ Fairness Drift       │        │ Model Audit Log          │
│ Monitor (Flink)      │        │ (S3 / Parquet Lake)      │
└──────────────────────┘        └──────────────────────────┘
```

#### Production Trade-offs Matrix
* **Real-time Path**: Never compute exact KernelSHAP inline on standard microsecond-latency scoring passes. Compute prediction instantly $\rightarrow$ Push inference payload to Kafka $\rightarrow$ Calculate TreeSHAP or Background SHAP asynchronously $\rightarrow$ Store in Redis/Cassandra cache for explainability UI views.
* **Fairness Monitoring**: Real-time evaluation of Disparate Impact Ratio on sliding dynamic time windows (e.g., Apache Flink over Kafka event streams) to detect data drift that distorts fairness bounds.

---

## ⚠️ 3. The Interview Warzone

### Scenario 1: High-Throughput Real-Time System Design

#### **Interviewer Scenario:**
> *"You are designing a high-throughput automated loan approval engine handling 10,000 requests per second. The model must return an outcome in less than 20 milliseconds at p99. Regulations require that for every rejected user, you provide the top 3 primary reasons for rejection (attributions), and the system must guarantee strict Equal Opportunity across demographic groups. How do you design this system?"*

#### **Probing Questions:**
* How do you avoid blowing up p99 latency when calculating feature attributions?
* What happens if the Equal Opportunity constraint reduces total revenue/model accuracy? How do you resolve that trade-off mathematically?

#### **Common Candidate Failure Modes:**
* Suggesting running KernelSHAP or LIME inline on the real-time serving thread.
* Suggesting dropping sensitive feature $A$ completely from the feature set and assuming that removes bias (ignoring *Proxy Variables*).
* Failing to define trade-off boundaries using Pareto Frontiers.

#### **Senior Staff Level Exemplar Response:**

##### 1. Latency & Attribution Strategy:
* **Inline Scoring Engine**: Use a GBDT model (XGBoost) optimized via ONNX Runtime or C++ native inference.
* **Fast Feature Attribution**: Use **TreeSHAP** (C++ optimized wrapper). Because TreeSHAP operates directly on tree structures, its execution latency for a shallow GBDT (e.g., depth=6, trees=100) is sub-millisecond ($<1\text{ms}$). Inline TreeSHAP execution within the 20ms p99 budget is mathematically and computationally feasible, avoiding distributed async lookup complexity.
* **Fallback Strategy**: If moving to a Deep Learning model where integrated gradients take $>50\text{ms}$, decoupling is mandatory:
  * Fast path: Return inference score $\hat{Y}$ in 5ms.
  * Async path: Push $(X, \hat{Y})$ to Kafka; an Explainability worker cluster calculates background attributions via Integrated Gradients or DeepSHAP, populating a low-latency cache (Redis) within 200ms. The client UI polls or consumes a WebSocket update for reason codes.

##### 2. Enforcing Equal Opportunity ($TPR_{A=0} = TPR_{A=1}$):
* Dropping protected attribute $A$ fails due to high mutual information in proxy attributes (e.g., postal code, historical credit lines).
* **In-Processing Penalty Strategy**: Add a fairness penalty to the loss function during model training via a constrained optimization framework (Lagrangian Dual Formulation):

$$\min_{\theta} \mathcal{L}_{\text{task}}(f_\theta(X), Y) \quad \text{s.t.} \quad |TPR_{A=0}(\theta) - TPR_{A=1}(\theta)| \le \epsilon$$

* **Post-Processing Alternative (Reject Option Classification / Threshold Adjustment)**:
  * Keep the model continuous output probability score $S = P(Y=1 \mid X)$.
  * Rather than applying a universal global decision threshold (e.g., $S \ge 0.50$), optimize group-specific thresholds $(\tau_0, \tau_1)$ post-hoc on validation data to satisfy $TPR_{A=0} = TPR_{A=1}$.

```
 Group A=0 Score Distribution        Group A=1 Score Distribution
      ───────┐                            ─────────┐
             │                                     │
             ▼                                     ▼
     [ Threshold τ0 ]                      [ Threshold τ1 ]
             │                                     │
             ▼                                     ▼
  Yields TPR_0 = 0.85                   Yields TPR_1 = 0.85
```

##### 3. Trade-off Resolution:
* Construct a **Pareto Frontier Plot** comparing Pareto-Optimal sets of (Equal Opportunity Difference vs. ROC-AUC / Business Revenue).
* Present business stakeholders with explicit quantitative trade-off options rather than making unquantified arbitrary choices.

---

### Scenario 2: Debugging / Root-Cause Analysis of Latent Bias

#### **Interviewer Scenario:**
> *"We deployed a LLM-backed resume parsing and candidate matching system. During offline evaluation, we noticed that removing explicit demographic terms (names, gender, age) did not eliminate severe bias against female applicants for senior engineering roles. Top matching scores disproportionately skew male. How do you systematically isolate the root cause, quantify the bias, and remediate the issue without destroying general candidate-retrieval performance?"*

#### **Probing Questions:**
* How do you detect and prove proxy variable leakage within dense embedding vector spaces?
* How do you remediate bias in non-linear dense embeddings without retraining a multi-billion parameter LLM from scratch?

#### **Common Candidate Failure Modes:**
* Recommending prompt engineering remedies alone (e.g., system prompt: "Please evaluate fairly and do not be biased"), which fail under edge cases and lack deterministic guarantees.
* Suggesting re-training the entire foundation LLM, which is economically and computationally prohibitive ($100k+ compute cost).

#### **Senior Staff Level Exemplar Response:**

##### 1. Diagnosis & Isolation (Root Cause Analysis):
* **Proxy Leakage Identification**: Dense text embeddings (e.g., OpenAI embeddings, BERT encoders) preserve demographic signals through latent correlations (e.g., "women's chess club captain", collegiate sorority names, gap years associated with maternity leave, or gendered language in recommendation phrases).
* **Linear Probe / Mutual Information Test**: Train a simple linear classifier (Logistic Regression or SVM) on the frozen resume embeddings $Z$ to predict the protected attribute $A$ (gender). If classification accuracy exceeds baseline chance ($>50\%$), demographic information is explicitly encoded in the latent manifold:

$$P(A \mid Z) \gg P(A)$$

* **Counterfactual Perturbation Testing**: Construct paired synthetic resumes $X_{\text{orig}}$ and $X_{\text{counter}}$ where only gendered tokens/proxies are modified (e.g., "Chairman" $\rightarrow$ "Chairperson", "Varsity Men's Swimming" $\rightarrow$ "Varsity Women's Swimming"). Measure prediction variance:

$$\Delta = |f(X_{\text{orig}}) - f(X_{\text{counter}})|$$

If $\Delta > \delta_{thresh}$, the network is demonstrating localized instability triggered by gender proxies.

##### 2. Remediation Architecture Options:

```
               ┌──────────────────────────────┐
               │    Raw Resume Embeddings (Z) │
               └──────────────┬───────────────┘
                              │
            ┌─────────────────┴─────────────────┐
            │                                   │
            ▼                                   ▼
[ Option A: Projection Deflection ]  [ Option B: Adversarial Adapter ]
  Project out gender-bias subspace     Train Lightweight Rank-Preserving
  via Nullspace Projection (INLP)      LoRA / MLP Adapter Layer
            │                                   │
            └─────────────────┬─────────────────┘
                              │
                              ▼
               ┌──────────────────────────────┐
               │  Debiased Embeddings (Z_clean)│
               └──────────────┬───────────────┘
                              │
                              ▼
               ┌──────────────────────────────┐
               │  Cosine Similarity Scoring   │
               └──────────────────────────────┘
```

##### Option A: Latent Space Projection (Iterative Nullspace Projection - INLP)
* Identify the linear subspace $W_A$ in the embedding space $Z$ that encodes gender information using iterative linear classifiers.
* Calculate the projection matrix $P_{N}$ onto the nullspace of $W_A$.
* Transform incoming embeddings at inference time: $Z_{\text{debiased}} = Z \cdot P_{N}$.
* *Result*: Strips the linear subspace encoding gender while preserving total vector dimension and general semantic structure without retraining the core transformer.

##### Option B: Parameter-Efficient Fine-Tuning (PEFT / LoRA) with Counterfactual Loss
* Freeze base LLM parameters.
* Attach a LoRA (Low-Rank Adaptation) adapter.
* Train with a composite loss function containing a pairwise counterfactual fairness constraint:

$$\mathcal{L}_{\text{total}} = \mathcal{L}_{\text{ranking}}(Y, \hat{Y}) + \lambda \cdot \|f_\theta(X_{\text{orig}}) - f_\theta(X_{\text{counter}})\|_2^2$$

##### 3. Continuous Verification & Monitoring:
* Implement an automated regression test pipeline using CI/CD.
* Every model release build must pass a evaluation check on a holdout **Counterfactual Evaluation Suite**.
* Define continuous acceptance criteria:
  1. **Disparate Impact Ratio (DIR)**: $0.90 \le DIR \le 1.11$ across all protected demographic slices.
  2. **Embedding Probe Accuracy**: Linear classifier accuracy on $Z_{\text{debiased}}$ predicting attribute $A$ must fall within random baseline chance error bounds ($\approx 50\%$).
  3. **Task Performance**: Mean Reciprocal Rank (MRR) or NDCG@K on candidate retrieval benchmarks must retain $\ge 98\%$ of non-debiased baseline performance.