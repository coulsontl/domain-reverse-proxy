# domain-reverse-proxy
一个简单的反代网站并把流量转发给代理的小工具

### 运行容器
要运行反向代理的容器，需要通过环境变量传递配置信息，例如代理URL、目标网站URLs和监听的端口。以下是一个示例：

```
# version: '3'
services:
  reverse-proxy:
    container_name: reverse-proxy
    image: coulsontl/domain-reverse-proxy
    network_mode: bridge
    restart: always
    ports:
      - '5000:5000'
      - '5001:5001'
    environment:
      - TZ=Asia/Shanghai
      - PROXY_URL=http://user:password@yourproxy:port
      - TARGET_URLS="https://site1.com,https://site2.com"
      - SERVER_PORTS=5000,5001
```

### 环境变量说明
* PROXY_URL: 指定所有请求通过的代理服务器的URL。
* TARGET_URLS: 以逗号分隔的目标网站URL列表，每个端口对应一个URL。
* SERVER_PORTS: 以逗号分隔的监听端口列表，数量应与TARGET_URLS中的URL数量匹配。

### 端口映射
使用 -p 标志映射容器内的端口到宿主机的端口。确保每个SERVER_PORTS中指定的端口都被映射。

### 验证运行
运行容器后，您可以通过访问宿主机上映射的端口来测试反向代理的工作情况。例如，如果您映射了端口5000到宿主机，并配置了相应的目标URL，那么访问 http://localhost:5000 应该会看到目标网站的内容。