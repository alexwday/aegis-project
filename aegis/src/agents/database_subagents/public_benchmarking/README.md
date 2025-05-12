# Public Benchmarking Subagent

This subagent handles retrieving and processing financial benchmarking data from major US and Canadian banks.

## Purpose

Financial benchmarking data provides comparative metrics across institutions and time periods. This subagent enables:

- Comparing performance metrics across different banks
- Analyzing trends in financial metrics over time (QoQ, YoY)
- Benchmarking specific financial ratios and indicators
- Identifying industry trends and outliers

## Functionality

The subagent implements a multi-step retrieval and synthesis process:

1. **Catalog Selection**: Identifies relevant benchmark data sets based on the query
2. **Data Retrieval**: Fetches and processes relevant metrics and comparisons
3. **Data Synthesis**: Generates structured, detailed responses with proper attribution and data visualization suggestions

## Data Structure

The benchmarking data is structured with the following elements:

- Bank identifiers
- Time periods (quarterly data)
- Metric categories (capital, profitability, asset quality, etc.)
- Specific metrics with values and units
- Change indicators (QoQ, YoY)

## Integration

This subagent is registered with the database router and can be accessed through the standard agent pipeline.
