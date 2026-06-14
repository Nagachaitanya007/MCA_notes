---
title: Data Preprocessing: Outliers, Missing Values, and Skewed Data
date: 2026-06-14T04:31:57.267602
---

# Data Preprocessing: Outliers, Missing Values, and Skewed Data

---

## 1. 🧱 The Core Concept

In production-scale machine learning, raw data is rarely model-ready. Data preprocessing is not a mechanical checklist; it is an optimization problem where every transformation alters the geometry of the loss surface, changes the variance of your estimators, and directly impacts downstream inference latency.

```
       [Raw Feature Vector]
                 │
                 ▼
     ┌───────────────────────┐
     │ 1. Outlier Filtering  │ ──► IQR/Mahalanobis Truncation (prevents gradient explosion)
     └───────────────────────┘
                 │
                 ▼
     ┌───────────────────────┐
     │ 2. Missing Imputation │ ──► Tree-native routing vs. Conditional Imputation
     └───────────────────────┘
                 │
                 ▼
     ┌───────────────────────┐
     │ 3. Skew Alignment     │ ──► Power Transforms (ststabilizes variance / homoscedasticity)
     └───────────────────────┘
                 │
                 ▼
      [Numerical Feature Store]
```

### Outliers: Signal vs. Stochastic Noise
An outlier is a data point that deviates significantly from the underlying generative process of the rest of the data. 

*   **Mathematical Identification**:
    *   **Univariate**: 
        *   *Z-Score*: $Z = \frac{x - \mu}{\sigma}$. Assumes normality; fails on skewed data.
        *   *Modified Z-Score*: $M_i = \frac{0.6745(x_i - \tilde{x})}{\text{MAD}}$, where $\text{MAD} = \text{median}(|x_i - \tilde{x}|)$. Highly robust to extreme values.
        *   *Interquartile Range (IQR)*: $[Q_1 - 1.5 \times \text{IQR}, Q_3 + 1.5 \times \text{IQR}]$. Distribution-agnostic but ignores joint distribution.
    *   **Multivariate**: 
        *   *Mahalanobis Distance*: $D_M(x) = \sqrt{(x - \mu)^T \Sigma^{-1} (x - \mu)}$. Accounts for covariance between features, identifying anomalies that appear normal when projected onto a single axis.
*   **Mitigation Trade-offs**:
    *   *Trimming (Dropping)*: Reduces dataset size; introduces selection bias if outliers are valid tail events (e.g., high-net-worth users in fraud detection).
    *   *Winsorizing (Clipping)*: Replaces extreme values with percentiles (e.g., 1st and 99th). Preserves sample size; artificially inflates variance at boundaries.
    *   *Robust Scaling*: $x_{scaled} = \frac{x - \text{median}(x)}{\text{IQR}}$. Keeps spatial relationships intact without squashing inline data.

### Missing Values: Mechanisms of Missingness
Imputation strategy depends entirely on the missingness mechanism. Treating all missing values as $0$ or mean-imputed is a common production anti-pattern.

| Mechanism | Definition | Mathematical Formulation | Best-Practice Mitigation |
| :--- | :--- | :--- | :--- |
| **MCAR** (Missing Completely at Random) | Missingness is independent of any observed or unobserved data. | $P(M \mid Y_{obs}, Y_{mis}) = P(M)$ | Mean/Median imputation, complete case analysis (if $<5\%$). |
| **MAR** (Missing at Random) | Missingness systematically depends on observed data, but not the missing values themselves. | $P(M \mid Y_{obs}, Y_{mis}) = P(M \mid Y_{obs})$ | Multiple Imputation by Chained Equations (MICE), KNN, MissForest, or Model-Native handling. |
| **MNAR** (Missing Not at Random) | Missingness depends directly on the unobserved missing value. | $P(M \mid Y_{obs}, Y_{mis}) \neq P(M \mid Y_{obs})$ | Pattern Mixture Models, adding missingness indicators ($I_m \in \{0, 1\}$), Heckman correction. |

### Skewed Data: Stabilizing Variance
Many parametric models (e.g., Linear/Logistic Regression, Neural Networks using MSE loss) assume homoscedasticity (constant variance of errors) and normality of residuals. High skewness causes gradients to be dominated by extreme tail values, slowing down convergence.

```
Positive (Right) Skew            Symmetric (Normal)            Negative (Left) Skew
      ▲                                 ▲                               ▲
      │  *                              │      *                        │          *
      │ * *                             │    *   *                      │        *   *
      │*   *                            │   *     *                     │       *     *
      │*     * * * *                    │  *       *                    │ * * * *     *
      └───────────────►                 └─────────────►                 └─────────────►
```

