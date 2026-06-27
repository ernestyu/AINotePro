# Third-Party Notices

AINotePro vendors selected Python dependencies in `libs/` so users do not need to install Python packages manually inside Anki.

## Vendored Dependencies

| Package | Vendored version | License | License/metadata currently included |
| --- | --- | --- | --- |
| aiohappyeyeballs | 2.4.4 | PSF-2.0 | `libs/aiohappyeyeballs-2.4.4.dist-info/` |
| aiohttp | 3.11.11 | Apache-2.0 | `libs/aiohttp-3.11.11.dist-info/` |
| aiosignal | 1.3.2 | Apache-2.0 | `libs/aiosignal-1.3.2.dist-info/` |
| async-timeout | 5.0.1 | Apache-2.0 | `libs/async_timeout-5.0.1.dist-info/` |
| attrs / attr | 25.3.0 | MIT | `libs/attrs-25.3.0.dist-info/` includes metadata and license text |
| certifi | 2025.01.31 | MPL-2.0 | `libs/certifi-2025.1.31.dist-info/` |
| charset-normalizer | 3.4.1 | MIT | `libs/charset_normalizer-3.4.1.dist-info/` |
| edge-tts | 7.0.0 | LGPL-3.0 | `libs/edge_tts-7.0.0.dist-info/` |
| frozenlist | 1.5.0 | Apache-2.0 | `libs/frozenlist-1.5.0.dist-info/` |
| idna | 3.10 | BSD-3-Clause | `libs/idna-3.10.dist-info/` includes metadata and license text |
| multidict | 6.1.0 | Apache-2.0 | `libs/multidict-6.1.0.dist-info/` |
| propcache | 0.2.1 | Apache-2.0 | `libs/propcache-0.2.1.dist-info/` |
| srt | 3.5.3 | MIT | `libs/srt-3.5.3.dist-info/` |
| typing_extensions | 4.12.2 | PSF-2.0 | `libs/typing_extensions-4.12.2.dist-info/` |
| yarl | 1.18.3 | Apache-2.0 | `libs/yarl-1.18.3.dist-info/` |

## Release Notes

- Do not remove vendored license files or `*.dist-info` metadata.
- If vendored dependencies are refreshed, update this table in the same release.
