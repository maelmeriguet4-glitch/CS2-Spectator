import os
import re

def process_dir(d):
    for root, dirs, files in os.walk(d):
        for f in files:
            if f.endswith('.py'):
                path = os.path.join(root, f)
                with open(path, 'r', encoding='utf-8') as file:
                    content = file.read()
                
                def replacer(match):
                    indent = match.group(1)
                    return f'except Exception as _e:\n{indent}    import logging\n{indent}    logging.debug(f"Ignored error: {{_e}}")'
                
                new_content = re.sub(r'except Exception:\n(\s+)pass', replacer, content)
                
                if new_content != content:
                    with open(path, 'w', encoding='utf-8') as file:
                        file.write(new_content)
                    print(f'Fixed {path}')

process_dir('src')
process_dir('tests')
process_dir('.')
