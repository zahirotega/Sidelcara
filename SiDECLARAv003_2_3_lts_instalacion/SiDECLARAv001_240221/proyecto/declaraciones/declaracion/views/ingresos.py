import uuid
from django.conf import settings
from django.urls import reverse_lazy, resolve
from django.views import View
from django.shortcuts import render, redirect
from django.http import HttpResponseRedirect, Http404
from django.forms.models import model_to_dict
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required
from declaracion.forms import (ObservacionesForm, DomiciliosForm,
                               InfoPersonalVarForm,IngresosDeclaracionForm)     
from declaracion.forms.ingresos import IngresosActividadExtra, IngresosFinancieraExtra, IngresosServiciosExtra, IngresosOtrosExtra, IngresosEnajenacionExtra
from declaracion.models import (Declaraciones, SeccionDeclaracion,
                                SeccionDeclaracion, Secciones,IngresosDeclaracion,ConyugeDependientes,InfoPersonalFija)

from .utils import (guardar_estatus, no_aplica, declaracion_datos,
                    validar_declaracion, obtiene_avance,campos_configuracion,actualizar_ingresos,
                    get_declaracion_anterior, get_declaracion_anterior_inicial)
from .declaracion import (DeclaracionDeleteView)
from django.contrib import messages
import json
from django.http import JsonResponse
from declaracion.models.catalogos import CatMonedas,CatTiposInstrumentos,CatTiposActividad, CatTiposBienes

def IngresosDeclaracionDelete(request):

    id_ingreso=request.POST.get('id')
    tipo_ingreso=request.POST.get('tipo_ingreso')

    response = {}
    response['id_ingreso']=id_ingreso
    response['tipo_ingreso']=tipo_ingreso
  
    try:
        ingresos = IngresosDeclaracion.objects.get(id = id_ingreso)
    except Exception as e:
        response['error'] = 'Error al eliminar, intente más tarde'

    try:
        if ingresos.ingreso_mensual_cargo:
            if tipo_ingreso == 'AC':
                IngresosDeclaracion.objects.filter(id = id_ingreso).update(ingreso_mensual_actividad = None)
            elif tipo_ingreso == 'FN':
                IngresosDeclaracion.objects.filter(id = id_ingreso).update(ingreso_mensual_financiera = None)
            elif tipo_ingreso == 'SV':
                IngresosDeclaracion.objects.filter(id = id_ingreso).update(ingreso_mensual_servicios = None)
            elif tipo_ingreso == 'OT':
                IngresosDeclaracion.objects.filter(id = id_ingreso).update(ingreso_otros_ingresos = None)
            elif tipo_ingreso == 'EN':
                IngresosDeclaracion.objects.filter(id = id_ingreso).update(ingreso_enajenacion_bienes = None)
        else:
            ingresos.delete()

        response['success'] = 'Borrado con éxito'

    except Exception as e:
        response['error'] = str(e)
    

    return JsonResponse(response)


