---
title: Data Preprocessing: Outliers, Missing Values, and Skewed Data
date: 2026-07-03T04:32:05.405823
---

# Data Preprocessing: Outliers, Missing Values, and Skewed Data

---

## 1. 🧱 The Core Concept (Basics Refresh)

In production machine learning systems, raw data is rarely model-ready. It is noisy, incomplete, and structurally biased. Data preprocessing is the systematic practice of transforming raw features into clean, high-signal representations that align with the structural assumptions of downstream learning algorithms.

```
       ┌────────────────────────────────────────────────────────┐
       │                   Raw Feature Matrix                   │
       └───────────────────────────┬────────────────────────────┘
                                   │
         ┌─────────────────────────┼─────────────────────────┐
         ▼                         ▼                         ▼
┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
│    Outliers     │       │ Missing Values  │       │   Skewed Data   │
│  (Noisy Signals)│       │  (Incomplete)   │       │ (Non-Normal/Tail)│
└────────┬────────┘       └────────┬────────┘       └────────┬────────┘
         │                         │                         │
         ▼                         ▼                         ▼
┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
│ • Z-Score / IQR │       │ • MCAR/MAR/MNAR │       │ • Box-Cox       │
│ • IsoForest     │       │ • MICE / KNN    │       │ • Yeo-Johnson   │
│ • Winsorization │       │ • Imputation    │       │ • Log1p         │
└────────┬────────┘       └────────┬────────┘       └────────┬────────┘
         │                         │                         │
         └─────────────────────────┼─────────────────────────┘
                                   ▼
       ┌────────────────────────────────────────────────────────┐
       │             Downstream Machine Learning Model          │
       └────────────────────────────────────────────────────────┘
```

### Outliers
Outliers are data points that deviate significantly from the central tendency of a feature's distribution. They introduce high variance, pull regression lines away from the true relationship, and destabilize optimization techniques (such as Gradient Descent).

*   **Detection**:
    *   **Z-Score**: Measures how many standard deviations a point is from the mean. Assumes normality:
        $$Z = \frac{x - \mu}{\sigma}$$
    *   **Interquartile Range (IQR)**: More robust to extreme values than Z-score. Outliers are defined as:
        $$x < Q_1 - 1.5 \times \text{IQR} \quad \text{or} \quad x > Q_3 + 1.5 \times \text{IQR}$$
        where $\text{IQR} = Q_3 - Q_1$.
    *   **Isolation Forest**: An unsupervised tree-based algorithm that isolates observations by randomly selecting a feature and split value. Outliers require fewer splits to isolate.
    *   **DBSCAN**: Density-based clustering where points in low-density regions (noise) are flagged as outliers.
*   **Treatment**:
    *   **Trimming (Dropping)**: Removing outlier rows. *Risk: Can introduce bias if outliers contain actual structural patterns.*
    *   **Winsorization**: Capping extreme values at a specific percentile (e.g., replacing values above the 99th percentile with the 99th percentile value).
    *   **Transformation**: Applying mathematical functions (e.g., log, box-cox) to dampen the magnitude of extreme values.

### Missing Values
Missing data degrades model performance and causes runtime execution failures in many popular libraries (e.g., scikit-learn). Understanding *why* data is missing dictates how we resolve it.

*   **Taxonomy of Missingness**:
    *   **Missing Completely at Random (MCAR)**: The probability of missingness is entirely independent of any observed or unobserved data. Example: A laboratory sample drops and breaks by accident.
    *   **Missing at Random (MAR)**: The probability of missingness depends systematically on other *observed* variables, but not the missing value itself. Example: Younger users are less likely to disclose their income on a survey, but we have their age.
    *   **Missing Not at Random (MNAR)**: The probability of missingness depends directly on the unobserved value itself. Example: High-income earners deliberately leave the income field blank due to privacy concerns.
