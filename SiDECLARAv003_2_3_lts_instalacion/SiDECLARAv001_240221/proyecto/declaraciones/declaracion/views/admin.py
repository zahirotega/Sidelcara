import uuid

from django.http import JsonResponse
from django.conf import settings
from django.contrib.auth.models import User
from django.db.models import Q
from django.forms.models import model_to_dict
from django.contrib.sites.shortcuts import get_current_site
from django.core.mail import send_mail #, EmailMultiAlternatives
from .mailto import mail_conf
from django.core.paginator import Paginator
from django.template.loader import render_to_string
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.views import View
from django.shortcuts import render, redirect
from django.http import HttpResponseRedirect, HttpResponse, Http404
from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist

from declaracion.forms import (BusquedaDeclaranteForm, BusquedaDeclaracionForm,
                                BusquedaUsuariosForm,RegistroUsuarioOICForm,BusquedaGraficasForm,
                                RegistroUsuarioDeclaranteForm, BusquedaDeclaracionExtForm, RegistroUsuarioDeclaranteEdicionForm)
from declaracion.models import (Declaraciones, InfoPersonalVar,
                                InfoPersonalFija, DatosCurriculares, Encargos,
                                ExperienciaLaboral, ConyugeDependientes,
                                Observaciones, SeccionDeclaracion, Secciones, IngresosDeclaracion, 
                                MueblesNoRegistrables, BienesInmuebles, ActivosBienes, BienesPersonas, 
                                BienesMuebles,SociosComerciales,Membresias, Apoyos,ClientesPrincipales,
                                BeneficiosGratuitos, Inversiones, DeudasOtros, PrestamoComodato, Fideicomisos, DeclaracionFiscal,
                                CatTiposDeclaracion, CatEstatusDeclaracion)
from declaracion.models.catalogos import CatPuestos
from declaracion.views import RegistroView
from declaracion.views.confirmacion import (get_context_InformacionPersonal,get_context_Intereses,get_context_pasivos,
                                            get_context_ingresos,get_inmuebles,get_context_activos, get_context_activos,
                                            get_context_vehiculos, get_context_inversiones, get_context_deudasotros,
                                            get_context_prestamocomodato, get_context_fideicomisos)

from .utils import (set_declaracion_extendida_simplificada, task_crear_pdf, task_obtener_estatus,
                                    obtener_pdf_existente, task_eliminar_background)
from sitio.util import account_activation_token
from sitio.models import sitio_personalizacion, Valores_SMTP, HistoricoAreasPuestos
from api.serialize_functions import serialize_empleo_cargo_comision

from datetime import datetime, date, timedelta
from rest_framework.views import APIView 
from rest_framework.response import Response

from weasyprint import HTML, CSS


from django.http import HttpResponse
from django.template.loader import render_to_string

from django.contrib import messages
import json
import os
import django_excel as excel


class BusquedaDeclarantesFormView(View):
    template_name="declaracion/admin/busqueda-declarantes.html"

    @method_decorator(login_required(login_url='/login'))
    def get(self,request,*args,**kwargs):

        if request.user.is_staff:
            return render(request,self.template_name,{'form':BusquedaDeclaranteForm(),"current_url_menu": "declarantes"})
        else:
            return redirect('login')

    @method_decorator(login_required(login_url='/login'))
    def post(self,request,*args,**kwargs):
        if request.user.is_staff:
            request_post = request.POST
            form = BusquedaDeclaranteForm(request_post)
            usuarios_sin_infopersonalfija = []
            usuarios_con_dec = []
            result = None
            tipo_registro = 'registrado'
            declaraciones = Declaraciones.objects.all()
            for dec in declaraciones:
                if not dec.info_personal_fija.pk in usuarios_con_dec:
                    usuarios_con_dec.append(dec.info_personal_fija.pk)

            if form.is_valid():
                result = InfoPersonalFija.objects.filter(usuario__is_staff=False, usuario__is_superuser=False)
                tipo_registro = form.cleaned_data.get('tipo_registro')
                page = form.cleaned_data.get('page')
                page_size =form.cleaned_data.get('page_size')
                nombre = form.cleaned_data.get('nombre')
                apellido1 = form.cleaned_data.get('apellido1')
                rfc = form.cleaned_data.get('rfc_search')
                estatus = form.cleaned_data.get('estatus')
                registrado = True
                q = Q(pk__isnull=False)

                if tipo_registro == 'todos':

                    if nombre and not nombre=="":
                        q &= Q(nombres__icontains=nombre)
                    if apellido1 and not apellido1=="":
                        q &= Q(apellido1__icontains=apellido1)
                    if rfc and not rfc=="":
                        q &= Q(rfc__icontains=rfc)
                    if estatus:
                        q &= Q(usuario__is_active = estatus)


                if tipo_registro == 'registrado':

                    result = result.filter(pk__in = usuarios_con_dec)

                    if nombre and not nombre=="":
                        q &= Q(nombres__icontains=nombre)
                    if apellido1 and not apellido1=="":
                        q &= Q(apellido1__icontains=apellido1)
                    if rfc and not rfc=="":
                        q &= Q(rfc__icontains=rfc)
                    if estatus:
                        q &= Q(usuario__is_active = estatus)

                if tipo_registro == 'registrado_sindec':
                    registrado = True

                    result = result.exclude(pk__in = usuarios_con_dec)

                    if nombre and not nombre=="":
                        q &= Q(nombres__icontains=nombre)
                    if apellido1 and not apellido1=="":
                        q &= Q(apellido1__icontains=apellido1)
                    if rfc and not rfc=="":
                        q &= Q(rfc__icontains=rfc)
                    if estatus:
                        q &= Q(usuario__is_active = estatus)

                
                if tipo_registro == 'no_registrado':
                    registrado = False
                    result_usuarios = User.objects.filter(is_staff=False, is_superuser=False)

                    for usuario in result_usuarios:
                        if not InfoPersonalFija.objects.filter(usuario=usuario):
                            usuarios_sin_infopersonalfija.append(usuario.pk)

                    result = result_usuarios.filter(pk__in=usuarios_sin_infopersonalfija)

                    if nombre and not nombre=="":
                        q &= Q(first_name__icontains=nombre)
                    if apellido1 and not apellido1=="":
                        q &= Q(last_name__icontains=apellido1)
                    if rfc and not rfc=="":
                        q &= Q(username__icontains=rfc)
                    if estatus:
                        q &= Q(is_active = estatus)
                
                fecha_inicio = False
                fecha_fin_mas_uno = False
                if request_post.get('fecha_inicio_year') and request_post.get('fecha_inicio_month') and request_post.get('fecha_inicio_day'):
                    fecha_inicio = date(int(request_post.get('fecha_inicio_year')),int(request_post.get('fecha_inicio_month')),int(request_post.get('fecha_inicio_day')))
                    
                if request_post.get('fecha_fin_day'):
                    fin_day = int(request_post.get('fecha_fin_day')) + 1 if int(request_post.get('fecha_fin_day')) <= 27 else int(request_post.get('fecha_fin_day'))
                    fecha_fin = date(int(request_post.get('fecha_fin_year')),int(request_post.get('fecha_fin_month')),int(request_post.get('fecha_fin_day')))
                    fecha_fin_mas_uno = date(int(request_post.get('fecha_fin_year')),int(request_post.get('fecha_fin_month')), fin_day )
                
                #Si el usuario solo selecciona la fecha de inicio
                if fecha_inicio and not fecha_fin_mas_uno:
                    if registrado:
                        q &= Q(fecha_inicio__gte=fecha_inicio)
                    else:
                        q &= Q(date_joined__gte=fecha_inicio)
                elif not fecha_inicio and fecha_fin_mas_uno:
                    if registrado:
                        q &= Q(fecha_inicio__lte=fecha_fin_mas_uno)
                    else:
                        q &= Q(date_joined__lte=fecha_fin_mas_uno)
                #El usuario desea buscar en un rango de fechas
                elif fecha_inicio and fecha_fin_mas_uno:
                    if registrado:
                        q &= Q(fecha_inicio__range=[fecha_inicio,fecha_fin_mas_uno])
                    else:
                        q &= Q(date_joined__range=[fecha_inicio,fecha_fin_mas_uno])

                result = result.filter(q)

            parametros = {
                'form':form,
                'tipo_registro': tipo_registro
            }

            if result:
                parametros.update({'result':result})
            else:
                messages.warning(request, u"No se encontraron resultados")

            return render(request,self.template_name,parametros)
        else:
            return redirect('declaracion:index')


