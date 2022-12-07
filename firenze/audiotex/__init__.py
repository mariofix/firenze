from fastapi import APIRouter, HTTPException, Depends, Security, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy.sql.sqltypes import JSON
from firenze.audiotex import models, schemas
from firenze.schemas import Message
from firenze.auth import loggedin_user
from typing import List, Any, Optional
from firenze.audiotex.database import db_state_default
import enum
from peewee import fn, DoesNotExist
from playhouse.shortcuts import model_to_dict
import phonenumbers
from typing import Any
import string
import secrets


async def reset_db_state():
    database.conn._state._state.set(db_state_default.copy())
    database.conn._state.reset()


def get_db(db_state=Depends(reset_db_state)):
    try:
        database.conn.connect()
        yield
    finally:
        if not database.conn.is_closed():
            database.conn.close()


def lee_numero(numero: str, request: Any, pais: str = "CL") -> str:
    try:
        tel = phonenumbers.parse(numero, pais)
    except Exception as e:
        request.app.logger.warning(f"{numero} no parece completo")
    else:
        request.app.logger.info(f"{tel=}")
        numero = tel.national_number

    return numero, tel


audiotexRouter = APIRouter(prefix="/audiotex", tags=["audiotex"])
##################
# Fonotarot Chile
##################
@audiotexRouter.get(
    "/fonotarot-cl/client",
    description="Busca clientid",
    response_model=schemas.ClientId,
    responses={404: {"model": Message}},
    summary="Busca clientid",
    dependencies=[Depends(get_db)],
)
def ftc_user_search(
    request: Request,
    correo: Optional[str] = Query(None, max_length=255),
    telefono: Optional[str] = Query(None, max_length=16),
    uid=Security(loggedin_user, scopes=["audiotex"]),
):
    salida = schemas.ClientId()
    if telefono:
        telefono, tel2 = lee_numero(telefono, request)

    sql_clientid = models.FTChileClientId.busca(telefono)
    if sql_clientid.count() == 0:
        sql_naw = models.FTChileNaw.select().where(models.FTChileNaw.correo == correo)
        if sql_naw.count() == 0:
            request.app.logger.warning(f"Telefono<{telefono}>: None")
            request.app.logger.warning(f"Correo<{correo}>: None")
            raise HTTPException(
                status_code=404,
                detail=f"No se encuentran registros",
            )
        naw = sql_naw.get()
        salida.clientid = naw.clientid
        salida.correo = naw.correo
    elif sql_clientid.count() == 1:
        clientid = sql_clientid.first()
        salida.clientid = clientid.clientid
        sql_naw = models.FTChileNaw.select().where(
            models.FTChileNaw.clientid == salida.clientid
        )
        if sql_naw.count() == 1:
            naw = sql_naw.first()
            salida.correo = naw.correo

    credits = models.FTChileCreditos.saldo(salida.clientid).get()
    salida.creditos = int(credits.creditos)

    tel = []
    sql_telefonos = models.FTChileClientId.info(salida.clientid)
    for phone in sql_telefonos:
        tel.append(f"56{phone.ani}")
    salida.telefonos = tel

    return salida


@audiotexRouter.get(
    "/fonotarot-cl/client/{clientid}",
    description="Busca Informacion de clientid",
    response_model=schemas.ClientId,
    responses={404: {"model": Message}},
    summary="Busca Informacion de clientid",
    dependencies=[Depends(get_db)],
)
def ftc_clientid_search(
    clientid: int,
    request: Request,
    uid=Security(loggedin_user, scopes=["audiotex"]),
):
    sql_clientid = models.FTChileClientId.select().where(
        models.FTChileClientId.clientid == clientid
    )
    count = sql_clientid.count()
    if count == 0:
        request.app.logger.info(f"{clientid=} not found")
        raise HTTPException(
            status_code=404,
            detail=f"ClientID:{clientid}  No se encuentra en la base de datos",
        )
    tel = []
    for phone in sql_clientid:
        tel.append(f"56{phone.ani}")
    credits = models.FTChileCreditos.saldo(clientid).get()
    try:
        naw = (
            models.FTChileNaw.select()
            .where(models.FTChileNaw.clientid == clientid)
            .first()
        )
        correo = naw.correo
    except Exception as e:
        correo = ""

    return {
        "clientid": clientid,
        "creditos": credits.creditos,
        "telefonos": tel,
        "correo": correo,
    }


