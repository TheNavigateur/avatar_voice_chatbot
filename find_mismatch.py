def find_mismatch(filepath):
    with open(filepath, 'r') as f:
        content = f.read()
    
    stack = []
    lines = content.split('\n')
    for i, line in enumerate(lines):
        for char in line:
            if char == '{':
                stack.append(i + 1)
            elif char == '}':
                if not stack:
                    print(f"Extra closing brace at line {i+1}")
                else:
                    stack.pop()
    
    if stack:
        print(f"Unclosed braces opened at lines: {stack}")

if __name__ == "__main__":
    import sys
    find_mismatch(sys.argv[1])
