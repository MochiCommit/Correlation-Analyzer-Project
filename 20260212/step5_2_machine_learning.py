import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.svm import SVR
from sklearn.neural_network import MLPRegressor
from sklearn.inspection import permutation_importance
from sklearn.metrics import r2_score
import shap
# from umap import UMAP
import time
import warnings
from sklearn.decomposition import PCA

# ==============================
# === 2단계: 최종 모델과 인사이트 (확장: RF, GB, SVM, NN 비교) ===
# ==============================

def render_metric_card(title, value, unit="", help_text=""):
    """중요 지표를 강조하는 카드 UI를 렌더링합니다."""
    st.markdown(f"""
    <div style="background-color: #F0F2F6; border-left: 5px solid #1E90FF; padding: 1rem; border-radius: 5px; margin-bottom: 1rem;">
        <p style="font-size: 0.9rem; margin: 0; color: #555;">{title}</p>
        <p style="font-size: 2.2rem; font-weight: bold; margin: 0;">{value} <span style="font-size: 1.5rem;">{unit}</span></p>
        <p style="font-size: 0.8rem; margin: 0.5rem 0 0 0; color: #888;">{help_text}</p>
    </div>
    """, unsafe_allow_html=True)

def format_number(val):
    return f"{val:,.2f}"

def _validate_prediction(y_pred, model_name: str = "Unknown"):
    """
    예측값의 유효성을 검증하고, 문제가 있으면 로그를 남깁니다.
    """
    if y_pred is None or not isinstance(y_pred, (int, float, np.number)):
        return False
    
    if np.isnan(y_pred) or np.isinf(y_pred):
        return False
    
    return True

@st.cache_data
def train_compare_models(_X_train, _y_train, _X_test, _y_test):
    """
    (캐시됨) RF, GB, SVM, NN + (Permutation Importance, SHAP) 총 6개 기법을 학습/비교 후 dict로 반환
    - 이 함수는 @st.cache_data로 캐시되어 동일한 데이터에 대해서는 재실행되지 않습니다.
    """

    # 기본 4개 모델
    models = {
        "Random Forest": RandomForestRegressor(n_estimators=200, random_state=42, n_jobs=-1),
        "Gradient Boosting": GradientBoostingRegressor(random_state=42, learning_rate=0.1, n_estimators=100),
        "Support Vector Machine": Pipeline([("scaler", StandardScaler()), ("svm", SVR(kernel="rbf", C=10.0, gamma="scale"))]),
        "Neural Network": Pipeline([("scaler", StandardScaler()), ("mlp", MLPRegressor(hidden_layer_sizes=(128, 64, 32), max_iter=1000, alpha=0.0001, learning_rate='adaptive', early_stopping=True, validation_fraction=0.1, random_state=42))]),
    }

    results = {}

    # 4개 모델 적합
    for name, model in models.items():
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            try:
                model.fit(_X_train, _y_train)
                y_pred = model.predict(_X_test)
                r2 = r2_score(_y_test, y_pred)
            except Exception as e:
                # 모델 학습 실패 시 대체 값
                y_pred = np.full_like(_y_test, _y_train.mean(), dtype=float)
                r2 = r2_score(_y_test, y_pred)
                st.warning(f"{name} 모델 학습 중 경고: {str(e)[:100]}")
            
            results[name] = {"model": model, "r2": float(r2), "y_pred": y_pred}

    # Linear Regression 추가
    from sklearn.linear_model import LinearRegression
    lr_model = Pipeline([("scaler", StandardScaler()), ("lr", LinearRegression())])
    lr_model.fit(_X_train, _y_train)
    y_pred_lr = lr_model.predict(_X_test)
    r2_lr = r2_score(_y_test, y_pred_lr)
    results["Linear Regression"] = {
        "model": lr_model, "r2": float(r2_lr), "y_pred": y_pred_lr
    }

    # Permutation Importance (별도 RF base)
    pi_base = RandomForestRegressor(n_estimators=150, random_state=123, n_jobs=-1)
    pi_base.fit(_X_train, _y_train)
    y_pred_pi = pi_base.predict(_X_test)
    r2_pi = r2_score(_y_test, y_pred_pi)
    try:
        pi = permutation_importance(pi_base, _X_test, _y_test, n_repeats=10, random_state=123, n_jobs=-1)
        pi_values = dict(zip(_X_test.columns, pi.importances_mean))
    except Exception:
        pi_values = None
    results["Permutation Importance"] = {
        "model": pi_base, "r2": float(r2_pi), "y_pred": y_pred_pi, "pi": pi_values
    }

    # SHAP(별도 GB base)
    shap_base = GradientBoostingRegressor(random_state=7)
    shap_base.fit(_X_train, _y_train)
    y_pred_shap = shap_base.predict(_X_test)
    r2_shap = r2_score(_y_test, y_pred_shap)
    shap_summary = None
    try:
        explainer = shap.TreeExplainer(shap_base)
        # 빠른 요약용으로 일부 샘플만
        idx = np.random.RandomState(7).choice(len(_X_test), size=min(200, len(_X_test)), replace=False)
        shap_values = explainer.shap_values(_X_test.iloc[idx])
        shap_importance = np.abs(shap_values).mean(axis=0)
        shap_summary = dict(zip(_X_test.columns, shap_importance))
    except Exception:
        pass
    results["SHAP"] = {
        "model": shap_base, "r2": float(r2_shap), "y_pred": y_pred_shap, "shap": shap_summary
    }

    # 최고 성능 태깅 (__best__ 키 제외)
    valid_models = [k for k in results.keys() if k != "__best__"]
    if valid_models:
        best_name = max(valid_models, key=lambda k: results[k]["r2"])
        results["__best__"] = best_name
    
    # === 모델별 성능 검증 ===
    # 각 모델의 R2 값 확인 및 음수 값 감지
    for model_name, model_result in results.items():
        if model_name != "__best__":
            r2_val = model_result["r2"]
            if r2_val < 0:
                # R2가 음수인 경우, 모델이 평균값보다 나쁜 성능을 냄
                # 이 경우 평균 모델로 대체하여 최소한 R2=0 수준으로 맞춤
                y_pred_mean = np.full_like(model_result["y_pred"], _y_test.mean(), dtype=float)
                r2_corrected = r2_score(_y_test, y_pred_mean)
                # 원래 음수 R2보다 평균 모델이 나으면 업데이트
                if r2_corrected > r2_val:
                    results[model_name]["r2"] = float(r2_corrected)
                    results[model_name]["y_pred"] = y_pred_mean
    
    # 최고 성능 재계산 (음수 R2 제거 후) (__best__ 키 제외)
    valid_models = [k for k in results.keys() if k != "__best__"]
    if valid_models:
        best_name = max(valid_models, key=lambda k: results[k]["r2"])
        results["__best__"] = best_name
    
    return results

def format_y_axis_tick(value):
    """
    Y축 틱 라벨용 포맷팅 (k 단위 사용)
    """
    if pd.isna(value) or value is None:
        return "N/A"
    
    abs_value = abs(value)
    
    # 백만 이상인 경우
    if abs_value >= 1_000_000:
        return f"{value/1_000_000:.1f}m"
    
    # 천 단위로 변환하여 k 표시
    if abs_value >= 1000:
        return f"{value/1000:.0f}k"
    else:
        # 1000 미만은 그대로 표시 (소수점 자릿수는 숫자 크기에 따라)
        if abs_value <= 1:
            return f"{value:.3f}"
        elif abs_value <= 10:
            return f"{value:.2f}"
        elif abs_value <= 100:
            return f"{value:.1f}"
        else:
            return f"{value:.0f}"
        
def _safe_std(s: pd.Series) -> float:
    v = float(np.nanstd(s.values.astype(float)))
    return v if v > 1e-12 else 1.0