class BusquedaUsuariosFormView(View):
    template_name="declaracion/admin/busqueda-usuarios.html"

    @method_decorator(login_required(login_url='/login'))
    def get(self,request,*args,**kwargs):

        if request.user.is_staff:
            return render(request,self.template_name,{'form':BusquedaUsuariosForm(), "current_url_menu": "usuarios"})
        else:
            return redirect('login')

    @method_decorator(login_required(login_url='/login'))
    def post(self,request,*args,**kwargs):
        if request.user.is_staff:
            form = BusquedaUsuariosForm(request.POST)
            result = InfoPersonalFija.objects.filter(usuario__is_staff=True)

            if form.is_valid():
                page = form.cleaned_data.get('page')
                page_size =form.cleaned_data.get('page_size')
                nombre = form.cleaned_data.get('nombre')
                estatus = form.cleaned_data.get('estatus')
                puesto = form.cleaned_data.get('puesto_str')

                if nombre and not nombre=="":
                    result = result.filter( nombres__icontains=nombre)
                apellido1 = form.cleaned_data.get('apellido1')
                if apellido1 and not apellido1=="":
                    result = result.filter( apellido1__icontains=apellido1)
                apellido2 = form.cleaned_data.get('apellido2')
                if apellido2 and not apellido2=="":
                    result = result.filter( apellido2__icontains=apellido2)
                if estatus:
                    result = result.filter( usuario__is_active = estatus)
                '''rfc = form.cleaned_data.get('rfc')
                if rfc and not rfc=="":
                    result = result.filter(rfc__icontains=rfc)'''
                
                usuario = form.cleaned_data.get('usuario')
                if usuario and not usuario=="":
                    result = result.filter(usuario__username__icontains=usuario)

                if puesto:
                    puesto_data = CatPuestos.objects.filter(puesto__contains=puesto)
                    puestos = []

                    for puesto in puesto_data:
                        puestos.append(puesto.pk)

                    result = result.filter(cat_puestos__in=puestos)

                if page and page.isdigit():
                    page = int(page)
                else:
                    page=1
                if page_size and page_size.isdigit():
                    page_size = int(page_size)
                else:
                    page_size=10

        no_results = False
        if result.count() == 0:
            no_results = True

        paginator = Paginator(result, page_size)
        result = paginator.get_page(page)

        return render(request,self.template_name,{'form':form,'result':result,'paginas': range(1, paginator.num_pages + 1), 'no_results':no_results} )


class BusquedaDeclaracionesFormView(View):
    template_name="declaracion/admin/busqueda-declaraciones.html"

    @method_decorator(login_required(login_url='/login'))
    def get(self,request,*args,**kwargs):

        if request.user.is_staff:
            return render(request,self.template_name,{'form':BusquedaDeclaracionForm(), "current_url_menu": "declaraciones"})
        else:
            return redirect('login')

    @method_decorator(login_required(login_url='/login'))
    def post(self,request,*args,**kwargs):
        if request.user.is_staff:
            request_post = request.POST
            form = BusquedaDeclaracionForm(request_post)
            result = None
            list_declaraciones = []

            if form.is_valid():
                try:
                    result = Declaraciones.objects.all()
                    page = form.cleaned_data.get('page')
                    page_size =form.cleaned_data.get('page_size')
                    folio = form.cleaned_data.get('folio')
                    filtro_fecha =request_post.get('filtro_fecha')

                    if folio and not folio=="":
                        result = result.filter(folio=uuid.UUID(folio))
                    
                    tipo = form.cleaned_data.get('tipo')
                    if tipo :
                        result = result.filter(cat_tipos_declaracion=tipo)
                    
                    estatus = form.cleaned_data.get('estatus')
                    if estatus:
                        result = result.filter(cat_estatus=estatus)

                    fecha_inicio = False
                    fecha_fin_mas_uno = False
                    if request_post.get('fecha_inicio_year') and request_post.get('fecha_inicio_month') and request_post.get('fecha_inicio_day'):
                        fecha_inicio = date(int(request_post.get('fecha_inicio_year')),int(request_post.get('fecha_inicio_month')),int(request_post.get('fecha_inicio_day')))
                        
                    if request_post.get('fecha_fin_day'):
                        fin_day = int(request_post.get('fecha_fin_day')) + 1 if int(request_post.get('fecha_fin_day')) <= 27 else int(request_post.get('fecha_fin_day'))
                        fecha_fin = date(int(request_post.get('fecha_fin_year')),int(request_post.get('fecha_fin_month')),int(request_post.get('fecha_fin_day')))
                        fecha_fin_mas_uno = date(int(request_post.get('fecha_fin_year')),int(request_post.get('fecha_fin_month')), fin_day )
                    
                    #Si el usuario solo selecciona la fecha de inicio
                    if fecha_inicio and not fecha_fin_mas_uno:
                        if filtro_fecha == '0':
                            result = result.filter(fecha_declaracion__gte=fecha_inicio)
                        else:
                            result = result.filter(fecha_recepcion__gte=fecha_inicio)
                    #El usuario desea buscar en un rango de fechas
                    elif fecha_inicio and fecha_fin_mas_uno:
                        if filtro_fecha == '0':
                            result = result.filter(fecha_declaracion__range=[fecha_inicio,fecha_fin_mas_uno])
                        else:
                            result = result.filter(fecha_recepcion__range=[fecha_inicio,fecha_fin_mas_uno])


                    #Reesctructura de declaraciones para mostrar en el template
                    for dato in result:
                        info_declaracion = {
                            "declaracion": dato
                        }

                        if dato.cat_estatus.pk == 4:
                            archivo_pdf =  obtener_pdf_existente("declaracion",dato)
                            if archivo_pdf:
                                info_declaracion.update({"archivo": archivo_pdf})
                            
                            estatus = task_obtener_estatus("declaracion",dato)
                            if estatus:
                                info_declaracion.update({"estatus_proceso": estatus})
                        
                        list_declaraciones.append(info_declaracion)
                                            
                except Exception as e:
                    print ("Error al consultar los datos-------------->",e)
                    messages.warning(request, u"Para buscar por folio este debe ser la cadena completa del mismo. NO SE ENCONTRARON RESULTADOS EN EL PERIODO DE FECHAS DADAS")
                    return redirect('declaracion:busqueda-declaraciones')

            if page and page.isdigit():
                    page = int(page)
            else:
                page=1
            if page_size and page_size.isdigit():
                page_size = int(page_size)
            else:
                page_size=10

            paginator = Paginator(result, page_size)
            result = paginator.get_page(page)

            print(page)
            print(page_size)
            print(result)

            context = {
                'form':form,
                'result':result,
                'limit_simp': settings.LIMIT_DEC_SIMP, #add 28/04/2023
                'paginas':range(1, paginator.num_pages+1),
                'page_size':page_size
            }

            

            return render(request,self.template_name,context)
        else:
            return redirect('declaracion:index')


class BusquedaUsDecFormView(View):
    template_name="declaracion/admin/busqueda-declarante-declaraciones.html"

    @method_decorator(login_required(login_url='/login'))
    def get(self,request,*args,**kwargs):

        if request.user.is_staff:
            return render(request,self.template_name,{'form':BusquedaDeclaracionExtForm()})
        else:
            return redirect('login')

    @method_decorator(login_required(login_url='/login'))
    def post(self,request,*args,**kwargs):
        if request.user.is_staff:
            request_post = request.POST
            form = BusquedaDeclaracionExtForm(request_post)
            dec={}
            l=[]
            if form.is_valid():

                dec_status = request_post.get('dec_status')
            
                if dec_status:
                    dec = Declaraciones.objects.filter(extemporanea=dec_status)

                    for d in dec:
                        if d.info_personal_fija_id not in l:
                            l.append(d.info_personal_fija_id)

                    result = InfoPersonalFija.objects.filter(usuario__is_staff=False, id__in=l)
                else:
                    result = InfoPersonalFija.objects.filter(usuario__is_staff=False)

                page = form.cleaned_data.get('page')
                page_size =form.cleaned_data.get('page_size')
                nombre = form.cleaned_data.get('nombre')
                estatus = form.cleaned_data.get('estatus')
            
                if nombre and not nombre=="":
                    result = result.filter( nombres__icontains=nombre)
                apellido1 = form.cleaned_data.get('apellido1')
                if apellido1 and not apellido1=="":
                    result = result.filter( apellido1__icontains=apellido1)
                apellido2 = form.cleaned_data.get('apellido2')
                if apellido2 and not apellido2=="":
                    result = result.filter( apellido2__icontains=apellido2)
                rfc = form.cleaned_data.get('rfc')
                if rfc and not rfc=="":
                    result = result.filter( rfc__icontains=rfc)
                curp = form.cleaned_data.get('curp')
                if curp and not curp=="":
                    result = result.filter(curp__icontains=curp)
                if estatus:
                    result = result.filter(usuario__is_active = estatus)

                if not dec_status:
                    for r in result:
                        l.append(r.id)

                    dec = Declaraciones.objects.filter(info_personal_fija_id__in=l)

                if page and page.isdigit():
                    page = int(page)
                else:
                    page=1
                if page_size and page_size.isdigit():
                    page_size = int(page_size)
                else:
                    page_size=10

                paginator = Paginator(result, page_size)
                result = paginator.get_page(page)


            return render(request,self.template_name,{'form':form,'result':result, 'dec_status':dec_status, 'dec':dec,'paginas': range(1, paginator.num_pages + 1)})
        else:
            return redirect('declaracion:index')

