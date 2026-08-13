# 📖 CloudDrive2 → 飞书通知 部署教程

把 CloudDrive2 的**文件变动 / 挂载状态**实时推送到**飞书群机器人**的中文通知，完整图文步骤。

---

## 目录

- [一、项目简介](#一项目简介)
- [二、原理图](#二原理图)
- [三、准备工作](#三准备工作)
- [四、部署中转服务](#四部署中转服务)
- [五、配置 CloudDrive2](#五配置-clouddrive2)
- [六、测试验证](#六测试验证)
- [七、常见问题](#七常见问题)
- [八、更新与卸载](#八更新与卸载)

---

## 一、项目简介

CloudDrive2（CD2）的 Webhook 只支持 JSON 变量模板，无法直接翻译动作（如 `create` → `新建`）。本项目作为**中间层**：

1. 接收 CD2 推送的原始 JSON
2. 解析 `data` 数组中的动作和文件路径
3. 翻译成中文 + Emoji
4. 转发到飞书群机器人

**效果示例：**

```
📁【CloudDrive2 文件变动通知】
-------------------------------
设备名称: godsdeMac-mini.local
操作用户: 18866770789@163.com
变动类型: 新建文件/目录 ➕
类型: 文件 📄
源 文件: /115open/Mac/宿命 - 鹿.flac
触发时间: 2026-08-14 01:06:07
```

---

## 二、原理图

```
┌──────────────┐   webhook   ┌─────────────────────┐   飞书Webhook   ┌──────────┐
│ CloudDrive2  │ ──────────▶ │ cd2-feishu-relay    │ ──────────────▶ │ 飞书群机器人 │
│ (config.toml)│    JSON     │ (Python HTTP 服务)  │    翻译后中文     │ (通知消息) │
└──────────────┘             └─────────────────────┘                 └──────────┘
```

---

## 三、准备工作

| 项目 | 说明 |
|---|---|
| 一台常开的电脑/NAS | 跑中转服务（Docker 或 Python 3.11+） |
| 飞书群机器人 | 群设置 → 机器人 → 添加自定义机器人，拿到 Webhook 地址 |
| CloudDrive2 会员 | 文件变动实时监控是**会员功能** |
| CID 版本 | V0.8.5+，建议最新版 |

---

## 四、部署中转服务

### 方式 A：Docker Compose（推荐）

```bash
mkdir cd2-feishu-relay && cd cd2-feishu-relay
# 下载项目文件后：
cp docker-compose.example.yml docker-compose.yml
```

编辑 `docker-compose.yml`，把 `FEISHU_WEBHOOK` 换成你的地址：

```yaml
environment:
  - FEISHU_WEBHOOK=https://open.feishu.cn/open-apis/bot/v2/hook/你的密钥
```

启动：

```bash
docker compose up -d
```

### 方式 B：直接运行 Python

```bash
export FEISHU_WEBHOOK="https://open.feishu.cn/open-apis/bot/v2/hook/你的密钥"
python3 server.py
```

> 默认监听 `9090` 端口，可通过 `LISTEN_PORT` 环境变量修改。

---

## 五、配置 CloudDrive2

### 找到 CD2 配置目录

- **Docker 部署**：通常挂载的 `config` 目录（本项目示例为 `/Volumes/ssd/docker/clouddrive2/config/`）
- 在该目录下新建或编辑 `webhook.toml`

### 填入配置

参考项目内的 `webhook.example.toml`，关键点：

```toml
[global_params]
base_url = "http://你的主机IP:9090"   # 中转服务的地址
enabled = true
time_format = "local:%Y-%m-%d %H:%M:%S"

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
    { "action": "{action}", "is_dir": "{is_dir}",
      "source_file": "{source_file}", "destination_file": "{destination_file}" }
  ]
}
'''

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
    { "action": "{action}", "mount_point": "{mount_point}",
      "status": "{status}", "reason": "{reason}" }
  ]
}
'''
```

### 保存并重启 CD2

保存 `webhook.toml` 后，**重启 CloudDrive2 容器/进程**使配置生效：

```bash
docker restart clouddrive2
```

---

## 六、测试验证

1. 往挂载的网盘里**新建一个文件**（如传一首歌）
2. 飞书群应立刻收到「新建文件/目录 ➕」通知，带真实路径
3. 再**删除**该文件 → 应收到「删除文件/目录 🗑️」
4. 若收不到，看中转服务日志排查：

```bash
docker logs -f cd2-feishu-relay
```

日志会打印：`[CD2 Received Payload] {...}` 和 `[Relay Success] Feishu response: {"StatusCode":0...}`

---

## 七、常见问题

| 问题 | 排查 |
|---|---|
| 收到 `{action}`、`{file_path}` 等字面量 | CD2 版本过旧或 body 未用 `data` 数组结构，升级 CD2 并用 `source_file`/`destination_file` 变量 |
| 收不到任何通知 | 检查 `base_url` 是否可达、CD2 是否会员、webhook `enabled` 是否为 true |
| 删除显示"重命名" | Mac 删除会先进废纸篓(`.Trashes`)触发 rename。已有废纸篓识别，目标含 `.Trashes` 会显示"删除" |
| 飞书返回 19001/19025 | Webhook 地址错误或被封禁，检查密钥 |

---

## 八、更新与卸载

**更新中转服务：**
```bash
docker compose pull && docker compose up -d
```

**卸载：**
```bash
docker compose down
# 删除目录
rm -rf cd2-feishu-relay
# 记住从 CD2 的 webhook.toml 里注释掉或删除对应配置
```

---

## License

MIT

## 致谢

- [zfhxi/partial-path-scanner](https://github.com/zfhxi/partial-path-scanner) — CD2 webhook 标准数据结构参考
- [wtf111/clouddrive2-webhook](https://hub.docker.com/r/wtf111/clouddrive2-webhook) — 中转思路启发（Bark 版）