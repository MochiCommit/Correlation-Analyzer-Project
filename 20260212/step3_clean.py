import streamlit as st
import pandas as pd
import numpy as np

def data_cleaner(df_subset):
    """
    결측치 처리를 담당하는 함수
    
    Args:
        df_subset (pd.DataFrame): 처리할 데이터프레임
        
    Returns:
        None: session state에 정리된 데이터를 저장
    """
    
    # Session state 초기화
    if 'cleaning_completed' not in st.session_state:
        st.session_state.cleaning_completed = False
    if 'cleaning_method' not in st.session_state:
        st.session_state.cleaning_method = None
    if 'df_ready' not in st.session_state:
        st.session_state.df_ready = None
    
    # 결측치 현황 표시
    missing_counts = df_subset.isnull().sum()
    missing_percentages = (missing_counts / len(df_subset)) * 100
    
    # 결측치가 있는 변수들만 표시
    variables_with_missing = missing_counts[missing_counts > 0]
    if len(variables_with_missing) > 0:
        st.markdown('<h4 style="margin: 15px 0; color: #333;">🔍 결측치가 있는 변수들</h3>', unsafe_allow_html=True)
        
        # Y 변수를 가장 왼쪽으로 이동
        y_column = st.session_state.get("y_column")
        
        if y_column:
            # Y 변수를 첫 번째로, 나머지 X 변수들을 뒤에 배치
            column_order = [y_column] + [col for col in df_subset.columns if col != y_column]
            df_preview = df_subset[column_order].copy()
        else:
            df_preview = df_subset.copy()
        
        # 변수 역할 행과 결측 현황 행 추가
        role_row = []
        missing_count_row = []
        missing_pct_row = []
        
        for col in df_preview.columns:
            if col == y_column:
                role_row.append("Y")
            else:
                role_row.append("X")
            
            # 결측 현황 정보 생성
            missing_count = missing_counts[col]
            total_count = len(df_subset)
            missing_pct = missing_percentages[col]
            missing_count_row.append(f"{missing_count:,} / {total_count:,}개")
            missing_pct_row.append(f"{missing_pct:.1f}%")
        
        # 구분 컬럼 추가
        role_row = ["역할"] + role_row
        missing_count_row = ["결측 수"] + missing_count_row
        missing_pct_row = ["결측 비율"] + missing_pct_row
        
        # 데이터프레임 생성
        missing_detail_df = pd.DataFrame([role_row, missing_count_row, missing_pct_row], columns=[""] + list(df_preview.columns))
        
        # Y 변수 열에 대한 시각적 구분을 위해 컬럼명에 표시
        display_columns = {}
        for i, col in enumerate(df_preview.columns):
            if col == y_column:
                display_columns[col] = f"🎯 {col}"
            else:
                display_columns[col] = f"📊 {col}"
        
        # 컬럼명 변경
        missing_detail_df.columns = ["구분"] + [display_columns[col] for col in df_preview.columns]
        
        st.dataframe(missing_detail_df, width='stretch', hide_index=True)
        
        # 결측치 처리 방법 선택 (아직 처리하지 않은 경우에만 표시)
        if not st.session_state.cleaning_completed:
            st.markdown('<h4 style="margin: 15px 0; color: #333;">🛠️ 결측치 처리 방법 선택</h3>', unsafe_allow_html=True)
            
            col_method1, col_method2 = st.columns(2)
            
            with col_method1:
                st.markdown("**Option 1: 행 삭제**")
                st.markdown("결측치가 있는 행을 완전히 제거합니다.")
                if st.button("🗑️ 결측치가 있는 행 삭제", type="primary", width='stretch'):
                    df_cleaned = df_subset.dropna()
                    st.session_state.df_ready = df_cleaned
                    st.session_state.cleaning_method = "행 삭제"
                    st.session_state.cleaning_completed = True
                    st.rerun()
            
            with col_method2:
                st.markdown("**Option 2: 평균값으로 대체**")
                st.markdown("수치형 변수의 결측치를 해당 변수의 평균값으로 채웁니다.")
                if st.button("🔢 평균값으로 대체", type="primary", width='stretch'):
                    df_cleaned = df_subset.copy()
                    
                    # 수치형 변수만 선택
                    numeric_cols = df_cleaned.select_dtypes(include=[np.number]).columns
                    numeric_cols_with_missing = [col for col in numeric_cols if df_cleaned[col].isnull().sum() > 0]
                    
                    if numeric_cols_with_missing:
                        for col in numeric_cols_with_missing:
                            # 원본 데이터 타입 저장
                            original_dtype = df_cleaned[col].dtype
                            
                            # 평균값 계산 및 결측치 채우기
                            mean_val = df_cleaned[col].mean()
                            df_cleaned[col].fillna(mean_val, inplace=True)
                            
                            # 원본 데이터 타입 복원
                            if pd.api.types.is_integer_dtype(original_dtype):
                                # 정수형인 경우
                                if pd.api.types.is_nullable_integer_dtype(original_dtype):
                                    # pandas nullable integer dtype (Int64, Int32 등)인 경우
                                    # 이 dtype은 float 값을 자동으로 처리할 수 있음
                                    df_cleaned[col] = df_cleaned[col].astype(original_dtype)
                                else:
                                    # numpy integer dtype인 경우
                                    # 모든 값이 정수인지 확인
                                    if df_cleaned[col].apply(lambda x: x.is_integer() if hasattr(x, 'is_integer') else x == int(x)).all():
                                        # 반올림 후 원본 dtype으로 변환
                                        df_cleaned[col] = df_cleaned[col].round().astype(original_dtype)
                                    # 정수가 아닌 값이 있으면 float로 유지 (안전성)
                            # float dtype은 그대로 유지
                        
                        st.session_state.df_ready = df_cleaned
                        st.session_state.cleaning_method = "평균값 대체"
                        st.session_state.cleaning_completed = True
                        st.rerun()
                    else:
                        st.info("수치형 변수에 결측치가 없습니다.")
        
        # 결측치 처리 완료 후
        if st.session_state.cleaning_completed and st.session_state.df_ready is not None:
            df_cleaned = st.session_state.df_ready
            
            # main.py에서 자동으로 다음 단계로 진행할 수 있도록 세션 상태 업데이트
            st.session_state.cleaning_completed = True
            return df_cleaned
            
    else:
        st.success("🎉 결측치가 없습니다! 데이터가 깨끗하게 정리되어 있습니다.")
        st.session_state.df_ready = df_subset.copy()
        st.session_state.cleaning_method = "처리 불필요"
        st.session_state.cleaning_completed = True
        return df_subset 