import streamlit as st
import pandas as pd
import plotly.express as px
import yfinance as yf
from fredapi import Fred
import feedparser
import requests
import google.generativeai as genai
from urllib.parse import quote

# ==========================================
# 1. 頁面配置與側邊欄設定
# ==========================================
st.set_page_config(
    page_title="總體經濟、金融與 NLP 市場情緒儀表板",
    page_icon="🌐",
    layout="wide"
)

st.title("🌐 總體經濟、金融指標與 AI 輿論情緒即時儀表板")
st.markdown("整合 **FRED 官方總經數據**、**yfinance 金融走勢** 與 **Gemini AI 鷹鴿派輿論情緒分析** 的現代化經濟分析平台。")

st.sidebar.header("⚙️ 設定與金鑰管理")

# 1.1 檢查 FRED API Key
fred_key = None
if "FRED_API_KEY" in st.secrets:
    fred_key = st.secrets["FRED_API_KEY"]
    st.sidebar.success("已自動讀取 FRED API Key！")
else:
    fred_key = st.sidebar.text_input("請輸入 FRED API Key:", type="password")

# 1.2 檢查 Gemini API Key
gemini_key = None
if "GEMINI_API_KEY" in st.secrets:
    gemini_key = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=gemini_key)
    st.sidebar.success("已自動讀取 Gemini API Key！")
else:
    gemini_input = st.sidebar.text_input("請輸入 Gemini API Key:", type="password")
    if gemini_input:
        gemini_key = gemini_input
        genai.configure(api_key=gemini_key)

if st.sidebar.button("🔄 手動刷新所有數據"):
    st.cache_data.clear()
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.info("💡 **提示**：本系統採用 `st.secrets` 資安防護機制，確保金鑰安全。")

# ==========================================
# 2. 數據抓取函式 (FRED, yfinance, RSS, Fear & Greed)
# ==========================================
@st.cache_data(ttl=3600)
def get_fred_data(api_key):
    fred = Fred(api_key=api_key)
    data = {
        "CPI 物價指數": fred.get_series("CPIAUCSL"),
        "10年期美債殖利率": fred.get_series("DGS10"),
        "美國失業率": fred.get_series("UNRATE"),
        "聯邦基金利率": fred.get_series("FEDFUNDS")
    }
    df = pd.DataFrame(data).ffill().tail(365)
    return df

@st.cache_data(ttl=600)
def get_market_data():
    tickers = {
        "S&P 500": "^GSPC",
        "台灣加權指數": "^TWII",
        "布蘭特原油": "BZ=F",
        "美元/台幣匯率": "TWD=X"
    }
    df = yf.download(list(tickers.values()), period="1y")["Close"]
    df.rename(columns={v: k for k, v in tickers.items()}, inplace=True)
    return df

@st.cache_data(ttl=1800)
def fetch_google_news(keyword="Federal Reserve Inflation"):
    safe_keyword = quote(keyword)
    url = f"https://news.google.com/rss/search?q={safe_keyword}&hl=en-US"
    feed = feedparser.parse(url)
    return [entry.title for entry in feed.entries[:8]]

@st.cache_data(ttl=3600)
def fetch_crypto_fear_greed():
    try:
        url = "https://api.alternative.me/fng/"
        res = requests.get(url, timeout=5).json()
        data = res["data"][0]
        return data["value"], data["value_classification"]
    except:
        return "N/A", "無法取得數據"

