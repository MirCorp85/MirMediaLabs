@echo off
:: Render every missing preview (series options + settings panel). Resumable; yields to anyone using the lab.
set PYTHONUTF8=1
cd /d "%~dp0.."
for %%m in (options setup objects stylevideos moves setup voices songs) do python -u tools\make_series_samples.py %%m
python -u tools\make_param_previews.py
:: optional: keep a second local copy of the previews in sync (set MML_SAMPLES_MIRROR / MML_FX_MIRROR to a folder)
if defined MML_SAMPLES_MIRROR robocopy "%~dp0..\server\static\series\samples" "%MML_SAMPLES_MIRROR%" /E /XO /XF _obase_* *.bak* *.src.mp4 /NFL /NDL /NJH /NJS >nul
if defined MML_FX_MIRROR robocopy "%~dp0..\server\static\fx" "%MML_FX_MIRROR%" /E /XO /XF *.src.mp4 /NFL /NDL /NJH /NJS >nul
exit /b 0
