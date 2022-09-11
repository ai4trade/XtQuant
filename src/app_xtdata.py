# -*- coding: utf-8 -*-

from xtquant import xtdata
import aiohttp, akshare, re, datetime, math, requests, pytz
import pandas as pd
import numpy as np
from sanic import Sanic, Blueprint, response
import pandas_market_calendars as mcal
from collections import defaultdict
import pandas_ta as ta
from tqdm import tqdm

api = Blueprint('xtdata', url_prefix='/api/xtdata')

@api.listener('before_server_start')
async def before_server_start(app, loop):
    '''全局共享session'''
    global session, cn_calendar, cn_tz, subscribe_ids, hs300_component, csi500_component, csi1000_component, all_a_tickers, last_day_price
    jar = aiohttp.CookieJar(unsafe=True)
    session = aiohttp.ClientSession(cookie_jar=jar, connector=aiohttp.TCPConnector(ssl=False))
    cn_calendar = mcal.get_calendar('SSE')
    cn_tz = pytz.timezone('Asia/Shanghai')
    subscribe_ids = []
    subscribe_ids.append(xtdata.subscribe_whole_quote(['SH', 'SZ', 'SHO', 'SZO', 'HK', 'IF', 'ZF', 'DF', 'SF']))
    hs300_component, csi500_component, csi1000_component = get_a_index_component()
    all_a_tickers = get_all_a_tickers()
    last_day_price = get_last_day_price(all_a_tickers)

@api.listener('after_server_stop')
async def after_server_stop(app, loop):
    '''关闭session'''
    for seq_num in subscribe_ids:
        xtdata.unsubscribe_quote(seq_num)
    await session.close()

async def req_json(url):
    async with session.get(url) as resp:
        return await resp.json()

def get_a_index_etf():
    '''
    获取 上证指数、深证成指、创业板指、科创50、上证50、沪深300、中证500、中证1000等主要指数ticker，以及活跃ETFticker
    '''
    indexes = ['000001.SH', '399001.SZ', '399006.SZ', '000688.SH', '000016.SH', '000300.SH', '000905.SH', '000852.SH']
    etf = ["512100.SH", "510050.SH", "510300.SH", "513050.SH", "515790.SH", "563000.SH", "588000.SH", "513180.SH", "513060.SH", "159915.SZ", "512880.SH", "512010.SH", "512660.SH", "159949.SZ", "510500.SH", "512690.SH", "518880.SH", "511260.SH", "512480.SH", "512200.SH", "515030.SH", "511380.SH", "512000.SH", "510330.SH", "513130.SH", "513500.SH", "513100.SH", "512800.SH", "512760.SH", "159920.SZ", "159605.SZ", "159941.SZ", "162411.SZ", "513330.SH", "510900.SH", "513090.SH", "513550.SH"]
    return indexes + etf 

def get_a_index_component():
    '''
    获取沪深300(000300)、中证500(000905)、中证1000(000852)指数成分股
    '''
    hs300 = akshare.index_stock_cons_weight_csindex(symbol="000300")
    hs300['stock'] = hs300.apply(lambda row: row['成分券代码'] + '.' + {'上海证券交易所' :'SH', '深圳证券交易所': 'SZ'}.get(row['交易所']), axis=1)
    csi500 = akshare.index_stock_cons_weight_csindex(symbol="000905")
    csi500['stock'] = csi500.apply(lambda row: row['成分券代码'] + '.' + {'上海证券交易所' :'SH', '深圳证券交易所': 'SZ'}.get(row['交易所']), axis=1)
    csi1000 = akshare.index_stock_cons_weight_csindex(symbol="000852")
    csi1000['stock'] = csi1000.apply(lambda row: row['成分券代码'] + '.' + {'上海证券交易所' :'SH', '深圳证券交易所': 'SZ'}.get(row['交易所']), axis=1)

    hs300_component = hs300.set_index('stock')[['指数代码', '成分券名称', '权重']].to_dict('index')
    csi500_component = csi500.set_index('stock')[['指数代码', '成分券名称', '权重']].to_dict('index')
    csi1000_component = csi1000.set_index('stock')[['指数代码', '成分券名称', '权重']].to_dict('index')

    return hs300_component, csi500_component, csi1000_component

