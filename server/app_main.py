"""MirMediaLabs.exe — entry point of the compiled PC build (installed at <dir>\\app\\).

  MirMediaLabs.exe                 start the server if needed, open the studio window
  MirMediaLabs.exe --server-only   start the server only (Startup shortcut)
  MirMediaLabs.exe --server        run the server in this process (spawned by the two above)
  MirMediaLabs.exe --stop          stop the server and this install's ComfyUI engine
The dev copy on the build PC keeps running medialab.py directly; this file is only compiled.
"""
import os
import socket
import subprocess
import sys
import time
import webbrowser

EXE = os.path.abspath(sys.argv[0])
ROOT = os.path.dirname(os.path.dirname(EXE))
NO_WINDOW, DETACHED = 0x08000000, 0x00000008


def port_open(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.3)
        return s.connect_ex(("127.0.0.1", port)) == 0


def run_server():
    logs = os.path.join(ROOT, "data", "logs")
    os.makedirs(logs, exist_ok=True)
    sys.stdout = open(os.path.join(logs, "server_out.log"), "a", encoding="utf-8", buffering=1)
    sys.stderr = open(os.path.join(logs, "server_err.log"), "a", encoding="utf-8", buffering=1)
    import medialab
    medialab.main()


def start_server(port):
    if port_open(port):
        return
    subprocess.Popen([EXE, "--server"], cwd=os.path.dirname(EXE), creationflags=DETACHED | NO_WINDOW)
    for _ in range(80):
        if port_open(port):
            return
        time.sleep(0.25)


def stop():
    dirs = " -or ".join("$_.ExecutablePath -like '%s\\*'" % os.path.join(ROOT, d).replace("'", "''")
                        for d in ("app", "runtime"))
    ps = ("Get-CimInstance Win32_Process | Where-Object { (%s) -and $_.ProcessId -ne %d } | "
          "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }" % (dirs, os.getpid()))
    subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps], creationflags=NO_WINDOW)


def open_window(port):
    url = "http://127.0.0.1:%d/" % port
    # own browser profile → own process + window, never merged into the user's normal browser
    profile = os.path.join(ROOT, "data", "window")
    for base in (os.environ.get(k, "") for k in ("ProgramFiles(x86)", "ProgramFiles", "LOCALAPPDATA")):
        for rel in (r"Microsoft\Edge\Application\msedge.exe", r"Google\Chrome\Application\chrome.exe"):
            exe = os.path.join(base, rel)
            if base and os.path.isfile(exe):
                subprocess.Popen([exe, "--app=" + url, "--window-size=1500,950", "--user-data-dir=" + profile,
                                  "--no-first-run", "--no-default-browser-check"], creationflags=DETACHED)
                import taskbar      # taskbar/pin identity = MirMediaLabs.exe + its icon, not Edge
                taskbar.brand_window(EXE)
                return
    webbrowser.open(url)


def main():
    args = sys.argv[1:]
    if "--server" in args:
        return run_server()
    if "--stop" in args:
        return stop()
    import taskbar
    taskbar.set_process_app_id()
    import core                     # port from mml_config.json
    start_server(core.PORT)
    if "--server-only" not in args:
        open_window(core.PORT)


if __name__ == "__main__":
    main()
