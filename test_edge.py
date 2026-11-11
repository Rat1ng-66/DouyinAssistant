
from datetime import datetime

from playwright.sync_api import sync_playwright

from browser_manager import PROFILE_DIR

PROFILE_DIR.mkdir(parents=True, exist_ok=True)

print("=" * 50)
print("Edge 持久化测试")
print("配置目录：", PROFILE_DIR)
print("=" * 50)


def check_cookie_files():
    print("\n开始检查 Cookie 文件...")

    possible_files = [
        PROFILE_DIR / "Default" / "Network" / "Cookies",
        PROFILE_DIR / "Default" / "Cookies",
    ]

    found = False

    for file in possible_files:
        if file.exists():
            found = True
            stat = file.stat()

            print("发现 Cookie 文件：", file)
            print("文件大小：", stat.st_size, "bytes")
            print(
                "最后修改时间：",
                datetime.fromtimestamp(
                    stat.st_mtime
                )
            )

    if not found:
        print("暂未发现 Cookie 数据库，请检查浏览器配置目录。")


with sync_playwright() as p:

    context = p.chromium.launch_persistent_context(
        user_data_dir=str(PROFILE_DIR),
        channel="msedge",
        headless=False,
        viewport={"width": 1366, "height": 768}
    )

    try:
        page = (
            context.pages[0]
            if context.pages
            else context.new_page()
        )

        page.goto(
            "https://live.douyin.com/",
            wait_until="domcontentloaded",
            timeout=60000
        )

        print("\nEdge 已启动！")
        print("请手动登录抖音。")
        print("登录成功后，不要直接强制关闭 Edge。")

        input("\n登录确认完成后，回到 CMD 按回车退出...")

    finally:
        print("\n正在正常关闭 Edge...")
        context.close()
        print("Edge 已关闭。")

check_cookie_files()

print("\n测试结束。")
input("按回车退出程序...")