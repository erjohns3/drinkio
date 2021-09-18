import sqlite3
import sqlalchemy
import shutil
from pathlib import Path
import os
import json

primary_db = "DRINKIO_DB"
backup_db = ".BACKUP_DRINKIO_DB"


class DB:
    @staticmethod
    def doIt(sql):
        connection = sqlalchemy.create_engine(f'sqlite:///{primary_db}')
        cursor = connection.connect()
        return cursor.execute(sql)

    @staticmethod
    def create_if_not_exists():
        create_table_sql = """
            CREATE TABLE IF NOT EXISTS user_pours (
                uuid REAL NOT NULL,
                drink TEXT NOT NULL,
                ingredients TEXT NOT NULL,
                Timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            );
        """
        DB.doIt(create_table_sql)

    @staticmethod
    def record_pour(uuid, drink, ingredients):
        DB.create_if_not_exists()
        query_sql = f"""
            INSERT INTO user_pours (uuid, drink, ingredients)
            VALUES (:uuid, :drink, :ingredients);
        """
        connection = sqlalchemy.create_engine(f'sqlite:///{primary_db}')
        cursor = connection.connect()
        return cursor.execute(query_sql, uuid=uuid, drink=drink, ingredients = json.dumps(ingredients))

    @staticmethod
    def getAll():
        query_sql = """
            SELECT uuid, drink, ingredients, count(*) AS count 
            FROM user_pours GROUP BY uuid, drink
        """
        return DB.doIt(query_sql)
        
    @staticmethod
    def backup_db():
        # hides a db backup in the parent directory :)
        try:
            p = Path(__file__).absolute()
            parent_dir = p.parents[1]
            shutil.copy(primary_db, os.path.join(parent_dir, backup_db))
        except Exception:
            # db does not exist
            return



# class Recommender:
#     @staticmethod
#     def get_them(uuid):
#         """
#         Returns ordered list of recommended drinks, from best to worst fit.
#         Using nearest neighbors algorithm.
#         https://towardsdatascience.com/how-did-we-build-book-recommender-systems-in-an-hour-part-2-k-nearest-neighbors-and-matrix-c04b3c2ef55c
#         """
#         return ['Hemenway Special']
## testing
# DB.record_pour(69, 'potent potable')
# res = DB.getAll()
# print(list(res))