*   **Handling Strategies**:
    *   **Deletion (Listwise/Pairwise)**: Simple, but introduces significant bias unless data is strictly MCAR and the missingness rate is low ($< 5\%$).
    *   **Simple Imputation**: Replacing missing values with a central statistic (mean, median, mode) or a constant (e.g., `-999`). Simple to implement but collapses variance and distorts correlations.
    *   **Advanced Imputation (KNN, MICE, Deep/Iterative Imputation)**: Reconstructing values using predictive models based on other features. High accuracy but computationally expensive at scale.
    *   **Missingness Indicator Columns**: Creating a binary helper column indicating whether the value was missing ($I_{\text{missing}} \in \{0, 1\}$). This allows models to learn the pattern of missingness directly (highly crucial for MNAR).

### Skewed Data
Skewness measures the asymmetry of a feature's probability distribution around its mean. Linear models, neural networks, and distance-based metrics perform optimal parameter updates when features are normally distributed (homoscedasticity).

```
         Positive Skew (Right)                     Negative Skew (Left)
         
          ▲                                         ▲
          │   *                                     │             *
          │  *  *                                   │           *   *
          │ *     *                                 │         *       *
          │*        *                               │       *          *
          │*          * * *                         │ * * *             *
          └─────────────────────►                   └───────────────────►
               Tail to the Right                        Tail to the Left
```

*   **Impact on Models**:
    *   **Linear/Logistic Regression & Neural Networks**: Skewed features distort the loss landscape, leading to unstable gradient updates, slower convergence, and poor generalization.
    *   **Distance-based models (KNN, SVM, K-Means)**: Highly skewed variables dominate distance metrics, overshadowing other features.
    *   **Tree-based models (XGBoost, Random Forest)**: Monotonic transformations do not affect tree-based splits, making them highly robust to skewness.
*   **Transformations**:
    *   **Log Transform**: $\tilde{x} = \ln(x + c)$. Compresses the range of wide-ranging variables. Requires $x > 0$.
    *   **Square Root Transform**: $\tilde{x} = \sqrt{x}$. Moderate transformation power, handles zero values.
    *   **Box-Cox**: Parametric power transform that finds the optimal $\lambda$ to stabilize variance and normalize data:
        $$y^{(\lambda)} = \begin{cases} \frac{y^\lambda - 1}{\lambda} & \text{if } \lambda \neq 0 \\ \ln(y) & \text{if } \lambda = 0 \end{cases}$$
        *Strict requirement: $y > 0$.*
    *   **Yeo-Johnson**: Extension of Box-Cox that accommodates zero and negative values.

---

## 2. ⚙️ Under the Hood (Internal Mechanics & Architecture)

### A. Mathematical Underpinnings of Transformations

#### 1. Yeo-Johnson Optimization Loop
The Yeo-Johnson transform optimizes its parameter $\lambda$ using Maximum Likelihood Estimation (MLE). For a given feature vector $y = [y_1, ..., y_n]^T$, the transform is defined as:

$$\psi(\lambda, y_i) = \begin{cases} 
\frac{(y_i + 1)^\lambda - 1}{\lambda} & \text{if } \lambda \neq 0, y_i \geq 0 \\ 
\ln(y_i + 1) & \text{if } \lambda = 0, y_i \geq 0 \\ 
-\frac{(1 - y_i)^{2 - \lambda} - 1}{2 - \lambda} & \text{if } \lambda \neq 2, y_i < 0 \\ 
-\ln(1 - y_i) & \text{if } \lambda = 2, y_i < 0 
\end{cases}$$

The algorithm searches for the parameter $\hat{\lambda}$ that minimizes the negative log-likelihood function of a normal distribution fit to the transformed data:

$$\mathcal{L}(\lambda) = -\frac{n}{2} \ln(\hat{\sigma}^2(\lambda)) + (\lambda - 1) \sum_{i=1}^n \text{sgn}(y_i) \ln(|y_i| + 1)$$

where $\hat{\sigma}^2(\lambda)$ is the sample variance of the transformed features $\psi(\lambda, y)$. In practice, frameworks like scikit-learn optimize this via Brent's scalar minimization method.

#### 2. Isolation Forest Isolation Metric
An Isolation Forest constructs an ensemble of Isolation Trees (iTrees). The anomaly score $s(x, n)$ for an instance $x$ given sample size $n$ is defined mathematically as:

$$s(x, n) = 2^{-\frac{\mathbb{E}(h(x))}{c(n)}}$$

Where:
*   $h(x)$ is the path length (number of edges $x$ traverses from the root to an external termination node).
*   $\mathbb{E}(h(x))$ is the average path length of $x$ across a collection of iTrees.
*   $c(n)$ is the average path length of an unsuccessful search in a Binary Search Tree (BST) built on $n$ nodes:
    $$c(n) = 2 \ln(n - 1) + 0.5772156649 \text{ (Euler-Mascheroni constant)} - \frac{2(n - 1)}{n}$$

```
Anomaly Score s(x, n) Distribution:
s -> 1 : Path length is very short -> Highly likely to be an anomaly.
s -> 0.5 : Path length is near the average BST depth -> Safe, normal point.
s -> 0 : Path length is long -> Definitely a normal point.
```

### B. Computational Tradeoffs & Algorithmic Complexity

| Preprocessing Technique | Time Complexity (Train) | Time Complexity (Inference) | Space Complexity | Memory/Compute Bottleneck |
| :--- | :--- | :--- | :--- | :--- |
| **Simple Mean/Median** | $\mathcal{O}(N \cdot D)$ | $\mathcal{O}(D)$ | $\mathcal{O}(D)$ | Out-of-core calculations for extremely large tables. |
| **KNN Imputation** | $\mathcal{O}(N^2 \cdot D)$ | $\mathcal{O}(N \cdot D)$ | $\mathcal{O}(N \cdot D)$ | High inference latency; requires storing the training set. |
| **MICE (Iterative)** | $\mathcal{O}(M \cdot I \cdot N \cdot D^2)$ | $\mathcal{O}(M \cdot D^2)$ | $\mathcal{O}(D^2)$ | Computationally expensive for high dimensions ($D$). |
| **Isolation Forest** | $\mathcal{O}(T \cdot \psi \log \psi)$ | $\mathcal{O}(T \cdot \log \psi)$ | $\mathcal{O}(T \cdot \psi)$ | Subsampling size $\psi$ and tree count $T$ limit memory footprint. |
| **Yeo-Johnson MLE** | $\mathcal{O}(Iter \cdot N \cdot D)$ | $\mathcal{O}(D)$ | $\mathcal{O}(D)$ | Slow execution due to iterative search optimization. |

*Notation: $N$ = Number of training samples, $D$ = Number of features, $M$ = Number of imputation iterations, $I$ = Number of estimators, $T$ = Number of trees in Isolation Forest, $\psi$ = Subsample size.*

### C. Pipeline Architecture: Preventing Data Leakage in Production

A classic mistake in production engineering is calculating preprocessing statistics over the *entire* dataset before split partitioning, or updating statistics dynamically at inference time. This causes **Data Leakage**, where information from the validation or test sets leaks into the training step, creating overly optimistic performance metrics that degrade instantly in production.

#### Production Pipeline Invariant: Fit on Train, Transform on Train/Test/Inference

```
                         [ Raw Raw Training Data ]
                                     │
                                     ▼
                     ┌──────────────────────────────┐
                     │   Fit & Save Parameters:     │
                     │   - Median = 42.5            │
                     │   - Power lambda = 0.25      │
                     └───────────────┬──────────────┘
                                     │
                     ┌───────────────┴──────────────┐
                     ▼                              ▼
             Transform Train                Transform Test
                     │                              │
                     ▼                              ▼
          [ Standardized Train ]         [ Standardized Test ]
```

##### Stateful Pipeline Storage Architecture:
To ensure alignment, stateful parameters derived during training ($\mu, \sigma$, quantiles, Yeo-Johnson $\lambda$) must be compiled into static config artifacts (Protobuf, JSON, or ONNX runtimes) and served alongside the model artifact.

