import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import plotly.graph_objects as go
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.linear_model import LinearRegression, Lasso, ElasticNet, ElasticNetCV
from sklearn.linear_model import RidgeCV, LassoCV, HuberRegressor, QuantileRegressor, TheilSenRegressor, RANSACRegressor
from sklearn.model_selection import GridSearchCV
from sklearn.pipeline import make_pipeline
from sklearn.metrics import r2_score
import cProfile
import pstats
import io

# 코드 소요 시간 분석 프로파일링
def profile_run(label, fn, *args, **kwargs):
    pr = cProfile.Profile()
    pr.enable()
    result = fn(*args, **kwargs)
    pr.disable()

    s = io.StringIO()
    ps = pstats.Stats(pr, stream=s).sort_stats("cumtime")
    ps.print_stats(30)

    st.subheader(f"⏱ Profiling result: {label}")
    st.text(s.getvalue())

    return result

def actual_vs_pred_plot(y_true, y_pred, title="", square_size=600, enforce_square=True):
    # 공통: 데이터 범위를 하나로 맞춰 1:1 대각선 포함
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)

    vmin = float(np.nanmin([y_true.min(), y_pred.min()]))
    vmax = float(np.nanmax([y_true.max(), y_pred.max()]))

    rng = [vmin, vmax]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=y_true, y=y_pred, mode='markers',
        name='Actual vs Predicted', opacity=0.7,
        marker=dict(line=dict(width=0))
    ))
    fig.add_trace(go.Scatter(
        x=rng, y=rng, mode='lines',
        name='y=x 기준선 (완벽한 예측선)',
        line=dict(color='red', dash='dash')
    ))

    # 축 설정: 범위 동일 + 단위 비율 1:1 고정
    fig.update_xaxes(
        title_text="Actual", range=rng,
        tickfont=dict(color='black'),
        title_font=dict(color='black'),
        scaleanchor="y",  # x축 스케일을 y축에 고정
        scaleratio=1,     # 1:1 비율
        constrain="domain"
    )
    fig.update_yaxes(
        title_text="Predicted", range=rng,
        tickfont=dict(color='black'),
        title_font=dict(color='black'),
        constrain="domain"
    )

    # 레이아웃
    layout_kwargs = dict(
        title=dict(text=title or "Actual vs Predicted", font=dict(color='black', size=16)),
        legend=dict(
            x=0.02, y=0.98,
            bgcolor='rgba(255,255,255,0.8)',
            bordercolor='black', borderwidth=1,
            font=dict(color='black')
        ),
        margin=dict(l=50, r=50, t=50, b=50),
        paper_bgcolor="white",
        plot_bgcolor="white"
    )

    # 정방형(캔버스 가로=세로) 보장: width='content'와 함께 사용
    if enforce_square:
        layout_kwargs.update(dict(width=square_size, height=square_size))

    fig.update_layout(**layout_kwargs)
    return fig

