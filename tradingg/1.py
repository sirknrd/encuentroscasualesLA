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
EMAIL_PASSWORD = 'tu_contraseña_app'  # Cambia por tu password app Gmail
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

# --- FUNCIONES ---
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
    # Convierte columnas a float64 y elimina NaN para evitar crashes en talib
    cols = ['open', 'high', 'low', 'close', 'volume']
    for c in cols:
        df[c] = pd.to_numeric(df[c], errors='coerce').astype('float64')
    df.dropna(subset=cols, inplace=True)
    return df

def calcular_indicadores(df):
    df = safe_talib_inputs(df)
    df['return'] = df['close'].pct_change()
    df['rsi'] = talib.RSI(df['close'], timeperiod=14)
    df['macd'], df['macd_signal'], _ = talib.MACD(df['close'])
    upper, middle, lower = talib.BBANDS(df['close'], timeperiod=20)
    df['bollinger_upper'] = upper
    df['bollinger_middle'] = middle
    df['bollinger_lower'] = lower
    df['adx'] = talib.ADX(df['high'], df['low'], df['close'], timeperiod=14)
    df['atr'] = talib.ATR(df['high'], df['low'], df['close'], timeperiod=14)
    df['obv'] = talib.OBV(df['close'], df['volume'])
    slowk, slowd = talib.STOCH(df['high'], df['low'], df['close'])
    df['stoch_k'] = slowk
    df['stoch_d'] = slowd
    df['cci'] = talib.CCI(df['high'], df['low'], df['close'], timeperiod=14)
    df['mom'] = talib.MOM(df['close'], timeperiod=10)
    df['volume_ema'] = df['volume'].ewm(span=14).mean()
    df['patron_vela'] = detectar_patron_vela(df)
    df.dropna(inplace=True)
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
        if hammer[i] != 0:
            patrones.append('Hammer')
        elif inverted_hammer[i] != 0:
            patrones.append('Inverted Hammer')
        elif engulfing[i] != 0:
            patrones.append('Engulfing')
        elif doji[i] != 0:
            patrones.append('Doji')
        elif morning_star[i] != 0:
            patrones.append('Morning Star')
        elif evening_star[i] != 0:
            patrones.append('Evening Star')
        elif three_white[i] != 0:
            patrones.append('3 White Soldiers')
        elif three_black[i] != 0:
            patrones.append('3 Black Crows')
        else:
            patrones.append(None)
    return patrones

def preparar_datos_para_modelo(df):
    df['patron_code'] = df['patron_vela'].astype('category').cat.codes
    features = ['return', 'rsi', 'macd', 'macd_signal', 'bollinger_upper', 'bollinger_middle',
                'bollinger_lower', 'adx', 'atr', 'obv', 'stoch_k', 'stoch_d', 'cci',
                'mom', 'volume_ema', 'patron_code']
    X = df[features]
    y = (df['close'].shift(-1) > df['close']).astype(int)
    X = X.iloc[:-1]
    y = y.iloc[:-1]
    return X, y

def entrenar_modelos(df):
    X, y = preparar_datos_para_modelo(df)
    X_train, X_val, y_train, y_val = train_test_split(X, y, test_size=0.2, shuffle=False)
    train_data = lgb.Dataset(X_train, label=y_train)
    val_data = lgb.Dataset(X_val, label=y_val)
    params = {
        'objective': 'binary',
        'metric': 'binary_logloss',
        'learning_rate': 0.03,
        'num_leaves': 31,
        'verbose': -1,
        'boosting_type': 'gbdt',
        'random_state': 42
    }
    model_lgb = lgb.train(params, train_data, valid_sets=[val_data], num_boost_round=500,
                          early_stopping_rounds=30, verbose_eval=False)
    model_rf = RandomForestClassifier(n_estimators=100, random_state=42)
    model_rf.fit(X_train, y_train)
    preds_lgb = (model_lgb.predict(X_val) > 0.5).astype(int)
    preds_rf = model_rf.predict(X_val)
    f1_lgb = f1_score(y_val, preds_lgb)
    f1_rf = f1_score(y_val, preds_rf)
    print(f"LightGBM F1: {f1_lgb:.3f}, RandomForest F1: {f1_rf:.3f}")
    return model_lgb, model_rf

def guardar_modelos(symbol, model_lgb, model_rf):
    joblib.dump(model_lgb, f"{MODEL_FOLDER}/{symbol.replace('/','_')}_lgb.pkl")
    joblib.dump(model_rf, f"{MODEL_FOLDER}/{symbol.replace('/','_')}_rf.pkl")

def cargar_modelos(symbol):
    path_lgb = f"{MODEL_FOLDER}/{symbol.replace('/','_')}_lgb.pkl"
    path_rf = f"{MODEL_FOLDER}/{symbol.replace('/','_')}_rf.pkl"
    if os.path.exists(path_lgb) and os.path.exists(path_rf):
        model_lgb = joblib.load(path_lgb)
        model_rf = joblib.load(path_rf)
        return model_lgb, model_rf
    else:
        return None, None

