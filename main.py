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
import tqdm
from concurrent.futures import ThreadPoolExecutor

# Import Mistral OCR processor
try:
    from mistral_ocr import MistralOCRProcessor
    MISTRAL_AVAILABLE = True
except ImportError:
    MISTRAL_AVAILABLE = False

# Initialize colorama for colored terminal output
colorama.init()

class InvoiceProcessor:
    def __init__(self, input_dir, output_dir, model=None, api_key=None, hotel_code="STLMO", 
                 batch_size=None, preview=False, max_workers=4, auto_detect_hotel=False):
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.model = model or "gpt-4o"  # Default to gpt-4o if not specified
        self.hotel_code = hotel_code
        self.processed_files = []
        self.failed_files = []
        self.batch_size = batch_size
        self.preview = preview
        self.max_workers = max_workers
        self.auto_detect_hotel = auto_detect_hotel
        
        # Set API keys based on model
        self.openai_api_key = api_key if self.model and self.model.startswith("gpt") else os.environ.get('OPENAI_API_KEY')
        self.anthropic_api_key = api_key if self.model and self.model.startswith("claude") else os.environ.get('ANTHROPIC_API_KEY')
        self.mistral_api_key = api_key if self.model and self.model.startswith("mistral") else os.environ.get('MISTRAL_API_KEY')
        
        # Initialize Mistral OCR processor if needed
        self.mistral_processor = None
        if self.model.startswith("mistral") and MISTRAL_AVAILABLE:
            self.mistral_processor = MistralOCRProcessor(api_key=self.mistral_api_key)
        
        # Validate API keys
        if self.model.startswith("gpt") and not self.openai_api_key:
            raise ValueError("OpenAI API key is required for GPT models")
        if self.model.startswith("claude") and not self.anthropic_api_key:
            raise ValueError("Anthropic API key is required for Claude models")
        if self.model.startswith("mistral") and not self.mistral_api_key:
            raise ValueError("Mistral API key is required for Mistral models")
        
        # Create output directory if it doesn't exist
        if not self.output_dir.exists():
            self.output_dir.mkdir(parents=True)
    
    def process_invoices(self):
        """Process all PDF invoices in the input directory"""
        pdf_files = list(self.input_dir.glob("*.pdf"))
        
        if not pdf_files:
            print(f"{Fore.YELLOW}No PDF files found in {self.input_dir}{Style.RESET_ALL}")
            return
        
        # Determine if we should use batch processing or not
        if self.batch_size and self.batch_size < len(pdf_files):
            batches = [pdf_files[i:i + self.batch_size] for i in range(0, len(pdf_files), self.batch_size)]
            print(f"{Fore.GREEN}Found {len(pdf_files)} PDF files to process in {len(batches)} batches{Style.RESET_ALL}")
            
            for batch_num, batch in enumerate(batches, 1):
                print(f"{Fore.CYAN}Processing batch {batch_num}/{len(batches)} ({len(batch)} files)...{Style.RESET_ALL}")
                self._process_batch(batch)
                
                if batch_num < len(batches):
                    print(f"{Fore.YELLOW}Batch {batch_num} complete. Waiting 5 seconds before next batch...{Style.RESET_ALL}")
                    time.sleep(5)
        else:
            print(f"{Fore.GREEN}Found {len(pdf_files)} PDF files to process{Style.RESET_ALL}")
            self._process_batch(pdf_files)
            
        # Final summary
        if self.failed_files:
            print(f"\n{Fore.RED}Failed to process {len(self.failed_files)} files:{Style.RESET_ALL}")
            for failed in self.failed_files:
                print(f"  - {failed['file'].name}: {failed['error']}")
    
    def _process_batch(self, files):
        """Process a batch of files, with optional parallel processing"""
        if self.max_workers > 1 and len(files) > 1:
            # Parallel processing
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                results = list(tqdm.tqdm(
                    executor.map(self._process_file_wrapper, files),
                    total=len(files),
                    desc="Processing invoices",
                    unit="file"
                ))
        else:
            # Sequential processing
            results = []
            for pdf_file in tqdm.tqdm(files, desc="Processing invoices", unit="file"):
                results.append(self._process_file_wrapper(pdf_file))
                
        # Add successful results to processed_files
        for result in results:
            if result and 'success' in result and result['success']:
                self.processed_files.append(result)
    
    def _process_file_wrapper(self, pdf_file):
        """Wrapper for process_invoice to handle exceptions"""
        try:
            return self.process_invoice(pdf_file)
        except Exception as e:
            error_msg = str(e)
            self.failed_files.append({
                'file': pdf_file,
                'error': error_msg
            })
            return {
                'success': False,
                'original_path': pdf_file,
                'error': error_msg
            }
    
    def process_invoice(self, pdf_path):
        """Process a single invoice PDF"""
        # Convert PDF to images
        pages = convert_from_path(pdf_path)
        
        # Use only the first page for analysis (usually contains invoice info)
        first_page = pages[0]
        
        # Extract information using vision-capable LLM
        result = self.extract_info_with_llm(first_page)
        
        if not result.get('vendor') or not result.get('invoice_number'):
            error_msg = f"Could not extract vendor or invoice number from {pdf_path.name}"
            raise ValueError(error_msg)
        
        # Clean up vendor name - remove spaces and special characters
        vendor = re.sub(r'[^A-Za-z0-9]', '', result['vendor'])
        invoice_number = re.sub(r'[^A-Za-z0-9\-_]', '', result['invoice_number'])  # Allow hyphens and underscores in invoice numbers
        
        # Use detected hotel code if available and auto-detection is enabled
        hotel_code = self.hotel_code
        if result.get('detected_hotel_code') and self.auto_detect_hotel:
            hotel_code = result['detected_hotel_code']
        
        # Create new filename with convention: [HotelCode]_Vendor_InvoiceNumber.pdf
        new_filename = f"{hotel_code}_{vendor}_{invoice_number}.pdf"
        output_path = self.output_dir / new_filename
        
        # In preview mode, just return the info without copying the file
        if self.preview:
            return {
                "success": True,
                "original_path": pdf_path,
                "new_path": output_path,
                "vendor": vendor,
                "invoice_number": invoice_number,
                "filename": new_filename,
                "hotel_location": result.get('hotel_location'),
                "detected_hotel_code": result.get('detected_hotel_code'),
                "used_hotel_code": hotel_code,
                "preview_only": True
            }
        
        # Copy file to output directory with new name
        import shutil
        shutil.copy2(pdf_path, output_path)
        
        return {
            "success": True,
            "original_path": pdf_path,
            "new_path": output_path,
            "vendor": vendor,
            "invoice_number": invoice_number,
            "filename": new_filename,
            "hotel_location": result.get('hotel_location'),
            "detected_hotel_code": result.get('detected_hotel_code'),
            "used_hotel_code": hotel_code
        }
    
    def encode_image(self, image):
        """Encode a PIL image to base64 string"""
        buffered = io.BytesIO()
        image.save(buffered, format="JPEG")
        return base64.b64encode(buffered.getvalue()).decode('utf-8')
    
    def extract_info_with_llm(self, image):
        """Extract invoice information using a vision-capable LLM"""
        
        # Maximum retry attempts for API calls
        max_retries = 3
        retry_delay = 2
        
        for attempt in range(max_retries):
            try:
                if self.model.startswith("gpt"):
                    return self.extract_with_openai(image)
                elif self.model.startswith("claude"):
                    return self.extract_with_anthropic(image)
                elif self.model.startswith("mistral") and self.mistral_processor:
                    return self.extract_with_mistral(image)
                else:
                    raise ValueError(f"Unsupported model: {self.model}")
            except requests.exceptions.RequestException as e:
                if attempt < max_retries - 1:
                    # Wait with exponential backoff
                    wait_time = retry_delay * (2 ** attempt)
                    print(f"{Fore.YELLOW}API call failed. Retrying in {wait_time} seconds...{Style.RESET_ALL}")
                    time.sleep(wait_time)
                else:
                    # Last attempt failed
                    raise ValueError(f"API call failed after {max_retries} attempts: {str(e)}")
    
    def extract_with_openai(self, image):
        """Extract information using OpenAI's API"""
        base64_image = self.encode_image(image)
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.openai_api_key}"
        }
        
        # Define the location mapping
        location_to_hotel_code = {
            "St. Louis, Missouri": "STLMO",
            "St. Louis, MO": "STLMO",
            "Saint Louis, Missouri": "STLMO",
            "Saint Louis, MO": "STLMO",
            "Birmingham, AL": "BHMCO",
            "Birmingham, Alabama": "BHMCO",
            "Baton Rouge, LA": "BTRGI",
            "Baton Rouge, Louisiana": "BTRGI",
            "Coralville, IA": None  # This will be handled by company name
        }
        
        # Special company name mapping for Coralville address
        company_to_hotel_code = {
            "Cast Iron Lodging": "BHMCO",
            "Saint Pine Lodging": "STLMO",
            "Hotel Majestic": "STLMO",
            "Red Stick Lodging": "BTRGI"
        }
        
        # Add hotel code detection to the prompt
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": """You are an invoice processing assistant. Extract information from invoice images.
                    
