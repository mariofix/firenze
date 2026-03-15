import logging.config
import logging

import typer
import os
from rich import box
from rich.console import Console
from rich.table import Table
from sqlalchemy import delete, select, update

from firenze.config import LOGGING_CONFIG_CLI
from firenze.database import SessionLocal, engine
from firenze.kvstore import Operator as KVOperator, Migrator
from firenze.models import Operator, OperatorPhone

logging.basicConfig(level=logging.DEBUG)

logging.config.dictConfig(LOGGING_CONFIG_CLI)
logger = logging.getLogger("firenze-cli")
app = typer.Typer()


@app.command("login")
def login(
    ctx: typer.Context, number: int = typer.Argument(..., help="Operator Number")
):
    """
    Login Operator
    """
    session = ctx.obj.get("dbsession")
    logger = ctx.obj.get("logger")

    operator = session.query(Operator).filter_by(number=number).first()

    if operator:
        operator.loggedin = True
        operator.available = True
        session.commit()
        session.refresh(operator)
        print(f"{operator=}")
        if operator.enable_valkey:

            kv_data = KVOperator(
                number=operator.number,
                loggedin=operator.loggedin,
                available=operator.available,
                lastcall=60,
            )
            kv_data.expire(8600)
            kv_data.save()
            print(f"{kv_data=}")
        raise typer.Exit(code=0)


@app.command("logout")
def logout(
    ctx: typer.Context, number: int = typer.Argument(..., help="Operator Number")
):
    """
    Logout Operator
    """
    session = ctx.obj.get("dbsession")
    logger = ctx.obj.get("logger")

    operator = session.query(Operator).filter_by(number=number).first()

    if operator:
        operator.loggedin = False
        operator.available = False
        session.commit()
        session.refresh(operator)
        print(f"{operator=}")
        raise typer.Exit(code=0)


@app.command("change-status")
def change_status(
    ctx: typer.Context,
    number: int = typer.Option(..., help="Operator Number"),
    status: int = typer.Option(..., help="New Status"),
):
    """
    Modify operator status
    """
    session = ctx.obj.get("dbsession")
    logger = ctx.obj.get("logger")

    operator = session.query(Operator).filter_by(number=number).first()

    if operator:
        operator.loggedin = True
        operator.available = True
        session.commit()
        session.refresh(operator)
        print(f"{operator=}")
        if operator.enable_valkey:

            kv_data = KVOperator(
                number=operator.number,
                loggedin=operator.loggedin,
                available=operator.available,
                lastcall=60,
            )
            kv_data.expire(8600)
            kv_data.save()
            print(f"{kv_data=}")
        raise typer.Exit(code=0)


@app.command("list")
def list(
    ctx: typer.Context,
):
    """
    List Operators
    """
    session = ctx.obj.get("dbsession")
    logger = ctx.obj.get("logger")

    operators = session.query(Operator).all()

    table = Table(title="Operators", highlight=True, box=box.ASCII2)

    table.add_column("Numero")
    table.add_column("Nombre")
    table.add_column("Opcion IVR")
    table.add_column("Telefonos")
    table.add_column("Ultima Llamada")
    table.add_column("Ingresado")
    table.add_column("Disponible")
    table.add_column("Ultima Llamada (V)")
    table.add_column("Ingresado (V)")
    table.add_column("Disponible (V)")

    for op in operators:
        data = {}
        table.add_row(
            str(op.number),
            str(op.name),
            str(op.option),
            "\n".join(
                [
                    f"{number.number}/E:{number.enabled}/C:{number.contact}/P:{number.pin}"
                    for number in op.numbers
                ]
            ),
            str(op.lastcall),
            str(op.loggedin),
            str(op.available),
            str(data.get("lastcall", "N/I")),
            str(data.get("loggedin", "N/I")),
            str(data.get("available", "N/I")),
        )

    console = Console()
    console.print(table)


@app.command("info")
def info(
    ctx: typer.Context,
    number: int = typer.Argument(..., help="Operator Number"),
):
    """
    Operator's information
    """
    session = ctx.obj.get("dbsession")
    logger = ctx.obj.get("logger")

    operators = session.query(Operator).all()

    table = Table(title="Operators", highlight=True, box=box.ASCII2)

    table.add_column("Numero")
    table.add_column("Nombre")
    table.add_column("Opcion IVR")
    table.add_column("Telefonos")
    table.add_column("Ultima Llamada")
    table.add_column("Ingresado")
    table.add_column("Disponible")
    table.add_column("Ultima Llamada (V)")
    table.add_column("Ingresado (V)")
    table.add_column("Disponible (V)")

    for op in operators:
        data = {}
        table.add_row(
            str(op.number),
            str(op.name),
            str(op.option),
            "\n".join(
                [
                    f"{number.number}/E:{number.enabled}/C:{number.contact}/P:{number.pin}"
                    for number in op.numbers
                ]
            ),
            str(op.lastcall),
            str(op.loggedin),
            str(op.available),
            str(data.get("lastcall", "N/I")),
            str(data.get("loggedin", "N/I")),
            str(data.get("available", "N/I")),
        )

    console = Console()
    console.print(table)
