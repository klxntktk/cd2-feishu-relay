# CloudDrive2 → 飞书(Feishu/Lark) Webhook 中转服务

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green)
![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker&logoColor=white)

接收 [CloudDrive2](https://www.clouddrive2.com/) 的 webhook 推送，将文件变动 / 挂载状态事件翻译为中文，并转发到**飞书群机器人**通知。

## 为什么需要中间层？

CloudDrive2 的 webhook 配置只支持 JSON 变量模板，无法直接处理变量替换后的动作翻译（如 `create` → `新建`）。同时文件变动事件依赖 `data` 数组结构才能正确拿到真实路径。本项目作为中间层接收 CD2 推送，解析并翻译后发送到飞书。

## 通知效果

![飞书通知效果](/preview.png)

```
📁【CloudDrive2 文件变动通知】
-------------------------------
设备名称: my-nas
操作用户: user@example.com
变动类型: 新建文件/目录 ➕
类型: 文件 📄
源 文件: /115open/Movies/星际穿越.mkv
触发时间: 2026-08-14 01:06:07
```

```
🔌【CloudDrive2 挂载状态通知】
-------------------------------
设备名称: my-nas
变动动作: 挂载成功 🔌
挂载路径: /CloudNAS/115
触发时间: 2026-08-14 01:10:00
```

## 特性

- ✅ 文件变动通知（新建 / 删除 / 重命名 / 移动）
- ✅ 自动识别 Mac 废纸篓删除（`.Trashes`），避免误报为"重命名"
- ✅ 挂载点状态通知（挂载成功 / 卸载 / 失败原因）
- ✅ 过滤未解析的 `{...}` 占位符，通知永远干净可读
- ✅ 中文 + Emoji 排版，飞书群机器人直接可读
- ✅ 多线程处理（`ThreadingHTTPServer`），高并发不阻塞
- ✅ 飞书推送超时保护 + 失败自动重试
- ✅ 消息长度截断保护（飞书 4096 字节限制）
- ✅ `GET /health` 健康检查端点
- ✅ 零第三方依赖（仅 Python 标准库）

## 快速开始

### 准备

- 一个飞书群机器人 Webhook 地址（群设置 → 机器人 → 添加自定义机器人）
- 装有 Docker 的机器（或 Python 3.11+）

### 方法一：直接拉取镜像（推荐）

> 🇨🇳 **国内用户推荐从 Docker Hub 拉取**（速度快，可配合国内加速器）：

```bash
docker pull vhgods/cd2-feishu-relay:latest
```

> 🌍 海外用户也可以从 GitHub Container Registry 拉取：

```bash
docker pull ghcr.io/klxntktk/cd2-feishu-relay:latest
```

两个仓库内容完全一致（GitHub Actions 自动同步），任选其一即可。

运行容器：

```bash
docker run -d \
  --name cd2-feishu-relay \
  --restart unless-stopped \
  -p 9095:9090 \
  -e FEISHU_WEBHOOK="https://open.feishu.cn/open-apis/bot/v2/hook/你的密钥" \
  vhgods/cd2-feishu-relay:latest
```

或使用 Docker Compose（Docker Hub 版）：

```yaml
services:
  cd2-feishu-relay:
    image: vhgods/cd2-feishu-relay:latest
    container_name: cd2-feishu-relay
    restart: unless-stopped
    ports:
      - "9095:9090"
    environment:
      - FEISHU_WEBHOOK=https://open.feishu.cn/open-apis/bot/v2/hook/你的密钥
      - LISTEN_PORT=9090
```

（如用 ghcr.io 镜像，把上面 `image` 换成 `ghcr.io/klxntktk/cd2-feishu-relay:latest` 即可）

```bash
docker compose up -d
```

### 方法二：直接运行 Python

```bash
git clone https://github.com/klxntktk/cd2-feishu-relay.git
cd cd2-feishu-relay
export FEISHU_WEBHOOK="https://open.feishu.cn/open-apis/bot/v2/hook/你的密钥"
python3 server.py
```

## 配置 CloudDrive2

在 CloudDrive2 的 `config` 目录添加 `webhook.toml`，`base_url` 指向本服务（参考项目内 `webhook.example.toml`）：

```toml
# global parameters
[global_params]
base_url = "http://你的主机IP:9090"
enabled = true
time_format = "local:%Y-%m-%d %H:%M:%S"

[global_params.default_headers]
content-type = "application/json"
user-agent = "clouddrive2/{version}"

# 1. 文件变动通知
[file_system_watcher]
url = "{base_url}"
method = "POST"
enabled = true
body = '''
{
  "device_name": "{device_name}",
  "user_name": "{user_name}",
  "version": "{version}",
  "event_category": "{event_category}",
  "event_name": "{event_name}",
  "event_time": "{event_time}",
  "send_time": "{send_time}",
  "data": [
    {
      "action": "{action}",
      "is_dir": "{is_dir}",
      "source_file": "{source_file}",
      "destination_file": "{destination_file}"
    }
  ]
}
'''

# 2. 挂载点状态通知
[mount_point_watcher]
url = "{base_url}"
method = "POST"
enabled = true
body = '''
{
  "device_name": "{device_name}",
  "user_name": "{user_name}",
  "version": "{version}",
  "event_category": "{event_category}",
  "event_name": "{event_name}",
  "event_time": "{event_time}",
  "send_time": "{send_time}",
  "data": [
    {
      "action": "{action}",
      "mount_point": "{mount_point}",
      "status": "{status}",
      "reason": "{reason}"
    }
  ]
}
'''
```

> ⚠️ 注意事项：文件变动实时监控是 CloudDrive2 **会员功能**。CD2 版本建议 V0.8.5+（最新版效果最佳）。

保存后重启 CloudDrive2 生效：

```bash
docker restart clouddrive2
```

## 环境变量

| 变量 | 必填 | 默认值 | 说明 |
|---|---|---|---|
| `FEISHU_WEBHOOK` | 是 | 无 | 飞书群机器人 Webhook 地址 |
| `LISTEN_PORT` | 否 | `9090` | HTTP 监听端口 |
| `FEISHU_TIMEOUT` | 否 | `10` | 飞书推送超时（秒） |
| `FEISHU_RETRIES` | 否 | `2` | 飞书推送失败重试次数 |

## 健康检查

```bash
curl http://localhost:9095/health
# {"status":"ok"}
```

## 测试

往挂载的网盘里新建/删除一个文件，飞书群应立刻收到中文通知。查看日志：

```bash
docker logs -f cd2-feishu-relay
```

## License

MIT

## 致谢

- 参考 [zfhxi/partial-path-scanner](https://github.com/zfhxi/partial-path-scanner) 的 CD2 webhook 标准数据结构
- 灵感来自 [wtf111/clouddrive2-webhook](https://hub.docker.com/r/wtf111/clouddrive2-webhook)（Bark 版中转）