```python
# Production-Grade Stateful Pipeline Pattern
from sklearn.base import BaseEstimator, TransformerMixin
import numpy as np

class SafeWinsorizer(BaseEstimator, TransformerMixin):
    def __init__(self, lower_quantile=0.01, upper_quantile=0.99):
        self.lower_quantile = lower_quantile
        self.upper_quantile = upper_quantile
        
    def fit(self, X, y=None):
        # Calculate percentiles strictly on the training partition
        self.lower_bounds_ = np.percentile(X, self.lower_quantile * 100, axis=0)
        self.upper_bounds_ = np.percentile(X, self.upper_quantile * 100, axis=0)
        return self
        
    def transform(self, X):
        # Clip incoming inference arrays using the saved, frozen training boundaries
        return np.clip(X, self.lower_bounds_, self.upper_bounds_)
```

During real-time inference, the prediction service ingests a singular request vector, runs the feature values through the cached pipeline (`SafeWinsorizer.transform()`), and forwards the preprocessed payload to the model predictor. **We never compute quantiles or mean values on the incoming live inference request or batch.**

---

## 3. ⚠️ The Interview Warzone (Scenario-Based Deep Dives)

### Scenario 1: High-throughput real-time ad-click prediction with missing historical signals

> **Interviewer**: We are building a high-throughput, real-time ad-click prediction system running at $100,000$ queries per second (QPS). Several high-signal historical features (e.g., historical user CTR) are frequently missing due to cold-start users or logging pipeline drops. Latency budget is hard-capped at $10\text{ ms}$. How do you design the missing value strategy?

#### The Candidate Trap
*   Suggesting KNN or MICE imputation because they are "highly accurate statistical methods." At $100\text{ ms}$ baseline, executing a KNN distance search over millions of training rows on a live $10\text{ ms}$ budget will completely crash the inference service.
*   Dropping rows with missing CTRs, which would throw away up to $40\%$ of potential ad inventory and destroy revenue.

#### Probing Questions
*   *How does your choice of imputation impact downstream prediction latency?*
*   *What are the structural differences in how linear classifiers vs. tree-boosted models handle these missing values?*
*   *If missingness is non-random (e.g., new users have missing CTRs systematically), does your approach preserve this signal?*

#### The "Senior Staff" Response

##### 1. Mathematical Classification of Missingness
In ad-click networks, missing historical CTR is fundamentally **MNAR (Missing Not at Random)**. The missingness indicates a cold-start state (new user or non-tracked session), which is highly predictive of lower base CTR. Removing this or relying purely on statistical imputation removes this crucial signal.

##### 2. Low-Latency Preprocessing Architecture
To satisfy the $10\text{ ms}$ p99 SLA, we must completely avoid dynamic model-based imputation at inference runtime. Instead, we use a hybrid **Indicator-Constant Imputation** approach:

*   **Feature Transformation**:
    *   For the raw continuous feature $x_{\text{CTR}}$, we map it to:
        $$\tilde{x}_{\text{CTR}} = \begin{cases} x_{\text{CTR}} & \text{if present} \\ 0.0 & \text{if missing} \end{cases}$$
    *   We introduce an explicit binary missingness indicator:
        $$I_{\text{missing\_CTR}} = \begin{cases} 0 & \text{if } x_{\text{CTR}} \text{ is present} \\ 1 & \text{if } x_{\text{CTR}} \text{ is missing} \end{cases}$$

##### 3. Downstream Model Selection
*   **If using Logistic Regression**: The indicator variable allows the linear optimizer to assign a specific weight ($w_{\text{missing\_CTR}}$) to the cold-start state, mitigating the bias of imputing with a zero or mean.
*   **If using Tree-based models (e.g., LightGBM / XGBoost)**: We leverage native missing value handling (sparsity-aware splitting). During training, these frameworks evaluate placing all missing values in either the left or right child node, choosing the split direction that maximizes gain:
    $$\mathcal{L}_{\text{split}} = \max \left( \mathcal{G}_{\text{L+missing}} + \mathcal{G}_{\text{R}}, \mathcal{G}_{\text{L}} + \mathcal{G}_{\text{R+missing}} \right)$$
    This preserves the raw MNAR signal natively with zero added CPU footprint at inference.

