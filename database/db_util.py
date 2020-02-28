""" 
Filename: db_util.py
Authors: Kush
Description: CRUD functions to interact with the database
"""

# imports
from datetime import datetime
import logging
import os
import sqlite3
import sys
from pathlib import Path
from sqlite3 import Error

sys.path.insert(0, str(Path(__file__).resolve().parents[1]) + '/')

# Third party imports
import click
import pandas as pd

# Project level imports
from config.config import opt, create_table_commands, select_from_table_commands
from constants.genericconstants import DBConstants as DBCONST
from utils.logger import Logger

# Module Level Constants
TABLE_NAME = DBCONST.TABLE
CREATE_CMD = create_table_commands
SELECT_CMD = select_from_table_commands


def insert_db(df, db_path=opt.DB_PATH, table_name=TABLE_NAME):
    """ Insert data into sqlite3 database

    :param df (pd.DataFrame): Data to be inserted
    :param db_path (str): Path to the database
    :param table_name (str): Name of the table
    :return:
    """
    try:
        conn = sqlite3.connect(db_path)
        print("\ta. Connected to Sqlite")
        # Upload data to the database
        df.to_sql(name=table_name, con=conn, if_exists='append', index=False)
        print("\tb. Inserted into Database")
        conn.commit()
        conn.close()
    except sqlite3.Error as error:
        print("Failed to Insert into table ", error)

    finally:
        if conn:
            conn.close()
            print("\tc. Sqlite connection is closed")


def pull_data(image_date=None, all=False, filtered_size=False, db_path=opt.DB_PATH):
    """ Pull data from sql database

    :param image_date(str): Image date filter for selecting images
    :param all (bool): Flag for pulling all images from database
    :param filtered_size (bool): Flag for indicating filtered size query command
    :param db_path (str): Path to the database
    :return:
        pd.DataFrame - pulled data
    """
    def get_query(filtered_size, all):
        """Get the query given the formatting options"""
        if not all:
            try:
                expected_fmt = '%Y%m%d'
                # convert date formatting for sql table
                date = datetime.strptime(image_date, expected_fmt).strftime('%Y-%m-%d')

                # Access sql database using filtered size query
                size_suffix = '_filtered_size' if filtered_size else ''
                query = SELECT_CMD["select_images" + size_suffix].format(date)
            except:
                raise ValueError(
                    f"time data '{date}' does not match format '{expected_fmt}'")
        else:
            query = SELECT_CMD["select_all"]
        return query

    # Log data
    fname = f'seascape_{datetime.now().strftime("%Y%m%d")}'
    log_fname = os.path.join(opt.META_DIR, fname + '.log')
    Logger(log_fname, logging.INFO, False)
    logger = logging.getLogger('pull_data')
    Logger.section_break(title='SEASCAPE')
    db = Database(db_path)

    # Determine which query to run
    # Pulls either all data or given a filtered option (size, date, etc.)
    query = get_query(filtered_size, all)

    # Pull data from database
    df = pd.read_sql(query, db.conn)

    # Encode unlabeled images
    df[DBCONST.IMG_LBL] = df[DBCONST.IMG_LBL].fillna(DBCONST.IMG_UNLBLED)

    # Log results
    logger.info('SUCCESS: meta file generated')
    logger.info(f'Dates pulled: {df.image_date.unique()}')
    logger.info(f'Dataset size: {df.shape[0]}')
    logger.info(f'Label Distribution\n{"-"*30}\n{df[DBCONST.IMG_LBL].value_counts()}')

    return df

class Database:
    """ Database instance for CRUD interaction
    """

    def __init__(self, db_path):
        """ construct the database
        :param db_path: path to the database
        """
        self.conn = self.create_connection(db_path)

    def create_connection(self, db_path):
        """ create a db connection to database
	    :param db_path: database file path
	    :return: Connection object or None
	    """
        try:
            conn = sqlite3.connect(db_path)
            print('SUCCESS: Table Connected')
            return conn
        except Error as e:
            print(e)

        return None

    def close_connection(self):
        """ close the connection
        """
        if self.conn != None:
            self.conn.close()

    def execute(self, operation, query):
        """ execute the given query
        :param operation: caller function's name
        :param query: query to be executed
        """
        try:
            cur = self.conn.cursor()
            cur.execute(query)
        except:
            print("Error in " + str(operation) + " operation")
            self.conn.rollback()

    def new_table(self, name, schema):
        """ create a new table with the given schema
        :param name: name of the new table
        :param schema: the schema as a string
        :return: None
        """
        query = "CREATE TABLE " + str(name) + " (" + str(schema) + ");"
        self.execute("create new table", query)

    def create(self, query, data):
        """ create rows in table from the given data
        :param query: the Insert query as a string
        :param data: a list of row tuples to be inserted
        :return: None
        """
        try:
            cur = self.conn.cursor()
            cur.executemany(query, data)
        except:
            print("error in insert operation")
            self.conn.rollback()

    def read(self, table_name, cols_needed="*", conditions=None):
        """ get all rows, or all rows specified by the query
        :param table_name: name of the table to select from
        :param cols_needed: string with comma separated list of cols needed, defaults to *
        :param conditions: string with conditions
        :return: result table
        """
        if conditions == None:
            query = "SELECT " + cols_needed + " FROM " + table_name
        else:
            query = "SELECT " + cols_needed + " FROM " + table_name + " " + conditions

        try:
            cur = self.conn.cursor()
            cur.execute(query)
            return cur.fetchall()
        except:
            print("error in select operation")
            self.conn.rollback()

    def update(self, table_name, new_vals, prim_key_id):
        """ update certain values specified by query
        :param table_name: name of th table to update
        :param new_vals: a dict with attributes as keys, and
                         values as values
        :param prim_key_id: key value pair as list of size 2
                         primary key identifier for row to update
        :return: None
        """
        query = "UPDATE " + table_name + " SET "
        for key in new_vals.keys():
            query += str(key) \
                    + " " \
                    + str(new_vals[key]) \
                    + " , "\

        # remove last comma, and space
        query = query[:len(query) - 3]
        query += " WHERE " \
                + str(prim_key_id[0]) \
                + " = " \
                + str(prim_key_id[1]) \

        # execute the query
        self.execute("update", query)

    def delete(self, table_name, prim_key_id):
        """ delete a row from specified table, and prim key value
        :param table_name: name of the table to delete from
        :param prim_key_id: key value pair as list of size 2
                         primary key identifier for row to update
        :return: None
        """
        query = "DELETE FROM " \
                + table_name \
                + " WHERE " \
                + str(prim_key_id[0]) \
                + " = " \
                + str(prim_key_id[1]) \
 \
            # execute the query
        self.execute("delete", query)
