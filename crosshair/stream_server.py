"""Optional local page for OBS / Streamlabs browser sources: crosshair preview + share code.
Bound to 127.0.0.1 only; off by default; nothing leaves this PC."""
import html
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PAGE = """<!doctype html><html><head><meta charset="utf-8"><title>Nullpoint</title>
<style>html,body{margin:0;background:transparent;color:#fff;font:600 22px Consolas,monospace}
.card{display:inline-flex;align-items:center;gap:16px;padding:12px 16px;background:rgba(0,0,0,.75);
border:1px solid #333;border-radius:6px}img{image-rendering:pixelated;width:96px;height:96px}
small{display:block;color:#aaa;font-size:14px}</style></head><body><div class="card">
<img id="x" src="/crosshair.png"><div><small>NULLPOINT</small><span id="c">%CODE%</span></div></div>
<script>let v=-1;setInterval(async()=>{try{const s=await(await fetch('/state.json',{cache:'no-store'})).json();
if(s.version!==v){v=s.version;document.getElementById('c').textContent=s.code;
document.getElementById('x').src='/crosshair.png?v='+v}}catch(e){}},1000)</script></body></html>"""


class StreamServer:
    def __init__(self):
        self.state = {"version": 0, "code": "", "png": b""}
        self.lock = threading.Lock()
        self.httpd = None

    def publish(self, code, png):
        with self.lock:
            self.state = {"version": self.state["version"] + 1, "code": code, "png": png}

    def start(self, port):
        self.stop()
        server = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                with server.lock:
                    st = dict(server.state)
                path = self.path.split("?")[0]
                if path == "/":
                    body, kind = PAGE.replace("%CODE%", html.escape(st["code"])).encode(), "text/html; charset=utf-8"
                elif path == "/state.json":
                    body, kind = json.dumps({"version": st["version"], "code": st["code"]}).encode(), "application/json"
                elif path == "/crosshair.png":
                    body, kind = st["png"], "image/png"
                else:
                    self.send_error(404)
                    return
                self.send_response(200)
                self.send_header("Content-Type", kind)
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *a):
                pass

        self.httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)  # loopback only
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def stop(self):
        if self.httpd:
            self.httpd.shutdown()
            self.httpd.server_close()
            self.httpd = None
