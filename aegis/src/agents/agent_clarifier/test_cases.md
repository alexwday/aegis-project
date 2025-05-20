# Clarifier Agent Test Cases

This document contains sample questions for testing the clarifier agent's ability to identify intent, years, quarters, banks, and metrics from user queries.

## Basic Queries

1. "What was BMO's revenue in Q2 2024?"
   - Intent: Retrieve BMO's revenue for Q2 2024
   - Years: [2024]
   - Quarters: [2]
   - Banks: ["BMO"]
   - Metrics: ["Revenue"]

2. "What was RBC's net income last quarter?"
   - Intent: Retrieve RBC's net income for Q1 2025 (assuming current quarter is Q2 2025)
   - Years: [2025]
   - Quarters: [1]
   - Banks: ["RBC"]
   - Metrics: ["Net Income"]

3. "Show me TD's efficiency ratio."
   - Intent: Retrieve TD's efficiency ratio for the current quarter
   - Years: [2025]
   - Quarters: [2]
   - Banks: ["TD"]
   - Metrics: ["Efficiency Ratio"]

## Multiple Banks

4. "Compare RBC and TD's net income for Q1 2025."
   - Intent: Compare net income between RBC and TD for Q1 2025
   - Years: [2025]
   - Quarters: [1]
   - Banks: ["RBC", "TD"]
   - Metrics: ["Net Income"]

5. "How did the big five Canadian banks perform in terms of revenue last quarter?"
   - Intent: Compare revenue performance across the big five Canadian banks for Q1 2025
   - Years: [2025]
   - Quarters: [1]
   - Banks: ["RBC", "TD", "BMO", "CIBC", "Scotiabank"]
   - Metrics: ["Revenue"]

## Multiple Metrics

6. "What were BMO's revenue and net income in Q2 2024?"
   - Intent: Retrieve BMO's revenue and net income for Q2 2024
   - Years: [2024]
   - Quarters: [2]
   - Banks: ["BMO"]
   - Metrics: ["Revenue", "Net Income"]

7. "Compare RBC and TD's efficiency ratio and net interest margin for Q1 2025."
   - Intent: Compare efficiency ratio and net interest margin between RBC and TD for Q1 2025
   - Years: [2025]
   - Quarters: [1]
   - Banks: ["RBC", "TD"]
   - Metrics: ["Efficiency Ratio", "Net Interest Margin"]

## Multiple Time Periods

8. "How has BMO's revenue changed over the past 4 quarters?"
   - Intent: Analyze BMO's revenue trend over the past 4 quarters
   - Years: [2024, 2025]
   - Quarters: [3, 4, 1, 2]
   - Banks: ["BMO"]
   - Metrics: ["Revenue"]

9. "Compare RBC's net income in Q1 2025 to Q1 2024."
   - Intent: Compare RBC's net income between Q1 2025 and Q1 2024
   - Years: [2024, 2025]
   - Quarters: [1]
   - Banks: ["RBC"]
   - Metrics: ["Net Income"]

10. "Show quarterly trend of TD's efficiency ratio for the full year 2024."
    - Intent: Analyze quarterly trend of TD's efficiency ratio throughout 2024
    - Years: [2024]
    - Quarters: [1, 2, 3, 4]
    - Banks: ["TD"]
    - Metrics: ["Efficiency Ratio"]

## Relative Time References

11. "What was BMO and RBC's net income last quarter compared to the year before?"
    - Intent: Compare BMO and RBC's net income between Q1 2025 and Q1 2024
    - Years: [2024, 2025]
    - Quarters: [1]
    - Banks: ["BMO", "RBC"]
    - Metrics: ["Net Income"]

12. "How did TD's revenue this quarter compare to the previous quarter?"
    - Intent: Compare TD's revenue between Q2 2025 and Q1 2025
    - Years: [2025]
    - Quarters: [1, 2]
    - Banks: ["TD"]
    - Metrics: ["Revenue"]

## Ambiguous Queries (Should Request Clarification)

13. "How did the banks perform last quarter?"
    - Missing specific banks
    - Missing specific metrics
    - Should request clarification

14. "What are the latest financial results?"
    - Missing specific banks
    - Missing specific metrics
    - Should request clarification

15. "Compare the dividend yields."
    - Missing specific banks
    - Missing specific time periods
    - Should request clarification

16. "Has the efficiency ratio improved?"
    - Missing specific bank
    - Missing specific time period for comparison
    - Should request clarification

## Complex Queries

17. "For each of the big five Canadian banks, what was their revenue, net income, and efficiency ratio in Q1 2025 compared to Q1 2024?"
    - Intent: Compare revenue, net income, and efficiency ratio for the big five Canadian banks between Q1 2025 and Q1 2024
    - Years: [2024, 2025]
    - Quarters: [1]
    - Banks: ["RBC", "TD", "BMO", "CIBC", "Scotiabank"]
    - Metrics: ["Revenue", "Net Income", "Efficiency Ratio"]

18. "Which bank had the highest net interest margin in Q1 2025, and how does that compare to their performance over the previous 4 quarters?"
    - Intent: Identify bank with highest net interest margin in Q1 2025 and analyze trend over 5 quarters
    - Years: [2024, 2025]
    - Quarters: [1, 2, 3, 4] (2024), [1] (2025)
    - Banks: Should request specific banks or default to major Canadian banks
    - Metrics: ["Net Interest Margin"]

19. "Show me how BMO and RBC's loan loss provisions have trended over 2024 and compare to their net income in the same period."
    - Intent: Compare trends in loan loss provisions and net income for BMO and RBC throughout 2024
    - Years: [2024]
    - Quarters: [1, 2, 3, 4]
    - Banks: ["BMO", "RBC"]
    - Metrics: ["Provision for Credit Losses", "Net Income"]

## Aliases and Alternate Names

20. "What was Royal Bank's profit in Q1 2025 compared to Bank of Montreal?"
    - Intent: Compare profit between RBC and BMO for Q1 2025
    - Years: [2025]
    - Quarters: [1]
    - Banks: ["RBC", "BMO"]
    - Metrics: ["Net Income"]

21. "How is Scotia's efficiency ratio trending compared to CIBC over the past 2 quarters?"
    - Intent: Compare efficiency ratio trends between Scotiabank and CIBC over the past 2 quarters
    - Years: [2025]
    - Quarters: [1, 2]
    - Banks: ["Scotiabank", "CIBC"]
    - Metrics: ["Efficiency Ratio"]

## Metrics with Different Names

22. "What was BMO's bottom line last quarter?"
    - Intent: Retrieve BMO's net income for Q1 2025
    - Years: [2025]
    - Quarters: [1]
    - Banks: ["BMO"]
    - Metrics: ["Net Income"]

23. "Compare RBC and TD's top line for Q2 2024."
    - Intent: Compare revenue between RBC and TD for Q2 2024
    - Years: [2024]
    - Quarters: [2]
    - Banks: ["RBC", "TD"]
    - Metrics: ["Revenue"]