import uuid
from django.urls import resolve
from django.views import View
from django.conf import settings
from django.shortcuts import render, redirect
from django.forms.models import model_to_dict
from django.http import HttpResponseRedirect, Http404
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Q
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required
from declaracion.models import (Declaraciones,
                                BienesMuebles,BienesInmuebles, MueblesNoRegistrables,
                                Inversiones, Fideicomisos,ActivosBienes,
                                BienesPersonas, InfoPersonalVar,
                                Secciones, SeccionDeclaracion, InfoPersonalFija, 
                                Observaciones, Domicilios)

from declaracion.forms import (BienesMueblesForm, BienesInmueblesForm,
                               MueblesNoRegistrablesForm, InversionesForm,
                               FideicomisosForm,BienesPersonasForm,
                               ActivosBienesForm, InfoPersonalVarForm,
                               DomiciliosForm, ObservacionesForm)
from declaracion.models.catalogos import (CatMunicipios,CatFormasAdquisiciones, CatTiposRelacionesPersonales,
                                            CatTipoParticipacion,CatTipoPersona,
                                            CatTiposEspecificosInversiones,CatTiposInversiones)

from .declaracion import (DeclaracionDeleteView)
from .utils import (actualizar_aplcia, guardar_estatus, no_aplica, declaracion_datos,
                    validar_declaracion,obtiene_avance,campos_configuracion, get_declaracion_anterior)
from django.contrib import messages
from django.http import JsonResponse
from api.serialize_functions import SECCIONES

import json
from django.template.loader import render_to_string
from django.core import serializers

def listaTiposInversionesEspecificos(request):
    """
    Función que se encarga de filtar los tipo de inversiones especificos de los tipos de inversiones
    """
    tipo_inversion = request.GET.get('tipo_inversion')
    invespecificas = CatTiposEspecificosInversiones.objects.none()
    tipo_inversion_ = CatTiposInversiones.objects.get(pk=tipo_inversion)

    options = '<option value="" selected="selected">Tipo {} ------------------------</option>'.format(tipo_inversion_.tipo_inversion)
    if tipo_inversion:
        invespecificas = CatTiposEspecificosInversiones.objects.filter(cat_tipos_inversiones=tipo_inversion)
    for invesp in invespecificas:
        options += '<option value="%s">%s</option>' % (
            invesp.pk,
            invesp.tipo_especifico_inversion
        )
    response = {}
    response['inversiones_especificas'] = options
    return JsonResponse(response)


def eliminarBienPersona_otraPersona(request):
    """
        Edita datos Nombres,Apellidos, Razón social y RFC de las terceras personas
        de las secciones de Bienes Inmuebles, vehiculos, muebles y fideicomisos
    """

    if request.method == "POST":
        bienPersona = BienesPersonas.objects.get(pk=request.POST.get("bienPersona_id"))
        infoVariable_otraPersona = bienPersona.otra_persona
        tmpObj = ""
        bienes_personas = []

        if bienPersona and infoVariable_otraPersona:
            bienPersona.delete()
            infoVariable_otraPersona.delete()

            #Consulta el el activo bien para obtener las personas que aún tiene relación
            activo_bien = ActivosBienes.objects.get(
                pk=request.POST.get("activo_id"),
                declaraciones=request.POST.get("declaracion"),
                cat_activo_bien_id=ActivosBienes.BIENES_INMUEBLES,
            )

            bienes_personas = BienesPersonas.objects.filter(
                activos_bienes=activo_bien,
                cat_tipo_participacion_id=BienesPersonas.COPROPIETARIO,
            )

            tmpJson = serializers.serialize("json",bienes_personas)
            tmpObj = json.loads(tmpJson)

    return JsonResponse({
        "hecho": True, 
        "dataLength": len(bienes_personas),
        "data": json.dumps(tmpObj),
        "title": request.POST.get("title"),
        "label": request.POST.get("label")
    })

def guardarBienPersona_otraPersona(request):
    if request.method == "POST":
        declaracion = request.POST.get("declaracion")
        bienId = request.POST.get("bienId")
        bienPersonaId = request.POST.get("bienPersonaId")
        otraPersonaId = request.POST.get("editar_id")
        tipoRelacion = int(request.POST.get("tipoRelacion")) if request.POST.get("tipoRelacion") else None
        current_url = request.POST.get("current_url").replace("bienes-", "").upper()
        model = None
        dataOtraPersona_infoVar_existente=None
        cat_tipoParticipacion = None
        tipoParticipacion = request.POST.get("tipoParticipacion")
        tipoParticipacionText = request.POST.get("html_name").split("-")[0].upper()

        #Tipo de bien a buscar
        if current_url == "INMUEBLES":
            model = BienesInmuebles
        if current_url == "MUEBLES":
            model = BienesMuebles
        if current_url == "MUEBLES-NOREGISTRABLES":
            model = MueblesNoRegistrables
        if current_url == "DEUDAS":
            model = DeudasOtros
        if current_url == "INVERSIONES":
            model = Inversiones
        
        data = model.objects.get(pk=bienId,declaraciones=declaracion)
        declaracionModel = Declaraciones.objects.get(pk=declaracion)

        #Tipo de participación de la persona que se agregará
        if tipoParticipacion == "COPROPIETARIO" or (tipoParticipacionText == "COPROPIETARIO" and tipoParticipacion is None):
            #En BienesPersonas > cat_tipo_participacion = 8 = Copropietario
            #En InfoPersonalVar > cat_tipo_persona = 12 = Copropietario
            cat_tipoParticipacion = BienesPersonas.COPROPIETARIO
            cat_tipoPersona = 12
        
        if tipoParticipacion == "PROPIETARIO_ANTERIOR" or (tipoParticipacionText == "PROPIETARIO_ANTERIOR" and tipoParticipacion is None):
            #En BienesPersonas > cat_tipo_participacion = 10 = Propietario anterior
            #En InfoPersonalVar > cat_tipo_persona = 13 = Propietario anterior
            cat_tipoParticipacion = BienesPersonas.PROPIETARIO_ANTERIOR
            cat_tipoPersona = 13

        #Se agrega la persona a InfoVar
        if otraPersonaId:
            dataOtraPersona_infoVar_existente = InfoPersonalVar.objects.get(pk=otraPersonaId)

        infoVar_form = InfoPersonalVarForm(
            request.POST,
            prefix=request.POST.get("tipoParticipacion").lower(),
            instance=dataOtraPersona_infoVar_existente)
        
        persona_infoVar = infoVar_form.save(commit=False)
        persona_infoVar.declaraciones = declaracionModel
        persona_infoVar.cat_tipo_persona_id = cat_tipoPersona
        persona_infoVar.save()

        info_personal_var_declarante = InfoPersonalVar.objects.filter(
            declaraciones=declaracionModel,
            cat_tipo_persona_id=InfoPersonalVar.TIPO_DECLARANTE
        ).first()

        #Se guarda información de la BienPersona
        if dataOtraPersona_infoVar_existente is None:
            bienes_personas, created = BienesPersonas.objects.update_or_create(
                info_personal_var=info_personal_var_declarante,
                otra_persona=persona_infoVar,
                activos_bienes=data.activos_bienes,
                tipo_relacion = CatTiposRelacionesPersonales.objects.get(pk=tipoRelacion) if tipoRelacion else None,
                cat_tipo_participacion_id=cat_tipoParticipacion,
                defaults={'porcentaje': 0},
            )
        else:
            bienes_personas = BienesPersonas.objects.get(pk=bienPersonaId)
            bienes_personas.info_personal_var=info_personal_var_declarante
            bienes_personas.otra_persona=persona_infoVar
            bienes_personas.activos_bienes=data.activos_bienes
            bienes_personas.tipo_relacion = CatTiposRelacionesPersonales.objects.get(pk=tipoRelacion) if tipoRelacion else None
            bienes_personas.cat_tipo_participacion_id=cat_tipoParticipacion
            bienes_personas.defaults={'porcentaje': 0}
            bienes_personas.save()
            
        
        #Se obtienen las personas relacionadas para devolver información a la vista
        bienes_personas = BienesPersonas.objects.filter(
            activos_bienes=data.activos_bienes.pk,
            cat_tipo_participacion_id=cat_tipoParticipacion,
        )

        html = render_to_string('layout/persona_tabla.html', {
            'data': bienes_personas,
            'html_name': request.POST.get("html_name"),
            'declaracion': declaracion,
            'idBien': bienId,
            'label': request.POST.get("label"),
            "title": request.POST.get("title")
        })
    
    return JsonResponse({"Guardado": "Hecho", "htmlTable": html})


class BienesMueblesDeleteView(DeclaracionDeleteView):
    """
    Class BienesMueblesDeleteView elimina los registros del modelo BienesMuebles
    """
    model = BienesMuebles


