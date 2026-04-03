import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import matplotlib.pyplot as plt
import io
import pandas as pd
import cProfile
import pstats
import os

# 커스텀 모듈 import with error handling
try:
    from step1_load import load_data, analyze_column_types, display_data_info, display_data_preview, get_emoji_for_type
    from step2_select import variable_selection_ui
    from step3_clean import data_cleaner
    from step4_eda import perform_eda_analysis
    from step5_1_linear_regression import perform_linear_regression
    from step5_2_machine_learning import perform_ml_analysis_and_simulator
    from step5_3_variable_feedback import perform_variable_check

except Exception as e:
    import sys, traceback
    tb = traceback.format_exc()
    st.error(f"모듈 가져오기 실패:\n{tb}")
    sys.exit(1)

# step 완료 시점에 시그니처 저장
def _df_signature(df: pd.DataFrame, cols=None) -> str:
    if cols:
        df = df[cols]
    return str(pd.util.hash_pandas_object(df, index=True).sum())


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

# matplotlib 백엔드 설정 (Streamlit 호환성)
plt.switch_backend('Agg')

# ==============================
# 페이지 설정 & 헤더
# ==============================
# 현재 파일이 있는 폴더 이름 가져오기
folder_name = os.path.basename(os.path.dirname(os.path.abspath(__file__)))
st.set_page_config(page_title=f"Analyzer Hub ({folder_name})", layout="wide")

st.markdown("""
<div class="header-container">
    <h1 style="margin: 0; padding: 0; text-align: left; color: #2C3E50; font-size: 42px; font-weight: bold;">
        공정 데이터 상관관계 분석 도우미
    </h1>
</div>
""", unsafe_allow_html=True)

# ==============================
# 공용: 패널 렌더 도우미
# ==============================
def panel(title: str, section_id: str = None, small_title: bool = False, collapsible: bool = False):
    """
    얕은 '계층 들여쓰기'를 표현하기 위해 좌우 마진이 있는 container를 반환합니다.
    하위 단계(panel 안에서 다시 panel())를 만들면 자연스럽게 들여쓰기 효과가 생깁니다.
    
    Parameters:
    - collapsible: True일 때 Expander 형태로 동작하여 제목을 클릭하여 펼칠 수 있습니다.
    """
    if collapsible:
        # 접혀있는 expander 사용
        exp = st.expander(title, expanded=False)
        with exp:
            if section_id:
                st.markdown(f"<div id='{section_id}'></div>", unsafe_allow_html=True)
            # 스타일이 적용된 제목을 expander 내부에 렌더링
            if small_title:
                st.markdown(f"<h3 style='margin:0 0 6px 0;color:#333;'>{title}</h3>", unsafe_allow_html=True)
            else:
                st.markdown(f"<h2 style='margin:0 0 6px 0;color:#333;'>{title}</h2>", unsafe_allow_html=True)
        return exp
    else:
        # 기존 panel 형태
        c = st.container(border=True)
        with c:
            if section_id:
                st.markdown(f"<div id='{section_id}'></div>", unsafe_allow_html=True)
            if small_title:
                st.markdown(f"<h3 style='margin:0 0 6px 0;color:#333;'>{title}</h3>", unsafe_allow_html=True)
            else:
                st.markdown(f"<h2 style='margin:0 0 6px 0;color:#333;'>{title}</h2>", unsafe_allow_html=True)
        return c


# ==============================
# 기존 내용을 보존하기 위한 렌더링 함수
# ==============================
@st.cache_data(show_spinner=False)
def render_upload_section(show_full: bool = True): #Step1_load.py 참고
    with panel("1단계: 파일 업로드 (완료)", "section-upload", collapsible=not show_full):
        st.success("✅ 파일이 성공적으로 업로드되었습니다.")
        if show_full and "df" in st.session_state:
            display_data_info(st.session_state.df,
                              st.session_state.get("numeric_columns", []),
                              st.session_state.get("categorical_columns", []),
                              st.session_state.get("date_columns", []),
                              st.session_state.get("datelike_columns", []),
                              st.session_state.get("filename", "알 수 없음"))
            st.subheader("데이터 미리보기")
            display_data_preview(st.session_state.df)

@st.cache_data(show_spinner=False)
def render_select_section(show_full: bool = True): #Step2_select.py 참고
    """변수군 선택 섹션을 요약/상세 형태로 다시 렌더링."""
    with panel("2단계: 변수군 선택 (완료)", "section-select", collapsible=not show_full):
        if "y_column" in st.session_state and st.session_state.y_column:
            st.success(f"✅ Y 변수: {st.session_state.y_column}")
        if "x_columns" in st.session_state and st.session_state.x_columns:
            x_count = len(st.session_state.x_columns)
            st.success(f"✅ X 변수({x_count}개): {',  '.join(st.session_state.x_columns)}")

        if show_full and "df_subset" in st.session_state and st.session_state.df_subset is not None:
            df_subset = st.session_state.df_subset
            
            st.markdown(f'<h4 style="margin:10px 0;color:#333;">👀 선택된 변수들의 데이터 미리보기</h4>', unsafe_allow_html=True)
            st.markdown(f'<p style="margin: 0px 0 6px 0; color: #333; font-size:18px;">데이터 크기: <strong>{df_subset.shape[1]}열</strong> <span style="font-size:15px;">(X변수 {df_subset.shape[1]-1}개 + Y변수 1개)</span> × <strong>{df_subset.shape[0]:,}행</strong></p>', unsafe_allow_html=True)


            # Y 변수를 가장 왼쪽으로 이동
            y_column = st.session_state.get("y_column")
            
            if y_column:
                # Y 변수를 첫 번째로, 나머지 X 변수들을 뒤에 배치
                column_order = [y_column] + [col for col in df_subset.columns if col != y_column]
                df_preview = df_subset[column_order].copy()
            else:
                df_preview = df_subset.copy()
                           
            # 컬럼 타입 분석
            column_analysis, _, _, date_columns, datelike_columns, _ = analyze_column_types(df_preview)
            
            # 변수 역할 행 추가
            role_row = []
            for col in df_preview.columns:
                if col == y_column:
                    role_row.append("Y")
                else:
                    role_row.append("X")
            
            # 변수 타입 행 추가
            type_row = []
            for col in df_preview.columns:
                sub_category = column_analysis[col]['sub_category']
                type_row.append(f"{get_emoji_for_type(sub_category)} {sub_category}")
            
            # 역할과 타입 행을 데이터프레임에 추가
            role_df = pd.DataFrame([role_row], columns=df_preview.columns, index=["역할"])
            type_df = pd.DataFrame([type_row], columns=df_preview.columns, index=["Type"])
            df_preview = pd.concat([role_df, type_df, df_preview])
            
            # 인덱스 재설정 (역할 행은 0, 타입 행은 1, 데이터는 2부터)
            df_preview.index = ["역할", "Type"] + list(range(1, len(df_preview) - 1))
            
            # Y 변수 열에 대한 시각적 구분을 위해 컬럼명에 표시
            display_columns = {}
            for i, col in enumerate(df_preview.columns):
                if col == y_column:
                    display_columns[col] = f"🎯 {col} "
                else:
                    display_columns[col] = f"📊 {col} "
            
            df_preview_display = df_preview.copy()
            df_preview_display.columns = [display_columns[col] for col in df_preview.columns]
            
            st.dataframe(df_preview_display, width='stretch', height=450, hide_index=False)

