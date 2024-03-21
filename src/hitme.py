"""
This provides the backbone for the CLI implementation of HitMe (including
the implementation of the database).

For more information - view staff-bin/hitme/README.md.

Chami Lamelas
Summer 2023 - Spring 2024
"""

from enum import Enum
import os
from filelock import FileLock
from datetime import datetime
import pandas as pd
import getpass
import stat
import random

COURSE_FOLDER = "/comp/15"

# Paths to backup, hitme folders
GRADING_FOLDER = os.path.join(COURSE_FOLDER, "grading")
HITME_DATABASE_FOLDER = os.path.join(GRADING_FOLDER, "hitme")


def _set_file_permissions(filepath):
    """
    Sets HitMe appropriate permissions on a file or directory path.

    Note: this is not recursive (see set_hitme_permissions).

    These are:
        User (cs15acc) read write and execute
        Group (ta15) read write and execute (for directories, not for files)

    Execute is necessary for directories in order to cd into them
    """

    filemask = stat.S_IRWXU | stat.S_IRGRP | stat.S_IWGRP
    if os.path.isdir(filepath):
        os.chmod(filepath, filemask | stat.S_IXGRP)
    elif os.path.isfile(filepath):
        os.chmod(filepath, filemask)


def set_hitme_permissions(path):
    """
    Recursively applies _set_file_permissions to each file
    and directory inside path.
    """

    _set_file_permissions(path)
    for root, files, dirs in os.walk(path):
        for f in files:
            _set_file_permissions(os.path.join(root, f))
        for d in dirs:
            _set_file_permissions(os.path.join(root, d))


def get_db_path(assignment):
    """Gets full path to database file for an assignment"""

    return os.path.join(HITME_DATABASE_FOLDER, assignment + ".db.pkl")


def get_lock_path(assignment):
    """Gets full path to database lock file for an assignment"""

    return os.path.join(HITME_DATABASE_FOLDER, "." + assignment + ".db.LCK")


def get_log_path(assignment):
    """Gets full path to database write log file for an assignment"""

    return os.path.join(HITME_DATABASE_FOLDER, assignment + ".log")


def check_db_initialized(assignment):
    """Checks that a HitMeDatabase has been initialized on file"""

    if not os.path.isfile(get_db_path(assignment)):
        raise HitMeException(
            f"HitMe database has not been initialized for {assignment}"
        )


class HitMeException(Exception):
    """
    Our program expects only this exception type to be thrown. All
    other exceptions are unexpected and dump the traceback.
    """

    pass


def hitmeassert(condition, message):
    """Equivalent to assert except raises HitMeException on failure"""

    if not condition:
        raise HitMeException(message)


class HitMeColumn(Enum):
    """
    Standard of how columns in HitMe Database will be referred to,
    better than just random strings which could have typos.

    It is assumed STUDENT_IDS is a primary key.
    """

    STUDENT_NAMES = 1
    STUDENT_IDS = 2
    GRADER = 3
    GRADESCOPE_URL = 4
    STATUS = 5

    def __repr__(self):
        return self.name.replace("_", " ").title()

    def __str__(self):
        return self.__repr__()


class HitMeStatus(Enum):
    """
    Represents grading status of a student. When represented as
    a string we have it look nice (e.g. HitMeStatus.IN_PROGRESS
    is "In Progress")

    Note, as these statuses are used as keys of a dictionary,
    HitMeStatus needs to be hashable (providing implementations
    of __lt__, __eq__, and __hash__).
    """

    IN_PROGRESS = 1
    NOT_STARTED = 2
    COMPLETE = 3

    def __repr__(self):
        return self.name.replace("_", " ").title()

    def __str__(self):
        return self.__repr__()

    def __lt__(self, other):
        return self.value < other.value

    def __eq__(self, other):
        return self.value == other.value

    def __hash__(self):
        return self.value


