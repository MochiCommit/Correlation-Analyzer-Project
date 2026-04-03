import streamlit as st
import pandas as pd
import numpy as np
import re

# -------------------------------
# 내부 유틸 (결측치/숫자 처리용)
# -------------------------------

# [FIX-NA] 엑셀/CSV에서 자주 보이는 오류·결측 토큰을 전역 패턴으로 정의
_NA_TOKENS = [
    r'#NODATA', r'#DIV/0!', r'#VALUE!', r'#REF!', r'#NAME\?', r'#NULL!',
    r'N/?A', r'NA', r'NaN', r'nan', r'None', r'NULL', r'—', r'-{1,2}'
]
_NA_REGEX = re.compile(r'^\s*(?:' + '|'.join(_NA_TOKENS) + r')\s*$', re.IGNORECASE)

def _strip_and_nanify(df: pd.DataFrame) -> pd.DataFrame:
    """문자열 양끝 공백 제거 + 오류/결측 토큰을 NaN으로 통일."""
    out = df.copy()
    for c in out.columns:
        if out[c].dtype == object:
            s = out[c].astype(str).str.strip()
            s = s.replace({'': np.nan})
            s = s.apply(lambda x: (np.nan if (isinstance(x, str) and _NA_REGEX.match(x)) else x))
            out[c] = s
    return out

def _coerce_numeric_series(s: pd.Series) -> pd.Series:
    """쉼표/공백/유니코드 마이너스 등을 정리해 숫자로 강제 변환."""
    if s.dtype != object:
        return pd.to_numeric(s, errors='coerce')
    ss = s.astype(str).str.strip()
    ss = ss.str.replace(',', '', regex=False)          # 천단위 구분 쉼표 제거
    ss = ss.str.replace('\u2212', '-', regex=False)    # 유니코드 마이너스 → 일반 -
    ss = ss.replace({'': np.nan})
    ss = ss.apply(lambda x: np.nan if (isinstance(x, str) and _NA_REGEX.match(x)) else x)
    return pd.to_numeric(ss, errors='coerce')


# -------------------------------
# 1) 파일 로더
# -------------------------------

def load_data(uploaded_file):
    """파일을 업로드하고 데이터를 로드합니다."""
    try:
        if uploaded_file.name.endswith('.csv'):
            encodings = ['utf-8', 'cp949', 'euc-kr', 'latin1']
            df = None
            for encoding in encodings:
                try:
                    uploaded_file.seek(0)
                    # [FIX-3] 오류 토큰을 바로 NaN으로, 쉼표 천단위도 인식
                    df = pd.read_csv(
                        uploaded_file,
                        encoding=encoding,
                        na_values=['', ' ', '#NODATA', '#DIV/0!', '#VALUE!', '#REF!', '#NAME?', '#NULL!', 'N/A', 'NA', 'NaN', 'nan', 'None', 'NULL', '-', '--', '—', ' - '],
                        keep_default_na=True,
                        skipinitialspace=True,
                        thousands=','   # 천단위 쉼표 인식
                    )
                    break
                except UnicodeDecodeError:
                    continue
                except Exception:
                    continue
            if df is None:
                st.error("지원되는 인코딩으로 파일을 읽을 수 없습니다. 파일 인코딩을 확인해주세요.")
                return None
        else:
            # 엑셀도 동일 컨셉: 읽은 뒤 문자열 정리→숫자 강제변환(대상 컬럼)
            df = pd.read_excel(uploaded_file)

        # [FIX-3] 값 내부 공백·결측·오류 토큰 정규화
        df = _strip_and_nanify(df)

        st.success("파일이 성공적으로 로드되었습니다.")
        return df
    except Exception as e:
        st.error(f"데이터 처리 중 오류가 발생했습니다: {str(e)}")
        return None

# -------------------------------
# 2) 컬럼 타입 분석
# -------------------------------

