import os, sys, stat, subprocess
import django
import uuid
from datetime import datetime, date
import sys
from weasyprint import HTML, CSS
from django.http import Http404, HttpResponseRedirect, HttpResponse, JsonResponse
from django.template.loader import render_to_string
from django.core.management.base import BaseCommand, CommandError
import subprocess
from django.conf import settings

import redis
import time
import json

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'declaraciones.settings')
django.setup()

from declaracion.models import Declaraciones, DeclaracionFiscal, InfoPersonalFija
from declaracion.views.confirmacion import (get_context_InformacionPersonal,get_context_Intereses,get_context_pasivos,
                                            get_context_ingresos, get_context_activos, get_context_vehiculos,
                                            get_context_inversiones,get_context_deudasotros,get_context_prestamocomodato,
                                            get_context_fideicomisos)
from declaracion.views.utils import (validar_declaracion, campos_configuracion_todos, declaracion_datos,set_declaracion_extendida_simplificada)
from django.contrib.auth.models import User
from sitio.models import sitio_personalizacion

if settings.DEVELOP:
    host = '127.0.0.1'
else:
    host = '192.168.156.3'
redis_cnx = redis.Redis(host=host,db=1,port=6379)

def consultaDeclaracion(declaracion):
    context = {}
    context.update(get_context_InformacionPersonal(declaracion))
    context.update(get_context_Intereses(declaracion))
    context.update(get_context_ingresos(declaracion))
    context.update(get_context_activos(declaracion))

    context.update({"vehiculos": get_context_vehiculos(declaracion)})
    context.update({"inversiones": get_context_inversiones(declaracion)})
    context.update({"adeudos": get_context_deudasotros(declaracion)})
    context.update({"prestamos": get_context_prestamocomodato(declaracion)})
    context.update({"fideicomisos": get_context_fideicomisos(declaracion)})
    context.update({"fiscal": DeclaracionFiscal.objects.filter(declaraciones=declaracion.pk).first()})

    context.update(set_declaracion_extendida_simplificada(context['info_personal_fija']))

    return context

