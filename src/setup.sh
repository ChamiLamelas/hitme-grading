# Bash script that sets up environment that enables for most recent installed version of
# Python (in /usr/sup/lib) to be run properly (LD_LIBARY_PATH destroyed once in SUID
# bit has been set on wrapping executable). It passes its command line arguments
# onto the Python script passed from C wrapper.
# 
# Author: Chami Lamelas (slamel01)
# Date: Fall 2023 - Spring 2024

PATH=/usr/sup/bin:$PATH
LD_LIBRARY_PATH=/usr/sup/lib:/usr/sup/lib64:${LD_LIBRARY_PATH}
export LD_LIBRARY_PATH

python3 /comp/15/staff-bin/hitme/src/setup.py $@
