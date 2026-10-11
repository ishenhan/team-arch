#!/usr/bin/env python3
"""
sentinel.py — SPM 哨兵示例（精简版）

这是示例代码，不是生产级实现。按你自己的平台改：
  - 改 LOBBY_STREAM_URL / TOKEN 为你团队的实际地址和凭据
  - 改 WATCH_RULES 为你团队成员的代号和关键词
  - 改 DOORBELL_PATH 为 hook 能看到的路径
  - 游标文件 sentinel_seen.txt 按需改位置

设计要点（对应 P-01 协议）：
  1. 只做纯字符串规则匹配，零 LLM —— 轻量、快速、不会编造
  2. 命中只写 doorbell.signal（时间戳），不写消息内容 —— 门铃只报"有事"
  3. 用本批条目 time 的最大值推进游标，不用 server_time —— 避免跳过同批消息
  4. 异常（断连）时退出，由外部 supervisor 重拉 —— 本体不依赖哨兵传信

依赖：仅标准库（urllib, json, time）。Python 3.8+。
"""

import json
import time
import urllib.request
import urllib.parse

# ============ 按自己平台改这里 ============
LOBBY_STREAM_URL = "https://YOUR-CASTLE-HOST/api/v1/stream"  # 改：你团队 lobby 的 stream 地址
TOKEN = "YOUR-SENTRY-TOKEN"                                   # 改：哨兵的只读 token（只读即可）
DOORBELL_PATH = "/tmp/doorbell.signal"                        # 改：hook 能检测到的路径
SEEN_PATH = "/tmp/sentinel_seen.txt"                          # 改：哨兵游标文件位置
POLL_WAIT = 10        # 长轮询秒数（上限 90），改：按需调整
ERROR_SLEEP = 5       # 出错后等待秒数再重试
# ==========================================

# 哨兵规则：纯字符串匹配，零 LLM。按团队成员改。
#  - "mentions": 成员代号列表，消息含 @代号 则命中
#  - "topics": 关键词列表，消息含关键词则命中
WATCH_RULES = {
    "mentions": ["@agent-a", "@agent-b", "@all"],
    "topics": ["deploy", "notice", "task"],  # 改：你团队的任务关键词
}


def load_seen():
    """读哨兵游标（上次处理到的消息时间）。"""
    try:
        with open(SEEN_PATH) as f:
            return f.read().strip()
    except FileNotFoundError:
        return "1970-01-01T00:00:00+00:00"


def save_seen(ts):
    """写哨兵游标。"""
    with open(SEEN_PATH, "w") as f:
        f.write(ts)


def ring_doorbell():
    """按门铃：只写时间戳，不写内容。"""
    with open(DOORBELL_PATH, "w") as f:
        f.write(time.strftime("%Y-%m-%dT%H:%M:%S%z"))


def hit_rules(msg_text):
    """规则过滤：命中任一条件即返回 True。纯字符串匹配，不调 LLM。"""
    text = msg_text or ""
    for m in WATCH_RULES["mentions"]:
        if m in text:
            return True
    for t in WATCH_RULES["topics"]:
        if t in text:
            return True
    return False


def poll_once(since):
    """拉一轮 stream。返回 (items, server_time)。"""
    url = LOBBY_STREAM_URL + "?" + urllib.parse.urlencode(
        {"since": since, "wait": POLL_WAIT}
    )
    req = urllib.request.Request(url, headers={"X-API-Token": TOKEN})
    with urllib.request.urlopen(req, timeout=POLL_WAIT + 20) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data.get("items", []), data.get("server_time", since)


def main():
    seen = load_seen()
    while True:
        try:
            items, server_time = poll_once(seen)
            max_time = seen
            for item in items:
                # 注意：正文在 msg 键，不在 content
                if hit_rules(item.get("msg", "")):
                    ring_doorbell()  # 只按铃，不传内容
                    break            # 一轮按一次铃就够了
                t = item.get("time", "")
                if t > max_time:
                    max_time = t
            # 用本批条目 time 的最大值推进游标（不用 server_time，避免跳过同批消息）
            if max_time != seen:
                seen = max_time
                save_seen(seen)
        except Exception as e:  # 断连等异常：记一句，等几秒，重试
            print(f"[sentinel] error: {e}, retry in {ERROR_SLEEP}s")
            time.sleep(ERROR_SLEEP)


if __name__ == "__main__":
    main()
