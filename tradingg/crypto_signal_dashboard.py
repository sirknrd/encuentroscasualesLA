
import os
import time
import threading
import ccxt
import joblib
import pandas as pd
import numpy as np
from datetime import datetime
import pytz
from sklearn.model_selection import train_test_split
from sklearn.metrics import precision_score, recall_score, f1_score
from sklearn.ensemble import RandomForestClassifier
import lightgbm as lgb
import talib
from dash import Dash, dcc, html, Input, Output
from dash.dash_table import DataTable
import plotly.graph_objs as go
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime
from sqlalchemy.orm import sessionmaker, declarative_base
from apscheduler.schedulers.background import BackgroundScheduler

# --- CONFIG ---
SYMBOLS = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'AVAX/USDT', 'MATIC/USDT']
TIMEFRAME = '15m'
LIMIT = 500
DB_PATH = 'sqlite:///crypto_signals.db'
MODEL_FOLDER = 'models'
os.makedirs(MODEL_FOLDER, exist_ok=True)

# --- DB SETUP ---
Base = declarative_base()
class Signal(Base):
    __tablename__ = 'signals'
    id = Column(Integer, primary_key=True)
    symbol = Column(String)
    timestamp = Column(DateTime)
    signal = Column(String)
    confidence = Column(Float)
    pattern = Column(String)

engine = create_engine(DB_PATH)
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)

exchange = ccxt.binance()

# --- FUNCIONES DE DATOS Y MODELOS ---
def fetch_ohlcv(symbol):
    return exchange.fetch_ohlcv(symbol, timeframe=TIMEFRAME, limit=LIMIT)

def safe_talib_inputs(df):
    for c in ['open', 'high', 'low', 'close', 'volume']:
        df[c] = pd.to_numeric(df[c], errors='coerce')
    df.dropna(inplace=True)
    return df

def detectar_patron_vela(df):
    df = safe_talib_inputs(df)
    patterns = talib.CDLHAMMER(df['open'], df['high'], df['low'], df['close'])
    if patterns.iloc[-1] != 0:
        return 'Hammer'
    patterns = talib.CDLDOJI(df['open'], df['high'], df['low'], df['close'])
    if patterns.iloc[-1] != 0:
        return 'Doji'
    return 'None'

def preparar_datos(df):
    df['rsi'] = talib.RSI(df['close'], timeperiod=14)
    df['macd'], _, _ = talib.MACD(df['close'])
    df['ema'] = talib.EMA(df['close'], timeperiod=14)
    df['target'] = (df['close'].shift(-3) > df['close']).astype(int)
    df.dropna(inplace=True)
    X = df[['rsi', 'macd', 'ema']]
    y = df['target']
    return X, y

def entrenar_modelo(X, y):
    X_train, X_val, y_train, y_val = train_test_split(X, y, test_size=0.2, shuffle=False)
    model = lgb.LGBMClassifier()
    model.fit(X_train, y_train)
    return model

def generar_senal(model, X):
    pred = model.predict(X)[-1]
    proba = model.predict_proba(X)[-1]
    conf = max(proba)
    if conf < 0.55:
        return 'HOLD', conf
    return ('BUY' if pred == 1 else 'SELL'), conf

def procesar_senales():
    session = Session()
    for symbol in SYMBOLS:
        ohlcv = fetch_ohlcv(symbol)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)
        df = safe_talib_inputs(df)
        if len(df) < 50:
            continue
        X, y = preparar_datos(df)
        model = entrenar_modelo(X, y)
        signal, conf = generar_senal(model, X)
        pattern = detectar_patron_vela(df)
        last_ts = df.index[-1].to_pydatetime()
        session.add(Signal(symbol=symbol, timestamp=last_ts, signal=signal, confidence=conf, pattern=pattern))
        session.commit()
    session.close()

# --- DASH APP ---
app = Dash(__name__)
app.layout = html.Div([
    html.H2("📊 Crypto Signal Dashboard"),
    dcc.Interval(id='interval', interval=5*60*1000, n_intervals=0),
    DataTable(id='tabla-senales', columns=[
        {'name': 'Symbol', 'id': 'symbol'},
        {'name': 'Signal', 'id': 'signal'},
        {'name': 'Confidence', 'id': 'confidence'},
        {'name': 'Pattern', 'id': 'pattern'},
        {'name': 'Timestamp', 'id': 'timestamp'}
    ])
])

@app.callback(
    Output('tabla-senales', 'data'),
    Input('interval', 'n_intervals')
)
def actualizar_tabla(n):
    session = Session()
    datos = []
    for symbol in SYMBOLS:
        row = session.query(Signal).filter(Signal.symbol==symbol).order_by(Signal.timestamp.desc()).first()
        if row:
            color = '🟢' if row.confidence > 0.8 else '🟠' if row.confidence > 0.6 else '🔴'
            datos.append({
                'symbol': symbol,
                'signal': f"{color} {row.signal}",
                'confidence': f"{row.confidence:.1%}",
                'pattern': row.pattern,
                'timestamp': row.timestamp.strftime('%Y-%m-%d %H:%M')
            })
    session.close()
    return datos

# --- SCHEDULER ---
scheduler = BackgroundScheduler()
scheduler.add_job(procesar_senales, 'interval', minutes=5)
scheduler.start()

if __name__ == '__main__':
    procesar_senales()
    app.run_server(debug=True)
