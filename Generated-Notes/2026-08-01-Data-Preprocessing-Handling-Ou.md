---
title: Data Preprocessing: Handling Outliers, Missing Values, and Skewed Data
date: 2026-08-01T04:32:08.310869
---

# Data Preprocessing: Handling Outliers, Missing Values, and Skewed Data

---

## 🧱 1. The Core Concept (Basics Refresh)

In production machine learning pipelines, raw data is rarely distributed cleanly or fully populated. Preprocessing converts noisy, real-world data into robust representations suitable for modeling.

```
       +-------------------------------------------------------+
       |                       RAW DATA                        |
       +-------------------------------------------------------+
                                   |
         +-------------------------+-------------------------+
         |                         |                         |
         v                         v                         v
+------------------+      +------------------+      +------------------+
|     OUTLIERS     |      |  MISSING VALUES  |      |   SKEWED DATA    |
| (Noise/Anomalies)|      | (MCAR/MAR/MNAR)  |      |  (Heavy Tails)   |
+------------------+      +------------------+      +------------------+
         |                         |                         |
         v                         v                         v
+------------------+      +------------------+      +------------------+
| Detection & Cap  |      | Imputation Logic |      | Power Transforms |
| (IQR / IsoForest)|      | (Indicator/MICE) |      |  (Box-Cox/Y-J)   |
+------------------+      +------------------+      +------------------+
         |                         |                         |
         +-------------------------+-------------------------+
                                   |
                                   v
       +-------------------------------------------------------+
       |               MODEL-READY DISTRIBUTION                |
       +-------------------------------------------------------+
```

### Outliers
Points that deviate significantly from the general distribution of the data. 
* **Parametric (Z-Score):** Assumes a Gaussian distribution. Identifies samples where $|Z| > 3$, where $Z = \frac{x - \mu}{\sigma}$.
* **Non-Parametric (IQR):** Uses quartiles. Outliers lie outside $[Q_1 - 1.5 \cdot \text{IQR},\, Q_3 + 1.5 \cdot \text{IQR}]$, where $\text{IQR} = Q_3 - Q_1$.
* **Multivariate (Isolation Forest / Mahalanobis):** Identifies anomalies across high-dimensional feature spaces where univariate metrics fail.

### Missing Values
Data points that are absent due to collection failure, refusal to respond, or system errors. Categorized by Rubin’s Missing Data Theory:
* **Missing Completely at Random (MCAR):** Missingness is independent of both observed and unobserved data.
* **Missing at Random (MAR):** Missingness depends on observed data, but not on the missing value itself.
* **Missing Not at Random (MNAR):** Missingness depends directly on the missing value itself (e.g., high earners omitting income).

### Skewed Data
Asymmetric probability distributions with heavy tails.
* **Positive (Right-Skewed):** Mean > Median > Mode. Common in financial transactions, user engagement metrics, and operational latencies.
* **Negative (Left-Skewed):** Mean < Median < Mode. Less common; seen in asset lifetimes or test scores with ceilings.
* **Impact:** Breaks linear/logistic regression assumptions (homoscedasticity and normality of residuals) and slows convergence in gradient-based optimization algorithms.

---

## ⚙️ 2. Under the Hood (Internal Mechanics & Architecture)

### Deep Math & Algorithms

#### Outlier Detection Mechanics

##### Mahalanobis Distance
Measures distance relative to the covariance matrix ($\Sigma$), capturing multivariate feature interactions:

$$D_M(\mathbf{x}) = \sqrt{(\mathbf{x} - \boldsymbol{\mu})^T \boldsymbol{\Sigma}^{-1} (\mathbf{x} - \boldsymbol{\mu})}$$

Unlike Euclidean distance, Mahalanobis accounts for non-spherical data clusters by scaling distance according to feature variance and co-variance.

##### Isolation Forest
Constructs an ensemble of random decision trees ($iTrees$). Anomaly isolation works on the principle that anomalies require fewer random recursive partitions to isolate than normal points.

The anomaly score $s$ for a sample $x$ over a dataset of size $n$ is defined as:

$$s(x, n) = 2^{-\frac{E(h(x))}{c(n)}}$$

