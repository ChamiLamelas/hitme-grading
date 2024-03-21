"""
Loads up grading backup and hitme database for an assignment.

This is called remotely by setup_assignment via setup.

Chami Lamelas
Summer 2023 - Spring 2024
"""

import misc
from hitme import (
    HitMeColumn,
    HitMeStatus,
    HitMeDatabase,
    HitMeException,
    GRADING_FOLDER,
    HITME_DATABASE_FOLDER,
    set_hitme_permissions,
)
import shutil
import os
import zipfile
import hitmeconfig as hmc
import sys
import getpass 

# Path to backup folder (for all assignments)
BACKUP_FOLDER = os.path.join(GRADING_FOLDER, "backup")

# Gradescope zip name - subject to change if Gradescope changes
# their website
SUBMISSIONS_FILE = "submissions.zip"

# Known prefix, suffix of folder that's zipped into submissions zip
# Like above, subject to Gradescope changing their website
PREFIX = "assignment_"
SUFFIX = "_export"


def get_backup_folder(assignment):
    """Gets the path to the backup folder for an assignment"""

    return os.path.join(BACKUP_FOLDER, assignment)


def _check_make_and_mod(*folders):
    """If a folder doesn't exist, makes it with hitme permissions"""

    for folder in folders:
        if not os.path.isdir(folder):
            os.mkdir(folder)
            set_hitme_permissions(folder)


def _make_grading_folders():
    """Makes the grading/ subfolders related to hitme if they haven't been made yet"""

    if not os.path.isdir(GRADING_FOLDER):
        raise HitMeException(
            f"{GRADING_FOLDER} does not exist -- this should have been created by the pipeline"
        )
    _check_make_and_mod(BACKUP_FOLDER, HITME_DATABASE_FOLDER)


def _get_names_and_ids(submitters):
    """Get list of names, IDs from submitters data of a submission"""

    names = list()
    ids = list()
    for submitter in submitters:
        names.append(submitter[":name"])

        # Lowercase email in database because we will lowercase any email input
        # by users in drop, markdone, etc. so that way we can do case-insensitive
        # email comparison
        ids.append(submitter[":email"].lower())
    return names, ids


def _get_key(ids):
    """
    Gets key representation (for our database) given a list of IDs

    Use this for any interaction with the database: adding a student,
    querying for a student, etc.

    ids is an iterable (list) to account for group assignments,
    usually just a singleton list
    """

    return ",".join(ids)


def _get_folder(ids):
    """
    Gets folder name given a list of IDs

    Use this for any interaction with creating a folder related
    to some students (e.g. for backup)

    ids is an iterable (list) to account for group assignments,
    usually just a singleton list
    """

    return "_".join(ids)


