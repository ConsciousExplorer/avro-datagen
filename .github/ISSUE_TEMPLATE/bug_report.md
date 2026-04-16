---
name: Bug report
about: Something isn't working as expected
labels: bug
---

## Description

<!-- A clear, concise description of the problem. -->

## Steps to reproduce

```bash
# Minimal command to reproduce
avro-datagen -s schema.avsc
```

**Schema (`schema.avsc`):**

```json
{
  "type": "record",
  "name": "Example",
  "fields": []
}
```

## Expected behavior

<!-- What you expected to happen. -->

## Actual behavior

<!-- What actually happened. Paste any error output. -->

```
error or unexpected output here
```

## Environment

- avro-datagen version: <!-- `avro-datagen --version` -->
- Python version: <!-- `python --version` -->
- OS:
