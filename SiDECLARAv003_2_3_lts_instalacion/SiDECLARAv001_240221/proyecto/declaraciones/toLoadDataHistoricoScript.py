# -*- coding: utf-8 -*-
import os, sys, stat, subprocess
import django

from datetime import datetime, date

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'declaraciones.settings')
django.setup()

from django.core.exceptions import ObjectDoesNotExist
from declaracion.models.catalogos import CatPuestos
from declaracion.models import InfoPersonalFija, Encargos, Declaraciones
from sitio.util import actualizarHistoricoPuestos
from sitio.models import HistoricoAreasPuestos

def initialData():
    usuariosDeclarantes = InfoPersonalFija.objects.all()
    puestosActivos = CatPuestos.objects.filter(default=0)
    count = 1

    #Cambia el campo default de los puestos
    for puestoInactivo in puestosActivos:
        puestoInactivo.default = 1
        puestoInactivo.save()
    

    for info_fija in usuariosDeclarantes:
        #Se obtienen las declaraciones del declarante
        print("Cargando {} de {}".format(count,len(usuariosDeclarantes)))
        count = count + 1
        
        declaraciones = Declaraciones.objects.filter(info_personal_fija=info_fija.pk)
        for declaracion_usuario in declaraciones:
            #Se obtiene el encargo guardado en la declaración
            encargo = Encargos.objects.filter(declaraciones=declaracion_usuario, cat_puestos__isnull=False,nivel_encargo__isnull=False).first()
            if encargo and encargo.updated_at:
                #Se valida si el ya existe un historico
                try:
                    historico = HistoricoAreasPuestos.objects.get(info_personal_fija=info_fija.pk, id_puesto__pk=encargo.cat_puestos.pk, nivel=encargo.nivel_encargo, fecha_fin=None)
                    
                except ObjectDoesNotExist:

                    try:
                        historicoAnterior = HistoricoAreasPuestos.objects.get(info_personal_fija=info_fija.pk, fecha_fin=None)
                        if historicoAnterior:
                            historicoAnterior.fecha_fin = declaracion_usuario.fecha_recepcion
                            historicoAnterior.save()
                    except ObjectDoesNotExist:
                        print("No existe un registro anterior que actualizar antes de crear uno nuevo para {}".format(info_fija.nombre_completo))

                    historicoN = HistoricoAreasPuestos(info_personal_fija=info_fija, fecha_inicio=declaracion_usuario.fecha_recepcion if declaracion_usuario.fecha_recepcion is not None else date.today(), id_puesto=encargo.cat_puestos, 
                                                        txt_puesto=encargo.cat_puestos.puesto, nivel=encargo.nivel_encargo, 
                                                        id_area=encargo.cat_puestos.cat_areas, txt_area=encargo.cat_puestos.cat_areas.area,
                                                        codigo_area=encargo.cat_puestos.cat_areas.codigo)
                    historicoN.save()


    print("Datos iniciales insertados = ", count)

if __name__ == "__main__":
    initialData()