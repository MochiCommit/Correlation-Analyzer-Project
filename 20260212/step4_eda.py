import streamlit as st
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import pandas as pd

# matplotlib 백엔드 설정 (Streamlit 호환성)
plt.switch_backend('Agg')

# 한글 폰트 설정 및 마이너스 기호 문제 해결
plt.rcParams['font.family'] = 'DejaVu Sans'
plt.rcParams['axes.unicode_minus'] = False  # 마이너스 기호 문제 해결

# Windows에서 한글 폰트 사용 시
try:
    font_path = 'C:/Windows/Fonts/malgun.ttf'  # 맑은 고딕
    font_prop = fm.FontProperties(fname=font_path)
    plt.rcParams['font.family'] = font_prop.get_name()
    plt.rcParams['axes.unicode_minus'] = False  # 마이너스 기호 문제 해결
except:
    pass

@st.cache_data(show_spinner="극단적 분포 감지 중...")
def detect_extreme_distribution(data):
    """
    극단적으로 분리된 분포를 감지하는 함수 (개선된 버전)
    
    Returns:
        tuple: (is_extreme, max_ratio, second_ratio, valley_ratio)
        - is_extreme: 극단적 분포 여부 (bool)
        - max_ratio: 주요 피크의 비율 (float)
        - second_ratio: 두 번째 피크의 비율 (float) 
        - valley_ratio: 골짜기(최소값)의 비율 (float)
    """
    if len(data) == 0:
        return False, 0, 0, 0
    
    # 히스토그램 생성 (더 세밀한 분석을 위해 bin 수 증가)
    hist, bin_edges = np.histogram(data, bins=50)
    
    # 정규화 (비율로 변환)
    hist_ratio = hist / len(data)
    
    # 1. 극단적 집중도 분석 (0 근처나 최대값 근처 집중)
    data_range = data.max() - data.min()
    
    # 0 근처 집중도 (데이터 범위의 10% 이내)
    zero_threshold = data_range * 0.1
    zero_concentration = len(data[data <= zero_threshold]) / len(data)
    
    # 최대값 근처 집중도 (상위 10% 구간)
    upper_threshold = data.quantile(0.9)
    upper_concentration = len(data[data >= upper_threshold]) / len(data)
    
    # 2. 피크 감지 (더 유연한 기준)
    peak_indices = []
    max_freq = np.max(hist)
    min_peak_height = max(max_freq * 0.15, 2)  # 기준을 20%에서 15%로 완화
    
    for i in range(1, len(hist)-1):
        if (hist[i] > hist[i-1] and hist[i] > hist[i+1] and 
            hist[i] >= min_peak_height):
            peak_indices.append(i)
    
    # 3. 극단적 분포 판단 (다양한 기준 추가)
    is_extreme = False
    max_ratio = 0
    second_ratio = 0
    valley_ratio = 0
    
    # 기준 1: 한쪽 극단에 50% 이상 집중 (기존 60%에서 완화)
    if zero_concentration >= 0.5 or upper_concentration >= 0.5:
        is_extreme = True
        max_ratio = max(zero_concentration, upper_concentration)
        second_ratio = 1 - max_ratio  # 나머지 분포
        valley_ratio = 0.1  # 극단적 집중이므로 골짜기 비율 낮게 설정
    
    # 기준 2: 기존 피크 기반 분석 (2개 이상 피크가 있는 경우)
    elif len(peak_indices) >= 2:
        # 피크들을 크기 순으로 정렬
        peak_values = [(i, hist_ratio[i]) for i in peak_indices]
        peak_values.sort(key=lambda x: x[1], reverse=True)
        
        max_ratio = peak_values[0][1]
        second_ratio = peak_values[1][1] if len(peak_values) > 1 else 0
        
        # 두 주요 피크 사이의 골짜기 찾기
        peak1_idx = peak_values[0][0]
        peak2_idx = peak_values[1][0]
        
        if peak1_idx > peak2_idx:
            peak1_idx, peak2_idx = peak2_idx, peak1_idx
        
        # 두 피크 사이의 최소값 찾기
        valley_region = hist_ratio[peak1_idx:peak2_idx+1]
        valley_ratio = np.min(valley_region) if len(valley_region) > 0 else 0
        
        # 피크 기반 극단적 분포 판단 (기준 완화)
        is_extreme = (max_ratio >= 0.5 and  # 기존 60%에서 50%로 완화
                      second_ratio >= 0.15 and  # 기존 20%에서 15%로 완화
                      valley_ratio < min(max_ratio, second_ratio) * 0.4)  # 기존 30%에서 40%로 완화
    
    # 기준 3: 편향도 기반 극단적 분포 (강한 편향 + 집중도)
    skewness = data.skew()
    if abs(skewness) > 2.0:  # 매우 강한 편향
        # 편향 방향의 극단 구간 집중도 확인
        if skewness > 0:  # 오른쪽 편향
            upper_25_percent = data.quantile(0.75)
            upper_concentration = len(data[data >= upper_25_percent]) / len(data)
            if upper_concentration >= 0.4:  # 상위 25%에 40% 이상 집중
                is_extreme = True
                max_ratio = upper_concentration
                second_ratio = 1 - upper_concentration
                valley_ratio = 0.1
        else:  # 왼쪽 편향
            lower_25_percent = data.quantile(0.25)
            lower_concentration = len(data[data <= lower_25_percent]) / len(data)
            if lower_concentration >= 0.4:  # 하위 25%에 40% 이상 집중
                is_extreme = True
                max_ratio = lower_concentration
                second_ratio = 1 - lower_concentration
                valley_ratio = 0.1
    
    return is_extreme, max_ratio, second_ratio, valley_ratio

