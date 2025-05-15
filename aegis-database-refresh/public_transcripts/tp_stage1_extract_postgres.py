# -*- coding: utf-8 -*-
"""
Stage 1: Extract & Compare - PostgreSQL Catalog vs. NAS Filesystem for Transcripts

This script performs the first stage of a transcript processing pipeline:
1. Identifies relevant fiscal quarters to process (current and previous, or all in full refresh)
2. Lists PDF transcript files from NAS directories organized by fiscal year/quarter
3. Extracts the first 3 pages from each transcript and uses GPT to identify the bank
4. Groups files by bank/year/quarter and keeps only the most recent version
5. Compares with PostgreSQL transcript_sections table to identify:
   - New transcript files to process
   - Updated transcript files to process (newer on NAS than in DB)
   - Corresponding DB records to delete

The results of the comparison are saved as JSON files to a specified output directory.
"""

import os
import sys
import json
import time
import tempfile
import requests  # For OAuth token request
import smbclient  # For NAS connection
import psycopg2
import pandas as pd
import logging
from datetime import datetime, timezone, timedelta
import pypdf  # For PDF processing
from typing import List, Dict, Tuple, Optional, Any
from openai import OpenAI

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# ==============================================================================
# --- Configuration ---
# ==============================================================================

# --- Database Configuration ---
# Database connection parameters 
DB_PARAMS = {
    "host": "localhost",
    "port": "5432",
    "dbname": "aegis",
    "user": "your_username",
    "password": "your_password"
}

# --- NAS Configuration ---
# Network attached storage connection parameters
NAS_PARAMS = {
    "ip": "your_nas_ip",
    "share": "your_share_name", 
    "user": "your_nas_user",
    "password": "your_nas_password"
}

# Base path on the NAS share for transcript files (organized by year/quarter)
NAS_BASE_INPUT_PATH = "path/to/your/transcripts"
# Base path on the NAS share where output JSON files will be stored
NAS_OUTPUT_FOLDER_PATH = "path/to/your/output_folder"

# --- Processing Configuration ---
# The name of the database table containing the transcript sections
DB_TABLE_NAME = 'transcript_sections'

# Document source identifier for earnings call transcripts
DOCUMENT_SOURCE = 'earnings_call'
DOCUMENT_TYPE = 'transcript'
DOCUMENT_LANGUAGE = 'en'

# Allowed banks for identification - the exact names to be used in the database
ALLOWED_BANKS = [
    "JP Morgan Chase",
    "Bank of America",
    "Wells Fargo",
    "Citigroup",
    "Goldman Sachs",
    "Morgan Stanley",
    "Royal Bank of Canada",
    "Toronto-Dominion Bank",
    "Scotiabank",
    "Bank of Montreal",
    "CIBC",
    "National Bank of Canada"
]

# --- Full Refresh Mode ---
# Set to True to process all quarters for the past 3 years
# Set to False to process only current and previous quarter
FULL_REFRESH = False

# --- OAuth Configuration ---
OAUTH_CONFIG = {
    "token_url": "YOUR_OAUTH_TOKEN_ENDPOINT_URL",
    "client_id": "YOUR_CLIENT_ID",
    "client_secret": "YOUR_CLIENT_SECRET",
    "scope": "api://YourResource/.default"
}

# --- GPT API Configuration ---
GPT_CONFIG = {
    "base_url": "YOUR_CUSTOM_GPT_API_BASE_URL",
    "model_name": "gpt-4o",  # Adjust to your model deployment name
    "api_version": "2024-02-01"
}

# --- CA Bundle for SSL ---
CA_BUNDLE_FILENAME = 'rbc-ca-bundle.cer'

# ==============================================================================
# --- Fiscal Calendar Functions ---
# ==============================================================================

def get_fiscal_period() -> Tuple[int, int]:
    """
    Calculate current fiscal year and quarter.
    Fiscal year runs from November 1 to October 31.

    Returns:
        Tuple[int, int]: Fiscal year and quarter
    """
    current_date = datetime.now()
    current_month = current_date.month
    calendar_year = current_date.year

    # If we're in Nov or Dec, we're in the next fiscal year
    fiscal_year = calendar_year + 1 if current_month >= 11 else calendar_year

    # Calculate fiscal quarter (Nov-Jan = Q1, Feb-Apr = Q2, May-Jul = Q3, Aug-Oct = Q4)
    month_adjusted = (current_month - 10) % 12  # Shift months to align with fiscal year
    fiscal_quarter = (month_adjusted - 1) // 3 + 1

    return fiscal_year, fiscal_quarter

