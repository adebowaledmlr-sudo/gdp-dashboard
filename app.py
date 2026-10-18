import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime, timezone

st.set_page_config(page_title="ScalpSignal Dashboard", page_icon="📈", layout="centered")

st.title("📈 ScalpSignal Dashboard")
st.caption("Free starter dashboard • Educational signals only • Not financial advice")

st.warning(
    "This starter uses Yahoo Finance data, which may be delayed, incomplete, or different "
    "from your broker's MT5 quote. It does not support every broker CFD or synthetic/volatility index. "
    "Always confirm prices and spreads in MT5. No trades are placed automatically."
)

symbols = {
    "Bitcoin (BTC-USD)": "BTC-USD",
    "Ethereum (ETH-USD)": "ETH-USD",
    "EUR/USD": "EURUSD=X",
    "GBP/USD": "GBPUSD=X",
    "USD/JPY": "JPY=X",
    "Gold futures (GC=F)": "GC=F",
    "S&P 500 ETF (SPY)": "SPY",
    "NASDAQ 100 ETF (QQQ)": "QQQ",
    "Apple (AAPL)": "AAPL",
    "Microsoft (MSFT)": "MSFT",
}

col1, col2 = st.columns(2)
with col1:
    instrument_name = st.selectbox("Market", list(symbols.keys()))
with col2:
    timeframe = st.selectbox("Chart timeframe", ["5m", "15m", "30m", "1h"], index=0)

st.caption("M1 is omitted because free public data may be unreliable for execution-grade scalping.")
refresh = st.button("Analyze latest available candles", type="primary", use_container_width=True)

def rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0).ewm(alpha=1/period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1/period, adjust=False).mean()
    rs = gain / loss.replace(0, float("nan"))
    return 100 - (100 / (1 + rs))

def analyze(ticker, interval):
    period = "5d" if interval in ("5m", "15m", "30m") else "1mo"
    data = yf.download(ticker, period=period, interval=interval, auto_adjust=True, progress=False)
    if data is None or data.empty:
        return None
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)
    required = {"Open", "High", "Low", "Close"}
    if not required.issubset(set(data.columns)):
        return None
    data = data.dropna(subset=["Open", "High", "Low", "Close"]).copy()
    if len(data) < 30:
        return None
    data["EMA9"] = data["Close"].ewm(span=9, adjust=False).mean()
    data["EMA21"] = data["Close"].ewm(span=21, adjust=False).mean()
    data["RSI14"] = rsi(data["Close"])
    prev_close = data["Close"].shift(1)
    tr = pd.concat([
        data["High"] - data["Low"],
        (data["High"] - prev_close).abs(),
        (data["Low"] - prev_close).abs()
    ], axis=1).max(axis=1)
    data["ATR14"] = tr.rolling(14).mean()
    # Avoid using the currently forming candle where possible.
    row = data.iloc[-2]
    previous = data.iloc[-3]
    close = float(row["Close"])
    ema9, ema21, rsi14, atr = float(row["EMA9"]), float(row["EMA21"]), float(row["RSI14"]), float(row["ATR14"])
    if pd.isna(rsi14) or pd.isna(atr) or atr <= 0:
        return None

    if ema9 > ema21 and close > ema9 and 50 <= rsi14 <= 68:
        signal = "BUY"
        reason = "EMA 9 is above EMA 21, price is above EMA 9, and RSI supports upward momentum."
        stop = close - 1.5 * atr
        target = close + 2.0 * atr
    elif ema9 < ema21 and close < ema9 and 32 <= rsi14 <= 50:
        signal = "SELL"
        reason = "EMA 9 is below EMA 21, price is below EMA 9, and RSI supports downward momentum."
        stop = close + 1.5 * atr
        target = close - 2.0 * atr
    else:
        signal = "WAIT"
        reason = "The EMA and RSI conditions do not align clearly. Wait for a stronger setup."
        stop = target = None

    return {
        "data": data,
        "signal": signal,
        "reason": reason,
        "close": close,
        "ema9": ema9,
        "ema21": ema21,
        "rsi": rsi14,
        "atr": atr,
        "stop": stop,
        "target": target,
        "candle_time": row.name,
    }

if refresh:
    with st.spinner("Fetching and analyzing latest available data..."):
        try:
            result = analyze(symbols[instrument_name], timeframe)
        except Exception as e:
            result = None
            st.error("Data provider error. Try again later. Details: " + str(e)[:180])

    if result is None:
        st.error("No usable data returned. Try another market/timeframe or try again later.")
    else:
        signal = result["signal"]
        if signal == "BUY":
            st.success("SIGNAL: BUY — setup conditions detected")
        elif signal == "SELL":
            st.error("SIGNAL: SELL — setup conditions detected")
        else:
            st.info("SIGNAL: WAIT — no aligned setup")

        st.write("**Why:** " + result["reason"])
        st.caption(f"Instrument: {instrument_name} • Timeframe: {timeframe} • Candle used: {result['candle_time']}")
        c1, c2 = st.columns(2)
        c1.metric("Last completed candle close", f"{result['close']:.5g}")
        c2.metric("RSI (14)", f"{result['rsi']:.1f}")
        c3, c4 = st.columns(2)
        c3.metric("EMA 9", f"{result['ema9']:.5g}")
        c4.metric("EMA 21", f"{result['ema21']:.5g}")

        if signal != "WAIT":
            st.subheader("Illustrative risk levels")
            c5, c6 = st.columns(2)
            c5.metric("ATR-based stop-loss", f"{result['stop']:.5g}")
            c6.metric("ATR-based take-profit", f"{result['target']:.5g}")
            st.caption("These are formula-based reference levels, not validated trade instructions. Check spread, contract size, and price against MT5.")
        st.subheader("Recent candles")
        chart_data = result["data"][["Close", "EMA9", "EMA21"]].tail(80)
        st.line_chart(chart_data)
        st.subheader("Reassessment")
        st.write(f"Reassess after the next completed {timeframe} candle, or sooner if the setup invalidates. This is not a guaranteed holding time.")
else:
    st.info("Choose a market and timeframe, then tap **Analyze latest available candles**.")
    st.write("**Signal rules:**")
    st.write("- BUY: EMA 9 above EMA 21, close above EMA 9, RSI 50–68.")
    st.write("- SELL: EMA 9 below EMA 21, close below EMA 9, RSI 32–50.")
    st.write("- WAIT: conditions are mixed.")
    st.write("This is a basic rules-based prototype, not a predictive AI model. Test on demo data before risking money.")

st.divider()
st.caption("No API key is required for this prototype. The public data source and hosting may change; free availability is not guaranteed.")
