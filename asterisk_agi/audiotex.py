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
cfg = config.config_audiotex()
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


class Operators(BaseModel):
    id = IntegerField(primary_key=True)
    operator = CharField(max_length=16)
    loggedin = IntegerField()
    available = IntegerField()
    name = CharField(max_length=255)
    lastcall = DateTimeField(default=datetime.datetime.now)
    timeslot = IntegerField()
    type = IntegerField()
    ast_option = IntegerField()
    telefono = CharField(max_length=20)
    telefono_alternativo = CharField(max_length=20)
    descripcion = TextField()

    @classmethod
    def info(cls, operator):
        return Operators.select().where(Operators.operator == operator)

    @classmethod
    def busca(cls, telefono, type):
        return Operators.select().where(
            (
                (Operators.telefono == telefono)
                | (Operators.telefono_alternativo == telefono)
            )
            & (Operators.type == type)
        )

    @classmethod
    def disponibles(cls, type):
        return (
            Operators.select()
            .where(
                Operators.type == type,
                Operators.available == 1,
                Operators.loggedin == 1,
            )
            .order_by(Operators.type, Operators.operator)
        )

    @classmethod
    def aleatorio(cls, type, limite=1):
        return (
            Operators.select()
            .where(
                Operators.type == type,
                Operators.available == 1,
                Operators.loggedin == 1,
            )
            .order_by(Operators.lastcall)
            .limit(limite)
        )

    class Meta:
        db_table = "operators"


class Services(BaseModel):
    ddi = CharField(max_length=16, primary_key=True)
    cost = IntegerField(default=None, null=True)
    service = CharField(max_length=255, default=None, null=True)
    # TODO: Cambiar null
    ast_context = CharField(max_length=255, default="", null=False)

    @classmethod
    def info(cls, ddi):
        return Services.select().where(Services.ddi == ddi)

    class Meta:
        db_table = "services"


class Call(BaseModel):
    ani = CharField(max_length=16, default=None)
    ddi = CharField(max_length=16, default=0)
    time = DateTimeField(default=datetime.datetime.now)

    class Meta:
        db_table = "clientespv"
        primary_key = False


###############################
# Modelos de Fonotarot Chile
###############################
class FTChileClientId(BaseModel):
    ani = IntegerField(primary_key=True)
    clientid = IntegerField()

    @classmethod
    def busca(cls, ani):
        return FTChileClientId.select().where(FTChileClientId.ani == ani)

    @classmethod
    def info(cls, clientid):
        return FTChileClientId.select().where(FTChileClientId.clientid == clientid)

    class Meta:
        db_table = "clientid"


class FTChileCreditos(BaseModel):
    clientid = IntegerField(index=True)
    creditos = IntegerField()
    outbound = IntegerField()

    @classmethod
    def saldo(cls, clientid):
        return FTChileCreditos.select().where(FTChileCreditos.clientid == clientid)

    @classmethod
    def suma(cls, clientid, creditos):
        return FTChileCreditos.update(
            {FTChileCreditos.creditos: FTChileCreditos.creditos + creditos}
        ).where(FTChileCreditos.clientid == clientid)

    @classmethod
    def set_cero(cls):
        return (
            FTChileCreditos.update({FTChileCreditos.creditos: 0})
            .where(FTChileCreditos.creditos < 0)
            .execute()
        )

    class Meta:
        db_table = "creditos"
        primary_key = False


########################
# Modelos de Alotarot
########################
class AlotarotClientId(BaseModel):
    ani = IntegerField(primary_key=True)
    clientid = IntegerField()

    @classmethod
    def busca(cls, ani):
        return AlotarotClientId.select().where(AlotarotClientId.ani == ani)

    @classmethod
    def info(cls, clientid):
        return AlotarotClientId.select().where(AlotarotClientId.clientid == clientid)

    class Meta:
        db_table = "clientidalo"