##### 4. Low-Latency Pipeline Integration
We pre-compute and store default global constants (like historical averages) in our Feature Store (e.g., Feast/Tecton) for offline training. At online inference, if the live feature retrieval fails (resulting in a cache miss or null), the system falls back to the static indicator schema in $\mathcal{O}(1)$ operations, completely avoiding complex in-memory imputations.

---

### Scenario 2: Fraud detection with extreme class imbalance and massive outliers in transaction amounts

> **Interviewer**: You are building a real-time card fraud detection system. The feature `transaction_amount` ranges from $\$0.01$ to $\$1,000,000.00$. The raw distribution has extreme positive skewness, and the minority class (fraud) is highly concentrated in both very low (test charges) and very high (large-scale theft) transactions. Your model is a Logistic Regression classifier. How do you handle outliers and skewness?

#### The Candidate Trap
*   Suggesting standard Z-score filtering to delete outliers outside $3\sigma$. In fraud detection, **outliers are often the target signal**. Deleting them removes the high-value fraud instances you need to catch.
*   Applying a standard Log transformation ($\log(x)$) without considering the $\$0.00$ transactions or negative adjustments, causing NaN errors.
*   Failing to connect feature engineering decisions with the specific model family (Logistic Regression).

#### Probing Questions
*   *Why will standard scale transformations like MinMaxScaler or StandardScaler fail on this distribution when using a linear classifier?*
*   *What are the specific mathematical issues that arise if we do not transform highly skewed continuous variables in logistic regression?*

#### The "Senior Staff" Response

##### 1. Diagnostics & Model Constraints
Logistic regression optimizes weights using gradient descent on the log-likelihood loss:

$$\nabla_w \mathcal{L} = \frac{1}{N} \sum_{i=1}^N (h_w(x^{(i)}) - y^{(i)}) x^{(i)}$$

If $x$ spans 8 orders of magnitude (from $10^{-2}$ to $10^{6}$), the gradients with respect to the transaction amount will be massive, dominating the parameter updates. This forces the learning rate to be extremely small to prevent gradient explosion, which prevents the weights of other high-signal features (e.g., location mismatches) from converging.

##### 2. The Multi-Step Preprocessing Pipeline

```
Raw Transaction Amount ────────► Yeo-Johnson Transform ────────► Quantile Discretization ────────► Logistic Regression
 ($0.01 to $1,000,000)               (Normalize Skew)             (Capture Non-Linearity)
```

###### Step A: Outlier Preservation via Monotonic Non-linear Scaling
Instead of deleting outliers, we compress their relative distance using the **Yeo-Johnson transformation**. This handles $0$ values (free trials/promotional sign-ups) gracefully and stabilizes variance. We do not use Box-Cox because it cannot handle $0.00$ values unless shifted artificially.

###### Step B: Feature Binning / Discretization
Because fraud has a non-monotonic relationship with transaction size (concentrated at the extreme low and extreme high ends), a simple linear model cannot easily draw a single line to separate both cases. We transform the continuous feature into categorical bins using quantile-based bucketing:

$$x_{\text{binned\_amount}} = \text{Quantile-Discretize}(x_{\text{transformed}}, \text{bins}=10)$$

This is followed by One-Hot Encoding:

$$\mathbf{x}_{\text{encoded}} = [x_{\text{bin\_1}}, x_{\text{bin\_2}}, \dots, x_{\text{bin\_10}}]^T$$

This representation allows the linear model to learn distinct weights for the extreme low-value bin ($w_{\text{bin\_1}}$) and the extreme high-value bin ($w_{\text{bin\_10}}$), capturing the non-linear relationship without switching to a complex non-linear model.

###### Step C: Robust Scaling
For any remaining raw continuous features, we apply robust scaling using statistics that are resistant to outliers:

$$\tilde{x} = \frac{x - \text{Median}(X)}{\text{IQR}(X)}$$

This ensures the scaling parameters themselves are not warped by outliers during the training phase.

---

### Scenario 3: Robust preprocessing pipeline for a 100TB Spark scale dataset with heavy partition skew

