# TD Transcript JSON Format Specification

This document defines the expected JSON format for extracting and structuring content from TD earnings call transcripts. Use this specification when building LLM extraction pipelines.

## Format Overview

Each transcript section should be extracted into a JSON file following this hierarchical structure:

```
Section
├── Metadata (name, title, statement)
└── Content
    └── Subsections
        └── Quotes (with full metadata)
```

## JSON Structure

### Top Level (Required Fields)

```json
{
  "section_name": "Credit",
  "section_title": "Credit: Reviewed credit portfolios and bolstered reserves", 
  "section_statement": "AI-generated summary of key section insights",
  "content": [...]
}
```

- **section_name**: Short identifier (e.g., "Credit", "Capital and Liquidity")
- **section_title**: Full section heading as it appears in reports
- **section_statement**: 1-2 sentence AI summary of the section's key points and themes
- **content**: Array of subsection objects

### Content Structure

```json
{
  "subsection": "Tariff Scenario Modeling",
  "quotes": [...]
}
```

- **subsection**: Specific topic within the section (e.g., "Macro Changes and Governance Process")
- **quotes**: Array of quote objects with full metadata

### Quote Structure (Required Fields)

```json
{
  "quote_text": "We did put <span class=\"highlight-keyword\">tariffs</span> into these scenarios:",
  "context": "Additional clarifying information or null",
  "speaker": {
    "name": "Gabriel Dechaine",
    "title": "CFO", 
    "company": "TD Bank"
  },
  "sentiment": "cautious",
  "sentiment_rationale": "Conservative scenario planning for risks",
  "key_metrics": ["10% tariffs for Canada", "12% tariffs for U.S."]
}
```

#### Quote Fields Explained

- **quote_text**: Exact quote from transcript with HTML highlighting
- **context**: Supporting data or clarification (use `null` if not needed)
- **speaker**: Object with name, title, company (all required)
- **sentiment**: One of the predefined sentiment values
- **sentiment_rationale**: Brief explanation for the sentiment classification
- **key_metrics**: Array of important numbers/metrics mentioned (empty array if none)

## Sentiment Classifications

Use these exact values for consistent sentiment analysis:

| Sentiment | Use Case | Example |
|-----------|----------|---------|
| `positive` | Good news, achievements, optimistic outlook | "Strong quarter results" |
| `negative` | Bad news, declines, pessimistic outlook | "Revenue declined 15%" |
| `neutral` | Factual statements, process descriptions | "We follow our governance process" |
| `cautious` | Risk awareness, conservative positioning | "Elevated risks in current environment" |
| `confident` | Strong conviction, certainty about outcomes | "We will achieve our targets" |
| `optimistic` | Forward-looking positive expectations | "Expect continued growth" |
| `bullish` | Very positive about specific prospects | "Tremendous opportunity ahead" |
| `stable` | Steady state, no significant change | "Maintaining current levels" |

## HTML Highlighting

Use these span classes in quote_text for emphasis:

- `<span class="highlight-keyword">tariffs</span>` - Key business terms
- `<span class="highlight-figure">$500MM</span>` - Important numbers
- `<span class="highlight-time">Q3</span>` - Time references

## Key Metrics Guidelines

Extract important quantitative information into the key_metrics array:

**Include:**
- Dollar amounts: "$500MM reserve build"
- Percentages: "10% tariffs for Canada" 
- Ratios: "141% LCR"
- Time periods: "six months duration"
- Guidance ranges: "45-55 basis points"

**Format:**
- Keep original units and formatting
- Include context when helpful: "30 million shares repurchased"
- Use empty array `[]` when no metrics present

## Implementation Notes

### For LLM Extraction Prompts

1. **Section Statement**: Ask LLM to synthesize 1-2 sentences capturing the main themes and business impact
2. **Quote Selection**: Focus on material management statements with specific metrics or strategic insights
3. **Context Addition**: Add supporting data when quotes reference specific programs, figures, or need clarification
4. **Speaker Attribution**: Identify based on business unit responsibility and context clues
5. **Subsection Grouping**: Organize quotes by logical business topics within each section

### Quality Checks

- Ensure all required fields are present
- Validate sentiment values against allowed list
- Check that key_metrics contain actual quantitative data
- Verify speaker attribution is consistent
- Confirm quote_text preserves exact wording with proper highlighting

## Example Files

Reference examples are available in:
- `structured_json/01_credit.json`
- `structured_json/02_capital_and_liquidity.json`
- `structured_json/03_restructuring.json`
- etc.

## Usage in 3-Column Reports

This format enables automatic generation of 3-column reports:
- **Column 1**: `section_statement` insights
- **Column 2**: `quote_text` with embedded highlights  
- **Column 3**: `speaker` details and `sentiment` analysis

---

*Last updated: 2025-06-05*
*Project: AEGIS Transcript Analysis*