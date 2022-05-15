from django.db import connection
from collections import OrderedDict
import decimal
import pandas

def __db_fetch_values(query):
    cursor = connection.cursor()
    cursor.execute(query)
    fetchVal = cursor.fetchall()
    cursor.close()
    return fetchVal


def __db_fetch_single_value(query):
    cursor = connection.cursor()
    cursor.execute(query)
    fetchVal = cursor.fetchone()
    cursor.close()
    return fetchVal[0]


def __db_fetch_values_dict(query):
    cursor = connection.cursor()
    cursor.execute(query)
    fetchVal = dictfetchall(cursor)
    cursor.close()
    return fetchVal


def __db_commit_query(query):
    cursor = connection.cursor()
    cursor.execute(query)
    cursor.close()


def __db_insert_query(query):
    cursor = connection.cursor()
    cursor.execute(query)
    fetch_val = cursor.fetchone()
    cursor.close()
    return fetch_val[0]


def dictfetchall(cursor):
    desc = cursor.description
    return [
        OrderedDict(zip([col[0] for col in desc], row))
        for row in cursor.fetchall()]


def decimal_date_default(obj):
    if isinstance(obj, decimal.Decimal):
        return float(obj)
    elif hasattr(obj, 'isoformat'):
        return obj.isoformat()
    else:
        return obj
    raise TypeError


def database(query):
    """
        This function excute query with the help of connection
        :param query: string
        :return: None
    """
    cursor = connection.cursor()
    cursor.execute(query)
    cursor.close()


def __db_fetch_single_value_excption(query):
    cursor = connection.cursor()
    cursor.execute(query)
    fetchVal = cursor.fetchone()
    cursor.close()
    print '---------fetchval--------'
    print fetchVal
    if fetchVal is None:
        return 0
    else:
        if fetchVal[0] is None:
            return 0
        else:
            return fetchVal[0]


def db_fetch_dataframe(query):
    data_frame = pandas.read_sql(query, connection)
    return data_frame