def predecir_signal(symbol):
    fetch_and_store_ohlcv(symbol)
    df = load_data(symbol)
    df = calcular_indicadores(df)
    model_lgb, model_rf = cargar_modelos(symbol)
    if model_lgb is None or model_rf is None:
        print(f"Modelos no encontrados para {symbol}, entrenando...")
        model_lgb, model_rf = entrenar_modelos(df)
        guardar_modelos(symbol, model_lgb, model_rf)
    X, _ = preparar_datos_para_modelo(df)
    latest = X.iloc[-1:]
    prob_lgb = model_lgb.predict(latest)[0]
    prob_rf = model_rf.predict_proba(latest)[0][1]
    prob_prom = (prob_lgb + prob_rf) / 2
    umbral_buy = 0.65
    umbral_sell = 0.35
    signal = 'HOLD'
    if prob_prom > umbral_buy:
        signal = 'BUY'
    elif prob_prom < umbral_sell:
        signal = 'SELL'
    ts = df.index[-1]
    price = df['close'].iloc[-1]
    session = Session()
    exists = session.query(Signal).filter_by(symbol=symbol, timestamp=ts).first()
    if not exists:
        s = Signal(symbol=symbol, timestamp=ts, signal=signal, price=price, confidence=prob_prom)
        session.add(s)
        session.commit()
        patron = df.loc[ts, 'patron_vela']
        if (signal == 'BUY' and patron in ['Hammer', 'Morning Star', 'Engulfing', '3 White Soldiers', 'Inverted Hammer']) or \
           (signal == 'SELL' and patron in ['Evening Star', '3 Black Crows']):
            enviar_email_senal(symbol, signal, price, prob_prom, ts)
        else:
            print(f"Señal {signal} para {symbol} descartada por patrón vela ({patron})")
    session.close()

def retrain_all_models():
    print("Retrain models started...")
    for symbol in enabled_cryptos:
        fetch_and_store_ohlcv(symbol)
        df = load_data(symbol)
        df = calcular_indicadores(df)
        if len(df) > 100:
            model_lgb, model_rf = entrenar_modelos(df)
            guardar_modelos(symbol, model_lgb, model_rf)
    print("Retrain models finished.")

# --- DASHBOARD ---
app = Dash(__name__)
app.layout = html.Div([
    html.H2("Crypto Signal Full Ensemble Dashboard"),
    dcc.Dropdown(id='symbol-dropdown', options=[{'label': s, 'value': s} for s in SYMBOLS], value=SYMBOLS[0]),
    dcc.Graph(id='price-chart'),
    html.H4("Tabla de Señales Recientes"),
    DataTable(id='tabla-senales', page_size=10, style_table={'overflowX': 'auto'}),
    dcc.Interval(id='interval', interval=5*60*1000, n_intervals=0)
])

@app.callback(
    Output('price-chart', 'figure'),
    Output('tabla-senales', 'data'),
    Input('interval', 'n_intervals'),
    Input('symbol-dropdown', 'value')
)
def update_dashboard(n, symbol):
    df = load_data(symbol)
    df = calcular_indicadores(df)
    session = Session()
    signals = pd.read_sql(session.query(Signal).filter(Signal.symbol == symbol).order_by(Signal.timestamp.desc()).limit(20).statement, engine, parse_dates=['timestamp'])
    session.close()
    fig = go.Figure(data=[go.Candlestick(x=df.index,
                                         open=df['open'], high=df['high'],
                                         low=df['low'], close=df['close'],
                                         name='OHLC')])
    buys = signals[signals['signal'] == 'BUY']
    sells = signals[signals['signal'] == 'SELL']
    fig.add_trace(go.Scatter(x=buys['timestamp'], y=buys['price'], mode='markers',
                             marker=dict(symbol='triangle-up', color='green', size=10), name='BUY'))
    fig.add_trace(go.Scatter(x=sells['timestamp'], y=sells['price'], mode='markers',
                             marker=dict(symbol='triangle-down', color='red', size=10), name='SELL'))

    tabla = []
    for _, row in signals.iterrows():
        patron = '—'
        try:
            patron = df.loc[row['timestamp'], 'patron_vela']
        except Exception:
            pass
        color = '🟢' if row['confidence'] > 0.8 else '🟠' if row['confidence'] > 0.6 else '🔴'
        tabla.append({
            'Fecha': row['timestamp'].strftime('%Y-%m-%d %H:%M'),
            'Cripto': row['symbol'],
            'Señal': row['signal'],
            'Precio': f"{row['price']:.2f}",
            'Confianza': f"{color} {row['confidence']*100:.1f}%",
            'Patrón Vela': patron or '—'
        })
    return fig, tabla

# --- SCHEDULER ---
scheduler = BackgroundScheduler()
scheduler.add_job(lambda: [predecir_signal(sym) for sym in enabled_cryptos], 'interval', minutes=5, timezone=pytz.UTC)
scheduler.add_job(retrain_all_models, 'cron', hour=RETRAIN_HOUR, timezone=pytz.UTC)
scheduler.start()

# --- MAIN ---
if __name__ == '__main__':
    threading.Thread(target=lambda: app.run(debug=False, use_reloader=False)).start()
    print("Dashboard iniciado en http://127.0.0.1:8050")
    while True:
        time.sleep(60)
