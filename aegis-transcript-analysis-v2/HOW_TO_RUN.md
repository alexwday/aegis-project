# How to Run the Iterative Research Plan Generation System

## 🚀 **Quick Start Guide**

### **1. Setup Environment**
```bash
# Navigate to the project
cd /Users/alexwday/Projects/aegis-project/aegis-transcript-analysis-v2

# Activate virtual environment
source ../venv/bin/activate

# Install dependencies (if needed)
pip install openai PyPDF2 beautifulsoup4 requests cryptography
```

### **2. Configure Authentication (REQUIRED)**

Edit `config.json` with your **corporate credentials**:
```json
{
  "base_url": "https://your-corporate-api-proxy.company.com/v1",
  "oauth_endpoint": "https://oauth.company.com/token", 
  "client_id": "your-oauth-client-id",
  "client_secret": "your-oauth-client-secret",
  "ssl_cert_path": "rbc-ca-bundle.cer",
  "openai_model": "gpt-4",
  "max_tokens": 8000,
  "temperature": 0.1
}
```

**⚠️ Important**: This system supports two authentication methods:
1. **Corporate OAuth**: Configure oauth_endpoint, client_id, client_secret + base_url
2. **Direct OpenAI**: Set OPENAI_API_KEY environment variable (no base_url needed)

For corporate environments, OAuth + SSL + base_url are typically required.

### **3. Configure Sections (Optional)**
```bash
# Open the visual section configuration interface
open 0_document_template.html
```
- ✅ Enable/disable sections you want to analyze
- ✏️ Edit section descriptions if needed  
- 💾 Save the file when done

### **4. Extract Section Instructions**
```bash
# Convert HTML template to structured JSON
python 1_document_template_extraction.py
```
This creates `2_section_instructions.json` with your configured sections.

### **5. Prepare Your Transcript**
```bash
# Copy your earnings call PDF into the input folder
cp your_earnings_transcript.pdf 4_transcript_input_pdf/
```

### **6. Run the Research Plan Generator**
```bash
# Generate iterative research plans
python 5_create_research_plan.py
```

### **7. Generate Section Analyses**
```bash
# Execute research plans to extract structured content
python 8_generate_sections.py
```
This processes each section using the research plans and generates structured JSON analyses.

### **8. Create HTML Report with Executive Summary**
```bash
# Generate final interactive HTML report with AI summary
python 11_generate_report.py
```
This creates the final report with:
- 🎯 **AI-Generated Executive Summary** - Comprehensive overview of entire call
- 📊 **Interactive Sections** - Collapsible sections with quotes and analysis
- 🎨 **Professional Styling** - Business-ready presentation format

## 📊 **Authentication Flow:**

1. **SSL Setup** - Configures SSL certificate for ALL connections:
   - Sets `SSL_CERT_FILE` environment variable (for OpenAI client)
   - Sets `REQUESTS_CA_BUNDLE` environment variable (for OAuth requests)
   - Both OAuth and API calls use the same SSL certificate

2. **OAuth Token** - Gets access token using client credentials:
   - Makes HTTPS request to oauth_endpoint (uses SSL)
   - Authenticates with client_id and client_secret
   - Returns OAuth bearer token

3. **API Client** - Creates OpenAI client with:
   - `api_key` = OAuth token (or OPENAI_API_KEY if OAuth not configured)
   - `base_url` = Corporate API proxy endpoint (if configured)
   - SSL certificate automatically applied via environment variables

## 📋 **Output Files:**

- `6_research_plan.json` - Research plans for all sections
- `9_report_sections.json` - Structured section analyses with quotes
- `12_transcript_summary_report.html` - **Final interactive report with AI summary**
- Log files: `research_plan_creator.log`, `section_generator.log`, `report_generator.log`

## 🛠 **Troubleshooting:**

**"No API key available" Error:**
Either:
- Configure OAuth: Set `oauth_endpoint`, `client_id`, `client_secret` in config.json
- OR set environment variable: `export OPENAI_API_KEY="your-key"`

**OAuth Authentication Failed:**
- Verify `oauth_endpoint`, `client_id`, `client_secret` are correct
- Check SSL certificate path exists and is valid
- Ensure corporate network/VPN access
- Test OAuth endpoint is reachable

**No PDF found:**
```bash
ls 4_transcript_input_pdf/  # Check PDF is there
```

**SSL Certificate Issues:**
- Verify `ssl_cert_path` points to correct certificate file
- Check certificate is valid and accessible

## ⚡ **Full Workflow Example:**
```bash
# 1. Setup
source ../venv/bin/activate

# 2. Configure authentication in config.json
# (Set real corporate endpoints and credentials)

# 3. Configure sections (optional)
open 0_document_template.html

# 4. Extract sections  
python 1_document_template_extraction.py

# 5. Add transcript
cp ~/Downloads/q2_earnings_transcript.pdf 4_transcript_input_pdf/

# 6. Generate research plans
python 5_create_research_plan.py

# 7. Execute section analyses
python 8_generate_sections.py

# 8. Create final HTML report with AI summary
python 11_generate_report.py

# 9. View results
open 12_transcript_summary_report.html
```

## 🏢 **Corporate Environment Note:**

This system is designed for corporate environments with:
- OAuth-based API access
- SSL certificate requirements  
- Proxy endpoints for LLM access
- Internal security protocols

It does **NOT** use direct OpenAI API keys or public OpenAI endpoints.