# PowerShell script to set up the Invoice Processing Agent on Windows

# Function to check if Chocolatey is installed
function Test-ChocolateyInstalled {
    try {
        Get-Command choco -ErrorAction SilentlyContinue
        return $?
    }
    catch {
        return $false
    }
}

# Function to install Chocolatey
function Install-Chocolatey {
    Write-Host "Chocolatey not found. Attempting to install Chocolatey..."
    Write-Host "This may require administrator privileges."
    try {
        Set-ExecutionPolicy Bypass -Scope Process -Force;
        [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072;
        iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))
        Write-Host "Chocolatey installation attempted. Please close this window, open a new PowerShell window as Administrator, and re-run this script."
        Write-Host "If Chocolatey is installed, you can proceed with the script."
        exit
    }
    catch {
        Write-Error "Chocolatey installation failed: $($_.Exception.Message)"
        Write-Host "Please install Chocolatey manually from https://chocolatey.org/install and then re-run this script."
        exit
    }
}

# Function to install Poppler using Chocolatey
function Install-Poppler {
    Write-Host "Attempting to install Poppler using Chocolatey..."
    Write-Host "This may require administrator privileges."
    try {
        choco install poppler --yes --force --execution-timeout=0
        Write-Host "Poppler installation successful."
    }
    catch {
        Write-Error "Poppler installation failed: $($_.Exception.Message)"
        Write-Host "Please ensure Chocolatey is installed and try running 'choco install poppler' manually in an Administrator PowerShell."
        exit
    }
}

# --- Main Script ---

Write-Host "Starting setup for Invoice Processing Agent..."

# Check for Chocolatey
if (-not (Test-ChocolateyInstalled)) {
    Install-Chocolatey
} else {
    Write-Host "Chocolatey is already installed."
}

# Check for Poppler (basic check, choco will handle actual versioning)
$popplerInstalled = $false
try {
    $popplerPath = Get-Command pdftotext -ErrorAction SilentlyContinue
    if ($popplerPath) {
        Write-Host "Poppler (pdftotext) seems to be installed."
        $popplerInstalled = $true
    }
} catch {}

if (-not $popplerInstalled) {
    Install-Poppler
}

# Create a virtual environment if it doesn't exist
if (-not (Test-Path -Path "venv")) {
    Write-Host "Creating Python virtual environment..."
    try {
        python -m venv venv
        Write-Host "Virtual environment created."
    }
    catch {
        Write-Error "Failed to create virtual environment. Ensure Python 3 is installed and in your PATH."
        exit
    }
} else {
    Write-Host "Virtual environment 'venv' already exists."
}

# Activate virtual environment and install Python dependencies
Write-Host "Installing Python dependencies from requirements.txt..."
try {
    # Activate venv and install requirements
    # Note: Activating venv in a script and having it persist for subsequent commands is tricky.
    # It's generally better to call the python/pip from within the venv directly.
    if (Test-Path -Path "venv\Scripts\pip.exe") {
        .\venv\Scripts\pip.exe install -r requirements.txt
        Write-Host "Python dependencies installed successfully."
    } elseif (Test-Path -Path "venv\bin\pip") { # For environments created in WSL/git-bash
         .\venv\bin\pip install -r requirements.txt
         Write-Host "Python dependencies installed successfully."
    }
    else {
        Write-Error "Could not find pip in the virtual environment. Please activate it manually and run 'pip install -r requirements.txt'"
        Write-Host "To activate: .\venv\Scripts\Activate.ps1"
        exit
    }
}
catch {
    Write-Error "Failed to install Python dependencies: $($_.Exception.Message)"
    Write-Host "Please activate the virtual environment manually (.\venv\Scripts\Activate.ps1) and run 'pip install -r requirements.txt'."
    exit
}

Write-Host "Setup complete!"
Write-Host ""
$launchApp = Read-Host "Do you want to launch the application now in interactive mode? (y/n)"
if ($launchApp -eq 'y' -or $launchApp -eq 'Y') {
    Write-Host "Launching application..."
    if (Test-Path -Path "venv\Scripts\python.exe") {
        .\venv\Scripts\python.exe main.py -i
    } elseif (Test-Path -Path "venv\bin\python") {
         .\venv\bin\python main.py -i
    } else {
        Write-Error "Could not find python.exe in the virtual environment. Please activate it manually and run 'python main.py -i'"
    }
} else {
    Write-Host "You can start the application later by running: python main.py -i (after activating the virtual environment: .\venv\Scripts\Activate.ps1)"
}
