#!/usr/bin/env python3
"""Koyeb 账号保活：通过 API Token 调用账号/组织接口。"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

API_BASE = "https://app.koyeb.com"
REQUEST_TIMEOUT = 30


def send_telegram_message(message: str) -> None:
    bot_token = os.environ.get("TEL_TOK")
    chat_id = os.environ.get("TEL_ID")
    if not bot_token or not chat_id:
        print("Telegram 配置缺失，跳过发送消息")
        return

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = json.dumps(
        {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
    ).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            print(f"Telegram 发送完成: HTTP {resp.status}")
    except Exception as exc:  # noqa: BLE001
        print(f"发送消息失败: {exc}")


def api_get(path: str, token: str, query: dict | None = None) -> tuple[int, dict | str]:
    url = API_BASE + path
    if query:
        url += "?" + urllib.parse.urlencode(query)
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "User-Agent": "koyeb-login-keepalive/2.1",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            try:
                return resp.status, json.loads(raw)
            except json.JSONDecodeError:
                return resp.status, raw
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            return exc.code, json.loads(raw)
        except json.JSONDecodeError:
            return exc.code, raw
    except Exception as exc:  # noqa: BLE001
        return 0, str(exc)


def detail_of(body: dict | str) -> str:
    if isinstance(body, dict):
        return str(body.get("message") or body.get("code") or body)
    return str(body)


def check_token(name: str, token: str) -> tuple[bool, str]:
    token = token.strip()
    if not token:
        return False, f"账号 {name} 保活失败: token 为空"

    # Koyeb personal/org API token 通常为 64 字符
    if len(token) < 32:
        return (
            False,
            f"账号 {name} 保活失败: token 长度异常({len(token)})。"
            "请到 https://app.koyeb.com/user/settings/api 创建 Personal Access Token（通常 64 位），"
            "不要填登录密码。格式: name:token",
        )

    # 1) 个人 Token：/v1/account/profile
    status, body = api_get("/v1/account/profile", token)
    if status == 200 and isinstance(body, dict):
        user = body.get("user") or {}
        email = user.get("email") or ""
        user_id = user.get("id") or ""

        org_status, org_body = api_get("/v1/account/organization", token)
        org_name = org_state = ""
        if org_status == 200 and isinstance(org_body, dict):
            org = org_body.get("organization") or {}
            org_name = org.get("name") or ""
            org_state = org.get("status") or ""

        parts = [f"账号 {name} 保活成功(user)"]
        if email:
            parts.append(f"email={email}")
        if user_id:
            parts.append(f"id={user_id}")
        if org_name:
            parts.append(f"org={org_name}")
        if org_state:
            parts.append(f"org_status={org_state}")
        return True, " | ".join(parts)

    msg = detail_of(body)

    # 2) 组织 Token：profile 会返回 404 No user defined in session
    #    改走 apps / organization 相关接口完成保活
    if status in (403, 404) or "No user defined in session" in msg:
        apps_status, apps_body = api_get("/v1/apps", token, {"limit": "1"})
        if apps_status == 200 and isinstance(apps_body, dict):
            apps = apps_body.get("apps") or []
            org_id = ""
            if apps and isinstance(apps[0], dict):
                org_id = apps[0].get("organization_id") or ""

            org_name = org_state = ""
            if org_id:
                o_status, o_body = api_get(f"/v1/organizations/{org_id}", token)
                if o_status == 200 and isinstance(o_body, dict):
                    org = o_body.get("organization") or {}
                    org_name = org.get("name") or ""
                    org_state = org.get("status") or ""

            parts = [f"账号 {name} 保活成功(org_token)"]
            if org_id:
                parts.append(f"org_id={org_id}")
            if org_name:
                parts.append(f"org={org_name}")
            if org_state:
                parts.append(f"org_status={org_state}")
            parts.append(f"apps={len(apps)}")
            return True, " | ".join(parts)

        # 再试 organizations 列表
        orgs_status, orgs_body = api_get(
            "/v1/account/organizations",
            token,
            {"limit": "1"},
        )
        if orgs_status == 200 and isinstance(orgs_body, dict):
            return True, f"账号 {name} 保活成功(orgs_list) | HTTP 200"

        return (
            False,
            f"账号 {name} 保活失败: profile={status} {msg}; "
            f"apps={apps_status} {detail_of(apps_body)}; "
            f"orgs={orgs_status} {detail_of(orgs_body)}",
        )

    return False, f"账号 {name} 保活失败: HTTP {status} - {msg}"


def parse_tokens(raw: str) -> list[tuple[str, str]]:
    """解析 `name:token` 列表，空格分隔。

    token 本身不含冒号；若 name 是邮箱，仍按第一个冒号分割。
    也兼容仅 token（自动命名）。
    """
    items: list[tuple[str, str]] = []
    for idx, part in enumerate(raw.split(), start=1):
        part = part.strip()
        if not part:
            continue
        if ":" in part:
            name, token = part.split(":", 1)
            name = name.strip() or f"account{idx}"
            token = token.strip()
        else:
            name, token = f"account{idx}", part
        if token:
            items.append((name, token))
    return items


def main() -> int:
    tokens_env = os.environ.get("KOY_TOKENS") or os.environ.get("KOY_ACC") or ""
    if not tokens_env.strip():
        print("错误：未找到 KOY_TOKENS（或 KOY_ACC）环境变量")
        print("格式: name1:token1 name2:token2")
        print("Token 获取: https://app.koyeb.com/user/settings/api")
        return 1

    accounts = parse_tokens(tokens_env)
    if not accounts:
        print("错误：KOY_TOKENS 解析后为空，请检查格式 name:token")
        return 1

    results: list[str] = []
    failed = 0

    for name, token in accounts:
        ok, msg = check_token(name, token)
        print(msg)
        results.append(msg)
        if not ok:
            failed += 1

    report = "*Koyeb API 保活任务报告*:\n\n" + "\n".join(results)
    send_telegram_message(report)

    if failed:
        print(f"完成：成功 {len(accounts) - failed}/{len(accounts)}，失败 {failed}")
        return 1

    print(f"完成：全部成功 {len(accounts)}/{len(accounts)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
