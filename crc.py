from __future__ import annotations

"""
patch_and_verify.py
===================

Workflow unico per la modifica Addressables del gioco.

Esegue:

    1. Verifica il gioco / aa / catalog.json
    2. Crea ogcrc/catalog.json se non esiste
       (NON lo sovrascrive mai)
    3. Analizza il catalogo originale
       e verifica il target:
           m_Hash
           m_Crc
           m_BundleSize
           m_UseCrcForCachedBundles
    4. Verifica il bundle originale prima della modifica
    5. Esegue script.py
    6. Verifica che il bundle sia effettivamente cambiato
    7. Crea una working copy del catalogo originale
    8. Usa Example.exe patchcrc sulla working copy
    9. Verifica che il CRC del target sia diventato 0
   10. Fa backup del catalog.json attuale
   11. Installa il catalogo patched nel gioco
   12. Verifica SHA256 del catalogo installato
   13. Produce un report completo

IMPORTANTE:

- script.py deve essere nella stessa directory di questo programma,
  oppure cambia USER_SCRIPT qui sotto.
- Example.exe deve essere nella stessa directory, oppure cambia
  ADDRESSABLES_TOOLS_EXE.
- Se script.py termina con errore, il catalogo NON viene patchato.
- Se il bundle non cambia dopo script.py, il catalogo NON viene patchato.
- ogcrc/catalog.json viene creato una sola volta e conservato.
- Il catalog.json del gioco viene modificato soltanto alla fine,
  dopo tutti i controlli.
"""

# ============================================================
# IMPORT
# ============================================================

import base64
import binascii
import hashlib
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


# ============================================================
# CONFIGURAZIONE
# ============================================================

GAME_ROOT = Path(
    r"F:\SteamLibrary\steamapps\common\game-g15\game-g15"
)

AA_DIR = (
    GAME_ROOT
    / "game-g15_Data"
    / "StreamingAssets"
    / "aa"
)

CATALOG_PATH = (
    AA_DIR / "catalog.json"
)

TARGET_BUNDLE = (
    AA_DIR
    / "StandaloneWindows64"
    / "masterdata_assets_all_1007e97d1154ffcb0e91f2346a050762.bundle"
)

# Script che esegue le modifiche ai MonoBehaviour.
USER_SCRIPT = (
    Path(__file__).resolve().parent
    / "script.py"
)

# AddressablesTools.
ADDRESSABLES_TOOLS_EXE = (
    Path(__file__).resolve().parent
    / "Tools" / "Example.exe"
)

# ------------------------------------------------------------
# Target Addressables
# ------------------------------------------------------------

TARGET_HASH = (
    "1007e97d1154ffcb0e91f2346a050762"
)

EXPECTED_CRC = 1968766263
EXPECTED_BUNDLE_SIZE = 268667

EXPECTED_ORIGINAL_BUNDLE_SHA256 = (
    "6E3FA9447CF247EDBEE1EA1DC3D98D2F5F57510E577DD488EE4D6FD644DA1BAA"
)

# ------------------------------------------------------------
# Output
# ------------------------------------------------------------

BASE_DIR = (
    Path(__file__).resolve().parent
)

OUTPUT_DIR = (
    BASE_DIR / "patch_and_verify_output"
)

OGCRC_DIR = (
    BASE_DIR / "ogcrc"
)

ORIGINAL_CATALOG_BACKUP = (
    OGCRC_DIR / "catalog.json"
)

WORKING_CATALOG = (
    OUTPUT_DIR / "catalog.working.json"
)

PATCHED_CATALOG = (
    OUTPUT_DIR / "catalog.patched.json"
)

REPORT_PATH = (
    OUTPUT_DIR / "patch_and_verify_report.txt"
)

# Snapshot del bundle dopo script.py.
MODIFIED_BUNDLE_SNAPSHOT = (
    OUTPUT_DIR
    / (
        TARGET_BUNDLE.name
        + ".modified"
    )
)

# Backup del catalogo prima dell'installazione patched.
INSTALLED_CATALOG_BACKUP_DIR = (
    OUTPUT_DIR
    / "catalog_backups"
)


# ============================================================
# LOGGER
# ============================================================

class Logger:
    def __init__(self, path: Path):
        self.path = path
        self.fp = None

    def open(self):
        self.path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.fp = self.path.open(
            "w",
            encoding="utf-8",
            errors="replace",
        )

        self.write("=" * 100)
        self.write(
            "ADDRESSABLES PATCH + VERIFY"
        )
        self.write("=" * 100)
        self.write(
            f"Started: "
            f"{datetime.now().isoformat(timespec='seconds')}"
        )
        self.write()

    def write(self, text: str = ""):
        if self.fp is None:
            return

        self.fp.write(
            text + "\n"
        )
        self.fp.flush()

    def close(self):
        if self.fp is None:
            return

        self.write()
        self.write(
            f"Finished: "
            f"{datetime.now().isoformat(timespec='seconds')}"
        )

        self.fp.close()
        self.fp = None


LOGGER = Logger(
    REPORT_PATH
)


# ============================================================
# CONSOLE
# ============================================================

