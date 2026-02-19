import os

def patch_index_html(filepath):
    with open(filepath, 'r') as f:
        lines = f.readlines()
    
    # 1. Add 'return div;' to addMessage
    # It's around line 2409 in the latest view
    found_add_message_end = False
    for i in range(2200, 2500):
        if i < len(lines) and 'tDiv.appendChild(div);' in lines[i]:
            # Look for the next closing brace
            for j in range(i + 1, i + 10):
                if j < len(lines) and '}' in lines[j] and 'return div;' not in lines[j-1]:
                    lines.insert(j, '        return div;\n')
                    found_add_message_end = True
                    break
            if found_add_message_end: break

    # 2. Fix orphaned code block
    # Orphaned block starts at line 2870 (roughly)
    # We want to delete from the orphan 'try {' till its corresponding '}'
    # But it might be easier to just find the marker and delete the block.
    
    start_line = -1
    for i, line in enumerate(lines):
        if 'const provider = document.getElementById' in line and 'ttsProvider' in line:
            # Backtrack to find the 'try {'
            for j in range(i, i-10, -1):
                if 'try {' in lines[j]:
                    start_line = j
                    break
            if start_line != -1: break
            
    if start_line != -1:
        # Find corresponding closing brace for this try
        stack = 1
        end_line = -1
        for i in range(start_line + 1, len(lines)):
            stack += lines[i].count('{')
            stack -= lines[i].count('}')
            if stack == 0:
                end_line = i
                break
        
        if end_line != -1:
            print(f"Deleting orphaned block from line {start_line+1} to {end_line+1}")
            del lines[start_line : end_line + 1]

    with open(filepath, 'w') as f:
        f.writelines(lines)

if __name__ == "__main__":
    patch_index_html('templates/index.html')
