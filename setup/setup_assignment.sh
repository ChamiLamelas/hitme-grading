#!/bin/bash

# Script to upload submissions.zip from a local machine to
# proper hitme folder on Halligan. Run this for each
# assignment. Make sure submissions.zip is in the same
# folder as this file.
#
# This script assumes that you have your local machine's
# public key set up on the homework server so that you
# can SSH/SCP without user interaction.
#
# Chami Lamelas
# Summer 2023 - Spring 2024 

# Make sure user has supplied proper arguments (at least 2 - UTLN, assignment)
if [ $# -lt 2 ]; then
    echo "Usage: setup_assignment.sh YOURUTLN ASSIGNMENTNAME [EMAILS FOR EXTENSIONS...]"
    exit 1
fi

# Parse the UTLN, the assignment and extensions are the remaining arguments
UTLN=$1
shift 1
ASSIGNMENT_AND_EXTENSIONS=$@

# Check that submissions.zip exists in the same folder as this script on
# TA's local machine
SUBMISSIONS=submissions.zip
if [ ! -f "$SUBMISSIONS" ]; then
    echo "$SUBMISSIONS does not exist, download it from Gradescope."
    exit 1
fi

COURSEFOLDER=/comp/15
echo "Course folder is $COURSEFOLDER."

# SSH to TA's Halligan account to make sure that /comp/15/grading exists, otherwise
# error that would result below is somewhat misleading
REMOTEHOST=$UTLN@homework.cs.tufts.edu
REMOTEDIR=$COURSEFOLDER/grading
ssh $REMOTEHOST "test -d $REMOTEDIR"
REMOTEDIREXISTS=$?
if [ $REMOTEDIREXISTS -ne 0 ]; then
    echo "$REMOTEDIR does not exist -- this should have been created by the pipeline"
    exit 1
fi

# SCP submissions.zip to /comp/15/grading, give ta15 read access (the /comp/15
# group), then run the hitme setup script (which does the backup -- read access necessary
# so that setup script that's run as cs15acc can unzip the file), lastly remove
# submissions.zip after setup is complete
REMOTEFILE=$REMOTEDIR/$SUBMISSIONS
scp $SUBMISSIONS $REMOTEHOST:$REMOTEDIR
ssh $REMOTEHOST "chmod g+r $REMOTEFILE; $COURSEFOLDER/staff-bin/hitme/src/setup $ASSIGNMENT_AND_EXTENSIONS; rm $REMOTEFILE"