def IngresosDeclaracionUpdate(request):
    tipo_actividad=request.GET.get('tipo_actividad')

    if tipo_actividad == 'AC':
        id_ingreso=request.GET.get('id')
        monto=request.GET.get('monto')
        moneda=request.GET.get('moneda')
        razon_social=request.GET.get('razon_social')
        tipo_negocio=request.GET.get('tipo_negocio')

        response = {}
        response['id_ingreso'] = id_ingreso
        response['monto'] = monto
        response['razon_social'] = razon_social
        response['tipo_negocio'] = tipo_negocio
        
        try:
            IngresosDeclaracion.objects.filter(id = id_ingreso).update(
                ingreso_mensual_actividad = monto, 
                cat_moneda_actividad = moneda,
                razon_social_negocio = razon_social,
                tipo_negocio = tipo_negocio
                )
            response['success'] = 'Registro editado correctamente'
        except Exception as e:
            response['error'] = 'Error al editar, intente más tarde '

    elif tipo_actividad == 'FN':
        id_ingreso=request.GET.get('id')
        monto=request.GET.get('monto')
        moneda=request.GET.get('moneda')
        tipo_instrumento=request.GET.get('tipo_instrumento')

        response = {}
        response['id_ingreso'] = id_ingreso
        response['monto'] = monto

        try:
            tipo_instrumento_obj = CatTiposInstrumentos.objects.get(pk= tipo_instrumento)
            tipo_instrumento_text = tipo_instrumento_obj.valor
            response['tipo_instrumento'] = tipo_instrumento_text
        except Exception as e:
            response['tipo_instrumento'] = tipo_instrumento
            
        try:
            IngresosDeclaracion.objects.filter(id = id_ingreso).update(
                ingreso_mensual_financiera = monto, 
                cat_moneda_financiera = moneda,
                cat_tipo_instrumento = tipo_instrumento
                )
            response['success'] = 'Registro editado correctamente'

        except Exception as e:
            response['error'] = str(e)
    elif tipo_actividad == 'SV':
        id_ingreso=request.GET.get('id')
        monto=request.GET.get('monto')
        moneda=request.GET.get('moneda')
        tipo_servicio=request.GET.get('tipo_servicio')

        response = {}
        response['id_ingreso'] = id_ingreso
        response['monto'] = monto
        response['tipo_servicio'] = tipo_servicio
        
        try:
            IngresosDeclaracion.objects.filter(id = id_ingreso).update(
                ingreso_mensual_servicios = monto, 
                cat_moneda_servicios = moneda,
                tipo_servicio = tipo_servicio
                )
            response['success'] = 'Registro editado correctamente'


        except Exception as e:
            response['error'] = 'Error al editar, intente más tarde '
    elif tipo_actividad == 'OT':
        id_ingreso=request.GET.get('id')
        monto=request.GET.get('monto')
        moneda=request.GET.get('moneda')
        tipo_ingreso=request.GET.get('tipo_ingreso')

        response = {}
        response['id_ingreso'] = id_ingreso
        response['monto'] = monto
        try:
            tipo_ingreso_obj = CatTiposActividad.objects.get(pk= tipo_ingreso)
            tipo_ingreso_text = tipo_ingreso_obj.tipo_actividad
            response['tipo_ingreso'] = tipo_ingreso_text
        except Exception as e:
            response['tipo_ingreso'] = str(e)
        
        try:
            IngresosDeclaracion.objects.filter(id = id_ingreso).update(
                ingreso_otros_ingresos = monto, 
                cat_moneda_otros_ingresos = moneda,
                cat_tipos_actividad = tipo_ingreso
                )
            response['success'] = 'Registro editado correctamente'


        except Exception as e:
            response['error'] = str(e)

    elif tipo_actividad == 'EN':
        id_ingreso=request.GET.get('id')
        monto=request.GET.get('monto')
        moneda=request.GET.get('moneda')
        tipo_bienes=request.GET.get('tipo_bienes')

        response = {}
        response['id_ingreso'] = id_ingreso
        response['monto'] = monto

        try:
            tipo_bienes_obj = CatTiposBienes.objects.get(pk= tipo_bienes)
            tipo_bienes_text = tipo_bienes_obj.tipo_bien
            response['tipo_bienes'] = tipo_bienes_text
            response['id_tipo_bienes'] = tipo_bienes
        except Exception as e:
            response['tipo_bienes'] = tipo_bienes
            
        try:
            IngresosDeclaracion.objects.filter(id = id_ingreso).update(
                ingreso_enajenacion_bienes = monto, 
                cat_moneda_enajenacion_bienes = moneda,
                cat_tipos_bienes = tipo_bienes
                )
            response['success'] = 'Registro editado correctamente'

        except Exception as e:
            response['error'] = str(e)




    try:
        moneda_text = CatMonedas.objects.get(pk= moneda)
        moneda_text = moneda_text.moneda
        response['moneda'] = moneda_text
        response['id_moneda']=moneda
    except Exception as e:
        response['moneda'] = moneda

    

    return JsonResponse(response)


