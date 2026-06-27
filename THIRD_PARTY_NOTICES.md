# Third-Party Notices

AINotePro vendors selected Python dependencies in `libs/` so the add-on can run inside Anki without requiring users to install packages manually.

Before each public release, verify that every vendored dependency includes its license text or distribution metadata in the packaged add-on. At the time of this release candidate, the package contains license metadata for dependencies such as `attrs` and `idna`; other vendored packages should be checked during cross-platform release testing.

Do not remove license files or `*.dist-info` metadata from `libs/` unless the dependency is also removed from the add-on.