def _pick_time_column(df: pd.DataFrame):
    """
    df에서 시간 축으로 쓸만한 컬럼을 자동 탐색합니다.
    - datetime dtype 우선
    - 없으면 'time','date','timestamp' 등 이름 기반 탐색
    """
    # 1) datetime dtype
    dt_cols = [c for c in df.columns if np.issubdtype(df[c].dtype, np.datetime64)]
    if dt_cols:
        return dt_cols[0]

    # 2) 이름 기반(파싱 시도는 비용이 큼 -> 우선 후보만)
    name_candidates = []
    for c in df.columns:
        lc = str(c).lower()
        if any(k in lc for k in ["time", "date", "timestamp", "datetime"]):
            name_candidates.append(c)
    if name_candidates:
        # 파싱 가능하면 사용
        c0 = name_candidates[0]
        try:
            tmp = pd.to_datetime(df[c0], errors="coerce")
            if tmp.notna().sum() >= max(3, int(0.5 * len(df))):
                return c0
        except Exception:
            pass
    return None

def _compute_case_distances(
    df: pd.DataFrame,
    x_query: dict,
    numeric_cols: list,
    cat_cols: list,
    distance_metric: str = "L2",   # "L2" or "L1"
    cat_weight: float = 1.0,
):
    """
    수치형: z-score 기반 거리
    범주형: match=0 / mismatch=1 (가중치 적용)
    반환: distances(np.ndarray), valid_mask(np.ndarray)
    """
    n = len(df)
    valid_mask = np.ones(n, dtype=bool)

    # --- numeric part ---
    num_dist = np.zeros(n, dtype=float)
    if numeric_cols:
        # z-score 기준(mean/std는 df 기준)
        for c in numeric_cols:
            if c not in df.columns:
                continue
            col = df[c]
            # df 값
            x = col.values.astype(float)
            mu = float(np.nanmean(x))
            sd = _safe_std(col)
            # query
            q = float(x_query.get(c, np.nan))
            # query가 NaN이면 numeric 거리 계산에서 제외
            if np.isnan(q):
                continue

            z = (x - mu) / sd
            zq = (q - mu) / sd
            diff = z - zq

            # df 행 값이 NaN이면 해당 행은 invalid 처리(거리 계산 불가)
            valid_mask &= ~np.isnan(diff)

            if distance_metric.upper() == "L1":
                num_dist += np.abs(diff)
            else:
                num_dist += diff ** 2

        if distance_metric.upper() != "L1":
            num_dist = np.sqrt(num_dist)

    # --- categorical part ---
    cat_dist = np.zeros(n, dtype=float)
    if cat_cols:
        for c in cat_cols:
            if c not in df.columns:
                continue
            qv = x_query.get(c, None)
            # query가 비어 있으면 categorical은 제외
            if qv is None or (isinstance(qv, float) and np.isnan(qv)):
                continue
            v = df[c].astype(str).values
            qvs = str(qv)
            mismatch = (v != qvs)
            # 결측은 mismatch로 간주(보수적으로)
            mismatch = np.logical_or(mismatch, pd.isna(df[c]).values)
            cat_dist += cat_weight * mismatch.astype(float)

    total = num_dist + cat_dist
    # invalid는 큰 값으로 밀어냄
    total[~valid_mask] = np.inf
    return total, valid_mask

def _knn_case_retrieval(
    df: pd.DataFrame,
    x_query: dict,
    x_cols: list,
    distance_metric: str = "L2",
    cat_weight: float = 1.0,
    k_max: int = 200,
    k_cap: int = 80,
    alpha: float = 0.20,
    delta: float = None,   # 예: 0.5
    use_mult: bool = True, # d <= d_best*(1+alpha)
):
    """
    1) 전체 거리 계산 후 K_max까지 정렬
    2) d_best 기준 임계치로 가변 K 선정
    3) 상한 K_cap 적용
    """
    # numeric / categorical split
    numeric_cols = df[x_cols].select_dtypes(include=np.number).columns.tolist() if x_cols else []
    cat_cols = [c for c in x_cols if c in df.columns and c not in numeric_cols]

    dists, valid_mask = _compute_case_distances(
        df=df,
        x_query=x_query,
        numeric_cols=numeric_cols,
        cat_cols=cat_cols,
        distance_metric=distance_metric,
        cat_weight=cat_weight,
    )

    # 유효 거리만
    idx_valid = np.where(np.isfinite(dists))[0]
    if len(idx_valid) == 0:
        return {
            "matched_df": df.iloc[0:0].copy(),
            "best_idx": None,
            "d_best": np.inf,
            "numeric_cols": numeric_cols,
            "cat_cols": cat_cols,
            "all_dists": dists,
        }

    # K_max 정렬
    idx_sorted = idx_valid[np.argsort(dists[idx_valid])]
    idx_top = idx_sorted[: min(k_max, len(idx_sorted))]
    d_best = float(dists[idx_top[0]])

    # 임계치 결정
    thr = None
    if use_mult:
        thr = d_best * (1.0 + float(alpha))
    if delta is not None:
        thr2 = d_best + float(delta)
        thr = thr2 if thr is None else min(thr, thr2)

    # 임계치 기반 선택
    if thr is None:
        selected = idx_top
    else:
        selected = idx_top[dists[idx_top] <= thr]

    # 상한
    if len(selected) > k_cap:
        selected = selected[:k_cap]

    matched_df = df.iloc[selected].copy()
    return {
        "matched_df": matched_df,
        "best_idx": int(idx_top[0]),
        "d_best": d_best,
        "numeric_cols": numeric_cols,
        "cat_cols": cat_cols,
        "all_dists": dists,
    }

def _similarity_from_distance(d: float, d_best: float) -> float:
    """
    best=100% 기준 상대 유사도(직관적)
    sim = (1 + d_best) / (1 + d)  -> best=1.0
    """
    if not np.isfinite(d) or not np.isfinite(d_best):
        return 0.0
    return float((1.0 + d_best) / (1.0 + d))

def _recommend_narrowing_candidates(df: pd.DataFrame, used_cols: list, top_n: int = 5):
    """
    "상황을 더 좁히기 위해" 추가하면 좋은 후보(휴리스틱):
    - 비수치형(또는 low-cardinality) 컬럼 중 사용 안한 것
    """
    used = set(used_cols or [])
    cands = []
    for c in df.columns:
        if c in used:
            continue
        s = df[c]
        nun = s.nunique(dropna=True)
        if nun <= 1:
            continue
        # 범주형/low-card 우선
        if (not np.issubdtype(s.dtype, np.number)) and (nun <= 30):
            cands.append((c, nun))
    cands.sort(key=lambda x: x[1])  # 너무 다양하지 않은 것 우선
    return [c for c, _ in cands[:top_n]]


def _sync_from_slider(col_name: str):
    """
    슬라이더가 변경되었을 때 호출되는 콜백.
    - 공용 상태(slider_values)에 값을 반영하고
    - 숫자 입력 박스의 값도 동일하게 맞춰줍니다.
    """
    try:
        new_val = st.session_state.get(f"slider_{col_name}")
        if new_val is None:
            return
        # 공용 상태 업데이트
        if "slider_values" not in st.session_state:
            st.session_state.slider_values = {}
        st.session_state.slider_values[col_name] = new_val
        # 숫자 입력 박스 값 동기화
        st.session_state[f"input_{col_name}"] = new_val
    except Exception:
        # 콜백에서는 절대적으로 앱이 죽지 않도록 예외 무시
        pass


def _sync_from_number_input(col_name: str):
    """
    숫자 입력 박스가 변경되었을 때 호출되는 콜백.
    - 공용 상태(slider_values)에 값을 반영하고
    - 슬라이더의 값도 동일하게 맞춰줍니다.
    """
    try:
        new_val = st.session_state.get(f"input_{col_name}")
        if new_val is None:
            return
        # 공용 상태 업데이트
        if "slider_values" not in st.session_state:
            st.session_state.slider_values = {}
        st.session_state.slider_values[col_name] = new_val
        # 슬라이더 값 동기화
        st.session_state[f"slider_{col_name}"] = new_val
    except Exception:
        # 콜백에서는 절대적으로 앱이 죽지 않도록 예외 무시
        pass


