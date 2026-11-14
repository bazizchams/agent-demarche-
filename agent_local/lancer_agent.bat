@echo off
rem ===================================================================
rem  Lancement de l'Agent Local : double-cliquez, puis laissez la fenetre
rem  noire OUVERTE. L'agent ouvre le navigateur sur ce PC quand vous
rem  cliquez sur "Ouvrir sur mon PC" dans l'interface du bureau.
rem ===================================================================
setlocal
cd /d "%~dp0.."
if not exist "agent_local\.venv-agent\Scripts\python.exe" (
  echo L'agent n'est pas encore installe sur ce PC.
  echo Double-cliquez d'abord sur "installer_agent.bat" ^(dossier agent_local^).
  echo.
  pause
  exit /b 1
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0lancer_agent.ps1" %*
set "CODE=%ERRORLEVEL%"
echo.
echo L'agent est arrete ^(code %CODE%^).
pause
endlocal & exit /b %CODE%
