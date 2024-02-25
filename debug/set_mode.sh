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
# Fall 2023

if [ $# -lt 1 ]; then
    echo "Usage: set_mode.sh [ debug | release ]"
    exit 1
fi

MODE=$1
if [ $MODE != "debug" ] && [ $MODE != "release" ]; then
    echo "Usage: set_mode.sh [ debug | release ]"
    exit 1
fi

DEBUGGRADING="/h/$USER/cs15/grading"
if [ -d $DEBUGGRADING ]; then
    rm -rf $DEBUGGRADING
fi

if [ $MODE = "debug" ]; then
    FIND="/comp/15"
    REPLACE="/h/$USER/cs15"
    mkdir $DEBUGGRADING
else
    FIND="/h/$USER/cs15"
    REPLACE="/comp/15"
fi

sed -i "s\\"$FIND"\\"$REPLACE"\g" ../src/hitme.py ../src/setup.c ../src/setup.sh ../setup/setup_assignment.sh ../setup/reset_assignment.sh
cd ../src
make
