#!/usr/bin/env python3
"""Koyeb 账号保活：通过 API Token 调用账号接口，替代已失效的浏览器登录。"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

API_PROFILE = "https://app.koyeb.com/v1/account/profile"
API_ORG = "https://app.koyeb.com/v1/account/organization"
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
            body = resp.read().decode("utf-8", errors="replace")
            print(f"Telegram 发送完成: HTTP {resp.status}")
            print(body[:300])
    except Exception as exc:  # noqa: BLE001
        print(f"发送消息失败: {exc}")


def api_get(url: str, token: str) -> tuple[int, dict | str]:
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "User-Agent": "koyeb-login-keepalive/2.0",
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


def check_token(name: str, token: str) -> tuple[bool, str]:
    status, body = api_get(API_PROFILE, token)
    if status != 200:
        detail = body
        if isinstance(body, dict):
            detail = body.get("message") or body.get("code") or body
        return False, f"账号 {name} 保活失败: HTTP {status} - {detail}"

    user = body.get("user") if isinstance(body, dict) else None
    email = ""
    user_id = ""
    if isinstance(user, dict):
        email = user.get("email") or ""
        user_id = user.get("id") or ""

    org_status, org_body = api_get(API_ORG, token)
    org_name = ""
    org_state = ""
    if org_status == 200 and isinstance(org_body, dict):
        org = org_body.get("organization") or {}
        if isinstance(org, dict):
            org_name = org.get("name") or ""
            org_state = org.get("status") or ""

    parts = [f"账号 {name} 保活成功"]
    if email:
        parts.append(f"email={email}")
    if user_id:
        parts.append(f"id={user_id}")
    if org_name:
        parts.append(f"org={org_name}")
    if org_state:
        parts.append(f"org_status={org_state}")
    return True, " | ".join(parts)


def parse_tokens(raw: str) -> list[tuple[str, str]]:
    """解析 `name:token` 列表，空格分隔。也兼容仅 token（自动命名）。"""
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
    # 优先 KOY_TOKENS；兼容误配到 KOY_ACC 的 token 列表
    tokens_env = os.environ.get("KOY_TOKENS") or os.environ.get("KOY_ACC") or ""
    if not tokens_env.strip():
        print("错误：未找到 KOY_TOKENS（或 KOY_ACC）环境变量")
        print("格式: name1:token1 name2:token2")
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