*   **Log Transformation**: $y = \log(x + c)$. Compresses right-hand tails. Only valid for positive values.
*   **Box-Cox Transformation**: 
    $$y^{(\lambda)} = \begin{cases} \frac{x^\lambda - 1}{\lambda} & \text{if } \lambda \neq 0 \\ \log(x) & \text{if } \lambda = 0 \end{cases}$$
    Requires $x > 0$. $\lambda$ is estimated via Maximum Likelihood Estimation (MLE) to maximize normality.
*   **Yeo-Johnson Transformation**: Extends Box-Cox to handle zero and negative values by incorporating piecewise modifications for $x \ge 0$ and $x < 0$.
*   **Quantile Transformer**: Maps features to a Uniform or Normal distribution using cumulative distribution functions (CDF). Highly effective at removing skew, but distorts linear relationships and distances between samples.

---

## 2. ⚙️ Under the Hood

### Data Leakage: The Silent Model Killer
Data leakage occurs when information from the holdout/test dataset is used to parameterize transformations during training.

```
❌ BAD: Global Fit (Data Leakage)
[ Train + Test Sets ] ──► Compute Global Mean/Std ──► Scale Train ──► Scale Test

     The test set's distribution parameters leak into the training process,
     yielding overly optimistic offline validation metrics.

─────────────────────────────────────────────────────────────────────────────

──► Compute Mean/Std ──► Scale Train
                         └──► Apply Saved Mean/Std ──► Scale Test
```

If you fit a scaler, power transformer, or imputer on the *entire* dataset before split, your model inherits a prior over the test set's distribution. 
*   **Impact**: Artificial inflation of offline validation metrics (e.g., AUC, RMSE) that collapses immediately upon online deployment.
*   **Engineered Prevention**: In PySpark or Scikit-Learn, transformations must be wrapped inside a `Pipeline` abstraction. Only `.fit()` the pipeline on the training split, and use `.transform()` on validation/test sets.

### Distributed Scale Bottlenecks
Calculating exact percentiles (for IQR, Winsorizing, or Median Imputation) across billions of rows is a massive computational bottleneck because it requires a global sort over distributed partitions.

*   **T-Digest & Greenwald-Khanna (GK) Algorithms**: To compute quantiles in distributed engines (e.g., Apache Spark, Presto), exact sorting is replaced with streaming centroid-based clustering (T-Digest) or rank-error bounds (GK). This reduces the memory footprint from $O(N)$ to $O(\log N)$ or $O(\frac{1}{\epsilon})$, enabling sub-linear execution times.

### Algorithmic Mechanics: Tree-Native Missing Value Routing
Modern gradient boosted decision trees (GBDTs)—specifically XGBoost and LightGBM—do not require explicit missing value imputation.

During training, for each split, XGBoost evaluates the split gain under two scenarios:
1.  Send all missing values to the Left node ($G_L$).
2.  Send all missing values to the Right node ($G_R$).

```
                      [Split Node: Feature X < Threshold]
                               /               \
            (Default: Go Left) /                 \ (Default: Go Right)
                              ▼                   ▼
                      [Left Child]             [Right Child]
                     (Includes NaNs           (Includes NaNs 
                      if GL > GR)              if GR > GL)
```

The algorithm computes the optimal split direction:
$$\mathcal{L}_{\text{split}} = \max \left( \frac{G_L^2}{H_L + \lambda} + \frac{(G_R + G_{\text{missing}})^2}{H_R + H_{\text{missing}} + \lambda}, \frac{(G_L + G_{\text{missing}})^2}{H_L + H_{\text{missing}} + \lambda} + \frac{G_R^2}{H_R + \lambda} \right) - \frac{(G_L + G_R + G_{\text{missing}})^2}{H_L + H_R + H_{\text{missing}} + \lambda}$$
Where $G$ and $H$ represent first (gradients) and second (hessians) order gradients. At inference time, if feature $X$ is missing, it is dynamically routed down the default direction learned during training. This is mathematically optimal and eliminates latency overhead from imputation layers.

---

## 3. ⚠️ The Interview Warzone

### Scenario 1: High-Throughput, Ultra-Low Latency Real-Time Ad-Click Prediction
**The Setup**: You are designing a feature engineering pipeline for an Ad-Click prediction model processing 100,000 queries per second (QPS) with an SLA of under $10\text{ms}$. User features (e.g., `historical_spend`, `time_since_last_click`) frequently contain missing values and extreme right-skewed outliers.

