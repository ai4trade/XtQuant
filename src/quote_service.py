# -*- coding: utf-8 -*-

from xtquant import xtdata
import aiohttp, datetime, os, math
import akshare as ak
from tqdm import tqdm
import pandas as pd
from sanic import Sanic, Blueprint, response


api = Blueprint('xtdata', url_prefix='/quote/xtdata')

@api.listener('before_server_start')
async def before_server_start(app, loop):
    '''全局共享session'''
    global session, base_url
    jar = aiohttp.CookieJar(unsafe=True)
    session = aiohttp.ClientSession(cookie_jar=jar, connector=aiohttp.TCPConnector(ssl=False))
    base_url = 'http://127.0.0.1:7700/quote/xtdata'

async def req_json(url):
    async with session.get(url) as resp:
        return await resp.json()

def get_shse_a_list():
    '''
    获取沪深指数、所有A股、ETF、债券列表
    '''
    index_code = ['000001.SH', '399001.SZ', '399006.SZ', '000688.SH', '000300.SH', '000016.SH', '000905.SH', '000852.SH'] # 上证指数、深证成指、创业板指、科创50、沪深300、上证50、中证500、中证1000
    a_code = xtdata.get_stock_list_in_sector('沪深A股')
    etf_code =  xtdata.get_stock_list_in_sector('沪深ETF')
    #bond_code = [i for i in xtdata.get_stock_list_in_sector('沪深债券') if i[:3] in {'110',  '111', '113', '118', '123', '127', '128'}]
    bond_code = get_bond_history()[-1]

    return index_code + a_code + etf_code + bond_code


def get_bond_history():
    bond_zh_cov_df = ak.bond_zh_cov()
    # 排除至今未上市的转债
    bond_zh_cov_df =  bond_zh_cov_df[bond_zh_cov_df['上市时间'] <= datetime.date.today()]
    stock_code_list, bond_code_list = [], []
    for _, row in bond_zh_cov_df.iterrows():
        if row['债券代码'].startswith('11'):
            market = '.SH'
        else:
            market = '.SZ'
        stock_code_list.append(row['正股代码'] + market)
        bond_code_list.append(row['债券代码'] + market)
    return stock_code_list, bond_code_list

def get_bond_spot():
    bond_cov_comparison_df = ak.bond_cov_comparison()
    # 排除至今未上市的转债
    bond_cov_comparison_df =  bond_cov_comparison_df[bond_cov_comparison_df['上市日期'] !='-']

    stock_code_list, bond_code_list = [], []
    for _, row in bond_cov_comparison_df.iterrows():
        if row['转债代码'].startswith('11'):
            market = '.SH'
        else:
            market = '.SZ'
        stock_code_list.append(row['正股代码'] + market)
        bond_code_list.append(row['转债代码'] + market)
    return stock_code_list, bond_code_list

def download_history_bond_tick(init=1):
    '''
    下载历史转债tick数据(20200401起)
    '''
    # 初始化：获取转债及其正股代码
    if init:
        # 包含历史过期代码
        stock_code_list, bond_code_list = get_bond_history()
    else:
        # 仅当日代码
        stock_code_list, bond_code_list = get_bond_spot()
    
    # 数据下载目录
    data_dir = 'E:\\QMT\\userdata_mini\\datadir\\'
    for stock, bond in tqdm(zip(stock_code_list, bond_code_list), total=len(stock_code_list)):
        print("开始下载：股票 {}, 转债 {}".format(stock, bond))
        # 上海转债: 已下载的数据
        if bond.endswith("SH"):
            dir_path = data_dir + "\\SH\\0\\" + bond.split('.', 1)[0]
        # 深圳转债：已下载的数据
        else:
            dir_path = data_dir + "\\SZ\\0\\" + bond.split('.', 1)[0]
        
        start_date = '20200401' # QMT支持的最久数据时间
        # 如果路径存在，断点续传，重设起点下载时间
        if os.path.exists(dir_path):
            downloaded = os.listdir(dir_path)
            # 获取已下载的最大日期，作为本次同步的起始时间
            if len(downloaded) > 0:
                start_date = max(downloaded).split('.', 1)[0]
            
        xtdata.download_history_data(stock_code=bond, period='tick', start_time=start_date)
        xtdata.download_history_data(stock_code=stock, period='tick', start_time=start_date)
    

def download_history_kline(code_list, start_time='', period='1m'):
    '''
    下载历史K线数据:
    code_list: 股票代码， 如：get_shse_a_list()
    '''
    print("本次开始下载的时间为：", datetime.datetime.now().strftime("%Y%m%d%H%M%S"))
    for code in tqdm(code_list):
        xtdata.download_history_data(code, period=period, start_time=start_time)


