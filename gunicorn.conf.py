# gunicorn.conf.py — firenze

bind = "0.0.0.0:9002"
workers = 2
worker_class = "uvicorn.workers.UvicornWorker"

# Process naming
proc_name = "firenze"

# Logging
accesslog = "logs/gunicorn-access.log"
errorlog = "logs/gunicorn-error.log"
loglevel = "info"
logconfig_dict = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "access": {
            "()": "firenze.logging_utils.CombinedAccessFormatter",
            "format": '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"',
        },
        "error": {
            "format": "%(asctime)s [%(process)d] [%(levelname)s] %(message)s",
        },
    },
    "handlers": {
        "access_file": {
            "class": "logging.handlers.TimedRotatingFileHandler",
            "filename": f"{accesslog}",
            "formatter": "access",
            "when": "D",
            "interval": 1,
            "backupCount": 3,
        },
        "error_file": {
            "class": "logging.handlers.TimedRotatingFileHandler",
            "filename": f"{errorlog}",
            "formatter": "error",
            "when": "D",
            "interval": 1,
            "backupCount": 3,
        },
    },
    "loggers": {
        "gunicorn.access": {
            "handlers": ["access_file"],
            "level": f"{loglevel.upper()}",
            "propagate": False,
        },
        "gunicorn.error": {
            "handlers": ["error_file"],
            "level": f"{loglevel.upper()}",
            "propagate": False,
        },
        "uvicorn.access": {
            "handlers": ["access_file"],
            "level": f"{loglevel.upper()}",
            "propagate": False,
        },
        "uvicorn.error": {
            "handlers": ["error_file"],
            "level": f"{loglevel.upper()}",
            "propagate": False,
        },
    },
    "root": {
        "handlers": ["error_file"],
        "level": "WARNING",
    },
}

# Proxy
forwarded_allow_ips = "*"