def declaraciontoPDF(args):
    declaracion_int = int(args[2])
    redis_cnx.hmset("declaracion", {declaracion_int:0})
    declaracion = Declaraciones.objects.filter(pk=declaracion_int).first()

    print('Obtención de datos----------------------------------------')
    #10% Del proceso ---------------------------------
    redis_cnx.hmset("declaracion",{declaracion_int:10})

    context = consultaDeclaracion(declaracion)
    context.update({"valor_privado_texto": "VALOR PRIVADO"})

    if not declaracion.datos_publicos:
        context.update({"campos_privados": campos_configuracion_todos('p')})

    context.update(set_declaracion_extendida_simplificada(context['info_personal_fija']))

    #20% Del proceso ---------------------------------
    redis_cnx.hmset("declaracion",{declaracion_int:20})
    print('Consulta terminada----------------------------------------')

    template_name = "sitio/descargar.html"
    usuario_ = User.objects.get(pk=declaracion.info_personal_fija.usuario.pk)
    usernamePDF = usuario_.username[0:5] + str(usuario_.pk)
    filename = "{}_{}_{}.pdf".format(usernamePDF,declaracion.cat_tipos_declaracion.codigo, declaracion.fecha_recepcion.date().strftime('%d%m%y'))

    #30% Del proceso ---------------------------------
    redis_cnx.hmset("declaracion",{declaracion_int:30})

    response = HttpResponse(content_type="application/pdf")
    response['Content-Disposition'] = "inline; {}".format(filename)
    html = render_to_string(template_name, context)

    #40% Del proceso ---------------------------------
    redis_cnx.hmset("declaracion",{declaracion_int:40})
    print('PDF nombre de archivo----------------------------------------')
    year=date.today().year
    tipo=declaracion.cat_tipos_declaracion.codigo
    if context['info_personal_fija']:
        if context['info_personal_fija'].cat_puestos:
            area = context['info_personal_fija'].cat_puestos.cat_areas.codigo
        else: 
            area=""
    else: 
        area=""
    
    #50% Del proceso ---------------------------------
    redis_cnx.hmset("declaracion",{declaracion_int:50})

    fecha_declaracion = str(declaracion.fecha_recepcion.date().strftime('%Y'))
    directory_tipo = './media/declaraciones/'+tipo
    directory_fecha = directory_tipo+'/'+fecha_declaracion
    directory = directory_fecha+'/'+area+'/'
    file_path = os.path.join(directory, filename)

    if not os.path.exists(directory):
        os.makedirs(directory)
        
        if oct(os.stat(directory_fecha).st_mode) != '0o40775' or oct(os.stat(directory).st_mode) != '0o40775':
            subprocess.call(['chmod', '-R', '775', directory_fecha])

    elif oct(os.stat('./media/declaraciones/'+tipo).st_mode) != '0o40775':
        for folder in os.listdir(directory_tipo):
            if oct(os.stat(directory_tipo+'/'+folder+'/').st_mode) != '0o40775':
                subprocess.call(['chmod', '-R', '775', directory_tipo+'/'+folder+'/'])

    #60% Del proceso ---------------------------------
    redis_cnx.hmset("declaracion",{declaracion_int:60})
    print('Creación de carpeta----------------------------------------')

    pdf2 = HTML(string=html,base_url=args[3]).write_pdf(stylesheets=[CSS(settings.STATIC_ROOT + "/app.css")]) #Convierte html a pdf para descargarse
    
    #70% Del proceso ---------------------------------
    redis_cnx.hmset("declaracion",{declaracion_int:70})
    print('PDF conversión de HTML ---------------------------------------------')
    f = open(file_path, "wb")
    
    #80% Del proceso ---------------------------------
    redis_cnx.hmset("declaracion",{declaracion_int:80})
    print("Abrir archivo ---------------------------------")
    f.write(pdf2)
    
    #90% Del proceso ---------------------------------
    redis_cnx.hmset("declaracion",{declaracion_int:90})
    print("Se guarda el html texto en pdf-----------------------------------------")
    f.close()
    print('Archivo creado----------------------------------------')

    #100% Del proceso ---------------------------------
    redis_cnx.hmset("declaracion",{declaracion_int:100})
    print("Proceso terminado ----------------------------------")

def declaracionPublicatoPDF(args):
    declaracion_int = int(args[2])
    redis_cnx.hmset("declaracion", {declaracion_int:0})
    declaracion = Declaraciones.objects.filter(pk=declaracion_int).first()

    print('Obtención de datos----------------------------------------')
    #10% Del proceso ---------------------------------
    redis_cnx.hmset("declaracion",{declaracion_int:20})

    context = consultaDeclaracion(declaracion)
    context.update(set_declaracion_extendida_simplificada(context['info_personal_fija']))
    context.update({"publica": " | CONFIDENCIAL - CONFIDENCIAL|"})

    #20% Del proceso ---------------------------------
    redis_cnx.hmset("declaracion",{declaracion_int:40})
    print('Consulta terminada----------------------------------------')

    template_name = "sitio/descargar.html"
    usuario_ = User.objects.get(pk=declaracion.info_personal_fija.usuario.pk)
    usernamePDF = usuario_.username[0:5] + str(usuario_.pk)
    filename = "{}_{}_{}.pdf".format(usernamePDF,declaracion.cat_tipos_declaracion.codigo, declaracion.fecha_recepcion.date().strftime('%d%m%y'))
    
    redis_cnx.hmset("declaracion",{declaracion_int:50})
    print('Nombre el archivo---------------------------------------', filename)

    response = HttpResponse(content_type="application/pdf")
    response['Content-Disposition'] = "invoice; {}".format(filename)
    html = render_to_string(template_name, context)

    redis_cnx.hmset("declaracion", {declaracion_int:60})
    print("Creación de directorio verificado-----------------> 60%")

    year = str(declaracion.fecha_recepcion.date().strftime('%Y'))
    directory_principal = './media/declaraciones/publicas/'
    directory = '{}{}'.format(directory_principal,year)
    file_path = os.path.join(directory, filename)


    pdf2 = HTML(string=html,base_url=args[3]).write_pdf(stylesheets=[CSS(settings.STATIC_ROOT + "/app.css")])

    '''if not os.path.exists(directory):
        os.makedirs(directory)
        os.chmod(directory, stat.S_IXOTH)'''
    
    if not os.path.exists(directory):
        os.makedirs(directory)
        
        if oct(os.stat(directory).st_mode) != '0o40775' or oct(os.stat(directory).st_mode) != '0o40775':
            subprocess.call(['chmod', '-R', '775', directory])

    elif oct(os.stat('./media/declaraciones/publicas/').st_mode) != '0o40775':
        for folder in os.listdir(directory_principal):
            if oct(os.stat(directory_principal+'/'+folder+'/').st_mode) != '0o40775':
                subprocess.call(['chmod', '-R', '775', directory_principal+'/'+folder+'/'])

    #80% Del proceso ---------------------------------
    redis_cnx.hmset("declaracion", {declaracion_int:80})
    print("Creación de directorio verificado-----------------> 80%")

    #90% Del proceso ---------------------------------
    redis_cnx.hmset("declaracion", {declaracion_int:90})
    print("HTML a PDF terminado-----------------> 90%")

    f = open(file_path, "wb")
    f.write(pdf2)
    f.close()

    redis_cnx.hmset("declaracion", {declaracion_int:100})
    print("HTML a PDF terminado-----------------> 100%")

    print("response----------->", response)
    return response



