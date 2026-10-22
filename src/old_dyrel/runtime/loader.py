import os


def load_dir(dir):
    for file in os.listdir(dir):
        if file.endswith("*.py"):
            load_file(file)


def load_file(file):
    with open(file, "r") as f:
        file_contents = f.read()

    try:
        code = compile(file_contents, f"<dyrel: {file}>", "exec")
    except Exception as e:
        print(e)
        breakpoint()
        raise
