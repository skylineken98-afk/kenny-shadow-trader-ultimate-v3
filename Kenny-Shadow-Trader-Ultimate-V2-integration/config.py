import os
DEFAULT_TICKERS=['SPY','QQQ','IWM','TSLA','NVDA','AAPL','MSFT','AMD','MU','SOFI','HOOD','COIN','BAC','F','PLTR','AMZN','GOOGL']
CRYPTO=['BTC-USD','ETH-USD','SOL-USD','DOGE-USD']
FOREX=['EURUSD=X','GBPUSD=X','JPY=X']
TIMEFRAMES={'4H':('60d','60m',4),'1H':('30d','60m',1),'5M':('5d','5m',1)}
DB_PATH=os.getenv('SHADOW_DB','data/shadow_trader.sqlite3')