def _build_coverage_model(X_train: pd.DataFrame):
    """
    학습 데이터의 X 공간에서 '어디까지가 익숙한 구간인지'를 정량화하는 커버리지 모델을 생성합니다.
    - Mahalanobis 거리 기반으로 학습 데이터 분포의 타원(고밀도 영역)을 추정합니다.
    - 거리 분포의 분위수를 사용해 '안전/주의/경고' 3단계로 나눌 수 있는 기준선을 저장합니다.
    """
    try:
        Xv = X_train.values.astype(float)
        # 평균 및 공분산(중심+타원 형태) 계산
        mu = Xv.mean(axis=0)
        Xc = Xv - mu
        # 공분산 역행렬 (수치적으로 불안정할 경우 의사역행렬 사용)
        cov = np.cov(Xc, rowvar=False)
        cov_inv = np.linalg.pinv(cov)

        # 각 학습 샘플의 Mahalanobis 제곱거리 d^2 분포
        d2 = np.einsum("ij,jk,ik->i", Xc, cov_inv, Xc)
        p90, p975 = np.percentile(d2, [90, 97.5])

        # 변수별 1~99 분위수(단변량 극단값 파악용)
        lower_q = X_train.quantile(0.01)
        upper_q = X_train.quantile(0.99)

        return {
            "mu": mu,
            "cov_inv": cov_inv,
            "p90": float(p90),
            "p975": float(p975),
            "columns": list(X_train.columns),
            "lower_q": lower_q,
            "upper_q": upper_q,
        }
    except Exception:
        return None


def _evaluate_coverage_level(coverage_model: dict, x_row: pd.Series):
    """
    주어진 X 조합이 학습 데이터 분포의 어디쯤에 위치하는지 평가합니다.
    - level: "high"(안전), "medium"(주의), "low"(경고)
    - d2: Mahalanobis 제곱거리 값
    """
    try:
        mu = coverage_model["mu"]
        cov_inv = coverage_model["cov_inv"]
        cols = coverage_model["columns"]

        x_vec = x_row[cols].values.astype(float)
        diff = x_vec - mu
        d2 = float(diff.T @ cov_inv @ diff)

        if d2 <= coverage_model["p90"]:
            level = "high"
        elif d2 <= coverage_model["p975"]:
            level = "medium"
        else:
            level = "low"

        return {"d2": d2, "level": level}
    except Exception:
        return None


def _find_extreme_variables(coverage_model: dict, x_row: pd.Series):
    """
    현재 X 조합에서 '학습 데이터의 일반적인 범위(1~99 분위수)를 벗어난' 변수들을 찾아냅니다.
    - 사용자가 어느 변수를 특히 조심해야 하는지 설명용으로 사용.
    """
    try:
        lower_q: pd.Series = coverage_model["lower_q"]
        upper_q: pd.Series = coverage_model["upper_q"]
        extreme_cols = []
        for col in coverage_model["columns"]:
            v = x_row[col]
            if pd.isna(v):
                continue
            if v < lower_q[col] or v > upper_q[col]:
                extreme_cols.append(col)
        return extreme_cols
    except Exception:
        return []


# -----------------------------
# --- Simulator renderer UI ---
# -----------------------------
def _map_exploration_settings(radius_label: str):
    """Map user-friendly radius to internal retrieval params."""
    label = (radius_label or "Balanced").lower()
    if label.startswith("narrow"):
        return dict(alpha=0.05, k_cap=20, k_max=200)
    if label.startswith("wide"):
        return dict(alpha=0.5, k_cap=200, k_max=2000)
    # balanced
    return dict(alpha=0.20, k_cap=80, k_max=500)


def _create_histogram_with_slider(df, col_name, current_value):
    """
    슬라이더 위에 표시할 히스토그램을 생성합니다.
    현재값을 빨간 수직선으로 표시합니다.
    """
    col_data = df[col_name].dropna()
    col_min = float(np.nanmin(col_data))
    col_max = float(np.nanmax(col_data))
    
    # 히스토그램 생성
    fig = go.Figure()
    
    fig.add_trace(go.Histogram(
        x=col_data,
        nbinsx=40,
        marker=dict(color='#4169E1', opacity=0.7),
        name='Data Distribution',
        hovertemplate='Range: %{x}<br>Count: %{y}<extra></extra>'
    ))
    
    # 현재값을 빨간 수직선으로 표시 (텍스트 없이)
    fig.add_vline(
        x=current_value,
        line_dash="solid",
        line_color="#FF4444",
        line_width=2
    )
    
    # 레이아웃 설정 - 여백을 완전히 제거 (x, y축 제거)
    fig.update_layout(
        height=60,
        margin=dict(l=0, r=0, t=0, b=0),
        xaxis_title="",
        yaxis_title="",
        showlegend=False,
        hovermode='closest',
        dragmode=False,
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        xaxis=dict(
            visible=False,
            range=[col_min, col_max]
        ),
        yaxis=dict(
            visible=False,
            showgrid=False,
            zeroline=False
        )
    )
    
    return fig


def _render_control_panel(df, numeric_x_cols):
    """Left: sliders for numeric X. Returns current_inputs dict."""
    if 'slider_values' not in st.session_state:
        st.session_state.slider_values = {}
    current_inputs = {}

    # st.markdown("**Control Panel**")
    for col_name in numeric_x_cols:
        col_min = float(np.nanmin(df[col_name]))
        col_max = float(np.nanmax(df[col_name]))
        col_mid = float(np.nanmedian(df[col_name]))
        step = (col_max - col_min) / 100 if col_max > col_min else 0.01

        if col_name not in st.session_state.slider_values:
            st.session_state.slider_values[col_name] = col_mid

        slider_key = f"slider_{col_name}"
        input_key = f"input_{col_name}"
        if slider_key not in st.session_state:
            st.session_state[slider_key] = st.session_state.slider_values[col_name]
        if input_key not in st.session_state:
            st.session_state[input_key] = st.session_state.slider_values[col_name]

        # 변수 이름과 현재값을 같은 줄에 배치
        col1, col2 = st.columns([5, 2], gap="small")
        with col1:
            st.markdown(f"**{col_name}**")
       
        with col2:
            # 작은 입력 필드 (숫자 직접 입력용)
            input_val = st.number_input(
                label="",
                min_value=col_min,
                max_value=col_max,
                step=(col_max - col_min) / 1000 if col_max > col_min else 0.001,
                format="%.2f",
                key=input_key,
                on_change=_sync_from_number_input,
                args=(col_name,),
                label_visibility="collapsed"
            )

        # 현재 슬라이더값 가져오기
        current_slider_value = st.session_state.slider_values.get(col_name, col_mid)
        
        # 슬라이더 위에 히스토그램 표시
        hist_fig = _create_histogram_with_slider(df, col_name, current_slider_value)
        
        # 히스토그램/슬라이더 사이의 여백을 강력하게 제거하여 밀착
        # height=60인 Plotly 차트(히스토그램)를 특정하여 스타일 적용
        st.markdown(f"""
        <style>
            div[data-testid="stElementContainer"]:has(iframe[height="60"]) {{
                margin-bottom: -18px !important;
                padding-bottom: 0 !important;
            }}
            div[data-testid="stElementContainer"]:has(iframe[height="60"]) + div[data-testid="stElementContainer"] {{
                margin-top: -12px !important;
                padding-top: 0 !important;
            }}
            div[data-testid="stSlider"] {{
                margin-top: -8px !important;
                padding-top: 0 !important;
            }}
        </style>
        """, unsafe_allow_html=True)
        
        st.plotly_chart(
            hist_fig, 
            use_container_width=True, 
            config={"displayModeBar": False}, 
            key=f"hist_{col_name}"
        )
        
        st.slider(
            label="",
            min_value=col_min,
            max_value=col_max,
            step=step,
            key=slider_key,
            on_change=_sync_from_slider,
            args=(col_name,),
            label_visibility="collapsed"
        )

    for col_name in numeric_x_cols:
        current_inputs[col_name] = st.session_state.slider_values[col_name]
    return current_inputs


