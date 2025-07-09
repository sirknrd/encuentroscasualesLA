# crypto_signal_dashboard_pro.py

import pandas as pd
import numpy as np
import dash
from dash import html, dcc, Input, Output
from dash.dash_table import DataTable
import plotly.graph_objs as go
import lightgbm as lgb
import yfinance as yf
import talib
import sqlite3
import threading
import time
import datetime
import warnings
warnings.filterwarnings('ignore')

# ============================
# CONFIGURACIÓN
# ============================

SYMBOLS = ['BTC-USD', 'ETH-USD', 'BNB-USD', 'AVAX-USD', 'MATIC-USD', 'ADA-USD', 'DOT-USD', 'ATOM-USD', 'LTC-USD']
INTERVAL = '15m'
LOOKBACK = '30d'
DATABASE = 'signals.db'

# ============================
# FUNCIONES DE DATOS Y PATRONES
# ============================

def get_data(symbol):
    try:
        df = yf.download(tickers=symbol, interval=INTERVAL, period=LOOKBACK)
        if df.empty or len(df) < 50:
            print(f"[WARN] Datos insuficientes para {symbol}")
            return pd.DataFrame()
        df.dropna(inplace=True)
        df.reset_index(inplace=True)
        df['Date'] = pd.to_datetime(df['Datetime'] if 'Datetime' in df else df['Date'])
        return df
    except Exception as e:
        print(f"[ERROR] Al descargar {symbol}: {e}")
        return pd.DataFrame()

def add_indicators(df):
    if df.empty or len(df) < 50:
        return df
    close = df['Close'].values
    high = df['High'].values
    low = df['Low'].values
    volume = df['Volume'].values

    df['RSI'] = talib.RSI(close)
    df['MACD'], _, _ = talib.MACD(close)
    df['ADX'] = talib.ADX(high, low, close)
    df['CCI'] = talib.CCI(high, low, close)
    df['OBV'] = talib.OBV(close, volume)
    df['WILLR'] = talib.WILLR(high, low, close)
    df['ROC'] = talib.ROC(close)
    df['EMA9'] = talib.EMA(close, timeperiod=9)
    df['EMA20'] = talib.EMA(close, timeperiod=20)
    df['EMA50'] = talib.EMA(close, timeperiod=50)
    df['SMA100'] = talib.SMA(close, timeperiod=100)
    df['UpperBB'], df['MiddleBB'], df['LowerBB'] = talib.BBANDS(close)
    df.fillna(method='bfill', inplace=True)
    return df

def add_target(df):
    if df.empty or len(df) < 55:
        return df
    future = df['Close'].shift(-5)
    diff = (future - df['Close']) / df['Close']
    df['target'] = pd.cut(diff, bins=[-np.inf, -0.005, 0.005, np.inf], labels=['SELL', 'HOLD', 'BUY'])
    return df.dropna()

def detectar_patrones(df):
    if df.empty or len(df) < 50:
        return []
    patrones = {
        'Hammer': talib.CDLHAMMER,
        'Hanging Man': talib.CDLHANGINGMAN,
        'Engulfing': talib.CDLENGULFING,
        'Doji': talib.CDLDOJI,
        'Morning Star': talib.CDLMORNINGSTAR,
        'Evening Star': talib.CDLEVENINGSTAR,
        '3 White Soldiers': talib.CDL3WHITESOLDIERS,
        '3 Black Crows': talib.CDL3BLACKCROWS,
        'Shooting Star': talib.CDLSHOOTINGSTAR,
        'Piercing Pattern': talib.CDLPIERCING,
        'Dark Cloud Cover': talib.CDLDARKCLOUDCOVER,
        'Tweezer Top': talib.CDLTWEEZERTOP,
        'Tweezer Bottom': talib.CDLTWEEZERBOTTOM,
        'Spinning Top': talib.CDLSPINNINGTOP
    }
    resultados = []
    for nombre, funcion in patrones.items():
        result = funcion(df['Open'].values, df['High'].values, df['Low'].values, df['Close'].values)
        if result[-1] != 0:
            resultados.append(nombre)
    return resultados

# ============================
# ENTRENAMIENTO Y PREDICCIÓN
# ============================

