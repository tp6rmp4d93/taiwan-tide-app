import streamlit as st
import pandas as pd
import datetime
import holidays

# 網頁標題與設定
st.set_page_config(page_title="台灣潮汐進階查詢系統", layout="wide")
st.title("🌊 台灣沿海測站潮汐查詢系統 (2026年預報)")

# 取得 2026 年台灣國定假日清單
tw_holidays = holidays.country_holidays('TW', years=2026)

# 1. 讀取並快取資料
@st.cache_data
def load_and_process_data():
    df = pd.read_csv('F-A0023-001.csv')
    
    # 時間與日期處理
    df['obsTime'] = pd.to_datetime(df['obsTime'])
    df['月份'] = df['obsTime'].dt.month
    df['日期'] = df['obsTime'].dt.strftime('%Y-%m-%d')
    df['小時'] = df['obsTime'].dt.hour
    df['時間'] = df['obsTime'].dt.strftime('%H:%M')
    
    # 增加星期
    weekday_map = {0: '週一', 1: '週二', 2: '週三', 3: '週四', 4: '週五', 5: '週六', 6: '週日'}
    df['星期'] = df['obsTime'].dt.weekday.map(weekday_map)
    
    # 這次我們保留所有資料 (包含 H 和 L)，以供使用者自由切換
    return df

try:
    df_processed = load_and_process_data()
except FileNotFoundError:
    st.error("找不到 `F-A0023-001.csv`，請確保檔案路徑正確。")
    st.stop()

# 2. 建立側邊欄篩選器 (Sidebar)
st.sidebar.header("🔍 進階查詢條件")

# 測站選擇
stations = df_processed['locationName'].unique().tolist()
selected_stations = st.sidebar.multiselect("📍 選擇潮汐站", stations, default=["淡水", "花蓮"]) 

# 月份選擇
st.sidebar.markdown("**📅 選擇月份**")
col1, col2, col3, col4 = st.sidebar.columns(4)
selected_months = []
for m in range(1, 13):
    with [col1, col2, col3, col4][(m-1) % 4]:
        if st.checkbox(f"{m}月", value=True):
            selected_months.append(m)

# 時間區段選擇 (Slide bar)
st.sidebar.markdown("**☀️/🌙 選擇時間區間 (小時)**")
start_hour, end_hour = st.sidebar.slider(
    "設定區間：", 
    min_value=0, max_value=24, 
    value=(7, 18),
    step=1
)

# ----------------- 新增：高/低潮類型切換與門檻值動態設定 -----------------
st.sidebar.markdown("**📉/📈 潮位門檻值設定**")
tide_filter_type = st.sidebar.radio("選擇篩選潮位類型：", ["高潮 (H)", "低潮 (L)"])

# 根據選擇的類型，動態改變輸入框的預設值與提示文字
if tide_filter_type == "高潮 (H)":
    threshold = st.sidebar.number_input("輸入高潮門檻值 (將篩選「大於」此數值)：", value=100, step=10)
    hl_mask = 'H'
else:
    threshold = st.sidebar.number_input("輸入低潮門檻值 (將篩選「小於」此數值)：", value=-100, step=10)
    hl_mask = 'L'
# ------------------------------------------------------------------------

# 3. 根據篩選器過濾資料
# 先過濾基本條件 (測站、月份、時間、高低潮標記)
filtered_df = df_processed[
    (df_processed['locationName'].isin(selected_stations)) &
    (df_processed['月份'].isin(selected_months)) &
    (df_processed['小時'] >= start_hour) &
    (df_processed['小時'] <= end_hour) &
    (df_processed['高低潮'] == hl_mask)
]

# 再根據使用者選擇的高/低潮，套用對應的「大於」或「小於」門檻邏輯
if tide_filter_type == "高潮 (H)":
    filtered_df = filtered_df[filtered_df['潮高(當地)'] > threshold]
else:
    filtered_df = filtered_df[filtered_df['潮高(當地)'] < threshold]

# 4. 準備顯示結果
st.subheader(f"📊 查詢結果 (共 {len(filtered_df)} 筆符合條件)")

if len(filtered_df) > 0:
    def highlight_holidays(row):
        date_obj = datetime.datetime.strptime(row['日期'], '%Y-%m-%d').date()
        if row['星期'] in ['週六', '週日'] or date_obj in tw_holidays:
            return ['background-color: rgba(255, 182, 193, 0.3)'] * len(row)
        else:
            return [''] * len(row)

    if selected_stations:
        tabs = st.tabs(selected_stations)
        for idx, tab in enumerate(tabs):
            station_name = selected_stations[idx]
            with tab:
                station_df = filtered_df[filtered_df['locationName'] == station_name]
                if len(station_df) > 0:
                    # 為了方便辨識，在表格中顯示出該筆資料是 H 還是 L
                    display_df = station_df[['日期', '星期', '時間', '高低潮', '潮高(當地)']].copy()
                    styled_df = display_df.style.apply(highlight_holidays, axis=1)
                    st.dataframe(styled_df, use_container_width=True, hide_index=True)
                else:
                    st.info(f"{station_name} 在此條件下查無資料。")
    else:
        st.warning("請在左側選單選擇至少一個測站。")
else:
    st.warning("查無符合條件的資料，請嘗試放寬時間區間、月份，或調整門檻值。")

st.info("💡 **顏色說明**：有**底色標記**之日期代表為週末（週六/週日）或 2026 年台灣國定假日。")
