#!/usr/bin/env python3
"""
Generate HTML report from JSON sections using template
"""

import json
import os
from pathlib import Path


def load_json_section(filepath):
    """Load a JSON section file"""
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)





def generate_section_html(section_data):
    """Generate HTML for a single section with card/tile structure"""
    section_html = f"""
    <div class="section">
        <div class="section-header">
            <h2>{section_data['section_title']}</h2>
            <div class="description">{section_data['section_statement']}</div>
        </div>
        <div class="quotes-container">
"""
    
    # Process each subsection and its quotes
    for content_item in section_data['content']:
        subsection = content_item['subsection']
        
        # Add each quote as a tile
        for quote in content_item['quotes']:
            # Use the quote text directly (already has highlighting from JSON)
            quote_text = quote['quote_text']
            
            # Generate sentiment class
            sentiment_class = f"sentiment-{quote['sentiment']}"
            
            section_html += f"""
            <div class="quote-tile">
                <div class="tile-header">
                    <h3 class="tile-title">{subsection}</h3>
                </div>
                <div class="content-row">
                    <div class="quote-column">
                        <div class="quote">{quote_text}</div>"""
            
            # Add context if it exists
            if quote.get('context'):
                section_html += f"""
                        <div class="context">{quote['context']}</div>"""
            
            section_html += f"""
                    </div>
                    <div class="attribution-column">
                        <div class="speaker">{quote['speaker']['name']}</div>
                        <div class="title">{quote['speaker']['title']}, {quote['speaker']['company']}</div>
                        <div class="sentiment {sentiment_class}">
                            {quote['sentiment'].title()}
                        </div>
                    </div>
                </div>
            </div>
"""
    
    section_html += """        </div>
    </div>
"""
    return section_html


def main():
    """Main function to generate the report"""
    
    # Paths
    script_dir = Path(__file__).parent
    json_dir = script_dir / "structured_json"
    template_path = script_dir / "template.html"
    output_path = script_dir / "td_earnings_report.html"
    
    # Load template
    with open(template_path, 'r', encoding='utf-8') as f:
        template = f.read()
    
    # Find all JSON files
    json_files = sorted([f for f in os.listdir(json_dir) if f.endswith('.json') and not f.startswith('README')])
    
    print(f"Found {len(json_files)} JSON section files")
    
    # Load all sections
    sections = []
    for json_file in json_files:
        filepath = json_dir / json_file
        section_data = load_json_section(filepath)
        sections.append(section_data)
        print(f"Loaded: {section_data['section_name']}")
    
    # Generate HTML for all sections
    sections_html = ""
    for section_data in sections:
        section_html = generate_section_html(section_data)
        sections_html += section_html
    
    # Replace template placeholders
    final_html = template.replace("{{REPORT_TITLE}}", "TD Bank Q2 2025 Earnings Analysis")
    final_html = final_html.replace("{{REPORT_SUBTITLE}}", "AI-Enhanced Transcript Intelligence Report")
    final_html = final_html.replace("{{SECTIONS}}", sections_html)
    
    # Write output file
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(final_html)
    
    print(f"\nReport generated successfully: {output_path}")
    print(f"Total sections processed: {len(sections)}")
    
    # Count total quotes
    total_quotes = sum(len(content['quotes']) for section in sections for content in section['content'])
    print(f"Total quotes processed: {total_quotes}")


if __name__ == "__main__":
    main()