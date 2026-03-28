# 📚 kindle-publisher

**One command to rule them all:** JSON/Markdown content → PDF + EPUB → Send to Kindle.

No manual steps. No file juggling. Write your content, run the command, and it lands on your Kindle.

---

## ✨ Features

- **PDF Generation** — Polished A4 documents with table of contents, bookmarks, callout boxes, code blocks, tables, and more (powered by ReportLab)
- **EPUB Generation** — Reflowable, Kindle-optimized EPUB with proper chapter splitting, semantic HTML, and clean CSS (powered by EbookLib)
- **Send to Kindle** — Delivers the EPUB directly to your Kindle via email (SMTP)
- **Dual Input** — Accepts both JSON content models and Markdown/plain-text files
- **Single Content Model** — One JSON file drives both PDF and EPUB outputs

## 🚀 Quick Start

### 1. Install dependencies

```bash
pip install reportlab ebooklib
```

### 2. Set up Kindle delivery (one-time)

Set these environment variables with your email credentials:

```bash
# Windows (PowerShell)
setx KINDLE_EMAIL "yourname@kindle.com"
setx SENDER_EMAIL "you@gmx.com"
setx SENDER_PASS "your-email-password"

# Linux/macOS
export KINDLE_EMAIL="yourname@kindle.com"
export SENDER_EMAIL="you@gmx.com"
export SENDER_PASS="your-email-password"
```

> **Important:** Make sure your sender email is added to Amazon's
> [Approved Personal Document E-mail List](https://www.amazon.com/hz/mycd/myx#/home/settings/payment),
> or deliveries will be silently rejected.

### 3. Run it

```bash
# Full pipeline: PDF + send to Kindle
python publish.py content.json --pdf --kindle

# Just PDF
python publish.py content.json --pdf

# Just EPUB (without sending)
python publish.py content.json --epub

# EPUB + send to Kindle
python publish.py content.json --kindle

# Works with Markdown too
python publish.py guide.md --pdf --kindle
```

## 📄 Content Model

Create a JSON file with your content. Here's a minimal example:

```json
{
  "title": "My Guide",
  "lang": "en",
  "toc": true,
  "blocks": [
    { "type": "h1", "text": "Getting Started" },
    { "type": "p", "text": "Welcome to the guide." },
    { "type": "steps", "items": ["Install it", "Configure it", "Run it"] },
    { "type": "h1", "text": "Configuration" },
    { "type": "code", "lines": ["python publish.py guide.json --kindle"] },
    { "type": "warning", "text": "Never commit your credentials." }
  ]
}
```

### Supported Block Types

| Type | Description |
|------|-------------|
| `h1`, `h2`, `h3` | Headings (h1 creates new EPUB chapters) |
| `p` | Paragraph with **bold**, *italic*, `code` support |
| `bullets` | Unordered list |
| `steps` | Numbered step-by-step list |
| `code` | Fenced code block with line array |
| `table` | Table with headers, rows, and optional column ratios |
| `note`, `tip`, `warning`, `caution`, `important` | Callout boxes |
| `boxes` | Box diagram for architecture/flow visualization |
| `footnotes` | Numbered footnotes |
| `hr`, `spacer`, `pagebreak` | Layout helpers |

### Top-Level Fields

| Field | Required | Description |
|-------|----------|-------------|
| `title` | Yes | Document title |
| `subtitle` | No | Subtitle shown below title |
| `lang` | No | Language code (`en`, `pt-BR`, etc.) |
| `toc` | No | Include table of contents |
| `numbered` | No | Auto-number headings |
| `doc_kind` | No | `tutorial`, `howto`, `reference`, `explanation` |
| `audience` | No | Target audience (shown in PDF header) |
| `summary` | No | Summary paragraph shown before TOC |
| `keywords` | No | PDF metadata keywords |
| `footer` | No | Footer text |

## 🏗️ Project Structure

```
kindle-publisher/
├── publish.py              # CLI entry point
├── engines/
│   ├── pdf_engine.py       # PDF generation (ReportLab)
│   ├── epub_engine.py      # EPUB generation (EbookLib)
│   └── kindle_sender.py    # SMTP email sender
├── tests/                  # 10 tests covering all components
├── sample.json             # Example content to try
└── requirements.txt
```

## 🧪 Running Tests

```bash
python -m pytest tests/ -v
```

All tests mock the SMTP layer — no real emails are sent during testing.

## 🔒 Security

- **No credentials in the codebase** — all secrets are read from environment variables at runtime
- Test files use only fake/dummy email addresses
- The `.gitignore` excludes generated PDF and EPUB files

## 📋 Requirements

- Python 3.10+
- [ReportLab](https://pypi.org/project/reportlab/) — PDF generation
- [EbookLib](https://pypi.org/project/ebooklib/) — EPUB generation
- An email account with SMTP access (configured for GMX by default)

## 🔧 Customizing the SMTP Provider

The default SMTP configuration uses GMX (`mail.gmx.com:587`). To use a different provider, edit the constants in `engines/kindle_sender.py`:

```python
SMTP_HOST = "smtp.your-provider.com"
SMTP_PORT = 587
```

For Gmail, you'll need an [App Password](https://support.google.com/accounts/answer/185833) instead of your regular password.

## 📝 License

MIT

---

Built with ReportLab, EbookLib, and a healthy dislike of reading PDFs on Kindle.
