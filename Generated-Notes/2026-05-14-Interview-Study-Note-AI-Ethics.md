---
title: Interview Study Note: AI Ethics, Bias, and Explainable AI (XAI)
date: 2026-05-14T04:31:28.105491
---

# Interview Study Note: AI Ethics, Bias, and Explainable AI (XAI)
**Role:** Senior Staff Engineer / FAANG Interviewer Perspective  
**Focus:** Large-scale Systems, Trade-offs, and Algorithmic Fairness

---

## 🧱 1. The Core Concept (Basics Refresh)

In a FAANG context, AI Ethics is not a "feel-good" add-on; it is **risk management**. A biased model isn't just unethical—it’s a product failure that leads to regulatory fines (GDPR/EU AI Act), brand erosion, and poor generalization.

### The Three Pillars:
1.  **Bias & Fairness:** Ensuring the model doesn't systematically disadvantage protected groups (race, gender, age, etc.). Bias can enter at the data collection (Historical Bias), sampling (Representation Bias), or labeling (Measurement Bias) stages.
2.  **Explainability (XAI):** The ability to provide human-interpretable reasons for a model's prediction. This is critical for high-stakes domains (Ads, Cloud Vision, Healthcare, RecSys).
3.  **Accountability & Safety:** Implementing guardrails (e.g., RLHF for LLMs) to prevent hallucination, toxicity, or "jailbreaking" that violates safety policies.

---

## ⚙️ 2. Under the Hood (Internal Mechanics & Architecture)

As a Senior Engineer, you must move beyond "fairness is important" to "here is the mathematical implementation."

### A. Quantifying Bias (The Metrics)
You cannot fix what you cannot measure. You must choose a fairness definition based on the product goal:
*   **Demographic Parity:** $P(\hat{Y}=1 | G=a) = P(\hat{Y}=1 | G=b)$. The positive rate is equal across groups. (Use when you want to correct historical imbalances).
*   **Equal Opportunity:** $P(\hat{Y}=1 | Y=1, G=a) = P(\hat{Y}=1 | Y=1, G=b)$. The True Positive Rates (TPR) are equal. (Standard for credit/hiring).
*   **Predictive Rate Parity:** Precision is equal across groups.

### B. Mitigation Strategies (The Pipeline)
1.  **Pre-processing (Data Level):** 
    *   *Re-weighting:* Assigning higher weights to underrepresented samples in the loss function.
    *   *Suppression:* Removing sensitive attributes (Warning: Often fails due to "redlining" where other features act as proxies).
2.  **In-processing (Algorithmic Level):**
    *   *Adversarial Debiasing:* Training a GAN where the "Generator" tries to predict the label while an "Adversary" tries to predict the protected attribute from the Generator's internal representations. You optimize for the Generator's success and the Adversary's failure.
    *   *Constrained Optimization:* Adding a fairness penalty term to the loss function ($Loss = \mathcal{L}_{task} + \lambda \cdot \mathcal{L}_{fairness}$).
3.  **Post-processing (Inference Level):**
    *   Adjusting classification thresholds independently for different groups to equalize TPR/FPR.

### C. XAI Architecture (The "How")
*   **SHAP (SHapley Additive exPlanations):** Based on Game Theory. It assigns each feature an importance value for a particular prediction. 
    *   *Pros:* Mathematically grounded (Axiomatic). 
    *   *Cons:* Computationally expensive ($O(2^n)$ without approximations).
*   **LIME (Local Interpretable Model-agnostic Explanations):** Permutes input data and trains a simple linear surrogate model around a specific prediction.
*   **Integrated Gradients (IG):** Computes the integral of gradients from a "baseline" (e.g., a black image) to the actual input. Best for Deep Learning and NLP.
*   **Attention Maps:** Visualizing weights in Transformer blocks to see which tokens the model "looked at."

---

## ⚠️ 3. The Interview Warzone

### The Scenario: "The Biased Loan Approver"
**Interviewer:** *"We deployed a credit scoring model. It’s 98% accurate overall, but we found it rejects minority applicants at a significantly higher rate despite similar income levels. How do you diagnose and fix this?"*

#### 🔴 The Junior Mistake:
"I would just remove the 'Race' column from the dataset and retrain."
*   **Why it fails:** Proxy variables (Zip code, education level) will still allow the model to 'learn' race. You haven't solved the underlying distribution shift.

#### 🟡 The Mid-Level Response:
"I would calculate the Disparate Impact ratio. If it's below 0.8, I'd use SHAP to see which features are causing the bias and then maybe re-weight the training data."
*   **Better, but:** Lacks an understanding of the **Accuracy-Fairness Trade-off**.

#### 🟢 The Senior/Staff "Perfect" Response:
1.  **Taxonomy of Bias:** "First, I'd determine if this is **Representation Bias** (lack of data) or **Historical Bias** (labels reflect past human prejudice). I’d analyze the feature correlations to identify **proxy variables**."
2.  **Metric Selection:** "Since this is lending, I’d prioritize **Equal Opportunity (TPR)**. We want to ensure that qualified applicants have the same chance of approval regardless of group."
3.  **The Pareto Frontier:** "I would implement **Adversarial Debiasing** in the training loop. However, I’d present a **Pareto Frontier** to stakeholders—showing the trade-off curve between Model Accuracy and Fairness Metrics. We must decide as a business where to sit on that curve."
4.  **Explainability as Debugging:** "I’d use **Integrated Gradients** or **SHAP** to see if the model is 'cheating' by using proxies. If 'Zip Code' has a high SHAP value and correlates with race, we may need to feature-engineer a 'Cost of Living' index to replace it."
5.  **Human-in-the-loop:** "Finally, I’d implement an **Audit Log** and a manual review trigger for 'marginal' cases (predictions near the decision threshold)."

### Deep Probing Questions & Counter-Punches:

*   **Q: "If SHAP tells us a feature is important, can we trust it?"**
    *   **A:** "Not entirely. SHAP measures *contribution*, not *causality*. If two features are highly correlated, SHAP might split the importance between them, leading to 'feature dependence' issues. I’d use **Permutation Importance** as a cross-check."
    *   
*   **Q: "How do you handle bias in LLMs (Generative AI)?"**
    *   **A:** "It’s harder because the output is unstructured. I’d use **Constitutional AI** (pioneered by Anthropic) or **RLHF** (Reinforcement Learning from Human Feedback) with a diverse set of labelers. I’d also implement **Red Teaming** to find edge cases where the system prompts bypass safety filters."

*   **Q: "We can't afford the latency of SHAP at inference time. What now?"**
    *   **A:** "We don't run SHAP on every request. We use it for **Global Explainability** during the validation phase to understand the model's 'brain.' For real-time 'Local' explanations, we can use a **Distilled Surrogate Model** (a smaller, interpretable model that mimics the large one)."

---

### 💎 Final Pro-Tip for the Interview:
When discussing Ethics/XAI, **always mention the business impact.** 
> *"Improving explainability isn't just about ethics; it's about debugging. If we can see WHY the model failed, we can iterate on the features faster, which ultimately reduces the cost per experiment."* 

This shows you are a **Senior Staff Engineer** who thinks about the bottom line, not just a researcher.