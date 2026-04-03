import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.linear_model import Lasso
from statsmodels.stats.outliers_influence import variance_inflation_factor
import shap
import time

# ==============================
# === 3단계: 변수 선택 적정성 점검 ===
# ==============================
def perform_variable_check(df, x_cols):
    """3단계: 다중공선성(VIF), 변수 선택(LASSO), SHAP 분석, 종합 해석을 4분면으로 렌더링합니다."""
        
    numeric_x_cols = df[x_cols].select_dtypes(include=np.number).columns.tolist()
    if not numeric_x_cols:
        st.warning("3단계 분석을 위해서는 수치형 변수가 필요합니다.")
        return
    
    # 분석 결과를 저장할 변수들
    vif_data = None
    lasso_data = None
    shap_data = None
        
    # === 상단 2분면: VIF와 LASSO ===
    col1, col2 = st.columns(2)

    with col1:
        with st.container(border=True):
            st.markdown("<h4 style='text-align: center;'>🚨 변수 간 '메아리 현상' 탐지 (VIF)</h4>", unsafe_allow_html=True)
            with st.spinner("변수들이 서로 얼마나 비슷한지 계산하는 중..."):
                X = df[numeric_x_cols].dropna()
                if X.shape[0] < 2:
                    st.warning("VIF를 계산하기에 데이터가 부족합니다.")
                else:
                    scaler = StandardScaler()
                    X_scaled = scaler.fit_transform(X)
                    vif_data = pd.DataFrame()
                    vif_data["feature"] = X.columns
                    vif_data["VIF"] = [variance_inflation_factor(X_scaled, i) for i in range(X_scaled.shape[1])]
                    vif_data = vif_data.sort_values('VIF', ascending=True)

                    colors = ['#2ca02c' if x < 5 else '#ff7f0e' if x < 10 else '#d62728' for x in vif_data['VIF']]
                    
                    fig = go.Figure(go.Bar(x=vif_data['VIF'], y=vif_data['feature'], orientation='h', marker_color=colors))
                    fig.update_layout(
                        xaxis_title="VIF 값 (높을수록 다른 변수와 유사)", height=350, margin=dict(l=20, r=20, t=40, b=20),
                        shapes=[
                            dict(type="line", xref="x", yref="paper", x0=5, y0=0, x1=5, y1=1, line=dict(color="#ff7f0e", width=2, dash="dash")),
                            dict(type="line", xref="x", yref="paper", x0=10, y0=0, x1=10, y1=1, line=dict(color="#d62728", width=2, dash="dash"))
                        ]
                    )
                    st.plotly_chart(fig, width='stretch')
                    st.caption("VIF가 5 이상이면 주의, 10 이상이면 다른 변수와 매우 유사하여 분석 결과를 왜곡시킬 수 있습니다.")

    with col2:
        with st.container(border=True):
            st.markdown("<h4 style='text-align: center;'>🤖 AI가 선택한 핵심 변수 (LASSO)</h4>", unsafe_allow_html=True)
            with st.spinner("AI가 스스로 중요 변수를 고르고 있습니다..."):
                X = df[numeric_x_cols]
                y = df[st.session_state.y_column]
                
                pipeline = Pipeline(steps=[('scaler', StandardScaler()), ('regressor', Lasso(alpha=0.1, random_state=42))])
                pipeline.fit(X, y)
                coefs = pipeline.named_steps['regressor'].coef_
                
                lasso_data = pd.DataFrame({'변수': X.columns, '영향력': coefs})
                lasso_data = lasso_data[abs(lasso_data['영향력']) > 1e-5].sort_values('영향력', ascending=True)
                
                fig = go.Figure(go.Bar(x=lasso_data['영향력'], y=lasso_data['변수'], orientation='h', marker_color=np.where(lasso_data['영향력'] > 0, '#1f77b4', '#d62728')))
                fig.update_layout(xaxis_title="Y값에 대한 영향력 (양수/음수)", height=350, margin=dict(l=20, r=20, t=40, b=20))
                st.plotly_chart(fig, width='stretch')
                st.caption("LASSO 모델은 영향력이 높은 변수를 스스로 탐색합니다. 막대가 길수록 중요한 변수입니다.")

    # === 하단 2분면: SHAP와 종합 해석 ===
    col3, col4 = st.columns(2)
    
    with col3:
        with st.container(border=True):
            st.markdown("<h4 style='text-align: center;'>🔬 변수별 실제 기여도 (SHAP)</h4>", unsafe_allow_html=True)
            with st.spinner("각 변수가 실제 예측에 미치는 영향력을 계산하는 중..."):
                try:
                    # 간단한 Random Forest 모델로 SHAP 계산
                    from sklearn.ensemble import RandomForestRegressor
                    X = df[numeric_x_cols].dropna()
                    y = df[st.session_state.y_column].loc[X.index]
                    
                    if len(X) > 10:  # 최소 데이터 요구사항
                        rf_model = RandomForestRegressor(n_estimators=50, random_state=42)
                        rf_model.fit(X, y)
                        
                        # SHAP 값 계산 (샘플링하여 계산 속도 향상)
                        sample_size = min(100, len(X))
                        X_sample = X.sample(n=sample_size, random_state=42)
                        
                        explainer = shap.TreeExplainer(rf_model)
                        shap_values = explainer.shap_values(X_sample)
                        
                        # SHAP 중요도 계산 (평균 절댓값)
                        shap_importance = pd.DataFrame({
                            '변수': X.columns,
                            'SHAP 중요도': np.abs(shap_values).mean(axis=0)
                        }).sort_values('SHAP 중요도', ascending=True)
                        
                        shap_data = shap_importance
                        
                        fig = go.Figure(go.Bar(
                            x=shap_importance['SHAP 중요도'], 
                            y=shap_importance['변수'], 
                            orientation='h', 
                            marker_color='#8e44ad'
                        ))
                        fig.update_layout(
                            xaxis_title="SHAP 중요도 (평균 절댓값)", 
                            height=350, 
                            margin=dict(l=20, r=20, t=40, b=20)
                        )
                        st.plotly_chart(fig, width='stretch')
                        st.caption("SHAP는 각 변수가 실제 예측값에 미치는 기여도를 정확히 측정합니다. 높을수록 중요한 변수입니다.")
                    else:
                        st.warning("SHAP 분석을 위한 데이터가 부족합니다.")
                except Exception as e:
                    st.warning(f"SHAP 분석 중 오류가 발생했습니다: {str(e)}")
    
    with col4:
        with st.container(border=True):
            st.markdown("<h4 style='text-align: center;'>🔬 변수 선택 적정성 종합 해석</h4>", unsafe_allow_html=True)
            
            # 종합 해석 생성
            interpretation = generate_variable_selection_interpretation(vif_data, lasso_data, shap_data, numeric_x_cols)
            
            st.markdown(f"""
            <div style="background: linear-gradient(135deg, #f8f9fa, #e9ecef); 
                        border: 2px solid #6c757d; 
                        border-radius: 15px; 
                        padding: 20px; 
                        margin: 10px 0;
                        line-height: 1.6;">
                {interpretation}
            </div>
            """, unsafe_allow_html=True)