class HitMeWriteLogger:
    """
    This class is a logger used by HitMeDatabase to log all
    write (modification) operations to a file. This provides
    log operations corresponding to the 2 write operations
    listed above as well as when initializing the database.

    Log file is HITME_DATABASE_FOLDER/assignment.log.
    """

    def __init__(self, assignment, script):
        self.assignment = assignment
        self.script = script

    def _log_message(self, message):
        """Helper function that logs a message with user and timestamp"""

        # Prefix message with datetime and user
        log_message = (
            f"{datetime.now().strftime('%Y-%m-%d %I:%M:%S %p')} : {getpass.getuser()}"
        )

        # Add script name if one was provided to wrapping database
        if self.script is not None:
            log_message += f" running {self.script}"

        # Add message and write - always append to file
        log_message += f" : {message}\n"
        with open(get_log_path(self.assignment), "a+") as f:
            f.write(log_message)

    def log_init(self):
        """Logs the initialization of a database, setting log file perms if it doesn't exist"""

        self._log_message("initialized database")
        set_hitme_permissions(get_log_path(self.assignment))

    def log_reset(self):
        """Logs the resetting of a database"""

        self._log_message("reset database")

    def log_set(self, where_col, where_key, update_cols, update_values):
        """
        Logs information about a HitMeDatabase::set( ) operation.

        Parameters:
            where_col: str
                Column to check for match

            where_key: Any
                Rows where row[where_col] = where_key will be updated

            update_cols: str or list[str]
                row[update_cols] will be updated for matching rows

            update_values: Any or list[Any]
                row[update_cols] will be updated to update_values for matching rows
        """

        settings = ", ".join(
            f"{uc} to {uv}" for uc, uv in zip(update_cols, update_values)
        )
        self._log_message(f"set {settings} where {where_col} is {where_key}")

    def log_update(self, *rows):
        """
        Logs information about an HitMeDatabase::update( ) operation.

        Parameters:
            rows: list[dict[HitMeColumn, Any]]
                Rows to add to the database formatted in the same
                    manner as HitMeDatabase::update( ).
        """

        for row in rows:
            settings = ", ".join(f"{k} = {v}" for k, v in row.items())
            self._log_message(f"added new row with {settings}")


