# kindle-publisher

CLI tool: JSON/Markdown content → PDF + EPUB → Send to Kindle.

## Structure
- `publish.py` — CLI entry point
- `engines/pdf_engine.py` — PDF generation (from pdf-doc skill)
- `engines/epub_engine.py` — EPUB generation via ebooklib
- `engines/kindle_sender.py` — SMTP sender (GMX)

## Environment Variables (required for --kindle)
- KINDLE_EMAIL — Kindle Send-to-Kindle address
- SENDER_EMAIL — GMX sender email
- SENDER_PASS — GMX password

## Usage
python publish.py content.json --pdf --kindle
