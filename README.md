## Koyeb API 批量保活

通过 **API Token** 定期调用 Koyeb 账号接口，保持账号活跃，并可选发送结果到 Telegram。

> 说明：Koyeb 网页登录已改为 WorkOS + Cloudflare Turnstile，GitHub Actions 无头浏览器无法完成登录。  
> 本仓库已改为 API Token 方案，稳定、快速、无需 Playwright。

### 1. Fork 仓库

将本仓库 Fork 到你的 GitHub 账号。

### 2. 获取 Koyeb API Token

1. 登录 [Koyeb 控制台](https://app.koyeb.com)
2. 进入 **User Settings → API**（或头像 → Settings → API）
3. 点击 **Create API token**，创建后立即复制（只显示一次）
4. 每个需要保活的账号各创建一个 Token

文档参考：https://www.koyeb.com/docs/cli/authentication

### 3. 配置 GitHub Secrets

仓库 → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

| Secret | 必填 | 说明 |
|--------|------|------|
| `KOY_TOKENS` | 是 | 账号 Token 列表，空格分隔 |
| `TEL_TOK` | 否 | Telegram Bot Token |
| `TEL_ID` | 否 | Telegram Chat ID |

`KOY_TOKENS` 格式：

```text
main:koyeb_xxxxxxxx acc2:koyeb_yyyyyyyy
```

- 左侧为备注名（任意）
- 右侧为 API Token
- 多个账号用空格分隔
- 也支持只写 token（自动命名为 account1、account2…）

Telegram（可选）：

1. 找 `@BotFather` 创建 Bot，得到 `TEL_TOK`
2. 给 Bot 发一条消息后访问  
   `https://api.telegram.org/bot<token>/getUpdates`  
   从返回中取 `chat.id` 作为 `TEL_ID`

### 4. 运行 GitHub Actions

1. 打开仓库 **Actions**，启用工作流
2. 选择 **Run Koyeb Auto Login** → **Run workflow** 手动触发
3. 默认定时：**每周一 UTC 00:00**
4. 任意账号失败时，workflow 会以失败状态结束（不再假成功）

### 5. 本地测试

```bash
export KOY_TOKENS='main:你的token'
# 可选
export TEL_TOK='...'
export TEL_ID='...'
python3 koyeb-login.py
```

成功示例输出：

```text
账号 main 保活成功 | email=you@example.com | id=... | org=... | org_status=ACTIVE
完成：全部成功 1/1
```

### 注意事项

- Token 等同账号权限，只放在 Secrets，不要提交到代码
- Token 丢失只能删除后重建
- 旧的邮箱密码 Secret `KOY_ACC` 已废弃；若仍配置且内容是 `name:token`，脚本会兼容读取
