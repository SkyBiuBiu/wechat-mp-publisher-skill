#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
微信公众号图文发布工具 —— 零依赖，只用 Python 标准库（Python 3.8+）

链路：access_token -> 上传正文图片(uploadimg) -> 上传封面永久素材(add_material)
      -> 新增草稿(draft/add) -> [可选] 正式发布(freepublish/submit)

用法：
    python publish.py check      # 只验证凭证 + IP 白名单，不发任何内容
    python publish.py preflight  # 只做发布前体检（字数/图片/排版/合规），不连微信
    python publish.py draft      # 建草稿（默认，安全）。发请求前会自动跑一次体检
    python publish.py publish    # 建草稿并立即正式发布（会二次确认）
    python publish.py publish --media-id XXX   # 直接发布草稿箱里已有的某篇，不重复建稿
    python publish.py list       # 列出草稿箱
    python publish.py delete --media-id XXX -y   # 删除指定草稿
    python publish.py token -f   # 强制刷新 access_token

    draft 相关逃生口：
    --no-preflight   跳过发布前体检（不建议）
    --no-compliance  体检时跳过广告法/导流/金融等合规词扫描

官方接口文档：
    token      GET  /cgi-bin/token
    正文图片   POST /cgi-bin/media/uploadimg
    永久素材   POST /cgi-bin/material/add_material?type=image
    新增草稿   POST /cgi-bin/draft/add
    发布草稿   POST /cgi-bin/freepublish/submit
"""

import argparse
import json
import mimetypes
import os
import re
import sys
import time
import uuid
import urllib.error
import urllib.parse
import urllib.request

API = "https://api.weixin.qq.com"
HERE = os.path.dirname(os.path.abspath(__file__))
FALLBACK_TOKEN_CACHE = os.path.join(HERE, ".token_cache.json")


def token_cache_path(cfg_path):
    """token 缓存跟着配置文件走，多个项目/多个公众号并存时不会互相覆盖。"""
    if cfg_path and os.path.isfile(cfg_path):
        return os.path.join(os.path.dirname(os.path.abspath(cfg_path)), ".token_cache.json")
    return FALLBACK_TOKEN_CACHE


def resolve_config_path(explicit):
    """配置查找顺序：-c 显式指定 > 当前工作目录 > 脚本所在目录。"""
    if explicit:
        return explicit
    for cand in (os.path.join(os.getcwd(), "config.json"),
                 os.path.join(HERE, "config.json")):
        if os.path.isfile(cand):
            return cand
    return os.path.join(os.getcwd(), "config.json")

# ---------------------------------------------------------------- 错误码字典
ERR_HINT = {
    -1: "微信系统繁忙，稍后重试",
    40001: "AppSecret 错误，或 access_token 已失效",
    40005: "文件格式不支持。正文图片仅支持 jpg/png",
    40007: "media_id 无效（封面素材可能被删了）",
    40009: "图片体积或尺寸太大。uploadimg 要求单张 < 1MB",
    40013: "AppID 不合法。检查大小写、有没有多余空格",
    40125: "AppSecret 不合法",
    40164: "调用来源 IP 不在白名单。去微信开发者平台 → 公众号详情页 → API IP白名单 添加；"
           "老入口 mp 后台「设置与开发 - 基本配置 - IP白名单」是同一个白名单，填哪边都可以",
    40243: "AppSecret 已被冻结，需在公众平台后台解冻",
    41004: "缺少 secret 参数",
    45009: "接口调用超过每日限额",
    48001: "接口未授权：该账号没有此接口权限。常见于未认证订阅号 / 未认证服务号",
    50004: "该账号禁止使用 token 接口",
    50007: "账号已冻结",
    53404: "账号被限制带货能力",
    53503: "草稿未通过发布检查",
    53504: "请到公众平台官网使用该草稿",
    53505: "请先到公众平台官网手动保存成功后再发布",
}


def out(msg=""):
    print(msg, flush=True)


def die(msg, code=1):
    print("\n[X] " + msg, file=sys.stderr, flush=True)
    sys.exit(code)


def check_api_error(res, stage):
    """微信的惯例：errcode 非 0 即失败。这里统一翻译成中文提示。"""
    code = res.get("errcode", 0)
    if code:
        errmsg = res.get("errmsg", "")
        hint = ERR_HINT.get(code, "未在本地字典中登记，请查微信通用错误码表")
        # 40164 的 errmsg 自带被拒的出口 IP，直接抠出来省得用户自己查
        extra = ""
        if code == 40164:
            ips = sorted(set(re.findall(r"\b\d{1,3}(?:\.\d{1,3}){3}\b", errmsg)))
            if ips:
                extra = "\n    → 把下面这个 IP 加进白名单即可：{}".format("、".join(ips))
        die("{} 失败 → errcode={} errmsg={}\n    可能原因：{}{}".format(
            stage, code, errmsg, hint, extra))
    return res


# ---------------------------------------------------------------- HTTP 封装
def http_get_json(url, timeout=30):
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        die("HTTP {} 请求失败：{}".format(e.code, e.read().decode("utf-8", "ignore")))


def build_multipart(fields, files):
    """fields: {name: str}; files: [(name, filename, bytes, content_type)]"""
    boundary = "----WXMPBoundary" + uuid.uuid4().hex
    crlf = b"\r\n"
    body = bytearray()
    for k, v in fields.items():
        body += b"--" + boundary.encode() + crlf
        body += ('Content-Disposition: form-data; name="%s"' % k).encode("utf-8") + crlf + crlf
        body += str(v).encode("utf-8") + crlf
    for name, filename, content, ctype in files:
        body += b"--" + boundary.encode() + crlf
        body += ('Content-Disposition: form-data; name="%s"; filename="%s"'
                 % (name, filename)).encode("utf-8") + crlf
        body += ("Content-Type: %s" % ctype).encode() + crlf + crlf
        body += content + crlf
    body += b"--" + boundary.encode() + b"--" + crlf
    return bytes(body), "multipart/form-data; boundary=" + boundary


def http_post_multipart(url, fields, files, timeout=90):
    body, ctype = build_multipart(fields, files)
    req = urllib.request.Request(url, data=body,
                                 headers={"Content-Type": ctype}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        die("HTTP {} 上传失败：{}".format(e.code, e.read().decode("utf-8", "ignore")))


def http_post_json(url, payload, timeout=60):
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json; charset=utf-8"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        die("HTTP {} 请求失败：{}".format(e.code, e.read().decode("utf-8", "ignore")))


# ---------------------------------------------------------------- token
def get_access_token(appid, secret, force=False, cache_path=None):
    cache_path = cache_path or FALLBACK_TOKEN_CACHE
    if not force and os.path.exists(cache_path):
        try:
            with open(cache_path, encoding="utf-8") as f:
                c = json.load(f)
            left = int(c.get("expire_at", 0) - time.time())
            if c.get("appid") == appid and left > 300:
                out("[1/5] access_token 复用本地缓存（剩余 {} 秒）".format(left))
                return c["access_token"]
        except Exception:
            pass

    out("[1/5] 向微信申请新的 access_token ...")
    qs = urllib.parse.urlencode({
        "grant_type": "client_credential",
        "appid": appid,
        "secret": secret,
    })
    res = http_get_json("{}/cgi-bin/token?{}".format(API, qs))
    check_api_error(res, "获取 access_token")
    tok = res.get("access_token")
    if not tok:
        die("返回体中没有 access_token：{}".format(res))
    try:
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump({"appid": appid, "access_token": tok,
                       "expire_at": time.time() + int(res.get("expires_in", 7200))}, f)
    except OSError:
        pass
    out("      token = {}...{}（有效期 {} 秒）".format(tok[:8], tok[-6:], res.get("expires_in")))
    return tok


# ---------------------------------------------------------------- 素材上传
def upload_inline_image(token, abs_path):
    """正文里的图片 -> /cgi-bin/media/uploadimg，返回 mmbiz.qpic.cn URL。
    注意：微信会过滤正文中的外部图片链接，正文图必须先过这个接口。"""
    if not os.path.isfile(abs_path):
        die("正文图片不存在：{}".format(abs_path))
    size = os.path.getsize(abs_path)
    if size > 1024 * 1024:
        die("正文图片 {} 有 {:.2f} MB，超过 uploadimg 的 1MB 上限".format(abs_path, size / 1048576))
    ext = os.path.splitext(abs_path)[1].lower()
    if ext not in (".jpg", ".jpeg", ".png"):
        die("正文图片仅支持 jpg/png，当前是 {}".format(ext))
    ctype = mimetypes.guess_type(abs_path)[0] or "image/png"
    with open(abs_path, "rb") as f:
        content = f.read()
    url = "{}/cgi-bin/media/uploadimg?{}".format(
        API, urllib.parse.urlencode({"access_token": token}))
    res = http_post_multipart(url, {}, [("media", os.path.basename(abs_path), content, ctype)])
    check_api_error(res, "上传正文图片 " + os.path.basename(abs_path))
    if not res.get("url"):
        die("uploadimg 未返回 url：{}".format(res))
    out("      正文图 {} → {}".format(os.path.basename(abs_path), res["url"][:64] + "..."))
    return res["url"]


def upload_cover_material(token, abs_path):
    """封面必须是永久素材，返回 media_id。"""
    if not os.path.isfile(abs_path):
        die("封面图不存在：{}".format(abs_path))
    size = os.path.getsize(abs_path)
    if size > 10 * 1024 * 1024:
        die("封面图 {:.2f} MB，超过永久图片素材 10MB 上限".format(size / 1048576))
    ctype = mimetypes.guess_type(abs_path)[0] or "image/png"
    with open(abs_path, "rb") as f:
        content = f.read()
    url = "{}/cgi-bin/material/add_material?{}".format(
        API, urllib.parse.urlencode({"access_token": token, "type": "image"}))
    res = http_post_multipart(url, {}, [("media", os.path.basename(abs_path), content, ctype)])
    check_api_error(res, "上传封面永久素材")
    if not res.get("media_id"):
        die("add_material 未返回 media_id：{}".format(res))
    out("      封面素材 media_id = {}".format(res["media_id"]))
    return res["media_id"]


# ---------------------------------------------------------------- 正文处理
IMG_LOCAL_RE = re.compile(r'(<img\b[^>]*?\bsrc\s*=\s*["\'])([^"\']+)(["\'])', re.I)
COMMENT_RE = re.compile(r"<!--.*?-->", re.S)


def rewrite_local_images(token, html, base_dir):
    """把正文里指向本地文件的 <img src> 换成微信域名下的 URL。
    已经是 http(s):// 的一律不动（但外链会被微信过滤，需自行确保是 mmbiz 域名）。"""
    def repl(m):
        head, src, tail = m.group(1), m.group(2), m.group(3)
        if re.match(r'^(https?:)?//', src) or src.startswith("data:"):
            return m.group(0)
        abs_path = src if os.path.isabs(src) else os.path.join(base_dir, src)
        new_url = upload_inline_image(token, abs_path)
        return head + new_url + tail

    return IMG_LOCAL_RE.sub(repl, html)


# ---------------------------------------------------------------- 配置
def load_config(path):
    """读配置。文件可以缺省，凭证允许用环境变量兜底：
    WECHAT_MP_APPID / WECHAT_MP_APPSECRET。"""
    cfg = {}
    if os.path.isfile(path):
        try:
            with open(path, encoding="utf-8") as f:
                cfg = json.load(f)
        except json.JSONDecodeError as e:
            die("配置文件 {} 不是合法 JSON：{}".format(path, e))
    else:
        out("[i] 没找到 {}，改从环境变量读凭证".format(path))

    if not cfg.get("appid"):
        cfg["appid"] = os.environ.get("WECHAT_MP_APPID", "")
    if not cfg.get("appsecret"):
        cfg["appsecret"] = os.environ.get("WECHAT_MP_APPSECRET", "")

    for k in ("appid", "appsecret"):
        v = str(cfg.get(k) or "")
        env = "WECHAT_MP_" + ("APPID" if k == "appid" else "APPSECRET")
        if not v:
            die("缺少 {}。填进 config.json，或设环境变量 {}。".format(k, env))
        if v.lower().startswith("wx000") or "填" in v or v.startswith("你的"):
            die("{} 还是占位值，请填真实数据".format(k))
    return cfg


# ---------------------------------------------------------------- 四个子命令
def publish_draft(token, media_id, args, title=""):
    """把指定草稿正式发布出去。不可撤回，务必带确认。"""
    out("\n" + "!" * 62)
    out("  即将正式发布（freepublish/submit）：粉丝会真的收到这条推送，且不可撤回")
    if title:
        out("  标题：{}".format(title))
    out("  草稿 media_id：{}".format(media_id))
    out("!" * 62)
    if not args.yes:
        ans = input("  确认发布？输入 yes 继续：").strip().lower()
        if ans != "yes":
            die("已取消。草稿已保留在草稿箱。", code=2)
    pub = http_post_json("{}/cgi-bin/freepublish/submit?{}".format(
        API, urllib.parse.urlencode({"access_token": token})), {"media_id": media_id})
    check_api_error(pub, "正式发布")
    out("      [OK] 发布任务已提交 publish_id={}".format(pub.get("publish_id")))
    out("      注意：errcode=0 只代表任务提交成功，最终结果以服务端事件推送为准")
    return pub


