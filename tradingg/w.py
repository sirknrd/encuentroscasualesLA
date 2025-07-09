
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
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# --- CONFIG ---
SYMBOLS = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'AVAX/USDT', 'MATIC/USDT']
MODEL_FOLDER = 'models'
DB_PATH = 'sqlite:///crypto_signals_full.db'
TIMEFRAME = '15m'
LIMIT = 500
RETRAIN_HOUR = 2
EMAIL_SENDER = 'cryptosignalpro07@gmail.com'
EMAIL_PASSWORD = 'tu_contraseña_app'
EMAIL_RECIPIENT = 'conradvonstillfried@gmail.com'
os.makedirs(MODEL_FOLDER, exist_ok=True)

# --- DB SETUP ---
Base = declarative_base()
class OHLCV(Base):
    __tablename__ = 'ohlcv'
    id = Column(Integer, primary_key=True)
    symbol = Column(String)
    timestamp = Column(DateTime, index=True)
    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)
    volume = Column(Float)

class Signal(Base):
    __tablename__ = 'signals'
    id = Column(Integer, primary_key=True)
    symbol = Column(String)
    timestamp = Column(DateTime)
    signal = Column(String)
    price = Column(Float)
    confidence = Column(Float)

engine = create_engine(DB_PATH)
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
exchange = ccxt.binance()
enabled_cryptos = SYMBOLS.copy()

def enviar_email_senal(symbol, signal, price, confidence, timestamp):
    asunto = f"🚨 Señal {signal} para {symbol}"
    cuerpo = f"""
    🔔 Señal generada por IA

    ▪️ Cripto: {symbol}
    ▪️ Señal: {signal}
    ▪️ Precio: {price:.2f} USDT
    ▪️ Confianza: {confidence:.1%}
    ▪️ Fecha: {timestamp.strftime('%Y-%m-%d %H:%M')}

    Este mensaje fue generado automáticamente por CryptoSignalPro.
    """
    msg = MIMEMultipart()
    msg['From'] = EMAIL_SENDER
    msg['To'] = EMAIL_RECIPIENT
    msg['Subject'] = asunto
    msg.attach(MIMEText(cuerpo, 'plain'))

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
        print(f"📧 Email enviado para {symbol} - {signal}")
    except Exception as e:
        print(f"❌ Error al enviar email: {e}")

def fetch_ohlcv(symbol):
    return exchange.fetch_ohlcv(symbol, timeframe=TIMEFRAME, limit=LIMIT)

def fetch_and_store_ohlcv(symbol):
    session = Session()
    ohlcv = fetch_ohlcv(symbol)
    for o in ohlcv:
        timestamp = datetime.utcfromtimestamp(o[0]/1000.0)
        if not session.query(OHLCV).filter_by(symbol=symbol, timestamp=timestamp).first():
            row = OHLCV(symbol=symbol, timestamp=timestamp, open=o[1], high=o[2], low=o[3], close=o[4], volume=o[5])
            session.add(row)
    session.commit()
    session.close()

def load_data(symbol):
    session = Session()
    df = pd.read_sql(session.query(OHLCV).filter(OHLCV.symbol==symbol).statement, engine, parse_dates=['timestamp'])
    session.close()
    df.set_index('timestamp', inplace=True)
    return df

def safe_talib_inputs(df):
    cols = ['open', 'high', 'low', 'close', 'volume']
    for c in cols:
        df[c] = pd.to_numeric(df[c], errors='coerce').astype('float64')
    df.dropna(subset=cols, inplace=True)
    return df

def detectar_patron_vela(df):
    df = safe_talib_inputs(df)
    patrones = []
    hammer = talib.CDLHAMMER(df['open'], df['high'], df['low'], df['close'])
    inverted_hammer = talib.CDLINVERTEDHAMMER(df['open'], df['high'], df['low'], df['close'])
    engulfing = talib.CDLENGULFING(df['open'], df['high'], df['low'], df['close'])
    doji = talib.CDLDOJI(df['open'], df['high'], df['low'], df['close'])
    morning_star = talib.CDLMORNINGSTAR(df['open'], df['high'], df['low'], df['close'], penetration=0)
    evening_star = talib.CDLEVENINGSTAR(df['open'], df['high'], df['low'], df['close'], penetration=0)
    three_white = talib.CDL3WHITESOLDIERS(df['open'], df['high'], df['low'], df['close'])
    three_black = talib.CDL3BLACKCROWS(df['open'], df['high'], df['low'], df['close'])

    for i in range(len(df)):
        if hammer.iloc[i] != 0:
            patrones.append('Hammer')
        elif inverted_hammer.iloc[i] != 0:
            patrones.append('Inverted Hammer')
        elif engulfing.iloc[i] != 0:
            patrones.append('Engulfing')
        elif doji.iloc[i] != 0:
            patrones.append('Doji')
        elif morning_star.iloc[i] != 0:
            patrones.append('Morning Star')
        elif evening_star.iloc[i] != 0:
            patrones.append('Evening Star')
        elif three_white.iloc[i] != 0:
            patrones.append('3 White Soldiers')
        elif three_black.iloc[i] != 0:
            patrones.append('3 Black Crows')
        else:
            patrones.append(None)
    return patrones

def entrenar_modelos(df):
    X, y = preparar_datos_para_modelo(df)
    X_train, X_val, y_train, y_val = train_test_split(X, y, test_size=0.2, shuffle=False)

    model_lgb = lgb.LGBMClassifier(objective='binary', learning_rate=0.03,
                                   num_leaves=31, n_estimators=500, random_state=42)
    model_lgb.fit(X_train, y_train, eval_set=[(X_val, y_val)],
                  early_stopping_rounds=30, verbose=False)

    model_rf = RandomForestClassifier(n_estimators=100, random_state=42)
    model_rf.fit(X_train, y_train)

    preds_lgb = model_lgb.predict(X_val)
    preds_rf = model_rf.predict(X_val)
    f1_lgb = f1_score(y_val, preds_lgb)
    f1_rf = f1_score(y_val, preds_rf)
    print(f"LightGBM F1: {f1_lgb:.3f}, RandomForest F1: {f1_rf:.3f}")
    return model_lgb, model_rf
