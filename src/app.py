import os
import asyncio
from aiohttp import web, TCPConnector, ClientSession
from dotenv import load_dotenv
import logging
import gzip
import brotli
import zlib
from urllib.parse import urlparse
import json
from bs4 import BeautifulSoup

# 加载环境变量
load_dotenv()

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 读取环境变量
proxy_url = os.getenv('PROXY_URL')
target_urls = os.getenv('TARGET_URLS').split(',')
server_ports = list(map(int, os.getenv('SERVER_PORTS').split(',')))

# 配置TCP连接器，限制最大连接数
connector = TCPConnector(limit=600)

async def should_use_stream(request, full_path):
    if 'stream' in request.query and request.query['stream'].lower() == 'true':
        return True
    if full_path.endswith(':streamGenerateContent'):
        return True
    if request.method == 'POST' and request.content_type == 'application/json':
        try:
            body = await request.json()  # 异步读取JSON请求体
            return body.get('stream', False)  # 假设请求体中包含stream字段
        except json.JSONDecodeError:
            logging.error("Error decoding JSON request body.")
            return False
    return False

async def proxy(request):
    path = request.match_info.get('path', '/')
    port = request.transport.get_extra_info('sockname')[1]  # 获取实际监听的端口号
    target_url = target_urls[server_ports.index(port)].rstrip('/')
    full_path = str(request.rel_url).lstrip('/')
    
    # 检查是否需要流式输出
    stream = await should_use_stream(request, full_path)

    async with ClientSession(connector=connector) as session:
        target = f"{target_url}/{full_path}"
        logging.info(f"Forwarding stream:{stream} request from port {port} to {target}")
        
        # 解析目标URL以获取Host
        parsed_target_url = urlparse(target)
        target_host = parsed_target_url.netloc
        
        request_body = await request.read()
        request_headers = {key: (target_host if key == 'Host' else value) for key, value in request.headers.items()}
        try:
            async with session.request(
                request.method, target, headers=request_headers, data=await request.read(), 
                proxy=proxy_url, allow_redirects=False
            ) as resp:
                if stream:
                    # 如果需要流式输出
                    response = web.StreamResponse(status=resp.status, reason=resp.reason)
                    headers = [(k, v) for k, v in resp.headers.items() if k.lower() not in ('content-encoding', 'content-length', 'transfer-encoding', 'connection')]
                    for name, value in headers:
                        response.headers[name] = value
                    await response.prepare(request)

                    response_content = bytearray()
                    async for data, _ in resp.content.iter_chunks():
                        await response.write(data)
                        response_content.extend(data)

                    await response.write_eof()
                    if resp.status != 200:
                        logging.error(f"Request to {target} completed with status {resp.status}. "
                                      f"Headers={request_headers}, Body={request_body.decode('utf-8', errors='replace')}, ")
                        logging.error(f"Response content (truncated): {response_content[:500].decode('utf-8', errors='replace')}")
                    else:
                        logging.info(f"Request to {target} completed with status {resp.status}")
                    return response
                else:
                    raw = await resp.read()

                    # 构建返回结果
                    headers = [(k, v) for k, v in resp.headers.items() if k.lower() not in ('content-encoding', 'content-length', 'transfer-encoding', 'connection')]
                    if resp.status != 200:
                        logging.error(f"Request to {target} completed with status {resp.status}. "
                                      f"Headers={request_headers}, Body={request_body.decode('utf-8', errors='replace')}, ")
                    else:
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