@st.cache_resource
def perform_linear_regression(df_ready, y_column, x_columns):

    # --- 1단계: 기준점 설정 (항상 표시) ---

    X = df_ready[x_columns].copy()
    y = df_ready[y_column].copy()

    # 범주형 변수들을 완전히 제외하고 수치형 변수만 선택
    # 더 확실한 방법: object, string, category 타입을 제외
    numeric_cols = []
    excluded_cat_cols = []
    
    for col in x_columns:
        if X[col].dtype in ['object', 'string', 'category'] or not pd.api.types.is_numeric_dtype(X[col]):
            excluded_cat_cols.append(col)
        else:
            numeric_cols.append(col)
    
    if not numeric_cols:
        st.warning("선형회귀분석을 위한 수치형 변수가 없습니다.")
        return {"r2_test": 0.0}
    
    # 수치형 변수만으로 X 재구성
    X = X[numeric_cols]
    
    # y를 확실히 수치형으로 변환 (문자열 숫자 등 처리)
    try:
        y = pd.to_numeric(y, errors='coerce')
    except Exception:
        st.error("Y 변수를 수치형으로 변환할 수 없습니다.")
        return {"r2_test": 0.0}
    
    # 범주형 변수가 제외되었음을 사용자에게 알림 - 일시 비활성화
    # if excluded_cat_cols:
    #     with st.expander(f"ℹ️ 범주형 변수는 분석에서 제외"):
    #         st.caption(f"선형회귀분석에서는 수치형 변수만 사용됩니다. (제외된 변수 {len(excluded_cat_cols)}개: {', '.join(excluded_cat_cols)})")

    # 데이터 타입 재확인 및 강제 변환
    for col in X.columns:
        if not pd.api.types.is_numeric_dtype(X[col]):
            try:
                X[col] = pd.to_numeric(X[col], errors='coerce')
            except:
                st.error(f"변수 '{col}'을 수치형으로 변환할 수 없습니다.")
                return {"r2_test": 0.0}
    
    # NaN 값이 있는 행 제거 (X 기준) 및 y 정렬
    X = X.dropna()
    y = y.loc[X.index]
    
    # y에 남아있는 NaN 제거하고 X 동기화
    _mask_valid_y = ~y.isna()
    if _mask_valid_y.sum() != len(y):
        X = X.loc[_mask_valid_y]
        y = y.loc[_mask_valid_y]
    
    if len(X) == 0:
        st.warning("수치형 변환 후 유효한 데이터가 없습니다.")
        return {"r2_test": 0.0}

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    # === OLS용 스케일러 ===
    OLS_scaler = StandardScaler(with_mean=False)
    OLS_X_train_s = OLS_scaler.fit_transform(X_train)
    OLS_X_test_s = OLS_scaler.transform(X_test)

    # === OLS (Ordinary Least Squares) 분석 ===
    OLS_lr = LinearRegression()
    OLS_lr.fit(OLS_X_train_s, y_train)
    OLS_y_tr_pred = OLS_lr.predict(OLS_X_train_s)
    OLS_y_te_pred = OLS_lr.predict(OLS_X_test_s)

    OLS_r2_te = r2_score(y_test, OLS_y_te_pred)

    OLS_coef_series = pd.Series(OLS_lr.coef_, index=X.columns)
    OLS_Xs = pd.DataFrame(OLS_X_test_s, columns=X.columns).iloc[:min(200, len(X_test))]
    OLS_term_analysis = [] #각 항별 기여도 계산
    OLS_y_pred_samp = (OLS_Xs @ OLS_coef_series.values) + OLS_lr.intercept_
    OLS_y_pred_mean = float(np.mean(OLS_y_pred_samp)) if len(OLS_Xs) else 1.0
    
    # OLS 역변환을 위한 스케일러 정보 저장
    OLS_inv_scaler = StandardScaler()
    OLS_inv_scaler.mean_ = OLS_scaler.mean_
    OLS_inv_scaler.scale_ = OLS_scaler.scale_
    
    OLS_Xs_original = pd.DataFrame(OLS_inv_scaler.inverse_transform(OLS_Xs), columns=X.columns)
    
    # 수치형 변수만 처리 (범주형 변수는 이미 제외됨)
    for name, coef in OLS_coef_series.items():
        avg_contrib = float(np.mean(OLS_Xs_original[name] * coef)) if len(OLS_Xs_original) else 0.0
        OLS_term_analysis.append({"name": name, "avg_contribution": avg_contrib})
        
    # 절편 추가
    OLS_term_analysis.append({"name": "절편", "avg_contribution": float(OLS_lr.intercept_)})
    
    # 전체 기여도 합계 계산 (음수/양수 모두 포함)
    OLS_total_contribution = sum(term["avg_contribution"] for term in OLS_term_analysis)
    
    # 각 항의 비율 계산 (전체 기여도 합계 대비, 부호 유지)
    for term in OLS_term_analysis:
        ratio = (term["avg_contribution"] / OLS_total_contribution * 100.0) if OLS_total_contribution != 0 else 0.0
        term["ratio"] = ratio
    
    # 절댓값 기준으로 정렬 (표시 순서만 결정)
    OLS_term_analysis.sort(key=lambda t: abs(t["ratio"]), reverse=True)

    # 히트맵과 비교표를 생성하기 위한 변수 저장
    st.session_state.setdefault("OLS_lr_coefficients", {})
    st.session_state.OLS_lr_coefficients = OLS_coef_series.to_dict()
    st.session_state.OLS_term_analysis = OLS_term_analysis

    def OLS_coef_str(c):
        c = float(c)
        if abs(c) >= 1e-3: return f"{c:.3f}"
        if abs(c) >= 1e-4: return f"{c:.4f}"
        return f"{c:.2e}"

    OLS_parts = []
    for t in OLS_term_analysis:
        if t["name"] == "절편":
            sign = "+" if OLS_lr.intercept_ >= 0 else "-"
            s = f"{sign} {OLS_coef_str(abs(OLS_lr.intercept_))} (절편) <span style='color:#0070C0;font-size:12px;'>({t['ratio']:+.1f}%)</span>"
        else:
            sign = "+" if OLS_coef_series[t["name"]] >= 0 else "-"
            s = f"{sign} {OLS_coef_str(abs(OLS_coef_series[t['name']]))} × {t['name']} <span style='color:#0070C0;font-size:12px;'>({t['ratio']:+.1f}%)</span>"
        OLS_parts.append("&nbsp;&nbsp;" + s)
    OLS_equation_html = "Y ("+str(y_column)+") = <br>" + "<br>".join(OLS_parts)

    # === ElasticNet용 스케일러 ===
    Elastic_scaler = StandardScaler(with_mean=True)  # ElasticNet은 평균 중심화가 중요
    Elastic_X_train_s = Elastic_scaler.fit_transform(X_train)
    Elastic_X_test_s = Elastic_scaler.transform(X_test)

    # === Elastic Net Regression 분석 ===

    # 1. 효율적인 Path 알고리즘을 사용하는 CV 모델 생성 및 학습
    # n_jobs=-1로 모든 CPU 코어를 사용하여 작업 시간을 대폭 단축합니다.
    Elastic_lr = ElasticNetCV(
        l1_ratio=[0.1, 0.5, 0.7, 0.9, 0.95, 0.99, 1], 
        alphas=[0.001, 0.01, 0.1, 1, 10, 100],
        cv=5, 
        max_iter=2000,
        random_state=42,
        n_jobs=-1 
    )

    # 2. 바로 학습 (이 한 번의 fit으로 최적 파라미터 찾기 + 최종 모델 학습이 끝납니다)
    Elastic_lr.fit(Elastic_X_train_s, y_train)

    # 3. 기존 코드 하단부와 호환을 위한 결과값 할당
    Elastic_r2_te = Elastic_lr.score(Elastic_X_test_s, y_test)
    best_alpha = Elastic_lr.alpha_
    best_l1_ratio = Elastic_lr.l1_ratio_

    Elastic_y_tr_pred = Elastic_lr.predict(Elastic_X_train_s)
    Elastic_y_te_pred = Elastic_lr.predict(Elastic_X_test_s)

    Elastic_coef_series = pd.Series(Elastic_lr.coef_, index=X.columns)
    Elastic_Xs = pd.DataFrame(Elastic_X_test_s, columns=X.columns).iloc[:min(200, len(X_test))]
    Elastic_term_analysis = [] #각 항별 기여도 계산
    Elastic_y_pred_samp = (Elastic_Xs @ Elastic_coef_series.values) + Elastic_lr.intercept_
    Elastic_y_pred_mean = float(np.mean(Elastic_y_pred_samp)) if len(Elastic_Xs) else 1.0
    
    # ElasticNet 역변환을 위한 스케일러 정보 저장
    Elastic_inv_scaler = StandardScaler()
    Elastic_inv_scaler.mean_ = Elastic_scaler.mean_
    Elastic_inv_scaler.scale_ = Elastic_scaler.scale_
    
    Elastic_Xs_original = pd.DataFrame(Elastic_inv_scaler.inverse_transform(Elastic_Xs), columns=X.columns)
    
    # 수치형 변수만 처리 (범주형 변수는 이미 제외됨)
    for name, coef in Elastic_coef_series.items():
        avg_contrib = float(np.mean(Elastic_Xs_original[name] * coef)) if len(Elastic_Xs_original) else 0.0
        Elastic_term_analysis.append({"name": name, "avg_contribution": avg_contrib})
        
    # 절편 추가
    Elastic_term_analysis.append({"name": "절편", "avg_contribution": float(Elastic_lr.intercept_)})
    
    # 전체 기여도 합계 계산 (음수/양수 모두 포함)
    Elastic_total_contribution = sum(term["avg_contribution"] for term in Elastic_term_analysis)
    
    # 각 항의 비율 계산 (전체 기여도 합계 대비, 부호 유지)
    for term in Elastic_term_analysis:
        ratio = (term["avg_contribution"] / Elastic_total_contribution * 100.0) if Elastic_total_contribution != 0 else 0.0
        term["ratio"] = ratio
    
    # 절댓값 기준으로 정렬 (표시 순서만 결정)
    Elastic_term_analysis.sort(key=lambda t: abs(t["ratio"]), reverse=True)

    # 히트맵과 비교표를 생성하기 위한 변수 저장
    st.session_state.setdefault("Elastic_lr_coefficients", {})
    st.session_state.Elastic_lr_coefficients = Elastic_coef_series.to_dict()
    st.session_state.Elastic_term_analysis = Elastic_term_analysis

    def Elastic_coef_str(c):
        c = float(c)
        if abs(c) >= 1e-3: return f"{c:.3f}"
        if abs(c) >= 1e-4: return f"{c:.4f}"
        return f"{c:.2e}"

    Elastic_parts = []
    for t in Elastic_term_analysis:
        if t["name"] == "절편":
            sign = "+" if Elastic_lr.intercept_ >= 0 else "-"
            s = f"{sign} {Elastic_coef_str(abs(Elastic_lr.intercept_))} (절편) <span style='color:#0070C0;font-size:12px;'>({t['ratio']:+.1f}%)</span>"
        else:
            sign = "+" if Elastic_coef_series[t["name"]] >= 0 else "-"
            s = f"{sign} {Elastic_coef_str(abs(Elastic_coef_series[t['name']]))} × {t['name']} <span style='color:#0070C0;font-size:12px;'>({t['ratio']:+.1f}%)</span>"
        Elastic_parts.append("&nbsp;&nbsp;" + s)
    Elastic_equation_html = "Y ("+str(y_column)+") = <br>" + "<br>".join(Elastic_parts)

    # ==============================
    # === New Linear Models (6종) ===
    # ==============================
    # 공통 헬퍼: (기여도·방정식 문자열 · 워터폴 데이터) 생성
    # def _build_term_analysis_and_equation(X_test_scaled, scaler_for_inverse, coef_series, intercept, model_name):
    #     # 역변환된 원 스케일로 평균 기여도 계산
    #     Xs = pd.DataFrame(X_test_scaled, columns=X.columns).iloc[:min(200, len(X_test_scaled))]
    #     inv = StandardScaler()
    #     inv.mean_ = getattr(scaler_for_inverse, "mean_", None)
    #     inv.scale_ = getattr(scaler_for_inverse, "scale_", None)
    #     # inv가 실제로 가능한 경우에만 역변환 (with_mean=True인 스케일러 기준)
    #     try:
    #         Xs_original = pd.DataFrame(inv.inverse_transform(Xs), columns=X.columns)
    #     except Exception:
    #         Xs_original = Xs.copy()  # 안전장치: 역변환 불가 시 스케일드 값으로 대체

    #     term_analysis = []
    #     for name, coef in coef_series.items():
    #         avg_contrib = float(np.mean(Xs_original[name] * coef)) if len(Xs_original) else 0.0
    #         term_analysis.append({"name": name, "avg_contribution": avg_contrib})
    #     term_analysis.append({"name": "절편", "avg_contribution": float(intercept)})

    #     total = sum(t["avg_contribution"] for t in term_analysis)
    #     for t in term_analysis:
    #         t["ratio"] = (t["avg_contribution"] / total * 100.0) if total != 0 else 0.0
    #     term_analysis.sort(key=lambda t: abs(t["ratio"]), reverse=True)

    #     def fmt(c):
    #         c = float(c)
    #         if abs(c) >= 1e-3: return f"{c:.3f}"
    #         if abs(c) >= 1e-4: return f"{c:.4f}"
    #         return f"{c:.2e}"

    #     parts = []
    #     for t in term_analysis:
    #         if t["name"] == "절편":
    #             sgn = "+" if intercept >= 0 else "-"
    #             s = f"{sgn} {fmt(abs(intercept))} (절편) <span style='color:#0070C0;font-size:12px;'>({t['ratio']:+.1f}%)</span>"
    #         else:
    #             sgn = "+" if coef_series[t["name"]] >= 0 else "-"
    #             s = f"{sgn} {fmt(abs(coef_series[t['name']]))} × {t['name']} <span style='color:#0070C0;font-size:12px;'>({t['ratio']:+.1f}%)</span>"
    #         parts.append("&nbsp;&nbsp;" + s)
    #     equation_html = "Y (" + str(y_column) + f") = <br>" + "<br>".join(parts)
    #     return term_analysis, equation_html

    # # 공통 헬퍼: 산점도(실측 vs 예측) — 기존 함수와 동일 시그니처 가정
    # def actual_vs_pred_plot(y_true, y_pred, title):
    #     fig = go.Figure()
    #     fig.add_trace(go.Scatter(x=y_true, y=y_pred, mode="markers", name="예측", opacity=0.7))
    #     fig.add_trace(go.Scatter(x=[y_true.min(), y_true.max()], y=[y_true.min(), y_true.max()],
    #                             mode="lines", name="y=x", line=dict(dash="dash")))
    #     fig.update_layout(title=title, xaxis_title="실제 값", yaxis_title="예측 값", height=380)
    #     return fig

    # # === 튜닝 그리드 (넓고 촘촘하게) ===
    # _ridge_alphas = np.logspace(-6, 2, 45)   # 1e-6 ~ 1e2
    # _lasso_alphas = np.logspace(-6, 2, 45)

    # # ========= 1) RidgeCV =========
    # ridge_scaler = StandardScaler(with_mean=True)
    # Xtr_r = ridge_scaler.fit_transform(X_train)
    # Xte_r = ridge_scaler.transform(X_test)

    # Ridge_lr = RidgeCV(alphas=_ridge_alphas, store_cv_values=False)
    # Ridge_lr.fit(Xtr_r, y_train)
    # Ridge_y_te_pred = Ridge_lr.predict(Xte_r)
    # Ridge_r2_te = r2_score(y_test, Ridge_y_te_pred)
    # Ridge_coef_series = pd.Series(Ridge_lr.coef_, index=X.columns)
    # Ridge_term_analysis, Ridge_equation_html = _build_term_analysis_and_equation(
    #     Xte_r, ridge_scaler, Ridge_coef_series, Ridge_lr.intercept_, "RidgeCV"
    # )

    # # ========= 2) LassoCV =========
    # lasso_scaler = StandardScaler(with_mean=True)
    # Xtr_l = lasso_scaler.fit_transform(X_train)
    # Xte_l = lasso_scaler.transform(X_test)

    # Lasso_lr = LassoCV(alphas=_lasso_alphas, max_iter=10000, n_jobs=-1, random_state=42)
    # Lasso_lr.fit(Xtr_l, y_train)
    # Lasso_y_te_pred = Lasso_lr.predict(Xte_l)
    # Lasso_r2_te = r2_score(y_test, Lasso_y_te_pred)
    # Lasso_coef_series = pd.Series(Lasso_lr.coef_, index=X.columns)
    # Lasso_term_analysis, Lasso_equation_html = _build_term_analysis_and_equation(
    #     Xte_l, lasso_scaler, Lasso_coef_series, Lasso_lr.intercept_, "LassoCV"
    # )

    # # ========= 3) HuberRegressor (로버스트 선형) =========
    # # alpha(규제), epsilon(허용 잔차) GridSearchCV로 최적화
    # huber_pipe = make_pipeline(StandardScaler(with_mean=True), HuberRegressor())
    # huber_param = {
    #     "huberregressor__alpha": np.logspace(-6, 0, 13),     # 1e-6 ~ 1e0
    #     "huberregressor__epsilon": [1.1, 1.2, 1.35, 1.5, 1.8, 2.0],
    # }
    # huber_gs = GridSearchCV(huber_pipe, huber_param, scoring="r2", cv=5, n_jobs=-1)
    # huber_gs.fit(X_train, y_train)
    # Huber_best = huber_gs.best_estimator_
    # Huber_y_te_pred = Huber_best.predict(X_test)
    # Huber_r2_te = r2_score(y_test, Huber_y_te_pred)
    # # 파이프라인에서 최종 회귀기 추출
    # _h = Huber_best.named_steps["huberregressor"]
    # _h_scaler = Huber_best.named_steps["standardscaler"]
    # Huber_coef_series = pd.Series(_h.coef_, index=X.columns)
    # Huber_term_analysis, Huber_equation_html = _build_term_analysis_and_equation(
    #     _h_scaler.transform(X_test), _h_scaler, Huber_coef_series, _h.intercept_, "Huber"
    # )

    # # ========= 4) QuantileRegressor (분위수 회귀; 선형) =========
    # # alpha(규제) & quantile(0.01~0.99) 탐색. solver='highs'가 안정적.
    # qr_pipe = make_pipeline(StandardScaler(with_mean=True),
    #                         QuantileRegressor(quantile=0.5, alpha=1e-4, solver="highs", fit_intercept=True))
    # qr_param = {
    #     "quantileregressor__alpha": np.logspace(-6, 0, 13),
    #     "quantileregressor__quantile": np.round(np.linspace(0.01, 0.99, 33), 2),
    # }
    # qr_gs = GridSearchCV(qr_pipe, qr_param, scoring="r2", cv=5, n_jobs=-1)
    # qr_gs.fit(X_train, y_train)
    # QR_best = qr_gs.best_estimator_
    # QR_y_te_pred = QR_best.predict(X_test)
    # QR_r2_te = r2_score(y_test, QR_y_te_pred)
    # _qr = QR_best.named_steps["quantileregressor"]
    # _qr_scaler = QR_best.named_steps["standardscaler"]
    # QR_coef_series = pd.Series(_qr.coef_, index=X.columns)
    # QR_term_analysis, QR_equation_html = _build_term_analysis_and_equation(
    #     _qr_scaler.transform(X_test), _qr_scaler, QR_coef_series, _qr.intercept_, "Quantile"
    # )

    # # ========= 5) Theil–Sen (로버스트 선형) =========
    # # TheilSenRegressor는 내부적으로 스케일링의 영향을 받으므로 평균중심 스케일 사용 권장
    # ts_scaler = StandardScaler(with_mean=True)
    # Xtr_ts = ts_scaler.fit_transform(X_train)
    # Xte_ts = ts_scaler.transform(X_test)

    # TheilSen_lr = TheilSenRegressor(random_state=42, n_jobs=-1)
    # TheilSen_lr.fit(Xtr_ts, y_train)
    # Theil_y_te_pred = TheilSen_lr.predict(Xte_ts)
    # Theil_r2_te = r2_score(y_test, Theil_y_te_pred)
    # Theil_coef_series = pd.Series(TheilSen_lr.coef_, index=X.columns)
    # Theil_term_analysis, Theil_equation_html = _build_term_analysis_and_equation(
    #     Xte_ts, ts_scaler, Theil_coef_series, TheilSen_lr.intercept_, "Theil-Sen"
    # )

    # # ========= 6) RANSAC (로버스트 inlier fitting; 선형 베이스) =========
    # # 베이스는 LinearRegression, 잔차 임계는 데이터 스케일에 의존 → 스케일 후 MAD 기반으로 유도
    # ra_scaler = StandardScaler(with_mean=True)
    # Xtr_ra = ra_scaler.fit_transform(X_train)
    # Xte_ra = ra_scaler.transform(X_test)

    # base_lr = LinearRegression()
    # # 잔차 스케일(훈련셋 OLS 예측 오차의 MAD)로 임계 추정
    # base_lr.fit(Xtr_ra, y_train)
    # _resid = y_train - base_lr.predict(Xtr_ra)
    # mad = np.median(np.abs(_resid - np.median(_resid)))
    # res_thr = 1.4826 * mad if mad > 0 else np.std(_resid) if len(_resid) else 1.0

    # RANSAC_lr = RANSACRegressor(
    #     base_estimator=LinearRegression(),
    #     min_samples=max(0.2, 0.5),        # 비율 허용
    #     residual_threshold=res_thr,
    #     random_state=42
    # )
    # RANSAC_lr.fit(Xtr_ra, y_train)
    # RANSAC_y_te_pred = RANSAC_lr.predict(Xte_ra)
    # RANSAC_r2_te = r2_score(y_test, RANSAC_y_te_pred)

    # # 베이스 추정기에서 coef_/intercept_ 추출 (inlier로 재적합된 선형식)
    # _r = RANSAC_lr.estimator_
    # RANSAC_coef_series = pd.Series(_r.coef_, index=X.columns)
    # RANSAC_term_analysis, RANSAC_equation_html = _build_term_analysis_and_equation(
    #     Xte_ra, ra_scaler, RANSAC_coef_series, _r.intercept_, "RANSAC"
    # )


    with st.container(border=True):
        
        # OLS 선형회귀분석
        st.markdown('<h4 style="margin: 10px 0; color: #333;">📈 최소제곱법 분석 (Ordinary Least Squares)</h4>', unsafe_allow_html=True)       
        st.markdown("""
        <div style="background-color: #E8F2FC; border: 1px solid #E8F2FC; border-radius: 0.375rem; padding: 1rem; margin: 1rem 0;">
            <div style="display: flex; align-items: flex-start;">
                <span style="font-size: 1.2em; margin-right: 0.5rem;"></span>
                <div>
                    <strong>💡 <u>Ordinary Least Squares 분석이란,</u></strong><br>
                    가장 기본적인 선형회귀분석 기법으로, 엑셀에서 선형 추세선을 그려내는 방식입니다.<br>
                    각 오차의 제곱의 합이 최소가 되도록 계수를 추정하며, 각 데이터의 신뢰도에는 별도의 가중치를 주지 않습니다.
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        colA, colB = st.columns(2)
        with colA:
            # OLS 모델 성능 표시
            st.markdown(f"""
            <div style="background:#e9ecef;padding:14px;border-radius:10px;border-left:5px solid #007bff;margin-top:12px;">
                <h4 style="margin:0 0 8px 0;color:#007bff;">📊 OLS 모델 성능</h4>
                <div style="font-size:32px;font-weight:bold;color:#007bff;">{OLS_r2_te:.1%}</div>
                <div style="font-size:13px;color:#666;">R² (설명력)</div>
            </div>
            """, unsafe_allow_html=True)
            
            if OLS_r2_te < 0.5:
                interp_text = "모델의 설명력이 낮습니다. 비선형적 관계가 있거나, 데이터 전처리가 필요하거나, 다른 X 변수를 선택해야 할 수 있습니다."
            elif OLS_r2_te < 0.8:
                interp_text = "모델의 설명력이 보통 수준입니다. 비선형적 관계가 있거나, 데이터 전처리가 필요하거나, 다른 X 변수를 선택해야 할 수 있습니다."
            else:
                interp_text = "모델의 설명력이 양호합니다. 이어지는 2단계/3단계 분석을 하지 않아도 충분한 설명이 가능할 수 있습니다."
            st.markdown(f"<div style='margin-top: 10px; color:#0c5460;'>💡 {interp_text}</div>", unsafe_allow_html=True)
            st.markdown("\n")
            # OLS 선형 회귀 방정식 표시
            st.markdown(f"""
            <div style="background:#f8f9fa;padding:16px;border-radius:10px;border-left:5px solid #dc3545; margin-top: 20px;">
            <h4 style="margin:0 0 10px 0;color:#dc3545;">🎯 OLS 선형 회귀 방정식</h4>
            <div style="font-family:monospace;line-height:1.6;color:#333;font-weight:500;">{OLS_equation_html}</div>
            </div>
            """, unsafe_allow_html=True)
            st.markdown("<div style='margin-top: 10px; margin-bottom: 20px; color:#0c5460;'>ℹ️ 각 항 오른쪽의 퍼센트<span style='color:#0070C0;font-size:15px;'>(~~%)</span> 값은 각 항(계수x변수 혹은 절편)이 전체 Y값에 기여하는 비중을 의미합니다.</div>", unsafe_allow_html=True)
            
        with colB:
            # OLS 실제 값 vs 모델 예측 값 표시
            fig = actual_vs_pred_plot(y_test, OLS_y_te_pred, "OLS: 실제 값 vs 모델 예측 값")
            st.plotly_chart(fig, width='stretch')
            
            # OLS 각 항의 Y값 기여도 Waterfall Chart 표시
            OLS_waterfall_data = []
            OLS_cumulative = 0
            for term in OLS_term_analysis:
                ratio = term["ratio"]  # 음수/양수 그대로 유지
                OLS_waterfall_data.append({
                    "name": term["name"],
                    "ratio": ratio,
                    "cumulative": OLS_cumulative,
                    "color": abs(ratio)  # 색상은 절댓값으로
                })
                OLS_cumulative += ratio  # 음수도 누적

            # 최종 Y(파란 막대) - 실제 합계로 설정
            OLS_waterfall_data.append({
                "name": f"{y_column} (Y)",
                "ratio": OLS_cumulative,  # 실제 누적 합계
                "cumulative": 0,
                "color": abs(OLS_cumulative)
            })

            # --- 색상 매핑 함수: red -> yellow -> green ---
            def ryb_color(norm):
                norm = max(0, min(1, norm))
                if norm <= 0.5:  # red -> yellow
                    r, g, b = 1.0, norm*2, 0.0
                else:            # yellow -> green
                    r, g, b = 2 - norm*2, 1.0, 0.0
                return f'rgb({int(r*255)},{int(g*255)},{int(b*255)})'

            OLS_fig_waterfall = go.Figure()

            # 정규화 기준(마지막 Y 막대 제외)
            OLS_max_abs_ratio = max(abs(d["ratio"]) for d in OLS_waterfall_data[:-1]) if OLS_waterfall_data[:-1] else 1.0

            # --- 막대 추가 ---
            for data in OLS_waterfall_data:
                if "(Y)" in data["name"]:
                    color = 'rgb(0,100,200)'  # 파란 막대
                    base = 0
                    height = data["ratio"]  # 실제 합계값
                    text = f"{data['ratio']:+.1f}%"
                else:
                    norm = abs(data["ratio"]) / OLS_max_abs_ratio if OLS_max_abs_ratio > 0 else 0
                    color = ryb_color(norm)
                    base = data["cumulative"]
                    height = data["ratio"]  # 음수/양수 그대로
                    text = f"{data['ratio']:+.1f}%"

                OLS_fig_waterfall.add_trace(go.Bar(
                    x=[data["name"]],
                    y=[height],
                    base=[base],
                    marker_color=color,
                    text=[text],
                    textposition='inside',
                    textfont=dict(color='black', size=12),
                    hovertemplate=f"{data['name']}<br>기여도: {data['ratio']:+.1f}%<extra></extra>",
                    showlegend=False
                ))

            # --- 점선 가이드라인(파란 막대 직전은 제외) ---
            for i in range(len(OLS_waterfall_data) - 1):
                cur = OLS_waterfall_data[i]
                nxt = OLS_waterfall_data[i + 1]
                if "(Y)" in nxt["name"]:
                    continue  # 파란 막대로 이어질 때는 그리지 않음
                current_top = cur["cumulative"] + cur["ratio"]
                next_bottom = nxt["cumulative"]
                OLS_fig_waterfall.add_trace(go.Scatter(
                    x=[cur["name"], nxt["name"]],
                    y=[current_top, next_bottom],
                    mode='lines',
                    line=dict(color='gray', width=1, dash='dot'),
                    showlegend=False,
                    hoverinfo='skip'
                ))

            # --- 레이아웃 ---
            OLS_fig_waterfall.update_layout(
                title=dict(
                    text="OLS: 각 항의 Y값 기여도",
                    font=dict(color='black', size=16)
                ),
                xaxis_title="",
                yaxis_title=dict(
                    text="기여도 (%)",
                    font=dict(color='black', size=14)
                ),
                barmode='relative',
                height=420,
                showlegend=False,
                font=dict(color='black', size=12)
            )

            # Y축: 동적 범위 설정 (음수 포함)
            OLS_y_min = min(0, min(d["cumulative"] + d["ratio"] for d in OLS_waterfall_data))
            OLS_y_max = max(100, max(d["cumulative"] + d["ratio"] for d in OLS_waterfall_data))
            
            # Y축 범위를 100 단위로 정렬
            OLS_y_min_rounded = (int(OLS_y_min / 100) - 1) * 100
            OLS_y_max_rounded = (int(OLS_y_max / 100) + 1) * 100
            
            # 주요 눈금선 위치 정의 (0%와 100%가 가장 진한 검정색)
            OLS_major_grid_lines = [0, 100]  # 가장 진한 검정색
            OLS_minor_grid_lines = [200, 300, 400, 500, 600, 700, 800, 900, 1000, 
                                  -100, -200, -300, -400, -500, -600, -700, -800, -900, -1000]  # 연한 회색
            
            # 범위 내의 눈금선만 필터링
            OLS_major_grid_lines = [line for line in OLS_major_grid_lines if OLS_y_min_rounded <= line <= OLS_y_max_rounded]
            OLS_minor_grid_lines = [line for line in OLS_minor_grid_lines if OLS_y_min_rounded <= line <= OLS_y_max_rounded]
            
            # shapes로 눈금선 추가
            OLS_shapes = []
            
            # 주요 눈금선 (0%, 100%) - 가장 진한 검정색
            for line in OLS_major_grid_lines:
                OLS_shapes.append(dict(
                    type="line",
                    xref="paper", yref="y",
                    x0=0, x1=1, y0=line, y1=line,
                    line=dict(color="black", width=2)
                ))
            
            # 보조 눈금선 - 연한 회색
            for line in OLS_minor_grid_lines:
                OLS_shapes.append(dict(
                    type="line",
                    xref="paper", yref="y",
                    x0=0, x1=1, y0=line, y1=line,
                    line=dict(color="lightgray", width=1)
                ))
            
            # 레이아웃에 shapes 추가
            OLS_fig_waterfall.update_layout(shapes=OLS_shapes)
            
            # Y축 틱 설정 - 적절한 간격으로 조정
            # 범위에 따라 틱 간격을 동적으로 조정
            OLS_y_range = OLS_y_max_rounded - OLS_y_min_rounded
            if OLS_y_range <= 200:
                OLS_dtick = 20
            elif OLS_y_range <= 500:
                OLS_dtick = 50
            elif OLS_y_range <= 1000:
                OLS_dtick = 100
            else:
                OLS_dtick = 200
            
            OLS_fig_waterfall.update_yaxes(
                range=[OLS_y_min_rounded, OLS_y_max_rounded],
                tick0=0,
                dtick=OLS_dtick,
                tickformat=".0f",
                ticksuffix="%",
                tickfont=dict(color='black', size=12),
                showgrid=True,
                gridcolor='rgba(200,200,200,0.3)',  # 기본 그리드는 매우 연하게
                gridwidth=0.5
            )
            
            # X축: 진한 검정색
            OLS_fig_waterfall.update_xaxes(
                tickfont=dict(color='black', size=12)
            )

            st.plotly_chart(OLS_fig_waterfall, width='stretch')

    # === Elastic Net Regression 분석 결과 표시 ===
    with st.container(border=True):
        
        # Elastic Net 선형회귀분석
        st.markdown('<h4 style="margin: 10px 0; color: #333;">📈 Elastic Net 회귀분석 (정규화된 선형회귀)</h4>', unsafe_allow_html=True)       
        st.markdown("""
        <div style="background-color: #E8F2FC; border: 1px solid #E8F2FC; border-radius: 0.375rem; padding: 1rem; margin: 1rem 0;">
            <div style="display: flex; align-items: flex-start;">
                <span style="font-size: 1.2em; margin-right: 0.5rem;"></span>
                <div>
                    <strong>💡 <u>Elastic Net 회귀분석이란,</u></strong><br>
                    L1(Lasso)와 L2(Ridge) 정규화를 결합한 고급 선형회귀 기법입니다.<br>
                    과적합을 방지하고 중요한 변수만 선택하며, 다중공선성 문제도 완화합니다. (최적 α={:.3f}, L1비율={:.1f})
                </div>
            </div>
        </div>
        """.format(best_alpha, best_l1_ratio), unsafe_allow_html=True)

        colA, colB = st.columns(2)
        with colA:
            # Elastic Net 모델 성능 표시
            st.markdown(f"""
            <div style="background:#e9ecef;padding:14px;border-radius:10px;border-left:5px solid #28a745;margin-top:12px;">
                <h4 style="margin:0 0 8px 0;color:#28a745;">📊 Elastic Net 모델 성능</h4>
                <div style="font-size:32px;font-weight:bold;color:#28a745;">{Elastic_r2_te:.1%}</div>
                <div style="font-size:13px;color:#666;">R² (설명력)</div>
            </div>
            """, unsafe_allow_html=True)
            
            if Elastic_r2_te < 0.5:
                interp_text = "모델의 설명력이 낮습니다. 비선형적 관계가 있거나, 데이터 전처리가 필요하거나, 다른 X 변수를 선택해야 할 수 있습니다."
            elif Elastic_r2_te < 0.8:
                interp_text = "모델의 설명력이 보통 수준입니다. 비선형적 관계가 있거나, 데이터 전처리가 필요하거나, 다른 X 변수를 선택해야 할 수 있습니다."
            else:
                interp_text = "모델의 설명력이 양호합니다. 이어지는 2단계/3단계 분석을 하지 않아도 충분한 설명이 가능할 수 있습니다."
            st.markdown(f"<div style='margin-top: 10px; color:#0c5460;'>💡 {interp_text}</div>", unsafe_allow_html=True)
            st.markdown("\n")
            # Elastic Net 선형 회귀 방정식 표시
            st.markdown(f"""
            <div style="background:#f8f9fa;padding:16px;border-radius:10px;border-left:5px solid #dc3545; margin-top: 20px;">
            <h4 style="margin:0 0 10px 0;color:#dc3545;">🎯 Elastic Net 회귀 방정식</h4>
            <div style="font-family:monospace;line-height:1.6;color:#333;font-weight:500;">{Elastic_equation_html}</div>
            </div>
            """, unsafe_allow_html=True)
            st.markdown("<div style='margin-top: 10px; margin-bottom: 20px; color:#0c5460;'>ℹ️ 각 항 오른쪽의 퍼센트<span style='color:#0070C0;font-size:15px;'>(~~%)</span> 값은 각 항(계수x변수 혹은 절편)이 전체 Y값에 기여하는 비중을 의미합니다.</div>", unsafe_allow_html=True)
            
        with colB:
            # Elastic Net 실제 값 vs 모델 예측 값 표시
            fig = actual_vs_pred_plot(y_test, Elastic_y_te_pred, "Elastic Net: 실제 값 vs 모델 예측 값")
            st.plotly_chart(fig, width='stretch')
            
            # Elastic Net 각 항의 Y값 기여도 Waterfall Chart 표시
            Elastic_waterfall_data = []
            Elastic_cumulative = 0
            for term in Elastic_term_analysis:
                ratio = term["ratio"]  # 음수/양수 그대로 유지
                Elastic_waterfall_data.append({
                    "name": term["name"],
                    "ratio": ratio,
                    "cumulative": Elastic_cumulative,
                    "color": abs(ratio)  # 색상은 절댓값으로
                })
                Elastic_cumulative += ratio  # 음수도 누적

            # 최종 Y(파란 막대) - 실제 합계로 설정
            Elastic_waterfall_data.append({
                "name": f"{y_column} (Y)",
                "ratio": Elastic_cumulative,  # 실제 누적 합계
                "cumulative": 0,
                "color": abs(Elastic_cumulative)
            })

            # --- 색상 매핑 함수: red -> yellow -> green ---
            def ryb_color(norm):
                norm = max(0, min(1, norm))
                if norm <= 0.5:  # red -> yellow
                    r, g, b = 1.0, norm*2, 0.0
                else:            # yellow -> green
                    r, g, b = 2 - norm*2, 1.0, 0.0
                return f'rgb({int(r*255)},{int(g*255)},{int(b*255)})'

            Elastic_fig_waterfall = go.Figure()

            # 정규화 기준(마지막 Y 막대 제외)
            Elastic_max_abs_ratio = max(abs(d["ratio"]) for d in Elastic_waterfall_data[:-1]) if Elastic_waterfall_data[:-1] else 1.0

            # --- 막대 추가 ---
            for data in Elastic_waterfall_data:
                if "(Y)" in data["name"]:
                    color = 'rgb(0,100,200)'  # 파란 막대
                    base = 0
                    height = data["ratio"]  # 실제 합계값
                    text = f"{data['ratio']:+.1f}%"
                else:
                    norm = abs(data["ratio"]) / Elastic_max_abs_ratio if Elastic_max_abs_ratio > 0 else 0
                    color = ryb_color(norm)
                    base = data["cumulative"]
                    height = data["ratio"]  # 음수/양수 그대로
                    text = f"{data['ratio']:+.1f}%"

                Elastic_fig_waterfall.add_trace(go.Bar(
                    x=[data["name"]],
                    y=[height],
                    base=[base],
                    marker_color=color,
                    text=[text],
                    textposition='inside',
                    textfont=dict(color='black', size=12),
                    hovertemplate=f"{data['name']}<br>기여도: {data['ratio']:+.1f}%<extra></extra>",
                    showlegend=False
                ))

            # --- 점선 가이드라인(파란 막대 직전은 제외) ---
            for i in range(len(Elastic_waterfall_data) - 1):
                cur = Elastic_waterfall_data[i]
                nxt = Elastic_waterfall_data[i + 1]
                if "(Y)" in nxt["name"]:
                    continue  # 파란 막대로 이어질 때는 그리지 않음
                current_top = cur["cumulative"] + cur["ratio"]
                next_bottom = nxt["cumulative"]
                Elastic_fig_waterfall.add_trace(go.Scatter(
                    x=[cur["name"], nxt["name"]],
                    y=[current_top, next_bottom],
                    mode='lines',
                    line=dict(color='gray', width=1, dash='dot'),
                    showlegend=False,
                    hoverinfo='skip'
                ))

            # --- 레이아웃 ---
            Elastic_fig_waterfall.update_layout(
                title=dict(
                    text="Elastic Net: 각 항의 Y값 기여도",
                    font=dict(color='black', size=16)
                ),
                xaxis_title="",
                yaxis_title=dict(
                    text="기여도 (%)",
                    font=dict(color='black', size=14)
                ),
                barmode='relative',
                height=420,
                showlegend=False,
                font=dict(color='black', size=12)
            )

            # Y축: 동적 범위 설정 (음수 포함)
            Elastic_y_min = min(0, min(d["cumulative"] + d["ratio"] for d in Elastic_waterfall_data))
            Elastic_y_max = max(100, max(d["cumulative"] + d["ratio"] for d in Elastic_waterfall_data))
            
            # Y축 범위를 100 단위로 정렬
            Elastic_y_min_rounded = (int(Elastic_y_min / 100) - 1) * 100
            Elastic_y_max_rounded = (int(Elastic_y_max / 100) + 1) * 100
            
            # 주요 눈금선 위치 정의 (0%와 100%가 가장 진한 검정색)
            Elastic_major_grid_lines = [0, 100]  # 가장 진한 검정색
            Elastic_minor_grid_lines = [200, 300, 400, 500, 600, 700, 800, 900, 1000, 
                                      -100, -200, -300, -400, -500, -600, -700, -800, -900, -1000]  # 연한 회색
            
            # 범위 내의 눈금선만 필터링
            Elastic_major_grid_lines = [line for line in Elastic_major_grid_lines if Elastic_y_min_rounded <= line <= Elastic_y_max_rounded]
            Elastic_minor_grid_lines = [line for line in Elastic_minor_grid_lines if Elastic_y_min_rounded <= line <= Elastic_y_max_rounded]
            
            # shapes로 눈금선 추가
            Elastic_shapes = []
            
            # 주요 눈금선 (0%, 100%) - 가장 진한 검정색
            for line in Elastic_major_grid_lines:
                Elastic_shapes.append(dict(
                    type="line",
                    xref="paper", yref="y",
                    x0=0, x1=1, y0=line, y1=line,
                    line=dict(color="black", width=2)
                ))
            
            # 보조 눈금선 - 연한 회색
            for line in Elastic_minor_grid_lines:
                Elastic_shapes.append(dict(
                    type="line",
                    xref="paper", yref="y",
                    x0=0, x1=1, y0=line, y1=line,
                    line=dict(color="lightgray", width=1)
                ))
            
            # 레이아웃에 shapes 추가
            Elastic_fig_waterfall.update_layout(shapes=Elastic_shapes)
            
            # Y축 틱 설정 - 적절한 간격으로 조정
            # 범위에 따라 틱 간격을 동적으로 조정
            Elastic_y_range = Elastic_y_max_rounded - Elastic_y_min_rounded
            if Elastic_y_range <= 200:
                Elastic_dtick = 20
            elif Elastic_y_range <= 500:
                Elastic_dtick = 50
            elif Elastic_y_range <= 1000:
                Elastic_dtick = 100
            else:
                Elastic_dtick = 200
            
            Elastic_fig_waterfall.update_yaxes(
                range=[Elastic_y_min_rounded, Elastic_y_max_rounded],
                tick0=0,
                dtick=Elastic_dtick,
                tickformat=".0f",
                ticksuffix="%",
                tickfont=dict(color='black', size=12),
                showgrid=True,
                gridcolor='rgba(200,200,200,0.3)',  # 기본 그리드는 매우 연하게
                gridwidth=0.5
            )
            
            # X축: 진한 검정색
            Elastic_fig_waterfall.update_xaxes(
                tickfont=dict(color='black', size=12)
            )

            st.plotly_chart(Elastic_fig_waterfall, width='stretch')

    # ==============================
    # === New: 결과 표시 공통 렌더러 ===
    # ==============================
    def _render_linear_block(title_prefix, r2_val, equation_html, y_test_vec, y_pred_vec, term_analysis):
        with st.container(border=True):
            st.markdown(f'<h4 style="margin: 10px 0; color: #333;">📈 {title_prefix}</h4>', unsafe_allow_html=True)
            colA, colB = st.columns(2)
            with colA:
                st.markdown(f"""
                <div style="background:#e9ecef;padding:14px;border-radius:10px;border-left:5px solid #0d6efd;margin-top:12px;">
                    <h4 style="margin:0 0 8px 0;color:#0d6efd;">📊 모델 성능</h4>
                    <div style="font-size:32px;font-weight:bold;color:#0d6efd;">{r2_val:.1%}</div>
                    <div style="font-size:13px;color:#666;">R² (설명력)</div>
                </div>
                """, unsafe_allow_html=True)

                st.markdown(f"""
                <div style="background:#f8f9fa;padding:16px;border-radius:10px;border-left:5px solid #dc3545; margin-top: 20px;">
                <h4 style="margin:0 0 10px 0;color:#dc3545;">🎯 선형 회귀 방정식</h4>
                <div style="font-family:monospace;line-height:1.6;color:#333;font-weight:500;">{equation_html}</div>
                </div>
                """, unsafe_allow_html=True)

            with colB:
                # 1) Actual vs Pred
                fig_sc = actual_vs_pred_plot(y_test_vec, y_pred_vec, f"{title_prefix}: 실제 값 vs 모델 예측 값")
                st.plotly_chart(fig_sc, width='stretch')

                # 2) Waterfall (기여도, % 비율)
                wf_data = []
                cumu = 0
                for term in term_analysis:
                    ratio = term["ratio"]
                    wf_data.append({"name": term["name"], "ratio": ratio, "cumulative": cumu})
                    cumu += ratio
                wf_data.append({"name": f"{y_column} (Y)", "ratio": cumu, "cumulative": 0})

                def _ryg(norm):
                    norm = max(0, min(1, norm))
                    if norm <= 0.5: r,g,b = 1.0, norm*2, 0.0
                    else:           r,g,b = 2 - norm*2, 1.0, 0.0
                    return f'rgb({int(r*255)},{int(g*255)},{int(b*255)})'

                fig_wf = go.Figure()
                max_abs = max(abs(d["ratio"]) for d in wf_data[:-1]) if wf_data[:-1] else 1.0
                for d in wf_data:
                    if "(Y)" in d["name"]:
                        color, base, height = 'rgb(0,100,200)', 0, d["ratio"]
                    else:
                        color = _ryg(abs(d["ratio"]) / max_abs if max_abs else 0)
                        base, height = d["cumulative"], d["ratio"]
                    fig_wf.add_trace(go.Bar(
                        x=[d["name"]], y=[height], base=[base],
                        marker_color=color, text=[f"{height:+.1f}%"], textposition='inside',
                        textfont=dict(color='black', size=12), hovertemplate=f"{d['name']}<br>기여도: {height:+.1f}%<extra></extra>",
                        showlegend=False
                    ))
                # Y축 범위/그리드
                y_min = min(0, min(d["cumulative"] + d["ratio"] for d in wf_data))
                y_max = max(100, max(d["cumulative"] + d["ratio"] for d in wf_data))
                y_min_r = (int(y_min/100)-1)*100
                y_max_r = (int(y_max/100)+1)*100
                shapes=[]
                for line in [0,100]:
                    if y_min_r<=line<=y_max_r:
                        shapes.append(dict(type="line", xref="paper", yref="y", x0=0, x1=1, y0=line, y1=line,
                                        line=dict(color="black", width=2)))
                for line in [200,300,400,500,600,700,800,900,1000,-100,-200,-300,-400,-500,-600,-700,-800,-900,-1000]:
                    if y_min_r<=line<=y_max_r:
                        shapes.append(dict(type="line", xref="paper", yref="y", x0=0, x1=1, y0=line, y1=line,
                                        line=dict(color="lightgray", width=1)))
                fig_wf.update_layout(
                    title=dict(text=f"{title_prefix}: 각 항의 Y값 기여도", font=dict(color='black', size=16)),
                    xaxis_title="", yaxis_title=dict(text="기여도 (%)", font=dict(color='black', size=14)),
                    barmode='relative', height=420, showlegend=False, font=dict(color='black', size=12),
                    shapes=shapes
                )
                y_rng = y_max_r - y_min_r
                dtick = 20 if y_rng<=200 else 50 if y_rng<=500 else 100 if y_rng<=1000 else 200
                fig_wf.update_yaxes(range=[y_min_r, y_max_r], tick0=0, dtick=dtick, tickformat=".0f", ticksuffix="%",
                                    tickfont=dict(color='black', size=12), showgrid=True, gridcolor='rgba(200,200,200,0.3)', gridwidth=0.5)
                fig_wf.update_xaxes(tickfont=dict(color='black', size=12))
                st.plotly_chart(fig_wf, width='stretch')


# # ========= 2) LassoCV =========
#     lasso_scaler = StandardScaler(with_mean=True)
#     Xtr_l = lasso_scaler.fit_transform(X_train)
#     Xte_l = lasso_scaler.transform(X_test)

#     Lasso_lr = LassoCV(alphas=_lasso_alphas, max_iter=10000, n_jobs=-1, random_state=42)
#     Lasso_lr.fit(Xtr_l, y_train)
#     Lasso_y_te_pred = Lasso_lr.predict(Xte_l)
#     Lasso_r2_te = r2_score(y_test, Lasso_y_te_pred)
#     Lasso_coef_series = pd.Series(Lasso_lr.coef_, index=X.columns)
#     Lasso_term_analysis, Lasso_equation_html = _build_term_analysis_and_equation(
#         Xte_l, lasso_scaler, Lasso_coef_series, Lasso_lr.intercept_, "LassoCV"
#     )

# # ========= 3) HuberRegressor (로버스트 선형) =========
#     # alpha(규제), epsilon(허용 잔차) GridSearchCV로 최적화
#     huber_pipe = make_pipeline(StandardScaler(with_mean=True), HuberRegressor())
#     huber_param = {
#         "huberregressor__alpha": np.logspace(-6, 0, 13),     # 1e-6 ~ 1e0
#         "huberregressor__epsilon": [1.1, 1.2, 1.35, 1.5, 1.8, 2.0],
#     }
#     huber_gs = GridSearchCV(huber_pipe, huber_param, scoring="r2", cv=5, n_jobs=-1)
#     huber_gs.fit(X_train, y_train)
#     Huber_best = huber_gs.best_estimator_
#     Huber_y_te_pred = Huber_best.predict(X_test)
#     Huber_r2_te = r2_score(y_test, Huber_y_te_pred)
#     # 파이프라인에서 최종 회귀기 추출
#     _h = Huber_best.named_steps["huberregressor"]
#     _h_scaler = Huber_best.named_steps["standardscaler"]
#     Huber_coef_series = pd.Series(_h.coef_, index=X.columns)
#     Huber_term_analysis, Huber_equation_html = _build_term_analysis_and_equation(
#         _h_scaler.transform(X_test), _h_scaler, Huber_coef_series, _h.intercept_, "Huber"
#     )

# # ========= 4) QuantileRegressor (분위수 회귀; 선형) =========
#     # alpha(규제) & quantile(0.01~0.99) 탐색. solver='highs'가 안정적.
#     qr_pipe = make_pipeline(StandardScaler(with_mean=True),
#                             QuantileRegressor(quantile=0.5, alpha=1e-4, solver="highs", fit_intercept=True))
#     qr_param = {
#         "quantileregressor__alpha": np.logspace(-6, 0, 13),
#         "quantileregressor__quantile": np.round(np.linspace(0.01, 0.99, 33), 2),
#     }
#     qr_gs = GridSearchCV(qr_pipe, qr_param, scoring="r2", cv=5, n_jobs=-1)
#     qr_gs.fit(X_train, y_train)
#     QR_best = qr_gs.best_estimator_
#     QR_y_te_pred = QR_best.predict(X_test)
#     QR_r2_te = r2_score(y_test, QR_y_te_pred)
#     _qr = QR_best.named_steps["quantileregressor"]
#     _qr_scaler = QR_best.named_steps["standardscaler"]
#     QR_coef_series = pd.Series(_qr.coef_, index=X.columns)
#     QR_term_analysis, QR_equation_html = _build_term_analysis_and_equation(
#         _qr_scaler.transform(X_test), _qr_scaler, QR_coef_series, _qr.intercept_, "Quantile"
#     )

# # ========= 5) Theil–Sen (로버스트 선형) =========
#     # TheilSenRegressor는 내부적으로 스케일링의 영향을 받으므로 평균중심 스케일 사용 권장
#     ts_scaler = StandardScaler(with_mean=True)
#     Xtr_ts = ts_scaler.fit_transform(X_train)
#     Xte_ts = ts_scaler.transform(X_test)

#     TheilSen_lr = TheilSenRegressor(random_state=42, n_jobs=-1)
#     TheilSen_lr.fit(Xtr_ts, y_train)
#     Theil_y_te_pred = TheilSen_lr.predict(Xte_ts)
#     Theil_r2_te = r2_score(y_test, Theil_y_te_pred)
#     Theil_coef_series = pd.Series(TheilSen_lr.coef_, index=X.columns)
#     Theil_term_analysis, Theil_equation_html = _build_term_analysis_and_equation(
#         Xte_ts, ts_scaler, Theil_coef_series, TheilSen_lr.intercept_, "Theil-Sen"
#     )

# # ========= 6) RANSAC (로버스트 inlier fitting; 선형 베이스) =========
#     # 베이스는 LinearRegression, 잔차 임계는 데이터 스케일에 의존 → 스케일 후 MAD 기반으로 유도
#     ra_scaler = StandardScaler(with_mean=True)
#     Xtr_ra = ra_scaler.fit_transform(X_train)
#     Xte_ra = ra_scaler.transform(X_test)

#     base_lr = LinearRegression()
#     # 잔차 스케일(훈련셋 OLS 예측 오차의 MAD)로 임계 추정
#     base_lr.fit(Xtr_ra, y_train)
#     _resid = y_train - base_lr.predict(Xtr_ra)
#     mad = np.median(np.abs(_resid - np.median(_resid)))
#     res_thr = 1.4826 * mad if mad > 0 else np.std(_resid) if len(_resid) else 1.0

#     RANSAC_lr = RANSACRegressor(
#         base_estimator=LinearRegression(),
#         min_samples=max(0.2, 0.5),        # 비율 허용
#         residual_threshold=res_thr,
#         random_state=42
#     )
#     RANSAC_lr.fit(Xtr_ra, y_train)
#     RANSAC_y_te_pred = RANSAC_lr.predict(Xte_ra)
#     RANSAC_r2_te = r2_score(y_test, RANSAC_y_te_pred)

#     # 베이스 추정기에서 coef_/intercept_ 추출 (inlier로 재적합된 선형식)
#     _r = RANSAC_lr.estimator_
#     RANSAC_coef_series = pd.Series(_r.coef_, index=X.columns)
#     RANSAC_term_analysis, RANSAC_equation_html = _build_term_analysis_and_equation(
#         Xte_ra, ra_scaler, RANSAC_coef_series, _r.intercept_, "RANSAC"
#     )

#     # --- 플레이스홀더(비활성화로 인한 NameError 방지) ---
#     # Lasso
#     Lasso_lr = type("D", (), {})()
#     setattr(Lasso_lr, "alpha_", 0.0)
#     Lasso_y_te_pred = np.zeros(len(y_test)) if 'y_test' in locals() else np.array([0.0])
#     Lasso_r2_te = 0.0
#     Lasso_coef_series = pd.Series(dtype=float)
#     Lasso_term_analysis = []
#     Lasso_equation_html = "LassoCV (비활성화됨)"

#     # Huber
#     huber_gs = type("D", (), {})()
#     setattr(huber_gs, "best_params_", {})
#     Huber_best = None
#     Huber_y_te_pred = np.zeros(len(y_test)) if 'y_test' in locals() else np.array([0.0])
#     Huber_r2_te = 0.0
#     Huber_coef_series = pd.Series(dtype=float)
#     Huber_term_analysis = []
#     Huber_equation_html = "HuberRegressor (비활성화됨)"

#     # Quantile
#     qr_gs = type("D", (), {})()
#     setattr(qr_gs, "best_params_", {})
#     QR_best = None
#     QR_y_te_pred = np.zeros(len(y_test)) if 'y_test' in locals() else np.array([0.0])
#     QR_r2_te = 0.0
#     QR_coef_series = pd.Series(dtype=float)
#     QR_term_analysis = []
#     QR_equation_html = "QuantileRegressor (비활성화됨)"

#     # Theil-Sen
#     TheilSen_lr = None
#     Theil_y_te_pred = np.zeros(len(y_test)) if 'y_test' in locals() else np.array([0.0])
#     Theil_r2_te = 0.0
#     Theil_coef_series = pd.Series(dtype=float)
#     Theil_term_analysis = []
#     Theil_equation_html = "Theil–Sen (비활성화됨)"

#     # RANSAC
#     RANSAC_lr = None
#     RANSAC_y_te_pred = np.zeros(len(y_test)) if 'y_test' in locals() else np.array([0.0])
#     RANSAC_r2_te = 0.0
#     RANSAC_coef_series = pd.Series(dtype=float)
#     RANSAC_term_analysis = []
#     RANSAC_equation_html = "RANSAC (비활성화됨)"

    # ==============================
    # === New: 6개 모델 표시 호출 ===
    # ==============================
    # _render_linear_block("RidgeCV", Ridge_r2_te, Ridge_equation_html, y_test, Ridge_y_te_pred, Ridge_term_analysis)
    # _render_linear_block("LassoCV", Lasso_r2_te, Lasso_equation_html, y_test, Lasso_y_te_pred, Lasso_term_analysis)
    # _render_linear_block("HuberRegressor", Huber_r2_te, Huber_equation_html, y_test, Huber_y_te_pred, Huber_term_analysis)
    # _render_linear_block("QuantileRegressor", QR_r2_te, QR_equation_html, y_test, QR_y_te_pred, QR_term_analysis)
    # _render_linear_block("Theil–Sen", Theil_r2_te, Theil_equation_html, y_test, Theil_y_te_pred, Theil_term_analysis)
    # _render_linear_block("RANSAC (Linear base)", RANSAC_r2_te, RANSAC_equation_html, y_test, RANSAC_y_te_pred, RANSAC_term_analysis)

    # ==============================
    # === New: 계수/기여도/정확도 비교 표 ===
    # ==============================


    # st.markdown("## 📚 모델 비교 표 (계수 · 기여도 · 정확도)")

    # # 0) 유틸: term_analysis(list[dict]) -> Series(name->avg_contribution)
    # def _term_to_series(term_list, value_key="avg_contribution"):
    #     if not isinstance(term_list, (list, tuple)):
    #         return pd.Series(dtype=float)
    #     pairs = {}
    #     for t in term_list:
    #         nm = t.get("name", None)
    #         if nm is None:
    #             continue
    #         pairs[nm] = float(t.get(value_key, 0.0))
    #     return pd.Series(pairs, dtype=float)

    # # 1) 모델별 결과 객체를 직접 참조
    # model_data = {
    #     "OLS": {
    #         "coef_series": OLS_coef_series if 'OLS_coef_series' in locals() else pd.Series(),
    #         "term_analysis": OLS_term_analysis if 'OLS_term_analysis' in locals() else [],
    #         "r2_val": OLS_r2_te if 'OLS_r2_te' in locals() else 0.0
    #     },
    #     "ElasticNet": {
    #         "coef_series": Elastic_coef_series if 'Elastic_coef_series' in locals() else pd.Series(),
    #         "term_analysis": Elastic_term_analysis if 'Elastic_term_analysis' in locals() else [],
    #         "r2_val": Elastic_r2_te if 'Elastic_r2_te' in locals() else 0.0
    #     },
    #     "RidgeCV": {
    #         "coef_series": Ridge_coef_series if 'Ridge_coef_series' in locals() else pd.Series(),
    #         "term_analysis": Ridge_term_analysis if 'Ridge_term_analysis' in locals() else [],
    #         "r2_val": Ridge_r2_te if 'Ridge_r2_te' in locals() else 0.0
    #     },
    #     "LassoCV": {
    #         "coef_series": Lasso_coef_series if 'Lasso_coef_series' in locals() else pd.Series(),
    #         "term_analysis": Lasso_term_analysis if 'Lasso_term_analysis' in locals() else [],
    #         "r2_val": Lasso_r2_te if 'Lasso_r2_te' in locals() else 0.0
    #     },
    #     "Huber": {
    #         "coef_series": Huber_coef_series if 'Huber_coef_series' in locals() else pd.Series(),
    #         "term_analysis": Huber_term_analysis if 'Huber_term_analysis' in locals() else [],
    #         "r2_val": Huber_r2_te if 'Huber_r2_te' in locals() else 0.0
    #     },
    #     "Quantile": {
    #         "coef_series": QR_coef_series if 'QR_coef_series' in locals() else pd.Series(),
    #         "term_analysis": QR_term_analysis if 'QR_term_analysis' in locals() else [],
    #         "r2_val": QR_r2_te if 'QR_r2_te' in locals() else 0.0
    #     },
    #     "Theil–Sen": {
    #         "coef_series": Theil_coef_series if 'Theil_coef_series' in locals() else pd.Series(),
    #         "term_analysis": Theil_term_analysis if 'Theil_term_analysis' in locals() else [],
    #         "r2_val": Theil_r2_te if 'Theil_r2_te' in locals() else 0.0
    #     },
    #     "RANSAC": {
    #         "coef_series": RANSAC_coef_series if 'RANSAC_coef_series' in locals() else pd.Series(),
    #         "term_analysis": RANSAC_term_analysis if 'RANSAC_term_analysis' in locals() else [],
    #         "r2_val": RANSAC_r2_te if 'RANSAC_r2_te' in locals() else 0.0
    #     }
    # }

    # # 2) 실제 데이터가 있는 모델만 필터링
    # coef_map = {}
    # term_map = {}
    # r2_map = {}

    # for label, data in model_data.items():
    #     if isinstance(data["coef_series"], pd.Series) and not data["coef_series"].empty:
    #         coef_map[label] = data["coef_series"].copy()
    #     if isinstance(data["term_analysis"], (list, tuple)) and len(data["term_analysis"]) > 0:
    #         term_map[label] = data["term_analysis"]
    #     if isinstance(data["r2_val"], (int, float, np.floating)) and not np.isnan(data["r2_val"]):
    #         r2_map[label] = float(data["r2_val"])

    # # 3) 인덱스(변수) 통일: X.columns + '절편'
    # all_vars = list(X.columns) if 'X' in locals() and hasattr(X, 'columns') else []
    # if "절편" not in all_vars:
    #     all_vars = all_vars + ["절편"]

    # # 4) 표 A: 계수 비교 (intercept는 '절편' 행에)
    # coef_df = pd.DataFrame(index=all_vars)

    # for label, s in coef_map.items():
    #     # 계수: 변수명 기준으로 채우고, 절편은 term_analysis에서 추출
    #     col = pd.Series(index=all_vars, dtype=float)
    #     # 변수 계수
    #     for v in X.columns:
    #         col.loc[v] = float(s.get(v, 0.0))
    #     # 절편 계수: term_analysis의 '절편' avg_contribution을 인터셉트로 간주
    #     ta = term_map.get(label, None)
    #     if ta is not None:
    #         ts = _term_to_series(ta, value_key="avg_contribution")
    #         if "절편" in ts.index:
    #             col.loc["절편"] = float(ts.loc["절편"])
    #         else:
    #             col.loc["절편"] = 0.0
    #     else:
    #         col.loc["절편"] = 0.0
    #     coef_df[label] = col

    # st.markdown("### 표 A. 계수 비교 (각 항의 계수, 절편 포함)")
    # st.dataframe(coef_df.round(6), width='stretch')

    # # 5) 표 B: 기여도 비교 (avg_contribution 기준, 절편 포함)
    # contrib_df = pd.DataFrame(index=all_vars)

    # for label, tl in term_map.items():
    #     ts = _term_to_series(tl, value_key="avg_contribution")
    #     col = pd.Series(index=all_vars, dtype=float)
    #     # 변수 + 절편 모두 반영, 없으면 0.0
    #     for v in all_vars:
    #         col.loc[v] = float(ts.get(v, 0.0))
    #     contrib_df[label] = col

    # st.markdown("### 표 B. 기여도 비교 (각 항 × 계수의 평균값, 절편 포함)")
    # st.dataframe(contrib_df.round(6), width='stretch')

    # # 6) 표 C: 정확도 비교 (R², 테스트셋 기준)
    # acc_df = pd.DataFrame([r2_map], index=["R² (test)"]).reindex(columns=list(r2_map.keys()))
    # st.markdown("### 표 C. 정확도 비교 (R²)")
    # st.dataframe(acc_df.applymap(lambda v: f"{v:.4f}" if pd.notnull(v) else ""), width='stretch')


    # --- dCor 히트맵 분석 helper: 거리상관(0~1, 부호 없음) ---
    @st.cache_data(show_spinner="dCor 계산 중...")
    def distance_correlation(a, b):
        a = pd.Series(a).astype(float); b = pd.Series(b).astype(float)
        m = (~a.isna()) & (~b.isna()); a = a[m].values; b = b[m].values
        if len(a) < 3: return np.nan
        A = np.abs(a[:, None] - a[None, :]); B = np.abs(b[:, None] - b[None, :])
        A -= A.mean(axis=1, keepdims=True); A -= A.mean(axis=0, keepdims=True); A += A.mean()
        B -= B.mean(axis=1, keepdims=True); B -= B.mean(axis=0, keepdims=True); B += B.mean()
        dcov2 = np.mean(A*B); dvarx = np.mean(A*A); dvary = np.mean(B*B)
        if dvarx <= 0 or dvary <= 0: return 0.0
        dcor = np.sqrt(max(dcov2,0)) / np.sqrt(np.sqrt(dvarx*dvary))
        return float(np.clip(dcor, 0, 1))

    @st.cache_data(show_spinner="dCor 계산 중...")
    def compute_dcor_matrix(df_num, cols):
        M = pd.DataFrame(np.eye(len(cols)), index=cols, columns=cols, dtype=float)
        for i, c1 in enumerate(cols):
            for j, c2 in enumerate(cols):
                if j < i: 
                    M.iloc[i, j] = M.iloc[j, i]
                elif j > i:
                    M.iloc[i, j] = distance_correlation(df_num[c1], df_num[c2])
                    M.iloc[j, i] = M.iloc[i, j]
        return M

    with st.container(border=True):
        # 상관관계 히트맵
        st.markdown('<h4 style="margin: 10px 0; color: #333;">🔗 상관관계 히트맵 분석</h4>', unsafe_allow_html=True)
        
        st.markdown("""
        <div style="background-color: #E8F2FC; border: 1px solid #E8F2FC; border-radius: 0.375rem; padding: 1rem; margin: 1rem 0;">
            <div style="display: flex; align-items: flex-start;">
                <span style="font-size: 1.2em; margin-right: 0.5rem;"></span>
                <div>
                    <strong>💡 <u>상관관계 히트맵이란,</u></strong><br>
                    &nbsp;변수 간 선형적인 상관관계를 시각화한 기법으로, 최소제곱법과 함께 데이터의 선형적 패턴을 파악하는 대표적인 도구입니다.<br>
                    &nbsp;두 변수가 선형적으로 결합된 강도와 방향을 설명합니다. <br>
                    <span style="font-size: 0.9em; color: #666;">&nbsp;&nbsp;•&nbsp; +1 : 완전한 양의 상관관계<br>
                    &nbsp;&nbsp;•&nbsp; 0 : 상관관계가 없음<br>
                    &nbsp;&nbsp;•&nbsp; -1 : 완전한 음의 상관관계</span>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # 수치형 변수만 선택하여 상관관계 계산
        numeric_cols = [col for col in [y_column] + x_columns if df_ready[col].dtype in ['int64', 'float64']]
        
        if len(numeric_cols) > 1:
           
            # 상관관계 분석 결과를 저장할 딕셔너리
            correlation_results = {}
            
            # 4분할 컬럼으로 히트맵 배치
            heatmap_col1, heatmap_col2, heatmap_col3, heatmap_col4 = st.columns([1, 1, 1, 1])
            
            # Pearson 히트맵
            with heatmap_col1:
                st.markdown("<h5 style='text-align: center; margin-bottom: 2px;'>Pearson</h5>", unsafe_allow_html=True)
                
                # Pearson 상관계수 설명
                st.markdown("""
                <div style="background-color: #f8f9fa; border-left: 4px solid #007bff; padding: 8px 12px; margin-bottom: 10px; font-size: 0.85rem; line-height: 1.4;">
                    • <strong>방식:</strong> 두 변수 간의 직선적 관계의 강도와 방향을 측정<br>
                    • <strong>특징:</strong> 가장 보수적이며, 이상치에 민감함<br>
                    • <strong>한계:</strong> 비선형 관계는 감지하지 못함 (곡선, 지수, 로그 관계 등)<br>
                    • <strong>적용:</strong> 정규분포를 따르는 데이터에 가장 적합
                </div>
                """, unsafe_allow_html=True)

                # Pearson 상관계수 계산 함수 호출 (기존 방식)
                correlation_matrix = df_ready[numeric_cols].corr(method='pearson')
                
                # Pearson 상관계수 계산 함수 호출 (프로파일링 적용)
                # correlation_matrix = profile_run(
                #     "Pearson correlation matrix compute (df_ready[numeric_cols].corr(method='pearson'))",
                #     df_ready[numeric_cols].corr,
                #     method='pearson')

                correlation_results['Pearson'] = correlation_matrix
                
                fig, ax = plt.subplots(figsize=(7, 7))
                im = ax.imshow(correlation_matrix, cmap='coolwarm', aspect='auto', vmin=-1, vmax=1)
                
                # 축 레이블 설정
                ax.set_xticks(range(len(correlation_matrix.columns)))
                ax.set_yticks(range(len(correlation_matrix.columns)))
                ax.set_xticklabels(correlation_matrix.columns, rotation=45, ha='right')
                ax.set_yticklabels(correlation_matrix.columns)
                
                # 상관계수 값 표시
                for i in range(len(correlation_matrix.columns)):
                    for j in range(len(correlation_matrix.columns)):
                        text = ax.text(j, i, f'{correlation_matrix.iloc[i, j]:.2f}',
                                    ha="center", va="center", color="black", fontsize=8)
                
                plt.colorbar(im, ax=ax)

                st.pyplot(fig)

            # Spearman 히트맵
            with heatmap_col2:
                st.markdown("<h5 style='text-align: center; margin-bottom: 2px;'>Spearman</h5>", unsafe_allow_html=True)
                
                # Spearman 상관계수 설명
                st.markdown("""
                <div style="background-color: #f8f9fa; border-left: 4px solid #28a745; padding: 8px 12px; margin-bottom: 10px; font-size: 0.85rem; line-height: 1.4;">
                    • <strong>방식:</strong> 데이터의 순위(rank)를 기반으로 관계를 측정<br>
                    • <strong>특징:</strong> 이상치에 강하며, 단조증가/감소 관계를 잘 포착<br>
                    • <strong>장점:</strong> 비선형 관계도 감지 가능 (단조적 관계 한정)<br>
                    • <strong>적용:</strong> 정규분포가 아닌 데이터나 순서가 중요한 경우에 유용
                </div>
                """, unsafe_allow_html=True)
                
                # Spearman 상관계수 계산 함수 호출
                correlation_matrix = df_ready[numeric_cols].corr(method='spearman')

                # Spearman 상관계수 계산 함수 호출 (프로파일링 적용)
                # correlation_matrix = profile_run(
                #     "Spearman correlation matrix compute (df_ready[numeric_cols].corr(method='spearman'))",
                #     df_ready[numeric_cols].corr,
                #     method='spearman')

                correlation_results['Spearman'] = correlation_matrix
                
                fig, ax = plt.subplots(figsize=(7, 7))
                im = ax.imshow(correlation_matrix, cmap='coolwarm', aspect='auto', vmin=-1, vmax=1)
                
                # 축 레이블 설정
                ax.set_xticks(range(len(correlation_matrix.columns)))
                ax.set_yticks(range(len(correlation_matrix.columns)))
                ax.set_xticklabels(correlation_matrix.columns, rotation=45, ha='right')
                ax.set_yticklabels(correlation_matrix.columns)
                
                # 상관계수 값 표시
                for i in range(len(correlation_matrix.columns)):
                    for j in range(len(correlation_matrix.columns)):
                        text = ax.text(j, i, f'{correlation_matrix.iloc[i, j]:.2f}',
                                    ha="center", va="center", color="black", fontsize=8)
                
                plt.colorbar(im, ax=ax)

                st.pyplot(fig)

            # Kendall 히트맵
            with heatmap_col3:
                st.markdown("<h5 style='text-align: center; margin-bottom: 2px;'>Kendall</h5>", unsafe_allow_html=True)
                
                # Kendall 상관계수 설명
                st.markdown("""
                <div style="background-color: #f8f9fa; border-left: 4px solid #ffc107; padding: 8px 12px; margin-bottom: 10px; font-size: 0.85rem; line-height: 1.4;">
                    • <strong>방식:</strong> 데이터 쌍의 일치/불일치 패턴을 기반으로 관계 측정<br>
                    • <strong>특징:</strong> Spearman보다 더 보수적이며, 작은 표본에서도 안정적<br>
                    • <strong>장점:</strong> 이상치에 매우 강하며, 순위 기반으로 비선형 관계 감지<br>
                    • <strong>적용:</strong> 작은 데이터셋이나 노이즈가 많은 데이터에 특히 유용
                </div>
                """, unsafe_allow_html=True)
                
                # Kendall 상관계수 계산 함수 호출
                correlation_matrix = df_ready[numeric_cols].corr(method='kendall')
                
                # Kendall 상관계수 계산 함수 호출 (프로파일링 적용)
                # correlation_matrix = profile_run(
                #     "Kendall correlation matrix compute (df_ready[numeric_cols].corr(method='kendall'))",
                #     df_ready[numeric_cols].corr,
                #     method='kendall')

                correlation_results['Kendall'] = correlation_matrix
                
                fig, ax = plt.subplots(figsize=(7, 7))
                im = ax.imshow(correlation_matrix, cmap='coolwarm', aspect='auto', vmin=-1, vmax=1)
                
                # 축 레이블 설정
                ax.set_xticks(range(len(correlation_matrix.columns)))
                ax.set_yticks(range(len(correlation_matrix.columns)))
                ax.set_xticklabels(correlation_matrix.columns, rotation=45, ha='right')
                ax.set_yticklabels(correlation_matrix.columns)
                
                # 상관계수 값 표시
                for i in range(len(correlation_matrix.columns)):
                    for j in range(len(correlation_matrix.columns)):
                        text = ax.text(j, i, f'{correlation_matrix.iloc[i, j]:.2f}',
                                    ha="center", va="center", color="black", fontsize=8)
                
                plt.colorbar(im, ax=ax)
                
                st.pyplot(fig)

            # dCor 히트맵
            with heatmap_col4:
                st.markdown("<h5 style='text-align:center;margin-bottom:2px;'>dCor (강도만 분석)</h5>", unsafe_allow_html=True)
                
                # dCor 설명
                st.markdown("""
                <div style="background-color: #f8f9fa; border-left: 4px solid #17a2b8; padding: 8px 12px; margin-bottom: 10px; font-size: 0.85rem; line-height: 1.4;">
                    • <strong>방식:</strong> 변수 간 거리 행렬을 기반으로 모든 종류의 관계를 측정<br>
                    • <strong>특징:</strong> 가장 포괄적이며, 선형/비선형 관계 모두 감지 가능<br>
                    • <strong>장점:</strong> 복잡한 패턴(곡선, 주기적, 클러스터 등)도 포착<br>
                    • <strong>한계:</strong><u> 부호(양수/음수) 정보는 제공하지 않음 (강도만 측정)</u>
                </div>
                """, unsafe_allow_html=True)
                
                # dcor matrix 계산 함수 호출
                dcor_matrix = compute_dcor_matrix(df_ready[numeric_cols], numeric_cols)

                # dcor matrix 계산 함수 호출 (프로파일링 적용)
                # dcor_matrix = profile_run(
                #     "dCor matrix compute (compute_dcor_matrix)",
                #     compute_dcor_matrix,
                #     df_ready[numeric_cols],  # 또는 df_num
                #     numeric_cols)

                correlation_results['dCor'] = dcor_matrix
                
                fig, ax = plt.subplots(figsize=(7,7))
                im = ax.imshow(dcor_matrix, cmap='YlGnBu', aspect='auto', vmin=0, vmax=1)
                ax.set_xticks(range(len(dcor_matrix.columns)))
                ax.set_yticks(range(len(dcor_matrix.columns)))
                ax.set_xticklabels(dcor_matrix.columns, rotation=45, ha='right')
                ax.set_yticklabels(dcor_matrix.columns)
                for i in range(len(dcor_matrix.columns)):
                    for j in range(len(dcor_matrix.columns)):
                        ax.text(j, i, f'{dcor_matrix.iloc[i,j]:.2f}', ha='center', va='center', color='black', fontsize=8)
                plt.colorbar(im, ax=ax)

                st.pyplot(fig)

        else:
            st.info("상관관계 분석을 위한 수치형 변수가 부족합니다.")

    with st.container(border=True):
        st.markdown("#### ⚖️ 기법 별 분석 결과 비교")

        # =================================================================
        # === 1. 데이터 준비: Y-X 쌍별 상관관계 값 집계 ===
        # =================================================================
        # 상관관계 분석을 위한 수치형 변수만 필터링
        numeric_cols_for_corr = [c for c in [y_column] + x_columns if c in numeric_cols]
        
        # 각 변수와 Y변수 간의 상관계수 추출
        _4rows = []
        if 'correlation_results' in locals() and 'dcor_matrix' in locals():
            for x in [c for c in x_columns if c in numeric_cols_for_corr]:
                p = correlation_results.get("Pearson", pd.DataFrame()).get(x, {}).get(y_column, np.nan)
                s = correlation_results.get("Spearman", pd.DataFrame()).get(x, {}).get(y_column, np.nan)
                k = correlation_results.get("Kendall", pd.DataFrame()).get(x, {}).get(y_column, np.nan)
                d = dcor_matrix.get(x, {}).get(y_column, np.nan)
                _4rows.append({"변수": x, "Pearson": p, "Spearman": s, "Kendall": k, "dCor": d})
        
        stats4 = pd.DataFrame(_4rows)

        # =================================================================
        # === 2. 헬퍼 함수 정의: 히트맵 합의 값 및 비교 로직 ===
        # =================================================================
        
        def get_heatmap_consensus_value(row):
            """
            부호와 강도를 종합하여 히트맵의 가중 평균 상관계수를 계산합니다.
            - 부호 합의: Pearson 50%, Spearman 30%, Kendall 20%
            - 강도 합의: |Pearson| 40%, |Spearman| 20%, |Kendall| 10%, dCor 30%
            """
            # --- 부호 계산 ---
            sign_weights = [0.5, 0.3, 0.2]
            sign_values = [row.get("Pearson", 0), row.get("Spearman", 0), row.get("Kendall", 0)]
            
            valid_sign_values = [v for v in sign_values if not pd.isna(v)]
            if not valid_sign_values:
                sign_consensus = 0
            else:
                weighted_sign_avg = np.average(
                    [v for v in sign_values if not pd.isna(v)],
                    weights=[w for v, w in zip(sign_values, sign_weights) if not pd.isna(v)]
                )
                if weighted_sign_avg > 0:
                    sign_consensus = 1
                else:
                    sign_consensus = -1

            # --- 강도(절댓값) 계산 ---
            strength_weights = [0.4, 0.2, 0.1, 0.3]
            strength_values = [
                abs(row.get("Pearson", 0)) if not pd.isna(row.get("Pearson")) else 0,
                abs(row.get("Spearman", 0)) if not pd.isna(row.get("Spearman")) else 0,
                abs(row.get("Kendall", 0)) if not pd.isna(row.get("Kendall")) else 0,
                row.get("dCor", 0) if not pd.isna(row.get("dCor")) else 0
            ]
            
            strength_consensus = np.average(strength_values, weights=strength_weights)
            
            return sign_consensus * strength_consensus

        def get_comparison_result(lr_ratio, heatmap_value):
            """
            최소제곱법 기여도와 히트맵 상관 강도를 비교하여 최종 결과를 판정합니다.
            (기존 코드 777~804행 로직과 동일)
            """
            lr_abs = abs(lr_ratio)
            heatmap_abs = abs(heatmap_value * 100) # % 단위로 변환
            lr_sign = np.sign(lr_ratio)
            heatmap_sign = np.sign(heatmap_value)

            if lr_abs <= 2 or heatmap_abs <= 2:
                return "🟡 관계성 모호"
            elif lr_sign != heatmap_sign and lr_sign != 0 and heatmap_sign != 0:
                return "🔴 방향 불일치"
            elif (lr_abs <= 10 and heatmap_abs <= 10) or (lr_abs > 10 and heatmap_abs > 10):
                return "🟢 상호 일치"
            elif (lr_abs <= 5 and heatmap_abs > 10) or (heatmap_abs <= 5 and lr_abs > 10):
                return "🟡 강도 불일치"
            else:
                return "🟢 상호 일치"

        # =================================================================
        # === 3. 테이블 데이터 구성 및 계산 ===
        # =================================================================
        table_data = []
        if not stats4.empty:
            for _, row in stats4.iterrows():
                var_name = row["변수"]
                special_notes = [] # 특기사항을 담을 리스트

                # --- 1) 최소제곱법 기여도 ---
                lr_ratio = 0.0
                if 'OLS_term_analysis' in locals():
                    for term in OLS_term_analysis:
                        if term["name"] == var_name:
                            lr_ratio = term.get("ratio", 0.0)
                            break
                
                # --- 2) 히트맵 상관 강도 ---
                heatmap_value = get_heatmap_consensus_value(row)
                
                # --- 3) 상호 비교 결과 ---
                comparison_result = get_comparison_result(lr_ratio, heatmap_value)

                # --- 4) 특기사항 ---
                # 6.1: dCor 값에 따른 비선형 관계 가능성
                dcor_val = row.get("dCor", 0)
                if not pd.isna(dcor_val) and dcor_val >= 0.3:
                    special_notes.append(f"⚠️ 비선형적 관계가 있을 수 있습니다. (dCor: {dcor_val:.3f})")

                # 6.2: 노란색 신호등(🟡) 상세 메시지 (기존 코드 889~902행 로직)
                if "🟡" in comparison_result:
                    lr_abs = abs(lr_ratio)
                    heatmap_abs = abs(heatmap_value * 100)
                    if lr_abs <= 2 or heatmap_abs <= 2: # 관계성 모호
                        if lr_abs <= 2 and heatmap_abs <= 2:
                            special_notes.append("두 분석 모두 관계성이 약하여 Y와 무관할 수 있습니다.")
                        elif lr_abs <= 2:
                            special_notes.append(f"최소제곱법 기여도({lr_abs:.1f}%)가 약하여 관계성 판단에 주의가 필요합니다.")
                        else:
                            special_notes.append(f"히트맵 상관 강도({heatmap_abs:.1f}%)가 약하여 관계성 판단에 주의가 필요합니다.")
                    else: # 강도 불일치
                        if lr_abs > heatmap_abs:
                            special_notes.append(f"최소제곱법 기여도({lr_abs:.1f}%)가 히트맵 상관 강도({heatmap_abs:.1f}%)에 비해 큽니다.")
                        else:
                            special_notes.append(f"히트맵 상관 강도({heatmap_abs:.1f}%)가 최소제곱법 기여도({lr_abs:.1f}%)에 비해 큽니다.")
                
                # 6.3: 빨간색 신호등(🔴) 메시지
                if "🔴" in comparison_result:
                    special_notes.append("최소제곱법과 히트맵의 상관관계 방향이 불일치합니다.")

                # 특기사항을 줄바꿈으로 연결 (2개 이상일 때만)
                if len(special_notes) == 1:
                    special_notes_merged = special_notes[0]
                elif len(special_notes) > 1:
                    special_notes_merged = "\n".join(special_notes)
                else:
                    special_notes_merged = ""

                table_data.append({
                    "X 변수": var_name,
                    "최소제곱법 (Y에 대한 기여도)": f"{lr_ratio:+.1f}%",
                    "히트맵 (상관 강도)": f"{heatmap_value * 100:+.1f}%",
                    "상호 비교 결과": comparison_result,
                    "특기사항": special_notes_merged,
                    "_sort_key": abs(lr_ratio) # 정렬을 위한 임시 키
                })

        # =================================================================
        # === 4. 정렬 및 최종 테이블 표시 ===
        # =================================================================
        if table_data:
            # 최소제곱법 기여도 절댓값 기준으로 내림차순 정렬
            table_data.sort(key=lambda x: x["_sort_key"], reverse=True)
            
            # 정렬 후 임시 키 제거
            for row in table_data:
                del row["_sort_key"]

            summary_df = pd.DataFrame(table_data)
            st.dataframe(summary_df, width='stretch', hide_index=True)
        else:
            st.info("비교 분석을 위한 데이터가 부족합니다.")

    return {
        "r2_test": float(OLS_r2_te),  # OLS를 기본값으로 유지 (기존 호환성)
        "coefficients": OLS_coef_series.to_dict(),  # OLS를 기본값으로 유지 (기존 호환성)
        
        # === OLS 결과 ===
        "OLS": {
            "r2_test": float(OLS_r2_te),
            "coefficients": OLS_coef_series.to_dict(),
            "term_analysis": OLS_term_analysis
        },
        
        # === ElasticNet 결과 ===
        "ElasticNet": {
            "r2_test": float(Elastic_r2_te),
            "coefficients": Elastic_coef_series.to_dict(),
            "term_analysis": Elastic_term_analysis,
            "best_alpha": float(best_alpha),
            "best_l1_ratio": float(best_l1_ratio)
        },
        
        # # === RidgeCV 결과 ===
        # "RidgeCV": {
        #     "r2_test": float(Ridge_r2_te),
        #     "coefficients": Ridge_coef_series.to_dict(),
        #     "term_analysis": Ridge_term_analysis,
        #     "best_alpha": float(Ridge_lr.alpha_)
        # },
        
        # # === LassoCV 결과 ===
        # "LassoCV": {
        #     "r2_test": float(Lasso_r2_te),
        #     "coefficients": Lasso_coef_series.to_dict(),
        #     "term_analysis": Lasso_term_analysis,
        #     "best_alpha": float(Lasso_lr.alpha_)
        # },
        
        # # === HuberRegressor 결과 ===
        # "HuberRegressor": {
        #     "r2_test": float(Huber_r2_te),
        #     "coefficients": Huber_coef_series.to_dict(),
        #     "term_analysis": Huber_term_analysis,
        #     "best_params": huber_gs.best_params_
        # },
        
        # # === QuantileRegressor 결과 ===
        # "QuantileRegressor": {
        #     "r2_test": float(QR_r2_te),
        #     "coefficients": QR_coef_series.to_dict(),
        #     "term_analysis": QR_term_analysis,
        #     "best_params": qr_gs.best_params_
        # },
        
        # # === TheilSenRegressor 결과 ===
        # "TheilSenRegressor": {
        #     "r2_test": float(Theil_r2_te),
        #     "coefficients": Theil_coef_series.to_dict(),
        #     "term_analysis": Theil_term_analysis
        # },
        
        # # === RANSACRegressor 결과 ===
        # "RANSACRegressor": {
        #     "r2_test": float(RANSAC_r2_te),
        #     "coefficients": RANSAC_coef_series.to_dict(),
        #     "term_analysis": RANSAC_term_analysis,
        #     "n_inliers": int(RANSAC_lr.n_estimators_) if hasattr(RANSAC_lr, 'n_estimators_') else None
        # },
        
        # === 전체 모델 성능 요약 ===
        "model_performance": {
            "OLS": float(OLS_r2_te),
            "ElasticNet": float(Elastic_r2_te),
            # "RidgeCV": float(Ridge_r2_te),
            # "LassoCV": float(Lasso_r2_te),
            # "HuberRegressor": float(Huber_r2_te),
            # "QuantileRegressor": float(QR_r2_te),
            # "TheilSenRegressor": float(Theil_r2_te),
            # "RANSACRegressor": float(RANSAC_r2_te)
        },
        
        # === 최고 성능 모델 정보 ===
        "best_model": {
            "name": max([
                ("OLS", OLS_r2_te),
                ("ElasticNet", Elastic_r2_te),
                # ("RidgeCV", Ridge_r2_te),
                # ("LassoCV", Lasso_r2_te),
                # ("HuberRegressor", Huber_r2_te),
                # ("QuantileRegressor", QR_r2_te),
                # ("TheilSenRegressor", Theil_r2_te),
                # ("RANSACRegressor", RANSAC_r2_te)
            ], key=lambda x: x[1])[0],
            "r2_score": max([
                OLS_r2_te, Elastic_r2_te
                # , Ridge_r2_te, Lasso_r2_te,
                # Huber_r2_te, QR_r2_te, Theil_r2_te, RANSAC_r2_te
            ])
        }
    }
