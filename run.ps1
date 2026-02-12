# Parameter to skip dependency installation
param(
    [switch]$SkipInstall
)

# 1. Start Infrastructure
Write-Host "Starting Docker Infrastructure..." -ForegroundColor Green
docker compose up -d

# 2. Backend Setup & Run
Write-Host "Setting up Backend..." -ForegroundColor Green
Set-Location backend

# Install requirements (skip if -SkipInstall flag is used)
if (-not $SkipInstall) {
    Write-Host "Installing Backend dependencies..."
    ../venv/Scripts/python.exe -m pip install -r requirements.txt
} else {
    Write-Host "Skipping Backend dependencies installation (-SkipInstall flag)" -ForegroundColor Yellow
}

# Init DB (Wait for Postgres to be ready might be needed in real scenario, here we assume it's fast enough or re-run)
Write-Host "Initializing Database..." -ForegroundColor Green
../venv/Scripts/python.exe -m app.db.init_db

# Start Backend in a new window
Write-Host "Starting Backend Server in new window..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "& '..\venv\Scripts\activate'; uvicorn app.main:app --reload"

# 3. Frontend Setup & Run
Set-Location ../frontend
Write-Host "Setting up Frontend..." -ForegroundColor Green

# Install npm packages (skip if -SkipInstall flag is used)
if (-not $SkipInstall) {
    Write-Host "Installing Frontend dependencies..."
    npm install
} else {
    Write-Host "Skipping Frontend dependencies installation (-SkipInstall flag)" -ForegroundColor Yellow
}

# Start Frontend in a new window
Write-Host "Starting Frontend Server in new window..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "npm run dev"

Set-Location ..
Write-Host "All services startup initiated!" -ForegroundColor Green
