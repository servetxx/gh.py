import ccxt
import pandas as pd
import pandas_ta as ta
import logging
import time
from datetime import datetime

# Günlüğü yapılandırma
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# MXC API anahtarını buraya girin
API_KEY = 'mx0vglpEOXDKxNMcSb'
API_SECRET = '49721b0afb9341dda592b050410e9f4d'

# MXC borsasına bağlan
exchange = ccxt.mexc({
    'apiKey': API_KEY,
    'secret': API_SECRET,
    'enableRateLimit': True,
})

def calculate_indicators(ohlcv):
    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    if len(df) < 50:
        return None, None, None, None, None, None

    rsi = df.ta.rsi(length=14)
    macd = df.ta.macd(fast=12, slow=26, signal=9)['MACDh_12_26_9']
    bb = df.ta.bbands(length=20)
    stoch = df.ta.stoch(k=14, d=3, smooth_k=3)
    
    return (
        rsi.iloc[-1] if not rsi.empty else None,
        macd.iloc[-1] if not macd.empty else None,
        bb['BBL_20_2.0'].iloc[-1] if not bb.empty else None,
        bb['BBU_20_2.0'].iloc[-1] if not bb.empty else None,
        stoch['STOCHk_14_3_3'].iloc[-1] if not stoch.empty else None,
        stoch['STOCHd_14_3_3'].iloc[-1] if not stoch.empty else None,
    )

def get_balance(symbol):
    try:
        balance = exchange.fetch_balance()
        coin = symbol.split('/')[0]
        coin_balance = balance['total'].get(coin, 0)
        usdt_balance = balance['total'].get('USDT', 0)
        logging.info(f"Mevcut {coin} bakiyesi: {coin_balance}")
        logging.info(f"Mevcut USDT bakiyesi: {usdt_balance}")
        return coin_balance, usdt_balance
    except Exception as e:
        logging.error(f"Bakiye alınırken hata oluştu: {e}")
        return 0, 0

def place_long_order(symbol, amount_usdt):
    try:
        exchange.set_leverage(3, symbol)
        order = exchange.create_market_buy_order(symbol, amount_usdt)
        logging.info(f"Long alım emri verildi: {amount_usdt} USDT karşılığında {symbol.split('/')[0]}")
    except Exception as e:
        logging.error(f"Long alım emri verirken hata oluştu: {e}")

def close_long_position(symbol, amount_coin):
    try:
        order = exchange.create_market_sell_order(symbol, amount_coin)
        logging.info(f"Long pozisyon kapatıldı: {amount_coin} {symbol.split('/')[0]}")
    except Exception as e:
        logging.error(f"Long pozisyon kapatılırken hata oluştu: {e}")

def place_short_order(symbol, amount_usdt):
    try:
        exchange.set_leverage(3, symbol)
        order = exchange.create_market_sell_order(symbol, amount_usdt)
        logging.info(f"Short alım emri verildi: {amount_usdt} USDT karşılığında {symbol.split('/')[0]}")
    except Exception as e:
        logging.error(f"Short alım emri verirken hata oluştu: {e}")

def close_short_position(symbol, amount_coin):
    try:
        order = exchange.create_market_buy_order(symbol, amount_coin)
        logging.info(f"Short pozisyon kapatıldı: {amount_coin} {symbol.split('/')[0]}")
    except Exception as e:
        logging.error(f"Short pozisyon kapatılırken hata oluştu: {e}")

def fetch_ohlcv(symbol, timeframe='15m', limit=100):
    try:
        data = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        logging.info(f"{len(data)} mum verisi alındı")
        return data
    except Exception as e:
        logging.error(f"OHLCV verisi alınırken hata oluştu: {e}")
        return []

def main(symbol):
    while True:
        coin_balance, usdt_balance = get_balance(symbol)
        
        ohlcv = fetch_ohlcv(symbol, timeframe='15m', limit=100)
        if not ohlcv:
            logging.warning("Veri alınamadı, 60 saniye sonra tekrar deneniyor...")
            time.sleep(60)
            continue

        try:
            rsi_15m, macd_15m, bb_lower, bb_upper, stoch_k, stoch_d = calculate_indicators(ohlcv)
        except Exception as e:
            logging.error(f"Göstergeler hesaplanırken hata oluştu: {e}")
            time.sleep(60)
            continue

        if rsi_15m is None or macd_15m is None or bb_lower is None or bb_upper is None or stoch_k is None or stoch_d is None:
            logging.warning("Göstergeler hesaplanamadı, 60 saniye sonra tekrar deneniyor...")
            time.sleep(60)
            continue

        logging.info(f"15 dakikalık RSI değeri: {rsi_15m}, MACD değeri: {macd_15m}, BB Lower: {bb_lower}, BB Upper: {bb_upper}, Stochastic %K: {stoch_k}, %D: {stoch_d}")

        # Alım ve satım sinyalleri
        if rsi_15m < 30 and macd_15m < 0 and ohlcv[-1][4] < bb_lower and stoch_k < 20 and stoch_k > stoch_d:  # Long alım sinyali
            logging.info(f"Long alım sinyali tespit edildi (RSI: {rsi_15m}, MACD: {macd_15m}, BB Lower: {bb_lower}, Stochastic %K: {stoch_k}, %D: {stoch_d})")
            if usdt_balance > 0:
                amount_usdt = usdt_balance * 0.5
                place_long_order(symbol, amount_usdt)

        elif rsi_15m > 70 and macd_15m > 0 and ohlcv[-1][4] > bb_upper and stoch_k > 80 and stoch_k < stoch_d:  # Long satım sinyali
            logging.info(f"Long satım sinyali tespit edildi (RSI: {rsi_15m}, MACD: {macd_15m}, BB Upper: {bb_upper}, Stochastic %K: {stoch_k}, %D: {stoch_d})")
            position = exchange.fetch_positions(symbol)
            if position:
                amount_coin = position[0]['amount']
                close_long_position(symbol, amount_coin)

        elif rsi_15m > 70 and macd_15m < 0 and ohlcv[-1][4] > bb_upper and stoch_k > 80 and stoch_k < stoch_d:  # Short alım sinyali
            logging.info(f"Short alım sinyali tespit edildi (RSI: {rsi_15m}, MACD: {macd_15m}, BB Upper: {bb_upper}, Stochastic %K: {stoch_k}, %D: {stoch_d})")
            if usdt_balance > 0:
                amount_usdt = usdt_balance * 0.5
                place_short_order(symbol, amount_usdt)

        elif rsi_15m < 30 and macd_15m > 0 and ohlcv[-1][4] < bb_lower and stoch_k < 20 and stoch_k > stoch_d:  # Short satım sinyali
            logging.info(f"Short satım sinyali tespit edildi (RSI: {rsi_15m}, MACD: {macd_15m}, BB Lower: {bb_lower}, Stochastic %K: {stoch_k}, %D: {stoch_d})")
            position = exchange.fetch_positions(symbol)
            if position:
                amount_coin = position[0]['amount']
                close_short_position(symbol, amount_coin)

        time.sleep(60)  # 15 dakika bekleyin

if __name__ == "__main__":
    symbol = 'XMR/USDT'
    main(symbol)
