---
title: Engineering Study Note: Data Preprocessing at Scale
date: 2026-07-08T04:31:55.547335
---

# Engineering Study Note: Data Preprocessing at Scale
## Handling Outliers, Missing Values, and Skewed Data

---

## 1. 🧱 The Core Concept (Basics Refresh)

In academic environments, data preprocessing is often treated as a series of recipes: "impute missing values with the mean, remove outliers beyond 3 standard deviations, and apply a log transform to skewed data." 

In production systems operating at FAANG scale, **naive application of these rules is a primary driver of silent model degradation, data leakage, and production outages.**

```
                           Raw Data Ingestion
                                   │
         ┌─────────────────────────┼─────────────────────────┐
         ▼                         ▼                         ▼
 ┌──────────────┐          ┌──────────────┐          ┌──────────────┐
 │   Outliers   │          │Missing Values│          │ Skewed Data  │
 └──────┬───────┘          └──────┬───────┘          └──────┬───────┘
        │                         │                         │
        ▼                         ▼                         ▼
  Signal vs Noise         MCAR / MAR / MNAR          Loss Surfaces &
  (Heavy Tails)          (Modeling Missingness)     Gradient Variance
```

### Outliers: Signal vs. Noise
An outlier is an observation that deviates significantly from other observations. In production, we categorize them into two groups:
1. **Structural Anomalies (Noise):** Data corruption, telemetry bugs, or upstream pipeline errors (e.g., a logging system reporting a latency of `-1` seconds or a user age of `999`).
2. **Natural Extremes (Signal):** Real but rare occurrences (e.g., a whale buyer spending $\$100,000$ in a free-to-play mobile game, or a sudden traffic spike during a DDoS attack). 

*The Production Sin:* Automatically deleting outliers. If you delete real, heavy-tailed data (e.g., in fraud detection or financial transactions), you strip the model of the exact signal it needs to learn rare events.

### Missing Values: The Taxonomy of Absence
Values are rarely missing at random. To handle them correctly, you must diagnose the underlying missingness mechanism:

*   **Missing Completely at Random (MCAR):** The probability of missingness is entirely independent of any observed or unobserved data. *Example:* A physical sensor momentarily loses power due to random thermal noise.
*   **Missing at Random (MAR):** The probability of missingness depends on observed features, but not the missing value itself. *Example:* Female survey respondents are statistically less likely to report their weight, but this probability can be fully explained by their reported gender and age.
*   **Missing Not at Random (MNAR):** The probability of missingness depends on the unobserved value itself. *Example:* High-income individuals refuse to disclose their salary on a tax survey. 

*The Production Sin:* Blindly imputing the mean. If a feature is MNAR, imputing a static value without preserving a missingness indicator destroys the structural signal of *why* the data was missing, leading to highly biased models.

### Skewed Data: Loss Surfaces & Gradient Variance
Skewed distributions (e.g., power-law, log-normal) present severe optimization challenges for parametric models:

$$\text{Skewness} = E\left[\left(\frac{X - \mu}{\sigma}\right)^3\right]$$

*   **Impact on Linear & Neural Models:** Highly skewed features result in highly skewed loss surfaces. Gradients computed on extreme values will dominate the weight updates, leading to unstable training, slow convergence, or exploding gradients.
*   **Impact on Tree-Based Models:** Tree algorithms (XGBoost, LightGBM) are invariant to monotonic transformations of individual features because they split on ordinal rank. However, extreme skewness still compresses the split search space and can lead to sub-optimal binning during histogram construction at scale.

---

## 2. ⚙️ Under the Hood (Internal Mechanics & Architecture)

### Outliers: Mathematical Detection and Capping

#### Median Absolute Deviation (MAD)
For non-normal or skewed distributions, the classic $3\sigma$ (Z-score) threshold is useless because the mean and standard deviation are themselves highly sensitive to outliers. Instead, we use the robust **Median Absolute Deviation (MAD)**:

$$\text{MAD} = \text{median}(|X_i - \text{median}(X)|)$$

