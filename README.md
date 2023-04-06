# Proyecto Firenze

Servicio de comunicacion y administracion para servicio Tatot  
Asterisk 18  
Python 3.10 
FastAPI  
SQLAdmin  
Typer

# Instalacion
poetry install --with deploy

# Changelog 
## [Unreleased]
- Que los audios los pueda subir ruurd desde Portal (#1)
- Migrar tablas operativas (#2)

## [1.0.6] - 2023-04-06
### Added
- CORS Middleware


## [1.0.5] - 2023-04-06
### Added
- Endpoint /audiotex/ejecutivos para el plugin de wordpress

### Changed
- Algunos logger.error a logger.warning para que Sentry no se queje tanto


## [1.0.4] - 2022-12-07
### Changed
- Pin se crea aca

### SQL Querys en audiotex
```sql
ALTER TABLE `clientidlat` CHANGE `pin` `pin` VARCHAR(8) NULL DEFAULT NULL;
```

## [1.0.3] - 2022-10-17
### Added
- CLI User Managament
ALTER TABLE `clientidlat` CHANGE `pin` `pin` INT(11) NULL DEFAULT NULL;
## [1.0.2] - 2022-10-14
### Added
- Sumar saldo en FonotarotLatam
- Metodo HEAD para /thanks
- Admin scope

### Changed
- Loggers separados por aplicacion (api, cli)
- Transformacion de numeros en audiotex

## [1.0.1] - 2022-09-27
### Added
- Metodo para buscar clientes en alotarot
- CLI App para asterisk en Typer
- SQLAdmin
- Soporte Python 3.10

### Changed
- Python environment en /opt/zvn-firenze

### Migrated
- Service: Tabla maestra de servicios
- ServiceNumber: DID asignados a cada servicio (1-n)
- DoNotCall: Tabla DNC estandar.
- OnlineCalls: Tabla para las llamadas activas


## [1.0.0] - 2022-07-26
### Changed
- Cambio de nombre a Firenze
- Incorporacion FastAPI para audiotex
- Nueva tabla de llamadas en linea
- Virtualenv en el directorio para facilidad de acceso

### DB Querys
```sql
CREATE TABLE `audiotex`.`clientesonline` (`id` bigint(20) UNSIGNED NOT NULL, `clientid` int(10) UNSIGNED NOT NULL DEFAULT 0, `ani` varchar(16) NOT NULL, `ddi` varchar(16) NOT NULL, `service` varchar(16) NOT NULL, `operator` varchar(4) NOT NULL, `phone` varchar(16) NOT NULL, `time` datetime NOT NULL) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
ALTER TABLE `clientesonline` ADD PRIMARY KEY (`id`);
```


## [prod-0.0.5] - 2022-05-18
### Added
- DID se registra en userfield
- Conexion con Entel
- Grabacion de llamadas

### Changed
- Login/logout cambia campo loggedin
- Número supervisor

## [mejoras-0.0.4] - 2022-02-17
### Added
- Tarotistas pueden ingresar/salir automaticamente
- logger

### Changed
- Nueva tabla de llamadas en linea

### DB Querys
```sql

```

## [peewee-0.0.3] - 2021-12-26
### Changed
- Se reemplaza pymysql por peewee
- Estandarizacion variables asterisk

### DB Querys
```sql
DELETE FROM services where ast_context = ""
```

## [login-0.0.2] - 2021-12-08
### Added
- Consume Saldo

### Changed
- Cambio a Python3.9 y version bump
- Bug en algunos AGI
- Migración a PJSIP
- Nuevos Audios

### Removed
- 

### DB Querys
```sql
ALTER TABLE `operators` ADD `telefono_alternativo` VARCHAR(20) NULL DEFAULT NULL AFTER `telefono`, ADD INDEX `idx_alt_phone` (`telefono_alternativo`);
ALTER TABLE `operators` RENAME INDEX `estado` TO `idx_status`;
```
### Audios
```bash
general/0 bienvenido fonotarot chile.wav = orig-intro-ftchile.wav
general/3 habilitado.wav = orig-no-habilitado.wav
general/5 MENU TAROT.wav = orig-menutarot.wav
general/7 ocupadas intenta mas tarde.m4a = ocupado.ulaw (desde g711.org)
general/8 bienvenido fonotarot latin america.wav = orig-intro-ftlatam.wav

prepago/1.wav = orig-numero-no-reconocido.wav
prepago/3.wav = orig-saldo-insuficiente.wav
prepago/3a.wav = orig-intro-alotarot.wav
prepago/3b.wav = orig-intro-alotarot-info.wav
prepago/4.wav = orig-espere-linea-supervisor.wav
prepago/5.wav = orig-exclusivo.wav
prepago/6.wav = orig-espere-linea.wav

```
## [asterisk-0.0.1] - 2021-06-20
### Added
- Archivo extensions.conf  
- Audios en /var/lib/asterisk/sounds/es/zvn/
- Proyecto Poetry **zvn-agi** (**zvn** en /var/lib/asterisk/agi-bin/)

### Changed
- Cambios en wwwfiles/api-privada_dev/ (modelo audiotex y funciones de API)

### DB Querys
```sql
ALTER TABLE zvn_asterisk.cdr ADD cdrid BIGINT UNSIGNED NOT NULL AUTO_INCREMENT FIRST, ADD PRIMARY KEY (cdrid);
ALTER TABLE zvn_asterisk.cdr DROP INDEX cliente, ADD INDEX cliente (zvn_clientid) USING BTREE;
ALTER TABLE zvn_asterisk.cdr DEFAULT CHARSET=utf8mb4 COLLATE utf8mb4_general_ci;
ALTER TABLE zvn_asterisk.cdr ADD zvn_clientid INT NULL DEFAULT NULL AFTER userfield;
ALTER TABLE audiotex.services ENGINE = INNODB DEFAULT  CHARSET=utf8mb4 COLLATE utf8mb4_general_ci;
ALTER TABLE audiotex.services ADD PRIMARY KEY (ddi);
ALTER TABLE audiotex.services ADD ast_context VARCHAR(255) NOT NULL AFTER service;
-- Cambiar nombre tabla payp a clientidlat y cambiarcharset
DELETE FROM `clientidlat` where clientid > 40;
ALTER TABLE `clientidlat` auto_increment = 41;
ALTER TABLE audiotex.operators ADD `id` INT UNSIGNED NOT NULL AUTO_INCREMENT FIRST, ADD PRIMARY KEY (`id`);
ALTER TABLE audiotex.operators ADD `ast_option` INT NOT NULL DEFAULT '0' AFTER `type`;
ALTER TABLE audiotex.operators ADD `telefono` VARCHAR(20) NULL DEFAULT NULL AFTER `ast_option`;
ALTER TABLE audiotex.operators ENGINE = INNODB DEFAULT CHARSET=utf8mb4 COLLATE utf8mb4_general_ci;
ALTER TABLE audiotex.operators ADD INDEX `estado` (`loggedin`, `available`);
-- Cambio viene de API
DELETE FROM pin WHERE clientid > (SELECT max(clientid) FROM clientid);
DELETE FROM naw WHERE clientid = 434;
ALTER TABLE audiotex.naw ADD PRIMARY KEY (clientid);
```
