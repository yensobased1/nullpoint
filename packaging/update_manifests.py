"""After building a release: write the Scoop, Chocolatey and winget files for it from dist\\ (versions + SHA-256).

    python packaging\\update_manifests.py 2.2.0
"""
import hashlib
import json
import os
import re
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = "yensobased1/nullpoint"


def sha(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def main(version):
    dist = os.path.join(ROOT, "dist")
    exe, setup = os.path.join(dist, "Nullpoint.exe"), os.path.join(dist, f"Nullpoint-Setup-{version}.exe")
    base = f"https://github.com/{REPO}/releases/download/v{version}/"
    exe_hash, setup_hash = sha(exe), sha(setup)

    with open(os.path.join(dist, "checksums.txt"), "w", encoding="utf-8", newline="\n") as f:
        f.write(f"{setup_hash}  Nullpoint-Setup-{version}.exe\n{exe_hash}  Nullpoint.exe\n")

    scoop = os.path.join(ROOT, "packaging", "scoop", "nullpoint.json")
    data = json.load(open(scoop, encoding="utf-8"))
    data.update(version=version, url=base + "Nullpoint.exe#/Nullpoint.exe", hash=exe_hash)
    json.dump(data, open(scoop, "w", encoding="utf-8", newline="\n"), indent=4)

    choco = os.path.join(ROOT, "packaging", "chocolatey")
    nuspec = os.path.join(choco, "nullpoint.nuspec")
    s = open(nuspec, encoding="utf-8").read()
    open(nuspec, "w", encoding="utf-8", newline="\n").write(re.sub(r"<version>[^<]*</version>", f"<version>{version}</version>", s))
    ps1 = os.path.join(choco, "tools", "chocolateyinstall.ps1")
    s = open(ps1, encoding="utf-8").read()
    s = re.sub(r"\$url = '[^']*'", f"$url = '{base}Nullpoint.exe'", s)
    s = re.sub(r"\$checksum = '[^']*'", f"$checksum = '{exe_hash}'", s)
    open(ps1, "w", encoding="utf-8", newline="\n").write(s)

    wg = os.path.join(ROOT, "packaging", "winget", "manifests", "y", "yensobased1", "Nullpoint")
    prev = sorted((d for d in os.listdir(wg) if d != version), key=lambda v: tuple(map(int, v.split("."))))[-1]
    dst = os.path.join(wg, version)
    shutil.copytree(os.path.join(wg, prev), dst, dirs_exist_ok=True)
    for name in os.listdir(dst):
        p = os.path.join(dst, name)
        s = open(p, encoding="utf-8").read().replace(prev, version)
        s = re.sub(r"InstallerSha256: \w+", f"InstallerSha256: {setup_hash.upper()}", s)
        open(p, "w", encoding="utf-8", newline="\n").write(s)
    print(f"setup {setup_hash}\nexe   {exe_hash}")


if __name__ == "__main__":
    main(sys.argv[1])
