# CV Generator Makefile
# Simple commands to manage the CV generation workflow

NAME=cv

# Main workflow: update from Notion, build PDF, and open it
all: update pdf open

# Fetch latest data from Notion and generate cv.tex
update:
	python update_cv.py

# Compile the LaTeX file to PDF using latexmk
pdf:
	latexmk -pdf ${NAME}.tex

# Open the generated PDF in the default viewer (Windows)
open:
	powershell -Command "Invoke-Item '${NAME}.pdf'"

# Remove LaTeX helper files (aux, log, etc.) - keeps PDF
clean:
	del /q *.aux *.bbl *.bcf *.fdb_latexmk *.fls *.log *.out *.run.xml *.blg *.toc *.synctex.gz *~ 2>nul

# Remove only the PDF file
clean-pdf:
	del /q ${NAME}.pdf 2>nul

# Remove the Notion API cache to force fresh data fetch
clean-cache:
	del /q notion_cache.json 2>nul

# Remove everything: helper files, PDF, and cache
clean-all: clean clean-pdf clean-cache

# Alias for clean-all (same thing, different name)
distclean: clean-all