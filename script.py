import subprocess
import os
import re
import sys

# ------------------------------------------------------------
# FORCE UTF-8 OUTPUT ON WINDOWS
# ------------------------------------------------------------

try:
    sys.stdout.reconfigure(
        encoding="utf-8",
        errors="replace"
    )

    sys.stderr.reconfigure(
        encoding="utf-8",
        errors="replace"
    )
except AttributeError:
    pass

script_dir = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/")
gameloc = "F:\SteamLibrary\steamapps\common\game-g15\game-g15\game-g15_Data"
program = "C:/Users/Volca/Documents/GitHub/NewUAFGJ/NewUAFGJ/bin/Release/net8.0/NewUAFGJ.exe"


# ============================================================
# ARGUMENT HELPERS
# ============================================================

def is_path_id(arg):
    """True se l'argomento è un PathID intero, anche negativo."""
    return bool(
        re.fullmatch(
            r"-?\d+",
            str(arg).strip()
        )
    )


def is_kind(arg):
    """
    True se l'argomento è un fileKind noto di UAFGJ.

    FileKind disponibili:

    MONOBEHAVIOUR_TEXT
        Usa questo quando il MonoBehaviour è una UI/TextMeshPro
        e ci interessa modificare SOLO:

            1 string m_text = "..."

        Non viene fatto alcun controllo degli altri scalar.
        Tutti gli altri campi del MonoBehaviour vengono lasciati
        esattamente come sono.

        È il tipo più semplice e sicuro quando sappiamo che
        l'unico dato che vogliamo cambiare è m_text.

    MONOBEHAVIOUR_TEXT_CHECKED
        Come MONOBEHAVIOUR_TEXT, quindi modifica SOLO m_text,
        ma richiede anche il controllo scalar del dump contro
        il BaseField.

        Usalo quando vuoi una verifica strutturale aggiuntiva
        oltre alla semplice sostituzione di m_text.

    MONOBEHAVIOUR_FONT
        Usa questo per MonoBehaviour che rappresentano un font
        / TMP FontAsset o comunque strutture in cui dobbiamo
        sostituire l'intero contenuto del dump.

        Viene importato TUTTO il MonoBehaviour.
        Non viene eseguito il controllo scalar.

    MONOBEHAVIOUR_FONT_CHECKED
        Come MONOBEHAVIOUR_FONT, quindi viene sostituito
        l'intero MonoBehaviour, ma viene anche eseguito
        il controllo scalar del dump.

        Usalo per i font quando vuoi anche la verifica
        strutturale completa prima del salvataggio.

    MONOBEHAVIOUR_FULL
        Usa questo per un MonoBehaviour generico che NON è
        un semplice m_text e NON è un font, quando vuoi
        sostituire l'intero contenuto del MonoBehaviour.

        Viene importato TUTTO il dump.
        Non viene eseguito il controllo scalar.

    MONOBEHAVIOUR_FULL_CHECKED
        Come MONOBEHAVIOUR_FULL, ma con controllo scalar.

        È il comportamento predefinito quando non specifichi
        un kind oppure quando il kind è vuoto e vuoi la modalità
        completa + verificata.


    In sintesi:

        TEXT
            → solo m_text
            → nessun controllo

        TEXT_CHECKED
            → solo m_text
            → controllo scalar

        FONT
            → tutto
            → nessun controllo

        FONT_CHECKED
            → tutto
            → controllo scalar

        FULL
            → tutto
            → nessun controllo

        FULL_CHECKED
            → tutto
            → controllo scalar
            → default


    Il confronto viene fatto ignorando maiuscole/minuscole e
    spazi iniziali/finali.
    """
    known_kinds = {
        "MONOBEHAVIOUR_TEXT",
        "MONOBEHAVIOUR_TEXT_CHECKED",
        "MONOBEHAVIOUR_FONT",
        "MONOBEHAVIOUR_FONT_CHECKED",
        "MONOBEHAVIOUR_FULL",
        "MONOBEHAVIOUR_FULL_CHECKED",
    }

    return (
        str(arg).strip().upper()
        in known_kinds
    )