def IngresosDeclaracionAdd(request):
    response = {}
    id_ingreso=request.GET.get('id')
    ingreso_extra=request.GET.get('ingreso_extra')
    tipo_ingreso=request.GET.get('tipo_ingreso')
    folio_declaracion=request.GET.get('folio_declaracion')
    success=""
    

    folio = uuid.UUID(folio_declaracion)
    declaracion = Declaraciones.objects.filter(folio=folio).first()

    try:

        ingresos_declaracion_data = IngresosDeclaracion.objects.filter(declaraciones=declaracion, tipo_ingreso=tipo_ingreso).first()

        if ingresos_declaracion_data:
            observaciones_data = ingresos_declaracion_data.observaciones
        else:
            observaciones_data = None

        observaciones_form = ObservacionesForm(
            request.GET,
            prefix="observaciones",
            instance=observaciones_data)


        if ingreso_extra == 'AC':
            form = IngresosActividadExtra(request.GET)
            response['monto']=request.GET.get('ingreso_mensual_actividad')
            moneda=request.GET.get('cat_moneda_actividad')
            response['moneda_id']=moneda
            response['razon_social']=request.GET.get('razon_social_negocio')
            response['tipo_negocio']=request.GET.get('tipo_negocio')
            success='Ingreso por actividad industrial, comercial y/o empresarial agregado correctamente'
        elif ingreso_extra == 'FN':
            form = IngresosFinancieraExtra(request.GET)
            response['monto']=request.GET.get('ingreso_mensual_financiera')
            moneda=request.GET.get('cat_moneda_financiera')
            response['moneda_id']=moneda
            tipo_instrumento=request.GET.get('cat_tipo_instrumento')
            response['tipo_instrumento_id']=tipo_instrumento
            success='Ingreso por actividad financiera agregado correctamente'

            tipo_instrumento_obj = CatTiposInstrumentos.objects.get(pk= tipo_instrumento)
            tipo_instrumento_text = tipo_instrumento_obj.valor
            response['tipo_instrumento'] = tipo_instrumento_text

        elif ingreso_extra == 'SV':
            form = IngresosServiciosExtra(request.GET)
            response['monto']=request.GET.get('ingreso_mensual_servicios')
            moneda=request.GET.get('cat_moneda_servicios')
            response['moneda_id']=moneda
            response['tipo_servicio']=request.GET.get('tipo_servicio')
            success='Ingreso por servicios profesionales, consejos, consultorias y/o asesorias agregado correctamente'

        elif ingreso_extra == 'OT':
            form = IngresosOtrosExtra(request.GET)
            response['monto']=request.GET.get('ingreso_otros_ingresos')
            moneda=request.GET.get('cat_moneda_otros_ingresos')
            response['moneda_id']=moneda
            tipo_actividad=request.GET.get('cat_tipos_actividad')
            response['tipo_actividad_id']=tipo_actividad
            success='Ingreso agregado correctamente'

            tipo_actividad_obj = CatTiposActividad.objects.get(pk= tipo_actividad)
            tipo_actividad_text = tipo_actividad_obj.tipo_actividad
            response['tipo_actividad'] = tipo_actividad_text

        elif ingreso_extra == 'EN':
            form = IngresosEnajenacionExtra(request.GET)
            response['monto']=request.GET.get('ingreso_enajenacion_bienes')
            moneda=request.GET.get('cat_moneda_enajenacion_bienes')
            response['moneda_id']=moneda
            tipo_bienes=request.GET.get('cat_tipos_bienes')
            response['tipo_bienes_id']=tipo_bienes
            success='Ingreso por enajenación de bienes agregado correctamente'

            tipo_bienes_obj = CatTiposBienes.objects.get(pk= tipo_bienes)
            tipo_bienes_text = tipo_bienes_obj.tipo_bien
            response['tipo_bienes'] = tipo_bienes_text

        form_is_valid = form.is_valid()
        if form_is_valid:
            form_info_obj = form.save(commit=False)
            form_info_obj.declaraciones = declaracion
            form_info_obj.observaciones = observaciones_form.save()
            form_info_obj.tipo_ingreso = tipo_ingreso
            form_info_obj.save()
            response['id_ingreso'] = form_info_obj.id
            response['success']=success
        else:
            response['error']='Error al guardar. Revise los datos ingresados.'
    except Exception as e:  
        response['error']=str(e)

    try:
        moneda_text = CatMonedas.objects.get(pk= moneda)
        moneda_text = moneda_text.moneda
        response['moneda'] = moneda_text
    except Exception as e:
        response['moneda'] = moneda


    return JsonResponse(response)


