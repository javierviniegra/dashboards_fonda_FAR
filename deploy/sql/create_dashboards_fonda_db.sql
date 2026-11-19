-- deploy/sql/create_dashboards_fonda_db.sql
--
-- Run ONCE as root on the database server 187.251.203.223 (phpMyAdmin > SQL).
-- Replace CHANGE_ME with a real password first (and type that same password
-- when deploy\windows\instalar.ps1 asks for it). Never commit the real one.
--
-- 1. This app's own database (users, branches, cache).
-- 2. The same account may only READ three tables of Central de Reportes'
--    database: the CEDIS customer -> branch mapping, the branches it points to,
--    and the INPC (owner, 2026-11-18: the mapping is read from Central's DB).
--    The indicator sources (Wansoft, Presupuestos AP) are read with Central's
--    existing SELECT-only account `central_reportes` (copied by instalar.ps1).

CREATE DATABASE IF NOT EXISTS dashboards_fonda CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

CREATE USER IF NOT EXISTS 'dashboards_fonda'@'%' IDENTIFIED BY 'CHANGE_ME';
GRANT ALL PRIVILEGES ON `dashboards_fonda`.* TO 'dashboards_fonda'@'%';

GRANT SELECT ON `centraldereportes`.`central_clientecedis` TO 'dashboards_fonda'@'%';
GRANT SELECT ON `centraldereportes`.`cuentas_sucursal`     TO 'dashboards_fonda'@'%';
GRANT SELECT ON `centraldereportes`.`central_inflacion`    TO 'dashboards_fonda'@'%';

FLUSH PRIVILEGES;
