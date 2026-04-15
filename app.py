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
    
    # 只保留低潮資料 (L)
    low_tide_df = df[df['高低潮'] == 'L'].copy()
    
    return low_tide_df

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

# 月份選擇 (改為純勾選群組)
st.sidebar.markdown("**📅 選擇月份**")
# 使用 columns 排版，讓月份勾選框不會拉得太長
col1, col2, col3, col4 = st.sidebar.columns(4)
selected_months = []
for m in range(1, 13):
    # 依序分配到四個欄位
    with [col1, col2, col3, col4][(m-1) % 4]:
        if st.checkbox(f"{m}月", value=True): # 預設全勾
            selected_months.append(m)

# 時間區段選擇 (Slide bar)
st.sidebar.markdown("**☀️/🌙 選擇時間區間 (小時)**")
start_hour, end_hour = st.sidebar.slider(
    "設定區間：", 
    min_value=0, max_value=24, 
    value=(7, 18), # 預設 7~18
    step=1
)

# 潮位等級門檻值 (Textbox)
st.sidebar.markdown("**📉 低潮門檻值設定**")
threshold = st.sidebar.number_input(
    "請輸入數值 (例如 -100)：", 
    value=-100, 
    step=10
)

# 3. 根據篩選器過濾資料
filtered_df = df_processed[
    (df_processed['locationName'].isin(selected_stations)) &
    (df_processed['月份'].isin(selected_months)) &
    (df_processed['小時'] >= start_hour) &
    (df_processed['小時'] <= end_hour) &
    (df_processed['潮高(當地)'] < threshold) # 潮高低於輸入的門檻值
]

# 4. 準備顯示結果
st.subheader(f"📊 查詢結果 (共 {len(filtered_df)} 筆符合條件)")

if len(filtered_df) > 0:
    # 定義顏色標記函數 (標記週末與國定假日)
    def highlight_holidays(row):
        date_obj = datetime.datetime.strptime(row['日期'], '%Y-%m-%d').date()
        # 判斷是否為週六、週日，或是台灣國定假日
        if row['星期'] in ['週六', '週日'] or date_obj in tw_holidays:
            # 假日整列標記為淺粉橘色 (您可以自己更改色碼)
            return ['background-color: rgba(255, 182, 193, 0.3)'] * len(row)
        else:
            return [''] * len(row)

    # 如果有選取測站，則產生分頁 (Tabs)
    if selected_stations:
        # 動態建立與測站數量相同的分頁
        tabs = st.tabs(selected_stations)
        
        for idx, tab in enumerate(tabs):
            station_name = selected_stations[idx]
            with tab:
                # 抓出該測站的資料
                station_df = filtered_df[filtered_df['locationName'] == station_name]
                
                if len(station_df) > 0:
                    # 整理要顯示的特定欄位
                    display_df = station_df[['日期', '星期', '時間', '潮高(當地)']].copy()
                    
                    # 套用 Pandas Styler 進行顏色渲染，並隱藏 Index
                    styled_df = display_df.style.apply(highlight_holidays, axis=1)
                    
                    # 顯示資料表
                    st.dataframe(styled_df, use_container_width=True, hide_index=True)
                else:
                    st.info(f"{station_name} 在此條件下查無資料。")
    else:
        st.warning("請在左側選單選擇至少一個測站。")
else:
    st.warning("查無符合條件的資料，請嘗試放寬時間區間、月份，或調高門檻值。")

# 補充說明
st.info("💡 **顏色說明**：有**底色標記**之日期代表為週末（週六/週日）或 2026 年台灣國定假日。")