def get_quarter_dates(fiscal_year: int, fiscal_quarter: int) -> Dict[str, datetime]:
    """
    Calculate the start and end dates for a given fiscal quarter.

    Args:
        fiscal_year (int): The fiscal year
        fiscal_quarter (int): The fiscal quarter (1-4)

    Returns:
        Dict[str, datetime]: Dictionary containing start and end dates
    """
    if fiscal_quarter < 1 or fiscal_quarter > 4:
        raise ValueError(
            f"Invalid fiscal quarter: {fiscal_quarter}. Must be between 1 and 4."
        )

    # Calculate the calendar year for the start date
    calendar_start_year = fiscal_year - 1 if fiscal_quarter == 1 else fiscal_year

    # Map fiscal quarters to their start months in the calendar year
    quarter_start_months = {
        1: 11,  # Nov (previous calendar year)
        2: 2,   # Feb
        3: 5,   # May
        4: 8,   # Aug
    }

    # Map fiscal quarters to their end months in the calendar year
    quarter_end_months = {
        1: 1,  # Jan
        2: 4,  # Apr
        3: 7,  # Jul
        4: 10, # Oct
    }

    # Calculate start date (first day of the quarter's first month)
    start_month = quarter_start_months[fiscal_quarter]
    start_year = calendar_start_year
    start_date = datetime(start_year, start_month, 1)

    # Calculate end date (last day of the quarter's last month)
    end_month = quarter_end_months[fiscal_quarter]
    end_year = fiscal_year

    # Get the last day of the month
    if end_month == 12:
        end_date = datetime(end_year, end_month, 31)
    else:
        # Get the first day of next month and subtract one day
        next_month = end_month + 1
        next_month_year = end_year
        if next_month > 12:
            next_month = 1
            next_month_year += 1
        end_date = datetime(next_month_year, next_month, 1) - timedelta(days=1)

    return {"start_date": start_date, "end_date": end_date}

# ==============================================================================
# --- Helper Functions ---
# ==============================================================================

def get_quarters_to_process() -> List[Tuple[int, int]]:
    """
    Determine which fiscal quarters to process based on current date and FULL_REFRESH setting.
    
    Returns:
        List[Tuple[int, int]]: List of (fiscal_year, fiscal_quarter) tuples to process
    """
    current_fiscal_year, current_fiscal_quarter = get_fiscal_period()
    quarters_to_process = []
    
    if FULL_REFRESH:
        # Process the last 3 years (12 quarters)
        for year_offset in range(3):
            year = current_fiscal_year - year_offset
            for quarter in range(1, 5):
                # Skip future quarters
                if year_offset == 0 and quarter > current_fiscal_quarter:
                    continue
                quarters_to_process.append((year, quarter))
    else:
        # Process current quarter and previous quarter
        quarters_to_process.append((current_fiscal_year, current_fiscal_quarter))
        
        # Calculate previous quarter
        prev_year, prev_quarter = current_fiscal_year, current_fiscal_quarter - 1
        if prev_quarter < 1:
            prev_quarter = 4
            prev_year -= 1
        
        quarters_to_process.append((prev_year, prev_quarter))
    
    logger.info(f"Selected quarters to process: {quarters_to_process}")
    return quarters_to_process

def construct_nas_quarter_path(base_path: str, fiscal_year: int, fiscal_quarter: int) -> str:
    """
    Construct the NAS path for a specific fiscal year and quarter.
    
    Args:
        base_path (str): Base path on NAS
        fiscal_year (int): Fiscal year (e.g., 2023)
        fiscal_quarter (int): Fiscal quarter (1-4)
        
    Returns:
        str: Full path to the quarter directory
    """
    return os.path.join(base_path, str(fiscal_year), f"Q{fiscal_quarter}").replace('\\', '/')

def initialize_smb_client():
    """Sets up smbclient credentials."""
    try:
        smbclient.ClientConfig(username=NAS_PARAMS["user"], password=NAS_PARAMS["password"])
        logger.info("SMB client configured successfully.")
        return True
    except Exception as e:
        logger.error(f"Failed to configure SMB client: {e}")
        return False

