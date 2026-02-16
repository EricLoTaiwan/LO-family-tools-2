import streamlit as st
import webbrowser
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, timezone
import urllib.parse
import time
import re

# 引入 googlemaps
try:
    import googlemaps
except ImportError:
    googlemaps = None
    
# 嘗試匯入 ZoneInfo (Python 3.9+)
try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None

# 嘗試匯入 twder (台灣銀行匯率套件)
try:
    import twder
except ImportError:
    twder = None

# ==========================================
# 設定：Google Maps API Key
# 警告：為了安全，請勿將真實 Key 直接暴露在公開代碼庫中
# ==========================================
# 請將下方的 "YOUR_API_KEY_HERE" 換回您原本的 Key
GOOGLE_MAPS_API_KEY = "AIzaSyBK2mfGSyNnfytW7sRkNM5ZWqh2SVGNabo" # 原始 Key: AIza... (請自行填入)

# ==========================================
# Streamlit 頁面設定
# ==========================================
st.set_page_config(
    page_title="四維家族 常用工具 (長輩友善版)",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ==========================================
# CSS 樣式注入 (還原 Tkinter 的視覺風格)
# ==========================================
st.markdown("""
    <style>
    /* 全域背景色 */
    .stApp {
        background-color: #f5f5f5;
    }
    
    /* 標題樣式 */
    .main-title {
        font-family: "Microsoft JhengHei";
        font-size: 36px;
        font-weight: bold;
        text-align: center;
        color: #000000;
        margin-bottom: 20px;
    }

    /* 區塊標題 */
    .section-title {
        font-family: "Microsoft JhengHei";
        font-size: 24px;
        font-weight: bold;
        color: #000000;
        margin-top: 10px;
        margin-bottom: 5px;
        border-bottom: 2px solid #ccc;
    }

    /* 數據顯示框 (模擬 LabelFrame + Label) */
    .data-box {
        background-color: #2c3e50;
        padding: 15px;
        border-radius: 5px;
        font-family: "Consolas";
        font-size: 24px;
        font-weight: bold;
        margin-bottom: 10px;
    }

    /* 字體顏色定義 */
    .text-gold { color: #f1c40f; } /* 去程預設色 */
    .text-cyan { color: #00d2d3; } /* 回程預設色/氣溫 */
    .text-green { color: #2ecc71; } /* 匯率 */
    .text-red { color: #ff3333; }   /* 警示/油價 */
    .text-white { color: #ffffff; }
    
    /* 連結樣式去除底線 */
    a { text-decoration: none; }
    a:hover { text-decoration: underline; }

    /* 按鈕樣式優化 */
    .stButton>button {
        font-family: "Microsoft JhengHei";
        font-weight: bold;
        border-radius: 5px;
    }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 邏輯功能函式 (Logic Functions)
# 使用 st.cache_data 替代 threading 來做快取管理
# ==========================================

def get_time_str(dt):
    return dt.strftime("%H:%M:%S")

def get_world_clock():
    now_utc = datetime.now(timezone.utc)
    try:
        if ZoneInfo:
            time_tw = now_utc.astimezone(ZoneInfo("Asia/Taipei"))
            time_bos = now_utc.astimezone(ZoneInfo("America/New_York"))
            time_ger = now_utc.astimezone(ZoneInfo("Europe/Berlin"))
        else:
            raise ImportError
    except:
        time_tw = now_utc + timedelta(hours=8)
        time_bos = now_utc - timedelta(hours=5)
        time_ger = now_utc + timedelta(hours=1)
    
    return {
        "TW": get_time_str(time_tw),
        "BOS": get_time_str(time_bos),
        "GER": get_time_str(time_ger)
    }

@st.cache_data(ttl=600) # 快取 10 分鐘
def get_currency_rate():
    if not twder:
        return "⚠️ 需安裝 twder"
    try:
        usd = twder.now('USD')[2]
        eur = twder.now('EUR')[2]
        jpy = twder.now('JPY')[2]
        return f"美金 : {usd}<br>歐元 : {eur}<br>日圓 : {jpy}"
    except Exception as e:
        return f"匯率讀取失敗"

@st.cache_data(ttl=600) # 快取 10 分鐘
def get_weather_data():
    locations = [
        {"name": "苗栗", "lat": 24.51, "lon": 120.82},
        {"name": "新竹", "lat": 24.80, "lon": 120.99},
        {"name": "芎林", "lat": 24.77, "lon": 121.07},
        {"name": "木柵", "lat": 24.99, "lon": 121.57}, 
        {"name": "內湖", "lat": 25.08, "lon": 121.56},
        {"name": "波士頓", "lat": 42.36, "lon": -71.06},
        {"name": "德國", "lat": 51.05, "lon": 13.74},
    ]
    
    result_html = ""
    
    for loc in locations:
        try:
            url = f"https://api.open-meteo.com/v1/forecast?latitude={loc['lat']}&longitude={loc['lon']}&current=temperature_2m,weather_code&hourly=precipitation_probability&timezone=auto&forecast_days=1"
            res = requests.get(url, timeout=5)
            if res.status_code == 200:
                data = res.json()
                temp = data['current']['temperature_2m']
                w_code = data['current'].get('weather_code', -1)
                
                # 降雨/天氣圖示邏輯 (保留原邏輯)
                icon = ""
                rain_text = ""
                try:
                    current_time_str = data['current']['time']
                    try:
                        cur_dt = datetime.strptime(current_time_str, "%Y-%m-%dT%H:%M")
                    except ValueError:
                        cur_dt = datetime.strptime(current_time_str, "%Y-%m-%dT%H:%M:%S")
                    
                    cur_hour_dt = cur_dt.replace(minute=0, second=0)
                    search_time = cur_hour_dt.strftime("%Y-%m-%dT%H:%M")
                    hourly_times = data['hourly']['time']
                    
                    if search_time in hourly_times:
                        idx = hourly_times.index(search_time)
                        probs = data['hourly']['precipitation_probability'][idx : idx+5]
                        if probs:
                            max_prob = max(probs)
                            
                            if w_code in [71, 73, 75, 77, 85, 86]: icon = "❄️"
                            elif w_code in [95, 96, 99]: icon = "⛈️"
                            else:
                                if max_prob <= 10: icon = "☀️"
                                elif max_prob <= 40: icon = "☁️"
                                elif max_prob <= 70: icon = "🌦️"
                                else: icon = "☔"
                            rain_text = f" ({icon}{max_prob}%)"
                except:
                    pass

                name_display = loc['name']
                if len(name_display) == 2: name_display += "&emsp;" # 全形空白對齊
                
                result_html += f"{name_display}: {temp}°C{rain_text}<br>"
            else:
                result_html += f"{loc['name']}: N/A<br>"
        except:
            result_html += f"{loc['name']}: Err<br>"
            
    return result_html

@st.cache_data(ttl=3600) # 油價快取 1 小時
def get_gas_price():
    url = "https://gas.goodlife.tw/"
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.encoding = 'utf-8'
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            cpc_main = soup.find("div", {"id": "cpc"})
            if cpc_main:
                prices = cpc_main.find_all("li")
                data = {"92": "--", "95": "--", "98": "--"}
                for p in prices:
                    text = p.get_text().strip()
                    if "92" in text: data['92'] = text.split(':')[-1].strip()
                    if "95" in text: data['95'] = text.split(':')[-1].strip()
                    if "98" in text: data['98'] = text.split(':')[-1].strip()
                return f"92無鉛: {data['92']} | 95無鉛: {data['95']} | 98無鉛: {data['98']}"
    except:
        pass
    return "油價連線失敗"

def parse_duration_to_minutes(text):
    try:
        total_mins = 0
        remaining_text = text
        if "小時" in text:
            parts = text.split("小時")
            hours = int(parts[0].strip())
            total_mins += hours * 60
            remaining_text = parts[1]
        if "分鐘" in remaining_text:
            mins_part = remaining_text.replace("分鐘", "").strip()
            if mins_part.isdigit():
                total_mins += int(mins_part)
        return total_mins
    except:
        return 0

def get_google_maps_url(start, end):
    s_enc = urllib.parse.quote(start)
    e_enc = urllib.parse.quote(end)
    return f"https://www.google.com.tw/maps/dir/{s_enc}/{e_enc}"

def calculate_traffic(gmaps, start_addr, end_addr, std_time, label_prefix):
    """
    計算單趟路況
    回傳: (顯示文字, CSS顏色class, GoogleMap連結)
    """
    url = get_google_maps_url(start_addr, end_addr)
    
    if not gmaps:
        return f"{label_prefix} : API未設定", "text-white", url

    try:
        matrix = gmaps.distance_matrix(
            origins=start_addr,
            destinations=end_addr,
            mode='driving',
            departure_time=datetime.now(),
            language='zh-TW'
        )
        el = matrix['rows'][0]['elements'][0]
        
        if 'duration_in_traffic' in el:
            time_str = el['duration_in_traffic']['text']
        elif 'duration' in el:
            time_str = el['duration']['text']
        else:
            time_str = "無法估算"
            
        cur_mins = parse_duration_to_minutes(time_str)
        
        # 顏色邏輯
        if label_prefix == "往苗栗":
            base_class = "text-gold"
        else:
            base_class = "text-cyan"
            
        if cur_mins > 0:
            diff = cur_mins - std_time
            sign = "+" if diff > 0 else ""
            display_text = f"{label_prefix} : {time_str} ({sign}{diff}分)"
            
            # 塞車警示 (紅色)
            color_class = "text-red" if diff > 20 else base_class
        else:
            display_text = f"{label_prefix} : {time_str}"
            color_class = base_class
            
        return display_text, color_class, url
        
    except Exception as e:
        return f"{label_prefix} : 查詢失敗", base_class, url

# ==========================================
# 主程式 UI 佈局
# ==========================================

# 1. 大標題
st.markdown('<div class="main-title">四維家族 專屬工具箱</div>', unsafe_allow_html=True)

# 2. 全域重新整理按鈕 (Streamlit 需要手動觸發更新)
if st.button("🔄 點擊手動更新所有即時資訊 (時間/路況/天氣)", use_container_width=True):
    st.cache_data.clear() # 清除快取以強制更新
    st.rerun()

# 3. 內容分欄 (左欄: 資訊 / 右欄: 路況)
col_left, col_right = st.columns([1, 1], gap="medium")

# --- 左欄內容 ---
with col_left:
    # 3.1 時間與匯率 (再分兩欄)
    sub_c1, sub_c2 = st.columns(2)
    
    with sub_c1:
        st.markdown('<div class="section-title">世界時間 (Live)</div>', unsafe_allow_html=True)
        clock_data = get_world_clock()
        st.markdown(f"""
        <div class="data-box text-gold">
            台灣&emsp;: {clock_data['TW']}<br>
            波士頓: {clock_data['BOS']}<br>
            德國&emsp;: {clock_data['GER']}
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown('<div class="section-title">即時匯率 (台銀)</div>', unsafe_allow_html=True)
        currency_html = get_currency_rate()
        st.markdown(f"""
        <div class="data-box text-green">
            {currency_html}
        </div>
        """, unsafe_allow_html=True)

    with sub_c2:
        st.markdown('<div class="section-title">即時氣溫 & 降雨率</div>', unsafe_allow_html=True)
        weather_html = get_weather_data()
        st.markdown(f"""
        <div class="data-box text-cyan" style="font-size: 22px;">
            {weather_html}
        </div>
        """, unsafe_allow_html=True)

    # 3.2 油價 (左欄下方)
    st.markdown('<div class="section-title">今日即時油價 (中油)</div>', unsafe_allow_html=True)
    gas_info = get_gas_price()
    st.markdown(f"""
    <div class="data-box text-red" style="text-align: center;">
        {gas_info}
    </div>
    """, unsafe_allow_html=True)

# --- 右欄內容 (路況) ---
with col_right:
    st.markdown('<div class="section-title">即時路況 (Google Map)</div>', unsafe_allow_html=True)
    st.markdown('<span style="color:#7f8c8d; font-size:14px;">※ 點擊下方文字可直接開啟 Google 地圖導航</span>', unsafe_allow_html=True)
    
    # 準備路況參數
    base_addr = "苗栗縣公館鄉鶴山村11鄰鶴山146號"
    target_locations = [
        ("月華家", "文山區木柵路二段109巷137號", "反木柵", 76, 76),
        ("秋華家", "新竹的名人大矽谷", "反芎林", 34, 36),
        ("孟竹家", "新竹市東區太原路128號", "反新竹", 31, 33),
        ("小凱家", "台北市內湖區文湖街21巷", "反內湖", 77, 79)
    ]
    
    # 初始化 Google Maps Client
    gmaps_client = None
    if GOOGLE_MAPS_API_KEY and "YOUR_KEY" not in GOOGLE_MAPS_API_KEY:
        try:
            gmaps_client = googlemaps.Client(key=GOOGLE_MAPS_API_KEY)
        except:
            pass
    
    # 顯示路況卡片
    for name, target_addr, return_label, std_go, std_back in target_locations:
        # 外框
        with st.container():
            st.markdown(f"""
            <div style="background-color:#34495e; padding:5px 10px; border-radius:5px 5px 0 0; margin-top:10px;">
                <span style="color:white; font-size:18px; font-weight:bold; font-family:'Microsoft JhengHei';">{name}</span>
            </div>
            """, unsafe_allow_html=True)
            
            # 計算數據 (為了不卡住畫面，Streamlit 會依序執行，可以考慮加 spinner)
            # 1. 往苗栗
            txt_go, cls_go, url_go = calculate_traffic(gmaps_client, target_addr, base_addr, std_go, "往苗栗")
            # 2. 回程
            txt_back, cls_back, url_back = calculate_traffic(gmaps_client, base_addr, target_addr, std_back, return_label)
            
            # 內容框 (模擬 LabelFrame 內部)
            st.markdown(f"""
            <div class="data-box" style="margin-top:0; border-radius:0 0 5px 5px; padding-top:5px;">
                <a href="{url_go}" target="_blank" class="{cls_go}" style="display:block; margin-bottom:5px;">{txt_go}</a>
                <a href="{url_back}" target="_blank" class="{cls_back}" style="display:block;">{txt_back}</a>
            </div>
            """, unsafe_allow_html=True)

# ==========================================
# 底部 Footer
# ==========================================
st.divider()
col_f1, col_f2 = st.columns([1, 4])
with col_f1:
    st.link_button("YouTube 轉 MP3", "https://yt1s.ai/zh-tw/youtube-to-mp3/")
with col_f2:
    st.markdown('<div style="margin-top: 10px; color: #7f8c8d; font-size: 16px;">← 點擊按鈕開啟轉檔網站</div>', unsafe_allow_html=True)