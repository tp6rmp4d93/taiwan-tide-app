import streamlit as st
import pandas as pd

# 網頁標題與設定
st.set_page_config(page_title="台灣潮汐查詢系統", layout="wide")
st.title("🌊 台灣沿海測站潮汐查詢系統 (2026年預報)")
st.markdown("本網頁依據氣象署預報資料，提供各測站的潮汐查詢，並自動計算**低潮位**與**較低潮位(最低25%)**。")

# 1. 讀取並快取資料 (避免每次選擇都重新讀取)
@st.cache_data
def load_and_process_data():
    df = pd.read_csv('F-A0023-001.csv')
    
    # 時間與日期處理
    df['obsTime'] = pd.to_datetime(df['obsTime'])
    df['月份'] = df['obsTime'].dt.month
    df['日期'] = df['obsTime'].dt.strftime('%Y-%m-%d')
    
    # 增加星期
    weekday_map = {0: '週一', 1: '週二', 2: '週三', 3: '週四', 4: '週五', 5: '週六', 6: '週日'}
    df['星期'] = df['obsTime'].dt.weekday.map(weekday_map)
    df['時間 (時:分)'] = df['obsTime'].dt.strftime('%H:%M')
    
    # 日夜區段判斷 (假設 06:00-17:59 為白天)
    df['時間區段'] = df['obsTime'].dt.hour.apply(lambda x: '白天' if 6 <= x < 18 else '夜晚')
    
    # 計算低潮指標
    low_tide_df = df[df['高低潮'] == 'L'].copy()
    stats = low_tide_df.groupby('locationName')['潮高(當地)'].agg(['mean', lambda x: x.quantile(0.25)]).reset_index()
    stats.columns = ['locationName', '平均低潮位', '較低潮位門檻']
    low_tide_df = low_tide_df.merge(stats, on='locationName', how='left')
    
    # 標記潮位等級
    def classify_tide(row):
        if row['潮高(當地)'] <= row['較低潮位門檻']:
            return '較低潮位 (最低25%)'
        elif row['潮高(當地)'] < row['平均低潮位']:
            return '低潮位 (低於平均)'
        else:
            return '一般低潮'
            
    low_tide_df['潮位等級'] = low_tide_df.apply(classify_tide, axis=1)
    
    # 整理最終要顯示的欄位
    final_df = low_tide_df[['locationName', '月份', '日期', '星期', '時間 (時:分)', '時間區段', '潮高(當地)', '潮位等級', '平均低潮位']]
    return final_df

# 載入資料
try:
    df_processed = load_and_process_data()
except FileNotFoundError:
    st.error("找不到 `F-A0023-001.csv`，請確保檔案放在與 app.py 相同的資料夾。")
    st.stop()

# 2. 建立側邊欄篩選器 (Sidebar)
st.sidebar.header("🔍 篩選條件")

# 測站選擇 (預設全選，或只選您關注的六個)
stations = df_processed['locationName'].unique().tolist()
selected_stations = st.sidebar.multiselect("📍 選擇潮汐站", stations)

# 月份選擇
months = sorted(df_processed['月份'].unique().tolist())
selected_months = st.sidebar.multiselect("📅 選擇月份", months, default=months)

# 時間區段選擇
time_periods = ['白天', '夜晚']
selected_periods = st.sidebar.multiselect("☀️/🌙 時間區段", time_periods, default=time_periods)

# 潮位等級選擇
tide_levels = ['較低潮位 (最低25%)', '低潮位 (低於平均)', '一般低潮']
selected_levels = st.sidebar.multiselect("📉 潮位等級", tide_levels, default=tide_levels)

# 3. 根據篩選器過濾資料
filtered_df = df_processed[
    (df_processed['locationName'].isin(selected_stations)) &
    (df_processed['月份'].isin(selected_months)) &
    (df_processed['時間區段'].isin(selected_periods)) &
    (df_processed['潮位等級'].isin(selected_levels))
]

# 4. 顯示結果
st.subheader(f"📊 查詢結果 (共 {len(filtered_df)} 筆)")

if len(filtered_df) > 0:
    # 使用 st.dataframe 顯示互動式表格
    st.dataframe(filtered_df, use_container_width=True, hide_index=True)
else:
    st.warning("查無符合條件的資料，請放寬側邊欄的篩選條件。")

# 補充說明
st.info("💡 **名詞說明**：\n* **低潮位**：該筆低潮水位低於該測站全年的「平均低潮位」。\n* **較低潮位**：該筆低潮水位落在該測站全年低潮位中「最低的 25%」。\n* 數據來源：中央氣象署 F-A0023-001 預報資料集。")
