# -*- coding: UTF-8 -*-
from __future__ import unicode_literals
import os
import uuid, re
from itertools import chain
from weasyprint import HTML, CSS
from django.views import View
from django.contrib import messages
#!/usr/bin/python
# -*- coding: latin-1 -*-
# -*- coding: utf-8 -*-
from django.utils.encoding import force_text
from django.utils.http import urlsafe_base64_decode
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.auth.views import PasswordResetView
from django.http import HttpResponseRedirect, HttpResponse, JsonResponse
from django.views.generic import (FormView, RedirectView, TemplateView, ListView)
from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, update_session_auth_hash
from django.urls import reverse_lazy, reverse, resolve
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm
from sitio.forms import LoginForm, PasswordResetForm
from sitio.util import account_activation_token
from declaracion.views.utils import (campos_configuracion_todos,declaracion_datos, 
                                    validar_declaracion,set_declaracion_extendida_simplificada,
                                    task_crear_pdf, task_obtener_estatus,
                                    obtener_pdf_existente, task_eliminar_background)
from declaracion.forms import ConfirmacionForm
from django.template.loader import render_to_string
from declaracion.models import (Declaraciones, InfoPersonalVar,
                                InfoPersonalFija, DatosCurriculares, Encargos,
                                ExperienciaLaboral, ConyugeDependientes,
                                Observaciones, SeccionDeclaracion, Secciones, IngresosDeclaracion, 
                                MueblesNoRegistrables, BienesInmuebles, ActivosBienes, BienesPersonas, 
                                BienesMuebles,SociosComerciales,Membresias, Apoyos,ClientesPrincipales,
                                BeneficiosGratuitos, Inversiones, DeudasOtros, PrestamoComodato, DeclaracionFiscal,
                                Fideicomisos)
from declaracion.models.catalogos import CatPuestos, CatAreas
from .models import declaracion_faqs as faqs, sitio_personalizacion 
from .forms import Personalizar_datosEntidadForm
import requests
from os import path
import json
from django.contrib.auth.models import User
from django.core.cache import cache
import base64

from datetime import datetime, date
from fnmatch import fnmatch
import redis
import time

from declaracion.views.confirmacion import (get_context_InformacionPersonal,get_context_Intereses,get_context_pasivos,
                                            get_context_ingresos,get_inmuebles,get_context_activos, get_context_activos,
                                            get_context_vehiculos, get_context_inversiones, get_context_deudasotros,
                                            get_context_prestamocomodato, get_context_fideicomisos)

from django.conf import settings
from io import BytesIO
from django.shortcuts import render
from reportlab.pdfgen import canvas
from django.views.generic import View
from django.http import HttpResponse
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch,mm,cm
from reportlab.lib.utils import ImageReader  

class IndexView(View):
    template_name = "sitio/index.html"
    context = {}
    
    def get(self, request):
        return render(request, self.template_name, self.context)


class FAQView(View):
    template_name = "sitio/faqs.html"
    context = {"current_url_menu":"preguntas-frecuentes"}

    def get(self, request):
        queryset = faqs.objects.all().order_by("orden").exclude(orden=0)
        self.context.update({'questions': queryset})
        return render(request, self.template_name, self.context)


class PersonalizacionDatosEntidadView(View):
    """
     ------------------------------------------------------------
        Clase para modificar los datos de la entidad del sistema sin el uso del admin
    """

    template_name = "sitio/personalizar/datosentidad.html"
    context = {}

    @method_decorator(login_required(login_url='/login'))
    def get(self, request):
        if request.user.is_superuser:
            try:
                datos = sitio_personalizacion.objects.all().first()
                form = Personalizar_datosEntidadForm(request)
            except Exception as e:
                datos = None
                form = None
            
            self.context["datos"] = datos
            self.context["form"] = form
            return render(request, self.template_name, self.context)
        else:
            return redirect('index')

    @method_decorator(login_required(login_url='/login'))
    def pos(self, request):
        if request.user.is_superuser:
            try:
                datos = sitio_personalizacion.objects.all().first()
                form = Personalizar_datosEntidadForm(request)
            except Exception as e:
                datos = None
                form = None
            self.context["datos"] = datos
            self.context["form"] = form
            return render(request, self.template_name, self.context)
        else:
            return redirect('index')
    

