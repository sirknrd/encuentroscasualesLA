import os
import time
import threading
import ccxt
import pandas as pd
import numpy as np
from datetime import datetime, timezone
import talib
import lightgbm as lgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import f1_score
from sklearn.preprocessing import LabelEncoder
from dash import Dash, dcc, html, Input, Output
from dash.dash_table import DataTable
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime
from sqlalchemy.orm import sessionmaker, declarative_base
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# --- CONFIG ---
SYMBOLS = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'AVAX/USDT', 'MATIC/USDT']
MODEL_FOLDER = 'models'
DB_PATH = 'sqlite:///crypto_signals_full.db'
TIMEFRAME = '15m'
LIMIT = 1000
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

# --- Funciones ---
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
    try:
        return exchange.fetch_ohlcv(symbol, timeframe=TIMEFRAME, limit=LIMIT)
    except Exception as e:
        print(f"Error fetch OHLCV {symbol}: {e}")
        return []

def fetch_and_store_ohlcv(symbol):
    session = Session()
    try:
        ohlcv = fetch_ohlcv(symbol)
        for o in ohlcv:
            timestamp = datetime.fromtimestamp(o[0]/1000, timezone.utc)
            if not session.query(OHLCV).filter_by(symbol=symbol, timestamp=timestamp).first():
                row = OHLCV(symbol=symbol, timestamp=timestamp, open=o[1], high=o[2], low=o[3], close=o[4], volume=o[5])
                session.add(row)
        session.commit()
    except Exception as e:
        print(f"Error storing OHLCV data for {symbol}: {e}")
        session.rollback()  # Rollback in case of error
    finally:
        session.close()

def load_data(symbol):
    session = Session()
    df = pd.read_sql(session.query(OHLCV).filter(OHLCV.symbol==symbol).statement, engine, parse_dates=['timestamp'])
    session.close()
    df.set_index('timestamp', inplace=True)
    return df

def calcular_indicadores(df):
    df['rsi'] = talib.RSI(df['close'], timeperiod=14)
    macd, _, _ = talib.MACD(df['close'])
    df['macd'] = macd
    df['ema20'] = talib.EMA(df['close'], timeperiod=20)
    df['adx'] = talib.ADX(df['high'], df['low'], df['close'])
    df['roc'] = talib.ROC(df['close'])
    upper, middle, lower = talib.BBANDS(df['close'])
    df['bb_width'] = (upper - lower) / middle
    df.dropna(inplace=True)
    return df

def preparar_datos_para_modelo(df):
    df = calcular_indicadores(df)
    df['target'] = 1  # HOLD por defecto
    df.loc[df['rsi'] < 30, 'target'] = 2  # BUY
    df.loc[df['rsi'] > 70, 'target'] = 0  # SELL

    features = ['rsi', 'macd', 'ema20', 'adx', 'roc', 'bb_width']
    df.dropna(subset=features + ['target'], inplace=True)

    X = df[features]
    y = df['target']
    return X, y

def entrenar_modelo(df):
    X, y = preparar_datos_para_modelo(df)
    le = LabelEncoder()
    y_encoded = le.fit_transform(y)

    X_train, X_val, y_train, y_val = train_test_split(X, y_encoded, test_size=0.2, shuffle=False)

    # Create the model
    model = lgb.LGBMClassifier(
        objective='multiclass',
        num_class=3,
        learning_rate=0.03,
        num_leaves=31,
        metric='multi_logloss',
        verbose=-1,
        random_state=42
    )

    # Fit the model with early stopping
    model.fit(
        X_train,
        y_train,
        eval_set=[(X_val, y_val)],
        eval_metric='multi_logloss',
        early_stopping_rounds=30,
        verbose=False
    )

    preds = model.predict(X_val)
    f1 = f1_score(y_val, preds, average='weighted')
    print(f"[INFO] Modelo entrenado con F1 score ponderado: {f1:.3f}")
    return model, le


def predecir_senal(model, label_encoder, df):
    X, _ = preparar_datos_para_modelo(df)
    proba = model.predict(X)
    preds = np.argmax(proba, axis=1)
    preds_labels = label_encoder.inverse_transform(preds)

    ultima = df.iloc[-1]
    idx = df.index[-1]
    signal = preds_labels[-1]
    confidence = max(proba[-1])
    price = ultima['close']
    timestamp = idx

    return signal, confidence, price, timestamp

def guardar_senal_db(symbol, timestamp, signal, price, confidence):
    session = Session()
    s = Signal(symbol=symbol, timestamp=timestamp, signal=str(signal), price=price, confidence=confidence)
    session.add(s)
    session.commit()
    session.close()

