#coding=utf-8


"""
常量定义模块
"""


"""
账号类型
"""
# 股票
SECURITY_ACCOUNT = 2
# 信用
CREDIT_ACCOUNT = 3

"""
委托类型
"""
STOCK_BUY = 23
STOCK_SELL = 24
CREDIT_BUY = 23    #担保品买入
CREDIT_SELL = 24   #担保品卖出
CREDIT_FIN_BUY = 27 #融资买入
CREDIT_SLO_SELL  = 28 #融券卖出
CREDIT_BUY_SECU_REPAY = 29 #买券还券
CREDIT_DIRECT_SECU_REPAY = 30 #直接还券
CREDIT_SELL_SECU_REPAY  = 31 #卖券还款
CREDIT_DIRECT_CASH_REPAY = 32 #直接还款
CREDIT_FIN_BUY_SPECIAL = 40 #专项融资买入
CREDIT_SLO_SELL_SPECIAL  = 41 #专项融券卖出
CREDIT_BUY_SECU_REPAY_SPECIAL = 42 #专项买券还券
CREDIT_DIRECT_SECU_REPAY_SPECIAL = 43 #专项直接还券
CREDIT_SELL_SECU_REPAY_SPECIAL  = 44 #专项卖券还款
CREDIT_DIRECT_CASH_REPAY_SPECIAL = 45 #专项直接还款

"""
报价类型
"""
# 最新价
LATEST_PRICE = 5
# 指定价/限价
FIX_PRICE = 11
# 上海最优五档即时成交剩余撤销
MARKET_SH_CONVERT_5_CANCEL = 42
# 上海最优五档即时成交剩余转限价
MARKET_SH_CONVERT_5_LIMIT = 43
# 深圳对手方最优价格
MARKET_PEER_PRICE_FIRST = 44
# 深圳本方最优价格
MARKET_MINE_PRICE_FIRST = 45
# 深圳即时成交剩余撤销
MARKET_SZ_INSTBUSI_RESTCANCEL = 46
# 深圳最优五档即时成交剩余撤销
MARKET_SZ_CONVERT_5_CANCEL = 47
# 深圳全额成交或撤销
MARKET_SZ_FULL_OR_CANCEL = 48


"""
市场类型
"""
# 上海市场
SH_MARKET = 0
# 深圳市场
SZ_MARKET = 1


"""
委托状态
"""
# 未报
ORDER_UNREPORTED = 48
# 待报
ORDER_WAIT_REPORTING = 49
# 已报
ORDER_REPORTED = 50
# 已报待撤
ORDER_REPORTED_CANCEL = 51
# 部成待撤
ORDER_PARTSUCC_CANCEL = 52
# 部撤
ORDER_PART_CANCEL = 53
# 已撤
ORDER_CANCELED = 54
# 部成
ORDER_PART_SUCC = 55
# 已成
ORDER_SUCCEEDED = 56
# 废单
ORDER_JUNK = 57
# 未知
ORDER_UNKNOWN = 255
