# 1. Start Infrastructure
Write-Host "Starting Docker Infrastructure..." -ForegroundColor Green
docker compose up -d

# 2. Backend Setup & Run
Write-Host "Setting up Backend..." -ForegroundColor Green
Set-Location backend

# Install requirements
Write-Host "Installing Backend dependencies..."
../venv/Scripts/python.exe -m pip install -r requirements.txt

# Start Backend in a new window
Write-Host "Starting Backend Server in new window..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "& '..\venv\Scripts\activate'; uvicorn app.main:app --reload"

# 3. Frontend Setup & Run
Set-Location ../frontend
Write-Host "Setting up Frontend..." -ForegroundColor Green
Write-Host "Installing Frontend dependencies..."
npm install

# Start Frontend in a new window
Write-Host "Starting Frontend Server in new window..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "npm run dev"

Set-Location ..
Write-Host "All services startup initiated!" -ForegroundColor Green
