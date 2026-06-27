# Third-Party Notices

AINotePro vendors selected Python dependencies in `libs/` so users do not need to install Python packages manually inside Anki.

## Vendored Dependencies

| Package | Vendored version | License | License/metadata currently included |
| --- | --- | --- | --- |
| aiohappyeyeballs | 2.4.4 | PSF-2.0 | No dist-info directory present |
| aiohttp | 3.11.11 | Apache-2.0 | No dist-info directory present |
| aiosignal | 1.3.2 | Apache-2.0 | No dist-info directory present |
| async-timeout | 5.0.1 | Apache-2.0 | No dist-info directory present |
| attrs / attr | 25.3.0 | MIT | `libs/attrs-25.3.0.dist-info/` includes metadata and license text |
| certifi | 2025.01.31 | MPL-2.0 | No dist-info directory present |
| charset-normalizer | 3.4.1 | MIT | No dist-info directory present |
| edge-tts | 7.0.0 | LGPL-3.0 | No dist-info directory present |
| frozenlist | 1.5.0 | Apache-2.0 | No dist-info directory present |
| idna | 3.10 | BSD-3-Clause | `libs/idna-3.10.dist-info/` includes metadata and license text |
| multidict | 6.1.0 | Apache-2.0 | No dist-info directory present |
| propcache | 0.2.1 | Apache-2.0 | No dist-info directory present |
| yarl | 1.18.3 | Apache-2.0 | No dist-info directory present |

## Release Notes

- Do not remove vendored license files or `*.dist-info` metadata when they are present.
- If vendored dependencies are refreshed, update this table in the same release.
- For a stricter source distribution, re-vendor the packages with their complete `*.dist-info` directories so each package's original license metadata is bundled alongside its code.
