docker cp backuptablas.sh declaraciones_db:/tmp/backuptablas.sh
docker exec -it declaraciones_db sh /tmp/backuptablas.sh
docker cp declaraciones_db:/tmp/data-tablas.sql .
