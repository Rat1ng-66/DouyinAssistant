# -*- coding: utf-8 -*-
"""DouyinAssistant V0.4.5 — dual-platform browser worker.

Douyin: contenteditable editor. Huya: #pub_msg_input textarea.
A 'submitted' result denotes an Enter attempt, not server delivery.
"""
import json
import queue
import re
import time
from pathlib import Path
from urllib.parse import urlparse

from PySide6.QtCore import QThread, Signal
from playwright.sync_api import sync_playwright, Error as PlaywrightError

from paths import app_data_dir


PROFILE_DIR = app_data_dir() / "EdgeProfile"

HOME_URL = "https://live.douyin.com/"
MIN_INTERVAL = 1
MAX_INTERVAL = 600
MAX_MESSAGES = 20
MAX_DURATION_SECONDS = 365 * 24 * 60 * 60
LIVE_CHECK_INTERVAL = 15.0
UNKNOWN_STOP_SECONDS = 60.0


def detect_platform(url):
    parsed = urlparse(str(url).strip())
    hostname = (parsed.hostname or "").lower()

    if parsed.scheme != "https":
        raise ValueError("请使用 HTTPS 直播间地址")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("直播间地址格式不正确")
    try:
        if parsed.port not in (None, 443):
            raise ValueError("直播间地址端口不受支持")
    except ValueError as exc:
        raise ValueError("直播间地址端口不正确") from exc

    if hostname == "live.douyin.com":
        platform = "douyin"
    elif hostname in ("huya.com", "www.huya.com"):
        platform = "huya"
    else:
        raise ValueError("目前仅支持抖音和虎牙直播间地址")

    if not parsed.path.strip("/"):
        raise ValueError("请输入具体直播间地址，而非平台首页")

    return platform


def validate_live_url(url):
    url = str(url).strip()
    if url.startswith("live.douyin.com/"):
        url = "https://" + url
    elif url.startswith(("huya.com/", "www.huya.com/")):
        url = "https://" + url
    detect_platform(url)
    return url


def normalize_messages(messages):
    result = []
    for message in messages:
        if not isinstance(message, str):
            continue
        if message.strip():
            result.append(message)
    if not result:
        raise ValueError("至少填写一条非空弹幕")
    if len(result) > 100:
        raise ValueError("最多配置100条弹幕")
    return result