class AlotarotCreditos(BaseModel):
    clientid = IntegerField(index=True)
    creditos = IntegerField()
    outbound = IntegerField()

    @classmethod
    def saldo(cls, clientid):
        return AlotarotCreditos.select().where(AlotarotCreditos.clientid == clientid)

    @classmethod
    def suma(cls, clientid, creditos):
        return AlotarotCreditos.update(
            {AlotarotCreditos.creditos: AlotarotCreditos.creditos + creditos}
        ).where(AlotarotCreditos.clientid == clientid)

    @classmethod
    def set_cero(cls):
        return (
            AlotarotCreditos.update({AlotarotCreditos.creditos: 0})
            .where(AlotarotCreditos.creditos < 0)
            .execute()
        )

    class Meta:
        db_table = "creditosalo"
        primary_key = False


###############################
# Modelos de Fonotarot Latam
###############################
class FTLatamClient(BaseModel):
    clientid = IntegerField(primary_key=True)
    nombres = TextField(null=True)
    correo = TextField(null=True)
    telefono = CharField(max_length=16, null=True)
    pin = IntegerField(index=True)
    creditos = IntegerField(null=True)

    @classmethod
    def busca(cls, pin):
        return FTLatamClient.select().where(FTLatamClient.pin == pin)

    @classmethod
    def info(cls, clientid):
        return FTLatamClient.select().where(FTLatamClient.clientid == clientid)

    @classmethod
    def suma_creditos(cls, clientid, creditos):
        return FTLatamClient.update(
            {FTLatamClient.creditos: FTLatamClient.creditos + creditos}
        ).where(FTLatamClient.clientid == clientid)

    @classmethod
    def set_cero(cls):
        return (
            FTLatamClient.update({FTLatamClient.creditos: 0})
            .where(FTLatamClient.creditos < 0)
            .execute()
        )

    class Meta:
        db_table = "clientidlat"


#####################
# Funciones archivo
#####################
def verbose(str):
    if agi is None:
        logger.info(str)
        print(str)
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


def zvn_obtiene_clientid(ani, servicio):
    try:
        if servicio == "fonotarot-cl":
            info = FTChileClientId.busca(ani)
        elif servicio == "alotarot":
            info = AlotarotClientId.busca(ani)
        elif servicio == "fonotarot-latam":
            # En este caso validamos el PIN en vez del ANI
            info = FTLatamClient.busca(ani)
        verbose(f"SQL: {info}")
        cliente = info.get()
    except Exception as e:
        verbose(f"ERROR: {e}")
        if agi:
            agi.execute(pystrix.agi.core.SetVariable("clientid", 0))
        verbose("clientid=0")
        return 25
    else:
        if agi:
            agi.execute(pystrix.agi.core.SetVariable("clientid", int(cliente.clientid)))
        verbose(f"clientid={int(cliente.clientid)}")
        return 0


def zvn_obtiene_segundos(clientid, servicio):
    try:
        if servicio == "fonotarot-cl":
            info = FTChileCreditos.saldo(clientid)
        elif servicio == "alotarot":
            info = AlotarotCreditos.saldo(clientid)
        elif servicio == "fonotarot-latam":
            info = FTLatamClient.info(clientid)
        verbose(f"SQL: {info}")
        cliente = info.get()
    except Exception as e:
        verbose(f"ERROR: {e}")
        if agi:
            agi.execute(pystrix.agi.core.SetVariable("segundos", 0))
        verbose("segundos=0")
        return 25
    else:
        if agi:
            agi.execute(pystrix.agi.core.SetVariable("segundos", int(cliente.creditos)))
        verbose(f"segundos={int(cliente.creditos)}")
        return 0


def zvn_verifica_did(did):
    try:
        info = Services.info(did)
        verbose(f"SQL: {info}")
        service = info.get()
    except Exception:
        if agi:
            agi.execute(pystrix.agi.core.SetVariable("siguiente", "no-service"))
        verbose(f"ERROR: {did} no existe en la tabla services.")
        return 37
    else:
        if agi:
            agi.execute(pystrix.agi.core.SetVariable("siguiente", service.ast_context))
        verbose(f"ast_context={service.ast_context}")
        return 0


