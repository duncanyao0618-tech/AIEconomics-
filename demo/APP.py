import streamlit as st
import pandas as pd
import plotly.express as px
import yfinance as yf
from fredapi import Fred
from google import genai  # Google GenAI 官方 SDK

# 頁面基本配置
st.set_page_config(page_title="總體經濟與金融即時儀表板", layout="wide")
st.title("🌐 全球總體經濟與金融指標即時儀表板")

# 側邊欄：輸入 API Keys 與刷新控制
st.sidebar.header("⚙️ 設定與金鑰")

# FRED API Key 設定
if "FRED_API_KEY" in st.secrets:
    fred_key = st.secrets["FRED_API_KEY"]
    st.sidebar.success("已自動讀取 FRED API Key！")
else:
    fred_key = st.sidebar.text_input("請輸入你的 FRED API Key:", type="password")

# Gemini API Key 設定 (新增)
if "GEMINI_API_KEY" in st.secrets:
    gemini_key = st.secrets["GEMINI_API_KEY"]
    st.sidebar.success("已自動讀取 Gemini API Key！")
else:
    gemini_key = st.sidebar.text_input("請輸入你的 Gemini API Key:", type="password")

if st.sidebar.button("手動刷新數據"):
    st.cache_data.clear()

# 1. 抓取 FRED 數據
@st.cache_data(ttl=3600)
def get_fred_data(api_key):
    fred = Fred(api_key=api_key)
    data = {
        "CPI 物價指數": fred.get_series("CPIAUCSL"),
        "10年期美債殖利率": fred.get_series("DGS10"),
        "2年期美債殖利率": fred.get_series("DGS2"),
        "美國失業率": fred.get_series("UNRATE"),
        "聯邦基金利率": fred.get_series("FEDFUNDS"),
        "日本10年期公債殖利率": fred.get_series("IRLTLT01JPM156N")
    }
    df = pd.DataFrame(data).ffill().tail(365)
    df["美債殖利率利差 (10Y-2Y)"] = df["10年期美債殖利率"] - df["2年期美債殖利率"]
    return df

# 2. 抓取 Market 數據
@st.cache_data(ttl=600)
def get_market_data():
    tickers = {
        "S&P 500": "^GSPC",
        "台灣加權指數": "^TWII",
        "布蘭特原油": "BZ=F",
        "美元/台幣匯率": "TWD=X",
        "黃金現貨價格": "GC=F"
    }
    df = yf.download(list(tickers.values()), period="1y")["Close"]
    
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.droplevel(0)
        
    df.rename(columns={v: k for k, v in tickers.items()}, inplace=True)
    return df

