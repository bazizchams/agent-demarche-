@echo off
rem ===================================================================
rem  Installation de l'Agent Local (a faire UNE SEULE FOIS sur le PC)
rem  Double-cliquez sur ce fichier. Aucun droit administrateur requis.
rem ===================================================================
setlocal
cd /d "%~dp0.."
echo.
echo === Installation de l'Agent Local du bureau ===
echo.

set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY (
  where python >nul 2>nul && set "PY=python"
)
if not defined PY (
  echo ERREUR : Python est introuvable.
  echo Installez Python 3.11 ou plus recent depuis https://www.python.org/downloads/
  echo ^(cochez la case "Add python.exe to PATH"^), puis relancez ce fichier.
  goto fin
)

%PY% -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)"
if errorlevel 1 (
  echo ERREUR : votre Python est trop ancien. Il faut Python 3.11 ou plus recent.
  echo Telechargez-le sur https://www.python.org/downloads/ puis relancez ce fichier.
  goto fin
)

if not exist "agent_local\.venv-agent\Scripts\python.exe" (
  echo [1/3] Creation de l'environnement prive de l'agent...
  %PY% -m venv "agent_local\.venv-agent"
  if errorlevel 1 goto erreur
) else (
  echo [1/3] Environnement deja cree : on le reutilise.
)

echo [2/3] Installation des composants ^(quelques minutes, internet requis^)...
"agent_local\.venv-agent\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto erreur
"agent_local\.venv-agent\Scripts\python.exe" -m pip install -e serveur
if errorlevel 1 goto erreur

echo.
echo [3/3] Navigateur de secours ^(facultatif^).
echo L'agent utilise Google Chrome s'il est installe, sinon Microsoft Edge ^(deja present
echo sous Windows^). Un Chromium de secours n'est utile que si aucun des deux ne marche.
set "REPONSE=N"
set /p "REPONSE=Installer aussi le Chromium de secours (O/N, defaut N) ? "
if /i "%REPONSE%"=="O" (
  "agent_local\.venv-agent\Scripts\python.exe" -m playwright install chromium
  if errorlevel 1 goto erreur
)

echo.
echo === Installation terminee. ===
echo Etape suivante : double-cliquez sur "lancer_agent.bat" ^(dans le dossier agent_local^).
goto fin

:erreur
echo.
echo ERREUR pendant l'installation. Relisez le message ci-dessus, verifiez votre connexion
echo internet, puis relancez ce fichier. Voir docs\AGENT_LOCAL.md ^(section "Si ca ne marche pas"^).

:fin
echo.
pause
endlocal
