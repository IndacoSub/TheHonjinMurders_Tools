import subprocess
import os
import re

# You can easily edit this kind of script to make it work with other Unity games such as HorrificXanatorium, FYI

script_dir = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/")
gameloc = "F:\SteamLibrary\steamapps\common\game-g15\game-g15\game-g15_Data"
program = "C:/Users/Volca/Documents/GitHub/UABEA/UAFGJ/bin/Release/net6.0/UAFGJ.exe"

def is_exception(arg):
    return arg.strip().isdigit() or bool(re.match(r'^-?\d+(\.\d+)?$', arg.strip()))
    
def check_program_exists(program):
    program_path = os.path.abspath(program)
    #program_path = program
    if not os.path.isfile(program_path):
        raise FileNotFoundError(f"The program '{program}' does not exist.")
    print(f"The program '{program}' exists")
    if not os.access(program_path, os.X_OK):
        raise PermissionError(f"The program '{program}' is not executable.")
    return program_path

def check_arguments_exist(args):
    for arg in args:
        arg_path = os.path.abspath(arg)
        if not os.path.isfile(arg_path) and not is_exception(arg):
            print(f"The argument '{arg}' does not exist.")
        if is_exception(arg):
            yield arg
        yield arg_path

def run_program(program, args_list):
    program_path = check_program_exists(program)
    for args in args_list:
        args_paths = list(check_arguments_exist(args))
        print(f"Running {program_path} with arguments: {args_paths}")
        try:
            process = subprocess.Popen([program_path] + args_paths)
            process.wait()
        except subprocess.CalledProcessError as e:
            print(f"Error occurred while running {program_path} with arguments: {args_paths}")
            print(e)
        print(f"Finished running {program_path} with arguments: {args_paths}")
        
def gameasset(arg):
    return os.path.join(gameloc, arg).replace("\\", "/")
    
def ga(arg):
    return gameasset(arg)
    
def png(arg):
    return os.path.join(script_dir, arg + ".png")
    
def txt(arg):
    return os.path.join(script_dir, arg + ".txt")
    
def pid(arg):
    return arg

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
