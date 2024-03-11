import os, sys, stat, subprocess
import django
from django.conf import settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'declaraciones.settings')
django.setup()
from django.contrib.auth.models import User
# Directorio raíz que deseas explorar
directorio_raiz = './media/declaraciones/'
# Función para recorrer y renombrar archivos
def recorrer_y_renombrar(directorio):
    count = 0
    total_archivos = 0
    for dirpath, dirnames, filenames in os.walk(directorio):
        # Recorre la lista de nombres de archivos y aumenta el conteo
        total_archivos += len(filenames)
    for dirpath, dirnames, filenames in os.walk(directorio):
        for filename in filenames:
            archivo_actual = os.path.join(dirpath, filename)
            splitArchivo = archivo_actual.split("/")
            rfc = splitArchivo[6][0:13]
            usuario = User.objects.get(username=rfc)
            iniciales = splitArchivo[6][0:5] + str(usuario.pk)
            nombreArchivo = splitArchivo[6][13:]
            
            splitArchivo.pop()
            cadena_concatenada = "/".join(splitArchivo)
            # Aquí puedes realizar lógica para determinar el nuevo nombre
            nuevo_nombre = "{}/{}{}".format(cadena_concatenada,iniciales,nombreArchivo)
            #nuevo_path = os.path.join(dirpath, nuevo_nombre)
            # Renombrar el archivo
            os.rename(archivo_actual, nuevo_nombre)
            count = count + 1
            print(f"Renombrado {count} de {total_archivos} : {archivo_actual} -> {nuevo_nombre}")
# Llama a la función para iniciar el proceso de recorrido y renombrado
recorrer_y_renombrar(directorio_raiz)