with open('migrations/versions/001_initial_schema.py', 'r') as f:
    content = f.read()

# Find and comment out all three gin_trgm_ops index creations
patterns = [
    (r'op\.create_index\(\s*"idx_speakers_name".*?postgresql_ops=\{"name": "gin_trgm_ops"\}.*?\)', '# op.create_index(\n    "idx_speakers_name"\n    "speakers"\n    ["name"]\n    # postgresql_using="gin",\n    # postgresql_ops={"name": "gin_trgm_ops"},\n)'),
    (r'op\.create_index\(\s*"idx_legislation_title".*?postgresql_ops=\{"title": "gin_trgm_ops"\}.*?\)', '# op.create_index(\n    "idx_legislation_title"\n    "legislation"\n    ["title"]\n    # postgresql_using="gin",\n    # postgresql_ops={"title": "gin_trgm_ops"},\n)'),
    (r'op\.create_index\(\s*"idx_legislation_sponsor".*?postgresql_ops=\{"sponsors": "gin_trgm_ops"\}.*?\)', '# op.create_index(\n    "idx_legislation_sponsor"\n    "legislation"\n    ["sponsors"]\n    # postgresql_using="gin",\n    # postgresql_ops={"sponsors": "gin_trgm_ops"},\n)'),
]

for pattern, replacement in patterns:
    content = re.sub(pattern, replacement, content)

# Also remove the line that got mangled earlier
content = re.sub(
    r'# Commented out due to pg_trgm extension issue:\n#',
    '# Commented out due to pg_trgm extension issue:\n#',
    content
)

with open('migrations/versions/001_initial_schema.py', 'w') as f:
    f.write(content)

print("Migration file updated")