def create_nas_directory(smb_dir_path):
    """Creates a directory on the NAS if it doesn't exist."""
    try:
        if not smbclient.path.exists(smb_dir_path):
            logger.info(f"Creating NAS directory: {smb_dir_path}")
            smbclient.makedirs(smb_dir_path, exist_ok=True)
            logger.info(f"Successfully created directory.")
        return True
    except smbclient.SambaClientError as e:
        logger.error(f"SMB Error creating/accessing directory '{smb_dir_path}': {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error creating/accessing NAS directory '{smb_dir_path}': {e}")
        return False

def write_json_to_nas(smb_path: str, data_string: str) -> bool:
    """
    Writes a string (expected to be JSON) to a specified file path on the NAS.

    Args:
        smb_path (str): The full SMB path (e.g., //nas_ip/share/path/to/file.json).
        data_string (str): The string content to write to the file.

    Returns:
        bool: True if the write operation was successful, False otherwise.
    """
    logger.info(f"Attempting to write to NAS path: {smb_path}")
    try:
        # Ensure the directory exists before writing the file
        dir_path = os.path.dirname(smb_path)
        if not smbclient.path.exists(dir_path):
            logger.info(f"Creating directory on NAS: {dir_path}")
            smbclient.makedirs(dir_path, exist_ok=True)

        with smbclient.open_file(smb_path, mode='w', encoding='utf-8') as f:
            f.write(data_string)
        logger.info(f"Successfully wrote to: {smb_path}")
        return True
    except smbclient.SambaClientError as e:
        logger.error(f"SMB Error writing to '{smb_path}': {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error writing to NAS '{smb_path}': {e}")
        return False

def get_transcript_pdf_files(nas_ip: str, share_name: str, quarter_folder_path: str, 
                         username: str, password: str) -> List[Dict[str, Any]]:
    """
    Lists PDF files in a specific fiscal quarter directory on an SMB share.

    Args:
        nas_ip (str): The IP address of the NAS.
        share_name (str): The name of the SMB share.
        quarter_folder_path (str): The path to the quarter folder (e.g., '2023/Q3').
        username (str): The username for NAS authentication.
        password (str): The password for NAS authentication.

    Returns:
        List[Dict[str, Any]]: List of dictionaries with file details, or empty list if error.
    """
    files_list = []
    smb_base_path = f"//{nas_ip}/{share_name}/{quarter_folder_path}"
    
    logger.info(f"Configuring SMB client for user '{username}'...")
    try:
        # Set credentials globally for this smbclient instance/session
        smbclient.ClientConfig(username=username, password=password)
        logger.info(f"Attempting to connect and list files from NAS path: {smb_base_path}")
        
        # Check if the base path exists
        if not smbclient.path.exists(smb_base_path):
            logger.error(f"Base NAS path does not exist or is inaccessible: {smb_base_path}")
            return []
        
        # List all PDF files in the directory (non-recursive)
        for item in smbclient.listdir(smb_base_path):
            full_path = os.path.join(smb_base_path, item).replace('\\', '/')
            
            try:
                # Check if it's a file and has .pdf extension
                if smbclient.path.isfile(full_path) and item.lower().endswith('.pdf'):
                    # Get file metadata
                    stat_info = smbclient.stat(full_path)
                    
                    # Convert modification time to timezone-aware UTC datetime
                    last_modified_dt = datetime.fromtimestamp(stat_info.st_mtime, tz=timezone.utc)
                    
                    # Get creation time, fallback to modification time if not available
                    creation_timestamp = getattr(stat_info, 'st_birthtime', stat_info.st_mtime)
                    created_dt = datetime.fromtimestamp(creation_timestamp, tz=timezone.utc)
                    
                    # Store relative path from the share root
                    relative_path = os.path.join(quarter_folder_path, item).replace('\\', '/')
                    
                    files_list.append({
                        'file_name': item,
                        'file_path': relative_path,
                        'file_size': stat_info.st_size,
                        'date_last_modified': last_modified_dt,
                        'date_created': created_dt,
                        'quarter_folder': quarter_folder_path
                    })
            except Exception as e:
                logger.warning(f"Error processing file '{item}': {e}")
        
        logger.info(f"Found {len(files_list)} PDF files in {smb_base_path}")
        return files_list
        
    except Exception as e:
        logger.error(f"Error listing files from '{smb_base_path}': {e}")
        return []

