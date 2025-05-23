# global_prompts/fiscal_calendar.py
"""
Fiscal Calendar Utility

Generates a fiscal context statement based on the current date.
Fiscal year runs from November 1 to October 31.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Tuple

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def validate_fiscal_year(year: int) -> bool:
    """
    Validate that a fiscal year is reasonable (not too far in past or future).
    
    Args:
        year: Fiscal year to validate
        
    Returns:
        bool: True if valid, False otherwise
    """
    current_year = datetime.now().year
    # Allow years within 10 years past and 2 years future
    return current_year - 10 <= year <= current_year + 2


def validate_fiscal_quarter(quarter: int) -> bool:
    """
    Validate that a fiscal quarter is between 1 and 4.
    
    Args:
        quarter: Fiscal quarter to validate
        
    Returns:
        bool: True if valid, False otherwise
    """
    return 1 <= quarter <= 4


def get_fiscal_period() -> Tuple[int, int]:
    """
    Calculate current fiscal year and quarter with validation.

    Returns:
        Tuple[int, int]: Fiscal year and quarter
        
    Raises:
        ValueError: If calculated values are invalid
    """
    current_date = datetime.now()
    current_month = current_date.month
    calendar_year = current_date.year

    # If we're in Nov or Dec, we're in the next fiscal year
    fiscal_year = calendar_year + 1 if current_month >= 11 else calendar_year

    # Calculate fiscal quarter (Nov-Jan = Q1, Feb-Apr = Q2, May-Jul = Q3, Aug-Oct = Q4)
    # Map calendar months to fiscal quarters
    fiscal_quarter_map = {
        11: 1,
        12: 1,
        1: 1,  # Q1: Nov-Jan
        2: 2,
        3: 2,
        4: 2,  # Q2: Feb-Apr
        5: 3,
        6: 3,
        7: 3,  # Q3: May-Jul
        8: 4,
        9: 4,
        10: 4,  # Q4: Aug-Oct
    }
    fiscal_quarter = fiscal_quarter_map[current_month]
    
    # Validate results
    if not validate_fiscal_year(fiscal_year):
        raise ValueError(f"Invalid fiscal year calculated: {fiscal_year}")
    if not validate_fiscal_quarter(fiscal_quarter):
        raise ValueError(f"Invalid fiscal quarter calculated: {fiscal_quarter}")

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
        2: 2,  # Feb
        3: 5,  # May
        4: 8,  # Aug
    }

    # Map fiscal quarters to their end months in the calendar year
    quarter_end_months = {
        1: 1,  # Jan
        2: 4,  # Apr
        3: 7,  # Jul
        4: 10,  # Oct
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


def get_quarter_range_str(fiscal_quarter: int) -> str:
    """
    Get a formatted string describing the date range for a fiscal quarter.

    Args:
        fiscal_quarter (int): The fiscal quarter (1-4)

    Returns:
        str: Formatted date range string
    """
    quarter_ranges = {
        1: "November 1st to January 31st",
        2: "February 1st to April 30th",
        3: "May 1st to July 31st",
        4: "August 1st to October 31st",
    }

    return quarter_ranges.get(fiscal_quarter, "Invalid quarter")


def get_fiscal_statement() -> str:
    """
    Generate a natural language statement about the current fiscal period.
    Uses XML-style delimiters for better sectioning.

    Returns:
        str: Formatted fiscal statement
    """
    try:
        current_date = datetime.now()
        formatted_date = current_date.strftime("%Y-%m-%d")  # Format as YYYY-MM-DD
        fiscal_year, fiscal_quarter = get_fiscal_period()
        current_quarter_range = get_quarter_range_str(fiscal_quarter)

        statement = f"""<FISCAL_CONTEXT>
<CURRENT_DATE>{formatted_date}</CURRENT_DATE>
<FISCAL_YEAR>{fiscal_year} (FY{fiscal_year})</FISCAL_YEAR>
<FISCAL_QUARTER>{fiscal_quarter} (Q{fiscal_quarter})</FISCAL_QUARTER>
<QUARTER_RANGE>{current_quarter_range}</QUARTER_RANGE>
<FISCAL_YEAR_DEFINITION>Our fiscal year runs from November 1st through October 31st.</FISCAL_YEAR_DEFINITION>
<EARNINGS_CALENDAR>
<TYPICAL_REPORTING_LAG>Banks typically report quarterly earnings 6-8 weeks after quarter end</TYPICAL_REPORTING_LAG>
<DATA_AVAILABILITY>
- If current date is within 8 weeks of quarter end, latest quarter data may not be available
- Always check actual data availability rather than assuming based on calendar
</DATA_AVAILABILITY>
</EARNINGS_CALENDAR>
</FISCAL_CONTEXT>"""

        return statement
    except Exception as e:
        logger.error(f"Error generating fiscal statement: {str(e)}")
        # Fallback statement in case of errors
        return "<FISCAL_CONTEXT>We operate on a fiscal year that runs from November 1st through October 31st.</FISCAL_CONTEXT>"


def calculate_relative_quarter(base_year: int, base_quarter: int, quarters_offset: int) -> Tuple[int, int]:
    """
    Calculate a fiscal quarter relative to a base quarter.
    
    Args:
        base_year: Base fiscal year
        base_quarter: Base fiscal quarter (1-4)
        quarters_offset: Number of quarters to offset (negative for past, positive for future)
        
    Returns:
        Tuple[int, int]: Target fiscal year and quarter
        
    Raises:
        ValueError: If inputs are invalid
    """
    if not validate_fiscal_year(base_year):
        raise ValueError(f"Invalid base fiscal year: {base_year}")
    if not validate_fiscal_quarter(base_quarter):
        raise ValueError(f"Invalid base fiscal quarter: {base_quarter}")
        
    # Calculate total quarters from start of fiscal time
    total_quarters = (base_year - 2000) * 4 + base_quarter + quarters_offset
    
    # Calculate target year and quarter
    target_year = 2000 + (total_quarters - 1) // 4
    target_quarter = ((total_quarters - 1) % 4) + 1
    
    if not validate_fiscal_year(target_year):
        raise ValueError(f"Calculated year {target_year} is out of valid range")
    
    return target_year, target_quarter


def test_fiscal_period_calculation():
    """
    Test function to verify the fiscal period calculation for different months.
    This can be run manually to debug fiscal period issues.
    """
    from datetime import datetime

    # Test for each month
    for month in range(1, 13):
        test_date = datetime(2025, month, 15)  # Use the 15th of each month
        current_month = test_date.month
        calendar_year = test_date.year

        # Calculate fiscal year
        fiscal_year = calendar_year + 1 if current_month >= 11 else calendar_year

        # Map calendar months to fiscal quarters
        fiscal_quarter_map = {
            11: 1,
            12: 1,
            1: 1,  # Q1: Nov-Jan
            2: 2,
            3: 2,
            4: 2,  # Q2: Feb-Apr
            5: 3,
            6: 3,
            7: 3,  # Q3: May-Jul
            8: 4,
            9: 4,
            10: 4,  # Q4: Aug-Oct
        }
        fiscal_quarter = fiscal_quarter_map[current_month]

        print(
            f"Date: {test_date.strftime('%Y-%m-%d')}, Fiscal Year: {fiscal_year}, Fiscal Quarter: Q{fiscal_quarter}"
        )