def info(text: str):
    print(text)


def warn(text: str):
    print(
        f"[WARN] {text}"
    )


def error(text: str):
    print(
        f"[ERROR] {text}"
    )


# ============================================================
# FILE HELPERS
# ============================================================

def file_exists(path: Path) -> bool:
    try:
        return path.is_file()
    except OSError:
        return False


def file_size(path: Path) -> int | None:
    try:
        return path.stat().st_size
    except OSError:
        return None


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as fp:

        while True:
            chunk = fp.read(
                1024 * 1024
            )

            if not chunk:
                break

            digest.update(
                chunk
            )

    return digest.hexdigest().upper()


def load_json(path: Path) -> dict[str, Any]:
    text = path.read_text(
        encoding="utf-8-sig"
    )

    data = json.loads(
        text
    )

    if not isinstance(
        data,
        dict,
    ):
        raise ValueError(
            f"{path} non contiene "
            "un oggetto JSON."
        )

    return data


# ============================================================
# BACKUP ORIGINAL CATALOG
# ============================================================

def ensure_original_catalog_backup():
    """
    Crea ogcrc/catalog.json soltanto se non esiste.
    """

    OGCRC_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    if not file_exists(
        CATALOG_PATH
    ):
        raise FileNotFoundError(
            f"catalog.json non trovato:\n"
            f"{CATALOG_PATH}"
        )

    current_sha = sha256_file(
        CATALOG_PATH
    )

    current_size = file_size(
        CATALOG_PATH
    )

    LOGGER.write(
        "=" * 100
    )
    LOGGER.write(
        "ORIGINAL CATALOG BACKUP"
    )
    LOGGER.write(
        "=" * 100
    )

    LOGGER.write(
        f"Current catalog: {CATALOG_PATH}"
    )

    LOGGER.write(
        f"Current size: {current_size}"
    )

    LOGGER.write(
        f"Current SHA256: {current_sha}"
    )

    if file_exists(
        ORIGINAL_CATALOG_BACKUP
    ):

        backup_sha = sha256_file(
            ORIGINAL_CATALOG_BACKUP
        )

        LOGGER.write(
            f"Existing backup: "
            f"{ORIGINAL_CATALOG_BACKUP}"
        )

        LOGGER.write(
            f"Existing backup SHA256: "
            f"{backup_sha}"
        )

        if backup_sha == current_sha:
            info(
                "[OK] Backup catalog già presente."
            )

        else:
            warn(
                "catalog.json corrente e "
                "ogcrc/catalog.json differiscono."
            )

        return

    shutil.copy2(
        CATALOG_PATH,
        ORIGINAL_CATALOG_BACKUP,
    )

    backup_sha = sha256_file(
        ORIGINAL_CATALOG_BACKUP
    )

    if backup_sha != current_sha:
        raise IOError(
            "Il backup del catalogo "
            "non ha lo stesso SHA256."
        )

    info(
        "[BACKUP] catalog.json salvato in:"
    )

    info(
        str(
            ORIGINAL_CATALOG_BACKUP
        )
    )

    LOGGER.write(
        "Original catalog backup created."
    )

    LOGGER.write(
        f"Backup SHA256: {backup_sha}"
    )


# ============================================================
# EXTRA DATA DECODING
# ============================================================

def get_extra_data_raw(
    catalog: dict[str, Any],
) -> bytes:

    value = catalog.get(
        "m_ExtraDataString"
    )

    if not isinstance(
        value,
        str,
    ):
        raise ValueError(
            "m_ExtraDataString mancante."
        )

    try:
        return base64.b64decode(
            value
        )
    except (
        binascii.Error,
        ValueError,
    ) as exc:
        raise ValueError(
            "m_ExtraDataString non è "
            f"Base64 valido: {exc}"
        ) from exc


def decode_extra_data(
    raw: bytes,
) -> list[tuple[str, str]]:

    results = []

    # Questo catalogo è UTF-16 LE.
    # Gli altri decoder rimangono come fallback.
    for encoding in (
        "utf-16-le",
        "utf-16-be",
        "utf-8",
        "latin-1",
    ):

        try:

            text = raw.decode(
                encoding,
                errors="ignore",
            )

            results.append(
                (
                    encoding,
                    text,
                )
            )

            LOGGER.write(
                f"m_ExtraDataString "
                f"{encoding}: "
                f"{len(text)} chars"
            )

        except Exception as exc:

            LOGGER.write(
                f"Decode {encoding} failed: "
                f"{exc}"
            )

    return results


# ============================================================
# EXTRACT TARGET RECORD
# ============================================================