To scale MAD to act as a consistent estimator for the standard deviation under a normal distribution, we multiply by a scaling factor ($k \approx 1.4826$):

$$\text{Modified Z-Score} = M_i = \frac{0.6745(X_i - \text{median}(X))}{\text{MAD}}$$

Observations with $|M_i| > 3.5$ are typically flagged as outliers.

#### Isolation Forest
For multivariate outlier detection, we isolate observations by randomly selecting a feature and split value. Because anomalies require fewer random splits to isolate, they appear closer to the root of the trees.

```
       [Normal Data Point]                     [Anomaly Point]
          Root (Depth 0)                       Root (Depth 0)
             /       \                            /       \
           Split1    Split2                     Split1   [Isolated!] (Path=1)
          /    \     /    \
        ...    ...  ...   ... (Path Length ~ 12)
```

The anomaly score $s(x, n)$ for a sample $x$ over a dataset of size $n$ is defined as:

$$s(x, n) = 2^{-\frac{E(h(x))}{c(n)}}$$

Where $E(h(x))$ is the average path length across all trees, and $c(n)$ is the average path length of an unsuccessful search in a Binary Search Tree (BST) built on $n$ nodes:

$$c(n) = 2\ln(n - 1) + 0.5772156649 - \frac{2(n - 1)}{n}$$

*   If $s \approx 1$, the path length is highly compressed $\to$ anomaly.
*   If $s \ll 0.5$, the path length is deep $\to$ normal instance.

---

### Missing Values: Imputation Mechanics & Information Preservation

When imputing missing values, we must preserve the data's original distribution while preventing information loss.

#### Multivariate Imputation by Chained Equations (MICE)
Instead of static imputation, MICE models each feature with missing values as a function of all other features in an iterative loop:

```
Initialization: Fill missing values with median.
For iteration 1...K:
  For each feature j with missing values:
    1. Isolate observed values of y = X[:, j] and corresponding predictors X_minus_j.
    2. Fit a regressor f(X_minus_j) -> y.
    3. Predict the missing values in y using the trained f.
    4. Update X[:, j] with new predictions.
```

#### The Missingness Indicator
For any imputed feature $X_j$, we **must** instantiate a binary helper feature $I_j$:

$$I_{ij} = \begin{cases} 1 & \text{if } X_{ij} \text{ was originally missing} \\ 0 & \text{otherwise} \end{cases}$$

This transforms an MNAR problem into a MAR/MCAR-equivalent structure for downstream learners by explicitly representing the structural absence of data.

---

### Skewed Data: Mathematical Transforms

#### Box-Cox Transformation
Applicable *only* for strictly positive data ($x > 0$):

$$y^{(\lambda)} = \begin{cases} \frac{x^\lambda - 1}{\lambda} & \text{if } \lambda \neq 0 \\ \ln(x) & \text{if } \lambda = 0 \end{cases}$$

The optimal parameter $\lambda$ is estimated using Maximum Likelihood Estimation (MLE) by maximizing:

$$L(\lambda) = -\frac{n}{2} \ln(s^2(\lambda)) + (\lambda - 1) \sum_{i=1}^n \ln(x_i)$$

#### Yeo-Johnson Transformation
Extends Box-Cox to support zero and negative values:

$$\psi(\lambda, x) = \begin{cases} \frac{(x + 1)^\lambda - 1}{\lambda} & \text{if } \lambda \neq 0, x \ge 0 \\ \ln(x + 1) & \text{if } \lambda = 0, x \ge 0 \\ -\frac{(-x + 1)^{2 - \lambda} - 1}{2 - \lambda} & \text{if } \lambda \neq 2, x < 0 \\ -\ln(-x + 1) & \text{if } \lambda = 2, x < 0 \end{cases}$$

---

### Architectural Design & Preventing Data Leakage

**Data Leakage** occurs when information from the validation or test sets is inadvertently used during training. 

