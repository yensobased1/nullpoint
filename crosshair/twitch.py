"""Opt-in Twitch chat command: '!crosshair' in YOUR channel -> the bot replies with your current share code.

Twitch IRC over TLS (irc.chat.twitch.tv:6697, certificate checked). The token comes from Windows Credential Manager.
Chat is untrusted: lines are length-limited, only the exact command is reacted to, chat text is never echoed back,
and replies have a cooldown.
"""
import re
import socket
import ssl
import threading
import time

HOST, PORT = "irc.chat.twitch.tv", 6697
CHANNEL_RE = re.compile(r"[a-z0-9_]{3,25}")
TOKEN_RE = re.compile(r"[a-z0-9]{20,64}")
PRIVMSG_RE = re.compile(r"^(?:@\S+ )?:\w+!\w+@[\w.]+ PRIVMSG #(\w+) :(.*)$")
MAX_LINE = 2048
REPO = "github.com/yensobased1/nullpoint"


def clean_token(token):
    t = (token or "").strip().lower()
    t = t[6:] if t.startswith("oauth:") else t
    return t if TOKEN_RE.fullmatch(t) else ""


def reply_text(code):
    """One safe line: our own share code only (no CR/LF, under Twitch's 500 character limit)."""
    code = re.sub(r"[^\w;:,.%\-]", "", code)[:400]
    return f"Nullpoint crosshair: {code} | get it at {REPO}"


def command_in(line, channel):
    """True when a chat line is exactly '!crosshair' in our channel."""
    m = PRIVMSG_RE.match(line[:MAX_LINE])
    return bool(m) and m.group(1).lower() == channel and m.group(2).strip().lower() == "!crosshair"


class TwitchBot:
    def __init__(self, on_status=lambda text: None):
        self.code = ""  # set by the app whenever the crosshair changes
        self.on_status = on_status
        self.cooldown = 30
        self._stop = threading.Event()
        self.thread = None

    def start(self, channel, token, cooldown=30):
        self.stop()
        channel, token = channel.lower().strip(), clean_token(token)
        if not CHANNEL_RE.fullmatch(channel) or not token:
            self.on_status("Twitch: channel name or token missing / invalid.")
            return
        self.cooldown = max(5, int(cooldown))
        self._stop = threading.Event()
        self.thread = threading.Thread(target=self._loop, args=(channel, token, self._stop), daemon=True)
        self.thread.start()

    def stop(self):
        self._stop.set()

    def _loop(self, channel, token, stop):
        wait = 5
        while not stop.is_set():
            try:
                self._session(channel, token, stop)
                wait = 5
            except PermissionError:
                self.on_status("Twitch: login failed - check the token (needs chat:read and chat:edit).")
                return
            except (OSError, ssl.SSLError):
                self.on_status(f"Twitch: disconnected, retrying in {wait} s.")
            stop.wait(wait)
            wait = min(wait * 2, 120)
        self.on_status("Twitch: off.")

    def _session(self, channel, token, stop):
        ctx = ssl.create_default_context()  # verifies the certificate and host name
        with socket.create_connection((HOST, PORT), timeout=10) as raw, ctx.wrap_socket(raw, server_hostname=HOST) as s:
            s.settimeout(1.0)
            send = lambda line: s.sendall((line + "\r\n").encode("utf-8"))
            send(f"PASS oauth:{token}")
            send(f"NICK {channel}")
            send(f"JOIN #{channel}")
            buf, last, last_rx = b"", 0.0, time.monotonic()
            while not stop.is_set():
                try:
                    data = s.recv(4096)
                except socket.timeout:
                    if time.monotonic() - last_rx > 360:  # Twitch pings every ~5 minutes
                        raise OSError("timeout")
                    continue
                if not data:
                    raise OSError("closed")
                last_rx = time.monotonic()
                buf += data
                if len(buf) > 16384 and b"\r\n" not in buf:
                    buf = b""  # one absurdly long line: drop it
                *lines, buf = buf.split(b"\r\n")
                for raw_line in lines:
                    line = raw_line[:MAX_LINE].decode("utf-8", "replace")
                    if line.startswith("PING"):
                        send("PONG :tmi.twitch.tv")
                    elif "Login authentication failed" in line or "Improperly formatted auth" in line:
                        raise PermissionError
                    elif " 001 " in line:
                        self.on_status(f"Twitch: connected to #{channel}.")
                    elif command_in(line, channel) and self.code and time.monotonic() - last >= self.cooldown:
                        last = time.monotonic()
                        send(f"PRIVMSG #{channel} :{reply_text(self.code)}")