#### Interviewer Probing Questions:
*   "How do you handle missing values without violating the 10ms SLA?"
*   "If you use KNN imputation or MICE, how do you deploy that to production?"
*   "If we choose to use tree-native missing routing, how do you handle features that are present at training time but missing *only* in online inference due to an upstream microservice timeout?"

#### The Perfect Response (System & Algorithmic Blueprint):
"For a 100k QPS, <10ms SLA system, iterative or model-based imputers (like KNN, MICE, or MissForest) are completely out of the question due to their $O(N \cdot D)$ inference-time computational complexity. 

We have two viable paths, depending on the model architecture:

```
                          [Online Request Received]
                                      │
                   ┌──────────────────┴──────────────────┐
                   ▼                                     ▼
        [Linear/NN Architecture]               [GBDT Architecture]
                   │                                     │
         [Is feature missing?]                 [Is feature missing?]
          /                 \                           │
      (Yes) /                 \ (No)                    ▼
        ▼                     ▼                [Route Native NaN]
  [Read Pre-computed      [Apply Robust        (Zero runtime compute
  Default from Redis]     Log Transform]        overhead; ideal SLA)
        │                     │
        └──────────┬──────────┘
                   │
                   ▼
         [Inference Engine]
```

1.  **If using a Linear Model / Deep Neural Network (DNN):**
    *   **Preprocessing**: We avoid online imputation computations entirely. During the offline training pipeline, we compute the training dataset's median (robust to outliers) and save these static scalars to our low-latency Feature Store (e.g., Redis).
    *   **Inference**: If a feature is missing online (due to client-side payload omission or upstream service timeout), our feature retrieval layer falls back to the Redis pre-computed median value in $O(1)$ time. 
    *   **Transformations**: For skewed values like `historical_spend`, we pre-compute a static logarithmic transformation parameter $\log(x + 1)$ or Yeo-Johnson parameters offline and hardcode the transform function inside the online model graph (e.g., using ONNX runtime or TensorFlow Serving graphs) to avoid serializing data back and forth to an external preprocessing service.
2.  **If using a GBDT (e.g., LightGBM / XGBoost):**
    *   **Handling Missingness**: We pass raw `NaN` values directly to the model. The model's runtime engine evaluates the default split direction learned during training. This introduces **zero compute overhead** for imputation at inference time.
    *   **Upstream Timeouts**: If a feature is present during training but missing online due to an API timeout, the tree naturally routes the record based on the optimal gradient direction calculated on whatever data *was* missing during training. To make this robust, we inject artificial missingness (data dropout) during training so the model learns a robust default routing path even for high-fidelity features."

---

### Scenario 2: Highly Skewed Financial Fraud Detection with Extreme Tail Risk
**The Setup**: You are training a credit-card fraud detection model. The transaction amount (`amount`) is highly skewed, spanning from $\$0.01$ to $\$1,000,000$. Real fraud transactions are concentrated heavily in the extreme tail (outliers).

#### Interviewer Probing Questions:
*   "How will standard Z-score scaling behave on the `amount` feature? Why?"
*   "If you log-transform the transaction amount, what happens to your model's ability to isolate massive multi-million dollar fraud instances? Is it better to drop outliers beyond the 99th percentile?"

```
                         [Fraud Feature Pipeline]
                                    │
                  ┌─────────────────┴─────────────────┐
                  ▼                                   ▼
          [Drop Outliers?]                    [Log-Transform?]
                 │                                   │
      ❌ NO: Tail events are                 ❌ NO: Squashes spatial
       highly correlated with                 variance; hard to isolate
       fraud. Outliers = Signal.              massive anomalies.
                  │                                   │
                  └─────────────────┬─────────────────┘
                                    │
                                    ▼
                          [Optimal Strategy]
               ┌─────────────────────────────────────┐
               │ 1. Quantile/Yeo-Johnson Transform   │
               │ 2. Isolation Forest Anomaly Score   │
               │ 3. Explicit Outlier Flag Feature    │
               └─────────────────────────────────────┘
```

#### The Perfect Response (A senior staff-level analysis):
"In fraud detection, **outliers are often the primary signal**. Standard heuristics must be discarded.

1.  **Z-Score Deconstruction**: 
    If we apply standard $Z = \frac{x - \mu}{\sigma}$ to the `amount` feature, the extreme right-skew (the multi-million dollar transactions) will heavily pull the mean $\mu$ to the right and massively inflate the standard deviation $\sigma$. As a result, typical fraudulent transactions in the $\$500$ to $\$5,000$ range will be compressed into a tight band near zero. This completely strips the model of its ability to distinguish normal $\$10$ transactions from suspicious $\$2,000$ transactions.