def cmd_check(cfg, args):
    out("== 连通性自检（不发任何内容）==")
    out("AppID = {}".format(cfg["appid"]))
    tok = get_access_token(cfg["appid"], cfg["appsecret"], force=args.force,
                           cache_path=token_cache_path(args.config))
    out("\n[OK] 凭证有效，IP 白名单正常。")
    out("     这条链路能跑通 = 后面的草稿接口也有资格调用。")
    out("\n注意：check 只能证明 token 接口可用，")
    out("      不能证明 draft/add、freepublish/submit 有权限（未认证账号会在那一步报 48001）。")


TITLE_MAX = 32
AUTHOR_MAX = 16
DIGEST_MAX = 120
CONTENT_MAX_CHARS = 20000


def run_preflight(cfg_path, with_compliance=True, quiet=False):
    """发布前体检。由同目录的 preflight.py 提供，P0 未通过则中止流程。

    为什么要在建草稿前跑：字数超限、图片超过 1MB、外链图这类问题，
    等微信报错时只知道 errcode，还得回来翻文件；本地先查一遍省一个来回。
    """
    if not os.path.isfile(os.path.join(HERE, "preflight.py")):
        out("[i] 没找到 preflight.py，跳过体检")
        return 0
    if HERE not in sys.path:
        sys.path.insert(0, HERE)
    try:
        import preflight
    except ImportError as e:
        out("[i] 体检模块加载失败（{}），跳过".format(e))
        return 0

    out("== 发布前体检（draft 自动执行，--no-preflight 可跳过）==")
    rc = preflight.run(cfg_path, with_compliance=with_compliance, quiet=quiet)
    if rc != 0:
        die("体检未通过：上面标 P0 的问题必须先在本地修掉。\n"
            "    确要跳过体检强行建草稿：加 --no-preflight（不建议，微信那一步通常也会失败）")
    return rc