@audiotexRouter.post(
    "/fonotarot-cl/client/",
    description="Crea un nuevo cliente",
    response_model=schemas.ClientId,
    responses={409: {"model": Message}, 500: {"model": Message}},
    summary="Crea un nuevo cliente",
    dependencies=[Depends(get_db)],
    response_model_exclude_unset=True,
)
def ftc_new_customer(
    cust: schemas.ClientId,
    request: Request,
    uid=Security(loggedin_user, scopes=["audiotex"]),
):
    telefono, tel2 = lee_numero(cust.telefonos[0], request)
    current = (
        models.FTChileClientId.select()
        .where(models.FTChileClientId.ani == telefono)
        .first()
    )
    if current is not None:
        request.app.logger.warning(
            f"El telefono {telefono=} está asociado a otro cliente"
        )
        raise HTTPException(
            status_code=409,
            detail=f"El telefono {telefono=} está asociado a otro cliente",
        )

    try:
        nuevo = models.FTChileClientId.create(
            ani=telefono,
            clientid=models.FTChileClientId.select(
                fn.Max(models.FTChileClientId.clientid)
            ).scalar()
            + 1,
        )
        clientid = nuevo.clientid
        nuevo.save()
    except Exception as error:
        request.app.logger.error(f"{error=}")
        raise HTTPException(
            status_code=500, detail=f"No se pudo insertar el registro: {error}"
        )
    try:
        creditos = models.FTChileCreditos.actualiza(clientid, cust.creditos)
    except Exception as error:
        request.app.logger.error(f"{error=}")
        raise HTTPException(status_code=500, detail="No se pudo agregar los creditos.")
    try:
        models.FTChileNaw.create(clientid=clientid, correo=cust.correo).save()
    except Exception as error:
        request.app.logger.warning(f"{error=}")
        pass

    salida = {
        "creditos": creditos,
        "telefonos": cust.telefonos,
        "clientid": clientid,
        "correo": cust.correo,
    }
    return salida


@audiotexRouter.post(
    "/fonotarot-cl/credit/{clientid}/{segundos}",
    description="Suma Saldo",
    response_model=schemas.Credits,
    responses={409: {"model": Message}, 500: {"model": Message}},
    summary="Suma Saldo",
    dependencies=[Depends(get_db)],
    response_model_exclude_unset=True,
)
def ftc_agrega_saldo(
    clientid: int,
    segundos: int,
    request: Request,
    uid=Security(loggedin_user, scopes=["audiotex"]),
):
    try:
        creditos = models.FTChileCreditos.actualiza(clientid, segundos)
    except Exception as error:
        request.app.logger.error(f"{error=}")
        raise HTTPException(status_code=500, detail="No se pudo agregar los creditos.")

    salida = {"creditos": creditos, "clientid": clientid}
    return salida


@audiotexRouter.get(
    "/fonotarot-cl/phone/{ani}",
    description="Busca informacion de cliente segun ANI",
    response_model=schemas.ClientId,
    responses={404: {"model": Message}},
    summary="Busca informacion de cliente segun ANI",
    dependencies=[Depends(get_db)],
)
def ftc_phone_search(
    ani: str, request: Request, uid=Security(loggedin_user, scopes=["audiotex"])
):
    ani, tel2 = lee_numero(ani, request)
    try:
        telefonos = models.FTChileClientId.busca(ani).get()
    except DoesNotExist as e:
        request.app.logger.warning(f"{ani=} no existe")
        raise HTTPException(status_code=404, detail=f"Teléfono {ani} no existe.")
    else:
        clientid = telefonos.clientid
        info = ftc_clientid_search(clientid, request)
        return info


@audiotexRouter.post(
    "/fonotarot-cl/phone/{clientid}/{ani}",
    description="Inserta telefono al clientid",
    response_model=schemas.ClientId,
    responses={404: {"model": Message}, 409: {"model": Message}},
    summary="Inserta telefono al clientid",
    dependencies=[Depends(get_db)],
)
def ftc_phone_update(
    clientid: int,
    ani: str,
    request: Request,
    uid=Security(loggedin_user, scopes=["audiotex"]),
):
    ani, tel2 = lee_numero(ani, request)
    try:
        models.FTChileClientId.info(clientid).get()
    except DoesNotExist as error:
        request.app.logger.warning(f"{clientid=} no existe")
        raise HTTPException(status_code=404, detail=f"Clientid {clientid} no existe.")

    try:
        models.FTChileClientId.busca(ani).get()
    except DoesNotExist:
        request.app.logger.info(f"{ani=} no existe, creando.")
        models.FTChileClientId.create(clientid=clientid, ani=ani).save()
        info = ftc_clientid_search(clientid, request)
        return info
    else:
        # Por que es un error?
        request.app.logger.warning(f"{ani=}")
        raise HTTPException(
            status_code=409, detail=f"Teléfono {ani} existe en los registros."
        )


