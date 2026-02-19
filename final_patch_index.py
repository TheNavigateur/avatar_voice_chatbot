import os

def final_patch(filepath):
    with open(filepath, 'r') as f:
        lines = f.readlines()
    
    # Based on the last view_file, the orphaned code starts around line 2871
    # and ends around line 2940.
    # Let's verify the content at these lines before deleting.
    
    if 'let voiceName' in lines[2872] and 'targetPackageId' in lines[2938]:
        print(f"Verified orphaned block line range. Deleting 2871 to 2940.")
        del lines[2871:2941]
    else:
        # Fallback: search for unique markers
        print("Line numbers mismatch. Searching for markers...")
        start = -1
        end = -1
        for i, line in enumerate(lines):
            if "let voiceName = 'en-GB-Chirp3-HD-Algenib';" in line:
                start = i
            if 'console.log(`[Audio] Audio ended at ${new Date().toLocaleTimeString()}`);' in line:
                # Find the next few lines till '};' or '}'
                for j in range(i, i+20):
                    if '};' in lines[j] or '    }' in lines[j]:
                        end = j
                        break
                break
        
        if start != -1 and end != -1:
            print(f"Found orphaned block via markers: {start+1} to {end+1}. Deleting.")
            del lines[start:end+1]

    with open(filepath, 'w') as f:
        f.writelines(lines)

if __name__ == "__main__":
    final_patch('templates/index.html')