Where:
* $h(x)$ is the path length of sample $x$.
* $E(h(x))$ is the average path length across all isolation trees.
* $c(n) = 2\ln(n - 1) + 0.5772156649 \ (\text{Euler's constant}) - \frac{2(n - 1)}{n}$ is the average path length of unsuccessful searches in a Binary Search Tree (BST).

```
   Normal Point Isolation                Anomaly Point Isolation
  (Requires Many Splits)                  (Requires Few Splits)

      o  o  o  o  o                            o  o  o  o
    -----------------                        ------------
   |    o   o   o    |                      |    o  o    |
   |  o   x   o      |                      |  o    o    |   x (Anomaly)
   |    o   o        |                      |    o       |  /
    -----------------                        --------------
     /     \     \                             |
   ...     ...   ...                           x isolated at depth = 1!
  (Deep path length)
```

An anomaly score $s \to 1$ indicates a high probability of being an outlier, while $s \ll 0.5$ indicates a standard point.

---

#### Missing Data Mechanisms & Advanced Imputation Algorithms

##### Mathematical Taxonomy of Missingness
Let $Y = (Y_{\text{obs}}, Y_{\text{mis}})$ be the full dataset, and $M$ be a binary missingness indicator matrix ($M_i = 1$ if missing, $0$ otherwise).

$$\begin{aligned}
\text{MCAR:} \quad & P(M \mid Y_{\text{obs}}, Y_{\text{mis}}) = P(M) \\
\text{MAR:} \quad & P(M \mid Y_{\text{obs}}, Y_{\text{mis}}) = P(M \mid Y_{\text{obs}}) \\
\text{MNAR:} \quad & P(M \mid Y_{\text{obs}}, Y_{\text{mis}}) \neq P(M \mid Y_{\text{obs}})
\end{aligned}$$

##### MICE (Multivariate Imputation by Chained Equations)
Operates under the MAR assumption via Fully Conditional Specification (FCS). For features $Y_1, Y_2, \dots, Y_p$:
1. Perform simple mean/median imputation for all missing values as a baseline start.
2. For feature $Y_j$: Set its imputed values back to `NaN`.
3. Fit a regressor or classifier $Y_j \sim Y_{-j}$ using observed values of $Y_j$.
4. Predict and fill missing $Y_j$ values with outputs from the trained model (often sampling from the predictive posterior distribution to preserve variance).
5. Cycle through all features $j = 1 \dots p$ repeatedly for $K$ iterations (typically 10–20 iterations) until convergence is reached.

---

#### Power Transformations

##### Box-Cox Transformation
Requires strictly positive values ($y > 0$). Parameter $\lambda$ is optimized via Maximum Likelihood Estimation (MLE):

$$y^{(\lambda)} = \begin{cases} \dfrac{y^\lambda - 1}{\lambda} & \text{if } \lambda \neq 0 \\[8pt] \ln(y) & \text{if } \lambda = 0 \end{cases}$$

##### Yeo-Johnson Transformation
Extends Box-Cox to support zero and negative values ($y \in \mathbb{R}$):

$$\psi(\lambda, y) = \begin{cases} \dfrac{(y + 1)^\lambda - 1}{\lambda} & \text{if } \lambda \neq 0, y \ge 0 \\[8pt] \ln(y + 1) & \text{if } \lambda = 0, y \ge 0 \\[8pt] -\dfrac{(-y + 1)^{2 - \lambda} - 1}{2 - \lambda} & \text{if } \lambda \neq 2, y < 0 \\[8pt] -\ln(-y + 1) & \text{if } \lambda = 2, y < 0 \end{cases}$$

---

### Data Leakage Mechanics

A common engineering mistake is calculating preprocessing statistics over the **entire dataset** before cross-validation splitting.

```
❌ DATA LEAKAGE PIPELINE (Flawed)
[ Full Dataset (Train + Test) ] 
               │
               ▼
   Calculates μ, σ, Quantiles  <-- LEAKS TEST DISTRIBUTION INTO TRAIN
               │
               ▼
     [ Train ] / [ Test ]
               │
               ▼
   Overoptimistic Performance Metrics

-----------------------------------------------------------------------

✅ ISOLATED PIPELINE (Production-Safe)
     [ Full Dataset ]
            │
            ▼
   [ Train ]    [ Test ]
       │            │
       ▼            │
  Calculates        │
   μ, σ, λ          │
       │            │
       ├────────────┼──────────────┐
       ▼                           ▼
[ Transform Train ]       [ Transform Test ]
(using Train parameters)  (using Train parameters)
```

When fitting stateful transformers (`StandardScaler`, `PowerTransformer`, `SimpleImputer`, `IsolationForest`):
* Parameters ($\mu, \sigma, Q_1, Q_3, \lambda$) must be calculated **only** on the training split $X_{\text{train}}$.
* Transforms are applied to $X_{\text{val}}$, $X_{\text{test}}$, and production inference payloads using the parameters fitted on $X_{\text{train}}$.
* Fitting transformers globally leaks distribution statistics from test sets into training splits, inflating validation performance and leading to silent failure in production.

---

### Production Architectural Trade-offs

#### Streaming/Online Systems vs. Batch Architectures
* **Batch Processing:** Computes global statistical properties (e.g., exact quantiles, dynamic MICE regressors) over full storage passes (Spark/BigQuery). High statistical precision; higher processing latency.
* **Online/Streaming Processing (Flink/Spark Streaming):** Cannot compute exact global statistical moments over sliding streaming windows without linear space overhead. 
  * *Solution for Mean/Variance:* Use **Welford’s Algorithm** for continuous online computation of mean and variance in $O(1)$ space complexity per sample:
    
    $$M_k = M_{k-1} + \frac{x_k - M_{k-1}}{k}, \quad S_k = S_{k-1} + (x_k - M_{k-1})(x_k - M_k)$$
    
    $$\sigma^2 = \frac{S_k}{k - 1}$$
    
  * *Solution for Quantiles:* Use probabilistic data structures like **T-Digest** or **Q-Digest** to approximate extreme percentiles ($p_{99}, p_{99.9}$) with low memory overhead.

#### Feature Engineering and Pipeline Complexity Matrix

| Strategy | Compute Complexity (Training) | Compute Complexity (Inference) | Memory Footprint | Edge Case Safety | Impact on Linear Models | Impact on Tree Ensembles |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Mean/Median Imputation** | $O(N)$ | $O(1)$ | $O(1)$ | High | Moderate distortion | Low |
| **MICE Imputation** | $O(K \cdot N \cdot D \cdot M)$ | $O(D \cdot M)$ | $O(D \cdot M)$ | Low (Sensitive to covariance shifts) | High preservation | Low |
| **Log Transform** | $O(N)$ | $O(1)$ | $O(1)$ | Fails on $x \le 0$ | High benefit | No impact (Monotonic transformation) |
| **Yeo-Johnson** | $O(N \cdot \text{MLE Iterations})$ | $O(1)$ | $O(1)$ | High | High benefit | No impact (Monotonic transformation) |
| **Isolation Forest** | $O(T \cdot N \log N)$ | $O(T \cdot \text{Depth})$ | $O(T \cdot \text{Nodes})$ | High | Cleans noise | Reduces bad split choices |
| **Winsorization (IQR Capping)**| $O(N \log N)$ | $O(1)$ | $O(1)$ | High | High benefit | Low-to-Moderate benefit |

---

## ⚠️ 3. The Interview Warzone (Scenario-based Questions & Staff-Level Responses)

### Scenario 1: Streaming E-Commerce Ads Engine with Heavy MNAR and Extreme Outliers

#### Interviewer Probing Pattern
> *"We are building a real-time ad click-through rate (CTR) and conversion value prediction system. Features include `user_historical_spend` (heavily right-skewed, continuous values up to $100k, missing 40% of the time because non-registered users don't have records) and `user_age`. How do you handle missing values, outliers, and extreme skew in a pipeline processing 50,000 QPS with an inference latency budget of < 10ms?"*

#### Naive Response
> *"I would drop the missing values or replace them with the median `user_historical_spend`. Then I'd remove outliers beyond 3 standard deviations using Z-score. Finally, I'd apply a log transformation to normalize `user_historical_spend`."*

#### Why the Naive Response Fails
1. **Misidentifying MNAR as MAR/MCAR:** `user_historical_spend` is missing *because* the user is unregistered (MNAR/Structural missingness). Imputing median spend introduces systematic bias, skewing non-registered user representations toward average registered users.
2. **Invalid Outlier Assumptions:** Z-score assumes a normal distribution. Extreme right-skewed features render standard deviation calculations meaningless.
3. **Inference Latency & Production Nuance:** Relying on computationally expensive imputations or missing-value lookups at 50,000 QPS risks latency SLA violations if not designed for $O(1)$ run-time complexity.

#### Staff-Level Response

##### 1. Structural Missingness Strategy (MNAR)
Do not use basic mean/median/MICE imputation. Introduce an explicit missingness indicator flag: `is_unregistered = isnan(user_historical_spend)`. 
* For tree-based estimators (e.g., LightGBM/XGBoost), set `user_historical_spend` to `NaN` or a sentinel value like `-1`. Modern gradient boosting trees learn default split paths for missing values by maximizing split gain during training.
* For linear models or neural network embeddings, impute missing values with a designated constant (e.g., `0`), relying on the `is_unregistered` binary indicator to let the linear layer learn distinct intercept offsets for unregistered users.

##### 2. Outlier Handling under SLA Constraints
Avoid parametric Z-scores. Derive fixed capping thresholds offline using training set quantiles ($p_{0.1}$ and $p_{99.9}$).
* Apply **Winsorization** at low/high percentile caps ($C_{\text{low}}, C_{\text{high}}$) in $O(1)$ operational latency during online feature extraction:

$$\hat{x} = \min(\max(x, C_{\text{low}}), C_{\text{high}})$$

* Update $C_{\text{low}}$ and $C_{\text{high}}$ offline using **T-Digest** over windowed data streams, periodically deploying parameters via an asynchronous feature store (e.g., Feast/Tecton).

##### 3. Skewness Mitigation
* If using **Gradient Boosted Decision Trees (GBDTs)**, explicit skew transformations are mathematically unnecessary because tree algorithms use rank-based monotonic splits $I(x_j \le \theta)$.
* If feeding into a **Neural Network / Logistic Regression** layer, apply a vectorized modified log transform: $\log1p(x) = \ln(1 + x)$ (for $x \ge 0$), or fit a **Yeo-Johnson Transformer** offline and export its parameter $\lambda$ as a static $O(1)$ computation graph node during serving.

---

### Scenario 2: Data Leakage in Cross-Validation & Preprocessing Pipelines

#### Interviewer Probing Pattern
> *"Look at this Python code written by a junior ML engineer. The validation ROC-AUC score is 0.98, but production performance drops to 0.65. Spot the flaws in this preprocessing structure and write the idiomatic production fix."*

```python
# FLAWED PIPELINE SUBMITTED BY JUNIOR ENGINEER
import pandas as pd
from sklearn.preprocessing import PowerTransformer
from sklearn.impute import KNNImputer
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.model_selection import cross_val_score

df = pd.read_csv("user_churn_data.csv")
X = df.drop(columns=["target"])
y = df["target"]

# Step 1: Preprocess global data
imputer = KNNImputer(n_neighbors=5)
X_imputed = imputer.fit_transform(X)

transformer = PowerTransformer(method='yeo-johnson')
X_transformed = transformer.fit_transform(X_imputed)

# Step 2: Perform Cross-Validation
clf = GradientBoostingClassifier()
scores = cross_val_score(clf, X_transformed, y, cv=5, scoring='roc_auc')
print(f"Mean CV ROC-AUC: {scores.mean()}")
```

#### Staff-Level Analysis & Code Fix

##### Flaws Identified
1. **Global Imputation Leakage:** `KNNImputer.fit_transform(X)` computes distances using samples across the entire dataset. Validation fold points directly influence the imputed values in training folds.
2. **Global Power Transformer Leakage:** `PowerTransformer.fit_transform(X_imputed)` estimates the optimal $\lambda$ parameter using MLE over the entire distribution, including the validation set.
3. **Data Drift & Serving Disconnect:** No stateful transformer objects are serialized for inference. Live serving requests cannot replicate the exact dynamic fits run across the combined dataset.

##### Production-Grade Fix
Enforce clean isolation between training and validation splits using `sklearn.pipeline.Pipeline`. All transformations are computed **only** on $X_{\text{train}}$ inside each cross-validation fold, preventing leakage and ensuring model parameters are saved cleanly.

```python
import pandas as pd
from sklearn.preprocessing import PowerTransformer
from sklearn.impute import SimpleImputer
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.model_selection import cross_val_score, StratifiedKFold
from sklearn.pipeline import Pipeline

df = pd.read_csv("user_churn_data.csv")
X = df.drop(columns=["target"])
y = df["target"]

# Structuring the stateful pipeline execution
pipeline = Pipeline([
    # Impute missingness locally within each cross-validation fold
    ('imputer', SimpleImputer(strategy='median', add_indicator=True)),
    # Power transform parameterized exclusively on the fold's training slice
    ('transformer', PowerTransformer(method='yeo-johnson')),
    # Estimator
    ('classifier', GradientBoostingClassifier(random_state=42))
])

# Enforce stratified fold splitting
cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)

# cross_val_score executes fit_transform on train folds, transform on val folds
scores = cross_val_score(pipeline, X, y, cv=cv, scoring='roc_auc', n_jobs=-1)

print(f"Production-Realistic CV ROC-AUC: {scores.mean():.4f}")
```

---

### Scenario 3: Real-Time Feature Store Design for Outliers and High-Dimensional Missingness

#### Interviewer Probing Pattern
> *"How do you handle feature transformations, missing value imputations, and outlier mitigation when training set sizes reach 10 TB, and serving requires low-latency feature serving via an online key-value store (e.g., Redis)?"*

#### Staff-Level Response

##### Architectural Strategy
Decouple transformation state generation from online inference execution.

```
       [ 10 TB Offline Raw Data ]
                   │
                   ▼
       Distributed Batch Job 
    (Spark / Ray / BigQuery Engine)
                   │
    ┌──────────────┴──────────────┐
    ▼                             ▼
Computes Global Bounds       Trains Transformer Specs
 (p0.1, p99.9 Capping)     (Imputation Constants, λ)
    │                             │
    └──────────────┬──────────────┘
                   ▼
     [ Immutable Metadata Store ]
      (JSON / Protobuf Artifacts)
                   │
    ┌──────────────┴──────────────┐
    ▼                             ▼
Batch Feature Pipeline       Online Feature Pipeline
 (Spark/Ray Transformations)   (Feast Stream Transformer / C++ Engine)
    │                             │
    ▼                             ▼
Offline Training Store       Online Cache Store (Redis)
 (Parquet / Iceberg)          (Evaluates pre-computed math at 1ms)
```

##### 1. Offline Parameter Computation (Spark / Ray)
* Run a distributed engine pass over historical data to compute standard transformation statistics:
  * Static capping thresholds ($p_{0.1}, p_{99.9}$).
  * Quantile boundary maps.
  * Mean/Median vectors and Yeo-Johnson $\lambda$ parameters per feature.
* Save these statistics as an immutable, versioned configuration artifact (e.g., Protobuf/JSON schema) in a model registry.

##### 2. Asynchronous Online Feature Transformation
* Compute complex transformations asynchronously on incoming feature streams (e.g., via Spark Streaming or Flink) before writing values to the low-latency cache (Redis).
* For raw features passed directly at request time, apply lightweight transformation functions using precomputed parameters. This simplifies inference logic to basic low-overhead math:
  
$$\text{Winsorize}(x) = \min(\max(x, \text{bound}_{\text{low}}), \text{bound}_{\text{high}})$$

$$\text{Log1P}(x) = \ln(1 + x)$$

##### 3. Handling Outlier Drift
* Outlier definitions naturally drift over time due to business evolution or structural distribution shifts.
* Deploy statistical monitoring jobs (e.g., calculating Population Stability Index (PSI) or Wasserstein Distance on serving log distributions) to track drift. Re-fit and update downstream transformer parameter configs asynchronously when cumulative drift metrics exceed target tolerances ($\text{PSI} > 0.2$).