def extract_target_record_from_text(
    text: str,
    target_hash: str,
) -> dict[str, Any] | None:

    # Cerca direttamente il token m_Hash.
    pattern = re.compile(
        r'"m_Hash"\s*:\s*"'
        + re.escape(target_hash)
        + r'"',
        re.IGNORECASE,
    )

    matches = list(
        pattern.finditer(text)
    )

    if not matches:
        return None

    for match in matches:

        hash_position = (
            match.start()
        )

        # Trova l'inizio del più vicino oggetto JSON.
        start = text.rfind(
            "{",
            0,
            hash_position,
        )

        if start < 0:
            continue

        # Scansione bilanciata.
        depth = 0
        in_string = False
        escaped = False
        end = None

        for pos in range(
            start,
            len(text),
        ):

            char = text[pos]

            if in_string:

                if escaped:
                    escaped = False
                    continue

                if char == "\\":
                    escaped = True
                    continue

                if char == '"':
                    in_string = False

                continue

            if char == '"':
                in_string = True
                continue

            if char == "{":
                depth += 1

            elif char == "}":

                depth -= 1

                if depth == 0:
                    end = pos + 1
                    break

        if end is None:
            continue

        fragment = text[
            start:end
        ]

        # --------------------------------------------------------
        # Primo tentativo: JSON vero.
        # --------------------------------------------------------

        try:

            value = json.loads(
                fragment
            )

            if (
                isinstance(
                    value,
                    dict,
                )
                and str(
                    value.get(
                        "m_Hash",
                        ""
                    )
                ).lower()
                == target_hash.lower()
            ):
                return value

        except Exception:
            pass

        # --------------------------------------------------------
        # Fallback singoli campi.
        # --------------------------------------------------------

        def get_string(
            name: str,
        ):
            result = re.search(
                rf'"{re.escape(name)}"\s*:\s*"([^"]*)"',
                fragment,
                re.IGNORECASE,
            )

            return (
                result.group(1)
                if result
                else None
            )

        def get_integer(
            name: str,
        ):
            result = re.search(
                rf'"{re.escape(name)}"\s*:\s*(-?\d+)',
                fragment,
                re.IGNORECASE,
            )

            return (
                int(
                    result.group(1)
                )
                if result
                else None
            )

        def get_boolean(
            name: str,
        ):
            result = re.search(
                rf'"{re.escape(name)}"\s*:\s*(true|false)',
                fragment,
                re.IGNORECASE,
            )

            if result is None:
                return None

            return (
                result.group(1).lower()
                == "true"
            )

        value = {
            "m_Hash": get_string(
                "m_Hash"
            ),
            "m_Crc": get_integer(
                "m_Crc"
            ),
            "m_Timeout": get_integer(
                "m_Timeout"
            ),
            "m_ChunkedTransfer":
                get_boolean(
                    "m_ChunkedTransfer"
                ),
            "m_RedirectLimit":
                get_integer(
                    "m_RedirectLimit"
                ),
            "m_RetryCount":
                get_integer(
                    "m_RetryCount"
                ),
            "m_BundleName":
                get_string(
                    "m_BundleName"
                ),
            "m_AssetLoadMode":
                get_integer(
                    "m_AssetLoadMode"
                ),
            "m_BundleSize":
                get_integer(
                    "m_BundleSize"
                ),
            "m_UseCrcForCachedBundles":
                get_boolean(
                    "m_UseCrcForCachedBundles"
                ),
            "m_UseUWRForLocalBundles":
                get_boolean(
                    "m_UseUWRForLocalBundles"
                ),
            "m_ClearOtherCachedVersionsWhenLoaded":
                get_boolean(
                    "m_ClearOtherCachedVersionsWhenLoaded"
                ),
        }

        if (
            str(
                value.get(
                    "m_Hash",
                    ""
                )
            ).lower()
            == target_hash.lower()
        ):
            return value

    return None


def extract_target_record(
    catalog_path: Path,
) -> tuple[
    dict[str, Any] | None,
    str | None,
    str | None,
]:
    """
    Ritorna:
        record
        encoding
        context

    context contiene un'ampia finestra attorno al match.
    """

    catalog = load_json(
        catalog_path
    )

    raw = get_extra_data_raw(
        catalog
    )

    decoded = decode_extra_data(
        raw
    )

    for (
        encoding,
        text,
    ) in decoded:

        position = text.lower().find(
            TARGET_HASH.lower()
        )

        if position < 0:
            LOGGER.write(
                f"{encoding}: "
                "target hash not found."
            )

            continue

        LOGGER.write(
            f"{encoding}: "
            f"target found at "
            f"offset {position}."
        )

        record = (
            extract_target_record_from_text(
                text,
                TARGET_HASH,
            )
        )

        if record is not None:

            context_start = max(
                0,
                position - 1000,
            )

            context_end = min(
                len(text),
                position + 5000,
            )

            context = text[
                context_start:context_end
            ]

            return (
                record,
                encoding,
                context,
            )

    return (
        None,
        None,
        None,
    )


# ============================================================
# CATALOG VERIFICATION
# ============================================================