# ==========================================
# 3. 頁面渲染邏輯
# ==========================================
if fred_key:
    try:
        macro_df = get_fred_data(fred_key)
        market_df = get_market_data()
        fng_value, fng_class = fetch_crypto_fear_greed()

        # 第一區塊：核心總經 KPI 卡片與市場情緒概覽
        st.subheader("📊 關鍵總體經濟與市場指標")
        col1, col2, col3, col4, col5 = st.columns(5)
        
        latest_cpi = macro_df["CPI 物價指數"].dropna().iloc[-1]
        col1.metric("CPI 物價指數", f"{latest_cpi:.1f}")
        
        latest_rate = macro_df["10年期美債殖利率"].dropna().iloc[-1]
        rate_prev = macro_df["10年期美債殖利率"].dropna().iloc[-2]
        col2.metric("10年美債殖利率", f"{latest_rate:.2f}%", f"{latest_rate - rate_prev:+.2f}%")
        
        latest_unemp = macro_df["美國失業率"].dropna().iloc[-1]
        col3.metric("美國失業率", f"{latest_unemp:.1f}%")
        
        latest_fed = macro_df["聯邦基金利率"].dropna().iloc[-1]
        col4.metric("聯邦基金利率", f"{latest_fed:.2f}%")

        col5.metric("市場情緒指數 (F&G)", f"{fng_value}", f"{fng_class}")

        st.write("---")

        # 第二區塊：多功能分頁儀表板
        tab1, tab2, tab3 = st.tabs([
            "📈 金融市場走勢 (yfinance)", 
            "🏛️ 總體經濟趨勢 (FRED)", 
            "📰 NLP 市場新聞與鷹鴿情緒分析"
        ])
        
        # 頁籤 1: 金融市場
        with tab1:
            market_choice = st.selectbox("選擇金融市場標的：", market_df.columns)
            fig1 = px.line(market_df, y=market_choice, title=f"{market_choice} 近一年走勢", template="plotly_white")
            st.plotly_chart(fig1, use_container_width=True)
            
        # 頁籤 2: 總體經濟
        with tab2:
            macro_choice = st.selectbox("選擇總體經濟指標：", macro_df.columns)
            fig2 = px.line(macro_df, y=macro_choice, title=f"{macro_choice} 近一年走勢", template="plotly_white")
            st.plotly_chart(fig2, use_container_width=True)

        # 頁籤 3: NLP 市場新聞與情緒分析
        with tab3:
            st.subheader("📰 即時財經新聞與 LLM 鷹鴿派情緒分析")
            
            search_kw = st.text_input("🔍 輸入新聞關鍵字 (預設: Federal Reserve Inflation):", value="Federal Reserve Inflation")
            news_titles = fetch_google_news(search_kw)

            nlp_col1, nlp_col2 = st.columns([1, 1])

            with nlp_col1:
                st.markdown("### 📌 最新財經新聞標題 (RSS)")
                if news_titles:
                    for i, title in enumerate(news_titles, 1):
                        st.write(f"**{i}.** {title}")
                else:
                    st.warning("查無相關新聞標題，請嘗試更換關鍵字。")

            with nlp_col2:
                st.markdown("### 🤖 Gemini AI 鷹鴿派與情緒打分")
                if gemini_key:
                    if st.button("🚀 開始分析新聞市場情緒", type="primary"):
                        if news_titles:
                            with st.spinner("Gemini 正在剖析文本立場與鷹鴿情緒中..."):
                                try:
                                    news_text = "\n".join([f"- {t}" for t in news_titles])
                                    prompt = (
                                        f"你是一位專業總體經濟分析師。請分析以下 8 條新聞標題：\n{news_text}\n\n"
                                        f"請以繁體中文輸出結構化報告：\n"
                                        f"1. 整體市場情緒分數 (0~100)\n"
                                        f"2. 貨幣政策立場判定 (鷹派/鴿派/中立)\n"
                                        f"3. 重點分析與逐條評分表格 (Markdown Format)"
                                    )
                                    
                                    # 自動嘗試不同的模型名稱，避免 404 錯誤
                                    response = None
                                    for model_name in ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-pro"]:
                                        try:
                                            model = genai.GenerativeModel(model_name)
                                            response = model.generate_content(prompt)
                                            break
                                        except Exception:
                                            continue

                                    if response:
                                        st.markdown(response.text)
                                        # 新增亮點：提供下載分析報告按鈕
                                        st.download_button(
                                            label="📥 下載 AI 分析報告 (.md)",
                                            data=response.text,
                                            file_name="AI_Macro_Sentiment_Report.md",
                                            mime="text/markdown"
                                        )
                                    else:
                                        st.error("無法載入任何可用的 Gemini 模型，請確認您的 API Key 是否正確。")

                                except Exception as e:
                                    st.error(f"AI 分析時發生錯誤: {e}")
                        else:
                            st.warning("尚無新聞數據可供分析。")
                else:
                    st.warning("👈 請在側邊欄輸入 Gemini API Key（或設定在 Secrets 中）以啟用 AI 文本情緒分析功能。")

    except Exception as e:
        st.error(f"數據讀取失敗，請確認 FRED API Key 是否正確。錯誤訊息: {e}")
else:
    st.info("👈 請在左側輸入您的 FRED API Key 以開啟儀表板。")
