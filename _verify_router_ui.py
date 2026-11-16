"""UI 验收：路由器上线后，前端有没有正确显示「走的是哪条路」。

只测两件事：
  1. 每条路走完，气泡下面那排小标签显示得对不对
  2. 控制台没有 JS 异常

⚠️ 只测 SSE 不够 —— 之前有个 `m is not defined`，
每一帧数据都是对的，但页面上什么也没渲染出来，只有打开浏览器才看得见。
"""
import base64
import json
import subprocess
import sys
import time
import urllib.request

import websocket

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
PORT = 9242
OUT = r"D:\Ai\Langchain\mycooker\_shots"
URL = "http://127.0.0.1:8002/"

# (问题, 期望标签里出现的字)
CASES = [
    ("你好呀，今天心情不错", "闲聊"),
    ("糖醋汁的番茄酱和糖是什么比例？", "RAG"),
]


class CDP:
    def __init__(self, ws_url):
        self.ws = websocket.create_connection(ws_url, timeout=300)
        self.seq = 0
        self.console, self.errors = [], []

    def send(self, method, **params):
        self.seq += 1
        self.ws.send(json.dumps({"id": self.seq, "method": method, "params": params}))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get("id") == self.seq:
                if "error" in msg:
                    raise RuntimeError(f"{method}: {msg['error']}")
                return msg.get("result", {})
            ev = msg.get("method")
            if ev == "Runtime.consoleAPICalled":
                p = msg.get("params", {})
                txt = " ".join(str(a.get("value", "")) for a in p.get("args", []))
                self.console.append((p.get("type"), txt))
            elif ev == "Runtime.exceptionThrown":
                d = msg.get("params", {}).get("exceptionDetails", {})
                self.errors.append(str(d.get("text", "")) + " " +
                                   str(d.get("exception", {}).get("description", "")))

    def ev(self, expr):
        return self.send("Runtime.evaluate", expression=expr,
                         returnByValue=True).get("result", {}).get("value")

    def shot(self, path):
        r = self.send("Page.captureScreenshot", format="png")
        open(path, "wb").write(base64.b64decode(r["data"]))


STATE_JS = """(() => {
  const s = document.querySelector('#btnSend');
  const metas = document.querySelectorAll('.msg.ai .agentmeta');
  const last = metas.length ? metas[metas.length - 1] : null;
  const bubbles = document.querySelectorAll('.msg.ai .bubble');
  return {
    streaming: s ? s.classList.contains('stop') : null,
    metas: metas.length,
    meta: last && !last.hidden ? last.textContent.trim() : null,
    meta_title: last ? (last.title || '') : '',
    textlen: bubbles.length ? bubbles[bubbles.length-1].textContent.length : 0,
    srcs: document.querySelectorAll('.src').length,
  };
})()"""


def main():
    prof = r"C:\Users\谢开然\AppData\Local\Temp\chrome-router-ui"
    proc = subprocess.Popen(
        [CHROME, "--headless=new", "--disable-gpu", "--no-sandbox", "--hide-scrollbars",
         f"--remote-debugging-port={PORT}", f"--user-data-dir={prof}",
         "--window-size=1440,940", "about:blank"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    pages = None
    for _ in range(40):
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json", timeout=5) as r:
                pages = [t for t in json.loads(r.read()) if t["type"] == "page"]
            if pages:
                break
        except Exception:
            pass
        time.sleep(0.4)

    if not pages:
        print("  ✘ Chrome 起不来")
        return 1

    c = CDP(pages[0]["webSocketDebuggerUrl"])
    c.send("Page.enable")
    c.send("Runtime.enable")
    c.send("Emulation.setDeviceMetricsOverride", width=1440, height=940,
           deviceScaleFactor=1, mobile=False)
    c.send("Page.navigate", url=URL)
    time.sleep(4)

    print("=" * 78)
    print("路由 UI 验收")
    print("=" * 78)
    print(f"  页面标题 : {c.ev('document.title')}")
    print(f"  状态     : {c.ev('document.querySelector(\"#statusTxt\").textContent')}")
    print()

    bad = 0
    for i, (q, want) in enumerate(CASES, 1):
        print(f"[{i}] {q}")
        c.ev(f"(()=>{{const i=document.querySelector('#input');i.value={json.dumps(q)};"
             "i.dispatchEvent(new Event('input'));return 1})()")
        time.sleep(0.3)
        c.ev("document.querySelector('#btnSend').click()")

        st = {}
        for _ in range(150):          # 最多等 120 秒（网络不稳时是真的慢）
            time.sleep(0.8)
            st = c.ev(STATE_JS) or {}
            if not st.get("streaming") and st.get("textlen", 0) > 20:
                break

        meta = st.get("meta") or ""
        hit = want in meta
        if not hit:
            bad += 1
        print(f"    标签   : {meta or '（没渲染）'}  {'✔' if hit else '✘ 期望含「' + want + '」'}")
        print(f"    悬浮   : {st.get('meta_title') or '（无）'}")
        print(f"    正文   : {st.get('textlen')} 字   来源 {st.get('srcs')} 条")
        print()

    c.shot(rf"{OUT}\router-ui.png")
    print(f"[截图] {OUT}\\router-ui.png")
    print()
    print("=" * 78)
    print(f"  标签正确 : {len(CASES) - bad}/{len(CASES)}")
    print(f"  JS 异常  : {len(c.errors)}")
    for e in c.errors[:5]:
        print(f"    ! {e[:200]}")
    print("=" * 78)

    try:
        proc.terminate()
    except Exception:
        pass
    return 0 if bad == 0 and not c.errors else 1


if __name__ == "__main__":
    sys.exit(main())