def perform_eda_analysis(df_ready, y_column, x_columns):
    """데이터 탐색 분석을 수행하는 함수"""
    
    # 변수별 분포 분석 (히스토그램만)
    st.markdown('<h4 style="margin: 10px 0; color: #333;">📊 변수별 분포 분석</h4>', unsafe_allow_html=True)

    # 모든 변수들 (Y + X) - 수치형과 범주형 모두 포함
    all_cols = [y_column] + x_columns
    
    if len(all_cols) > 0:
        for idx, col in enumerate(all_cols):
            # 변수 타입 확인 (수치형 vs 범주형)
            is_numeric = df_ready[col].dtype in ['int64', 'float64']
            
            # 변수별 제목 추가
            if col == y_column:
                st.markdown(f'<h5 style="margin: 10px 0; color: #666;">{col} (Y 변수)</h5>', unsafe_allow_html=True)
            else:
                x_idx = idx - 1  # Y변수 제외하고 X변수 순서 계산
                # 한글 순번 생성
                korean_numbers = ["첫번째", "두번째", "세번째", "네번째", "다섯번째", "여섯번째", "일곱번째", "여덟번째", "아홉번째", "열번째"]
                if x_idx < len(korean_numbers):
                    order_text = korean_numbers[x_idx]
                else:
                    order_text = f"{x_idx + 1}번째"
                st.markdown(f'<h5 style="margin: 10px 0; color: #666;">{col} ({order_text} X 변수)</h5>', unsafe_allow_html=True)
            
            # 각 변수별로 좌우 컬럼 레이아웃
            col1, col2 = st.columns([1, 1])
            
            with col1:
                # 히스토그램 차트
                fig, ax = plt.subplots(figsize=(8, 6))
                
                if is_numeric:
                    # 수치형 변수 처리
                    # 원본 시리즈 취득 후 숫자 변환 (문자열형 숫자 처리)
                    raw_series = df_ready[col]
                    if raw_series.dtype == 'O':
                        cleaned = (raw_series.astype(str)
                                     .str.strip()
                                     .str.replace(',', '', regex=False)
                                     .str.replace(' ', '', regex=False)
                                     .str.replace('\u00a0', '', regex=False))
                        # 점(.)이 여러 개인 경우 천 단위 구분자로 판단하여 모두 제거
                        cleaned = cleaned.apply(lambda s: s.replace('.', '') if s.count('.') > 1 else s)
                        # 숫자, 음수부호, 소수점만 남기기 (그 외 문자는 제거)
                        cleaned = cleaned.str.replace(r'[^0-9\.-]', '', regex=True)
                        data = pd.to_numeric(cleaned, errors='coerce').dropna()
                    else:
                        data = raw_series.dropna()
                
                if is_numeric and len(data) > 0:
                    # 기본 통계량 계산 (히스토그램 그리기 전에)
                    mean_val = data.mean()
                    q25 = data.quantile(0.25)
                    q75 = data.quantile(0.75)
                    
                    # 히스토그램 그리기
                    weights = np.ones(len(data)) / len(data) * 100
                    n, bins, patches = ax.hist(data, bins=30, alpha=0.7, 
                                             color='skyblue' if col == y_column else 'lightcoral', 
                                             edgecolor='black', weights=weights)
                    ax.set_ylim(0, 100)
                    
                    # 중위 50% 구간 영역 표시 (Q25-Q75) - 최소 너비 보장
                    iqr = q75 - q25
                    data_range = data.max() - data.min()
                    bin_width = data_range / 30  # 히스토그램 한 칸의 너비
                    
                    # 최소 너비를 히스토그램 한 칸의 2배로 설정
                    min_width = bin_width * 2
                    if iqr < min_width:
                        # IQR이 너무 작으면 최소 너비로 확장 (중심점 기준)
                        center = (q25 + q75) / 2
                        q25_adjusted = center - min_width / 2
                        q75_adjusted = center + min_width / 2
                        # 데이터 범위를 벗어나지 않도록 조정
                        q25_adjusted = max(q25_adjusted, data.min())
                        q75_adjusted = min(q75_adjusted, data.max())
                    else:
                        q25_adjusted = q25
                        q75_adjusted = q75
                    
                    ax.axvspan(q25_adjusted, q75_adjusted, alpha=0.2, color='lightblue', 
                              label='중위 50% 구간')
                    
                    # 평균선 표시 (진한 세로선)
                    ax.axvline(mean_val, color='darkblue', linewidth=2, 
                              label='평균')
                    
                    # 그룹 별 대푯값 표시 (네러티브와 동일한 기준 적용)
                    # 네러티브에서 사용하는 그룹 감지 로직과 동일하게 적용
                    hist, bin_edges = np.histogram(data, bins=30)
                    
                    # 1. 피크 감지 개선 - 네러티브와 동일한 기준
                    peak_values = []
                    max_freq = np.max(hist)
                    min_peak_height = max(max_freq * 0.25, 3)  # 네러티브와 동일한 기준
                    
                    # 스무딩을 적용한 히스토그램으로 피크 감지 개선
                    from scipy import ndimage
                    smoothed_hist = ndimage.gaussian_filter1d(hist.astype(float), sigma=1.0)
                    
                    for i in range(1, len(smoothed_hist)-1):
                        # 피크 조건: 양쪽보다 높고, 최소 높이 이상, 그리고 주변과 충분한 차이
                        if (smoothed_hist[i] > smoothed_hist[i-1] and smoothed_hist[i] > smoothed_hist[i+1] and 
                            smoothed_hist[i] >= min_peak_height and
                            smoothed_hist[i] - min(smoothed_hist[i-1], smoothed_hist[i+1]) >= max_freq * 0.05):  # 네러티브와 동일한 차이 기준
                            peak_values.append(bin_edges[i])
                    
                    # 2. 피크 간 거리 분석 - 네러티브와 동일한 기준
                    if len(peak_values) > 1:
                        peak_values.sort()
                        filtered_peaks = [peak_values[0]]  # 첫 번째 피크는 항상 포함
                        
                        for i in range(1, len(peak_values)):
                            # 이전 피크와의 거리가 전체 범위의 5% 이상인 경우만 포함 (네러티브와 동일)
                            data_range = data.max() - data.min()
                            min_distance = data_range * 0.05
                            
                            if peak_values[i] - filtered_peaks[-1] >= min_distance:
                                filtered_peaks.append(peak_values[i])
                        
                        peak_values = filtered_peaks
                    
                    # 3. 추가 피크 검증 - 네러티브와 동일한 기준
                    if len(peak_values) >= 2:
                        # 각 피크 주변의 실제 데이터 밀도 확인
                        validated_peaks = []
                        for peak in peak_values:
                            # 피크 주변 ±5% 구간의 데이터 비율 계산
                            peak_range = data_range * 0.1
                            nearby_data = data[(data >= peak - peak_range) & (data <= peak + peak_range)]
                            if len(nearby_data) >= len(data) * 0.05:  # 전체 데이터의 5% 이상
                                validated_peaks.append(peak)
                        
                        if len(validated_peaks) >= 2:
                            peak_values = validated_peaks
                    
                    # 4. 분포의 이중성(dip) 분석 - 네러티브와 동일한 기준
                    bimodal_score = 0
                    if len(peak_values) >= 2:
                        # 두 피크 사이의 최소값 찾기
                        peak1_idx = np.argmin(np.abs(bin_edges - peak_values[0]))
                        peak2_idx = np.argmin(np.abs(bin_edges - peak_values[1]))
                        
                        if peak1_idx < peak2_idx:
                            valley_region = hist[peak1_idx:peak2_idx+1]
                            valley_min = np.min(valley_region)
                            valley_ratio = valley_min / max(hist[peak1_idx], hist[peak2_idx])
                            
                            # 골짜기가 깊을수록 이중 분포 가능성 높음
                            if valley_ratio < 0.3:  # 골짜기가 최고점의 30% 미만
                                bimodal_score = 1
                    
                    # 5. 극단값 집중도 분석 - 네러티브와 동일한 기준
                    extreme_concentration = 0
                    data_range = data.max() - data.min()
                    
                    # 하위 20% 구간의 데이터 비율
                    lower_20_percent = data.quantile(0.2)
                    lower_ratio = len(data[data <= lower_20_percent]) / len(data)
                    
                    # 상위 20% 구간의 데이터 비율  
                    upper_20_percent = data.quantile(0.8)
                    upper_ratio = len(data[data >= upper_20_percent]) / len(data)
                    
                    # 0 근처 집중도 (데이터 범위의 5% 이내)
                    zero_threshold = data_range * 0.05
                    zero_concentration = len(data[data <= zero_threshold]) / len(data)
                    
                    # 한쪽 극단에 50% 이상 집중된 경우
                    if lower_ratio >= 0.5 or upper_ratio >= 0.5 or zero_concentration >= 0.5:
                        extreme_concentration = 1
                    
                    # 6. 편향도 기반 극단적 분포 감지 - 네러티브와 동일한 기준
                    skewness_based_extreme = 0
                    skewness = data.skew()
                    if abs(skewness) > 1.5:  # 강한 편향
                        if skewness > 0:  # 오른쪽 편향
                            # 상위 30% 구간의 집중도
                            upper_30_percent = data.quantile(0.7)
                            upper_30_ratio = len(data[data >= upper_30_percent]) / len(data)
                            if upper_30_ratio >= 0.4:  # 상위 30%에 40% 이상 집중
                                skewness_based_extreme = 1
                        else:  # 왼쪽 편향
                            # 하위 30% 구간의 집중도
                            lower_30_percent = data.quantile(0.3)
                            lower_30_ratio = len(data[data <= lower_30_percent]) / len(data)
                            if lower_30_ratio >= 0.4:  # 하위 30%에 40% 이상 집중
                                skewness_based_extreme = 1
                    
                    # 7. 그룹 별 대푯값 표시 - 네러티브와 동일한 기준 적용
                    show_group_lines = False
                    
                    # 명확한 2개 그룹이 감지된 경우
                    if len(peak_values) == 2 and (bimodal_score == 1 or extreme_concentration == 1 or skewness_based_extreme == 1):
                        show_group_lines = True
                    # 3개 이상 그룹이 감지된 경우
                    elif len(peak_values) >= 3:
                        show_group_lines = True
                    # 극단적 집중도나 편향도 기반으로 2개 그룹이 감지된 경우
                    elif extreme_concentration == 1 or skewness_based_extreme == 1:
                        show_group_lines = True
                    
                    # 그룹 별 대푯값 표시 (평균선보다 옅은 색)
                    if show_group_lines:
                        if len(peak_values) >= 2:
                            # 피크 기반 그룹 대푯값 표시
                            for i, peak in enumerate(peak_values):
                                ax.axvline(peak, color='steelblue', linewidth=1.5, linestyle='--', alpha=0.7,
                                          label='그룹 별 대푯값' if i == 0 else '')
                        elif extreme_concentration == 1 or skewness_based_extreme == 1:
                            # 극단적 분포 기반 그룹 대푯값 표시
                            if zero_concentration >= 0.5:
                                # 0 근처와 나머지 분포의 대푯값
                                ax.axvline(0, color='steelblue', linewidth=1.5, linestyle='--', alpha=0.7,
                                          label='그룹 별 대푯값')
                                # 나머지 분포의 대푯값 (0이 아닌 데이터의 평균)
                                non_zero_data = data[data > zero_threshold]
                                if len(non_zero_data) > 0:
                                    non_zero_mean = non_zero_data.mean()
                                    ax.axvline(non_zero_mean, color='steelblue', linewidth=1.5, linestyle='--', alpha=0.7)
                            elif lower_ratio >= 0.5:
                                # 하위 극단과 나머지 분포의 대푯값
                                lower_mean = data[data <= lower_20_percent].mean()
                                upper_mean = data[data > lower_20_percent].mean()
                                ax.axvline(lower_mean, color='steelblue', linewidth=1.5, linestyle='--', alpha=0.7,
                                          label='그룹 별 대푯값')
                                ax.axvline(upper_mean, color='steelblue', linewidth=1.5, linestyle='--', alpha=0.7)
                            elif upper_ratio >= 0.5:
                                # 상위 극단과 나머지 분포의 대푯값
                                upper_mean = data[data >= upper_20_percent].mean()
                                lower_mean = data[data < upper_20_percent].mean()
                                ax.axvline(upper_mean, color='steelblue', linewidth=1.5, linestyle='--', alpha=0.7,
                                          label='그룹 별 대푯값')
                                ax.axvline(lower_mean, color='steelblue', linewidth=1.5, linestyle='--', alpha=0.7)
                    
                    # 그래프 꾸미기
                    ax.set_xlabel(col, fontsize=14)
                    ax.set_ylabel('빈도 (%)', fontsize=14)
                    ax.grid(True, alpha=0.3)
                    
                    # x축, y축 틱 라벨 크기 설정
                    ax.tick_params(axis='both', which='major', labelsize=14)
                    
                    # x축 값 포맷팅 (1000 이상은 쉼표 추가, 10 미만은 소수점 둘째자리)
                    def format_x_ticks(x, pos):
                        if x >= 1000:
                            return f'{x:,.0f}'
                        elif x >= 10:
                            return f'{x:.1f}'
                        else:
                            return f'{x:.2f}'
                    
                    ax.xaxis.set_major_formatter(plt.FuncFormatter(format_x_ticks))
                    
                    # 범례 추가 (최대 3개 항목만 표시)
                    handles, labels = ax.get_legend_handles_labels()
                    if len(handles) > 3:
                        handles = handles[:3]
                        labels = labels[:3]
                    ax.legend(handles, labels, loc='upper right', fontsize=10)
                
                elif not is_numeric:
                    # 범주형 변수 처리
                    raw_series = df_ready[col].dropna()
                    
                    if len(raw_series) > 0:
                        # 범주별 카운트 계산 및 이름 오름차순 정렬
                        category_counts = raw_series.value_counts()
                        category_counts = category_counts.sort_index()  # 범주 이름 오름차순
                        
                        # 빈도를 퍼센트로 변환
                        category_percentages = (category_counts / len(raw_series)) * 100
                        
                        # 막대 그래프 그리기
                        bars = ax.bar(range(len(category_percentages)), 
                                     category_percentages.values,
                                     color='lightcoral' if col != y_column else 'skyblue',
                                     edgecolor='black',
                                     alpha=0.7)
                        
                        # x축 설정
                        ax.set_xticks(range(len(category_percentages)))
                        ax.set_xticklabels(category_percentages.index, rotation=45, ha='right', fontsize=12)
                        
                        # y축 설정 (0-100%)
                        ax.set_ylim(0, 100)
                        ax.set_ylabel('빈도 (%)', fontsize=14)
                        ax.set_xlabel(col, fontsize=14)
                        
                        # 그리드 추가
                        ax.grid(True, alpha=0.3, axis='y')
                        
                        # y축 틱 라벨 크기 설정
                        ax.tick_params(axis='y', which='major', labelsize=14)
                
                plt.tight_layout()
                st.pyplot(fig)
            
            with col2:
                # 변수별 분포 내러티브 생성
                if is_numeric and len(data) > 0:
                    # 기본 통계량 계산
                    mean_val = data.mean()
                    std_val = data.std()
                    median_val = data.median()
                    q1 = data.quantile(0.25)
                    q3 = data.quantile(0.75)
                    skewness = data.skew()
                    kurtosis = data.kurtosis()
                    
                    # 변수 타입 및 숫자 포맷팅 정의
                    var_type = "Y변수" if col == y_column else "X변수"
                    
                    # 숫자 포맷팅 (큰 숫자는 소수점 제거, 천 단위 이상은 쉼표 추가)
                    if mean_val >= 100:
                        mean_str = f"{mean_val:,.0f}"
                    else:
                        mean_str = f"{mean_val:.2f}"
                    
                    # 분포 형태 분석 개선 (더 세분화된 기준과 다양한 분석 기법)
                    if abs(skewness) < 0.1:
                        dist_type = "거의 완벽한 정규분포"
                        dist_desc = "대칭적이고 균등한 분포를 보입니다."
                    elif abs(skewness) < 0.3:
                        dist_type = "정규분포에 매우 가까운"
                        dist_desc = "약간의 비대칭이 있지만 거의 대칭적인 분포를 보입니다."
                    elif abs(skewness) < 0.5:
                        dist_type = "정규분포에 가까운"
                        dist_desc = "대체로 대칭적이지만 약간의 치우침이 있는 분포를 보입니다."
                    elif abs(skewness) < 0.7:
                        dist_type = "약간 치우친"
                        dist_desc = "중간 정도의 치우침을 보이는 분포를 보입니다."
                    elif abs(skewness) < 1.0:
                        dist_type = "치우친"
                        dist_desc = "명확한 치우침을 보이는 분포를 보입니다."
                    elif abs(skewness) < 1.5:
                        dist_type = "심하게 치우친"
                        dist_desc = "강한 치우침을 보이는 분포를 보입니다."
                    else:
                        dist_type = "매우 심하게 치우친"
                        dist_desc = "매우 강한 치우침을 보이는 분포를 보입니다."
                    
                    # 분포 형태 분석 개선 - 종합적 판단으로 더 정확한 분류
                    # 1. 먼저 분포의 기본 형태를 판단 (정규분포, 이중분포, 극단분포 등)
                    
                    # 히스토그램으로 피크 분석 (분포 형태 판단용)
                    hist, bin_edges = np.histogram(data, bins=30)
                    max_freq = np.max(hist)
                    min_peak_height = max(max_freq * 0.25, 3)
                    
                    # 스무딩을 적용한 히스토그램으로 피크 감지
                    from scipy import ndimage
                    smoothed_hist = ndimage.gaussian_filter1d(hist.astype(float), sigma=1.0)
                    
                    peak_values = []
                    for i in range(1, len(smoothed_hist)-1):
                        if (smoothed_hist[i] > smoothed_hist[i-1] and smoothed_hist[i] > smoothed_hist[i+1] and 
                            smoothed_hist[i] >= min_peak_height and
                            smoothed_hist[i] - min(smoothed_hist[i-1], smoothed_hist[i+1]) >= max_freq * 0.05):
                            peak_values.append(bin_edges[i])
                    
                    # 피크 간 거리 분석
                    if len(peak_values) > 1:
                        peak_values.sort()
                        filtered_peaks = [peak_values[0]]
                        data_range = data.max() - data.min()
                        min_distance = data_range * 0.05
                        
                        for i in range(1, len(peak_values)):
                            if peak_values[i] - filtered_peaks[-1] >= min_distance:
                                filtered_peaks.append(peak_values[i])
                        peak_values = filtered_peaks
                    
                    # 2. 분포 형태 종합 판단
                    is_bimodal = False
                    is_multimodal = False
                    is_extreme = False
                    is_normal_like = False
                    
                    # 이중분포/다중분포 판단
                    if len(peak_values) >= 2:
                        # 두 피크 사이의 골짜기 깊이 확인
                        peak1_idx = np.argmin(np.abs(bin_edges - peak_values[0]))
                        peak2_idx = np.argmin(np.abs(bin_edges - peak_values[1]))
                        
                        if peak1_idx < peak2_idx:
                            valley_region = hist[peak1_idx:peak2_idx+1]
                            valley_min = np.min(valley_region)
                            valley_ratio = valley_min / max(hist[peak1_idx], hist[peak2_idx])
                            
                            if valley_ratio < 0.3:  # 골짜기가 깊음
                                if len(peak_values) == 2:
                                    is_bimodal = True
                                else:
                                    is_multimodal = True
                    
                    # 극단분포 판단
                    q25, q75 = data.quantile([0.25, 0.75])
                    lower_25_data = data[data <= q25]
                    upper_25_data = data[data >= q75]
                    middle_50_data = data[(data > q25) & (data < q75)]
                    
                    lower_ratio = len(lower_25_data) / len(data)
                    upper_ratio = len(upper_25_data) / len(data)
                    middle_ratio = len(middle_50_data) / len(data)
                    
                    # 0 근처 집중도
                    zero_threshold = data_range * 0.05
                    zero_concentration = len(data[data <= zero_threshold]) / len(data)
                    
                    # 극단분포 조건
                    if (lower_ratio >= 0.5 or upper_ratio >= 0.5 or zero_concentration >= 0.5 or 
                        middle_ratio < 0.3):
                        is_extreme = True
                    
                    # 정규분포 유사성 판단 (편향도 + 첨도 + 대칭성 종합)
                    mean_median_diff = abs(mean_val - median_val) / mean_val * 100 if mean_val != 0 else 0
                    
                    if (abs(skewness) < 0.3 and abs(kurtosis) < 0.5 and mean_median_diff < 5 and 
                        not is_bimodal and not is_multimodal and not is_extreme):
                        is_normal_like = True
                    
                    # 3. 분포 형태에 따른 설명 생성
                    if is_normal_like:
                        if abs(skewness) < 0.1:
                            dist_type = "거의 완벽한 정규분포"
                            dist_desc = "대칭적이고 균등한 분포를 보입니다."
                        else:
                            dist_type = "정규분포에 매우 가까운"
                            dist_desc = "약간의 비대칭이 있지만 거의 대칭적인 분포를 보입니다."
                    elif is_bimodal:
                        dist_type = "두개의 피크를 가진 이중분포"
                        dist_desc = "서로 다른 두 그룹의 데이터가 혼재되어 있습니다."
                    elif is_multimodal:
                        dist_type = f"{len(peak_values)}개의 피크를 가진 다중분포"
                        dist_desc = "여러 그룹의 데이터가 혼재되어 있습니다."
                    elif is_extreme:
                        if zero_concentration >= 0.5:
                            dist_type = "0 근처 집중분포"
                            dist_desc = "0 근처에 대부분의 데이터가 집중되어 있는 분포입니다."
                        elif lower_ratio >= 0.5:
                            dist_type = "하위 극단 집중분포"
                            dist_desc = "낮은 값 구간에 대부분의 데이터가 집중되어 있는 분포입니다."
                        elif upper_ratio >= 0.5:
                            dist_type = "상위 극단 집중분포"
                            dist_desc = "높은 값 구간에 대부분의 데이터가 집중되어 있는 분포입니다."
                        elif middle_ratio < 0.3:
                            dist_type = "양극단 분포"
                            dist_desc = "낮은 값과 높은 값 구간에 데이터가 집중되어 있고, 중간 구간에는 데이터가 적은 분포입니다."
                        else:
                            # 편향도 기반 분류
                            if abs(skewness) < 0.3:
                                dist_type = "약간 치우친"
                                dist_desc = "중간 정도의 치우침을 보이는 분포를 보입니다."
                            elif abs(skewness) < 0.7:
                                dist_type = "치우친"
                                dist_desc = "명확한 치우침을 보이는 분포를 보입니다."
                            elif abs(skewness) < 1.0:
                                dist_type = "심하게 치우친"
                                dist_desc = "강한 치우침을 보이는 분포를 보입니다."
                            else:
                                dist_type = "매우 심하게 치우친"
                                dist_desc = "매우 강한 치우침을 보이는 분포를 보입니다."
                    else:
                        # 일반적인 편향도 기반 분류
                        if abs(skewness) < 0.3:
                            dist_type = "대체로 대칭적인"
                            dist_desc = "약간의 비대칭이 있지만 대체로 대칭적인 분포를 보입니다."
                        elif abs(skewness) < 0.7:
                            dist_type = "약간 치우친"
                            dist_desc = "중간 정도의 치우침을 보이는 분포를 보입니다."
                        elif abs(skewness) < 1.0:
                            dist_type = "치우친"
                            dist_desc = "명확한 치우침을 보이는 분포를 보입니다."
                        elif abs(skewness) < 1.5:
                            dist_type = "심하게 치우친"
                            dist_desc = "강한 치우침을 보이는 분포를 보입니다."
                        else:
                            dist_type = "매우 심하게 치우친"
                            dist_desc = "매우 강한 치우침을 보이는 분포를 보입니다."
                    
                    # 편향 방향 분석 - 더 정확한 분포 쏠림 분석
                    # 분포의 실제 집중 구간을 분석하여 쏠림 방향 결정
                    q25, q50, q75 = data.quantile([0.25, 0.5, 0.75])
                    data_range = data.max() - data.min()
                    
                    # 하위 25% 구간과 상위 25% 구간의 데이터 밀도 비교
                    lower_25_data = data[data <= q25]
                    upper_25_data = data[data >= q75]
                    middle_50_data = data[(data > q25) & (data < q75)]
                    
                    # 각 구간의 데이터 비율
                    lower_ratio = len(lower_25_data) / len(data)
                    upper_ratio = len(upper_25_data) / len(data)
                    middle_ratio = len(middle_50_data) / len(data)
                    
                    # 분포의 쏠림 패턴 분석
                    if middle_ratio < 0.3:  # 중간 구간에 데이터가 30% 미만
                        if lower_ratio > upper_ratio * 1.5:  # 하위 구간이 상위 구간보다 1.5배 이상 많음
                            skew_direction = "낮은 값 쪽으로 쏠린"
                            skew_explanation = "낮은 값 구간에 데이터가 집중되어 있고, 중간 구간에는 데이터가 적은 분포"
                        elif upper_ratio > lower_ratio * 1.5:  # 상위 구간이 하위 구간보다 1.5배 이상 많음
                            skew_direction = "높은 값 쪽으로 쏠린"
                            skew_explanation = "높은 값 구간에 데이터가 집중되어 있고, 중간 구간에는 데이터가 적은 분포"
                        else:  # 양쪽 극단에 비슷하게 분포
                            skew_direction = "양극단에 쏠린"
                            skew_explanation = "낮은 값과 높은 값 구간에 데이터가 집중되어 있고, 중간 구간에는 데이터가 적은 분포"
                    elif skewness > 0.1:
                        skew_direction = "오른쪽으로 치우친"
                        skew_explanation = "낮은 값들이 많고 높은 값들이 적은 분포 (오른쪽에 긴 꼬리)"
                    elif skewness < -0.1:
                        skew_direction = "왼쪽으로 치우친"
                        skew_explanation = "높은 값들이 많고 낮은 값들이 적은 분포 (왼쪽에 긴 꼬리)"
                    else:
                        skew_direction = "대칭적"
                        skew_explanation = "왼쪽과 오른쪽이 균형잡힌 분포"
                    
                    # 첨도(Kurtosis) 분석 추가
                    if kurtosis < -0.5:
                        kurtosis_desc = "매우 평평한 분포 (platykurtic)"
                        kurtosis_explanation = "데이터가 평균 주변에 넓게 퍼져있어 분포가 평평함"
                    elif kurtosis < 0.5:
                        kurtosis_desc = "정상적인 첨도 (mesokurtic)"
                        kurtosis_explanation = "정규분포와 유사한 첨도를 가짐"
                    elif kurtosis < 2:
                        kurtosis_desc = "뾰족한 분포 (leptokurtic)"
                        kurtosis_explanation = "데이터가 평균 주변에 집중되어 분포가 뾰족함"
                    else:
                        kurtosis_desc = "매우 뾰족한 분포 (highly leptokurtic)"
                        kurtosis_explanation = "데이터가 평균 주변에 매우 집중되어 분포가 매우 뾰족함"
                    
                    # 분포의 집중도 분석 (더 세분화)
                    data_range = data.max() - data.min()
                    q1, q3 = data.quantile(0.25), data.quantile(0.75)
                    iqr = q3 - q1
                    
                    # 변동계수(CV) 계산 - 평균 대비 표준편차의 비율
                    cv = std_val / mean_val if mean_val != 0 else 0
                    
                    # 데이터가 특정 구간에 얼마나 집중되어 있는지 분석 (더 세분화)
                    concentration_25_75 = len(data[(data >= q1) & (data <= q3)]) / len(data) * 100
                    concentration_10_90 = len(data[(data >= data.quantile(0.1)) & (data <= data.quantile(0.9))]) / len(data) * 100
                    concentration_5_95 = len(data[(data >= data.quantile(0.05)) & (data <= data.quantile(0.95))]) / len(data) * 100
                    
                    if concentration_25_75 > 70:
                        concentration_desc = "매우 집중된"
                        concentration_explanation = "데이터의 75% 이상이 중간 50% 구간에 집중됨"
                    elif concentration_25_75 > 60:
                        concentration_desc = "집중된"
                        concentration_explanation = "데이터의 60-70%가 중간 50% 구간에 집중됨"
                    elif concentration_25_75 > 50:
                        concentration_desc = "보통 수준의 집중도"
                        concentration_explanation = "데이터의 50-60%가 중간 50% 구간에 집중됨"
                    else:
                        concentration_desc = "분산된"
                        concentration_explanation = "데이터가 넓은 범위에 고르게 분포됨"
                    
                    # 분포 설명 개선 - 분포 형태에 따른 적절한 설명
                    if is_normal_like:
                        # 정규분포 유사한 경우에만 "정규분포" 언급
                        distribution_analysis = f"{dist_type} {concentration_desc} 분포를 보입니다. {dist_desc}"
                    elif is_bimodal:
                        # 이중분포인 경우
                        distribution_analysis = f"{dist_type}로, {dist_desc}"
                    elif is_multimodal:
                        # 다중분포인 경우
                        distribution_analysis = f"{dist_type}로, {dist_desc}"
                    elif is_extreme:
                        # 극단분포인 경우 집중도보다는 분포 형태에 집중
                        distribution_analysis = f"{dist_type}로, {dist_desc}"
                    else:
                        # 일반적인 경우 편향도와 집중도 결합
                        if concentration_desc == "분산된":
                            distribution_analysis = f"{dist_type} 분포로, {skew_explanation}입니다."
                        else:
                            distribution_analysis = f"{dist_type} {concentration_desc} 분포로, {skew_explanation}입니다."
                    
                    # 극값 분석 (더 세분화)
                    lower_bound = q1 - 1.5 * iqr
                    upper_bound = q3 + 1.5 * iqr
                    outliers = data[(data < lower_bound) | (data > upper_bound)]
                    outlier_ratio = len(outliers) / len(data) * 100
                    
                    # 극값의 심각도 분석
                    extreme_outliers = data[(data < q1 - 3 * iqr) | (data > q3 + 3 * iqr)]
                    extreme_outlier_ratio = len(extreme_outliers) / len(data) * 100
                    
                    if outlier_ratio < 2:
                        outlier_desc = "극값이 거의 없는"
                        outlier_explanation = "데이터가 매우 안정적이고 극값이 거의 없습니다"
                    elif outlier_ratio < 5:
                        outlier_desc = "극값이 매우 적은"
                        outlier_explanation = "데이터가 안정적이고 극값이 매우 적습니다"
                    elif outlier_ratio < 10:
                        outlier_desc = "극값이 적은"
                        outlier_explanation = "데이터가 비교적 안정적이고 극값이 적습니다"
                    elif outlier_ratio < 20:
                        outlier_desc = "적당한 극값을 가진"
                        outlier_explanation = "일부 극값이 있지만 관리 가능한 수준입니다"
                    else:
                        outlier_desc = "많은 극값을 가진"
                        outlier_explanation = "상당한 수의 극값이 있어 주의가 필요합니다"
                    
                    # 데이터 범위 분석 (더 세분화)
                    if cv < 0.05:
                        range_desc = "매우 좁은 범위에 집중된"
                        range_explanation = "데이터가 매우 좁은 범위에 집중되어 있습니다."
                    elif cv < 0.1:
                        range_desc = "좁은 범위에 집중된"
                        range_explanation = "데이터가 좁은 범위에 집중되어 있습니다."
                    elif cv < 0.2:
                        range_desc = "적당한 범위에 분포된"
                        range_explanation = "데이터가 적당한 범위에 분포되어 있습니다."
                    elif cv < 0.5:
                        range_desc = "넓은 범위에 분포된"
                        range_explanation = "데이터가 넓은 범위에 분포되어 있습니다."
                    else:
                        range_desc = "매우 넓은 범위에 분포된"
                        range_explanation = "데이터가 매우 넓은 범위에 분포되어 있습니다."
                    
                    # 분산 설명 개선 - 분포 형태에 따른 적절한 설명
                    if is_bimodal or is_multimodal:
                        # 이중/다중분포인 경우 각 그룹별 분포 분석
                        group_analyses = []
                        
                        if len(peak_values) >= 2:
                            # 각 피크 주변의 데이터를 그룹으로 분리
                            for i, peak in enumerate(peak_values):
                                # 피크 주변 ±10% 구간의 데이터 추출
                                peak_range = data_range * 0.1
                                group_data = data[(data >= peak - peak_range) & (data <= peak + peak_range)]
                                 
                        # 전체 분산 설명 (이중분포 특성 반영)
                        if len(group_analyses) >= 2:
                            variance_desc = f"데이터가 {len(peak_values)}개의 그룹으로 나뉘어 있습니다. "
                            variance_desc += "; ".join(group_analyses) + ". "
                            variance_explanation = "각 그룹 내에서는 상대적으로 일관된 패턴을 보이지만, 그룹 간에는 명확한 차이가 있습니다"
                        else:
                            variance_desc = f"데이터 값들이 평균 주변에서 넓게 퍼져있습니다."
                            variance_explanation = "데이터의 변동성이 커서 다양한 패턴을 보입니다"
                    
                    elif is_extreme:
                        # 극단분포인 경우
                        if zero_concentration >= 0.5:
                            variance_desc = f"데이터가 0 근처에 집중되어 있습니다."
                            variance_explanation = "대부분의 데이터가 0 근처에 집중되어 있어 변동성이 제한적입니다"
                        elif lower_ratio >= 0.5:
                            variance_desc = f"데이터가 낮은 값 구간에 집중되어 있습니다."
                            variance_explanation = "대부분의 데이터가 낮은 값 구간에 집중되어 있어 변동성이 제한적입니다"
                        elif upper_ratio >= 0.5:
                            variance_desc = f"데이터가 높은 값 구간에 집중되어 있습니다."
                            variance_explanation = "대부분의 데이터가 높은 값 구간에 집중되어 있어 변동성이 제한적입니다"
                        else:
                            variance_desc = f"데이터가 양극단에 집중되어 있습니다."
                            variance_explanation = "데이터가 양극단에 집중되어 있어 중간 구간에는 데이터가 적습니다"
                    
                    else:
                        # 일반적인 분포인 경우 (기존 로직 유지)
                        if cv < 0.1:
                            variance_desc = f"데이터 값들이 평균 주변에 매우 촘촘하게 모여있습니다."
                            variance_explanation = "데이터의 변동성이 매우 작아 일관된 패턴을 보입니다"
                        elif cv < 0.3:
                            variance_desc = f"데이터 값들이 평균 주변에 비교적 일정하게 분포됩니다."
                            variance_explanation = "데이터의 변동성이 적당하여 안정적인 패턴을 보입니다"
                        elif cv < 0.5:
                            variance_desc = f"데이터 값들이 평균 주변에서 적당한 폭으로 퍼져있습니다."
                            variance_explanation = "데이터의 변동성이 보통 수준으로 다양한 패턴을 보입니다"
                        else:
                            variance_desc = f"데이터 값들이 평균 주변에서 넓게 퍼져있습니다."
                            variance_explanation = "데이터의 변동성이 커서 다양한 패턴을 보입니다"
                    
                    # 분포의 대칭성 분석 추가
                    mean_median_diff = abs(mean_val - median_val) / mean_val * 100 if mean_val != 0 else 0
                    if mean_median_diff < 2:
                        symmetry_desc = "거의 완벽한 대칭"
                        symmetry_explanation = "평균과 중앙값이 거의 같아 대칭적임"
                    elif mean_median_diff < 5:
                        symmetry_desc = "대체로 대칭"
                        symmetry_explanation = "평균과 중앙값이 비슷하여 대체로 대칭적임"
                    elif mean_median_diff < 10:
                        symmetry_desc = "약간 비대칭"
                        symmetry_explanation = "평균과 중앙값에 차이가 있어 약간 비대칭임"
                    else:
                        symmetry_desc = "명확한 비대칭"
                        symmetry_explanation = "평균과 중앙값에 큰 차이가 있어 명확히 비대칭임"
                    
                    # 그룹 분석 개선 - 더 정교한 수학적 접근
                    hist, bin_edges = np.histogram(data, bins=30)
                    
                    # 1. 피크 감지 개선 - 더 유연한 기준 적용 (3개 그룹도 인식하도록)
                    peak_values = []
                    max_freq = np.max(hist)
                    min_peak_height = max(max_freq * 0.25, 3)  # 최소 피크 높이를 낮춤 (25% 또는 최소 3개)
                    
                    # 스무딩을 적용한 히스토그램으로 피크 감지 개선
                    from scipy import ndimage
                    smoothed_hist = ndimage.gaussian_filter1d(hist.astype(float), sigma=1.0)
                    
                    for i in range(1, len(smoothed_hist)-1):
                        # 피크 조건: 양쪽보다 높고, 최소 높이 이상, 그리고 주변과 충분한 차이
                        if (smoothed_hist[i] > smoothed_hist[i-1] and smoothed_hist[i] > smoothed_hist[i+1] and 
                            smoothed_hist[i] >= min_peak_height and
                            smoothed_hist[i] - min(smoothed_hist[i-1], smoothed_hist[i+1]) >= max_freq * 0.05):  # 차이 기준 완화
                            peak_values.append(bin_edges[i])
                    
                    # 2. 피크 간 거리 분석 - 더 유연한 거리 기준
                    if len(peak_values) > 1:
                        peak_values.sort()
                        filtered_peaks = [peak_values[0]]  # 첫 번째 피크는 항상 포함
                        
                        for i in range(1, len(peak_values)):
                            # 이전 피크와의 거리가 전체 범위의 5% 이상인 경우만 포함 (기존 10%에서 완화)
                            data_range = data.max() - data.min()
                            min_distance = data_range * 0.05
                            
                            if peak_values[i] - filtered_peaks[-1] >= min_distance:
                                filtered_peaks.append(peak_values[i])
                        
                        peak_values = filtered_peaks
                    
                    # 3. 추가 피크 검증 - 실제 데이터 분포와 비교
                    if len(peak_values) >= 2:
                        # 각 피크 주변의 실제 데이터 밀도 확인
                        validated_peaks = []
                        for peak in peak_values:
                            # 피크 주변 ±5% 구간의 데이터 비율 계산
                            peak_range = data_range * 0.1
                            nearby_data = data[(data >= peak - peak_range) & (data <= peak + peak_range)]
                            if len(nearby_data) >= len(data) * 0.05:  # 전체 데이터의 5% 이상
                                validated_peaks.append(peak)
                        
                        if len(validated_peaks) >= 2:
                            peak_values = validated_peaks
                    
                    # 4. 분포의 이중성(dip) 분석 - 두 개의 명확한 그룹이 있는지 확인
                    bimodal_score = 0
                    if len(peak_values) >= 2:
                        # 두 피크 사이의 최소값 찾기
                        peak1_idx = np.argmin(np.abs(bin_edges - peak_values[0]))
                        peak2_idx = np.argmin(np.abs(bin_edges - peak_values[1]))
                        
                        if peak1_idx < peak2_idx:
                            valley_region = hist[peak1_idx:peak2_idx+1]
                            valley_min = np.min(valley_region)
                            valley_ratio = valley_min / max(hist[peak1_idx], hist[peak2_idx])
                            
                            # 골짜기가 깊을수록 이중 분포 가능성 높음
                            if valley_ratio < 0.3:  # 골짜기가 최고점의 30% 미만
                                bimodal_score = 1
                    
                    # 5. 극단값 집중도 분석 - 0 근처나 최대값 근처에 집중된 데이터 (개선)
                    extreme_concentration = 0
                    data_range = data.max() - data.min()
                    
                    # 하위 20% 구간의 데이터 비율
                    lower_20_percent = data.quantile(0.2)
                    lower_ratio = len(data[data <= lower_20_percent]) / len(data)
                    
                    # 상위 20% 구간의 데이터 비율  
                    upper_20_percent = data.quantile(0.8)
                    upper_ratio = len(data[data >= upper_20_percent]) / len(data)
                    
                    # 0 근처 집중도 (데이터 범위의 5% 이내)
                    zero_threshold = data_range * 0.05
                    zero_concentration = len(data[data <= zero_threshold]) / len(data)
                    
                    # 한쪽 극단에 50% 이상 집중된 경우 (기존 60%에서 완화)
                    if lower_ratio >= 0.5 or upper_ratio >= 0.5 or zero_concentration >= 0.5:
                        extreme_concentration = 1
                    
                    # 6. 편향도 기반 극단적 분포 감지 추가
                    skewness_based_extreme = 0
                    if abs(skewness) > 1.5:  # 강한 편향
                        if skewness > 0:  # 오른쪽 편향
                            # 상위 30% 구간의 집중도
                            upper_30_percent = data.quantile(0.7)
                            upper_30_ratio = len(data[data >= upper_30_percent]) / len(data)
                            if upper_30_ratio >= 0.4:  # 상위 30%에 40% 이상 집중
                                skewness_based_extreme = 1
                        else:  # 왼쪽 편향
                            # 하위 30% 구간의 집중도
                            lower_30_percent = data.quantile(0.3)
                            lower_30_ratio = len(data[data <= lower_30_percent]) / len(data)
                            if lower_30_ratio >= 0.4:  # 하위 30%에 40% 이상 집중
                                skewness_based_extreme = 1
                    
                    # 7. 그룹 설명 생성 - 더 정확한 판단 (기준 완화)
                    if len(peak_values) >= 2 and (bimodal_score == 1 or extreme_concentration == 1 or skewness_based_extreme == 1):
                        # 2개 이상의 그룹이 감지된 경우
                        group_centers = []
                        for peak in peak_values:
                            if peak >= 1000:
                                group_centers.append(f"{peak:,.0f}")
                            else:
                                group_centers.append(f"{peak:.1f}")
                        
                        group_desc = f"{len(peak_values)}개의 그룹(대푯값: {', '.join(group_centers)})으로 나뉘어 있으며, 이는 한가지 변수 안에 서로 다른 {len(peak_values)}개의 운전/운영 상황이 내재되어 있음을 의미할 수 있습니다."
                    
                    elif extreme_concentration == 1 or skewness_based_extreme == 1:
                        # 극단적 집중도나 편향도 기반으로 2개 그룹 감지
                        if zero_concentration >= 0.5:
                            # 0 근처 집중 + 나머지 분포
                            group_desc = f"0 근처에 집중된 {zero_concentration*100:.0f}%의 그룹과 나머지 분포 그룹으로 나뉘어 있으며, 이는 한가지 변수 안에 서로 다른 2개의 운전/운영 상황이 내재되어 있음을 의미할 수 있습니다."
                        elif lower_ratio >= 0.5:
                            # 하위 극단 집중
                            group_desc = f"하위 극단에 집중된 {lower_ratio*100:.0f}%의 그룹과 나머지 분포 그룹으로 나뉘어 있으며, 이는 한가지 변수 안에 서로 다른 2개의 운전/운영 상황이 내재되어 있음을 의미할 수 있습니다."
                        elif upper_ratio >= 0.5:
                            # 상위 극단 집중
                            group_desc = f"상위 극단에 집중된 {upper_ratio*100:.0f}%의 그룹과 나머지 분포 그룹으로 나뉘어 있으며, 이는 한가지 변수 안에 서로 다른 2개의 운전/운영 상황이 내재되어 있음을 의미할 수 있습니다."
                        else:
                            # 편향도 기반 그룹
                            group_desc = f"편향된 방향에 집중된 그룹과 나머지 분포 그룹으로 나뉘어 있으며, 이는 한가지 변수 안에 서로 다른 2개의 운전/운영 상황이 내재되어 있음을 의미할 수 있습니다."
                    
                    else:
                        # 단일 그룹 또는 불명확한 분리
                        group_desc = "단일 그룹으로 구성되어 있습니다."
                    
                    # 분석 적합도 점수 계산 (0-100점) - 감점 기준 완화
                    suitability_score = 100
                    penalty_reasons = []  # 감점 요인 저장
                    
                    # 편향도 감점 (기준 완화, 5점 단위)
                    if abs(skewness) > 1.5:  # 기존 1.0에서 1.5로 완화
                        penalty = 15  # 기존 20에서 15로 완화
                        suitability_score -= penalty
                        penalty_reasons.append(f"-{penalty}점: 분포가 심하게 치우쳐 있음 (편향도: {skewness:.2f})")
                    elif abs(skewness) > 0.8:  # 기존 0.5에서 0.8로 완화
                        penalty = 10  # 기존 8에서 10으로 조정 (5점 단위)
                        suitability_score -= penalty
                        penalty_reasons.append(f"-{penalty}점: 분포가 약간 치우쳐 있음 (편향도: {skewness:.2f})")
                    
                    # 극값 비율 감점 (기준 완화, 5점 단위)
                    if outlier_ratio > 30:  # 기존 20에서 30으로 완화
                        penalty = 20  # 기존 25에서 20으로 완화
                        suitability_score -= penalty
                        penalty_reasons.append(f"-{penalty}점: 극값이 매우 많음 ({outlier_ratio:.1f}%)")
                    elif outlier_ratio > 15:  # 기존 10에서 15로 완화
                        penalty = 15  # 기존 12에서 15로 조정 (5점 단위)
                        suitability_score -= penalty
                        penalty_reasons.append(f"-{penalty}점: 극값이 많음 ({outlier_ratio:.1f}%)")
                    elif outlier_ratio > 8:  # 기존 5에서 8로 완화
                        penalty = 5  # 기존 4에서 5로 조정 (5점 단위)
                        suitability_score -= penalty
                        penalty_reasons.append(f"-{penalty}점: 극값이 약간 있음 ({outlier_ratio:.1f}%)")
                    
                    # 변동계수 감점 (기준 완화, 5점 단위)
                    if cv < 0.02:  # 기존 0.05에서 0.02로 완화
                        penalty = 15  # 기존 20에서 15로 완화
                        suitability_score -= penalty
                        penalty_reasons.append(f"-{penalty}점: 데이터 변동이 너무 적음 (CV: {cv:.3f})")
                    elif cv < 0.05:  # 기존 0.1에서 0.05로 완화
                        penalty = 10  # 기존 8에서 10으로 조정 (5점 단위)
                        suitability_score -= penalty
                        penalty_reasons.append(f"-{penalty}점: 데이터 변동이 적음 (CV: {cv:.3f})")
                    elif cv > 3:  # 기존 2에서 3으로 완화
                        penalty = 15  # 기존 12에서 15로 조정 (5점 단위)
                        suitability_score -= penalty
                        penalty_reasons.append(f"-{penalty}점: 데이터 변동이 너무 큼 (CV: {cv:.3f})")
                    
                    # 극단적 분포에 대한 감점 추가 (기준 완화)
                    is_extreme, max_ratio, second_ratio, valley_ratio = detect_extreme_distribution(data)

                    if is_extreme:
                        penalty = 25  # 기존 30에서 25로 완화
                        suitability_score -= penalty
                        penalty_reasons.append(f"-{penalty}점: 극단적으로 분리된 분포 (주요 피크: {max_ratio*100:.1f}%, 부차 피크: {second_ratio*100:.1f}%)")
                    
                    # 점수에 따른 적합도 판단 및 데이터 변환 안내
                    if suitability_score >= 90:
                        analysis_suitability = "상관관계 분석에 매우 적합한 데이터입니다."
                    elif suitability_score >= 80:
                        analysis_suitability = "상관관계 분석에 적합한 데이터입니다."
                    elif suitability_score >= 70:
                        analysis_suitability = "약간의 전처리를 수행하면 상관관계 분석에 더 유리합니다."
                    elif suitability_score >= 60:
                        analysis_suitability = "적극적인 전처리 후 상관관계를 분석하는 것을 권장합니다."
                    else:
                        analysis_suitability = "상관관계 분석에 어려움이 있을 수 있어 주의가 필요합니다. 적극적인 전처리 혹은 이상치를 제거한 후 상관관계를 분석하는 것을 권장합니다."
                    
                    # 데이터 변환 안내 추가 - 점수 구간별 세분화
                    if suitability_score >= 90:
                        data_transform_guide = ""
                    elif suitability_score >= 80:
                        data_transform_guide = ""
                    elif suitability_score >= 70:
                        data_transform_guide = f"\n\n**🔧 전처리 방안 (선택 권장)**: \n정규화 전처리를 적용한 후 분석을 수행하면 정확도가 개선될 수 있습니다."
                    elif suitability_score >= 60:
                        data_transform_guide = f"\n\n**🔧 전처리 방안 (선택 권장)**: \n정규화/로그변환/제곱근변환 등 적극적인 전처리를 적용한 후 분석을 수행하면 정확도가 개선될 수 있습니다."
                    else:
                        data_transform_guide = f"\n\n**🔧 전처리 방안 (강력 권장)**: \n상관관계 분석에 어려움이 있을 수 있어 주의가 필요한 변수입니다. 정규화/로그변환/제곱근변환/이상치제거 등 적극적인 전처리를 적용한 후 분석을 수행하면 정확도가 개선됩니다."
                    
                    # 개선 방안 생성 (긍정적 워딩으로 변경) - 점수 조정
                    improvement_suggestions = []
                    if penalty_reasons:
                        for reason in penalty_reasons:
                            if "편향도" in reason:
                                if "심하게" in reason:  # -15점 감점
                                    improvement_suggestions.append(" 분포 정규화 조치 +15점")
                                else:  # -10점 감점
                                    improvement_suggestions.append(" 분포 정규화 조치 +10점")
                            elif "극값" in reason:
                                if "매우 많음" in reason:  # -20점 감점
                                    improvement_suggestions.append(" 극값 처리 조치 +20점")
                                elif "많음" in reason:  # -15점 감점
                                    improvement_suggestions.append(" 극값 처리 조치 +15점")
                                else:  # -5점 감점
                                    improvement_suggestions.append(" 극값 처리 조치 +5점")
                            elif "변동" in reason:
                                if "너무 적음" in reason or "너무 큼" in reason:  # -15점 감점
                                    improvement_suggestions.append(" 데이터 정규화 조치 +15점")
                                else:  # -10점 감점
                                    improvement_suggestions.append(" 데이터 정규화 조치 +10점")
                            elif "그룹" in reason:  # -25점 감점
                                improvement_suggestions.append(" 그룹별 분석 조치 +25점")
                    
                    improvement_text = ""
                    if improvement_suggestions:
                        improvement_text = f"\n\n**✨ 분석 적합도 개선 방안**:\n{', '.join(improvement_suggestions)}"
                    
                    narrative = f"**💡 분석 적합도**: {suitability_score:.0f}점 - {analysis_suitability}\n\n**📊 분포 특성 분석**:\n평균은 **{mean_str}**이며 {variance_desc} {distribution_analysis}\n\n**📈 데이터 그룹**:\n{group_desc}{improvement_text}{data_transform_guide}"
                    
                    st.write(narrative)
                elif not is_numeric:
                    # 범주형 변수 나레이션
                    raw_series = df_ready[col].dropna()
                    
                    if len(raw_series) > 0:
                        # 범주별 카운트 계산 및 이름 오름차순 정렬
                        category_counts = raw_series.value_counts()
                        category_counts = category_counts.sort_index()  # 범주 이름 오름차순
                        
                        # 빈도를 퍼센트로 변환
                        category_percentages = (category_counts / len(raw_series)) * 100
                        
                        # 총 범주 개수
                        total_categories = len(category_percentages)
                        
                        # 상위 분포 범주 찾기 (빈도 기준)
                        top_categories = category_percentages.sort_values(ascending=False)
                        
                        # 분포 특성 분석
                        # 1. 가장 많은 범주 3개
                        top_3 = []
                        for i, (cat, pct) in enumerate(top_categories.head(3).items()):
                            if pct >= 100:
                                pct_str = f"{pct:,.0f}"
                            else:
                                pct_str = f"{pct:.1f}"
                            top_3.append(f"'{cat}' ({pct_str}%)")
                        
                        # 2. 분포 형태 분석
                        # 집중도 분석
                        top1_pct = top_categories.iloc[0]
                        top2_pct = top_categories.iloc[1] if len(top_categories) > 1 else 0
                        top3_pct = top_categories.iloc[2] if len(top_categories) > 2 else 0
                        
                        # 상위 3개 범주의 누적 비율
                        top3_cumulative = top1_pct + top2_pct + top3_pct
                        
                        # 분포 형태 판단
                        if top1_pct >= 70:
                            distribution_type = "극도로 집중된 분포"
                            distribution_desc = f"전체 데이터의 대부분({top1_pct:.1f}%)이 '{top_categories.index[0]}' 범주에 집중"
                        elif top1_pct >= 50:
                            distribution_type = "매우 집중된 분포"
                            distribution_desc = f"전체 데이터의 절반 이상({top1_pct:.1f}%)이 '{top_categories.index[0]}' 범주에 집중"
                        elif top3_cumulative >= 80 and len(top_categories) >= 3:
                            distribution_type = "상위 범주 집중 분포"
                            top3_names = "', '".join([str(c) for c in top_categories.head(3).index])
                            distribution_desc = f"상위 3개 범주('{top3_names}')에 전체 데이터의 {top3_cumulative:.1f}%가 집중"
                        elif top1_pct >= 30:
                            distribution_type = "약간 치우친 분포"
                            distribution_desc = f"'{top_categories.index[0]}' 범주에 {top1_pct:.1f}%가 분포하며, 나머지 범주들에도 고르게 분산"
                        else:
                            distribution_type = "균등한 분포"
                            distribution_desc = f"전체 {total_categories}개 범주에 비교적 고르게 분포"
                        
                        # 3. 희소 범주 분석 (5% 미만)
                        sparse_categories = category_percentages[category_percentages < 5]
                        sparse_ratio = len(sparse_categories) / total_categories * 100 if total_categories > 0 else 0
                        
                        if len(sparse_categories) > 0:
                            sparse_desc = f"전체 {total_categories}개 범주 중 {len(sparse_categories)}개({sparse_ratio:.0f}%)가 5% 미만의 적은 데이터를 포함하고 있어, 이들 범주는 분석 시 신뢰도가 낮을 수 있습니다."
                        else:
                            sparse_desc = f"모든 범주가 5% 이상의 데이터를 포함하고 있어 범주별 분석 신뢰도가 높습니다."
                        
                        # 4. 범주 다양성 분석
                        if total_categories <= 3:
                            diversity_desc = f"총 {total_categories}개의 범주로 구성된 단순한 범주형 변수입니다."
                        elif total_categories <= 7:
                            diversity_desc = f"총 {total_categories}개의 범주로 구성되어 있으며, 적절한 다양성을 가진 변수입니다."
                        elif total_categories <= 15:
                            diversity_desc = f"총 {total_categories}개의 범주로 구성되어 있으며, 비교적 많은 범주를 포함하는 변수입니다."
                        else:
                            diversity_desc = f"총 {total_categories}개의 범주로 구성되어 있으며, 매우 많은 범주를 포함하는 변수입니다."
                        
                        # 최종 나레이션 구성
                        narrative = f"**📊 분포 특성 분석**: {sparse_desc} {diversity_desc}\n\n**📈 분포 형태**: {distribution_type}입니다. {distribution_desc}되어 있습니다. {', '.join(top_3)} 순으로 데이터가 많이 분포되어 있습니다."
                        
                        st.write(narrative)
                    else:
                        st.warning(f"{col} 변수에 유효한 데이터가 없습니다.")
                else:
                    st.warning(f"{col} 변수에 유효한 데이터가 없습니다.")
            
            # 마지막 변수가 아닌 경우에만 구분선 표시
            if idx < len(all_cols) - 1:
                st.markdown("---")  # 변수 간 구분선
    
    else:
        st.info("분석할 변수가 없습니다.") 
   
