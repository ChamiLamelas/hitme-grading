#!/bin/bash

# Script to reset the hitme files for an assignment.
# In particular, to wipe those files. The heavy lifting
# of this script is done in src/reset. 
#
# This script assumes that you have your local machine's
# public key set up on the homework server so that you
# can SSH without user interaction.
#
# Chami Lamelas
# Spring 2024

# Make sure user has supplied proper arguments
if [ $# -ne 2 ]; then
    echo "Usage: reset_assignment.sh YOURUTLN ASSIGNMENTNAME"
    exit 1
fi

# Parse the two arguments (UTLN, assignment name)
UTLN=$1
ASSIGNMENT=$2

COURSEFOLDER=/comp/15
echo "Course folder is $COURSEFOLDER."

# ssh in and run the reset script to do the heavy lifting 
REMOTEHOST=$UTLN@homework.cs.tufts.edu
ssh $REMOTEHOST "$COURSEFOLDER/staff-bin/hitme/src/reset $ASSIGNMENT"