```
               ┌────────────────────────────────────────┐
               │              Target Data               │
               └───────────────────┬────────────────────┘
                                   │
                         [Random Train/Test Split]
                                   │
                 ┌─────────────────┴─────────────────┐
                 ▼                                   ▼
        ┌─────────────────┐                 ┌─────────────────┐
        │   Train Split   │                 │   Test Split    │
        └────────┬────────┘                 └────────┬────────┘
                 │                                   │
           [.fit_transform()]                    [.transform()]
                 │                                   │
                 ▼                                   ▼
     Calculate parameters:                 Apply parameters:
     - Mean / Median                       - Use Train Mean/Median
     - MAD / Percentiles                   - Use Train MAD/Percentiles
     - Box-Cox Lambda                      - Use Train Lambda
                 │                                   │
                 └───────────────► ─── ──────────────┘
                               (No Leakage)
```

In a production pipeline, transformations must be decoupled into two stages:
1.  **Fit Phase:** Compute statistical properties (e.g., medians, MAD, $\lambda$) *only* on the training split.
2.  **Transform Phase:** Apply those pre-computed parameters to the training, validation, test, and real-time inference pipelines. **Never recompute stats on the validation set or inference payload.**

#### Production-Grade Python Implementation
Below is a highly optimized, scikit-learn compatible custom transformer that handles outliers via MAD-based capping, missing values via median imputation with missingness flags, and skewness via the Yeo-Johnson transform, entirely free of data leakage.

```python
import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.preprocessing import PowerTransformer

class RobustPreprocessor(BaseEstimator, TransformerMixin):
    def __init__(self, mad_threshold=3.5, transform_skew=True):
        self.mad_threshold = mad_threshold
        self.transform_skew = transform_skew
        
        # State parameters to be learned during .fit()
        self.medians_ = {}
        self.mads_ = {}
        self.skew_transformer_ = {}
        self.columns_ = []
        self.missing_flags_ = []

    def fit(self, X, y=None):
        if isinstance(X, np.ndarray):
            X = pd.DataFrame(X)
        self.columns_ = list(X.columns)
        
        for col in self.columns_:
            series = X[col]
            # 1. Compute missingness parameters
            null_count = series.isnull().sum()
            if null_count > 0:
                self.missing_flags_.append(col)
            
            # Use non-null values to calculate robust statistics
            clean_series = series.dropna()
            
            if len(clean_series) > 0:
                median = clean_series.median()
                self.medians_[col] = median
                
                # Median Absolute Deviation (MAD)
                mad = np.median(np.abs(clean_series - median))
                # Avoid division by zero for invariant columns
                self.mads_[col] = mad if mad > 1e-8 else 1e-8 
                
                # 2. Skewness estimation & Transformer fitting
                if self.transform_skew:
                    # Fit Yeo-Johnson on imputed and capped data to prevent outlier-driven lambdas
                    capped_series = self._cap_outliers(clean_series, col).values.reshape(-1, 1)
                    pt = PowerTransformer(method='yeo-johnson', standardize=True)
                    pt.fit(capped_series)
                    self.skew_transformer_[col] = pt
            else:
                # Edge case: Column is completely empty
                self.medians_[col] = 0.0
                self.mads_[col] = 1.0

        return self

    def _cap_outliers(self, series, col):
        median = self.medians_[col]
        mad = self.mads_[col]
        
        # Calculate modified Z-score
        modified_z = 0.6745 * (series - median) / mad
        
        # Compute exact bounds based on threshold
        lower_bound = median - (self.mad_threshold * mad / 0.6745)
        upper_bound = median + (self.mad_threshold * mad / 0.6745)
        
        return series.clip(lower_bound, upper_bound)

    def transform(self, X):
        if isinstance(X, np.ndarray):
            X = pd.DataFrame(X, columns=self.columns_)
        
        X_out = pd.DataFrame(index=X.index)
        
        for col in self.columns_:
            series = X[col].copy()
            
            # 1. Generate Binary Missingness Indicator Flag
            if col in self.missing_flags_:
                X_out[f"{col}_is_missing"] = series.isnull().astype(float)
            
            # 2. Impute with training median
            series = series.fillna(self.medians_[col])
            
            # 3. Cap Outliers using fitted bounds
            series = self._cap_outliers(series, col)
            
            # 4. Apply fitted Yeo-Johnson power transform
            if self.transform_skew and col in self.skew_transformer_:
                transformed_arr = self.skew_transformer_[col].transform(series.values.reshape(-1, 1))
                X_out[col] = transformed_arr.flatten()
            else:
                X_out[col] = series
                
        return X_out

# Example usage validating zero data-leakage pipeline execution
if __name__ == "__main__":
    np.random.seed(42)
    # Generate mock training data (highly skewed with outliers and missing values)
    train_data = pd.DataFrame({
        'feat_A': np.concatenate([np.random.lognormal(mean=1.5, sigma=0.7, size=95), [500.0, 1000.0, np.nan, np.nan, np.nan]])
    })
    
    test_data = pd.DataFrame({
        'feat_A': [1.2, np.nan, 2000.0]  # Contains missing values and a massive outlier
    })
    
    preprocessor = RobustPreprocessor(mad_threshold=3.0, transform_skew=True)
    
    # Fit & Transform Train
    X_train_clean = preprocessor.fit_transform(train_data)
    print("Processed Train Data Shape:", X_train_clean.shape)
    
    # Transform Test (No Fitting!)
    X_test_clean = preprocessor.transform(test_data)
    print("\nProcessed Test Output:\n", X_test_clean)
```

