---
name: libmagic-png-fixtures
description: libmagic needs a real IHDR chunk to classify PNG as image/png in upload tests
metadata:
  type: project
---

libmagic (via python-magic) classifies a PNG as `image/png` only when the test
fixture includes a real IHDR chunk after the signature. The 8-byte PNG signature
followed by zero-padding is detected as `application/octet-stream`, not PNG.

Minimal PNG that passes `MagicValidator` / `detect_mime_type`:
`b'\x89PNG\r\n\x1a\n' + b'\x00\x00\x00\rIHDR' + 13 bytes of IHDR data`.

PDF (`%PDF-1.4`) and JPEG (`\xff\xd8\xff\xe0...JFIF`) classify fine from just the
header bytes — only PNG needs the chunk.

**Why:** caught while writing Sprint 6 Bloco 2 upload tests — padded-signature PNGs
failed the allowlist check and made `test_upload_validates_mime_via_magic` red.

**How to apply:** when authoring any future file-upload test that needs a "real PNG"
to pass MIME validation, use the IHDR-bearing fixture, not signature + padding.
python-magic 0.4.27; libmagic.so.1 present at /lib/x86_64-linux-gnu on this host.