def consultarDeclaracionesAjax(request):
    if request.user.is_staff:
        result = None
        results_json = []
        request_post=request.POST

        try:
            page=request_post.get('page')
            page_size=request_post.get('page_size')
            folio=request_post.get('folio')
            filtro_fecha=request_post.get('filtro_fecha')
            tipo=request_post.get('tipo')
            estatus=request_post.get('estatus')
            q = Q(pk__isnull=False)

            if folio and not folio=="":
                q &= Q(folio=uuid.UUID(folio))
            if tipo :
                q &= Q(cat_tipos_declaracion=tipo)
            if estatus:
                q &= Q(cat_estatus=estatus)

            fecha_inicio = False
            fecha_fin_mas_uno = False
            if request_post.get('fecha_inicio_year') and request_post.get('fecha_inicio_month') and request_post.get('fecha_inicio_day'):
                fecha_inicio = date(int(request_post.get('fecha_inicio_year')),int(request_post.get('fecha_inicio_month')),int(request_post.get('fecha_inicio_day')))
                
            if request_post.get('fecha_fin_day'):
                fin_day = int(request_post.get('fecha_fin_day')) + 1 if int(request_post.get('fecha_fin_day')) <= 27 else int(request_post.get('fecha_fin_day'))
                fecha_fin = date(int(request_post.get('fecha_fin_year')),int(request_post.get('fecha_fin_month')),int(request_post.get('fecha_fin_day')))
                fecha_fin_mas_uno = date(int(request_post.get('fecha_fin_year')),int(request_post.get('fecha_fin_month')), fin_day )
            
            #Si el usuario solo selecciona la fecha de inicio
            if fecha_inicio and not fecha_fin_mas_uno:
                if filtro_fecha == '0':
                    q &= Q(fecha_declaracion__gte=fecha_inicio)

                else:
                    q &= Q(fecha_recepcion__gte=fecha_inicio)
            #El usuario desea buscar en un rango de fechas
            elif fecha_inicio and fecha_fin_mas_uno:
                if filtro_fecha == '0':
                    q &= Q(fecha_declaracion__range=[fecha_inicio,fecha_fin_mas_uno])
                else:
                    q &= Q(fecha_recepcion__range=[fecha_inicio,fecha_fin_mas_uno])

                
        except Exception as e:
            print("Error al consultar los datos-------------->",e)

        result = Declaraciones.objects.filter(q).order_by('pk')
        total_registros = result.count()

        if page and page.isdigit():
                page = int(page)
        else:
            page=1
        if page_size and page_size.isdigit():
            page_size = int(page_size)
        else:
            page_size=10

        paginator = Paginator(result, page_size)
        result = paginator.get_page(page)
        paginas = list(range(1, paginator.num_pages+1))

        for res in result:
            estatus_proceso = False
            archivo = False
            
            #ADD Historicos: Se obtiene el puesto correspondiente a la declaración de acuerdo a su fecha recepción
            if res.cat_estatus.pk == 4:

                try:
                    archivo =  obtener_pdf_existente("declaracion",res)
                except Exception as e:
                    archivo = None

                try:
                    estatus_proceso = task_obtener_estatus("declaracion",res)
                except Exception as e:
                    estatus_proceso = None

                try:
                    encargos = res.encargos_set.filter(cat_puestos__isnull=False)
                    if encargos.count() > 0:
                        encargo = encargos.first()
                        puesto = serialize_empleo_cargo_comision(res, encargo)
                        nivel = puesto["puesto_codigo"]
                except ObjectDoesNotExist:
                    #Se toma el nivel actual del declarante en el puesto de infoFija
                    nivel = res.info_personal_fija.cat_puestos.codigo
            else:
                #Se toma el nivel actual del declarante en el puesto de infoFija
                nivel = res.info_personal_fija.cat_puestos.codigo

            data = {
                'id':res.id,
                'archivo':archivo,
                'estatus_proceso': estatus_proceso,
                'folio':res.folio,
                'cat_tipos_declaracion':res.cat_tipos_declaracion.codigo,
                'avance':res.avance,
                'extendida': 'No' if int(nivel) <= int(settings.LIMIT_DEC_SIMP) else 'Sí',
                'extemporanea': res.extemporanea,
                'limit_simp': settings.LIMIT_DEC_SIMP,
                'extemporanea':res.extemporanea,
                'fecha_declaracion':res.fecha_declaracion.strftime('%d-%m-%Y') if res.fecha_declaracion else 'N/A',
                'fecha_recepcion':res.fecha_recepcion.strftime('%d-%m-%Y') if res.fecha_recepcion else 'N/A',
                'cat_estatus':res.cat_estatus.estatus_declaracion,
                'cat_estatus_pk':res.cat_estatus.pk,
                'datos_publicos':res.datos_publicos,
            }

            results_json.append(data)

        response = {
            'results': results_json,
            'has_next': result.has_next(),
            'has_previous': result.has_previous(),
            'current_page': result.number,
            'total_pages': paginator.num_pages,
            'paginas': paginas,
            'total_registros': total_registros,
            'page_size': page_size
        }

        return JsonResponse(response)


def consultarDeclarantesAjax(request):
    if request.user.is_staff:
        request_post = request.POST
        form = BusquedaDeclaranteForm(request_post)
        usuarios_con_infopersonalfija = []
        usuarios_con_dec = []
        result = None

        result = InfoPersonalFija.objects.filter(usuario__is_staff=False, usuario__is_superuser=False)
        tipo_registro = request_post.get('tipo_registro')
        page = request_post.get('page')
        page_size =request_post.get('page_size')
        nombre = request_post.get('nombre')
        apellido1 = request_post.get('apellido1')
        rfc = request_post.get('rfc_search')
        estatus = request_post.get('estatus')
        q = Q(pk__isnull=False)


        if tipo_registro != 'no_registrado':
            registrado = True
            declaraciones = Declaraciones.objects.all()
            for dec in declaraciones:
                if not dec.info_personal_fija.pk in usuarios_con_dec:
                    usuarios_con_dec.append(dec.info_personal_fija.pk)

            if nombre and not nombre=="":
                q &= Q(nombres__icontains=nombre)
            if apellido1 and not apellido1=="":
                q &= Q(apellido1__icontains=apellido1)
            if rfc and not rfc=="":
                q &= Q(rfc__icontains=rfc)
            if estatus:
                q &= Q(usuario__is_active = estatus)

            if tipo_registro == 'registrado':
                result = result.filter(pk__in = usuarios_con_dec)

            elif tipo_registro == 'registrado_sindec':
                result = result.exclude(pk__in = usuarios_con_dec)
        else:
            registrado = False
            for info_fija in result:
                usuarios_con_infopersonalfija.append(info_fija.usuario.pk)

            result = User.objects.filter(is_staff=False, is_superuser=False).exclude(pk__in=usuarios_con_infopersonalfija)

            if nombre and not nombre=="":
                q &= Q(first_name__icontains=nombre)
            if apellido1 and not apellido1=="":
                q &= Q(last_name__icontains=apellido1)
            if rfc and not rfc=="":
                q &= Q(username__icontains=rfc)
            if estatus:
                q &= Q(is_active = estatus)
        
        fecha_inicio = False
        fecha_fin_mas_uno = False
        if request_post.get('fecha_inicio_year') and request_post.get('fecha_inicio_month') and request_post.get('fecha_inicio_day'):
            fecha_inicio = date(int(request_post.get('fecha_inicio_year')),int(request_post.get('fecha_inicio_month')),int(request_post.get('fecha_inicio_day')))
            
        if request_post.get('fecha_fin_year') and request_post.get('fecha_fin_month') and request_post.get('fecha_fin_day'):
            fecha_fin_mas_uno = date(int(request_post.get('fecha_fin_year')),int(request_post.get('fecha_fin_month')),int(request_post.get('fecha_fin_day'))) + timedelta(days=1)
        
        #Si el usuario solo  selecciona la fecha de inicio
        if fecha_inicio and not fecha_fin_mas_uno:
            if registrado:
                q &= Q(fecha_inicio__gte=fecha_inicio)
            else:
                q &= Q(date_joined__gte=fecha_inicio)
        #Si el usuario solo  selecciona la fecha de fin
        elif not fecha_inicio and fecha_fin_mas_uno:
            if registrado:
                q &= Q(fecha_inicio__lte=fecha_fin_mas_uno)
            else:
                q &= Q(date_joined__lte=fecha_fin_mas_uno)
        #El usuario desea buscar en un rango de fechas
        elif fecha_inicio and fecha_fin_mas_uno:
            if registrado:
                q &= Q(fecha_inicio__range=[fecha_inicio,fecha_fin_mas_uno])
            else:
                q &= Q(date_joined__range=[fecha_inicio,fecha_fin_mas_uno])

        result = result.filter(q).order_by('pk')
        total_registros = result.count()

        if page and page.isdigit():
            page = int(page)
        else:
            page=1
        if page_size and page_size.isdigit():
            page_size = int(page_size)
        else:
            page_size=10

        paginator = Paginator(result, page_size)
        result = paginator.get_page(page)
        paginas = list(range(1, paginator.num_pages+1))
        result_json = []
        for res in result:
            if registrado:
                nombre_completo = res.nombres + ' ' + res.apellido1 + ' ' + res.apellido2
                fecha = res.fecha_inicio
                rfc = res.rfc
                estatus = res.usuario.is_active 
            else:
                nombre_completo = res.first_name + ' ' + res.last_name
                fecha = res.date_joined
                rfc = res.username
                estatus = res.is_active 

            data = {
                'pk':res.pk,
                'tipo_registro': tipo_registro,
                'nombre_completo': nombre_completo,
                'fecha': fecha,
                'rfc': rfc,
                'estatus': 'Activo' if estatus else 'Inactivo',
            }
            result_json.append(data)
        

        response = {
            'results': result_json,
            'has_next': result.has_next(),
            'has_previous': result.has_previous(),
            'current_page': result.number,
            'total_pages': paginator.num_pages,
            'paginas': paginas,
            'total_registros': total_registros,
            'page_size': page_size
        }
        return JsonResponse(response)


