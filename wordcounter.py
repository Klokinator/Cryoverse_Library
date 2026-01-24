import os
import re
import json

def clean_text(text_lines):
    if not text_lines:
        return 0, 0, 0

    # Skip first line (Title)
    lines = text_lines[1:]
    
    # Skip Author Notes at the top
    start_idx = 0
    while start_idx < len(lines):
        line = lines[start_idx].strip()
        if not line:
            start_idx += 1
            continue
        if any(marker in line.upper() for marker in ["**AUTHOR NOTE:", "**A/N:", "**AN:", "**AUTHOR NOTE!"]):
            # Find the end of this block (usually an empty line or a divider)
            while start_idx < len(lines) and lines[start_idx].strip():
                start_idx += 1
            continue
        break
    
    lines = lines[start_idx:]
    
    # Skip Author Notes at the bottom
    end_idx = len(lines)
    while end_idx > 0:
        line = lines[end_idx-1].strip()
        if not line:
            end_idx -= 1
            continue
        if any(marker in line.upper() for marker in ["**AUTHOR NOTE:", "**A/N:", "**AN:", "**AUTHOR NOTE!"]):
            # Find the start of this block
            while end_idx > 0 and lines[end_idx-1].strip():
                end_idx -= 1
            continue
        break
        
    lines = lines[:end_idx]
    
    # Filter out dividers and clean content
    content_lines = []
    divider_pattern = re.compile(r"^\s*(--+|\.\.\.+)\s*$")
    url_pattern = re.compile(r"https?://\S+")
    
    for line in lines:
        if divider_pattern.match(line):
            continue
        
        # Strip URLs, asterisks, underscores
        line = url_pattern.sub("", line)
        line = line.replace("*", "").replace("_", "")
        
        if line.strip():
            content_lines.append(line)
            
    full_text = " ".join(content_lines)
    words = len(re.findall(r'\b\w+\b', full_text))
    chars_with_spaces = len(full_text)
    chars_no_spaces = len(full_text.replace(" ", "").replace("\n", "").replace("\r", "").replace("\t", ""))
    
    return words, chars_with_spaces, chars_no_spaces

def update_readme(path, wordcount_data, is_root=False):
    header = "# --- Wordcounts ---"
    
    content = ""
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
            
    if header in content:
        content = content.split(header)[0].strip()
    else:
        content = content.strip()
        
    new_section = f"\n\n{header}\n"
    
    if is_root:
        new_section += "| Series | Total Words | Total Characters |\n"
        new_section += "| --- | --- | --- |\n"
        for folder, data in sorted(wordcount_data.items()):
            folder_name = folder.replace("[", "\[").replace("]", "\]")
            # Root: Only show folder totals
            new_section += f"| {folder_name} | {data['total_words']:,} | {data['total_chars']:,} |\n"
    else:
        parts = wordcount_data['parts']
        if len(parts) <= 50:
            new_section += "| Part Name | Word Count | Character Count |\n"
            new_section += "| --- | --- | --- |\n"
            for part in parts:
                new_section += f"| {part['name']} | {part['words']:,} | {part['chars']:,} |\n"
        else:
            # Group into chunks of 50
            for i in range(0, len(parts), 50):
                chunk = parts[i:i+50]
                start_part = i + 1
                end_part = min(i + 50, len(parts))
                new_section += f"<details><summary>Parts {start_part} - {end_part}</summary>\n\n"
                new_section += "| Part Name | Word Count | Character Count |\n"
                new_section += "| --- | --- | --- |\n"
                for part in chunk:
                    new_section += f"| {part['name']} | {part['words']:,} | {part['chars']:,} |\n"
                new_section += "\n</details>\n\n"

        new_section += f"\n**Total Words:** {wordcount_data['total_words']:,}\n"
        new_section += f"**Total Characters:** {wordcount_data['total_chars']:,}\n"

    with open(path, 'w', encoding='utf-8') as f:
        f.write(content + new_section)

def main():
    root_dir = os.getcwd()
    global_data = {}
    
    exclude_dirs = {'.git', '.vscode', '__pycache__'}
    exclude_files = {'wordcounter.py', 'update_counts.bat', 'AgentWordCounterPlan.md', 'global_index.json'}

    for item in sorted(os.listdir(root_dir)):
        item_path = os.path.join(root_dir, item)
        if os.path.isdir(item_path) and item not in exclude_dirs:
            print(f"Processing folder: {item}")
            folder_data = {"total_words": 0, "total_chars": 0, "parts": []}
            
            # Sort files to maintain order
            files = sorted([f for f in os.listdir(item_path) if f.endswith('.txt')])
            
            for file in files:
                file_path = os.path.join(item_path, file)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        text_lines = f.readlines()
                    
                    words, chars_total, chars_no_space = clean_text(text_lines)
                    
                    part_info = {
                        "name": file.replace(".txt", ""),
                        "words": words,
                        "chars": chars_total
                    }
                    folder_data["parts"].append(part_info)
                    folder_data["total_words"] += words
                    folder_data["total_chars"] += chars_total
                except Exception as e:
                    print(f"Error processing {file}: {e}")
            
            # Save subfolder index.json
            with open(os.path.join(item_path, "index.json"), 'w', encoding='utf-8') as f:
                json.dump(folder_data, f, indent=4)
            
            # Update subfolder README.md
            update_readme(os.path.join(item_path, "README.md"), folder_data)
            
            global_data[item] = folder_data
            
    # Save global_index.json
    with open(os.path.join(root_dir, "global_index.json"), 'w', encoding='utf-8') as f:
        json.dump(global_data, f, indent=4)
        
    # Update root README.md
    update_readme(os.path.join(root_dir, "README.md"), global_data, is_root=True)
    print("Wordcount update complete!")

if __name__ == "__main__":
    main()
