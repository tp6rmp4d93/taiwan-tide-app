import streamlit as st
import pandas as pd
import datetime
import holidays
import os
import glob
import xml.etree.ElementTree as ET

# 網頁標題與設定
st.set_page_config(page_title="台灣潮汐進階查詢系統", layout="wide")
st.title("🌊 台灣沿海測站潮汐查詢系統 (2026~2027)")

# 預先載入幾年的假日清單 (設定 2024~2030 以確保未來檔案也能直接用)
tw_holidays = holidays.country_holidays('TW', years=range(2024, 2031))

# --- 定義 XML 解析函數 ---
def parse_cwa_xml(xml_file):
    tree = ET.parse(xml_file)
    root = tree.getroot()
    # 氣象署 XML 的 Namespace
    ns = {'cwa': 'urn:cwa:gov:tw:cwacommon:0.1'} 
    
    records = []
    # 找到所有的測站 (Location)
    locations = root.findall('.//cwa:Data/cwa:TideForecasts/cwa:Location', ns)
    
    for loc in locations:
        station_name = loc.find('cwa:StationName', ns).text
        
        # 找到每日資料
        dailies = loc.findall('cwa:TimePeriods/cwa:Daily', ns)
        for daily in dailies:
            times = daily.findall('cwa:Time', ns)
            for t in times:
                obs_time = t.find('cwa:DateTime', ns).text
                tide_type = t.find('cwa:Tide', ns).text
                height_elem = t.find('cwa:TideHeights/cwa:AboveLocalMSL', ns)
                
                # 處理可能的空值
                try:
                    local_height = int(height_elem.text)
                except (AttributeError, ValueError, TypeError):
                    local_height = None
                    
                records.append({
                    'locationName': station_name,
                    'obsTime': obs_time,
                    '高低潮': 'H' if tide_type == '滿潮' else 'L',
                    '潮高(當地)': local_height
                })
    return pd.DataFrame(records)

# --- 主資料載入與處理邏輯 ---
@st.cache_data
def load_and_process_data():
    all_dfs = []
    
    # 自動尋找當前目錄下所有符合條件的 CSV 檔案
    csv_files = glob.glob('F-A0023-001*.csv')
    for file in csv_files:
        try:
            df = pd.read_csv(file)
            all_dfs.append(df)
        except Exception as e:
            st.warning(f"讀取 {file} 時發生錯誤: {e}")
            
    # 自動尋找當前目錄下所有符合條件的 XML 檔案
    xml_files = glob.glob('F-A0023-001*.xml')
    for file in xml_files:
        try:
            df = parse_cwa_xml(file)
            all_dfs.append(df)
        except Exception as e:
            st.warning(f"解析 {file} 時發生錯誤: {e}")

    # 如果什麼檔案都沒找到，中止程式
    if not all_dfs:
        st.error("找不到任何符合 `F-A0023-001` 開頭的 CSV 或 XML 檔案，請將資料檔放入同一資料夾。")
        st.stop()
        
    # 合併所有找到的資料表
    df = pd.concat(all_dfs, ignore_index=True)
    
    # 確保高潮與低潮標記格式統一 (防呆機制)
    df['高低潮'] = df['高低潮'].replace({'滿潮': 'H', '乾潮': 'L'})
    
    # 確保潮高為數值格式並移除空值
    df['潮高(當地)'] = pd.to_numeric(df['潮高(當地)'], errors='coerce')
    df = df.dropna(subset=['潮高(當地)'])
    df['潮高(當地)'] = df['潮高(當地)'].astype(int)
    
    # 時間與日期處理
    df['obsTime'] = pd.to_datetime(df['obsTime'])
    df['年份'] = df['obsTime'].dt.year
    df['月份'] = df['obsTime'].dt.month
    df['日期'] = df['obsTime'].dt.strftime('%Y-%m-%d')
    df['小時'] = df['obsTime'].dt.hour
    df['時間'] = df['obsTime'].dt.strftime('%H:%M')
    
    # 增加星期
    weekday_map = {0: '週一', 1: '週二', 2: '週三', 3: '週四', 4: '週五', 5: '週六', 6: '週日'}
    df['星期'] = df['obsTime'].dt.weekday.map(weekday_map)
    
    # 移除可能重複的紀錄 (如果同一年份的資料同時有 CSV 跟 XML 檔)
    df = df.drop_duplicates(subset=['locationName', 'obsTime'])
    
    return df

# 載入資料
df_processed = load_and_process_data()

# 2. 建立側邊欄篩選器 (Sidebar)
st.sidebar.header("🔍 進階查詢條件")

# 顯示系統找到了幾年的資料
years = sorted(df_processed['年份'].unique().tolist())
st.sidebar.success(f"系統已自動載入資料年份：{', '.join(map(str, years))}")

# 年份選擇
selected_years = st.sidebar.multiselect("📆 選擇年份", years, default=years)

# 測站選擇
stations = sorted(df_processed['locationName'].unique().tolist())
default_stations = [s for s in stations if any(x in s for x in ['淡水', '淡海', '花蓮'])]
if not default_stations:
    default_stations = stations[:2]
selected_stations = st.sidebar.multiselect("📍 選擇潮汐站", stations, default=default_stations) 

# 月份選擇
st.sidebar.markdown("**📅 選擇月份**")
col1, col2, col3, col4 = st.sidebar.columns(4)
selected_months = []
for m in range(1, 13):
    with [col1, col2, col3, col4][(m-1) % 4]:
        if st.checkbox(f"{m}月", value=True):
            selected_months.append(m)

# 時間區段選擇
st.sidebar.markdown("**☀️/🌙 選擇時間區間 (小時)**")
start_hour, end_hour = st.sidebar.slider("設定區間：", min_value=0, max_value=24, value=(7, 18), step=1)

# 潮位門檻值設定
st.sidebar.markdown("**📉/📈 潮位門檻值設定**")
tide_filter_type = st.sidebar.radio("選擇篩選潮位類型：", ["高潮 (H)", "低潮 (L)"])

if tide_filter_type == "高潮 (H)":
    threshold = st.sidebar.number_input("輸入高潮門檻值 (將篩選「大於」此數值)：", value=100, step=10)
    hl_mask = 'H'
else:
    threshold = st.sidebar.number_input("輸入低潮門檻值 (將篩選「小於」此數值)：", value=-100, step=10)
    hl_mask = 'L'

# 3. 根據篩選器過濾資料
filtered_df = df_processed[
    (df_processed['年份'].isin(selected_years)) &
    (df_processed['locationName'].isin(selected_stations)) &
    (df_processed['月份'].isin(selected_months)) &
    (df_processed['小時'] >= start_hour) &
    (df_processed['小時'] <= end_hour) &
    (df_processed['高低潮'] == hl_mask)
]

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
                    display_df = station_df[['年份', '日期', '星期', '時間', '高低潮', '潮高(當地)']].copy()
                    styled_df = display_df.style.apply(highlight_holidays, axis=1)
                    st.dataframe(styled_df, use_container_width=True, hide_index=True)
                else:
                    st.info(f"{station_name} 在此條件下查無資料。")
    else:
        st.warning("請在左側選單選擇至少一個測站。")
else:
    st.warning("查無符合條件的資料，請嘗試放寬時間區間、月份，或調整門檻值。")

st.info("💡 **操作與顏色說明**：\n* 有**底色標記**之日期代表為週末或台灣國定假日。\n* 系統會自動抓取資料夾內所有 `F-A0023-001` 開頭的 CSV 與 XML 檔。")