def analyze_column_types(df):
    """각 열의 데이터 타입을 대분류와 소분류로 분석합니다."""
    column_analysis = {}
    numeric_columns = []
    categorical_columns = []
    date_columns = []
    datelike_columns = []  # 패턴 매칭으로 추정된 날짜형
    empty_columns = []  # Empty 컬럼들을 별도로 관리

    for col in df.columns:
        col_dtype = df[col].dtype
        non_null_values = df[col].dropna()

        if len(non_null_values) == 0:
            column_analysis[col] = {'main_category': 'Empty', 'sub_category': 'Empty', 'is_numeric': False}
            empty_columns.append(col)
            continue

        # Boolean 패턴 감지: [0, 1, -, O, X, 공백] 조합만 있는 경우 (모든 타입에서 먼저 확인)
        unique_values = set(non_null_values.astype(str).str.strip().str.upper())
        boolean_patterns = {'0', '1', '-', 'O', 'X', '', ' - '}
        
        if unique_values.issubset(boolean_patterns):
            # Boolean으로 분류하고 값 정규화
            column_analysis[col] = {'main_category': '범주형', 'sub_category': '불리언', 'is_numeric': False}
            
            # 값 정규화: 0/1로 변환
            normalized_values = non_null_values.astype(str).str.strip().str.upper()
            normalized_values = normalized_values.replace({'': '0', '0': '0', '-': '0', 'X': '0', '1': '1', 'O': '1', ' - ': '0'})
            
            # 원본 데이터프레임의 해당 컬럼도 정규화된 값으로 업데이트
            df[col] = df[col].astype(str).str.strip().str.upper().replace({'': '0', '0': '0', '-': '0', 'X': '0', '1': '1', 'O': '1', ' - ': '0'})
            
            categorical_columns.append(col)
            continue

        # 정수/실수/날짜/불린: 기존 로직 유지
        if col_dtype in ['int64', 'int32', 'int16', 'int8']:
            column_analysis[col] = {'main_category': '수치형', 'sub_category': '정수', 'is_numeric': True}
            numeric_columns.append(col)

        elif col_dtype in ['float64', 'float32', 'float16']:
            column_analysis[col] = {'main_category': '수치형', 'sub_category': '실수', 'is_numeric': True}
            numeric_columns.append(col)

        elif 'datetime' in str(col_dtype):
            column_analysis[col] = {'main_category': '날짜형', 'sub_category': '날짜시간', 'is_numeric': False}
            date_columns.append(col)

        elif col_dtype == 'bool':
            column_analysis[col] = {'main_category': '범주형', 'sub_category': '불리언', 'is_numeric': False}
            categorical_columns.append(col)

        # object(문자열/혼합형) 처리
        else:
            # [FIX-2] 카테고리 판단 전에 "숫자 강제 변환"을 먼저 시도
            coerced = _coerce_numeric_series(df[col])
            # non-null 중 몇 %가 숫자로 안전 변환되는지(유연성 확보)
            convertible_frac = (coerced.notna().sum() / len(non_null_values))

            if convertible_frac >= 0.90:
                # 숫자로 보는 것이 타당
                sub = '실수' if ((coerced.dropna() % 1) != 0).any() else '정수'
                column_analysis[col] = {'main_category': '수치형', 'sub_category': sub, 'is_numeric': True}
                numeric_columns.append(col)
                continue

            # 날짜 패턴/카테고리/텍스트 판정 로직
            is_date_like = False
            date_patterns = [
                r'^\d{4}-\d{1,2}-\d{1,2}$',
                r'^\d{4}/\d{1,2}/\d{1,2}$',
                r'^\d{4}\.\d{1,2}\.\d{1,2}$',
                r'^\d{1,2}/\d{1,2}/\d{4}$',
                r'^\d{1,2}-\d{1,2}-\d{4}$',
                r'^\d{4}-\d{1,2}-\d{1,2} \d{1,2}:\d{1,2}:\d{1,2}$',
                r'^\d{4}-\d{1,2}-\d{1,2} \d{1,2}:\d{1,2}$',
                r'^\d{4}/\d{1,2}/\d{1,2} \d{1,2}:\d{1,2}:\d{1,2}$',
                r'^\d{4}/\d{1,2}/\d{1,2} \d{1,2}:\d{1,2}$',
            ]
            for pattern in date_patterns:
                if non_null_values.astype(str).str.match(pattern).all():
                    is_date_like = True
                    break

            if not is_date_like and non_null_values.astype(str).str.match(r'^\d+$').all():
                try:
                    numeric_values = non_null_values.astype(float)
                    if (numeric_values >= 42000).all() and (numeric_values <= 48000).all():
                        is_date_like = True
                except:
                    pass

            if not is_date_like:
                flexible_patterns = [
                    r'^\d{4}년\d{1,2}월\d{1,2}일',
                    r'^\d{4}.\d{1,2}.\d{1,2}',
                    r'^\d{1,2}/\d{1,2}/\d{2,4}',
                ]
                for pattern in flexible_patterns:
                    if non_null_values.astype(str).str.match(pattern).all():
                        is_date_like = True
                        break

            if is_date_like:
                column_analysis[col] = {'main_category': '날짜형', 'sub_category': '날짜', 'is_numeric': False}
                datelike_columns.append(col)
            elif len(non_null_values.unique()) / len(non_null_values) < 0.1:
                column_analysis[col] = {'main_category': '범주형', 'sub_category': '범주', 'is_numeric': False}
                categorical_columns.append(col)
            elif non_null_values.astype(str).str.match(r'^\d+$').all():
                column_analysis[col] = {'main_category': '범주형', 'sub_category': '식별자', 'is_numeric': False}
                categorical_columns.append(col)
            else:
                column_analysis[col] = {'main_category': '범주형', 'sub_category': '텍스트', 'is_numeric': False}
                categorical_columns.append(col)

    return column_analysis, numeric_columns, categorical_columns, date_columns, datelike_columns, empty_columns

