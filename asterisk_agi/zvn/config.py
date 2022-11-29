class config_audiotex:
    debug = True

    class database:
        name = "zvn_audiotex_dev"
        hostname = "zvn-dev-db1.cdfzcdggdpd5.sa-east-1.rds.amazonaws.com"
        username = "zvn"
        password = "zvn.r0t5y3"


class config_portal:
    debug = True

    class database:
        name = "zvn_portal_dev"
        hostname = "zvn-dev-db1.cdfzcdggdpd5.sa-east-1.rds.amazonaws.com"
        username = "zvn"
        password = "zvn.r0t5y3"


class config_cdr:
    debug = True

    class database:
        name = ""
        hostname = ""
        username = ""
        password = ""


class config_crm:
    debug = True

    class database:
        name = ""
        hostname = ""
        username = ""
        password = ""

    class api:
        url = ""
        username = ""
        password = ""
        domain = ""
        ua = "zvn-agi/0.0.3 requests/2.26.0"
