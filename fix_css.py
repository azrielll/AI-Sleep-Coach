with open('static/css/style.css', 'rb') as f:
    content = f.read()

# Try to decode safely
text = content.decode('utf-8', errors='ignore')
# Split at the start of the corrupted part, usually starts with NULL bytes if it was utf-16 appended to utf-8.
# But PowerShell echo "..." >> file writes a BOM or just utf-16 le.
import re
# The text has spaces between characters like: [ d a t a - t h e m e = " l i g h t " ]
# The original file ends with .cat-kurang { color: var(--danger); }
idx = text.find('.cat-kurang { color: var(--danger); }')
if idx != -1:
    clean_text = text[:idx + len('.cat-kurang { color: var(--danger); }')]
else:
    clean_text = text

light_mode_css = """
/* ─── Light Mode ─────────────────────────────────────────── */
:root[data-theme="light"] {
  --bg-base:        #f4f6fb;
  --bg-card:        #ffffff;
  --bg-card2:       #f8fafc;
  --bg-input:       #f1f5f9;
  --border:         rgba(99,120,220,0.2);
  --border-bright:  rgba(108,125,255,0.4);

  --text-primary:   #1e293b;
  --text-secondary: #475569;
  --text-muted:     #94a3b8;

  --shadow-card:    0 4px 20px rgba(0,0,0,0.06);
  --shadow-glow:    0 0 25px rgba(108,125,255,0.15);
}

:root[data-theme="light"] body::before {
  background:
    radial-gradient(ellipse 80% 50% at 20% 10%, rgba(108,125,255,0.08) 0%, transparent 60%),
    radial-gradient(ellipse 60% 40% at 80% 80%, rgba(167,139,250,0.08) 0%, transparent 60%);
}

:root[data-theme="light"] .navbar {
  background: rgba(255,255,255,0.85);
}

:root[data-theme="light"] .btn-ghost {
  background: rgba(108,125,255,0.05);
  color: var(--primary);
}
:root[data-theme="light"] .btn-ghost:hover {
  background: rgba(108,125,255,0.15);
}

:root[data-theme="light"] .form-control, 
:root[data-theme="light"] .form-select {
  background: #ffffff;
}

:root[data-theme="light"] .card::before {
  background: linear-gradient(90deg, transparent, rgba(108,125,255,0.2), transparent);
}
"""

with open('static/css/style.css', 'w', encoding='utf-8') as f:
    f.write(clean_text + '\n' + light_mode_css)
