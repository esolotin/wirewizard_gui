# Vendored Graphviz

The build script automatically downloads Graphviz 15.1.0 from the official
Graphviz GitLab package registry and verifies the pinned SHA-256 before
extracting it into the `graphviz` directory next to this file.

For an offline build, extract the official x64 Windows ZIP manually. The build
accepts both a direct layout and an extra top-level directory from the archive;
the direct layout looks like this:

```text
vendor/
└── graphviz/
    ├── bin/
    │   └── dot.exe
    ├── lib/
    └── share/
```

The complete Graphviz directory is copied into both the portable application
and the installer. The upstream binary ZIP does not include its license file,
so the shared PyInstaller spec separately bundles the exact official
`packaging/licenses/EPL-2.0.txt` from the Graphviz 15.1.0 source tag.