def extract_pdf_first_pages(nas_ip: str, share_name: str, file_path: str, 
                           username: str, password: str, pages: int = 3) -> str:
    """
    Extracts the first N pages from a PDF file on the NAS.
    
    Args:
        nas_ip (str): The IP address of the NAS.
        share_name (str): The name of the SMB share.
        file_path (str): The relative path to the PDF file from share root.
        username (str): The username for NAS authentication.
        password (str): The password for NAS authentication.
        pages (int): Number of pages to extract (default 3).
        
    Returns:
        str: Extracted text from the first N pages or empty string on error.
    """
    full_smb_path = f"//{nas_ip}/{share_name}/{file_path}"
    logger.info(f"Extracting first {pages} pages from {full_smb_path}")
    
    try:
        # Configure SMB client
        smbclient.ClientConfig(username=username, password=password)
        
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_file:
            temp_pdf_path = temp_file.name
            
            # Download the PDF file to a temporary location
            with smbclient.open_file(full_smb_path, mode='rb') as f_remote:
                temp_file.write(f_remote.read())
                
        # Extract text from the PDF using pypdf
        extracted_text = ""
        with open(temp_pdf_path, 'rb') as f:
            pdf_reader = pypdf.PdfReader(f)
            max_pages = min(pages, len(pdf_reader.pages))
            
            for i in range(max_pages):
                page = pdf_reader.pages[i]
                page_text = page.extract_text()
                extracted_text += f"\n--- Page {i+1} ---\n{page_text}\n"
                
        # Clean up temporary file    
        os.unlink(temp_pdf_path)
        
        return extracted_text
        
    except Exception as e:
        logger.error(f"Error extracting PDF content from {full_smb_path}: {e}")
        # Try to clean up temp file if it exists
        try:
            if 'temp_pdf_path' in locals():
                os.unlink(temp_pdf_path)
        except:
            pass
        return ""

def get_oauth_token():
    """Retrieves an OAuth access token using client credentials flow."""
    logger.info("Requesting OAuth access token...")
    token_url = OAUTH_CONFIG['token_url']
    payload = {
        'client_id': OAUTH_CONFIG['client_id'],
        'client_secret': OAUTH_CONFIG['client_secret'],
        'grant_type': 'client_credentials'
    }
    # Add scope if defined and not empty
    if OAUTH_CONFIG.get('scope'):
        payload['scope'] = OAUTH_CONFIG['scope']

    try:
        # Create a temporary file for the CA bundle if needed
        ca_bundle_path = None
        if CA_BUNDLE_FILENAME:
            try:
                smb_ca_path = f"//{NAS_PARAMS['ip']}/{NAS_PARAMS['share']}/{CA_BUNDLE_FILENAME}"
                if smbclient.path.exists(smb_ca_path):
                    with tempfile.NamedTemporaryFile(suffix='.cer', delete=False) as temp_ca_file:
                        ca_bundle_path = temp_ca_file.name
                        with smbclient.open_file(smb_ca_path, mode='rb') as f_ca:
                            temp_ca_file.write(f_ca.read())
                    logger.info(f"CA bundle downloaded to temporary file: {ca_bundle_path}")
                else:
                    logger.warning(f"CA bundle not found at: {smb_ca_path}")
            except Exception as e:
                logger.warning(f"Failed to download CA bundle: {e}")

        # Make the POST request, using CA bundle if available
        if ca_bundle_path:
            response = requests.post(token_url, data=payload, verify=ca_bundle_path)
        else:
            response = requests.post(token_url, data=payload)
            
        response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
        token_data = response.json()
        access_token = token_data.get('access_token')
        
        # Clean up the temporary CA file if it was created
        if ca_bundle_path:
            try:
                os.remove(ca_bundle_path)
            except Exception as e:
                logger.warning(f"Failed to remove temporary CA bundle file: {e}")
                
        if not access_token:
            logger.error("'access_token' not found in OAuth response.")
            return None
            
        logger.info("OAuth token obtained successfully.")
        return access_token
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to get OAuth token: {e}")
        # Log more details if possible
        if hasattr(e, 'response') and e.response is not None:
            logger.error(f"Response status: {e.response.status_code}")
            logger.error(f"Response body: {e.response.text}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error during OAuth token request: {e}")
        return None

def setup_openai_client():
    """
    Sets up the OpenAI client with auth token and SSL configuration.
    
    Returns:
        Optional[OpenAI]: Configured OpenAI client or None on failure
    """
    try:
        # Get OAuth token
        access_token = get_oauth_token()
        if not access_token:
            logger.error("Failed to obtain OAuth token. Cannot proceed with GPT identification.")
            return None
            
        # Set up OpenAI client
        client = OpenAI(
            api_key=access_token,  # Using OAuth token as API key
            base_url=GPT_CONFIG.get('base_url', 'https://api.openai.com/v1')
        )
        
        return client
    except Exception as e:
        logger.error(f"Error setting up OpenAI client: {e}")
        return None

