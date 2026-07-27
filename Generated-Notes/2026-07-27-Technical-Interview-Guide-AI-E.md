---
title: Technical Interview Guide: AI Ethics, Bias, and Explainable AI (XAI)
date: 2026-07-27T04:31:55.484442
---

# Technical Interview Guide: AI Ethics, Bias, and Explainable AI (XAI)

---

## 🧱 1. The Core Concept (Basics Refresh)

Evaluating AI systems at Staff/Principal levels requires moving past superficial hand-waving about "fairness" and "transparency." You must treat AI Ethics and Explainability as **hard mathematical constraints and system trade-offs**.

---

### Algorithmic Bias: Mathematical Formalisms & The Impossibility Theorem

When a model makes a decision $\hat{Y} \in \{0, 1\}$ based on input features $X$, given a binary protected attribute $A \in \{0, 1\}$ (e.g., race, gender, age) and ground truth $Y \in \{0, 1\}$, bias is measured via three mutually exclusive mathematical formulations:

#### 1. Demographic Parity (Independence)
The likelihood of receiving a positive prediction must be identical across all protected groups.
$$\mathbb{P}(\hat{Y}=1 \mid A=0) = \mathbb{P}(\hat{Y}=1 \mid A=1)$$
* **Use Case:** Affirmative action, historical bias compensation (e.g., university admissions).
* **Flaw:** Ignores ground-truth target distributions ($Y$). If base rates differ, enforcing Demographic Parity forces high false positive rates for lower-base-rate groups or high false negative rates for higher-base-rate groups.

#### 2. Equalized Odds (Separation)
The model’s predictions must be conditionally independent of protected attributes given the ground truth label $Y$. This requires equal True Positive Rates (TPR) and False Positive Rates (FPR) across groups.
$$\mathbb{P}(\hat{Y}=1 \mid A=0, Y=y) = \mathbb{P}(\hat{Y}=1 \mid A=1, Y=y) \quad \forall y \in \{0, 1\}$$
* **Equal Opportunity Variant:** Enforces parity *only* on the True Positive Rate ($y=1$).
* **Use Case:** High-stakes risk scoring (e.g., criminal justice recidivism, loan defaults).

#### 3. Predictive Parity / Calibration within Groups (Sufficiency)
The true outcome $Y$ is conditionally independent of protected attribute $A$ given the prediction $\hat{Y}$.
$$\mathbb{P}(Y=1 \mid \hat{Y}=1, A=0) = \mathbb{P}(Y=1 \mid \hat{Y}=1, A=1)$$
* **Use Case:** Risk assessment tools where a score of $0.8$ must represent an $80\%$ probability of the event regardless of group membership.

```
                  ┌─────────────────────────────────────────┐
                  │ Chouldechova / Kleinberg Impossibility  │
                  │              Theorem                    │
                  └────────────────────┬────────────────────┘
                                       │
         Enforces simultaneous satisfaction of 3 fairness metrics:
         ┌───────────────────┬───────────────────┬───────────────────┐
         │ Demographic       │ Equalized         │ Predictive        │
         │ Parity            │ Odds              │ Parity            │
         └─────────┬─────────┴─────────┬─────────┴─────────┬─────────┘
                   │                   │                   │
                   └───────────────────┼───────────────────┘
                                       ▼
                     Impossible to satisfy simultaneously 
                     UNLESS base rates are equal:
                     P(Y=1|A=0) = P(Y=1|A=1)
                     OR the model has perfect accuracy (100%).
```

> **The Impossibility Theorem of Fairness:** You cannot satisfy Demographic Parity, Equalized Odds, and Predictive Parity simultaneously unless the base rates are identical across groups ($\mathbb{P}(Y=1 \mid A=0) = \mathbb{P}(Y=1 \mid A=1)$) or the model is a deterministic, error-free classifier ($\text{TPR}=1, \text{FPR}=0$).

---

### Explainable AI (XAI) Taxonomy

XAI methodologies fall along three architectural axes:

```
                          ┌───────────────────────────┐
                          │   XAI Taxonomy Axes       │
                          └─────────────┬─────────────┘
                                        │
        ┌───────────────────────────────┼───────────────────────────────┐
        ▼                               ▼                               ▼
┌───────────────┐               ┌───────────────┐               ┌───────────────┐
│ Intrinsic vs. │               │ Local vs.     │               │ Model-Agnostic│
│ Post-Hoc      │               │ Global        │               │ vs. Specific  │
└───────┬───────┘               └───────┬───────┘               └───────┬───────┘
        │                               │                               │
        ├─ Intrinsic:                   ├─ Local:                       ├─ Agnostic:
        │  Linear, EBMs                 │  SHAP, LIME                   │  KernelSHAP
        │                               │                               │
        └─ Post-Hoc:                    └─ Global:                      └─ Specific:
           Surrogates, Grad-CAM            PDP, TreeSHAP                   TreeSHAP, IG
```

1. **Intrinsic vs. Post-Hoc:**
   * **Intrinsic:** Models designed to be directly interpretable by humans (e.g., shallow Decision Trees, Linear Models, Explainable Boosting Machines [EBMs]).
   * **Post-Hoc:** Applying secondary diagnostic models/algorithms to extract explanations *after* training a complex, non-interpretable model (e.g., Deep Neural Networks, XGBoost).

2. **Local vs. Global:**
   * **Local:** Explains *why* a specific inference was made for single input vector $x$ (e.g., "Why was *this specific user* denied a loan?").
   * **Global:** Explains the general behavior of model $f(X)$ across the entire dataset manifold (e.g., "What are the top 5 global drivers of default risk for this model?").

3. **Model-Agnostic vs. Model-Specific:**
   * **Model-Agnostic:** Treats the model as a black box $f(x)$ by perturbing inputs and observing outputs (e.g., LIME, KernelSHAP). Flexible, but computationally expensive ($O(2^M)$).
   * **Model-Specific:** Leverages internal structural properties like gradients or tree structures (e.g., Integrated Gradients, Grad-CAM, TreeSHAP). Fast, but tied to specific architecture framework.

---

## ⚙️ 2. Under the Hood (Internal Mechanics & Architecture)

---

### Deep Dive: Post-Hoc Interpretability Algorithms

#### 1. SHAP (SHapley Additive exPlanations)
Based on cooperative game theory, SHAP computes feature contributions (Shapley values) by measuring the marginal contribution of feature $i$ across all possible feature subsets $S \subseteq N \setminus \{i\}$.

$$\phi_i(v) = \sum_{S \subseteq N \setminus \{i\}} \frac{|S|!(|N| - |S| - 1)!}{|N|!} \left[ v(S \cup \{i\}) - v(S) \right]$$

Where:
* $N$ is the set of all features.
* $S$ is a subset of features excluding feature $i$.
* $v(S)$ is the expected outcome of the model conditioned on feature subset $S$: $\mathbb{E}[f(x) \mid x_S]$.

```
   Shapley Value Computational Complexity
   
   Features (N)   Subsets (2^N)   KernelSHAP Computations
   ────────────   ─────────────   ───────────────────────
   10             1,024           10³
   30             1.07 x 10⁹      10⁹  (Requires Sampling)
   100            1.26 x 10³⁰     Unfeasible via Brute Force
```

* **Mathematical Guarantees (Efficiency, Symmetry, Dummy, Additivity):** SHAP is the *only* local explanation method that guarantees these four fundamental properties simultaneously.
* **TreeSHAP Optimization:** Computes exact Shapley values in polynomial time $O(TLD^2)$ instead of exponential time $O(TL2^M)$—where $T$ is the number of trees, $L$ is max leaves, $D$ is max depth, and $M$ is feature count—by recursively tracing tree execution paths.

#### 2. Integrated Gradients (IG)
For differentiable models (Neural Networks), IG solves the saturation problem of raw gradients (where non-zero signals vanish in saturated activation regions like Sigmoid or ReLU) by integrating gradients along a straight trajectory from a baseline input $x'$ to the input $x$.

