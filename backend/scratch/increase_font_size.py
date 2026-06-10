import re
import os

file_path = '/home/jackc/projects/homma-research/frontend/app/continuation/page.tsx'

if not os.path.exists(file_path):
    print(f"Error: {file_path} not found.")
    exit(1)

with open(file_path, 'r') as f:
    content = f.read()

# Define size mapping
mapping = {
    'text-[10px]': 'text-xs',
    'text-xs': 'text-sm',
    'text-sm': 'text-base',
    'text-base': 'text-lg',
    'text-xl': 'text-2xl',
    'text-2xl': 'text-3xl'
}

pattern = r'\b(text-\[10px\]|text-xs|text-sm|text-base|text-xl|text-2xl)\b'

def replace_fn(match):
    token = match.group(1)
    new_token = mapping[token]
    return new_token

new_content, count = re.subn(pattern, replace_fn, content)

print(f"Made {count} font size replacements in {file_path}")

with open(file_path, 'w') as f:
    f.write(new_content)

print("File updated successfully!")
