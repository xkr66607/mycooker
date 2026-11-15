"""UI 验收：Agent 模式下工具进度、执行摘要、引用、控制台无异常。"""
import base64
import json
import subprocess
import time
import urllib.request

import websocket

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
PORT = 9241
OUT = r"D:\Ai\Langchain\mycooker\_shots"
URL = "http://127.0.0.1:8002/"


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


def main():
    prof = r"C:\Users\谢开然\AppData\Local\Temp\chrome-agent-ui"
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

    c = CDP(pages[0]["webSocketDebuggerUrl"])
    c.send("Page.enable")
    c.send("Runtime.enable")
    c.send("Emulation.setDeviceMetricsOverride", width=1440, height=940,
           deviceScaleFactor=1, mobile=False)
    c.send("Page.navigate", url=URL)
    time.sleep(4)

    print("[1] 页面加载")
    print(f"    标题: {c.ev('document.title')}")
    print(f"    状态: {c.ev('document.querySelector(\"#statusTxt\").textContent')}")
    print(f"    模型: {c.ev('document.querySelector(\"#modelTag\").textContent')}")

    print("\n[2] 提问（多跳，会连续调工具）")
    q = "我想做红烧肉，按知识库的用量算，这一锅多少热量？一人份多少？"
    c.ev(f"(()=>{{const i=document.querySelector('#input');i.value={json.dumps(q)};"
         "i.dispatchEvent(new Event('input'));return 1})()")
    time.sleep(0.3)
    c.ev("document.querySelector('#btnSend').click()")

    saw_tool = False
    tooltexts = []
    st = {}
    for _ in range(120):
        time.sleep(0.8)
        st = c.ev("""(() => {
          const s = document.querySelector('#btnSend');
          const b = document.querySelectorAll('.msg.ai .bubble');
          const meta = document.querySelector('.msg.ai .agentmeta');
          const tb = document.querySelector('.thinkingbar');
          return { streaming: s.classList.contains('stop'),
                   len: b.length ? b[b.length-1].textContent.length : 0,
                   bar: tb ? tb.textContent.trim().slice(0,40) : null,
                   meta: meta && !meta.hidden ? meta.textContent.trim() : null,
                   cites: document.querySelectorAll('.bubble .cite').length,
                   srcs: document.querySelectorAll('.src').length };
        })()""")
        if st.get("bar"):
            saw_tool = True
            tooltexts.append(st["bar"])
        if not st.get("streaming") and st.get("len", 0) > 60:
            break

    print(f"    最终状态: {st}")
    print(f"    抓到工具进度提示: {saw_tool}")
    for t in dict.fromkeys(tooltexts):
        print(f"      · {t}")

    print("\n[3] 控制台")
    print(f"    异常: {len(c.errors)}")
    for e in c.errors[:3]:
        print(f"      ! {e[:180]}")
    bad = [x for x in c.console if x[0] in ("error", "warning")]
    print(f"    error/warning: {len(bad)}")
    for x in bad[:3]:
        print(f"      - {x[0]}: {x[1][:160]}")

    c.shot(f"{OUT}\\agent-01.png")
    print(f"\n    截图 -> {OUT}\\agent-01.png")
    proc.kill()
    print("\n完成")


if __name__ == "__main__":
    main()