def cmd_draft(cfg, args):
    art = cfg.get("article", {})
    base_dir = os.path.dirname(os.path.abspath(args.config))

    # ---- 发布前体检：本地先拦掉会因为平台约束翻车的内容
    if getattr(args, "no_preflight", False):
        out("[i] 已跳过发布前体检（--no-preflight）")
    else:
        run_preflight(args.config,
                      with_compliance=not getattr(args, "no_compliance", False))

    # ---- 标题/作者/摘要长度校验（微信的硬限制，超了直接报错更省事）
    title = (art.get("title") or "").strip()
    if not title:
        die("article.title 不能为空")
    if len(title) > TITLE_MAX:
        die("标题 {} 个字，超过 {} 字上限".format(len(title), TITLE_MAX))
    author = (art.get("author") or cfg.get("author") or "").strip()
    if len(author) > AUTHOR_MAX:
        die("作者 {} 个字，超过 {} 字上限".format(len(author), AUTHOR_MAX))

    # ---- 正文
    content_path = art.get("content_file")
    if not content_path:
        die("article.content_file 未配置")
    content_path = content_path if os.path.isabs(content_path) else os.path.join(base_dir, content_path)
    if not os.path.isfile(content_path):
        die("正文文件不存在：{}".format(content_path))
    with open(content_path, encoding="utf-8") as f:
        content = f.read().strip()

    # 公众号会过滤 HTML 注释；更要紧的是注释里的 <img> 示例会被误判成本地图片去上传，先剥离
    content, n_cmt = COMMENT_RE.subn("", content)
    if n_cmt:
        out("[i] 剥离了 {} 段 HTML 注释（公众号本身也会过滤，不影响成稿）".format(n_cmt))

    if len(content) > CONTENT_MAX_CHARS:
        die("正文 {} 字符，超过 {} 上限".format(len(content), CONTENT_MAX_CHARS))
    if len(content.encode("utf-8")) > 1024 * 1024:
        die("正文超过 1MB 上限")

    digest = (art.get("digest") or "").strip()
    if not digest:
        plain = re.sub(r"<[^>]+>", "", content)
        plain = re.sub(r"\s+", " ", plain).strip()
        digest = plain[:54]
        out("[i] 摘要留空，自动抓取正文前 54 字")
    if len(digest) > DIGEST_MAX:
        digest = digest[:DIGEST_MAX]
        out("[i] 摘要超过 {} 字，已截断".format(DIGEST_MAX))

    token = get_access_token(cfg["appid"], cfg["appsecret"], force=args.force,
                             cache_path=token_cache_path(args.config))

    out("[2/5] 处理正文内本地图片（上传到微信图床）...")
    before = len(IMG_LOCAL_RE.findall(content))
    content = rewrite_local_images(token, content, base_dir)
    out("      <img> 标签共 {} 个，其中本地路径的已上传并替换".format(before))

    out("[3/5] 上传封面永久素材 ...")
    cover_file = art.get("cover_file")
    thumb_media_id = None
    if cover_file:
        cp = cover_file if os.path.isabs(cover_file) else os.path.join(base_dir, cover_file)
        thumb_media_id = upload_cover_material(token, cp)
    else:
        out("      [i] 未配置封面图。图文消息的 thumb_media_id 必填，微信可能报错 40007。")

    article = {
        "article_type": "news",
        "title": title,
        "author": author,
        "digest": digest,
        "content": content,
        "content_source_url": art.get("content_source_url", "") or "",
        "need_open_comment": int(cfg.get("need_open_comment", 0)),
        "only_fans_can_comment": int(cfg.get("only_fans_can_comment", 0)),
    }
    if thumb_media_id:
        article["thumb_media_id"] = thumb_media_id

    out("[4/5] 新增草稿 ...")
    url = "{}/cgi-bin/draft/add?{}".format(API, urllib.parse.urlencode({"access_token": token}))
    res = http_post_json(url, {"articles": [article]})
    check_api_error(res, "新增草稿")
    media_id = res.get("media_id")
    out("      [OK] 草稿已创建")
    out("      draft media_id = {}".format(media_id))
    out("      现在去公众平台 → 草稿箱 就能看到这篇《{}》".format(title))

    # 附赠：试着查一下该草稿的详情，确认内容真的落库了
    out("\n[5/5] 回查草稿详情 ...")
    g = http_post_json("{}/cgi-bin/draft/get?{}".format(
        API, urllib.parse.urlencode({"access_token": token})), {"media_id": media_id})
    if g.get("errcode") in (0, None) and g.get("news_item"):
        it = g["news_item"][0]
        out("      标题: {}".format(it.get("title")))
        out("      作者: {}".format(it.get("author")))
        out("      封面: {}".format((it.get("thumb_url") or "")[:70]))
        out("      正文长度: {} 字符".format(len(it.get("content", ""))))
    else:
        out("      [i] 回查未返回详情：{}".format(g))

    if args.publish:
        publish_draft(token, media_id, args, title=title)


def cmd_delete(cfg, args):
    """删除草稿箱里的指定草稿。破坏性操作，必须显式给 --media-id。"""
    if not args.media_id:
        die("delete 必须用 --media-id 指定要删除的草稿。可以用 list 先查 media_id。")
    token = get_access_token(cfg["appid"], cfg["appsecret"], force=args.force,
                             cache_path=token_cache_path(args.config))
    if not args.yes:
        ans = input("  确认删除草稿 {}？输入 yes 继续：".format(args.media_id)).strip().lower()
        if ans != "yes":
            die("已取消。", code=2)
    res = http_post_json("{}/cgi-bin/draft/delete?{}".format(
        API, urllib.parse.urlencode({"access_token": token})), {"media_id": args.media_id})
    check_api_error(res, "删除草稿")
    out("[OK] 草稿已删除：{}".format(args.media_id))


