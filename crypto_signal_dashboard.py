import os
import time
import threading
import ccxt
import joblib
import pandas as pd
import numpy as np
from datetime import datetime
import pytz
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
LIMIT = 1000  # más datos
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

exchange = ccxt.binance({
    'apiKey': 'J3lIRo05Z23HawGi6LznhHe8rrMhJiZBCcIIy8mmSqGkvMqSNyTiQdHT3NJniXaD',
    'secret': 'yYoOfF4hl8f4P1HdxigEHiigRjT2kmrSICXxBNE4Bua0RXideVEPfJ6e8xrtZU8O',
    'enableRateLimit': True,
})

# --- FUNCIONES UTILITARIAS ---

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

# --- Indicadores técnicos extendidos ---
def calcular_indicadores(df):
    df = safe_talib_inputs(df)
    close = df['close']
    high = df['high']
    low = df['low']
    volume = df['volume']

    # Básicos
    df['rsi'] = talib.RSI(close, timeperiod=14)
    macd, macdsignal, macdhist = talib.MACD(close)
    df['macd'] = macd
    df['ema20'] = talib.EMA(close, timeperiod=20)

    # Stochastic
    slowk, slowd = talib.STOCH(high, low, close)
    df['stoch_k'] = slowk
    df['stoch_d'] = slowd

    # ADX
    df['adx'] = talib.ADX(high, low, close)

    # ROC
    df['roc'] = talib.ROC(close)

    # Bollinger Bands Width
    upper, middle, lower = talib.BBANDS(close)
    df['bb_width'] = (upper - lower) / middle

    # Volumen SMA
    df['vol_sma20'] = talib.SMA(volume, timeperiod=20)

    # Ichimoku Cloud
    high_9 = df['high'].rolling(window=9).max()
    low_9 = df['low'].rolling(window=9).min()
    df['tenkan_sen'] = (high_9 + low_9) / 2

    high_26 = df['high'].rolling(window=26).max()
    low_26 = df['low'].rolling(window=26).min()
    df['kijun_sen'] = (high_26 + low_26) / 2

    df['senkou_span_a'] = ((df['tenkan_sen'] + df['kijun_sen']) / 2).shift(26)

    high_52 = df['high'].rolling(window=52).max()
    low_52 = df['low'].rolling(window=52).min()
    df['senkou_span_b'] = ((high_52 + low_52) / 2).shift(26)

    df['chikou_span'] = df['close'].shift(-26)

    df.dropna(inplace=True)
    return df

def estado_ichimoku(row):
    # Compara precio cierre con nube para dar estado
    price = row['close']
    span_a = row['senkou_span_a']
    span_b = row['senkou_span_b']

    if price > max(span_a, span_b):
        return 'Alcista'
    elif min(span_a, span_b) <= price <= max(span_a, span_b):
        return 'Indeciso'
    else:
        return 'Bajista'

# --- Patrones de velas ---
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

# --- Preparar datos para modelo ---
def preparar_datos_para_modelo(df):
    df['rsi'] = talib.RSI(df['close'], timeperiod=14)
    df['macd'], _, _ = talib.MACD(df['close'])
    df['ema20'] = talib.EMA(df['close'], timeperiod=20)
    df['adx'] = talib.ADX(df['high'], df['low'], df['close'])
    df['roc'] = talib.ROC(df['close'], timeperiod=10)
    df['bb_upper'], df['bb_middle'], df['bb_lower'] = talib.BBANDS(df['close'])
    df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['bb_middle']

    df.dropna(inplace=True)

    df['target'] = 1  # HOLD
    df.loc[df['rsi'] < 30, 'target'] = 2  # BUY
    df.loc[df['rsi'] > 70, 'target'] = 0  # SELL

    features = ['rsi', 'macd', 'ema20', 'adx', 'roc', 'bb_width']

    # 🔍 Eliminar columnas constantes
    features_valid = [col for col in features if df[col].nunique() > 1]
    print("[DEBUG] Features válidos:", features_valid)

    # 🔍 Verificar columnas con NaNs
    for col in features_valid:
        if df[col].isnull().sum() > 0:
            print(f"[WARN] Columna {col} tiene NaNs")

    df = df.dropna(subset=features_valid + ['target'])

    X = df[features_valid]
    y = df['target']

    print("[DEBUG] Describe de features:\n", X.describe())
    return X, y