class InfoDeclarantesFormView(View):
    template_name="declaracion/admin/info-declarante.html"

    @method_decorator(login_required(login_url='/login'))
    def get(self,request,*args,**kwargs):
        usuario = self.kwargs['pk']
        context = {
            "tipo_registro": self.kwargs['tipo_registro']
        }

        if request.user.is_staff:
            if context['tipo_registro'] == 'no_registrado':
                result = User.objects.get(pk=usuario)
            else:
                result = InfoPersonalFija.objects.get(pk=usuario)
                declaraciones = Declaraciones.objects.filter(info_personal_fija=result)

                if declaraciones:
                    context.update({"declaraciones": declaraciones})

                    cargo = Encargos.objects.filter(declaraciones=declaraciones[0].pk, cat_puestos__isnull=False).first()
                    if cargo:
                        context.update({"cargo": cargo})


            context.update({"result": result, 'year': date.today().year})
            return render(request,self.template_name,context)
        else:
            return redirect('login')


class InfoUsuarioFormView(View):
    template_name="declaracion/admin/info-usuario.html"

    @method_decorator(login_required(login_url='/login'))
    def get(self,request,*args,**kwargs):

        if request.user.is_superuser:
            result = InfoPersonalFija.objects.get(usuario__pk=self.kwargs['pk'])
            return render(request,self.template_name,{'info':result})
        else:
            return redirect('login')


class InfoDeclaracionFormView(View):
    template_name="declaracion/admin/info-declaracion.html"

    @method_decorator(login_required(login_url='/login'))
    def get(self,request,*args,**kwargs):
        context = {}
        if request.user.is_staff:
            declaracion = Declaraciones.objects.get(pk=self.kwargs['pk'])
            folio_declaracion = str(declaracion.folio)
            
            archivo_pdf = obtener_pdf_existente("declaracion",declaracion)
            if archivo_pdf:
                context.update({"archivo": archivo_pdf})

            context.update(get_context_InformacionPersonal(declaracion))
            context.update(get_context_Intereses(declaracion))
            context.update(get_context_ingresos(declaracion))
            context.update(get_context_activos(declaracion))

            vehiculos = MueblesNoRegistrables.objects.filter(declaraciones=declaracion)
            inversiones = Inversiones.objects.filter(declaraciones=declaracion)
            adeudos = DeudasOtros.objects.filter(declaraciones=declaracion)
            prestamos = PrestamoComodato.objects.filter(declaraciones=declaracion)
            fideicomisos = Fideicomisos.objects.filter(declaraciones=declaracion)
            context.update({"vehiculos": get_context_vehiculos(declaracion)})
            context.update({"inversiones": get_context_inversiones(declaracion)})
            context.update({"adeudos": get_context_deudasotros(declaracion)})
            context.update({"prestamos": get_context_prestamocomodato(declaracion)})
            context.update({"fideicomisos": get_context_fideicomisos(declaracion)})
            context.update({"tipo": self.kwargs['tipo']})

            #Determina la información a mostrar por tipo de declaración
            context.update(set_declaracion_extendida_simplificada(context['info_personal_fija']))

            try:
                fiscal = DeclaracionFiscal.objects.filter(declaraciones=declaracion).first()
                context.update({"fiscal": fiscal})
            except Exception as e:
                return u""
            
            return render(request,self.template_name,context)
        else:
            return redirect('login')


class EliminarUsuarioFormView(View):
    @method_decorator(login_required(login_url='/login'))
    def post(self,request,*args,**kwargs):

        if request.user.is_superuser:
            user = User.objects.get(pk=self.kwargs['pk'])
            user.is_active=False
            user.save()
            return HttpResponse("",status=200)
        else:
            return HttpResponse("", status=500)


class NuevoUsuariosOICFormView(View):
    template_name = 'declaracion/admin/registro_usuario_oic.html'
    template_redirect='declaracion/admin/busqueda-usuarios.html'
    form_redirect = BusquedaUsuariosForm
    is_staff = True

    @method_decorator(login_required(login_url='/login'))
    def get(self, request, *args, **kwargs):

        if not request.user.is_authenticated or not request.user.is_superuser :
            raise Http404()

        return render(request, self.template_name, {
            'form': RegistroUsuarioOICForm(),
            'is_staff': self.is_staff,
            'es_oic': True,

        })

    @method_decorator(login_required(login_url='/login'))
    def post(self, request, *args, **kwargs):
        if not request.user.is_authenticated or not request.user.is_superuser :
            raise Http404()

        registro = RegistroUsuarioOICForm(request.POST) #J

        id_puesto = request.POST.get('cat_puestos')  #J


        if registro.is_valid():
            email = registro.cleaned_data.get('email')
            usuario = registro.cleaned_data.get('usuario')

            password = User.objects.make_random_password()

            nombre = registro.cleaned_data.get("nombres")
            rol = registro.cleaned_data.get("rol")
            apellidos = registro.cleaned_data.get("apellido1")+" "+registro.cleaned_data.get("apellido2")

            user = User.objects.create_user(username=usuario,
                                            email=email,
                                            password=password,
                                            first_name=nombre,
                                            last_name=apellidos

                                            )
            user.is_superuser = registro.cleaned_data.get("rol")
            user.is_staff = True
            user.is_superuser=rol

            user.is_active=False
            user.save()
            
            datos = InfoPersonalFija(
                nombres=nombre,
                apellido1=registro.cleaned_data.get("apellido1"),
                apellido2=registro.cleaned_data.get("apellido2"),
                rfc=usuario,
                curp=registro.cleaned_data.get("usuario"),
                usuario=user,
                nombre_ente_publico=registro.cleaned_data.get("nombre_ente_publico"),
                telefono=registro.cleaned_data.get('telefono'),
                puesto="",#J
                cat_puestos= CatPuestos.objects.get(pk=request.POST.get('cat_puestos'))
            )
            datos.save()

            current_site = get_current_site(request)
            mail_subject = 'Activación de cuenta'
            message = render_to_string('declaracion/admin/acc_active_email_admin.html', {
                'user': user,
                'domain': current_site.domain,
                'uid':urlsafe_base64_encode(force_bytes(user.pk)),
                'token':account_activation_token.make_token(user),
                'protocol': request.scheme,
                'password': password
            })            

            if Valores_SMTP.objects.filter(pk=1).exists():
                smtp = Valores_SMTP.objects.get(pk=1)
                
                try:
                    send_mail=mail_conf()
                    send_mail.estandar_mail_to(mail_subject, smtp.mailaddress, email, message, smtp.mailpassword, smtp.nombre_smtp, smtp.puerto)
                    email_result = "Se ha enviado un correo eléctrónico a la persona que se acaba de registrar como usuario operador del ente."
                except Exception as e:
                    email_result = "No se ha podido enviar un correo electrónico a la persona que se acaba de registrar "

            if self.form_redirect:
                context = {'form':self.form_redirect(),'msg':True,'infopersonalfija':datos,'is_staff':self.is_staff, 'email_result':email_result}
                return render(request,self.template_redirect,context)
            else:
                context= {'form': None, 'msg': True, 'infopersonalfija': datos, 'is_staff': self.is_staff, 'email_result':email_result}
                return render(request, self.template_redirect,context)


        return render(request, self.template_name, {
            'form': registro,
            'is_staff':self.is_staff,
            'es_oic': True,
            'puesto': id_puesto #J
        })


