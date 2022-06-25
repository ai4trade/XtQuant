# coding=utf-8
"""
取行情、财务等数据的相关接口
"""

import sys, traceback
from .IPythonApiClient import IPythonApiClient as RPCClient
from .IPythonApiClient import get_local_data_field_list as getLocalDataFieldList
from .IPythonApiClient import get_local_tick_data_batch as getLocalTickDataBatch
import json
import os

__all__ = [
    'subscribe_quote'
    , 'subscribe_whole_quote'
    , 'unsubscribe_quote'
    , 'run'
    , 'get_market_data'
    , 'get_local_data'
    , 'get_full_tick'
    , 'get_divid_factors'
    , 'get_l2_quote'
    , 'get_l2_order'
    , 'get_l2_transaction'
    , 'download_history_data'
    , 'get_financial_data'
    , 'download_financial_data'
    , 'get_instrument_detail'
    , 'get_instrument_type'
    , 'get_trading_dates'
    , 'get_sector_list'
    , 'get_stock_list_in_sector'
    , 'download_sector_data'
    , 'add_sector'
    , 'remove_sector'
    , 'get_index_weight'
    , 'download_index_weight'
    #, 'get_industry'
    #, 'get_etf_info'
    #, 'get_main_contract'
    #, 'download_history_contracts'
]