class BienesMueblesView(View):
    """
    Class BienesMueblesView vista basada en clases, carga y guardar BienesMuebles
    --------

    Methods
    -------
    get(self,request,*args,**kwargs)
        Obtiene la información inicial de la sección y carga los formularios necesarios para ser guardada

    post(self, request, *args, **kwargs)
        Recibe datos ingresados por el usario y son guardados en la base de datos por medio de ORM de Django

    """
    template_name = 'declaracion/activos/bienes-muebles.html'

    @method_decorator(login_required(login_url='/login'))
    def get(self, request, *args, **kwargs):
        """
        Una sección puede estar conformado por más de un modelo y un formulario
        Se inicializan algunos campos con valores predeterminados, frecuentemente serán moneda y entidad federativa
        """
        folio_declaracion = self.kwargs['folio']
        avance, faltas = 0, None
        copropietario_bienes_personas, propietario_anterior_bienes_personas = None, None
        declaracion_previa = False
        encabezados_registros = None
        informacion_registrada_previa = None

        try:
            declaracion_obj = validar_declaracion(request, folio_declaracion)
            avance, faltas = obtiene_avance(declaracion_obj)
        except:
            raise Http404()
        
        aplica = actualizar_aplcia(BienesMuebles, declaracion_obj, SECCIONES["MUEBLES"])

        # Busca información de una declaración previa si es de tipo MODIFICACIÓN/CONCLUSIÓN
        # Solo se obtiene información previa si la declaración actual aún no tiene registro de esta sección
        if declaracion_obj.cat_tipos_declaracion.codigo != 'INICIAL':
            bienes_muebles_data = BienesMuebles.objects.filter(declaraciones=declaracion_obj)            
            if len(bienes_muebles_data) == 0:
                declaracion = get_declaracion_anterior(declaracion_obj)
                if declaracion:
                    declaracion_obj = declaracion
                    declaracion_previa = True
                    encabezados_registros = {
                        'titulo_uno':"TIPO DE OPERACIÓN",
                        'titulo_dos':"Forma de adquisición",
                        'titulo_tres':"Titular"
                    }


        info_personal_var = InfoPersonalVar.objects.filter(
            declaraciones=declaracion_obj,
            cat_tipo_persona_id=InfoPersonalVar.TIPO_DECLARANTE
        ).first()

        agregar, editar_id, bienes_muebles_data, informacion_registrada = (
            declaracion_datos(kwargs, BienesMuebles, declaracion_obj)
        )

        #Se valida si existe una declaración previa
        if declaracion_previa:
            informacion_registrada_previa = informacion_registrada
            informacion_registrada = None
            bienes_muebles_data = None
        
        #Si ya existe información se obtiene y separa la información necesaria
        #frecuentemente observaciones y domicilio o demás datos que pertenezcan a otro formulario que no sea el prinicipal
        if bienes_muebles_data:
            if "pk" in self.kwargs:
                activos_bienes = ActivosBienes.objects.filter(
                    id_activobien=self.kwargs["pk"],
                    declaraciones=declaracion_obj,
                    cat_activo_bien_id=ActivosBienes.BIENES_MUEBLES,
                ).first()
            else:
                activos_bienes = ActivosBienes.objects.filter(
                    declaraciones=declaracion_obj,
                    cat_activo_bien_id=ActivosBienes.BIENES_MUEBLES,
                ).order_by('-id')[0]

            observaciones_data = bienes_muebles_data.observaciones
            bienes_muebles_data = model_to_dict(bienes_muebles_data)
            observaciones_data = model_to_dict(observaciones_data)

            copropietario_bienes_personas = BienesPersonas.objects.filter(
                activos_bienes=activos_bienes,
                cat_tipo_participacion_id=BienesPersonas.COPROPIETARIO,
            )

            if copropietario_bienes_personas:
                copropietario_data = copropietario_bienes_personas.first().otra_persona
                copropietario_data = model_to_dict(copropietario_data)
            else:
                copropietario_data = {}

            propietario_anterior_bienes_personas = BienesPersonas.objects.filter(
                activos_bienes=activos_bienes,
                cat_tipo_participacion_id=BienesPersonas.PROPIETARIO_ANTERIOR,
            )
            if propietario_anterior_bienes_personas:
                propietario_anterior_data = propietario_anterior_bienes_personas.first().otra_persona
                propietario_anterior_data = model_to_dict(propietario_anterior_data)
            else:
                propietario_anterior_data = {}

            declarante_bienes_personas = BienesPersonas.objects.filter(
                activos_bienes=activos_bienes,
                cat_tipo_participacion_id=BienesPersonas.DECLARANTE,
            ).first()

            if declarante_bienes_personas:
                bienes_personas_data = model_to_dict(declarante_bienes_personas)
            else:
                bienes_personas_data = {}

        else:
            bienes_muebles_data = {'cat_monedas':101,'precio_adquisicion':0}
            observaciones_data = {}
            bienes_personas_data = {}
            copropietario_data = {}
            propietario_anterior_data = {}
        
        #Se inicializan los formularios a utilizar que conformen a la sección
        bienes_muebles_form = BienesMueblesForm(
            prefix="bienes_muebles",
            initial=bienes_muebles_data)
        observaciones_form = ObservacionesForm(
            prefix="observaciones",
            initial=observaciones_data)
        bienes_personas_form = BienesPersonasForm(
            prefix="bienes_personas",
            initial=bienes_personas_data)
        copropietario_form = InfoPersonalVarForm(
            prefix="copropietario",
            initial=copropietario_data)
        propietario_anterior_form = InfoPersonalVarForm(
            prefix="propietario_anterior",
            initial=propietario_anterior_data)

        #Se obtiene los campos que serán privados
        current_url = resolve(request.path_info).url_name
        current_url = current_url.replace('-agregar','')
        current_url = current_url.replace('-editar','')
        current_url = current_url.replace('-borrar','')
        seccion = Secciones.objects.filter(url=current_url).first()

        if folio_declaracion:
            try:
                declaracion2 = validar_declaracion(request, folio_declaracion)
            except ObjectDoesNotExist as e:
                raise Http404()
        
        usuario = request.user
        info_per_fija = InfoPersonalFija.objects.filter(usuario=usuario).first()
        puesto = info_per_fija.cat_puestos.codigo

        bienes_personas_form.fields['tipo_relacion'].queryset = CatTiposRelacionesPersonales.objects.filter(grupo_familia=2)


        return render(request, self.template_name, {
            'bienes_muebles_form': bienes_muebles_form,
            'observaciones_form': observaciones_form,
            'bienes_personas_form': bienes_personas_form,
            'copropietario_form': copropietario_form,
            'copropietario_bienes_personas': copropietario_bienes_personas,#ADD Febrero 22
            'propietario_anterior_form': propietario_anterior_form,
            'propietario_anterior_bienes_personas': propietario_anterior_bienes_personas,#ADD Febrero 22
            'folio_declaracion': folio_declaracion,
            'avance':avance,
            'faltas':faltas,
            'informacion_registrada': informacion_registrada,
            'agregar': agregar,
            'bien_id':bienes_muebles_data["id"] if "id" in bienes_muebles_data else None,#ADD Febrero 22
            'aplica':aplica,
            'editar_id': editar_id,
            'declaracion_obj': declaracion_obj, #ADD Marzo 22
            'declaracion_previa': declaracion_previa, #ADD Marzo 22
            'encabezados_registros': encabezados_registros, #ADD Marzo 22
            'informacion_registrada_previa': informacion_registrada_previa, #ADD Marzo 22
            'current_url_seccion': current_url,#ADD Marzo 22
            'current_url': 'declaracion:'+current_url,#ADD Marzo 22
            'campos_privados': campos_configuracion(seccion,'p'),
            'campos_obligatorios': campos_configuracion(seccion,'o'),
            'declaracion2':declaracion2,
            'puesto':puesto,
            'limit_simp':settings.LIMIT_DEC_SIMP
        })

    @method_decorator(login_required(login_url='/login'))
    def post(self, request, *args, **kwargs):
        """
        Obtiene y calcula el avance de la declaración con los datos ingresados
        Redirecciona a la siguiente sección de la declaración
        """
        folio_declaracion = self.kwargs['folio']

        try:
            declaracion = validar_declaracion(request, folio_declaracion)
        except:
            raise Http404()

        info_personal_var = InfoPersonalVar.objects.filter(
            declaraciones=declaracion,
            cat_tipo_persona_id=InfoPersonalVar.TIPO_DECLARANTE
        ).first()

        agregar, editar_id, bienes_muebles_data, informacion_registrada = (
            declaracion_datos(kwargs, BienesMuebles, declaracion)
        )

        #ADD 25/02/22 Se manda llamar función para guardar todos los datos
        if request.POST.get('registrosPrevios', 0):
            self.guardar_registros_previos(request,declaracion,request.POST['registrosPrevios'], kwargs)
            return redirect('declaracion:bienes-muebles', folio=folio_declaracion)
        
        #Debido a que se guardan registros diferentes en activos bienes se obtiene la relación para poder asignarlo a los formularios
        if bienes_muebles_data:
            nuevo_bien = False
            
            if "pk" in self.kwargs:
                activos_bienes = ActivosBienes.objects.filter(
                    id_activobien = self.kwargs["pk"],
                    declaraciones=declaracion,
                    cat_activo_bien_id=ActivosBienes.BIENES_MUEBLES,
                ).order_by('-id')[0]
            else:
                activos_bienes = ActivosBienes.objects.filter(
                    declaraciones=declaracion,
                    cat_activo_bien_id=ActivosBienes.BIENES_MUEBLES,
                ).order_by('-id')[0]

            activos_bienes_id = activos_bienes.pk

            observaciones_data = bienes_muebles_data.observaciones
            declarante_bienes_personas = BienesPersonas.objects.filter(
                activos_bienes=activos_bienes,
                cat_tipo_participacion_id=BienesPersonas.DECLARANTE,
            ).first()

            if declarante_bienes_personas:
                bienes_personas_data = declarante_bienes_personas
            else:
                bienes_personas_data = None

        else:
            bienes_muebles_data = None
            observaciones_data = None
            bienes_personas_data = None
            nuevo_bien = True
        
        #Se asigna por formulario la información correspondiente
        bienes_muebles_form = BienesMueblesForm(
            request.POST,
            prefix="bienes_muebles",
            instance=bienes_muebles_data)
        observaciones_form = ObservacionesForm(
            request.POST,
            prefix="observaciones",
            instance=observaciones_data)
        bienes_personas_form = BienesPersonasForm(
            request.POST,
            prefix="bienes_personas",
            instance=bienes_personas_data)
        copropietario_form = InfoPersonalVarForm(prefix="copropietario")
        propietario_anterior_form = InfoPersonalVarForm(prefix="propietario_anterior")

        if (
            bienes_muebles_form.is_valid() and
            observaciones_form.is_valid() and
            bienes_personas_form.is_valid() 
            ):
            aplica = no_aplica(request)
            observaciones = observaciones_form.save()
            
            #Se guarda individualmente los formularios para posteriormente integrar la información retornada al fomulario principal de la sección
            if aplica:
                #Cuando es un inmueble nuevo siempre se creara------------------------------------------------------------------
                if nuevo_bien:
                    activos_bienes = ActivosBienes(
                        declaraciones=declaracion,
                        cat_activo_bien_id=ActivosBienes.BIENES_MUEBLES,
                    )
                    activos_bienes.save()
                else:
                    activos_bienes, created = ActivosBienes.objects.get_or_create(
                        pk=activos_bienes_id,
                        declaraciones=declaracion,
                        cat_activo_bien_id=ActivosBienes.BIENES_MUEBLES,
                    )

                forma_pago = request.POST.get('forma_pago')
                bienes_muebles_form.precio_adquisicion = 0
                bienes_muebles_form.cat_monedas = 101
                
 
                bienes_muebles = bienes_muebles_form.save(commit=False)

                bienes_muebles.declaraciones = declaracion
                bienes_muebles.observaciones = observaciones
                bienes_muebles.activos_bienes = activos_bienes
                bienes_muebles.save()

                activos_bienes.id_activobien = bienes_muebles.id
                activos_bienes.save()

                bienes_personas = bienes_personas_form.save(commit=False)
                bienes_personas.info_personal_var = info_personal_var
                bienes_personas.activos_bienes = activos_bienes
                bienes_personas.cat_tipo_participacion_id = BienesPersonas.DECLARANTE
                bienes_personas.tipo_relacion = None
                bienes_personas.save()


                if request.POST.get("copropietario-es_fisica_datos"):
                    listDatos = json.loads(request.POST.get("copropietario-es_fisica_datos"))
                    if len(listDatos) > 0:
                        for nuevoData in listDatos:
                            copropietario_form = InfoPersonalVarForm(
                            nuevoData,
                            prefix="copropietario")

                            copropietario = copropietario_form.save(commit=False)
                            copropietario.declaraciones = declaracion
                            copropietario.cat_tipo_persona_id = InfoPersonalVar.TIPO_COPROPIETARIO
                            copropietario.save()

                            copropietario_bienes_personas, created = BienesPersonas.objects.update_or_create(
                                info_personal_var=info_personal_var,
                                otra_persona=copropietario,
                                activos_bienes=activos_bienes,
                                cat_tipo_participacion_id=BienesPersonas.COPROPIETARIO,
                            )
                
                if request.POST.get("propietario_anterior-es_fisica_datos"):
                    listDatos = json.loads(request.POST.get("propietario_anterior-es_fisica_datos"))
                    if len(listDatos) > 0:
                        for nuevoData in listDatos:
                            tipo_relacion_persona = int(nuevoData["propietario_anterior-tipo_relacion"]) if nuevoData["propietario_anterior-tipo_relacion"] != "null" else 29
                            propietario_anterior_form = InfoPersonalVarForm(
                            nuevoData,
                            prefix="propietario_anterior")
                            
                            propietario_anterior = propietario_anterior_form.save(commit=False)
                            propietario_anterior.declaraciones = declaracion
                            propietario_anterior.cat_tipo_persona_id = InfoPersonalVar.TIPO_PROPIETARIO_ANTERIOR
                            propietario_anterior.save()

                            propietario_anterior_bienes_personas, created = BienesPersonas.objects.update_or_create(
                                info_personal_var=info_personal_var,
                                otra_persona=propietario_anterior,
                                activos_bienes=activos_bienes,
                                tipo_relacion = CatTiposRelacionesPersonales.objects.get(pk=tipo_relacion_persona),
                                cat_tipo_participacion_id=BienesPersonas.PROPIETARIO_ANTERIOR,
                            )


            if not agregar and not editar_id:
                status, status_created = guardar_estatus(
                    request,
                    declaracion.folio,
                    SeccionDeclaracion.COMPLETA,
                    aplica=aplica,
                    observaciones=observaciones)

                #Se valida que se completen los datos obligatorios
                seccion_dec = SeccionDeclaracion.objects.get(pk=status.id)
                if seccion_dec.num == 0:
                    seccion_dec.num = 1

                faltantes = seccion_dec.max/seccion_dec.num
                if faltantes != 1.0:
                    messages.warning(request, u"Algunos campos obligatorios de la sección no se completaron pero los datos han sido guardados, favor de completar información más tarde")
                    return redirect('declaracion:bienes-muebles',folio=folio_declaracion)
            

            if request.POST.get("accion") == "guardar_otro":
                return redirect('declaracion:bienes-muebles-agregar', folio=folio_declaracion)
            if request.POST.get("accion") == "guardar_salir":
                return redirect('declaracion:bienes-muebles',folio=folio_declaracion)

            return redirect('declaracion:inversiones',
                            folio=folio_declaracion)

        #Se obtiene la url de la sección para obtener el nombre y que este sea buscado en DB para obtener el ID
        #Esta información es utilizada para obtener la configuración de los campos(obligatorios y privados)
        current_url = resolve(request.path_info).url_name
        current_url = current_url.replace('-agregar','')
        current_url = current_url.replace('-editar','')
        current_url = current_url.replace('-borrar','')
        seccion = Secciones.objects.filter(url=current_url).first()

        usuario = request.user
        info_per_fija = InfoPersonalFija.objects.filter(usuario=usuario).first()
        puesto = info_per_fija.cat_puestos.codigo

        return render(request, self.template_name, {
            'bienes_muebles_form': bienes_muebles_form,
            'observaciones_form': observaciones_form,
            'bienes_personas_form': bienes_personas_form,
            'copropietario_form': copropietario_form,
            'propietario_anterior_form': propietario_anterior_form,
            'folio_declaracion': folio_declaracion,
            'avance':declaracion.avance,
            'informacion_registrada': informacion_registrada,
            'agregar': agregar,
            'editar_id': editar_id,
            'campos_privados': campos_configuracion(seccion,'p'),
            'campos_obligatorios': campos_configuracion(seccion,'o'),
            'puesto':puesto,
            'limit_simp':settings.LIMIT_DEC_SIMP
        })
    
    def guardar_registros_previos(self, request, declaracion, registros, kwargs):
        datosGuardados = True
        datos = json.loads(registros)
        declaracion_anterior = get_declaracion_anterior(declaracion)

        agregar, editar_id, bienes_muebles_data, informacion_registrada = (
            declaracion_datos(kwargs, BienesMuebles, declaracion_anterior)
        )

        for dato in informacion_registrada:
            try:
                if str(dato.pk) in datos:
                    observaciones = Observaciones.objects.get(pk=dato.observaciones.pk)
                    if observaciones:
                        observaciones.pk = None
                        observaciones.save()
                        dato.observaciones = observaciones
                    
                    dato.pk = None
                    dato.declaraciones = declaracion
                    dato.save()

                    activos_bienes = ActivosBienes.objects.get(pk=dato.activos_bienes.pk)
                    if activos_bienes:
                        bienes_personas = BienesPersonas.objects.filter(activos_bienes=activos_bienes)

                        activos_bienes.pk = None
                        activos_bienes.id_activobien = dato.pk
                        activos_bienes.cat_activo_bien_id = ActivosBienes.BIENES_MUEBLES
                        activos_bienes.declaraciones = declaracion

                        #Se guarda el activo bien
                        activos_bienes.save()
                        #Se actualiza el inmueble con el nuevo activo bien
                        dato.activos_bienes = activos_bienes
                        dato.save()
                        
                        for persona in bienes_personas:                            
                            if persona.otra_persona:
                                otra_persona = InfoPersonalVar.objects.get(pk=persona.otra_persona.pk)
                                if otra_persona:
                                    otra_persona.pk = None
                                    otra_persona.declaraciones = declaracion
                                    otra_persona.save()
                                    persona.otra_persona = otra_persona
                            
                            persona.pk = None
                            persona.activos_bienes = activos_bienes
                            persona.save()
            except ObjectDoesNotExist as e:
                datosGuardados =  False
                raise Http404()
        
        if datosGuardados:
            status, status_created = guardar_estatus(
                request,
                declaracion.folio,
                SeccionDeclaracion.COMPLETA)