def reportetoPDF(args):
    template_name="declaracion/admin/reportes_main.html"
    parametros_busqueda = json.loads(args[3])
    tipo_reporte = parametros_busqueda['tipo_reporte']
    identificador = int(args[2])

    print("***** Comenzando con {} *****".format(tipo_reporte))
    #20% Del proceso ---------------------------------
    redis_cnx.hmset(tipo_reporte, {identificador:20})
    print("Creación de variables-----------------> 20%")

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
    usuarios = User.objects.all()
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

    if 'folio' in parametros_busqueda:
        declaraciones = declaraciones.filter(folio=uuid.UUID(parametros_busqueda['folio']))
    if 'tipo' in parametros_busqueda:
        declaraciones = declaraciones.filter(cat_tipos_declaracion=parametros_busqueda['tipo'])
    if 'estatus' in parametros_busqueda:
        declaraciones = declaraciones.filter(cat_estatus=parametros_busqueda['estatus'])
    
    #30% Del proceso ---------------------------------
    redis_cnx.hmset(tipo_reporte, {identificador:30})
    
    #Fecha para mostrar las declaraciones en el periodo de tiempo introducido------------------------------------
    fecha_inicio = False
    fecha_fin_mas_uno = False
    filtro_fecha = parametros_busqueda['filtro_fecha']

    if parametros_busqueda['fecha_inicio_year'] and parametros_busqueda['fecha_inicio_month'] and parametros_busqueda['fecha_fin_day']:
        fecha_inicio = date(int(parametros_busqueda['fecha_inicio_year']),int(parametros_busqueda['fecha_inicio_month']),int(parametros_busqueda['fecha_fin_day']))
    
    if parametros_busqueda['fecha_fin_day'] and parametros_busqueda['fecha_fin_month'] and parametros_busqueda['fecha_fin_year']:
        fin_day = int(parametros_busqueda['fecha_fin_day']) + 1 if int(parametros_busqueda['fecha_fin_day']) <= 27 else int(parametros_busqueda['fecha_fin_day'])
        fecha_fin = date(int(parametros_busqueda['fecha_fin_year']),int(parametros_busqueda['fecha_fin_month']),int(parametros_busqueda['fecha_fin_day']))
        fecha_fin_mas_uno = date(int(parametros_busqueda['fecha_fin_year']),int(parametros_busqueda['fecha_fin_month']), fin_day ) 

    #Si el usuario solo selecciona la fecha de inicio
    if fecha_inicio and not fecha_fin_mas_uno:
        if filtro_fecha == '0':
            declaraciones = declaraciones.filter(fecha_declaracion__gte=fecha_inicio)
        else:
            declaraciones = declaraciones.filter(fecha_recepcion__gte=fecha_inicio)
    #El usuario desea buscar en un rango de fechas
    elif fecha_inicio and fecha_fin_mas_uno:
        if filtro_fecha == '0':
            declaraciones = declaraciones.filter(fecha_declaracion__range=[fecha_inicio,fecha_fin_mas_uno])
        else:
            declaraciones = declaraciones.filter(fecha_recepcion__range=[fecha_inicio,fecha_fin_mas_uno])   
    
        #usuarios = usuarios.filter(date_joined__range=[fecha_inicio,fecha_fin_mas_uno])

    '''if usuarios:
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
                    resumen['inactivos']['declarantes'].append(usuario)'''
    
    usuario_id_activo = []
    usuario_id_inactivo = []
    if declaraciones:
        for declaracion in declaraciones:
            infoFija = InfoPersonalFija.objects.get(pk=declaracion.info_personal_fija.pk)
            if infoFija.usuario.is_active:
                usuario_id_activo.append(infoFija.usuario.pk)
            else:
                usuario_id_inactivo.append(infoFija.usuario.pk)

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
    
    usuario_id_activo = list(dict.fromkeys(usuario_id_activo))
    usuario_id_inactivo = list(dict.fromkeys(usuario_id_inactivo))

    total_usuario = [x for n in (usuario_id_activo,usuario_id_inactivo) for x in n]
    total_usuario = list(dict.fromkeys(total_usuario))

    resumen['total_usuarios'] = len(total_usuario)
    resumen['activos']['declarantes'] = usuario_id_activo
    resumen['inactivos']['declarantes'] = usuario_id_inactivo
    
    #50% Del proceso ---------------------------------
    redis_cnx.hmset(tipo_reporte, {identificador:50})
    print("Filtrado completado-----------------> 50%")

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

    filename = "{}_{}_{}.pdf".format(tipo_reporte,date.today().strftime('%d%m%y'),identificador)
    response = HttpResponse(content_type="application/pdf")
    response['Content-Disposition'] = "inline; {}".format(filename)
    html = render_to_string(template_name, context)
    
    #70% Del proceso ---------------------------------
    redis_cnx.hmset(tipo_reporte, {identificador:70})
    print("configuración archivo competado-----------------> 70%")

    directory = './media/reportes/{}/{}'.format(tipo_reporte, str(date.today().year))
    file_path = os.path.join(directory, filename)

    '''if not os.path.exists(directory):
        os.makedirs(directory)
        os.chmod('./media/reportes/', stat.S_IXOTH)'''

    if not os.path.exists(directory):
        os.makedirs(directory)
        
        if oct(os.stat(directory).st_mode) != '0o40775':
            subprocess.call(['chmod', '-R', '775', directory])
    
    #80% Del proceso ---------------------------------
    redis_cnx.hmset(tipo_reporte, {identificador:80})
    print("Creación de directorio verificado-----------------> 80%")

    pdf2 = HTML(string=html,base_url=parametros_busqueda['base_url']).write_pdf(stylesheets=[CSS(settings.STATIC_ROOT + "/app.css")])

    #90% Del proceso ---------------------------------
    redis_cnx.hmset(tipo_reporte, {identificador:90})
    print("HTML a PDF terminado-----------------> 90%")

    f = open(file_path, "wb")
    f.write(pdf2)
    f.close()

    #100% Del proceso ---------------------------------
    redis_cnx.hmset(tipo_reporte, {identificador:100})
    print("Archivo fisico gurdado-----------------> 100%")
    print("***** PROCESO COMPLETO *****")

    return 10

    

if __name__ == "__main__":

    if sys.argv[1] == "declaracion":
        declaraciontoPDF(sys.argv)
    
    if sys.argv[1] == "declaracion_publica":
        declaracionPublicatoPDF(sys.argv)
    
    if sys.argv[1] == "reporte":
        reportetoPDF(sys.argv)
    