def get_etf_option():
    '''
    获取50ETF、300ETF对应的当月/次月期权ticker
    '''
    select_option = {}

    etf_price = {}
    # 获取ETF行情
    etf_tick = xtdata.get_full_tick(['510300.SH', '510050.SH', '159919.SZ'])
    # 取今日开盘价/昨日收盘价均值
    for code in ['510300.SH', '510050.SH', '159919.SZ']:
        etf_price[code] = (etf_tick[code]['open'] + etf_tick[code]['lastClose']) / 2

    options = xtdata.get_stock_list_in_sector('上证期权') + xtdata.get_stock_list_in_sector('深证期权')
    # 获取主力期权(标的价格附近上下5档,当月/次月)
    for code in options:
        meta = xtdata.get_instrument_detail(code)
        # 期权名称
        name = meta['InstrumentName']
        # 对应的ETF
        etf = re.findall(r'\((\d+)\)', meta['ProductID'])[0] 
        etf = {'510300': '510300.SH', '510050': '510050.SH', '159919': '159919.SZ'}.get(etf)
        # 剩余有效日
        days = (datetime.date(year=int(str(meta['ExpireDate'])[:4]), month=int(str(meta['ExpireDate'])[4:6]), day=int(str(meta['ExpireDate'])[6:8])) - datetime.date.today()).days
        call_put = 'call' if '购' in name else 'put'
        if days < 32:
            if math.fabs(etf_price[etf] - int(name[-4:]) / 1000.0) < 0.2:
                select_option[code] = [etf, call_put, int(name[-4:]), days]
        elif days < 65:
            if math.fabs(etf_price[etf] - int(name[-4:]) / 1000.0) < 0.25:
                select_option[code] = [etf, call_put, int(name[-4:]), days]

    return select_option

def get_a_future_contract():
    '''
    获取中金所、大商所、郑商所、上期所的主要连续合约
    '''
    contract = xtdata.get_stock_list_in_sector('中金所') + xtdata.get_stock_list_in_sector('大商所') + xtdata.get_stock_list_in_sector('郑商所') + xtdata.get_stock_list_in_sector('上期所') 
    market_mapping = {'CZCE': 'ZF', 'DCE': 'DF', 'CFFEX': 'IF', 'SHFE': 'SF'}
    contract_main = [i.split('.')[0] + '.' + market_mapping.get(i.split('.')[1]) for i in contract if re.search(r'[A-Za-z]00\.[A-Z]', i)]
    if 'IM00.IF' not in contract_main:
        contract_main.append('IM00.IF')
    return contract_main

def get_a_cffex_contract():
    '''
    获取中金所股指期货和期权合约(上证50、沪深300[期权IO]、中证500、中证1000[期权MO])
    交割日期：每月第三个周五，遇节假日顺延
    '''
    trade_month = []
    today = datetime.date.today()
    this_month = datetime.date(today.year, today.month, 1)
    next_month1 = this_month + datetime.timedelta(days=31)
    next_month2 = this_month + datetime.timedelta(days=62)

    cnt = 0
    temp_date = None
    for i in pd.date_range(this_month, next_month1, freq='D'):
        if i.weekday() == 4:
            cnt += 1
        if cnt == 3:
            temp_date = i
            break

    month0_reverso_date = cn_calendar.schedule(start_date=temp_date, end_date=next_month1, tz=cn_tz).index.tolist()[0].date()
    if today > month0_reverso_date:
        # 本月交割日期之后，选择次月、次次月
        trade_month = ['{}{}'.format(next_month1.year % 100, str(next_month1.month).zfill(2)), '{}{}'.format(next_month2.year % 100, str(next_month2.month).zfill(2))]
    else:
        trade_month = ['{}{}'.format(this_month.year % 100, str(this_month.month).zfill(2)), '{}{}'.format(next_month1.year % 100, str(next_month1.month).zfill(2))]

    future_main_contract = ['{}{}.IF'.format(i, j) for i in ['IH', 'IF', 'IC', 'IM'] for j in trade_month]
    return future_main_contract, trade_month