class IngresosDeclaracionView(View):
    """
    Class IngresosDeclaracionView vista basada en clases, carga y guardar ingresosDeclaración(Sección: VIII.INGRESOS NETOS DECLARANTE Y IX.TE DESEMPEÑASTE COMO SERVIDOR PÚBLICO?)
    Esta vista es usada en dos secciones que usan practicamento los mismos formularios a excepcion de algunos campos que los diferencian
    --------

    Methods
    -------
    get(self,request,*args,**kwargs)
        Obtiene la información inicial de la sección y carga los formularios necesarios para ser guardada

    post(self, request, *args, **kwargs)
        Recibe datos ingresados por el usario y son guardados en la base de datos por medio de ORM de Django

    """
    template_name = 'declaracion/ingresos/ingresos-declaracion.html'

    @method_decorator(login_required(login_url='/login'))
    def get(self, request, *args, **kwargs):
        """
        Una sección puede estar conformado por más de un modelo y un formulario
        Se inicializan algunos campos con valores predeterminados, frecuentemente serán moneda y entidad federativa
        """
        folio_declaracion = self.kwargs['folio']

        #Se obtiene la url de la sección para obtener el nombre y que este sea buscado en DB para obtener el ID
        #Esta información es utilizada para obtener la configuración de los campos(obligatorios y privados)
        current_url = resolve(request.path_info).url_name
        seccion = Secciones.objects.filter(url=current_url).first()

        tipo_ingreso = True
        ingresos_pareja = 0
        if current_url == 'ingresos-servidor-publico':
            tipo_ingreso = False

        avance, faltas = 0, None
        try:
            declaracion = validar_declaracion(request, folio_declaracion)
            avance, faltas = obtiene_avance(declaracion)
        except ObjectDoesNotExist as e:
            raise Http404()

        try:
            ingresos_declaracion_data = IngresosDeclaracion.objects.filter(declaraciones=declaracion, tipo_ingreso=tipo_ingreso, ingreso_mensual_cargo__isnull=False).first()        

        except:
            ingresos_declaracion_data = None
        try:
            ingresos_actividad_extra_data = IngresosDeclaracion.objects.filter(declaraciones=declaracion, tipo_ingreso=tipo_ingreso)
        except:
            ingresos_actividad_extra_data = None
        declaracion_previa = False
        encabezados_registros={}
        ingresos=None
        declaracion_obj=None
        # Busca información de una declaración previa si es de tipo MODIFICACIÓN/CONCLUSIÓN
        # Solo se obtiene información previa si la declaración actual aún no tiene registro de esta sección
        if declaracion.cat_tipos_declaracion.codigo != 'INICIAL':              
            if not ingresos_declaracion_data:
                if tipo_ingreso:
                    declaracion_obj = get_declaracion_anterior(declaracion)
                     
                else:
                    declaracion_obj = get_declaracion_anterior_inicial(declaracion)

                if declaracion_obj:
                    if not ingresos_actividad_extra_data:
                        ingresos = declaracion_obj.ingresosdeclaracion_set.filter(tipo_ingreso=tipo_ingreso)
                        encabezados_registros = {
                            'titulo_uno':"Monto",
                            'titulo_dos':"Moneda",
                            'titulo_tres':"Tipo Ingreso"
                        }
                        declaracion_previa = True

                        
                    
                if ingresos_declaracion_data:
                    ingresos_declaracion_data.pk = None
                    ingresos_declaracion_data.observaciones.pk = None
                    pareja_dependieintes = ConyugeDependientes.objects.filter(declaraciones=declaracion_obj)
                    if pareja_dependieintes:
                        ingresos_pareja = actualizar_ingresos(declaracion_obj)
                        ingresos_declaracion_data.ingreso_mensual_pareja_dependientes = ingresos_pareja

                            #Si la declaración ya tiene registros de la pareja o dependientes con un salario se toma ese dato
                            # y no el de la declaración anterior

        



        #Si ya existe información se obtiene y separa la información necesaria
        #frecuentemente observaciones y domicilio o demás datos que pertenezcan a otro formulario que no sea el prinicpal
        if ingresos_declaracion_data:
            observaciones_data =  ingresos_declaracion_data.observaciones
            if tipo_ingreso:
                pareja_dependieintes = ConyugeDependientes.objects.filter(declaraciones=declaracion) 
                if pareja_dependieintes:
                    ingresos_pareja = actualizar_ingresos(declaracion)
                    ingresos_declaracion_data.ingreso_mensual_pareja_dependientes = ingresos_pareja 
                if ingresos_declaracion_data.ingreso_mensual_total is None or not ingresos_declaracion_data.ingreso_mensual_total:
                    ingresos_declaracion_data.ingreso_mensual_total = 0
           

            ingresos_declaracion_data = model_to_dict(ingresos_declaracion_data)
            observaciones_data = model_to_dict(observaciones_data)

        else:

            if tipo_ingreso:
                ingresos_pareja=actualizar_ingresos(declaracion)
                if declaracion.cat_tipos_declaracion.codigo != 'MODIFICACIÓN': 
                    ingresos_declaracion_data = {
                        'ingreso_mensual_pareja_dependientes': ingresos_pareja,
                        'ingreso_mensual_total':ingresos_pareja
                    }
            observaciones_data = {}


        
        #Se inicializan los formularios a utilizar que conformen a la sección
        ingresos_declaracion_forms =IngresosDeclaracionForm(
            prefix='ingresos_declaracion', 
            initial=ingresos_declaracion_data)
        observaciones_form = ObservacionesForm(
            prefix="observaciones",
            initial=observaciones_data)
        ingresos_actividad_extra_form =IngresosActividadExtra
        ingresos_financiera_extra_form =IngresosFinancieraExtra
        ingresos_servicios_extra_form =IngresosServiciosExtra
        ingresos_otros_extra_form =IngresosOtrosExtra
        ingresos_enajenacion_form =IngresosEnajenacionExtra

        if folio_declaracion:
            try:
                declaracion2 = validar_declaracion(request, folio_declaracion)
            except ObjectDoesNotExist as e:
                raise Http404()


        usuario = request.user
        info_per_fija = InfoPersonalFija.objects.filter(usuario=usuario).first()
        puesto = info_per_fija.cat_puestos.codigo

        return render(request, self.template_name, {
            'encabezados_registros':encabezados_registros,
            'ingresos':ingresos,
            'declaracion':declaracion,
            'declaracion_obj':declaracion_obj,
            'declaracion_previa':declaracion_previa, #add marzo 22
            'ingresos_declaracion_data':ingresos_declaracion_data,
            'folio_declaracion': folio_declaracion,
            'ingresos_declaracion_forms': ingresos_declaracion_forms,
            'observaciones': observaciones_form,
            'ingresos_pareja': ingresos_pareja,
            'avance':avance,
            'faltas':faltas,
            'current_url_seccion':current_url,
            'current_url':'declaracion:'+current_url,
            'campos_privados': campos_configuracion(seccion,'p'),
            'campos_obligatorios': campos_configuracion(seccion,'o'),
            'declaracion2':declaracion2,
            'puesto':puesto,
            'limit_simp':settings.LIMIT_DEC_SIMP,
            'declaracion': declaracion,
            'tipo_ingreso':tipo_ingreso,
            'ingresos_actividad_extra_data':ingresos_actividad_extra_data,
            'ingresos_actividad_extra':ingresos_actividad_extra_form,
            'ingresos_financiera_extra':ingresos_financiera_extra_form,
            'ingresos_servicios_extra':ingresos_servicios_extra_form,
            'ingresos_otros_extra':ingresos_otros_extra_form,
            'ingresos_enajenacion_extra':ingresos_enajenacion_form
        })

    @method_decorator(login_required(login_url='/login'))
    def post(self, request, *args, **kwargs):
        """
        Obtiene y calcula el avance de la declaración con los datos ingresados
        Redirecciona a la siguiente sección de la declaración
        """
        folio_declaracion = self.kwargs['folio']

        current_url = resolve(request.path_info).url_name
        seccion = Secciones.objects.filter(url=current_url).first()
        
        usuario = request.user
        info_per_fija = InfoPersonalFija.objects.filter(usuario=usuario).first()
        puesto = info_per_fija.cat_puestos.codigo

        tipo_ingreso = True
        if current_url == 'ingresos-servidor-publico':
            tipo_ingreso = False

        avance, faltas = 0, None
        try:
            declaracion = validar_declaracion(request, folio_declaracion)
            avance, faltas = obtiene_avance(declaracion)
        except ObjectDoesNotExist as e:
            raise Http404()

        folio = uuid.UUID(folio_declaracion)
        declaracion = Declaraciones.objects.filter(folio=folio).first()

        ingresos_declaracion_data = IngresosDeclaracion.objects.filter(declaraciones=declaracion, tipo_ingreso=tipo_ingreso).first()
        if ingresos_declaracion_data:
            observaciones_data = ingresos_declaracion_data.observaciones
        else:
            ingresos_declaracion_data = None
            observaciones_data = None
        if request.POST.get('registrosPrevios'):
            registrosPreviosIngresos = json.loads(request.POST.get('registrosPrevios'));
            for ingreso in registrosPreviosIngresos:
                ingresos = IngresosDeclaracion.objects.filter(pk=ingreso['id']).first()
                ingresos.pk=None        
                ingresos.declaraciones = declaracion

                if ingreso['tipo'] == 'AC':
                    ingresos.ingreso_mensual_cargo = None
                    ingresos.ingreso_mensual_financiera = None                
                    ingresos.ingreso_mensual_servicios = None                
                    ingresos.ingreso_otros_ingresos = None 
                    ingresos.ingreso_enajenacion_bienes = None 
                elif ingreso['tipo'] == 'FN':
                    ingresos.ingreso_mensual_cargo = None
                    ingresos.ingreso_mensual_actividad = None                
                    ingresos.ingreso_mensual_servicios = None                
                    ingresos.ingreso_otros_ingresos = None  
                    ingresos.ingreso_enajenacion_bienes = None 

                elif ingreso['tipo'] == 'SV':
                    ingresos.ingreso_mensual_cargo = None
                    ingresos.ingreso_mensual_financiera = None                
                    ingresos.ingreso_mensual_actividad = None                
                    ingresos.ingreso_otros_ingresos = None 
                    ingresos.ingreso_enajenacion_bienes = None 

                elif ingreso['tipo'] == 'OT':
                    ingresos.ingreso_mensual_cargo = None
                    ingresos.ingreso_mensual_financiera = None                       
                    ingresos.ingreso_mensual_servicios = None                
                    ingresos.ingreso_mensual_actividad = None
                    ingresos.ingreso_enajenacion_bienes = None 

                elif ingreso['tipo'] == 'NA':
                    ingresos.ingreso_otros_ingresos = None
                    ingresos.ingreso_mensual_financiera = None                
                    ingresos.ingreso_mensual_servicios = None                
                    ingresos.ingreso_mensual_actividad = None
                    ingresos.ingreso_enajenacion_bienes = None 

                elif ingreso['tipo'] == 'EN':
                    ingresos.ingreso_mensual_cargo = None
                    ingresos.ingreso_otros_ingresos = None
                    ingresos.ingreso_mensual_financiera = None                
                    ingresos.ingreso_mensual_servicios = None                
                    ingresos.ingreso_mensual_actividad = None

                ingresos.save()
            return redirect('declaracion:'+current_url,folio=folio_declaracion)


        #Se asigna por formulario la información correspondiente
        ingresos_declaracion_form = IngresosDeclaracionForm(
            request.POST,
            prefix="ingresos_declaracion",
            instance=ingresos_declaracion_data)
        observaciones_form = ObservacionesForm(
            request.POST,
            prefix="observaciones",
            instance=observaciones_data)

        ingresos_declaracion_is_valid = ingresos_declaracion_form.is_valid()
        observaciones_is_valid = observaciones_form.is_valid()

            


        
        if (ingresos_declaracion_is_valid and observaciones_is_valid):
            aplica = no_aplica(request)
            observaciones = None
            
            #Se guarda individualmente los formularios para posteriormente integrar la información retornada al fomulario principal de la sección
            if aplica:
                ingresos_declaracion = ingresos_declaracion_form.save(commit=False)
                observaciones = observaciones_form.save()
                
                if 'ingreso_declaracion-ingreso_anio_anterior' in request.POST:
                    ingreso_anterior = json.loads(request.POST.get('ingreso_declaracion-ingreso_anio_anterior').lower())
                else:
                    ingreso_anterior = False
                
                if request.POST.get('ingresos_declaracion-ingreso_mensual_total') is None or ingresos_declaracion.ingreso_mensual_total is None:
                    ingresos_declaracion.ingreso_mensual_total = 0

                if request.POST.get('ingresos_declaracion-ingreso_mensual_neto') is None or ingresos_declaracion.ingreso_mensual_neto is None:
                    ingresos_declaracion.ingreso_mensual_neto = 0

                if request.POST.get('ingresos_declaracion-ingreso_mensual_cargo') is None or ingresos_declaracion.ingreso_mensual_cargo is None:
                    ingresos_declaracion.ingreso_mensual_cargo = 0
                    
                ingresos_declaracion.declaraciones = declaracion
                ingresos_declaracion.observaciones = observaciones
                ingresos_declaracion.tipo_ingreso = tipo_ingreso
                ingresos_declaracion.ingreso_anio_anterior = ingreso_anterior

                ingresos_declaracion.save()


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
               # ToDo error link? //  messages.warning(request, u"Algunos campos obligatorios de la sección no se completaron pero los datos han sido guardados, favor de completar información más tarde")
                return redirect('declaracion:ingresos-netos',folio=folio_declaracion)

            if request.POST.get("accion") == "guardar_salir":
                if current_url == 'ingresos-servidor-publico':
                    return redirect('declaracion:ingresos-servidor-publico',folio=folio_declaracion)
                else:
                    return redirect('declaracion:ingresos-netos', folio=folio_declaracion)
              
            if current_url == 'ingresos-servidor-publico':
                if puesto >settings.LIMIT_DEC_SIMP:
                    return HttpResponseRedirect(
                        reverse_lazy('declaracion:bienes-inmuebles',
                                     args=[folio_declaracion]))
                else:
                    return HttpResponseRedirect(
                        reverse_lazy('declaracion:confirmar-allinone',
                                     args=[folio_declaracion]))
            else:
                if puesto >settings.LIMIT_DEC_SIMP:
                    if declaracion.cat_tipos_declaracion_id != 1:
                        return HttpResponseRedirect(
                            reverse_lazy('declaracion:bienes-inmuebles',
                                         args=[folio_declaracion]))
                    else:
                        return HttpResponseRedirect(
                            reverse_lazy('declaracion:ingresos-servidor-publico',
                                         args=[folio_declaracion]))
                else:
                    if declaracion.cat_tipos_declaracion_id != 1:
                        return HttpResponseRedirect(
                            reverse_lazy('declaracion:confirmar-allinone',
                                         args=[folio_declaracion]))
                    else:
                        return HttpResponseRedirect(
                            reverse_lazy('declaracion:ingresos-servidor-publico',
                                         args=[folio_declaracion]))


        return render(request, self.template_name, {
            'folio_declaracion': folio_declaracion,
            'ingresos_declaracion_forms': ingresos_declaracion_form,
            'observaciones': observaciones_form,
            'avance':avance,
            'faltas':faltas,
            'current_url':current_url,
            'campos_privados': campos_configuracion(seccion,'p'),
            'campos_obligatorios': campos_configuracion(seccion,'o'),
            'puesto':puesto,
            'limit_simp':settings.LIMIT_DEC_SIMP
            


        })

