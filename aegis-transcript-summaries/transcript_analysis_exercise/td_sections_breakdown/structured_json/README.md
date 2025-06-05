# TD Business Summary - Structured JSON Format

This folder contains the TD earnings call summary converted into structured JSON format for each of the 8 main sections. Each JSON file follows a consistent schema designed for the new 3-column report format.

## JSON Schema Structure

Each section JSON file contains:

### Top-Level Fields
- **section_name**: Short section identifier
- **section_title**: Full section heading as it appears in the summary
- **section_statement**: AI-generated paraphrased summary of the key points in the section
- **content**: Array of subsections with quotes and metadata

### Content Structure
Each content item has:
- **subsection**: The specific topic within the section
- **quotes**: Array of individual quotes with full metadata

### Quote Structure
Each quote contains:
- **quote_text**: The exact quote from the transcript
- **context**: Additional clarifying information (null if not needed)
- **speaker**: Object with name, title, and company
- **sentiment**: AI-generated sentiment assessment
- **sentiment_rationale**: Explanation for the sentiment classification
- **key_metrics**: Array of important numbers/metrics mentioned in the quote

## Sentiment Classifications Used

- **positive**: Clearly good news, achievements, or optimistic outlook
- **negative**: Bad news, declines, or pessimistic outlook  
- **neutral**: Factual statements, process descriptions, balanced commentary
- **cautious**: Risk awareness, conservative positioning, uncertainty
- **confident**: Strong conviction, certainty about outcomes
- **optimistic**: Forward-looking positive expectations
- **bullish**: Very positive about specific business prospects
- **stable**: Steady state, no significant change expected

## Files Included

1. **01_credit.json** - Credit portfolio and reserve analysis
2. **02_capital_and_liquidity.json** - Capital deployment and liquidity management
3. **03_restructuring.json** - Efficiency programs and strategic transformation
4. **04_us_retail_bank.json** - U.S. operations and balance sheet restructuring
5. **05_canadian_pc_banking.json** - Canadian personal and commercial banking
6. **06_wealth_management_insurance.json** - Wealth and insurance businesses
7. **07_wholesale_banking.json** - Investment banking and trading
8. **08_corporate_segment.json** - Corporate segment results

## Key Observations

- **Quote Selection**: Focused on material management statements with specific metrics
- **Context Addition**: Added where quotes needed clarification or supporting data
- **Speaker Attribution**: Identified based on business unit responsibility and content context
- **Sentiment Analysis**: Reflects both explicit tone and business implications
- **Metrics Extraction**: Captured key financial figures, percentages, and targets

This structured format enables the new 3-column report generation with:
- Column 1: section_statement insights
- Column 2: quote_text with embedded key_metrics
- Column 3: speaker details and sentiment analysis