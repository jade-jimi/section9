@echo off
rem section9 Windows entry — python 런처 자동 탐색
where python >nul 2>nul && (python "%~dp0s9-install" %*) || (py -3 "%~dp0s9-install" %*)