def cmd_list(cfg, args):
    token = get_access_token(cfg["appid"], cfg["appsecret"], force=args.force,
                             cache_path=token_cache_path(args.config))
    url = "{}/cgi-bin/draft/batchget?{}".format(API, urllib.parse.urlencode({"access_token": token}))
    res = http_post_json(url, {"offset": 0, "count": 20, "no_content": 1})
    check_api_error(res, "获取草稿列表")
    items = res.get("item", [])
    out("草稿总数：{}（本次列出 {} 条）".format(res.get("total_count"), len(items)))
    for it in items:
        mid = str(it.get("media_id") or "")
        for n in it.get("content", {}).get("news_item", []):
            out("  - [{}...] {}".format(mid[:24], n.get("title")))


# ---------------------------------------------------------------- main
def main():
    p = argparse.ArgumentParser(
        description="微信公众号图文发布工具（零依赖）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__)
    p.add_argument("action",
                   choices=["check", "preflight", "draft", "publish", "list", "delete", "token"],
                   help="check=自检 / preflight=发布前体检 / draft=建草稿 / "
                        "publish=建草稿并发布 / list=看草稿箱 / "
                        "delete=删草稿（需 --media-id）/ token=刷新凭证")
    p.add_argument("-c", "--config", default=None,
                   help="配置文件路径。默认按 当前目录/config.json → 脚本目录/config.json 查找")
    p.add_argument("-f", "--force", action="store_true",
                   help="强制重新获取 access_token（忽略本地缓存）")
    p.add_argument("-y", "--yes", action="store_true",
                   help="发布时跳过交互确认（危险，脚本化场景才用）")
    p.add_argument("--media-id", default=None,
                   help="配合 publish 使用：直接发布这条已存在的草稿，不重新建草稿")
    p.add_argument("--no-preflight", action="store_true",
                   help="draft 前不跑发布前体检（不建议，体检能提前拦掉字数/图片/排版问题）")
    p.add_argument("--no-compliance", action="store_true",
                   help="体检时跳过广告法/导流/金融等合规词扫描")
    p.add_argument("--warn-only", action="store_true",
                   help="配合 preflight 使用：即使有 P0 也返回退出码 0")
    p.add_argument("--json", dest="as_json", action="store_true",
                   help="配合 preflight 使用：输出 JSON 结果，便于 CI 消费")
    args = p.parse_args()

    if args.action == "publish" and not args.media_id:
        args.publish = True
        args.action = "draft"
    else:
        args.publish = False

    args.config = resolve_config_path(args.config)

    # 体检不碰网络、也不需要凭证，所以放在 load_config 之前，
    # 这样 appid 还没配好时也能先查内容和排版。
    if args.action == "preflight":
        if HERE not in sys.path:
            sys.path.insert(0, HERE)
        try:
            import preflight
        except ImportError as e:
            die("无法加载体检模块 {}：{}".format(os.path.join(HERE, "preflight.py"), e))
        sys.exit(preflight.run(args.config,
                               with_compliance=not args.no_compliance,
                               warn_only=args.warn_only,
                               as_json=args.as_json,
                               quiet=False))

    cfg = load_config(args.config)

    if args.action == "check":
        cmd_check(cfg, args)
    elif args.action == "publish" and args.media_id:
        token = get_access_token(cfg["appid"], cfg["appsecret"], force=args.force,
                                 cache_path=token_cache_path(args.config))
        publish_draft(token, args.media_id, args)
    elif args.action == "draft":
        cmd_draft(cfg, args)
    elif args.action == "list":
        cmd_list(cfg, args)
    elif args.action == "delete":
        cmd_delete(cfg, args)
    elif args.action == "token":
        args.force = True
        get_access_token(cfg["appid"], cfg["appsecret"], force=True,
                         cache_path=token_cache_path(args.config))
        out("[OK] 凭证已刷新并写入本地缓存")


if __name__ == "__main__":
    main()
