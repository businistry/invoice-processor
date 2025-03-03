#!/usr/bin/env python3
import os
import argparse
import re
import json
import base64
import io
import time
import getpass
from pathlib import Path
import requests
from pdf2image import convert_from_path
from PIL import Image
import sys
import colorama
from colorama import Fore, Style, Back

# Initialize colorama for colored terminal output
colorama.init()

class InvoiceProcessor:
    def __init__(self, input_dir, output_dir, model=None, api_key=None, hotel_code="STLMO"):
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.model = model
        self.hotel_code = hotel_code
        self.processed_files = []
        
        # Set API keys
        self.openai_api_key = api_key if self.model and self.model.startswith("gpt") else os.environ.get('OPENAI_API_KEY')
        self.anthropic_api_key = api_key if self.model and self.model.startswith("claude") else os.environ.get('ANTHROPIC_API_KEY')
        
        # Create output directory if it doesn't exist
        if not self.output_dir.exists():
            self.output_dir.mkdir(parents=True)
    
    def process_invoices(self):
        """Process all PDF invoices in the input directory"""
        pdf_files = list(self.input_dir.glob("*.pdf"))
        
        if not pdf_files:
            print(f"{Fore.YELLOW}No PDF files found in {self.input_dir}{Style.RESET_ALL}")
            return
        
        print(f"{Fore.GREEN}Found {len(pdf_files)} PDF files to process{Style.RESET_ALL}")
        
        for pdf_file in pdf_files:
            try:
                print(f"{Fore.CYAN}Processing {pdf_file.name}...{Style.RESET_ALL}")
                result = self.process_invoice(pdf_file)
                if result:
                    self.processed_files.append(result)
            except Exception as e:
                print(f"{Fore.RED}Error processing {pdf_file.name}: {str(e)}{Style.RESET_ALL}")
    
    def process_invoice(self, pdf_path):
        """Process a single invoice PDF"""
        # Convert PDF to images
        pages = convert_from_path(pdf_path)
        
        # Use only the first page for analysis (usually contains invoice info)
        first_page = pages[0]
        
        # Show spinner while processing
        print(f"{Fore.YELLOW}Analyzing invoice with {self.model}...{Style.RESET_ALL}", end="")
        sys.stdout.flush()
        
        # Extract information using vision-capable LLM
        result = self.extract_info_with_llm(first_page)
        
        # Clear the spinner line
        print("\r" + " " * 80 + "\r", end="")
        
        if not result.get('vendor') or not result.get('invoice_number'):
            print(f"{Fore.RED}Could not extract vendor or invoice number from {pdf_path.name}{Style.RESET_ALL}")
            print(f"{Fore.RED}LLM response: {result}{Style.RESET_ALL}")
            return None
        
        # Clean up vendor name - remove spaces and special characters
        vendor = re.sub(r'[^A-Za-z0-9]', '', result['vendor'])
        invoice_number = result['invoice_number']
        
        # Create new filename with convention: [HotelCode]_Vendor_InvoiceNumber.pdf
        new_filename = f"{self.hotel_code}_{vendor}_{invoice_number}.pdf"
        output_path = self.output_dir / new_filename
        
        # Copy file to output directory with new name
        import shutil
        shutil.copy2(pdf_path, output_path)
        
        print(f"{Fore.GREEN}Saved invoice as {new_filename}{Style.RESET_ALL}")
        
        return {
            "original_path": pdf_path,
            "new_path": output_path,
            "vendor": vendor,
            "invoice_number": invoice_number,
            "filename": new_filename
        }
    
    def encode_image(self, image):
        """Encode a PIL image to base64 string"""
        buffered = io.BytesIO()
        image.save(buffered, format="JPEG")
        return base64.b64encode(buffered.getvalue()).decode('utf-8')
    
    def extract_info_with_llm(self, image):
        """Extract invoice information using a vision-capable LLM"""
        
        if self.model.startswith("gpt"):
            return self.extract_with_openai(image)
        elif self.model.startswith("claude"):
            return self.extract_with_anthropic(image)
        else:
            raise ValueError(f"Unsupported model: {self.model}")
    
    def extract_with_openai(self, image):
        """Extract information using OpenAI's API"""
        base64_image = self.encode_image(image)
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.openai_api_key}"
        }
        
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are an invoice processing assistant. Extract the vendor name and invoice number from the invoice image."
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Extract the following information from this invoice:\n1. Vendor/Company Name\n2. Invoice Number\n\nRespond with a JSON object with keys 'vendor' and 'invoice_number'."
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            }
                        }
                    ]
                }
            ],
            "max_tokens": 300
        }
        
        response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
        response.raise_for_status()
        
        result = response.json()
        content = result['choices'][0]['message']['content']
        
        # Extract JSON from the response
        try:
            # Try to parse the entire content as JSON
            return json.loads(content)
        except json.JSONDecodeError:
            # If that fails, try to extract JSON from the text
            json_match = re.search(r'```json\s*(.*?)\s*```', content, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(1))
            
            # If still no JSON, try to extract the information manually
            vendor_match = re.search(r'"vendor"\s*:\s*"([^"]+)"', content)
            invoice_match = re.search(r'"invoice_number"\s*:\s*"([^"]+)"', content)
            
            return {
                "vendor": vendor_match.group(1) if vendor_match else None,
                "invoice_number": invoice_match.group(1) if invoice_match else None
            }
    
    def extract_with_anthropic(self, image):
        """Extract information using Anthropic's API"""
        base64_image = self.encode_image(image)
        
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.anthropic_api_key,
            "anthropic-version": "2023-06-01"
        }
        
        payload = {
            "model": self.model,
            "max_tokens": 300,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Extract the following information from this invoice:\n1. Vendor/Company Name\n2. Invoice Number\n\nRespond with a JSON object with keys 'vendor' and 'invoice_number'."
                        },
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/jpeg",
                                "data": base64_image
                            }
                        }
                    ]
                }
            ]
        }
        
        response = requests.post("https://api.anthropic.com/v1/messages", headers=headers, json=payload)
        response.raise_for_status()
        
        result = response.json()
        content = result['content'][0]['text']
        
        # Extract JSON from the response
        try:
            # Try to parse the entire content as JSON
            return json.loads(content)
        except json.JSONDecodeError:
            # If that fails, try to extract JSON from the text
            json_match = re.search(r'```json\s*(.*?)\s*```', content, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(1))
            
            # If still no JSON, try to extract the information manually
            vendor_match = re.search(r'"vendor"\s*:\s*"([^"]+)"', content)
            invoice_match = re.search(r'"invoice_number"\s*:\s*"([^"]+)"', content)
            
            return {
                "vendor": vendor_match.group(1) if vendor_match else None,
                "invoice_number": invoice_match.group(1) if invoice_match else None
            }

