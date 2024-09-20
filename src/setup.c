/*
File that wraps setup.py's execution so that the backup and
hitme files are done in the name of cs15acc (the owner
of /comp/15).

The majority of work is done by staff/bin/hitme/src/setup.py

NOTE: If you make any changes to this file make sure you
recompile it by running `make setup` before pushing to the repo! 

Author: Chami Lamelas (slamel01)
Date: Fall 2023 - Fall 2025
*/

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/types.h>
#include <unistd.h>
#include <errno.h>

int main(int argc, char *argv[]) {

    // SUID bit stuff.. don't know all the details see the
    // 15 infra doc for what details I do know:
    // staff/docs/infra/Infrastructure.md 
    setuid(geteuid());
    setgid(getegid());
    setreuid(geteuid(), geteuid());
    setregid(getegid(), getegid());

    /*
    argv will be:
        argv[0] = executable path
        argv[1] = assignment name
        argv[2] = first extension ID
        argv[3] = second extension ID
        argv[4] = ...

    argv[2] and on are optional, and are of unknown
    length (known as argv at runtime)

    Will use this to construct our command to execute
    where we pass the assignment and the extension IDs
    into setup.sh script, basically making:

    exec_argv:
        exec_argv[0] = setup.sh path
        exec_argv[1] = assignment name
        exec_argv[2] = first extension ID
        exec_argv[3] = second extension ID
        exec_argv[4] = ...
        ...
        exec_argv[argc] = NULL

    We malloc to store all these shallow copies of strings
    (and string literals) then pass those on to execvp( ) 
    because we don't know length of this array of strings 
    till runtime

    In the case of a crash, just free the array (not the strings 
    themselves as they are just shallow copies of argv or literals).
    */
    char **exec_argv = malloc((argc + 1) * sizeof(char *)); 
    if (exec_argv == NULL) {
        perror("Simple malloc failed on Halligan, this is unexpected.\n");
        return 1;
    }

    exec_argv[0] = "/comp/15/staff/bin/hitme/src/setup.sh"; 
    for (int i = 1; i < argc; i++) {
        exec_argv[i] = argv[i];
    }
    exec_argv[argc] = NULL;

    // Execute the setup.sh script with above arguments
    if (execvp(exec_argv[0], exec_argv) < 0) {
        fprintf(stderr, "execvp error running %s: %s\n", exec_argv[0], strerror(errno));
        fprintf(stderr, "If this happens just once, try waiting a couple of minutes and rerunning.\n");
        free(exec_argv);
        return 1;
    }

    // Don't free exec_argv here because this code would be unreachable since
    // execvp replaces the current process code with the new process code (i.e.
    // running setup.sh ...). All allocated memory is freed when bash process ends.
    // See: https://linux.die.net/man/3/execvp
    return 0;
}