def generate_variable_selection_interpretation(vif_data, lasso_data, shap_data, all_vars):
    """VIF, LASSO, SHAP 분석 결과를 종합하여 변수 선택 적정성 해석을 생성합니다."""
    
    interpretation_parts = []
    
    # VIF 분석 결과 해석
    if vif_data is not None and len(vif_data) > 0:
        high_vif_vars = vif_data[vif_data['VIF'] >= 10]['feature'].tolist()
        medium_vif_vars = vif_data[(vif_data['VIF'] >= 5) & (vif_data['VIF'] < 10)]['feature'].tolist()
        
        if high_vif_vars:
            interpretation_parts.append(f"<strong> 심각한 다중공선성:</strong> {', '.join(high_vif_vars)} 변수들은 VIF 10 이상으로 서로 매우 유사합니다. 이 중 일부를 제거하는 것을 권장합니다.")
        elif medium_vif_vars:
            interpretation_parts.append(f"<strong>⚠️ 주의 필요:</strong> {', '.join(medium_vif_vars)} 변수들은 VIF 5-10으로 어느 정도 유사합니다. 모니터링이 필요합니다.")
        else:
            interpretation_parts.append("<strong>✅ 다중공선성 양호:</strong> 모든 변수들이 VIF 5 미만으로 독립성이 잘 유지되고 있습니다.")
    
    # LASSO 분석 결과 해석
    if lasso_data is not None and len(lasso_data) > 0:
        important_vars = lasso_data[abs(lasso_data['영향력']) > 0.1]['변수'].tolist()
        if important_vars:
            interpretation_parts.append(f"<strong>🎯 핵심 변수:</strong> LASSO 분석 결과 {', '.join(important_vars)} 변수들이 Y값 예측에 가장 중요한 것으로 나타났습니다.")
        else:
            interpretation_parts.append("<strong>📊 변수 영향력:</strong> LASSO 분석에서 모든 변수들의 영향력이 상대적으로 작게 나타났습니다.")
    
    # SHAP 분석 결과 해석
    if shap_data is not None and len(shap_data) > 0:
        top_shap_vars = shap_data.nlargest(3, 'SHAP 중요도')['변수'].tolist()
        if top_shap_vars:
            interpretation_parts.append(f"<strong>🔬 실제 기여도:</strong> SHAP 분석에서 {', '.join(top_shap_vars)} 변수들이 실제 예측에 가장 큰 기여를 하고 있습니다.")
    
    # 종합 권고사항
    interpretation_parts.append("<strong>💡 권고사항:</strong>")
    
    if vif_data is not None:
        high_vif_count = len(vif_data[vif_data['VIF'] >= 10])
        if high_vif_count > 0:
            interpretation_parts.append("• 다중공선성이 심한 변수들을 제거하여 모델의 안정성을 높이세요.")
    
    if lasso_data is not None and shap_data is not None:
        lasso_vars = set(lasso_data['변수'].tolist())
        shap_vars = set(shap_data['변수'].tolist())
        common_vars = lasso_vars.intersection(shap_vars)
        if len(common_vars) >= 2:
            interpretation_parts.append("• LASSO와 SHAP 분석에서 공통으로 중요하게 나타난 변수들을 중심으로 모델을 구성하세요.")
    
    return "<br><br>".join(interpretation_parts)

