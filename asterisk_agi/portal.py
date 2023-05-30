#!/home/mariofix/proyectos/zvn-firenze/.venv/bin/python
import datetime
import sys
from contextvars import ContextVar

import peewee
import pystrix
import sentry_sdk
from peewee import CharField, DateTimeField, IntegerField, Model, TextField
from zvn import config, logger

"""
sentry_sdk.init(
    dsn="https://3e98f1dd32dd45deb0c078da57200121@o438601.ingest.sentry.io/5827586",
    release="zvn-agi@0.0.5",
    traces_sample_rate=0.2,
    environment="development",
    request_bodies="always",
)
"""
db_state_default = {"closed": None, "conn": None, "ctx": None, "transactions": None}
db_state = ContextVar("db_state", default=db_state_default.copy())


class PeeweeConnectionState(peewee._ConnectionState):
    def __init__(self, **kwargs):
        super().__setattr__("_state", db_state)
        super().__init__(**kwargs)

    def __setattr__(self, name, value):
        self._state.get()[name] = value

    def __getattr__(self, name):
        return self._state.get()[name]


logger = logger.zvn
cfg = config.config_portal()
agi = None
agi = pystrix.agi.AGI()

conn = peewee.MySQLDatabase(
    cfg.database.name,
    user=cfg.database.username,
    password=cfg.database.password,
    host=cfg.database.hostname,
)
conn._state = PeeweeConnectionState()


########################
# Modelo Generales DB
########################
class BaseModel(Model):
    class Meta:
        database = conn


class Calls(BaseModel):
    recordid = IntegerField(primary_key=True)
    ani = CharField(max_length=16, null=False)
    ddi = CharField(max_length=16, null=False)
    time = DateTimeField(default=datetime.datetime.now)
    duration = IntegerField()
    clientid = IntegerField()
    ssi = CharField(max_length=255)

    class Meta:
        db_table = "callsprepago"


#####################
# Funciones archivo
#####################
def verbose(str):
    if agi is None:
        logger.info(str)
    else:
        agi.execute(pystrix.agi.core.Verbose(str))


def zvn_test():
    sql_test = "SELECT CURRENT_TIMESTAMP() as hora"
    if cfg.debug:
        verbose(f"SQL: {sql_test}")
    try:
        hora = conn.execute_sql(sql_test)
        hora_val = hora.fetchone()
        hora_str = hora_val[0].strftime("%Y-%m-%d %H:%M:%S")
    except Exception as e:
        verbose(f"ERROR: {e}")
        return 2
    else:
        verbose(f"Hora Servidor: {hora_str}")
        return 0


def zvn_inserta_llamada_cdr(ani, did, seg, cid, ssi):
    try:
        llamada = Calls.insert(
            ani=ani,
            ddi=did,
            time=datetime.datetime.now(),
            duration=seg,
            clientid=cid,
            ssi=ssi,
        )
        if cfg.debug:
            verbose(f"SQL: {llamada}")
        llamada.execute()
    except Exception as e:
        verbose(f"Error: {e}")
        return 42
    else:
        return 0


#########
# Main
#########
if __name__ == "__main__":
    if len(sys.argv) == 1:
        verbose("Debe ingresar un comando.")
        sys.exit(1)

    if sys.argv[1] == "test":
        verbose("Ejecutando zvn_test()")
        sys.exit(zvn_test())

    elif sys.argv[1] == "inserta_llamada_cdr":
        ani = sys.argv[2]
        did = sys.argv[3]
        seg = sys.argv[4]
        cid = sys.argv[5]
        ssi = sys.argv[6]
        verbose(
            f"Ejecutando zvn_inserta_llamada_cdr({ani}, {did}, {seg}, {cid}, {ssi})"
        )
        sys.exit(zvn_inserta_llamada_cdr(ani, did, seg, cid, ssi))

    else:
        verbose(f"Comando {sys.argv[1]} no existe en {sys.argv[0]}.")
        sys.exit(1)
