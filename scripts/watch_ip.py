#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
白名单生效监听器。

你在这边改后台白名单，它在那边每 30 秒试一次。一旦微信放行，
自动继续建草稿，不用反复回来问"好了没"。

用法：
    python watch_ip.py                  # 只等白名单生效
    python watch_ip.py --draft          # 生效后自动建草稿
    python watch_ip.py -i 60            # 每 60 秒试一次（默认 30）
    python watch_ip.py -m 3             # 只试 3 次就退出（测试用）
"""
import argparse
import json
import os
import sys
import time
import urllib.parse
import urllib.request
import urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import publish


def try_token(appid, secret):
    qs = urllib.parse.urlencode({
        "grant_type": "client_credential",
        "appid": appid,
        "secret": secret,
    })
    return publish.http_get_json("{}/cgi-bin/token?{}".format(publish.API, qs))


def main():
    p = argparse.ArgumentParser(description="轮询等待 IP 白名单生效")
    p.add_argument("-c", "--config", default=None)
    p.add_argument("-i", "--interval", type=int, default=30, help="重试间隔秒数，默认 30")
    p.add_argument("-m", "--max-attempts", type=int, default=0, help="最多试几次，0=不限")
    p.add_argument("--draft", action="store_true", help="白名单生效后自动建草稿")
    p.add_argument("--no-preflight", action="store_true",
                   help="配合 --draft：建草稿时跳过发布前体检")
    args = p.parse_args()

    args.config = publish.resolve_config_path(args.config)
    cfg = publish.load_config(args.config)
    appid, secret = cfg["appid"], cfg["appsecret"]
    cache_path = publish.token_cache_path(args.config)

    print("监听中：每 {} 秒探测一次 token 接口。Ctrl+C 停止。".format(args.interval))
    print("AppID = {}".format(appid))
    print("-" * 58)

    n = 0
    last_ip = None
    while True:
        n += 1
        try:
            res = try_token(appid, secret)
        except SystemExit:
            raise
        except Exception as e:
            print("[{}] 第 {} 次：网络异常 {}，{} 秒后重试".format(
                time.strftime("%H:%M:%S"), n, e, args.interval))
            time.sleep(args.interval)
            continue

        if res.get("access_token"):
            print("[{}] [OK] 第 {} 次：白名单已生效，token 拿到".format(
                time.strftime("%H:%M:%S"), n))
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump({"appid": appid, "access_token": res["access_token"],
                           "expire_at": time.time() + int(res.get("expires_in", 7200))}, f)
            break

        code = res.get("errcode")
        if code == 40164:
            errmsg = res.get("errmsg", "")
            import re
            ips = sorted(set(re.findall(r"\b\d{1,3}(?:\.\d{1,3}){3}\b", errmsg)))
            cur = "、".join(ips) if ips else "?"
            if cur != last_ip:
                print("[{}] 第 {} 次：仍是 40164，被拒 IP = {}".format(
                    time.strftime("%H:%M:%S"), n, cur))
                print("           请确认这个 IP 已保存，且管理员扫码确认完成")
                last_ip = cur
            else:
                print("[{}] 第 {} 次：仍未生效 ...".format(time.strftime("%H:%M:%S"), n))
        else:
            print("[X] 遇到非白名单类错误，停止监听")
            print("    errcode={} errmsg={}".format(code, res.get("errmsg")))
            print("    {}".format(publish.ERR_HINT.get(code, "请查微信通用错误码表")))
            sys.exit(1)

        if args.max_attempts and n >= args.max_attempts:
            print("已试满 {} 次，退出。".format(n))
            sys.exit(3)
        time.sleep(args.interval)

    if args.draft:
        print("-" * 58)
        print("接着建草稿 ...")
        sys.argv = ["publish.py", "draft", "-c", args.config]
        if args.no_preflight:
            sys.argv.append("--no-preflight")
        publish.main()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n已手动停止。")