def kind(arg):
    """
    Restituisce il fileKind così com'è.

    Serve a mantenere una sintassi uniforme:
        kind("MONOBEHAVIOUR_FULL_CHECKED")
    """
    return str(arg).strip()


# ============================================================
# PATH HELPERS
# ============================================================

def gameasset(arg):
    return os.path.join(
        gameloc,
        arg
    ).replace("\\", "/")


def ga(arg):
    return gameasset(arg)


def png(arg):
    return os.path.join(
        script_dir,
        arg + ".png"
    ).replace("\\", "/")


def txt(arg):
    return os.path.join(
        script_dir,
        arg + ".txt"
    ).replace("\\", "/")


def pid(arg):
    return str(arg)


# ============================================================
# FILE / ARGUMENT CHECKING
# ============================================================

def check_program_exists(program):
    program_path = os.path.abspath(
        program
    )

    if not os.path.isfile(program_path):
        raise FileNotFoundError(
            f"The program '{program}' does not exist."
        )

    print(
        f"The program '{program}' exists"
    )

    if not os.access(
        program_path,
        os.X_OK
    ):
        raise PermissionError(
            f"The program '{program}' is not executable."
        )

    return program_path


def check_arguments_exist(args):
    """
    I PathID e i fileKind NON vengono trattati come file.

    Tutto il resto viene considerato un path.
    """

    for arg in args:

        arg = str(arg).strip()

        # ----------------------------------------------------
        # PATH ID
        # ----------------------------------------------------

        if is_path_id(arg):
            yield arg
            continue

        # ----------------------------------------------------
        # FILE KIND
        # ----------------------------------------------------

        if is_kind(arg):
            yield arg
            continue

        # ----------------------------------------------------
        # FILE
        # ----------------------------------------------------

        arg_path = os.path.abspath(
            arg
        )

        if not os.path.isfile(
            arg_path
        ):
            print(
                f"The argument '{arg}' does not exist."
            )

        yield arg_path


# ============================================================
# PROGRAM EXECUTION
# ============================================================

def run_program(program, args_list):
    program_path = check_program_exists(
        program
    )

    for args in args_list:

        # ----------------------------------------------------
        # IGNORA I BLOCCHI COMMENTATI CON """ ... """
        # ----------------------------------------------------
        if isinstance(args, str):
            continue

        args_paths = list(
            check_arguments_exist(
                args
            )
        )

        print(
            f"Running {program_path} "
            f"with arguments: {args_paths}"
        )

        try:
            process = subprocess.Popen(
                [program_path] + args_paths
            )

            process.wait()

        except subprocess.CalledProcessError as e:
            print(
                f"Error occurred while running "
                f"{program_path} with arguments: "
                f"{args_paths}"
            )

            print(e)

        print(
            f"Finished running {program_path} "
            f"with arguments: {args_paths}"
        )

# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    print(f"Executing from: '{script_dir}'")
    
    arguments = [
    
        # TEXT
        
        [ga("StreamingAssets/aa/StandaloneWindows64/masterdata_assets_all_1007e97d1154ffcb0e91f2346a050762.bundle"),    txt("en/MasterADV"),                pid('-3291574284806033374')],
        [ga("StreamingAssets/aa/StandaloneWindows64/masterdata_assets_all_1007e97d1154ffcb0e91f2346a050762.bundle"),    txt("en/MasterCharacter"),          pid('-861232449677649201')],
        [ga("StreamingAssets/aa/StandaloneWindows64/masterdata_assets_all_1007e97d1154ffcb0e91f2346a050762.bundle"),    txt("en/MasterChunk"),              pid('4712180173613728409')],
        [ga("StreamingAssets/aa/StandaloneWindows64/masterdata_assets_all_1007e97d1154ffcb0e91f2346a050762.bundle"),    txt("en/MasterCorrelationDiagram"), pid('4081150100993318159')],
        
        # and so on...
    ]
    
    run_program(program, arguments)
