# CloudDrive2 → 飞书(Feishu/Lark) Webhook 中转服务

接收 [CloudDrive2](https://www.clouddrive2.com/) 的 webhook 推送，将文件变动 / 挂载状态事件翻译为中文，并转发到**飞书群机器人**通知。

## 为什么需要中间层？

CloudDrive2 的 webhook 配置只支持 JSON 变量模板，无法直接处理变量替换后的动作翻译（如 `create` → `新建`）。同时文件变动事件依赖 `data` 数组结构才能正确拿到真实路径。本项目作为中间层接收 CD2 推送，解析并翻译后发送到飞书。

## 特性

- ✅ 文件变动通知（新建 / 删除 / 重命名 / 移动）
- ✅ 自动识别 Mac 废纸篓删除（`.Trashes`），避免误报为"重命名"
- ✅ 挂载点状态通知（挂载成功 / 卸载 / 失败原因）
- ✅ 过滤未解析的 `{...}` 占位符，通知永远干净可读
- ✅ 中文 + Emoji 排版，飞书群机器人直接可读
- ✅ 零第三方依赖（仅 Python 标准库）

## 快速开始

### 1. 准备

- 一个飞书群机器人 Webhook 地址（群设置 → 机器人 → 添加自定义机器人）
- Python 3.11+ 或 Docker

### 2. 运行

#### Docker Compose（推荐）

```bash
mkdir cd2-feishu-relay && cd cd2-feishu-relay
cp docker-compose.example.yml docker-compose.yml
# 编辑 docker-compose.yml，填入你的 FEISHU_WEBHOOK
docker compose up -d
```

#### 直接运行

```bash
export FEISHU_WEBHOOK="https://open.feishu.cn/open-apis/bot/v2/hook/你的密钥"
python3 server.py
```

### 3. 配置 CloudDrive2

在 CloudDrive2 的 `config` 目录添加 `webhook.toml`，`base_url` 指向本服务：

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

## 通知效果示例

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

## 环境变量

| 变量 | 必填 | 默认值 | 说明 |
|---|---|---|---|
| `FEISHU_WEBHOOK` | 是 | 无 | 飞书群机器人 Webhook 地址 |
| `LISTEN_PORT` | 否 | `9090` | HTTP 监听端口 |

## License

MIT

## 致谢

- 参考 [zfhxi/partial-path-scanner](https://github.com/zfhxi/partial-path-scanner) 的 CD2 webhook 标准数据结构
- 灵感来自 [wtf111/clouddrive2-webhook](https://hub.docker.com/r/wtf111/clouddrive2-webhook)（Bark 版中转）