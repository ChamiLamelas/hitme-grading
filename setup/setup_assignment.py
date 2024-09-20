"""
Script to upload submissions.zip from a local machine to
proper hitme folder on Halligan. Run this for each
assignment. Make sure submissions.zip is in the same
folder as this file.

This script assumes that you have your local machine's
public key set up on the homework server so that you
can SSH/SCP.

For SSH setup instructions, see: 
https://docs.google.com/document/d/1PP3z9dFNvR7QRskbeoOGARQmJkBVItwH0xLLS05mapo/edit?usp=sharing

Useful links about paramiko/SSH for this file and 
reset_assignment.py:
https://stackoverflow.com/a/69596
https://stackoverflow.com/a/56522068
https://docs.paramiko.org/en/latest/api/client.html
https://docs.paramiko.org/en/latest/api/sftp.html
https://security.stackexchange.com/a/20710

Chami Lamelas
Summer 2023 - Spring 2024 
"""

import paramiko
import argparse
import stat
import sys
import os


def make_halligan_path(*path_components):
    """
    Alternative to os.path.join( ) which uses the local
    OS path separator to join the components of a path.
    This is needed for when we are constructing a path
    to be used on Halligan (i.e. remotely not locally).

    *path_components: Iterable[str]

    Returns path joined with / path separator
    """

    return "/".join(path_components)


SUBMISSIONS_FILE = "submissions.zip"
COURSEFOLDER = "/comp/15"

# We'll be using these paths on the remote (i.e. Halligan)
# so we don't use os.path.join( ) here
GRADINGFOLDER = make_halligan_path(COURSEFOLDER, "grading")
REMOTE_FILE = make_halligan_path(GRADINGFOLDER, SUBMISSIONS_FILE)


def get_args():
    """Parse the two or more arguments (UTLN, assignment name, extensions)"""

    parser = argparse.ArgumentParser()
    parser.add_argument("utln", type=str, help="Your UTLN")
    parser.add_argument("assignment", type=str, help="Gradescope assignment name")
    parser.add_argument(
        "extensions",
        nargs="*",
        type=str,
        help="Emails of students with extensions (see Gradescope roster)",
    )
    return parser.parse_args()


def setup_halligan_connection(ssh, utln):
    """
    Sets up SSH connection to utln@homework.cs.tufts.edu.
    Connection is done using private key and known hosts in ~/.ssh.

    ssh is a paramiko.client.SSHClient is an SSH client to be setup

    paramiko.sftp_client.SFTPClient is returned if connection
    can be made (a separate SFTP connection) or None if setup failed
    """

    # Here we use os.path.join as we are looking for a local file
    ssh.load_host_keys(os.path.expanduser(os.path.join("~", ".ssh", "known_hosts")))

    # Here we make check that TA can ssh to Halligan (i.e. have
    # their public key added to Halligan)
    try:
        ssh.connect("homework.cs.tufts.edu", username=utln)
    except paramiko.ssh_exception.AuthenticationException:
        return None 
    
    sftp = ssh.open_sftp()
    return sftp


def check_grading_dir_exists(sftp):
    """
    Make sure that /comp/15/grading exists, otherwise
    error that would result in following remote work would
    be misleading

    sftp is an paramiko.sftp_client.SFTPClient

    Returns true if folder exists, false otherwise
    """

    try:
        return os.path.basename(GRADINGFOLDER) in sftp.listdir(COURSEFOLDER)
    except IOError:
        return False


def run_remote_command(ssh, command):
    """
    Runs a command on a remote machine using established
    paramiko.SSHClient

    Command's stdout is displayed if no stderr is reported,
    otherwise stderr is displayed
    """

    # Commands we run for reset/setup don't require stdin
    _, stdout, stderr = ssh.exec_command(command)

    # If any stderr existed, it's printed as raw bytes to
    # avoid further decode error checks..
    stderr = stderr.read()
    stdout = stdout.read()
    if len(stderr) > 0:
        print("An error occurred running setup:", file=sys.stderr)
        print(stderr)
        print("Following output is stdout:", file=sys.stderr)
    try:
        print(stdout.decode("utf-8"))
    except UnicodeDecodeError:
        print(stdout)


def remote_run_hitme_setup(ssh, sftp, assignment, extensions):
    """
    Runs the hitme setup process on Halligan

    Takes output of get_halligan_connections, assignment,
    and extensions -- the latter two to pass to setup
    script
    """

    # SCP submissions.zip over, then give group read access
    # that way setup (running as cs15acc in group ta15) can
    # access this script as well (assuming TA is also
    # in group ta15) -- the reason why this is works is
    # somewhat complicated, and I try to explain it
    # here: https://docs.google.com/document/d/17dNXUSTioa-Kosv3lPU_y4k7kEo5IVVsrgTj80_0Yk8/edit#heading=h.anlydsu64drg
    sftp.put(SUBMISSIONS_FILE, REMOTE_FILE)
    sftp.chmod(REMOTE_FILE, stat.S_IRWXU | stat.S_IRGRP)

    # Run setup command, then remove the zip file
    command = make_halligan_path(COURSEFOLDER,
                                 "staff", "bin", "hitme", "src", "setup")
    command += " " + assignment
    if len(extensions) > 0:
        command += " " + " ".join(extensions)
    run_remote_command(ssh, command)
    sftp.remove(REMOTE_FILE)


def main():
    args = get_args()
    print(f"Course folder is {COURSEFOLDER}.")

    # Check that submissions.zip exists in the same folder as this script on
    # TA's local machine
    if not os.path.isfile(SUBMISSIONS_FILE):
        print(
            f"{SUBMISSIONS_FILE} doesn't exist in the current working directory",
            file=sys.stderr,
        )
        return

    ssh = paramiko.SSHClient()

    # Get SFTP session if SSH connection was successful (or None if not)
    sftp = setup_halligan_connection(ssh, args.utln)

    if sftp is None:
        print(
            f"ssh authentication failed to Halligan -- did you generate an SSH key pair and add the public key to Halligan?", 
            file=sys.stderr,
        )
    else:
        if check_grading_dir_exists(sftp):
            remote_run_hitme_setup(ssh, sftp, args.assignment, args.extensions)
        else:
            print(
                f"{GRADINGFOLDER} does not exist -- this should have been created by the pipeline",
                file=sys.stderr,
            )
        sftp.close()
    ssh.close()


if __name__ == "__main__":
    main()
