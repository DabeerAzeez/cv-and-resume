# Dynamic CV Generator

A LaTeX-based CV generator that automatically pulls data from Notion and generates a professional PDF. Based on the [autoCV template](https://github.com/jitinnair1/autoCV) by [jitinnair1](https://github.com/jitinnair1).

## Features

- **Notion Integration**: Automatically syncs with your Notion database
- **Jinja2 Templating**: Dynamic content generation with LaTeX formatting
- **Automated Workflow**: GitHub Actions for continuous deployment
- **Caching System**: Reduces API calls with intelligent caching
- **Multiple Sections**: Work Experience, Education, Projects, Leadership and Other Experience, Awards, Publications
- **Date Sorting**: Automatically sorts entries chronologically (newest first)

## Quick Start

### 1. Prerequisites

- Python 3.7+
- LaTeX distribution (MiKTeX, TeX Live, or Overleaf)
- Notion account

### 2. Setup

1. **Fork and clone this repository**
2. **Create a Notion database** with these columns:
   - `Name` (Title)
   - `Type` (Select: Work Experience, Education, Projects, Leadership and Other Experience, Awards, Publications)
     > These are the section types currently supported by the template.  
     > If you want to add more types (e.g., Certifications, Volunteering), you must also update the Jinja2 template in `cv_template.tex` and the logic in `update_cv.py` to handle and render those new types correctly.
   - `Organization` (Text)
   - `Location` (Text)
   - `Start Date` (Date)
   - `End Date` (Date)
   - `Show on CV?` (Checkbox)

3. **Get Notion API credentials**:
   - Create integration at [notion.so/my-integrations](https://notion.so/my-integrations)
   - Copy the integration token
   - Share your database with the integration

4. **Configure environment variables**:
   ```bash
   # Create .env file
   NOTION_TOKEN=secret_your_token_here
   DATABASE_ID=your_database_id_here
   ```

5. **Install dependencies**:
   ```bash
   pip install notion-client python-dotenv Jinja2
   ```

### 3. Usage

```bash
# Generate CV from Notion data
make all

# Individual commands
make update    # Fetch from Notion and generate cv.tex
make pdf       # Compile LaTeX to PDF
make clean     # Remove temporary files
```

## Configuration

### Notion Database Setup

The database requires specific column names and types for proper integration:

| Column | Type | Description |
|--------|------|-------------|
| Name | Title | Entry title/name |
| Type | Select | Section type (Work Experience, Education, etc.) |
| Organization | Text | Company/institution name |
| Location | Text | Geographic location |
| Start Date | Date | Start date |
| End Date | Date | End date (optional) |
| Show on CV? | Checkbox | Include in CV |

### Content Organization

Each database entry can include rich content in the page body:
- Use "For Resume" heading for content to include
- Use "Not For Resume" heading for content to exclude
- Supports rich text formatting (bold, italic, links, etc.)

## File Structure

```
cv-and-resume/
├── cv_template.tex      # Jinja2 LaTeX template
├── update_cv.py         # Notion integration script
├── Makefile            # Build commands
├── .env                # Environment variables
└── notion_cache.json   # API response cache
```

## GitHub Actions

The repository includes automated deployment via GitHub Actions:
- Builds PDF on every push
- Deploys to GitHub Pages
- Available at `https://username.github.io/repo-name/`

## Customization

### Template Modifications

Edit `cv_template.tex` to customize:
- Contact information
- Section ordering
- Styling and formatting
- Static content (Summary, Skills)

### Manually Edited Sections

The Summary section is manually written. One suggestion is to feed your CV to an AI chatbot and have it create a short CV summary for you. The Skills section is also manually curated. Again, I'd suggest a mix of getting AI suggestions and manual updates.

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "No CV data found" | Check `.env` file and database permissions |
| LaTeX compilation fails | Install LaTeX distribution |
| Notion API errors | Verify token and database ID |
| Make command not found | Use PowerShell or install make |

## Development

### Adding New Section Types

1. Add new type to `TYPES_LONG` or `TYPES_SHORT` in `update_cv.py`
2. Update template logic in `cv_template.tex`
3. Test with sample data

### Caching

- Cache expires after 1 hour
- Use `--refresh` flag to force update
- Cache file: `notion_cache.json`

## License

MIT License - Based on original work by Jitin Nair (2021).  
Significantly modified by Dabeer Ahmad Abdul Azeez (2024).

## Contributing

Issues and pull requests are welcome. For major changes, please open an issue first to discuss the proposed changes.