class RegistroDeclaranteFormView(View):
    template_name = 'declaracion/admin/registro_usuario_declarante.html'
    template_redirect='declaracion/admin/busqueda-declarantes.html'
    form_redirect = BusquedaDeclaranteForm
    is_staff = True
    
    @method_decorator(login_required(login_url='/login'))
    def get(self, request, *args, **kwargs):
        editar_id = kwargs.get("pk", False)
        tipo_registro = kwargs.get("tipo_registro")
        data_usuario = None
        form_registro = RegistroUsuarioDeclaranteForm
        model_registro = User
        PUESTO = ""
        preregistro = False

        if editar_id:
            form_registro = RegistroUsuarioDeclaranteEdicionForm
            if tipo_registro == 'registrado' or tipo_registro == "registrado_sindec":             
                data_usuario = InfoPersonalFija.objects.get(pk=editar_id)
                area, puesto, estatus, email = data_usuario.cat_puestos.cat_areas, data_usuario.cat_puestos, data_usuario.usuario.is_active, data_usuario.usuario.email
                PUESTO=puesto.pk                
            else:
                #Edicion usuario preregistrado y todo
                if tipo_registro =="todos":
                    data_usuario = InfoPersonalFija.objects.filter(pk=editar_id).first()
                else:
                    data_user = User.objects.get(pk=editar_id)
                    data_usuario = InfoPersonalFija.objects.filter(usuario__pk=data_user.pk).first()                   
                #Es preregistrado
                if not data_usuario:
                    data_usuario = data_user
                    form_registro = RegistroUsuarioDeclaranteForm
                    preregistro = True
                else:                   
                    area, puesto, estatus, email = data_usuario.cat_puestos.cat_areas, data_usuario.cat_puestos, data_usuario.usuario.is_active, data_usuario.usuario.email
                    PUESTO=puesto.pk    
                    
            data_usuario = model_to_dict(data_usuario)

            #Ya que es un formulario creado manualmewnte y no desde un model, cat_areas no pertenece al info fija,por lo que al cargar los datos al formulario
            #creado este campo no se muestra así que se le asigna una variable donde se guarda el valor del area obtenido desde el campo cat_puestos de info fija
            if tipo_registro == 'registrado' or tipo_registro == 'registrado_sindec' or not preregistro:
                data_usuario["cat_areas"] = area
                data_usuario["cat_puestos"] = puesto
                data_usuario["estatus"] = estatus
                data_usuario["email"] = email


        form_declarante = form_registro(initial=data_usuario)

        if not request.user.is_authenticated or not request.user.is_superuser:
            raise Http404()

        return render(request, self.template_name,{
            'editar': editar_id,
            'form': form_declarante,
            'is_staff': self.is_staff,
            'tipo_registro': tipo_registro,
            'puesto_id':PUESTO,
            'preregistro':preregistro  
        })


    @method_decorator(login_required(login_url='/login'))
    def post(self, request, *args, **kwargs):
        editar_id = kwargs.get("pk", False)
        tipo_registro = kwargs.get("tipo_registro")
        data_usuario = None
        request_post = request.POST
        id_puesto = request.POST.get('cat_puestos') #add JM
        

        if editar_id:
            if tipo_registro == 'registrado' or tipo_registro == "registrado_sindec" or tipo_registro=="todos":
                fecha_inicio = date(int(request_post.get('fecha_inicio_year')),int(request_post.get('fecha_inicio_month')),int(request_post.get('fecha_inicio_day')))
                info_personal_fija_data = InfoPersonalFija.objects.get(pk=editar_id)
                info_personal_fija_data.rfc = request_post.get('rfc')
                info_personal_fija_data.nombres = request_post.get('nombres').upper()
                #if not info_personal_fija_data.nombres or not  info_personal_fija_data.rfc: return redirect('.')
                info_personal_fija_data.apellido1 = request_post.get('apellido1').upper()
                info_personal_fija_data.apellido2 = request_post.get('apellido2').upper()
                #info_personal_fija_data.cat_puestos = CatPuestos.objects.get(pk=request_post.get('cat_puestos'))
                puesto= CatPuestos.objects.get(pk=int(id_puesto)) #Obtenemos el puesto | add J
                info_personal_fija_data.cat_puestos = puesto #Guardar el dato cat_puestos.puesto | add J
                info_personal_fija_data.puesto = str(puesto) #Guardar puesto InfoPersonalFija.puesto  | add J   
                info_personal_fija_data.fecha_inicio = fecha_inicio
                info_personal_fija_data.save()
                
                data_usuario_registrado = User.objects.get(pk=info_personal_fija_data.usuario.id)
                data_usuario_registrado.is_active = request_post.get("estatus")
                data_usuario_registrado.username = request_post.get("rfc")
                data_usuario_registrado.first_name = request_post.get("nombres")
                data_usuario_registrado.last_name = request_post.get("apellido1")
                data_usuario_registrado.email = request_post.get("email")
                data_usuario_registrado.save()
                 
            else:
                data_usuario_preregistrado = User.objects.get(pk=editar_id)
                registro = RegistroUsuarioDeclaranteForm(request_post, instance=data_usuario_preregistrado)
               
                if registro.is_valid():
                    registro.save()
            
            context = {
                    'form':self.form_redirect(),
                    'msg':True,
                    'is_staff':self.is_staff,
                    'editar': editar_id
                }
            return render(request,self.template_redirect,context)

        else:
            registro = RegistroUsuarioDeclaranteForm(request.POST)
            if registro.is_valid():
                datos_usuario = registro.save(commit=False)
                datos_usuario.is_staff = False
                datos_usuario.is_superuser = False
                datos_usuario.is_active = 0
                datos_usuario.save()

                context = {
                    'form':self.form_redirect(),
                    'msg':True,
                    'is_staff':self.is_staff,
                    'editar': editar_id
                }
                return render(request,self.template_redirect,context)
            
            else:
                context = {
                    'form':registro,
                    'is_staff':self.is_staff
                }
                return render(request,self.template_name,context,{'puesto':'id_puesto'})


class EditarUsuarioFormView(View):
    template_name = 'declaracion/admin/registro_usuario_oic.html'
    template_redirect='declaracion/admin/busqueda-usuarios.html'
    form_redirect = BusquedaUsuariosForm
    is_staff = True

    @method_decorator(login_required(login_url='/login'))
    def get(self, request, *args, **kwargs):

        if request.user.is_authenticated and not self.is_staff:

            return redirect('logout')
        info = InfoPersonalFija.objects.get(usuario__pk=self.kwargs['pk'])
        initial = {
            'nombres':info.nombres,
            'apellido1':info.apellido1,
            'apellido2':info.apellido2,
            'nombre_ente_publico':info.nombre_ente_publico,
            'telefono':info.telefono,
            'usuario':info.usuario.username,
            'email':info.usuario.email,
            'rol':info.usuario.is_superuser,
            'estatus':info.usuario.is_active,
            'id':info.usuario_id,
        }

        if info.cat_puestos:
            initial.update({'cat_puestos': info.cat_puestos.pk})#add JM
            initial.update({'cat_areas': info.cat_puestos.cat_areas})

        return render(request, self.template_name, {
            'form': RegistroUsuarioOICForm(initial=initial),
            'is_staff': self.is_staff,
            'editar':True,
            'info':info,
            'es_oic':True,
            'puesto_id': info.cat_puestos.pk #add JM
        })

    @method_decorator(login_required(login_url='/login'))
    def post(self, request, *args, **kwargs):
        registro = RegistroUsuarioOICForm(request.POST)
        id_puesto = request.POST.get('cat_puestos') #add JM
        
        if registro.is_valid():

            id = registro.cleaned_data.get('id')
            user = User.objects.get(pk=id)

            email = registro.cleaned_data.get('email')
            usuario = registro.cleaned_data.get('usuario')
            #rfc = registro.cleaned_data.get('rfc')
            #rfc = rfc.upper()
            nombre = registro.cleaned_data.get("nombres")
            apellidos = registro.cleaned_data.get("apellido1")+" "+registro.cleaned_data.get("apellido2")

            #user.username=rfc
            user.username=usuario
            user.email=email
            user.first_name=nombre
            user.last_name=apellidos

            user.is_superuser = registro.cleaned_data.get("rol")
            user.is_staff = True

            user.is_active=registro.cleaned_data.get("estatus")

            user.save()

            datos = InfoPersonalFija.objects.get(usuario__pk=id)

            datos.nombres=registro.cleaned_data.get("nombres")
            datos.apellido1=registro.cleaned_data.get("apellido1")
            datos.apellido2=registro.cleaned_data.get("apellido2")
            #datos.rfc=rfc
            #datos.curp=registro.cleaned_data.get("rfc")
            datos.nombre_ente_publico=registro.cleaned_data.get("nombre_ente_publico")
            datos.telefono=registro.cleaned_data.get('telefono')
            #Get, trae un objeto QuerySet.
            #Filter, trae un arreglo de objeto QuerySet.
            puesto = CatPuestos.objects.get(pk= int(id_puesto)) #Obtenemos el puesto | add J
            datos.cat_puestos = puesto #Guardar el dato cat_puestos.puesto | add J
            datos.puesto = str(puesto) #Guardar puesto InfoPersonalFija.puesto  | add J   
            datos.save() 
        
            if self.form_redirect:
                return render(request,self.template_redirect,{'form':self.form_redirect(),'msg':False,'infopersonalfija':datos,'is_staff':self.is_staff,'editar':True})
            else:
                return render(request, self.template_redirect, {'form': None, 'msg': False, 'infopersonalfija': datos,'is_staff': self.is_staff,'editar':True})

        else:
            return render(request, self.template_name, {                
                'form': registro,
                'is_staff':self.is_staff,
                'editar':True,
                'es_oic': True,
                'puesto': id_puesto #add JM                
            })
            
    