def render_clean_section(show_full: bool = True): #Step3_clean.py 참고
    """결측치 처리 섹션을 요약/상세 형태로 다시 렌더링."""
    with panel("3단계: 결측치 처리 (완료)", "section-clean", collapsible=not show_full):
        if "cleaning_method" in st.session_state and st.session_state.cleaning_method:
            st.success(f"✅ 처리 방법: {st.session_state.cleaning_method}")
        if "df_ready" in st.session_state and st.session_state.df_ready is not None:
            st.success("✅ 처리가 완료되었습니다.")
            if show_full:
                st.markdown('<h4 style="margin:10px 0;color:#333;">👀 정리된 데이터 미리보기</h4>', unsafe_allow_html=True)
                
                # 결측치 처리 방법에 따라 다른 메시지 표시
                if st.session_state.cleaning_method == "행 삭제":
                    st.markdown(f'<p style="margin: 0px 0 6px 0; color: #333; font-size:18px;">데이터 크기: <strong>{st.session_state.df_ready.shape[1]}열</strong> <span style="font-size:15px;">(X변수 {st.session_state.df_ready.shape[1]-1}개 + Y변수 1개)</span> × <strong>{st.session_state.df_ready.shape[0]:,}행&nbsp;&nbsp;</strong> <span style="font-size:15px; color: #333;">(🧹 전체 데이터의 <strong>{((st.session_state.df_subset.shape[0] - st.session_state.df_ready.shape[0]) / st.session_state.df_subset.shape[0] * 100):.1f}% ({st.session_state.df_subset.shape[0] - st.session_state.df_ready.shape[0]:,}개 행)</strong> 이 제거됨.)</span></p>', unsafe_allow_html=True)
                elif st.session_state.cleaning_method == "평균값 대체":
                    st.markdown(f'<p style="margin: 0px 0 6px 0; color: #333; font-size:18px;">데이터 크기: <strong>{st.session_state.df_ready.shape[1]}열</strong> <span style="font-size:15px;">(X변수 {st.session_state.df_ready.shape[1]-1}개 + Y변수 1개)</span> × <strong>{st.session_state.df_ready.shape[0]:,}행&nbsp;&nbsp;</strong> <span style="font-size:15px; color: #333;">(✅ 수치형 변수에 있던 결측치들이 <strong>평균값</strong>으로 채워짐.)</span></p>', unsafe_allow_html=True)
                else:
                    st.markdown(f'<p style="margin: 0px 0 6px 0; color: #333; font-size:18px;">데이터 크기: <strong>{st.session_state.df_ready.shape[1]}열</strong> <span style="font-size:15px;">(X변수 {st.session_state.df_ready.shape[1]-1}개 + Y변수 1개)</span> × <strong>{st.session_state.df_ready.shape[0]:,}행  </strong></p>', unsafe_allow_html=True)
                
                # Y 변수를 가장 왼쪽으로 이동
                y_column = st.session_state.get("y_column")
                
                if y_column and y_column in st.session_state.df_ready.columns:
                    # Y 변수를 첫 번째로, 나머지 X 변수들을 뒤에 배치
                    column_order = [y_column] + [col for col in st.session_state.df_ready.columns if col != y_column]
                    df_preview = st.session_state.df_ready[column_order].copy()
                else:
                    df_preview = st.session_state.df_ready.copy()
                
                # 컬럼 타입 분석
                column_analysis, _, _, date_columns, datelike_columns, _ = analyze_column_types(df_preview)
                
                # 변수 역할 행 추가
                role_row = []
                for col in df_preview.columns:
                    if col == y_column:
                        role_row.append("Y")
                    else:
                        role_row.append("X")
                
                # 변수 타입 행 추가
                type_row = []
                for col in df_preview.columns:
                    sub_category = column_analysis[col]['sub_category']
                    type_row.append(f"{get_emoji_for_type(sub_category)} {sub_category}")
                
                # 역할과 타입 행을 데이터프레임에 추가
                role_df = pd.DataFrame([role_row], columns=df_preview.columns, index=["역할"])
                type_df = pd.DataFrame([type_row], columns=df_preview.columns, index=["Type"])
                df_preview = pd.concat([role_df, type_df, df_preview])
                
                # 인덱스 재설정 (역할 행은 0, 타입 행은 1, 데이터는 2부터)
                df_preview.index = ["역할", "Type"] + list(range(1, len(df_preview) - 1))
                
                # Y 변수 열에 대한 시각적 구분을 위해 컬럼명에 표시
                display_columns = {}
                for i, col in enumerate(df_preview.columns):
                    if col == y_column:
                        display_columns[col] = f"🎯 {col}"
                    else:
                        display_columns[col] = f"📊 {col}"
                
                df_preview_display = df_preview.copy()
                df_preview_display.columns = [display_columns[col] for col in df_preview.columns]
                
                st.dataframe(df_preview_display, width='stretch', height=450, hide_index=False)
                
                # 3분할 컬럼으로 버튼을 1/3 크기로 배치
                col1, col2, col3 = st.columns([2, 2, 3])
                
                with col3:
                    with st.container(border=True):
                        # CSV 다운로드 섹션 추가
                        st.markdown('<h4 style="margin:10px 0;color:#333;">💾 최종 파일 다운로드</h4>', unsafe_allow_html=True)
                        st.markdown('<p style="margin: 0px 0 10px 0; color: #666; font-size:14px;">다음에도 똑같은 분석을 수행하고 싶다면 정리된 파일을 다운로드 받아 사용하세요.</p>', unsafe_allow_html=True)
                    
                        # CSV 파일 생성
                        csv_buffer = io.StringIO()
                        st.session_state.df_ready.to_csv(csv_buffer, index=False, encoding='utf-8-sig')
                        csv_data = csv_buffer.getvalue()
                        
                        # 파일명 생성 (원본 파일명 + _cleaned)
                        original_filename = st.session_state.get("filename", "data")
                        if original_filename.endswith(('.csv', '.xlsx')):
                            base_name = original_filename.rsplit('.', 1)[0]
                            download_filename = f"{base_name}_cleaned.csv"
                        else:
                            download_filename = f"{original_filename}_cleaned.csv"
                        
                        # 다운로드 버튼
                        st.markdown('<div class="download-button">', unsafe_allow_html=True)
                        st.download_button(
                            label="📥 정리된 파일 다운로드",
                            data=csv_data,
                            file_name=download_filename,
                            mime="text/csv",
                            type="secondary",
                            width='stretch',
                            help="정리된 데이터를 CSV 파일로 다운로드합니다."
                        )
                        st.markdown('</div>', unsafe_allow_html=True)

