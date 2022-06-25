#coding=utf-8
import asyncio
import os
from threading import Thread
from concurrent.futures import ThreadPoolExecutor
from . import xtpythonclient as XTQC
from . import xttype

# 交易回调类
class XtQuantTraderCallback(object):
    def on_disconnected(self):
        """
        """
        pass

    def on_stock_order(self, order):
        """
        :param order: XtOrder对象
        :return:
        """
        pass

    def on_stock_asset(self, asset):
        """
        :param asset: XtAsset对象
        :return:
        """
        pass

    def on_stock_trade(self, trade):
        """
        :param trade: XtTrade对象
        :return:
        """
        pass

    def on_stock_position(self, position):
        """
        :param position: XtPosition对象
        :return:
        """
        pass

    def on_order_error(self, order_error):
        """
        :param order_error: XtOrderError 对象
        :return:
        """
        pass

    def on_cancel_error(self, cancel_error):
        """
        :param cancel_error:XtCancelError 对象
        :return:
        """
        pass

    def on_order_stock_async_response(self, response):
        """
        :param response: XtOrderResponse 对象
        :return:
        """
        pass

    def on_cancel_order_stock_async_response(self, response):
        """
        :param response: XtCancelOrderResponse 对象
        :return:
        """
        pass

class XtQuantTrader(object):
    def __init__(self, path, session, callback=None):
        """
        :param path: mini版迅投极速交易客户端安装路径下，userdata文件夹具体路径
        :param session: 当前任务执行所属的会话id
        :param callback: 回调方法
        """
        self.async_client = XTQC.XtQuantAsyncClient(path.encode('gb18030'), 'xtquant', session)
        self.callback = callback

        self.connected = False

        self.oldloop = asyncio.get_event_loop()
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.requests = {}

        self.async_order_stock_sequences = set()
        self.async_cancel_order_stock_sequences = set()

        self.handled_async_order_stock_order_id = set()
        self.sync_order_stock_order_id = set()
        self.queuing_order_errors = {}

        self.handled_async_cancel_order_stock_order_id = set()
        self.handled_async_cancel_order_stock_order_sys_id = set()
        self.sync_cancel_order_stock_order_id = set()
        self.sync_cancel_order_stock_order_sys_id = set()
        self.queuing_cancel_errors_by_order_id = {}
        self.queuing_cancel_errors_by_order_sys_id = {}

        # 连接断开推送
        self.disconnected_sem = asyncio.Semaphore(0)

        def on_disconnected_callback():
            self.loop.call_soon_threadsafe(self.disconnected_sem.release)

        self.async_client.bindOnDisconnectedCallback(on_disconnected_callback)

        def on_subscribe_resp_callback(seq, resp):
            future = self.requests[seq]
            self.loop.call_soon_threadsafe(future.set_result, resp)

        self.async_client.bindOnSubscribeRespCallback(on_subscribe_resp_callback)

        def on_unsubscribe_resp_callback(seq, resp):
            future = self.requests[seq]
            self.loop.call_soon_threadsafe(future.set_result, resp)

        self.async_client.bindOnUnsubscribeRespCallback(on_unsubscribe_resp_callback)

        # 异步下单反馈
        self.async_order_response_sem = asyncio.Semaphore(0)
        self.async_order_responses = []

        def on_order_stock_resp_callback(seq, resp):
            if seq in self.async_order_stock_sequences:
                self.async_order_stock_sequences.remove(seq)
                self.async_order_responses.append(xttype.XtOrderResponse(resp.m_strAccountID, resp.m_nOrderID, resp.m_strStrategyName, resp.m_strOrderRemark, seq))
                self.loop.call_soon_threadsafe(self.async_order_response_sem.release)
            else:
                self.sync_order_stock_order_id.add(resp.m_nOrderID)
                future = self.requests[seq]
                self.loop.call_soon_threadsafe(future.set_result, resp.m_nOrderID)

        self.async_client.bindOnOrderStockRespCallback(on_order_stock_resp_callback)

        # 异步撤单反馈
        self.async_cancel_order_response_sem = asyncio.Semaphore(0)
        self.async_cancel_order_responses = []

        def on_cancel_order_stock_resp_callback(seq, resp):
            if seq in self.async_cancel_order_stock_sequences:
                self.async_cancel_order_stock_sequences.remove(seq)
                self.async_cancel_order_responses.append(xttype.XtCancelOrderResponse(resp.m_strAccountID, resp.m_nCancelResult, resp.m_nOrderID, resp.m_strOrderSysID, seq))
                self.loop.call_soon_threadsafe(self.async_cancel_order_response_sem.release)
            else:
                if not resp.m_strOrderSysID:
                    self.sync_cancel_order_stock_order_id.add(resp.m_nOrderID)
                else:
                    self.sync_cancel_order_stock_order_sys_id.add(resp.m_strOrderSysID)
                future = self.requests[seq]
                self.loop.call_soon_threadsafe(future.set_result, resp.m_nCancelResult)

        self.async_client.bindOnCancelOrderStockRespCallback(on_cancel_order_stock_resp_callback)

        def on_query_stock_orders_resp_callback(seq, resp):
            future = self.requests[seq]
            self.loop.call_soon_threadsafe(future.set_result, resp)

        self.async_client.bindOnQueryStockOrdersCallback(on_query_stock_orders_resp_callback)

        def on_query_stock_asset_resp_callback(seq, resp):
            future = self.requests[seq]
            self.loop.call_soon_threadsafe(future.set_result, resp)

        self.async_client.bindOnQueryStockAssetCallback(on_query_stock_asset_resp_callback)

        def on_query_stock_trades_resp_callback(seq, resp):
            future = self.requests[seq]
            self.loop.call_soon_threadsafe(future.set_result, resp)

        self.async_client.bindOnQueryStockTradesCallback(on_query_stock_trades_resp_callback)

        def on_query_stock_positions_resp_callback(seq, resp):
            future = self.requests[seq]
            self.loop.call_soon_threadsafe(future.set_result, resp)

        self.async_client.bindOnQueryStockPositionsCallback(on_query_stock_positions_resp_callback)

        def on_query_credit_detail_resp_callback(seq, resp):
            future = self.requests[seq]
            self.loop.call_soon_threadsafe(future.set_result, resp)

        self.async_client.bindOnQueryCreditDetailRespCallback(on_query_credit_detail_resp_callback)

        def on_query_stk_compacts_resp_callback(seq, resp):
            future = self.requests[seq]
            self.loop.call_soon_threadsafe(future.set_result, resp)

        self.async_client.bindOnQueryStkCompactsRespCallback(on_query_stk_compacts_resp_callback)

        def on_query_credit_subjects_resp_callback(seq, resp):
            future = self.requests[seq]
            self.loop.call_soon_threadsafe(future.set_result, resp)

        self.async_client.bindOnQueryCreditSubjectsRespCallback(on_query_credit_subjects_resp_callback)

        def on_query_credit_slo_code_resp_callback(seq, resp):
            future = self.requests[seq]
            self.loop.call_soon_threadsafe(future.set_result, resp)

        self.async_client.bindOnQueryCreditSloCodeRespCallback(on_query_credit_slo_code_resp_callback)

        def on_query_credit_assure_resp_callback(seq, resp):
            future = self.requests[seq]
            self.loop.call_soon_threadsafe(future.set_result, resp)

        self.async_client.bindOnQueryCreditAssureRespCallback(on_query_credit_assure_resp_callback)

        # stock委托失败主推
        self.order_error_sem = asyncio.Semaphore(0)
        self.order_errors = []

        def on_order_error_callback(order_error):
            self.order_errors.append(order_error)
            self.loop.call_soon_threadsafe(self.order_error_sem.release)

        self.async_client.bindOnOrderErrorCallback(on_order_error_callback)

        # stock撤单失败主推
        self.cancel_error_sem = asyncio.Semaphore(0)
        self.cancel_orders = []

        def on_cancel_error_callback(cancel_error):
            self.cancel_orders.append(cancel_error)
            self.loop.call_soon_threadsafe(self.cancel_error_sem.release)

        self.async_client.bindOnCancelErrorCallback(on_cancel_error_callback) 
        
        # asset资金主推
        self.stock_asset_sem = asyncio.Semaphore(0)
        self.stock_assets = []

        def on_stock_asset_callback(asset):
            self.stock_assets.append(asset)
            self.loop.call_soon_threadsafe(self.stock_asset_sem.release)

        self.async_client.bindOnStockAssetCallback(on_stock_asset_callback)

        
        # stock委托主推
        self.stock_orders_sem = asyncio.Semaphore(0)
        self.stock_orders = []

        def on_stock_order_callback(order):
            self.stock_orders.append(order)
            self.loop.call_soon_threadsafe(self.stock_orders_sem.release)

        self.async_client.bindOnStockOrderCallback(on_stock_order_callback)

        # trade成交主推
        self.stock_trade_sem = asyncio.Semaphore(0)
        self.stock_trades = []

        def on_stock_trade_callback(trade):
            self.stock_trades.append(trade)
            self.loop.call_soon_threadsafe(self.stock_trade_sem.release)

        self.async_client.bindOnStockTradeCallback(on_stock_trade_callback)

        # position持仓主推
        self.stock_position_sem = asyncio.Semaphore(0)
        self.stock_positions = []

        def on_stock_position_callback(position):
            self.stock_positions.append(position)
            self.loop.call_soon_threadsafe(self.stock_position_sem.release)

        self.async_client.bindOnStockPositionCallback(on_stock_position_callback)
    
    def __del__(self):
        asyncio.set_event_loop(self.oldloop)

    def register_callback(self, callback):
        self.callback = callback

    def start(self):
        self.async_client.init()
        self.async_client.start()

        self.executor = ThreadPoolExecutor(max_workers=min(32, os.cpu_count() + 4))

        async def listen_disconnected():
            await self.disconnected_sem
            if self.callback is not None:
                await self.loop.run_in_executor(self.executor, self.callback.on_disconnected)

        async def listen_stock_order():
            while True:
                await self.stock_orders_sem
                if self.callback is not None:
                    o = self.stock_orders.pop(0)
                    await self.loop.run_in_executor(self.executor, self.callback.on_stock_order, o)

        async def listen_order_error():
            while True:
                await self.order_error_sem
                if self.callback is not None:
                    o = self.order_errors.pop(0)
                    if o.order_id in self.handled_async_order_stock_order_id or o.order_id in self.sync_order_stock_order_id:
                        await self.loop.run_in_executor(self.executor, self.callback.on_order_error, o)
                    else:
                        self.queuing_order_errors[o.order_id] = o

        async def listen_cancel_error():
            while True:
                await self.cancel_error_sem
                if self.callback is not None:
                    o = self.cancel_orders.pop(0)
                    if not o.order_sysid:
                        if o.order_id in self.handled_async_cancel_order_stock_order_id or o.order_id in self.sync_cancel_order_stock_order_id:
                            await self.loop.run_in_executor(self.executor, self.callback.on_cancel_error, o)
                        else:
                            self.queuing_cancel_errors_by_order_id[o.order_id] = o
                    else:
                        if o.order_sysid in self.handled_async_cancel_order_stock_order_sys_id or o.order_sysid in self.sync_cancel_order_stock_order_sys_id:
                            await self.loop.run_in_executor(self.executor, self.callback.on_cancel_error, o)
                        else:
                            self.queuing_cancel_errors_by_order_sys_id[o.order_sysid] = o

        async def listen_stock_asset():
            while True:
                await self.stock_asset_sem
                if self.callback is not None:
                    o = self.stock_assets.pop(0)
                    await self.loop.run_in_executor(self.executor, self.callback.on_stock_asset, o)

        async def listen_stock_trade():
            while True:
                await self.stock_trade_sem
                if self.callback is not None:
                    o = self.stock_trades.pop(0)
                    await self.loop.run_in_executor(self.executor, self.callback.on_stock_trade, o)

        async def listen_stock_position():
            while True:
                await self.stock_position_sem
                if self.callback is not None:
                    o = self.stock_positions.pop(0)
                    await self.loop.run_in_executor(self.executor, self.callback.on_stock_position, o)

        async def listen_async_order_stock_response():
            while True:
                await self.async_order_response_sem
                if self.callback is not None:
                    o = self.async_order_responses.pop(0)
                    await self.loop.run_in_executor(self.executor, self.callback.on_order_stock_async_response, o)

                    self.handled_async_order_stock_order_id.add(o.order_id)
                    e = self.queuing_order_errors.pop(o.order_id, None)
                    if e is not None:
                        await self.loop.run_in_executor(self.executor, self.callback.on_order_error, e)

        async def listen_async_cancel_order_stock_response():
            while True:
                await self.async_cancel_order_response_sem
                if self.callback is not None:
                    o = self.async_cancel_order_responses.pop(0)
                    await self.loop.run_in_executor(self.executor, self.callback.on_cancel_order_stock_async_response, o)

                    if not o.order_sysid:
                        self.handled_async_cancel_order_stock_order_id.add(o.order_id)
                        e = self.queuing_cancel_errors_by_order_id.pop(o.order_id, None)
                        if e is not None:
                            await self.loop.run_in_executor(self.executor, self.callback.on_cancel_error, e)
                    else:
                        self.handled_async_cancel_order_stock_order_sys_id.add(o.order_sysid)
                        e = self.queuing_cancel_errors_by_order_sys_id.pop(o.order_sysid, None)
                        if e is not None:
                            await self.loop.run_in_executor(self.executor, self.callback.on_cancel_error, e)

        self.loop.create_task(listen_disconnected())
        self.loop.create_task(listen_stock_order())
        self.loop.create_task(listen_order_error())
        self.loop.create_task(listen_cancel_error())
        self.loop.create_task(listen_stock_asset())
        self.loop.create_task(listen_stock_trade())
        self.loop.create_task(listen_stock_position())
        self.loop.create_task(listen_async_order_stock_response())
        self.loop.create_task(listen_async_cancel_order_stock_response())

    def stop(self):
        self.async_client.stop()
        self.loop.call_soon_threadsafe(self.loop.stop)

    def connect(self):
        def run_event_loop():
            try:
                self.loop.run_forever()
            except KeyboardInterrupt:
                self.loop.call_soon_threadsafe(self.loop.stop)
            finally:
                self.loop.close()

        result = self.async_client.connect()
        self.connected = result == 0
        if self.connected:
            self.loop_thread = Thread(target=run_event_loop)
            self.loop_thread.start()
            return 0
        return result

    def sleep(self, time):
        async def sleep_coroutine(time):
            await asyncio.sleep(time)
        asyncio.run_coroutine_threadsafe(sleep_coroutine(time), self.loop).result()

    def run_forever(self):
        self.loop_thread.join()

    def subscribe(self, account):
        async def subscribe_coroutine(account):
            req = XTQC.SubscribeReq()
            req.m_nAccountType = account.account_type
            req.m_strAccountID = account.account_id

            seq = self.async_client.subscribe(req)
            future = self.requests[seq] = self.loop.create_future()

            result = await future
            self.requests.pop(seq, None)
            return result

        return asyncio.run_coroutine_threadsafe(subscribe_coroutine(account), self.loop).result()

    def unsubscribe(self, account):
        async def unsubscribe_coroutine(account):
            req = XTQC.UnsubscribeReq()
            req.m_nAccountType = account.account_type
            req.m_strAccountID = account.account_id

            seq = self.async_client.unsubscribe(req)
            future = self.requests[seq] = self.loop.create_future()

            result = await future
            self.requests.pop(seq, None)
            return result

        return asyncio.run_coroutine_threadsafe(unsubscribe_coroutine(account), self.loop).result()

    def order_stock(self, account, stock_code, order_type, order_volume, price_type, price, strategy_name='',
                    order_remark=''):
        """
        :param account: 证券账号
        :param stock_code: 证券代码, 例如"600000.SH"
        :param order_type: 委托类型, 23:买, 24:卖
        :param order_volume: 委托数量, 股票以'股'为单位, 债券以'张'为单位
        :param price_type: 报价类型, 详见帮助手册
        :param price: 报价价格, 如果price_type为指定价, 那price为指定的价格, 否则填0
        :param strategy_name: 策略名称
        :param order_remark: 委托备注
        :return: 返回服务器生成的订单编号order_id, 成功委托后的委托编号为大于0的正整数, 如果为-1表示委托失败
        """
        async def order_stock_coroutine(account, stock_code, order_type, order_volume, price_type, price, strategy_name,
                                        order_remark):
            req = XTQC.OrderStockReq()
            req.m_nAccountType = account.account_type
            req.m_strAccountID = account.account_id
            req.m_strStockCode = stock_code
            req.m_nOrderType = order_type
            req.m_nOrderVolume = order_volume
            req.m_nPriceType = price_type
            req.m_dPrice = price
            req.m_strStrategyName = strategy_name
            req.m_strOrderRemark = order_remark

            seq = self.async_client.orderStock(req)
            future = self.requests[seq] = self.loop.create_future()

            order_ref = 0
            try:
                order_ref = await asyncio.wait_for(future, 5, loop=self.loop)
            except asyncio.TimeoutError:
                order_ref = -2

            self.requests.pop(seq, None)
            return order_ref

        # 这里不保证返回order_ref和order_detail回调之间的先后顺序
        return asyncio.run_coroutine_threadsafe(
            order_stock_coroutine(account, stock_code, order_type, order_volume, price_type, price,
                                  strategy_name, order_remark),
            self.loop
        ).result()

    def order_stock_async(self, account, stock_code, order_type, order_volume, price_type, price, strategy_name='',
                          order_remark=''):
        """
        :param account: 证券账号
        :param stock_code: 证券代码, 例如"600000.SH"
        :param order_type: 委托类型, 23:买, 24:卖
        :param order_volume: 委托数量, 股票以'股'为单位, 债券以'张'为单位
        :param price_type: 报价类型, 详见帮助手册
        :param price: 报价价格, 如果price_type为指定价, 那price为指定的价格, 否则填0
        :param strategy_name: 策略名称
        :param order_remark: 委托备注
        :return: 返回下单请求序号, 成功委托后的下单请求序号为大于0的正整数, 如果为-1表示委托失败
        """
        req = XTQC.OrderStockReq()
        req.m_nAccountType = account.account_type
        req.m_strAccountID = account.account_id
        req.m_strStockCode = stock_code
        req.m_nOrderType = order_type
        req.m_nOrderVolume = order_volume
        req.m_nPriceType = price_type
        req.m_dPrice = price
        req.m_strStrategyName = strategy_name
        req.m_strOrderRemark = order_remark

        seq = self.async_client.orderStock(req)
        self.async_order_stock_sequences.add(seq)
        return seq

    def cancel_order_stock(self, account, order_id):
        """
        :param account: 证券账号
        :param order_id: 委托编号, 报单时返回的编号
        :return: 返回撤单成功或者失败, 0:成功,  -1:委托已完成撤单失败, -2:未找到对应委托编号撤单失败, -3:账号未登陆撤单失败
        """
        async def cancel_order_stock_coroutine(account, order_id):
            cancel_req = XTQC.CancelOrderStockReq()
            cancel_req.m_nAccountType = account.account_type
            cancel_req.m_strAccountID = account.account_id
            cancel_req.m_nOrderID = order_id
            seq = self.async_client.cancelOrderStock(cancel_req)
            future = self.requests[seq] = self.loop.create_future()

            ret = 0
            try:
                ret = await asyncio.wait_for(future, 5, loop=self.loop)
            except asyncio.TimeoutError:
                ret = -2

            self.requests.pop(seq, None)
            return ret

        return asyncio.run_coroutine_threadsafe(cancel_order_stock_coroutine(account, order_id), self.loop).result()

    def cancel_order_stock_async(self, account, order_id):
        """
        :param account: 证券账号
        :param order_id: 委托编号, 报单时返回的编号
        :return: 返回撤单请求序号, 成功委托后的撤单请求序号为大于0的正整数, 如果为-1表示委托失败
        """
        cancel_req = XTQC.CancelOrderStockReq()
        cancel_req.m_nAccountType = account.account_type
        cancel_req.m_strAccountID = account.account_id
        cancel_req.m_nOrderID = order_id
        seq = self.async_client.cancelOrderStock(cancel_req)
        self.async_cancel_order_stock_sequences.add(seq)
        return seq

    def cancel_order_stock_sysid(self, account, market, sysid):
        """
        :param account:证券账号
        :param market: 交易市场 0:上海 1:深圳
        :param sysid: 柜台合同编号
        :return:返回撤单成功或者失败, 0:成功,  -1:撤单失败
        """
        async def cancel_order_stock_sysid_coroutine(account, market, sysid):
            cancel_req = XTQC.CancelOrderStockReq()
            cancel_req.m_nAccountType = account.account_type
            cancel_req.m_strAccountID = account.account_id
            cancel_req.m_nMarket = market
            cancel_req.m_strOrderSysID = sysid
            seq = self.async_client.cancelOrderStock(cancel_req)
            future = self.requests[seq] = self.loop.create_future()

            ret = 0
            try:
                ret = await asyncio.wait_for(future, 5, loop=self.loop)
            except asyncio.TimeoutError:
                ret = -2

            self.requests.pop(seq, None)
            return ret

        return asyncio.run_coroutine_threadsafe(cancel_order_stock_sysid_coroutine(account, market, sysid), self.loop).result()

    def cancel_order_stock_sysid_async(self, account, market, sysid):
        """
        :param account:证券账号
        :param market: 交易市场 0:上海 1:深圳
        :param sysid: 柜台编号
        :return:返回撤单请求序号, 成功委托后的撤单请求序号为大于0的正整数, 如果为-1表示委托失败
        """
        cancel_req = XTQC.CancelOrderStockReq()
        cancel_req.m_nAccountType = account.account_type
        cancel_req.m_strAccountID = account.account_id
        cancel_req.m_nMarket = market
        cancel_req.m_strOrderSysID = sysid

        seq = self.async_client.cancelOrderStock(cancel_req)
        self.async_cancel_order_stock_sequences.add(seq)
        return seq
        
    def query_stock_order(self, account, order_id):
        """
        :param account: 证券账号
        :param order_id:  订单编号，同步报单接口返回的编号
        :return: 返回订单编号对应的委托对象
        """
        async def query_stock_order_coroutine(account, order_id):
            req = XTQC.QueryStockOrdersReq()
            req.m_nAccountType = account.account_type
            req.m_strAccountID = account.account_id
            req.m_nOrderID = order_id
            seq = self.async_client.queryStockOrders(req)
            future = self.requests[seq] = self.loop.create_future()
            resp = await future
            self.requests.pop(seq, None)
            if len(resp):
                return resp[0]
            return None

        return asyncio.run_coroutine_threadsafe(query_stock_order_coroutine(account, order_id), self.loop).result()

    def query_credit_detail(self, account):
        """
        :param account: 证券账号
        :return: 返回委托编号对应的委托对象
        """
        async def query_credit_detail_coroutine(account):
            req = XTQC.QueryCreditDetailReq()
            req.m_nAccountType = account.account_type
            req.m_strAccountID = account.account_id
            seq = self.async_client.queryCreditDetail(req)
            future = self.requests[seq] = self.loop.create_future()
            resp = await future
            self.requests.pop(seq, None)
            if resp:
                return resp
            return None

        return asyncio.run_coroutine_threadsafe(query_credit_detail_coroutine(account), self.loop).result()

    def query_stk_compacts(self, account):
        """
        :param account: 证券账号
        :return: 返回负债合约
        """
        async def query_stk_compacts_coroutine(account):
            req = XTQC.QueryStkCompactsReq()
            req.m_nAccountType = account.account_type
            req.m_strAccountID = account.account_id
            seq = self.async_client.queryStkCompacts(req)
            future = self.requests[seq] = self.loop.create_future()
            resp = await future
            self.requests.pop(seq, None)
            if resp:
                return resp
            return None

        return asyncio.run_coroutine_threadsafe(query_stk_compacts_coroutine(account), self.loop).result()

    def query_credit_subjects(self, account):
        """
        :param account: 证券账号
        :return: 返回融资融券标的
        """
        async def query_credit_subjects_coroutine(account):
            req = XTQC.QueryCreditSubjectsReq()
            req.m_nAccountType = account.account_type
            req.m_strAccountID = account.account_id
            seq = self.async_client.queryCreditSubjects(req)
            future = self.requests[seq] = self.loop.create_future()
            resp = await future
            self.requests.pop(seq, None)
            if resp:
                return resp
            return None

        return asyncio.run_coroutine_threadsafe(query_credit_subjects_coroutine(account), self.loop).result()

    def query_credit_slo_code(self, account):
        """
        :param account: 证券账号
        :return: 返回可融券数据
        """
        async def query_credit_slo_code_coroutine(account):
            req = XTQC.QueryCreditSloCodeReq()
            req.m_nAccountType = account.account_type
            req.m_strAccountID = account.account_id
            seq = self.async_client.queryCreditSloCode(req)
            future = self.requests[seq] = self.loop.create_future()
            resp = await future
            self.requests.pop(seq, None)
            if resp:
                return resp
            return None

        return asyncio.run_coroutine_threadsafe(query_credit_slo_code_coroutine(account), self.loop).result()

    def query_credit_assure(self, account):
        """
        :param account: 证券账号
        :return: 返回标的担保品
        """
        async def query_credit_assure_coroutine(account):
            req = XTQC.QueryCreditAssureReq()
            req.m_nAccountType = account.account_type
            req.m_strAccountID = account.account_id
            seq = self.async_client.queryCreditAssure(req)
            future = self.requests[seq] = self.loop.create_future()
            resp = await future
            self.requests.pop(seq, None)
            if resp:
                return resp
            return None

        return asyncio.run_coroutine_threadsafe(query_credit_assure_coroutine(account), self.loop).result()

    def query_stock_orders(self, account):
        """
        :param account: 证券账号
        :return: 返回当日所有委托的委托对象组成的list
        """
        async def query_stock_orders_coroutine(account):
            req = XTQC.QueryStockOrdersReq()
            req.m_nAccountType = account.account_type
            req.m_strAccountID = account.account_id
            seq = self.async_client.queryStockOrders(req)
            future = self.requests[seq] = self.loop.create_future()
            resp = await future
            self.requests.pop(seq, None)
            return resp

        return asyncio.run_coroutine_threadsafe(query_stock_orders_coroutine(account), self.loop).result()

    def query_stock_asset(self, account):
        """
        :param account: 证券账号
        :return: 返回当前证券账号的资产数据
        """
        async def query_stock_asset_coroutine(account):
            req = XTQC.QueryStockAssetReq()
            req.m_nAccountType = account.account_type
            req.m_strAccountID = account.account_id
            seq = self.async_client.queryStockAsset(req)
            future = self.requests[seq] = self.loop.create_future()
            resp = await future
            self.requests.pop(seq, None)
            if len(resp):
                return resp[0]
            return None

        return asyncio.run_coroutine_threadsafe(query_stock_asset_coroutine(account), self.loop).result()

    def query_stock_trades(self, account):
        """
        :param account:  证券账号
        :return:  返回当日所有成交的成交对象组成的list
        """
        async def query_stock_trades_coroutine(account):
            req = XTQC.QueryStockTradesReq()
            req.m_nAccountType = account.account_type
            req.m_strAccountID = account.account_id
            seq = self.async_client.queryStockTrades(req)
            future = self.requests[seq] = self.loop.create_future()
            resp = await future
            self.requests.pop(seq, None)
            return resp
        return asyncio.run_coroutine_threadsafe(query_stock_trades_coroutine(account), self.loop).result()

    def query_stock_position(self, account, stock_code):
        """
        :param account: 证券账号
        :param stock_code: 证券代码, 例如"600000.SH"
        :return: 返回证券代码对应的持仓对象
        """
        async def query_stock_position_coroutine(account, stock_code):
            req = XTQC.QueryStockPositionsReq()
            req.m_nAccountType = account.account_type
            req.m_strAccountID = account.account_id
            req.m_strStockCode = stock_code
            seq = self.async_client.queryStockPositions(req)
            future = self.requests[seq] = self.loop.create_future()
            resp = await future
            self.requests.pop(seq, None)
            if len(resp):
                return resp[0]
            return None
        return asyncio.run_coroutine_threadsafe(query_stock_position_coroutine(account, stock_code), self.loop).result()

    def query_stock_positions(self, account):
        """
        :param account: 证券账号
        :return: 返回当日所有持仓的持仓对象组成的list
        """
        async def query_stock_positions_coroutine(account):
            req = XTQC.QueryStockPositionsReq()
            req.m_nAccountType = account.account_type
            req.m_strAccountID = account.account_id
            seq = self.async_client.queryStockPositions(req)
            future = self.requests[seq] = self.loop.create_future()
            resp = await future
            self.requests.pop(seq, None)
            return resp
        return asyncio.run_coroutine_threadsafe(query_stock_positions_coroutine(account), self.loop).result()

    def trade_function_template(self, param):
        def on_trade_callback(seq, callback_resp):
            future = self.requests[seq]
            self.loop.call_soon_threadsafe(future.set_result, callback_resp)
        self.async_client.bindTradeFunctionCallback(on_trade_callback)

        async def trade_function_coroutine(param):
            # TODO 构造请求体
            req = None
            # TODO 交易类请求
            seq = self.async_client.trade(req)
            future = self.requests[seq] = self.loop.create_future()
            resp = await future
            self.requests.pop(seq, None)
            return resp
        return asyncio.run_coroutine_threadsafe(trade_function_coroutine(param), self.loop).result()