def zvn_inserta_llamada_online(ani, did):
    try:
        llamada = Call.insert(ani=ani, ddi=did, time=datetime.datetime.now())
    except Exception:
        verbose("ERROR: No se pudo insertar la llamada en la tabla")
    else:
        if cfg.debug:
            verbose(f"SQL: {llamada}")
        llamada.execute()
        return 0


def zvn_elimina_llamada_online(ani):
    try:
        llamada = Call.delete().where(Call.ani == ani)
    except Exception:
        verbose("ERROR: No se pudo eliminar la llamada de la tabla")
    else:
        if cfg.debug:
            verbose(f"SQL: {llamada}")
        llamada.execute()
        return 0


def zvn_ejecutivos_disponibles(tipo):
    try:
        ejecutivos_sql = Operators.disponibles(tipo)
        if cfg.debug:
            verbose(f"SQL: {ejecutivos_sql}")
        # TODO: Dejar así por ahora, pero aquí debería ir un get
        ejecutivos = ejecutivos_sql.execute()
    except Exception as e:
        verbose(f"ERROR: {e}")
        return 38
    else:
        if len(ejecutivos) == 0:
            if agi:
                agi.execute(pystrix.agi.core.SetVariable("siguiente", "no-operators"))
                agi.execute(pystrix.agi.core.SetVariable("disponibles", 0))
            if cfg.debug:
                verbose("No se encontraron ejecutivos disponibles.")
                verbose("siguiente=no-operators")
                verbose("disponibles=0")
            return 10
        elif len(ejecutivos) > 0:
            disponibles = len(ejecutivos)
            if agi:
                agi.execute(pystrix.agi.core.SetVariable("siguiente", ""))
                agi.execute(pystrix.agi.core.SetVariable("disponibles", disponibles))
            if cfg.debug:
                verbose("siguiente=")
                verbose(f"disponibles={disponibles}")

            audio_str = ""
            for info in ejecutivos:
                audio_str = f"{audio_str}&zvn/tarotistas/{info.name.strip()}"
                if agi:
                    agi.execute(
                        pystrix.agi.core.SetVariable(
                            f"tar_opt_{info.ast_option}", info.operator
                        )
                    )
                if cfg.debug:
                    verbose(
                        f"{info.name}::{info.ast_option}::{info.telefono}::{info.operator}"
                    )
                    verbose(f"tar_opt_{info.ast_option}={info.operator}")

            if agi:
                agi.execute(pystrix.agi.core.SetVariable("audio_str", audio_str[1:]))
            if cfg.debug:
                verbose(f"audio_str={audio_str[1:]}")
            return 0


def zvn_ejecutivo_aleatorio(tipo):
    try:
        ejecutivos_sql = Operators.aleatorio(tipo)
        if cfg.debug:
            verbose(f"SQL: {ejecutivos_sql}")
        # TODO: dejar así pero aquí va get()
        ejecutivos = ejecutivos_sql.execute()
    except Exception as e:
        verbose(f"ERROR: {e}")
        return 39
    else:
        if len(ejecutivos) == 0:
            if agi:
                agi.execute(pystrix.agi.core.SetVariable("siguiente", "no-operators"))
                agi.execute(pystrix.agi.core.SetVariable("disponibles", 0))
            if cfg.debug:
                verbose("No se encontraron ejecutivos disponibles.")
                verbose("siguiente=no-operators")
                verbose("disponibles=0")
            return 10
        elif len(ejecutivos) == 1:
            disponibles = len(ejecutivos)
            if agi:
                agi.execute(pystrix.agi.core.SetVariable("siguiente", ""))
                agi.execute(pystrix.agi.core.SetVariable("disponibles", disponibles))
            if cfg.debug:
                verbose("siguiente=")
                verbose(f"disponibles={disponibles}")

            for info in ejecutivos:
                if agi:
                    agi.execute(
                        pystrix.agi.core.SetVariable(
                            "ejecutivo_seleccionado", info.operator
                        )
                    )
                if cfg.debug:
                    verbose(
                        f"{info.name}::{info.ast_option}::{info.telefono}::{info.operator}"
                    )
                    verbose(f"ejecutivo_seleccionado={info.operator}")

            return 0