def verify_original_catalog():
    info(
        "[CHECK] Verifico catalogo originale..."
    )

    (
        record,
        encoding,
        context,
    ) = extract_target_record(
        ORIGINAL_CATALOG_BACKUP
    )

    if record is None:
        raise RuntimeError(
            "Non riesco a estrarre dal catalogo "
            "originale l'AssetBundleRequestOptions "
            f"per {TARGET_HASH}."
        )

    LOGGER.write()
    LOGGER.write(
        "=" * 100
    )
    LOGGER.write(
        "ORIGINAL CATALOG TARGET"
    )
    LOGGER.write(
        "=" * 100
    )

    LOGGER.write(
        f"Encoding: {encoding}"
    )

    LOGGER.write(
        json.dumps(
            record,
            indent=2,
            ensure_ascii=False,
        )
    )

    LOGGER.write(
        "Context:"
    )

    if context:
        LOGGER.write(
            context
        )

    # --------------------------------------------------------
    # Exact checks
    # --------------------------------------------------------

    if (
        str(
            record.get(
                "m_Hash",
                ""
            )
        ).lower()
        != TARGET_HASH.lower()
    ):
        raise RuntimeError(
            "m_Hash del target non coincide."
        )

    if (
        record.get(
            "m_Crc"
        )
        != EXPECTED_CRC
    ):
        raise RuntimeError(
            "CRC del catalogo originale "
            "inaspettato: "
            f"{record.get('m_Crc')} "
            f"(atteso {EXPECTED_CRC})."
        )

    if (
        record.get(
            "m_BundleSize"
        )
        != EXPECTED_BUNDLE_SIZE
    ):
        raise RuntimeError(
            "BundleSize del catalogo originale "
            "inaspettato: "
            f"{record.get('m_BundleSize')} "
            f"(atteso {EXPECTED_BUNDLE_SIZE})."
        )

    if (
        record.get(
            "m_UseCrcForCachedBundles"
        )
        is not True
    ):
        raise RuntimeError(
            "m_UseCrcForCachedBundles "
            "non è true sul catalogo originale."
        )

    info(
        "[OK] Hash target verificato."
    )

    info(
        f"[OK] CRC originale = "
        f"{record['m_Crc']}"
    )

    info(
        f"[OK] BundleSize = "
        f"{record['m_BundleSize']}"
    )

    info(
        "[OK] UseCrcForCachedBundles = true"
    )

    return record


# ============================================================
# ORIGINAL BUNDLE VERIFICATION
# ============================================================

def analyze_bundle(
    label: str,
    path: Path,
):
    if not file_exists(
        path
    ):
        raise FileNotFoundError(
            f"{label}: file non trovato:\n"
            f"{path}"
        )

    size = file_size(
        path
    )

    sha = sha256_file(
        path
    )

    LOGGER.write()
    LOGGER.write(
        "=" * 100
    )
    LOGGER.write(
        label
    )
    LOGGER.write(
        "=" * 100
    )

    LOGGER.write(
        f"Path: {path}"
    )

    LOGGER.write(
        f"Size: {size}"
    )

    LOGGER.write(
        f"SHA256: {sha}"
    )

    return {
        "path": str(
            path
        ),
        "size": size,
        "sha256": sha,
    }


def verify_original_bundle():
    info(
        "[CHECK] Verifico bundle originale..."
    )

    data = analyze_bundle(
        "ORIGINAL BUNDLE BEFORE PATCH",
        TARGET_BUNDLE,
    )

    if (
        data["size"]
        != EXPECTED_BUNDLE_SIZE
    ):
        raise RuntimeError(
            "Il bundle non è quello originale: "
            f"size={data['size']}, "
            f"expected={EXPECTED_BUNDLE_SIZE}."
        )

    if (
        data["sha256"]
        != EXPECTED_ORIGINAL_BUNDLE_SHA256
    ):
        raise RuntimeError(
            "Il bundle non corrisponde "
            "allo SHA256 originale noto."
        )

    info(
        "[OK] Bundle originale verificato."
    )

    info(
        f"  Size: {data['size']:,}"
    )

    info(
        f"  SHA256: {data['sha256']}"
    )

    return data


# ============================================================
# RUN USER SCRIPT
# ============================================================

def run_user_script():
    if not file_exists(
        USER_SCRIPT
    ):
        raise FileNotFoundError(
            "script.py non trovato:\n"
            f"{USER_SCRIPT}"
        )

    info("")
    info(
        "=" * 80
    )
    info(
        "[RUN] Eseguo script.py..."
    )
    info(
        "=" * 80
    )

    LOGGER.write()
    LOGGER.write(
        "=" * 100
    )
    LOGGER.write(
        "RUN USER SCRIPT"
    )
    LOGGER.write(
        "=" * 100
    )

    # Usiamo lo stesso Python con cui è stato lanciato
    # patch_and_verify.py.
    command = [
        sys.executable,
        str(USER_SCRIPT),
    ]

    LOGGER.write(
        f"Command: {command}"
    )

    try:
        result = subprocess.run(
            command,
            cwd=str(
                USER_SCRIPT.parent
            ),
        )

    except Exception as exc:

        LOGGER.write(
            f"User script exception: "
            f"{type(exc).__name__}: {exc}"
        )

        raise

    LOGGER.write(
        f"Return code: "
        f"{result.returncode}"
    )

    if result.returncode != 0:

        raise RuntimeError(
            "script.py è terminato con "
            f"exit code {result.returncode}. "
            "Catalogo NON patchato."
        )

    info(
        "[OK] script.py terminato correttamente."
    )


# ============================================================
# VERIFY MODIFICATION
# ============================================================

