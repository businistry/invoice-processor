# Invoice Processing Agent with Vision LLM (v1.2.0)

This tool processes PDF invoices using a vision-capable LLM (like GPT-4o or Claude), extracts vendor names and invoice numbers, and saves them with the naming convention: `HotelCode_Vendor_InvoiceNumber.pdf`.

## Features

- Automatic hotel location detection from invoice content
- Process invoices in parallel for faster throughput
- Batch processing to handle large volumes of invoices
- Preview mode to verify extraction before renaming files
- Robust error handling and retry mechanisms
- Support for multiple LLM providers (OpenAI and Anthropic)
- Interactive or command-line operation

## Quick Start

Run the appropriate setup script for your operating system to install dependencies and start the application.

**For Windows:**

Open PowerShell, navigate to the project directory, and run:

```powershell
.\setup.ps1
```
You may need to adjust your script execution policy. If you see an error, try:
`Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`
Then run `.\setup.ps1` again.

The script will:
1. Guide you through installing Chocolatey (a package manager) if not already present.
2. Install Poppler (for PDF processing) using Chocolatey.
3. Create a Python virtual environment (`venv`).
4. Install Python dependencies.
5. Offer to launch the application in interactive mode.

**For Linux/macOS:**

```bash
# Make the script executable (if needed)
chmod +x setup.sh

# Run the setup script
./setup.sh
```

The script will:
1. Install necessary system dependencies (Poppler and libraries).
2. Install Python dependencies.
3. Launch the application in interactive mode.

## Requirements

- Python 3.6+
- Poppler (for PDF to image conversion)
- API key for OpenAI or Anthropic (set as environment variables or entered interactively)
- Python dependencies (see requirements.txt)

## Manual Installation

If you prefer to install components manually:

1. Install Poppler:
   - **Windows:** The recommended method is to use the `.\setup.ps1` script which handles this. Alternatively, for manual installation:
     - Install Chocolatey from https://chocolatey.org/install
     - Then run `choco install poppler` in an Administrator PowerShell.
     - Or, download Poppler for Windows from a reputable source (e.g., the one often cited is [Poppler for Windows on Alivate.com.au](https://blog.alivate.com.au/poppler-windows/)) and add its `bin` directory to your system's PATH.
   - Ubuntu/Debian: `sudo apt-get install -y libjpeg-dev libpoppler-cpp-dev poppler-utils`
   - MacOS: `brew install poppler`

2. Install Python dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Set API keys as environment variables (optional, can also be entered interactively):
   ```
   # For OpenAI
   export OPENAI_API_KEY=your-api-key

   # For Anthropic
   export ANTHROPIC_API_KEY=your-api-key
   ```

## Usage

**Important:** Before running the application, ensure you have activated the Python virtual environment created during setup.

- **Windows (PowerShell):**
  ```powershell
  .\venv\Scripts\Activate.ps1
  ```
- **Windows (Command Prompt):**
  ```cmd
  .\venv\Scripts\activate.bat
  ```
- **Linux/macOS (bash/zsh):**
  ```bash
  source venv/bin/activate
  ```

Once the virtual environment is active, you can run the application.

### Interactive Mode (Recommended)

Run the tool with the interactive CLI interface:

```
python main.py -i
```

Follow the prompts to:
1. Select input and output directories
2. Choose a hotel code (STLMO, BHMCO, BTRGI, or custom)
3. Configure advanced options (preview mode, batch size, parallel processing)
4. Select which LLM to use
5. Enter API keys if not set in environment variables
6. Review and process invoices

### Command-line Mode

```
python main.py --input /path/to/invoices --output /path/to/output [options]
```

Available options:
```
--hotel-code HOTELCODE    Hotel code for naming convention (default: STLMO)
--model MODEL_NAME        Model to use (default: gpt-4o)
--api-key API_KEY         API key for the selected model
--preview                 Preview mode - don't actually rename files
--batch-size SIZE         Process files in batches of this size
--workers N               Number of parallel workers (1-8, default: 1)
--auto-detect             Auto-detect hotel location from invoice content
--version, -v             Show version information
```

### Examples

Basic usage with default settings (STLMO, GPT-4o):
```
python main.py --input ./invoices --output ./processed_invoices
```

With advanced options:
```
python main.py --input ./invoices --output ./processed_invoices --auto-detect --preview --batch-size 5 --workers 4
```

With Anthropic Claude:
```
python main.py --input ./invoices --output ./processed_invoices --model claude-3-sonnet-20240229
```

## Supported Hotel Codes

- `STLMO` - St. Louis, Missouri (default)
- `BHMCO` - Birmingham, Colorado
- `BTRGI` - Baton Rouge, Georgia
- Any custom code can be used in interactive mode

## Supported Models

- OpenAI: gpt-4o (default), gpt-4-vision-preview
- Anthropic: claude-3-sonnet-20240229, claude-3-opus-20240229, claude-3-haiku-20240307

## Notes

- The tool processes all PDF files in the input directory
- The agent uses a vision-capable LLM to analyze the first page of each invoice
- The LLM extracts vendor names and invoice numbers directly from the visual representation
- Files are saved with the naming convention HotelCode_Vendor_InvoiceNumber.pdf
- If you installed Poppler manually (not via `setup.sh`, `setup.ps1`, or a package manager like Chocolatey/Homebrew), ensure its `bin` directory is in your system's PATH.

## New in v1.2.0

- Added automatic hotel location detection from invoice content
- Enhanced display of detected location information
- Added `--auto-detect` command line flag
- Updated interactive mode with auto-detection option

## New in v1.1.0

- Added parallel processing support for faster throughput
- Added batch processing to handle large volumes of invoices
- Added preview mode to verify extraction before file operations
- Improved error handling with retry mechanisms for API calls
- Enhanced JSON parsing to better handle different LLM response formats
- Added progress bars for better visibility during processing