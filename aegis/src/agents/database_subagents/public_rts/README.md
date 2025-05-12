# Public Reports to Shareholders (RTS) Subagent

This subagent handles retrieving and processing information from quarterly reports to shareholders of major US and Canadian banks.

## Purpose

Shareholder reports contain valuable information including quarterly financial results, management discussion and analysis, detailed financial statements, and formal disclosures. This subagent enables:

- Searching through formal financial reports for specific metrics and disclosures
- Analyzing management discussion and analysis sections
- Extracting specific financial data and metrics
- Comparing official financial reporting across different quarters or institutions

## Functionality

The subagent implements a multi-step retrieval and synthesis process:

1. **Catalog Selection**: Identifies relevant shareholder report documents based on the query
2. **Content Retrieval**: Fetches and processes report sections
3. **Content Synthesis**: Generates structured, detailed responses with proper attribution and citations

## Data Structure

The shareholder reports are stored with the following metadata:

- Bank name
- Fiscal quarter/year
- Publication date
- Report sections (e.g., MD&A, Financial Statements, Notes)

## Integration

This subagent is registered with the database router and can be accessed through the standard agent pipeline.
