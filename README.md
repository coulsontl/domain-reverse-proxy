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
      - SERVER_PORT_5000=https://site1.com
      - SERVER_PORT_5001=https://site2.com
```

### 环境变量说明
* PROXY_URL: 指定所有请求通过的代理服务器的URL
* SERVER_PORT_5000: 必须以SERVER_PORT_开头，5000代表监听的端口，值对应的是目标网站URL
* 如果有多个反代站点直接添加多个以SERVER_PORT_开头的环境变量就行了

### 端口映射
使用 -p 标志映射容器内的端口到宿主机的端口。确保每个SERVER_PORT指定的端口都被映射。

### 验证运行
如果您映射了端口5000到宿主机，并配置了相应的目标URL，那么访问 http://localhost:5000 应该会看到目标网站的内容。