@st.cache_data(show_spinner=False)
def render_eda_section(show_full: bool = True): #Step4_eda.py 참고
    """EDA 섹션을 요약/상세 형태로 다시 렌더링."""
    with panel("4단계: 데이터 탐색 (완료)", "section-eda", collapsible=not show_full):
        st.success("✅ 데이터 탐색이 완료되었습니다.")
        if "df_ready" in st.session_state and st.session_state.df_ready is not None:
            perform_eda_analysis(st.session_state.df_ready,
                                 st.session_state.get("y_column"),
                                 st.session_state.get("x_columns", []))

# ==============================
# 새로운 파일 업로드 시 세션 초기화
# ==============================

def reset_session_state():
    """새로운 파일 업로드 시 모든 세션 상태를 초기화합니다."""
    # 모든 세션 상태 키들을 초기화
    keys_to_reset = [
        'current_step', 'variables_confirmed', 'selected_vars', 'df_subset', 
        'df_ready', 'y_column', 'x_columns', 'numeric_x_selected', 'eda_completed',
        'df', 'numeric_columns', 'categorical_columns', 'date_columns', 
        'datelike_columns', 'filename', 'cleaning_method', 'cleaning_completed',
        'analysis_stage', 'scroll_to', 'category_filter_counter', 'current_filtered_df_key'
    ]
    
    # 과거의 필터링된 데이터셋들도 초기화
    for key in list(st.session_state.keys()):
        if key.startswith('df_ready_categoryfilter'):
            keys_to_reset.append(key)
    
    for key in keys_to_reset:
        if key in st.session_state:
            del st.session_state[key]
    
    # st.cache로 캐시된 모든 데이터 초기화
    st.cache_data.clear()
    st.cache_resource.clear()
    
    # 기본값으로 초기화
    st.session_state.current_step = "upload"
    st.session_state.category_filter_counter = 0


def reset_after_variable_selection():
    """변수군 선택이 다시 선택될 때 이후 단계(결측치 처리, 데이터 탐색, 데이터 분석)의 세션 상태를 초기화합니다."""
    # 이후 단계에서 사용되는 세션 상태 키들을 초기화
    keys_to_reset = [
        'df_subset', 'df_ready', 'df_ready_sig',
        'cleaning_method', 'cleaning_completed',
        'eda_completed',
        'analysis_stage', 'baseline_r2',
        'category_filter_counter', 'current_filtered_df_key'
    ]
    
    # 과거의 필터링된 데이터셋들도 초기화
    for key in list(st.session_state.keys()):
        if key.startswith('df_ready_categoryfilter'):
            keys_to_reset.append(key)
    
    for key in keys_to_reset:
        if key in st.session_state:
            del st.session_state[key]
    
    # st.cache로 캐시된 모든 데이터 초기화
    st.cache_data.clear()
    st.cache_resource.clear()
    
    # 기본값으로 초기화
    st.session_state.category_filter_counter = 0


def reset_to_select_step():
    """2단계(변수군 선택)로 완전히 돌아갈 때, 이후 단계 및 관련 상태/캐시를 초기화합니다."""
    keys_to_reset = [
        # 2단계 자체 및 이후 단계에서 사용하는 상태
        'variables_confirmed', 'selected_vars',
        'df_subset', 'df_ready', 'df_ready_sig',
        'y_column', 'x_columns', 'numeric_x_selected',
        'cleaning_method', 'cleaning_completed',
        'eda_completed',
        'analysis_stage', 'baseline_r2',
        'scroll_to', 'category_filter_counter', 'current_filtered_df_key'
    ]
    
    # 과거의 필터링된 데이터셋들도 초기화
    for key in list(st.session_state.keys()):
        if key.startswith('df_ready_categoryfilter'):
            keys_to_reset.append(key)

    for key in keys_to_reset:
        if key in st.session_state:
            del st.session_state[key]

    # 캐시 초기화
    st.cache_data.clear()
    st.cache_resource.clear()

    # 2단계로 상태 이동
    st.session_state.current_step = "select"
    st.session_state.category_filter_counter = 0


# 5단계 상태머신
if 'current_step' not in st.session_state:
    st.session_state.current_step = "upload"  # upload -> select -> clean -> eda -> analyze

# 보관용 상태
for key, default in [
    ('variables_confirmed', False),
    ('selected_vars', {}),
    ('df_subset', None),
    ('df_ready', None),
    ('y_column', None),
    ('x_columns', None),
    ('numeric_x_selected', None),
    ('eda_completed', False),
    ('category_filter_counter', 0),  # 필터 적용 카운터
]:
    if key not in st.session_state:
        st.session_state[key] = default


