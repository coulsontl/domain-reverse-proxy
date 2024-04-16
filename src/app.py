import os
import asyncio
from aiohttp import web, ClientSession
from dotenv import load_dotenv
import logging
import gzip
import brotli
import zlib
from bs4 import BeautifulSoup

# 加载环境变量
load_dotenv()

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 读取环境变量
proxy_url = os.getenv('PROXY_URL')
target_urls = os.getenv('TARGET_URLS').split(',')
server_ports = list(map(int, os.getenv('SERVER_PORTS').split(',')))

async def proxy(request):
    path = request.match_info.get('path', '/')
    port = request.transport.get_extra_info('sockname')[1]  # 获取实际监听的端口号
    target_url = target_urls[server_ports.index(port)]

    logging.info(f"Forwarding request from port {port} to {target_url}/{path}")

    async with ClientSession() as session:
        target = f"{target_url}/{path}"
        headers = {key: value for (key, value) in request.headers.items() if key != 'Host'}
        try:
            async with session.request(
                request.method, target, headers=headers, data=await request.read(), 
                proxy=proxy_url, allow_redirects=False
            ) as resp:
                raw = await resp.read()

                # 构建返回结果
                headers = [(k, v) for k, v in resp.headers.items() if k.lower() not in ('content-encoding', 'content-length', 'transfer-encoding', 'connection')]
                logging.info(f"Request to {target} successful with status {resp.status}")
                return web.Response(body=raw, status=resp.status, headers=headers)
        except Exception as e:
            logging.error(f"Error during request to {target}: {e}")
            return web.Response(status=502, text="Bad Gateway")

async def start_proxy(port):
    app = web.Application()
    app.router.add_route('*', '/{path:.*}', proxy)  # 简化的路由匹配
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    logging.info(f"Proxy server started on port {port}")

async def main():
    await asyncio.gather(*(start_proxy(port) for port in server_ports))

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
    loop.run_forever()