def identify_bank_with_gpt(pdf_text: str, allowed_banks: List[str], api_client: OpenAI) -> Optional[str]:
    """
    Identify which bank the transcript belongs to using GPT.
    
    Args:
        pdf_text (str): Extracted text from the PDF's first pages.
        allowed_banks (List[str]): List of allowed bank names.
        api_client (OpenAI): Configured OpenAI client.
        
    Returns:
        Optional[str]: Identified bank name, or None if identification failed.
    """
    if not pdf_text.strip():
        logger.error("Cannot identify bank: PDF text is empty")
        return None
        
    try:
        # Construct the prompt with the bank list
        bank_list_formatted = "\n".join([f"{i+1}. {bank}" for i, bank in enumerate(allowed_banks)])
        
        prompt = f"""You are tasked with identifying which bank's earnings call transcript this is.
Below is the text from the first few pages of an earnings call transcript.
Identify which bank this transcript belongs to from the following list of banks, and ONLY respond with the corresponding number:

{bank_list_formatted}

If you cannot determine the bank with confidence, respond with "0".

Transcript text:
{pdf_text[:5000]}  # Limit text length to avoid token issues
"""

        response = api_client.chat.completions.create(
            model=GPT_CONFIG['model_name'],
            messages=[
                {"role": "system", "content": "You are a helpful assistant that identifies banks from earnings call transcripts."},
                {"role": "user", "content": prompt}
            ],
            temperature=0,
            max_tokens=10  # We only need a short response
        )
        
        # Parse the response to get the bank index
        response_text = response.choices[0].message.content.strip()
        
        try:
            bank_idx = int(response_text)
            if bank_idx == 0:
                logger.warning("GPT could not confidently identify the bank")
                return None
                
            if 1 <= bank_idx <= len(allowed_banks):
                identified_bank = allowed_banks[bank_idx - 1]
                logger.info(f"GPT identified bank: {identified_bank}")
                return identified_bank
            else:
                logger.error(f"GPT returned invalid bank index: {bank_idx}")
                return None
        except ValueError:
            logger.error(f"GPT returned non-numeric response: {response_text}")
            return None
            
    except Exception as e:
        logger.error(f"Error identifying bank with GPT: {e}")
        return None

def process_transcript_files(file_list: List[Dict[str, Any]], nas_ip: str, share_name: str,
                          username: str, password: str, api_client: OpenAI, 
                          allowed_banks: List[str]) -> List[Dict[str, Any]]:
    """
    Process transcript files to identify banks and group by bank/year/quarter.
    
    Args:
        file_list (List[Dict[str, Any]]): List of transcript files with metadata.
        nas_ip (str): The IP address of the NAS.
        share_name (str): The name of the SMB share.
        username (str): The username for NAS authentication.
        password (str): The password for NAS authentication.
        api_client (OpenAI): Configured OpenAI client.
        allowed_banks (List[str]): List of allowed bank names.
        
    Returns:
        List[Dict[str, Any]]: List of processed files with bank information.
    """
    processed_files = []
    
    for file_info in file_list:
        # Extract quarter and year from quarter_folder
        quarter_folder = file_info['quarter_folder']
        parts = quarter_folder.split('/')
        
        try:
            fiscal_year = int(parts[-2])
            fiscal_quarter = int(parts[-1].replace('Q', ''))
        except (IndexError, ValueError):
            logger.error(f"Cannot parse year/quarter from folder: {quarter_folder}")
            continue
        
        # Extract text from PDF
        pdf_text = extract_pdf_first_pages(
            nas_ip, share_name, file_info['file_path'], 
            username, password, pages=3
        )
        
        if not pdf_text:
            logger.warning(f"Skipping file due to empty PDF content: {file_info['file_name']}")
            continue
            
        # Identify bank using GPT
        bank_name = identify_bank_with_gpt(pdf_text, allowed_banks, api_client)
        
        if not bank_name:
            logger.warning(f"Skipping file due to bank identification failure: {file_info['file_name']}")
            continue
            
        # Add identified information to file_info
        complete_file_info = file_info.copy()
        complete_file_info.update({
            'bank_name': bank_name,
            'fiscal_year': fiscal_year,
            'fiscal_quarter': fiscal_quarter,
            'document_source': DOCUMENT_SOURCE,
            'document_type': DOCUMENT_TYPE,
            'document_name': f"Q{fiscal_quarter} {fiscal_year} Earnings Call",
            'document_language': DOCUMENT_LANGUAGE
        })
        
        processed_files.append(complete_file_info)
        
    return processed_files