# ==============================
# CSS 스타일 정의
# ==============================
st.markdown("""
<style>
    /* 전체 페이지 스타일 */
    .main .block-container {
        padding-top: 1rem;
        padding-bottom: 1rem;
    }
    
    /* 헤더 스타일 */
    .header-container {
        background: linear-gradient(135deg, #E8F4FD 0%, #F0F8FF 100%);
        padding: 1.5rem 2rem;
        margin: -1rem -2rem 2rem -2rem;
        border-bottom: 2px solid #D1E7DD;
    }
    
    /* 좌측 네비게이션 패널 스타일 */
    .sidebar .sidebar-content {
        background: linear-gradient(180deg, #F8F9FA 0%, #E9ECEF 100%);
        border-right: 2px solid #DEE2E6;
    }
    
    .nav-panel {
        background: linear-gradient(135deg, #F0F8FF 0%, #E6F3FF 100%);
        border: 1px solid #B8D4FE;
        border-radius: 12px;
        padding: 1.5rem;
        margin: 1rem 0;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    }
    
    .nav-step {
        padding: 0.75rem 1rem;
        margin: 0.5rem 0;
        border-radius: 8px;
        border-left: 4px solid transparent;
        transition: all 0.3s ease;
    }
    
    .nav-step.active {
        background: linear-gradient(135deg, #D4EDDA 0%, #C3E6CB 100%);
        border-left-color: #28A745;
        box-shadow: 0 2px 4px rgba(40, 167, 69, 0.2);
    }
    
    .nav-step.completed {
        background: linear-gradient(135deg, #D1ECF1 0%, #BEE5EB 100%);
        border-left-color: #17A2B8;
    }
    
    .nav-step.pending {
        background: linear-gradient(135deg, #F8F9FA 0%, #E9ECEF 100%);
        border-left-color: #6C757D;
    }
    
    .nav-substep {
        padding: 0.5rem 1rem;
        margin: 0.25rem 0 0.25rem 1.5rem;
        border-radius: 6px;
        border-left: 3px solid transparent;
        transition: all 0.3s ease;
        font-size: 0.9em;
    }
    
    .nav-substep.active {
        background: linear-gradient(135deg, #D4EDDA 0%, #C3E6CB 100%);
        border-left-color: #28A745;
        box-shadow: 0 2px 4px rgba(40, 167, 69, 0.2);
    }
    
    .nav-substep.completed {
        background: white;
    }
    
    .nav-substep.pending {
        background: linear-gradient(135deg, #F8F9FA 0%, #E9ECEF 100%);
        border-left-color: transparent;
        opacity: 0.6;
    }
    
    /* 네비게이션 버튼 스타일 */
    .stButton > button {
        background: linear-gradient(135deg, #E8F5E8 0%, #D4EDDA 100%);
        border: 2px solid #28A745;
        border-radius: 8px;
        color: #155724;
        font-weight: 600;
        padding: 0.75rem 1rem;
        margin: 0.5rem 0;
        transition: all 0.3s ease;
        box-shadow: 0 2px 4px rgba(40, 167, 69, 0.2);
    }
    
    .stButton > button:hover {
        background: linear-gradient(135deg, #D4EDDA 0%, #C3E6CB 100%);
        border-color: #1E7E34;
        box-shadow: 0 4px 8px rgba(40, 167, 69, 0.3);
        transform: translateY(-1px);
    }
    
    .stButton > button:active {
        transform: translateY(0);
        box-shadow: 0 2px 4px rgba(40, 167, 69, 0.2);
    }
    
    /* 비활성화된 버튼 스타일 */
    .stButton > button:disabled {
        background: linear-gradient(135deg, #F8F9FA 0%, #E9ECEF 100%);
        border-color: #6C757D;
        color: #6C757D;
        cursor: not-allowed;
        box-shadow: none;
    }
    
    .stButton > button:disabled:hover {
        transform: none;
        box-shadow: none;
    }
    
    /* 메인 컨텐츠 영역 스타일 */
    .main-content {
        background: white;
        padding: 2rem;
        border-radius: 12px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        margin-left: 1rem;
    }
    
    /* 패널 스타일 */
    .content-panel {
        background: white;
        border: 1px solid #E9ECEF;
        border-radius: 8px;
        padding: 1.5rem;
        margin: 1rem 0;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    
    /* 스크롤바 스타일링 */
    ::-webkit-scrollbar {
        width: 8px;
    }
    
    ::-webkit-scrollbar-track {
        background: #f1f1f1;
        border-radius: 4px;
    }
    
    ::-webkit-scrollbar-thumb {
        background: #c1c1c1;
        border-radius: 4px;
    }
    
    ::-webkit-scrollbar-thumb:hover {
        background: #a8a8a8;
    }
    
    /* 스크롤 상단 버튼 */
    .scroll-top-btn {
        position: fixed;
        bottom: 20px;
        right: 20px;
        background: linear-gradient(135deg, #28A745 0%, #20C997 100%);
        color: white;
        border: none;
        border-radius: 50%;
        width: 50px;
        height: 50px;
        font-size: 20px;
        cursor: pointer;
        box-shadow: 0 4px 12px rgba(40, 167, 69, 0.3);
        transition: all 0.3s ease;
        z-index: 1000;
        display: none;
    }
    
    .scroll-top-btn:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 16px rgba(40, 167, 69, 0.4);
    }
    
    .scroll-top-btn.show {
        display: block;
    }

    /* 다운로드 버튼 전용 스타일 */
    .download-button > button {
        background: linear-gradient(135deg, #E3F2FD 0%, #BBDEFB 100%) !important;
        border: 2px solid #2196F3 !important;
        border-radius: 8px !important;
        color: #0D47A1 !important;
        font-weight: 600 !important;
        padding: 0.75rem 1rem !important;
        margin: 0.5rem 0 !important;
        transition: all 0.3s ease !important;
        box-shadow: 0 2px 4px rgba(33, 150, 243, 0.2) !important;
    }
    
    .download-button > button:hover {
        background: linear-gradient(135deg, #BBDEFB 0%, #90CAF9 100%) !important;
        border-color: #1976D2 !important;
        box-shadow: 0 4px 8px rgba(33, 150, 243, 0.3) !important;
        transform: translateY(-1px) !important;
    }
    
    .download-button > button:active {
        transform: translateY(0) !important;
        box-shadow: 0 2px 4px rgba(33, 150, 243, 0.2) !important;
    }
</style>

<script>
    // 부드러운 스크롤 함수
    function smoothScrollTo(elementId) {
        const element = document.getElementById(elementId);
        if (element) {
            element.scrollIntoView({
                behavior: 'smooth',
                block: 'start'
            });
        }
    }

    // 스크롤 상단 버튼 표시/숨김
    window.addEventListener('scroll', function() {
        const scrollBtn = document.querySelector('.scroll-top-btn');
        if (window.pageYOffset > 300) {
            scrollBtn.classList.add('show');
        } else {
            scrollBtn.classList.remove('show');
        }
    });

    // 스크롤 상단으로 이동
    function scrollToTop() {
        window.scrollTo({
            top: 0,
            behavior: 'smooth'
        });
    }

    // 페이지 로드 시 실행
    document.addEventListener('DOMContentLoaded', function() {
        // 스크롤 상단 버튼 추가
        const scrollBtn = document.createElement('button');
        scrollBtn.className = 'scroll-top-btn';
        scrollBtn.innerHTML = '↑';
        scrollBtn.onclick = scrollToTop;
        scrollBtn.title = '맨 위로 이동';
        document.body.appendChild(scrollBtn);
    });
</script>
""", unsafe_allow_html=True)


