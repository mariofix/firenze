from dotenv import load_dotenv
import datetime

load_dotenv()
from redis_om import HashModel, get_redis_connection, Migrator

conn = get_redis_connection()


class Operator(HashModel):
    number: int
    loggedin: int
    available: int
    lastcall: int


Migrator().run()