# --- Entrenar modelo ---
def entrenar_modelo(df):
    X, y = preparar_datos_para_modelo(df)
    print("[DEBUG] Shape X:", X.shape)
    print("[DEBUG] Columnas con varianza cero:", X.loc[:, X.nunique() <= 1].columns.tolist())
    print("[DEBUG] Columnas con NaNs:", X.columns[X.isnull().any()].tolist())
    print("[DEBUG] Clases únicas en target:", np.unique(y))

    le = LabelEncoder()
    y_encoded = le.fit_transform(y)

    X_train, X_val, y_train, y_val = train_test_split(X, y_encoded, test_size=0.2, shuffle=False)
    print("[INFO] Entrenando con:", X_train.shape[0], "ejemplos y", X_train.shape[1], "features.")

    model = lgb.LGBMClassifier(
        objective='multiclass',
        num_class=3,
        learning_rate=0.03,
        num_leaves=31,
        n_estimators=500,
        random_state=42
    )

    model.fit(
        X_train, y_train,
        eval_set=[(X_val, y_val)],
        early_stopping_rounds=30,
        verbose=False
    )

    preds = model.predict(X_val)
    f1 = f1_score(y_val, preds, average='weighted')
    print(f"[INFO] Modelo entrenado con F1 score ponderado: {f1:.3f}")
    return model, le


# --- Predecir señales ---
def predecir_senal(model, label_encoder, df):
    X, _ = preparar_datos_para_modelo(df)
    proba = model.predict_proba(X)
    preds = model.predict(X)
    preds_labels = label_encoder.inverse_transform(preds)

    # Última fila con datos para devolver señal actual
    ultima = df.iloc[-1]
    idx = df.index[-1]
    signal = preds_labels[-1]
    confidence = max(proba[-1])

    # Detectar patrón vela
    patrones = detectar_patron_vela(df)
    patron_actual = patrones[-1]

    # Estado ichimoku
    estado_nube = estado_ichimoku(ultima)

    return signal, confidence, patron_actual, estado_nube, ultima['close'], idx

# --- Guardar señal ---
def guardar_senal_db(symbol, timestamp, signal, price, confidence):
    session = Session()
    s = Signal(symbol=symbol, timestamp=timestamp, signal=signal, price=price, confidence=confidence)
    session.add(s)
    session.commit()
    session.close()

# --- Función principal que corre todo para cada cripto ---
def procesar_symbol(symbol, model=None, label_encoder=None):
    fetch_and_store_ohlcv(symbol)
    df = load_data(symbol)
    if len(df) < 100:  # poco dato
        print(f"[WARN] Datos insuficientes para {symbol}")
        return None

    df = calcular_indicadores(df)
    if model is None or label_encoder is None:
        model, label_encoder = entrenar_modelo(df)

    signal, confidence, patron, estado_nube, price, timestamp = predecir_senal(model, label_encoder, df)
    print(f"[INFO] {symbol} Señal: {signal} Confianza: {confidence:.2%} Patrón: {patron} Nube: {estado_nube}")

    guardar_senal_db(symbol, timestamp, signal, price, confidence)

    # Enviar email sólo si señal BUY o SELL con confianza alta > 85%
    if signal in ['2', 2, 0] or signal in ['BUY', 'SELL']:  # podría venir como número o texto
        if confidence > 0.85:
            enviar_email_senal(symbol, signal, price, confidence, timestamp)

    return model, label_encoder