# ==============================
# 네비게이션 패널
# ==============================
with st.sidebar:
    st.markdown("### 📋 분석 단계")
    
    # 1단계: 파일 업로드
    if st.session_state.current_step in ["select", "clean", "eda", "analyze"]:
        if st.button("✅ 1단계: 파일 업로드", key="nav_upload", width='stretch', 
                    help="파일 업로드로 이동"):
            st.session_state.scroll_to = "section-upload"
            st.rerun()
    else:
        st.markdown("""
        <div class="nav-step active">
            <div style="display: flex; align-items: center; justify-content: center;">
                <span style="color: #28A745; font-size: 1.2em;">📁</span>
                <span style="margin-left: 0.5rem; font-weight: 600; color: #2C3E50;">1단계: 파일 업로드</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    # 2단계: 변수군 선택
    if st.session_state.current_step in ["clean", "eda", "analyze"]:
        if st.button("✅ 2단계: 변수군 선택", key="nav_select", width='stretch',
                    help="변수군 선택으로 이동"):
            st.session_state.scroll_to = "section-select"
            st.rerun()
    elif st.session_state.current_step == "select":
        st.markdown("""
        <div class="nav-step active">
            <div style="display: flex; align-items: center; justify-content: center;">
                <span style="color: #FF6B6B; font-size: 1.2em;">✏️</span>
                <span style="margin-left: 0.5rem; font-weight: 600; color: #2C3E50;">2단계: 변수군 선택</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        if st.button("🔲 2단계: 변수군 선택", key="nav_select_pending", width='stretch',
                    help="변수군 선택으로 이동", disabled=True):
            pass
    
    # 3단계: 결측치 처리
    if st.session_state.current_step in ["eda", "analyze"]:
        if st.button("✅ 3단계: 결측치 처리", key="nav_clean", width='stretch',
                    help="결측치 처리로 이동"):
            st.session_state.scroll_to = "section-clean"
            st.rerun()
    elif st.session_state.current_step == "clean":
        st.markdown("""
        <div class="nav-step active">
            <div style="display: flex; align-items: center; justify-content: center;">
                <span style="color: #FF6B6B; font-size: 1.2em;">🧹</span>
                <span style="margin-left: 0.5rem; font-weight: 600; color: #2C3E50;">3단계: 결측치 처리</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        if st.button("🔲 3단계: 결측치 처리", key="nav_clean_pending", width='stretch',
                    help="결측치 처리로 이동", disabled=True):
            pass
    
    # 4단계: 데이터 탐색
    if st.session_state.current_step == "analyze":
        if st.button("✅ 4단계: 데이터 탐색", key="nav_eda", width='stretch',
                    help="데이터 탐색으로 이동"):
            st.session_state.scroll_to = "section-eda"
            st.rerun()
    elif st.session_state.current_step == "eda":
        st.markdown("""
        <div class="nav-step active">
            <div style="display: flex; align-items: center; justify-content: center;">
                <span style="color: #FF6B6B; font-size: 1.2em;">📊</span>
                <span style="margin-left: 0.5rem; font-weight: 600; color: #2C3E50;">4단계: 데이터 탐색</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
    else:
        if st.button("🔲 4단계: 데이터 탐색", key="nav_eda_pending", width='stretch',
                    help="데이터 탐색으로 이동", disabled=True):
            pass
    
    # 5단계: 데이터 분석
    if st.session_state.current_step == "analyze":
        # 5단계 메인 컨테이너
        with st.container(border=True):
            st.markdown("""
            <div style="display: flex; align-items: center; justify-content: center; margin-bottom: 15px;">
                <span style="color: #FF6B6B; font-size: 1.2em;">🔍</span>
                <span style="margin-left: 0.5rem; font-weight: 600; color: #2C3E50; font-size: 1.1em;">5단계: 데이터 분석</span>
            </div>
            """, unsafe_allow_html=True)
            
            # 하위 단계 표시
            analysis_stage = st.session_state.get("analysis_stage", 1)
            
            # 1. 선형 관계 탐색
            if analysis_stage >= 1:
                if analysis_stage == 1:
                    st.markdown("""
                    <div class="nav-step active">
                        <div style="display: flex; align-items: center; justify-content: center;">
                            <span style="margin-left: 0.5rem; font-weight: 600; color: #2C3E50; font-size: 1.1em;">① 선형 관계 탐색</span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    if st.button("✅ ① 선형 관계 탐색", key="nav_stage1_completed", width='stretch',
                                help="선형 관계 탐색으로 이동"):
                        st.session_state.scroll_to = "section-linear-regression"
                        st.rerun()
            else:
                if st.button("🔲 ① 선형 관계 탐색", key="nav_stage1_pending", width='stretch',
                            help="선형 관계 탐색으로 이동", disabled=True):
                    pass
            
            # 2. 머신 러닝
            if analysis_stage >= 2:
                if analysis_stage == 2:
                    st.markdown("""
                    <div class="nav-step active">
                        <div style="display: flex; align-items: center; justify-content: center;">
                            <span style="margin-left: 0.5rem; font-weight: 600; color: #2C3E50; font-size: 1.1em;">② 머신 러닝 모델</span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    if st.button("✅ ② 머신 러닝 모델", key="nav_stage2_completed", width='stretch',
                                help="머신 러닝 모델로 이동"):
                        st.session_state.scroll_to = "section-machine-learning"
                        st.rerun()
            else:
                if st.button("② 머신 러닝 모델", key="nav_stage2_pending", width='stretch',
                            help="머신 러닝 모델로 이동", disabled=True):
                    pass
            
            # 3. 변수 적정성 점검
            if analysis_stage >= 3:
                if analysis_stage == 3:
                    st.markdown("""
                    <div class="nav-step active">
                        <div style="display: flex; align-items: center; justify-content: center;">
                            <span style="margin-left: 0.5rem; font-weight: 600; color: #2C3E50; font-size: 1.1em;">③ 변수 적정성 점검</span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    if st.button("✅ ③ 변수 적정성 점검", key="nav_stage3_completed", width='stretch',
                                help="변수 적정성 점검으로 이동"):
                        st.session_state.scroll_to = "section-variable-check"
                        st.rerun()
            else:
                if st.button("③ 변수 적정성 점검", key="nav_stage3_pending", width='stretch',
                            help="변수 적정성 점검으로 이동", disabled=True):
                    pass
    else:
        # analyze 상태가 아닐 때 - 5단계 비활성화 상태
        with st.container(border=True):
            st.markdown("""
            <div style="display: flex; align-items: center; justify-content: center; margin-bottom: 1rem; opacity: 0.6;">
                <span style="margin-left: 0.5rem; color: #6C757D;">🔲 5단계: 데이터 분석</span>
            </div>
            """, unsafe_allow_html=True)
            
            st.button("① 선형 관계 탐색", key="nav_stage1_pending_analyze", width='stretch',
                    help="선형 관계 탐색으로 이동", disabled=True)
            
            st.button("② 머신 러닝 모델", key="nav_stage2_pending_analyze", width='stretch',
                    help="머신 러닝 모델로 이동", disabled=True)
            
            st.button("③ 변수 적정성 점검", key="nav_stage3_pending_analyze", width='stretch',
                    help="변수 적정성 점검으로 이동", disabled=True)
    
    st.markdown("</div>", unsafe_allow_html=True)
    
    # 추가 네비게이션 도구
    st.markdown("---")
    st.markdown("### 🔁 단계 되돌리기")
    
    # 1단계: 파일 업로드로 완전 초기화
    if st.button("📁 1단계: 파일 업로드", key="reset_to_step1", width='stretch',
                help="모든 분석 내용을 초기화하고 1단계(파일 업로드)로 돌아갑니다."):
        # 전체 세션 및 캐시 초기화
        reset_session_state()
        # 업로드 섹션으로 스크롤 이동
        st.session_state.scroll_to = "section-upload"
        st.rerun()

    # 2단계: 변수군 선택으로 복귀
    # 👉 1단계 파일 업로드가 완료되지 않은 경우 비활성화
    upload_ready = (
        'df' in st.session_state and st.session_state.df is not None and
        'numeric_columns' in st.session_state and st.session_state.numeric_columns is not None
    )

    if upload_ready:
        if st.button("✏️ 2단계: 변수군 선택", key="reset_to_step2", width='stretch',
                    help="2단계(변수군 선택) 이후의 분석 내용과 캐시를 초기화하고 해당 단계로 돌아갑니다."):
            reset_to_select_step()
            st.session_state.scroll_to = "section-select"
            st.rerun()
    else:
        st.button("✏️ 2단계: 변수군 선택", key="reset_to_step2_disabled", width='stretch',
                  help="1단계(파일 업로드)가 완료된 후에 사용할 수 있습니다.", disabled=True)

# ==============================
# 메인 컨텐츠 영역
# ==============================
main_container = st.container()

# 스크롤 위치 자동 이동
if 'scroll_to' in st.session_state and st.session_state.scroll_to:
    scroll_target = st.session_state.scroll_to
    del st.session_state.scroll_to
    
    # Streamlit 컴포넌트를 이용해 JS 실행 (window.parent.document 기준)
    components.html(
        f"""
        <script>
        (function() {{
            function scrollToTargetWithOffset() {{
                try {{
                    const w = window.parent || window;      // ✅ 부모 window
                    const doc = w.document || document;     // ✅ 부모 document
                    const el = doc.getElementById('{scroll_target}');
                    if (!el) return;

                    const offset = 100; // 🔧 여기 숫자만 조절 (px). 100~180 추천

                    // 1) 먼저 target으로 이동
                    el.scrollIntoView({{ behavior: 'smooth', block: 'start' }});

                    // 2) 이동 후 약간 위로 보정 (부모 window 기준!)
                    w.setTimeout(() => {{
                        w.scrollBy({{ top: -offset, left: 0, behavior: 'smooth' }});
                    }}, 250);
                }} catch (e) {{
                    console.error('scroll error', e);
                }}
            }}

            // DOM 렌더 이후 실행
            setTimeout(scrollToTargetWithOffset, 200);
        }})();
        </script>
        """,
        height=0,
        width=0,
    )

with main_container:
    # 1) 업로드
    if st.session_state.current_step == "upload":
        with panel("1단계: 파일 업로드", "section-upload"):
            uploaded_file = st.file_uploader("CSV 또는 Excel 파일을 업로드하세요", type=["csv", "xlsx"])
            if uploaded_file is not None:
                # 새로운 파일이 업로드되면 세션 상태 초기화
                reset_session_state()
                
                df = load_data(uploaded_file)
                if df is not None:
                    # 컬럼 전처리
                    df.columns = df.columns.str.strip()
                    column_analysis, numeric_columns, categorical_columns, date_columns, datelike_columns, empty_columns = analyze_column_types(df)

                    # 세션 저장
                    st.session_state.df = df
                    st.session_state.numeric_columns = numeric_columns
                    st.session_state.categorical_columns = categorical_columns
                    st.session_state.date_columns = date_columns
                    st.session_state.datelike_columns = datelike_columns
                    st.session_state.empty_columns = empty_columns
                    st.session_state.filename = uploaded_file.name

                    # 열 이름에서 (varY)와 (varX) 검사
                    y_candidates = [col for col in df.columns if '(varY)' in col]
                    x_candidates = [col for col in df.columns if '(varX)' in col]

                    if y_candidates:
                        if len(y_candidates) > 1:
                            st.error("⚠️ (varY)는 하나만 지정 가능합니다.")
                        elif y_candidates[0] not in numeric_columns:
                            st.error("⚠️ Y 변수는 수치형이어야 합니다.")
                        else:
                            y_column_raw = y_candidates[0]
                            x_columns_raw = x_candidates
                            
                            # 깨끗한 이름 생성
                            y_column_clean = y_column_raw.replace('(varY)', '').strip()
                            x_columns_clean = [col.replace('(varX)', '').strip() for col in x_candidates]
                            
                            # df_subset 생성 (원본 열 이름 사용)
                            selected_columns = [y_column_raw] + x_columns_raw
                            df_subset = df[selected_columns].copy()
                            
                            # 열 이름 변경
                            df_subset.columns = [y_column_clean] + x_columns_clean
                            
                            # numeric_x_selected: X 중 수치형인 깨끗한 이름
                            numeric_x_selected = [x_clean for x_raw, x_clean in zip(x_columns_raw, x_columns_clean) if x_raw in numeric_columns]
                            
                            # categorical_x_selected: X 중 범주형인 깨끗한 이름
                            categorical_x_selected = [x_clean for x_raw, x_clean in zip(x_columns_raw, x_columns_clean) if x_raw in categorical_columns]
                            
                            # 세션 상태 설정 (깨끗한 이름 사용)
                            st.session_state.df_subset = df_subset
                            st.session_state.y_column = y_column_clean
                            st.session_state.x_columns = x_columns_clean
                            st.session_state.numeric_x_selected = numeric_x_selected
                            st.session_state.categorical_x_columns = categorical_x_selected
                            st.session_state.variables_confirmed = True
                            
                            # 다음 단계로 자동 진행
                            st.session_state.current_step = "clean"
                            st.success("✅ 열 제목에서 자동으로 변수군을 설정했습니다. 결측치 처리 단계로 진행합니다.")
                            st.rerun()
                    else:
                        # 상세 출력(업로드 단계 자체에서 확인)
                        display_data_info(df, numeric_columns, categorical_columns, date_columns, datelike_columns, empty_columns, uploaded_file.name)
                        st.subheader("데이터 미리보기")
                        display_data_preview(df)

                        st.markdown("---")
                        if st.button("➡️ 다음 단계로 진행 (2단계: 변수군 선택)", type="primary", width='stretch'):
                            st.session_state.current_step = "select"
                            st.rerun()
            else:
                st.info("분석할 파일을 업로드하세요. 데이터는 회사 내부 서버에 저장됩니다.")

    # 2) 변수군 선택
    elif st.session_state.current_step == "select":
        # 이전 단계(업로드) 전체 보존 렌더
        render_upload_section(show_full=False)

        # 현재 단계 UI
        with panel("2단계: 변수군 선택", "section-select"):
            y_column, available_x_columns, numeric_x_selected, categorical_x_columns, df_subset = variable_selection_ui(
                st.session_state.numeric_columns,
                st.session_state.categorical_columns,
                st.session_state.df
            )

            if df_subset is not None:
                # 변수군 선택이 다시 선택되면 이후 단계들의 세션 상태 초기화
                reset_after_variable_selection()
                
                # 세션 저장
                st.session_state.df_subset = df_subset
                st.session_state.y_column = y_column
                st.session_state.x_columns = available_x_columns
                st.session_state.numeric_x_selected = numeric_x_selected
                st.session_state.current_step = "clean"
                st.rerun()

    # 3) 결측치 처리
    elif st.session_state.current_step == "clean":
        # 이전 단계들 전체 보존 렌더
        render_upload_section(show_full=False)
        render_select_section(show_full=False)

        # 현재 단계 UI
        with panel("3단계: 결측치 처리", "section-clean"):
            df_ready = data_cleaner(st.session_state.df_subset)

            if df_ready is not None and st.session_state.get("cleaning_completed"):
                st.session_state.df_ready = df_ready
                st.session_state.df_ready_sig = _df_signature(df_ready)
                st.session_state.current_step = "eda"
                st.rerun()

    # 4) 데이터 탐색
    elif st.session_state.current_step == "eda":
        # 이전 단계들 전체 보존 렌더
        render_upload_section(show_full=False)
        render_select_section(show_full=False)
        render_clean_section(show_full=False)

        # 현재 단계 UI
        with panel("4단계: 데이터 탐색", "section-eda"):
            perform_eda_analysis(st.session_state.df_ready,
                                 st.session_state.get("y_column"),
                                 st.session_state.get("x_columns", []))

            # 다음 단계로 진행 버튼
            st.markdown("---")
            if st.button("➡️ 다음 단계로 진행 (5단계: 데이터 분석 - 1. 선형 관계 탐색)", type="primary", width='stretch'):
                st.session_state.eda_completed = True
                st.session_state.current_step = "analyze"
                st.rerun()

    # 5) 데이터 분석
    elif st.session_state.current_step == "analyze":
        # 이전 단계들 보존 렌더링
        render_upload_section(show_full=False)
        render_select_section(show_full=False)
        render_clean_section(show_full=False)
        render_eda_section(show_full=False)

        # 현재 단계 UI
        with panel(f"5단계: 데이터 분석", "section-analyze"):
            if "df_ready" in st.session_state and st.session_state.df_ready is not None:
                y_column = st.session_state.get("y_column")
                x_columns = st.session_state.get("x_columns", [])
                
                if y_column and len(x_columns) > 0:
                    # df_ready에 대해 컬럼 타입 재분석 (깨끗한 이름 기반)
                    _, _, categorical_columns_ready, _, _, _ = analyze_column_types(st.session_state.df_ready)
                    
                    # 범주형 X 변수 확인
                    categorical_x = [x for x in x_columns if x in categorical_columns_ready]
                    
                    # 필터링된 데이터프레임 초기화
                    filtered_df = st.session_state.df_ready
                    
                    # 범주형 변수가 있으면 필터링 옵션 제공
                    if categorical_x:
                        with st.container(border=True):
                            # 제목
                            st.markdown("#### 🏷️ 범주형 변수 필터")
                            
                            # 설명 정보
                            st.info(
                                "**전체**를 선택하면 모든 범주를 통합 분석하고, **특정 범주**만 골라 선택하면 해당 데이터만 필터링하여 세부 분석을 수행합니다.\n\n"
                                "이 필터를 선택하고 **분석 시작** 버튼을 누르면 **5단계 전체**가 필터링된 데이터를 기준으로 다시 실행됩니다."
                            )

                            # 범주형 변수 개수에 따라 동적으로 컬럼 수 결정
                            # 1-2개: 1개 컬럼, 3개 이상: 2개 컬럼
                            if len(categorical_x) <= 2:
                                cols = st.columns(1)
                                num_cols = 1
                            else:
                                cols = st.columns(2)
                                num_cols = 2

                            # 각 칼럼에 드롭다운 배치
                            selected_filters = {}
                            for i, cat_var in enumerate(categorical_x):
                                col_idx = i % num_cols
                                with cols[col_idx] if num_cols > 1 else cols[0]:
                                    unique_vals = sorted(st.session_state.df_ready[cat_var].dropna().unique())
                                    selected = st.multiselect(
                                        f'변수명: **"{cat_var}"**',
                                        ["전체"] + list(unique_vals),
                                        default=["전체"],
                                        key=f"filter_{cat_var}",
                                        help=f"'{cat_var}'변수에 대하여 분석할 세부 범주를 선택합니다. '전체'를 선택하면 모든 범주를 포함합니다."
                                    )
                                    selected_filters[cat_var] = selected

                            # 버튼을 오른쪽 정렬으로 배치
                            st.divider()
                            col1, col2, col3 = st.columns([3, 1, 1], gap="small")
                            with col3:
                                apply_button = st.button(
                                    "🚀 분석 시작",
                                    key="apply_filters",
                                    type="primary",
                                    use_container_width=True,
                                    help="선택한 필터를 적용하고 분석을 시작합니다."
                                )
                            
                            if apply_button:
                                # 필터링 적용
                                filtered_df = st.session_state.df_ready.copy()
                                applied_filters = []
                                for var, vals in selected_filters.items():
                                    if "전체" not in vals and len(vals) > 0:
                                        filtered_df = filtered_df[filtered_df[var].isin(vals)]
                                        applied_filters.append(f"**{var}**: {', '.join(map(str, vals))}")
                                
                                # 필터 카운터 증가 및 필터링된 데이터셋 저장
                                st.session_state.category_filter_counter += 1
                                filter_key = f"df_ready_categoryfilter{st.session_state.category_filter_counter}"
                                st.session_state[filter_key] = filtered_df
                                st.session_state.current_filtered_df_key = filter_key
                                
                                # 5단계 분석을 처음부터 재수행하기 위해 초기화
                                st.session_state.analysis_stage = 1
                                st.session_state.baseline_r2 = None
                                st.session_state.filters_applied = True
                                st.session_state.applied_filters = applied_filters
                                
                                # 성공 메시지 표시
                                if applied_filters:
                                    filter_text = " / ".join(applied_filters)
                                    st.success(f"✅ 필터 적용 완료 ({len(filtered_df):,}행 남음)\n\n{filter_text}")
                                else:
                                    st.info("ℹ️ 전체 범주를 선택했습니다. (전체 {0:,}행 분석)".format(len(filtered_df)))
                                st.rerun()
                            
                            # 현재 선택된 필터로 임시 필터링 적용 (다운로드용)
                            # temp_filtered_df = st.session_state.df_ready.copy()
                            # temp_applied_filters = []
                            # for var, vals in selected_filters.items():
                            #     if "전체" not in vals and len(vals) > 0:
                            #         temp_filtered_df = temp_filtered_df[temp_filtered_df[var].isin(vals)]
                            #         temp_applied_filters.append(f"{var} ∈ {vals}")
                            
                            # 3분할 컬럼으로 버튼을 1/3 크기로 배치
                            # col1, col2, col3 = st.columns([2, 2, 3])
                            
                            # with col3:
                            #     with st.container(border=True):

                            #         # 필터링된 데이터 다운로드 섹션
                            #         st.markdown('<h4 style="margin:10px 0;color:#333;">💾 선별된 데이터 다운로드</h4>', unsafe_allow_html=True)
                            #         st.markdown('<p style="margin: 0px 0 10px 0; color: #666; font-size:14px;">선택한 범주에 해당하는 데이터만 다운로드하여 분포 및 이상 여부를 사전에 점검할 수 있습니다.</p>', unsafe_allow_html=True)
                                                        
                            #         # 필터링된 데이터 다운로드
                            #         csv_data = temp_filtered_df.to_csv(index=False, encoding='utf-8-sig')
                            #         st.markdown('<div class="download-button">', unsafe_allow_html=True)
                            #         st.download_button(
                            #             label="📥 필터링된 파일 다운로드",
                            #             data=csv_data,
                            #             file_name="filtered_data.csv",
                            #             mime="text/csv",
                            #             type="secondary",
                            #             width='stretch',
                            #             help="사용자가 선택한 범주형 변수들만으로 필터링된 데이터를 다운로드합니다. (CSV)"
                            #         )
                            #         st.markdown('</div>', unsafe_allow_html=True)
                        
                        # 버튼 누르기 전까지는 전체 데이터 사용
                        filtered_df = st.session_state.df_ready
                        if not st.session_state.get("current_filtered_df_key"):
                            st.session_state.current_filtered_df_key = None
                    
                    # 필터링된 데이터 사용 (버튼 누른 후) 또는 범주형 없으면 전체 데이터 사용
                    if st.session_state.get("current_filtered_df_key"):
                        filtered_df = st.session_state[st.session_state.current_filtered_df_key]
                    else:
                        filtered_df = st.session_state.df_ready
                    
                    # --- [개선된 로직 시작] ---
                    
                    # 1. 분석 단계 상태 초기화
                    if "analysis_stage" not in st.session_state:
                        st.session_state.analysis_stage = 1
                    if "baseline_r2" not in st.session_state:
                        st.session_state.baseline_r2 = None

                    # [1단계: 선형관계탐색] 
                    # 조건: 항상 보여주거나, stage가 1 이상일 때
                    with st.container():
                        st.markdown("<div id='section-linear-regression'></div>", unsafe_allow_html=True)
                        # 하위 제목 표시
                        st.markdown("""
                        <div style="display: flex; align-items: center; gap: 12px; margin: 2rem 0 1.5rem 0; opacity: 0.7;">
                            <div style="flex: 1; height: 2px; background: linear-gradient(to right, transparent, #28A745, transparent);"></div>
                            <span style="font-size: 12px; color: #666; white-space: nowrap; font-weight: 500;">아래의 분석 결과에 필터가 적용됩니다</span>
                            <div style="flex: 1; height: 2px; background: linear-gradient(to right, transparent, #28A745, transparent);"></div>
                        </div>
                        """, unsafe_allow_html=True)

                        st.markdown("""
                        <div style="background: linear-gradient(135deg, #D4EDDA 0%, #C3E6CB 100%); 
                                    border-left: 5px solid #28A745; 
                                    padding: 1rem 1.5rem; 
                                    border-radius: 8px; 
                                    margin-bottom: 1.5rem;
                                    box-shadow: 0 2px 4px rgba(40, 167, 69, 0.2);">
                        <h3 style="margin: 0; color: #2C3E50; font-size: 1.5em; font-weight: 600;">
                            ① 선형 관계 탐색 (가장 단순한 모델)
                        </h3>
                        <div style="font-size: 16px; line-height: 1.6; color: #2c3e50;">
                            Y 변수가 X 변수들과 직선적 관계로 이루어져 있는지 확인합니다.
                            <br>이 모델의 예측력이 좋지 않다면 선형 이외의 (더 복잡한) 패턴이 있다고 판단할 수 있습니다.
                        </div>
                        """, unsafe_allow_html=True)

                        # 1단계: 선형관계탐색 함수 호출
                        lr_results = perform_linear_regression(filtered_df, y_column, x_columns)

                        # 1단계: 선형관계탐색 함수 호출 (프로파일링 적용)
                        # lr_results = profile_run(
                        #     "Step5-1 perform_linear_regression",
                        #     perform_linear_regression,
                        #     st.session_state.df_ready,
                        #     y_column,
                        #     x_columns)

                        if lr_results and 'r2_test' in lr_results:
                            st.session_state.baseline_r2 = lr_results['r2_test']

                        if st.session_state.analysis_stage == 1:
                            st.markdown("---")
                            if st.button("➡️ 다음 단계로 진행 (5단계: 데이터 분석 - 2. 머신러닝 모델을 통한 예측)", key="goto_stage2", type="primary", width='stretch'):
                                st.session_state.analysis_stage = 2
                                st.rerun()

                    # [2단계: 머신러닝 분석 및 시뮬레이터]
                    if st.session_state.analysis_stage >= 2:
                        st.markdown("<div id='section-machine-learning'></div>", unsafe_allow_html=True)
                        st.markdown("<hr style='margin: 2rem 0;'>", unsafe_allow_html=True)
                        # 하위 제목 표시
                        st.markdown("""
                        <div style="background: linear-gradient(135deg, #D4EDDA 0%, #C3E6CB 100%); 
                                    border-left: 5px solid #28A745; 
                                    padding: 1rem 1.5rem; 
                                    border-radius: 8px; 
                                    margin-bottom: 1.5rem;
                                    box-shadow: 0 2px 4px rgba(40, 167, 69, 0.2);">
                        <h3 style="margin: 0; color: #2C3E50; font-size: 1.8em; font-weight: 600;">
                            ② 머신 러닝 모델을 통한 예측
                        </h3>
                        <div style="font-size: 16px; line-height: 1.6; color: #2c3e50;">
                            사용자의 데이터를 여러가지 머신러닝 모델들에 학습시킵니다.
                            <br>각 모델은 서로 다른 관점으로 데이터의 패턴을 찾고 각자의 해석에 따라 Y값을 유추합니다.
                            <br>사용된 모델 (6가지): Random Forest, Gradient Boosting, Support Vector Machine, Neural Network, Permutation Importance, SHAP
                        </div>
                        """, unsafe_allow_html=True)

                        # 분리된 파일 2의 함수 호출
                        perform_ml_analysis_and_simulator(
                            filtered_df, 
                            y_column, 
                            x_columns, 
                            st.session_state.baseline_r2
                        )
                        
                        if st.session_state.analysis_stage == 2:
                            st.markdown("---")
                            if st.button("➡️ 다음 단계로 진행 (5단계: 데이터 분석 - 3. 변수 선택 적정성 점검)", key="goto_stage3", type="primary", width='stretch'):
                                st.session_state.analysis_stage = 3
                                st.rerun()

                    # [3단계: 변수 선택 적정성 점검]
                    if st.session_state.analysis_stage >= 3:
                        st.markdown("<div id='section-variable-check'></div>", unsafe_allow_html=True)
                        st.markdown("<hr style='margin: 2rem 0;'>", unsafe_allow_html=True)
                        # 하위 제목 표시
                        st.markdown("""
                        <div style="background: linear-gradient(135deg, #D4EDDA 0%, #C3E6CB 100%); 
                                    border-left: 5px solid #28A745; 
                                    padding: 1rem 1.5rem; 
                                    border-radius: 8px; 
                                    margin-bottom: 1.5rem;
                                    box-shadow: 0 2px 4px rgba(40, 167, 69, 0.2);">
                        <h3 style="margin: 0; color: #2C3E50; font-size: 1.8em; font-weight: 600;">
                            ③ 변수 선택 적정성 점검
                        </h3>
                        <div style="font-size: 16px; line-height: 1.6; color: #2c3e50;">
                            만들어진 모델의 정확도를 더 향상시키고 싶다면 변수 선택이 적정했는지 재검토해 볼 필요가 있습니다. (AI의 도움을 받아 변수의 옥석을 가려낼 수 있습니다.)
                            <br>어떤 변수들은 서로 너무 비슷해서 분석을 방해(다중공선성; VIF)하기도 하고, 어떤 변수들은 너무 사소하여 예측에 기여하지 못하기도 합니다.
                            <br>또는 데이터 탐색(4단계) 시 분석 적합도가 낮았던 변수들에 전처리를 적용하여 예측 정확도를 높일 수 있습니다.
                        </div>
                        """, unsafe_allow_html=True)

                        # 분리된 파일 3의 함수 호출
                        perform_variable_check(filtered_df, x_columns)
                    
                else:
                    st.warning("분석을 위한 변수가 선택되지 않았습니다. 2단계에서 변수를 선택해주세요.")