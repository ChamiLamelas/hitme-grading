# CLI Version of HitMe

This document serves as a design description of the implementation of the command line interface (CLI) version of HitMe. It was built with the move off of the `provide` framework upon which the old website version of HitMe depended on. This version provides the same (with additional) functionality.

This document does not describe how to use or set up HitMe. For information on how to use HitMe, see [here](#hitme-ta-instructions) for teaching assistants and [here](#hitme-tf-instructions) for teaching fellows.

**Summer 2023 - Present**

## Note to those Outside of Tufts 

This system relies on access to certain software and devices restricted to the staff of the Tufts University CS 15 staff. This includes the folder `/comp/15` which holds course resources on a restricted server, course Gradescope resources, and the course GitLab repository.

Private information related to system setup such as course Gradescope information and course staff members is not included in this repository and has to be specified in a course configuration file.

## Overview

The CLI version of HitMe is initialized by a TA providing a `submissions.zip` file taken from Gradescope. From this file, student submissions are backed up into `/comp/15/grading/backup/assignmentname` and a database is initialized in `/comp/15/grading/hitme/assignmentname.pkl`.

Using a collection of scripts, TAs can get students to grade (including their Gradescope URL), mark students as complete, and view their grading progress. These operations are all simply interactions with the database.

## HitMe Database

We first describe the design of the HitMe database.

### Schema

Our database really consists of a single table per assignment. The table has the following schema.

| Column          | Type          | Description                                                                                                                                           |
| --------------- | ------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
| `STUDENTNAMES`  | `string`      | Comma separated list of Gradescope names of the students in the submission.                                                                           |
| `STUDENTIDS`    | `string`      | Comma separated list of emails of the students in the submission.                                                                                     |
| `GRADER`        | `string`      | `None` if `STATUS` is `NOTSTARTED`, the assigned TA when `STATUS` is `INPROGRESS`, and the grader who finished the grading if `STATUS` is `COMPLETE`. |
| `GRADESCOPEURL` | `string`      | Gradescope URL of the submission.                                                                                                                     |
| `STATUS`        | `enumeration` | One of `NOTSTARTED`, `INPROGRESS`, or `COMPLETE`.                                                                                                     |

### Simplified SQL

All of the HitMe operations can be implemented using a simplified set of SQL commands. If you are unfamiliar with SQL, please read up on the basic functionality of the following commands:

- `SELECT-FROM-WHERE` (with `LIMIT`)
- `GROUPBY-COUNT`
- `UPDATE-SET-WHERE`

This is described in more detail in [this section](#hitme-operations).

This is implemented atop [pandas](https://pandas.pydata.org/) in [hitme.py](src/hitme.py).

### Readers and Writers

During grading, some TAs will be reading while others will be writing. For instance, TAs who are viewing their progress or getting a Gradescope link will be readers. This is because these operations only read data from our database. On the other hand, TAs who are marking a submission as done will be updating information in the database.

To ensure that writes are consistent (same across all users), any write operation is protected by a lock as follows. Let a writer be an instance of a running HitMe operation that may require an update to the database. For example, an instance of a TA asking to get randomly assigned a submission to grade (running `hitme`).

1. Writer requests database write lock. If the lock is in use by another writer, wait until the other writer relinquishes the lock. Once the lock can be obtained by this writer, we go to step 2.
2. Writer acquires the database write lock.
3. Writer loads the database on file into memory. This is to ensure that any write operations are done on a fresh version of the database.
4. Writer performs any read operations necessary that may impact the write. Using the example of a TA running `hitme`, this could be to get a student at random who has not been completed or assigned to another TA.
5. Perform the write if necessary (e.g. assigning retrieved student to TA).
6. Relinquish the database write lock.

Steps 3 through 5 will be done knowing that no other writer could have touched the on file database.

A reader is an instance of a HitMe operation that would never need to update the database. For example, a TA who is viewing their grading progress. Readers do not get the lock. Therefore it is possible that their in memory copy of the database is stale (out of sync with the on file version). This is alright because if the TA decides to make a write operation based on what they see from the read, the writer will operate on a fresh version of the database as described in steps 3 through 5 above. Furthermore, this improves performance as it avoids unncessary lock contention.

The following HitMe operations are readers:

- `getlink`
- `viewprogress`
- `totalprogress`
- `admin --get`

The following HitMe operations are writers:

- `hitme`
- `markdone`
- `markundone`
- `swap`
- `admin --set`
- Initializing the database (i.e. `setup.py`).

Note that `startgrading` does not interact with the database.

For more information:

- The concept of a writer is similar to a SQL transaction.
- The readers writers problem is an example of a synchronization operating systems problem.

### Initializing the Database

All of the information necessary to initialize the database as per the schema above can be found in the `submissions.zip` provided by Gradescope. When extracted, it includes the active submissions in a subfolder named with the Gradescope assignment ID as well as a `submission_metadata.yml` which includes:

- Submitter Gradescope names.
- Submitter emails.
- Submission IDs. These along with the assignment and course IDs are all that is necessary to reconstruct Gradescope submission links.

After a TA downloads `submissions.zip` to their local machine, we perform the following steps. For simplicity of explanation, we make the following assumptions:

- The TA performing the setup has UTLN `slamel01`.
- The owner of `/comp/15/grading` has UTLN `cs15acc`.
- The group of `/comp/15/grading` is named `ta15`.

1. Copy the file to `/comp/15/grading` as `slamel01`.
2. Have `slamel01` give `ta15` read permission of `submissions.zip`.
3. Perform the following as `cs15acc`:

- Make `backup` and `hitme` subfolders of `/comp/15/grading` if they don't exist.
- Extract `submissions.zip`, extract all of the submissions and put them in `backup` named according to their submitters' emails. Emails are assumed unique while names may not be.
- Using the information from `submission_metadata.yml`, initialize the HitMe database with the previously described schema.

4. Have `slamel01` delete `submissions.zip`.

Step 3 can be performed by using the SUID bit.

This process is implemented over the following files:

- [setup.c](src/setup.c)
- [setup.sh](src/setup.sh)
- [setup.py](src/setup.py)
- [setup_assignment.sh](setup/setup_assignment.sh)

All the SUID bit stuff via these files may not be necessary for your application.

## HitMe Operations

In this section, we describe using simplified SQL how to implement each of the operations in the CLI version of HitMe to replicate what is provided on the website. These are just general pseudocode algorithms, and do not cover all the details. We recommend viewing the documented source code for more information.

### Get Gradescope URL

This gets the Gradescope URL for the submission given the submitter email(s). In this and following SQL blocks, we let `EMAIL` refer to the submitters emails provided by the user and `HITMEDATABASE` to refer to our HitMe database (table).

```sql
SELECT GRADESCOPEURL
FROM HITMEDATABASE
WHERE STUDENTIDS = EMAIL
```

This is implemented in [getlink](src/getlink).

### HitMe

This picks up a submission where grading has not been started. In this and following SQL blocks, we let `TA` refer to the UTLN of the TA performing the operation.

```sql
ACQUIRE LOCK

SAMPLEDSTUDENTID = (
    SELECT STUDENTIDS LIMIT 1
    FROM HITMEDATABASE
    WHERE STATUS = NOTSTARTED
)

UPDATE HITMEDATABASE
SET STATUS = INPROGRESS, GRADER = TA
WHERE STUDENTIDS = SAMPLEDSTUDENID

RELEASE LOCK
```

Here we use `ACQUIRE LOCK` and `RELEASE LOCK` to delimit a block of work protected by a lock (also known as a critical section).

This is implemented in [hitme](src/hitme).

### Mark Done

This just marks a submission as completed by a certain TA.

```sql
ACQUIRE LOCK

UPDATE HITMEDATABASE
SET GRADER = TA, STATUS = COMPLETE
WHERE STUDENTIDS = EMAIL

RELEASE LOCK
```

This is implemented in [markdone](src/markdone).

### Mark Undone

This just marks a submission as back in progress but originally assigned TA.

```sql
ACQUIRE LOCK

UPDATE HITMEDATABASE
SET GRADER = NONE, STATUS = INPROGRESS
WHERE STUDENTIDS = EMAIL

RELEASE LOCK
```

This is implemented in [markundone](src/markundone).

### Start Grading

As mentioned previously, `startgrading` does not interact with the database. Instead, it just sets a file (`~/.hitme_current_assignment.pkl`) with the current assignment a TA will be grading. Calls to the other HitMe operations (minus initializing the database) are done with the assignment read from this file.

This is implemented in [startgrading](src/startgrading).

### Swap

This takes another student and swaps out a TA's requested student to change.

```sql
ACQUIRE LOCK

SAMPLEDSTUDENTID = (
    SELECT STUDENTIDS LIMIT 1
    FROM HITMEDATABASE
    WHERE STATUS = NOTSTARTED
)

UPDATE HITMEDATABASE
SET STATUS = NOTSTARTED, GRADER = None
WHERE STUDENTIDS = EMAIL

UPDATE HITMEDATABASE
SET STATUS = INPROGRESS, GRADER = TA
WHERE STUDENTIDS = SAMPLEDSTUDENTID

RELEASE LOCK
```

This is implemented in [swap](src/swap).

### Drop

This takes a student assigned to a TA and allows the TA to get rid of them. It's very similar to a portion of `swap`.

```sql
ACQUIRE LOCK

UPDATE HITMEDATABASE
SET STATUS = NOTSTARTED, GRADER = None
WHERE STUDENTIDS = EMAIL

RELEASE LOCK
```

This is implemented in [drop](src/drop).

### View Progress

This has 3 steps:

1.  It breaks down how many submissions have not been started, are in progress, and are done.

    ```sql
    SELECT STATUS, COUNT(STUDENTNAMES)
    FROM HITMEDATABASE
    GROUP BY STATUS
    ```

2.  It breaks down a grader's submissions into in progress and complete. Note, this lists out the submitter emails in each category. This is not a convential SQL operation. Typically, SQL engines provide a way to aggregate groups not just dump the groups (though `pandas` does).

    ```sql
    SELECT STATUS, STUDENTIDS
    FROM HITMEDATABASE
    WHERE GRADER = TA
    ```

3.  It breaks down the in progress and completed submission counts per TA for HitMe "super users" only.

    ```sql
    SELECT COUNT(STUDENTIDS)
    FROM HITMEDATABASE
    GROUP BY GRADER, STATUS
    ```

    This is implemented in [viewprogress](src/viewprogress).

### Total Progress


This is similar to view progress. It tells a TF how much each TA graded over the course of the semester. It can be run at any point in the semester. It is a unique command in that `startgrading` does not have to be run before hand. It solely relies on the appropriate files in `/comp/15`. The following is done for each HitMe database file that has been initialized so far:

```sql
SELECT GRADER, COUNT(STATUS)
FROM HITMEDATABASE
WHERE STATUS = COMPLETE
GROUP BY GRADER
```

Note this is not implemented exactly in this manner using our HitMe database as a groupby plus filter is not possible. See [totalprogress](src/totalprogress) for more details.

It has an additional mode where it can get a breakdown per assignment
for a particular TA in which case the SQL query, for a particular 
assignment, would be: 

```sql
SELECT GRADER, COUNT(STATUS)
FROM HITMEDATABAE
WHERE STATUS = COMPLETE
```

### Admin 

This is a special command for directly manipulating the database via `admin --set`. This has proved useful in the following scenarios: 
* A TA accidentally moves to another student on Gradescope that was assigned to another TA (or no TA)
  - Fix: A super user can run `admin --set` to assign the student to the TA who made the Gradescope mistake 
* Someone forgot to add an extension student when setting up hitme. 
  - Fix: A super user can run `admin --set` to assign the student to themself and hold them there until the extension window expires and the student (with their finished work) can be added into the database. That way, another TA won't accidentally start grading them. 

It also has a mode for seeing who has been assigned to grade a particular student (`admin --get`). 

It also has an `admin --assign` mode for running `hitme` on the behalf of another TA for a certain grading load (number) for TAs who need to be preloaded with grading assignments ahead of time. This is useful for TAs who are behind on grading. 

`admin --set <STUDENTEMAIL> <TAUTLN> <GRADINGSTATUS>` is implemented with: 

```sql
ACQUIRE LOCK

UPDATE HITMEDATABASE
SET GRADER = <TAUTLN>, STATUS = <GRADINGSTATUS>
WHERE STUDENTIDS = <STUDENTEMAIL>

RELEASE LOCK
```

`admin --get <STUDENTEMAIL>` is implemented with: 
```sql
SELECT GRADER, STATUS
FROM HITMEDATABASE
WHERE STUDENTIDS = <STUDENTEMAIL>
```

`admin --assign <TAUTLN> <GRADINGLOAD>` is implemented with

```sql
ACQUIRE LOCK

SAMPLEDSTUDENTIDS = (
    SELECT STUDENTIDS LIMIT <GRADINGLOAD>
    FROM HITMEDATABASE
    WHERE STATUS = NOTSTARTED
)

-- This is more psuedocode than SQL
FOR ID IN SAMPLEDSTUDENTIDS (
  UPDATE HITMEDATABASE
  SET STATUS = INPROGRESS, GRADER = <TAULTN>
  WHERE STUDENTIDS = ID
)

RELEASE LOCK
```

This is implemented in [admin](src/admin).

## Vulnerabilities

This CLI version has similar vulnerabilities as the website version used up to spring 2023. For example, a TA could mark 20 students as done if they wish (including those they did not actually grade). To combat this (unlike the old version) the simple solution, the CLI version logs all write operations to the database in case future investigation is necessary.

A TA could still technically delete the file, if you really didn't trust TAs, you could have all scripts run with elevated privileges (like the setup script) thus locking TAs out from interacting with any hitme files outside of interaction via the hitme commands.

It has the additional vulnerability of `swap` which means they could keep swapping out students they do not want to grade. However, the new student they get is also random.

## Compatability

The spring 2024 version of hitme that uses emails is not compatible with the summer - fall 2023 version of hitme which used Gradescope sids. This should not be noticeable as each semester a new version of `/comp/15` is built off the corresponding `/g/15` mirror.

## Further Development

Our design is made to make it easy to add features in future by abstracting the HitMe system as a simple SQL database. Our database wrapped over `pandas` enables the addition of other operations that can be expressed as simple SQL queries or updates.

Note, commands so far are implemented as Python scripts inside [src](src/) without the `.py` extension and using the appropriate shebang. Furthermore, make sure to add newly added commands to the `HITME_COMMANDS` list in [misc.py](src/misc.py) to make sure the `-h` commands continue to work properly.

## Acknowledgements

- [Chami Lamelas](https://sites.google.com/brandeis.edu/chamilamelas) - primary developer.
- Annika Tanner - implemented `drop`.
- Liam Drew - implemented `totalprogress`.

## HitMe TA Instructions 

### 1 time setup

1. Open `~/.cshrc` in a text editor (e.g. `nano` or `vim`).
2. If you have a setting for `PATH`, make sure it has at least the folders specified below. If you do not have a setting, add the following line at the bottom of `~/.cshrc`.

    ```bash
    setenv PATH ${PATH}:/usr/bin/:/usr/bin/python3:/comp/15/staff-bin/:/comp/15/bin:/comp/15/staff-bin/hitme/src
    ```

### Per Semester Setup

Run `source ~/.cshrc` to get any updates to the hitme commands.

### Per Assignment Setup

Run `startgrading ASSIGNMENTNAME` to set your current hitme assignment to match the Gradescope name.

### Assignment Grading
* Run `hitme` to get assigned a student.
  * This command will give you the student’s email and a link to the submission on gradescope. 
  * Once you get the link, click it and it will take you to their submission. The “Grade” button no longer appears at these links. 
  * To get it to appear, scroll down on the right to the first rubric item after the autograder. Then click it and the grade button will appear on the bottom tool bar. 
  * Click the "Grade" button and then you can begin manual grading.
* Run `swap email` to trade a student back (e.g. if you know them) and get a new random student.
* Run `drop email` to trade a student back (e.g. if you know them). It’s easier just to use `swap`.
* Run `markdone email` to mark a student as done.
* Run `markundone email` to mark a student as back in progress.
* Run `viewprogress` to track your progress. It will show you the student emails.
* Run `getlink email` if you forget a Gradescope link.
* If you run [HITMECOMMAND] -h where [HITMECOMMAND] is any of the above commands, you will see a help message as well as a list of all the other hitme commands.

## HitMe TF Instructions 

### Prerequisites (1 time setup) 

Go through the same `PATH` setup as a regular TA.

Add a public SSH key for your computer to Halligan if you have not done so already. 

### Prerequisites (1 time setup per semester) 

1. Obtain `setup_assignment.sh` and `reset_assignment.sh` from the course repository in `staff-bin/hitme/setup` or an infrastructure TA. If anything about HitMe gets changed, make sure you have the most recent version by checking with an infrastructure TA.
2. Either have an infrastructure TA or yourself modify `config.toml` in the course GitLab repository as follows:
* Set `COURSE_ID` to the Gradescope Course ID (top left of the course Gradescope page).
* Set` EXEMPT_USERS` to a list of Gradescope emails who we don’t want TAs to grade (infrastructure TAs who are submitting solutions, our fake Gradescope account, etc.).
* Set `SUPER_USERS` to a list of the UTLNs of the current TFs and anyone who should be able to:
  * See the more detailed information reported by `viewprogress`.
  * See the information reported by `totalprogress`
  * Use the `admin` command

### Assignment Setup
1. After the 2 token deadline, go to the assignment on Gradescope > Review Grades. Click Export Submissions.
2. Put the downloaded submissions (submissions.zip) into the same folder where you have setup_assignment.sh.
3. Run `bash setup_assignment.sh YOURUTLN ASSIGNMENTNAME [EXTENSION EMAILS…]`. Follow all the prompts. The `ASSIGNMENTNAME` should match what’s on Gradescope for consistency. `[EXTENSION EMAILS…]` is optional as indicated by the [ ] and should be the emails of all the students who have received extensions. 

    a) Note, for students who have received extensions, we don’t want to put them in the hitme database (or backup) yet. This way, TAs won’t be grading people who have not necessarily yet submitted their final work.

    b) Now, at some point we will want to include these students into the database. Once the extension periods have expired, you can rerun setup_assignment.sh again (this time with those extensions removed). Note, you can do this with a redownloaded submissions.zip of all the submissions.

    c) This seems like it would erase grading progress, but it will not. If a student appears in the existing hitme database (from a previous setup run) and in the current setup run, the hitme grading progress will be left untouched as long as the submissions from the two runs are the same. New students in the new run are added as expected.

    d) If the more recent run has a student submission that’s different, it will replace the old submission and the hitme entry for the student will be reset. By reset meaning they are marked as back to “in progress” if they were set as complete. Note, this really shouldn’t be happening. This would only happen if you forgot to include an extension or some other scenario where a student has changed their submission somehow after a TA graded it. The grader is left the same.

    e) Note, you can get the extensions that have been granted for an assignment by going to the assignment on Gradescope and then choosing extensions from the left toolbar. Now, Gradescope is dumb and only shows names in this tab (not emails). Therefore, once you see the names of who got extensions, you have to go to the roster and then get the emails from there.

