from marshmallow import Schema, fields



class DncQueryArgsSchema(Schema):
    uniqueid = fields.String(
        load_default=None,
        metadata={"description": "Asterisk UNIQUEID for this call session"},
    )
    channel = fields.String(
        load_default=None,
        metadata={"description": "Asterisk channel name for this call session"},
    )


class DncResponseSchema(Schema):
    dnc = fields.String(required=True, metadata={"description": "YES or NO"})


class DidQueryArgsSchema(Schema):
    uniqueid = fields.String(
        load_default=None,
        metadata={"description": "Asterisk UNIQUEID for this call session"},
    )
    channel = fields.String(
        load_default=None,
        metadata={"description": "Asterisk channel name for this call session"},
    )


class DidLookupResponseSchema(Schema):
    siguiente = fields.String(
        required=True,
        metadata={"description": "Contexto de Asterisk para Goto (\"prepago-service\" para todos los DIDs nuevos)"},
    )
    servicio = fields.String(
        required=True,
        metadata={"description": "Slug del servicio (p. ej. \"alotarot\", \"fonotarot-cl\")"},
    )
    auth_method = fields.String(
        required=True,
        metadata={"description": "\"ani\" o \"pin\""},
    )
    intro_audio = fields.String(
        required=True,
        metadata={"description": "Cadena compatible con Playback (p. ej. \"zvn/intro-alotarot\")"},
    )


class CallInsertFormSchema(Schema):
    service = fields.String(required=True)
    ani = fields.String(required=True)
    did = fields.String(required=True)
    client_id = fields.Integer(required=True)
    operator = fields.Integer(load_default=0)


class CallAssignFormSchema(Schema):
    operator = fields.Integer(
        required=True,
        metadata={"description": "Operator number assigned to this call"},
    )


class CallCloseFormSchema(Schema):
    # Asterisk CURL() only reliably does GET / POST-with-body, so close
    # rides in on a throwaway body field.
    _ = fields.String(load_default="1")


class CallResultSchema(Schema):
    ok = fields.Boolean()
    reason = fields.String(allow_none=True)


class ActiveCallSchema(Schema):
    llamada_activa = fields.String(required=True)



class CreditLimitArgsSchema(Schema):
    seconds = fields.Integer(required=True, metadata={"description": "Credit balance in seconds"})
    uniqueid = fields.String(load_default=None, metadata={"description": "Asterisk UNIQUEID for this call session"})
    channel = fields.String(load_default=None, metadata={"description": "Asterisk channel name for this call session"})

class ClientLookupArgsSchema(Schema):
    service = fields.String(required=True, metadata={"description": "Service slug, e.g. fonotarot-latam"})
    identifier = fields.String(required=True, metadata={"description": "Client identifier (ANI or PIN)"})

class ClientDeductFormSchema(Schema):
    seconds = fields.Integer(required=True, metadata={"description": "Seconds to deduct"})
    operator = fields.String(load_default=None, metadata={"description": "Operator Name"})

class SessionArgsSchema(Schema):
    uniqueid = fields.String(load_default=None, metadata={"description": "Asterisk UNIQUEID for this call session"})
    channel = fields.String(load_default=None, metadata={"description": "Asterisk channel name for this call session"})

class OperatorSelectFormSchema(Schema):
    mode = fields.String(required=True, metadata={"description": '"random" or "option"'})
    selection = fields.String(load_default=None, metadata={"description": "Operator option digits, required when mode=option"})
    client_id = fields.Integer(load_default=None, metadata={"description": "Internal client ID for measurement tracking"})
