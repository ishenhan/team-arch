#!/usr/bin/env bash
# doorbell-hook.sh — 门铃触发 hook 示例
#
# 这是示例代码，不是生产级实现。按你自己的平台改：
#   - 改 DOORBELL_PATH 为哨兵实际写的路径
#   - 改 WAKE_COMMAND 为叫醒你家 Main 本体的实际命令
#     （如：向任务队列写一条记录、发一个 HTTP 回调、touch 一个唤醒文件）
#
# 设计要点（对应 P-01 协议）：
#   1. hook 只检测门铃文件的时间戳，不读消息内容 —— 门铃只报"有事"
#   2. 检测到新信号就叫醒本体一次，重复信号幂等（本体自己去 stream 拉全量）
#   3. 纯 shell，无 LLM、无判断 —— cron/hook 里不许有 agent 逻辑
#
# 建议运行方式：每 60~90 秒跑一次（cron 或 supervisor 常驻均可）。

set -euo pipefail

# ============ 按自己平台改这里 ============
DOORBELL_PATH="/tmp/doorbell.signal"      # 改：哨兵写的门铃文件
LAST_SEEN_PATH="/tmp/doorbell_lastseen"   # 改：hook 自己的已处理水位
# ==========================================

# 叫醒本体：改成你团队的实际唤醒方式。
# 示例只是写一行日志，生产环境换成真实动作。
wake_main() {
    echo "[$(date -Is)] doorbell rang, waking main"
    # 改：下面换成你的唤醒命令，例如：
    #   curl -s -X POST http://127.0.0.1:9000/wake
    #   touch /tmp/wake_main.signal
}

last_seen=""
if [ -f "$LAST_SEEN_PATH" ]; then
    last_seen=$(cat "$LAST_SEEN_PATH")
fi

if [ ! -f "$DOORBELL_PATH" ]; then
    exit 0  # 门铃文件不存在，无事发生
fi

current=$(cat "$DOORBELL_PATH")
if [ "$current" != "$last_seen" ]; then
    wake_main
    echo "$current" > "$LAST_SEEN_PATH"
fi