The vendor name is the company that issued the invoice. The invoice number is a unique identifier for this specific invoice.

Pay special attention to any hotel or location information in the invoice. Look for addresses, letterheads, or location references that might indicate which hotel this invoice is for. Common locations are:
- St. Louis, Missouri (or MO)
- Birmingham, Alabama (or AL)
- Baton Rouge, Louisiana (or LA)
- Coralville, Iowa (or IA) - look for address: 2706 James St. Coralville, IA

If the address mentions Coralville, IA, look for these company names:
- Cast Iron Lodging (code for Birmingham)
- Saint Pine Lodging or Hotel Majestic (code for St. Louis)
- Red Stick Lodging (code for Baton Rouge)

If you find a matching location or company, include it in your response."""
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": """Extract the following information from this invoice:
1. Vendor/Company Name: The name of the company that issued the invoice
2. Invoice Number: The unique identifier for this invoice
3. Hotel Location: If present, identify which hotel location this invoice is from (St. Louis, Birmingham, Baton Rouge, or Coralville)
4. Hotel Company: If the Coralville, IA address appears, identify which company name is associated with it (Cast Iron Lodging, Saint Pine Lodging, Hotel Majestic, or Red Stick Lodging)

Respond ONLY with a valid JSON object with keys 'vendor', 'invoice_number', 'hotel_location', and 'hotel_company' (if found). If any field is not clearly identifiable, set its value to null. Do not include explanations or any other text outside the JSON."""
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
        
        parsed_result = self._parse_llm_response(content)
        
        # Check if hotel_location is present and map it to hotel code
        if 'hotel_location' in parsed_result and parsed_result['hotel_location']:
            # Create a simplified version of the location text for better matching
            location_text = parsed_result['hotel_location'].lower()
            
            # Simple city name matching for common cases
            if 'birmingham' in location_text:
                parsed_result['detected_hotel_code'] = "BHMCO"
                parsed_result['matched_location'] = "Birmingham, AL"
            elif 'louis' in location_text or 'stl' in location_text:
                parsed_result['detected_hotel_code'] = "STLMO"
                parsed_result['matched_location'] = "St. Louis, MO"
            elif 'baton' in location_text or 'rouge' in location_text:
                parsed_result['detected_hotel_code'] = "BTRGI"
                parsed_result['matched_location'] = "Baton Rouge, LA"
            else:
                # More specific matching if simple matching fails
                for location, code in location_to_hotel_code.items():
                    if location.lower() in location_text:
                        parsed_result['detected_hotel_code'] = code
                        parsed_result['matched_location'] = location
                        break
            
            # Handle Coralville, IA special case with company name mapping
            if 'coralville' in location_text and 'hotel_company' in parsed_result and parsed_result['hotel_company']:
                for company, code in company_to_hotel_code.items():
                    if company.lower() in parsed_result['hotel_company'].lower():
                        parsed_result['detected_hotel_code'] = code
                        parsed_result['company_match'] = company
                        parsed_result['matched_location'] = f"Coralville, IA ({company})"
                        break
        
        return parsed_result
    
    def extract_with_anthropic(self, image):
        """Extract information using Anthropic's API"""
        base64_image = self.encode_image(image)
        
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.anthropic_api_key,
            "anthropic-version": "2023-06-01"
        }
        
        # Define the location mapping
        location_to_hotel_code = {
            "St. Louis, Missouri": "STLMO",
            "St. Louis, MO": "STLMO",
            "Saint Louis, Missouri": "STLMO",
            "Saint Louis, MO": "STLMO",
            "Birmingham, AL": "BHMCO",
            "Birmingham, Alabama": "BHMCO",
            "Baton Rouge, LA": "BTRGI",
            "Baton Rouge, Louisiana": "BTRGI",
            "Coralville, IA": None  # This will be handled by company name
        }
        
        # Special company name mapping for Coralville address
        company_to_hotel_code = {
            "Cast Iron Lodging": "BHMCO",
            "Saint Pine Lodging": "STLMO",
            "Hotel Majestic": "STLMO",
            "Red Stick Lodging": "BTRGI"
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
                            "text": """Extract the following information from this invoice:
1. Vendor/Company Name: The name of the company that issued the invoice
2. Invoice Number: The unique identifier for this invoice
3. Hotel Location: If present, identify which hotel location this invoice is from (St. Louis, Birmingham, Baton Rouge, or Coralville)
4. Hotel Company: If the Coralville, IA address appears, identify which company name is associated with it (Cast Iron Lodging, Saint Pine Lodging, Hotel Majestic, or Red Stick Lodging)

Pay special attention to any hotel or location information in the invoice. Look for addresses, letterheads, or location references that might indicate which hotel this invoice is for. Common locations are:
- St. Louis, Missouri (or MO)
- Birmingham, Alabama (or AL)
- Baton Rouge, Louisiana (or LA)
- Coralville, Iowa (or IA) - look for address: 2706 James St. Coralville, IA

If the address mentions Coralville, IA, look for these company names:
- Cast Iron Lodging (code for Birmingham)
- Saint Pine Lodging or Hotel Majestic (code for St. Louis)
- Red Stick Lodging (code for Baton Rouge)

Respond ONLY with a valid JSON object with keys 'vendor', 'invoice_number', 'hotel_location', and 'hotel_company' (if found). If any field is not clearly identifiable, set its value to null. Do not include explanations or any other text outside the JSON."""
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
        
        parsed_result = self._parse_llm_response(content)
        
        # Check if hotel_location is present and map it to hotel code
        if 'hotel_location' in parsed_result and parsed_result['hotel_location']:
            # Create a simplified version of the location text for better matching
            location_text = parsed_result['hotel_location'].lower()
            
            # Simple city name matching for common cases
            if 'birmingham' in location_text:
                parsed_result['detected_hotel_code'] = "BHMCO"
                parsed_result['matched_location'] = "Birmingham, AL"
            elif 'louis' in location_text or 'stl' in location_text:
                parsed_result['detected_hotel_code'] = "STLMO"
                parsed_result['matched_location'] = "St. Louis, MO"
            elif 'baton' in location_text or 'rouge' in location_text:
                parsed_result['detected_hotel_code'] = "BTRGI"
                parsed_result['matched_location'] = "Baton Rouge, LA"
            else:
                # More specific matching if simple matching fails
                for location, code in location_to_hotel_code.items():
                    if location.lower() in location_text:
                        parsed_result['detected_hotel_code'] = code
                        parsed_result['matched_location'] = location
                        break
            
            # Handle Coralville, IA special case with company name mapping
            if 'coralville' in location_text and 'hotel_company' in parsed_result and parsed_result['hotel_company']:
                for company, code in company_to_hotel_code.items():
                    if company.lower() in parsed_result['hotel_company'].lower():
                        parsed_result['detected_hotel_code'] = code
                        parsed_result['company_match'] = company
                        parsed_result['matched_location'] = f"Coralville, IA ({company})"
                        break
        
        return parsed_result
        
    def extract_with_mistral(self, image):
        """Extract information using Mistral's OCR and document understanding capabilities"""
        try:
            # Use the MistralOCRProcessor to extract information
            result = self.mistral_processor.extract_info(image)
            return result
        except Exception as e:
            raise ValueError(f"Mistral OCR processing failed: {str(e)}")
        
    def _parse_llm_response(self, content):
        """Parse the response from the LLM and extract JSON data"""
        # Try different parsing strategies in order of preference
        
        # 1. Try to parse the entire content as JSON
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass
            
        # 2. Try to extract JSON from code blocks
        json_match = re.search(r'```(?:json)?\s*(.*?)\s*```', content, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass
                
        # 3. Try to extract JSON without code blocks (may have JSON without formatting)
        json_match = re.search(r'(\{.*\})', content, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass
        
        # 4. If all parsing fails, try to extract fields directly
        vendor_match = re.search(r'"vendor"\s*:\s*"([^"]+)"', content)
        invoice_match = re.search(r'"invoice_number"\s*:\s*"([^"]+)"', content)
        
        if vendor_match and invoice_match:
            return {
                "vendor": vendor_match.group(1),
                "invoice_number": invoice_match.group(1)
            }
            
        # 5. Look for the fields in natural language format
        vendor_nl_match = re.search(r'vendor(?:\s*name)?[:\s]+([^\n,]+)', content, re.IGNORECASE)
        invoice_nl_match = re.search(r'invoice\s+number[:\s]+([^\n,]+)', content, re.IGNORECASE)
        
        return {
            "vendor": vendor_nl_match.group(1).strip() if vendor_nl_match else None,
            "invoice_number": invoice_nl_match.group(1).strip() if invoice_nl_match else None
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
    
    # Step 3: Hotel code options
    print(f"\n{Fore.YELLOW}Step 3: Hotel code options{Style.RESET_ALL}")
    auto_detect = input(f"Auto-detect hotel location from invoices? (y/n) [n]: ").strip().lower() == "y"
    
    hotel_code = "STLMO"  # Default
    if not auto_detect:
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
    else:
        print(f"{Fore.CYAN}Using auto-detection of hotel location from invoice content{Style.RESET_ALL}")
        print(f"Fallback hotel code if detection fails: {Fore.CYAN}STLMO{Style.RESET_ALL}")
    
    # Step 4: Advanced options
    print(f"\n{Fore.YELLOW}Step 4: Advanced options{Style.RESET_ALL}")
    preview_mode = input(f"Preview mode (don't actually rename files)? (y/n) [n]: ").strip().lower() == "y"
    
    batch_size_input = input(f"Batch size (leave empty for all at once): ").strip()
    batch_size = int(batch_size_input) if batch_size_input.isdigit() else None
    
    parallel_input = input(f"Number of parallel workers (1-8) [1]: ").strip()
    max_workers = max(1, min(8, int(parallel_input))) if parallel_input.isdigit() else 1
    
    # Step 5: Select LLM model
    print(f"\n{Fore.YELLOW}Step 5: Select the AI model to use{Style.RESET_ALL}")
    print(f"{Fore.CYAN}Available models:{Style.RESET_ALL}")
    models = [
        ("1", "gpt-4o", "OpenAI GPT-4o (Recommended)"),
        ("2", "gpt-4-vision-preview", "OpenAI GPT-4 Vision"),
        ("3", "claude-3-opus-20240229", "Anthropic Claude 3 Opus"),
        ("4", "claude-3-sonnet-20240229", "Anthropic Claude 3 Sonnet"),
        ("5", "claude-3-haiku-20240307", "Anthropic Claude 3 Haiku")
    ]
    
    # Add Mistral models if available
    if MISTRAL_AVAILABLE:
        models.extend([
            ("6", "mistral-large-2402", "Mistral Large (OCR-optimized)"),
            ("7", "mistral-medium-2312", "Mistral Medium (OCR-optimized)")
        ])
    
    for num, model_id, desc in models:
        print(f"  {Fore.GREEN}{num}{Style.RESET_ALL}. {model_id} - {desc}")
    
    model_choice = input(f"Choose a model [1]: ").strip() or "1"
    model_dict = {num: model_id for num, model_id, _ in models}
    model = model_dict.get(model_choice, "gpt-4o")
    
    # Step 6: Get API key if needed
    api_key = None
    if model.startswith("gpt") and not os.environ.get('OPENAI_API_KEY'):
        print(f"\n{Fore.YELLOW}Step 6: Enter your OpenAI API key{Style.RESET_ALL}")
        api_key = getpass.getpass("OpenAI API Key: ")
    elif model.startswith("claude") and not os.environ.get('ANTHROPIC_API_KEY'):
        print(f"\n{Fore.YELLOW}Step 6: Enter your Anthropic API key{Style.RESET_ALL}")
        api_key = getpass.getpass("Anthropic API Key: ")
    elif model.startswith("mistral") and not os.environ.get('MISTRAL_API_KEY'):
        print(f"\n{Fore.YELLOW}Step 6: Enter your Mistral API key{Style.RESET_ALL}")
        api_key = getpass.getpass("Mistral API Key: ")
    
    # Final step: Confirm and run
    print(f"\n{Fore.YELLOW}Summary:{Style.RESET_ALL}")
    print(f"  Input directory: {Fore.CYAN}{input_dir}{Style.RESET_ALL}")
    print(f"  Output directory: {Fore.CYAN}{output_dir}{Style.RESET_ALL}")
    if auto_detect:
        print(f"  Hotel code: {Fore.CYAN}Auto-detect (fallback: STLMO){Style.RESET_ALL}")
    else:
        print(f"  Hotel code: {Fore.CYAN}{hotel_code}{Style.RESET_ALL}")
    print(f"  Model: {Fore.CYAN}{model}{Style.RESET_ALL}")
    print(f"  Preview mode: {Fore.CYAN}{'On' if preview_mode else 'Off'}{Style.RESET_ALL}")
    if batch_size:
        print(f"  Batch size: {Fore.CYAN}{batch_size}{Style.RESET_ALL}")
    if max_workers > 1:
        print(f"  Parallel workers: {Fore.CYAN}{max_workers}{Style.RESET_ALL}")
    
    confirm = input(f"\n{Fore.GREEN}Start processing? (y/n) [{Fore.GREEN}y{Style.RESET_ALL}]: ").strip().lower() or "y"
    
    if confirm == "y":
        try:
            processor = InvoiceProcessor(
                input_dir, 
                output_dir, 
                model, 
                api_key, 
                hotel_code,
                batch_size=batch_size,
                preview=preview_mode,
                max_workers=max_workers,
                auto_detect_hotel=auto_detect
            )
            
            # Start processing
            print(f"\n{Fore.GREEN}Starting invoice processing...{Style.RESET_ALL}")
            processor.process_invoices()
            
            # Display results
            if processor.processed_files:
                print(f"\n{Fore.GREEN}Processing complete! {len(processor.processed_files)} files processed.{Style.RESET_ALL}")
                print(f"\n{Fore.YELLOW}Processed files:{Style.RESET_ALL}")
                
                for i, file_info in enumerate(processor.processed_files, 1):
                    preview_tag = f" {Fore.YELLOW}[PREVIEW]{Style.RESET_ALL}" if file_info.get('preview_only') else ""
                    print(f"  {i}. {Fore.CYAN}{file_info['filename']}{preview_tag}{Style.RESET_ALL}")
                    print(f"     Vendor: {file_info['vendor']}")
                    print(f"     Invoice #: {file_info['invoice_number']}")
                    
                    # Show hotel location info if available
                    if file_info.get('hotel_location'):
                        hotel_detected = f"{Fore.GREEN}Yes{Style.RESET_ALL}" if file_info.get('detected_hotel_code') else f"{Fore.RED}No{Style.RESET_ALL}"
                        print(f"     Hotel location: {file_info['hotel_location']}")
                        
                        if file_info.get('matched_location'):
                            print(f"     Matched to: {Fore.GREEN}{file_info['matched_location']}{Style.RESET_ALL}")
                        
                        if file_info.get('hotel_company'):
                            print(f"     Hotel company: {file_info['hotel_company']}")
                            
                        if file_info.get('company_match'):
                            print(f"     Company matched: {Fore.GREEN}{file_info['company_match']}{Style.RESET_ALL}")
                            
                        print(f"     Auto-detected: {hotel_detected}")
                        if file_info.get('detected_hotel_code'):
                            print(f"     Used hotel code: {Fore.CYAN}{file_info['used_hotel_code']}{Style.RESET_ALL}")
                    
                    print()
                
                if not preview_mode:
                    print(f"All files saved to: {Fore.GREEN}{output_dir}{Style.RESET_ALL}")
                else:
                    print(f"{Fore.YELLOW}Preview mode: No files were actually moved or renamed.{Style.RESET_ALL}")
            else:
                print(f"\n{Fore.YELLOW}No files were processed. Check that your input directory contains PDF invoices.{Style.RESET_ALL}")
                
            # Display failed files if any
            if processor.failed_files:
                print(f"\n{Fore.RED}Failed to process {len(processor.failed_files)} files:{Style.RESET_ALL}")
                for i, failed in enumerate(processor.failed_files, 1):
                    print(f"  {i}. {failed['file'].name}: {failed['error']}")
        except Exception as e:
            print(f"\n{Fore.RED}Error: {str(e)}{Style.RESET_ALL}")
    else:
        print(f"\n{Fore.RED}Operation cancelled by user.{Style.RESET_ALL}")

def main():
    parser = argparse.ArgumentParser(description="Process invoices and rename them according to convention")
    parser.add_argument("--input", help="Directory containing invoice PDFs")
    parser.add_argument("--output", help="Directory to save processed invoices")
    parser.add_argument("--hotel-code", help="Hotel code for naming convention (e.g., STLMO, BHMCO, BTRGI)")
    parser.add_argument("--model", help="Model to use (gpt-4o, claude-3-sonnet-20240229, mistral-large-latest, etc.)")
    parser.add_argument("--api-key", help="API key for the selected model")
    parser.add_argument("--interactive", "-i", action="store_true", help="Run in interactive mode with CLI interface")
    parser.add_argument("--preview", action="store_true", help="Preview mode - don't actually rename files")
    parser.add_argument("--batch-size", type=int, help="Process files in batches of this size")
    parser.add_argument("--workers", type=int, default=1, help="Number of parallel workers (1-8)")
    parser.add_argument("--auto-detect", action="store_true", help="Auto-detect hotel location from invoice content")
    parser.add_argument("--version", "-v", action="store_true", help="Show version information")
    
    args = parser.parse_args()
    
    # Show version info
    if args.version:
        print(f"Invoice Processor v1.3.0")
        print(f"Vision AI-powered invoice processing tool")
        print(f"Supports OpenAI, Anthropic, and Mistral OCR")
        return
    
    # Run in interactive mode if no arguments provided or --interactive flag is used
    if args.interactive or (not args.input and not args.output):
        interactive_mode()
    else:
        # Use command-line arguments
        if not args.input or not args.output:
            parser.error("--input and --output are required in non-interactive mode")
        
        hotel_code = args.hotel_code or "STLMO"
        max_workers = max(1, min(8, args.workers))
        
        try:
            processor = InvoiceProcessor(
                args.input, 
                args.output, 
                args.model, 
                args.api_key, 
                hotel_code,
                batch_size=args.batch_size,
                preview=args.preview,
                max_workers=max_workers,
                auto_detect_hotel=args.auto_detect
            )
            
            processor.process_invoices()
            
            # Display results
            if processor.processed_files:
                print(f"\nProcessing complete! {len(processor.processed_files)} files processed.")
                print("\nProcessed files:")
                for i, file_info in enumerate(processor.processed_files, 1):
                    preview_tag = " [PREVIEW]" if file_info.get('preview_only') else ""
                    print(f"  {i}. {file_info['filename']}{preview_tag}")
                    
                    # Show detected location/company info if available
                    if file_info.get('hotel_location'):
                        print(f"     Location: {file_info['hotel_location']}")
                        
                    if file_info.get('matched_location'):
                        print(f"     Matched to: {file_info['matched_location']}")
                    
                    if file_info.get('hotel_company'):
                        print(f"     Company: {file_info['hotel_company']}")
                        
                    if file_info.get('company_match'):
                        print(f"     Company matched: {file_info['company_match']}")
                        
                    if file_info.get('detected_hotel_code'):
                        print(f"     Used hotel code: {file_info['used_hotel_code']}")
                    
                    print()
                    
                if args.preview:
                    print("\nPreview mode: No files were actually moved or renamed.")
            else:
                print("\nNo files were processed. Check that your input directory contains PDF invoices.")
                
            # Display failed files if any
            if processor.failed_files:
                print(f"\nFailed to process {len(processor.failed_files)} files:")
                for failed in processor.failed_files:
                    print(f"  - {failed['file'].name}: {failed['error']}")
        except Exception as e:
            print(f"\nError: {str(e)}")
            sys.exit(1)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
        sys.exit(0)