def zvn_buscar_pin(pin):
    try:
        info = FTLatamClient.busca(pin)
        if cfg.debug:
            verbose(f"SQL: {info}")
        cliente = info.get()
    except Exception as e:
        verbose(f"ERROR: {e}")
        verbose(f"El PIN {pin} no existe en la tabla clientidlat.")
        if agi:
            agi.execute(pystrix.agi.core.SetVariable("siguiente", "bad-pin"))
        if cfg.debug:
            verbose("siguiente=bad-pin")
        return 41
    else:
        if agi:
            agi.execute(pystrix.agi.core.SetVariable("clientid", cliente.clientid))
            agi.execute(pystrix.agi.core.SetVariable("segundos", cliente.creditos))
        if cfg.debug:
            verbose(f"clientid={cliente.clientid}")
            verbose(f"segundos={cliente.creditos}")
        return 0


def zvn_info_ejecutivo(campo, valor):
    try:
        if campo == "telefono":
            info = Operators.busca(valor, 7)
        else:
            info = Operators.info(valor)
        if cfg.debug:
            verbose(f"SQL: {info}")
        ejecutivo = info.get()
    except Exception as e:
        verbose(f"ERROR: {e}")
        verbose(f"El operador {campo}={valor} no existe (probablemente).")
        verbose("siguiente=no-operator")
        if agi:
            agi.execute(pystrix.agi.core.SetVariable("siguiente", "no-operator"))
        return 40
    else:
        if agi:
            agi.execute(
                pystrix.agi.core.SetVariable("operador_nombre", ejecutivo.name.strip())
            )
            agi.execute(
                pystrix.agi.core.SetVariable(
                    "operador_telefono", ejecutivo.telefono.strip()
                )
            )
            agi.execute(
                pystrix.agi.core.SetVariable(
                    "operador_numero", ejecutivo.operator.strip()
                )
            )

        if ejecutivo.loggedin == 0:
            estado = "not-loggedin"
            siguiente = "operator-busy"
        else:
            estado = "loggedin"
            if ejecutivo.available == 0:
                siguiente = "operator-busy"
                estado = "not-available"
            else:
                estado = "available"
                siguiente = ""

        if agi:
            agi.execute(pystrix.agi.core.SetVariable("siguiente", siguiente))
            agi.execute(pystrix.agi.core.SetVariable("estado", estado))

        if cfg.debug:
            verbose(f"siguiente={siguiente}")
            verbose(f"estado={estado}")
            verbose(f"operador_nombre={ejecutivo.name.strip()}")
            verbose(f"operador_telefono={ejecutivo.telefono.strip()}")
            verbose(f"operador_numero={ejecutivo.operator.strip()}")


def zvn_cambia_estado(ejecutivo, disponible, loggedin=1):
    try:
        actualiza = Operators.update(
            {
                Operators.available: disponible,
                Operators.loggedin: loggedin,
                Operators.lastcall: datetime.datetime.now(),
            }
        ).where(Operators.operator == ejecutivo)
        if cfg.debug:
            verbose(f"SQL: {actualiza}")
        actualiza.execute()
    except Exception as e:
        verbose(f"ERROR: {e}")
        return 41
    else:
        return 0


