---
title: Technical Interview Study Note: AI Ethics, Bias, and Explainable AI (XAI)
date: 2026-04-26T04:31:22.404923
---

# Technical Interview Study Note: AI Ethics, Bias, and Explainable AI (XAI)

**Author:** Senior Staff Engineer & FAANG Interviewer  
**Scope:** Addressing the "Black Box" problem, mathematical fairness, and the implementation of interpretability in production systems.

---

## 🧱 1. The Core Concept (Basics Refresh)

In a FAANG context, AI Ethics is not "philosophy"—it is **Risk Management and Engineering Rigor.** As models move from research to serving billions of users, the cost of a biased or unexplainable model is measured in lawsuits, brand erosion, and regulatory fines (e.g., EU AI Act).

### The Three Pillars:
1.  **Bias & Fairness:** Identifying and mitigating systematic prejudice in model outputs (e.g., gender bias in recruiting tools, racial bias in facial recognition).
2.  **Explainability (XAI):** The ability to explain *why* a model made a specific prediction. This is critical for high-stakes domains (Ads, Healthcare, FinTech).
3.  **Accountability & Privacy:** Ensuring data provenance (where did the data come from?) and model robustness (can the model be "tricked" or leak private info?).

### Key Distinction: Interpretability vs. Explainability
*   **Interpretability (Ante-hoc):** The model is simple enough that a human can understand its internal logic (e.g., a shallow Decision Tree or Linear Regression).
*   **Explainability (Post-hoc):** The model is a "Black Box" (e.g., a 175B parameter Transformer), and we use external techniques to probe its reasoning.

---

## ⚙️ 2. Under the Hood (Internal Mechanics & Architecture)

### A. Mathematical Fairness Metrics
You cannot optimize for "fairness" until you define it mathematically. However, the **Impossibility Theorem of Fairness** states you cannot satisfy all metrics simultaneously if base rates differ between groups.

*   **Demographic Parity:** The likelihood of a positive outcome is the same across all groups. 
    *   $P(\hat{Y}=1 | G=a) = P(\hat{Y}=1 | G=b)$
*   **Equal Opportunity:** The True Positive Rate (TPR) is the same across all groups. 
    *   $P(\hat{Y}=1 | Y=1, G=a) = P(\hat{Y}=1 | Y=1, G=b)$
*   **Predictive Parity (Calibration):** The probability of a positive outcome given a positive prediction is equal.
    *   $P(Y=1 | \hat{Y}=1, G=a) = P(Y=1 | \hat{Y}=1, G=b)$

### B. XAI Techniques (The Toolbelt)
#### 1. SHAP (SHapley Additive exPlanations)
Based on **Game Theory**. It treats each feature as a "player" in a game and assigns a "payout" (the prediction) based on their contribution.
*   **Pro:** Solid mathematical foundation; provides local and global consistency.
*   **Con:** Computationally expensive ($O(2^n)$ without approximations like KernelSHAP or TreeSHAP).

#### 2. LIME (Local Interpretable Model-agnostic Explanations)
LIME perturbs the input (changes bits of data) and sees how the prediction changes. It fits a simple linear model *locally* around that specific prediction.
*   **Pro:** Very fast; works on any model.
*   **Con:** Explanations can be unstable (small input changes lead to wildly different explanations).

#### 3. Integrated Gradients (IG)
Used for deep networks. It calculates the integral of the gradients along the path from a "baseline" (e.g., a black image) to the actual input.
*   **Application:** Identifying which pixels in an image or tokens in a sentence caused the model to trigger a specific classification.

#### 4. Attention Maps (For Transformers)
Visualizing attention weights. **Warning:** As a Senior Engineer, you must know that *Attention is not always Explanation*. High attention weights don't necessarily mean that feature was the causal driver of the prediction.

---

## ⚠️ 3. The Interview Warzone

### Scenario: "We are launching a credit-scoring model. Our audits show that the model grants lower credit limits to residents of specific zip codes, which correlates with protected racial groups. How do you handle this?"

#### ❌ The Junior Mistake:
"I'll just remove the 'Zip Code' column from the training data." 
*   **Interviewer Probe:** "Wait, won't other features (like income, education, or even naming conventions) act as proxies for Zip Code?" (This is **Redundant Encoding**).

#### ✅ The Senior/Staff Response:
1.  **Acknowledge Proxy Variables:** Removing the protected attribute isn't enough. I'd perform a **Correlation Analysis** to identify features that encode the same bias.
2.  **Define the Metric:** I would consult stakeholders to choose the right fairness metric. For credit, **Equal Opportunity** is often preferred over Demographic Parity to ensure we aren't penalizing creditworthy individuals in any group.
3.  **Mitigation Strategies:**
    *   **Pre-processing:** Re-weighting the training data (Oversampling underrepresented groups).
    *   **In-processing:** Adding a **Fairness Constraint** to the loss function (e.g., penalizing the model for differences in TPR between groups).
    *   **Post-processing:** Adjusting the classification thresholds per group to ensure equal TPR (though this can have legal/compliance implications).
4.  **Monitoring:** Implementing a **Model Card** and a drift detection system to monitor fairness in real-time production traffic.

---

### Probing Pattern: "Why use SHAP over LIME?"
*   **Deep Answer:** "LIME is a local approximation, which can be inconsistent. SHAP values are the only attribution method that satisfies the **Symmetry** and **Additivity** axioms of game theory. If I sum the SHAP values of all features, they equal the difference between the actual prediction and the average prediction. This makes SHAP more reliable for regulatory auditing."

### Probing Pattern: "How do you explain a 'Hallucination' in an LLM to a non-technical CEO?"
*   **Deep Answer:** "I’d frame it as a **Probability Mismatch**. LLMs are next-token predictors optimized for 'plausibility,' not 'veracity.' I would propose a RAG (Retrieval-Augmented Generation) architecture to provide 'Grounding'—essentially giving the model an open-book exam where it must cite its sources, making the reasoning traceable (Explainable) rather than purely generative."

---

### The "Perfect" Summary for the Interviewer:
> "In production, Ethics and XAI are not afterthoughts—they are part of the **CI/CD pipeline**. A Senior Engineer doesn't just build a model that is 99% accurate; they build a model that is 95% accurate but is **robust, fair, and auditable**, because the risk of that 4% difference is often smaller than the risk of an unexplainable failure."