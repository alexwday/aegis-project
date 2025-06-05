#!/usr/bin/env python3
"""
Document Template Extraction Script

This script extracts section information from the HTML template file and converts it
to a structured JSON format for further processing in the analysis pipeline.

Input: 0_document_template.html (HTML template with section definitions)
Output: 2_section_instructions.json (Structured section data)
"""

import json
import re
from pathlib import Path
from bs4 import BeautifulSoup


def extract_section_data(html_content):
    """
    Extract section data from HTML template.

    Args:
        html_content (str): HTML content from the template file

    Returns:
        list: List of section dictionaries with name and description
    """
    soup = BeautifulSoup(html_content, "html.parser")
    sections = []

    # Find all section rows in the table
    section_rows = soup.find_all("tr", class_="section-row")

    for row in section_rows:
        section_data = {}

        # Extract section ID from data attribute
        section_id = row.get("data-section-id", "")
        section_data["section_id"] = section_id

        # Extract section name
        section_name_elem = row.find("div", class_="section-name")
        if section_name_elem:
            section_data["section_name"] = section_name_elem.get_text(strip=True)

        # Extract section description from the visible description
        section_desc_elem = row.find("div", class_="section-desc")
        if section_desc_elem:
            section_data["section_description"] = section_desc_elem.get_text(strip=True)

        # Check if section is enabled (checkbox checked)
        checkbox = row.find("input", class_="section-checkbox")
        section_data["enabled"] = checkbox and checkbox.get("checked") is not None

        # Extract detailed description from the textarea in the details row
        details_row = row.find_next_sibling("tr", class_="section-details-row")
        if details_row:
            textarea = details_row.find("textarea", class_="detail-textarea")
            if textarea:
                detailed_description = textarea.get_text(strip=True)
                if detailed_description:
                    section_data["detailed_description"] = detailed_description
                else:
                    # Use the visible description as fallback
                    section_data["detailed_description"] = section_data.get(
                        "section_description", ""
                    )

        # Only add sections that have meaningful content
        if section_data.get("section_name"):
            sections.append(section_data)

    return sections


def clean_and_format_sections(sections):
    """
    Clean and format section data for better JSON output.

    Args:
        sections (list): Raw section data list

    Returns:
        list: Cleaned and formatted section data
    """
    cleaned_sections = []

    for section in sections:
        cleaned_section = {
            "section_id": section.get("section_id", ""),
            "section_name": section.get("section_name", ""),
            "enabled": section.get("enabled", True),
            "description": section.get(
                "detailed_description", section.get("section_description", "")
            ),
        }

        # Clean up the description text
        description = cleaned_section["description"]
        if description:
            # Remove extra whitespace and normalize line breaks
            description = re.sub(r"\s+", " ", description)
            description = description.replace("\\n", "\n")
            cleaned_section["description"] = description.strip()

        cleaned_sections.append(cleaned_section)

    return cleaned_sections


def main():
    """Main function to extract template data and save as JSON."""

    # Define file paths
    template_file = Path("0_document_template.html")
    output_file = Path("2_section_instructions.json")

    # Check if template file exists
    if not template_file.exists():
        print(f"Error: Template file '{template_file}' not found.")
        return

    try:
        # Read HTML template
        print(f"Reading template file: {template_file}")
        with open(template_file, "r", encoding="utf-8") as f:
            html_content = f.read()

        # Extract section data
        print("Extracting section data from template...")
        sections = extract_section_data(html_content)

        # Clean and format sections
        print("Cleaning and formatting section data...")
        cleaned_sections = clean_and_format_sections(sections)

        # Create output structure
        output_data = {
            "metadata": {
                "source_file": str(template_file),
                "extraction_timestamp": "2024-01-01T00:00:00Z",
                "total_sections": len(cleaned_sections),
                "enabled_sections": sum(1 for s in cleaned_sections if s["enabled"]),
            },
            "sections": cleaned_sections,
        }

        # Save to JSON file
        print(f"Saving extracted data to: {output_file}")
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)

        print(f"Successfully extracted {len(cleaned_sections)} sections")
        print(f"Output saved to: {output_file}")

        # Print summary
        print("\nExtracted sections:")
        for i, section in enumerate(cleaned_sections, 1):
            status = "✓" if section["enabled"] else "✗"
            print(f"  {i:2d}. {status} {section['section_name']}")

    except Exception as e:
        print(f"Error during extraction: {e}")
        raise


if __name__ == "__main__":
    main()