def get_global_future_contract():
    '''
    外盘期货市场主要标的，包含汇率、利率、商品以及股指
    '''
    forex = ['DXY.OTC', 'EURUSD.OTC', 'GBPUSD.OTC', 'USDJPY.OTC', 'USDRUB.OTC', 'USDCNH.OTC', 'USDHKD.OTC']
    interest = ['US10YR.OTC', 'DE10YR.OTC', 'UK10YR.OTC', 'CN10YR.OTC', 'JP10YR.OTC', 'US5YR.OTC', 'US2YR.OTC', 'US1YR.OTC', 'US30YR.OTC', 'FR10YR.OTC', 'CN5YR.OTC', 'CN2YR.OTC', 'CN1YR.OTC', 'CN7YR.OTC']
    commodity = ['USHG.OTC', 'UKAH.OTC', 'UKCA.OTC', 'UKNI.OTC', 'UKPB.OTC', 'UKZS.OTC', 'UKSN.OTC', 'USZC.OTC', 'USZW.OTC', 'USYO.OTC', 'USZS.OTC', 'USLHC.OTC', 'UKOIL.OTC', 'USCL.OTC', 'USNG.OTC', 'XAUUSD.OTC', 'USGC.OTC', 'XAGUSD.OTC', 'USSI.OTC', 'AUTD.SGE', 'AGTD.SGE', 'PT9995.SGE', 'USPL.OTC', 'USPA.OTC']
    index = ["US500F.OTC", "VIXF.OTC", "US30F.OTC", "USTEC100F.OTC", "JP225F.OTC", "EU50F.OTC", "DE30F.OTC", "FR40F.OTC", "ES35F.OTC", "AU200F.OTC", "STOXX50F.OTC"]
    return forex + interest + commodity + index

def get_hk_index_comonent():
    '''
    获取恒生指数、恒生科技指数的成分股
    '''
    url = 'https://quotes.sina.cn/hq/api/openapi.php/HK_StockRankService.getHkStockList?page=1&num=100&symbol={}&asc=0&sort=changepercent&type={}'
    headers = {"user-agent": "sinafinance__6.4.0__iOS__248f2d8bf77fb1696a52f1bd4a55c1a256e54711__15.6__iPhone 11 Pro", "Host": "quotes.sina.cn", "accept-language": "zh-CN,zh-Hans;q=0.9"}

    component = {"HSI": {}, "HSTECH": {}}
    for index in ["HSI", "HSTECH"]:
        data = requests.get(url.format(index, index), headers=headers)
        try:
            data = data.json()['result']['data']['data']
            for item in data:
                component[index][item['symbol'] + '.HK'] = [index, item['name'], float(item['weight'])]
        except:
            pass
    return component["HSI"], component["HSTECH"]

@api.route('/subscribe', methods=['GET'])
async def subscribe(request, ticker_input=''):
    '''
    订阅单股行情: 获得tick/kline行情
    '''
    if ticker_input == '':
        ticker = request.args.get("ticker", "000001.SH")
    else:
        ticker = ticker_input
    period = request.args.get("period", "1m")
    start_time = request.args.get("start_time", "")
    end_time = request.args.get("end_time", "")
    subscribe_ids.append(xtdata.subscribe_quote(ticker, period, start_time=start_time, end_time=end_time, count=10))
    if ticker_input == '':
        return response.json({"data": subscribe_ids[-1]})
    else:
        return {"data": subscribe_ids[-1]}