def get_latest_version_by_bank(processed_files: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Group files by bank/year/quarter and keep only the latest version of each.
    
    Args:
        processed_files (List[Dict[str, Any]]): List of processed files with bank information.
        
    Returns:
        List[Dict[str, Any]]: List of latest files for each bank/year/quarter.
    """
    # Group files by bank, year, and quarter
    grouped_files = {}
    
    for file_info in processed_files:
        key = (file_info['bank_name'], file_info['fiscal_year'], file_info['fiscal_quarter'])
        
        if key not in grouped_files or file_info['date_last_modified'] > grouped_files[key]['date_last_modified']:
            grouped_files[key] = file_info
            
    # Convert back to list
    latest_files = list(grouped_files.values())
    logger.info(f"Reduced {len(processed_files)} files to {len(latest_files)} latest versions")
    
    return latest_files

# ==============================================================================
# --- Main Execution Logic ---
# ==============================================================================

if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info(f"Running Stage 1: Extract & Compare for Transcript Processing")
    logger.info(f"Document Source: {DOCUMENT_SOURCE}")
    logger.info(f"DB Table: {DB_TABLE_NAME}")
    logger.info(f"Mode: {'FULL REFRESH' if FULL_REFRESH else 'INCREMENTAL'}")
    logger.info("=" * 60)

    # --- Initialize SMB Client ---
    if not initialize_smb_client():
        logger.error("Failed to initialize SMB client. Exiting.")
        sys.exit(1)

    # --- Set up OpenAI Client with OAuth ---
    openai_client = setup_openai_client()
    if not openai_client:
        logger.error("Failed to set up OpenAI client. Exiting.")
        sys.exit(1)

    # --- Determine Quarters to Process ---
    logger.info("[1] Determining fiscal quarters to process...")
    quarters_to_process = get_quarters_to_process()

    # --- Construct NAS Output Path ---
    logger.info("[2] Constructing NAS output path...")
    nas_output_dir_relative = os.path.join(
        NAS_OUTPUT_FOLDER_PATH, 
        DOCUMENT_SOURCE,
        datetime.now().strftime("%Y%m%d_%H%M%S")
    ).replace('\\', '/')
    
    nas_output_dir_smb_path = f"//{NAS_PARAMS['ip']}/{NAS_PARAMS['share']}/{nas_output_dir_relative}"
    logger.info(f"NAS Output Directory: {nas_output_dir_smb_path}")
    
    # Define specific output file paths
    db_output_smb_file = os.path.join(nas_output_dir_smb_path, '1A_catalog_in_postgres.json').replace('\\', '/')
    nas_output_smb_file = os.path.join(nas_output_dir_smb_path, '1B_files_in_nas.json').replace('\\', '/')
    process_output_smb_file = os.path.join(nas_output_dir_smb_path, '1C_nas_files_to_process.json').replace('\\', '/')
    delete_output_smb_file = os.path.join(nas_output_dir_smb_path, '1D_postgres_files_to_delete.json').replace('\\', '/')
    
    # --- Ensure NAS Output Directory Exists ---
    logger.info("[3] Ensuring NAS output directory exists...")
    if not create_nas_directory(nas_output_dir_smb_path):
        logger.error("Failed to create output directory. Exiting.")
        sys.exit(1)

    # --- Get Transcript PDF Files from NAS ---
    logger.info("[4] Listing transcript PDF files from NAS...")
    all_nas_files = []
    
    for fiscal_year, fiscal_quarter in quarters_to_process:
        quarter_path = construct_nas_quarter_path(NAS_BASE_INPUT_PATH, fiscal_year, fiscal_quarter)
        logger.info(f"Processing quarter folder: {quarter_path}")
        
        quarter_files = get_transcript_pdf_files(
            NAS_PARAMS["ip"],
            NAS_PARAMS["share"],
            quarter_path,
            NAS_PARAMS["user"],
            NAS_PARAMS["password"]
        )
        
        all_nas_files.extend(quarter_files)
    
    logger.info(f"Found {len(all_nas_files)} transcript PDF files across {len(quarters_to_process)} quarters")
    
    # --- Process Transcript Files to Identify Banks ---
    logger.info("[5] Processing transcript files to identify banks...")
    processed_files = process_transcript_files(
        all_nas_files,
        NAS_PARAMS["ip"],
        NAS_PARAMS["share"],
        NAS_PARAMS["user"],
        NAS_PARAMS["password"],
        openai_client,
        ALLOWED_BANKS
    )
    
    logger.info(f"Successfully processed {len(processed_files)} files with bank identification")
    
    # --- Get Latest Version of Each Bank's Transcript ---
    logger.info("[6] Identifying latest version of each bank's transcript...")
    latest_files = get_latest_version_by_bank(processed_files)
    
    # --- Save NAS File List to NAS ---
    logger.info("[7] Saving NAS file list to output...")
    nas_files_df = pd.DataFrame(latest_files)
    nas_json_string = nas_files_df.to_json(orient='records', indent=4, date_format='iso')
    
    if not write_json_to_nas(nas_output_smb_file, nas_json_string):
        logger.error("Failed to write NAS file list JSON")
        sys.exit(1)

    # --- Get Data from PostgreSQL ---
    logger.info("[8] Fetching existing transcript data from PostgreSQL...")
    conn = None
    db_df = pd.DataFrame()  # Initialize empty DataFrame
    
    try:
        logger.info(f"Connecting to database {DB_PARAMS['dbname']} on {DB_PARAMS['host']}...")
        conn = psycopg2.connect(**DB_PARAMS)
        
        # Construct WHERE clause for fiscal quarters
        fiscal_conditions = []
        for fiscal_year, fiscal_quarter in quarters_to_process:
            fiscal_conditions.append(
                f"(fiscal_year = {fiscal_year} AND fiscal_quarter = {fiscal_quarter})"
            )
        
        fiscal_where_clause = " OR ".join(fiscal_conditions)
        
        # SQL query to select relevant columns for the specified quarters
        query = f"""
            SELECT id, file_name, file_path, date_last_modified, file_size,
                   document_source, document_type, document_name, document_language,
                   fiscal_year, fiscal_quarter, bank_name
            FROM {DB_TABLE_NAME}
            WHERE document_source = %s AND ({fiscal_where_clause});
        """
        
        logger.info(f"Executing query for document_source = '{DOCUMENT_SOURCE}'...")
        db_df = pd.read_sql_query(query, conn, params=(DOCUMENT_SOURCE,))
        
        # Process timestamps to ensure they're timezone-aware UTC
        if not db_df.empty and 'date_last_modified' in db_df.columns:
            db_df['date_last_modified'] = pd.to_datetime(db_df['date_last_modified'], errors='coerce')
            valid_dates = db_df['date_last_modified'].notna()
            
            if db_df.loc[valid_dates, 'date_last_modified'].dt.tz is None:
                db_df.loc[valid_dates, 'date_last_modified'] = db_df.loc[valid_dates, 'date_last_modified'].dt.tz_localize('UTC')
            else:
                db_df.loc[valid_dates, 'date_last_modified'] = db_df.loc[valid_dates, 'date_last_modified'].dt.tz_convert('UTC')
                
        logger.info(f"Found {len(db_df)} existing transcript records in database")
        
        # Save DB records to NAS
        logger.info("Saving DB catalog data to NAS...")
        db_json_string = db_df.to_json(orient='records', indent=4, date_format='iso')
        
        if not write_json_to_nas(db_output_smb_file, db_json_string):
            logger.error("Failed to write DB catalog JSON")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"Database error: {e}")
        sys.exit(1)
    finally:
        if conn:
            conn.close()
            logger.info("Database connection closed")

    # --- Compare NAS Files with DB Records ---
    logger.info("[9] Comparing NAS files with database records...")
    
    # Initialize DataFrames
    files_to_process = pd.DataFrame()
    files_to_delete = pd.DataFrame()
    
    # Handle Full Refresh Mode
    if FULL_REFRESH:
        logger.info("Full refresh mode: Processing all files and deleting all existing records")
        files_to_process = nas_files_df.copy()
        files_to_process['reason'] = 'full_refresh'
        
        if not db_df.empty:
            files_to_delete = db_df.copy()
    else:
        # Incremental Update Mode
        logger.info("Incremental update mode: Comparing files based on bank, year, quarter, and modification date")
        
        # Convert DataFrames to be compatible for merging
        if not nas_files_df.empty:
            nas_files_df['key'] = nas_files_df.apply(
                lambda row: f"{row['bank_name']}_{row['fiscal_year']}_{row['fiscal_quarter']}", 
                axis=1
            )
            
        if not db_df.empty:
            db_df['key'] = db_df.apply(
                lambda row: f"{row['bank_name']}_{row['fiscal_year']}_{row['fiscal_quarter']}", 
                axis=1
            )
            
        # Files in NAS but not in DB (new files)
        if not nas_files_df.empty and not db_df.empty:
            new_files = nas_files_df[~nas_files_df['key'].isin(db_df['key'])].copy()
            new_files['reason'] = 'new'
            
            # Files that exist in both NAS and DB
            common_keys = set(nas_files_df['key']).intersection(set(db_df['key']))
            
            # For common keys, check if NAS version is newer
            updated_files = []
            files_to_delete_list = []
            
            for key in common_keys:
                nas_row = nas_files_df[nas_files_df['key'] == key].iloc[0]
                db_rows = db_df[db_df['key'] == key]
                
                # Get the latest modification date from DB
                latest_db_date = db_rows['date_last_modified'].max()
                
                # If NAS file is newer than DB record, mark for update
                if nas_row['date_last_modified'] > latest_db_date:
                    nas_file_copy = nas_row.copy()
                    nas_file_copy['reason'] = 'updated'
                    updated_files.append(nas_file_copy)
                    
                    # Mark all DB records with this key for deletion
                    files_to_delete_list.extend(db_rows.to_dict('records'))
            
            # Combine new and updated files
            if updated_files:
                updated_files_df = pd.DataFrame(updated_files)
                files_to_process = pd.concat([new_files, updated_files_df], ignore_index=True)
            else:
                files_to_process = new_files
                
            # Convert files to delete to DataFrame
            if files_to_delete_list:
                files_to_delete = pd.DataFrame(files_to_delete_list)
                
        elif not nas_files_df.empty:
            # If DB is empty but NAS has files, all NAS files are new
            files_to_process = nas_files_df.copy()
            files_to_process['reason'] = 'new'
    
    # --- Save Comparison Results ---
    logger.info("[10] Saving comparison results...")
    
    # Save files to process
    logger.info(f"Found {len(files_to_process)} files to process")
    process_json_string = files_to_process.to_json(orient='records', indent=4, date_format='iso')
    
    if not write_json_to_nas(process_output_smb_file, process_json_string):
        logger.error("Failed to write 'files to process' JSON")
        sys.exit(1)
        
    # Save files to delete
    logger.info(f"Found {len(files_to_delete)} database records to delete")
    delete_json_string = files_to_delete.to_json(orient='records', indent=4, date_format='iso')
    
    if not write_json_to_nas(delete_output_smb_file, delete_json_string):
        logger.error("Failed to write 'files to delete' JSON")
        sys.exit(1)
    
    # --- Create Skip Flag if No Files to Process ---
    logger.info("[11] Managing flag files...")
    skip_flag_file_name = '_SKIP_SUBSEQUENT_STAGES.flag'
    refresh_flag_file_name = '_FULL_REFRESH.flag'
    skip_flag_smb_path = os.path.join(nas_output_dir_smb_path, skip_flag_file_name).replace('\\', '/')
    refresh_flag_smb_path = os.path.join(nas_output_dir_smb_path, refresh_flag_file_name).replace('\\', '/')
    
    # Skip Flag Logic
    if files_to_process.empty:
        logger.info("No files to process. Creating skip flag.")
        try:
            smbclient.ClientConfig(username=NAS_PARAMS["user"], password=NAS_PARAMS["password"])
            with smbclient.open_file(skip_flag_smb_path, mode='w', encoding='utf-8') as f:
                f.write('')
            logger.info(f"Created skip flag: {skip_flag_file_name}")
        except Exception as e:
            logger.warning(f"Error creating skip flag: {e}")
    else:
        logger.info(f"Files found for processing ({len(files_to_process)}). No skip flag needed.")
        
    # Full Refresh Flag Logic
    if FULL_REFRESH:
        logger.info("Full refresh mode. Creating refresh flag.")
        try:
            smbclient.ClientConfig(username=NAS_PARAMS["user"], password=NAS_PARAMS["password"])
            with smbclient.open_file(refresh_flag_smb_path, mode='w', encoding='utf-8') as f:
                f.write('')
            logger.info(f"Created refresh flag: {refresh_flag_file_name}")
        except Exception as e:
            logger.warning(f"Error creating refresh flag: {e}")
    
    logger.info("=" * 60)
    logger.info("Stage 1 completed successfully!")
    logger.info("=" * 60)