2.  **Mitigation Strategy (No Trimming)**:
    We absolutely **cannot drop or winsorize outliers**. Dropping points above the 99th percentile removes the exact high-value fraud signals we are trying to detect.
3.  **Optimal Transformation Architecture**:
    *   We preserve the original scale by creating an auxiliary feature: `is_extreme_amount = I(amount > P99)`. This explicitly signals the model to treat these cases as a separate regime.
    *   To normalize the feature for gradient descent optimization without losing separation in the tail, we use a **RobustScaler** (median and IQR baseline):
        $$x_{\text{robust}} = \frac{x - \text{median}(x)}{\text{IQR}}$$
    *   Alternatively, we apply a dual-representation strategy: feed the raw `amount` into tree models (which are scale-invariant and split naturally on thresholds), while feeding a Yeo-Johnson transformed version into neural/linear models to keep gradient updates stable."

---

### Scenario 3: Production Pipeline Leakage and Scale Post-Mortem
**The Setup**: A machine learning pipeline trained offline achieved $0.92$ ROC-AUC. Upon production release to a distributed streaming pipeline, the online ROC-AUC dropped to $0.61$. The pipeline performs standard normalization and KNN imputation on missing user telemetry profiles.

#### Interviewer Probing Questions:
*   "Walk me through how data leakage could have occurred in this preprocessing setup."
*   "How would you diagnose and fix this leakage in a distributed Spark environment?"
*   "How does KNN scale as a production imputation strategy on 100M+ records?"

#### The Perfect Response (Diagnostic & Architectural Resolution):
"An offline-to-online metric collapse from $0.92$ to $0.61$ is a classic symptom of **data leakage** and **imputation drift**.

#### 1. The Diagnosis of Leakage
The offline preprocessing script likely calculated the global mean, standard deviation, and KNN neighbor index over the entire dataset *prior* to splitting the data into cross-validation folds or train/test sets:

```python
# ❌ CODE LEAKAGE EXPOSURE
df = load_data()
# This computes global statistics over both train and test distributions!
imputer = KNNImputer(n_neighbors=5).fit(df) 
scaler = StandardScaler().fit(df)

train_df, test_df = train_test_split(df)
```

By fitting the `KNNImputer` and `StandardScaler` globally, the feature values of the test set directly influenced the imputed values and scaling factors of the training set. Consequently, the model memorized relationships within the leaked test set distributions. In production, incoming real-time records are imputed using only historical neighbors, removing this leakage and causing the performance collapse.

#### 2. The Algorithmic Scale Failure
Using `KNNImputer` at scale ($100\text{M}+$ records) is an $O(D \cdot N^2)$ training-time complexity disaster. During serving, finding the nearest neighbors for a single real-time inference request requires scanning the entire historical training set unless we construct approximate nearest neighbor (ANN) indexes like HNSW, which introduces latency overhead and memory bloat.

#### 3. The Production-Grade Solution
We rewrite our distributed pipeline using Spark ML Pipelines to guarantee strict isolation. We replace `KNNImputer` with a highly scalable alternative (e.g., a median/indicator pipeline or a distributed tree model) and save the pipeline state as a self-contained artifact:

```python
from pyspark.ml import Pipeline
from pyspark.ml.feature import Imputer, StandardScaler, VectorAssembler

# Split first to prevent ANY leakage
train_df, test_df = raw_df.randomSplit([0.8, 0.2], seed=42)

# Define estimators inside a Pipeline. They will ONLY fit on the training split.
imputer = Imputer(
    inputCols=["telemetry_1", "telemetry_2"],
    outputCols=["imputed_tel_1", "imputed_tel_2"]
).setStrategy("median")

assembler = VectorAssembler(
    inputCols=["imputed_tel_1", "imputed_tel_2"], 
    outputCol="features"
)

scaler = StandardScaler(
    inputCol="features", 
    outputCol="scaled_features", 
    withStd=True, 
    withMean=True
)

# Bind into a strict evaluation pipeline
preprocessing_pipeline = Pipeline(stages=[imputer, assembler, scaler])

# Fit on training split ONLY
pipeline_model = preprocessing_pipeline.fit(train_df)

# Apply downstream transformations without leakage
clean_train = pipeline_model.transform(train_df)
clean_test = pipeline_model.transform(test_df) # Uses training-derived median and scale factors
```

To deploy this online, we serialize the fitted `pipeline_model` (e.g., to MLeap or ONNX format) and load it into our serving containers. This ensures that the online transformation uses the exact static parameters computed offline from the training split, completely eliminating data leakage."