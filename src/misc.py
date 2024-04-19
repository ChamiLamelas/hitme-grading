"""
Collection of miscellaneous utilities used by hitme.py and the 
various commands files not particularly related to HitMe. 

Chami Lamelas
Summer 2023 - Spring 2024
"""

import pickle
import os
import yaml
import sys
import argparse
import filecmp
import shutil

HITME_COMMANDS = [
    "drop",
    "getlink",
    "hitme",
    "markdone",
    "markundone",
    "startgrading",
    "swap",
    "viewprogress",
]
"""List of all commands in our system available to regular users -- make sure to keep this updated!"""


def dirs_differ(dir1, dir2):
    """
    Checks whether two directories differ. This is not recursive and
    assumes that dir1 and dir2 are just directories each with just
    files in them. Like for example student submissions.

    Parameters:
        dir1, dir2: str paths to directories

    Returns:
        True if dir1 and dir2 have different files
    """

    # Do all list comparisons as sorted list comparisons just in case
    # of differences in file orderings -- this may not be necessary
    dir1_files = sorted(os.listdir(dir1))

    # Check if they have different file names in their directories
    if dir1_files != sorted(os.listdir(dir2)):
        return True

    # Now, compare the files in the directories the files to compare
    # are all the files in both (which are determined to be the
    # same from the above check)
    filecmp.clear_cache()
    output = filecmp.cmpfiles(dir1, dir2, dir1_files, shallow=False)

    # Files differ if the files that match do not include all the files
    return sorted(output[0]) != dir1_files


def help(command_help=None):
    """
    Returns a help message that includes all but the current command

    This uses the current script (assuming that's how commands are implemented)
    combined with the above HITME_COMMANDS list to show all the possible hitme
    commands.

    The output is a 2 element tuple, the first element is the help message for
    the command and the second contains the list of hitme commands
    """

    # Sort commands (in case they weren't specified alphabetically), then tab them all over
    commands_str = "\n".join(f"\t{e}" for e in sorted(HITME_COMMANDS))
    output = (
        command_help,
        f"The hitme commands are:\n{commands_str}\n\nRun [command] -h to get more details about each.\n",
    )
    return output


def lower(x):
    """Returns a function that lowercases a string"""

    return x.lower()


def get_one_argument(argument, argument_help, description, modifier=None):
    """
    Sets up ArgumentParser to parse a single command line argument

    Parameters:
        argument: str
            The name of the argument

        argument_help: str
            The help text for said argument

        description: tuple
            The help text for the program stored as a 2-tuple as
            returned by help( )

    Returns:
        The parsed argument
    """

    parser = argparse.ArgumentParser(
        description=description[0],
        epilog=description[1],
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(argument, type=str, help=argument_help)
    output = next(iter(vars(parser.parse_args()).values()))
    return modifier(output) if modifier is not None else output


def check_no_arguments(description):
    """Handles scripts that take no arguments, but still will display a help message"""

    script = os.path.basename(sys.argv[0])
    if len(sys.argv) == 2 and sys.argv[1] in {"-h", "--help"}:
        print(f"{script}: {description[0]}\n{description[1]}")
        sys.exit(0)
    elif len(sys.argv) != 1:
        red(f"{script} takes no arguments")
        sys.exit(1)


def read_yaml(filepath):
    """Reads a YAML file into a dict"""

    with open(filepath, "r") as f:
        return yaml.safe_load(f)


def read_pickle(filepath):
    """Reads a pickle file into appropriate object"""

    with open(filepath, "rb") as f:
        return pickle.load(f)


def write_pickle(filepath, obj):
    """Writes an object to a pickle file"""

    with open(filepath, "wb+") as f:
        pickle.dump(obj, f)


def colored_print(text, end, color):
    """Prints text in color"""

    # Adding flush in the hope that it appears faster
    print(f"\033[1;{color}{text}\033[0m", end=end, flush=True)


def get_screen_width():
    """Gets width of hitme program screen"""

    # Using shutil instead os to avoid issues when you pipe
    # viewprogress (the only command that uses this) into
    # grep for example -- found this solution here:
    # https://stackoverflow.com/questions/63345739/ioerror-errno-25-inappropriate-ioctl-for-device
    # https://stackoverflow.com/questions/58861759/python-return-something-similar-to-os-get-terminal-size
    return shutil.get_terminal_size().columns


def separator(text):
    """Prints a separator like:

    ======= Section header ======

    Based on screen width
    """

    screen_width = get_screen_width()
    num_markers = screen_width - len(text) - 2
    first_half = num_markers // 2
    second_half = num_markers - first_half
    blue("\n" + first_half * "=" + " " + text + " " + second_half * "=" + "\n")


def yellow(text, end="\n"):
    """Prints message in yellow"""

    colored_print(text, end, "93m")


def blue(text, end="\n"):
    """Prints message in blue"""

    colored_print(text, end, "36m")


def green(text, end="\n"):
    """Prints message in green"""

    colored_print(text, end, "32m")


def red(text, end="\n"):
    """Prints message in red"""

    colored_print(text, end, "31m")


def read_first_line(fp):
    """Reads and returns first line of a file"""

    with open(fp) as f:
        return next(iter(f))


def drop_extension(fp):
    """Drop extension from filepath if one is present"""

    idx = fp.find(".")
    if idx < 0:
        return fp
    return fp[:idx]


def left_justify_list(ls):
    """
    Left justifies the elements of a list so that they are
    right padded for use in a table. 

    For example, suppose we have ls = ["a", "bob", "slamel01"]

    Let X be a space. The output would be: 

    aXXXXXXXXXXXXXXX
    bobXXXXXXXXXXXXX
    slamel01XXXXXXXX
    
    That way whatever is printed right of the returned list 
    elements will all start at the same spot.
    """

    # We have the columns have a width that is some multiple
    # of tab length, and an 8-space tab looks the nicest in
    # my opinion
    indent_size = 8
    max_len = max(len(e) for e in ls)
    justification = ((max_len // indent_size) + 1) * indent_size
    return [e.ljust(justification) for e in ls]


def split_into_lists(ls):
    """Turns a list of 2-tuples into 2 lists"""

    ls1 = list()
    ls2 = list()
    for e1, e2 in ls:
        ls1.append(e1)
        ls2.append(e2)
    return ls1, ls2
