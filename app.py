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
server_urls = os.getenv('SERVER_URLS')

async def proxy(request):
    path = request.match_info.get('path', '/')
    port = request.transport.get_extra_info('sockname')[1]  # 获取实际监听的端口号
    target_url = target_urls[server_ports.index(port)]
    server_url = None
    if server_urls:
        server_url = server_urls[server_ports.index(port)]

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

                # 如果指定了SERVER_URL，替换内容中TARGET_URL为SERVER_URL
                if server_url:
                    content_encoding = resp.headers.get('Content-Encoding', '')
                    # logging.info(f"raw content: {raw}")
                    try:
                        if 'gzip' in content_encoding:
                            data = gzip.decompress(raw)
                        elif 'br' in content_encoding:
                            data = brotli.decompress(raw)
                        elif 'deflate' in content_encoding:
                            data = zlib.decompress(raw)
                        else:
                            data = raw
                        raw = data
                        logging.info("Gzip compression detected and decompressed.")
                    except OSError as e:
                        logging.error(f"Error during gzip decompression: {e}")
                    
                    # 检查Content-Type是否为文本类型
                    content_type = resp.headers.get('Content-Type', '')
                    if 'text' in content_type or 'html' in content_type:
                        charset = 'utf-8'  # 默认使用UTF-8
                        # 尝试从Content-Type中获取字符集
                        if 'charset=' in content_type:
                            charset = content_type.split('charset=')[-1]
                        try:
                            content = raw.decode(charset)
                            content = content.replace(target_url, server_url)
                            raw = content.encode(charset)
                        except UnicodeDecodeError:
                            logging.warning(f"Failed to decode content from {target} as {charset}.")
                            # UTF-8解码失败，使用BeautifulSoup查找正确的字符集
                            soup = BeautifulSoup(raw, 'html.parser')
                            meta = soup.find('meta', {'charset': True})
                            if meta:
                                charset = meta['charset']
                                try:
                                    # 根据HTML中的字符集重新解码
                                    content = raw.decode(charset)
                                    content = content.replace(target_url, server_url)
                                    raw = content.encode(charset)
                                except UnicodeDecodeError:
                                    print("Failed to decode content with charset from HTML meta tag.")
                            else:
                                print("Charset not found in HTML.")
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