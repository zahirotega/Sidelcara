import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "declaraciones.settings")
import django
django.setup()

from declaracion.models.catalogos import CatEntesPublicos
from declaracion.models import InfoPersonalFija

info = InfoPersonalFija.objects.all()
ente = CatEntesPublicos.objects.get(pk = 1)

for i in info:
    i.cat_ente_publico = ente
    i.save()

print('Proceso terminado')