class BienesInmueblesDeleteView(DeclaracionDeleteView):
    """
    Class BienesInmueblesDeleteView elimina los registros del modelo BienesInmuebles
    """
    model = BienesInmuebles


class BienesInmueblesView(View):
    """
    Class BienesInmueblesView vista basada en clases, carga y guardar BienesInmuebles
    --------

    Methods
    -------
    get(self,request,*args,**kwargs)
        Obtiene la información inicial de la sección y carga los formularios necesarios para ser guardada

    post(self, request, *args, **kwargs)
        Recibe datos ingresados por el usario y son guardados en la base de datos por medio de ORM de Django

    """
    template_name = 'declaracion/activos/bienes-inmuebles.html'

    @method_decorator(login_required(login_url='/login'))
    def get(self, request, *args, **kwargs):
        """
        Una sección puede estar conformado por más de un modelo y un formulario
        Se inicializan algunos campos con valores predeterminados, frecuentemente serán moneda y entidad federativa
        """
        folio_declaracion = self.kwargs['folio']
        avance, faltas = 0, None
        copropietario_bienes_personas, propietario_anterior_bienes_personas = None, None
        declaracion_previa = False
        encabezados_registros = None
        informacion_registrada_previa = None

        try:
            declaracion_obj = validar_declaracion(request, folio_declaracion)
            avance, faltas = obtiene_avance(declaracion_obj)
        except:
            raise Http404()
        
        aplica = actualizar_aplcia(BienesInmuebles, declaracion_obj, SECCIONES["INMUEBLES"])

        # Busca información de una declaración previa si es de tipo MODIFICACIÓN/CONCLUSIÓN
        # Solo se obtiene información previa si la declaración actual aún no tiene registro de esta sección
        if declaracion_obj.cat_tipos_declaracion.codigo != 'INICIAL':
            bienes_inmuebles_data = BienesInmuebles.objects.filter(declaraciones=declaracion_obj)
            if len(bienes_inmuebles_data) == 0:
                declaracion = get_declaracion_anterior(declaracion_obj)            
                if declaracion:
                    declaracion_obj = declaracion
                    declaracion_previa = True
                    encabezados_registros = {
                        'titulo_uno':"TIPO DE OPERACIÓN",
                        'titulo_dos':"Forma de adquisición",
                        'titulo_tres':"Titular"
                    }

        info_personal_var = InfoPersonalVar.objects.filter(
            declaraciones=declaracion_obj,
            cat_tipo_persona_id=InfoPersonalVar.TIPO_DECLARANTE
        ).first()

        agregar, editar_id, bienes_inmuebles_data, informacion_registrada = (
            declaracion_datos(kwargs, BienesInmuebles, declaracion_obj)
        )

        #Se valida si existe una declaración previa
        if declaracion_previa:
            informacion_registrada_previa = informacion_registrada
            informacion_registrada = None
            bienes_inmuebles_data = None
        
        #Si ya existe información se obtiene y separa la información necesaria
        #frecuentemente observaciones y domicilio o demás datos que pertenezcan a otro formulario que no sea el prinicipal
        if bienes_inmuebles_data:
            if "pk" in self.kwargs:
                activos_bienes = ActivosBienes.objects.filter(
                    id_activobien=self.kwargs["pk"],
                    declaraciones=declaracion_obj,
                    cat_activo_bien_id=ActivosBienes.BIENES_INMUEBLES,
                ).first()
            else:
                activos_bienes = ActivosBienes.objects.filter(
                    declaraciones=declaracion_obj,
                    cat_activo_bien_id=ActivosBienes.BIENES_INMUEBLES,
                ).order_by('-id')[0]

            observaciones_data = bienes_inmuebles_data.observaciones
            domicilios_data = bienes_inmuebles_data.domicilios
            bienes_inmuebles_data = model_to_dict(bienes_inmuebles_data)
            observaciones_data = model_to_dict(observaciones_data)
            domicilios_data = model_to_dict(domicilios_data)

            copropietario_bienes_personas = BienesPersonas.objects.filter(
                activos_bienes=activos_bienes,
                cat_tipo_participacion_id=BienesPersonas.COPROPIETARIO,
            )

            if copropietario_bienes_personas:
                copropietario_data = copropietario_bienes_personas.first().otra_persona
                copropietario_data = model_to_dict(copropietario_data)
            else:
                copropietario_data = {}

            propietario_anterior_bienes_personas = BienesPersonas.objects.filter(
                activos_bienes=activos_bienes,
                cat_tipo_participacion_id=BienesPersonas.PROPIETARIO_ANTERIOR,
            )
            if propietario_anterior_bienes_personas:
                propietario_anterior_data = propietario_anterior_bienes_personas.first().otra_persona
                propietario_anterior_data = model_to_dict(propietario_anterior_data)
            else:
                propietario_anterior_data = {}

            declarante_bienes_personas = BienesPersonas.objects.filter(
                activos_bienes=activos_bienes,
                cat_tipo_participacion_id=BienesPersonas.DECLARANTE,
            ).first()

            if declarante_bienes_personas:
                if propietario_anterior_bienes_personas:
                    declarante_bienes_personas.tipo_relacion = propietario_anterior_bienes_personas.first().tipo_relacion

                bienes_personas_data = model_to_dict(declarante_bienes_personas)
            else:
                bienes_personas_data = {}

        else:
            bienes_inmuebles_data = {'cat_monedas':101}
            observaciones_data = {}
            domicilios_data = {}
            bienes_personas_data = {}
            copropietario_data = {}
            propietario_anterior_data = {}
        
        #Se inicializan los formularios a utilizar que conformen a la sección
        bienes_inmuebles_form = BienesInmueblesForm(
            prefix="bienes_inmuebles",
            initial=bienes_inmuebles_data)
        observaciones_form = ObservacionesForm(
            prefix="observaciones",
            initial=observaciones_data)
        domicilio_form = DomiciliosForm(
            prefix="domicilio",
            initial=domicilios_data)
        bienes_personas_form = BienesPersonasForm(
            prefix="bienes_personas",
            initial=bienes_personas_data)
        copropietario_form = InfoPersonalVarForm(
            prefix="copropietario",
            initial=copropietario_data)
        propietario_anterior_form = InfoPersonalVarForm(
            prefix="propietario_anterior",
            initial=propietario_anterior_data)

        if folio_declaracion:
            try:
                declaracion2 = validar_declaracion(request, folio_declaracion)
            except ObjectDoesNotExist as e:
                raise Http404()

        usuario = request.user
        info_per_fija = InfoPersonalFija.objects.filter(usuario=usuario).first()
        puesto = info_per_fija.cat_puestos.codigo

        bienes_personas_form.fields['tipo_relacion'].queryset = CatTiposRelacionesPersonales.objects.filter(grupo_familia=2)

        #Se obtiene los campos que serán privados
        current_url = resolve(request.path_info).url_name
        current_url = current_url.replace('-agregar','')
        current_url = current_url.replace('-editar','')
        current_url = current_url.replace('-borrar','')
        seccion = Secciones.objects.filter(url=current_url).first()

        return render(request, self.template_name, {
            'bienes_inmuebles_form': bienes_inmuebles_form,
            'observaciones_form': observaciones_form,
            'domicilio_form': domicilio_form,
            'bienes_personas_form': bienes_personas_form,
            'copropietario_form': copropietario_form,
            'copropietario_bienes_personas': copropietario_bienes_personas,#ADD Febrero 22
            'propietario_anterior_form': propietario_anterior_form,
            'propietario_anterior_bienes_personas': propietario_anterior_bienes_personas,#ADD Febrero 22
            'folio_declaracion': folio_declaracion,
            'avance':avance,
            'faltas':faltas,
            'aplica':aplica,
            'informacion_registrada': informacion_registrada,
            'agregar': agregar,
            'bien_id':bienes_inmuebles_data["id"] if "id" in bienes_inmuebles_data else None,#ADD Febrero 22
            'declaracion_obj': declaracion_obj, #ADD Marzo 22
            'declaracion_previa': declaracion_previa, #ADD Marzo 22
            'encabezados_registros': encabezados_registros, #ADD Marzo 22
            'informacion_registrada_previa': informacion_registrada_previa, #ADD Marzo 22
            'current_url_seccion': current_url,#ADD Marzo 22
            'current_url': 'declaracion:'+current_url,#ADD Marzo 22
            'editar_id': editar_id,
            'campos_privados': campos_configuracion(seccion,'p'),
            'campos_obligatorios': campos_configuracion(seccion,'o'),
            'declaracion2':declaracion2,
            'puesto':puesto,
            'limit_simp':settings.LIMIT_DEC_SIMP
        })
    
    @method_decorator(login_required(login_url='/login'))
    def post(self, request, *args, **kwargs):
        """
        Obtiene y calcula el avance de la declaración con los datos ingresados
        Redirecciona a la siguiente sección de la declaración
        """
        folio_declaracion = self.kwargs['folio']

        try:
            declaracion = validar_declaracion(request, folio_declaracion)
        except:
            raise Http404()

        info_personal_var = InfoPersonalVar.objects.filter(
            declaraciones=declaracion,
            cat_tipo_persona_id=InfoPersonalVar.TIPO_DECLARANTE
        ).first()

        agregar, editar_id, bienes_inmuebles_data, informacion_registrada = (
            declaracion_datos(kwargs, BienesInmuebles, declaracion)
        )

        #ADD 25/02/22 Se manda llamar función para guardar todos los datos
        if request.POST.get('registrosPrevios', 0):
            self.guardar_registros_previos(request,declaracion,request.POST['registrosPrevios'], kwargs)
            return redirect('declaracion:bienes-inmuebles', folio=folio_declaracion)
        
        if bienes_inmuebles_data:
            nuevo_bien = False
            
            if "pk" in self.kwargs:
                activos_bienes = ActivosBienes.objects.filter(
                    id_activobien = self.kwargs["pk"],
                    declaraciones=declaracion,
                    cat_activo_bien_id=ActivosBienes.BIENES_INMUEBLES,
                ).order_by('-id')[0]
            else:
                activos_bienes = ActivosBienes.objects.filter(
                    declaraciones=declaracion,
                    cat_activo_bien_id=ActivosBienes.BIENES_INMUEBLES,
                ).order_by('-id')[0]

            activos_bienes_id = activos_bienes.pk
            
            if bienes_inmuebles_data:
                observaciones_data = bienes_inmuebles_data.observaciones
                domicilios_data = bienes_inmuebles_data.domicilios
            else:
                bienes_inmuebles_data = None
                observaciones_data = None
                domicilios_data = None

            declarante_bienes_personas = BienesPersonas.objects.filter(
                activos_bienes=activos_bienes,
                cat_tipo_participacion_id=BienesPersonas.DECLARANTE,
            ).first()

            if declarante_bienes_personas:
                bienes_personas_data = declarante_bienes_personas
            else:
                bienes_personas_data = None
        else:
            bienes_inmuebles_data = None
            observaciones_data = None
            domicilios_data = None
            bienes_personas_data = None
            nuevo_bien = True
        
        #Se asigna por formulario la información correspondiente
        bienes_inmuebles_form = BienesInmueblesForm(
            request.POST,
            prefix="bienes_inmuebles",
            instance=bienes_inmuebles_data)
        observaciones_form = ObservacionesForm(
            request.POST,
            prefix="observaciones",
            instance=observaciones_data)
        domicilio_form = DomiciliosForm(
            request.POST,
            prefix="domicilio",
            instance=domicilios_data)
        bienes_personas_form = BienesPersonasForm(
            request.POST,
            prefix="bienes_personas",
            instance=bienes_personas_data)
        info_personal_var_form = InfoPersonalVarForm(
            request.POST,
            prefix="info_personal_var",
            instance=None)

        if(
            bienes_inmuebles_form.is_valid() and
            observaciones_form.is_valid() and
            domicilio_form.is_valid() and
            bienes_personas_form.is_valid() and
            info_personal_var_form.is_valid()
            ):
            aplica = no_aplica(request)
            observaciones = observaciones_form.save()
            
            #Se guarda individualmente los formularios para posteriormente integrar la información retornada al fomulario principal de la sección
            if aplica:
                #Cuando es un inmueble nuevo siempre se creara------------------------------------------------------------------
                if nuevo_bien:
                    activos_bienes = ActivosBienes(
                        declaraciones=declaracion,
                        cat_activo_bien_id=ActivosBienes.BIENES_INMUEBLES,
                    )
                    activos_bienes.save()
                else:
                    activos_bienes, created = ActivosBienes.objects.get_or_create(
                        pk=activos_bienes_id,
                        declaraciones=declaracion,
                        cat_activo_bien_id=ActivosBienes.BIENES_INMUEBLES,
                    )

                bienes_inmuebles = bienes_inmuebles_form.save(commit=False)
                domicilio = domicilio_form.save()

                bienes_inmuebles.declaraciones = declaracion
                bienes_inmuebles.domicilios = domicilio
                bienes_inmuebles.activos_bienes = activos_bienes
                bienes_inmuebles.observaciones = observaciones
                bienes_inmuebles.save()

                activos_bienes.id_activobien = bienes_inmuebles.id
                activos_bienes.save()

                bienes_personas = bienes_personas_form.save(commit=False)
                bienes_personas.info_personal_var = info_personal_var
                bienes_personas.activos_bienes = activos_bienes
                bienes_personas.cat_tipo_participacion_id = BienesPersonas.DECLARANTE
                bienes_personas.tipo_relacion = None
                bienes_personas.save()

                if request.POST.get("copropietario-es_fisica_datos"):
                    listDatos = json.loads(request.POST.get("copropietario-es_fisica_datos"))
                    if len(listDatos) > 0:
                        for nuevoData in listDatos:
                            copropietario_form = InfoPersonalVarForm(
                            nuevoData,
                            prefix="copropietario")

                            copropietario = copropietario_form.save(commit=False)
                            copropietario.declaraciones = declaracion
                            copropietario.cat_tipo_persona_id = InfoPersonalVar.TIPO_COPROPIETARIO
                            copropietario.save()

                            copropietario_bienes_personas, created = BienesPersonas.objects.update_or_create(
                                info_personal_var=info_personal_var,
                                otra_persona=copropietario,
                                activos_bienes=activos_bienes,
                                cat_tipo_participacion_id=BienesPersonas.COPROPIETARIO,
                            )
                
                if request.POST.get("propietario_anterior-es_fisica_datos"):
                    listDatos = json.loads(request.POST.get("propietario_anterior-es_fisica_datos"))
                    if len(listDatos) > 0:
                        for nuevoData in listDatos:
                            tipo_relacion_persona = int(nuevoData["propietario_anterior-tipo_relacion"]) if nuevoData["propietario_anterior-tipo_relacion"] != "null" else 29
                            propietario_anterior_form = InfoPersonalVarForm(
                            nuevoData,
                            prefix="propietario_anterior")
                            
                            propietario_anterior = propietario_anterior_form.save(commit=False)
                            propietario_anterior.declaraciones = declaracion
                            propietario_anterior.cat_tipo_persona_id = InfoPersonalVar.TIPO_PROPIETARIO_ANTERIOR
                            propietario_anterior.save()

                            propietario_anterior_bienes_personas, created = BienesPersonas.objects.update_or_create(
                                info_personal_var=info_personal_var,
                                otra_persona=propietario_anterior,
                                activos_bienes=activos_bienes,
                                tipo_relacion = CatTiposRelacionesPersonales.objects.get(pk=tipo_relacion_persona) if tipo_relacion_persona else tipo_relacion_persona,
                                cat_tipo_participacion_id=BienesPersonas.PROPIETARIO_ANTERIOR,
                            )

            if not agregar and not editar_id:
                status, status_created = guardar_estatus(
                    request,
                    declaracion.folio,
                    SeccionDeclaracion.COMPLETA,
                    aplica=aplica,
                    observaciones=observaciones)

                #Se valida que se completen los datos obligatorios
                seccion_dec = SeccionDeclaracion.objects.get(pk=status.id)
                if seccion_dec.num == 0:
                    seccion_dec.num = 1

                faltantes = seccion_dec.max/seccion_dec.num
                if faltantes != 1.0:
                    messages.warning(request, u"Algunos campos obligatorios de la sección no se completaron pero los datos han sido guardados, favor de completar información más tarde")
                    return redirect('declaracion:bienes-inmuebles',folio=folio_declaracion)
            
            if request.POST.get("accion") == "guardar_otro":
                return redirect('declaracion:bienes-inmuebles-agregar', folio=folio_declaracion)
            if request.POST.get("accion") == "guardar_salir":
                 return redirect('declaracion:bienes-inmuebles',folio=folio_declaracion)

            return redirect('declaracion:muebles-noregistrables',
                            folio=folio_declaracion)

        #Se obtiene la url de la sección para obtener el nombre y que este sea buscado en DB para obtener el ID
        #Esta información es utilizada para obtener la configuración de los campos(obligatorios y privados)
        current_url = resolve(request.path_info).url_name
        current_url = current_url.replace('-agregar','')
        current_url = current_url.replace('-editar','')
        current_url = current_url.replace('-borrar','')
        seccion = Secciones.objects.filter(url=current_url).first()


        usuario = request.user
        info_per_fija = InfoPersonalFija.objects.filter(usuario=usuario).first()
        puesto = info_per_fija.cat_puestos.codigo

        return render(request, self.template_name, {
            'bienes_inmuebles_form': bienes_inmuebles_form,
            'observaciones_form': observaciones_form,
            'domicilio_form': domicilio_form,
            'bienes_personas_form': bienes_personas_form,
            'copropietario_form': copropietario_form,
            'propietario_anterior_form': propietario_anterior_form,
            'folio_declaracion': folio_declaracion,
            'informacion_registrada': informacion_registrada,
            'agregar': agregar,
            'editar_id': editar_id,
            'campos_privados': campos_configuracion(seccion,'p'),
            'campos_obligatorios': campos_configuracion(seccion,'o'),
            'puesto':puesto,
            'limit_simp':settings.LIMIT_DEC_SIMP
        })
    
    def guardar_registros_previos(self, request, declaracion, registros, kwargs):
        datosGuardados = True
        datos = json.loads(registros)
        declaracion_anterior = get_declaracion_anterior(declaracion)

        agregar, editar_id, bienes_inmuebles_data, informacion_registrada = (
            declaracion_datos(kwargs, BienesInmuebles, declaracion_anterior)
        )

        for dato in informacion_registrada:
            try:
                if str(dato.pk) in datos:
                    observaciones = Observaciones.objects.get(pk=dato.observaciones.pk)
                    if observaciones:
                        observaciones.pk = None
                        observaciones.save()
                        dato.observaciones = observaciones
                    
                    domicilio = Domicilios.objects.get(pk=dato.domicilios.pk)
                    if domicilio:
                        domicilio.pk = None
                        domicilio.save()
                        dato.domicilio = domicilio

                    dato.pk = None
                    dato.declaraciones = declaracion
                    dato.save()

                    activos_bienes = ActivosBienes.objects.get(pk=dato.activos_bienes.pk)
                    if activos_bienes:
                        bienes_personas = BienesPersonas.objects.filter(activos_bienes=activos_bienes)

                        activos_bienes.pk = None
                        activos_bienes.id_activobien = dato.pk
                        activos_bienes.cat_activo_bien_id = ActivosBienes.BIENES_INMUEBLES
                        activos_bienes.declaraciones = declaracion

                        #Se guarda el activo bien
                        activos_bienes.save()
                        #Se actualiza el inmueble con el nuevo activo bien
                        dato.activos_bienes = activos_bienes
                        dato.save()
                        
                        for persona in bienes_personas:                            
                            if persona.otra_persona:
                                otra_persona = InfoPersonalVar.objects.get(pk=persona.otra_persona.pk)
                                if otra_persona:
                                    otra_persona.pk = None
                                    otra_persona.declaraciones = declaracion
                                    otra_persona.save()
                                    persona.otra_persona = otra_persona
                            
                            persona.pk = None
                            persona.activos_bienes = activos_bienes
                            persona.save()
            except ObjectDoesNotExist as e:
                datosGuardados =  False
                raise Http404()
        
        if datosGuardados:
            status, status_created = guardar_estatus(
                request,
                declaracion.folio,
                SeccionDeclaracion.COMPLETA)



