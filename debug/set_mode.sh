#!/bin/bash

# It is useful when debugging to work in a clone of the repo on
# your account on Halligan. If you run:
#
#   bash set_mode.sh debug
#
# This will change all the hitme source code to work with the
# course folder being ~/cs15 (this is assumed where your clone
# of the course repo is). It will also create a dummy grading/
# folder in your clone.
#
# You can now go into staff-bin of the clone and mess with the
# hitme source code for debugging.
#
# If you run:
#
#   bash set_mode.sh release
#
# This will change all the hitme source code back to use /comp/15
# as the course folder. It will remove the dummy grading/ folder
# from your clone. Even though it won't get pushed (because it's
# in the repo .gitignore) it's still good to remove.
#
# Make sure you run bash set_mode.sh release before you push!
#
# Chami Lamelas
# Fall 2023 - Spring 2024 

# Check 1 argument provided
if [ $# -lt 1 ]; then
    echo "Usage: set_mode.sh [ debug | release ]"
    exit 1
fi

# Check that argument is either debug or release 
MODE=$1
if [ $MODE != "debug" ] && [ $MODE != "release" ]; then
    echo "Usage: set_mode.sh [ debug | release ]"
    exit 1
fi

# Remove the debug grading folder if it already exists 
DEBUGGRADING="/h/$USER/cs15/grading"
if [ -d $DEBUGGRADING ]; then
    rm -rf $DEBUGGRADING
fi

# If debug mode, replace /comp/15 with /h/username/cs15 in 
# the necessary files (see sed below) and then make
# the debug grading folder  
if [ $MODE = "debug" ]; then
    FIND="/comp/15"
    REPLACE="/h/$USER/cs15"
    mkdir $DEBUGGRADING
else
    # In release mode, do the opposite -- use the real cs15 folder
    # which is /comp/15 
    FIND="/h/$USER/cs15"
    REPLACE="/comp/15"
fi

sed -i "s\\"$FIND"\\"$REPLACE"\g" ../src/hitme.py ../src/setup.c ../src/setup.sh ../setup/setup_assignment.py ../setup/reset_assignment.py

# Recompile setup.c -> setup (python scripts obviously don't
# have to be recompiled)
cd ../src
make
