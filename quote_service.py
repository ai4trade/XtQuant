# -*- coding: utf-8 -*-

from xtquant import xtdata
import aiohttp, datetime, os
import akshare as ak
from tqdm import tqdm
import pandas as pd
from sanic import Sanic, Blueprint, response


api = Blueprint('xtdata', url_prefix='/quote/xtdata')

@api.listener('before_server_start')
async def before_server_start(app, loop):
    '''全局共享session'''
    global session
    jar = aiohttp.CookieJar(unsafe=True)
    session = aiohttp.ClientSession(cookie_jar=jar, connector=aiohttp.TCPConnector(ssl=False))

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

def download_history_kline(start_time='', period='1m'):
    '''
    下载历史K线数据
    '''
    code_list = get_shse_a_list()
    print("本次开始下载的时间为：", datetime.datetime.now().strftime("%Y%m%d%H%M%S"))
    for code in tqdm(code_list):
        xtdata.download_history_data(code, period=period, start_time=start_time)


def store_history_bond_tick(init=1):
    # 定义Clickhouse客户端
    if init:
        # 创建数据库表
        pass


if __name__ == '__main__':
    app = Sanic(name='xtdata')
    app.config.RESPONSE_TIMEOUT = 600000
    app.config.REQUEST_TIMEOUT = 600000
    app.config.KEEP_ALIVE_TIMEOUT = 600
    app.blueprint(api)
    app.run(host='0.0.0.0', port=7000, workers=1, auto_reload=True, debug=False)