class MueblesNoRegistrablesDeleteView(DeclaracionDeleteView):
    """
    Class MueblesNoRegistrablesDeleteView elimina los registros del modelo MueblesNoRegistrables(Sección: Vehiculos)
    """
    model = MueblesNoRegistrables


class MueblesNoRegistrablesView(View):
    """
    Class MueblesNoRegistrablesView vista basada en clases, carga y guardar Membresias(Sección: Vehiculos)
    --------

    Methods
    -------
    get(self,request,*args,**kwargs)
        Obtiene la información inicial de la sección y carga los formularios necesarios para ser guardada

    post(self, request, *args, **kwargs)
        Recibe datos ingresados por el usario y son guardados en la base de datos por medio de ORM de Django

    """
    template_name = 'declaracion/activos/muebles-no-registrables.html'

    @method_decorator(login_required(login_url='/login'))
    def get(self, request, *args, **kwargs):
        """
        Una sección puede estar conformado por más de un modelo y un formulario
        Se inicializan algunos campos con valores predeterminados, frecuentemente serán moneda y entidad federativa
        """
        folio_declaracion = self.kwargs['folio']
        avance, faltas = 0, None
        copropietario_bienes_personas, propietario_anterior_bienes_personas = None, None
        declaracion_previa = False
        encabezados_registros = None
        informacion_registrada_previa = None

        try:
            declaracion_obj = validar_declaracion(request, folio_declaracion)
            avance, faltas = obtiene_avance(declaracion_obj)
        except:
            raise Http404()
        
        aplica = actualizar_aplcia(MueblesNoRegistrables, declaracion_obj, SECCIONES["VEHICULOS"])

        # Busca información de una declaración previa si es de tipo MODIFICACIÓN/CONCLUSIÓN
        # Solo se obtiene información previa si la declaración actual aún no tiene registro de esta sección
        if declaracion_obj.cat_tipos_declaracion.codigo != 'INICIAL':
            bienes_inmuebles_data = MueblesNoRegistrables.objects.filter(declaraciones=declaracion_obj)
            if len(bienes_inmuebles_data) == 0:
                declaracion = get_declaracion_anterior(declaracion_obj)
                if declaracion:
                    declaracion_obj = declaracion
                    declaracion_previa = True
                    encabezados_registros = {
                        'titulo_uno':"TIPO DE OPERACIÓN",
                        'titulo_dos':"Forma de adquisición",
                        'titulo_tres':"Titular"
                    }

        info_personal_var = InfoPersonalVar.objects.filter(
            declaraciones=declaracion_obj,
            cat_tipo_persona_id=InfoPersonalVar.TIPO_DECLARANTE
        ).first()

        agregar, editar_id, muebles_no_registrables_data, informacion_registrada = (
            declaracion_datos(kwargs, MueblesNoRegistrables, declaracion_obj)
        )

        #Se valida si existe una declaración previa
        if declaracion_previa:
            informacion_registrada_previa = informacion_registrada
            informacion_registrada = None
            muebles_no_registrables_data = None
        
        #Si ya existe información se obtiene y separa la información necesaria
        #frecuentemente observaciones y domicilio o demás datos que pertenezcan a otro formulario que no sea el prinicipal
        if muebles_no_registrables_data:
            if "pk" in self.kwargs:
                activos_bienes = ActivosBienes.objects.filter(
                    id_activobien=self.kwargs["pk"],
                    declaraciones=declaracion_obj,
                    cat_activo_bien_id=ActivosBienes.MUEBLES_NO_REGISTRABLES,
                ).first()
            else:
                activos_bienes = ActivosBienes.objects.filter(
                    declaraciones=declaracion_obj,
                    cat_activo_bien_id=ActivosBienes.MUEBLES_NO_REGISTRABLES,
                ).order_by('-id')[0]


            domicilios_data = muebles_no_registrables_data.domicilios
            domicilios_data = model_to_dict(domicilios_data)

            observaciones_data = muebles_no_registrables_data.observaciones
            muebles_no_registrables_data = model_to_dict(muebles_no_registrables_data)
            observaciones_data = model_to_dict(observaciones_data)


            copropietario_bienes_personas = BienesPersonas.objects.filter(
                activos_bienes=activos_bienes,
                cat_tipo_participacion_id=BienesPersonas.COPROPIETARIO,
            )

            if copropietario_bienes_personas:
                copropietario_data = copropietario_bienes_personas.first().otra_persona
                copropietario_data = model_to_dict(copropietario_data)
            else:
                copropietario_data = {}

            propietario_anterior_bienes_personas = BienesPersonas.objects.filter(
                activos_bienes=activos_bienes,
                cat_tipo_participacion_id=BienesPersonas.PROPIETARIO_ANTERIOR,
            )
            if propietario_anterior_bienes_personas:
                propietario_anterior_data = propietario_anterior_bienes_personas.first().otra_persona
                propietario_anterior_data = model_to_dict(propietario_anterior_data)
            else:
                propietario_anterior_data = {}

            declarante_bienes_personas = BienesPersonas.objects.filter(
                activos_bienes=activos_bienes,
                cat_tipo_participacion_id=BienesPersonas.DECLARANTE,
            ).first()

            if declarante_bienes_personas:
                bienes_personas_data = model_to_dict(declarante_bienes_personas)
            else:
                bienes_personas_data = {}

        else:
            muebles_no_registrables_data = {'cat_monedas':101}
            observaciones_data = {}
            bienes_personas_data = {}
            copropietario_data = {}
            propietario_anterior_data = {}
            domicilios_data={}

        #Se inicializan los formularios a utilizar que conformen a la sección
        muebles_no_registrables_form = MueblesNoRegistrablesForm(
            prefix="muebles_no_registrables",
            initial=muebles_no_registrables_data)
        observaciones_form = ObservacionesForm(
            prefix="observaciones",
            initial=observaciones_data)
        bienes_personas_form = BienesPersonasForm(
            prefix="bienes_personas",
            initial=bienes_personas_data)
        copropietario_form = InfoPersonalVarForm(
            prefix="copropietario",
            initial=copropietario_data)
        propietario_anterior_form = InfoPersonalVarForm(
            prefix="propietario_anterior",
            initial=propietario_anterior_data)
        domicilio_form = DomiciliosForm(
            prefix="domicilio",
            initial=domicilios_data)
        bienes_personas_form.fields['tipo_relacion'].queryset = CatTiposRelacionesPersonales.objects.filter(grupo_familia=2)

         #Se obtiene los campos que serán privados
        current_url = resolve(request.path_info).url_name
        current_url = current_url.replace('-agregar','')
        current_url = current_url.replace('-editar','')
        current_url = current_url.replace('-borrar','')
        seccion = Secciones.objects.filter(url=current_url).first()

        if folio_declaracion:
            try:
                declaracion2 = validar_declaracion(request, folio_declaracion)
            except ObjectDoesNotExist as e:
                raise Http404()
        usuario = request.user
        info_per_fija = InfoPersonalFija.objects.filter(usuario=usuario).first()
        puesto = info_per_fija.cat_puestos.codigo

        return render(request, self.template_name, {
            'muebles_no_registrables_form': muebles_no_registrables_form,
            'observaciones_form': observaciones_form,
            'bienes_personas_form': bienes_personas_form,
            'copropietario_form': copropietario_form,
            'copropietario_bienes_personas': copropietario_bienes_personas,#ADD Febrero 22
            'propietario_anterior_form': propietario_anterior_form,
            'propietario_anterior_bienes_personas': propietario_anterior_bienes_personas,#ADD Febrero 22
            'folio_declaracion': folio_declaracion,
            'avance':avance,
            'domicilio_form': domicilio_form,
            'faltas':faltas,
            'informacion_registrada': informacion_registrada,
            'agregar': agregar,
            'bien_id':muebles_no_registrables_data["id"] if "id" in muebles_no_registrables_data else None,#ADD  Febrero 22
            'declaracion_obj': declaracion_obj, #ADD Marzo 22
            'declaracion_previa': declaracion_previa, #ADD Marzo 22
            'encabezados_registros': encabezados_registros, #ADD Marzo 22
            'informacion_registrada_previa': informacion_registrada_previa, #ADD Marzo 22
            'current_url_seccion': current_url,#ADD Marzo 22
            'current_url': 'declaracion:'+current_url,#ADD Marzo 22
            'aplica':aplica,
            'editar_id': editar_id,
            'campos_privados': campos_configuracion(seccion,'p'),
            'campos_obligatorios': campos_configuracion(seccion,'o'),
            'declaracion2':declaracion2,
            'puesto':puesto,
            'limit_simp':settings.LIMIT_DEC_SIMP

        })

    @method_decorator(login_required(login_url='/login'))
    def post(self, request, *args, **kwargs):
        """
        Obtiene y calcula el avance de la declaración con los datos ingresados
        Redirecciona a la siguiente sección de la declaración
        """
        folio_declaracion = self.kwargs['folio']
        try:
            declaracion = validar_declaracion(request, folio_declaracion)
        except:
            raise Http404()

        info_personal_var = InfoPersonalVar.objects.filter(
            declaraciones=declaracion,
            cat_tipo_persona_id=InfoPersonalVar.TIPO_DECLARANTE
        ).first()

        agregar, editar_id, muebles_no_registrables_data, informacion_registrada = (
            declaracion_datos(kwargs, MueblesNoRegistrables, declaracion)
        )

        #ADD 25/02/22 Se manda llamar función para guardar todos los datos
        if request.POST.get('registrosPrevios', 0):
            self.guardar_registros_previos(request,declaracion,request.POST['registrosPrevios'], kwargs)
            return redirect('declaracion:muebles-noregistrables', folio=folio_declaracion)

        if muebles_no_registrables_data:
            nuevo_bien = False
            
            if "pk" in self.kwargs:
                activos_bienes = ActivosBienes.objects.filter(
                    id_activobien = self.kwargs["pk"],
                    declaraciones=declaracion,
                    cat_activo_bien_id=ActivosBienes.MUEBLES_NO_REGISTRABLES,
                ).order_by('-id')[0]
            else:
                activos_bienes = ActivosBienes.objects.filter(
                    declaraciones=declaracion,
                    cat_activo_bien_id=ActivosBienes.MUEBLES_NO_REGISTRABLES,
                ).order_by('-id')[0]

            activos_bienes_id = activos_bienes.pk

            observaciones_data = muebles_no_registrables_data.observaciones
            domicilios_data = muebles_no_registrables_data.domicilios

            declarante_bienes_personas = BienesPersonas.objects.filter(
                activos_bienes=activos_bienes,
                cat_tipo_participacion_id=BienesPersonas.DECLARANTE,
            ).first()

            if declarante_bienes_personas:
                bienes_personas_data = declarante_bienes_personas
            else:
                bienes_personas_data = None

            copropietario_bienes_personas = BienesPersonas.objects.filter(
                activos_bienes=activos_bienes,
                cat_tipo_participacion_id=BienesPersonas.COPROPIETARIO,
            ).first()

            if copropietario_bienes_personas:
                copropietario_data = copropietario_bienes_personas.otra_persona
            else:
                copropietario_data = None

            propietario_anterior_bienes_personas = BienesPersonas.objects.filter(
                activos_bienes=activos_bienes,
                cat_tipo_participacion_id=BienesPersonas.PROPIETARIO_ANTERIOR,
            ).order_by('-id')

            if propietario_anterior_bienes_personas:
                propietario_anterior_data = propietario_anterior_bienes_personas[0].otra_persona
            else:
                propietario_anterior_data = None
        else:
            muebles_no_registrables_data = None
            observaciones_data = None
            bienes_personas_data = None
            copropietario_data = None
            propietario_anterior_data = None
            domicilios_data = None
            nuevo_bien = True

        #Se asigna por formulario la información correspondiente
        muebles_no_registrables_form = MueblesNoRegistrablesForm(
            request.POST,
            prefix="muebles_no_registrables",
            instance=muebles_no_registrables_data)
        observaciones_form = ObservacionesForm(
            request.POST,
            prefix="observaciones",
            instance=observaciones_data)
        bienes_personas_form = BienesPersonasForm(
            request.POST,
            prefix="bienes_personas",
            instance=bienes_personas_data)
        domicilio_form = DomiciliosForm(
            request.POST,
            prefix="domicilio",
            instance=domicilios_data)
     
        if (
            muebles_no_registrables_form.is_valid() and
            observaciones_form.is_valid() and
            bienes_personas_form.is_valid()
            ):

            aplica = no_aplica(request)
            observaciones = observaciones_form.save()
            #Se guarda individualmente los formularios para posteriormente integrar la información retornada al fomulario principal de la sección
            if aplica:
                #Cuando es un inmueble nuevo siempre se creara------------------------------------------------------------------
                if nuevo_bien:
                    activos_bienes = ActivosBienes(
                        declaraciones=declaracion,
                        cat_activo_bien_id=ActivosBienes.MUEBLES_NO_REGISTRABLES,
                    )
                    activos_bienes.save()
                else:
                    activos_bienes, created = ActivosBienes.objects.get_or_create(
                        pk=activos_bienes_id,
                        declaraciones=declaracion,
                        cat_activo_bien_id=ActivosBienes.MUEBLES_NO_REGISTRABLES,
                    )

                muebles_no_registrables = muebles_no_registrables_form.save(commit=False)
                domicilio = domicilio_form.save()

                muebles_no_registrables.declaraciones = declaracion
                muebles_no_registrables.activos_bienes = activos_bienes
                muebles_no_registrables.observaciones = observaciones
                muebles_no_registrables.domicilios = domicilio
                muebles_no_registrables.save()

                activos_bienes.id_activobien = muebles_no_registrables.id
                activos_bienes.save()

                bienes_personas = bienes_personas_form.save(commit=False)
                bienes_personas.info_personal_var = info_personal_var
                bienes_personas.activos_bienes = activos_bienes
                bienes_personas.tipo_relacion = None
                bienes_personas.cat_tipo_participacion_id = BienesPersonas.DECLARANTE
                bienes_personas.save()
                
                if request.POST.get("copropietario-es_fisica_datos"):
                    listDatos = json.loads(request.POST.get("copropietario-es_fisica_datos"))
                    if len(listDatos) > 0:
                        for nuevoData in listDatos:
                            copropietario_form = InfoPersonalVarForm(
                            nuevoData,
                            prefix="copropietario")

                            copropietario = copropietario_form.save(commit=False)
                            copropietario.declaraciones = declaracion
                            copropietario.cat_tipo_persona_id = InfoPersonalVar.TIPO_COPROPIETARIO
                            copropietario.save()

                            copropietario_bienes_personas, created = BienesPersonas.objects.update_or_create(
                                info_personal_var=info_personal_var,
                                otra_persona=copropietario,
                                activos_bienes=activos_bienes,
                                cat_tipo_participacion_id=BienesPersonas.COPROPIETARIO,
                            )
                
                if request.POST.get("propietario_anterior-es_fisica_datos"):
                    listDatos = json.loads(request.POST.get("propietario_anterior-es_fisica_datos"))
                    if len(listDatos) > 0:
                        for nuevoData in listDatos:
                            tipo_relacion_persona = int(nuevoData["propietario_anterior-tipo_relacion"]) if nuevoData["propietario_anterior-tipo_relacion"] != "null" else 29
                            propietario_anterior_form = InfoPersonalVarForm(
                            nuevoData,
                            prefix="propietario_anterior")
                            
                            propietario_anterior = propietario_anterior_form.save(commit=False)
                            propietario_anterior.declaraciones = declaracion
                            propietario_anterior.cat_tipo_persona_id = InfoPersonalVar.TIPO_PROPIETARIO_ANTERIOR
                            propietario_anterior.save()

                            propietario_anterior_bienes_personas, created = BienesPersonas.objects.update_or_create(
                                info_personal_var=info_personal_var,
                                otra_persona=propietario_anterior,
                                activos_bienes=activos_bienes,
                                tipo_relacion = CatTiposRelacionesPersonales.objects.get(pk=tipo_relacion_persona),
                                cat_tipo_participacion_id=BienesPersonas.PROPIETARIO_ANTERIOR,
                            )

            if not agregar and not editar_id:
                status, status_created = guardar_estatus(
                    request,
                    declaracion.folio,
                    SeccionDeclaracion.COMPLETA,
                    aplica=aplica,
                    observaciones=observaciones)

                #Se valida que se completen los datos obligatorios
                seccion_dec = SeccionDeclaracion.objects.get(pk=status.id)
                if seccion_dec.num == 0:
                    seccion_dec.num = 1

                faltantes = seccion_dec.max/seccion_dec.num
                if faltantes != 1.0:
                    messages.warning(request, u"Algunos campos obligatorios de la sección no se completaron pero los datos han sido guardados, favor de completar información más tarde")
                    return redirect('declaracion:muebles-noregistrables',folio=folio_declaracion)

            if request.POST.get("accion") == "guardar_otro":
                return redirect('declaracion:muebles-noregistrables-agregar', folio=folio_declaracion)
            if request.POST.get("accion") == "guardar_salir":
                 return redirect('declaracion:muebles-noregistrables',folio=folio_declaracion)

            return redirect('declaracion:bienes-muebles',
                            folio=folio_declaracion)
        
        #Se obtiene la url de la sección para obtener el nombre y que este sea buscado en DB para obtener el ID
        #Esta información es utilizada para obtener la configuración de los campos(obligatorios y privados)
        current_url = resolve(request.path_info).url_name
        current_url = current_url.replace('-agregar','')
        current_url = current_url.replace('-editar','')
        current_url = current_url.replace('-borrar','')
        seccion = Secciones.objects.filter(url=current_url).first()

        usuario = request.user
        info_per_fija = InfoPersonalFija.objects.filter(usuario=usuario).first()
        puesto = info_per_fija.cat_puestos.codigo

        return render(request, self.template_name, {
            'muebles_no_registrables_form': muebles_no_registrables_form,
            'observaciones_form': observaciones_form,
            'domicilio_form': domicilio_form,
            'bienes_personas_form': bienes_personas_form,
            'copropietario_form': copropietario_form,
            'propietario_anterior_form': propietario_anterior_form,
            'folio_declaracion': folio_declaracion,
            'informacion_registrada': informacion_registrada,
            'agregar': agregar,
            'editar_id': editar_id,
            'campos_privados': campos_configuracion(seccion,'p'),
            'campos_obligatorios': campos_configuracion(seccion,'o'),
            'puesto':puesto,
            'limit_simp':settings.LIMIT_DEC_SIMP
        })
    
    def guardar_registros_previos(self, request, declaracion, registros, kwargs):
        datosGuardados = True
        datos = json.loads(registros)
        declaracion_anterior = get_declaracion_anterior(declaracion)

        agregar, editar_id, muebles_no_registrables_data, informacion_registrada = (
            declaracion_datos(kwargs, MueblesNoRegistrables, declaracion_anterior)
        )

        for dato in informacion_registrada:
            try:
                if str(dato.pk) in datos:
                    observaciones = Observaciones.objects.get(pk=dato.observaciones.pk)
                    if observaciones:
                        observaciones.pk = None
                        observaciones.save()
                        dato.observaciones = observaciones
                    
                    domicilio = Domicilios.objects.get(pk=dato.domicilios.pk)
                    if domicilio:
                        domicilio.pk = None
                        domicilio.save()
                        dato.domicilio = domicilio

                    dato.pk = None
                    dato.declaraciones = declaracion
                    dato.save()

                    activos_bienes = ActivosBienes.objects.get(pk=dato.activos_bienes.pk)
                    if activos_bienes:
                        bienes_personas = BienesPersonas.objects.filter(activos_bienes=activos_bienes)

                        activos_bienes.pk = None
                        activos_bienes.id_activobien = dato.pk
                        activos_bienes.cat_activo_bien_id = ActivosBienes.MUEBLES_NO_REGISTRABLES
                        activos_bienes.declaraciones = declaracion

                        #Se guarda el activo bien
                        activos_bienes.save()
                        #Se actualiza el inmueble con el nuevo activo bien
                        dato.activos_bienes = activos_bienes
                        dato.save()
                        
                        for persona in bienes_personas:                            
                            if persona.otra_persona:
                                otra_persona = InfoPersonalVar.objects.get(pk=persona.otra_persona.pk)
                                if otra_persona:
                                    otra_persona.pk = None
                                    otra_persona.declaraciones = declaracion
                                    otra_persona.save()
                                    persona.otra_persona = otra_persona
                            
                            persona.pk = None
                            persona.activos_bienes = activos_bienes
                            persona.save()
            except ObjectDoesNotExist as e:
                datosGuardados =  False
                raise Http404()
        
        if datosGuardados:
            status, status_created = guardar_estatus(
                request,
                declaracion.folio,
                SeccionDeclaracion.COMPLETA)