> **Interviewer**: You are training an XGBoost model on a 100TB dataset in PySpark. One of your features, `user_session_count`, is extremely skewed: $99.9\%$ of users have $\le 5$ sessions, but a few bot accounts have $> 100,000,000$ sessions. When running your preprocessing job, it consistently crashes with Executor Out-Of-Memory (OOM) errors during the scaling phase. How do you diagnose and redesign this pipeline?

#### The Candidate Trap
*   Recommending a call to `.collect()` on the Spark DataFrame to calculate mean and variance. This brings 100TB of data to the driver node, causing an instant driver OOM crash.
*   Blaming the issue on "insufficient hardware" and simply requesting larger instances, rather than addressing the structural data skew.

#### Probing Questions
*   *Why does skewness in a feature distribution cause JVM memory issues in a distributed system during scaling or partitioning?*
*   *How do Spark's transformations (like bucketizer or standard scaler) handle data distribution across partitions?*

#### The "Senior Staff" Response

##### 1. Root Cause Analysis of Spark OOM on Skewed Data
The OOM issue is driven by **Partition Skew**. When Spark performs wide transformations (shuffling data across partitions based on a key) or computes global statistics, it distributes data points into partitions.

If a feature contains massive outlier values, operations like sorting, percentile computation, or join keys associated with these outlier records end up concentrated on a single executor task (e.g., the partition containing the bot accounts). This executor runs out of JVM heap space and crashes, while the other executors remain idle.

```
Incoming Rows:
[Bot: 100M] ─────────┐
[Bot: 50M]  ─────────┼─► [ Executor 1 Partition (Hotspot) ] ──► OOM Crash!
[User A: 2] ─────────┘
[User B: 1] ───────────► [ Executor 2 Partition (Empty) ]
[User C: 5] ───────────► [ Executor 3 Partition (Empty) ]
```

##### 2. The Redesigned Distributed Preprocessing Architecture

###### Step A: Outlier Capping at the Source via Approximate Quantiles
Rather than computing exact percentiles—which requires a costly global sort across the cluster—we use the Greenwald-Khanna algorithm to compute highly accurate approximate percentiles. This runs in parallel with a single pass over the dataset:

```python
# Compute approximate 99.99th percentile with 0.001 relative error tolerance
approx_99_99 = df.stat.approxQuantile("user_session_count", [0.9999], 0.001)[0]

# Clip the outliers in a narrow transformation (no shuffling required)
from pyspark.sql.functions import col, when
df_capped = df.withColumn(
    "user_session_count_capped",
    when(col("user_session_count") > approx_99_99, approx_99_99)
    .otherwise(col("user_session_count"))
)
```

Because `when().otherwise()` is a narrow transformation, it executes entirely within the local executor partitions without triggering a shuffle, preventing OOM failures.

###### Step B: Log-Transforming to Resolve Skew Natively
We apply a vectorized `log1p` transformation to compress the dynamic range of the data, reducing the variance across partitions:

```python
from pyspark.sql.functions import log1p
df_transformed = df_capped.withColumn(
    "log_user_session_count", 
    log1p(col("user_session_count_capped"))
)
```

###### Step C: Two-Pass Aggregation for Standard Scaling
Instead of using standard scaling methods that might trigger full shuffles, we compute mean and variance by leveraging Spark’s built-in `Summarizer` API within the MLlib ecosystem. This performs local partition aggregations first (map-side reduction) before sending aggregate scalars to the driver, minimizing network traffic:

```python
from pyspark.ml.feature import StandardScaler
from pyspark.ml.feature import VectorAssembler

assembler = VectorAssembler(
    inputCols=["log_user_session_count"], 
    outputCol="features_vector"
)
df_vector = assembler.transform(df_transformed)

# Scaler uses distributed map-side aggregation to prevent executor memory spikes
scaler = StandardScaler(
    inputCol="features_vector", 
    outputCol="scaled_features", 
    withStd=True, 
    withMean=True
)
scaler_model = scaler.fit(df_vector)
```

This ensures our 100TB pipeline runs end-to-end using efficient, distributed operations without memory bottlenecks.