# ==============================
# === 시각화 및 UI 헬퍼 함수 ===
# ==============================

def format_number(value):
    """
    수치 포맷팅 함수
    - 백만 이하: ##,### 형태 (소수점 자릿수는 숫자 크기에 따라)
    - 백만 이상: ##.#m 형태
    """
    if pd.isna(value) or value is None:
        return "N/A"
    
    abs_value = abs(value)
    
    # 백만 이상인 경우
    if abs_value >= 1_000_000:
        return f"{value/1_000_000:.1f}m"
    
    # 백만 이하인 경우 - 소수점 자릿수 결정
    if abs_value <= 1:
        # 1 이하: 소수점 3자리
        return f"{value:,.3f}"
    elif abs_value <= 10:
        # 10 이하: 소수점 2자리
        return f"{value:,.2f}"
    elif abs_value <= 100:
        # 100 이하: 소수점 1자리
        return f"{value:,.1f}"
    else:
        # 100 초과: 정수 (쉼표만)
        return f"{value:,.0f}"

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

def render_metric_card(title, value, unit="", help_text=""):
    """중요 지표를 강조하는 카드 UI를 렌더링합니다."""
    st.markdown(f"""
    <div style="background-color: #F0F2F6; border-left: 5px solid #1E90FF; padding: 1rem; border-radius: 5px; margin-bottom: 1rem;">
        <p style="font-size: 0.9rem; margin: 0; color: #555;">{title}</p>
        <p style="font-size: 2.2rem; font-weight: bold; margin: 0;">{value} <span style="font-size: 1.5rem;">{unit}</span></p>
        <p style="font-size: 0.8rem; margin: 0.5rem 0 0 0; color: #888;">{help_text}</p>
    </div>
    """, unsafe_allow_html=True)