##################
# Alotarot
##################
@audiotexRouter.get(
    "/alotarot/client",
    description="Busca clientid",
    response_model=schemas.ClientId,
    responses={404: {"model": Message}},
    summary="Busca clientid",
    dependencies=[Depends(get_db)],
)
def at_user_search(
    request: Request,
    correo: Optional[str] = Query(None, max_length=255),
    telefono: Optional[str] = Query(None, max_length=16),
    uid=Security(loggedin_user, scopes=["audiotex"]),
):
    if telefono:
        telefono, tel2 = lee_numero(telefono, request)

    salida = schemas.ClientId()
    sql_clientid = models.AlotarotClientId.busca(telefono)
    if sql_clientid.count() == 0:
        request.app.logger.warning(f"Telefono<{telefono}>: None")
        raise HTTPException(
            status_code=404,
            detail=f"No se encuentran registros",
        )
    elif sql_clientid.count() == 1:
        clientid = sql_clientid.first()
        salida.clientid = clientid.clientid

    credits = models.AlotarotCreditos.saldo(salida.clientid).get()
    salida.creditos = int(credits.creditos)

    tel = []
    sql_telefonos = models.AlotarotClientId.info(salida.clientid)
    for phone in sql_telefonos:
        tel.append(f"56{phone.ani}")
    salida.telefonos = tel

    return salida


@audiotexRouter.get(
    "/alotarot/client/{clientid}",
    description="Busca informacion del ClientID",
    response_model=schemas.ClientId,
    responses={404: {"model": Message}},
    summary="Información de ClientID",
    dependencies=[Depends(get_db)],
    response_model_exclude_unset=True,
)
def at_clientid_search(
    clientid: int, request: Request, uid=Security(loggedin_user, scopes=["audiotex"])
):
    sql_clientid = models.AlotarotClientId.select().where(
        models.AlotarotClientId.clientid == clientid
    )
    count = sql_clientid.count()
    if count == 0:
        request.app.logger.info(f"{clientid=} not found")
        raise HTTPException(
            status_code=404,
            detail=f"ClientID: {clientid} :: No se encuentra en la base de datos",
        )
    tel = []
    for phone in sql_clientid:
        tel.append(f"56{phone.ani}")
    credits = models.AlotarotCreditos.saldo(clientid).get()

    return {
        "clientid": clientid,
        "creditos": credits.creditos,
        "telefonos": tel,
    }


@audiotexRouter.post(
    "/alotarot/client/",
    description="Crea un nuevo cliente",
    response_model=schemas.ClientId,
    responses={409: {"model": Message}, 500: {"model": Message}},
    summary="Crea un nuevo cliente",
    dependencies=[Depends(get_db)],
    response_model_exclude_unset=True,
)
def at_new_customer(
    cust: schemas.ClientId,
    request: Request,
    uid=Security(loggedin_user, scopes=["audiotex"]),
):
    telefono, tel2 = lee_numero(cust.telefonos[0], request)
    current = (
        models.AlotarotClientId.select()
        .where(models.AlotarotClientId.ani == telefono)
        .first()
    )
    if current:
        request.app.logger.warning(
            f"El telefono {telefono=} está asociado a otro cliente"
        )
        raise HTTPException(
            status_code=409,
            detail=f"El telefono {telefono} está asociado a otro cliente",
        )

    try:
        nuevo = models.AlotarotClientId.create(
            ani=telefono,
            clientid=models.AlotarotClientId.select(
                fn.Max(models.AlotarotClientId.clientid)
            ).scalar()
            + 1,
        )
        clientid = nuevo.clientid
        nuevo.save()
    except Exception as error:
        request.app.logger.error(f"{error=}")
        raise HTTPException(
            status_code=500, detail=f"No se pudo insertar el registro: {error}"
        )
    try:
        creditos = models.AlotarotCreditos.actualiza(clientid, cust.creditos)
    except Exception as error:
        request.app.logger.error(f"{error=}")
        raise HTTPException(status_code=500, detail="No se pudo agregar los creditos.")

    salida = {
        "creditos": creditos,
        "telefonos": cust.telefonos,
        "clientid": clientid,
    }
    return salida


@audiotexRouter.post(
    "/alotarot/credit/{clientid}/{segundos}",
    description="Suma Saldo",
    response_model=schemas.Credits,
    responses={409: {"model": Message}, 500: {"model": Message}},
    summary="Suma Saldo",
    dependencies=[Depends(get_db)],
    response_model_exclude_unset=True,
)
def at_agrega_saldo(
    clientid: int,
    segundos: int,
    request: Request,
    uid=Security(loggedin_user, scopes=["audiotex"]),
):
    try:
        creditos = models.AlotarotCreditos.actualiza(clientid, segundos)
    except Exception as error:
        request.app.logger.error(f"{error=}")
        raise HTTPException(status_code=500, detail="No se pudo agregar los creditos.")

    salida = {"creditos": creditos, "clientid": clientid}
    return salida


