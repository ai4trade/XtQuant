# -*- coding: utf-8 -*-

from xtquant import xtdata
import aiohttp
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


if __name__ == '__main__':
    app = Sanic(name='xtdata')
    app.config.RESPONSE_TIMEOUT = 600000
    app.config.REQUEST_TIMEOUT = 600000
    app.config.KEEP_ALIVE_TIMEOUT = 600
    app.blueprint(api)
    app.run(host='0.0.0.0', port=7000, workers=1, auto_reload=True, debug=False)