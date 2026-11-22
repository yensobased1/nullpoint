"""Lobby detection from a game's own text log, for games that also hide the Windows cursor in menus.

Deadlock writes game\\citadel\\console.log; every map change is a line like  [Client] Map: "dl_hideout".
Only "<empty>" (start screen / loading) counts as lobby: the hideout is a playable map (you walk and shoot in it), and
Deadlock keeps the cursor hidden and locked to the center in its menus too, so menus over the hideout can't be told
apart from playing without reading the game's screen or memory, which Nullpoint never does.
Only this plain text file is read, new bytes only and size-capped: nothing from the game's memory or screen.
"""
import os
import re

MAP_RE = re.compile(rb'\[Client\] Map: "([^"\r\n]{0,64})"')
# shortcut: map names seen on one PC (2026-11)
GAMES = {"deadlock.exe": (os.path.join("..", "..", "citadel", "console.log"), {b"<empty>"})}
MAX_READ = 1024 * 1024  # bytes per check


class LobbyLog:
    def __init__(self):
        self.path, self.pos, self.map = None, 0, None

    def in_lobby(self, exe, exe_path):
        """True / False when the log says lobby / match; None when the game has no log support or no map line yet."""
        spec = GAMES.get(exe)
        if not spec or not exe_path:
            return None
        path = os.path.normpath(os.path.join(os.path.dirname(exe_path), spec[0]))
        if path != self.path:
            self.path, self.pos, self.map = path, 0, None
        try:
            size = os.path.getsize(path)
            if size < self.pos:  # the game started a fresh log
                self.pos, self.map = 0, None
            if size > self.pos:
                start = max(self.pos, size - MAX_READ)  # first look / big jump: only the newest part matters
                with open(path, "rb") as f:
                    f.seek(start)
                    data = f.read(size - start)
                self.pos = size
                found = MAP_RE.findall(data)
                if found:
                    self.map = found[-1]
        except OSError:
            return None
        return None if self.map is None else self.map in spec[1]