def train_model(df):
    df = add_indicators(df)
    df = add_target(df)
    if df.empty:
        return None, []
    features = ['RSI', 'MACD', 'ADX', 'CCI', 'OBV', 'WILLR', 'ROC',
                'EMA9', 'EMA20', 'EMA50', 'SMA100', 'UpperBB', 'MiddleBB', 'LowerBB']
    X = df[features]
    y = df['target']
    model = lgb.LGBMClassifier()
    model.fit(X, y)
    return model, features

def make_prediction(df, model, features):
    if model is None or df.empty:
        return "HOLD", 0.0
    last = df.tail(1)
    x = last[features]
    pred = model.predict(x)[0]
    prob = model.predict_proba(x).max()
    return pred, prob

# ============================
# BASE DE DATOS
# ============================

def init_db():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS signals
                 (timestamp TEXT, symbol TEXT, signal TEXT, confidence REAL)''')
    conn.commit()
    conn.close()

def save_signal(symbol, signal, confidence):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute("INSERT INTO signals VALUES (?, ?, ?, ?)", (str(datetime.datetime.now()), symbol, signal, confidence))
    conn.commit()
    conn.close()

def load_signals():
    conn = sqlite3.connect(DATABASE)
    df = pd.read_sql('SELECT * FROM signals ORDER BY timestamp DESC LIMIT 200', conn)
    conn.close()
    return df

# ============================
# DASH APP
# ============================

app = dash.Dash(__name__)
init_db()

app.layout = html.Div([
    html.H1("📊 Crypto Signal Pro con Velas Japonesas", style={'textAlign': 'center'}),
    
    dcc.Dropdown(id='symbol-dropdown', options=[{'label': s, 'value': s} for s in SYMBOLS],
                 value='ETH-USD'),
    
    dcc.Graph(id='price-graph'),

    html.Div(id='signal-output', style={'fontSize': 24, 'marginTop': 10, 'textAlign': 'center'}),
    html.Div(id='candlestick-patterns', style={'fontSize': 18, 'color': 'gray', 'textAlign': 'center'}),

    html.H3("📋 Historial de Señales"),
    DataTable(id='signals-table', style_table={'overflowX': 'auto'},
              style_cell={'textAlign': 'center', 'padding': '5px'},
              columns=[{'name': i, 'id': i} for i in ['timestamp', 'symbol', 'signal', 'confidence']]),

    dcc.Interval(id='interval-component', interval=5*60*1000, n_intervals=0)
])

@app.callback(
    Output('price-graph', 'figure'),
    Output('signal-output', 'children'),
    Output('candlestick-patterns', 'children'),
    Output('signals-table', 'data'),
    Input('symbol-dropdown', 'value'),
    Input('interval-component', 'n_intervals')
)
def update_dashboard(symbol, n):
    df = get_data(symbol)
    if df.empty or len(df) < 50:
        return go.Figure(), f"No hay datos suficientes para {symbol}", "", []
    
    df = add_indicators(df)
    model, features = train_model(df)
    signal, conf = make_prediction(df, model, features)
    patrones = detectar_patrones(df)
    save_signal(symbol, signal, float(conf))

    emoji_map = {'BUY': '🟢', 'SELL': '🔴', 'HOLD': '🟠'}
    msg = f"Señal actual: {emoji_map.get(signal, '🟠')} **{signal}** (Confianza: {conf:.2%})"
    patron_msg = "🕯️ Patrón detectado: " + ", ".join(patrones) if patrones else "Sin patrón reciente detectado."

    fig = go.Figure(data=[go.Candlestick(
        x=df['Date'],
        open=df['Open'],
        high=df['High'],
        low=df['Low'],
        close=df['Close']
    )])
    fig.update_layout(title=f'{symbol} - Gráfico OHLC', xaxis_rangeslider_visible=False)

    table = load_signals().to_dict('records')
    return fig, msg, patron_msg, table

# ============================
# AUTOACTUALIZACIÓN EN SEGUNDO PLANO
# ============================

def background_loop():
    while True:
        for sym in SYMBOLS:
            df = get_data(sym)
            if df.empty or len(df) < 50:
                continue
            df = add_indicators(df)
            model, features = train_model(df)
            if model is None:
                continue
            signal, conf = make_prediction(df, model, features)
            save_signal(sym, signal, float(conf))
        time.sleep(300)

threading.Thread(target=background_loop, daemon=True).start()

# ============================
# EJECUCIÓN
# ============================

if __name__ == '__main__':
    app.run(debug=True)