class DescargarReportesView(View):
    template_name="declaracion/admin/reportes_main.html"

    @method_decorator(login_required(login_url='/login'))
    def get(self, request, *args, **kwargs):
        tipo_reporte = self.kwargs['tipo']
        request_get = request.GET
        form = BusquedaDeclaracionForm(request_get)

        #Fecha para mostrar las declaraciones en el periodo de tiempo introducido
        fin_day = int(request_get.get('fecha_fin_day')) + 1 if int(request_get.get('fecha_fin_day')) <= 27 else int(request_get.get('fecha_fin_day'))
        fecha_fin_mas_uno = date(int(request_get.get('fecha_fin_year')),int(request_get.get('fecha_fin_month')), fin_day )

        fecha_inicio = date(int(request_get.get('fecha_inicio_year')),int(request_get.get('fecha_inicio_month')),int(request_get.get('fecha_inicio_day')))
        fecha_fin = date(int(request_get.get('fecha_fin_year')),int(request_get.get('fecha_fin_month')),int(request_get.get('fecha_fin_day')))
        
        resumen = {
            'total_usuarios': 0,
            'activos':{
                'oic': [],
                'declarantes': [],
                'admin': []
            },
            'inactivos':{
                'oic': [],
                'declarantes': [],
                'admin': []
            },
            'iniciales':{
                'abiertas': 0,
                'cerradas': 0,
                'data': []
            },
            'modificacion':{
                'abiertas': 0,
                'cerradas': 0,
                'data': []
            },
            'conclusion':{
                'abiertas': 0,
                'cerradas': 0,
                'data': []
            },
            'abiertas':[],
            'cerradas':[],
            'usuarios_activos_d_inicial':[],
            'usuarios_activos_d_pendiente':[]
        }

        if tipo_reporte:
            usuarios = User.objects.filter(date_joined__range=[fecha_inicio,fecha_fin_mas_uno])
            declaraciones = Declaraciones.objects.extra(
                select={
                    'patrimonial': 'SELECT max FROM declaracion_secciondeclaracion WHERE  declaracion_secciondeclaracion.seccion_id = 1 AND declaracion_secciondeclaracion.declaraciones_id = declaracion_declaraciones.id',
                    'patrimonial_total': 'SELECT sum(num) FROM declaracion_secciondeclaracion WHERE  declaracion_secciondeclaracion.seccion_id between 2 and 16 AND declaracion_secciondeclaracion.declaraciones_id = declaracion_declaraciones.id',
                    'intereses': 'SELECT max FROM declaracion_secciondeclaracion WHERE  declaracion_secciondeclaracion.seccion_id = 17 AND declaracion_secciondeclaracion.declaraciones_id = declaracion_declaraciones.id',
                    'intereses_total': 'SELECT sum(num) FROM declaracion_secciondeclaracion WHERE  declaracion_secciondeclaracion.seccion_id between 18 and 24 AND declaracion_secciondeclaracion.declaraciones_id = declaracion_declaraciones.id',
                    'fiscal': 'SELECT max FROM declaracion_secciondeclaracion WHERE  declaracion_secciondeclaracion.seccion_id = 25 AND declaracion_secciondeclaracion.declaraciones_id = declaracion_declaraciones.id',
                    'fiscal_total': 'SELECT sum(num) FROM declaracion_secciondeclaracion WHERE  declaracion_secciondeclaracion.seccion_id = 26 AND declaracion_secciondeclaracion.declaraciones_id = declaracion_declaraciones.id'
                }
            )

            #Se realiza el filtro de acuerdo a los parametros recibidos
            if form.is_valid():
                folio = form.cleaned_data.get('folio')
                if folio and not folio=="":
                    declaraciones = declaraciones.filter(folio=uuid.UUID(folio))
                
                tipo = form.cleaned_data.get('tipo')
                if tipo :
                    declaraciones = declaraciones.filter(cat_tipos_declaracion=tipo)
                
                estatus = form.cleaned_data.get('estatus')
                if estatus:
                    declaraciones = declaraciones.filter(cat_estatus=estatus)
                
                filtro_fecha =request_get.get('filtro_fecha')
                if filtro_fecha == '0':
                    declaraciones = declaraciones.filter(fecha_declaracion__range=[fecha_inicio,fecha_fin_mas_uno])
                else:
                    declaraciones = declaraciones.filter(fecha_recepcion__range=[fecha_inicio,fecha_fin_mas_uno])
                
                declaraciones = declaraciones.filter(fecha_declaracion__range=[fecha_inicio,fecha_fin])

            for usuario in usuarios:
                resumen['total_usuarios'] = resumen['total_usuarios'] + 1
                if usuario.is_active == True:
                    #Separa aquellos usuarios que ya tiene una declaración y los que faltan
                    usuario_declaraciones = Declaraciones.objects.filter(info_personal_fija__usuario=usuario, cat_estatus=1, cat_tipos_declaracion=1)
                    usuario_declaraciones_terminadas = Declaraciones.objects.filter(info_personal_fija__usuario=usuario, cat_estatus=4, cat_tipos_declaracion=1)

                    if usuario_declaraciones.count() > 0:
                        resumen['usuarios_activos_d_inicial'].append(usuario)
                    if usuario_declaraciones_terminadas.count() == 0 and usuario_declaraciones.count() == 0:
                        resumen['usuarios_activos_d_pendiente'].append(usuario)
                    
                    #Separa por tipo de usuario
                    if usuario.is_staff and usuario.is_superuser == 0:
                        resumen['activos']['oic'].append(usuario)
                    if (usuario.is_staff == 0 and usuario.is_superuser) or (usuario.is_staff and usuario.is_superuser):
                        resumen['activos']['admin'].append(usuario)
                    if usuario.is_staff == 0 and usuario.is_superuser == 0:
                        resumen['activos']['declarantes'].append(usuario)
                    
                else:
                    #Separa por tipo de usuario
                    if usuario.is_staff and usuario.is_superuser == 0:
                        resumen['inactivos']['oic'].append(usuario)
                    if (usuario.is_staff == 0 and usuario.is_superuser) or (usuario.is_staff and usuario.is_superuser):
                        resumen['inactivos']['admin'].append(usuario)
                    if usuario.is_staff == 0 and usuario.is_superuser == 0:
                        resumen['inactivos']['declarantes'].append(usuario)

            for declaracion in declaraciones:
                #Declaraciones inciales por abiertas y cerradas
                if declaracion.cat_tipos_declaracion.pk == 1:
                    resumen['iniciales']['data'].append(declaracion)
                    if declaracion.cat_estatus.pk == 4:
                        resumen['iniciales']['cerradas'] = resumen['iniciales']['cerradas'] +1
                    else:
                        resumen['iniciales']['abiertas'] = resumen['iniciales']['abiertas'] +1
                
                #Declaraciones modificacion por abiertas y cerradas
                if declaracion.cat_tipos_declaracion.pk == 2:
                    resumen['modificacion']['data'].append(declaracion)
                    if declaracion.cat_estatus.pk == 4:
                        resumen['modificacion']['cerradas'] = resumen['modificacion']['cerradas'] +1
                    else:
                        resumen['modificacion']['abiertas'] = resumen['modificacion']['abiertas'] +1
                
                #Declaraciones conclusion por abiertas y cerradas
                if declaracion.cat_tipos_declaracion.pk == 3:
                    resumen['conclusion']['data'].append(declaracion)
                    if declaracion.cat_estatus.pk == 4:
                        resumen['conclusion']['cerradas'] = resumen['conclusion']['cerradas'] +1
                    else:
                        resumen['conclusion']['abiertas'] = resumen['conclusion']['abiertas'] +1

                #Separa por estatus de declaración sin tomar en cuenta el tip de declaración
                if declaracion.cat_estatus_id == 1:
                    resumen['abiertas'].append(declaracion)
                if declaracion.cat_estatus_id == 4:
                    resumen['cerradas'].append(declaracion)

            context = {
                'declaraciones': declaraciones,
                'tipo_reporte': tipo_reporte,
                'resumen': resumen
            }

            try:
                personalizacion_data = sitio_personalizacion.objects.filter(id=1)
                if personalizacion_data.exists():
                    context.update({'color_encabezado': personalizacion_data[0].color_primario})
            except Exception as e:
                print('error-----------------------', e)
                
            response = HttpResponse(content_type="application/pdf")
            response['Content-Disposition'] = "inline; filename={}_{}.pdf".format(tipo_reporte,usuario.username)
            html = render_to_string(self.template_name, context)

            HTML(string=html,base_url=request.build_absolute_uri()).write_pdf(response,stylesheets=[CSS(settings.STATIC_ROOT + "/app.css")])
            return response


