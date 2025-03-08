#!/usr/bin/env python3
import os
import base64
import io
import json
import re
from pathlib import Path
import requests
from PIL import Image
from colorama import Fore, Style
import time

class MistralOCRProcessor:
    """
    Implementation of OCR processing using Mistral AI.
    This class handles the document analysis and text extraction from PDFs.
    """
    
    def __init__(self, api_key=None):
        """Initialize the Mistral OCR processor with API key."""
        self.api_key = api_key or os.environ.get('MISTRAL_API_KEY')
        if not self.api_key:
            raise ValueError("Mistral API key is required")
        
        self.base_url = "https://api.mistral.ai/v1"
        self.default_model = "mistral-large-latest"  # Model with vision capabilities
        
        # Define the location mapping for hotel code detection
        self.location_to_hotel_code = {
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
        self.company_to_hotel_code = {
            "Cast Iron Lodging": "BHMCO",
            "Saint Pine Lodging": "STLMO",
            "Hotel Majestic": "STLMO",
            "Red Stick Lodging": "BTRGI"
        }
    
    def encode_image(self, image):
        """Encode a PIL image to base64 string."""
        buffered = io.BytesIO()
        image.save(buffered, format="JPEG")
        return base64.b64encode(buffered.getvalue()).decode('utf-8')
    
    def extract_info(self, image, max_retries=3, retry_delay=2):
        """Extract invoice information using Mistral's OCR capabilities."""
        for attempt in range(max_retries):
            try:
                # Convert PIL image to base64
                base64_image = self.encode_image(image)
                
                # Call the Mistral API to extract information
                result = self._call_mistral_api(base64_image)
                
                # Map the hotel location to hotel code if available
                if 'hotel_location' in result and result['hotel_location']:
                    self._map_location_to_hotel_code(result)
                
                return result
                
            except requests.exceptions.RequestException as e:
                if attempt < max_retries - 1:
                    # Wait with exponential backoff
                    wait_time = retry_delay * (2 ** attempt)
                    print(f"{Fore.YELLOW}API call failed. Retrying in {wait_time} seconds...{Style.RESET_ALL}")
                    time.sleep(wait_time)
                else:
                    # Last attempt failed
                    raise ValueError(f"Mistral API call failed after {max_retries} attempts: {str(e)}")
    
    def _call_mistral_api(self, base64_image):
        """Call the Mistral API to extract information from the image."""
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        payload = {
            "model": self.default_model,
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
        
        response = requests.post(f"{self.base_url}/chat/completions", headers=headers, json=payload)
        response.raise_for_status()
        
        content = response.json()['choices'][0]['message']['content']
        return self._parse_llm_response(content)
    
    def _parse_llm_response(self, content):
        """Parse the response from the LLM and extract JSON data."""
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
    
    def _map_location_to_hotel_code(self, result):
        """Map hotel location to hotel code."""
        # Create a simplified version of the location text for better matching
        location_text = result['hotel_location'].lower()
        
        # Simple city name matching for common cases
        if 'birmingham' in location_text:
            result['detected_hotel_code'] = "BHMCO"
            result['matched_location'] = "Birmingham, AL"
        elif 'louis' in location_text or 'stl' in location_text:
            result['detected_hotel_code'] = "STLMO"
            result['matched_location'] = "St. Louis, MO"
        elif 'baton' in location_text or 'rouge' in location_text:
            result['detected_hotel_code'] = "BTRGI"
            result['matched_location'] = "Baton Rouge, LA"
        else:
            # More specific matching if simple matching fails
            for location, code in self.location_to_hotel_code.items():
                if location.lower() in location_text:
                    result['detected_hotel_code'] = code
                    result['matched_location'] = location
                    break
        
        # Handle Coralville, IA special case with company name mapping
        if 'coralville' in location_text and 'hotel_company' in result and result['hotel_company']:
            for company, code in self.company_to_hotel_code.items():
                if company.lower() in result['hotel_company'].lower():
                    result['detected_hotel_code'] = code
                    result['company_match'] = company
                    result['matched_location'] = f"Coralville, IA ({company})"
                    break

    def process_batch(self, image_paths, max_workers=1):
        """
        Process a batch of images in parallel.
        
        Args:
            image_paths: List of paths to images to process
            max_workers: Number of parallel workers
            
        Returns:
            List of extracted information for each image
        """
        from concurrent.futures import ThreadPoolExecutor
        import tqdm
        
        if max_workers > 1 and len(image_paths) > 1:
            # Parallel processing
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                results = list(tqdm.tqdm(
                    executor.map(self._process_single_image, image_paths),
                    total=len(image_paths),
                    desc="Processing with Mistral OCR",
                    unit="image"
                ))
        else:
            # Sequential processing
            results = []
            for image_path in tqdm.tqdm(image_paths, desc="Processing with Mistral OCR", unit="image"):
                results.append(self._process_single_image(image_path))
                
        return results
    
    def _process_single_image(self, image_path):
        """Process a single image and extract information."""
        try:
            image = Image.open(image_path)
            return {
                'path': image_path,
                'result': self.extract_info(image),
                'success': True
            }
        except Exception as e:
            return {
                'path': image_path,
                'error': str(e),
                'success': False
            }