"""
This provides a small set of functions relating to HitMe's configuration.

Chami Lamelas
Summer 2023 - Spring 2024
"""

import toml
from hitme import COURSE_FOLDER, HitMeException, check_db_initialized
import os
import misc
import toml
import getpass
import pandas as pd
from pathlib import Path

# Path to hitme config
HITME_CONFIG_PATH = os.path.join(COURSE_FOLDER, "config.toml")

# Path to the assignment configuration (on a user account)
CURRENT_ASSIGNMENT_FILE = os.path.expanduser(
    os.path.join("~", ".hitme_current_assignment.pkl")
)

# Path prefix to TA roster
TA_ROSTER_FILE_PREFIX = os.path.join(COURSE_FOLDER, "ta_roster")

# Allowed roster file formats
ALLOWED_ROSTER_TYPES = [".xlsx", ".csv", ".txt"]


def get_exempt_users():
    """
    Gets set of exempt users -- users whose submissions will be
    skipped. The set is of strings of Gradescope emails - lowercased.

    We lowercase to enable case insensitve check -- again emails should
    be treated case insensitively
    """

    return {u.lower() for u in toml.load(HITME_CONFIG_PATH)["hitme"]["EXEMPT_USERS"]}


def check_user_is_super_user(error=True):
    """
    Enforces that the current program user is a super user

    If they aren't, and error is True, a HitMeException is raised.
    If error is False, False is returned. Pass error as True (
    the default) when we want operation to halt. error False indicates
    that we want to silently do the check (and maybe not inform
    the user - e.g. viewprogress)

    If the user is a super user, True is returned

    The comparison is done in a case insensitive manner because program
    users on the Tufts homework servers are Tufts UTLNs.

    This is safe to use within Python scripts that are invoked via
    a SUID-bit set C executable (e.g. setup.py invoked from setup).
    """

    # The reason this is SUID-script-safe is because setuid modifies
    # the user ID of a process which is separate from the environment
    # variables checked by getpass.getuser( ) (see its documentation
    # here: https://docs.python.org/3/library/getpass.html#getpass.getuser)
    # It seems like these environment variables are unrelated from
    # user IDs, and are set elsewhere in Linux sessions:
    # https://unix.stackexchange.com/a/76356
    user = getpass.getuser().lower()
    if user not in {
        u.lower() for u in toml.load(HITME_CONFIG_PATH)["hitme"]["SUPER_USERS"]
    }:
        if error:
            raise HitMeException(
                f"You ({user}) are not a HitMe super user. Please contact the infra team."
            )
        else:
            return False
    return True


def get_course_id():
    """Gets Gradescope course ID as string."""

    return toml.load(HITME_CONFIG_PATH)["gradescope"]["COURSE_ID"]


def get_assignment():
    """Gets assignment name from file as string."""

    if not os.path.isfile(CURRENT_ASSIGNMENT_FILE):
        raise HitMeException(f"Assignment has not been set with startgrading.")
    return misc.read_pickle(CURRENT_ASSIGNMENT_FILE)


def set_assignment(assignment):
    """Sets user assignment by setting user file"""

    check_db_initialized(assignment)
    misc.write_pickle(CURRENT_ASSIGNMENT_FILE, assignment)


def get_tas():
    """
    Loads a set of the TAs utlns from a roster file

    For supported roster file types and formats, see the TF
    instructions file
    """

    # Look for a roster file from one of the allowed types
    roster_file = None
    for t in ALLOWED_ROSTER_TYPES:
        roster_file = TA_ROSTER_FILE_PREFIX + t
        if os.path.isfile(roster_file):
            break

    # No roster file could be found (none of the attempts above
    # were valid files)
    if roster_file is None:
        raise HitMeException(
            f"A roster file could not be found -- see the TF instructions"
        )

    # For txt files, we just assume its utlns on their own lines
    if roster_file.endswith(".txt"):
        return set(Path(roster_file).read_text().splitlines())

    # For tabular file types (Excel, CSV) we assume that there is
    # a utln column
    if roster_file.endswith(".xlsx"):
        roster = pd.read_excel(roster_file)
    elif roster_file.endswith(".csv"):
        roster = pd.read_csv(roster_file)

    # Make the columns lowercase to be nice to whoever made the
    # roster file, so we can accept Utln, UTLN, utln, etc.. 
    roster.columns = map(str.lower, roster.columns)

    if "utln" not in roster.columns:
        raise HitMeException(f"utln column missing from roster file")

    return set(roster["utln"].tolist())