# 頁面渲染邏輯
if fred_key:
    try:
        macro_df = get_fred_data(fred_key)
        market_df = get_market_data()

        # 取得最新數值供後續顯示與 AI 使用
        latest_spread = macro_df["美債殖利率利差 (10Y-2Y)"].dropna().iloc[-1]
        latest_cpi = macro_df["CPI 物價指數"].dropna().iloc[-1]
        latest_rate = macro_df["10年期美債殖利率"].dropna().iloc[-1]
        rate_prev = macro_df["10年期美債殖利率"].dropna().iloc[-2]
        latest_unemp = macro_df["美國失業率"].dropna().iloc[-1]
        latest_fed = macro_df["聯邦基金利率"].dropna().iloc[-1]
        latest_jp_rate = macro_df["日本10年期公債殖利率"].dropna().iloc[-1]
        jp_rate_prev = macro_df["日本10年期公債殖利率"].dropna().iloc[-2]
        latest_gold = market_df["黃金現貨價格"].dropna().iloc[-1]
        gold_prev = market_df["黃金現貨價格"].dropna().iloc[-2]

        # 檢查並顯示殖利率倒掛警示
        if latest_spread < 0:
            st.warning(f"🚨 **【經濟衰退警示】美國公債殖利率曲線發生倒掛！** 目前 10年期與 2年期美債殖利率利差為 **{latest_spread:.2f}%**（小於 0）。")
        else:
            st.success(f"✅ **目前 10Y-2Y 美債殖利率利差正常**：**{latest_spread:+.2f}%**（大於等於 0）。")

        # 第一區塊：核心 KPI 卡片
        st.subheader("📊 關鍵總體經濟與指標概覽")
        
        col1, col2, col3 = st.columns(3)
        col1.metric("CPI 物價指數", f"{latest_cpi:.1f}")
        col2.metric("10年美債殖利率", f"{latest_rate:.2f}%", f"{latest_rate - rate_prev:+.2f}%")
        col3.metric("美國失業率", f"{latest_unemp:.1f}%")

        col4, col5, col6 = st.columns(3)
        col4.metric("聯邦基金利率", f"{latest_fed:.2f}%")
        col5.metric("日本 10 年期公債殖利率", f"{latest_jp_rate:.2f}%", f"{latest_jp_rate - jp_rate_prev:+.2f}%")
        col6.metric("黃金現貨價格 (美元)", f"{latest_gold:.2f}", f"{latest_gold - gold_prev:+.2f}")

        # 第二區塊：互動式圖表
        st.write("---")
        st.subheader("📈 市場走勢與總體指標折線圖")
        
        tab1, tab2, tab3 = st.tabs(["金融市場走勢 (yfinance)", "總體經濟趨勢 (FRED)", "美債 10Y-2Y 利差分析"])
        
        with tab1:
            market_choice = st.selectbox("選擇金融市場標的：", market_df.columns, key="market_select")
            fig1 = px.line(market_df, y=market_choice, title=f"{market_choice} 近一年走勢")
            st.plotly_chart(fig1, use_container_width=True)
            
        with tab2:
            macro_options = [col for col in macro_df.columns if col != "美債殖利率利差 (10Y-2Y)"]
            macro_choice = st.selectbox("選擇總體經濟指標：", macro_options, key="macro_select")
            fig2 = px.line(macro_df, y=macro_choice, title=f"{macro_choice} 近一年走勢")
            st.plotly_chart(fig2, use_container_width=True)

        with tab3:
            st.markdown("### 📉 10 年期與 2 年期美債殖利率利差（10Y - 2Y）")
            fig3 = px.line(macro_df, y="美債殖利率利差 (10Y-2Y)", title="美國 10年期與 2年期公債殖利率利差走勢")
            fig3.add_hline(y=0, line_dash="dash", line_color="red", annotation_text="倒掛分界線 (0%)")
            st.plotly_chart(fig3, use_container_width=True)

        # 第三區塊：AI 總體經濟智慧短評 (新增)
        st.write("---")
        st.subheader("🤖 AI 總體經濟智慧短評")
        st.write("點擊下方按鈕，讓 Gemini AI 根據當前儀表板抓取到的最新數據自動為您生成專業的 200 字總經分析報告。")

        if st.button("✨ 產生 AI 總體經濟摘要", type="primary"):
            if not gemini_key:
                st.error("請先在側邊欄輸入您的 Gemini API Key，才能使用 AI 摘要功能！")
            else:
                with st.spinner("AI 正在分析當前全球總經與市場數據，請稍候..."):
                    try:
                        client = genai.Client(api_key=gemini_key)
                        prompt = f"""
                        請根據以下最新的總體經濟與金融市場數據，以專業總體經濟分析師的角度，撰寫一份大約 200 字的繁體中文短評：
                        - CPI 物價指數: {latest_cpi:.1f}
                        - 10年期美債殖利率: {latest_rate:.2f}%
                        - 10Y-2Y 美債殖利率利差: {latest_spread:.2f}%
                        - 美國失業率: {latest_unemp:.1f}%
                        - 聯邦基金利率: {latest_fed:.2f}%
                        - 日本10年期公債殖利率: {latest_jp_rate:.2f}%
                        - 黃金現貨價格: {latest_gold:.2f} USD
                        
                        請點出目前的通膨、利率環境、殖利率曲線倒掛狀態與市場資產（如黃金）表現的關聯與潛在風險。
                        """
                        
                        response = client.models.generate_content(
                            model="gemini-3.8-flash",
                            contents=prompt
                        )
                        
                        st.success("✅ AI 總體經濟摘要生成完畢！")
                        st.info(response.text)
                    except Exception as e:
                        st.error(f"AI 摘要生成失敗，請確認 Gemini API Key 是否正確。錯誤訊息: {e}")

    except Exception as e:
        st.error(f"數據讀取失敗，請確認 FRED API Key 是否正確。錯誤訊息: {e}")
else:
    st.info("👈 請在左側輸入您的 FRED API Key 以開啟儀表板。")
