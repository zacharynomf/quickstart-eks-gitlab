from __future__ import print_function
from crhelper import CfnResource
import logging

# import the PostgreSQL client for Python
# reference https://pythontic.com/database/postgresql/create%20database
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

logger = logging.getLogger(__name__)
# Initialise the helper, all inputs are optional, this example shows the defaults
helper = CfnResource(json_logging=False, log_level='DEBUG', boto_level='CRITICAL', sleep_on_delete=120)

@helper.create
@helper.update
def create(event, context):
    logger.info("Got Create")
    # Connect to PostgreSQL DBMS
    database, cursor = createConnection(event)

    # check if database exist
    cursor.execute("SELECT datname FROM pg_database;")
    list_database = cursor.fetchall()
    if (database,) in list_database:
        logger.info(f"Database {database} exist, skip create")
    else:
        # Create database
        cursor.execute(f"create database {database};")
        logger.info("Complete create")

@helper.delete
def delete(event, context):
    logger.info("Got Delete")
    # Connect to PostgreSQL DBMS
    database, cursor = createConnection(event)

    cursor.execute(f"drop database {database};")
    logger.info("Complete Delete")

def createConnection(event):
    properties = event['ResourceProperties']
    userName = properties['UserName']
    password = properties['Password']
    host = properties['Host']
    databasename = properties['DBName']
    return databasename, createCursor(host, userName, password)

def createCursor(host, userName, password):
    con = psycopg2.connect("user={} password={} host={}".format(userName, password, host))
    con.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    return con.cursor()

def handler(event, context):
    helper(event, context)
    