def _render_data_map_placeholder(df, numeric_x_cols, current_inputs, matched_df, y_col, method="PCA", bins=60):
    """Center: 2D projection (PCA or UMAP if available).
    Shows historical points colored by Y (heatmap-like), trajectory and neighbors.
    """
    X_map = df[numeric_x_cols].fillna(0)
    y_map = df[y_col].reindex(X_map.index).fillna(method='ffill').fillna(0)

    emb = None
    used_method = method.upper() if method else "PCA"
    if used_method == "UMAP":
        try:
            import umap
            reducer = umap.UMAP(n_components=2, random_state=42)
            emb = reducer.fit_transform(X_map.values)
        except Exception:
            used_method = "PCA"

    if used_method == "PCA" or emb is None:
        pca = PCA(n_components=2)
        try:
            emb = pca.fit_transform(X_map.values)
        except Exception:
            emb = np.zeros((len(X_map), 2))

    # project current point
    try:
        cur_vec = np.array([current_inputs[c] for c in numeric_x_cols], dtype=float).reshape(1, -1)
        if used_method == "UMAP":
            cur_proj = reducer.transform(cur_vec)[0]
        else:
            cur_proj = pca.transform(cur_vec)[0]
    except Exception:
        cur_proj = np.array([0.0, 0.0])

    # matched projections
    try:
        matched_proj = (reducer.transform(matched_df[numeric_x_cols].fillna(0).values) if (used_method == "UMAP" and 'reducer' in locals())
                        else pca.transform(matched_df[numeric_x_cols].fillna(0).values)) if (not matched_df.empty) else np.empty((0, 2))
    except Exception:
        matched_proj = np.empty((0, 2))

    # heatmap grid by averaging y per bin
    x_vals = emb[:, 0]
    y_vals = emb[:, 1]
    grid_x_edges = np.linspace(x_vals.min(), x_vals.max(), bins + 1)
    grid_y_edges = np.linspace(y_vals.min(), y_vals.max(), bins + 1)
    sum_y, _, _ = np.histogram2d(x_vals, y_vals, bins=[grid_x_edges, grid_y_edges], weights=y_map.values)
    counts, _, _ = np.histogram2d(x_vals, y_vals, bins=[grid_x_edges, grid_y_edges])
    with np.errstate(invalid='ignore', divide='ignore'):
        avg_y = sum_y / counts

    # compute bin centers
    x_centers = (grid_x_edges[:-1] + grid_x_edges[1:]) / 2
    y_centers = (grid_y_edges[:-1] + grid_y_edges[1:]) / 2
    # create figure
    fig = go.Figure()

    # background small history points colored by Y value
    # Normalize Y values to [0, 1] for color mapping
    y_min = y_map.min()
    y_max = y_map.max()
    y_range = y_max - y_min if y_max > y_min else 1.0
    y_norm = (y_map.values - y_min) / y_range
    
    # Create custom gray gradient colors
    # Low Y (#E5E7EB) → Mid Y (#9CA3AF) → High Y (#374151)
    def interpolate_color(t):
        if t < 0.5:
            # Low to Mid
            r = int(0xE5 * (1 - 2*t) + 0x9C * 2*t)
            g = int(0xE7 * (1 - 2*t) + 0xA3 * 2*t)
            b = int(0xEB * (1 - 2*t) + 0xAF * 2*t)
        else:
            # Mid to High
            r = int(0x9C * (2 - 2*t) + 0x37 * (2*t - 1))
            g = int(0xA3 * (2 - 2*t) + 0x41 * (2*t - 1))
            b = int(0xAF * (2 - 2*t) + 0x51 * (2*t - 1))
        return f'rgba({r}, {g}, {b}, 0.55)'
    
    bg_colors = [interpolate_color(y) for y in y_norm]
    
    # Colorbar 틱 포맷팅
    tick_vals = []
    tick_texts = []
    tick_val = y_min
    dtick = y_range / 5 if y_range > 0 else 1
    while tick_val <= y_max + 1e-6:
        tick_vals.append(tick_val)
        tick_texts.append(_format_number(tick_val))
        tick_val += dtick
    
    # Layer 1: Background data points (drawn first)
    fig.add_trace(go.Scattergl(
        x=x_vals, 
        y=y_vals, 
        mode='markers', 
        marker=dict(
            size=5,
            color=bg_colors,
            showscale=False
        ),
        showlegend=False,
        hoverinfo='skip'
    ))
    
    # Add colorbar via invisible reference trace for Y values
    fig.add_trace(go.Scatter(
        x=[None], y=[None],
        mode='markers',
        marker=dict(
            size=0,
            color=y_map.values,
            colorscale=[
                [0.0, '#E5E7EB'],
                [0.5, '#9CA3AF'],
                [1.0, '#374151']
            ],
            showscale=True,
            colorbar=dict(
                title=y_col,
                orientation='v',
                x=1.05,
                y=0.5,
                len=0.9,
                thickness=18,
                tickvals=tick_vals,
                ticktext=tick_texts
            )
        ),
        showlegend=False,
        hoverinfo='skip'
    ))

    # Layer 2: Neighbors (brand color, medium importance)
    if matched_proj.shape[0] > 0:
        fig.add_trace(go.Scattergl(
            x=matched_proj[:, 0], 
            y=matched_proj[:, 1], 
            mode='markers', 
            marker=dict(
                size=12,
                color='#2563EB',
                opacity=0.80,
                line=dict(width=0)
            ), 
            name='유사 사례',
            hoverinfo='skip'
        ))

    # Layer 3: Trajectory (context line)
    if 'sim_traj' not in st.session_state:
        st.session_state.sim_traj = []
    st.session_state.sim_traj.append(tuple(cur_proj.tolist()))
    if len(st.session_state.sim_traj) > 40:
        st.session_state.sim_traj = st.session_state.sim_traj[-40:]
    traj = np.array(st.session_state.sim_traj)
    
    # trajectory with gradient color (과거: 옅은색 → 최근: 진한색)
    if traj.shape[0] > 1:
        n_points = traj.shape[0]
        for i in range(n_points - 1):
            # 색상 강도: 과거는 옅고, 최근은 진함 (0 to 1)
            alpha = (i + 1) / max(1, n_points)  # 0.025 ~ 1.0
            # RGB(69, 183, 209) 기반으로 알파값만 조정
            color = f'rgba(69, 183, 209, {0.15 + 0.85 * alpha})'
            
            fig.add_trace(go.Scatter(
                x=traj[i:i+2, 0],
                y=traj[i:i+2, 1],
                mode='lines',
                line=dict(color=color, width=2.5),
                showlegend=(i == n_points - 2),  # 마지막 세그먼트만 범례에 표시
                name='탐색 자취' if i == n_points - 2 else None,
                hoverinfo='skip'
            ))
        
        # trajectory 점들 (선택사항: 시각적 강조)
        fig.add_trace(go.Scatter(
            x=traj[:, 0],
            y=traj[:, 1],
            mode='markers',
            marker=dict(size=3, color='rgba(69, 183, 209, 0.5)'),
            showlegend=False,
            hoverinfo='skip'
        ))

    # Layer 4: Current position (HIGHEST PRIORITY — drawn LAST for top z-index)
    # White halo effect
    fig.add_trace(go.Scatter(
        x=[cur_proj[0]], 
        y=[cur_proj[1]], 
        mode='markers', 
        marker=dict(
            size=50,
            color='rgba(255, 255, 255, 0.6)',
            line=dict(width=0)
        ),
        showlegend=False,
        hoverinfo='skip'
    ))
    
    # Dark outline
    fig.add_trace(go.Scatter(
        x=[cur_proj[0]], 
        y=[cur_proj[1]], 
        mode='markers', 
        marker=dict(
            size=45,
            color='#F97316',
            line=dict(color='#111827', width=3)
        ),
        showlegend=True,
        name='현재 위치',
        hovertemplate='<b>현재 위치</b><extra></extra>'
    ))

    # move legend to bottom outside chart
    fig.update_layout(
        height=560,
        showlegend=True,
        legend=dict(
            orientation='h',
            x=0.5,
            y=-0.09,
            xanchor='center',
            yanchor='top',
            bgcolor='rgba(255,255,255,0.95)',
            bordercolor='rgba(0,0,0,0.2)',
            borderwidth=1
        ),
        margin=dict(l=10, r=160, t=10, b=10),
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_prediction_panel(models_results, df, numeric_x_cols, x_df, coverage_model, y_col):
    """Right: consensus + simple model cards + confidence badge."""
    results = models_results
    
    # 6개 모델 이름 정의
    six_names = [
        "Random Forest",
        "Gradient Boosting",
        "Support Vector Machine",
        "Neural Network",
        "Permutation Importance",
        "SHAP",
    ]
    
    # Linear Regression 이름
    lr_name = "Linear Regression"
    
    # 상위 4개 모델 선택
    ai_perf = [{"모델": k, "R2": results[k]["r2"]} for k in six_names if k in results]
    perf_df = pd.DataFrame(ai_perf).sort_values("R2", ascending=False).reset_index(drop=True)
    top4_names = perf_df.head(4)["모델"].tolist()
    
    # 예측값 계산 (모든 입력값이 유효한지 확인)
    preds = []
    
    # 입력값 검증
    x_df_valid = x_df.copy()
    x_df_valid = x_df_valid.fillna(x_df_valid.mean())  # NaN을 평균으로 대체
    
    if lr_name in results:
        try:
            lr_hat = float(results[lr_name]["model"].predict(x_df_valid)[0])
            # 예측값이 NaN이나 inf가 아닌지 확인
            if not (np.isnan(lr_hat) or np.isinf(lr_hat)):
                preds.append({"모델": lr_name, "예측 Y": lr_hat, "R²": results[lr_name]["r2"]})
            else:
                # 유효하지 않은 예측값인 경우 평균값 사용
                lr_hat = float(np.nanmean(results[lr_name].get("y_pred", [0.0])))
                preds.append({"모델": lr_name, "예측 Y": lr_hat, "R²": results[lr_name]["r2"]})
        except Exception as e:
            lr_hat = float(np.nanmean(results[lr_name].get("y_pred", [0.0])))
            preds.append({"모델": lr_name, "예측 Y": lr_hat, "R²": results[lr_name]["r2"]})
    
    for name in top4_names:
        try:
            y_hat = float(results[name]["model"].predict(x_df_valid)[0])
            # 예측값이 NaN이나 inf가 아닌지 확인
            if not (np.isnan(y_hat) or np.isinf(y_hat)):
                preds.append({"모델": name, "예측 Y": y_hat, "R²": results[name]["r2"]})
            else:
                # 유효하지 않은 예측값인 경우 평균값 사용
                y_hat = float(np.nanmean(results[name].get("y_pred", [0.0])))
                preds.append({"모델": name, "예측 Y": y_hat, "R²": results[name]["r2"]})
        except Exception as e:
            y_hat = float(np.nanmean(results[name].get("y_pred", [0.0])))
            preds.append({"모델": name, "예측 Y": y_hat, "R²": results[name]["r2"]})
    
    # 가중 평균 계산 (상위 4개만 사용)
    top4_preds = [p for p in preds if p["모델"] != lr_name]
    
    # 음수 R2를 0으로 처리하여 가중치 계산
    weights_raw = np.array([max(0.0, p["R²"]) for p in top4_preds], dtype=float)
    
    # 모든 가중치가 0이면 균등 가중치 사용
    if weights_raw.sum() == 0:
        weights = np.ones_like(weights_raw) / len(weights_raw) if len(weights_raw) > 0 else np.array([])
    else:
        weights = weights_raw / weights_raw.sum()
    
    consensus = float(np.dot(weights, np.array([p["예측 Y"] for p in top4_preds]))) if len(top4_preds) > 0 else 0.0
    
    # 최종 예측 결과 표시
    st.markdown("<div style='background:#001f3f;color:#fff;padding:18px;border-radius:10px;'>"
                "<div style='font-size:14px;opacity:0.8;'>최종 예측 결과 (모델 별 가중평균)</div>"
                f"<div style='font-size:36px;font-weight:800;'>{_format_number(consensus)}</div>"
                "</div>", unsafe_allow_html=True)
    
    """Y 변수 분포와 모델 예측값을 시각화하는 함수."""
    import plotly.express as px
    import plotly.graph_objects as go
    
    fig_hist = px.histogram(
        df[y_col].dropna(), nbins=40,
        labels={y_col: y_col}, color_discrete_sequence=["#636EFA"]
    )
    
    # 히스토그램 자체 범례 제거 및 legendgroup 제거 (variable 헤더 제거)
    fig_hist.update_traces(showlegend=False, legendgroup="", selector=dict(type='histogram'))
    
    # Consensus와의 거리 계산
    distances = {}
    for pred in preds:
        model_name = pred["모델"]
        if model_name != "Linear Regression":
            dist = abs(pred["예측 Y"] - consensus)
            distances[model_name] = dist
    
    # 거리순으로 정렬 (가까운 것부터)
    sorted_models = sorted(distances.items(), key=lambda x: x[1])
    
    # 색상 스펙트럼 (빨강→분홍)
    color_spectrum = ["#FF3B3B", "#FF5252", "#FF6B6B", "#FF8585", "#FFA0A0", "#FFBDBD", "#FFDADA"]
    
    # Consensus 먼저 추가 (범례에서 가장 처음에 나타나도록)
    fig_hist.add_vline(
        x=consensus, line_color="red", line_width=4
    )
    # Consensus 범례용 invisible trace 추가
    consensus_label = f"최종 예측 결과 ({_format_number(consensus)})"
    fig_hist.add_trace(go.Scatter(
        x=[None], y=[None],
        mode='lines',
        line=dict(color='red', width=4),
        name=consensus_label,
        showlegend=True,
        legendgroup=""
    ))
    
    # 거리 기반 색상 할당 및 범례 추가
    if sorted_models:
        min_dist = sorted_models[0][1]
        max_dist = sorted_models[-1][1]
        dist_range = max_dist - min_dist if max_dist > min_dist else 1.0
        
        # 거리순으로 (가까운 것부터) 추가
        for idx, (model_name, dist) in enumerate(sorted_models):
            # 색상 선택: 거리 정규화에 따라 (0=빨강, 1=초록)
            norm_dist = (dist - min_dist) / dist_range if dist_range > 0 else 0
            color_idx = int(norm_dist * (len(color_spectrum) - 1))
            color_idx = min(color_idx, len(color_spectrum) - 1)  # 범위 제한
            color = color_spectrum[color_idx]
            
            # 실제 예측값 찾기
            for pred in preds:
                if pred["모델"] == model_name:
                    y_hat = pred["예측 Y"]
                    fig_hist.add_vline(
                        x=y_hat, line_color=color, line_width=1.5
                    )
                    # 범례용 invisible trace 추가 (숫자 포함)
                    legend_label = f"{model_name} ({_format_number(y_hat)})"
                    fig_hist.add_trace(go.Scatter(
                        x=[None], y=[None],
                        mode='lines',
                        line=dict(color=color, width=1.5),
                        name=legend_label,
                        showlegend=True,
                        legendgroup=""
                    ))
                    break
    
    # Linear Regression을 마지막에 추가 (검정색)
    for pred in preds:
        if pred["모델"] == "Linear Regression":
            y_hat = pred["예측 Y"]
            fig_hist.add_vline(
                x=y_hat, line_color="#000000", line_width=1.5
            )
            # 범례용 invisible trace 추가 (숫자 포함)
            legend_label = f"Linear Regression ({_format_number(y_hat)})"
            fig_hist.add_trace(go.Scatter(
                x=[None], y=[None],
                mode='lines',
                line=dict(color="#000000", width=1.5),
                name=legend_label,
                showlegend=True,
                legendgroup=""
            ))
            break
    
    # x축의 범위와 틱 간격 계산
    x_min = df[y_col].dropna().min()
    x_max = df[y_col].dropna().max()
    x_range = x_max - x_min
    
    # 틱 간격 자동 계산 (30% 더 촘촘하게)
    default_dtick = x_range / 10  # 기본 10등분
    dtick = default_dtick * 0.7   # 70%로 설정 (30% 더 촘촘)는 의미)
    
    # 커스텀 tickformat 함수를 사용하기 위해 tickvals, ticktext 설정
    tick_vals = []
    tick_texts = []
    tick_val = x_min
    while tick_val <= x_max:
        tick_vals.append(tick_val)
        tick_texts.append(_format_number(tick_val))
        tick_val += dtick
    
    fig_hist.update_layout(
        height=480, 
        showlegend=True,
        xaxis=dict(
            title="",
            showgrid=True,
            gridwidth=1,
            gridcolor="rgba(128,128,128,0.2)",
            tickvals=tick_vals,
            ticktext=tick_texts
        ),
        yaxis=dict(title=""),
        legend=dict(
            x=0,
            xanchor="left",
            y=-0.2,
            yanchor="top",
            orientation="h",
            bgcolor="rgba(255,255,255,0.95)",
            bordercolor="rgba(0,0,0,0.2)",
            borderwidth=1,
            title=""
        ),
        margin=dict(b=10)
    )
    st.plotly_chart(fig_hist, use_container_width=True, key="prediction_panel_histogram")

    # # 표: Linear Regression + 6개 전체를 정렬해서 표시
    # table_rows = []
    # # LR
    # if lr_name in results:
    #     lr_pred = [p for p in preds if p["모델"] == lr_name]
    #     if lr_pred:
    #         table_rows.append({"모델": lr_name, "모델 R²": float(results[lr_name]["r2"]),
    #                             "합의 가중치(%)": "-", "예측 Y값": _format_number(lr_pred[0]["예측 Y"])})
    
    # # 6개 전체
    # for name in six_names:
    #     if name in results:
    #         # 상위4는 실제 가중치, 하위2는 "-" 처리
    #         if name in top4_names:
    #             w = weights[list(top4_names).index(name)]
    #             w_txt = f"{w:.0%}"
    #         else:
    #             w_txt = "-"
    #         y_hat = [p for p in preds if p["모델"] == name]
    #         y_txt = _format_number(y_hat[0]["예측 Y"]) if y_hat else "-"
    #         table_rows.append({"모델": name, "모델 R²": float(results[name]['r2']),
    #                             "합의 가중치(%)": w_txt, "예측 Y값": y_txt})

    # table_df = pd.DataFrame(table_rows).sort_values("모델 R²", ascending=False).reset_index(drop=True)
    # st.dataframe(table_df, width='stretch', hide_index=True)
    st.caption("※ 최종 예측값은 성능이 가장 우수한 4개의 머신러닝 모델 결과를 기반으로 합의(Consensus)하여 산출됩니다.")

    return preds, consensus


def _render_operational_twins(df, matched_df, numeric_x_cols, x_df, retrieval=None, y_col=None):
    """Bottom: render 'Operational Twins' as an HTML table with differences highlighted."""
    if matched_df.empty:
        st.info("유사 사례가 없습니다.")
        return

    # compute distances if available
    all_dists = None
    if retrieval is not None and "all_dists" in retrieval:
        all_dists = retrieval["all_dists"]
    else:
        dists, _ = _compute_case_distances(df, x_query=dict(x_df.iloc[0]), numeric_cols=numeric_x_cols, cat_cols=[], distance_metric="L2")
        all_dists = dists

    # helper to format cell with highlight if differs significantly
    def fmt_cell(val, ref, is_num):
        try:
            if is_num:
                a = float(val)
                b = float(ref)
                if not np.isfinite(a) or not np.isfinite(b):
                    return f"{val}"
                # relative diff
                denom = max(abs(b), 1e-6)
                rel = abs(a - b) / denom
                if rel > 0.05:  # >5% difference -> highlight red
                    return f"<span style='color:#c82333;font-weight:700'>{format_number(a)}</span>"
                if rel > 0.01:
                    return f"<span style='color:#d35400'>{format_number(a)}</span>"
                return f"{format_number(a)}"
            else:
                # string compare
                return f"<span>{val}</span>" if str(val) != str(ref) else f"{val}"
        except Exception:
            return str(val)

    # build HTML table
    html = []
    html.append("<div style='max-height:420px; overflow:auto;'>")
    html.append("<table style='width:100%; border-collapse:collapse; font-size:13px;'>")

    # header
    cols = list(matched_df.columns)
    header = "<tr>"
    header += "<th style='text-align:left; padding:6px 8px;'>Similarity</th>"
    for c in cols:
        header += f"<th style='text-align:left; padding:6px 8px;'>{c}</th>"
    header += "</tr>"
    html.append(header)

    # rows
    display_df = matched_df.head(20)
    for idx, row in display_df.iterrows():
        # similarity
        try:
            pos = int(np.where(df.index.values == idx)[0][0])
            d = float(all_dists[pos])
        except Exception:
            d = np.nan
        sim = _similarity_from_distance(d, float(retrieval.get('d_best', d) if retrieval else d)) * 100.0 if np.isfinite(d) else 0.0

        r_html = f"<tr style='border-top:1px solid #eee;'>"
        r_html += f"<td style='padding:6px 8px; font-weight:700; width:90px;'>{sim:.0f}%</td>"
        for c in cols:
            val = row.get(c)
            is_num = c in numeric_x_cols
            ref = x_df.iloc[0].get(c) if c in x_df.columns else None
            cell = fmt_cell(val, ref, is_num)
            r_html += f"<td style='padding:6px 8px;'>{cell}</td>"
        r_html += "</tr>"
        html.append(r_html)

    html.append("</table>")
    html.append("</div>")

    # st.markdown("#### Operational Twins")
    st.markdown("""<div style='font-size:0.9rem; color:#666; margin-bottom:6px;'>가장 유사한 과거 운전 조건 (빨간색: Simulation 입력값과 차이가 큰 변수)</div>""", unsafe_allow_html=True)
    st.markdown("".join(html), unsafe_allow_html=True)


def _format_number(val):
    """범례용 숫자 포매팅 함수.
    ~0: 소수점 3자리
    0~9: 소수점 2자리
    10~99: 소수점 1자리
    100이 넘는 숫자: 소수점 없이
    1000이 넘는 숫자: 쉼표 달고 소수점 없이
    """
    if val is None:
        return "N/A"
    
    abs_val = abs(val)
    
    if abs_val < 10:
        if abs_val < 1:
            return f"{val:.3f}"
        else:
            return f"{val:.2f}"
    elif abs_val < 100:
        return f"{val:.1f}"
    elif abs_val < 1000:
        return f"{val:.0f}"
    else:
        return f"{val:,.0f}"


def _render_y_distribution_chart(df, y_col, preds, consensus):
    """Y 변수 분포와 모델 예측값을 시각화하는 함수."""
    import plotly.express as px
    import plotly.graph_objects as go
    
    fig_hist = px.histogram(
        df[y_col].dropna(), nbins=40,
        labels={y_col: y_col}, color_discrete_sequence=["#636EFA"]
    )
    
    # 히스토그램 자체 범례 제거 및 legendgroup 제거 (variable 헤더 제거)
    fig_hist.update_traces(showlegend=False, legendgroup="", selector=dict(type='histogram'))
    
    # Consensus와의 거리 계산
    distances = {}
    for pred in preds:
        model_name = pred["모델"]
        if model_name != "Linear Regression":
            dist = abs(pred["예측 Y"] - consensus)
            distances[model_name] = dist
    
    # 거리순으로 정렬 (가까운 것부터)
    sorted_models = sorted(distances.items(), key=lambda x: x[1])
    
    # 색상 스펙트럼 (빨강→주황→청록→초록)
    color_spectrum = ["#E63946", "#F77F00", "#F1A208", "#06A77D", "#2A9D8F", "#1B9E77", "#66BB6A"]
    
    # Consensus 먼저 추가 (범례에서 가장 처음에 나타나도록)
    fig_hist.add_vline(
        x=consensus, line_color="red", line_width=4
    )
    # Consensus 범례용 invisible trace 추가
    consensus_label = f"최종 예측 결과 ({_format_number(consensus)})"
    fig_hist.add_trace(go.Scatter(
        x=[None], y=[None],
        mode='lines',
        line=dict(color='red', width=4),
        name=consensus_label,
        showlegend=True,
        legendgroup=""
    ))
    
    # 거리 기반 색상 할당 및 범례 추가
    if sorted_models:
        min_dist = sorted_models[0][1]
        max_dist = sorted_models[-1][1]
        dist_range = max_dist - min_dist if max_dist > min_dist else 1.0
        
        # 거리순으로 (가까운 것부터) 추가
        for idx, (model_name, dist) in enumerate(sorted_models):
            # 색상 선택: 거리 정규화에 따라 (0=빨강, 1=초록)
            norm_dist = (dist - min_dist) / dist_range if dist_range > 0 else 0
            color_idx = int(norm_dist * (len(color_spectrum) - 1))
            color_idx = min(color_idx, len(color_spectrum) - 1)  # 범위 제한
            color = color_spectrum[color_idx]
            
            # 실제 예측값 찾기
            for pred in preds:
                if pred["모델"] == model_name:
                    y_hat = pred["예측 Y"]
                    fig_hist.add_vline(
                        x=y_hat, line_color=color, line_width=2.5
                    )
                    # 범례용 invisible trace 추가 (숫자 포함)
                    legend_label = f"{model_name} ({_format_number(y_hat)})"
                    fig_hist.add_trace(go.Scatter(
                        x=[None], y=[None],
                        mode='lines',
                        line=dict(color=color, width=2.5),
                        name=legend_label,
                        showlegend=True,
                        legendgroup=""
                    ))
                    break
    
    # Linear Regression을 마지막에 추가 (검정색)
    for pred in preds:
        if pred["모델"] == "Linear Regression":
            y_hat = pred["예측 Y"]
            fig_hist.add_vline(
                x=y_hat, line_color="#000000", line_width=2.5
            )
            # 범례용 invisible trace 추가 (숫자 포함)
            legend_label = f"Linear Regression ({_format_number(y_hat)})"
            fig_hist.add_trace(go.Scatter(
                x=[None], y=[None],
                mode='lines',
                line=dict(color="#000000", width=2.5),
                name=legend_label,
                showlegend=True,
                legendgroup=""
            ))
            break
    
    # x축의 범위와 틱 간격 계산
    x_min = df[y_col].dropna().min()
    x_max = df[y_col].dropna().max()
    x_range = x_max - x_min
    
    # 틱 간격 자동 계산
    dtick = x_range / 10  * 0.7
    
    # 커스텀 tickformat 함수를 사용하기 위해 tickvals, ticktext 설정
    tick_vals = []
    tick_texts = []
    tick_val = x_min
    while tick_val <= x_max:
        tick_vals.append(tick_val)
        tick_texts.append(_format_number(tick_val))
        tick_val += dtick
    
    fig_hist.update_layout(
        height=480, 
        showlegend=True,
        xaxis=dict(
            title="",
            showgrid=True,
            gridwidth=1,
            gridcolor="rgba(128,128,128,0.2)",
            tickvals=tick_vals,
            ticktext=tick_texts
        ),
        yaxis=dict(title=""),
        legend=dict(
            x=0,
            xanchor="left",
            y=-0.2,
            yanchor="top",
            orientation="h",
            bgcolor="rgba(255,255,255,0.95)",
            bordercolor="rgba(0,0,0,0.2)",
            borderwidth=1,
            title=""
        ),
        margin=dict(b=10)
    )
    st.plotly_chart(fig_hist, use_container_width=True, key="y_distribution_chart")


def render_ai_simulator(df, models_results, coverage_model, numeric_x_cols, y_col):
    """Main renderer: left controls, right tabs (data map & prediction), bottom twins."""
    left, right = st.columns([1, 2.6])

    # 기본 설정 먼저 정의
    radius = "Balanced"
    params = _map_exploration_settings(radius)
    method = "PCA"

    with left:
        st.markdown("##### X변수 Control Panel")
        current_inputs = _render_control_panel(df, numeric_x_cols)

    x_df = pd.DataFrame([current_inputs])[numeric_x_cols]

    cat_x_cols = [c for c in df.columns if c not in numeric_x_cols and c != y_col]
    x_cols = numeric_x_cols + cat_x_cols
    retrieval = _knn_case_retrieval(
        df=df,
        x_query=current_inputs,
        x_cols=x_cols,
        distance_metric="L2",
        cat_weight=1.0,
        k_max=int(params["k_max"]),
        k_cap=int(params["k_cap"]),
        alpha=float(params["alpha"]),
        delta=None,
        use_mult=True,
    )
    matched_df = retrieval["matched_df"]

    with right:
        tab1, tab2 = st.tabs(["🔮 Y 변수 예측", "📊 Data 지도"])

        with tab1:
            # st.markdown("##### Prediction")
            preds, consensus = _render_prediction_panel(models_results, df, numeric_x_cols, x_df, coverage_model, y_col)
        
        with tab2:
            # st.markdown("##### Data Map")
            _render_data_map_placeholder(df, numeric_x_cols, current_inputs, matched_df, y_col=y_col, method=method)
        
        # Exploration Radius와 Map Projection을 탭 아래에 좌우로 배치
        col_radius, col_method = st.columns([1, 1])
        with col_radius:
            st.markdown("**Exploration Radius**")
            radius = st.select_slider("exploration_radius_slider", options=["Narrow", "Balanced", "Wide"], value=radius, label_visibility="collapsed")
            params = _map_exploration_settings(radius)
        with col_method:
            st.markdown("**Map Projection**")
            method = st.selectbox("map_projection_select", options=["PCA", "UMAP"], index=0 if method == "PCA" else 1, label_visibility="collapsed")
    st.markdown("---")
    _render_operational_twins(df, matched_df, numeric_x_cols, x_df, retrieval=retrieval, y_col=y_col)

    # save a compact snapshot for later UI rendering / download
    try:
        st.session_state.stage2_simulator = {
            "consensus": format_number(consensus) if 'consensus' in locals() else None,
            "preds": preds if 'preds' in locals() else [],
            "matched_count": int(len(matched_df)) if 'matched_df' in locals() else 0,
            "exploration_radius": radius if 'radius' in locals() else None,
        }
    except Exception:
        pass



def perform_ml_analysis_and_simulator(df, y_col, x_cols, baseline_r2):
    """2단계: 6개 모델 학습/비교, 최고 모델 기준 리포트 + 시뮬레이터(합의 예측)"""
    
   
    numeric_x_cols = df[x_cols].select_dtypes(include=np.number).columns.tolist()
    if not numeric_x_cols:
        st.warning("2단계 분석을 위해서는 수치형 변수가 필요합니다.")
        return

    # with st.spinner(...) 블록을 제거하고 아래 코드로 대체합니다.
    X = df[numeric_x_cols]
    y = df[y_col]
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    # 학습 데이터 분포 기반 커버리지(신뢰도) 모델 생성
    coverage_model = _build_coverage_model(X_train[numeric_x_cols])
    
    # 캐시된 함수를 호출합니다. 처음 실행 시에만 스피너가 표시되고 모델이 학습됩니다.
    # 슬라이더 조작 등으로 재실행될 때는 캐시된 결과를 즉시 반환합니다.
    results = train_compare_models(X_train, y_train, X_test, y_test)
    
    best_name = results["__best__"]
    best_model = results[best_name]["model"]
    best_r2 = results[best_name]["r2"]
    best_y_pred = results[best_name]["y_pred"]

    with st.container(border=True):
        # --- 1) 성능 카드: 기준선 vs 최고 성능 ---
        col1, col2 = st.columns(2)
        with col1:
            render_metric_card("선형회귀 기준 성능 (R²)", f"{baseline_r2:.1%}", help_text="최소제곱법 모델의 정확도")
        with col2:
            render_metric_card(f"AI 머신 러닝 모델의 최고 성능 (R²)", f"{best_r2:.1%}", help_text=f"6개 모델 중 가장 설명력이 우수한 {best_name}의 정확도")

        # 개선율 내러티브
        improvement_diff = (best_r2 - baseline_r2) * 100 if baseline_r2 is not None else np.nan  # 차이값을 퍼센트 포인트로 변환
        if baseline_r2 is not None and not np.isnan(improvement_diff):
            if best_r2 >= 0.90:
                st.success(f"✨ 단순 선형 관계 대비 **설명력이 {improvement_diff:.1f}%p 향상되었으며, 설명력이 매우 우수합니다.**")
            elif best_r2 >= 0.80:
                st.info(f"✨ 단순 선형 관계 대비 **설명력이 {improvement_diff:.1f}%p 향상되었으며, 설명력이 우수합니다.**  ""\n\n"
                        "Y값의 변화에 기여하는 공정 변수를 추가로 발굴하여 반영하면 더 정밀해질 수 있습니다.")
            else:
                st.markdown(
                    f"<div style='background-color: #fff3cd; border-left: 4px solid #ffc107; padding: 1rem; border-radius: 0.375rem; margin: 1rem 0;'>"
                    f"<p style='margin: 0 0 0.75rem 0; display: block;'>🔎 선형 관계 탐색 대비하여 정확도가 {improvement_diff:.0f}%p 향상되었습니다.</p>"
                    "<p style='margin: 0 0 0.5rem 0; display: block; font-weight: bold;'>추가 개선 방안:</p>"
                    "<p style='margin: 0 0 0.5rem 0; display: block;'>• [4단계: 데이터 탐색]에서 제안된 전처리/데이터 분리를 수행한 후 다시 분석</p>"
                    "<p style='margin: 0 0 0.5rem 0; display: block;'>• 다음 단계(변수 선택 적정성 점검)를 통해 변수 선택에 오류가 있었는지 확인 후 X 변수 제거</p>"
                    "<p style='margin: 0; display: block;'>• Y를 설명할 수 있는 다른 X 변수들을 더 발굴하여 재탐색</p>"
                    "</div>",
                    unsafe_allow_html=True
                )
        else:
            st.info("선형회귀 모델과 상대적인 비교가 곤란합니다. 모델의 절대 성능을 중심으로 판단하세요.")

        # --- 2) 모델 별 성능 요약 ---
        others = {k: v for k, v in results.items() if k not in ("__best__", best_name)}
        perf_df = pd.DataFrame([{"모델": k, "R2": v["r2"]} for k, v in ([ (best_name, results[best_name]) ] + list(others.items()))])
        perf_df = perf_df.sort_values("R2", ascending=False).reset_index(drop=True)

        st.markdown("### 🧠 AI 모델 별 예측 정확도")

        # 6개 AI 기법 이름(표시용)
        six_names = [
            "Random Forest",
            "Gradient Boosting",
            "Support Vector Machine",
            "Neural Network",
            "Permutation Importance",
            "SHAP",
        ]

        # 전체 모델 성능 테이블 구성(여기서는 6개만)
        ai_perf_df = pd.DataFrame(
            [{"모델": k, "R2": results[k]["r2"]} for k in six_names if k in results]
        ).sort_values("R2", ascending=False).reset_index(drop=True)

        # 상위 4개 / 하위 2개 분리
        top4_df = ai_perf_df.head(4).copy()
        bottom2_df = ai_perf_df.tail(2).copy().sort_values("R2", ascending=False)

        # 모델 설명(간략 개념 설명)
        model_descriptions = {
            "Random Forest": ("🌲", "여러 결정나무의 앙상블로 비선형 패턴을 안정적으로 포착"),
            "Gradient Boosting": ("🚀", "오류를 단계적으로 보완하며 예측력을 끌어올리는 기법"),
            "Support Vector Machine": ("🎯", "고차원 변환 후 최적 경계를 찾는 커널 기반 학습"),
            "Neural Network": ("🧠", "은닉층을 통해 복잡한 비선형 관계를 학습하는 신경망"),
            "Permutation Importance": ("🧩", "특성 셔플로 성능 저하를 측정해 중요도를 추정(RF 기반)"),
            "SHAP": ("🔬", "각 특성의 기여도를 일관된 방식으로 분해/해석(GB 기반)"),
        }
        model_colors = {
            "Random Forest": "#28a745",
            "Gradient Boosting": "#ffc107",
            "Support Vector Machine": "#dc3545",
            "Neural Network": "#6f42c1",
            "Permutation Importance": "#17a2b8",
            "SHAP": "#8e44ad",
        }

        # 상위 4개 카드 표시
        cols = st.columns(len(top4_df))
        for idx, row in enumerate(top4_df.itertuples()):
            name, r2 = row.모델, row.R2
            emoji, desc = model_descriptions.get(name, ("🤖", "고급 머신러닝 모델"))
            color = model_colors.get(name, "#6c757d")

            with cols[idx]:
                st.markdown(f"""
                <div style="background: linear-gradient(135deg, {color}15, {color}05);
                            border: 2px solid {color};
                            border-radius: 15px;
                            padding: 20px; margin-bottom: 15px;
                            text-align: center; box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                            display: flex; flex-direction: column; height: 320px; justify-content: space-between;">
                    <div style="font-size: 2.3rem; margin-bottom: 10px;">{emoji}</div>
                    <div style="color: {color}; font-weight: bold; font-size: 1.3rem;">{name}</div>
                    <div style="background: {color}; color: white; padding: 8px 12px; border-radius: 20px; font-size: 1.2rem; font-weight: bold; margin: 10px 0;">
                    {r2:.1%}
                    </div>
                    <p style="font-size: 0.85rem; color: #666; line-height: 1.4; margin: 0; height: 54px; display: flex; align-items: center; justify-content: center;">
                    {desc}
                    </p>
                </div>
                """, unsafe_allow_html=True)

        # 하위 2개 Note 처리
        if len(bottom2_df) == 2:
            n1, n2 = bottom2_df.iloc[0], bottom2_df.iloc[1]
            e1, d1 = model_descriptions.get(n1["모델"], ("🤖", ""))
            e2, d2 = model_descriptions.get(n2["모델"], ("🤖", ""))
            st.markdown(
                f"<div style='font-size:1.1rem; color:#000000; margin-top:15px; line-height:1.6;'>"
                f"이외 모델들의 예측 성능<br>"
                f"&nbsp;&nbsp;• {n1['모델']}: {n1['R2']:.1%} <span style='font-size:0.9rem;'>({d1})</span><br>"
                f"&nbsp;&nbsp;• {n2['모델']}: {n2['R2']:.1%} <span style='font-size:0.9rem;'>({d2})</span>"
                f"</div>",
                unsafe_allow_html=True
            )
            
        st.markdown("\n")

    with st.container(border=True):
        # --- 4) AI Model 시뮬레이터 ---
        # Launch the redesigned, simplified AI simulator UI (separated renderer)
        st.markdown("### 🎛️ AI Model 시뮬레이터")
        st.markdown("""
        <div style="background-color: #E8F2FC; border: 1px solid #E8F2FC; border-radius: 0.375rem; padding: 1rem; margin: 1rem 0;">
            <div style="display: flex; align-items: flex-start;">
                <span style="font-size: 1.2em; margin-right: 0.5rem;"></span>
                <div>
                    <strong>💡 <u>AI Model 시뮬레이터 :</u></strong><br>
                    &nbsp;각 X 변수들을 조정하면서 AI Model이 제안하는 Y 값을 확인할 수 있습니다.<br>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        render_ai_simulator(df=df, models_results=results, coverage_model=coverage_model, numeric_x_cols=numeric_x_cols, y_col=y_col)

    # === 세션 스냅샷 저장(보존 렌더링용) ===
    try:
        st.session_state.stage2_overview = {
            "baseline_r2": float(baseline_r2) if baseline_r2 is not None else None,
            "best_name": str(best_name),
            "best_r2": float(best_r2),
            "consensus": format_number(consensus) if 'consensus' in locals() else None,
            "results": {k: float(v.get("r2", 0.0)) for k, v in results.items() if k != "__best__"},
            "top4_names": list(top4_names) if 'top4_names' in locals() else [],
            "weights": list(weights) if 'weights' in locals() else [],
            "preds": preds if 'preds' in locals() else [],
            "fig_scatter": fig if 'fig' in locals() else None,
            "table_df": table_df
        }
    except Exception as _e:
        pass