@audiotexRouter.get(
    "/alotarot/phone/{ani}",
    description="Busca informacion de cliente segun ANI",
    response_model=schemas.ClientId,
    responses={404: {"model": Message}},
    summary="Busca informacion de cliente segun ANI",
    dependencies=[Depends(get_db)],
)
def at_phone_search(
    ani: str, request: Request, uid=Security(loggedin_user, scopes=["audiotex"])
):
    ani, tel2 = lee_numero(ani, request)
    try:
        telefonos = models.AlotarotClientId.busca(ani).get()
    except DoesNotExist as error:
        request.app.logger.error(f"{error=}")
        raise HTTPException(status_code=404, detail=f"Teléfono {ani} no existe.")
    else:
        clientid = telefonos.clientid
        info = at_clientid_search(clientid, request)
        return info


@audiotexRouter.post(
    "/alotarot/phone/{clientid}/{ani}",
    description="Inserta telefono al clientid",
    response_model=schemas.ClientId,
    responses={404: {"model": Message}, 409: {"model": Message}},
    summary="Inserta telefono al clientid",
    dependencies=[Depends(get_db)],
)
def at_phone_update(
    clientid: int,
    ani: str,
    request: Request,
    uid=Security(loggedin_user, scopes=["audiotex"]),
):
    ani, tel2 = lee_numero(ani, request)
    try:
        models.AlotarotClientId.info(clientid).get()
    except DoesNotExist as error:
        request.app.logger.warning(f"{clientid=} not found")
        raise HTTPException(status_code=404, detail=f"Clientid {clientid} no existe.")

    try:
        models.AlotarotClientId.busca(ani).get()
    except DoesNotExist as error:
        request.app.logger.info(f"{ani=} no existe, creando.")
        models.AlotarotClientId.create(clientid=clientid, ani=ani).save()
        info = at_clientid_search(clientid, request)
        return info
    else:
        # Por que es un error?
        request.app.logger.warning(f"{ani=}")
        raise HTTPException(
            status_code=409, detail=f"Teléfono {ani} existe en los registros."
        )


##################
# Fonotarot Latam
##################
@audiotexRouter.get(
    "/fonotarot-latam/client/{pin}",
    description="Busca informacion del ClientID",
    response_model=schemas.ClientIdLatam,
    responses={404: {"model": Message}},
    summary="Busca informacion del ClientID",
    dependencies=[Depends(get_db)],
    response_model_exclude_unset=True,
)
def ftl_clientid_search(
    pin: int, request: Request, uid=Security(loggedin_user, scopes=["audiotex"])
):
    try:
        cliente = models.FTLatamClient.busca(pin).get()
    except DoesNotExist:
        request.app.logger.warning(f"PIN {pin} no existe.")
        raise HTTPException(status_code=404, detail=f"PIN {pin} no existe.")
    else:
        return model_to_dict(cliente)


@audiotexRouter.post(
    "/fonotarot-latam/client/",
    description="Inserta un nuevo Cliente",
    response_model=schemas.ClientIdLatam,
    responses={409: {"model": Message}},
    summary="Inserta un nuevo Cliente",
    dependencies=[Depends(get_db)],
    response_model_exclude_unset=True,
)
def pin_post(
    cust: schemas.ClientIdLatam,
    request: Request,
    uid=Security(loggedin_user, scopes=["audiotex"]),
):
    if "pin" not in cust or cust.pin == 0 or not cust.pin:
        cust_pin = "".join(secrets.choice(string.digits) for i in range(8))
    else:
        cust_pin = cust.pin

    try:
        new = models.FTLatamClient.create(
            pin=cust_pin,
            correo=cust.correo,
            creditos=cust.creditos,
        )
        new.save()
    except Exception as e:
        request.app.logger.error(e)
        raise HTTPException(status_code=409, detail=f"No se pudo insertar: {e}")

    return model_to_dict(new)


@audiotexRouter.post(
    "/fonotarot-latam/credit/{clientid}/{segundos}",
    description="Suma Saldo",
    response_model=schemas.Credits,
    responses={409: {"model": Message}, 500: {"model": Message}},
    summary="Suma Saldo",
    dependencies=[Depends(get_db)],
    response_model_exclude_unset=True,
)
def ftl_agrega_saldo(
    clientid: int,
    segundos: int,
    request: Request,
    uid=Security(loggedin_user, scopes=["audiotex"]),
):
    try:
        creditos = models.FTLatamClient.actualiza_creditos(clientid, segundos)
    except Exception as e:
        request.app.logger.error(e)
        raise HTTPException(status_code=500, detail="No se pudo agregar los creditos.")

    salida = {"creditos": creditos, "clientid": clientid}
    return salida
