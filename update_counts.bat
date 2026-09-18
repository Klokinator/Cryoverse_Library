@echo off
git config core.hooksPath .githooks
python .utils\booktool.py all
pause
