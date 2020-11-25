import os
import codecs


def save_file(path, content):
    with codecs.open(path, "wb", "utf8") as f:
        f.write(content)


def get_files_and_subfiles(folder, suffix, recursively=True):
    files = []
    if recursively:
        for root, _, dirfiles in os.walk(folder):
            for filename in dirfiles:
                path = os.path.join(root, filename)
                if file_ends_with(path, suffix):
                    files.append(path)
    else:
        files += [
            os.path.join(folder, f)
            for f in os.listdir(folder)
            if file_ends_with(os.path.join(folder, f), suffix)
        ]

    return files


def file_ends_with(path, suffix):
    return path.endswith(suffix)