def get_local_tick_data(code='110075.SH', start_time='19700101'):
    # 获取本地数据
    df = xtdata.get_local_data(stock_code=[code], period='tick', field_list=['time', 'open', 'lastPrice', 'high', 'low', 'lastClose', 'volume', 'amount', 'askPrice', 'bidPrice', 'askVol', 'bidVol'], start_time=start_time, end_time=start_time)

    # 转成DataFRame
    df = pd.DataFrame(df[code])
    if len(df) < 1:
        return df

    # 日期处理
    df['trade_time'] = df['time'].apply(lambda x: datetime.datetime.fromtimestamp(x / 1000.0)) # , cn_tz
    df['trade_day'] = df['trade_time'].apply(lambda x: x.date())
    df['trade_minute'] = df['trade_time'].apply(lambda x: x.hour * 60 + x.minute)
    df['trade_second'] = df['trade_time'].apply(lambda x: x.hour * 3600 + x.minute * 60 + x.second)
    df = df[df.trade_second <= 54001] # 排除盘后交易
    df = df[df.trade_second >= 33840] # 保留最后一分钟的集合竞价数据
    df = df.reset_index(drop=True)

    # 重新计算成交量、成交额
    df['volume_deal'] = df.groupby(['trade_day'])['volume'].diff(periods=1).fillna(0)
    df['amount_deal'] = df.groupby(['trade_day'])['amount'].diff(periods=1).fillna(0)

    # 重新选择列
    df['code'] = '110075.SH'
    df['close'] = df['lastPrice'] # 收盘
    df['last'] = df['lastClose'] # 昨收
    df = df[['code', 'trade_time', 'trade_day', 'trade_minute', 'open', 'close', 'high', 'low', 'last', 'volume', 'amount', 'volume_deal', 'amount_deal', 'askPrice', 'bidPrice', 'askVol', 'bidVol']]

    return df


def get_sector_list():
    '''
    获取沪深指数、行业指数
    '''
    sector_1 = xtdata.get_stock_list_in_sector('证监会行业板块指数')
    sector_1 = [(i, xtdata.get_instrument_detail(i)['InstrumentName'], '证监会一级行业') for i in sector_1]

    sector_2 = xtdata.get_stock_list_in_sector('板块指数')
    sector_2 = [(i, xtdata.get_instrument_detail(i)['InstrumentName'], '证监会二级行业') for i in sector_2 if i.startswith('23')]


    index_code = [('000001.SH', '上证指数', '大盘指数'), ('399001.SZ', '深证成指', '大盘指数'), ('399006.SZ', '创业板指', '大盘指数'), ('000688.SH', '科创50', '大盘指数'), ('000300.SH', '沪深300', '大盘指数'), ('000016.SH', '上证50', '大盘指数'), ('000905.SH', '中证500', '大盘指数'), ('000852.SH', '中证1000', '大盘指数')]

    code_list = {i[0]: i[1:] for i in sector_1 + sector_2 + index_code}

    return code_list

def get_local_kline_data(code='230130.BKZS', start_time='20200101', period='1d', code_list=get_sector_list()):
    # 获取本地数据
    df = xtdata.get_local_data(stock_code=[code], period=period, field_list=['time', 'open', 'close', 'high', 'low', 'volume', 'amount'], start_time=start_time, end_time=datetime.datetime.now().strftime('%Y%m%d%H%M%S'))
    df = pd.concat([df[i].T.rename(columns={code:i}) for i in ['time', 'open', 'close', 'high', 'low', 'volume', 'amount']], axis=1)

    if len(df) < 1:
        return df

    # 时间转换
    df['trade_day'] = df['time'].apply(lambda x: datetime.datetime.fromtimestamp(x / 1000.0).date())

    # 重新选择列
    df['code'] = code
    df['sector_name'] = df['code'].apply(lambda x: code_list[x][0])
    df['sector_type'] = df['code'].apply(lambda x: code_list[x][1])
    df = df[['code', 'trade_day', 'sector_name', 'sector_type', 'open', 'close', 'high', 'low', 'volume', 'amount']]

    return df

def store_history_bond_tick(init=1):
    # 定义Clickhouse客户端
    if init:
        # 创建数据库表
        pass


@api.route('/sync/bond/tick', methods=['GET'])
async def sync_bond_tick(request):
    stock_code_list, bond_code_list = get_bond_spot()
    # 数据下载目录
    data_dir = 'E:\\QMT\\userdata_mini\\datadir\\'
    for stock, bond in tqdm(zip(stock_code_list, bond_code_list), total=len(stock_code_list)):
        print("开始下载：股票 {}, 转债 {}".format(stock, bond))
        # 上海转债: 已下载的数据
        if bond.endswith("SH"):
            dir_path = data_dir + "\\SH\\0\\" + bond.split('.', 1)[0]
        # 深圳转债：已下载的数据
        else:
            dir_path = data_dir + "\\SZ\\0\\" + bond.split('.', 1)[0]
        
        start_date = '20200401' # QMT支持的最久数据时间
        # 如果路径存在，断点续传，重设起点下载时间
        if os.path.exists(dir_path):
            downloaded = os.listdir(dir_path)
            # 获取已下载的最大日期，作为本次同步的起始时间
            if len(downloaded) > 0:
                start_date = max(downloaded).split('.', 1)[0]
            
        xtdata.download_history_data(stock_code=bond, period='tick', start_time=start_date)

    return response.json({"status": 0}, ensure_ascii=False)

@api.route('/sync/stock/kline', methods=['GET'])
async def sync_stock_kline(request):
    code_list = get_shse_a_list()
    start_time = request.args.get('start_time', "20220630160000")
    period = request.args.get('period', "1m")
    for code in tqdm(code_list):
        xtdata.download_history_data(code, period=period, start_time=start_time)
    return response.json({"status": 0}, ensure_ascii=False)

if __name__ == '__main__':
    app = Sanic(name='xtdata')
    app.config.RESPONSE_TIMEOUT = 600000
    app.config.REQUEST_TIMEOUT = 600000
    app.config.KEEP_ALIVE_TIMEOUT = 600
    app.blueprint(api)
    app.run(host='0.0.0.0', port=7700, workers=1, auto_reload=True, debug=False)