---

## 3. ⚠️ The Interview Warzone (Scenario-Based Deep Dive)

### Scenario 1: The Billion-Row Scale-Up (Distributed Latency & Compute)

**Interviewer Prompt:**
> "You have a 10TB dataset of user interaction profiles stored in S3. Some continuous columns (e.g., transaction volumes) are highly skewed and have up to 30% missing values. How do you design and execute a preprocessing pipeline using PySpark? Why can't you just use standard Python/scikit-learn libraries?"

```
                         10TB Log Data in S3
                                  │
                       [PySpark Cluster Ingest]
                                  │
         ┌────────────────────────┴────────────────────────┐
         ▼                                                 ▼
[Approximate Quantiles]                           [Missing Indicators]
- Greenwald-Khanna (GK)                           - Generate Column: is_missing
- No global sort / shuffle                        - O(1) Local Map Operation
         │                                                 │
         └────────────────────────┬────────────────────────┘
                                  ▼
                     [Broadcasting Parameters]
                     - Broadcast stats to all workers
                     - Local map transformations:
                       y_capped = clip(y, lower, upper)
```

#### The Candidate Trap
Suggesting that the team use PySpark's standard `Imputer` or computing the *exact* median and IQR across all 10TB using sorting operations. This triggers a massive global shuffle across the cluster, leading to executor Out-Of-Memory (OOM) errors and high cluster compute costs.

#### The Staff-Level Pivot
1.  **Avoid Global Sorting:** Explain that exact medians and percentiles require a global sort, which is an $O(N \log N)$ operation requiring massive partition shuffles. Instead, use the **Greenwald-Khanna (GK) algorithm** for approximate quantiles (`approxQuantile` in Spark) which runs in $O(N \log(\epsilon N))$ where $\epsilon$ is the acceptable error rate (e.g., 1%).
2.  **Broadcast Variables for Parameters:** Compute the approximate medians, MAD, or clipping thresholds on the cluster *once*, pull those tiny scalars back to the driver node, and **broadcast** them to workers as read-only variables. This turns the transformation step into a localized, map-only $O(1)$ partition execution with zero network shuffles.
3.  **Preserve Missingness at Scale:** Generate binary missingness indicator columns dynamically using PySpark SQL expression maps. This is an $O(1)$ local map operation.

---

### Scenario 2: The Online Inference Latency Dilemma

**Interviewer Prompt:**
> "You have built a complex offline preprocessing pipeline utilizing MICE (Multivariate Imputation by Chained Equations) for missing feature restoration, followed by a Yeo-Johnson transform. Your production system requires model predictions within a 10ms SLA. How do you serve this pipeline online?"