def descargarReporteView(request):
    template_name="declaracion/admin/reportes_main.html"
    request_get = request.GET
    response = {
        "estatus_proceso": 0
    }

    tipo_reporte = request_get.get('tipo_reporte')
    form = BusquedaDeclaracionForm(request_get)

    parametros_busqueda = {
        "tipo_reporte": tipo_reporte,
        "fecha_inicio_day": request_get.get('fecha_inicio_day'),
        "fecha_inicio_month": request_get.get('fecha_inicio_month'),
        "fecha_inicio_year": request_get.get('fecha_inicio_year'),
        "fecha_fin_day": request_get.get('fecha_fin_day'),
        "fecha_fin_month": request_get.get('fecha_fin_month'),
        "fecha_fin_year": request_get.get('fecha_fin_year'),
        "base_url": request.build_absolute_uri(),
        "usuario_oic": request.user.pk,
        "filtro_fecha": request_get.get('filtro_fecha')
    }

    if tipo_reporte:
        #Se realiza el filtro de acuerdo a los parametros recibidos
        if form.is_valid():
            folio = form.cleaned_data.get('folio')
            if folio and not folio=="":
                parametros_busqueda.update({"folio": folio})
            tipo = form.cleaned_data.get('tipo')
            if tipo:
                tipo = CatTiposDeclaracion.objects.get(tipo_declaracion=tipo)
                parametros_busqueda.update({"tipo": tipo.pk})
            estatus = form.cleaned_data.get('estatus')
            if estatus:
                estatus = CatEstatusDeclaracion.objects.get(estatus_declaracion=estatus)
                parametros_busqueda.update({"estatus": estatus.pk})
        
        str_dict = json.dumps(parametros_busqueda)

        tark_pdf = task_crear_pdf("reporte", request.user.pk, str_dict)
        response['estatus_proceso'] = tark_pdf

    else:
        response['estatus_proceso'] = 0
    
    return JsonResponse(response)

def consultaEstatusTaskPDFReporte(request):
    """
    Función que se encarga de de las consultas ajax para obtener el proceso
    """
    response = {}
    tipo_reporte = request.GET.get('tipo_reporte')
    usuario =request.user.pk

    estatus = task_obtener_estatus("reporte",usuario,tipo_reporte)
    response['estatus_proceso'] = estatus

    archivo_pdf =  obtener_pdf_existente("reporte",{"tipo_reporte": tipo_reporte, "usuario": usuario})
    if archivo_pdf:
        response["archivo"] = archivo_pdf

    return JsonResponse(response)

def eliminarProcesoPDFReporte(request):
    return JsonResponse(task_eliminar_background("reporte", request))

def cambiarEstatusDatosPublicosDeclaracion(request):
    response = {}
    declaracion_id = request.GET.get('id_declaracion_datos_publicos')

    declaracion = Declaraciones.objects.get(pk=int(declaracion_id))
    if declaracion:
        declaracion.datos_publicos = not declaracion.datos_publicos
        declaracion.save()

        response.update({"succes": "Dato cambiado"})


    archivo_pdf =  obtener_pdf_existente("declaracion",declaracion)

    if archivo_pdf:
        archivo_pdf_ruta_fisica = archivo_pdf.replace(settings.MEDIA_URL, settings.MEDIA_ROOT)
        
        if os.path.isfile(archivo_pdf_ruta_fisica):
            response.update({"archivo": True})
            os.remove(archivo_pdf_ruta_fisica)

    return JsonResponse(response)
def cambiarEstatusExtemporaneaDeclaracion(request):
    response = {}
    declaracion_id = request.GET.get('id_declaracion_extemporanea')

    declaracion = Declaraciones.objects.get(pk=int(declaracion_id))
    if declaracion:
        declaracion.extemporanea = not declaracion.extemporanea
        declaracion.save()

        response.update({"succes": "Dato cambiado"})


    

    return JsonResponse(response)

class DeclaracionesGraficas(View):
    template_name="declaracion/admin/reportes_graficas.html"

    @method_decorator(login_required(login_url='/login'))
    def get(self,request,*args,**kwargs):
        usuarios = User.objects.all()
        usuarios_activos = usuarios.filter(is_active=1)
        usuarios_baja = usuarios.filter(is_active=0)

        tipos_declaracion = ['Sin declaración']
        for tipo in CatTiposDeclaracion.objects.all():
            tipos_declaracion.append(tipo.codigo)

        context = {
            "total_usuario_activos":len(usuarios_activos),
            "total_usuario_baja":len(usuarios_baja),
            "tipos_declaracion":tipos_declaracion,
            "form":BusquedaGraficasForm(),
            "extra_params": date.today().year,
            "current_url_menu": "graficas"
        }

        return render(request,self.template_name,context)

    @method_decorator(login_required(login_url='/login'))
    def post(self,request,*args,**kwargs):
        return render(request,self.template_name)


class DeclaracionesGraficasData(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request, format = None):
        declaraciones_por_usuario = {'sin_declaracion':0}
        tipos_declaracion = ['Sin declaración']
        request_get = request.GET
        fecha_inicio = date(date.today().year,1,1)
        fecha_fin = date(date.today().year,12,31)

        if request_get.get('year') != None:
            fecha_inicio = date(int(request_get.get('year')),1,1)
            fecha_fin = date(int(request_get.get('year')),12,31)


        #Información que mostrará el promedio de las declaraciones creadas por la cantidad de usuario existentes
        for tipo in CatTiposDeclaracion.objects.all():
            tipos_declaracion.append(tipo.codigo)
            declaraciones_por_usuario.update({tipo.codigo: 0})

        usuarios = User.objects.all()
        usuarios_activos = usuarios.filter(is_active=1,date_joined__range=[fecha_inicio,fecha_fin], is_staff=0)
        usuarios_baja = usuarios.filter(is_active=0,date_joined__range=[fecha_inicio,fecha_fin], is_staff=0)

        declaraciones = Declaraciones.objects.all()
        declaraciones_por_anio = declaraciones.filter(fecha_declaracion__range=[fecha_inicio,fecha_fin])

        for usuario in usuarios_activos:
            usuario_declaraciones = declaraciones_por_anio.filter(info_personal_fija__usuario=usuario)
            if usuario_declaraciones.exists():
                for usu_dec in usuario_declaraciones:
                    declaraciones_por_usuario[usu_dec.cat_tipos_declaracion.codigo]+=1
            else:
                declaraciones_por_usuario['sin_declaracion']+=1

        chartdata = declaraciones_por_usuario.values()

        #Información que mostrara la cantidad de usuarios y declaraciónes creados por año
        meses = ['Enero', 'Febrero','Marzo','Abril','Mayo','Junio','Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre']
        if len(usuarios_activos) > len(declaraciones):
            total_usuarios_declaraciones = len(usuarios_activos)
        else:
            total_usuarios_declaraciones = len(declaraciones)

        usuarios_por_anio = usuarios.filter(date_joined__range=[fecha_inicio,fecha_fin])
        declaraciones_por_mes={}
        usuarios_por_mes={}

        for mes in meses:
            mes_index = meses.index(mes)+1
            declaraciones_mes = declaraciones_por_anio.filter(fecha_declaracion__month=mes_index)
            if declaraciones_mes:
                declaraciones_por_mes.update({mes: len(declaraciones_mes)})
            else:
                declaraciones_por_mes.update({mes:0})

            usuarios_mes = usuarios_por_anio.filter(date_joined__month=mes_index)
            if usuarios_mes:
                usuarios_por_mes.update({mes:len(usuarios_mes)})
            else:
                usuarios_por_mes.update({mes:0})

        data = {
            "labels":tipos_declaracion,
            "lables_meses": meses,
            "chartLabel":"Declaraciones",
            "chartLabel_usuario":"Usuarios",
            "chartdata":chartdata,
            "total_usuario_activos": len(usuarios_activos),
            "total_usuario_baja": len(usuarios_baja),
            "total_usuarios_declaraciones": total_usuarios_declaraciones,
            "chartdata_datos_anuales_declaraciones": declaraciones_por_mes.values(),
            "chartdata_datos_anuales_usuarios": usuarios_por_mes.values(),
            "extra_params": [request_get.get('anio')]
        }
        return Response(data)


