# Public Transcripts Subagent

This subagent handles retrieving and processing information from earnings call transcripts of major US and Canadian banks.

## Purpose

Earnings call transcripts contain valuable information including management discussion, forward-looking statements, analyst questions, and strategic priorities. This subagent enables:

- Searching through transcripts for mentions of specific topics, metrics, or strategies
- Analyzing management commentary on financial performance
- Extracting insights from Q&A sessions with analysts
- Comparing statements across different quarters or institutions

## Functionality

The subagent implements a multi-step retrieval and synthesis process:

1. **Catalog Selection**: Identifies relevant transcript documents based on the query
2. **Content Retrieval**: Fetches and processes transcript sections
3. **Content Synthesis**: Generates structured, detailed responses with proper attribution

## Data Structure

The transcripts are stored with the following metadata:

- Bank name
- Fiscal quarter/year
- Publication date
- Speaker information (executives, analysts)
- Section type (prepared remarks, Q&A)

## Integration

This subagent is registered with the database router and can be accessed through the standard agent pipeline.
