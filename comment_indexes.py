import re

with open('migrations/versions/001_initial_schema.py', 'r') as f:
    content = f.read()

# Comment out lines with gin_trgm_ops
content = re.sub(
    r"(\s+)op\.create_index\([^)]+\n\s+postgresql_using=\"gin\",\n\s+postgresql_ops=\{[^}]+\}[^)]*\n\s+\)",
    lambda m: f"# Commented out due to pg_trgm extension issue:\n# {m.group(0)}",
    content
)

with open('migrations/versions/001_initial_schema.py', 'w') as f:
    f.write(content)

print("Done")