class HitMeSetup:
    """
    Class that is really a function, made a class for cleaner code. When
    an instance is initialized, the hitme database is initialized and a
    backup is performed for a particular assignment.

    Attributes:

        I list all the attributes here because they are not all
        initialized directly in __init__. Many are initialized
        and used across a variety of helper methods.

        assignment: str
            The assignment being setup (Gradescope name)

        extensions: set[str]
            Set of IDs (emails) of students granted extensions

        db: HitMeDatabase
            Internal database that we will be setting up/updating

        output_folder: str
            Path to where the backup will go to

        export_folder: str
            Path to where Gradescope submissinos are unzipped into

        assignment_id: str
            Gradescope assignment ID for the assignment

        num_submitters: int
            Number of people who submitted to the assignment (includes
                exempted users)

        submissions_modified: list[str]
            List of keys of those submissions that were modified

        new_rows: list[dict[HitMeColumn, Any]]
            New rows to add into our database specified as dictionaries
                of our attributes -- see HitMeDatabase::update( )

        exempted: list[str]
            List of keys (combined ids, emails) of those students who are
                exempted (by being a provided extension, exempt user)
    """

    def __init__(self, assignment, extensions):
        self.assignment = assignment
        self.extensions = set(extensions)
        try:
            # We will be interacting with database and modifying
            # it, potentially, on a rerun of setup.py we could
            # be doing this at the same time as a TA doing a
            # write operation - so we need the lock before
            # doing any edits
            self.db = HitMeDatabase(self.assignment, os.path.basename(__file__))

            # Here we make a lock file if it doesn't exist -- it
            # won't exist the first time this is run, so we make it
            # with cs15acc ownership
            self.db.acquire_writelock(make_lock_file=True)

            # Attempts to load from existing file
            self.db.load()
            if self.db.is_loaded():
                self._display_loaded_message()

            # Here we modify what was loaded (or initialize
            # the database from scratch)
            self._get_new_rows()
            self._update_disk()
        except HitMeException as e:
            misc.red(str(e))
        finally:
            if self.db is not None:
                self.db.release_writelock()

    def _update_disk(self):
        """
        Updates the HitMe backup on disk after the setup process. In addition,
        it provides output to the user on the result of the setup.

        This includes:
            - Removing the zip export folder
            - Reports which submissions were exempted (from EXEMPT_USERS, extensions)
            - Updates the database with new rows
            - Reports which submissions were added or modified (if this is a second
                or later setup) or how many submissions were added (if this is a
                first time setup)
            - Updates the permissions on the created backup folders, hitme database
                files.
        """

        # Delete export (deleting the zip is handled by setup_assignment.sh)
        shutil.rmtree(self.export_folder)

        # If we added no new rows and we modified no rows, say nothing happened
        if len(self.new_rows) == 0 and len(self.submissions_modified) == 0:
            misc.blue(f"HitMe database for {self.assignment} not modified.")
            return

        # Report who was exempted
        if len(self.exempted) > 0:
            misc.blue(
                f"Exempted {len(self.exempted)} submissions:\n"
                + "\n".join(map(lambda e: "\t" + e, self.exempted))
            )

        # If we are updating an already loaded database, we update it
        # by adding the new rows
        if self.db.is_loaded():
            change = "updated"
            self.db.update(self.new_rows)

            # Report the new rows that were added -- note when we add new rows
            # to an existing database, we expect there to not be too many
            # new rows as they correspond to extensions, so we give
            # details on each extension
            if len(self.new_rows) > 0:
                misc.blue(
                    f"Added {len(self.new_rows)} submissions (out of {self.num_submitters} new submissions)"
                )
                misc.blue(
                    "\n".join(
                        "\t" + row[HitMeColumn.STUDENT_IDS] for row in self.new_rows
                    )
                )

            # Report the modified submissions - we put it in yellow because
            # this should be something user should take seriously and we
            # give details on students
            if len(self.submissions_modified) > 0:
                misc.yellow(
                    f"Modified {len(self.submissions_modified)} submissions (out of {self.num_submitters} new submissions)"
                )
                misc.yellow(
                    "\n".join(map(lambda e: "\t" + e, self.submissions_modified))
                )
        else:
            # Initialize the database now with the new rows -- here we don't
            # dump all the new rows used to initialize the database because
            # we expect there to be a lot
            change = "initialized"
            self.db.load(self.new_rows)
            misc.blue(f"Added {len(self.new_rows)}/{self.num_submitters} submissions")

        # Afterwards, make sure that the backup folder has the right permissions
        # both when new submissions are added upon initialization or we replace
        # submissions via modification (the database files have their perms set
        # properly by HitMeDatabase)
        set_hitme_permissions(self.output_folder)
        misc.green(f"HitMe database has been {change} for {self.assignment}.")

    def _get_new_rows(self):
        """
        Get new rows for the database from the current submission set

        New rows are:
        - New students in this submission set
        - Students whose submissions have changed
        """

        self._unzip_gs_submissions()
        submission_metadata = misc.read_yaml(
            os.path.join(self.export_folder, "submission_metadata.yml")
        )

        self.num_submitters = len(submission_metadata)
        self.submissions_modified = list()
        self.new_rows = list()
        self.exempted = list()

        for submission, submission_info in submission_metadata.items():
            submission_id = submission[len("submission_") :]
            names, ids = _get_names_and_ids(submission_info[":submitters"])

            # Check if this is an exempt student
            if not self._should_keep(ids):
                self.exempted.append(_get_key(ids))
                continue

            # If we are initializing the database, or the student
            # does not exist in the database, copy over the submission
            # into the backup and add a new row to the database
            if (
                not self.db.is_loaded()
                or len(
                    self.db.get(
                        HitMeColumn.STUDENT_IDS, _get_key(ids), HitMeColumn.STUDENT_IDS
                    )
                )
                == 0
            ):
                self._move_folder(submission, ids)
                self.new_rows.append(self._make_row(names, ids, submission_id))
                continue

            # If we are modifying the database and the submission changed,
            # modify the row (else: submission didn't change, do nothing)
            if self._submission_changed(submission, ids):
                self._reset_row(ids, submission_id)
                self._move_folder(submission, ids)

    def _reset_row(self, ids, submission_id):
        """
        Resets the row for a student. That is, it modifies a row in the
        existing database to be the initial setup:
        - The gradescope URL provided in the most recent setup run
        - The status is in progress if it was complete, otherwise it's
            left as is
        """

        self.submissions_modified.append(_get_key(ids))
        status = self.db.get(
            HitMeColumn.STUDENT_IDS, _get_key(ids), HitMeColumn.STATUS
        )[0]
        if status == HitMeStatus.COMPLETE:
            status = HitMeStatus.IN_PROGRESS
        self.db.set(
            HitMeColumn.STUDENT_IDS,
            _get_key(ids),
            [HitMeColumn.GRADESCOPE_URL, HitMeColumn.STATUS],
            [self._get_gs_url(submission_id), status],
        )

    def _submission_changed(self, submission, ids):
        """
        Checks if a student's submission has changed from the current
        export with what was previously stored -- note this does
        not check that there was a previous submission, it is assumed
        upon function call
        """

        return misc.dirs_differ(
            os.path.join(self.export_folder, submission),
            os.path.join(self.output_folder, _get_folder(ids)),
        )

    def _move_folder(self, submission, ids):
        """
        Move submission folder's contents from Gradescope export into
        an appropriately named folder in the hitme backup. If a folder
        with that name already exists, it is deleted so that the 'mv'
        can work properly
        """

        dst = os.path.join(self.output_folder, _get_folder(ids))
        if os.path.isdir(dst):
            shutil.rmtree(dst)
        shutil.move(os.path.join(self.export_folder, submission), dst)

    def _find_export_folder(self):
        """
        Identifies the Gradescope export folder in the output folder
        and identifies the assignment ID.

        It does so by finding the subfolder that starts with assignment_
        and ends with _export. The string between the two is the
        assignment ID.

        An error is raised if this is not possible.
        """

        for subfoldername in os.listdir(self.output_folder):

            # Find subfolder that matches (assumes there's only one)
            if subfoldername.startswith(PREFIX) and subfoldername.endswith(SUFFIX):

                # Construct export folder path, parses assignment ID
                self.export_folder = os.path.join(self.output_folder, subfoldername)
                self.assignment_id = subfoldername[len(PREFIX) : -len(SUFFIX)]
                return

        raise HitMeException(
            f"Could not identify Gradescope export folder in {self.output_folder}"
        )

    def _unzip_gs_submissions(self):
        """
        Extract GS submissions into a single folder:
        BACKUP_FOLDER/ASSIGNMENTNAME/assignment_GSID_export

        It identifies said folder and the assignment ID using
        _find_export_folder
        """

        self.output_folder = get_backup_folder(self.assignment)
        submissions_path = os.path.join(GRADING_FOLDER, SUBMISSIONS_FILE)
        with zipfile.ZipFile(submissions_path, "r") as zip_file:
            zip_file.extractall(self.output_folder)
        self._find_export_folder()

    def _display_loaded_message(self):
        """Display a message informing if we're editing an existing database"""

        misc.blue(
            f"A HitMe database has already been initialized for {self.assignment}. Its contents may be updated in this setup run. If you would like to delete the previous database, download and run reset_assignment.py."
        )

    def _should_keep(self, ids):
        """
        If any of the submitters are exempt, we skip them in adding them
        to hitme database or backing them up. Thus, we keep submissions
        where all the IDs are not exempt users.

        Here we consider extensions and exempt users
        """

        return (
            len(hmc.get_exempt_users().intersection(ids)) == 0
            and len(self.extensions.intersection(ids)) == 0
        )

    def _get_gs_url(self, submission_id):
        """
        Gets a Gradescope submission URL given a submission using the
        course and assignment this setup pertains to
        """

        return f"https://www.gradescope.com/courses/{hmc.get_course_id()}/assignments/{self.assignment_id}/submissions/{submission_id}#"

    def _make_row(self, names, ids, submission_id):
        """
        Makes a Database row as a JSON-like dict:

        {
            STUDENTNAMES: comma separated list of names
            STUDENTIDS: comma separated list of ids
            GRADESCOPEURL: gradescope template subsituted with course, assignment,
                and submission IDs
            GRADER: None
            STATUS: NOTSTARTED
        }
        """

        return {
            HitMeColumn.STUDENT_NAMES: ",".join(names),
            HitMeColumn.STUDENT_IDS: _get_key(ids),
            HitMeColumn.GRADESCOPE_URL: self._get_gs_url(submission_id),
            HitMeColumn.GRADER: None,
            HitMeColumn.STATUS: HitMeStatus.NOT_STARTED,
        }


def main():
    # Abort immediately if TA not authorized 
    try:
        hmc.check_user_is_super_user()
    except HitMeException as e:
        misc.red(str(e))
        return 
    
    _make_grading_folders()
    HitMeSetup(sys.argv[1], sys.argv[2:])


if __name__ == "__main__":
    main()
