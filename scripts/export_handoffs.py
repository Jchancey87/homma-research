#!/usr/bin/env python3
"""
Handoff markdown to premium HTML converter.
Provides a rich, interactive web interface for development handoffs.
"""

import os
import re
import sys
from pathlib import Path
import html

# Style guidelines: Inter/Outfit fonts, modern dark theme, glassmorphism, transitions, copy-buttons, responsive design.
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} - Handoff Document</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Outfit:wght@400;600;700;800&family=Fira+Code:wght@400;500&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg-base: #0b0f19;
            --bg-surface: rgba(17, 24, 39, 0.7);
            --bg-card: rgba(30, 41, 59, 0.4);
            --border-color: rgba(255, 255, 255, 0.08);
            --text-primary: #f8fafc;
            --text-secondary: #94a3b8;
            --text-muted: #64748b;
            --accent-primary: #6366f1;
            --accent-glow: rgba(99, 102, 241, 0.15);
            
            --note-color: #3b82f6;
            --tip-color: #10b981;
            --important-color: #8b5cf6;
            --warning-color: #f59e0b;
            --caution-color: #ef4444;
        }}

        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}

        body {{
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            background-color: var(--bg-base);
            color: var(--text-primary);
            line-height: 1.625;
            -webkit-font-smoothing: antialiased;
            background-image: 
                radial-gradient(at 0% 0%, rgba(99, 102, 241, 0.1) 0px, transparent 50%),
                radial-gradient(at 100% 100%, rgba(168, 85, 247, 0.08) 0px, transparent 50%);
            background-attachment: fixed;
        }}

        /* Scrollbar styling */
        ::-webkit-scrollbar {{
            width: 8px;
            height: 8px;
        }}
        ::-webkit-scrollbar-track {{
            background: rgba(15, 23, 42, 0.3);
        }}
        ::-webkit-scrollbar-thumb {{
            background: rgba(99, 102, 241, 0.3);
            border-radius: 4px;
        }}
        ::-webkit-scrollbar-thumb:hover {{
            background: rgba(99, 102, 241, 0.5);
        }}

        .layout {{
            display: flex;
            min-height: 100vh;
        }}

        /* Sidebar & Navigation */
        .sidebar {{
            width: 300px;
            background: var(--bg-surface);
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            border-right: 1px solid var(--border-color);
            padding: 2.5rem 1.5rem;
            position: fixed;
            height: 100vh;
            overflow-y: auto;
            display: flex;
            flex-direction: column;
            gap: 2rem;
            z-index: 10;
        }}

        .logo {{
            font-family: 'Outfit', sans-serif;
            font-size: 1.25rem;
            font-weight: 800;
            background: linear-gradient(135deg, #a5b4fc, #818cf8);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }}

        .nav-section {{
            display: flex;
            flex-direction: column;
            gap: 0.75rem;
        }}

        .nav-title {{
            font-size: 0.75rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--text-muted);
        }}

        .nav-list {{
            list-style: none;
            display: flex;
            flex-direction: column;
            gap: 0.25rem;
        }}

        .nav-link {{
            display: block;
            padding: 0.5rem 0.75rem;
            border-radius: 0.375rem;
            color: var(--text-secondary);
            text-decoration: none;
            font-size: 0.875rem;
            transition: all 0.2s ease;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }}

        .nav-link:hover, .nav-link.active {{
            background: rgba(99, 102, 241, 0.1);
            color: var(--text-primary);
            padding-left: 1rem;
        }}

        .nav-link.active {{
            border-left: 3px solid var(--accent-primary);
            font-weight: 600;
        }}

        /* Main Content Panel */
        .content-panel {{
            margin-left: 300px;
            flex-grow: 1;
            padding: 4rem 5% 6rem 5%;
            max-width: 1200px;
        }}

        .card {{
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            backdrop-filter: blur(8px);
            -webkit-backdrop-filter: blur(8px);
            border-radius: 1rem;
            padding: 3rem;
            box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.3), 0 10px 10px -5px rgba(0, 0, 0, 0.2);
        }}

        /* Typography */
        h1, h2, h3, h4, h5, h6 {{
            font-family: 'Outfit', sans-serif;
            color: var(--text-primary);
            font-weight: 700;
            margin-top: 2.5rem;
            margin-bottom: 1rem;
            letter-spacing: -0.02em;
        }}

        h1 {{
            font-size: 2.5rem;
            margin-top: 0;
            background: linear-gradient(to right, #f8fafc, #cbd5e1);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 1.5rem;
            margin-bottom: 2rem;
        }}

        h2 {{
            font-size: 1.75rem;
            border-bottom: 1px solid rgba(255, 255, 255, 0.05);
            padding-bottom: 0.5rem;
        }}

        h3 {{ font-size: 1.35rem; }}
        h4 {{ font-size: 1.15rem; }}

        p, ul, ol, table, pre {{
            margin-bottom: 1.5rem;
        }}

        p {{
            color: var(--text-secondary);
        }}

        strong {{
            color: var(--text-primary);
            font-weight: 600;
        }}

        /* Lists */
        ul, ol {{
            padding-left: 1.5rem;
            color: var(--text-secondary);
        }}

        li {{
            margin-bottom: 0.5rem;
        }}

        /* Inline Code */
        code:not(pre code) {{
            font-family: 'Fira Code', monospace;
            background: rgba(99, 102, 241, 0.12);
            color: #a5b4fc;
            padding: 0.2rem 0.4rem;
            border-radius: 0.25rem;
            font-size: 0.85em;
            border: 1px solid rgba(99, 102, 241, 0.2);
        }}

        /* Code Blocks */
        .code-container {{
            position: relative;
            background: #070a13;
            border: 1px solid var(--border-color);
            border-radius: 0.75rem;
            margin: 1.5rem 0;
            overflow: hidden;
        }}

        .code-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 0.5rem 1rem;
            background: rgba(15, 23, 42, 0.6);
            border-bottom: 1px solid var(--border-color);
            font-family: 'Fira Code', monospace;
            font-size: 0.75rem;
            color: var(--text-muted);
        }}

        .copy-btn {{
            background: rgba(99, 102, 241, 0.15);
            border: 1px solid rgba(99, 102, 241, 0.3);
            color: #a5b4fc;
            padding: 0.25rem 0.5rem;
            font-size: 0.75rem;
            border-radius: 0.25rem;
            cursor: pointer;
            transition: all 0.2s ease;
        }}

        .copy-btn:hover {{
            background: var(--accent-primary);
            color: #ffffff;
        }}

        pre {{
            font-family: 'Fira Code', monospace;
            font-size: 0.875rem;
            padding: 1.25rem;
            overflow-x: auto;
            color: #e2e8f0;
            margin-bottom: 0;
        }}

        /* Tables */
        .table-container {{
            overflow-x: auto;
            border: 1px solid var(--border-color);
            border-radius: 0.75rem;
            margin: 2rem 0;
            background: rgba(15, 23, 42, 0.2);
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 0.875rem;
            text-align: left;
            margin-bottom: 0;
        }}

        th, td {{
            padding: 1rem 1.25rem;
            border-bottom: 1px solid var(--border-color);
        }}

        th {{
            background: rgba(15, 23, 42, 0.4);
            color: var(--text-primary);
            font-weight: 600;
        }}

        tr:last-child td {{
            border-bottom: none;
        }}

        tr:hover td {{
            background: rgba(255, 255, 255, 0.02);
        }}

        /* Callouts / Alerts */
        .alert {{
            border-left: 4px solid;
            padding: 1.25rem 1.5rem;
            border-radius: 0.5rem;
            background: rgba(30, 41, 59, 0.2);
            margin: 1.5rem 0;
        }}

        .alert p:last-child {{
            margin-bottom: 0;
        }}

        .alert-title {{
            font-family: 'Outfit', sans-serif;
            font-weight: 700;
            font-size: 0.875rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 0.5rem;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }}

        .alert.note {{ border-color: var(--note-color); }}
        .alert.note .alert-title {{ color: var(--note-color); }}

        .alert.tip {{ border-color: var(--tip-color); }}
        .alert.tip .alert-title {{ color: var(--tip-color); }}

        .alert.important {{ border-color: var(--important-color); }}
        .alert.important .alert-title {{ color: var(--important-color); }}

        .alert.warning {{ border-color: var(--warning-color); }}
        .alert.warning .alert-title {{ color: var(--warning-color); }}

        .alert.caution {{ border-color: var(--caution-color); }}
        .alert.caution .alert-title {{ color: var(--caution-color); }}

        /* File Links */
        a {{
            color: #818cf8;
            text-decoration: none;
            transition: color 0.2s ease;
        }}

        a:hover {{
            color: #a5b4fc;
            text-decoration: underline;
        }}

        /* Responsive */
        @media (max-width: 968px) {{
            .sidebar {{
                display: none;
            }}
            .content-panel {{
                margin-left: 0;
                padding: 2rem 1.5rem;
            }}
            .card {{
                padding: 1.5rem;
            }}
        }}
    </style>