```
           [Online Transaction Request] (SLA: 10ms)
                        │
                        ├────────────────────────┐
                        ▼                        ▼
              {Feature Present}           {Feature Missing}
                        │                        │
                        ▼                        ▼
               Apply Pre-computed          [Latency Safeguard]
               Yeo-Johnson Lambda          1. Fallback to pre-computed
               (O(1) Math Operation)          Offline Segment Median
                                           2. Direct Feature Flags (0/1)
                                                 │
                                                 ▼
                                        Avoid running MICE 
                                        regressors online!
```

#### The Candidate Trap
Proposing to package and run the MICE imputer online. MICE is an iterative algorithm that fits/predicts multiple models sequentially. Running it online requires querying other features, loading auxiliary models, and executing multiple inference loops in sequence—which easily exceeds the 10ms SLA.

#### The Staff-Level Pivot
1.  **Decouple Online vs. Offline Architectures:** Never run iterative, multi-variable imputation online. 
2.  **Deterministic Math Simplification:** If a feature is present online, applying the Yeo-Johnson transform is simply a local, $O(1)$ floating-point operation. Serialize the learned parameters ($\lambda$, mean, scale) into an efficient configuration file or serialize the pipeline using ONNX runtime to execute mathematical transformations in native C++.
3.  **Online Missingness Safeguards:** If a feature is missing at inference time:
    *   **Level 1 Fallback (Low Latency):** Use pre-computed segment-level medians calculated offline and cached in an in-memory key-value store (e.g., Redis).
    *   **Level 2 Fallback (Representation):** Instantly set the missingness binary flag feature to `1.0`. Keep the default value static. Tree-based production models like XGBoost handle missing values natively (by learning default directions during split construction), rendering complex online imputation unnecessary.

---

### Scenario 3: The Silent Failure of Feature Drift

**Interviewer Prompt:**
> "Your production pipeline caps outliers at the 99th percentile determined from your training set. During a holiday marketing campaign, transaction volumes double, and high-spend customers begin purchasing at triple their normal rate. How does your preprocessing pipeline react, and what are the downstream consequences on the model?"

```
             Training Distribution           Holiday Shift (Drift)
             
                 [ Normal ]                          [ Shifted Real Data ]
             ┌───────┴───────┐                       ┌─────────┴─────────┐
             │               │                       │                   │
  0 ────────────────── 99th_Limit (Capping) ──────────────────────────────► Feature Value
                                │                      │        │        │
                                ▼                      ▼        ▼        ▼
                      [All capped at Limit!] ◄─────────┴────────┴────────┘
                      - Model sees flat value
                      - Complete loss of variance
                      - High-value buyers flagged as identical normal users
```

#### The Candidate Trap
Answering that "the model will correctly handle them because they are capped, protecting the model from exploding gradients."

#### The Staff-Level Pivot
1.  **The Saturation Effect:** Hard-capping features at fixed training-time percentiles under a severe distribution shift causes **saturation**. Every single high-value customer during the holiday campaign gets clamped to the exact same maximum value (the 99th percentile limit). 
2.  **Downstream Loss of Signal:** The model loses all variance and resolution at the tail end of the distribution. It can no longer distinguish between a moderately high-value customer and an ultra-high-value customer, which impairs downstream tasks like fraud detection, LTV prediction, or personalized recommendations.
3.  **The Mitigation Architecture:**
    *   **Dynamic / Relative Normalization:** Implement non-parametric transformations like `QuantileTransformer` (which maps features to uniform or normal distributions based on cumulative distribution functions) to preserve ordinal relationships, even when scale shifts.
    *   **Real-time Feature Monitoring:** Deploy population monitoring systems using metrics like the **Population Stability Index (PSI)** or the **Kolmogorov-Smirnov (KS) test** to detect feature drift on incoming data. If PSI $> 0.2$, trigger an automated pipeline alert to retrain the preprocessing scaling vectors on a rolling window of recent data.

$$\text{PSI} = \sum \left( (Actual\% - Expected\%) \times \ln\left(\frac{Actual\%}{Expected\%}\right) \right)$$