class HitMeDatabase:
    """
    This provides an abstraction of the HitMe database. Through
    this class, one can read and write information to the database.
    This can be thought of as a simplified version of SQL that
    only provides the necessary operations needed to implement
    the behavior of our program. The database is stored on file
    and operated on in memory.

    The database supports two types of operations:
        1) Reads - retrieves some information
            from the database.
        3) Writes - has the database update some information.
            These operations must be protected by a lock.
            The database provides the functionality to
            acquire and release a lock as normal.

    Read operations:
        get
        groupby

    Write operations:
        load
        set

    These operations are described in more detail below.
    """

    def __init__(self, assignment, script=None):
        """
        This does not initialize the database on file or load it into
        memory. It simply stores the assignment we will be operating on
        as well as the logger and lock we will use.

        It can also set the name of the script in the internal logger. The
        script name is the name of the script that's currently using a
        HitMeDatabase. This is not required, but is useful for when the
        database will involve write operations to know which script was
        invoked to trigger them.
        """

        self.assignment = assignment
        self.logger = HitMeWriteLogger(assignment, script)
        self.lock = None
        self.db = None
        self.has_lock = False

    def _check_loaded(self):
        """
        Enforces that the in memory database has loaded from file

        That is, load( ) has been called once with a DataFrame
        (via setup( )) or from a file (via a previous db pkl file).
        """

        if not self.is_loaded():
            raise HitMeException(
                f"HitMe database has not been loaded for {self.assignment}"
            )

    def _check_locked(self):
        """Checks that an in memory database has the write lock"""

        if not self.has_lock:
            raise HitMeException(
                f"HitMe database instance must have lock before write operations."
            )

    def is_loaded(self):
        """
        Returns whether that the in memory database has loaded from file

        That is, load( ) has been called once with a DataFrame
        (via setup( )) or from a file (via a previous db pkl file).
        """

        return self.db is not None

    def load(self, data=None):
        """
        This loads the file database into memory from what's on disk or can
        initialize the database on disk.

        Parameters:
            data: pandas.DataFrame or None
                If data is None, we just try to load what's on file for
                this assignment's database into memory. If data is not None
                we initialize the database from the provided data and
                overwrite what's on file. The log is reset in this case as
                well.

        Notes:
        * Anytime we initialize a HitMeDatabase, we run this function to
            actually load the database.
        * Running this will increase the freshness of the in memory
            database. However, if this is done outside of a critical
            section, it could become stale.
        * When doing write operations, it is recommended to load( )
            after acquiring the write lock. That way, you are ensuring
            the database that you have in memory will not become stale
            (as noone else can write to the in file database as you
            have the lock).
        """

        db_path = get_db_path(self.assignment)
        if data is not None:
            self._check_locked()
            self.db = pd.DataFrame(data)
            self.db.to_pickle(db_path)
            set_hitme_permissions(db_path)
            set_hitme_permissions(get_lock_path(self.assignment))
            self.logger.log_init()
            self.logger.log_update(*data)
        elif os.path.isfile(db_path):
            self.db = pd.read_pickle(db_path)

    def acquire_writelock(self, make_lock_file=False):
        """
        Tries to acquire the lock for writing to the database. This is
        necessary before any write operation.

        Parameters:
            make_lock_file: bool (default: False)
                By default, this function will not make the lock file
                if it does not exist. However, we can specify with
                make_lock_file = True to make the lock file if one
                does not exist. This is useful when setting up a
                database. There, we want to create a lock file
                in the name of the setup account (cs15acc). However,
                in other operations (e.g. hitme) we don't want to create
                a lock file when doesn't exit when we try to acquire the
                lock. In those situations, random TAs could be creating
                lock files in their name.
        """

        if self.lock is None:
            lock_path = get_lock_path(self.assignment)

            # If we shouldn't make the lock file and it doesn't exist,
            # we expect it to exist -- so we raise an error
            if not make_lock_file and not os.path.isfile(lock_path):
                raise HitMeException(
                    f"Lock file does not exist for assignment {self.assignment}"
                )

            # Either we should be making this file, or it already exists
            # so we make the file lock and continue forward to acquire it
            self.lock = FileLock(lock_path)
        self.lock.acquire()
        self.has_lock = True

    def release_writelock(self):
        """
        Releases the lock for writing to the database. Do this after
        any write operation. It is recommended to do this in a
        try-finally approach:

        try:
            db.acquire_writelock()
            db.load()
            db.set_status(student, HitMeStatus.COMPLETE)
        finally:
            db.release_writelock()

        That way, the lock is always released.
        """

        # Only release the lock if we have it, otherwise do nothing
        if self.has_lock:
            self.lock.release()
            self.has_lock = False

    def get(self, where_col, where_key, attribute, limit=None, empty_error=None):
        """
        Performs a read operation similar to a simple SQL SELECT on the database.

        Examples:
            1.  get("A", 1, "B") is equivalent to:

                SELECT B
                FROM (THE DATABASE)
                WHERE A = 1

            2.  get("A", 1, ["A", "B"]) is equivalent to:

                SELECT A, B
                FROM (THE DATABASE)
                WHERE A = 1

        Parameters:
            where_col: HitMeColumn
                Column to check for match

            where_key: Any
                Rows where row[where_col] = where_key will be updated

            attribute: HitMeColumn or list[HitMeColumn]
                row[attribute] is returned for each matching row

            limit: int or None
                Positive integer or None. Only limit results will
                be returned if limit is a positive integer. The
                selected limit results will be random. If limit is
                greater than the number of queried results, then
                all of the queried results are returned.

            empty_error: str or None
                If the query yields an empty result, [ ] is returned if
                empty_error is None, otherwise a HitMeException with
                empty_error as the message is raised

        Returns:
            list[Any]:
                If the query has only a single column in the response (e.g.
                a list[HitMeColumn]).

            list[dict[HitMeColumn, Any]]:
                If the query has multiple columns, the response is in a JSON
                like format. A list of dictionaries of columns to values is
                returned (e.g. [{ "A": 1, "B": 2 }, { "A": 1, "B": 3 }]).
        """

        hitmeassert(
            isinstance(where_col, HitMeColumn), f"{where_col} must be HitMeColumn"
        )
        hitmeassert(
            limit is None or limit > 0, f"{limit} must be a positive integer or None."
        )

        self._check_loaded()

        # Get DataFrame matching query
        cols = self.db.loc[self.db[where_col] == where_key]

        if len(cols) == 0:
            if empty_error is not None:
                raise HitMeException(empty_error)
            return list()

        if isinstance(attribute, HitMeColumn):
            # We requested just a single column, so we build a list of
            # values (not single value dicts)
            select_list = cols[attribute].tolist()
        else:
            # Convert DataFrame into JSON like dict format (return cases 2,4)
            # If response had a single column, convert a dict shaped like:
            # [{"A": 1}, {"A": 2}] -> [1,2]
            select_list = cols[attribute].to_dict("records")

        return (
            select_list
            if limit is None or limit > len(select_list)
            else random.sample(select_list, k=limit)
        )

    def set(self, where_col, where_key, update_cols, update_values, empty_error=None):
        """
        Performs a write operation similar to a simple SQL UPDATE on the database.

        Examples:
            1.  set("A", 1, "B", 2) is equivalent to:

                UPDATE (THE DATABASE)
                SET B = 2
                WHERE A = 1

            2.  set("A", 1, ["B", "C"], [2, 3]) is equivalent to:

                UPDATE (THE DATABASE)
                SET B = 2, C = 3
                WHERE A = 1

        Parameters:
            where_col: HitMeColumn
                Column to check for match

            where_key: Any
                Rows where row[where_col] = where_key will be updated

            update_cols: HitMeColumn or list[HitMeColumn]
                row[update_cols] will be updated for matching rows

            update_values: Any or list[Any]
                row[update_col] will be updated to update_value for matching rows

            empty_error: str
                If the query yields an empty result, nothing is done and otherwise
                a HitMeException with empty_error as the message is raised
        """
        hitmeassert(
            isinstance(where_col, HitMeColumn), f"{where_col} must be HitMeColumn"
        )

        self._check_loaded()
        self._check_locked()

        cols = self.db.loc[self.db[where_col] == where_key]
        if len(cols) == 0:
            if empty_error is not None:
                raise HitMeException(empty_error)
            else:
                return

        # Perform the update, back up to file, and log the write
        self.db.loc[self.db[where_col] == where_key, update_cols] = update_values
        self.db.to_pickle(get_db_path(self.assignment))
        self.logger.log_set(where_col, where_key, update_cols, update_values)

    def groupby(self, by, aggregate_col, aggregator=lambda x: x):
        """
        Performs a read operation similar to a simple SQL GROUPBY on the database.

        Examples:
            1.  groupby("A", "B", len) is equivalent to:

                SELECT A, COUNT(B)
                FROM (THE DATABASE)
                GROUPBY A

            2.  groupby(["A", "B"], "C", len) is equivalent to:

                SELECT A, B, COUNT(C)
                FROM (THE DATABASE)
                GROUPBY A, B

            3.  groupby("A", "B") is not equivalent to a typical
                SQL query. It returns something like:

                1: [B values for rows with A value of 1],
                2: [B values for rows with A value of 2],
                etc.

            4.  groupby("A", ["B", "C"]) is also not equivalent to
                a typical SQL query. It returns something like:

                1: [ list of 2-element lists that are the B and C
                     values for rows with A value of 1 ] ,
                2: [ list of 2-element lists that are the B and C
                     values for rows with A value of 2 ] ,
                etc.

        Notes: applying groupby with None by keys behaves the same as in pandas.

        Parameters:
            by: HitMeColumn or list[HitMeColumn]
                Column(s) to aggregate on

            aggregate_col: HitMeColumn or list[HitMeColumn]
                Column(s) that will be aggregated

            aggregator: function[list[Any], Any] if aggregate_col
                is a HitMeColumn, function[list[dict[HitMeColumn, Any]], Any]
                if aggregate_col is a list[HitMeColumn]

                Function to be applied to the aggregation of aggregate_col
                values for each unique by key. It is passed a list of the
                values to aggregate and then will produce some aggregation
                of them. For example, len can be used to count as in the
                examples above.

                For instance:

                    groupby("A", "B") produces something like:

                    { 1: [2, 3], 2: [2, 4, 5] }

                    groupby("A", "B", len) produces something like:

                    { 1: 2, 2: 3}

                    Where len( ) has been applied to [2, 3] and [2, 4, 5].

                    len( ) also works in the instance where aggregate_col
                    is a list[HitMeColumn]. Example:

                    groupby("A", ["B", "C"]) produces something like:

                    { 1: [{"B": 2, "C": 3}, {"B": 4, "C": 5}],
                      2: [{"B": 2, "C": 3}, {"B": 4, "C": 5}, {"B": 6, "C": 7}] }

                    groupby("A", ["B", "C"], len) produces something like:

                    { 1: 2, 2: 3}

                    Where len( ) has been applied to
                    [{"B": 2, "C": 3}, {"B": 4, "C": 5}]
                    and [{"B": 2, "C": 3}, {"B": 4, "C": 5}, {"B": 6, "C": 7}].

        Returns:
            dict[Any, list[Any]]:
                If by is a HitMeColumn and we do not aggregate.

            dict[Any, Any]:
                If by is a HitMeColumn and we apply an aggregator.

            dict[tuple[Any, ...], list[Any]]:
                If by is a list, the keys will be tuples of length len(by).

                For example, groupby(["A", "B"], "C") would output
                something like:

                { (1,2): [1, 2], (1,3): [2, 3] }

                Note here output Any could be a list[dict[HitMeColumn, Any]]
                in the event aggregate_col is a list[HitMeColumn].

            dict[tuple[Any, ...], Any]:
                If by is a list, the keys will be tuples of length len(by).

                For example, groupby(["A", "B"], "C", len) would output
                something like:

                { (1,2): 2, (1,3): 3 }

                Note here output Any could be a list[dict[HitMeColumn, Any]]
                in the event aggregate_col is a list[HitMeColumn].
        """

        self._check_loaded()
        pd_groupby = self.db.groupby(by, sort=False)
        if isinstance(aggregate_col, HitMeColumn):
            pre_agg_pd_series = pd_groupby[aggregate_col].apply(list)
        else:
            pre_agg_pd_series = pd_groupby[aggregate_col].apply(
                lambda x: x.to_dict("records")
            )
        return pre_agg_pd_series.apply(aggregator).to_dict()

    def update(self, rows):
        """
        Updates the database with additional rows. The additional rows
        are added to the end of the database.

        Warning:
            No explicit check is done to make sure this does not
            lead to duplicates of any way. We leave that to the
            client/invoking code.

        Parameters:
            rows: list
                In particular, the rows should be in a format that
                can be easily turned into a pandas DataFrame. For
                instance, a list of dictionaries specifing the
                attributes keys and values in each row.
        """

        self._check_loaded()
        self._check_locked()
        self.db = pd.concat([self.db, pd.DataFrame(rows)], ignore_index=True)
        self.db.to_pickle(get_db_path(self.assignment))
        self.logger.log_update(*rows)