def procesar_symbol(symbol, model=None, label_encoder=None):
    fetch_and_store_ohlcv(symbol)
    df = load_data(symbol)
    if len(df) < 100:
        print(f"[WARN] Datos insuficientes para {symbol}")
        return None, None

    if model is None or label_encoder is None:
        model, label_encoder = entrenar_modelo(df)

    signal, confidence, price, timestamp = predecir_senal(model, label_encoder, df)
    print(f"[INFO] {symbol} Señal: {signal} Confianza: {confidence:.2%}")

    guardar_senal_db(symbol, timestamp, signal, price, confidence)

    if signal == 2 and confidence > 0.85:  # BUY con confianza alta
        enviar_email_senal(symbol, "BUY", price, confidence, timestamp)
    elif signal == 0 and confidence > 0.85:  # SELL con confianza alta
        enviar_email_senal(symbol, "SELL", price, confidence, timestamp)

    return model, label_encoder

# --- DASH UI ---
app = Dash(__name__)
app.title = "Crypto Signal Pro Dashboard"

def color_confianza(c):
    if c > 0.8:
        return 'green'
    elif c > 0.6:
        return 'orange'
    else:
        return 'red'

def icono_semaforo(c):
    if c > 0.8:
        return '🟢'
    elif c > 0.6:
        return '🟠'
    else:
        return '🔴'

@app.callback(
    Output('signal-table', 'data'),
    Input('interval', 'n_intervals')
)
def actualizar_tabla(n):
    session = Session()
    ultimas = []
    for sym in SYMBOLS:
        res = session.query(Signal).filter(Signal.symbol==sym).order_by(Signal.timestamp.desc()).first()
        if res:
            ultimas.append({
                'symbol': res.symbol,
                'signal': res.signal,
                'confidence': res.confidence,
                'timestamp': res.timestamp,
                'price': res.price
            })
    session.close()

    display = []
    for r in ultimas:
        icon = icono_semaforo(r['confidence'])
        color = color_confianza(r['confidence'])
        display.append({
            'Symbol': r['symbol'],
            'Signal': f"{icon} {r['signal']}",
            'Confidence': f"{r['confidence']*100:.1f}%",
            'Timestamp': r['timestamp'].strftime('%Y-%m-%d %H:%M'),
            'Price': f"{r['price']:.2f} USDT"
        })
    return display

app.layout = html.Div([
    html.H1("📊 Crypto Signal Pro Dashboard"),
    dcc.Interval(id='interval', interval=5*60*1000, n_intervals=0),  # Actualiza cada 5 minutos
    DataTable(
        id='signal-table',
        columns=[
            {'name': 'Symbol', 'id': 'Symbol'},
            {'name': 'Signal', 'id': 'Signal'},
            {'name': 'Confidence', 'id': 'Confidence'},
            {'name': 'Timestamp', 'id': 'Timestamp'},
            {'name': 'Price', 'id': 'Price'},
        ],
        data=[],
        style_cell={'textAlign': 'center', 'fontFamily': 'Arial', 'fontSize': '16px'},
        style_header={'backgroundColor': 'lightgray', 'fontWeight': 'bold'},
        style_data_conditional=[
            {
                'if': {'filter_query': '{Signal} contains "🟢"', 'column_id': 'Signal'},
                'color': 'green',
                'fontWeight': 'bold',
            },
            {
                'if': {'filter_query': '{Signal} contains "🟠"', 'column_id': 'Signal'},
                'color': 'orange',
                'fontWeight': 'bold',
            },
            {
                'if': {'filter_query': '{Signal} contains "🔴"', 'column_id': 'Signal'},
                'color': 'red',
                'fontWeight': 'bold',
            },
        ],
        style_table={'maxWidth': '900px', 'margin': 'auto'}
    ),
])

def job_recurrente():
    modelos = {}
    label_encoders = {}
    while True:
        for sym in SYMBOLS:
            print(f"[INFO] Procesando {sym}")
            model, le = procesar_symbol(sym, model=modelos.get(sym), label_encoder=label_encoders.get(sym))
            if model is not None:
                modelos[sym] = model
            if le is not None:
                label_encoders[sym] = le
        print("[INFO] Esperando 5 minutos para siguiente ciclo...\n")
        time.sleep(300)

if __name__ == '__main__':
    threading.Thread(target=job_recurrente, daemon=True).start()
    app.run(debug=True)
