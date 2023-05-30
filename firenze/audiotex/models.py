import datetime

from peewee import CharField, DateTimeField, IntegerField, Model, TextField

from firenze.audiotex.database import conn


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

    class Meta:
        table_name = "operators"

    def __str__(self):
        return self.operator


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
        table_name = "services"


class Call(BaseModel):
    ani = CharField(max_length=16, default=None)
    ddi = CharField(max_length=16, default=0)
    time = DateTimeField(default=datetime.datetime.now)

    class Meta:
        table_name = "clientespv"
        primary_key = False


class CurrentCall(BaseModel):
    id = IntegerField(primary_key=True)
    clientid = IntegerField(null=False, default=0)
    ani = CharField(max_length=16, default=None)
    ddi = CharField(max_length=16, default=0)
    service = CharField(max_length=16, default=0)
    operator = CharField(max_length=4, default=0)
    phone = CharField(max_length=16, default=0)
    time = DateTimeField(default=datetime.datetime.now)

    class Meta:
        table_name = "clientesonline"


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
        table_name = "clientid"


class FTChileCreditos(BaseModel):
    clientid = IntegerField(index=True)
    creditos = IntegerField()
    outbound = IntegerField()

    @classmethod
    def saldo(cls, clientid):
        return FTChileCreditos.select().where(FTChileCreditos.clientid == clientid)

    @classmethod
    def actualiza(cls, clientid, creditos):
        try:
            FTChileCreditos.select(FTChileCreditos.creditos).where(
                FTChileCreditos.clientid == clientid
            ).get()
        except Exception as e:
            FTChileCreditos.insert(clientid=clientid, creditos=creditos).execute()
        else:
            FTChileCreditos.update(
                {FTChileCreditos.creditos: FTChileCreditos.creditos + creditos}
            ).where(FTChileCreditos.clientid == clientid).execute()
        return (
            FTChileCreditos.select(FTChileCreditos.creditos)
            .where(FTChileCreditos.clientid == clientid)
            .scalar()
        )

    class Meta:
        table_name = "creditos"
        primary_key = False


class FTChileNaw(BaseModel):
    clientid = IntegerField(primary_key=True)
    nombre = TextField()
    apellido = TextField()
    correo = TextField()
    servicio = CharField(max_length=50)
    prepago = TextField()

    class Meta:
        table_name = "naw"


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
        table_name = "clientidalo"


class AlotarotCreditos(BaseModel):
    clientid = IntegerField(index=True)
    creditos = IntegerField()
    outbound = IntegerField()

    @classmethod
    def saldo(cls, clientid):
        return AlotarotCreditos.select().where(AlotarotCreditos.clientid == clientid)

    @classmethod
    def actualiza(cls, clientid, creditos):
        try:
            AlotarotCreditos.select(AlotarotCreditos.creditos).where(
                AlotarotCreditos.clientid == clientid
            ).get()
        except Exception as e:
            AlotarotCreditos.insert(clientid=clientid, creditos=creditos).execute()
        else:
            AlotarotCreditos.update(
                {AlotarotCreditos.creditos: AlotarotCreditos.creditos + creditos}
            ).where(AlotarotCreditos.clientid == clientid).execute()
        return (
            AlotarotCreditos.select(AlotarotCreditos.creditos)
            .where(AlotarotCreditos.clientid == clientid)
            .scalar()
        )

    class Meta:
        table_name = "creditosalo"
        primary_key = False


###############################
# Modelos de Fonotarot Latam
###############################
class FTLatamClient(BaseModel):
    clientid = IntegerField(primary_key=True)
    nombres = TextField(null=True)
    correo = TextField(null=True)
    telefono = CharField(max_length=16, null=True)
    pin = CharField(index=True, max_length=8)
    creditos = IntegerField(null=True)

    @classmethod
    def busca(cls, pin):
        return FTLatamClient.select().where(FTLatamClient.pin == pin)

    @classmethod
    def info(cls, clientid):
        return FTLatamClient.select().where(FTLatamClient.clientid == clientid)

    @classmethod
    def actualiza_creditos(cls, clientid, creditos):
        return (
            FTLatamClient.update(
                {FTLatamClient.creditos: FTLatamClient.creditos + creditos}
            )
            .where(FTLatamClient.clientid == clientid)
            .execute()
        )

    class Meta:
        table_name = "clientidlat"