def verify_bundle_modified(
    original_bundle_info: dict[str, Any],
):
    info("")
    info(
        "[CHECK] Verifico bundle modificato..."
    )

    current = analyze_bundle(
        "BUNDLE AFTER script.py",
        TARGET_BUNDLE,
    )

    same_size = (
        current["size"]
        == original_bundle_info["size"]
    )

    same_sha = (
        current["sha256"]
        == original_bundle_info["sha256"]
    )

    LOGGER.write(
        f"Same size as original: {same_size}"
    )

    LOGGER.write(
        f"Same SHA256 as original: {same_sha}"
    )

    # Salviamo sempre uno snapshot del bundle risultante.
    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    shutil.copy2(
        TARGET_BUNDLE,
        MODIFIED_BUNDLE_SNAPSHOT,
    )

    LOGGER.write(
        f"Modified snapshot: "
        f"{MODIFIED_BUNDLE_SNAPSHOT}"
    )

    if same_sha:

        raise RuntimeError(
            "script.py ha terminato correttamente, "
            "ma il bundle ha ancora esattamente "
            "lo SHA256 originale. "
            "Nessuna modifica binaria rilevata. "
            "Catalogo NON patchato."
        )

    info(
        "[OK] Bundle modificato rilevato."
    )

    info(
        f"  Size: {current['size']:,}"
    )

    info(
        f"  SHA256: {current['sha256']}"
    )

    return current


# ============================================================
# CREATE WORKING CATALOG
# ============================================================

def create_working_catalog():
    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    if file_exists(
        WORKING_CATALOG
    ):
        WORKING_CATALOG.unlink()

    shutil.copy2(
        ORIGINAL_CATALOG_BACKUP,
        WORKING_CATALOG,
    )

    sha_original = sha256_file(
        ORIGINAL_CATALOG_BACKUP
    )

    sha_working = sha256_file(
        WORKING_CATALOG
    )

    LOGGER.write()
    LOGGER.write(
        "=" * 100
    )
    LOGGER.write(
        "WORKING CATALOG"
    )
    LOGGER.write(
        "=" * 100
    )

    LOGGER.write(
        f"Original SHA: {sha_original}"
    )

    LOGGER.write(
        f"Working SHA: {sha_working}"
    )

    if sha_original != sha_working:
        raise RuntimeError(
            "La working copy del catalogo "
            "non coincide col backup originale."
        )

    info(
        "[OK] Working copy del catalogo creata."
    )

    return WORKING_CATALOG


# ============================================================
# FIND ADDRESSABLESTOOLS
# ============================================================

def find_addressables_tools():
    if file_exists(
        ADDRESSABLES_TOOLS_EXE
    ):
        return ADDRESSABLES_TOOLS_EXE

    # Fallback: qualche possibile posizione.
    candidates = [
        Path.cwd()
        / "Example.exe",

        BASE_DIR
        / "Example.exe",

        BASE_DIR.parent
        / "Example.exe",
    ]

    seen = set()

    for candidate in candidates:

        if candidate in seen:
            continue

        seen.add(
            candidate
        )

        if file_exists(
            candidate
        ):
            return candidate

    return None


# ============================================================
# PATCH CRC
# ============================================================

def run_patchcrc(
    tool: Path,
):
    info("")
    info(
        "=" * 80
    )
    info(
        "[PATCH] Azzero CRC nella working copy..."
    )
    info(
        "=" * 80
    )

    LOGGER.write()
    LOGGER.write(
        "=" * 100
    )
    LOGGER.write(
        "ADDRESSABLESTOOLS PATCHCRC"
    )
    LOGGER.write(
        "=" * 100
    )

    command = [
        str(tool),
        "patchcrc",
        str(WORKING_CATALOG),
    ]

    LOGGER.write(
        f"Command: {command}"
    )

    try:

        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
        )

    except Exception as exc:

        LOGGER.write(
            f"patchcrc exception: "
            f"{type(exc).__name__}: {exc}"
        )

        raise

    LOGGER.write(
        "STDOUT:"
    )

    LOGGER.write(
        result.stdout
    )

    LOGGER.write(
        "STDERR:"
    )

    LOGGER.write(
        result.stderr
    )

    LOGGER.write(
        f"Return code: "
        f"{result.returncode}"
    )

    if result.returncode != 0:

        raise RuntimeError(
            "AddressablesTools patchcrc "
            f"ha restituito {result.returncode}."
        )

    # --------------------------------------------------------
    # Output variations
    # --------------------------------------------------------

    candidates = [
        WORKING_CATALOG,

        Path(
            str(WORKING_CATALOG)
            + ".patched"
        ),

        WORKING_CATALOG.with_name(
            WORKING_CATALOG.stem
            + ".patched"
            + WORKING_CATALOG.suffix
        ),

        OUTPUT_DIR
        / "catalog.patched.json",
    ]

    generated = None

    for candidate in candidates:

        if file_exists(
            candidate
        ):

            generated = candidate
            break

    if generated is None:

        raise RuntimeError(
            "patchcrc terminato correttamente "
            "ma non è stato trovato il catalogo "
            "patched risultante."
        )

    # Se patchcrc ha modificato la working copy
    # direttamente, la copiamo in PATCHED_CATALOG.
    if (
        generated.resolve()
        == WORKING_CATALOG.resolve()
    ):

        shutil.copy2(
            WORKING_CATALOG,
            PATCHED_CATALOG,
        )

    else:

        shutil.copy2(
            generated,
            PATCHED_CATALOG,
        )

    info(
        "[OK] Catalogo patched creato:"
    )

    info(
        str(
            PATCHED_CATALOG
        )
    )

    return PATCHED_CATALOG


