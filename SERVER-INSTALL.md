# Firenze

## Instalación de Firenze

Si poetry da problemas, resolverlo con `export PYTHON_KEYRING_BACKEND=keyring.backends.null.Keyring`

```bash
git init
git branch -m stable
git remote add gitlab git@gitlab.com:fonotarot/firenze.git
git pull gitlab stable
poetry install --with dev,deploy
```

## Instalación del servidor Asterisk

Descargar e instalar la última versión TLS de asterisk <https://www.asterisk.org/downloads/>

```bash
sudo contrib/scripts/install_prereq install
sudo contrib/scripts/install_prereq install-unpackaged
./configure
make menuconfig # Seleccionar LOW_MEM y sonidos (gsm, ulaw, y alaw)
make
sudo make install
sudo make config
sudo make install-logrotate
sudo systemctl enable asterisk
```

Copiar `asterisk_config/*.conf` desde el directorio de instalación de Firenze a `/etc/asterisk`

## Instalación de unixODBC/conector

```bash
sudo apt install odbc-mariadb unixodbc unixodbcinst unixodbc-dev
```

Buscar la ubicación del archivo `libmaodbc.so` y verificar que esté correctamente en `driver_template.ini`

```bash
sudo odbcinst -i -d -f asterisk_config/driver_template.ini
```

Agregar al archivo `/etc/odbc.ini`

```ini
[ODBC]
Debug = 1
DebugFile = /tmp/unixodbc.debug
Trace = 1
TraceFile = /tmp/unixodbc.trace
TraceAutoStop = 0

[cdr-mariadb]
Description=Conexión a CDR de Asterisk
Driver=zvn-mariadb-driver
SERVER=localhost
USER=cdr
DATABASE=zvn_asterisk
PASSWORD=
PORT=3306
AUTO_RECONNECT=1
```

El usuario debe tener acceso solamente a la base de datos `zvn_asterisk`

## Configuración de Asterisk

Es necesario verificar que los archivos de configuración estén correctos

Archivo `/etc/asterisk/res_odbc.conf`

```ini
[cdr-mariadb]
enabled => yes
dsn = cdr-mariadb
pre-connect => yes
max_connections => 2
connect_timeout => 5
logging => yes
slow_query_limit => 5000
```

Archivo `/etc/asterisk/cdr_adaptive_odbc.conf`

```ini
[first]
dsn=cdr-mariadb
table=cdr
```

Archivo `/etc/asterisk/cel_odbc.conf`

```ini
[first]
dsn=cdr-mariadb
table=cel
```