</head>
<body>
    <div class="layout">
        <aside class="sidebar">
            <div class="logo">
                <span>🛸</span> Homma Research
            </div>
            <nav class="nav-section">
                <div class="nav-title">Documents</div>
                <ul class="nav-list">
                    {nav_links}
                </ul>
            </nav>
        </aside>
        <main class="content-panel">
            <article class="card">
                {content}
            </article>
        </main>
    </div>

    <script>
        async function copyToClipboard(button, text) {{
            try {{
                await navigator.clipboard.writeText(text);
                const originalText = button.textContent;
                button.textContent = 'Copied!';
                button.style.background = 'var(--tip-color)';
                button.style.borderColor = 'var(--tip-color)';
                button.style.color = '#ffffff';
                setTimeout(() => {{
                    button.textContent = originalText;
                    button.style.background = 'rgba(99, 102, 241, 0.15)';
                    button.style.borderColor = 'rgba(99, 102, 241, 0.3)';
                    button.style.color = '#a5b4fc';
                }}, 2000);
            }} catch (err) {{
                console.error('Failed to copy text: ', err);
            }}
        }}
    </script>
</body>
</html>
"""

class SimpleMarkdownParser:
    def __init__(self):
        pass

    def parse(self, text):
        # Normalize line endings
        text = text.replace('\r\n', '\n')
        
        # Pre-process code blocks to prevent parsing internals
        code_blocks = []
        def save_code_block(match):
            lang = match.group(1) or 'code'
            code_content = match.group(2)
            code_blocks.append((lang, code_content))
            return f"<!--CODEBLOCK_{len(code_blocks)-1}-->"
            
        text = re.sub(r'```(\w*)\n(.*?)\n```', save_code_block, text, flags=re.DOTALL)

        # Pre-process tables
        tables = []
        def save_table(match):
            table_str = match.group(0)
            tables.append(table_str)
            return f"\n\n<!--TABLE_{len(tables)-1}-->\n\n"
            
        # Match table blocks
        text = re.sub(r'((?:\|[^\n]*\|\n)+)', save_table, text)

        # Split into blocks (double newlines)
        raw_blocks = [b.strip() for b in text.split('\n\n') if b.strip()]
        html_blocks = []

        for block in raw_blocks:
            # Code block placeholder
            code_match = re.match(r'<!--CODEBLOCK_(\d+)-->', block)
            if code_match:
                idx = int(code_match.group(1))
                lang, code_content = code_blocks[idx]
                escaped_code = html.escape(code_content)
                html_blocks.append(
                    f'<div class="code-container">'
                    f'  <div class="code-header">'
                    f'    <span>{lang.upper()}</span>'
                    f'    <button class="copy-btn" onclick="copyToClipboard(this, decodeURIComponent(\'{self._escape_js_string(code_content)}\'))">Copy</button>'
                    f'  </div>'
                    f'  <pre><code class="language-{lang}">{escaped_code}</code></pre>'
                    f'</div>'
                )
                continue

            # Table placeholder
            table_match = re.match(r'<!--TABLE_(\d+)-->', block)
            if table_match:
                idx = int(table_match.group(1))
                html_blocks.append(self._parse_table(tables[idx]))
                continue

            # Headers
            header_match = re.match(r'^(#{1,6})\s+(.*)$', block)
            if header_match:
                level = len(header_match.group(1))
                title = self._parse_inline(header_match.group(2))
                html_blocks.append(f'<h{level}>{title}</h{level}>')
                continue

            # GitHub Callouts / Alerts (e.g. > [!NOTE])
            if block.startswith('>'):
                lines = [l.lstrip('> ').strip() for l in block.split('\n')]
                alert_match = re.match(r'^\[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\]', lines[0], re.IGNORECASE)
                if alert_match:
                    alert_type = alert_match.group(1).lower()
                    alert_content = self._parse_inline("<br>".join(lines[1:]))
                    html_blocks.append(
                        f'<div class="alert {alert_type}">'
                        f'  <div class="alert-title">📢 {alert_type.upper()}</div>'
                        f'  <p>{alert_content}</p>'
                        f'</div>'
                    )
                else:
                    blockquote_content = self._parse_inline("<br>".join(lines))
                    html_blocks.append(f'<blockquote>{blockquote_content}</blockquote>')
                continue

            # Unordered List
            if block.startswith(('* ', '- ', '+ ')):
                list_items = []
                for line in block.split('\n'):
                    item_text = re.sub(r'^[*+-]\s+', '', line)
                    list_items.append(f'<li>{self._parse_inline(item_text)}</li>')
                html_blocks.append(f'<ul>{"".join(list_items)}</ul>')
                continue

            # Ordered List
            if re.match(r'^\d+\.\s+', block):
                list_items = []
                for line in block.split('\n'):
                    item_text = re.sub(r'^\d+\.\s+', '', line)
                    list_items.append(f'<li>{self._parse_inline(item_text)}</li>')
                html_blocks.append(f'<ol>{"".join(list_items)}</ol>')
                continue

            # Regular Paragraph
            html_blocks.append(f'<p>{self._parse_inline(block)}</p>')

        return "\n".join(html_blocks)

    def _parse_inline(self, text):
        # Escape HTML tags (except ones we generate)
        text = html.escape(text)
        
        # Restore escaped link brackets & symbols needed for formatting
        text = text.replace('&lt;br&gt;', '<br>').replace('&amp;nbsp;', '&nbsp;')

        # Links: [text](url)
        text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', text)

        # Bold: **text**
        text = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', text)

        # Italic: *text*
        text = re.sub(r'\*([^*]+)\*', r'<em>\1</em>', text)

        # Inline code: `code`
        text = re.sub(r'`([^`]+)`', r'<code>\1</code>', text)

        return text

    def _parse_table(self, table_str):
        lines = [l.strip() for l in table_str.strip().split('\n') if l.strip()]
        if len(lines) < 2:
            return ""

        headers = [h.strip() for h in lines[0].split('|')[1:-1]]
        
        # Skip separator line (lines[1])
        rows = []
        for line in lines[2:]:
            cells = [c.strip() for c in line.split('|')[1:-1]]
            rows.append(cells)

        header_html = "".join(f"<th>{self._parse_inline(h)}</th>" for h in headers)
        
        row_htmls = []
        for row in rows:
            cells_html = "".join(f"<td>{self._parse_inline(c)}</td>" for c in row)
            row_htmls.append(f"<tr>{cells_html}</tr>")

        return (
            f'<div class="table-container">'
            f'  <table>'
            f'    <thead><tr>{header_html}</tr></thead>'
            f'    <tbody>{"".join(row_htmls)}</tbody>'
            f'  </table>'
            f'</div>'
        )

    def _escape_js_string(self, text):
        import urllib.parse
        return urllib.parse.quote(text)


def build_handoffs():
    workspace = Path('/home/jackc/projects/homma-research')
    handoffs_dir = workspace / 'handoffs'
    output_dir = handoffs_dir / 'html'
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Collect md files
    md_files = sorted(list(handoffs_dir.glob('*.md')))
    
    # Generate navigation links
    nav_links = []
    for f in md_files:
        html_name = f.with_suffix('.html').name
        nav_links.append(f'<li><a href="{html_name}" class="nav-link" data-filename="{html_name}">{f.stem.replace("_", " ").title()}</a></li>')
    
    nav_html = "\n".join(nav_links)
    parser = SimpleMarkdownParser()

    for f in md_files:
        print(f"Converting {f.name}...")
        with open(f, 'r', encoding='utf-8') as file_in:
            markdown_content = file_in.read()

        html_content = parser.parse(markdown_content)
        
        # Set active nav link script snippet
        html_name = f.with_suffix('.html').name
        active_nav_html = nav_html.replace(
            f'data-filename="{html_name}"', 
            f'data-filename="{html_name}" class="nav-link active"'
        )
        
        full_html = HTML_TEMPLATE.format(
            title=f.stem.replace('_', ' ').title(),
            nav_links=active_nav_html,
            content=html_content
        )
        
        output_file = output_dir / html_name
        with open(output_file, 'w', encoding='utf-8') as file_out:
            file_out.write(full_html)

    print("Success. All handoffs converted.")

if __name__ == '__main__':
    build_handoffs()
