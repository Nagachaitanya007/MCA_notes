---
title: Technical Interview Deep-Dive: Data Preprocessing
date: 2026-05-03T04:31:29.757833
---

# Technical Interview Deep-Dive: Data Preprocessing
**Focus: Outliers, Missing Values, and Skewed Data**

In the FAANG context, data preprocessing is not a "cleanup" task—it is an architectural decision. Senior engineers are expected to understand how these choices impact the convergence of gradient descent, the bias-variance tradeoff, and the production latency of the inference pipeline.

---

## 🧱 1. The Core Concept (Basics Refresh)

Data preprocessing ensures that the mathematical assumptions of your model hold true.

*   **Outliers:** Observations that lie at an abnormal distance from other values. They are not always "errors"; they can be the most critical data points (e.g., fraud).
*   **Missing Values:** The absence of data. The *mechanism* of missingness is more important than the *method* of filling it.
*   **Skewed Data:** When the distribution of features is asymmetrical. High skewness can lead to models that are biased toward the "head" of the distribution, failing to generalize to the "tail."

---

## ⚙️ 2. Under the Hood (Internal Mechanics & Architecture)

### A. The Geometry of Outliers
Outliers distort the **Loss Surface**.
*   **MSE (L2 Loss):** Because errors are squared, an outlier has a quadratic impact on the gradient. The model will "tilt" its weights disproportionately to minimize the error of a single outlier, degrading performance on the 99% of normal data.
*   **Detection Mechanics:**
    *   **Z-Score:** Assumes Gaussian distribution. $Z = (x - \mu) / \sigma$. Threshold usually > 3.
    *   **IQR (Interquartile Range):** Non-parametric. $Boundaries = [Q1 - 1.5 \times IQR, Q3 + 1.5 \times IQR]$.
    *   **Isolation Forests:** An unsupervised approach that "isolates" points by randomly selecting a feature and a split value. Outliers are isolated in fewer steps (shorter path lengths) than normal points.

### B. Missingness Mechanisms (Rubin’s Theory)
In production, we categorize missing data to choose the imputation strategy:
1.  **MCAR (Missing Completely at Random):** No relationship between missingness and any values. *Action:* Simple imputation (mean/median).
2.  **MAR (Missing at Random):** Missingness is related to *observed* data (e.g., "Men are less likely to report weight"). *Action:* Multivariate imputation (MICE).
3.  **MNAR (Missing Not at Random):** Missingness depends on the *unobserved* value itself (e.g., "People with high debt don't report it"). *Action:* This is a feature. Use an "Indicator Variable" (Is_Missing flag).

### C. The Calculus of Skewness
Models like Linear Regression or LDA assume **Homoscedasticity** (constant variance). Highly skewed data violates this.
*   **Log Transform:** Compresses the range of values, effectively "pulling in" the long tail. Works only for positive values.
*   **Box-Cox:** A parametric power transform that find the $\lambda$ that best approximates normality. Requires positive data.
*   **Yeo-Johnson:** A modern generalization that handles zero and negative values.
*   **The Staff Engineer Perspective:** Tree-based models (XGBoost, LightGBM) are **invariant** to monotonic transformations. You transform for the *optimizer*, not for the *split logic*.

---

## ⚠️ 3. The Interview Warzone

### Scenario 1: The "Blind" Imputer
**Interviewer:** *"I see you used Mean Imputation for the 'Income' column. Why?"*
*   **Red Flag Response:** "It’s standard practice to fill nulls so the model doesn't crash."
*   **Staff Level Response:** "Mean imputation is dangerous for 'Income' because it's typically a right-skewed distribution; the mean is pulled by high-earners. I’d prefer **Median Imputation** to maintain central tendency or, better yet, **Iterative Imputation (MICE)** using 'Education' and 'Job Title' to predict income. Most importantly, I’d add a **Binary Mask** (`income_is_missing`) because the fact that income is missing is often a signal of credit risk itself (MNAR)."

### Scenario 2: The Outlier Dilemma
**Interviewer:** *"We are building a Fraud Detection model. We found thousands of outliers. Should we remove them using the IQR method?"*
*   **The Trap:** Outliers in fraud *are* the signal.
*   **Staff Level Response:** "No. In Fraud, outliers are the minority class we want to capture. Instead of removing them, I would use **Robust Scaling** (scaling by IQR instead of Mean/SD) to ensure the features are on the same scale without squashing the signal. If we use a distance-based model like KNN, outliers will dominate. I’d recommend a **Tree-based ensemble** or **Huber Loss**, which is less sensitive to outliers than MSE but more differentiable than MAE."

### Scenario 3: Data Leakage in Preprocessing
**Interviewer:** *"Walk me through your preprocessing pipeline code. Where do you calculate the mean for scaling?"*
*   **The Critical Error:** Calculating stats on the whole dataset before splitting.
*   **The Perfect Response:** "Calculations must happen **after** the train/test split. I calculate the $\mu$ and $\sigma$ only on the **training set** and then apply (transform) those exact values to the test/validation set. Calculating on the whole dataset introduces **Data Leakage**, as information from the 'future' (the test set) leaks into the training process, leading to over-optimistic performance metrics."

### Scenario 4: The Scale of Data
**Interviewer:** *"We have 100TB of data with 30% missing values in a critical column. MICE is too slow. What do you do?"*
*   **The Engineering Trade-off:** "At that scale, iterative imputation is computationally prohibitive ($O(n \cdot p)$). I would implement a **Constant Imputation** (e.g., -999 or 'Missing') and use a model that handles missingness natively, like **XGBoost or CatBoost**. These models learn the optimal split direction for missing values during training by minimizing the loss, effectively treating 'missing' as its own category."

---

### 💡 Staff Pro-Tips (The "Differentiator")
1.  **Domain Knowledge > Statistics:** If a "blood pressure" reading is 0, it’s not an outlier; it’s a sensor error or a dead patient. Don't just look at the distribution; understand the data generating process.
2.  **The "Clipping" Strategy:** Sometimes, instead of removing outliers, "Winsorizing" (clipping at the 1st and 99th percentile) is better. It preserves the data volume while neutralizing the gradient explosion.
3.  **Feature Interaction:** Scaling is mandatory for models using L1/L2 regularization. If features aren't on the same scale, the penalty will unfairly suppress features with naturally smaller magnitudes.