# ============================================================
# VERIFY PATCHED CATALOG
# ============================================================

def verify_patched_catalog():
    info(
        "[CHECK] Verifico CRC patched..."
    )

    (
        record,
        encoding,
        context,
    ) = extract_target_record(
        PATCHED_CATALOG
    )

    if record is None:
        raise RuntimeError(
            "Non riesco a trovare il target "
            "nel catalogo patched."
        )

    LOGGER.write()
    LOGGER.write(
        "=" * 100
    )
    LOGGER.write(
        "PATCHED TARGET RECORD"
    )
    LOGGER.write(
        "=" * 100
    )

    LOGGER.write(
        f"Encoding: {encoding}"
    )

    LOGGER.write(
        json.dumps(
            record,
            indent=2,
            ensure_ascii=False,
        )
    )

    if context:
        LOGGER.write(
            "Context:"
        )
        LOGGER.write(
            context
        )

    # --------------------------------------------------------
    # Hash invariato
    # --------------------------------------------------------

    if (
        str(
            record.get(
                "m_Hash",
                ""
            )
        ).lower()
        != TARGET_HASH.lower()
    ):
        raise RuntimeError(
            "m_Hash del catalogo patched "
            "non coincide col target."
        )

    # --------------------------------------------------------
    # CRC = 0
    # --------------------------------------------------------

    if (
        record.get(
            "m_Crc"
        )
        != 0
    ):
        raise RuntimeError(
            "Il CRC del target non è zero: "
            f"{record.get('m_Crc')}"
        )

    # --------------------------------------------------------
    # BundleSize lasciato invariato
    # --------------------------------------------------------

    if (
        record.get(
            "m_BundleSize"
        )
        != EXPECTED_BUNDLE_SIZE
    ):
        raise RuntimeError(
            "Il BundleSize nel catalogo patched "
            "è cambiato inaspettatamente: "
            f"{record.get('m_BundleSize')}"
        )

    info(
        "[OK] m_Hash invariato."
    )

    info(
        "[OK] m_Crc = 0."
    )

    info(
        "[OK] m_BundleSize invariato."
    )

    return record


# ============================================================
# INSTALL PATCHED CATALOG
# ============================================================

def install_patched_catalog():
    info("")
    info(
        "=" * 80
    )
    info(
        "[INSTALL] Installo catalog.json patched..."
    )
    info(
        "=" * 80
    )

    # --------------------------------------------------------
    # Backup
    # --------------------------------------------------------

    INSTALLED_CATALOG_BACKUP_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    backup_path = (
        INSTALLED_CATALOG_BACKUP_DIR
        / (
            "catalog.before_patch."
            + timestamp
            + ".json"
        )
    )

    catalog_before_sha = sha256_file(
        CATALOG_PATH
    )

    shutil.copy2(
        CATALOG_PATH,
        backup_path,
    )

    backup_sha = sha256_file(
        backup_path
    )

    if backup_sha != catalog_before_sha:
        raise RuntimeError(
            "Backup del catalogo di gioco "
            "fallito."
        )

    LOGGER.write()
    LOGGER.write(
        "=" * 100
    )
    LOGGER.write(
        "CATALOG INSTALLATION"
    )
    LOGGER.write(
        "=" * 100
    )

    LOGGER.write(
        f"Game catalog backup: "
        f"{backup_path}"
    )

    LOGGER.write(
        f"Game catalog SHA before: "
        f"{catalog_before_sha}"
    )

    # --------------------------------------------------------
    # Install
    # --------------------------------------------------------

    patched_sha = sha256_file(
        PATCHED_CATALOG
    )

    shutil.copy2(
        PATCHED_CATALOG,
        CATALOG_PATH,
    )

    installed_sha = sha256_file(
        CATALOG_PATH
    )

    LOGGER.write(
        f"Patched catalog SHA: "
        f"{patched_sha}"
    )

    LOGGER.write(
        f"Installed catalog SHA: "
        f"{installed_sha}"
    )

    # --------------------------------------------------------
    # Final SHA verification
    # --------------------------------------------------------

    if installed_sha != patched_sha:

        raise RuntimeError(
            "SHA256 del catalogo installato "
            "non coincide con il catalogo patched."
        )

    info(
        "[OK] catalog.json installato."
    )

    info(
        f"[OK] Backup:\n{backup_path}"
    )

    info(
        f"[OK] SHA256: {installed_sha}"
    )

    return {
        "backup": backup_path,
        "before_sha": catalog_before_sha,
        "patched_sha": patched_sha,
        "installed_sha": installed_sha,
    }


