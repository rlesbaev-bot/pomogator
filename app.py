import streamlit as st
import pandas as pd
import requests
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

st.set_page_config(page_title="Семейный Инвест-Помощник", page_icon="📈", layout="wide")
st.title("📈 Семейный Инвест-Помощник")
st.markdown("Анализ акций и облигаций Мосбиржи в реальном времени")

st.sidebar.header("⚙️ Настройки")
risk_profile = st.sidebar.radio("Риск-профиль:", ("🔵 Консервативный", "🟡 Умеренный", "🔴 Агрессивный"))

if 'stocks' not in st.session_state:
    st.session_state.stocks = ["SBER", "LKOH", "GAZP", "YDEX", "MGNT", "HYDR"]
if 'bonds' not in st.session_state:
    st.session_state.bonds = ["SU26238RMFS5"]

new_ticker = st.sidebar.text_input("Добавить акцию (тикер):", "").upper()
if st.sidebar.button("➕ Добавить акцию"):
    if new_ticker and new_ticker not in st.session_state.stocks:
        st.session_state.stocks.append(new_ticker)
        st.rerun()

new_bond = st.sidebar.text_input("Добавить облигацию (тикер):", "").upper()
if st.sidebar.button("➕ Добавить облигацию"):
    if new_bond and new_bond not in st.session_state.bonds:
        st.session_state.bonds.append(new_bond)
        st.rerun()

st.sidebar.markdown("**Мои акции:**")
for stock in st.session_state.stocks:
    c1, c2 = st.sidebar.columns([3, 1])
    c1.write(f"• {stock}")
    if c2.button("❌", key=f"del_{stock}"):
        st.session_state.stocks.remove(stock)
        st.rerun()

st.sidebar.markdown("**Мои облигации:**")
for bond in st.session_state.bonds:
    c1, c2 = st.sidebar.columns([3, 1])
    c1.write(f"• {bond}")
    if c2.button("❌", key=f"del_{bond}"):
        st.session_state.bonds.remove(bond)
        st.rerun()

FUNDAMENTAL_DATA = {
    "SBER": {"name": "Сбербанк", "div_yield": 12.5, "reliable": True},
    "LKOH": {"name": "Лукойл", "div_yield": 16.0, "reliable": True},
    "GAZP": {"name": "Газпром", "div_yield": 0.0, "reliable": True},
    "YDEX": {"name": "Яндекс", "div_yield": 0.0, "reliable": True},
    "MGNT": {"name": "Магнит", "div_yield": 8.5, "reliable": True},
    "HYDR": {"name": "РусГидро", "div_yield": 7.0, "reliable": True},
}