class InversionesDeleteView(DeclaracionDeleteView):
    """
    Class InversionesDeleteView elimina los registros del modelo Inversiones
    """
    model = Inversiones


class InversionesView(View):
    """
    Class MembresiaView vista basada en clases, carga y guardar Membresias(Sección: ¿PARTICIPA EN LA TOMA DE DECISIONES DE ALGUNA DE ESTAS INSTITUCIONES ?)
    --------

    Methods
    -------
    get(self,request,*args,**kwargs)
        Obtiene la información inicial de la sección y carga los formularios necesarios para ser guardada

    post(self, request, *args, **kwargs)
        Recibe datos ingresados por el usario y son guardados en la base de datos por medio de ORM de Django

    """
    template_name = 'declaracion/activos/inversiones.html'

    @method_decorator(login_required(login_url='/login'))
    def get(self, request, *args, **kwargs):
        """
        Una sección puede estar conformado por más de un modelo y un formulario
        Se inicializan algunos campos con valores predeterminados, frecuentemente serán moneda y entidad federativa
        """
        folio_declaracion = self.kwargs['folio']
        avance, faltas = 0, None
        info_personal_var_data = None
        declaracion_previa = False
        encabezados_registros = None
        informacion_registrada_previa = None

        try:
            declaracion_obj = validar_declaracion(request, folio_declaracion)
            avance, faltas = obtiene_avance(declaracion_obj)
        except:
            raise Http404()
        
        aplica = actualizar_aplcia(Inversiones, declaracion_obj, SECCIONES["INVERSIONES"])
        
        # Busca información de una declaración previa si es de tipo MODIFICACIÓN/CONCLUSIÓN
        # Solo se obtiene información previa si la declaración actual aún no tiene registro de esta sección
        if declaracion_obj.cat_tipos_declaracion.codigo != 'INICIAL':
            inversiones_data = Inversiones.objects.filter(declaraciones=declaracion_obj)
            if len(inversiones_data) == 0:
                declaracion = get_declaracion_anterior(declaracion_obj)
                if declaracion:
                    declaracion_obj = declaracion
                    declaracion_previa = True
                    encabezados_registros = {
                        'titulo_uno':"Tipo de operación",
                        'titulo_dos':"Tipo de inversión",
                        'titulo_tres':"Titular"
                    }

        agregar, editar_id, inversiones_data, informacion_registrada = (
            declaracion_datos(kwargs, Inversiones, declaracion_obj)
        )

        if declaracion_previa:
            informacion_registrada_previa = informacion_registrada
            informacion_registrada = None
            inversiones_data = None
        
        #Si ya existe información se obtiene y separa la información necesaria
        #frecuentemente observaciones y domicilio o demás datos que pertenezcan a otro formulario que no sea el prinicipal
        if inversiones_data:
            observaciones_data = inversiones_data.observaciones
            info_personal_var_data = inversiones_data.info_personal_var
            if info_personal_var_data:
                domicilios_data = info_personal_var_data.domicilios
            else:
                domicilios_data = {}
            observaciones_data = model_to_dict(observaciones_data)
            domicilios_data = model_to_dict(domicilios_data)
            inversiones_data = model_to_dict(inversiones_data)
            info_personal_var_data = model_to_dict(info_personal_var_data)
        else:
            observaciones_data = {}
            domicilios_data = {}
            inversiones_data = {'cat_monedas':101}
            info_personal_var_data = {}
        
        #Se inicializan los formularios a utilizar que conformen a la sección
        inversiones_form = InversionesForm(
            prefix="inversiones",
            initial=inversiones_data)
        observaciones_form = ObservacionesForm(
            prefix="observaciones",
            initial=observaciones_data)
        domicilio_form = DomiciliosForm(
            prefix="domicilio",
            initial=domicilios_data)
        info_personal_var_form = InfoPersonalVarForm(
            prefix="var",
            initial=info_personal_var_data)

        
        
        
        #Se obtiene la url de la sección para obtener el nombre y que este sea buscado en DB para obtener el ID
        #Esta información es utilizada para obtener la configuración de los campos(obligatorios y privados)
        current_url = resolve(request.path_info).url_name
        current_url = current_url.replace('-agregar','')
        current_url = current_url.replace('-editar','')
        current_url = current_url.replace('-borrar','')
        seccion = Secciones.objects.filter(url=current_url).first()

        if folio_declaracion:
            try:
                declaracion2 = validar_declaracion(request, folio_declaracion)
            except ObjectDoesNotExist as e:
                raise Http404()
        usuario = request.user
        info_per_fija = InfoPersonalFija.objects.filter(usuario=usuario).first()
        puesto = info_per_fija.cat_puestos.codigo


        return render(request, self.template_name, {
            'form': inversiones_form,
            'domicilio_form': domicilio_form,
            'observaciones_form': observaciones_form,
            'info_personal_var_form': info_personal_var_form,
            'info_personal_var_data': info_personal_var_data,
            'folio_declaracion': folio_declaracion,
            'avance':avance,
            'faltas':faltas,
            'informacion_registrada': informacion_registrada,
            'agregar': agregar,
            'editar_id': editar_id,
            'aplica':aplica,
            'campos_privados': campos_configuracion(seccion,'p'),
            'campos_obligatorios': campos_configuracion(seccion,'o'),
            'declaracion2':declaracion2,
            'puesto':puesto,
            'declaracion_obj': declaracion_obj, #ADD Marzo 22
            'declaracion_previa': declaracion_previa, #ADD Marzo 22
            'encabezados_registros': encabezados_registros, #ADD Marzo 22
            'informacion_registrada_previa': informacion_registrada_previa, #ADD Marzo 22
            'current_url_seccion': current_url,#ADD Marzo 22
            'current_url': 'declaracion:'+current_url,#ADD Marzo 22
            'limit_simp':settings.LIMIT_DEC_SIMP

        })

    @method_decorator(login_required(login_url='/login'))
    def post(self, request, *args, **kwargs):
        """
        Obtiene y calcula el avance de la declaración con los datos ingresados
        Redirecciona a la siguiente sección de la declaración
        """
        folio_declaracion = self.kwargs['folio']
        avance, faltas = 0, None
        try:
            declaracion = validar_declaracion(request, folio_declaracion)
        except:
            raise Http404()

        agregar, editar_id, inversiones_data, informacion_registrada = (
            declaracion_datos(kwargs, Inversiones, declaracion)
        )

        #ADD 25/02/22 Se manda llamar función para guardar todos los datos
        if request.POST.get('registrosPrevios', 0):
            self.guardar_registros_previos(request,declaracion,folio_declaracion,request.POST['registrosPrevios'], kwargs)
            return redirect('declaracion:inversiones', folio=folio_declaracion)
        
        if inversiones_data:
            observaciones_data = inversiones_data.observaciones
            info_personal_var_data = inversiones_data.info_personal_var
            domicilios_data = info_personal_var_data.domicilios
        else:
            observaciones_data = None
            domicilios_data = None
            inversiones_data = None
            info_personal_var_data = None
        
        #Se asigna por formulario la información correspondiente
        inversiones_form = InversionesForm(
            request.POST,
            prefix="inversiones",
            instance=inversiones_data)
        observaciones_form = ObservacionesForm(
            request.POST,
            prefix="observaciones",
            instance=observaciones_data)
        domicilio_form = DomiciliosForm(
            request.POST,
            prefix="domicilio",
            instance=domicilios_data)
        info_personal_var_form = InfoPersonalVarForm(
            request.POST,
            prefix="var",
            instance=info_personal_var_data)


        inversiones_is_valid = inversiones_form.is_valid()
        observaciones_is_valid = observaciones_form.is_valid()
        domicilio_is_valid = domicilio_form.is_valid()
        info_personal_var_is_valid = info_personal_var_form.is_valid()

        if (inversiones_is_valid and
            observaciones_is_valid and
            domicilio_is_valid and
            info_personal_var_is_valid):

            aplica = no_aplica(request)
            observaciones = observaciones_form.save()
            #Se guarda individualmente los formularios para posteriormente integrar la información retornada al fomulario principal de la sección
            if aplica:
                inversiones = inversiones_form.save(commit=False)
                domicilio = domicilio_form.save()

                info_personal_var = info_personal_var_form.save(commit=False)
                info_personal_var.declaraciones = declaracion
                info_personal_var.domicilios = domicilio
                info_personal_var.cat_tipo_persona_id = 12
                info_personal_var.save()

                inversiones.info_personal_var = info_personal_var
                inversiones.declaraciones = declaracion
                inversiones.observaciones = observaciones
                inversiones.save()

            if not agregar and not editar_id:
                status, status_created = guardar_estatus(
                    request,
                    declaracion.folio,
                    SeccionDeclaracion.COMPLETA,
                    aplica=aplica,
                    observaciones=observaciones)

                #Se valida que se completen los datos obligatorios
                seccion_dec = SeccionDeclaracion.objects.get(pk=status.id)
                if seccion_dec.num == 0:
                    seccion_dec.num = 1

                faltantes = seccion_dec.max/seccion_dec.num
                if faltantes != 1.0:
                    messages.warning(request, u"Algunos campos obligatorios de la sección no se completaron pero los datos han sido guardados, favor de completar información más tarde")
                    return redirect('declaracion:inversiones',folio=folio_declaracion)

            if request.POST.get("accion") == "guardar_otro":
                return redirect('declaracion:inversiones-agregar', folio=folio_declaracion)
            if request.POST.get("accion") == "guardar_salir":
                 return redirect('declaracion:inversiones',folio=folio_declaracion)

            return redirect('declaracion:deudas',
                            folio=folio_declaracion)

        #Se obtiene la url de la sección para obtener el nombre y que este sea buscado en DB para obtener el ID
        #Esta información es utilizada para obtener la configuración de los campos(obligatorios y privados)
        current_url = resolve(request.path_info).url_name
        current_url = current_url.replace('-agregar','')
        current_url = current_url.replace('-editar','')
        current_url = current_url.replace('-borrar','')
        seccion = Secciones.objects.filter(url=current_url).first()

        usuario = request.user
        info_per_fija = InfoPersonalFija.objects.filter(usuario=usuario).first()
        puesto = info_per_fija.cat_puestos.codigo

        return render(request, self.template_name, {
            'form': inversiones_form,
            'observaciones_form': observaciones_form,
            'domicilio_form': domicilio_form,
            'info_personal_var_form': info_personal_var_form,
            'folio_declaracion': folio_declaracion,
            'avance':declaracion.avance,
            'informacion_registrada': informacion_registrada,
            'agregar': agregar,
            'editar_id': editar_id,
            'campos_privados': campos_configuracion(seccion,'p'),
            'campos_obligatorios': campos_configuracion(seccion,'o'),
            'puesto':puesto,
            'limit_simp':settings.LIMIT_DEC_SIMP
        })
    
    def guardar_registros_previos(self, request, declaracion, folio_declaracion, registros, kwargs):
        datosGuardados = True
        datos = json.loads(registros)
        declaracion_anterior = get_declaracion_anterior(declaracion)

        agregar, editar_id, inversiones_data, informacion_registrada = (
            declaracion_datos(kwargs, Inversiones, declaracion_anterior)
        )

        for dato in informacion_registrada:
            try:
                if str(dato.pk) in datos:
                    if dato.observaciones:
                        observaciones = Observaciones.objects.get(pk=dato.observaciones.pk)
                        if observaciones:
                            observaciones.pk = None
                            observaciones.save()
                            dato.observaciones = observaciones
                    
                    if dato.info_personal_var:
                        info_personal_var = InfoPersonalVar.objects.get(pk=dato.info_personal_var.pk)

                        if info_personal_var:
                            info_personal_var.pk = None
                            info_personal_var.declaraciones = declaracion
                            info_personal_var.save()
                            dato.info_personal_var = info_personal_var

                    dato.pk = None
                    dato.declaraciones = declaracion
                    dato.save()
            except ObjectDoesNotExist as e:
                datosGuardados =  False
                raise Http404()
        
        if datosGuardados:
            status, status_created = guardar_estatus(
                request,
                declaracion.folio,
                SeccionDeclaracion.COMPLETA)