def consultaDeclaraciones(request):
    
    if request.user.is_staff:
        result = None
        results_json = []
        request_post=request.POST

        try:
            result = Declaraciones.objects.all()

            folio=request_post.get('folio')
            filtro_fecha=request_post.get('filtro_fecha')
            tipo=request_post.get('tipo')
            estatus=request_post.get('estatus')

            if folio and not folio=="":
                result = result.filter(folio=uuid.UUID(folio))
            if tipo :
                result = result.filter(cat_tipos_declaracion=tipo)
            if estatus:
                result = result.filter(cat_estatus=estatus)

            fecha_inicio = False
            fecha_fin_mas_uno = False
            if request_post.get('fecha_inicio_year') and request_post.get('fecha_inicio_month') and request_post.get('fecha_inicio_day'):
                fecha_inicio = date(int(request_post.get('fecha_inicio_year')),int(request_post.get('fecha_inicio_month')),int(request_post.get('fecha_inicio_day')))
                
            if request_post.get('fecha_fin_day'):
                fin_day = int(request_post.get('fecha_fin_day')) + 1 if int(request_post.get('fecha_fin_day')) <= 27 else int(request_post.get('fecha_fin_day'))
                fecha_fin = date(int(request_post.get('fecha_fin_year')),int(request_post.get('fecha_fin_month')),int(request_post.get('fecha_fin_day')))
                fecha_fin_mas_uno = date(int(request_post.get('fecha_fin_year')),int(request_post.get('fecha_fin_month')), fin_day )
            
            #Si el usuario solo selecciona la fecha de inicio
            if fecha_inicio and not fecha_fin_mas_uno:
                if filtro_fecha == '0':
                    result = result.filter(fecha_declaracion__gte=fecha_inicio)
                else:
                    result = result.filter(fecha_recepcion__gte=fecha_inicio)
            #El usuario desea buscar en un rango de fechas
            elif fecha_inicio and fecha_fin_mas_uno:
                if filtro_fecha == '0':
                    result = result.filter(fecha_declaracion__range=[fecha_inicio,fecha_fin_mas_uno])
                else:
                    result = result.filter(fecha_recepcion__range=[fecha_inicio,fecha_fin_mas_uno])

                
        except Exception as e:
            print("Error al consultar los datos-------------->",e)

        for res in result:
            
            estatus_proceso = False
            archivo = False
            
            #ADD Historicos: Se obtiene el puesto correspondiente a la declaración de acuerdo a su fecha recepción
            if res.cat_estatus.pk == 4:

                try:
                    archivo =  obtener_pdf_existente("declaracion",res)
                except Exception as e:
                    archivo = None
                    

                try:
                    estatus_proceso = task_obtener_estatus("declaracion",res)
                except Exception as e:
                    estatus_proceso = None

                try:
                    encargos = res.encargos_set.filter(cat_puestos__isnull=False)
                    if encargos.count() > 0:
                        encargo = encargos.first()
                        puesto = serialize_empleo_cargo_comision(res, encargo)
                        nivel = puesto["puesto_codigo"]
                except ObjectDoesNotExist:
                    #Se toma el nivel actual del declarante en el puesto de infoFija
                    nivel = res.info_personal_fija.cat_puestos.codigo
            else:
                #Se toma el nivel actual del declarante en el puesto de infoFija
                nivel = res.info_personal_fija.cat_puestos.codigo

            data = {
                'id':res.id,
                'archivo':archivo,
                'estatus_proceso': estatus_proceso,
                'folio':res.folio,
                'cat_tipos_declaracion':res.cat_tipos_declaracion.codigo,
                'avance':res.avance,
                'extendida': 'No' if int(nivel) <= int(settings.LIMIT_DEC_SIMP) else 'Sí',
                'extemporanea': res.extemporanea,
                'limit_simp': settings.LIMIT_DEC_SIMP,
                'extemporanea':res.extemporanea,
                'fecha_declaracion':res.fecha_declaracion.strftime('%d-%m-%Y') if res.fecha_declaracion else 'N/A',
                'fecha_recepcion':res.fecha_recepcion.strftime('%d-%m-%Y') if res.fecha_recepcion else 'N/A',
                'cat_estatus':res.cat_estatus.estatus_declaracion,
                'cat_estatus_pk':res.cat_estatus.pk,
                'datos_publicos':res.datos_publicos,
                'nombre':res.info_personal_fija.nombres,
                'apellido_paterno': res.info_personal_fija.apellido1,
                'apellido_materno': res.info_personal_fija.apellido2,
                'rfc': res.info_personal_fija.rfc,
                'puesto': res.info_personal_fija.cat_puestos.puesto #add historico puestos
            }

            results_json.append(data) 
            

        response = {
            'results': results_json,
        }
        
        

        return JsonResponse(response) 

def consultarDeclarantesExcel(request):
    print("-------------------------------ya entro a bck")
    if request.user.is_staff:
        print("----------------------entro en if")
        request_post = request.POST
        form = BusquedaDeclaranteForm(request_post)
        usuarios_con_infopersonalfija = []
        usuarios_con_dec = []
        result = None
        response = {}

        result = InfoPersonalFija.objects.filter(usuario__is_staff=False, usuario__is_superuser=False)
        print(result)
        tipo_registro = request_post.get('tipo_registro')
        nombre = request_post.get('nombre')
        apellido1 = request_post.get('apellido1')
        rfc = request_post.get('rfc_search')
        estatus = request_post.get('estatus')
        q = Q(pk__isnull=False)


        if tipo_registro != 'no_registrado':
            registrado = True
            declaraciones = Declaraciones.objects.all()
            for dec in declaraciones:
                if not dec.info_personal_fija.pk in usuarios_con_dec:
                    usuarios_con_dec.append(dec.info_personal_fija.pk)

            if nombre and not nombre=="":
                q &= Q(nombres__icontains=nombre)
            if apellido1 and not apellido1=="":
                q &= Q(apellido1__icontains=apellido1)
            if rfc and not rfc=="":
                q &= Q(rfc__icontains=rfc)
            if estatus:
                q &= Q(usuario__is_active = estatus)

            if tipo_registro == 'registrado':
                result = result.filter(pk__in = usuarios_con_dec)

            elif tipo_registro == 'registrado_sindec':
                result = result.exclude(pk__in = usuarios_con_dec)
        else:
            registrado = False
            for info_fija in result:
                usuarios_con_infopersonalfija.append(info_fija.usuario.pk)

            result = User.objects.filter(is_staff=False, is_superuser=False).exclude(pk__in=usuarios_con_infopersonalfija)

            if nombre and not nombre=="":
                q &= Q(first_name__icontains=nombre)
            if apellido1 and not apellido1=="":
                q &= Q(last_name__icontains=apellido1)
            if rfc and not rfc=="":
                q &= Q(username__icontains=rfc)
            if estatus:
                q &= Q(is_active = estatus)
        
        fecha_inicio = False
        fecha_fin_mas_uno = False
        if request_post.get('fecha_inicio_year') and request_post.get('fecha_inicio_month') and request_post.get('fecha_inicio_day'):
            fecha_inicio = date(int(request_post.get('fecha_inicio_year')),int(request_post.get('fecha_inicio_month')),int(request_post.get('fecha_inicio_day')))
            
        if request_post.get('fecha_fin_year') and request_post.get('fecha_fin_month') and request_post.get('fecha_fin_day'):
            fecha_fin_mas_uno = date(int(request_post.get('fecha_fin_year')),int(request_post.get('fecha_fin_month')),int(request_post.get('fecha_fin_day'))) + timedelta(days=1)
        
        #Si el usuario solo  selecciona la fecha de inicio
        if fecha_inicio and not fecha_fin_mas_uno:
            if registrado:
                q &= Q(fecha_inicio__gte=fecha_inicio)
            else:
                q &= Q(date_joined__gte=fecha_inicio)
        #Si el usuario solo  selecciona la fecha de fin
        elif not fecha_inicio and fecha_fin_mas_uno:
            if registrado:
                q &= Q(fecha_inicio__lte=fecha_fin_mas_uno)
            else:
                q &= Q(date_joined__lte=fecha_fin_mas_uno)
        #El usuario desea buscar en un rango de fechas
        elif fecha_inicio and fecha_fin_mas_uno:
            if registrado:
                q &= Q(fecha_inicio__range=[fecha_inicio,fecha_fin_mas_uno])
            else:
                q &= Q(date_joined__range=[fecha_inicio,fecha_fin_mas_uno])

        result = result.filter(q).order_by('pk')
        


        
        result_json = []
        for res in result:
            if registrado:
                nombre_completo = res.nombres + ' ' + res.apellido1 + ' ' + res.apellido2
                fecha = res.fecha_inicio
                rfc = res.rfc
                estatus = res.usuario.is_active 
            else:
                nombre_completo = res.first_name + ' ' + res.last_name
                fecha = res.date_joined
                rfc = res.username
                estatus = res.is_active 

            data = {
                'pk':res.pk,
                'tipo_registro': tipo_registro,
                'nombre_completo': nombre_completo,
                'fecha': fecha,
                'rfc': rfc,
                'estatus': 'Activo' if estatus else 'Inactivo',
            }
            result_json.append(data)
        

        response['results'] = result_json
        
        return JsonResponse(response)
