# Invoice Processing Agent with Vision LLM

This tool processes PDF invoices using a vision-capable LLM (like GPT-4o or Claude), extracts vendor names and invoice numbers, and saves them with the naming convention: `HotelCode_Vendor_InvoiceNumber.pdf`.

## Requirements

- Python 3.6+
- Poppler (for PDF to image conversion)
- API key for OpenAI or Anthropic (set as environment variables or entered interactively)
- Python dependencies (see requirements.txt)

## Installation

1. Install Poppler:
   - Ubuntu/Debian: `sudo apt-get install poppler-utils`
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
3. Select which LLM to use
4. Enter API keys if not set in environment variables
5. Review and process invoices

### Command-line Mode

```
python main.py --input /path/to/invoices --output /path/to/output [--hotel-code HOTELCODE] [--model MODEL_NAME] [--api-key API_KEY]
```

### Examples

Basic usage with default settings (STLMO, GPT-4o):
```
python main.py --input ./invoices --output ./processed_invoices
```

With custom hotel code:
```
python main.py --input ./invoices --output ./processed_invoices --hotel-code BHMCO
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
- For Mac users, you may need to add Poppler to your PATH with: `export PATH=/usr/local/Cellar/poppler/xx.xx.x/bin:$PATH`