$$\text{IntegratedGrads}_i(x) = (x_i - x'_i) \times \int_{0}^{1} \frac{\partial F(x' + \alpha(x - x'))}{\partial x_i} d\alpha$$

* **Approximation via Riemann Sums:**
$$\text{IntegratedGrads}_i^{\text{approx}}(x) \approx (x_i - x'_i) \times \frac{1}{m} \sum_{k=1}^{m} \frac{\partial F\left(x' + \frac{k}{m}(x - x')\right)}{\partial x_i}$$
* **Axioms Satisfied:**
  1. **Completeness:** $\sum_{i=1}^{M} \text{IntegratedGrads}_i(x) = F(x) - F(x')$. The sum of feature attributions equals the difference between the model output at $x$ and the baseline output at $x'$.
  2. **Implementation Invariance:** Two functionally equivalent models yield identical attributions regardless of network architecture.

---

### Bias Mitigation Pipeline Architecture

To systematically minimize bias, mitigations must be inserted into the ML lifecycle at distinct stages:

```
 raw DATA           TRAINING phase          POST-PROCESSING
 ┌──────────────┐   ┌───────────────────┐   ┌─────────────────┐
 │ Pre-         │──>│ In-               │──>│ Post-           │
 │ Processing   │   │ Processing        │   │ Processing      │
 └──────────────┘   └───────────────────┘   └─────────────────┘
   • Re-weighing      • Adversarial           • Threshold
   • Disparate          Debiasing               Optimization
     Impact           • Constrained           • Reject Option
     Remover            Optimization            Classification
```

#### 1. Pre-Processing (Data-Level)
* **Re-weighing:** Modifies instance weights in the training set before modeling to eliminate correlation between protected attributes and ground truth labels:
$$W(x) = \frac{\mathbb{P}(A = a) \times \mathbb{P}(Y = y)}{\mathbb{P}(A = a \land Y = y)}$$
* **Disparate Impact Remover:** Edits feature distributions to increase data overlap while preserving rank-order within groups using cumulative distribution functions (CDFs).

#### 2. In-Processing (Algorithmic-Level)
* **Adversarial Debiasing:** Set up a min-max game using a Gradient Reversal Layer (GRL). A predictor model $f_\theta$ minimizes classification loss $\mathcal{L}_{\text{pred}}$, while an adversarial network $g_\phi$ tries to predict protected attribute $A$ from $f_\theta$'s internal representations.

$$\min_{\theta} \max_{\phi} \left[ \mathcal{L}_{\text{pred}}(\theta) - \lambda \mathcal{L}_{\text{adv}}(\theta, \phi) \right]$$

```
                   ┌─────────────────┐
                   │  Input Data X   │
                   └────────┬────────┘
                            │
                            ▼
                   ┌─────────────────┐
                   │ Predictor f(θ)  │
                   └────────┬────────┘
                            │
              ┌─────────────┴─────────────┐
              │                           │
              ▼                           ▼
    ┌──────────────────┐        ┌──────────────────┐
    │ Label Output Y^  │        │ Hidden Layer z   │
    └──────────────────┘        └────────┬─────────┘
                                         │
                                         ▼
                                ┌──────────────────┐
                                │ Gradient Reversal│
                                │   Layer (GRL)    │
                                └────────┬─────────┘
                                         │
                                         ▼
                                ┌──────────────────┐
                                │ Adversary g(φ)   │
                                └────────┬─────────┘
                                         │
                                         ▼
                                ┌──────────────────┐
                                │ Protected Attr A │
                                └──────────────────┘
```

* **Lagrangian Constrained Optimization:** Formulate training loss with explicit inequality constraints representing fairness requirements (e.g., bounded demographic parity differences):

$$\min_{\theta} \mathcal{L}_{\text{base}}(\theta) \quad \text{s.t.} \quad |\mathbb{P}(\hat{Y}=1 \mid A=0) - \mathbb{P}(\hat{Y}=1 \mid A=1)| \le \epsilon$$

#### 3. Post-Processing (Inference-Level)
* **Group-Specific Threshold Adjustment:** Solve for distinct classification decision thresholds $\tau_0, \tau_1$ such that $\mathbb{P}(\hat{Y}=1 \mid A=0, \text{score} > \tau_0) = \mathbb{P}(\hat{Y}=1 \mid A=1, \text{score} > \tau_1)$.
* *Trade-off:* High risk of legal liability under civil rights legislation (e.g., US Title VII compliance, GDPR Article 22) that bans explicitly using protected attributes at inference time.

---

### Production Enterprise System Design for Responsible AI

Below is a low-latency, scalable production ML pipeline integrating feature stores, real-time explanation generation, and fairness drift monitoring.

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                                FEATURE STORE                                    │
│   ┌────────────────────────────────┐   ┌────────────────────────────────────┐   │
│   │ Online Features (Redis/Dynamo) │   │ Offline Features (Snowflake/Iceberg)│   │
│   └───────────────┬────────────────┘   └─────────────────┬──────────────────┘   │
└───────────────────┼──────────────────────────────────────┼──────────────────────┘
                    │                                      │
                    ▼                                      ▼
┌───────────────────────────────────────┐  ┌──────────────────────────────────────┐
│        INFERENCE SERVICE              │  │        TRAINING & FAIRNESS           │
│ ┌───────────────────────────────────┐ │  │ ┌──────────────────────────────────┐ │
│ │ Model Serving (Triton / TorchServe)│ │  │ │ Training Pipeline (Ray/Kubeflow) │ │
│ └─────────────────┬─────────────────┘ │  │ └──────────────────┬───────────────┘ │
│                   │ Predictions       │  │                    │                 │
│                   ▼                   │  │                    ▼                 │
│ ┌───────────────────────────────────┐ │  │ ┌──────────────────────────────────┐ │
│ │ Async XAI Engine                  │ │  │ │ Fairness Bounds Verification     │ │
│ │ (FastSHAP/Integrated Gradients)   │ │  │ │ (Lagrangian Enforcement)         │ │
│ └─────────────────┬─────────────────┘ │  │ └──────────────────┬───────────────┘ │
└───────────────────┼───────────────────┘  └────────────────────┼─────────────────┘
                    │ Explanations                              │ Register
                    ▼                                           ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           CENTRAL MODEL REGISTRY                                │
│                     (MLflow / Weights & Biases)                                 │
└───────────────────────────────────────┬─────────────────────────────────────────┘
                                        │ Audit Telemetry
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                        OBSERVABILITY & MONITORING                               │
│  ┌─────────────────────────────────┐      ┌──────────────────────────────────┐  │
│  │ Disparate Impact Monitoring     │      │ Feature Attribution Drift        │  │
│  │ (Prometheus / Grafana Alerting) │      │ (Population Stability Index - PSI│  │
│  └─────────────────────────────────┘      └──────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## ⚠️ 3. The Interview Warzone

---

### Scenario 1: Real-Time Credit Scoring under Strict Fairness and Compliance Constraints

#### 🎙️ The Prompt
> "Design a real-time Credit Decision Engine for a global bank processing 10,000 requests per second. The compliance team mandates that:
> 1. The model must not show Disparate Impact ($DI < 0.8$) across protected groups.
> 2. Protected attributes (e.g., age, race, gender) **cannot** be passed to the model at inference time.
> 3. Every rejection must return the top 4 exact reasons (adverse action codes) within a 30ms latency budget ($p_{99}$).
>
> How do you engineer this system?"

#### 🔍 Interviewer Probing Strategy
* Do they fall into the trap of assuming that omitting protected attributes guarantees fairness (Fairness through Unawareness)?
* Do they try to compute slow $O(2^M)$ KernelSHAP evaluations synchronously during the inference call?
* How do they handle proxy variables (e.g., zip code, income history correlated with protected status)?

#### 🎯 The Perfect Response

##### 1. Anti-Proxy Strategy (Training Phase)
Omit explicit demographic variables from inference, but use them in training to strip bias from proxy features:
* **Mutual Information Screening:** Calculate mutual information $I(X_j; A)$ between non-protected feature $X_j$ and protected attribute $A$. Drop or transform high-MI features (e.g., granular zip codes).
* **Adversarial Representation Learning:** Train an encoder network using Adversarial Debiasing. The encoder creates an un-correlated intermediate embedding $Z$ where $I(Z; A) \to 0$, while maximizing predicting power for $Y$.

##### 2. Real-Time Explainability Architecture
To satisfy the 30ms $p_{99}$ latency requirement, bypass brute-force runtime SHAP:
* **Option A (Distilled Interpretability):** Train an **Explainable Boosting Machine (EBM)** or **Generalized Additive Model (GAM)** with main effects and pairwise interactions:
$$g(E[Y]) = \beta_0 + \sum f_i(x_i) + \sum f_{ij}(x_i, x_j)$$
Evaluating feature attribution drops to an $O(1)$ table lookup of pre-binned functions $f_i(x_i)$, requiring $< 2\text{ms}$.
* **Option B (FastSHAP Surrogate Model):** If a neural net is required, train a secondary FastSHAP neural network parameterized by $\theta_{\text{shap}}$ that directly predicts Shapley values in a single forward pass: $s(x) \approx \phi(f, x)$. Inference latency: $\approx 5\text{ms}$.

```
                 ┌────────────────────────────────┐
                 │  Credit Application Request    │
                 └───────────────┬────────────────┘
                                 │
                                 ▼
                 ┌────────────────────────────────┐
                 │  Feature Retrieval (Redis)     │
                 └───────────────┬────────────────┘
                                 │
                 ┌───────────────┴────────────────┐
                 │                                │
                 ▼                                ▼
  ┌─────────────────────────────┐  ┌─────────────────────────────┐
  │ Primary Scoring Model (EBM) │  │ Async Logging Pipeline      │
  │ Latency: < 5ms              │  │ (Kafka Stream)              │
  └──────────────┬──────────────┘  └──────────────┬──────────────┘
                 │                                │
                 ▼                                ▼
  ┌─────────────────────────────┐  ┌─────────────────────────────┐
  │ Feature Score Lookup &      │  │ Continuous Fairness Engine  │
  │ Reason Code Extraction      │  │ Calculates DI & Drift       │
  └──────────────┬──────────────┘  └─────────────────────────────┘
                 │
                 ▼
  ┌─────────────────────────────┐
  │ Response Payload            │
  │ Decision + Top 4 Attributions│
  └─────────────────────────────┘
```

##### 3. System Design and Adverse Action Code Extraction
```json
// Real-time API Response Construction
{
  "application_id": "app_9201841",
  "decision": "REJECTED",
  "credit_score": 580,
  "adverse_action_codes": [
    {"rank": 1, "code": "HIGH_UTILIZATION", "attribution_val": -0.42},
    {"rank": 2, "code": "DELINQUENCY_HISTORY", "attribution_val": -0.31},
    {"rank": 3, "code": "SHORT_CREDIT_HISTORY", "attribution_val": -0.15},
    {"rank": 4, "code": "HIGH_INQUIRY_COUNT", "attribution_val": -0.09}
  ]
}
```

##### 4. Production Observability
Implement continuous statistical drift monitoring via Kafka streaming consumers calculating rolling **Disparate Impact Ratio**:

$$\text{DI} = \frac{\mathbb{P}(\hat{Y}=1 \mid A=1)}{\mathbb{P}(\hat{Y}=1 \mid A=0)}$$

If rolling 1-hour $DI < 0.8$, trigger a PagerDuty alert to fallback to a conservative intrinsic model ruleset and initiate automated retraining.

---

### Scenario 2: The XAI Latency & Reliability Trap (SHAP Instability in Production)

#### 🎙️ The Prompt
> "Your team deployed a multi-modal neural network (Tabular + Image) for an e-commerce fraud system running at 100k QPS. The product team enabled KernelSHAP for real-time customer support disputes.
>
> Customer service reports that:
> 1. Explanations for the *exact same transaction* change depending on when the dispute call is made.
> 2. Generating explanations causes severe tail-latency spikes ($p_{99} > 4.5\text{s}$), crashing downstream inference nodes.
>
> What is mathematically and architecturally going wrong, and how do you resolve both issues?"

#### 🔍 Interviewer Probing Strategy
* Does the candidate understand the inner mechanics of KernelSHAP sampling approximations?
* Do they recognize out-of-distribution (OOD) feature perturbation failures in Shapley value estimation?
* Can they propose architectural decoupling patterns for heavy background compute?

#### 🎯 The Perfect Response

##### 1. Mathematical Root Cause Analysis

* **Non-Determinism (Sampling Instability):** KernelSHAP approximates the theoretical Shapley expectation $\mathbb{E}[f(x) \mid x_S]$ by taking Monte Carlo samples over background datasets. Because random background samples are drawn per inference request, different calls draw different subsets, causing variance in computed Shapley values ($\sigma^2_{\phi_i} > 0$).
* **Out-Of-Distribution (OOD) Perturbations:** Observational SHAP sets unconditioned features $x_{\bar{S}}$ by sampling from the marginal background distribution $P(X_{\bar{S}})$. When features are correlated (e.g., `Age=12` and `Income=$100,000`), independent sampling generates unrealistic data points, sending the neural network into undefined manifold regions and yielding erratic gradients.

```
       Observational vs. Interventional Sampling

       Realistic Feature Space          OOD Perturbation Error
       ┌────────────────────────┐       ┌────────────────────────┐
       │ Income                 │       │ Income                 │
       │   ^                    │       │   ^   * Unrealistic    │
       │   │     * High-Income  │       │   │     Data Point     │
       │   │    /  Adults       │       │   │   * (Age=12,       │
       │   │   /                │       │   │      Income=100k)  │
       │   │  /                 │       │   │                    │
       │   └─────────> Age      │       │   └─────────> Age      │
       └────────────────────────┘       └────────────────────────┘
```

##### 2. Fixing Explanatory Instability
* **Fix 1 (Interventional SHAP via Causal Graphs):** Replace marginal sampling with conditional sampling $P(X_{\bar{S}} \mid X_S)$ or employ **Path-Dependent TreeSHAP / Integrated Gradients** using a fixed, deterministic baseline $x'$ (e.g., median vector for tabular data, neutral grey/black background for images).
* **Fix 2 (Deterministic Random Seed & Background Indexing):** Fix a static background dataset $B$ of $K=100$ medoid centroids computed via $k$-medoids clustering over the training set. Lock the random sampling seed across all inference worker nodes:

```python
# Fixed-Baseline Deterministic Local Explanation Pattern
import torch
from captum.attr import IntegratedGradients

class DeterministicExplainer:
    def __init__(self, model, baseline_tensor):
        self.ig = IntegratedGradients(model)
        # Static medoid baseline derived offline
        self.baseline = baseline_tensor 

    def explain(self, input_tensor, target_class):
        # Deterministic: IG produces exact same attribution for fixed input
        attributions, delta = self.ig.attribute(
            input_tensor,
            baselines=self.baseline,
            target=target_class,
            return_convergence_delta=True
        )
        return attributions
```

##### 3. Fixing Architectural Latency Bottlenecks
Decouple compute-heavy explanations from synchronous request-response execution paths:

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                               INFERENCE PATH                                    │
│                                                                                 │
│  User Request ──> API Gateway ──> Model Inference Service ──> Sync Response     │
│                                          │                    (Latency < 20ms)  │
└──────────────────────────────────────────┼──────────────────────────────────────┘
                                           │ Log Context (Async)
                                           ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              BACKGROUND PIPELINE                                │
│                                                                                 │
│                                Kafka Event Bus                                  │
│                                          │                                      │
│                                          ▼                                      │
│                            Async Worker Pool (Celery/Ray)                       │
│                       (Runs Deterministic IG / FastSHAP)                        │
│                                          │                                      │
│                                          ▼                                      │
│                              Cache Store (Redis TTL)                            │
│                                          │                                      │
│                                          ▼                                      │
│                        Customer Support Portal Read Access                      │
└─────────────────────────────────────────────────────────────────────────────────┘
```

1. **Synchronous Fast-Path:** The inference service runs only the primary forward pass ($f(x)$) and returns the classification decision in $<20\text{ms}$.
2. **Asynchronous Event Stream:** Write inference payloads $(I_d, X, \hat{Y})$ to a high-throughput Kafka topic.
3. **Background Worker Pool:** Asynchronous background GPU workers consume from Kafka and calculate Integrated Gradients or FastSHAP attributions.
4. **Caching Layer:** Persist pre-computed attributions into Redis keyed by `transaction_id` with a 30-day TTL. When a dispute is logged minutes or days later, the support portal fetches pre-computed, deterministic attributions instantly in $O(1)$ time.

---

## 💡 Executive Summary Checklist for Staff+ Candidates

* **Do not treat fairness as a single metric:** Call out the *Impossibility Theorem of Fairness* early. Frame the choice between Demographic Parity, Equalized Odds, and Predictive Parity as a business and legal strategy decision.
* **Know the algorithmic trade-offs:** Never suggest standard KernelSHAP for low-latency ($<50\text{ms}$) real-time serving. Offer alternatives like **TreeSHAP**, **Integrated Gradients**, **FastSHAP**, or **Explainable Boosting Machines (EBMs)**.
* **Address correlation & instability in XAI:** Show deep knowledge of out-of-distribution sampling failures in model-agnostic explainers and offer solutions (e.g., static background baselines, path-dependent methods).
* **System Design must reflect compliance laws:** Always decouple protected attributes from runtime inference features while retaining them in offline pipelines for adversarial debiasing, auditability, and disparate impact telemetry.