class FideicomisosDeleteView(DeclaracionDeleteView):
    """
    Class FideicomisosDeleteView elimina los registros del modelo Fideicomisos
    """
    model = Fideicomisos


class FideicomisosView(View):
    """
    Class FideicomisosView vista basada en clases, carga y guardar Fideicomisos
    --------

    Methods
    -------
    get(self,request,*args,**kwargs)
        Obtiene la información inicial de la sección y carga los formularios necesarios para ser guardada

    post(self, request, *args, **kwargs)
        Recibe datos ingresados por el usario y son guardados en la base de datos por medio de ORM de Django

    """
    template_name = 'declaracion/activos/fideicomisos.html'

    @method_decorator(login_required(login_url='/login'))
    def get(self, request, *args, **kwargs):
        """
        Una sección puede estar conformado por más de un modelo y un formulario
        Se inicializan algunos campos con valores predeterminados, frecuentemente serán moneda y entidad federativa
        """
        folio_declaracion = self.kwargs['folio']
        avance, faltas = 0, None
        declaracion_previa = False
        encabezados_registros = None
        informacion_registrada_previa = None

        try:
            declaracion_obj = validar_declaracion(request, folio_declaracion)
            avance, faltas = obtiene_avance(declaracion_obj)
        except:
            raise Http404()

        aplica = actualizar_aplcia(Fideicomisos, declaracion_obj, SECCIONES["FIDEICOMISOS"])

        # Busca información de una declaración previa si es de tipo MODIFICACIÓN/CONCLUSIÓN
        # Solo se obtiene información previa si la declaración actual aún no tiene registro de esta sección
        if declaracion_obj.cat_tipos_declaracion.codigo != 'INICIAL':
            fideicomisos_data = Fideicomisos.objects.filter(declaraciones=declaracion_obj)
            if len(fideicomisos_data) == 0:
                declaracion = get_declaracion_anterior(declaracion_obj)
                if declaracion:
                    declaracion_obj = declaracion
                    declaracion_previa = True
                    encabezados_registros = {
                        'titulo_uno':"TIPO DE OPERACIÓN",
                        'titulo_dos':"TIPO DE FIDEICOMISO",
                        'titulo_tres':"SECTOR FIDEICOMISO"
                    }

        info_personal_var = InfoPersonalVar.objects.filter(
            declaraciones=declaracion_obj,
            cat_tipo_persona_id=InfoPersonalVar.TIPO_DECLARANTE
        ).first()



        agregar, editar_id, fideicomisos_data, informacion_registrada = (
            declaracion_datos(kwargs, Fideicomisos, declaracion_obj)
        )

        #Se valida si existe una declaración previa
        if declaracion_previa:
            informacion_registrada_previa = informacion_registrada
            informacion_registrada = None
            fideicomisos_data = None
        
        #Si ya existe información se obtiene y separa la información necesaria
        #frecuentemente observaciones y domicilio o demás datos que pertenezcan a otro formulario que no sea el prinicipal
        if fideicomisos_data:
            activos_bienes = ActivosBienes.objects.filter(
                declaraciones=declaracion_obj,
                cat_activo_bien_id=ActivosBienes.FIDEICOMISOS,
            ).first()
            observaciones_data = fideicomisos_data.observaciones
            fideicomisos_data = model_to_dict(fideicomisos_data)
            observaciones_data = model_to_dict(observaciones_data)

            fideicomisario_bienes_personas = BienesPersonas.objects.filter(
                activos_bienes=activos_bienes,
                cat_tipo_participacion_id=BienesPersonas.FIDEICOMISARIO,
            ).first()

            if fideicomisario_bienes_personas:
                fideicomisario_data = fideicomisario_bienes_personas.otra_persona
                domicilio_fideicomisario_data = fideicomisario_data.domicilios
                fideicomisario_data = model_to_dict(fideicomisario_data)
                domicilio_fideicomisario_data = model_to_dict(domicilio_fideicomisario_data)
            else:
                fideicomisario_data = {}
                domicilio_fideicomisario_data = {}

            fideicomitente_bienes_personas = BienesPersonas.objects.filter(
                activos_bienes=activos_bienes,
                cat_tipo_participacion_id=BienesPersonas.FIDEICOMITENTE,
            ).first()

            if fideicomitente_bienes_personas:
                fideicomitente_data = fideicomitente_bienes_personas.otra_persona
                domicilio_fideicomitente_data = fideicomitente_data.domicilios
                fideicomitente_data = model_to_dict(fideicomitente_data)
                domicilio_fideicomitente_data = model_to_dict(domicilio_fideicomitente_data)
            else:
                fideicomitente_data = {}
                domicilio_fideicomitente_data = {}


            fiduciario_bienes_personas = BienesPersonas.objects.filter(
                activos_bienes=activos_bienes,
                cat_tipo_participacion_id=BienesPersonas.FIDUCIARIO,
            ).first()

            if fiduciario_bienes_personas:
                fiduciario_data = fiduciario_bienes_personas.otra_persona
                domicilio_fiduciario_data = fiduciario_data.domicilios
                fiduciario_data = model_to_dict(fiduciario_data)
                domicilio_fiduciario_data = model_to_dict(domicilio_fiduciario_data)
            else:
                fiduciario_data = {}
                domicilio_fiduciario_data = {}

        else:
            fideicomisario_data = {}
            fideicomitente_data = {}
            fiduciario_data = {}
            domicilio_fideicomitente_data = {}
            domicilio_fideicomisario_data = {}
            domicilio_fiduciario_data = {}
            fideicomisos_data = {}
            observaciones_data = {}

        #Se inicializan los formularios a utilizar que conformen a la sección
        fideicomisario_form = InfoPersonalVarForm(
            prefix="fideicomisario",
            initial=fideicomisario_data)
        fideicomitente_form = InfoPersonalVarForm(
            prefix="fideicomitente",
            initial=fideicomitente_data)
        fiduciario_form = InfoPersonalVarForm(
            prefix="fiduciario",
            initial=fiduciario_data)
        domicilio_fideicomitente_form = DomiciliosForm(
            prefix="domicilio_fideicomitente",
            initial=domicilio_fideicomitente_data)
        domicilio_fideicomisario_form = DomiciliosForm(
            prefix="domicilio_fideicomisario",
            initial=domicilio_fideicomisario_data)
        domicilio_fiduciario_form = DomiciliosForm(
            prefix="domicilio_fiduciario",
            initial=domicilio_fiduciario_data)
        fideicomisos_form = FideicomisosForm(
            prefix="fideicomisos",
            initial=fideicomisos_data)
        observaciones_form = ObservacionesForm(
            prefix="observaciones",
            initial=observaciones_data)
        if folio_declaracion:
            try:
                declaracion2 = validar_declaracion(request, folio_declaracion)
            except ObjectDoesNotExist as e:
                raise Http404()

        usuario = request.user
        info_per_fija = InfoPersonalFija.objects.filter(usuario=usuario).first()
        puesto = info_per_fija.cat_puestos.codigo


        #Se obtiene la url de la sección para obtener el nombre y que este sea buscado en DB para obtener el ID
        #Esta información es utilizada para obtener la configuración de los campos(obligatorios y privados)
        current_url = resolve(request.path_info).url_name
        current_url = current_url.replace('-agregar','')
        current_url = current_url.replace('-editar','')
        current_url = current_url.replace('-borrar','')
        seccion = Secciones.objects.filter(url=current_url).first()

        return render(request, self.template_name, {
            'fideicomisos_form': fideicomisos_form,
            'fideicomisario_form': fideicomisario_form,
            'fideicomitente_form': fideicomitente_form,
            'fiduciario_form': fiduciario_form,
            'domicilio_fideicomitente_form': domicilio_fideicomitente_form,
            'domicilio_fideicomisario_form': domicilio_fideicomisario_form,
            'domicilio_fiduciario_form': domicilio_fiduciario_form,
            'observaciones_form': observaciones_form,
            'folio_declaracion': folio_declaracion,
            'avance':avance,
            'aplica':aplica,
            'faltas':faltas,
            'informacion_registrada': informacion_registrada,
            'agregar': agregar,
            'editar_id': editar_id,
            'campos_privados': campos_configuracion(seccion,'p'),
            'campos_obligatorios': campos_configuracion(seccion,'o'),
            'declaracion2':declaracion2,
            'puesto':puesto,
            'declaracion_obj': declaracion_obj, #ADD Marzo 22
            'declaracion_previa': declaracion_previa, #ADD Marzo 22
            'encabezados_registros': encabezados_registros, #ADD Marzo 22
            'informacion_registrada_previa': informacion_registrada_previa, #ADD Marzo 22
            'current_url_seccion': current_url,#ADD Marzo 22
            'current_url': 'declaracion:'+current_url,#ADD Marzo 22
            'limit_simp':settings.LIMIT_DEC_SIMP
        })

    @method_decorator(login_required(login_url='/login'))
    def post(self, request, *args, **kwargs):
        """
        Obtiene y calcula el avance de la declaración con los datos ingresados
        Redirecciona a la siguiente sección de la declaración
        """
        folio_declaracion = self.kwargs['folio']
        try:
            declaracion = validar_declaracion(request, folio_declaracion)
        except:
            raise Http404()

        info_personal_var = InfoPersonalVar.objects.filter(
            declaraciones=declaracion,
            cat_tipo_persona_id=1
        ).first()

        agregar, editar_id, fideicomisos_data, informacion_registrada = (
            declaracion_datos(kwargs, Fideicomisos, declaracion)
        )

        #ADD 25/02/22 Se manda llamar función para guardar todos los datos
        if request.POST.get('registrosPrevios', 0):
            self.guardar_registros_previos(request,declaracion,request.POST['registrosPrevios'], kwargs)
            return redirect('declaracion:fideicomisos', folio=folio_declaracion)

        if fideicomisos_data:
            activos_bienes = ActivosBienes.objects.filter(
                declaraciones=declaracion,
                cat_activo_bien_id=ActivosBienes.FIDEICOMISOS,
            ).first()
            observaciones_data = fideicomisos_data.observaciones

            fideicomisario_bienes_personas = BienesPersonas.objects.filter(
                activos_bienes=activos_bienes,
                cat_tipo_participacion_id=BienesPersonas.FIDEICOMISARIO,
            ).first()

            if fideicomisario_bienes_personas:
                fideicomisario_data = fideicomisario_bienes_personas.otra_persona
                domicilio_fideicomisario_data = fideicomisario_data.domicilios
            else:
                fideicomisario_data = None
                domicilio_fideicomisario_data = None

            fideicomitente_bienes_personas = BienesPersonas.objects.filter(
                activos_bienes=activos_bienes,
                cat_tipo_participacion_id=BienesPersonas.FIDEICOMITENTE,
            ).first()

            if fideicomitente_bienes_personas:
                fideicomitente_data = fideicomitente_bienes_personas.otra_persona
                domicilio_fideicomitente_data = fideicomitente_data.domicilios
            else:
                fideicomitente_data = None
                domicilio_fideicomitente_data = None

            fiduciario_bienes_personas = BienesPersonas.objects.filter(
                activos_bienes=activos_bienes,
                cat_tipo_participacion_id=BienesPersonas.FIDUCIARIO,
            ).first()

            if fiduciario_bienes_personas:
                fiduciario_data = fiduciario_bienes_personas.otra_persona
                domicilio_fiduciario_data = fiduciario_data.domicilios
            else:
                fiduciario_data = None
                domicilio_fiduciario_data = None

        else:
            fideicomisario_data = None
            fideicomitente_data = None
            fiduciario_data = None
            domicilio_fideicomitente_data = None
            domicilio_fideicomisario_data = None
            domicilio_fiduciario_data = None
            fideicomisos_data = None
            observaciones_data = None

        #Se asigna por formulario la información correspondiente
        fideicomisario_form = InfoPersonalVarForm(
            request.POST,
            prefix="fideicomisario",
            instance=fideicomisario_data)
        fideicomitente_form = InfoPersonalVarForm(
            request.POST,
            prefix="fideicomitente",
            instance=fideicomitente_data)
        fiduciario_form = InfoPersonalVarForm(
            request.POST,
            prefix="fiduciario",
            instance=fiduciario_data)
        domicilio_fideicomitente_form = DomiciliosForm(
            request.POST,
            prefix="domicilio_fideicomitente",
            instance=domicilio_fideicomitente_data)
        domicilio_fideicomisario_form = DomiciliosForm(
            request.POST,
            prefix="domicilio_fideicomisario",
            instance=domicilio_fideicomisario_data)
        domicilio_fiduciario_form = DomiciliosForm(
            request.POST,
            prefix="domicilio_fiduciario",
            instance=domicilio_fiduciario_data)
        fideicomisos_form = FideicomisosForm(
            request.POST,
            prefix="fideicomisos",
            instance=fideicomisos_data)
        observaciones_form = ObservacionesForm(
            request.POST,
            prefix="observaciones",
            instance=observaciones_data)

        if (fideicomisario_form.is_valid() and
            fideicomitente_form.is_valid() and
            fiduciario_form.is_valid() and
            domicilio_fideicomitente_form.is_valid() and
            domicilio_fideicomisario_form.is_valid() and
            domicilio_fiduciario_form.is_valid() and
            fideicomisos_form.is_valid() and
            observaciones_form.is_valid()):

            aplica = no_aplica(request)
            observaciones = observaciones_form.save()

            #Se guarda individualmente los formularios para posteriormente integrar la información retornada al fomulario principal de la sección
            if aplica:
                fideicomisos = fideicomisos_form.save(commit=False)

                domicilio_fideicomitente = domicilio_fideicomitente_form.save()
                domicilio_fideicomisario = domicilio_fideicomisario_form.save()
                domicilio_fiduciario = domicilio_fiduciario_form.save()

                fideicomisario = fideicomisario_form.save(commit=False)
                fideicomitente = fideicomitente_form.save(commit=False)
                fiduciario = fiduciario_form.save(commit=False)

                fideicomisario.domicilios = domicilio_fideicomisario
                fideicomisario.cat_tipo_persona_id = 8
                fideicomisario.declaraciones = declaracion
                fideicomisario.save()
                fideicomitente.domicilios = domicilio_fideicomitente
                fideicomitente.cat_tipo_persona_id = 9
                fideicomitente.declaraciones = declaracion
                fideicomitente.save()
                fiduciario.domicilios = domicilio_fiduciario
                fiduciario.cat_tipo_persona_id = 10
                fiduciario.declaraciones = declaracion
                fiduciario.save()


                activos_bienes, created = ActivosBienes.objects.update_or_create(
                    declaraciones=declaracion,
                    cat_activo_bien_id=ActivosBienes.FIDEICOMISOS,
                )

                fideicomisos.observaciones = observaciones
                fideicomisos.activos_bienes = activos_bienes
                fideicomisos.declaraciones = declaracion
                fideicomisos.save()

                activos_bienes.id_activobien = fideicomisos.id
                activos_bienes.save()

                fideicomisario_bienes_personas, created = BienesPersonas.objects.update_or_create(
                    info_personal_var=info_personal_var,
                    otra_persona=fideicomisario,
                    activos_bienes=activos_bienes,
                    cat_tipo_participacion_id=BienesPersonas.FIDEICOMISARIO,
                )

                fideicomitente_bienes_personas, created = BienesPersonas.objects.update_or_create(
                    info_personal_var=info_personal_var,
                    otra_persona=fideicomitente,
                    activos_bienes=activos_bienes,
                    cat_tipo_participacion_id=BienesPersonas.FIDEICOMITENTE,
                )

                fiduciario_bienes_personas, created = BienesPersonas.objects.update_or_create(
                    info_personal_var=info_personal_var,
                    otra_persona=fiduciario,
                    activos_bienes=activos_bienes,
                    cat_tipo_participacion_id=BienesPersonas.FIDUCIARIO,
                )

            if not agregar and not editar_id:
                status, status_created = guardar_estatus(
                    request,
                    declaracion.folio,
                    SeccionDeclaracion.COMPLETA,
                    aplica=aplica,
                    observaciones=observaciones)

                #Se valida que se completen los datos obligatorios
                seccion_dec = SeccionDeclaracion.objects.get(pk=status.id)
                if seccion_dec.num == 0:
                    seccion_dec.num = 1

                faltantes = seccion_dec.max/seccion_dec.num
                if faltantes != 1.0:
                    messages.warning(request, u"Algunos campos obligatorios de la sección no se completaron pero los datos han sido guardados, favor de completar información más tarde")
                    return redirect('declaracion:fideicomisos',folio=folio_declaracion)

            if request.POST.get("accion") == "guardar_otro":
                return redirect('declaracion:fideicomisos-agregar', folio=folio_declaracion)
            if request.POST.get("accion") == "guardar_salir":
                return redirect('declaracion:fideicomisos',folio=folio_declaracion)

            return redirect('declaracion:declaracion-fiscal',
                            folio=folio_declaracion)

            #return redirect('declaracion:confirmar-allinone',
            #                folio=folio_declaracion)

        #Se obtiene la url de la sección para obtener el nombre y que este sea buscado en DB para obtener el ID
        #Esta información es utilizada para obtener la configuración de los campos(obligatorios y privados)
        current_url = resolve(request.path_info).url_name
        current_url = current_url.replace('-agregar','')
        current_url = current_url.replace('-editar','')
        current_url = current_url.replace('-borrar','')
        seccion = Secciones.objects.filter(url=current_url).first()

        usuario = request.user
        info_per_fija = InfoPersonalFija.objects.filter(usuario=usuario).first()
        puesto = info_per_fija.cat_puestos.codigo
        
        return render(request, self.template_name, {
            'fideicomisos_form': fideicomisos_form,
            'fideicomisario_form': fideicomisario_form,
            'fideicomitente_form': fideicomitente_form,
            'fiduciario_form': fiduciario_form,
            'domicilio_fideicomitente_form': domicilio_fideicomitente_form,
            'domicilio_fideicomisario_form': domicilio_fideicomisario_form,
            'domicilio_fiduciario_form': domicilio_fiduciario_form,
            'observaciones_form': observaciones_form,
            'folio_declaracion': folio_declaracion,
            'avance':declaracion.avance,
            'informacion_registrada': informacion_registrada,
            'agregar': agregar,
            'editar_id': editar_id,
            'campos_privados': campos_configuracion(seccion,'p'),
            'campos_obligatorios': campos_configuracion(seccion,'o'),
            'puesto':puesto,
            'limit_simp':settings.LIMIT_DEC_SIMP
        })

    def guardar_registros_previos(self, request, declaracion, registros, kwargs):
        datosGuardados = True
        datos = json.loads(registros)
        declaracion_anterior = get_declaracion_anterior(declaracion)

        agregar, editar_id, fideicomisos_data, informacion_registrada = (
            declaracion_datos(kwargs, Fideicomisos, declaracion_anterior)
        )

        for dato in informacion_registrada:
            try:
                if str(dato.pk) in datos:
                    observaciones = Observaciones.objects.get(pk=dato.observaciones.pk)
                    if observaciones:
                        observaciones.pk = None
                        observaciones.save()
                        dato.observaciones = observaciones

                    dato.pk = None
                    dato.declaraciones = declaracion
                    dato.save()

                    activos_bienes = ActivosBienes.objects.get(pk=dato.activos_bienes.pk)
                    if activos_bienes:
                        bienes_personas = BienesPersonas.objects.filter(activos_bienes=activos_bienes)

                        activos_bienes.pk = None
                        activos_bienes.id_activobien = dato.pk
                        activos_bienes.cat_activo_bien_id = ActivosBienes.FIDEICOMISOS
                        activos_bienes.declaraciones = declaracion

                        #Se guarda el activo bien
                        activos_bienes.save()
                        #Se actualiza el inmueble con el nuevo activo bien
                        dato.activos_bienes = activos_bienes
                        dato.save()

                        for persona in bienes_personas:                            
                            if persona.otra_persona:
                                otra_persona = InfoPersonalVar.objects.get(pk=persona.otra_persona.pk)
                                if otra_persona:
                                    otra_persona.pk = None
                                    otra_persona.declaraciones = declaracion
                                    otra_persona.save()
                                    persona.otra_persona = otra_persona
                            
                            persona.pk = None
                            persona.activos_bienes = activos_bienes
                            persona.save()
            except ObjectDoesNotExist as e:
                datosGuardados =  False
                raise Http404()
        
        if datosGuardados:
            status, status_created = guardar_estatus(
                request,
                declaracion.folio,
                SeccionDeclaracion.COMPLETA)