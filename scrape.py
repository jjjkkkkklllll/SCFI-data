# -*- coding: utf-8 -*-
"""
从上海航运交易所抓取 SCFI（上海出口集装箱运价指数）并写入 scfi.json。
由 GitHub Actions 每周自动运行，不需要人工干预。

只依赖 Python 标准库，GitHub 的 ubuntu 环境直接能跑。
"""
import json
import pathlib
import re
import sys
import urllib.request
from datetime import datetime, timezone

URL = "https://www.sse.net.cn/index/singleIndex?indexType=scfi"
OUT = pathlib.Path("scfi.json")


def fetch(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/141.0.0.0 Safari/537.36"),
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    })
    with urllib.request.urlopen(req, timeout=90) as r:
        raw = r.read()
    for enc in ("utf-8", "gb18030"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "replace")


def parse(html):
    """取出本期数值、本期日期、上期数值与涨跌。页面是服务端渲染的静态 HTML。"""
    t = re.sub(r"<script.*?</script>", " ", html, flags=re.S)
    t = re.sub(r"<style.*?</style>", " ", t, flags=re.S)
    t = re.sub(r"<[^>]+>", " ", t)
    t = t.replace("&nbsp;", " ")
    t = re.sub(r"\s+", " ", t)

    cur = re.search(r"本期\s+(\d{4}-\d{2}-\d{2})", t)
    prev = re.search(r"上期\s+(\d{4}-\d{2}-\d{2})", t)
    val = re.search(r"综合指数\s+Comprehensive Index\s+([\d.]+)\s+([\d.]+)", t)

    if not (cur and val):
        raise ValueError("页面结构可能变了：找不到「本期」日期或综合指数数值")

    return {
        "date": cur.group(1),
        "prevDate": prev.group(1) if prev else None,
        "prev": float(val.group(1)),
        "value": float(val.group(2)),
    }


def main():
    html = fetch(URL)
    now = parse(html)
    print("抓到：%s  %s  (上期 %s %s)" % (
        now["date"], now["value"], now["prevDate"], now["prev"]))

    data = {"points": []}
    if OUT.exists():
        try:
            data = json.loads(OUT.read_text(encoding="utf-8"))
        except Exception as e:
            print("原有 scfi.json 读不动（%s），按空的来" % e)

    points = {p["d"]: p["v"] for p in data.get("points", [])
              if isinstance(p, dict) and "d" in p and "v" in p}
    points[now["date"]] = now["value"]

    out = {
        "source": "上海航运交易所 SCFI",
        "updated": now["date"],
        "fetchedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "points": [{"d": d, "v": points[d]} for d in sorted(points)],
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("已写入 scfi.json，共 %d 个数据点" % len(out["points"]))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("抓取失败：%s" % e)
        sys.exit(1)