def zvn_resta_saldo(segundos, clientid, servicio):
    try:
        if servicio == "fonotarot-cl":
            creditos = FTChileCreditos.suma(clientid, segundos)
        elif servicio == "alotarot":
            creditos = AlotarotCreditos.suma(clientid, segundos)
        elif servicio == "fonotarot-latam":
            creditos = FTLatamClient.suma_creditos(clientid, segundos)
        verbose(f"SQL: {creditos}")
        creditos.execute()
    except Exception as e:
        verbose(f"ERROR: {e}")
        return 42

    try:
        FTChileCreditos.set_cero()
        AlotarotCreditos.set_cero()
        FTLatamClient.set_cero()
    except Exception as e:
        verbose(f"ERROR: {e}")

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

    elif sys.argv[1] == "verifica_did":
        did = sys.argv[2].strip()
        verbose(f"Ejecutando zvn_verifica_did({did})")
        sys.exit(zvn_verifica_did(did))

    elif sys.argv[1] == "obtiene_clientid":
        ani = sys.argv[2]
        servicio = sys.argv[3]
        verbose(f"Ejecutando zvn_obtiene_clientid({ani}, {servicio})")
        sys.exit(zvn_obtiene_clientid(ani, servicio))

    elif sys.argv[1] == "obtiene_segundos":
        clientid = sys.argv[2]
        servicio = sys.argv[3]
        verbose(f"Ejecutando zvn_obtiene_segundos({clientid}, {servicio})")
        sys.exit(zvn_obtiene_segundos(clientid, servicio))

    elif sys.argv[1] == "inserta_llamada_online":
        ani = sys.argv[2]
        did = sys.argv[3]
        verbose(f"Ejecutando zvn_inserta_llamada_online({ani}, {did})")
        sys.exit(zvn_inserta_llamada_online(ani, did))

    elif sys.argv[1] == "elimina_llamada_online":
        ani = sys.argv[2]
        verbose(f"Ejecutando zvn_elimina_llamada_online({ani})")
        sys.exit(zvn_elimina_llamada_online(ani))

    elif sys.argv[1] == "ejecutivos_disponibles":
        tipo = sys.argv[2]
        verbose(f"Ejecutando zvn_ejecutivos_disponibles({tipo})")
        sys.exit(zvn_ejecutivos_disponibles(tipo))

    elif sys.argv[1] == "buscar_pin":
        pin = sys.argv[2]
        verbose(f"Ejecutando zvn_buscar_pin({pin})")
        sys.exit(zvn_buscar_pin(pin))

    elif sys.argv[1] == "ejecutivo_aleatorio":
        tipo = sys.argv[2]
        verbose(f"Ejecutando zvn_ejecutivo_aleatorio({tipo})")
        sys.exit(zvn_ejecutivo_aleatorio(tipo))

    elif sys.argv[1] == "info_ejecutivo":
        campo = sys.argv[2]
        valor = sys.argv[3]
        verbose(f"Ejecutando zvn_info_ejecutivo({campo}, {valor})")
        sys.exit(zvn_info_ejecutivo(campo, valor))

    elif sys.argv[1] == "cambia_estado":
        ejecutivo = sys.argv[2]
        disponible = sys.argv[3]
        verbose(f"Ejecutando zvn_cambia_estado({ejecutivo}, {disponible})")
        sys.exit(zvn_cambia_estado(ejecutivo, disponible))

    elif sys.argv[1] == "cambia_login":
        ejecutivo = sys.argv[2]
        disponible = sys.argv[3]
        loggedin = sys.argv[4]
        verbose(f"Ejecutando zvn_cambia_estado({ejecutivo}, {disponible}, {loggedin})")
        sys.exit(zvn_cambia_estado(ejecutivo, disponible, loggedin))

    elif sys.argv[1] == "resta_saldo":
        segundos = abs(int(sys.argv[2])) * -1
        clientid = sys.argv[3]
        servicio = sys.argv[4]
        verbose(f"Ejecutando zvn_resta_saldo({segundos}, {clientid}, {servicio})")
        sys.exit(zvn_resta_saldo(segundos, clientid, servicio))

    else:
        verbose(f"Comando {sys.argv[1]} no existe en {sys.argv[0]}.")
        sys.exit(1)
