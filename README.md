# Correlation-Analyzer-Project

Correlation-Analyzer-Project is an interactive **process-data intelligence workbench** built with Streamlit for chemical/process engineers. It is designed to help teams move from raw plant data to actionable decisions by combining preprocessing, statistical correlation analysis, regression modeling, machine-learning benchmarking, and downloadable reporting in one guided flow.

## 1) Project Purpose

The project exists to answer one practical question:

> **"Given many process variables, which ones really drive the target KPI, and how reliable is that relationship?"**

To answer this, the app guides users through a staged workflow:

1. Upload production/process data.
2. Clean and qualify data quality issues (including Excel-style error codes).
3. Select target and candidate explanatory variables.
4. Reveal structure via correlations and distribution diagnostics.
5. Quantify influence through regression + model comparison.
6. Package findings as Word/PDF reports.

---

## 2) What Features Are Included?

### A. Data ingestion and session-safe state control
- CSV/XLSX upload support.
- Multi-encoding CSV loader fallback (`utf-8`, `cp949`, `euc-kr`, etc.).
- Automatic state reset when users replace/remove files, so stale model state does not leak across analyses.
- Temporary timestamped file persistence.

### B. Three-stage missing/error value intelligence
Unlike generic null checks, this project explicitly recognizes **process-data reality** where spreadsheets contain pseudo-missing values.

- **Stage 1**: blanks, whitespace-only strings, textual null forms (`None`, `null`, `NaN`, symbols such as `-`, `_`).
- **Stage 2**: common Excel error tokens (`#DIV/0!`, `#N/A`, `#REF!`, `#VALUE!`, `#NODATA`, variants).
- **Stage 3**: extended Excel/system error tokens (`#NULL!`, `#SPILL!`, `#CALC!`, `#BUSY!`, `#UNKNOWN!`, etc.).

It then builds stage-wise masks and a color-coded missingness map for transparent diagnosis.

### C. Variable selection and base exploratory analytics
- Numeric variable gating (at least two numeric columns required).
- Y (target) + multi-X selection (recommended 2–5 explanatory variables).
- Statistical summary table + histogram grid for selected fields.

### D. Correlation and relationship discovery
- Correlation matrix heatmap with coefficient annotations.
- Automatic extraction of variable pairs above a threshold (absolute correlation >= 0.4 in main section).
- Positive/negative and strong/moderate pair counts.
- Scatter matrix visualization.
- Auto-generated insight cards:
  - strong/moderate linear relationships,
  - skew/kurtosis-based distribution characteristics,
  - low-correlation candidates that may hide nonlinear structure.

### E. Predictive modeling and interpretability
- Train/test split linear regression.
- Equation rendering with signed coefficients.
- Coefficient interpretation and variable-by-variable effect direction.
- **Term contribution ratio analysis** (estimated share of each term in predicted Y).
- Model quality metrics (R²/MAE/RMSE) with grade bands.

### F. Machine-learning model benchmark
- Parallel benchmark of 4 regressors:
  - Random Forest,
  - Gradient Boosting,
  - Support Vector Regression,
  - Neural Network (MLP).
- Ranked comparison by R² with error metrics.
- Unified actual-vs-predicted scatter chart with best model emphasis.

### G. Deep variable grouping / correlation network analysis
- Full numeric-space correlation scan.
- Threshold-based significant pair extraction.
- Pair severity segmentation (collinearity/very-strong/strong/moderate/weak).
- Additional insight synthesis for recommendation-ready interpretation.

### H. Reporting and export
- DOCX report generation including key charts/summary blocks.
- PDF report generation fallback path (when dependencies are available).

---

## 3) How the Content Progresses in the App (User Journey)

### Step 1 — File Upload
The user uploads a CSV or Excel file. The app initializes/reset session context to guarantee a clean run per dataset.

### Step 2 — Data Preprocessing
The app shows data preview and quality profile, then performs stage-wise missing/error classification and visualization. Users may preprocess or skip based on analysis intent.

### Step 3 — Variable Selection + EDA
Users choose one target (Y) and explanatory variables (X). The app immediately surfaces descriptive stats, histograms, correlation matrix, high-correlation pairs, and scatter-matrix patterns.

### Step 4 — Analytical Results
The app then executes:
1. Interpretable linear regression diagnostics,
2. Multi-model machine-learning comparison,
3. Deep all-variable correlation grouping insights.

### Step 5 — Report Download
After analysis completion, users can export a formal report (DOCX/PDF) for handoff and decision meetings.

---

## 4) Core Insight-Extraction Engine (Most Important Part)

If your goal is to extract real insight from process data, the most critical implementation is the pipeline below.

### 4.1 Data trust gate (quality before modeling)
Insight quality depends on data quality. The app’s staged missing/error recognition is effectively a **trust gate**:

- It prevents hidden spreadsheet error tokens from silently contaminating statistics.
- It exposes quality debt visually and quantitatively before model fitting.
- It keeps missingness semantics explicit rather than blending all failures into generic NaN.

**Why this matters:** in industrial data, a model trained on silently corrupted tokens can produce "good-looking" but operationally misleading coefficients.

### 4.2 Structure discovery (correlation + distribution + geometry)
Before fitting models, the app captures variable structure using three complementary lenses:

1. **Correlation heatmap** → linear dependence map.
2. **Distribution diagnostics (skew/kurtosis)** → shape/risk profile of each variable.
3. **Scatter matrix** → pairwise geometry and nonlinear suspicion.

This triangulation prevents over-reliance on a single metric and improves root-cause hypothesis generation.

### 4.3 Influence quantification (regression equation + contribution ratio)
The regression block is not limited to "fit score." It exposes:

- signed coefficient direction,
- variable-by-variable sensitivity,
- and term contribution ratio to predicted Y.

This gives engineers an interpretable narrative:

- Which variables have dominant impact,
- whether that impact is positive/negative,
- and which terms are secondary versus critical.

### 4.4 Robustness via model plurality
Linear regression is compared against nonlinear learners (RF/GB/SVR/MLP). This acts as a **robustness check**:

- If nonlinear models greatly outperform linear, the process likely has nonlinear behavior.
- If linear holds competitively, simpler and more explainable controls may be sufficient.

### 4.5 Scale-up insight through deep correlation grouping
Beyond user-selected variables, deep analysis scans all numeric variables and organizes meaningful pairs. This helps identify:

- collinearity candidates to remove,
- high-value related variables for feature design,
- low-correlation independent variables that may improve model breadth.

---

## 5) Intended Users

- Process/chemical engineers,
- Production optimization teams,
- Data analysts supporting manufacturing operations,
- Technical managers preparing evidence-based improvement actions.

---

## 6) Practical Value Delivered

This project turns a traditionally fragmented workflow (cleaning in one tool, plotting in another, modeling in another, reporting manually) into a **single guided analysis product**. The main value is not just prediction—it is **interpretable, operationally actionable insight extraction** from multivariable process data.