# ============================================================
# FINAL VERIFY
# ============================================================

def final_verify(
    modified_bundle_info: dict[str, Any],
    install_info: dict[str, Any],
):
    info("")
    info(
        "=" * 80
    )
    info(
        "[FINAL CHECK]"
    )
    info(
        "=" * 80
    )

    # --------------------------------------------------------
    # Bundle deve ancora essere quello modificato
    # --------------------------------------------------------

    current_bundle = analyze_bundle(
        "FINAL BUNDLE",
        TARGET_BUNDLE,
    )

    if (
        current_bundle["sha256"]
        != modified_bundle_info["sha256"]
    ):
        raise RuntimeError(
            "Il bundle è cambiato dopo "
            "l'installazione del catalogo."
        )

    # --------------------------------------------------------
    # Catalog deve coincidere con patched
    # --------------------------------------------------------

    current_catalog_sha = sha256_file(
        CATALOG_PATH
    )

    if (
        current_catalog_sha
        != install_info["installed_sha"]
    ):
        raise RuntimeError(
            "SHA del catalogo finale "
            "inaspettato."
        )

    # --------------------------------------------------------
    # Rileggiamo target
    # --------------------------------------------------------

    (
        final_record,
        final_encoding,
        _final_context,
    ) = extract_target_record(
        CATALOG_PATH
    )

    if final_record is None:
        raise RuntimeError(
            "Target non trovato "
            "nel catalogo installato."
        )

    if (
        final_record.get(
            "m_Hash"
        )
        != TARGET_HASH
    ):
        raise RuntimeError(
            "Hash target alterato."
        )

    if (
        final_record.get(
            "m_Crc"
        )
        != 0
    ):
        raise RuntimeError(
            "CRC finale non zero."
        )

    if (
        final_record.get(
            "m_BundleSize"
        )
        != EXPECTED_BUNDLE_SIZE
    ):
        raise RuntimeError(
            "BundleSize finale alterato."
        )

    LOGGER.write()
    LOGGER.write(
        "=" * 100
    )
    LOGGER.write(
        "FINAL VERIFICATION"
    )
    LOGGER.write(
        "=" * 100
    )

    LOGGER.write(
        "FINAL TARGET RECORD:"
    )

    LOGGER.write(
        json.dumps(
            final_record,
            indent=2,
            ensure_ascii=False,
        )
    )

    LOGGER.write(
        f"Final bundle SHA256: "
        f"{current_bundle['sha256']}"
    )

    LOGGER.write(
        f"Final catalog SHA256: "
        f"{current_catalog_sha}"
    )

    info(
        "[OK] Bundle invariato dopo il patch del catalogo."
    )

    info(
        "[OK] Catalogo finale contiene m_Crc = 0."
    )

    info(
        "[OK] Catalogo finale contiene "
        "BundleSize = 268667."
    )

    info(
        "[OK] Catalogo installato verificato."
    )

    return final_record


# ============================================================
# MAIN WORKFLOW
# ============================================================