@api.route('/download/history_data', methods=['GET'])
async def download_history_data(request):
    '''
    批量下载: 获得tick/kline数据
    '''
    ticker = request.args.get("ticker", "IM00.IF")
    period = request.args.get("period", "1m")
    start_time = request.args.get("start_time", "")
    end_time = request.args.get("end_time", "")

    xtdata.download_history_data(stock_code=ticker, period=period, start_time=start_time, end_time=end_time)
    return response.json({"download": ticker, "period": period})

def get_all_a_tickers():
    # 沪深指数
    index_ticker = xtdata.get_stock_list_in_sector("沪深指数")
    # 沪深A股
    stock_ticker = xtdata.get_stock_list_in_sector("沪深A股")
    # 沪深债券
    bond_ticker = xtdata.get_stock_list_in_sector("沪深债券")
    # 板块指数
    sector_ticker = xtdata.get_stock_list_in_sector("板块指数")
    # 沪深基金
    fund_ticker = xtdata.get_stock_list_in_sector("沪深基金")
    tickers = index_ticker + stock_ticker + bond_ticker + sector_ticker + fund_ticker
    return tickers

@api.route('/download/kline/1m', methods=['GET'])
async def download_kline_1m(request):
    '''
    下载A股市场全部1分钟K线
    '''
    start_time = request.args.get("start_time", datetime.datetime.now().strftime("%Y%m%d000001"))
    
    for ticker in tqdm(all_a_tickers):
       xtdata.download_history_data(stock_code=ticker, period='1m', start_time=start_time, end_time='')
    return response.json({"data": len(all_a_tickers)})

@api.route('/download/basic_data', methods=['GET'])
async def download_basic_data(request):
    '''
    下载基础数据: 财务报表、板块分类
    '''
    print("下载板块分类信息... ",  xtdata.download_sector_data())
    print("下载指数成分权重信息... ",  xtdata.download_index_weight())
    print("下载历史合约... ",  xtdata.download_history_contracts())
    all_a_stock = xtdata.get_stock_list_in_sector('沪深A股') 
    print("下载财务数据... ",  xtdata.download_financial_data(all_a_stock))

@api.route('/quote/kline', methods=['GET'])
async def quote_kline(request, tickers=''):
    '''
    查询市场行情: 获得kline数据
    '''
    if tickers == '':
        tickers = request.args.get("tickers", "IM00.IF,159919.SZ,00700.HK,10004407.SHO")
    period = request.args.get("period", "1m")
    start_time = request.args.get("start_time", "")
    end_time = request.args.get("end_time", "")
    count = request.args.get("count", "1")
    dividend_type = request.args.get("dividend_type", "none") # none 不复权 front 前复权 back 后复权 front_ratio 等比前复权 back_ratio 等比后复权
    stock_list = tickers.split(',')

    kline_data = xtdata.get_market_data(field_list=['time', 'open', 'high', 'low', 'close', 'volume', 'amount'], stock_list=stock_list, period=period, start_time=start_time, end_time=end_time, count=int(count), dividend_type=dividend_type, fill_data=True)

    quote_data = {}
    for stock in stock_list:
        df = pd.concat([kline_data[i].loc[stock].T for i in ['time', 'open', 'high', 'low', 'close', 'volume', 'amount']], axis=1)
        df.columns = ['time', 'open', 'high', 'low', 'close', 'volume', 'amount']
        df = df[df.volume !=0]
        df['time'] = df['time'].apply(lambda x: datetime.datetime.fromtimestamp(x / 1000.0).strftime("%Y-%m-%d %H:%M:%S"))
        df['ticker'] = stock
        df = df[['ticker', 'time', 'open', 'high', 'low', 'close', 'volume', 'amount']].values.tolist() 
        quote_data[stock] = df

    return response.json({"data": quote_data})

@api.route('/quote/tick', methods=['GET'])
async def quote_tick(request):
    '''
    查询市场行情: 获得tick数据
    '''
    tickers = request.args.get("tickers", "159919.SZ,00700.HK")
    stock_list = tickers.split(',')
    data = xtdata.get_full_tick(stock_list)
    return response.json({"data": data})

