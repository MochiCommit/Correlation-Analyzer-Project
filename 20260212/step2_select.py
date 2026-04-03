import streamlit as st

def variable_selection_ui(numeric_columns, categorical_columns, df):
    """변수 선택 UI를 표시합니다."""
       
    # Y값 선택 (수치형 변수만)
    if numeric_columns:
        # Y 변수 선택
        st.markdown('<h3 style="margin: 10px 0; color: #333;">🎯 종속변수 (Y)</h3>', unsafe_allow_html=True)
        st.markdown(
            '<p style="margin: 0px 0 6px 0; color: #333; font-size:15px;">'
            '예측하려는 변수를 선택하세요 (수치형 변수만 선택 가능)'
            '</p>', 
            unsafe_allow_html=True
        )
        col_y, col_empty = st.columns([1, 1])
        with col_y:
            y_column = st.selectbox(
                "",
                options=["변수 선택"] + numeric_columns,
                index=0,
                label_visibility="collapsed"
            )
        # X 변수 선택
        st.markdown('<h3 style="margin: 10px 0; color: #333;">💡 독립변수 (X)</h3>', unsafe_allow_html=True)
        st.markdown(
            '<p style="margin: 0px 0 6px 0; color: #333; font-size:15px;">'
            'Y에 영향을 줄 수 있는 변수들을 선택하세요. 이 변수들로 Y를 예측하기 위한 모델을 만들게 됩니다.'
            '</p>', 
            unsafe_allow_html=True
        )
        # X 변수 선택을 좌우로 분할
        col_left, col_right = st.columns(2)
        
        with col_left:
            numeric_x_columns = [col for col in numeric_columns if col != y_column]
            st.markdown('<p style="font-size: 13px; font-weight: normal; margin-bottom: 5px;">🔢 수치형 변수 선택 (여러 개 선택 가능)</p>', unsafe_allow_html=True)
            numeric_x_selected = st.multiselect(
                "", 
                numeric_x_columns,
                label_visibility="collapsed"
            )
        
        with col_right:
            
            if categorical_columns:
                st.markdown('<p style="font-size: 13px; font-weight: normal; margin-bottom: 5px;">📊 범주형 변수 선택 (여러 개 선택 가능)</p>', unsafe_allow_html=True)
                categorical_x_columns = st.multiselect(
                    "", 
                    categorical_columns,
                    label_visibility="collapsed"
                )
            else:
                categorical_x_columns = []
                st.info("범주형 변수가 없습니다")
        
        # 선택된 X 변수들을 하나의 리스트로 통합
        available_x_columns = (categorical_x_columns if categorical_x_columns else []) + (numeric_x_selected if numeric_x_selected else [])
        
        # 다음 단계로 진행 버튼 추가
        st.markdown("---")
        confirm_button = st.button("➡️ 다음 단계로 진행 (3단계: 결측치 처리)", type="primary", width='stretch')
        
        # 다음 단계로 진행 버튼을 눌렀을 때의 처리
        if confirm_button:
            if y_column == "변수 선택":
                st.error("⚠️ Y 변수를 선택해주세요.")
                return None, None, None, None, None
            
            if not available_x_columns:
                st.error("⚠️ 최소 하나의 X 변수를 선택해주세요.")
                return None, None, None, None, None
            
            # 선택된 열들로 데이터 사본 생성
            selected_columns = [y_column] + available_x_columns
            df_subset = df[selected_columns].copy()
            
            # df_preview 먼저 생성
            df_preview = df_subset.copy()
            df_preview.index = range(1, len(df_preview) + 1)  # 1부터 시작
            
            # main에서 자동으로 다음 단계로 진행할 수 있도록 세션 상태 업데이트
            return y_column, available_x_columns, numeric_x_selected, categorical_x_columns, df_subset
        
        return y_column, available_x_columns, numeric_x_selected, categorical_x_columns, None
    else:
        st.warning("⚠️ 데이터에 수치형 변수가 없습니다. 분석을 위해서는 최소 하나의 수치형 변수가 필요합니다.")
        return None, None, None, None, None 