# 直播间弹幕助手

Windows 桌面程序，当前版本 V0.4.6。用本机已安装的 Microsoft Edge 打开抖音或虎牙直播间，按列表顺序发送事先写好的弹幕。

只支持这两个地址：

- `https://live.douyin.com/房间号`
- `https://www.huya.com/房间号`

## 使用

1. 点击「启动 Edge」，在打开的浏览器里登录对应平台。
2. 填入直播间地址，点击「连接直播间」。
3. 弹幕每行写一条，按顺序循环发送。最多 100 条。
4. 设置发送间隔（1–600 秒）。结束方式可以按条数（本次最多 1–20 条），或按时长（分钟、小时、天，最长 365 天）。暂停期间不计时。
5. 勾选使用确认，点击「开始发送」，在弹出窗口里再次确认。

发送过程中可以暂停、继续或停止。页面长时间无法确认仍在直播时，发送会停下来。界面上的「已执行提交」表示浏览器里按下了回车且没有报错，不代表平台一定已经把这条弹幕发出去。

右侧可以收藏直播间。双击一条收藏会把地址填进输入框。

## 源码运行

需要 Windows、Python 3.10 或更高版本，以及已经安装的 Microsoft Edge。

```powershell
python -m venv venv
.\venv\Scripts\pip install -r requirements.txt
.\venv\Scripts\python.exe main.py
```

源码运行时，弹幕配置、收藏和 Edge 登录数据保存在：

`%LOCALAPPDATA%\DouyinAssistant`

## 打包

```powershell
.\venv\Scripts\pyinstaller.exe --noconfirm "直播间弹幕助手.spec"
```

生成的程序在 `dist\直播间弹幕助手\直播间弹幕助手.exe`。拷走时要带上旁边的 `_internal` 文件夹。目标电脑需要安装 Edge，不需要安装 Python。

打包后的配置、收藏和登录数据放在 exe 旁边的 `data` 文件夹里，和源码运行的数据互不相通。换电脑时把整个文件夹一起复制。

`data` 里有登录状态。不要把这个文件夹发给别人，也不要提交到仓库。
