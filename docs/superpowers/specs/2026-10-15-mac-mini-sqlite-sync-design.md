# Sabrina English Mac mini 部署与同步设计

## 目标

把 Sabrina English 恢复为一个可长期运行的个人英语学习网站。用户本人、Sabrina 和 Max 可以通过 `https://sabrina.redflyingpig.com/` 在手机或电脑浏览器访问；三人的学习记录分别保存在 Mac mini 上，并在各自设备之间同步。

这个项目保持个人工具应有的克制：不引入 Docker、自托管 Supabase、邮件系统、管理后台或复杂权限平台。现有每日课程、发音、学习记录、连续学习、复习、收藏和 JSON 导入导出继续保留。

## 当前状态

- 应用是一个包含 HTML、CSS 和 JavaScript 的单文件静态站点。
- Mac mini 已通过 `launchd` 在 `127.0.0.1:18880` 运行 Python 静态服务器。
- 已有 Cloudflare Tunnel 将 `sabrina.redflyingpig.com` 转发到该端口。
- 原 Supabase 项目不可用；前端会降级到 `localStorage`，但无法跨设备同步。
- Mac mini 已有 Python 3 和 SQLite，没有 Docker 或 PostgreSQL。

## 架构

采用一个仅依赖 Python 标准库的本地应用进程：

```text
手机或电脑浏览器
        |
        | HTTPS
        v
Cloudflare + Cloudflare Tunnel
        |
        v
127.0.0.1:18880
Python Sabrina 服务
  |- 静态文件
  |- JSON API
  `- SQLite
```

Python 服务同时提供静态页面和同源 JSON API。它只监听 `127.0.0.1`，不会直接暴露到局域网或公网；外部请求只能通过现有 Cloudflare Tunnel 到达。

继续使用 macOS `launchd` 管理服务，实现登录后启动和异常退出后重启。现有 Tunnel 配置与域名不变。

## 用户身份

用户通过“用户名 + PIN”访问自己的学习档案。

- 用户名经过去除首尾空格、合并连续空格和不区分大小写的标准化。
- PIN 至少 6 位，允许数字或字符，最长 64 个字符。
- 部署时通过仅能在 Mac mini 本地运行的管理命令创建 `Owner`、`Sabrina`、`Max` 三个档案，并分别生成初始 PIN。
- 公网界面只允许登录，不允许注册任意新用户名，防止他人抢占家庭成员的档案。
- 服务器使用 `hashlib.scrypt` 和每个用户独立的随机盐保存 PIN 哈希，不保存明文 PIN。
- 登录成功后服务器签发随机会话令牌。数据库只保存令牌哈希、用户 ID、创建时间和过期时间。
- 浏览器把会话令牌保存在 `localStorage`，请求时通过 `Authorization: Bearer` 发送。
- 会话默认有效 90 天；用户可在界面中退出并清除本机令牌。

用户名不是安全边界，PIN 和随机会话令牌才是。服务不提供邮件找回功能；用户可以通过现有 JSON 导出保留自己的学习数据。个人工具无需为了“忘记 PIN”养一套邮件系统。

## 数据模型

SQLite 数据库包含以下表：

### `profiles`

- `id`：整数主键
- `username_normalized`：唯一标准化用户名
- `display_name`：显示名称
- `pin_salt`：随机盐
- `pin_hash`：scrypt 结果
- `state_json`：完整学习状态 JSON
- `state_version`：服务端递增版本号
- `created_at`、`updated_at`：UTC 时间

### `sessions`

- `token_hash`：会话令牌的 SHA-256 哈希，主键
- `profile_id`：所属档案
- `created_at`、`expires_at`：UTC 时间

数据库启动时启用 WAL、外键和合理的 busy timeout。学习状态保持现有结构：`history`、`favorites`、`streak`、`updatedAt` 和格式版本号。

## API

所有响应使用 JSON；除注册和登录外均要求 Bearer 会话令牌。

- `GET /api/health`：不包含敏感信息的服务和数据库健康检查。
- `POST /api/auth/login`：验证用户名和 PIN 并返回会话令牌。
- `POST /api/auth/logout`：删除当前会话。
- `GET /api/profile`：读取当前档案和学习状态。
- `PUT /api/profile`：校验并写入学习状态。

`PUT /api/profile` 携带客户端已知的 `state_version`。版本一致才直接写入；发生并发修改时，服务器返回 `409` 和最新状态，由前端运行现有合并逻辑后重试一次，避免两个设备互相覆盖。

管理命令只能在 Mac mini 本地终端执行，用于初始化三个档案、重置 PIN 和列出档案名称。它不会显示学习数据或既有 PIN。初始 PIN 只在创建时输出一次。

API 限制请求体大小为 1 MiB，校验 JSON 类型和字段，拒绝跨站写请求，并给动态响应设置 `Cache-Control: no-store`。登录按来源 IP 和用户名做内存级限流；进程重启后计数清零，这对低流量个人站点足够。

## 前端数据流

1. 首次访问时显示三个家庭档案选项和 PIN 输入框。
2. 登录成功后，浏览器保存会话令牌并加载服务器状态。
3. 如果本机已有旧 `localStorage` 记录，前端使用现有合并规则合并本机与服务器状态，然后上传。
4. 每次学习操作先同步写入 `localStorage`，保证界面即时响应；随后短暂防抖并上传服务器。
5. API 不可用时显示“离线模式”，学习继续写入本机。
6. 页面重新获得焦点、浏览器恢复在线或下次启动时重新拉取并同步。
7. 令牌失效时保留本机数据，要求重新登录，不清除学习记录。

旧 Supabase URL、匿名密钥和 RPC 调用全部删除。JSON 导入导出继续作为人工备份和应急迁移工具。

## 本机数据与备份

- 运行数据放在 `~/Library/Application Support/SabrinaEnglish/`，不放在 Git 仓库内。
- 数据库文件权限仅允许当前 macOS 用户访问。
- 每天通过独立备份脚本调用 SQLite backup API 生成一致性备份。
- 备份保存在 `~/Library/Application Support/SabrinaEnglish/backups/`，保留最近 30 份。
- 提供手动备份命令，部署与恢复步骤写入项目文档。

本地备份不能替代异地备份；如果 Mac mini 已启用 Time Machine，应把该数据目录纳入备份。首个 baseline 不额外引入云备份服务。

## 服务运行与故障处理

- 新服务接管现有 `127.0.0.1:18880`。
- 更新现有 `ai.sabrina-english.site` LaunchAgent，使其启动新的 Python 入口。
- 标准输出和错误日志写入项目现有日志路径，并配置轻量日志轮转，避免无限增长。
- 服务启动时自动创建数据库和执行幂等 schema migration。
- 数据库写入失败时返回明确错误，前端保留 `localStorage` 数据并显示离线状态。
- Cloudflare Tunnel 或家庭网络中断时，本机数据不受影响；恢复连接后客户端再次同步。

## 安全范围

- 服务只绑定回环地址，不开放数据库端口。
- Cloudflare Tunnel 采用现有出站连接，不在路由器上做端口映射。
- API 使用参数化 SQL、PIN 哈希、随机会话令牌、输入长度限制、同源检查和安全响应头。
- 不把 SQLite、备份、PIN 或会话令牌提交到 Git。
- 不把数据库通过 Tunnel 单独暴露；只有 Web API 可以访问数据库。
- 本项目不承诺企业级身份恢复、审计或高可用。Mac mini 关机、休眠或断网时网站会暂时不可用，这是自托管基线的明确取舍。

## 测试与验收

自动测试覆盖：

- 数据库创建、迁移和约束。
- 本地档案初始化、登录、错误 PIN、PIN 重置、退出和会话过期。
- 三个档案的数据隔离。
- 状态读写、版本冲突、请求体限制和无效 JSON。
- 旧本地记录与服务器记录的合并。
- 静态文件、健康检查和安全响应头。
- 备份生成、保留数量和从备份恢复。

部署后的实际验收覆盖：

1. Mac mini 本机健康检查返回成功。
2. `https://sabrina.redflyingpig.com/` 可从公网访问。
3. 分别建立三个档案，记录互不串号。
4. 在手机和电脑上登录同一档案，一端标记学习后另一端能看到更新。
5. 临时停止 API 后仍可在浏览器记录学习，恢复后能同步。
6. 重启应用服务后网页、数据库和既有记录仍正常。
7. 验证 LaunchAgent 与 Cloudflare Tunnel 都处于运行状态。

## 明确不做

- 邮箱、短信或第三方账号登录
- 管理后台和用户列表界面
- 排行榜、社交分享或消息通知
- Docker、Kubernetes、自托管 Supabase 或 PostgreSQL
- 为扩展性提前拆分微服务

这些功能与三人个人学习网站的目标不匹配，除非未来出现具体需求，否则不加入。
