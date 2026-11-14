<#
.SYNOPSIS
  Enrôle et lance l'Agent Local du bureau sur ce PC Windows.

.DESCRIPTION
  - Demande l'adresse du serveur et la clé de l'agent (saisie masquée : rien ne s'affiche).
  - Peut mémoriser l'adresse et la clé SUR CE PC, chiffrées par Windows (DPAPI) : seul votre compte
    Windows sur ce PC peut les relire. Jamais dans un fichier en clair, jamais sur la ligne de commande.
  - Lance `lanceur.py --mode ecouter`. La clé n'est transmise au programme que par une variable
    d'environnement propre à ce processus.
  Option -Oublier : efface l'adresse et la clé mémorisées.
#>
param(
  [string]$UrlServeur = "",
  [switch]$Oublier
)

$ErrorActionPreference = "Stop"
$dossierAgent = Split-Path -Parent $MyInvocation.MyCommand.Path
$racine = Split-Path -Parent $dossierAgent
$python = Join-Path $dossierAgent ".venv-agent\Scripts\python.exe"
$lanceur = Join-Path $dossierAgent "lanceur.py"
$dossierConfig = Join-Path $env:APPDATA "AgentBureau"
$fichierUrl = Join-Path $dossierConfig "serveur.txt"
$fichierJeton = Join-Path $dossierConfig "jeton.dpapi"
# Profil navigateur (cookies de session des portails) : hors dépôt Git, réservé à l'utilisateur Windows courant.
$dossierProfil = Join-Path (Join-Path $env:LOCALAPPDATA "AgentBureau") "profil_chromium"

if ($Oublier) {
  Remove-Item -LiteralPath $fichierUrl, $fichierJeton -Force -ErrorAction SilentlyContinue
  Write-Host "Adresse et clé mémorisées effacées de ce PC."
  exit 0
}

New-Item -ItemType Directory -Force -Path $dossierConfig | Out-Null

# --- Adresse du serveur -------------------------------------------------------------------------
if (-not $UrlServeur -and (Test-Path -LiteralPath $fichierUrl)) {
  $UrlServeur = (Get-Content -LiteralPath $fichierUrl -TotalCount 1).Trim()
}
if (-not $UrlServeur) {
  Write-Host ""
  Write-Host "Adresse du serveur du bureau (celle affichée dans le navigateur quand vous ouvrez l'interface)."
  Write-Host "Exemple : http://127.0.0.1:8000"
  $UrlServeur = (Read-Host "Adresse du serveur").Trim()
}
if ($UrlServeur -notmatch '^https?://[^\s/]+') {
  Write-Host "Adresse invalide : elle doit commencer par http:// ou https://" -ForegroundColor Red
  exit 2
}
$UrlServeur = $UrlServeur.TrimEnd('/')
if ($UrlServeur -match '^http://' -and $UrlServeur -notmatch '^http://(127\.0\.0\.1|localhost)(:\d+)?(/|$)') {
  Write-Host "Adresse refusée : http:// n'est accepté que vers localhost ou 127.0.0.1 (la clé de l'agent ne doit jamais circuler en clair). Utilisez https://" -ForegroundColor Red
  exit 2
}

# --- Clé de l'agent -----------------------------------------------------------------------------
$memorisee = $false
if (Test-Path -LiteralPath $fichierJeton) {
  try {
    $jetonSecurise = Get-Content -LiteralPath $fichierJeton -TotalCount 1 | ConvertTo-SecureString
    $memorisee = $true
  } catch {
    Write-Host "La clé mémorisée est illisible (autre compte Windows ?) : elle est ignorée." -ForegroundColor Yellow
    Remove-Item -LiteralPath $fichierJeton -Force -ErrorAction SilentlyContinue
  }
}
if (-not $memorisee) {
  Write-Host ""
  Write-Host "Collez la clé de l'agent (donnée une seule fois par « Enrôler un poste agent local »)."
  Write-Host "Rien ne s'affiche pendant la saisie : c'est normal. Terminez par Entrée."
  $jetonSecurise = Read-Host "Clé de l'agent" -AsSecureString
}

$pointeur = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($jetonSecurise)
try {
  $jeton = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointeur)
} finally {
  [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointeur)
}
if (-not $jeton.Trim()) {
  Write-Host "Aucune clé saisie." -ForegroundColor Red
  exit 2
}

if (-not $memorisee) {
  $reponse = Read-Host "Mémoriser l'adresse et la clé sur ce PC, protégées par votre session Windows ? (O/N)"
  if ($reponse -match '^[OoYy]') {
    Set-Content -LiteralPath $fichierUrl -Value $UrlServeur -Encoding ASCII
    $jetonSecurise | ConvertFrom-SecureString | Set-Content -LiteralPath $fichierJeton -Encoding ASCII
    Write-Host "Mémorisé. Pour l'oublier : lancer_agent.bat -Oublier"
  }
}

# --- Lancement ----------------------------------------------------------------------------------
$env:BE_JETON_AGENT = $jeton.Trim()
$jeton = $null
Write-Host ""
Write-Host "Connexion à $UrlServeur ... (Ctrl+C pour arrêter proprement)"
New-Item -ItemType Directory -Force -Path $dossierProfil | Out-Null
# Droits : plus d'héritage, accès complet au seul utilisateur courant (au mieux : un échec n'empêche pas le lancement).
try {
  & icacls $dossierProfil /inheritance:r /grant:r "$($env:USERDOMAIN)\$($env:USERNAME):(OI)(CI)F" | Out-Null
} catch {
  Write-Host "Droits du dossier de profil non restreints : $($_.Exception.Message)" -ForegroundColor Yellow
}
Push-Location $racine
try {
  & $python $lanceur --mode ecouter --url-serveur $UrlServeur --profil-navigateur $dossierProfil
  $code = $LASTEXITCODE
} finally {
  Pop-Location
  Remove-Item Env:\BE_JETON_AGENT -ErrorAction SilentlyContinue
}
if ($code -eq 3) {
  Write-Host "La clé a été refusée. Demandez-en une nouvelle à l'administrateur, puis relancez avec -Oublier pour effacer l'ancienne." -ForegroundColor Red
}
exit $code
