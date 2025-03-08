# Invoice Processing Agent with Vision LLM (v1.3.0)

This tool processes PDF invoices using a vision-capable LLM (like GPT-4o, Claude, or Mistral AI), extracts vendor names and invoice numbers, and saves them with the naming convention: `HotelCode_Vendor_InvoiceNumber.pdf`.

## Features

- Automatic hotel location detection from invoice content
- Process invoices in parallel for faster throughput
- Batch processing to handle large volumes of invoices
- Preview mode to verify extraction before renaming files
- Robust error handling and retry mechanisms
- Support for multiple LLM providers (OpenAI, Anthropic, and Mistral AI)
- Interactive or command-line operation

## Quick Start

Run the setup script to install all dependencies and start the application:

```bash
# Make the script executable (if needed)
chmod +x setup.sh

# Run the setup script with CLI interface (original version)
./setup.sh

# Or run with the new web interface (monetized version)
./setup.sh --web
```

The script will:
1. Install necessary system dependencies (Poppler and libraries)
2. Install Python dependencies
3. Launch the application in your preferred mode:
   - CLI mode: Interactive command-line interface
   - Web mode: Modern web interface accessible at http://localhost:5000

## Requirements

- Python 3.6+
- Poppler (for PDF to image conversion)
- API key for OpenAI, Anthropic, or Mistral AI (set as environment variables or entered interactively)
- Python dependencies (see requirements.txt)

## Manual Installation

If you prefer to install components manually:

1. Install Poppler:
   - Ubuntu/Debian: `sudo apt-get install -y libjpeg-dev libpoppler-cpp-dev poppler-utils`
   - MacOS: `brew install poppler`
   - Windows: Download from https://blog.alivate.com.au/poppler-windows/

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
   
   # For Mistral AI
   export MISTRAL_API_KEY=your-api-key
   ```

## Usage

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

With Mistral AI:
```
python main.py --input ./invoices --output ./processed_invoices --model mistral-large-latest
```

## Supported Hotel Codes

- `STLMO` - St. Louis, Missouri (default)
- `BHMCO` - Birmingham, Colorado
- `BTRGI` - Baton Rouge, Georgia
- Any custom code can be used in interactive mode

## Supported Models

- OpenAI: gpt-4o (default), gpt-4-vision-preview
- Anthropic: claude-3-sonnet-20240229, claude-3-opus-20240229, claude-3-haiku-20240307
- Mistral AI: mistral-large-latest, mistral-medium-latest

## Notes

- The tool processes all PDF files in the input directory
- The agent uses a vision-capable LLM to analyze the first page of each invoice
- The LLM extracts vendor names and invoice numbers directly from the visual representation
- Files are saved with the naming convention HotelCode_Vendor_InvoiceNumber.pdf
- For Mac users, you may need to add Poppler to your PATH with: `export PATH=/usr/local/Cellar/poppler/xx.xx.x/bin:$PATH`

## New in v1.3.0

- Added support for Mistral AI's OCR and document understanding capabilities
- Integrated Mistral's advanced document analysis for improved extraction accuracy
- Updated the model selection UI to include Mistral models
- Added environment variable support for Mistral API keys

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