def get_emoji_for_type(type_name):
    emoji_map = {
        '정수': '🔢', '실수': '🔢',
        '날짜': '📅', '날짜시간': '📅',
        '불리언': '✅', '범주': '🏷️', '식별자': '🆔', '텍스트': '📝', 'Empty': '❌'
    }
    return emoji_map.get(type_name, '❓')

# -------------------------------
# 3) 데이터 요약 표시 (원형 유지)
# -------------------------------

def display_data_info(df, numeric_columns, categorical_columns, date_columns, datelike_columns, empty_columns, filename=None):
    variable_types = []
    if len(numeric_columns) > 0:
        variable_types.append(f"🔢 수치형 {len(numeric_columns)}개")
    if len(categorical_columns) > 0:
        variable_types.append(f"🏷️ 범주형 {len(categorical_columns)}개")
    if len(date_columns) > 0:
        variable_types.append(f"📅 날짜형 {len(date_columns)}개")
    if len(datelike_columns) > 0:
        variable_types.append(f"📅 날짜형 {len(datelike_columns)}개")
    if len(empty_columns) > 0:
        variable_types.append(f"❌ 비어있는 열 {len(empty_columns)}개")
    variable_types_str = ", ".join(variable_types)
    explanation = ""
    if len(categorical_columns) > 0 or len(numeric_columns) > 0 or len(date_columns) > 0 or len(datelike_columns) > 0 or len(empty_columns) > 0:
        explanation = '<span style="font-size: 13px; color: #1a1a1a; line-height: 1.8;"><strong>변수 유형 설명:</strong><br/>• <strong>🔢 수치형</strong>: 정수, 실수 등 숫자 데이터 (예: 온도, 압력, 유량)<br/>• <strong>🏷️ 범주형</strong>: 텍스트, 불리언(0/1), 식별자 등 (예: 제품명, 상태, ID)<br/>• <strong>📅 날짜형</strong>: 날짜, 날짜+시간 데이터 (예: 측정일시, 생산일)</span>'
    st.markdown(f"""
    <div style="background: linear-gradient(135deg, #D4EDDA 0%, #C3E6CB 100%); padding: 20px; border-radius: 10px; border-left: 5px solid #28A745; margin: 20px 0; box-shadow: 0 2px 4px rgba(40, 167, 69, 0.2);">
        <h3 style="margin: 0 0 15px 0; color: #155724; font-weight: bold;">📊 데이터 정보</h3>
        <div style="font-size: 16px; line-height: 1.6; color: #1a1a1a;">
            <p style="margin: 2px 0;"><strong>파일명:</strong> {filename if filename else '알 수 없음'}</p>
            <p style="margin: 2px 0;"><strong>데이터 크기:</strong> {df.shape[1]}열 × {df.shape[0]}행</p>
            <p style="margin: 2px 0 7px 0;"><strong>변수(열) 종류:</strong> {variable_types_str}</p>
            <p style="margin: 2px 0;">{explanation}</p>
        </div>
    </div>
    """, unsafe_allow_html=True)


def display_data_preview(df):
    df_preview = df.copy()
    df_preview.index = range(1, len(df_preview) + 1)
    
    column_analysis, _, _, date_columns, datelike_columns, _ = analyze_column_types(df)
    all_date_columns = list(set(date_columns + datelike_columns))
    if all_date_columns:
        reordered_columns = all_date_columns + [col for col in df_preview.columns if col not in all_date_columns]
        df_preview = df_preview[reordered_columns]
    dtype_row = {}
    for col in df_preview.columns:
        sub_category = column_analysis[col]['sub_category']
        dtype_row[col] = f"{get_emoji_for_type(sub_category)} {sub_category}"
    df_preview_with_dtypes = pd.concat([
        pd.DataFrame([dtype_row], index=['Type']),
        df_preview
    ])
    st.dataframe(
        df_preview_with_dtypes,
        width='stretch',
        height=500,
        hide_index=True
    )
