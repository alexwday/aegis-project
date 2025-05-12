# Example Reference Subagent

This directory contains a reference implementation of a database subagent retained for future development purposes.

It should NOT be used in production. Instead, refer to this code as an example when implementing actual database integrations.

## Structure

- `subagent.py`: Main implementation with full database integration logic
- `catalog_selection_prompt.py`: Prompts for selecting relevant documents
- `content_synthesis_prompt.py`: Prompts for synthesizing responses

## Implementation Details

The reference implementation demonstrates how to:

1. Query document catalogs
2. Select relevant documents using LLMs
3. Synthesize information from multiple sources
4. Format responses for downstream consumption
EOF < /dev/null