def try_except(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception:
            exc_type, exc_instance, exc_traceback = sys.exc_info()
            formatted_traceback = ''.join(traceback.format_tb(exc_traceback))
            message = '\n{0} raise {1}:{2}'.format(
                formatted_traceback,
                exc_type.__name__,
                exc_instance
            )
            # raise exc_type(message)
            print(message)
            return None

    return wrapper


CLIENT = None

from os.path import abspath, dirname
__curdir = dirname(abspath(__file__))

__rpc_config = __curdir + '/xtdata.ini'
__xtdata_config = __curdir + '/xtdata.ini'

from .IPythonApiClient import rpc_init
__rpc_init_status = rpc_init(__rpc_config)
if __rpc_init_status < 0:
    print(f'rpc初始化失败，配置文件：{__rpc_config}')

def get_client():
    global CLIENT
    if not CLIENT:
        CLIENT = RPCClient('client_xtdata', __xtdata_config)
        if not CLIENT:
            raise Exception("创建连接失败！")
    if not CLIENT.is_connected():
        if not CLIENT.connect():
            raise Exception("无法连接行情服务！")
    return CLIENT

def init_data_dir():
    try:
        client = get_client()
        data_dir = client.get_app_dir() + '/../userdata_mini/datadir'
    except Exception as e:
        data_dir = '../userdata_mini/datadir'
        print(f'本地数据路径：{data_dir}')
    return data_dir

data_dir = init_data_dir()

def create_array(shape, dtype_tuple, capsule, size):
    import numpy as np
    import ctypes
    
    ctypes.pythonapi.PyCapsule_GetPointer.restype = ctypes.POINTER(ctypes.c_char)
    ctypes.pythonapi.PyCapsule_GetPointer.argtypes = [ctypes.py_object, ctypes.c_char_p]
    buff = ctypes.pythonapi.PyCapsule_GetPointer(capsule, None)
    base_type = size * buff._type_
    
    for dim in shape[::-1]:
        base_type = dim * base_type
    p_arr_type = ctypes.POINTER(base_type)
    obj = ctypes.cast(buff, p_arr_type).contents
    obj._base = capsule
    return np.ndarray(shape = shape, dtype = np.dtype(dtype_tuple), buffer = obj)

from .IPythonApiClient import get_np_tool
get_np_tool().create_array = create_array

def get_industry(industry_name):
    '''
    获取行业成份股，支持申万行业和证监会行业
    :param industry_name: (str)行业名称
    :return: list
    '''
    client = get_client()
    return client.get_industry(industry_name)


def get_stock_list_in_sector(sector_name):
    '''
    获取板块成份股，支持客户端左侧板块列表中任意的板块，包括自定义板块
    :param sector_name: (str)板块名称
    :return: list
    '''
    client = get_client()
    return client.get_stock_list_in_sector(sector_name, 0)


def get_index_weight(index_code):
    '''
    获取某只股票在某指数中的绝对权重
    :param index_code: (str)指数名称
    :return: dict
    '''
    client = get_client()
    return client.get_weight_in_index(index_code)


def get_financial_data(stock_list, table_list=[], start_time='', end_time='', report_type='report_time'):
    '''
     获取财务数据
    :param stock_list: (list)合约代码列表
    :param table_list: (list)报表名称列表
    :param start_time: (str)起始时间
    :param end_time: (str)结束时间
    :param report_type: (str) 时段筛选方式 'announce_time' / 'report_time'
    :return:
        field: list[str]
        date: list[int]
        stock: list[str]
        value: list[list[float]]
    '''
    client = get_client()
    all_table = {
        'Balance' : 'ASHAREBALANCESHEET'
        , 'Income' : 'ASHAREINCOME'
        , 'CashFlow' : 'ASHARECASHFLOW'
        #, 'Capital' : 'CAPITAL'
    }
    
    if not table_list:
        table_list = list(all_table.keys())
    
    all_table_upper = {table.upper() : all_table[table] for table in all_table}
    req_list = []
    names = {}
    for table in table_list:
        req_table = all_table_upper.get(table.upper(), table)
        req_list.append(req_table)
        names[req_table] = table
    data = client.get_financial_data(stock_list, req_list, start_time, end_time, report_type)
    
    import time
    def conv_date(data, key):
        if key in data:
            data[key] = time.strftime('%Y%m%d', time.localtime(data[key] / 1000))
        return
    
    result = {}
    import pandas as pd
    for stock in data:
        stock_data = data[stock]
        result[stock] = {}
        for table in stock_data:
            table_data = stock_data[table]
            for row_data in table_data:
                conv_date(row_data, 'm_timetag')
                conv_date(row_data, 'm_anntime')
            result[stock][names[table]] = pd.DataFrame(table_data)
    return result


def get_market_data(field_list=[], stock_list=[], period='1d', start_time='', end_time='', count=-1,
                    dividend_type='none', fill_data=True):
    '''
    获取历史行情数据
    :param field_list: 行情数据字段列表，[]为全部字段
        K线可选字段：
            "time"                #时间戳
            "open"                #开盘价
            "high"                #最高价
            "low"                 #最低价
            "close"               #收盘价
            "volume"              #成交量
            "amount"              #成交额
            "settle"              #今结算
            "openInterest"        #持仓量
        分笔可选字段：
            "time"                #时间戳
            "lastPrice"           #最新价
            "open"                #开盘价
            "high"                #最高价
            "low"                 #最低价
            "lastClose"           #前收盘价
            "amount"              #成交总额
            "volume"              #成交总量
            "pvolume"             #原始成交总量
            "stockStatus"         #证券状态
            "openInt"             #持仓量
            "lastSettlementPrice" #前结算
            "askPrice1", "askPrice2", "askPrice3", "askPrice4", "askPrice5" #卖一价~卖五价
            "bidPrice1", "bidPrice2", "bidPrice3", "bidPrice4", "bidPrice5" #买一价~买五价
            "askVol1", "askVol2", "askVol3", "askVol4", "askVol5"           #卖一量~卖五量
            "bidVol1", "bidVol2", "bidVol3", "bidVol4", "bidVol5"           #买一量~买五量
    :param stock_list: 股票代码 "000001.SZ"
    :param period: 周期 分笔"tick" 分钟线"1m"/"5m" 日线"1d"
    :param start_time: 起始时间 "20200101" "20200101093000"
    :param end_time: 结束时间 "20201231" "20201231150000"
    :param count: 数量 -1全部/n: 从结束时间向前数n个
    :param dividend_type: 除权类型"none" "front" "back" "front_ratio" "back_ratio"
    :param fill_data: 对齐时间戳时是否填充数据，仅对K线有效，分笔周期不对齐时间戳
        为True时，以缺失数据的前一条数据填充
            open、high、low、close 为前一条数据的close
            amount、volume为0
            settle、openInterest 和前一条数据相同
        为False时，缺失数据所有字段填NaN
    :return: 数据集，分笔数据和K线数据格式不同
        period为'tick'时：{stock1 : value1, stock2 : value2, ...}
            stock1, stock2, ... : 合约代码
            value1, value2, ... : np.ndarray 数据列表，按time增序排列
        period为其他K线周期时：{field1 : value1, field2 : value2, ...}
            field1, field2, ... : 数据字段
            value1, value2, ... : pd.DataFrame 字段对应的数据，各字段维度相同，index为stock_list，columns为time_list
    '''
    return getMarketData(field_list, stock_list, period, start_time, end_time, count, dividend_type, fill_data)


@try_except
def getMarketData(field_list, stock_list, period, start_time, end_time, count, dividend_type, fill_data):
    client = get_client()
    if period in {'tick'}:
        return client.get_market_data2(field_list, stock_list, period, start_time, end_time, count, dividend_type, fill_data)
    if period in {'1m', '5m', '1d'}:
        import pandas as pd
        index, data = client.get_market_data2(field_list, stock_list, period, start_time, end_time, count, dividend_type, fill_data)
        result = {}
        for field in data:
            result[field] = pd.DataFrame(data[field], index = index[0], columns = index[1])
        return result
    return None


def get_local_data(field_list=[], stock_code=[], period='1d', start_time='', end_time='', count=-1,
                              dividend_type='none', fill_data=True, data_dir=data_dir):
    '''
    从本地数据缓存读取行情数据
    :param field_list: 行情数据字段列表，[]为全部字段
        K线可选字段：
            "time"                #时间戳
            "open"                #开盘价
            "high"                #最高价
            "low"                 #最低价
            "close"               #收盘价
            "volume"              #成交量
            "amount"              #成交额
            "settle"              #今结算
            "openInterest"        #持仓量
        分笔可选字段：
            "time"                #时间戳
            "lastPrice"           #最新价
            "open"                #开盘价
            "high"                #最高价
            "low"                 #最低价
            "lastClose"           #前收盘价
            "amount"              #成交总额
            "volume"              #成交总量
            "pvolume"             #原始成交总量
            "stockStatus"         #证券状态
            "openInt"             #持仓量
            "lastSettlementPrice" #前结算
            "askPrice1", "askPrice2", "askPrice3", "askPrice4", "askPrice5" #卖一价~卖五价
            "bidPrice1", "bidPrice2", "bidPrice3", "bidPrice4", "bidPrice5" #买一价~买五价
            "askVol1", "askVol2", "askVol3", "askVol4", "askVol5"           #卖一量~卖五量
            "bidVol1", "bidVol2", "bidVol3", "bidVol4", "bidVol5"           #买一量~买五量
    :param stock_code: 股票代码列表，例如：["000001.SZ", "600000.SH"]
    :param period: 周期 分笔"tick" 分钟线"1m"/"5m" 日线"1d"
    :param start_time: 开始时间，格式YYYYMMDD/YYYYMMDDhhmmss/YYYYMMDDhhmmss.milli，例如："20200427" "20200427093000" "20200427093000.000"
    :param end_time: 结束时间 格式同上
    :param count: 数量 -1全部，n: 从结束时间向前数n个
    :param dividend_type: 除权类型"none" "front" "back" "front_ratio" "back_ratio"
    :param data_dir: 本地数据缓存路径
    :param fill_data: 对齐时间戳时是否填充数据，仅对K线有效，分笔周期不对齐时间戳
        为True时，以缺失数据的前一条数据填充
            open、high、low、close 为前一条数据的close
            amount、volume为0
            settle、openInterest 和前一条数据相同
        为False时，缺失数据所有字段填NaN
    :return: 数据集，分笔数据和K线数据格式不同
        period为'tick'时：{stock1 : value1, stock2 : value2, ...}
            stock1, stock2, ... : 合约代码
            value1, value2, ... : np.ndarray 数据列表，按time增序排列
        period为其他K线周期时：{field1 : value1, field2 : value2, ...}
            field1, field2, ... : 数据字段
            value1, value2, ... : pd.DataFrame 字段对应的数据，各字段维度相同，index为stock_list，columns为time_list
    '''
    if period in {'tick'}:
        return getLocalTickDataBatch(data_dir, '000001.SH', field_list, stock_code, period, start_time, end_time, count)
    if period in {'1m', '5m', '1d'}:
        import pandas as pd
        index, data = getLocalDataFieldList(data_dir, '000001.SH', field_list, stock_code, period, start_time, end_time, count,
                                            dividend_type)
        result = {}
        for field in data:
            result[field] = pd.DataFrame(data[field], index = index[0], columns = index[1])
        return result
    return None


def get_l2_quote(field_list=[], stock_code='', start_time='', end_time='', count=-1):
    '''
    level2实时行情
    '''
    client = get_client()
    datas = client.get_market_data2(field_list, [stock_code], 'l2quote', start_time, end_time, count, 'none', False)
    if datas:
        return datas[stock_code]
    return None


def get_l2_order(field_list=[], stock_code='', start_time='', end_time='', count=-1):
    '''
    level2逐笔委托
    '''
    client = get_client()
    datas = client.get_market_data2(field_list, [stock_code], 'l2order', start_time, end_time, count, 'none', False)
    if datas:
        return datas[stock_code]
    return None


def get_l2_transaction(field_list=[], stock_code='', start_time='', end_time='', count=-1):
    '''
    level2逐笔成交
    '''
    client = get_client()
    datas = client.get_market_data2(field_list, [stock_code], 'l2transaction', start_time, end_time, count, 'none', False)
    if datas:
        return datas[stock_code]
    return None


def get_divid_factors(stock_code, start_time='', end_time=''):
    '''
    获取除权除息日及对应的权息
    :param stock_code: (str)股票代码
    :param date: (str)日期
    :return: pd.DataFrame 数据集
    '''
    client = get_client()
    datas = client.get_divid_factors(stock_code, start_time, end_time)
    import pandas as pd
    datas = pd.DataFrame(datas).T
    return datas


@try_except
def getDividFactors(stock_code, date):
    client = get_client()
    resData = client.get_divid_factors(stock_code, date)
    res = {resData[i]: [resData[i + 1][j] for j in
                        range(0, len(resData[i + 1]), 1)] for i in range(0, len(resData), 2)}
    if isinstance(res, dict):
        for k, v in res.items():
            if isinstance(v, list) and len(v) > 5:
                v[5] = int(v[5])
    return res


def get_main_contract(code_market):
    '''
    获取当前期货主力合约
    :param code_market: (str)股票代码
    :return: str
    '''
    client = get_client()
    return client.get_main_contract(code_market)


def timetag_to_datetime(timetag, format):
    '''
    将毫秒时间转换成日期时间
    :param timetag: (int)时间戳毫秒数
    :param format: (str)时间格式
    :return: str
    '''
    return timetagToDateTime(timetag, format)


@try_except
def timetagToDateTime(timetag, format):
    import time
    timetag = timetag / 1000
    time_local = time.localtime(timetag)
    return time.strftime(format, time_local)


def get_trading_dates(market, start_time='', end_time='', count=-1):
    '''
    根据市场获取交易日列表
    : param market: 市场代码 e.g. 'SH','SZ','IF','DF','SF','ZF'等
    : param start_time: 起始时间 '20200101'
    : param end_time: 结束时间 '20201231'
    : param count: 数据个数，-1为全部数据
    :return list(long) 毫秒数的时间戳列表
    '''
    client = get_client()
    datas = client.get_trading_dates_by_market(market, start_time, end_time, count)
    return list(datas.values())


def get_full_tick(code_list):
    '''
    获取盘口tick数据
    :param code_list: (list)stock.market组成的股票代码列表
    :return: dict
    {'stock.market': {dict}}
    '''
    client = get_client()
    resp_json = client.get_full_tick(code_list)
    return json.loads(resp_json)


def subscribe_callback_wrapper(callback):
    import traceback
    def subscribe_callback(datas):
        try:
            callback(datas)
        except:
            print('subscribe_quote callback error:', callback)
            traceback.print_exc()
    return subscribe_callback


def subscribe_quote(stock_code, period='1d', start_time='', end_time='', count=0, callback=None):
    '''
    订阅股票行情数据
    :param stock_code: 股票代码 e.g. "000001.SZ"
    :param start_time: 开始时间，格式YYYYMMDD/YYYYMMDDhhmmss/YYYYMMDDhhmmss.milli，e.g."20200427" "20200427093000" "20200427093000.000"
        若取某日全量历史数据，时间需要具体到秒，e.g."20200427093000"
    :param end_time: 结束时间 同“开始时间”
    :param count: 数量 -1全部/n: 从结束时间向前数n个
    :param period: 周期 分笔"tick" 分钟线"1m"/"5m" 日线"1d"
    :param callback:
        订阅回调函数onSubscribe(datas)
        :param datas: {stock : [data1, data2, ...]} 数据字典
    :return: int 订阅序号
    '''
    if callback:
        callback = subscribe_callback_wrapper(callback)
    return subscribeQuote({'stockCode': stock_code, 'period': period}, {'startTime': start_time, 'endTime': end_time},
                          count, callback)


@try_except
def subscribeQuote(meta, region, count, callback):
    client = get_client()
    return client.subscribe_quote(meta, region, count, callback)


def subscribe_whole_quote(code_list, callback=None):
    '''
    订阅全推数据
    :param code_list: 市场代码列表 ["SH", "SZ"]
    :param callback:
        订阅回调函数onSubscribe(datas)
        :param datas: {stock1 : data1, stock2 : data2, ...} 数据字典
    :return: int 订阅序号
    '''
    if callback:
        callback = subscribe_callback_wrapper(callback)
    return subscribeWholeQuote(code_list, callback)


@try_except
def subscribeWholeQuote(code_list, callback):
    client = get_client()
    return client.subscribe_whole_quote(code_list, callback)


def unsubscribe_quote(seq):
    '''
    :param seq: 订阅接口subscribe_quote返回的订阅号
    :return:
    '''
    client = get_client()
    return client.unsubscribe_quote(seq)


def run():
    '''阻塞线程接收行情回调'''
    import time
    client = get_client()
    while True:
        time.sleep(3)
        if not client.is_connected():
            raise Exception('行情服务连接断开')
            break
    return


def get_sector_list():
    '''
    获取板块列表
    :return: (list[str])
    '''
    client = get_client()
    return client.get_sector_list()


def add_sector(sector_name, stock_list):
    '''
    增加自定义板块
    :param sector_name: 板块名称 e.g. "我的自选"
    :param stock_list: (list)stock.market组成的股票代码列表
    '''
    client = get_client()
    return client.add_sector(sector_name, stock_list, 1)


def remove_sector(sector_name):
    '''
    删除自定义板块
    :param sector_name: 板块名称 e.g. "我的自选"
    '''
    client = get_client()
    return client.add_sector(sector_name, [], -1)


def get_instrument_detail(stock_code):
    '''
    获取合约信息
    :param stock_code: 股票代码 e.g. "600000.SH"
    :return: dict
        ExchangeID(str):合约市场代码, InstrumentID(str):合约代码, InstrumentName(str):合约名称, ProductID(str):合约的品种ID(期货), ProductName(str)合约的品种名称(期货),
        CreateDate(int):上市日期(期货), OpenDate(int):IPO日期(股票), ExpireDate(int):退市日或者到期日, PreClose(double):前收盘价格, SettlementPrice(double):前结算价格, 
        UpStopPrice(double):当日涨停价, DownStopPrice(double):当日跌停价, FloatVolume(double):流通股本, TotalVolume(double):总股本, LongMarginRatio(double):多头保证金率,
        ShortMarginRatio(double):空头保证金率, PriceTick(double):最小变价单位, VolumeMultiple(int):合约乘数(对期货以外的品种，默认是1),
        MainContract(int):主力合约标记，1、2、3分别表示第一主力合约，第二主力合约，第三主力合约, LastVolume(int):昨日持仓量, InstrumentStatus(int):合约停牌状态,
        IsTrading(bool):合约是否可交易, IsRecent(bool):是否是近月合约,
    '''
    client = get_client()
    inst = client.get_instrument_detail(stock_code)
    if not inst:
        return None
    field_list = [
            'ExchangeID'
            , 'InstrumentID'
            , 'InstrumentName'
            , 'ProductID'
            , 'ProductName'
            , 'CreateDate'
            , 'OpenDate'
            , 'ExpireDate'
            , 'PreClose'
            , 'SettlementPrice'
            , 'UpStopPrice'
            , 'DownStopPrice'
            , 'FloatVolume'
            , 'TotalVolume'
            , 'LongMarginRatio'
            , 'ShortMarginRatio'
            , 'PriceTick'
            , 'VolumeMultiple'
            , 'MainContract'
            , 'LastVolume'
            , 'InstrumentStatus'
            , 'IsTrading'
            , 'IsRecent'
        ]
    ret = {}
    for field in field_list:
        ret[field] = inst.get(field)
    return ret


def get_etf_info(stockCode):
    '''
    获取etf申赎清单
    :param stockCode: ETF代码 e.g. "159811.SZ"
    :return: dict
        etfCode(str):ETF代码, etfExchID(str):ETF市场, prCode(str):基金申赎代码, 
        stocks(dict):成分股 
            key: 成分股代码 e.g. "000063.SZ"
            value: dict
                componentExchID(str):成份股市场代码, componentCode(str):成份股代码, componentName(str):成份股名称, componentVolume(int):成份股数量
    '''
    client = get_client()
    return client.get_etf_info(stockCode)


def download_index_weight():
    '''
    下载指数权重数据
    '''
    client = get_client()
    client.down_index_weight()


def download_history_contracts():
    '''
    下载过期合约数据
    '''
    client = get_client()
    client.down_history_contracts()


class TimeListBuilder:
    def __init__(self):
        # param
        self.period = 3600000
        self.open_list = None  # [['093000', '113000'], ['130000', '150000']]

        # build up
        self.cur_date = 0
        self.date_offset = 3600000 * 8
        self.day_time_list = []
        self.cur_index = 0

    def init(self):
        if not self.open_list: return False
        if self.period <= 0: return False

        for scope in self.open_list:
            hour, minute, second = self.parse_time(scope[0])
            start = (((hour * 60) + minute) * 60 + second) * 1000
            hour, minute, second = self.parse_time(scope[1])
            end = (((hour * 60) + minute) * 60 + second) * 1000
            t = start + self.period
            while t <= end:
                self.day_time_list.append(t)
                t += self.period
        self.cur_index = 0

        if not self.day_time_list: return False
        return True

    def parse_time(self, ft):
        ft = int(ft)
        second = ft % 100
        ft = int((ft - second) / 100)
        minute = ft % 100
        ft = int((ft - minute) / 100)
        hour = ft % 100
        return hour, minute, second

    def get(self):
        if self.day_time_list:
            return self.cur_date + self.day_time_list[self.cur_index]
        else:
            return self.cur_date

    def next(self):
        self.cur_index += 1
        if self.cur_index >= len(self.day_time_list):
            self.cur_date += 86400000
            self.cur_index = 0

    def locate(self, t):
        day_time = t % 86400000
        self.cur_date = t - day_time - self.date_offset
        self.cur_index = 0
        for i in range(len(self.day_time_list)):
            te = self.day_time_list[i]
            if t < te:
                self.cur_index = i
                break


class MergeData:
    def __init__(self):
        # param
        self.period = 3600000
        self.open_list = None  # [['093000', '113000'], ['130000', '150000']]
        self.merge_func = None

        # build up
        self.timer = None

        # result
        self.time_list = []
        self.data_list = []

    def init(self):
        self.timer = TimeListBuilder()
        self.timer.open_list = self.open_list
        self.timer.period = self.period
        self.timer.init()

    def push(self, t, data):
        if self.time_list:
            te = self.time_list[-1]
            if t <= te:
                self.data_list[-1] = self.merge_func(self.data_list[-1], data)
            else:
                self.timer.next()
                te = self.timer.get()
                self.time_list.append(te)
                self.data_list.append(data)
        else:
            self.timer.locate(t)

            te = self.timer.get()
            self.time_list.append(te)
            self.data_list.append(data)


def merge_data_sum(data1, data2):
    return data1 + data2


def merge_data_max(data1, data2):
    return max(data1, data2)


def merge_data_min(data1, data2):
    return min(data1, data2)


def merge_data_first(data1, data2):
    return data1


def merge_data_last(data1, data2):
    return data2


def merge_data(time_list, data_list, period, open_list, field):
    merge_func = {}
    merge_func['open'] = merge_data_first
    merge_func['high'] = merge_data_max
    merge_func['low'] = merge_data_min
    merge_func['close'] = merge_data_last
    merge_func['volume'] = merge_data_sum
    merge_func['amount'] = merge_data_sum

    md = MergeData()
    md.period = period
    md.open_list = open_list
    md.merge_func = merge_func[field.lower()]
    md.init()

    for i in range(len(time_list)):
        md.push(time_list[i], data_list[i])

    return md.time_list, md.data_list


def download_history_data(stock_code, period, start_time='', end_time=''):
    '''
    :param stock_code: 股票代码 e.g. "000001.SZ"
    :param period: 周期 分笔"tick" 分钟线"1m"/"5m" 日线"1d"
    :param start_time: 开始时间，格式YYYYMMDD/YYYYMMDDhhmmss/YYYYMMDDhhmmss.milli，e.g."20200427" "20200427093000" "20200427093000.000"
        若取某日全量历史数据，时间需要具体到秒，e.g."20200427093000"
    :param end_time: 结束时间 同上，若是未来某时刻会被视作当前时间
    :return: bool 是否成功
    '''
    client = get_client()
    client.supply_history_data(stock_code, period, start_time, end_time)


supply_history_data = download_history_data


def download_financial_data(stock_list, table_list=[]):
    '''
    :param stock_list: 股票代码列表
    :param table_list: 财务数据表名列表，[]为全部表
        可选范围：['Balance','Income','CashFlow','PreshareIndex','Capital','Top10FlowHolder','Top10Holder','HolderNum']
    '''
    client = get_client()
    if not table_list:
        table_list = ['Balance','Income','CashFlow','PreshareIndex','Capital','Top10FlowHolder','Top10Holder','HolderNum']
    table_list = [table.upper() for table in table_list]
    
    status = [False, 0, 1, '']
    def on_progress(data):
        try:
            finished = data['finished']
            total = data['total']
            done = (finished >= total)
            status[0] = done
            status[1] = finished
            status[2] = total
            return done
        except:
            status[0] = True
            status[3] = 'exception'
            return True
    
    client.supply_finance_data(stock_list, table_list, on_progress)
    
    import time
    while not status[0]:
        time.sleep(0.1)
        if not client.is_connected():
            raise Exception('行情服务连接断开')
            break
    return


def get_instrument_type(stock_code):
    '''
    判断证券类型
    :param stock_code: 股票代码 e.g. "600000.SH"
    :return: dict{str : bool} {类型名：是否属于该类型}
    '''
    client = get_client()
    return client.get_stock_type(stock_code)

get_stock_type = get_instrument_type


def download_sector_data():
    '''
    下载行业板块数据
    '''
    client = get_client()
    client.down_all_sector_data()
