from django.contrib.auth.tokens import PasswordResetTokenGenerator
import six
#ADD 28/03/23
from django.http import JsonResponse
from datetime import datetime, date
from declaracion.models import InfoPersonalFija
from declaracion.models.catalogos import CatPuestos, CatAreas
from sitio.models import HistoricoAreasPuestos

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver 

class TokenGenerator(PasswordResetTokenGenerator):
    def _make_hash_value(self, user, timestamp):
        return (
            six.text_type(user.pk) + six.text_type(timestamp) +
            six.text_type(user.is_active)
        )
account_activation_token = TokenGenerator()


#ADD 28/03/23
def actualizarHistoricoPuestos(id_info_personal_fija, tipo = None, object= None):
    """
    Función para actualizar la tabla del historico de puestos y áreas
    """

    try:
        info_personal_fija = InfoPersonalFija.objects.get(pk=id_info_personal_fija)
        if tipo == None:
            historico = HistoricoAreasPuestos(info_personal_fija=info_personal_fija, fecha_inicio=date(1950,1,1), id_puesto=info_personal_fija.cat_puestos, 
                                                txt_puesto=info_personal_fija.cat_puestos.puesto, nivel=info_personal_fija.cat_puestos.codigo, 
                                                id_area=info_personal_fija.cat_puestos.cat_areas, txt_area=info_personal_fija.cat_puestos.cat_areas.area,
                                                codigo_area=info_personal_fija.cat_puestos.cat_areas.codigo)
            historico.save()
        else:
            if HistoricoAreasPuestos.objects.filter(info_personal_fija=info_personal_fija, fecha_fin=None).exists():
                historicoAnterior = HistoricoAreasPuestos.objects.get(info_personal_fija=info_personal_fija, fecha_fin=None)
                historicoAnterior.fecha_fin = date.today()
                historicoAnterior.save()
    except Exception as e:
        print("Error al actualizar los datos -----> ",str(e))
    
    try:
        if tipo:
            if tipo == "INFOFIJA":
                historico = HistoricoAreasPuestos(info_personal_fija=info_personal_fija, fecha_inicio=date.today(), id_puesto=object.cat_puestos, 
                                                txt_puesto=object.cat_puestos.puesto, nivel=object.cat_puestos.codigo, 
                                                id_area=object.cat_puestos.cat_areas, txt_area=object.cat_puestos.cat_areas.area,
                                                codigo_area=object.cat_puestos.cat_areas.codigo)
            
            if tipo == "PUESTOS":
                historico = HistoricoAreasPuestos(info_personal_fija=info_personal_fija, fecha_inicio=date.today(), id_puesto=object, 
                                                txt_puesto=object.puesto, nivel=object.codigo, 
                                                id_area=object.cat_areas, txt_area=object.cat_areas.area,
                                                codigo_area=object.cat_areas.codigo)
            
            if tipo == "AREAS":
                historico = HistoricoAreasPuestos(info_personal_fija=info_personal_fija, fecha_inicio=date.today(), id_puesto=info_personal_fija.cat_puestos, 
                                                txt_puesto=info_personal_fija.cat_puestos.puesto, nivel=info_personal_fija.cat_puestos.codigo, 
                                                id_area=object, txt_area=object.area,
                                                codigo_area=object.codigo)
            
            historico.save()
    except Exception as e:
        print("Error al actualizar registro anterior -----> ",str(e))

    return JsonResponse({"guardado": True})


@receiver(pre_save, sender=InfoPersonalFija)
def saveHistoricoInfoFija(sender, instance, **kwargs):
    current = instance

    try:
        previous = InfoPersonalFija.objects.get(pk=instance.pk)
    except Exception as e:
        previous = None
        print("error al consultar InfoPersonalFija--------------------->", e)

    if previous:
        if current.cat_puestos.pk != previous.cat_puestos.pk:
            actualizarHistoricoPuestos(instance.pk,'INFOFIJA', current)

@receiver(post_save, sender=InfoPersonalFija)
def saveHistoricoInfoFijaNuevo(sender, instance, **kwargs):

    try:
        if not HistoricoAreasPuestos.objects.filter(info_personal_fija=instance, fecha_fin=None).exists():
            actualizarHistoricoPuestos(instance.pk, None, None)
    except Exception as e:
        print("error al crear nuevo historico--------------------->", e)

@receiver(pre_save, sender=CatPuestos)
def saveHistoricoPuestos(sender, instance, **kwargs):
    current = instance

    try:
        previous = CatPuestos.objects.get(pk=instance.pk)
    except Exception as e:
        previous = None
        print("error al consultar CatPuestos--------------------->", e)

    if previous:
        if current.puesto != previous.puesto or current.codigo != previous.codigo or current.cat_areas.pk != previous.cat_areas.pk:
            usuarios = InfoPersonalFija.objects.filter(cat_puestos__pk = previous.pk)
            if usuarios:
                for usuario in usuarios:
                    actualizarHistoricoPuestos(usuario.pk, "PUESTOS", current)
        print("---------CAT PUESTOS-----GUARDADO DATO EN HISTORICO-----")
    else:
        print("El puesto será agregado al hisotorico hasta que se relacione con un usuario")


@receiver(pre_save, sender=CatAreas)
def saveHistoricoAreas(sender, instance, **kwargs):
    try:
        current = instance

        try:
            previous = CatAreas.objects.get(pk=instance.pk)
        except Exception as e:
            previous = None
            print("error al consultar CatAreas--------------------->", e)
    
        if previous:
            if current.area != previous.area or current.codigo != previous.codigo:
                try:
                    puestos = CatPuestos.objects.filter(cat_areas__pk = previous.pk)
                except Exception as e:
                    puestos = None
                    print("error al consultar CatPuestos a crear area--------------------->", e)

                if puestos:
                    for puesto in puestos:

                        try:
                            usuarios = InfoPersonalFija.objects.filter(cat_puestos__pk = puesto.pk)
                        except Exception as e:
                            usuarios = None
                            print("error al consultar InfoPersonalFija a crear area--------------------->", e)
                            
                        if usuarios:
                            for usuario in usuarios:
                                actualizarHistoricoPuestos(usuario.pk, "AREAS", current)

            print("---------CAT AREAS-----GUARDADO DATO EN HISTORICO-----")
        else:
            print("El area será agregada al historico hasta que se relacione con un usuario")

    except Exception as e:
        print("Error general----->", e)
