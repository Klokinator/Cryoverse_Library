# Agent Plan: Cryoverse Automated Wordcounter

This plan outlines the implementation of an automated wordcounting utility for the Cryoverse library.

## Goals
- Calculate cleaned word and character counts for every part/chapter in the repository.
- Exclude titles, Author Notes (AN), dividers (`---`, `...`), URLs, and markdown formatting characters (`*`, `_`).
- Maintain granularity at the folder level and an overview at the root level.
- Provide a simple one-click update mechanism.

## Components
1. **`.utils/wordcounter.py`**: A Python script that handles the heavy lifting of cleaning and counting.
2. **`update_counts.bat`**: A batch file in the root to run the Python script.
3. **`index.json`**: Per-folder index files for programmatic access.
4. **`.utils/global_index.json`**: A root-level index file for cumulative totals.
5. **`README.md` Updates**: Automated formatting of wordcounts into folder and root readmes.

## Cleaning Logic
- **Title Skip**: The first line of every file is skipped.
- **Author Note Skip**: Lines at the top and bottom starting with or containing `**Author Note:**`, `**A/N:**`, `**AN:**`, or `**AUTHOR NOTE!**` are skipped, along with the blocks they belong to.
- **Divider Skip**: Lines consisting solely of `---` or `...` are ignored.
- **Character/URL Strip**: URLs (http/https), asterisks, and underscores are removed before counting.

## Execution
1. Traverse all directories.
2. For each `.txt` file, apply cleaning and count words/characters.
3. Aggregate totals per folder.
4. Update/Create `index.json` in subfolders and `global_index.json` in root.
5. Insert wordcount tables into subfolder `README.md` files after `# --- Wordcounts ---`.
6. Insert folder totals into root `README.md` under `<details>` spoilers.

## Schedule
- [x] Create `wordcounter.py`
- [x] Create `update_counts.bat`
- [x] Run the utility and verify results.
