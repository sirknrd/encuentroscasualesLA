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
import plotly.graph_objs as go

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

# --- PREPARAR DATOS ---
def preparar_datos_para_modelo(df):
    df['rsi'] = talib.RSI(df['close'], timeperiod=14)
    df['macd'], _, _ = talib.MACD(df['close'])
    df['ema20'] = talib.EMA(df['close'], timeperiod=20)
    df['adx'] = talib.ADX(df['high'], df['low'], df['close'])
    df['roc'] = talib.ROC(df['close'], timeperiod=10)
    df['bb_upper'], df['bb_middle'], df['bb_lower'] = talib.BBANDS(df['close'])
    df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['bb_middle']
    df['cci'] = talib.CCI(df['high'], df['low'], df['close'])
    df['atr'] = talib.ATR(df['high'], df['low'], df['close'])
    df['obv'] = talib.OBV(df['close'], df['volume'])
    df['mfi'] = talib.MFI(df['high'], df['low'], df['close'], df['volume'])

    df.dropna(inplace=True)

    df['target'] = 1
    df.loc[df['rsi'] < 30, 'target'] = 2
    df.loc[df['rsi'] > 70, 'target'] = 0

    features = ['rsi', 'macd', 'ema20', 'adx', 'roc', 'bb_width', 'cci', 'atr', 'obv', 'mfi']
    df.dropna(subset=features + ['target'], inplace=True)

    X = df[features]
    y = df['target']
    return X, y

# --- ENTRENAR MODELO ---
def entrenar_modelo(df):
    X, y = preparar_datos_para_modelo(df)
    print("=== Diagnóstico de Features ===")
    for col in X.columns:
        print(f"Feature: {col} | Valores únicos: {X[col].nunique()} | Valores nulos: {X[col].isnull().sum()}")
    print("Clases target:", dict(pd.Series(y).value_counts()))
    print("==============================")

    le = LabelEncoder()
    y_encoded = le.fit_transform(y)

    X_train, X_val, y_train, y_val = train_test_split(X, y_encoded, test_size=0.2, shuffle=False)
    print(f"[INFO] Entrenando con {X_train.shape[0]} ejemplos y {X_train.shape[1]} features.")

    train_data = lgb.Dataset(X_train, label=y_train)
    val_data = lgb.Dataset(X_val, label=y_val, reference=train_data)

    params = {
        'objective': 'multiclass',
        'num_class': 3,
        'learning_rate': 0.03,
        'num_leaves': 31,
        'metric': 'multi_logloss',
        'verbosity': -1,
        'seed': 42
    }

    model = lgb.train(
        params,
        train_data,
        num_boost_round=500,
        valid_sets=[val_data],
        verbose_eval=False
    )

    preds = model.predict(X_val)
    preds_labels = np.argmax(preds, axis=1)
    f1 = f1_score(y_val, preds_labels, average='weighted')
    print(f"[INFO] Modelo entrenado con F1 score ponderado: {f1:.3f}")
    return model, le

# --- DASHBOARD ---
app = Dash(__name__)

app.layout = html.Div([
    html.H1("🔥 Crypto Signal Pro Dashboard"),
    html.Div([
        html.Label("Seleccionar Cripto:"),
        dcc.Dropdown(
            id='symbol-dropdown',
            options=[{'label': sym, 'value': sym} for sym in SYMBOLS],
            value='BTC/USDT'
        )
    ]),
    dcc.Graph(id='price-chart'),
    html.H2("📋 Señales Recientes"),
    html.Button("Exportar CSV", id="export-csv", n_clicks=0),
    DataTable(
        id='signal-table',
        columns=[
            {'name': 'Símbolo', 'id': 'Símbolo'},
            {'name': 'Señal', 'id': 'Señal'},
            {'name': 'Confianza', 'id': 'Confianza'},
            {'name': 'Precio', 'id': 'Precio'},
            {'name': 'Fecha', 'id': 'Fecha'}
        ],
        style_data_conditional=[
            {
                'if': {
                    'filter_query': '{Confianza} >= 0.8',
                    'column_id': 'Confianza'
                },
                'backgroundColor': '#d4edda',
                'color': 'black'
            },
            {
                'if': {
                    'filter_query': '{Confianza} >= 0.5 && {Confianza} < 0.8',
                    'column_id': 'Confianza'
                },
                'backgroundColor': '#fff3cd',
                'color': 'black'
            },
            {
                'if': {
                    'filter_query': '{Confianza} < 0.5',
                    'column_id': 'Confianza'
                },
                'backgroundColor': '#f8d7da',
                'color': 'black'
            }
        ],
        style_cell={'textAlign': 'center'},
        export_format='csv'
    )
])

@app.callback(
    Output('price-chart', 'figure'),
    Input('symbol-dropdown', 'value')
)
def update_chart(symbol):
    session = Session()
    rows = session.query(OHLCV).filter_by(symbol=symbol).order_by(OHLCV.timestamp.desc()).limit(100).all()
    session.close()

    if not rows:
        return go.Figure().update_layout(title=f'No hay datos para {symbol}')

    data = []
    for r in rows:
        data.append({
            'id': r.id,
            'symbol': r.symbol,
            'timestamp': r.timestamp if isinstance(r.timestamp, datetime) else datetime.strptime(str(r.timestamp), '%Y-%m-%d %H:%M:%S'),
            'open': r.open,
            'high': r.high,
            'low': r.low,
            'close': r.close,
            'volume': r.volume
        })

    df = pd.DataFrame(data)
    df = df.sort_values('timestamp')

    fig = go.Figure(data=[go.Candlestick(
        x=df['timestamp'],
        open=df['open'], high=df['high'], low=df['low'], close=df['close'],
        name='OHLC'
    )])

    fig.update_layout(title=f'Precio de {symbol}', xaxis_title='Tiempo', yaxis_title='Precio')
    return fig

@app.callback(
    Output('signal-table', 'data'),
    Input('symbol-dropdown', 'value')
)
def update_table(symbol):
    session = Session()
    rows = session.query(Signal).filter_by(symbol=symbol).order_by(Signal.timestamp.desc()).limit(10).all()
    session.close()

    return [
        {
            'Símbolo': r.symbol,
            'Señal': r.signal,
            'Confianza': float(f"{r.confidence:.2f}"),
            'Precio': r.price,
            'Fecha': r.timestamp.strftime('%Y-%m-%d %H:%M')
        }
        for r in rows
    ]

# --- MAIN ---
if __name__ == '__main__':
    modelos = {}
    label_encoders = {}
    print("[INFO] Script listo para ejecutar el modelo con LightGBM entrenado con .train() compatible.")
    app.run(debug=True)
