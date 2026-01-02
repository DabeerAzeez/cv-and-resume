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

Required:
- Python 3.7+
- LaTeX distribution (only MikTeX was tested here)
- CMAKE ([https://cmake.org/download/](https://cmake.org/download/))
- Notion account

Optional:
- Make (to use the Makefile commands, download [chocolatey](https://chocolatey.org/install) and then run `choco install make`)

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
   # Create .env file in root of this repo
   NOTION_TOKEN=<get token from Notion Integrations page>
   DATA_SOURCE_ID=<get database ID from database settings>
   ```

   For the data source ID you can specifically access the database's settings > Manage data sources > Copy data source ID. Note that this data source ID is NOT the id in the URL of the webpage for the database.

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

The repository includes automated CV updates via GitHub Actions:

### Automated Workflow
- **Daily Updates**: Runs every day at midnight UTC to fetch latest data from Notion
- **Manual Triggers**: Can be triggered manually from the GitHub Actions tab
- **Cache Control**: Option to force refresh Notion cache when running manually
- **Auto-commit**: Automatically commits updated CV files back to the repository

### Setup GitHub Actions

1. **Add Secrets to Repository**:
   - Go to your repository → Settings → Secrets and variables → Actions
   - Add these repository secrets:
     - `NOTION_TOKEN`: Your Notion integration token
     - `DATABASE_ID`: Your Notion database ID

2. **Enable Workflow**:
   - The workflow is automatically enabled when you push the `.github/workflows/update-cv.yml` file
   - Go to Actions tab to see workflow runs

3. **Manual Trigger**:
   - Go to Actions → Update CV → Run workflow
   - Choose whether to refresh the Notion cache
   - Click "Run workflow"

### Workflow Features
- Fetches latest data from Notion
- Compiles LaTeX to PDF
- Uploads PDF as artifact (retained for 30 days)
- Commits changes back to repository
- Skips CI on auto-commits to prevent loops

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

### XeLatex

- `XeLaTeX` was used instead of the default `latexmk` to allow different fonts

## License

MIT License - Based on original work by Jitin Nair (2021).  
Significantly modified by Dabeer Ahmad Abdul Azeez (2024).

## Contributing

Issues and pull requests are welcome. For major changes, please open an issue first to discuss the proposed changes.