@api.route('/subscribe/kline/hs300', methods=['GET'])
async def subscribe_kline_hs300(request):
    '''
    订阅市场行情: 沪深300成分股1分钟K线行情
    '''
    seq_ids = []
    for ticker in hs300_component:
       seq_id =  await subscribe(request, ticker_input=ticker)
       seq_ids.append(seq_id.get('data', -1))
    return response.json({"data": seq_ids})

@api.route('/quote/kline/hs300', methods=['GET'])
async def quote_kline_hs300(request):
    '''
    查询市场行情: 沪深300成分股1分钟K线行情
    '''
    return await quote_kline(request, ','.join(list(hs300_component)))

@api.route('/quote/instrument/detail', methods=['GET'])
async def get_instrument_detail(request):
    '''
    获取合约基础信息
    '''
    ticker = request.args.get("ticker", "159919.SZ")
    return response.json({"data": xtdata.get_instrument_detail(ticker)})

@api.route('/quote/sector/list', methods=['GET'])
async def get_sector_list(request):
    '''
    获取板块列表
    '''
    return response.json({"data": xtdata.get_sector_list()})

@api.route('/quote/sector/component', methods=['GET'])
async def get_sector_component(request):
    '''
    获取板块成分股列表
    '''
    sector_name = request.args.get("sector", "沪深ETF")
    return response.json({"data": xtdata.get_stock_list_in_sector(sector_name)})

def get_last_day_price(tickers=['159919.SZ', '510050.SH', '000810.SZ'], trade_day=datetime.date.today().strftime("%Y%m%d")):
    kline_data = xtdata.get_market_data(field_list=['close'], stock_list=tickers, period='1m', start_time='', end_time=trade_day + '080000', count=1, dividend_type='front', fill_data=True)
    result = {}
    for ticker in tickers:
        result[ticker] = kline_data['close'].loc[ticker].values[0]
    return result

