# TheHonjinMurders_Tools

Tools and utilities for the translation and modification of **Kindaichi Mystery Series: The Honjin Murders**.

> **AI-assisted development**
>
> Parts of this repository were developed with assistance from generative AI. AI was used during implementation, debugging, diagnostic analysis, Unity serialization research, and development of supporting tooling. The generated code was reviewed, adapted, and tested against the actual target files and game environment.
>
> This README was also written with the assistance of generative AI.

## Usage

You'll need to edit `script_base.txt` and `script.py` in order to make the pipeline work:

Among other data, `script_base.txt` contains the relative locations of your dumped (and presumably edited) files, whereas `script.py` may rely on external tools whose full path you'll need to edit or specify, and/or use different paths than those specified in general.

Once you've made those changes, you can run `script_gui.py` in order to easily select which files from `script_base.txt` should be compiled, and then generate the new `script.py`. Finally, just use `BUILD.bat` to compile.

---

## UAFGJ

**UAFGJ is our own custom asset replacement tool, based on UABEA.**

UAFGJ was originally created as part of the effort to translate **Danganronpa V3 on Nintendo Switch**, and has since been further developed and adapted for other Unity-based projects.

The current development version is maintained in the custom branch of: https://github.com/IndacoSub/UABEA/tree/custom

UAFGJ is used to replace and rebuild Unity assets while performing extensive integrity checks on the resulting files.

For **The Honjin Murders**, the relevant workflow primarily involves Unity `MonoBehaviour` assets stored inside AssetBundles.

### MonoBehaviour replacement

UAFGJ can import structured Unity/UABEA TXT dumps into `MonoBehaviour` assets (`TypeID 114`).

The existing Unity serialization tree is preserved and the values represented by the TXT dump are applied to the target asset.

The target can be resolved using its exact Unity `PathID`, avoiding ambiguity when multiple assets have similar names.

### Bundle rebuilding

After replacement, UAFGJ:

- rebuilds the embedded `.assets` file;
- rebuilds the UnityFS AssetBundle;
- preserves the original compression format;
- preserves the original bundle directory layout;
- reopens the generated files for validation.

The generated bundle is only committed after the validation checks succeed.

---

## Validation

UAFGJ performs extensive checks throughout the replacement process.

These include:

- UnityFS container validation;
- Unity version validation;
- AssetBundle compression validation;
- bundle directory layout validation;
- asset count validation;
- PathID validation;
- TypeID validation;
- MonoScript index validation;
- serialized asset SHA-256 validation;
- target payload SHA-256 validation;
- detection of unexpected changes to unrelated assets;
- final TXT/value validation after reopening the rebuilt bundle.

This is intended to catch serialization or rebuilding problems before the modified bundle replaces the original file.

---

## Addressables and CRC

**The Honjin Murders uses Unity Addressables** to reference its AssetBundles.

The Addressables catalog contains metadata for individual bundles, including information such as:

```json
{
    "m_Hash": "...",
    "m_Crc": 123456789,
    "m_BundleName": "...",
    "m_BundleSize": 123456,
    "m_UseCrcForCachedBundles": true
}
````

When an AssetBundle is modified, its binary contents change while the original Addressables catalog still contains metadata generated for the original file.

The `crc.py` workflow handles the required catalog-side CRC change.

### Why the CRC patch is needed

The original catalog can contain an entry such as:

```json
"m_Crc": 1968766263
```

After rebuilding the bundle, that CRC no longer describes the modified file.

The patch changes the target entry to:

```json
"m_Crc": 0
```

while preserving and verifying the other relevant catalog data.

This disables CRC verification for the modified bundle.

---

## `crc.py`

The normal workflow is:

```powershell
python crc.py
```

`crc.py` is the main entry point and performs the complete patching workflow.

It:

1. verifies that the original catalog backup exists;
2. verifies that the installed bundle matches the known original;
3. records the original bundle size and SHA-256;
4. runs `script.py`;
5. verifies that the bundle was actually modified;
6. creates a working copy of the Addressables catalog;
7. patches the CRC of the target bundle;
8. verifies the patched catalog;
9. installs the patched catalog;
10. creates backups and diagnostic reports.

Because `crc.py` runs `script.py` automatically, the normal workflow is simply:

```powershell
python crc.py
```

Do not normally run:

```powershell
python script.py
python crc.py
```

because `crc.py` expects the bundle to still be in its original state when its initial verification runs.

---

## AddressablesTools

The CRC workflow requires `Example.exe` from **AddressablesTools** (https://github.com/nesrak1/AddressablesTools).

Place it in:

```text
Tools/
└── Example.exe
```

`Example.exe` is an external dependency and is **not included in this repository**.

The executable is used to patch the Addressables catalog during the CRC workflow.

If it cannot be found, the CRC patching step cannot be performed.

---

## Original catalog backup

The original Addressables catalog is stored as a local reference under:

```text
ogcrc/
└── catalog.json
```

This is the known-good copy used to verify the original catalog metadata.

The backup should not be modified manually.

Additional backups are created before a patched catalog is installed.

---

## Workflow

The complete process can be summarized as:

```text
Original game files
        │
        ▼
     crc.py
        │
        ├── verify original bundle
        │
        ├── run script.py
        │      │
        │      └── UAFGJ
        │             └── replace MonoBehaviour data
        │
        ├── verify rebuilt bundle
        │
        ├── patch Addressables CRC
        │
        └── install patched catalog
```

The objective is to keep the bundle modification and its Addressables metadata consistent enough for the modified local files to be used by the game.

---

## Project structure

A simplified repository layout is:

```text
TheHonjinMurders_Tools/
├── Tools/
│   └── Example.exe
├── ogcrc/
│   └── catalog.json
├── en/
│   └── ...
├── script.py
├── crc.py
├── BUILD.bat
├── LICENSE
└── README.md
```

Diagnostic reports and additional backups are generated during execution.

---

## License

This repository is released under the **ISC License**.

See `LICENSE` for the complete license text.