def main():

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    LOGGER.open()

    try:

        info(
            "=" * 80
        )

        info(
            "ADDRESSABLES PATCH + VERIFY"
        )

        info(
            "=" * 80
        )

        # --------------------------------------------------------
        # 0. Configuration report
        # --------------------------------------------------------

        LOGGER.write(
            f"GAME_ROOT: {GAME_ROOT}"
        )

        LOGGER.write(
            f"AA_DIR: {AA_DIR}"
        )

        LOGGER.write(
            f"CATALOG_PATH: {CATALOG_PATH}"
        )

        LOGGER.write(
            f"USER_SCRIPT: {USER_SCRIPT}"
        )

        LOGGER.write(
            f"ADDRESSABLES_TOOLS_EXE: "
            f"{ADDRESSABLES_TOOLS_EXE}"
        )

        LOGGER.write(
            f"TARGET_BUNDLE: {TARGET_BUNDLE}"
        )

        LOGGER.write(
            f"TARGET_HASH: {TARGET_HASH}"
        )

        LOGGER.write(
            f"EXPECTED_CRC: {EXPECTED_CRC}"
        )

        LOGGER.write(
            f"EXPECTED_BUNDLE_SIZE: "
            f"{EXPECTED_BUNDLE_SIZE}"
        )

        LOGGER.write(
            f"EXPECTED_ORIGINAL_BUNDLE_SHA256: "
            f"{EXPECTED_ORIGINAL_BUNDLE_SHA256}"
        )

        # --------------------------------------------------------
        # 1. Paths
        # --------------------------------------------------------

        if not GAME_ROOT.exists():
            raise FileNotFoundError(
                f"Game root non trovato:\n"
                f"{GAME_ROOT}"
            )

        if not AA_DIR.exists():
            raise FileNotFoundError(
                f"Directory aa non trovata:\n"
                f"{AA_DIR}"
            )

        if not file_exists(
            CATALOG_PATH
        ):
            raise FileNotFoundError(
                f"catalog.json non trovato:\n"
                f"{CATALOG_PATH}"
            )

        if not file_exists(
            USER_SCRIPT
        ):
            raise FileNotFoundError(
                f"script.py non trovato:\n"
                f"{USER_SCRIPT}"
            )

        if not file_exists(
            ADDRESSABLES_TOOLS_EXE
        ):
            raise FileNotFoundError(
                "Example.exe non trovato:\n"
                f"{ADDRESSABLES_TOOLS_EXE}"
            )

        # --------------------------------------------------------
        # 2. Original catalog backup
        # --------------------------------------------------------

        ensure_original_catalog_backup()

        # --------------------------------------------------------
        # 3. Verify original catalog
        # --------------------------------------------------------

        info(
            "\n[1/7] Verifico catalogo originale..."
        )

        original_record = (
            verify_original_catalog()
        )

        # --------------------------------------------------------
        # 4. Verify original bundle
        # --------------------------------------------------------

        info(
            "\n[2/7] Verifico bundle originale..."
        )

        original_bundle = (
            verify_original_bundle()
        )

        # --------------------------------------------------------
        # 5. Run user's script
        # --------------------------------------------------------

        info(
            "\n[3/7] Eseguo il programma di modifica..."
        )

        run_user_script()

        # --------------------------------------------------------
        # 6. Verify modified bundle
        # --------------------------------------------------------

        info(
            "\n[4/7] Verifico che il bundle sia realmente cambiato..."
        )

        modified_bundle = (
            verify_bundle_modified(
                original_bundle
            )
        )

        # --------------------------------------------------------
        # 7. Working catalog
        # --------------------------------------------------------

        info(
            "\n[5/7] Creo working copy del catalogo..."
        )

        create_working_catalog()

        # --------------------------------------------------------
        # 8. patchcrc
        # --------------------------------------------------------

        info(
            "\n[6/7] Patch CRC..."
        )

        tool = (
            find_addressables_tools()
        )

        if tool is None:
            raise FileNotFoundError(
                "Example.exe non trovato."
            )

        run_patchcrc(
            tool
        )

        verify_patched_catalog()

        # --------------------------------------------------------
        # 9. Install
        # --------------------------------------------------------

        info(
            "\n[7/7] Installo catalogo patched..."
        )

        install_info = (
            install_patched_catalog()
        )

        # --------------------------------------------------------
        # Final verification
        # --------------------------------------------------------

        final_record = final_verify(
            modified_bundle,
            install_info,
        )

        # --------------------------------------------------------
        # Report final
        # --------------------------------------------------------

        LOGGER.write()
        LOGGER.write(
            "=" * 100
        )
        LOGGER.write(
            "SUCCESS"
        )
        LOGGER.write(
            "=" * 100
        )

        LOGGER.write(
            "Original catalog record:"
        )

        LOGGER.write(
            json.dumps(
                original_record,
                indent=2,
                ensure_ascii=False,
            )
        )

        LOGGER.write(
            "Modified bundle:"
        )

        LOGGER.write(
            json.dumps(
                modified_bundle,
                indent=2,
                ensure_ascii=False,
            )
        )

        LOGGER.write(
            "Final catalog record:"
        )

        LOGGER.write(
            json.dumps(
                final_record,
                indent=2,
                ensure_ascii=False,
            )
        )

        info("")
        info(
            "=" * 80
        )
        info(
            "COMPLETATO"
        )
        info(
            "=" * 80
        )

        info(
            "Bundle modificato: OK"
        )

        info(
            "Catalogo Addressables patchato: OK"
        )

        info(
            "CRC target: 0"
        )

        info(
            f"Backup catalog originale:\n"
            f"{ORIGINAL_CATALOG_BACKUP}"
        )

        info(
            f"Backup catalog prima dell'installazione:\n"
            f"{install_info['backup']}"
        )

        info(
            f"Snapshot bundle modificato:\n"
            f"{MODIFIED_BUNDLE_SNAPSHOT}"
        )

        info(
            f"Report:\n"
            f"{REPORT_PATH}"
        )

        info("")
        info(
            "Ora puoi avviare il gioco."
        )

        return 0

    except KeyboardInterrupt:

        warn(
            "Operazione interrotta dall'utente."
        )

        LOGGER.write(
            "INTERRUPTED BY USER."
        )

        return 130

    except Exception as exc:

        error(
            f"{type(exc).__name__}: {exc}"
        )

        LOGGER.write()
        LOGGER.write(
            "=" * 100
        )
        LOGGER.write(
            "FAILED"
        )
        LOGGER.write(
            "=" * 100
        )

        LOGGER.write(
            f"{type(exc).__name__}: {exc}"
        )

        # --------------------------------------------------------
        # IMPORTANT SAFETY NOTE
        # --------------------------------------------------------
        #
        # Se qualcosa fallisce PRIMA dell'installazione del
        # catalogo patched, il catalogo del gioco rimane intatto.
        #
        # Se l'installazione è già avvenuta e una verifica finale
        # fallisce, esiste comunque il backup nella directory
        # catalog_backups.
        #

        print("")
        print(
            f"Report:\n{REPORT_PATH}"
        )

        return 1

    finally:

        LOGGER.close()


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    raise SystemExit(
        main()
    )