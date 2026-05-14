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
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"'

# Proxy
forwarded_allow_ips = "*"