@api.route('/feature/tech', methods=['GET'])
async def feature_tech(request, tickers=''):
    '''
    计算实时技术特征
    '''
    if tickers == '':
        tickers = request.args.get("tickers", "159919.SZ,510050.SH,000810.SZ")
    stock_list = tickers.split(',')
    start_time = request.args.get("start_time", datetime.datetime.now().strftime("%Y%m%d000001"))
    end_time = request.args.get("end_time", datetime.datetime.now().strftime("%Y%m%d%H%M%S"))

    kline_data = xtdata.get_market_data(field_list=['time', 'open', 'high', 'low', 'close', 'volume', 'amount'], stock_list=stock_list, period='1m', start_time=start_time, end_time=end_time)

    features = []
    for stock in stock_list:
        kline_df = pd.concat([kline_data[i].loc[stock].T for i in ['time', 'open', 'high', 'low', 'close', 'volume', 'amount']], axis=1)
        kline_df.columns = ['time', 'open', 'high', 'low', 'close', 'volume', 'amount']
        kline_df['trade_time'] = kline_df['time'].apply(lambda x: datetime.datetime.fromtimestamp(x / 1000.0))
        ticker= stock.split('.')[0] + {'SH': '.XSHG', 'SZ': '.XSHE'}.get(stock.split('.')[1])
        trade_date = kline_df['trade_time'].iloc[0].strftime("%Y-%m-%d")
        trade_time = int(kline_df['time'].iloc[-1] // 1000)
        kline_df['price_last'] = last_day_price.get(stock, None)
        kline_df['minute_avg'] = (kline_df['high'] + kline_df['low']) / 2
        kline_df['minutes_of_day'] = kline_df.trade_time.dt.hour * 60 + kline_df.trade_time.dt.minute

        kline_df['price_open'] = kline_df['minute_avg'].iloc[0]
        kline_df['pct_daily'] = (kline_df['close'] - kline_df['price_last']).div(kline_df['price_last'])
        kline_df['pct_intraday'] = (kline_df['close'] - kline_df['price_open']).div(kline_df['price_open'])

        pct_daily = kline_df['pct_daily'].iloc[-1]
        pct_intraday = kline_df['pct_intraday'].iloc[-1]
        rsi_3 = (kline_df.ta.rsi(length=3) / 100).fillna(0.5).iloc[-1]
        cmo_5 = (kline_df.ta.cmo(length=5) / 100).fillna(0.).iloc[-1]
        cmo_8 = (kline_df.ta.cmo(length=8) / 100).fillna(0.).iloc[-1]
        kdj_9_3 = (kline_df.ta.kdj(min(9, len(kline_df)), 3) / 100).fillna(0.5).iloc[-1].tolist() 
        willr_3 = (kline_df.ta.willr(length=3) / 100).clip(-1, 1).fillna(-0.5).iloc[-1]
        willr_5 = (kline_df.ta.willr(length=5) / 100).clip(-1, 1).fillna(-0.5).iloc[-1]
        willr_10 = (kline_df.ta.willr(length=min(10, len(kline_df))) / 100).clip(-1, 1).fillna(-0.5).iloc[-1]
        dpo_5 = (kline_df.ta.dpo(length=5, lookahead=False) * 10).clip(-3, 3).fillna(0.0).iloc[-1]
        log_return_10 = (kline_df.ta.log_return(length=10) * 10).clip(-3, 3).fillna(0.).iloc[-1]
        log_return_5 = (kline_df.ta.log_return(length=5) * 10).clip(-3, 3).fillna(0.).iloc[-1]
        log_return_3 = (kline_df.ta.log_return(length=3) * 10).clip(-3, 3).fillna(0.).iloc[-1]
        zscore_10 = (kline_df.ta.zscore(length=10)).clip(-3, 3).fillna(0.).iloc[-1]
        zscore_5 = (kline_df.ta.zscore(length=5)).clip(-3, 3).fillna(0.).iloc[-1]
        zscore_3 = (kline_df.ta.zscore(length=3)).clip(-3, 3).fillna(0.).iloc[-1]
        pct_volatility = (10 * (kline_df['high'] - kline_df['low']).div(kline_df['minute_avg'])).clip(-1, 1).fillna(0.).iloc[-1]
        rolling_pct_volatility_3 =  (20 * (kline_df['high'].rolling(3, min_periods=1).max() - kline_df['low'].rolling(3, min_periods=1).min()).div(kline_df['minute_avg'])).clip(-3, 3).fillna(0.).iloc[-1]
        rolling_pct_volatility_5 =  (20 * (kline_df['high'].rolling(5, min_periods=1).max() - kline_df['low'].rolling(5, min_periods=1).min()).div(kline_df['minute_avg'])).clip(-3, 3).fillna(0.).iloc[-1]
        rolling_pct_volatility_10 =  (20 * (kline_df['high'].rolling(10, min_periods=1).max() - kline_df['low'].rolling(10, min_periods=1).min()).div(kline_df['minute_avg'])).clip(-3.1, 3.1).fillna(0.).iloc[-1]

        feature = [ticker, trade_date, trade_time] +  (np.array([pct_daily, pct_intraday, rsi_3 , cmo_5, cmo_8] + kdj_9_3 +[willr_3, willr_5, willr_10, dpo_5, log_return_3, log_return_5, log_return_10, zscore_3, zscore_5, zscore_10, pct_volatility, rolling_pct_volatility_3, rolling_pct_volatility_5, rolling_pct_volatility_10]) * 10000).clip(-2**15, 2**15-1).round().tolist()
        features.append(feature)
    return response.json({"data": features})

if __name__ == '__main__':
    app = Sanic(name='xtquant')
    app.config.RESPONSE_TIMEOUT = 600000
    app.config.REQUEST_TIMEOUT = 600000
    app.config.KEEP_ALIVE_TIMEOUT = 6000
    app.blueprint(api)
    app.run(host='0.0.0.0', port=7800, workers=4, auto_reload=True, debug=False)