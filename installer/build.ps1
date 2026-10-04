# Builds the compiled PC edition of MIR MEDIA LABS.
#   powershell -File C:\AiMir-Tools\MirMediaLabs\installer\build.ps1 [-Bump] [-Publish -Notes "what changed"]
#
#   app\MirMediaLabs.exe        the server + launcher, compiled to native code by Nuitka (no .py ships);
#                               the web UI is minified and embedded inside the binary
#   MirMediaLabs-Setup.exe      native one-file setup wizard carrying the app (payload.zip)
#   -Publish                    signs the setup (Ed25519) into updates\pc\ = the PC update server,
#                               served by this PC's MIR MEDIA LABS at /updates/pc/
param([switch]$Bump, [switch]$Publish, [switch]$Public, [string]$Notes = "", [string]$UpdateUrl = "")
# -Public: GitHub release build - no private update URL or channel token inside the binary.
# Update channel: -UpdateUrl, else $env:MML_UPDATE_URL, else installer\signing\update_url.txt (private, gitignored).
# Empty = auto-update off (public builds get updates from GitHub Releases).
if ($Public) { $UpdateUrl = "-" }
if (-not $UpdateUrl) { $UpdateUrl = $env:MML_UPDATE_URL }
$urlFile = Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) 'signing\update_url.txt'
if (-not $UpdateUrl -and (Test-Path $urlFile)) { $UpdateUrl = (Get-Content $urlFile -Raw).Trim() }
$ErrorActionPreference = 'Stop'
$here  = Split-Path -Parent $MyInvocation.MyCommand.Path
$root  = Split-Path -Parent $here
$build = Join-Path $here 'build'
$tools = Join-Path $build 'tools'
$py    = Join-Path $build 'nvenv\Scripts\python.exe'
$env:NUITKA_CACHE_DIR = Join-Path $tools 'nuitka-cache'     # real folder (the app sandbox virtualizes AppData)
$env:PYTHONUTF8 = '1'

# 0. build venv: Python 3.12 + Nuitka (MinGW is downloaded by Nuitka on first build)
if (-not (Test-Path $py)) {
    $uv = Join-Path $tools 'uv.exe'
    if (-not (Test-Path $uv)) {
        New-Item -ItemType Directory -Force $tools | Out-Null
        Invoke-WebRequest https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-pc-windows-msvc.zip -OutFile "$tools\uv.zip"
        Expand-Archive "$tools\uv.zip" $tools -Force
    }
    $env:UV_PYTHON_INSTALL_DIR = Join-Path $tools 'python'; $env:UV_CACHE_DIR = Join-Path $tools 'uvcache'
    & $uv venv (Join-Path $build 'nvenv') --python 3.12 --managed-python
    & $uv pip install --python $py nuitka ordered-set zstandard flask requests cryptography
}
if (-not (Test-Path (Join-Path $here 'pc_version.json'))) { '{"version": "1.0.0"}' | Set-Content -Encoding ascii (Join-Path $here 'pc_version.json') }
if ($Bump) { & $py (Join-Path $here 'build_tool.py') bump }
$ver = (Get-Content (Join-Path $here 'pc_version.json') | ConvertFrom-Json).version
"== MIR MEDIA LABS PC v$ver"

# 1. keys + staged source (server code + generated _buildinfo / _assets)
& $py (Join-Path $here 'build_tool.py') keys
$src = Join-Path $build 'src'
& $py (Join-Path $here 'build_tool.py') stage $src $UpdateUrl
if ($LASTEXITCODE) { throw 'stage failed' }

# 2. compile the app (standalone folder, no console)
$appOut = Join-Path $build 'appout'
Remove-Item $appOut -Recurse -Force -ErrorAction SilentlyContinue
$ico  = Join-Path $root 'MirMediaLabs.ico'
# plain string arrays: PowerShell 5.1 splits "--opt=(expr)" into two arguments
$common = @("-m", "nuitka", "--assume-yes-for-downloads", "--windows-console-mode=disable", "--python-flag=no_docstrings", "--python-flag=no_asserts", "--lto=yes", "--deployment",
            "--windows-icon-from-ico=$ico", "--company-name=MirCorp", "--product-name=MIR MEDIA LABS",
            "--file-version=$ver.0", "--product-version=$ver.0", "--copyright=(c) 2026 MirCorp. GPL-3.0")