4. Now run startgrading as a regular TA would.

### Grading
* You can grade as normal as a regular TA. 
* When you run `viewprogress` you will additionally see a per-TA grading breakdown (regular TAs won’t see this). If you do not see this, contact someone on the infrastructure team. If you want to see the progress of a particular TA you can do 
`viewprogress | grep slamel01` for example.
* Note, in `viewprogress`, you see as “in progress” any students who have not been marked complete as anyone. If a student was assigned to Chami and Matt finishes grading them, then it will not appear in Chami’s “in progress” section.
* Finally, you can see all TAs’ progress throughout the entire semester up to this point by running `totalprogress`. You can again see the progress of a particular TA with `totalprogress | grep slamel01` for example. 
* If there’s some confusion where a TA accidentally starts grading another student, or a particular student needs to be given to a particular TA (maybe a TF to hold onto), you can use the admin command. This command allows you to directly update a particular student’s status and grader. For more details, run `admin -h`. Like `totalprogress`, and the special view of `viewprogress`, regular TAs can’t access this command.

### Checking TAs

* The current version has the same vulnerabilities as the website version used up to spring 2023. That is, a TA could mark like 20 students as done if they wish (including those they didn't grade). It has the additional vulnerability of swap which means they could keep swapping out students they don't want. However, the new student they get is also random.
* To combat this (unlike the old version) the simple solution is to log all write operations to the HitMe database. Write operations correspond to any grading status changes or grader reassignments. 

The operations are logged in (easiest to grep this file to look for particular TAs):
`/comp/15/grading/hitme/assignmentname.log.`

Example log entry:
```
2024-02-09 04:28:52 PM : slamel01 running markdone : set Grader to slamel01, Status to Complete where Student Ids is john.smith@tufts.edu
```

### Miscellaneous Notes
* The `setup_assignment.sh` script can be used to backup labs and phase 1s submitted on Gradescope as well (which aren't manually graded). The only difference is that we would just ignore the hitme database initialized for them as grades can be collected automatically from Gradescope. 
* The `reset_assignment.sh` script (found in the same place as `setup_assignment.sh`) can be used to wipe a backup and hitme database if this is really needed.

## Changelog

### 9/20/2024 
- Update `setup.c` to better report errors with `execvp` and update call to `malloc` for better stability. 

### 5/10/2024
- Made it so `viewprogress` and `totalprogress` will always show all the TAs. This is done by providing `hitme` with a roster file. The roster file can be provided in a variety of formats (CSV, Excel, text).

### 4/19/2024
- Cleaned up help description for 0 argument commands (e.g. `hitme`, `viewprogress`)
- Cleaned up tabular printing in `viewprogress`, `totalprogress`. 
- Added option to show the completed counts per assignment for a TA with `totalprogress UTLN`. 

### 4/18/2024
- Update vulnerabilities 

### 4/11/2024
- Made `dirs_differ` to do sorted comparisons of folder contents.

### 4/5/2024
- Added `admin --assign` command for assigining a batch of assignments to a grader.
- Updated `setup.sh` based on fix from EECS staff (caused an import bug)

### 3/11/2024

- Patched bugs with TA permissions enforcement on `admin`, `reset`, and `setup.py`. In particular, previously exceptions would be raised and dump to console, now like in other scripts exceptions are caught and printed.
- Add SSH authentication failure handling to `setup_assignment.py` and `reset_assignment.py`. 

### 3/10/2024

- Modified setup process:
  - Setup process (via `setup.py`) is restricted to super users only.
  - `setup_assignment.sh` is replaced with `setup_assignment.py`. This was done to account for the possibility of a TF who is setting up hitme who uses Windows. Previously, with a `bash` setup script, only Unix-based users (i.e. OSX and Linux) could use this script. Now, it is done in Python which both Windows and Unix users are assumed to have. The only prerequisite now is to install the provided required SSH/SFTP library `paramiko`. 
- Modified reset process: 
  - hitme log is no longer deleted by `reset` or when setup is run twice. That is, those operations are added to the same log. If a log becames unwieldingly large, it must be deleted manually. 
  - Reset process (via `reset`) is restricted to super users only. 
  - `reset_assignment.sh` is replaced with `reset_assignment.py`. This was done for the same reason as for the setup process described above. Furthermore, user input reset confirmation is moved from remote (`reset`) to local (`reset_assignment.py`).
- Made `HitMeWriteLogger` as a top level class in `hitme.py`.
- Further expanded on [this patch](#2292024). In particular, `viewprogress` will break complete count ties on in progress count first before falling back to UTLN. See [viewprogress](src/viewprogress) for more details.

### 3/9/2024

- Made hitme setup process case insensitive for both emails and UTLNs. Student emails are lowercased when initializing the database, but now we also lowercase all user configuration information (emails in exempt users, UTLNs in super users). This enables case insensitive lookups without relying on people specifying configuration with the correct casing. 

### 3/8/2024

- Reverted the index component of the previous patch. This is because a pandas index is not like a SQL index in that it cannot be treated like any other column in terms of selections, updates, etc. Pandas requires special syntax for all operations surrounding an index that overall complicates the implementation more so than benefitting efficiency. It speeds up pandas ops by 2x, but the large amount of time involved with running hitme commands is the time it takes to boot the python interpreter and do the imports (~1s). Pandas ops are < 0.01 s with and without the index. 

### 2/29/2024

- Updated hitme setup process by establishing the student ID as the primary key by making it a sorted index. This will speed up queries (read and write) on that ID (e.g. `getlink` and `markdone`)
- Updated `HitMeDatabase:groupby( )` to no longer automatically sort (this is default behavior of pandas). Not sorting improves performance.
- Updated `viewprogress` and `totalprogress` to now list results in increasing order of submissions completed. 
  - This was done upon request of current staff, it's easier to identify lagging TAs etc. 
  - The alphabetical sorting by UTLN was done to make it easier to scan for individual TAs but we can just pipe into `grep` (e.g. `viewprogress | grep slamel01`)

### 2/14/2024
- Small improvements to `viewprogress`
  - Patch display bug introduced from previous update
  - Display emails of students shown to TAs that they have completed or in progress in sorted order
  - Display in progress and complete counts on same name as TA UTLN for TFs so that one could do `viewprogress | grep slamel01`
- Small improvement to `misc.py` in how we capture screen width

### 2/13/2024
- Have `viewprogress` display total submission count before status breakdown at the top
  - Added this because it's nice to check when running the database setup to make sure submission count matches with Gradescope (in the past, you'd have to sum the status counts, so we just have the code replace our mental math).

### 2/12/2024
- Improved `admin` help message
- Added `admin` to this file's documentation

### 2/9/2024
- Improved logging (more details, nicer log messages)

### 2/4/2024
- Patched a bug where a user could create a lock file with their ownership unknowingly. 
  - In particular, what would happen is, suppose a user runs `hitme` without running `startgrading` at the beginning of a new semester. They would default to trying to `hitme` a student from the last assignment of the previous semester, which doesn't exist as a HitMe database file. I discovered this occurred by noticing (after `hw_arraylists` grading began in spring 2024) that there were a couple lock files in `/comp/15/grading/hitme` that had names from final assignments from last semester.
  - What happened was, in the `HitMeDatabase` constructor, it would instantiate a `FileLock` without checking if the lock file existed. In the setup process, a lock file should be getting created under `cs15acc` ownership. However, if we instantiated a `HitMeDatabase` for an assignment that didn't exist (as in the above scenario) it would make the lock file before checking that the assignment didn't exist.
  - The fix is to move `FileLock` creation to `acquire_writelock`. In particular, if a lock file doesn't exist when we run regular hitme operations (`hitme`, `drop`, etc.) this causes an error. That way, a user won't accidentally create one when running these operations on some old assignment previously set by `startgrading`. 
  - This is the default behavior for `acquire_writelock`, but we can override it to create the file if we want. We do this only when it is invoked in `setup.py` where the file will be created by `cs15acc` as intended as part of the setup process run via the SUID bit.
- Patched a bug in how the export folder was identified.
  - Before the setup process change on 1/31 (see below) we only ran setup once. In that case, the export folder was the one and only folder in the folder where we extract into. Therefore, we identified its path by just getting the one and only subfolder with `os.listdir( OUTPUTFOLDER )[0]`.
  - However, when existing solutions exist in the output folder, which is the backup folder, when we run multiple times, we have to specifically identify the assignment export folder. `os.listdir( )` provides no guarantees on ordering (based on name, time created, etc.)
  - The fix is, we identify the export folder as the folder starting with "assignment_" and ending with "_export". We did this already to identify the assignment ID.

### 2/2/2024

- Various setup bug fixes 

### 2/1/2024

- Added an `admin` command.
  - `admin --get ID` gives you the grader and status for a student with provided ID (email).
  - `admin --set ID GRADER STATUS` which sets the grader and status for a student.
  - Only super users can run this command. This gives you a way to manually modify the database values modified via the other hitme commands (besides setup).
  - This is just a safety net, an override if something goes wrong with other commands or if a TA doesn't have access to `/comp/15` and can't run hitme. Another TA (who's a super user) could run it for them.

### 1/31/2024

- Modified setup process to account for extensions.
  - When you run `setup_assignment.sh`, you can now supply IDs (emails) of
    students who have been granted extensions. These students, like the `exempt_users` (recall these are staff members, test accounts..) will
    be exempt from being added to the hitme database and the backup. \* _Why?_ If these students have submitted by the time `setup_assignment.sh` is run, then TAs may start accidentally grading an old submission (not the student's final work). This way, we don't put them in.
  - Now, how do we eventually add those extensions' submissions into the database and backup? `setup_assignment.sh` can now be run multiple times.
    - On the first run (say after the 2 token deadline), given the submissions archive from gradescope, will add all the submissions into the database.
    - If you were to run a second time (or any time after the first on the same assignment), given the submissions from gradescope, will:
      - Add submissions from any new students. Say for example any students previously marked as having an extension. By this we mean, a new entry is added into the database (where grading hasn't begun) and a new folder is added into the backup.
      - For any student who was already in the database, if the submission in the most recent gradescope archive is different than the previous one in the backup, the more recent submission overwrites the backup and resets the grading progress back to in progress (but with the same TA) if they were marked complete in the database. Now, this should not happen frequently. This is highlighted in the setup process.
      - If the submission did not change between the two for a student, their grading progress is left untouched. This allows multiple runs to not affect TAs' grading as desired. The only time its changed is if there's a duplicate submission.
  - Added a new script `setup/reset_assignment.sh` that can be invokved to wipe the hitme database and backup for an assignment if a user truly wants to reset it. This used to be done automatically when the old `setup/setup_assignment.sh` was run multiple times.
- Moved Gradescope course ID out of `[hitme]` portion of `config.toml` into recently created `[gradescope]` section.
- The assignment ID is no longer saved as part of the backup. This can
  be found on Gradescope, and used to be pickled anyway.

### 1/18/2024

- Updated help descriptions for all commands
- Since Outlook emails are case-insensitive, enabled case-insensitive email comparison when it comes to commands that take emails (e.g. `drop`, `markdone`, etc.). Therefore, instead of email being our primary key (see below), it's lowercase email.
- An explicit check is added to ensure that the lowercase email (or whatever is chosen as the student ID) is a primary key when constructing the hitme database in the setup process (see `setup.py`).

### 1/9/2024

- Swapped to use email instead of SID on Gradescope.
  - When this was initially built, it was assumed the Gradescope SID was set to students' UTLNs. However, this is not the case if the Gradescope page is not linked with a Canvas page where UTLNs are preloaded.
  - Hence, Gradescope would set SIDs seemingly random, yet unique, numerical IDs which worked but was not the most user friendly.
  - To provide user friendliness, uniqueness, and consistency with the [course autograder](https://gitlab.cs.tufts.edu/mrussell/gradescope-autograder), hitme and the autograder have both been swapped to using students' emails.
- Added help functionality to all commands as well as a `hitmehelp` command.
- Added a new `totalprogress` command which allows TFs to see TAs' progress over an entire semester.

### 10/20/2023

- Added `drop` functionality.

### 9/29/2023

- Fixed bug with permissions.

### 9/22/2023

- Fixed bug where if someone ran `startgrading NONEXISTENTASSIGNMENT` followed by `hitme`, it would create a `.LCK` file with that name. This file became undeletable (except by user who ran it). Now, you can only `startgrading` on hitme databases that already exist on file.
- Changed whenever `setup.py` is run (via `setup_assignment.sh`), the `hitme/` and `backup/` `grading/` subfolders are not permissions modded. This is only done if the directories
  don not already exist.

### 9/13/2023

- Condensed `ASSIGNEDGRADER` and `COMPLETEDGRADER` into `GRADER`.
- Fixed bug with initial `viewprogress`.

### 8/28/2023

- Allowed for `groupby` to return multiple columns.
- Various bug fixes.

### 8/23/2023

- Submissions for exempt users are no longer backed up.
- Various bug fixes.

### 8/19/2023

- Get first non-beta version up and running on homework server.
- Add documentation.