# --- DASH UI ---
app = Dash(__name__)
app.title = "Crypto Signal Pro"

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
                'pattern': None,
                'ichimoku': None,
                'timestamp': res.timestamp,
                'price': res.price
            })
    session.close()

    # Para mostrar patrón e ichimoku, recalculemos último df y patrones:
    display = []
    for r in ultimas:
        df = load_data(r['symbol'])
        if len(df) < 100:
            continue
        df = calcular_indicadores(df)
        patrones = detectar_patron_vela(df)
        estado_nube = estado_ichimoku(df.iloc[-1])
        patron_actual = patrones[-1]

        icon = icono_semaforo(r['confidence'])
        color = color_confianza(r['confidence'])
        display.append({
            'Symbol': r['symbol'],
            'Signal': f"{icon} {r['signal']}",
            'Confidence': f"{r['confidence']*100:.1f}%",
            'Pattern': patron_actual or '-',
            'Ichimoku': estado_nube
        })
    return display

app.layout = html.Div([
    html.H1("📊 Crypto Signal Pro Dashboard"),
    dcc.Interval(id='interval', interval=5*60*1000, n_intervals=0),  # cada 5 minutos
    DataTable(
        id='signal-table',
        columns=[
            {'name': 'Symbol', 'id': 'Symbol'},
            {'name': 'Signal', 'id': 'Signal'},
            {'name': 'Confidence', 'id': 'Confidence'},
            {'name': 'Pattern', 'id': 'Pattern'},
            {'name': 'Ichimoku', 'id': 'Ichimoku'}
        ],
        data=[],
        style_cell={'textAlign': 'center', 'fontFamily': 'Arial', 'fontSize': '16px'},
        style_header={'backgroundColor': 'lightgray', 'fontWeight': 'bold'},
        style_data_conditional=[
            {
                'if': {'filter_query': '{Confidence} contains "🟢"', 'column_id': 'Signal'},
                'color': 'green',
                'fontWeight': 'bold',
            },
            {
                'if': {'filter_query': '{Confidence} contains "🟠"', 'column_id': 'Signal'},
                'color': 'orange',
                'fontWeight': 'bold',
            },
            {
                'if': {'filter_query': '{Confidence} contains "🔴"', 'column_id': 'Signal'},
                'color': 'red',
                'fontWeight': 'bold',
            },
            {
                'if': {'filter_query': '{Confidence} contains "Alcista"', 'column_id': 'Ichimoku'},
                'color': 'green',
                'fontWeight': 'bold',
            },
            {
                'if': {'filter_query': '{Ichimoku} = "Indeciso"', 'column_id': 'Ichimoku'},
                'color': 'orange',
                'fontWeight': 'bold',
            },
            {
                'if': {'filter_query': '{Ichimoku} = "Bajista"', 'column_id': 'Ichimoku'},
                'color': 'red',
                'fontWeight': 'bold',
            },
        ],
    )
])

# --- Scheduler que lanza análisis y entrenamiento ---
def job_recurrente():
    print("[INFO] Iniciando análisis y predicción para todas las criptos...")
    global modelos, label_encoders
    for sym in SYMBOLS:
        m, le = procesar_symbol(sym,
                               model=modelos.get(sym),
                               label_encoder=label_encoders.get(sym))
        if m and le:
            modelos[sym] = m
            label_encoders[sym] = le

modelos = {}
label_encoders = {}

def iniciar_scheduler():
    import sched, time
    scheduler = sched.scheduler(time.time, time.sleep)

    def periodic(sc):
        job_recurrente()
        sc.enter(300, 1, periodic, (sc,))  # cada 300 seg = 5 min

    scheduler.enter(0, 1, periodic, (scheduler,))
    threading.Thread(target=scheduler.run, daemon=True).start()

# --- MAIN ---
if __name__ == '__main__':
    modelos = {}
    label_encoders = {}

    # Aquí debería ir job_recurrente() y app.run si están definidos
    print("[INFO] Script listo para ejecutar el modelo con indicadores corregidos.")