$appArgs = $common + @("--standalone", "--nofollow-import-to=imageio_ffmpeg", "--nofollow-import-to=tkinter",
                       "--output-filename=MirMediaLabs.exe", "--file-description=MIR MEDIA LABS",
                       "--output-dir=$appOut", (Join-Path $src 'app_main.py'))
& $py @appArgs
if ($LASTEXITCODE) { throw 'Nuitka (app) failed' }
$dist = Join-Path $appOut 'app_main.dist'

# 3. payload = compiled app + Android update folder + icon (never data\, never source)
$stage = Join-Path $build 'payload'
Remove-Item $stage -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force (Join-Path $stage 'updates') | Out-Null
Copy-Item $dist (Join-Path $stage 'app') -Recurse
if ($Public) {
    # public payload carries the MirCorp-signed release APK (never the private debug build)
    $rel = Join-Path $root 'MirMediaLabs-release.apk'
    if (-not (Test-Path $rel)) { throw 'run build_apk.ps1 -Release first' }
    Copy-Item $rel "$stage\updates\MirMediaLabs.apk"
    $g = Get-Content (Join-Path $root 'app\app\build.gradle') -Raw
    $vj = [ordered]@{ versionCode = [int]([regex]::Match($g, 'versionCode (\d+)').Groups[1].Value);
                      versionName = [regex]::Match($g, 'versionName "([^"]+)"').Groups[1].Value; notes = "";
                      apk = "MirMediaLabs.apk"; sha256 = (Get-FileHash $rel -Algorithm SHA256).Hash.ToLower() } | ConvertTo-Json
    [IO.File]::WriteAllText("$stage\updates\version.json", $vj)
} else {
    foreach ($f in 'version.json', 'MirMediaLabs.apk') { if (Test-Path "$root\updates\$f") { Copy-Item "$root\updates\$f" "$stage\updates" } }
}
Copy-Item (Join-Path $root 'MirMediaLabs.ico') $stage
$zip = Join-Path $build 'payload.zip'
Remove-Item $zip -ErrorAction SilentlyContinue
& $py -c "import shutil,sys; shutil.make_archive(sys.argv[1][:-4], 'zip', sys.argv[2])" $zip $stage
"{`"version`": `"$ver`"}" | Set-Content -Encoding ascii (Join-Path $build 'build.json')
if (-not (Test-Path (Join-Path $build 'icon-64.png'))) { Copy-Item (Join-Path $root 'server\static\icon-512.png') (Join-Path $build 'icon-64.png') }

# 3b. showcase gallery (real MML renders) + mobile-companion QR for the wizard — Pillow runs here, not in the setup
& $py -c "import PIL, qrcode" 2>$null
if ($LASTEXITCODE) { & (Join-Path $tools 'uv.exe') pip install --python $py pillow qrcode }
$show = Join-Path $build 'showcase'
& $py (Join-Path $here 'make_showcase.py') $show
if ($LASTEXITCODE) { throw 'showcase failed' }

# 4. compile the setup wizard (one file)
$setupOut = Join-Path $build 'setupout'
$setupArgs = $common + @("--onefile", "--enable-plugin=tk-inter",
    "--include-data-files=$zip=payload.zip", "--include-data-files=$build\build.json=build.json",
    "--include-data-files=$ico=MirMediaLabs.ico", "--include-data-files=$build\icon-64.png=icon-64.png",
    "--include-data-dir=$show=showcase",
    "--output-filename=MirMediaLabs-Setup.exe", "--file-description=MIR MEDIA LABS Setup",
    "--output-dir=$setupOut", (Join-Path $here 'setup_wizard.py'))
& $py @setupArgs
if ($LASTEXITCODE) { throw 'Nuitka (setup) failed' }
$exe = Join-Path $setupOut 'MirMediaLabs-Setup.exe'
Copy-Item $exe (Join-Path $root 'MirMediaLabs-Setup.exe') -Force
"built MirMediaLabs-Setup.exe v$ver ($([math]::Round((Get-Item $exe).Length/1MB,1)) MB)"

# 5. publish to the update server
if ($Publish) { & $py (Join-Path $here 'build_tool.py') publish $exe $Notes }
