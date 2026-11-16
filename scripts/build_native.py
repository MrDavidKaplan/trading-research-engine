"""Build with GCC/Clang (Linux/macOS) or MSVC/MinGW (Windows). No CMake needed."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def build(debug=False):
    compiler = os.environ.get("CXX") or next((x for x in ("c++", "g++", "clang++", "cl") if shutil.which(x)), None)
    if not compiler:
        raise RuntimeError("No C++ compiler found. Install GCC/Clang or use --backend python.")
    output_dir = ROOT / "build"
    output_dir.mkdir(exist_ok=True)
    suffix = ".dll" if sys.platform == "win32" else ".dylib" if sys.platform == "darwin" else ".so"
    output = output_dir / ("execution" + suffix)
    source = ROOT / "native" / "execution.cpp"
    if Path(compiler).stem.lower() == "cl":
        command = [compiler, "/nologo", "/std:c++17", "/EHsc", "/LD", "/O2", str(source), f"/Fe:{output}"]
    else:
        command = [compiler, "-std=c++17", "-Wall", "-Wextra", "-Werror", "-shared", "-fPIC",
                   "-O0" if debug else "-O2", str(source), "-o", str(output)]
        if debug:
            command += ["-g", "-fsanitize=undefined", "-fno-sanitize-recover=all"]
    subprocess.run(command, check=True, cwd=output_dir)
    print(output)
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--debug", action="store_true", help="Enable undefined-behavior checks (GCC/Clang)")
    build(parser.parse_args().debug)
