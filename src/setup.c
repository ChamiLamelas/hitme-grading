/*
File that wraps setup.py's execution so that the backup and
hitme files are done in the name of cs15acc (the owner
of /comp/15).

The majority of work is done by staff-bin/hitme/src/setup.py

Author: Chami Lamelas (slamel01)
Date: Fall 2023 - Spring 2024
*/

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/types.h>
#include <unistd.h>

int main(int argc, char *argv[]) {
    
    // SUID bit stuff.. don't know the details see the
    // 15 infra doc for what details I do know:
    // https://docs.google.com/document/d/17dNXUSTioa-Kosv3lPU_y4k7kEo5IVVsrgTj80_0Yk8/edit#heading=h.emeweg40h6co
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

    Then, just free the array (not the strings themselves
    as they are just shallow copies of argv or literals).
    */
    char **exec_argv = malloc(argc + 1);
    exec_argv[0] = "/comp/15/staff-bin/hitme/src/setup.sh";
    for (int i = 1; i < argc; i++) {
        exec_argv[i] = argv[i];
    }
    exec_argv[argc] = NULL;

    int exit_code = 0;
    if (execvp(exec_argv[0], exec_argv) < 0) {
        perror("execvp error (aborting) - wait a minute before rerunning");
        exit_code = 1;
    }

    free(exec_argv);
    return exit_code;
}
