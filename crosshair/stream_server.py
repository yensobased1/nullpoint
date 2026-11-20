"""Optional local page for OBS / Streamlabs browser sources: crosshair preview, share code, name, QR.

Locked down on purpose: off by default, bound to 127.0.0.1 only, every URL needs the random token
(http://127.0.0.1:<port>/<token>/), the Host header must be 127.0.0.1 / localhost (blocks DNS rebinding),
GET only (other methods get 501 from the base class), no CORS headers, read-only data, nothing leaves this PC.
"""
import hmac
import html
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

THEMES = ("dark", "light", "transparent")
POSITIONS = ("top-left", "top-right", "bottom-left", "bottom-right", "center")
CSP = ("default-src 'none'; img-src 'self'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; "
       "connect-src 'self'; base-uri 'none'; form-action 'none'")

PAGE = """<!doctype html><html><head><meta charset="utf-8"><title>Nullpoint</title>
<style>html,body{margin:0;height:100%;background:transparent;font:600 22px Consolas,monospace}
body{display:flex;padding:16px;box-sizing:border-box}
.card{display:inline-flex;align-items:center;gap:16px;padding:12px 16px;border-radius:6px;height:fit-content}
.dark{background:rgba(0,0,0,.75);color:#fff;border:1px solid #333}.light{background:#fff;color:#000;border:1px solid #ccc}
.transparent{background:none;color:#fff;text-shadow:0 0 3px #000}
img{image-rendering:pixelated}small{display:block;opacity:.65;font-size:14px}#c{word-break:break-all;max-width:420px}
.top-left{align-items:flex-start;justify-content:flex-start}.top-right{align-items:flex-start;justify-content:flex-end}
.bottom-left{align-items:flex-end;justify-content:flex-start}.bottom-right{align-items:flex-end;justify-content:flex-end}
.center{align-items:center;justify-content:center}</style></head><body class="%POS%"><div id="k" class="card %THEME%">
<img id="x" src="crosshair.png" alt=""><div><small id="n">NULLPOINT</small><span id="c">%CODE%</span></div>
<img id="q" src="" alt="" style="display:none;width:96px;height:96px"></div>
<script>let v=-1;const $=i=>document.getElementById(i);setInterval(async()=>{try{
const s=await(await fetch('state.json',{cache:'no-store'})).json();if(s.version===v)return;v=s.version;const o=s.options;
document.body.className=o.pos;$('k').className='card '+o.theme;$('x').src='crosshair.png?v='+v;
$('x').style.width=$('x').style.height=o.size+'px';$('c').textContent=o.code?s.code:'';$('c').style.display=o.code?'':'none';
$('n').textContent=o.name?s.name:'NULLPOINT';$('q').style.display=o.qr?'':'none';if(o.qr)$('q').src='qr.png?v='+v;
}catch(e){}},1000)</script></body></html>"""


class StreamServer:
    def __init__(self):
        self.state = {"version": 0, "code": "", "png": b"", "qr": b"", "name": "",
                      "options": {"theme": "dark", "pos": "top-left", "size": 96, "code": True, "qr": False,
                                  "name": True}}
        self.lock = threading.Lock()
        self.httpd = None
        self.token = ""  # nosec B105 - not a password: set by start() to the page's random URL token

    def publish(self, code, png, name="", qr=b"", options=None):
        with self.lock:
            st = self.state
            self.state = {"version": st["version"] + 1, "code": code, "png": png, "qr": qr, "name": name[:60],
                          "options": dict(options or st["options"])}

    def start(self, port, token):
        self.stop()
        server, self.token = self, token

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                # DNS rebinding: a web page can point its own name at 127.0.0.1, but it can't fake the Host header.
                if self.headers.get("Host", "") not in server.hosts or len(self.path) > 200:
                    self.send_error(403)
                    return
                parts = self.path.split("?")[0].split("/")
                if len(parts) != 3 or parts[0] != "" or not hmac.compare_digest(parts[1], server.token):
                    self.send_error(404)
                    return
                with server.lock:
                    st = dict(server.state)
                name = parts[2]
                o = st["options"]
                if name == "":
                    page = (PAGE.replace("%CODE%", html.escape(st["code"]) if o["code"] else "")
                            .replace("%POS%", o["pos"]).replace("%THEME%", o["theme"]))
                    body, kind = page.encode(), "text/html; charset=utf-8"
                elif name == "state.json":
                    body = json.dumps({"version": st["version"], "code": st["code"], "name": st["name"],
                                       "options": o}).encode()
                    kind = "application/json"
                elif name == "crosshair.png":
                    body, kind = st["png"], "image/png"
                elif name == "qr.png" and o["qr"]:
                    body, kind = st["qr"], "image/png"
                else:
                    self.send_error(404)
                    return
                self.send_response(200)
                self.send_header("Content-Type", kind)
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("Content-Security-Policy", CSP)
                self.send_header("Referrer-Policy", "no-referrer")
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *a):
                pass

        self.httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)  # loopback only
        port = self.httpd.server_address[1]
        self.hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def stop(self):
        if self.httpd:
            self.httpd.shutdown()
            self.httpd.server_close()
            self.httpd = None
