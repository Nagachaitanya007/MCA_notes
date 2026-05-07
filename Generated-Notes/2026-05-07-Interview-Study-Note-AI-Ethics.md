---
title: Interview Study Note: AI Ethics, Bias, and Explainable AI (XAI)
date: 2026-05-07T04:31:38.966064
---

# Interview Study Note: AI Ethics, Bias, and Explainable AI (XAI)
**Target Audience:** Senior/Staff Software & ML Engineers
**Role:** FAANG Interviewer Perspective

---

## 🧱 1. The Core Concept (Basics Refresh)

In high-stakes FAANG environments (Ads, Credit, Healthcare, Search), AI Ethics is not a "soft skill"—it is a **system reliability and compliance requirement**. If a model is biased, it is technically inaccurate for a subset of your users. If it isn't explainable, it is un-debuggable and legally indefensible.

### The Taxonomy of the Problem
1.  **Bias (Algorithmic Unfairness):** Systematic prejudice in model outputs. It is often categorized into:
    *   **Historical Bias:** Real-world inequality reflected in training data.
    *   **Representation Bias:** Under-sampling certain populations.
    *   **Measurement Bias:** Proxies that don't capture the true label (e.g., using "arrests" as a proxy for "crime").
2.  **Explainability (XAI):** The ability to explain *why* a model reached a decision. 
    *   **Post-hoc:** Explaining a black-box model (e.g., BERT, ResNet) after training.
    *   **Intrinsic:** Using inherently interpretable models (e.g., Lasso Regression, shallow Decision Trees).
3.  **Ethics:** The framework of trade-offs (e.g., Privacy vs. Utility, Accuracy vs. Fairness).

---

## ⚙️ 2. Under the Hood (Internal Mechanics & Architecture)

As a Senior Engineer, you must move beyond "fairness is important" to "here is how we mathematically constrain the loss function."

### A. Mathematical Fairness Metrics
To mitigate bias, you must first define it mathematically. There is no "perfect" metric; they often contradict each other (the **Impossibility Theorem of Fairness**).
*   **Demographic Parity:** $P(\hat{Y}=1 | A=0) = P(\hat{Y}=1 | A=1)$. The probability of a positive outcome is the same regardless of the sensitive attribute $A$.
*   **Equalized Odds:** $P(\hat{Y}=1 | A=0, Y=y) = P(\hat{Y}=1 | A=1, Y=y)$. Ensures equal True Positive and False Positive rates across groups.
*   **Counterfactual Fairness:** A decision is fair if it remains the same in a world where the individual's protected attribute was different.

### B. The XAI Toolkit
1.  **SHAP (SHapley Additive exPlanations):** Based on Cooperative Game Theory. It assigns each feature an importance value for a specific prediction.
    *   *The Math:* $\phi_i = \sum_{S \subseteq \{x_1, \dots, x_n\} \setminus \{i\}} \frac{|S|!(n-|S|-1)!}{n!} [v(S \cup \{i\}) - v(S)]$
    *   *Trade-off:* Computationally expensive ($2^n$ combinations), though optimized versions like TreeSHAP exist.
2.  **LIME (Local Interpretable Model-agnostic Explanations):** Learns an interpretable model (linear) locally around a specific prediction by perturbing the input.
3.  **Integrated Gradients (IG):** Primarily for Deep Learning. It computes the integral of gradients along a path from a "baseline" input to the actual input. Crucial for attributing importance in NLP/Vision.

### C. Mitigation Strategies
*   **Pre-processing:** Re-weighing instances or transforming data (e.g., Disparate Impact Remover).
*   **In-processing:** Adding a "fairness penalty" to the loss function: $L = L_{task} + \lambda L_{fairness}$.
*   **Post-processing:** Adjusting the classification thresholds for different groups to satisfy equalized odds.

---

## ⚠️ 3. The Interview Warzone

### The Scenario-Based Question
> *"We are building a machine learning model to rank job applicants for internal engineering roles at [FAANG]. Initial tests show the model prefers male candidates. How do you handle this?"*

#### 🚩 Red Flag Responses (The "Junior" mistakes):
*   "I’ll just remove the 'Gender' column." (False: Proxies like 'Sports' or 'University' will still encode gender).
*   "I'll just collect more data." (Naive: If the industry is historically biased, more data just reinforces the bias).

#### ✅ The Perfect Response (The "Staff" approach):
1.  **Identify the Source:** Is it *Representation Bias* (fewer female resumes) or *Historical Bias* (historical hiring managers were biased)?
2.  **Define the Metric:** For hiring, I’d suggest **Equalized Odds**. We want to ensure that a qualified candidate has the same probability of being recommended regardless of gender.
3.  **Technical Intervention:**
    *   **Audit for Proxies:** Use **SHAP** to see if features like "Gap in Resume" or "Specific Keywords" are acting as proxies for gender.
    *   **Adversarial Debiasing:** Train a secondary "adversary" network that tries to predict gender from the main model's latent representations. We optimize the main model to minimize its own loss while *maximizing* the adversary's error.
4.  **Explainability for Stakeholders:** Implement **Counterfactual Explanations**. If a candidate is rejected, the system should generate a statement like: *"If your experience with Python was 2 years instead of 1, you would have been recommended."* This ensures the decision is tied to skills, not attributes.

### Probing Patterns (What the interviewer will ask next)

**Q: "If your Fairness constraint drops Model Precision by 5%, do you deploy?"**
*   **Staff Answer:** "This is a product and legal decision, not just an engineering one. I would present a **Pareto Frontier** showing the trade-off between Accuracy and Fairness. In regulated domains (hiring/finance), we accept the 5% drop to mitigate legal risk and ensure long-term brand trust. In a low-stakes ad-ranking scenario, we might tune $\lambda$ differently."

**Q: "Why choose SHAP over LIME?"**
*   **Staff Answer:** "SHAP is grounded in game theory and satisfies the **Consistency** and **Missingness** axioms. LIME is a local approximation and can be unstable—small changes in input can lead to wildly different explanations. For high-stakes decisions, SHAP's mathematical guarantees are worth the extra compute cost."

**Q: "How do you handle 'Black Box' LLM bias in a RAG (Retrieval-Augmented Generation) system?"**
*   **Staff Answer:** "Bias in RAG is two-fold: Retrieval bias and Generation bias. I’d implement **Constitutional AI** principles—using a second 'critic' LLM to audit the output against a set of ethical principles before it reaches the user. I'd also use **Integrated Gradients** on the attention heads to see if the model is over-indexing on biased tokens in the retrieved context."

---

### Final Pro-Tip for the Interview
When discussing AI Ethics, **always mention Latency and Cost.** Senior Engineers know that computing SHAP values for every user in a real-time 100ms request cycle is impossible. Propose **asynchronous explanation logging** or **distilling** the complex model into a "teacher-student" interpretable proxy for real-time monitoring.