@st.cache_data(ttl=3600)
def analyze_market(stocks_list, bonds_list, profile):
    results = []
    buy_signals = []
    
    for ticker in stocks_list:
        try:
            till_date = datetime.now().strftime('%Y-%m-%d')
            from_date = (datetime.now() - timedelta(days=60)).strftime('%Y-%m-%d')
            url = f"https://iss.moex.com/iss/engines/stock/markets/shares/boards/TQBR/securities/{ticker}/candles.json?interval=24&from={from_date}&till={till_date}"
            response = requests.get(url, timeout=5)
            data = response.json()
            
            df = pd.DataFrame(data['candles']['data'], columns=data['candles']['columns'])
            df['close'] = pd.to_numeric(df['close'])
            df['begin'] = pd.to_datetime(df['begin'])
            df.set_index('begin', inplace=True)
            df = df.sort_index()
            
            df['SMA_30'] = df['close'].rolling(window=30).mean()
            df['SMA_10'] = df['close'].rolling(window=10).mean()
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            df['RSI'] = (100 - (100 / (1 + (gain / loss))))
            
            latest = df.iloc[-1]
            price = latest['close']
            rsi = latest['RSI']
            sma_30 = latest['SMA_30']
            fund = FUNDAMENTAL_DATA.get(ticker, {"name": "Неизвестно", "div_yield": 0, "reliable": False})
            
            if not fund["reliable"]:
                signal, reason = "⛔ ОТКАЗ", "Нет в белом списке"
            elif profile == "🔵 Консервативный" and fund["div_yield"] < 10:
                signal, reason = "⛔ ОТКАЗ", "Низкая див. доходность для консерватора"
            elif price < sma_30 * 0.97 and rsi < 40:
                signal, reason = "🟢 ПОКУПКА", "У поддержки + перепроданность"
                buy_signals.append({"ticker": ticker, "df": df})
            elif price > df['SMA_10'].iloc[-1] * 1.03 and rsi > 70:
                signal, reason = "🔴 ПЕРЕГРЕВ", "RSI > 70"
            else:
                signal, reason = "🔍 ОЖИДАНИЕ", "Боковик"
                
            results.append({"Тикер": ticker, "Тип": "Акция", "Компания": fund["name"], "Цена": f"{price:.2f} ₽", "RSI": f"{rsi:.1f}", "Сигнал": signal, "Причина": reason})
        except:
            results.append({"Тикер": ticker, "Тип": "Акция", "Компания": "Ошибка", "Цена": "-", "RSI": "-", "Сигнал": "❌ ОШИБКА", "Причина": "Нет данных"})

    for ticker in bonds_list:
        try:
            url = f"https://iss.moex.com/iss/securities/{ticker}.json"
            info = requests.get(url, timeout=5).json()
            name = next((row[2] for row in info['description']['data'] if row[0] == 'SHORTNAME'), "Облигация")
            results.append({"Тикер": ticker, "Тип": "Облигация", "Компания": name, "Цена": "По рынку", "RSI": "-", "Сигнал": "✅ СТАБИЛЬНО", "Причина": "Защитный актив"})
        except:
            results.append({"Тикер": ticker, "Тип": "Облигация", "Компания": "Ошибка", "Цена": "-", "RSI": "-", "Сигнал": "❌ ОШИБКА", "Причина": "Нет данных"})
            
    return pd.DataFrame(results), buy_signals

if st.sidebar.button("🔄 Обновить анализ", type="primary"):
    st.cache_data.clear()

st.markdown("---")
st.subheader(f"Результаты для профиля: **{risk_profile}**")

with st.spinner("Загружаю данные с Мосбиржи..."):
    df_results, buy_signals = analyze_market(st.session_state.stocks, st.session_state.bonds, risk_profile)

def color_signals(val):
    if '🟢' in val or '✅' in val: return 'background-color: #d4edda; color: #155724; font-weight: bold'
    if '🔴' in val: return 'background-color: #f8d7da; color: #721c24; font-weight: bold'
    if '⛔' in val or '❌' in val: return 'background-color: #fff3cd; color: #856404; font-weight: bold'
    return ''

st.dataframe(df_results.style.applymap(color_signals, subset=['Сигнал']), use_container_width=True)

if buy_signals:
    st.markdown("### 🎯 Точки для входа (Графики)")
    for item in buy_signals:
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.7, 0.3])
        fig.add_trace(go.Candlestick(x=item["df"].index, open=item["df"]["open"], high=item["df"]["high"], low=item["df"]["low"], close=item["df"]["close"], name="Цена"), row=1, col=1)
        fig.add_trace(go.Scatter(x=item["df"].index, y=item["df"]["SMA_30"], name="SMA 30", line=dict(color="blue")), row=1, col=1)
        fig.add_trace(go.Scatter(x=item["df"].index, y=item["df"]["RSI"], name="RSI", line=dict(color="purple")), row=2, col=1)
        fig.add_hline(y=30, line_dash="dash", line_color="green", row=2, col=1)
        fig.update_layout(title=f"🟢 {item['ticker']}", height=400, xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)
else:
    st.info("💡 Явных точек для покупки по выбранной стратегии сейчас нет. Сохранение капитала — тоже результат!")

csv = df_results.to_csv(index=False, encoding='utf-8-sig').encode('utf-8')
st.download_button(label="💾 Скачать отчет в Excel (CSV)", data=csv, file_name=f"invest_report_{datetime.now().strftime('%Y%m%d')}.csv", mime="text/csv")
