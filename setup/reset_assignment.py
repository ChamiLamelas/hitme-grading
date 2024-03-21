"""
Script to reset the hitme files for an assignment.
In particular, to wipe those files. The heavy lifting
of this script is done in src/reset. 

This script assumes that you have your local machine's
public key set up on the homework server.

For SSH setup instructions, see: 
https://docs.google.com/document/d/1PP3z9dFNvR7QRskbeoOGARQmJkBVItwH0xLLS05mapo/edit?usp=sharing

Chami Lamelas
Spring 2024
"""

import argparse
import paramiko
import sys
import os

COURSEFOLDER = "/comp/15"


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


def get_args():
    """Parse the two arguments (UTLN, assignment name)"""

    parser = argparse.ArgumentParser()
    parser.add_argument("utln", type=str, help="Your UTLN")
    parser.add_argument("assignment", type=str, help="Gradescope assignment name")
    return parser.parse_args()


def setup_halligan_connection(ssh, utln):
    """
    Sets up SSH connection to utln@homework.cs.tufts.edu.
    Connection is done using private key and known hosts in ~/.ssh.

    ssh is a paramiko.client.SSHClient is an SSH client to be setup

    True is returned if connection can be made or False if setup failed
    """

    # Here we use os.path.join as we are looking for a local file
    ssh.load_host_keys(os.path.expanduser(os.path.join("~", ".ssh", "known_hosts")))

    # Here we make check that TA can ssh to Halligan (i.e. have
    # their public key added to Halligan)
    try:
        ssh.connect("homework.cs.tufts.edu", username=utln)
    except paramiko.ssh_exception.AuthenticationException:
        return False 
    
    return True 


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


def confirm_reset(assignment):
    """
    Has user confirm they want to delete the grading backup and
    HitMe on file database for an assignment.
    """

    print(f"Grading may have begun for {assignment}")
    text = "Are you sure you would like to reset hitme (and delete the backup)? (y/n) "
    confirmation = input(text)
    while confirmation not in {"y", "n"}:
        confirmation = input("Choose y or n: ")
    return confirmation == "y"


def main():
    args = get_args()
    print(f"Course folder is {COURSEFOLDER}.")
    if confirm_reset(args.assignment):
        ssh = paramiko.SSHClient()
        if setup_halligan_connection(ssh, args.utln):
            # reset script does the heavy lifting - script
            # invoked remote side, don't use os.path.join
            command = (
                make_halligan_path(COURSEFOLDER, "staff-bin", "hitme", "src", "reset")
                + " "
                + args.assignment
            )
            run_remote_command(ssh, command)
        else:
            print(
                f"ssh authentication failed to Halligan -- did you generate an SSH key pair and add the public key to Halligan?", 
                file=sys.stderr,
            )
        ssh.close()


if __name__ == "__main__":
    main()