def display_banner():
    """Display a colorful banner for the tool"""
    print(f"""
{Fore.CYAN}╔════════════════════════════════════════════════════════════╗
║                                                            ║
║  {Fore.YELLOW}█ █▄░█ █░█ █▀█ █ █▀▀ █▀▀   █▀█ █▀█ █▀█ █▀▀ █▀▀ █▀ █▀ █▀█ █▀█{Fore.CYAN}  ║
║  {Fore.YELLOW}█ █░▀█ ▀▄▀ █▄█ █ █▄▄ ██▄   █▀▀ █▀▄ █▄█ █▄▄ ██▄ ▄█ ▄█ █▄█ █▀▄{Fore.CYAN}  ║
║                                                            ║
║  STLMO Invoice Processing System                           ║
║  Powered by Vision AI                                      ║
╚════════════════════════════════════════════════════════════╝{Style.RESET_ALL}
""")

def interactive_mode():
    """Run the tool in interactive mode with a nice CLI interface"""
    display_banner()
    
    # Step 1: Select input directory
    print(f"{Fore.YELLOW}Step 1: Select the directory containing your invoices{Style.RESET_ALL}")
    default_input = './invoices'
    input_dir = input(f"Input directory [{default_input}]: ").strip() or default_input
    
    # Create input directory if it doesn't exist
    input_path = Path(input_dir)
    if not input_path.exists():
        print(f"Creating input directory: {input_dir}")
        input_path.mkdir(parents=True)
    
    # Step 2: Select output directory
    print(f"\n{Fore.YELLOW}Step 2: Select where to save processed invoices{Style.RESET_ALL}")
    default_output = './processed_invoices'
    output_dir = input(f"Output directory [{default_output}]: ").strip() or default_output
    
    # Step 3: Select hotel code
    print(f"\n{Fore.YELLOW}Step 3: Select the hotel code for file naming{Style.RESET_ALL}")
    print(f"{Fore.CYAN}Available hotel codes:{Style.RESET_ALL}")
    hotel_codes = [
        ("1", "STLMO", "St. Louis, Missouri"),
        ("2", "BHMCO", "Birmingham, Colorado"),
        ("3", "BTRGI", "Baton Rouge, Georgia"),
        ("4", "custom", "Enter a custom code")
    ]
    
    for num, code, desc in hotel_codes:
        print(f"  {Fore.GREEN}{num}{Style.RESET_ALL}. {code} - {desc}")
    
    hotel_choice = input(f"Choose a hotel code [1]: ").strip() or "1"
    hotel_dict = {num: code for num, code, _ in hotel_codes}
    
    if hotel_choice == "4":
        hotel_code = input(f"Enter your custom hotel code: ").strip().upper()
    else:
        hotel_code = hotel_dict.get(hotel_choice, "STLMO")
    
    # Step 4: Select LLM model
    print(f"\n{Fore.YELLOW}Step 4: Select the AI model to use{Style.RESET_ALL}")
    print(f"{Fore.CYAN}Available models:{Style.RESET_ALL}")
    models = [
        ("1", "gpt-4o", "OpenAI GPT-4o (Recommended)"),
        ("2", "gpt-4-vision-preview", "OpenAI GPT-4 Vision"),
        ("3", "claude-3-opus-20240229", "Anthropic Claude 3 Opus"),
        ("4", "claude-3-sonnet-20240229", "Anthropic Claude 3 Sonnet"),
        ("5", "claude-3-haiku-20240307", "Anthropic Claude 3 Haiku")
    ]
    
    for num, model_id, desc in models:
        print(f"  {Fore.GREEN}{num}{Style.RESET_ALL}. {model_id} - {desc}")
    
    model_choice = input(f"Choose a model [1]: ").strip() or "1"
    model_dict = {num: model_id for num, model_id, _ in models}
    model = model_dict.get(model_choice, "gpt-4o")
    
    # Step 5: Get API key if needed
    api_key = None
    if model.startswith("gpt") and not os.environ.get('OPENAI_API_KEY'):
        print(f"\n{Fore.YELLOW}Step 5: Enter your OpenAI API key{Style.RESET_ALL}")
        api_key = getpass.getpass("OpenAI API Key: ")
    elif model.startswith("claude") and not os.environ.get('ANTHROPIC_API_KEY'):
        print(f"\n{Fore.YELLOW}Step 5: Enter your Anthropic API key{Style.RESET_ALL}")
        api_key = getpass.getpass("Anthropic API Key: ")
    
    # Final step: Confirm and run
    print(f"\n{Fore.YELLOW}Summary:{Style.RESET_ALL}")
    print(f"  Input directory: {Fore.CYAN}{input_dir}{Style.RESET_ALL}")
    print(f"  Output directory: {Fore.CYAN}{output_dir}{Style.RESET_ALL}")
    print(f"  Hotel code: {Fore.CYAN}{hotel_code}{Style.RESET_ALL}")
    print(f"  Model: {Fore.CYAN}{model}{Style.RESET_ALL}")
    
    confirm = input(f"\n{Fore.GREEN}Start processing? (y/n) [{Fore.GREEN}y{Style.RESET_ALL}]: ").strip().lower() or "y"
    
    if confirm == "y":
        processor = InvoiceProcessor(input_dir, output_dir, model, api_key, hotel_code)
        
        # Start processing
        print(f"\n{Fore.GREEN}Starting invoice processing...{Style.RESET_ALL}")
        processor.process_invoices()
        
        # Display results
        if processor.processed_files:
            print(f"\n{Fore.GREEN}Processing complete! {len(processor.processed_files)} files processed.{Style.RESET_ALL}")
            print(f"\n{Fore.YELLOW}Processed files:{Style.RESET_ALL}")
            
            for i, file_info in enumerate(processor.processed_files, 1):
                print(f"  {i}. {Fore.CYAN}{file_info['filename']}{Style.RESET_ALL}")
                print(f"     Vendor: {file_info['vendor']}")
                print(f"     Invoice #: {file_info['invoice_number']}")
                print()
                
            print(f"All files saved to: {Fore.GREEN}{output_dir}{Style.RESET_ALL}")
        else:
            print(f"\n{Fore.YELLOW}No files were processed. Check that your input directory contains PDF invoices.{Style.RESET_ALL}")
    else:
        print(f"\n{Fore.RED}Operation cancelled by user.{Style.RESET_ALL}")