class LoginView(FormView):
    form_class = AuthenticationForm
    template_name = "sitio/login.html"
    success_url =  reverse_lazy("declaracion:perfil")
    context = {}
    try:
        cap_webkey =sitio_personalizacion.objects.first().google_captcha_sitekey

    except Exception as e:
        cap_webkey =''



    def get(self, request, *args, **kwargs):
        cap_bool =sitio_personalizacion.objects.first().recaptcha

        if request.user.is_authenticated:
            return HttpResponseRedirect(self.get_success_url())
        else:
            context = {'form': LoginForm(), 'cap_webkey':self.cap_webkey, 'cap_bool':cap_bool}
            return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        username = request.POST.get('username')
        try:
            user = User.objects.get(username=username)
            if user.password == '':
                url = reverse('password_reset')
                return HttpResponseRedirect(url + "?rfc=%s" % (username))
        except:
            pass
        form = LoginForm(request.POST)
    
        try:
            ente_p =sitio_personalizacion.objects.first().nombre_institucion
            cap_secret =sitio_personalizacion.objects.first().google_captcha_secretkey
            cap_bool =sitio_personalizacion.objects.first().recaptcha
        except Exception as e:
            ente_p = 'Secretaría Ejecutiva'
            cap_secret =''
            
        if cap_bool:
            captcha_token=request.POST.get("g-recaptcha-response")
            cap_url="https://www.google.com/recaptcha/api/siteverify"
            cap_data={"secret":cap_secret,"response":captcha_token}
            cap_server_response=requests.post(url=cap_url,data=cap_data)
            cap_json=json.loads(cap_server_response.text)

            if cap_json["success"]==True:
                valido_captcha = True
            else:
                error="Llenar recaptcha, por favor"
                valido_captcha = False
        else:
            valido_captcha = True
        
        num=cache.get_or_set(username,0,300)
       
        if num<5:
            if valido_captcha:
                
                if form.is_valid():
                    login(request,user, backend='django.contrib.auth.backends.ModelBackend')
                    return HttpResponseRedirect(self.get_success_url())
                    cache.set(username,0,300)
                else:
                    context = {'form': form,'cap_webkey':self.cap_webkey,
                'cap_bool':cap_bool}

                    num=cache.get(username)
                    if num:
                        num=num+1
                        cache.set(username,num,300)
                    else:
                        cache.set(username,1,300)

                    return render(request,self.template_name, context)

                return super(LoginView, self).post(request, *args, **kwargs)
            else:
                context = {'form': form,'cap_webkey':self.cap_webkey,
                'cap_bool':cap_bool, 'error':error}
                return render(request,self.template_name, context)
        else:
            error="Exceso de intentos, intente más tarde."
            context = {'form': form,'cap_webkey':self.cap_webkey,
            'cap_bool':cap_bool, 'error':error}
            return render(request,self.template_name, context)  


    def form_valid(self, form):
        login(self.request, form.get_user(), backend='django.contrib.auth.backends.ModelBackend')
        return super(LoginView, self).form_valid(form)

class LogoutView(RedirectView):
    pattern_name = 'login'

    def get(self, request, *args, **kwargs):
        logout(request)
        return super(LogoutView, self).get(request, *args, **kwargs)


