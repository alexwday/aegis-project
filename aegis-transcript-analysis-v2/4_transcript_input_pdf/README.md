# Transcript Input PDF Folder

Place your earnings call transcript PDF files in this folder for processing.

## Usage

1. Copy your PDF transcript file(s) into this folder
2. Run `5_create_research_plan.py` to process the transcript(s)
3. The system will extract text from the PDF and create iterative research plans

## Expected File Format

- PDF files containing earnings call transcripts
- Files should be readable text PDFs (not scanned images)
- One transcript per PDF file

## Processing Flow

1. PDF text extraction
2. Section-by-section research plan creation
3. Iterative context building (each section builds on prior sections)
4. Output saved to `6_research_plan.json`

## Notes

- The system processes one PDF at a time
- If multiple PDFs are present, it will process the first one found
- Ensure PDF files are properly formatted for text extraction