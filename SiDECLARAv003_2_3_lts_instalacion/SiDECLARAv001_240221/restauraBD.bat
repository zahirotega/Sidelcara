
docker cp restore.sql declaraciones_db:/tmp/restore.sql
docker cp ./data-tablas.sql declaraciones_db:/tmp/data-tablas.sql 
docker exec -i declaraciones_db mysql --user=declaracionesus --password=declaracionespass< restore.sql
docker exec -i declaraciones_db mysql --user=declaracionesus --password=declaracionespass declaracionesdb < data-tablas.sql