def activar(request, uidb64, token):
    """
    Function activar se encarga de activar al usuario en respuesta a la confirmación de su correo
    """
    try:
        uid = force_text(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except(TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None
    if user is not None and account_activation_token.check_token(user, token):
        user.is_active = True
        user.save()
        login(request, user, backend='django.contrib.auth.backends.ModelBackend')
        messages.success(request, '¡Tu cuenta a sido activada. ¡Cambia tu contraseña!')
        return redirect('cambiar')
    else:
        return HttpResponse('¡El enlace es invalido!')


class DeclaracionesPreviasView(View):
    template_name = "sitio/declaraciones-previas.html"

    @method_decorator(login_required(login_url='/login'))
    def get(self, request, *args, **kwargs):
        declaraciones = Declaraciones.objects.filter(
            cat_estatus_id = 4,
            info_personal_fija__usuario=self.request.user
        )

        #Se recorren las declaración para buscar aquellas que tienen un archivo pdf creado
        declaraciones_archivos = []
        for declaracion in declaraciones:
            declaracion_objc = {"declaracion": declaracion, "archivo": ""}

            archivo_pdf =  obtener_pdf_existente("declaracion",declaracion)            
            if archivo_pdf:
                declaracion_objc["archivo"] = archivo_pdf
            
            estatus = task_obtener_estatus("declaracion",declaracion)
            declaracion_objc["estatus_proceso"] = estatus

            #Se verfica que el proceso se ejecuto cuando el usuario cerro su declaración mediante la fecha
            if date.today() == declaracion.fecha_recepcion.date() and not archivo_pdf:
                declaracion_objc["cierre_declaracion"] = True

            declaraciones_archivos.append(declaracion_objc)
        
        return render(request, self.template_name, {"declaraciones": declaraciones_archivos})


def consultaObservacionesDeclaracion(request):
    declaracion_id = int(request.GET.get('declaracion'))
    declaracion = Declaraciones.objects.get(pk=declaracion_id)
    simp_exten = declaracion.info_personal_fija.cat_puestos.codigo

    if simp_exten > settings.LIMIT_DEC_SIMP:
        simplificada = {"declaraciones":declaracion}
    else:
        simplificada = {"declaraciones":declaracion, "seccion__simp":1}

    seccionesDeclaracion = SeccionDeclaracion.objects.filter(**simplificada).exclude(seccion__pk__in=[3,25,26]).order_by('seccion__pk')
    response = {"declaracion": declaracion_id, "secciones_observaciones": {}}

    for sec_dec in seccionesDeclaracion:
        if sec_dec.seccion.level == 0:
            if not sec_dec.seccion.seccion in response:
                response["secciones_observaciones"].update({sec_dec.seccion.pk: {"seccion": sec_dec.seccion.seccion, "subsecciones": {}}})
        else:
            response["secciones_observaciones"][sec_dec.seccion.parent.pk]["subsecciones"].update({
                sec_dec.seccion.seccion: {
                    "seccion_orden": sec_dec.seccion.order,
                    "seccion_url": sec_dec.seccion.url
                }
            })
            if sec_dec.observaciones:
                observacion_date = sec_dec.observaciones.updated_at
                response["secciones_observaciones"][sec_dec.seccion.parent.pk]["subsecciones"][sec_dec.seccion.seccion].update({
                    "observacion_last_update": observacion_date.strftime("%d/%m/%Y - %H:%M"),
                    "observacion_id": sec_dec.observaciones.pk,
                    "observacion": sec_dec.observaciones.observacion
                })

    return JsonResponse(response)

def guardarObservacionesDeclaracion(request):
    data = request.POST
    declaracion = data.get('declaracion')
    observaciones = json.loads(data.get('campos'))

    for observacion in observaciones:
        if "id" in observacion:
            if observacion["id"] == "null" and observacion["observacion"] != "":
                new_observacion = Observaciones(observacion=observacion["observacion"])
                new_observacion.save()

                update_seccion = SeccionDeclaracion.objects.get(declaraciones__pk=declaracion,seccion__url=observacion["seccion"])
                update_seccion.observaciones = new_observacion
                update_seccion.save()

            elif observacion["id"] != "null":
                dec_observaciones = Observaciones.objects.get(pk=int(observacion["id"]))

                if dec_observaciones.observacion != observacion["observacion"]:
                    dec_observaciones.observacion = observacion["observacion"]
                    dec_observaciones.save()

    response = {"mensaje": "SE HAN GUARDADO LOS DATOS"}

    return JsonResponse(response)


def consultaEstatusTaskPDFDeclaracion(request):
    """
    Función que se encarga de de las consultas ajax para obtener el proceso
    """
    response = {}
    declaracion_id = int(request.GET.get('declaracion'))
    declaracion = Declaraciones.objects.get(pk=declaracion_id)
    tipo_pdf = "declaracion"

    if request.GET.get("publica"):
        tipo_pdf = "declaracion_publica"

    estatus = task_obtener_estatus(tipo_pdf,declaracion)
    response['estatus_proceso'] = estatus

    archivo_pdf =  obtener_pdf_existente(tipo_pdf,declaracion)
    if archivo_pdf:
        response["archivo"] = archivo_pdf

    return JsonResponse(response)


def crearPDFDeclaracion(request):
    response = {}
    tipo = "declaracion"
    declaracion_id = int(request.GET.get('declaracion'))
    declaracion_publica = request.GET.get('publica') if request.GET.get('publica') else False
    declaracion = Declaraciones.objects.get(pk=declaracion_id)

    if declaracion_publica:
        tipo = "declaracion_publica"
    
    task_crear_pdf(tipo,declaracion, request.build_absolute_uri())

    response['estatus_proceso'] = 10
    return JsonResponse(response)


def eliminarProcesoPDF(request):
    
    return JsonResponse(task_eliminar_background("declaracion",request))


class DeclaracionesPreviasDescargarView(View):
    template_name = "sitio/descargar.html"

    @method_decorator(login_required(login_url='/login'))
    def get(self, request, *args, **kwargs):
        usuario = request.user

        try:
            folio_declaracion = self.kwargs['folio']
            declaracion = Declaraciones.objects.filter(folio=uuid.UUID(folio_declaracion)).first()
            if 'user' in request:
                usuario = request.user
            else:
                usuario = declaracion.info_personal_fija.usuario.pk
        except Exception :
            folio_declaracion = None

        context = {}

        declaracion = Declaraciones.objects.filter(folio=uuid.UUID(folio_declaracion), info_personal_fija__usuario=usuario).all()[0]
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
        context.update({"valor_privado_texto": "VALOR PRIVADO"})

        
        if declaracion.datos_publicos == False:
           context.update({"campos_privados": campos_configuracion_todos('p')})

        #Determina la información a mostrar por tipo de declaración
        context.update(set_declaracion_extendida_simplificada(context['info_personal_fija']))

        try:
            fiscal = DeclaracionFiscal.objects.filter(declaraciones=declaracion).first()
            context.update({"fiscal": fiscal})
        except Exception as e:
            return u""

        usuario_ = User.objects.get(pk=usuario)

        #Genera el archivo PDF
        response = HttpResponse(content_type="application/pdf")
        usernamePDF = usuario_.username[0:5]
        response['Content-Disposition'] = "inline; filename={}_{}.pdf".format(usernamePDF,declaracion.cat_tipos_declaracion)
        html = render_to_string(self.template_name, context)

        HTML(string=html,base_url=request.build_absolute_uri()).write_pdf(response,stylesheets=[CSS(settings.STATIC_ROOT + "/app.css")])

        return response


class DeclaracionesPreviasVerView(View):
    template_name = "sitio/ver_declaracion.html"
    
    @method_decorator(login_required(login_url='/login'))
    def get(self, request, *args, **kwargs):
        template_name = "sitio/ver_declaracion.html"
        folio_declaracion = self.kwargs['folio']
        context = {
            'folio_declaracion': folio_declaracion
        }
        declaracion = Declaraciones.objects.filter(
            cat_estatus_id = 4,
            info_personal_fija__usuario=self.request.user,
            folio=uuid.UUID(folio_declaracion)
        )
        declaracion = declaracion.first()

        if declaracion:
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

            try:
                fiscal = DeclaracionFiscal.objects.filter(declaraciones=declaracion).first()
                context.update({"fiscal": fiscal})
            except Exception as e:
                return u""

            #Determina la información a mostrar por tipo de declaración
            context.update(set_declaracion_extendida_simplificada(context['info_personal_fija']))
        else:
            template_name="404.html"

        return render(request, template_name, context)

class CambioPasswordView(View):
    template_name = 'sitio/cambio-password.html'

    @method_decorator(login_required(login_url='/login'))
    def get(self, request, *args, **kwargs):
        form = PasswordChangeForm(request.user)

        return render(request, self.template_name, {
            'form': form
        })

    @method_decorator(login_required(login_url='/login'))
    def post(self, request, *args, **kwargs):
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            if request.user.check_password(form.cleaned_data['new_password2']):
                messages.error(request,"Tu nueva contraseña es idéntica a la actual")
                return render(request, self.template_name, {
                    'form': form
                })

            user = form.save()
            update_session_auth_hash(request, user)  # Important!
            messages.success(request, '¡Tu contraseña a sido cambiada!')

            return redirect('declaracion:perfil')

        return render(request, self.template_name, {
                'form': form
        })

class PasswordResetRFCView(PasswordResetView):
    from_email=settings.EMAIL_SENDER
    form_class = PasswordResetForm
    def get(self,request,*args,**kwargs):
        rfc = request.GET.get('rfc')

        try:
            obj = User.objects.get(username=rfc,password='')
            form = PasswordResetForm(initial={'rfc':obj.username})
            return render(request,self.template_name,{'form':form})
        except Exception: # as e:
            return render(request, self.template_name, {'form': PasswordResetForm()})

    def form_valid(self, form):
        opts = {
            'use_https': self.request.is_secure(),
            'token_generator': self.token_generator,
            'from_email': self.from_email,
            'email_template_name': self.email_template_name,
            'subject_template_name': self.subject_template_name,
            'request': self.request,
            'html_email_template_name': self.html_email_template_name,
            'extra_email_context': self.extra_email_context,
        }

        if form.save(**opts):
            return HttpResponseRedirect(self.get_success_url())
        else:
            content = "<center><div style=\"margin-top: 3rem;\"><img src=\"{}\"><h1>El usuario no ha sido encontrado</h1><a href=\"/password_reset/\">REGRESAR</a></div></center>".format("/static/src/img/404.png")
            return HttpResponse(content=content,status=500)


class PersonalizacionCatalogoPuestosView(View):
    """
        ------------------------------------------------------------
        Clase para editar, crear, borrar los puestos usados en el sistema
    """
    template_name = "sitio/personalizar/catpuestos.html"
    context = {}

    @method_decorator(login_required(login_url='/login'))
    def get(self, request, pkid=None):
        if request.user.is_superuser or request.user.is_staff:
            current_url = resolve(request.path_info).url_name
            if ("_editar" in current_url or "_eliminar" in current_url or "_agregar" in current_url) and current_url != None: 
                return redirect("peronalizar_catpuestos")

            self.context["puestos"] = CatPuestos.objects.filter(default=True).all()
            self.context["areas"] = CatAreas.objects.all()
            return render(request, self.template_name, self.context)
        else:
            return redirect("index")
    
    # ToDo agregar multiples puestos a la vez mediante json
    @method_decorator(login_required(login_url='/login')) 
    def post(self, request, pkid=None):
        if request.user.is_staff:
            current_url = resolve(request.path_info).url_name
            
            if "_editar" in current_url and current_url != None: 

                puesto = request.POST.get("nuevo_puesto")
                codigo = request.POST.get("nuevo_puesto_codigo")
                area = request.POST.get("nueva_area")
                result = self.editar(pkid, puesto, codigo, area)

                if result != True:
                    return JsonResponse({"messages": "Surgio un problema con los datos de su puesto, valide toda la información", "tipo": "error"})
                else:
                    return JsonResponse({"messages": "Editado","tipo": "succes"})
                    
            if "_eliminar" in current_url and current_url != None:
                puesto = CatPuestos.objects.get(pk=pkid).puesto
                result = self.eliminar(pkid)

                if result != True:
                    mensaje_error = "Ha surgido un error al intentar elminar el registro"

                    if '1451' in result:
                        u"{} {}".format
                        mensaje_error = u"El puesto - {} - no se puede borrar debido a que el puesto se esta utilizando por un o varios usuarios".format(puesto)

                    return JsonResponse({"messages": mensaje_error,"tipo": "error"})
                else:
                    return JsonResponse({"messages": u"Puesto - {} - desactivado con éxito ".format(puesto), "tipo": "succes"})

            if "_agregar" in current_url and current_url != None:
                value = request.POST.get("input-puesto-agregar")
                codigo = request.POST.get("input-puesto_codigo-agregar")
                area_valuea = request.POST.get("input-puesto_area-agregar")
                value = value.strip()
                value_empty = re.sub(r'[^\w]', '', value)

                if value_empty == "" or value_empty is None:
                    self.context["messages"] = {"El puesto no puede ser nulo y solo debe contener letras"}
                else:
                    result = self.agregar(value, codigo, area_valuea)
                    if result != True:
                        self.context["messages"] = {result}
                    else:
                        return JsonResponse({"message": "agregado"})

            queryset = CatPuestos.objects.all()
            self.context["puestos"] = queryset
            return render(request, self.template_name, self.context)
        else:
            return redirect("index")
    
    def editar(self, id, puesto_txt, codigo, area):
        try:
            obj = CatPuestos.objects.get(pk=id)
            obj.puesto=puesto_txt
            obj.codigo=codigo
            obj.cat_areas=CatAreas.objects.get(pk=area)
            obj.save()
        except Exception as e:
            return e
        return True

    def eliminar(self, id):
        try:
            obj = CatPuestos.objects.get(pk=id)
            obj.default = True
            obj.save()
        except Exception as e:
            return str(e) + " " + str(id)
        return True
    
    def agregar(self, value, codigo, area):
        try:
            area = CatAreas.objects.get(pk=area)
            obj = CatPuestos(puesto=value, cat_areas=area,codigo=codigo)
            obj.save()
        except Exception as e:
            if not area:
                return 'falta área de asignacion del puesto'
                
            return 'No se puedo agregar el puesto, validar datos'
        return True

class PersonalizacionCatalogoAreasView(View):
    template_name = "sitio/personalizar/catareas.html"
    context = {}

    @method_decorator(login_required(login_url='/login'))
    def get(self, request, pkid=None):
        if request.user.is_superuser or request.user.is_staff:
            current_url = resolve(request.path_info).url_name
            if ("_editar" in current_url or "_eliminar" in current_url or "_agregar" in current_url) and current_url != None: 
                return redirect("peronalizar_catareas")

            self.context["areas"] = CatAreas.objects.all()
            return render(request, self.template_name, self.context)
        else:
            return redirect("index")
    
    @method_decorator(login_required(login_url='/login')) 
    def post(self, request, pkid=None):
        if request.user.is_staff:
            current_url = resolve(request.path_info).url_name
            if "_editar" in current_url and current_url != None: 

                area = request.POST.get("nueva_area")
                codigo = request.POST.get("nueva_area_codigo")
                result = self.editar(pkid,area,codigo)
                
                if result != True:
                    return JsonResponse({"messages": "Surgio un problema con los datos de su área, valide toda la información", "tipo": "error"})
                else:
                    return JsonResponse({"messages": "Editado","tipo": "succes"})

            if "_eliminar" in current_url and current_url != None: 
                area = CatAreas.objects.get(pk=pkid).area
                result = self.eliminar(pkid)
                if result != True:
                    mensaje_error = "Ha surgido un error al intentar elminar el registro"

                    if '1451' in result:
                        u"{} {}".format
                        mensaje_error = u"El área - {} - no se puede borrar debido a que existe un puesto que hace referencia a esta área".format(area)

                    return JsonResponse({"messages": mensaje_error,"tipo": "error"})
                else:
                    return JsonResponse({"messages": u"Área - {} - eliminada con éxito ".format(area), "tipo": "succes"})

            if "_agregar" in current_url and current_url != None:
                value_area = request.POST.get("input-area-agregar")
                value_codigo = request.POST.get("input-area-codigo-agregar")
                value = value_area.strip()
                value = re.sub(r'[^\w]', '', value)
                if value == "" or value is None:
                    self.context["messages"] = {"El área no puede ser nulo y solo debe contener letras"}
                else:
                    result = self.agregar(value_area,value_codigo)
                    if result != True:
                        self.context["messages"] = {result}
                    else:
                        return JsonResponse({"message": "agregado"})

            queryset = CatAreas.objects.all()
            self.context["areas"] = queryset
            return render(request, self.template_name, self.context)
        else:
            return redirect("index")
    
    def editar(self, id, area_txt, codigo):
        try:
            obj = CatAreas.objects.get(pk=id)
            obj.area=area_txt if area_txt else ''
            obj.codigo = codigo if codigo else ''
            obj.save()
        except Exception as e:
            return e
        return True

    def eliminar(self, id):
        try:
            obj = CatAreas.objects.get(pk=id)
            obj.delete()
        except Exception as e:
            return str(e) + " " + str(id)
        return True
    
    def agregar(self, value_area, value_codigo):
        try:
            obj = CatAreas(area=value_area,codigo=value_codigo)
            obj.save()
        except Exception as e:
            return 'No se puedo agregar el área, validar datos'
        return True

def GenerarHTMLView(request):
    template_name='sitio/generar_html.html'

    years=[]

    declaracionInicial = Declaraciones.objects.filter(cat_estatus_id=4, cat_tipos_declaracion_id=1).all().order_by('fecha_recepcion')
    declaracionMod = Declaraciones.objects.filter(cat_estatus_id=4, cat_tipos_declaracion_id=2).all()
    declaraciones = Declaraciones.objects.filter(cat_estatus_id=4).all()

    for dec in declaraciones:
        if not dec.fecha_recepcion.year in years:
            years.append(dec.fecha_recepcion.year)

    areas = CatAreas.objects.all()

    context = {
    'declaracionInicial':declaracionInicial,
    'declaracionMod':declaracionMod,
    'areas':areas,
    'years':years
    }

    html=render_to_string(template_name, context)

    archivo=open("prueba.html","w")
    archivo.write(html)
    archivo.close()
    
    return render(request, template_name, context)



def GenerarHTMLView2(request):
    template_name='sitio/generar_html.html'

    html="<html><head></head><body>"

    declaracion = Declaraciones.objects.filter(cat_estatus_id=4).all()

    for dec in declaracion:
        usernamePDF = dec.info_personal_fija.rfc[0:5]
        html=html+'<br><a target="blank" href="/media/declaraciones/'+dec.cat_tipos_declaracion.codigo+'/'+str(dec.fecha_recepcion.year)+'/'+dec.info_personal_fija.cat_puestos.cat_areas.codigo+'/'+usernamePDF +'_'+str(dec.cat_tipos_declaracion)+'.pdf" >'+ usernamePDF+'_'+str(dec.cat_tipos_declaracion)+'.pdf</a>'

    html = html+"</body></html>"
    archivo=open("/templates/sitio/generar_html.html","r")
    archivo.write(html)
    archivo.close()
        
    context = {
    'html':html
    }
    
    return render(request, template_name, context)


class PdfConfirmacion(View):
    template_name="sitio/comprobante.html"

    @method_decorator(login_required(login_url='/login'))
    def get(self,request,*args,**kwargs):
        context = {}
        
        declaracion = Declaraciones.objects.get(pk=self.kwargs['pk'])
        usuario = declaracion.info_personal_fija.usuario.pk

        folio_declaracion = str(declaracion.folio)
        context.update({"declaracion": declaracion})
        context.update(get_context_InformacionPersonal(declaracion))


        response = HttpResponse(content_type="application/pdf")
        response['Content-Disposition'] = "inline; filename={}_comprobante.pdf".format(folio_declaracion)
        html = render_to_string(self.template_name, context)

        HTML(string=html,base_url=request.build_absolute_uri()).write_pdf(response,stylesheets=[CSS(settings.STATIC_ROOT + "/app.css")])

        return response