def main():
    parser = argparse.ArgumentParser(description="Process invoices and rename them according to convention")
    parser.add_argument("--input", help="Directory containing invoice PDFs")
    parser.add_argument("--output", help="Directory to save processed invoices")
    parser.add_argument("--hotel-code", help="Hotel code for naming convention (e.g., STLMO, BHMCO, BTRGI)")
    parser.add_argument("--model", help="Model to use (gpt-4o, claude-3-sonnet-20240229, etc.)")
    parser.add_argument("--api-key", help="API key for the selected model")
    parser.add_argument("--interactive", "-i", action="store_true", help="Run in interactive mode with CLI interface")
    
    args = parser.parse_args()
    
    # Run in interactive mode if no arguments provided or --interactive flag is used
    if args.interactive or (not args.input and not args.output):
        interactive_mode()
    else:
        # Use command-line arguments
        if not args.input or not args.output:
            parser.error("--input and --output are required in non-interactive mode")
        
        hotel_code = args.hotel_code or "STLMO"
        processor = InvoiceProcessor(args.input, args.output, args.model, args.api_key, hotel_code)
        processor.process_invoices()
        
        # Display summary
        if processor.processed_files:
            print(f"\nProcessing complete! {len(processor.processed_files)} files processed.")
            print("\nProcessed files:")
            for file_info in processor.processed_files:
                print(f"  - {file_info['filename']}")

if __name__ == "__main__":
    main()