class BrowserManager(QThread):
    log_signal = Signal(str)
    status_signal = Signal(str)
    browser_ready = Signal()
    room_info_signal = Signal(dict)
    error_signal = Signal(str)
    task_signal = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.commands = queue.Queue()
        self.room_url = ""

    def log(self, message):
        self.log_signal.emit(str(message))

    def open_live_room(self, url):
        self.commands.put(("navigate", url))

    def refresh_room(self):
        self.commands.put(("refresh", None))

    def start_messages(
        self, messages, interval, limit,
        mode="count", duration_seconds=300
    ):
        self.commands.put((
            "start_messages",
            {
                "messages": list(messages),
                "interval": interval,
                "limit": limit,
                "mode": mode,
                "duration_seconds": duration_seconds,
            },
        ))

    def pause_messages(self):
        self.commands.put(("pause", None))

    def resume_messages(self):
        self.commands.put(("resume", None))

    def stop_messages(self):
        self.commands.put(("stop_messages", None))

    def stop_browser(self):
        self.commands.put(("stop_browser", None))

    def emit_task(self, status, attempted=0, confirmed=0, message=""):
        # Field 'confirmed' retained for compatibility with older main.py.
        # It counts Enter submission attempts with no Playwright exception,
        # NOT chat messages verified as delivered by the platform.
        self.task_signal.emit({
            "status": status,
            "attempted": attempted,
            "confirmed": confirmed,
            "message": message,
        })

    def collect_room_info(self, page):
        title = page.title() or ""
        match = re.match(r"^(.+?)的抖音直播间\s*[-|｜]", title)
        anchor = match.group(1).strip() if match else "未识别"

        platform = "未知"
        try:
            platform = detect_platform(page.url)
        except ValueError:
            pass

        return {
            "anchor": anchor,
            "title": title or "未识别",
            "live_status": "无法确认",
            "login_status": "未单独验证",
            "url": page.url,
            "platform": platform,
            "update_time": time.strftime("%H:%M:%S"),
        }



    def check_stream_state(self, page):
        """
        保守地检查主播是否仍在直播。
        ended: 明确的停播提示、退出直播间页面
        live: 可见视频正在播放，或播放器内明确显示“直播中”
        unknown: 不能判断（例如网络故障、播放器未就绪、DOM 改版）

        注意：这是前端启发式检测，不是平台官方开播状态接口。
        """
        if page is None or page.is_closed():
            return "ended", "直播页面已关闭"

        try:
            platform = detect_platform(page.url)
        except ValueError:
            return "ended", "已离开支持的直播间页面"

        try:
            findings = []
            frames = [page.main_frame] + [
                frame for frame in page.frames if frame != page.main_frame
            ]
            for frame in frames:
                try:
                    data = frame.evaluate(r"""
                    () => {
                        const visible = el => {
                            const r = el.getBoundingClientRect();
                            const s = getComputedStyle(el);
                            return r.width > 0 && r.height > 0
                                && s.visibility !== "hidden"
                                && s.display !== "none";
                        };
                        const videoPlaying = [...document.querySelectorAll("video")]
                            .some(v => visible(v) && !v.paused && !v.ended
                                && v.readyState >= 2);
                        const playerRoots = [
                            ...document.querySelectorAll(
                                '[class*="player"], [id*="player"], ' +
                                '[class*="Player"], [id*="Player"], ' +
                                '[class*="video-container"], [id*="video-container"]'
                            )
                        ].filter(visible).slice(0, 30);
                        const textSelectors = [
                            "span", "div", "p", "strong", "h2", "h3"
                        ].join(",");
                        const endedPattern =
                            /^(?:本场)?直播(?:已)?结束(?:了|啦)?$|^主播(?:已)?下播(?:了)?$|^主播暂未开播$|^暂未开播$|^直播已关闭$/;
                        const livePattern = /^直播中$/;
                        let endedText = "";
                        let liveLabel = false;
                        for (const root of playerRoots) {
                            const nodes = [root, ...root.querySelectorAll(textSelectors)];
                            for (const el of nodes.slice(0, 300)) {
                                if (!visible(el) || el.children.length > 0) continue;
                                const t = (el.textContent || "").trim().replace(/\s+/g, "");
                                if (t.length > 24) continue;
                                if (endedPattern.test(t)) endedText = t;
                                if (livePattern.test(t)) liveLabel = true;
                                if (endedText) break;
                            }
                            if (endedText) break;
                        }
                        return {endedText, videoPlaying, liveLabel};
                    }
                    """)
                    findings.append(data)
                except PlaywrightError:
                    continue

            for item in findings:
                if item.get("endedText"):
                    return "ended", f"{platform}播放器提示：{item['endedText']}"

            if any(item.get("videoPlaying") for item in findings):
                return "live", f"{platform}播放器视频正在播放"

            if any(item.get("liveLabel") for item in findings):
                return "live", f"{platform}播放器显示直播中"

            return "unknown", (
                f"{platform}未取得可靠的直播状态；"
                "直播间可能停播、网络异常或播放器结构发生变化"
            )
        except PlaywrightError as exc:
            return "unknown", f"直播状态检测异常：{str(exc)[:120]}"

    def find_message_input(self, page):
        """按平台定位编辑器。抖音优先主文档，虎牙使用已验证的 textarea。"""
        try:
            platform = detect_platform(page.url)
        except ValueError:
            self.log(f"无法识别当前直播间地址：{page.url}")
            return None

        if platform == "douyin":
            selectors = [
                'div.editor-kit-container[contenteditable="true"]',
                '.zone-container.editor-kit-container[contenteditable]',
                'div[contenteditable="true"].notranslate',
            ]
        else:
            selectors = [
                'textarea#pub_msg_input',
                '#pub_msg_input',
            ]

        # 同一页面可能有其他 iframe。优先主文档，减少误匹配。
        frames = [page.main_frame] + [
            frame for frame in page.frames if frame != page.main_frame
        ]

        for frame in frames:
            for selector in selectors:
                try:
                    items = frame.locator(selector)
                    for index in range(min(items.count(), 10)):
                        editor = items.nth(index)
                        if (editor.is_visible()
                                and editor.is_enabled()
                                and editor.is_editable()):
                            self.log(
                                f"已定位{platform}弹幕编辑器："
                                f"{selector}"
                            )
                            return editor
                except PlaywrightError:
                    continue

        self.log(
            f"{platform}编辑器未找到。"
            "请确认账号已登录、直播间已加载且聊天区域可用。"
        )
        return None

    def inspect_huya_chat(self, page):
        """Read-only DOM metadata; never inspect input values, Cookies or tokens."""
        try:
            if detect_platform(page.url) != "huya":
                return []
        except ValueError:
            return []

        return page.evaluate(r"""
            () => {
              const selector = 'textarea, input, [contenteditable], [role="textbox"]';
              return [...document.querySelectorAll(selector)]
                .filter(el => {
                  const r = el.getBoundingClientRect();
                  const s = getComputedStyle(el);
                  return r.width > 0 && r.height > 0 &&
                         s.display !== 'none' && s.visibility !== 'hidden';
                })
                .slice(0, 30)
                .map(el => ({
                  tag: el.tagName,
                  id: el.id || '',
                  className: String(el.className || '').slice(0, 160),
                  placeholder: (el.getAttribute('placeholder') || '').slice(0, 100),
                  role: el.getAttribute('role') || '',
                  contenteditable: el.getAttribute('contenteditable') || ''
                }));
            }
        """)

    def send_one_message(self, page, message):
        """每条消息只执行一次 Enter；不把提交操作等同于平台送达。"""
        if page.is_closed():
            return "blocked", "直播页面已关闭"

        try:
            platform = detect_platform(page.url)
        except ValueError:
            return "blocked", "当前页面不是支持的直播间"

        if not isinstance(message, str) or not message.strip():
            return "blocked", "弹幕内容为空"

        editor = self.find_message_input(page)
        if editor is None:
            return "blocked", f"未找到{platform}弹幕输入框"

        try:
            # 抖音是 contenteditable 富文本 DIV；虎牙是 textarea。
            # 保留各自的编辑器定位，避免修改虎牙时影响抖音。
            editor.click(timeout=5000)
            editor.fill(message, timeout=5000)
            self.log(f"{platform}弹幕已填写，准备执行 Enter")

            # 不做严格文本相等比较，兼容抖音编辑器的零宽字符。
            # press 会在目标编辑器上触发按键。
            editor.press("Enter", timeout=5000)
            self.log(f"{platform}已执行 Enter，未验证平台接收结果")

            # 抖音曾出现按下 Enter 后文字留在输入框的情况。
            # 这里只记录诊断，不重复按键，以免导致重复发送。
            if platform == "douyin":
                try:
                    page.wait_for_timeout(350)
                    raw = editor.evaluate(
                        'el => el.innerText || el.textContent || ""'
                    )
                    # 仅忽略编辑器可能插入的零宽格式字符
                    remaining = str(raw)
                    for char in ("\u200b", "\u200c", "\u200d", "\ufeff"):
                        remaining = remaining.replace(char, "")
                    if remaining.strip():
                        self.log(
                            "抖音：Enter 后编辑器仍有内容，"
                            "请观察是否已上屏；本次不自动重发"
                        )
                        return (
                            "uncertain",
                            "Enter 后编辑器仍有内容，已停止后续发送"
                        )
                except PlaywrightError as exc:
                    self.log(f"抖音发送后检查不可用：{exc}")
                    return "uncertain", "无法检查抖音编辑器状态"

            return "submitted", "已执行 Enter 提交操作"

        except PlaywrightError as exc:
            return "uncertain", f"{platform}页面操作异常：{exc}"

    def run(self):
        context = None
        page = None

        task = None
        next_send_at = float("inf")
        attempted = 0
        submitted = 0
        index = 0
        last_refresh = 0.0
        last_live_check = 0.0

        self.status_signal.emit("启动中")

        try:
            PROFILE_DIR.mkdir(parents=True, exist_ok=True)
            self.log(f"浏览器配置目录：{PROFILE_DIR}")

            with sync_playwright() as playwright:
                context = playwright.chromium.launch_persistent_context(
                    user_data_dir=str(PROFILE_DIR),
                    channel="msedge",
                    headless=False,
                    chromium_sandbox=True,
                    viewport={"width": 1366, "height": 768},
                    timeout=60000,
                )

                page = context.pages[0] if context.pages else context.new_page()
                self.status_signal.emit("运行中")
                self.browser_ready.emit()
                self.log("Edge 启动成功")

                try:
                    page.goto(
                        HOME_URL,
                        wait_until="domcontentloaded",
                        timeout=30000,
                    )
                except PlaywrightError as exc:
                    self.log(f"打开首页提示：{exc}")

                while True:
                    try:
                        command, value = self.commands.get(timeout=0.2)
                    except queue.Empty:
                        command, value = None, None

                    if command == "stop_browser":
                        task = None
                        self.emit_task("stopped", attempted, submitted)
                        break

                    if command == "navigate":
                        task = None
                        last_live_check = 0.0
                        next_send_at = float("inf")
                        self.room_url = ""
                        self.emit_task("stopped", attempted, submitted)
                        try:
                            target = validate_live_url(value)
                            platform = detect_platform(target)

                            if page.is_closed():
                                page = context.new_page()

                            page.goto(
                                target,
                                wait_until="domcontentloaded",
                                timeout=30000,
                            )
                            self.room_url = target
                            self.log(f"已打开{('抖音' if platform == 'douyin' else '虎牙')}直播间：{target}")
                            self.room_info_signal.emit(self.collect_room_info(page))

                            if platform == "huya":
                                page.wait_for_timeout(1500)
                                try:
                                    controls = self.inspect_huya_chat(page)
                                    self.log(
                                        "虎牙输入区域诊断（只读）：\n"
                                        + json.dumps(controls, ensure_ascii=False, indent=2)
                                    )
                                    self.log("虎牙已启用独立输入框定位：textarea#pub_msg_input")
                                except PlaywrightError as exc:
                                    self.log(f"虎牙输入区域诊断暂不可用：{exc}")

                        except (ValueError, PlaywrightError) as exc:
                            self.log(f"连接直播间失败：{exc}")
                            self.error_signal.emit(str(exc))

                    if command == "refresh" and self.room_url and not page.is_closed():
                        try:
                            self.room_info_signal.emit(self.collect_room_info(page))
                        except PlaywrightError as exc:
                            self.log(f"读取信息失败：{exc}")

                    if command == "start_messages":
                        try:
                            if task is not None:
                                raise ValueError("已有任务正在运行")
                            if not self.room_url:
                                raise ValueError("请先连接直播间")
                            if page.is_closed():
                                raise ValueError("直播页面已关闭")
                            # 最多等待 10 秒，让直播间输入框初始化
                            editor = None

                            for _ in range(20):
                                editor = self.find_message_input(page)

                                if editor is not None:
                                    break

                                page.wait_for_timeout(500)

                            if editor is None:
                                raise ValueError(
                                    "等待 10 秒后仍未找到弹幕输入框"
                                )

                            messages = normalize_messages(value["messages"])
                            interval = int(value["interval"])
                            limit = int(value["limit"])
                            mode = value.get("mode", "count")
                            duration_seconds = int(
                                value.get("duration_seconds", 300)
                            )

                            if mode not in ("count", "duration"):
                                raise ValueError("未知发送任务模式")
                            if mode == "duration":
                                if not 60 <= duration_seconds <= MAX_DURATION_SECONDS:
                                    raise ValueError("运行时长必须为1分钟至365天")

                            if not MIN_INTERVAL <= interval <= MAX_INTERVAL:
                                raise ValueError("发送间隔必须为1～600秒")
                            if not 1 <= limit <= MAX_MESSAGES:
                                raise ValueError("发送上限必须为1～20条")

                            attempted = 0
                            submitted = 0
                            index = 0
                            next_send_at = time.monotonic()
                            task = {
                                "messages": messages,
                                "interval": interval,
                                "limit": limit,
                                "paused": False,
                                "remaining": 0.0,
                                "mode": mode,
                                "duration_seconds": duration_seconds,
                                "deadline": (
                                    time.monotonic() + duration_seconds
                                    if mode == "duration"
                                    else float("inf")
                                ),
                                "deadline_remaining": duration_seconds,
                                "last_live_state": None,
                                "unknown_since": None,
                            }
                            end_text = (
                                f"时长 {duration_seconds} 秒"
                                if mode == "duration"
                                else f"上限 {limit} 条"
                            )
                            self.log(
                                f"任务开始：{len(messages)} 条内容，"
                                f"间隔 {interval} 秒，{end_text}"
                            )
                            self.emit_task("running", attempted, submitted)

                        except (ValueError, TypeError, PlaywrightError) as exc:
                            task = None
                            next_send_at = float("inf")
                            self.log(f"任务启动失败：{exc}")
                            self.error_signal.emit(str(exc))
                            self.emit_task("stopped", attempted, submitted)

                    if command == "pause" and task and not task["paused"]:
                        task["remaining"] = max(0.0, next_send_at - time.monotonic())
                        if task["mode"] == "duration":
                            task["deadline_remaining"] = max(
                                0.0,
                                task["deadline"] - time.monotonic()
                            )
                        task["paused"] = True
                        self.log("弹幕任务已暂停")
                        self.emit_task("paused", attempted, submitted)

                    if command == "resume" and task and task["paused"]:
                        task["paused"] = False
                        last_live_check = 0.0  # 恢复后必须重新确认是否仍在直播
                        task["last_live_state"] = None
                        task["unknown_since"] = None
                        next_send_at = time.monotonic() + task["remaining"]
                        if task["mode"] == "duration":
                            task["deadline"] = (
                                time.monotonic() + task["deadline_remaining"]
                            )
                        self.log("弹幕任务已继续")
                        self.emit_task("running", attempted, submitted)

                    if command == "stop_messages" and task is not None:
                        task = None
                        next_send_at = float("inf")
                        self.log("弹幕任务已停止")
                        self.emit_task("stopped", attempted, submitted)

                    # 每15秒检查直播状态；如果不能确认在线，
                    # 停止发送动作。持续1分钟仍不明确则终止任务。
                    if (
                        task is not None
                        and not task["paused"]
                        and (
                            last_live_check == 0.0
                            or time.monotonic() - last_live_check
                            >= LIVE_CHECK_INTERVAL
                        )
                    ):
                        last_live_check = time.monotonic()
                        live_state, reason = self.check_stream_state(page)
                        previous_state = task["last_live_state"]
                        task["last_live_state"] = live_state

                        if live_state != previous_state:
                            self.log(f"直播状态：{live_state}，{reason}")

                        if live_state == "ended":
                            self.log("检测到停播或退出直播间，已停止发送任务")
                            task = None
                            next_send_at = float("inf")
                            self.emit_task(
                                "stopped", attempted, submitted,
                                "停播或直播间已退出"
                            )

                        elif live_state == "unknown":
                            if task["unknown_since"] is None:
                                task["unknown_since"] = time.monotonic()
                            elif (
                                time.monotonic() - task["unknown_since"]
                                >= UNKNOWN_STOP_SECONDS
                            ):
                                self.log(
                                    "直播状态持续无法确认，"
                                    "为防止停播后继续提交，任务已停止"
                                )
                                task = None
                                next_send_at = float("inf")
                                self.emit_task(
                                    "stopped", attempted, submitted,
                                    "直播状态无法确认"
                                )

                        else:
                            task["unknown_since"] = None

                    # 到达持续运行时长时，自动终止任务；
                    # 按时长模式不受20条上限限制。
                    if (
                        task is not None
                        and not task["paused"]
                        and task["mode"] == "duration"
                        and time.monotonic() >= task["deadline"]
                    ):
                        self.log("达到设定运行时长，任务自动结束")
                        task = None
                        next_send_at = float("inf")
                        self.emit_task(
                            "completed", attempted, submitted,
                            "达到设定运行时长"
                        )

                    if (
                        task is not None
                        and not task["paused"]
                        and task["last_live_state"] == "live"
                        and time.monotonic() >= next_send_at
                    ):
                        # 发送前再检查一次，避免在两次定时巡检之间停播。
                        pre_state, pre_reason = self.check_stream_state(page)
                        if pre_state != "live":
                            task["last_live_state"] = pre_state
                            last_live_check = 0.0
                            self.log(
                                "发送前直播状态未确认，"
                                f"已阻止本次提交：{pre_reason}"
                            )
                            if pre_state == "ended":
                                task = None
                                next_send_at = float("inf")
                                self.emit_task(
                                    "stopped", attempted, submitted,
                                    "直播已经结束"
                                )
                            else:
                                if task["unknown_since"] is None:
                                    task["unknown_since"] = time.monotonic()
                            continue

                        message = task["messages"][index % len(task["messages"])]
                        planned_at = next_send_at
                        result, detail = self.send_one_message(page, message)
                        attempted += 1

                        if result == "submitted":
                            submitted += 1
                            index += 1
                            self.log(
                                (
                                    f"[{attempted}/{task['limit']}] 已尝试提交：{detail}"
                                    if task["mode"] == "count"
                                    else f"[持续模式 第{attempted}次] 已尝试提交：{detail}"
                                )
                            )
                            self.emit_task("running", attempted, submitted)

                            if (
                                task["mode"] == "count"
                                and attempted >= task["limit"]
                            ):
                                self.log("达到发送上限，任务结束")
                                task = None
                                next_send_at = float("inf")
                                self.emit_task("completed", attempted, submitted)
                            else:
                                # Keep the requested cadence based on planned starts.
                                # Skip missed ticks instead of queueing catch-up sends.
                                now = time.monotonic()
                                candidate = planned_at + task["interval"]
                                if candidate <= now:
                                    candidate = now + task["interval"]
                                next_send_at = candidate
                        else:
                            self.log(f"提交结果不明确，任务停止：{detail}")
                            task = None
                            next_send_at = float("inf")
                            self.emit_task("stopped", attempted, submitted, detail)

                    now = time.monotonic()
                    if self.room_url and now - last_refresh >= 5:
                        last_refresh = now
                        try:
                            if page.is_closed():
                                self.room_url = ""
                                task = None
                                next_send_at = float("inf")
                                self.emit_task(
                                    "stopped",
                                    attempted,
                                    submitted,
                                    "浏览器页面已关闭",
                                )
                            else:
                                self.room_info_signal.emit(
                                    self.collect_room_info(page)
                                )
                        except PlaywrightError as exc:
                            self.log(f"页面检查异常：{exc}")

        except Exception as exc:
            self.log(f"浏览器运行异常：{exc}")
            self.error_signal.emit(str(exc))

        finally:
            self.status_signal.emit("关闭中")
            self.emit_task("stopped")
            if context is not None:
                try:
                    context.close()
                    self.log("Edge 已关闭")
                except PlaywrightError:
                    self.log("Edge 已提前关闭或连接断开")
            self.status_signal.emit("未启动")
            self.log("浏览器线程已结束")
