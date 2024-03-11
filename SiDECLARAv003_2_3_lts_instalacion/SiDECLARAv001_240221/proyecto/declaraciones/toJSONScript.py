import os, sys, stat, subprocess
import django
import uuid
from datetime import datetime, date
import sys
from django.http import JsonResponse
import subprocess
from django.conf import settings

import redis
import time
import json


os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'declaraciones.settings')
django.setup()

from declaracion.models import Declaraciones
from declaracion.models.catalogos import CatTipoPersona
from declaracion.models import BienesPersonas, IngresosDeclaracion
from sitio.models import sitio_personalizacion, HistoricoAreasPuestos
from declaracion.views.utils import campos_configuracion

if settings.DEVELOP:
    host = '127.0.0.1'
else:
    host = '192.168.156.3'
redis_cnx = redis.Redis(host=host,db=1,port=6379)

TIME_FORMAT = "%Y-%m-%d"
DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S-05:00"

SECCIONES = {
    "DATOS_GENERALES": 2,
    "DOMICILIO": 3,
    "CURRICULAR": 4,
    "EMPLEO": 5,
    "EXPERIENCIA":6,
    "PAREJA": 7,
    "DEPENDIENTES":8,
    "INGRESOS":9,
    "SERVIDOR":10,
    "INMUEBLES":11,
    "VEHICULOS":12,
    "MUEBLES":13,
    "INVERSIONES":14,
    "ADEUDOS":15,
    "PRESTAMO":16,
    "PARTICIPACION":18,
    "TOMA_DECISIONES":19,
    "APOYOS":20,
    "REPRESENTACION":21,
    "CLIENTES":22,
    "BENEFICIOS":23,
    "FIDEICOMISOS":24
}

SECCIONES_PRIVADAS = {
    "DOMICILIO": True,
    "PAREJA":True,
    "DEPENDIENTES": True
}

serialzied_key={
    "INICIAL":
    [
        "remuneracionMensualCargoPublico",
        "ingresoMensualNetoDeclarante",
        "totalIngresosMensualesNetos",
        "ingresoMensualNetoParejaDependiente",
        "otrosIngresosMensualesTotal"
    ],
    "MODIFICACIÓN":
    [
        "remuneracionAnualCargoPublico",
        "ingresoAnualNetoDeclarante",
        "totalIngresosAnualesNetos",
        "ingresoAnualNetoParejaDependiente",
        "otrosIngresosAnualesTotal"
    ],
    "CONCLUSIÓN":
    [
        "remuneracionConclusionCargoPublico",
        "ingresoConclusionNetoDeclarante",
        "totalIngresosConclusionNetos",
        "ingresoConclusionNetoParejaDependiente",
        "otrosIngresosConclusionTotal"
    ]
}

def default_if_none(
    object_argument, default_type, function
):
    """ Returns a defualt for an expected type,
    else runs a function with the given object as
    an argument
    """
    if object_argument is None:
        if default_type == str:
            return ""
    return function(object_argument)

def actualizacionConflictoInteres(declaracion, extendida):
    if extendida:
        dataConflictoInteres = serialize_interes(declaracion)

        if len(dataConflictoInteres["participacion"]["participacion"]) > 0:
            for dato in dataConflictoInteres["participacion"]["participacion"]:
                if "tipoOperacion" in dato:
                    if dato["tipoOperacion"] == "MODIFICAR":
                        return True

        if len(dataConflictoInteres["participacionTomaDecisiones"]["participacion"]) > 0:
            for dato in dataConflictoInteres["participacionTomaDecisiones"]["participacion"]:
                if "tipoOperacion" in dato:
                    if dato["tipoOperacion"] == "MODIFICAR":
                        return True

        if len(dataConflictoInteres["apoyos"]["apoyo"]) > 0:
            for dato in dataConflictoInteres["apoyos"]["apoyo"]:
                if "tipoOperacion" in dato:
                    if dato["tipoOperacion"] == "MODIFICAR":
                        return True

        if len(dataConflictoInteres["representacion"]["representacion"]) > 0:
            for dato in dataConflictoInteres["representacion"]["representacion"]:
                if "tipoOperacion" in dato:
                    if dato["tipoOperacion"] == "MODIFICAR":
                        return True

        if len(dataConflictoInteres["clientesPrincipales"]["cliente"]) > 0:
            for dato in dataConflictoInteres["clientesPrincipales"]["cliente"]:
                if "tipoOperacion" in dato:
                    if dato["tipoOperacion"] == "MODIFICAR":
                        return True

        if len(dataConflictoInteres["beneficiosPrivados"]["beneficio"]) > 0:
            for dato in dataConflictoInteres["beneficiosPrivados"]["beneficio"]:
                if "tipoOperacion" in dato:
                    if dato["tipoOperacion"] == "MODIFICAR":
                        return True

        if len(dataConflictoInteres["fideicomisos"]["fideicomisos"]) > 0:
            for dato in dataConflictoInteres["fideicomisos"]["fideicomisos"]:
                if "tipoOperacion" in dato:
                    if dato["tipoOperacion"] == "MODIFICAR":
                        return True
    
    redis_cnx.hmset("declaracion_json",{"declaracion_json":40})
    
    return False

def serialize_response_entry(declaracion):
    """
    '#/components/schemas/resDeclaraciones'
    """
    redis_cnx.hmset("declaracion_json",{"declaracion_json":0})
    extendida = True if declaracion.info_personal_fija.cat_puestos.codigo > settings.LIMIT_DEC_SIMP else False
    #Se obtiene el encargo para recuperar el nombre de la entidad
    encargo = declaracion.encargos_set.filter(cat_puestos__isnull=False).first()
    redis_cnx.hmset("declaracion_json",{"declaracion_json":10})
    encargo_nombreInstitucionPersonalizado = serialize_datos_empleado_cargo_comision(encargo,declaracion)
    redis_cnx.hmset("declaracion_json",{"declaracion_json":30})

    serialized_response = {
        "id": str(declaracion.folio),
        "metadata": {
            "fechaCierre": declaracion.fecha_recepcion.strftime(DATETIME_FORMAT),
            "actualizacion": declaracion.fecha_declaracion.strftime(DATETIME_FORMAT),
            "institucion": encargo_nombreInstitucionPersonalizado["nombreEntePublico"],
            "tipo": declaracion.cat_tipos_declaracion.codigo,
            "declaracionCompleta": extendida,
            "actualizacionConflictoInteres": actualizacionConflictoInteres(declaracion, extendida)
        },
        "declaracion": serialize_declaracion(declaracion)
    }
    redis_cnx.hmset("declaracion_json",{"declaracion_json":80})
    return serialized_response


def serialize_declaracion(declaracion):
    redis_cnx.hmset("declaracion_json",{"declaracion_json":50})
    return {
        "situacionPatrimonial": serialize_situacion_patrimonial(declaracion),
        "interes": serialize_interes(declaracion)
    }


def serialize_situacion_patrimonial(declaracion):
    encargos = declaracion.encargos_set.filter(cat_puestos__isnull=False)
    exp_laborales = declaracion.experiencialaboral_set.all()

    try:
        pareja = declaracion.conyugedependientes_set.get(es_pareja=1)
    except Exception as e:
        pareja = False

    serialized = {
        # $ref: '#/components/schemas/datosGenerales'
        "datosGenerales": serialize_datos_generales(declaracion),
        # $ref: '#/components/schemas/datosCurricularesDeclarante'
        "datosCurricularesDeclarante": serialize_datos_curriculares_declarante(declaracion),
        # $ref: '#/components/schemas/experienciaLaboral'   
        "experienciaLaboral": serialize_experiencias_laborales(exp_laborales,declaracion),
        # $ref: '#/components/schemas/ingresos'
        "ingresos": serialize_ingreso(declaracion,1), # TBD,  
        # $ref: '#/components/schemas/bienesInmuebles'
        "bienesInmuebles": serialize_bienes_inmuebles(declaracion), #TBD
        # $ref: '#/components/schemas/vehiculos'
        "vehiculos": serialize_vehiculos(declaracion), #TBD
        # $ref: '#/components/schemas/bienesMuebles'
        "bienesMuebles": serialize_bienes_muebles(declaracion), #TBD   
        # $ref: '#/components/schemas/inversionesCuentasValores'
        "inversiones": serialize_inversiones_cuentas_valores(declaracion), #TBD
        # $ref: '#/components/schemas/adeudosPasivos'
        "adeudos": serialize_adeudos_pasivos(declaracion), #TBD
        # $ref: '#/components/schemas/prestamoComodato'
        "prestamoOComodato": serialize_prestamo_comodato(declaracion) #TBD
    }

    redis_cnx.hmset("declaracion_json",{"declaracion_json":55})


    if encargos.count() > 0:
        # $ref: '#/components/schemas/datosEmpleoCargoComision'
        encargo = encargos.first()
        serialized["datosEmpleoCargoComision"] = serialize_datos_empleado_cargo_comision(encargo,declaracion) # TBD
    
    if declaracion.cat_tipos_declaracion.codigo != "MODIFICACIÓN":
        # $ref: '#/components/schemas/actividadAnualAnterior' 
        serialized["actividadAnualAnterior"] = serialize_ingreso(declaracion,0)

    if not SECCIONES_PRIVADAS["DOMICILIO"]:
        # $ref: '#/components/schemas/domicilioDeclarante
        serialized["domicilioDeclarante"] = serialize_domicio_declarante(declaracion)
    
    if pareja and not SECCIONES["PAREJA"]:
        # $ref: '#/components/schemas/datosPareja'
        serialized["datosPareja"] = serialize_datos_pareja(pareja)

    if not SECCIONES_PRIVADAS["DEPENDIENTES"]:
        # $ref: '#/components/schemas/datosDependientesEconomicos'
        serialized["datosDependienteEconomico"] = serialize_datos_dependiente_economico(declaracion)


    redis_cnx.hmset("declaracion_json",{"declaracion_json":60})

    return serialized


def serialize_ingreso(declaracion, tipo):
    """
    # $ref: '#/components/schemas/ingresos'
    """
    #ingreso_actual = declaracion.ingresosdeclaracion_set.filter(tipo_ingreso=tipo) # TBD
    ingresos = IngresosDeclaracion.objects.filter(declaraciones=declaracion,tipo_ingreso=tipo)

    #if not ingreso_actual:
    if not ingresos:
        return dic_default_ingresos(declaracion)
    else:
        acts_comerciales = []
        acts_financieras = []
        acts_servicios = []
        acts_otros_ingresos = []
        acts_enajenacion_bienes = []

        acts_comerciales = {"monto": 0,"moneda":"", "registros":[]}
        acts_financieras = {"monto": 0,"moneda":"", "registros":[]}
        acts_servicios = {"monto": 0,"moneda":"", "registros":[]}
        acts_otros_ingresos = {"monto": 0,"moneda":"", "registros":[]}
        acts_enajenacion_bienes = {"monto": 0,"moneda":"", "registros":[]}

        ingreso_mensual_cargo = {"monto": 0, "moneda":""}
        ingreso_mensual_neto ={"monto": 0, "moneda":""}
        ingreso_mensual_total = {"monto": 0, "moneda":""}
        ingreso_mensual_otros_ingresos = {"monto": 0, "moneda":""}
        ingreso_anio_anterior_fechas = {}
        ingreso_anio_anterior = False
        ingresos_totales = False

        for ingreso in ingresos:
            if not tipo:
                ingreso_anio_anterior_fechas["fechaIngreso"] = str(ingreso.fecha_ingreso) if ingreso.fecha_ingreso else "2020-01-01"
                ingreso_anio_anterior_fechas["fechaConclusion"] = str(ingreso.fecha_conclusion) if ingreso.fecha_conclusion else "2020-01-01"
                ingreso_anio_anterior = True
                
            if not ingresos_totales:
                if ingreso.ingreso_mensual_cargo and ingreso.ingreso_mensual_neto and ingreso.ingreso_mensual_total:
                    if len(ingresos) > 1:
                        if not ingreso.ingreso_mensual_actividad and not ingreso.ingreso_mensual_financiera and not ingreso.ingreso_mensual_servicios and not ingreso.ingreso_otros_ingresos and not ingreso.ingreso_enajenacion_bienes:
                            ingresos_totales = True
                    else:
                        ingresos_totales = True

            if ingresos_totales:
                ingreso_mensual_cargo["monto"] = int(ingreso.ingreso_mensual_cargo)
                ingreso_mensual_cargo["moneda"] = ingreso.cat_moneda_cargo.codigo
                ingreso_mensual_neto["monto"] = int(ingreso.ingreso_mensual_neto)
                ingreso_mensual_neto["moneda"] = ingreso.cat_moneda_neto.codigo
                ingreso_mensual_otros_ingresos["monto"] = int(ingreso.ingreso_mensual_otros_ingresos)
                ingreso_mensual_otros_ingresos["moneda"] = ingreso.cat_moneda_otro_ingresos_mensual.codigo
                ingreso_mensual_total["monto"] = int(ingreso.ingreso_mensual_total)
                ingreso_mensual_total["moneda"] = ingreso.cat_moneda_total.codigo
                ingresos_totales = False

            
            if ingreso.ingreso_mensual_actividad and int(ingreso.ingreso_mensual_actividad) != 0:
                acts_comerciales["monto"] = acts_comerciales["monto"] + int(ingreso.ingreso_mensual_actividad)
                acts_comerciales["moneda"] = ingreso.cat_moneda_actividad.codigo
                acts_comerciales["registros"].append({
                    "monto":ingreso.ingreso_mensual_actividad,
                    "moneda": ingreso.cat_moneda_actividad.codigo,
                    "razon_social": ingreso.razon_social_negocio,
                    "tipo_negocio": ingreso.tipo_negocio
                })

            if ingreso.ingreso_mensual_financiera and int(ingreso.ingreso_mensual_financiera) != 0:
                acts_financieras["monto"] = acts_financieras["monto"] + int(ingreso.ingreso_mensual_financiera)
                acts_financieras["moneda"] = ingreso.cat_moneda_financiera.codigo
                acts_financieras["registros"].append({
                    "monto": ingreso.ingreso_mensual_financiera,
                    "moneda": ingreso.cat_moneda_financiera.codigo,
                    "tipo_instrumento": serialize_tipo_instrumento(ingreso.cat_tipo_instrumento)
                })

            if ingreso.ingreso_mensual_servicios and int(ingreso.ingreso_mensual_servicios) != 0:
                acts_servicios["monto"] = acts_servicios["monto"] + int(ingreso.ingreso_mensual_servicios)
                acts_servicios["moneda"] = ingreso.cat_moneda_servicios.codigo
                acts_servicios["registros"].append({
                    "monto": ingreso.ingreso_mensual_servicios,
                    "moneda": ingreso.cat_moneda_servicios.codigo,
                    "tipo_servicio": ingreso.tipo_servicio
                })
            
            if ingreso.ingreso_otros_ingresos and int(ingreso.ingreso_otros_ingresos) != 0:
                acts_otros_ingresos["monto"] = acts_otros_ingresos["monto"] + int(ingreso.ingreso_otros_ingresos)
                acts_otros_ingresos["moneda"] = ingreso.cat_moneda_otros_ingresos.codigo
                acts_otros_ingresos["registros"].append({
                    "monto": ingreso.ingreso_otros_ingresos,
                    "moneda": ingreso.cat_moneda_otros_ingresos.codigo,
                    "tipo_actividad": "" if ingreso.cat_tipos_actividad is None else ingreso.cat_tipos_actividad.codigo
                })
            
            if ingreso.ingreso_enajenacion_bienes and int(ingreso.ingreso_enajenacion_bienes) != 0:
                acts_enajenacion_bienes["monto"] = acts_enajenacion_bienes["monto"] + int(ingreso.ingreso_enajenacion_bienes)
                acts_enajenacion_bienes["moneda"] = ingreso.cat_moneda_enajenacion_bienes.codigo
                acts_enajenacion_bienes["registros"].append({
                    "monto": ingreso.ingreso_enajenacion_bienes,
                    "moneda": ingreso.cat_moneda_enajenacion_bienes.codigo,
                    "tipo_bien": "" if ingreso.cat_tipos_bienes is None else ingreso.cat_tipos_bienes.codigo
                })

        serialized = {
            "servidorPublicoAnioAnterior": ingreso_anio_anterior,
            # $ref: '#/components/schemas/monto'
            serialzied_key[declaracion.cat_tipos_declaracion.codigo][0]: serialize_monto(ingreso_mensual_cargo["monto"],ingreso_mensual_cargo["moneda"]),
            # $ref: '#/components/schemas/monto'
            #"otrosIngresosMensualesTotal": serialize_monto(ingreso_actual.ingreso_mensual_otros_ingresos,ingreso_actual.cat_moneda_otro_ingresos_mensual.codigo),
            serialzied_key[declaracion.cat_tipos_declaracion.codigo][4]: serialize_monto(ingreso_mensual_otros_ingresos["monto"],ingreso_mensual_otros_ingresos["moneda"]),
            "actividadIndustrialComercialEmpresarial": {
                # $ref: '#/components/schemas/monto'
                "remuneracionTotal": serialize_monto(acts_comerciales["monto"],acts_comerciales["moneda"]),
                "actividades": [
                    {
                        # $ref: '#/components/schemas/monto'
                        "remuneracion": serialize_monto(actividad["monto"], actividad["moneda"]),
                        "nombreRazonSocial": actividad["razon_social"] if actividad["razon_social"] else "",
                        "tipoNegocio": actividad["tipo_negocio"] if actividad["tipo_negocio"] else ""
                    } for actividad in acts_comerciales["registros"]
                ],
            },
            "actividadFinanciera": {
                # $ref: '#/components/schemas/monto'
                "remuneracionTotal": serialize_monto(acts_financieras["monto"], acts_financieras["moneda"]),
                "actividades": [
                    {
                        # $ref: '#/components/schemas/monto'
                        "remuneracion": serialize_monto(actividad["monto"], actividad["moneda"]),
                        "tipoInstrumento": actividad["tipo_instrumento"]
                    } for actividad in acts_financieras["registros"]
                ],
            },
            "serviciosProfesionales":{
                # $ref: '#/components/schemas/monto'
                "remuneracionTotal": serialize_monto(acts_servicios["monto"], acts_servicios["moneda"]),
                "servicios": [ 
                    {
                        # $ref: '#/components/schemas/monto'
                        "remuneracion": serialize_monto(servicio["monto"], servicio["moneda"]),
                        "tipoServicio": servicio["tipo_servicio"] if servicio["tipo_servicio"] else ""
                    } for servicio in acts_servicios["registros"]
                ]
            },
            "otrosIngresos": {
                # $ref: '#/components/schemas/monto'
                "remuneracionTotal": serialize_monto(acts_otros_ingresos["monto"] ,acts_otros_ingresos["moneda"] ),
                "ingresos": [
                    {
                        "remuneracion": serialize_monto(ingreso["monto"], ingreso["moneda"]),
                        "tipoIngreso": ingreso["tipo_actividad"]
                    } for ingreso in acts_otros_ingresos["registros"]
                ]
            },
            "enajenacionBienes": {
                # $ref: '#/components/schemas/monto'
                "remuneracionTotal": serialize_monto(acts_enajenacion_bienes["monto"], acts_enajenacion_bienes["moneda"] ),
                "bienes": [
                    {
                        "remuneracion": serialize_monto(bien["monto"],bien["moneda"]),
                        "tipoBienEnajenado": bien["tipo_bien"] if bien["tipo_bien"] else "MUEBLE",
                    } for bien in acts_enajenacion_bienes["registros"]
                ]
            },
            # $ref: '#/components/schemas/monto'  
            serialzied_key[declaracion.cat_tipos_declaracion.codigo][1]: serialize_monto(ingreso_mensual_neto["monto"], ingreso_mensual_neto["moneda"]),
            # $ref: '#/components/schemas/monto'
            #serialzied_key[declaracion.cat_tipos_declaracion.codigo][3]: serialize_monto(ingreso_actual.ingreso_mensual_pareja_dependientes,ingreso_actual.cat_moneda_pareja_dependientes.codigo), #CAMPO_PRIVADO
            # $ref: '#/components/schemas/monto'
            serialzied_key[declaracion.cat_tipos_declaracion.codigo][2]: serialize_monto(ingreso_mensual_total["monto"], ingreso_mensual_total["moneda"])
        }

        if tipo:
            if declaracion.cat_tipos_declaracion.codigo != 'MODIFICACIÓN':
                del serialized["enajenacionBienes"]
            #serialized["aclaracionesObservaciones"] = serialize_declaracion_seccion(declaracion, SECCIONES["INGRESOS"]) #CAMPO_PRIVADO
        else:
            serialized.update(ingreso_anio_anterior_fechas)

            serialized['otrosIngresosTotal'] = serialized.pop(serialzied_key[declaracion.cat_tipos_declaracion.codigo][4])
            #serialized['ingresoNetoAnualParejaDependiente'] = serialized.pop(serialzied_key[declaracion.cat_tipos_declaracion.codigo][3]) #CAMPO_PRIVADO

            serialized['remuneracionNetaCargoPublico'] = serialized.pop(serialzied_key[declaracion.cat_tipos_declaracion.codigo][0])
            serialized['ingresoNetoAnualDeclarante'] = serialized.pop(serialzied_key[declaracion.cat_tipos_declaracion.codigo][1])
            serialized['totalIngresosNetosAnuales'] = serialized.pop(serialzied_key[declaracion.cat_tipos_declaracion.codigo][2])
            
            #serialized["aclaracionesObservaciones"] = serialize_declaracion_seccion(declaracion, SECCIONES["SERVIDOR"]) #CAMPO_PRIVADO            

        return  serialized                                  

    return {}


def serialize_datos_generales(declaracion):
    """
    '#/components/schemas/datosGenerales'
    """
    info_personal_fija = declaracion.info_personal_fija
    info_personal_var = declaracion.infopersonalvar_set.get(
        cat_tipo_persona=1
    )

    encargo = declaracion.encargos_set.first() # TBD: ENCARGOS DECLARACION:N?
    regimen_matrimonial = info_personal_var.cat_regimenes_matrimoniales
    estado_civil = info_personal_var.cat_estados_civiles
    
    serialized = {
        "nombre": info_personal_fija.nombres,
        "primerApellido": info_personal_fija.apellido1, 
        "segundoApellido": info_personal_fija.apellido2,
        #"curp": info_personal_fija.curp, #CAMPO_PRIVADO
        #"rfc": { #CAMPO_PRIVADO
        #    "rfc": info_personal_fija.rfc[3:],
        #    "homoclave": info_personal_fija.rfc[:3]
        #},
        "correoElectronico": {
        #    "personal": info_personal_var.email_personal, #TBD declaracion_infopersonalvar(email_personal) #CAMPO_PRIVADO
            "institucional": info_personal_fija.usuario.email
        },
        #"telefono": { #CAMPO_PRIVADO
        #    "casa": info_personal_var.tel_particular, # info_personal_fija.rfc, #telefono
        #    "celularPersonal": info_personal_var.tel_movil
        #},
        #"paisNacimiento": info_personal_var.cat_pais.codigo, #CAMPO_PRIVADO
        #"nacionalidad": info_personal_var.cat_pais.codigo, #CAMPO_PRIVADO
        #"aclaracionesObservaciones": serialize_declaracion_seccion(declaracion, SECCIONES["DATOS_GENERALES"]),#info_personal_var.observaciones.observacion #CAMPO_PRIVADO
    }

    '''if regimen_matrimonial:
        serialized["regimenMatrimonial"] = { #CAMPO_PRIVADO
            "clave": regimen_matrimonial.codigo,
            "valor": regimen_matrimonial.regimen_matrimonial
        }

    if estado_civil:
        serialized["situacionPersonalEstadoCivil"] = { #CAMPO_PRIVADO
            "clave": info_personal_var.cat_estados_civiles.codigo,
            "valor": info_personal_var.cat_estados_civiles.estado_civil
        }'''
        
    return serialized


def serialize_interes(declaracion):
    """
    """
    
    serialized = {
        # $ref: '#/components/schemas/participacion'
        "participacion": serialize_participacion(declaracion), 
        # $ref: '#/components/schemas/participacionTomaDecisiones'
        "participacionTomaDecisiones": serialize_participacion_toma_decisiones(declaracion), 
        # $ref: '#/components/schemas/apoyos'
        "apoyos": serialize_apoyos(declaracion), 
        # $ref: '#/components/schemas/representaciones'
        "representacion": serialize_representacion(declaracion), 
        # $ref: '#/components/schemas/clientesPrincipales'
        "clientesPrincipales": serialize_clientes_principales(declaracion), 
        # $ref: '#/components/schemas/beneficiosPrivados'
        "beneficiosPrivados": serialize_beneficios_privados(declaracion), 
        # $ref: '#/components/schemas/fideicomisos'
        "fideicomisos": serialize_fideicomisos(declaracion)
    }
    redis_cnx.hmset("declaracion_json",{"declaracion_json":65})

    return serialized


def serialize_domicio_declarante(declaracion):
    """
    # $ref: '#/components/schemas/domicilioDeclarante
    """
    info_personal_fija = declaracion.info_personal_fija
    info_personal_var = declaracion.infopersonalvar_set.get(
        #cat_tipo_persona=cat_tipo_persona_declarante
        cat_tipo_persona=1
    ) # TBD
    return {
        "domicilioMexico": serialize_domicilio_mexico(info_personal_var.domicilios),
        "domicilioExtranjero": serialize_domicilio_extranjero(info_personal_var.domicilios), # TBD THIS ???
        "aclaracionesObservaciones": serialize_declaracion_seccion(declaracion, SECCIONES["DOMICILIO"]),#info_personal_var.observaciones.observacion # TBD
    }


def serialize_datos_curriculares_declarante(declaracion):
    """
    # $ref: '#/components/schemas/datosCurricularesDeclarante'
    """
    def serialize_dato_curricular(dato_curricular):

        documentos_obtenidos = dato_curricular.cat_documentos_obtenidos
        if dato_curricular:
            serialized = {
                    # $ref: '#/components/schemas/tipoOperacion'
                    "tipoOperacion": serialize_tipo_operacion(dato_curricular.cat_tipos_operaciones),
                    "nivel":{},
                    "institucionEducativa": {
                        "nombre": dato_curricular.institucion_educativa if dato_curricular.institucion_educativa else "",
                        "ubicacion": serialize_pais(dato_curricular.cat_pais)
                    },
                    "carreraAreaConocimiento": dato_curricular.carrera_o_area if dato_curricular.carrera_o_area else "",
                    "estatus": dato_curricular.cat_estatus_estudios.estatus_estudios if dato_curricular.cat_estatus_estudios else "",
                    "fechaObtencion": str(dato_curricular.conclusion) if dato_curricular.conclusion else "2020-01-01" # TBD FORMAT '2017-11-29'  
            }
            if documentos_obtenidos:
                serialized["documentoObtenido"] = documentos_obtenidos.documento_obtenido
            if dato_curricular.cat_grados_academicos:
                serialized["nivel"]["clave"] = dato_curricular.cat_grados_academicos.codigo
                serialized["nivel"]["valor"] = dato_curricular.cat_grados_academicos.grado_academico
            
            return serialized

    return_serialized = {
        "escolaridad": [
            serialize_dato_curricular(dato_curricular) for dato_curricular in declaracion.datoscurriculares_set.all()
        ],
        #"aclaracionesObservaciones": serialize_declaracion_seccion(declaracion,SECCIONES["CURRICULAR"]) #CAMPO_PRIVADO
    }
    
    return return_serialized

def serialize_domicilio_mexico(domicilio):
    """
    $ref: '#/components/schemas/domicilioMexico'
    """
    entidad_federativa = domicilio.cat_entidades_federativas
    serialized = {
        "calle": domicilio.nombre_via,
        "numeroExterior": domicilio.num_exterior,
        "numeroInterior": domicilio.num_interior,
        "coloniaLocalidad": domicilio.colonia,
        "municipioAlcaldia": {
            "clave": "001" if domicilio.municipio is None else domicilio.municipio.clave, 
            "valor": "Acatlán" if domicilio.municipio is None else domicilio.municipio.valor
        },
        
        "codigoPostal": domicilio.cp
    }
    if entidad_federativa:
        serialized["entidadFederativa"] = serialize_entidad_federativa(entidad_federativa)
    return serialized


def serialize_domicilio_extranjero(domicilio):
    """
    $ref: '#/components/schemas/domicilioExtranjero'
    """
    
    cat_pais =  domicilio.cat_pais
    serialized = {
        "calle": domicilio.nombre_via,
        "numeroExterior": domicilio.num_exterior,
        "numeroInterior": domicilio.num_interior,
        "ciudadLocalidad": domicilio.ciudadLocalidad or "No especificado",
        "estadoProvincia": domicilio.estadoProvincia or "No especificado",
        "codigoPostal": domicilio.cp
    }
    if cat_pais:
        # $ref: '#/components/schemas/pais'
        serialized["pais"] = serialize_pais(domicilio.cat_pais)
    return serialized

def serialize_pais(pais):
    """
    # $ref: '#/components/schemas/pais'
    """
    if pais:
        if pais.codigo != 'MX':
            return 'EX'

    return 'MX'


def serialize_entidad_federativa(entidad_federativa):
    """
    $ref: '#/components/schemas/entidadFederativa'
    CatPaises
    """
    if entidad_federativa:
        return {
            "clave": entidad_federativa.codigo, 
            "valor": entidad_federativa.entidad_federativa
        }
    return {"clave":'14',"valor":"Jalisco"}


def serialize_ubicacion(ubicacion):
    """
    # $ref: '#/components/schemas/ubicacion'
    """
    return {
        # $ref: '#/components/schemas/pais'
        "pais": serialize_pais(ubicacion.cat_pais),
        # $ref: '#/components/schemas/entidadFederativa'
        "entidadFederativa": serialize_entidad_federativa(
            ubicacion.cat_entidades_federativas
        )
    }

def serialize_participacion_toma_decisiones(declaracion):
    """
    # $ref: '#/components/schemas/participacionTomaDecisiones'
    """
    participaciones = declaracion.membresias_set.all()

    to_be_add = []
    for parti in participaciones:
        titular = serialize_tipo_relacion(parti.tipoRelacion)

        if titular == "DECLARANTE" and parti.tipoRelacion is not None:
            to_be_add.append(parti.pk)

    participaciones = participaciones.filter(id__in=to_be_add)
    count_row_total = len(participaciones)

    def serialize_participacion(participacion):
        tipo_relacion = participacion.tipoRelacion

        if tipo_relacion:
            # $ref: '#/components/schemas/tipoRelacion'
            serialized={
                "tipoRelacion":serialize_tipo_relacion(tipo_relacion)
            }

            if serialized["tipoRelacion"] == 'DECLARANTE':
                serialized["tipoInstitucion"] = serialize_tipo_institucion(participacion.cat_tipos_instituciones)
                #serialized["nombreInstitucion"]= participacion.nombre_institucion #CAMPO_PRIVADO
                #serialized["rfc"]= participacion.rfc #CAMPO_PRIVADO
                serialized["puestoRol"] = participacion.puesto_rol if participacion.puesto_rol else ""
                serialized["fechaInicioParticipacion"]= participacion.fecha_inicio.strftime(TIME_FORMAT)
                serialized["recibeRemuneracion"]= participacion.pagado if participacion.pagado else False
                # $ref: '#/components/schemas/ubicacion'
                serialized["ubicacion"] = serialize_ubicacion(participacion.domicilios)
                
                if participacion.cat_tipos_operaciones:
                    # $ref: '#/components/schemas/tipoOperacion'
                    serialized["tipoOperacion"] = serialize_tipo_operacion(participacion.cat_tipos_operaciones)

                if participacion.moneda:
                    # $ref: '#/components/schemas/monto'
                    serialized["montoMensual"]: serialize_monto(participacion.monto, participacion.moneda.codigo)

        return serialized

    serialized =  {
        "ninguno": serialize_declaracion_seccion(declaracion,SECCIONES["TOMA_DECISIONES"], "NINGUNO",count_row_total),
        "participacion": [],
        #"aclaracionesObservaciones": serialize_declaracion_seccion(declaracion, SECCIONES["PARTICIPACION"]) #CAMPOS_PRIVADOS  
    }

    if not serialized["ninguno"] and len(participaciones) > 0:
        serialized["participacion"] = [
            serialize_participacion(participacion) for participacion in participaciones if participacion.cat_tipos_instituciones
        ]

    return serialized 


def serialize_apoyos(declaracion):
    """
    # $ref: '#/components/schemas/apoyos'
    """
    apoyos = declaracion.apoyos_set.all()
    to_be_add = []

    if apoyos:
        for apoy in apoyos:
            titular = serialize_beneficiarios_programa(apoy.cat_tipos_relaciones_personales)

            if titular["clave"] == "DC" and apoy.cat_tipos_relaciones_personales is not None:
                to_be_add.append(apoy.pk)
    
    apoyos = apoyos.filter(id__in=to_be_add)
    count_row_total = len(apoyos)

    def serialize_apoyo(apoyo):

        serialized = {
            # $ref: '#/components/schemas/beneficiariosPrograma'
            "beneficiarioPrograma": serialize_beneficiarios_programa(apoyo.cat_tipos_relaciones_personales), #CAMPO_PRIVADO SI NO ES DECLARANTE
            "nombrePrograma": apoyo.nombre_programa if apoyo.nombre_programa else "",
            "institucionOtorgante": apoyo.institucion_otorgante if apoyo.institucion_otorgante else "",
            # $ref: '#/components/schemas/nivelOrdenGobierno'
            "nivelOrdenGobierno": serialize_nivel_orden_gobierno(
                apoyo.cat_ordenes_gobierno
            ),
            # $ref: '#/components/schemas/formaRecepcion'
            "formaRecepcion": apoyo.forma_recepcion,
            "especifiqueApoyo": apoyo.especifiqueApoyo if apoyo.especifiqueApoyo else ""
        }
        if apoyo.cat_tipos_operaciones:
            # $ref: '#/components/schemas/tipoOperacion'
            serialized["tipoOperacion"]: serialize_tipo_operacion(apoyo.cat_tipos_operaciones)

        if apoyo.cat_tipos_apoyos:
            serialized["tipoApoyo"] =  { 
                "clave": apoyo.cat_tipos_apoyos.codigo,
                "valor": apoyo.cat_tipos_apoyos.tipo_apoyo
            }
        if apoyo.moneda:
            # $ref: '#/components/schemas/monto'
            serialized["montoApoyoMensual"] = serialize_monto(
                apoyo.monto_apoyo_mensual, 
                apoyo.moneda.codigo, 
            )
            
            
        return serialized
    serialized = {
        "ninguno": serialize_declaracion_seccion(declaracion,SECCIONES["APOYOS"], "NINGUNO",count_row_total),
        "apoyo": [],
        #"aclaracionesObservaciones": serialize_declaracion_seccion(declaracion,SECCIONES["APOYOS"]) #CAMPO_PRIVADO
    }

    if not serialized["ninguno"]:
        serialized["apoyo"] = [
            serialize_apoyo(apoyo) for apoyo in apoyos
        ]

    return serialized

def serialize_beneficiarios_programa(beneficiario):
    """
    # $ref: '#/components/schemas/beneficiariosPrograma'
    """
    if beneficiario:
        if beneficiario.codigo == 'DC':
            return {
                "clave": beneficiario.codigo,
                "valor": beneficiario.tipo_relacion
            }
        else:
            return {"clave": "OTRO", "valor":"Otro"}

    else:
        return {"clave": "OTRO", "valor":"Otro"}


def serialize_representacion(declaracion):
    """
    # $ref: '#/components/schemas/representaciones'
    """
    representaciones = declaracion.representaciones_set.all()

    to_be_add = []
    for represent in representaciones:
        titular = serialize_tipo_relacion(represent.cat_tipos_relaciones_personales)

        if titular == "DECLARANTE" and represent.cat_tipos_relaciones_personales is not None:
            to_be_add.append(represent.pk)
    
    representaciones = representaciones.filter(id__in=to_be_add)
    count_row_total = len(representaciones)

    def serialize_representacion(representacion):
        if representacion:

            if representacion.cat_tipos_relaciones_personales:
                info_personal_var = representacion.info_personal_var

                serialized={
                    "tipoRelacion":serialize_tipo_relacion(representacion.cat_tipos_relaciones_personales),
                    "tipoRepresentacion": serialize_tipo_representacion(representacion.cat_tipos_representaciones),
                    "fechaInicioRepresentacion": representacion.fecha_inicio.strftime(TIME_FORMAT)
                }

                if info_personal_var.cat_tipo_persona:
                    # $ref: '#/components/schemas/tipoPersona'
                    serialzied["tipoPersona"] = serialize_persona_fisica_moral(info_personal_var.es_fisica)
                    serialized["recibeRemuneracion"]= representacion.pagado if representacion.pagado else False

                    if serialzied["tipoPersona"] == "MORAL":
                        serialized["nombreRazonSocial"]= serialize_nombre_completo_razon_social(info_personal_var) #CAMPO_PRIVADO
                        serialized["rfc"]= info_personal_var.rfc if info_personal_var.rfc else "" #CAMPO_PRIVADO
                
                if representacion.cat_tipos_operaciones:
                    serialized["tipoOperacion"] =  serialize_tipo_operacion(
                        representacion.cat_tipos_operaciones
                    )

                if info_personal_var.cat_sectores_industria:
                    serialized["sector"] =  serialize_sector_industria(info_personal_var.cat_sectores_industria)
                
                if representacion.cat_moneda:
                    serialized["montoMensual"] = serialize_monto(
                        representacion.monto,
                        representacion.cat_moneda.codigo
                    )
                if info_personal_var.domicilios.cat_pais and info_personal_var.domicilios.cat_entidades_federativas:
                    serialized["ubicacion"] = serialize_ubicacion(info_personal_var.domicilios)

            return serialized
        
    
    serialized = {
        "ninguno": serialize_declaracion_seccion(declaracion,SECCIONES["REPRESENTACION"], "NINGUNO",count_row_total), 
        "representacion": [],
        #"aclaracionesObservaciones": serialize_declaracion_seccion(declaracion, SECCIONES["REPRESENTACION"]) #CAMPO_PRIVADO
    }

    if not serialized["ninguno"]:
        serialized["representacion"] = [
            serialize_representacion(representacion) for representacion in representaciones 
        ]

    return serialized


def serialize_fideicomisos(declaracion):
    """
    # $ref: '#/components/schemas/fideicomisos'
        
    """
    fideicomisos = declaracion.fideicomisos_set.all()

    to_be_add = []
    for fideicomiso in fideicomisos:
        titular = serialize_tipo_relacion(fideicomiso.tipo_relacion)

        if titular == "DECLARANTE" and fideicomiso.tipo_relacion is not None:
            to_be_add.append(fideicomiso.pk)
    
    fideicomisos = fideicomisos.filter(id__in=to_be_add)
    count_row_total = len(fideicomisos)

    def serialize_fideicomiso(fideicomiso):
        """
        """
        if fideicomiso:
            if fideicomiso.tipo_relacion:
                # $ref : '#/components/schemas/tipoRelacion'
                serialized = {
                    "tipoRelacion": serialize_tipo_relacion(fideicomiso.tipo_relacion)
                }

                fideicomitente = BienesPersonas.objects.filter(activos_bienes = fideicomiso.activos_bienes,cat_tipo_participacion_id=BienesPersonas.FIDEICOMITENTE).first()
                fiduciario = BienesPersonas.objects.filter(activos_bienes = fideicomiso.activos_bienes,cat_tipo_participacion_id=BienesPersonas.FIDUCIARIO).first()
                fideicomisario = BienesPersonas.objects.filter(activos_bienes = fideicomiso.activos_bienes,cat_tipo_participacion_id=BienesPersonas.FIDEICOMISARIO).first()

                # $ref : '#/components/schemas/tipoOperacion'
                serialized["tipoOperacion"]= serialize_tipo_operacion(fideicomiso.cat_tipos_operaciones)
                serialized["tipoFideicomiso"]= fideicomiso.cat_tipos_fideicomisos.tipo_fideicomiso if fideicomiso.cat_tipos_fideicomisos else "MIXTO"
                serialized["rfcFideicomiso"]= fideicomiso.rfc if fideicomiso.rfc else ""
                serialized["tipoParticipacion"]= fideicomiso.cat_tipo_participacion.codigo if fideicomiso.cat_tipo_participacion else "FIDEICOMITENTE"
                serialized["extranjero"] = serialize_pais(fideicomiso.cat_paises)

                if fideicomitente:
                    serialized["fideicomitente"] = {
                        # '#/components/schemas/tipoPersona
                        "tipoPersona": serialize_persona_fisica_moral(fideicomitente.info_personal_var.es_fisica)
                    }

                    if serialized["fideicomitente"]["tipoPersona"] == "MORAL":
                        serialized["fideicomitente"]["nombreRazonSocial"] = serialize_nombre_completo_razon_social(fideicomitente.info_personal_var) #CAMPO_PRIVADO
                        serialized["fideicomitente"]["rfc"] = fideicomitente.info_personal_var.rfc if fideicomitente.info_personal_var.rfc else "" #CAMPO_PRIVADO

                if fiduciario:
                    serialized["fiduciario"] = {
                        "nombreRazonSocial": serialize_nombre_completo_razon_social(fiduciario.info_personal_var),
                        "rfc": fiduciario.info_personal_var.rfc if fiduciario.info_personal_var.rfc else ""
                    }

                if fideicomisario:
                    serialized["fideicomisario"]= {
                        # '#/components/schemas/tipoPersona
                        "tipoPersona": serialize_persona_fisica_moral(fideicomisario.info_personal_var.es_fisica)
                    }

                    if serialized["fideicomisario"]["tipoPersona"] == "MORAL":
                        serialized["fideicomisario"]["nombreRazonSocial"] = serialize_nombre_completo_razon_social(fideicomisario.info_personal_var) #CAMPO_PRIVADO
                        serialized["fideicomisario"]["rfc"] = fideicomisario.info_personal_var.rfc if fideicomisario.info_personal_var.rfc else "" #CAMPO_PRIVADO

                if fideicomiso.cat_sectores_industria:
                    serialized["sector"]: serialize_sector_industria(fideicomiso.cat_sectores_industria)

            return serialized
        return {}

    serialized = {
        "ninguno": serialize_declaracion_seccion(declaracion,SECCIONES["FIDEICOMISOS"], "NINGUNO",count_row_total),
        "fideicomisos": [],
        #"aclaracionesObservaciones": serialize_declaracion_seccion(declaracion,SECCIONES["FIDEICOMISOS"]) #CAMPO_PRIVADO
    }

    if not serialized["ninguno"]:
        serialized["fideicomisos"] = [
            serialize_fideicomiso(fideicomiso) for fideicomiso in fideicomisos
        ]
    return serialized 


def serialize_tipo_relacion(tipo_relacion):
    """
    #/components/schemas/tipoRelacion
    """
    if tipo_relacion:
        return tipo_relacion.codigo
    return "DECLARANTE"


def serialize_tipo_persona(tipo_persona):
    """
    '#/components/schemas/tipoPersona'
    """
    if tipo_persona:
        return tipo_persona.tipo_persona
    return ""

def serialize_tipo_institucion(institucion):
    if institucion:
        return {
            "clave": institucion.codigo,
            "valor": institucion.tipo_institucion
        }
    return {"clave": "OTRO","valor": "No aplica"}


def serialize_persona_fisica_moral(persona):
    """
    '#/components/schemas/tipoPersona'
    """
    if persona:
        return "FISICA"
    else:
        return "MORAL"


def serialize_datos_empleado_cargo_comision(encargo,declaracion):
    """
    $ref: '#/components/schemas/datosEmpleoCargoComision'
    """
    tipo_operaciones = encargo.cat_tipos_operaciones
    poder = encargo.cat_poderes
    funcion_principal = encargo.cat_funciones_principales
    puesto = serialize_empleo_cargo_comision(declaracion,encargo)

    serialized = {
        # $ref: '#/components/schemas/nivelOrdenGobierno'
        "nivelOrdenGobierno": serialize_nivel_orden_gobierno(encargo.cat_ordenes_gobierno),
        "nombreEntePublico": "" if encargo.nombre_ente_publico is None else encargo.nombre_ente_publico,
        "areaAdscripcion": "",
        "empleoCargoComision": "",
        "nivelEmpleoCargoComision": "",
        "contratadoPorHonorarios": encargo.honorarios if encargo.honorarios else False,
        "funcionPrincipal": funcion_principal.funcion if funcion_principal else "",
        "fechaTomaPosesion": encargo.posesion_inicio.strftime(TIME_FORMAT) if encargo.posesion_inicio else "",
        "telefonoOficina": {
            "telefono": encargo.telefono_laboral if encargo.telefono_laboral else "",
            "extension": encargo.telefono_extension if encargo.telefono_extension else ""
        },
        # $ref: '#/components/schemas/domicilioMexico'
        "domicilioMexico": serialize_domicilio_mexico(encargo.domicilios),
        # $ref: '#/components/schemas/domicilioExtranjero'
        "domicilioExtranjero": serialize_domicilio_extranjero(encargo.domicilios),
        #"aclaracionesObservaciones": serialize_declaracion_seccion(encargo.declaraciones,SECCIONES["EMPLEO"]),#CAMPO_PRIVADO
    }
    # $ref: '#/components/schemas/tipoOperacion'
    if tipo_operaciones:
        serialized["tipoOperacion"] = serialize_tipo_operacion(tipo_operaciones)
    if poder:
        # $ref: '#/components/schemas/ambitoPublico'
        serialized["ambitoPublico"] = serialize_ambito_publico(poder)
    if puesto:
        serialized["areaAdscripcion"] = puesto["area"]
        serialized["empleoCargoComision"] = puesto["puesto"]
        serialized["nivelEmpleoCargoComision"] = str(puesto["puesto_codigo"])


    
    return serialized

def serialize_experiencias_laborales(experiencias,declaracion):
    """
    $ref: '#/components/schemas/experienciaLaboral'
    """
    campos_privados = serialize_declaracion_seccion(declaracion, SECCIONES["EXPERIENCIA"], 'CAMPOS_PRIVADOS')

    def serialize_experiencia_laboral(experiencia):
        if experiencia:
            serialized =  {
                # $ref: '#/components/schemas/tipoOperacion'
                "tipoOperacion": serialize_tipo_operacion(experiencia.cat_tipos_operaciones),
                # $ref: '#/components/schemas/ambitoSector'
                "ambitoSector": serialize_actividad_laboral(experiencia.cat_ambitos_laborales, 'EXPERIENCIA'),
                "fechaIngreso": experiencia.fecha_ingreso.strftime(TIME_FORMAT) if experiencia.fecha_ingreso else "2020-01-01",
                "fechaEgreso": experiencia.fecha_salida.strftime(TIME_FORMAT) if experiencia.fecha_salida else "2020-01-01",
                "ubicacion": serialize_pais(experiencia.domicilios.cat_pais)
            }

            if serialized["ambitoSector"]["clave"] == 'PUB':
                serialized["nivelOrdenGobierno"] = serialize_nivel_orden_gobierno(experiencia.cat_ordenes_gobierno)
                serialized["ambitoPublico"] = serialize_ambito_publico(experiencia.cat_poderes)
                serialized["nombreEntePublico"] =  experiencia.nombre_institucion if experiencia.nombre_institucion else ""
                serialized["areaAdscripcion"] = experiencia.unidad_area_administrativa if experiencia.unidad_area_administrativa else ""
                serialized["empleoCargoComision"] = experiencia.cargo_puesto if experiencia.cargo_puesto else ""
                serialized["funcionPrincipal"] = serialize_funciones(experiencia.cat_funciones_principales)
            else:
                serialized["nombreEmpresaSociedadAsociacion"] = experiencia.nombre_institucion if experiencia.nombre_institucion else ""
                serialized["rfc"] = experiencia.rfc if experiencia.rfc else ""
                serialized["area"] = experiencia.unidad_area_administrativa if experiencia.unidad_area_administrativa else ""
                serialized["puesto"] = experiencia.cargo_puesto if experiencia.cargo_puesto else ""
                serialized["sector"] = serialize_sector_industria(experiencia.cat_sectores_industria)

            return serialized
    
    serialized = {
        "ninguno": serialize_declaracion_seccion(declaracion,SECCIONES["EXPERIENCIA"], "NINGUNO"), # TBD
        "experiencia": [],
        #"aclaracionesObservaciones": serialize_declaracion_seccion(declaracion,SECCIONES["EXPERIENCIA"]) #CAMPO_PRIVADO
    }

    if not serialized["ninguno"]:
        serialized["experiencia"] = [
            serialize_experiencia_laboral(experiencia) for experiencia in experiencias
        ]

    return serialized


def serialize_datos_pareja(datos_pareja):
    """
    # $ref: '#/components/schemas/datosPareja'   
    """
    if datos_pareja:
        cat_ente_publico = datos_pareja.actividadLaboralSector.cat_entes_publicos
        cat_poder = datos_pareja.actividadLaboralSector.cat_poderes
        fecha_nacimiento =  str(datos_pareja.declarante_infopersonalvar.fecha_nacimiento) if datos_pareja.declarante_infopersonalvar.fecha_nacimiento else ""
        actividad_laboral = datos_pareja.actividadLaboralSector
        
        funcion_principal = datos_pareja.actividadLaboralSector.cat_funciones_principales

        serialized = {
            "ninguno": serialize_declaracion_seccion(datos_pareja.declaraciones, SECCIONES["PAREJA"],"NINGUNO"),
            # $ref : '#/components/schemas/tipoOperacion'
            "tipoOperacion": serialize_tipo_operacion(
                datos_pareja.cat_tipos_operaciones
            ),
            "nombre": datos_pareja.declarante_infopersonalvar.nombres, 
            "primerApellido": datos_pareja.declarante_infopersonalvar.apellido1,
            "segundoApellido": datos_pareja.declarante_infopersonalvar.apellido2,
            
            "rfc": datos_pareja.declarante_infopersonalvar.rfc,
            "relacionConDeclarante": serialize_relacion_con_declarante(
                datos_pareja.cat_tipos_relaciones_personales
            ),
            "ciudadanoExtranjero": datos_pareja.es_extranjero if datos_pareja.es_extranjero else False, #TBD
            "curp": datos_pareja.declarante_infopersonalvar.curp,
            "esDependienteEconomico": datos_pareja.ingresos_propios if datos_pareja.ingresos_propios else False,
            "habitaDomicilioDeclarante": datos_pareja.habita_domicilio,
            # $ref: '#/components/schemas/lugarDondeReside'
            "lugarDondeReside": serialize_lugar_donde_reside(
                datos_pareja.declarante_infopersonalvar.domicilios
            ),
            # $ref: '#/components/schemas/domicilioMexico'
            "domicilioMexico": serialize_domicilio_mexico(
                datos_pareja.declarante_infopersonalvar.domicilios
            ),
            # $ref: '#/components/schemas/domicilioExtranjero'
            "domicilioExtranjero": serialize_domicilio_extranjero(
                datos_pareja.declarante_infopersonalvar.domicilios
            ),
            # $ref: '#/components/schemas/actividadLaboral'
            "actividadLaboral": serialize_actividad_laboral(
                datos_pareja.actividadLaboral,'PAREJA'
            ), #TBD ???,
            "actividadLaboralSectorPublico": {
                # #/components/schemas/nivelOrdenGobierno
                "nivelOrdenGobierno": serialize_nivel_orden_gobierno(
                    datos_pareja.actividadLaboralSector.cat_ordenes_gobierno
                ),
                "nombreEntePublico": default_if_none(
                    cat_ente_publico, str, lambda obj_inst: obj_inst.ente_publico
                ),
                "areaAdscripcion": datos_pareja.actividadLaboralSector.area_adscripcion if datos_pareja.actividadLaboralSector.area_adscripcion else "", 
                "empleoCargoComision": datos_pareja.actividadLaboralSector.empleo_cargo_comision if datos_pareja.actividadLaboralSector.empleo_cargo_comision else "",
                "salarioMensualNeto": {"valor": 0,"moneda": "MXN"},
                "fechaIngreso": datos_pareja.actividadLaboralSector.posesion_inicio.strftime(TIME_FORMAT) if datos_pareja.actividadLaboralSector.posesion_inicio else "2020-01-01",
            },
            "actividadLaboralSectorPrivadoOtro": {
                "nombreEmpresaSociedadAsociacion": datos_pareja.actividadLaboralSector.nombreEmpresaSociedadAsociacion if datos_pareja.actividadLaboralSector.nombreEmpresaSociedadAsociacion else "",
                "empleoCargoComision": datos_pareja.actividadLaboralSector.empleo_cargo_comision if datos_pareja.actividadLaboralSector.empleo_cargo_comision else "",
                "rfc": datos_pareja.actividadLaboralSector.rfc if datos_pareja.actividadLaboralSector.rfc else "",
                "fechaIngreso": datos_pareja.actividadLaboralSector.posesion_inicio.strftime(TIME_FORMAT) if datos_pareja.actividadLaboralSector.posesion_inicio else "2020-01-01",
                # '#/components/schemas/sector
                "sector": serialize_sector_industria(
                     datos_pareja.actividadLaboralSector.cat_sectores_industria
                ),
                # $ref: '#/components/schemas/monto'
                "salarioMensualNeto": {"valor": 0,"moneda": "MXN"},
                "proveedorContratistaGobierno": datos_pareja.proveedor_contratista if datos_pareja.proveedor_contratista else False
            },
            #"aclaracionesObservaciones": serialize_declaracion_seccion(datos_pareja.declaraciones, SECCIONES["PAREJA"]),#datos_pareja.declarante_infopersonalvar.observaciones.observacion #CAMPO_PRIVADO
        }
        if fecha_nacimiento: 
            serialized["fechaNacimiento"]=fecha_nacimiento.strftime(TIME_FORMAT)    
        if funcion_principal:
            serialized["actividadLaboralSectorPublico"]["funcionPrincipal"]= serialize_funciones(funcion_principal)
        if cat_poder:
            #/components/schemas/ambitoPublico
            serialized["actividadLaboralSectorPublico"]["ambitoPublico"] = serialize_ambito_publico(cat_poder)
        if actividad_laboral:
            #/components/schemas/monto
            serialized["salarioMensualNeto"] = serialize_monto(
                actividad_laboral.salarioMensualNeto if actividad_laboral.salarioMensualNeto else 0, 
                actividad_laboral.moneda.codigo if actividad_laboral.moneda else "MXN"
            )

        return serialized
    return {}

def serialize_lugar_donde_reside(lugar_donde_reside):
    """
    # $ref: '#/components/schemas/lugarDondeReside'
    """
    if lugar_donde_reside:
        if lugar_donde_reside.cat_pais:
            return 'MEXICO' if lugar_donde_reside.cat_pais.codigo == 'MX' else 'EXTRANJERO'

    return 'SE_DESCONOCE'


def serialize_datos_dependiente_economico(declaracion):
    """
    $ref: '#/components/schemas/datosDependientesEconomicos'     
    """
    def serialize_dependiente_economico(dependiente_economico):
        if dependiente_economico:
            actividad_laboral_sector = dependiente_economico.actividadLaboralSector
            actividadLaboral = dependiente_economico.actividadLaboral
            poder = actividad_laboral_sector.cat_poderes
            ente_publico = actividad_laboral_sector.cat_entes_publicos
            orden_gobierno = actividad_laboral_sector.cat_ordenes_gobierno
            tipo_operaciones = dependiente_economico.cat_tipos_operaciones
            funcion_principal = actividad_laboral_sector.cat_funciones_principales

            serialized = {
                "nombre": dependiente_economico.dependiente_infopersonalvar.nombres,
                "primerApellido": dependiente_economico.dependiente_infopersonalvar.apellido1,
                "segundoApellido": dependiente_economico.dependiente_infopersonalvar.apellido2,
                "fechaNacimiento": str(dependiente_economico.dependiente_infopersonalvar.fecha_nacimiento) if dependiente_economico.dependiente_infopersonalvar.fecha_nacimiento else "",
                "rfc": dependiente_economico.dependiente_infopersonalvar.rfc,
                # $ref : '#/components/schemas/parentescoRelacion'
                "parentescoRelacion": serialize_parentesco_relacion(
                    dependiente_economico.cat_tipos_relaciones_personales
                ),
                "extranjero": True if "MX" else False,
                "curp": dependiente_economico.dependiente_infopersonalvar.curp,
                "habitaDomicilioDeclarante": dependiente_economico.habita_domicilio,
                "lugarDondeReside": serialize_lugar_donde_reside(dependiente_economico.dependiente_infopersonalvar.domicilios),#"" if dependiente_economico.dependiente_infopersonalvar.cat_pais is None else dependiente_economico.dependiente_infopersonalvar.cat_pais.codigo,
                "domicilioMexico": serialize_domicilio_mexico(dependiente_economico.dependiente_infopersonalvar.domicilios),
                "domicilioExtranjero": serialize_domicilio_extranjero(dependiente_economico.dependiente_infopersonalvar.domicilios),
                "proveedorContratistaGobierno": dependiente_economico.proveedor_contratista,
                "sector": serialize_sector_industria(
                     dependiente_economico.actividadLaboralSector.cat_sectores_industria
                ),
                "actividadLaboralSectorPublico": {
                    # TBD $ref: '#/components/schemas/nivelOrdenGobierno'
                    "nivelOrdenGobierno": serialize_nivel_orden_gobierno(
                        dependiente_economico.actividadLaboralSector.cat_ordenes_gobierno
                    ),        
                    "nombreEntePublico":  default_if_none(ente_publico, str, lambda obj_inst: obj_inst.ente_publico),
                    # declaracion.conyugedependientes_set.all()[0].actividadLaboralSector.cat_entes_publicos.ente_publico,
                    "areaAdscripcion": actividad_laboral_sector.area_adscripcion if actividad_laboral_sector.area_adscripcion else "", 
                    "empleoCargoComision": actividad_laboral_sector.empleo_cargo_comision if actividad_laboral_sector.empleo_cargo_comision else "",
                    "salarioMensualNeto": serialize_monto(
                        actividad_laboral_sector.salarioMensualNeto, actividad_laboral_sector.moneda.codigo
                    ),
                    "fechaIngreso": actividad_laboral_sector.posesion_inicio.strftime(TIME_FORMAT) if actividad_laboral_sector.posesion_inicio else "2020-01-01"
                },
                "actividadLaboralSectorPrivadoOtro": {
                    "nombreEmpresaSociedadAsociacion": actividad_laboral_sector.nombreEmpresaSociedadAsociacion if actividad_laboral_sector.nombreEmpresaSociedadAsociacion else "",
                    "rfc":actividad_laboral_sector.rfc if actividad_laboral_sector.rfc else "",   
                    "empleoCargo": actividad_laboral_sector.empleo_cargo_comision if actividad_laboral_sector.empleo_cargo_comision else "",
                    "fechaIngreso": actividad_laboral_sector.posesion_inicio.strftime(TIME_FORMAT) if actividad_laboral_sector.posesion_inicio else "2020-01-01",   
                    "salarioMensualNeto": serialize_monto(
                        actividad_laboral_sector.salarioMensualNeto, actividad_laboral_sector.moneda.codigo
                    ),
                },
            }
            if actividadLaboral:
                serialized["actividadLaboral"] = serialize_actividad_laboral(actividadLaboral,'DEPENDIENTE')
            if poder:
                # $ref: '#/components/schemas/ambitoPublico'
                serialized["actividadLaboralSectorPublico"]["ambitoPublico"] = serialize_ambito_publico(
                    poder
                )
            if funcion_principal:
               serialized["actividadLaboralSectorPublico"]["funcionPrincipal"] = funcion_principal.funcion

            if tipo_operaciones:
                # $ref : '#/components/schemas/tipoOperacion'
                serialized["tipoOperacion"]= serialize_tipo_operacion(tipo_operaciones)

            if actividad_laboral_sector.moneda:
                serialized["actividadLaboralSectorPrivadoOtro"]["salarioMensualNeto"]["moneda"] = \
                actividad_laboral_sector.moneda.codigo


            return serialized
        else:
            return{}

    serialized = {
        "ninguno": serialize_declaracion_seccion(declaracion, SECCIONES["DEPENDIENTES"],"NINGUNO"),
        # 
        "dependienteEconomico": [],
        #"aclaracionesObservaciones": serialize_declaracion_seccion(declaracion, SECCIONES["DEPENDIENTES"]) #CAMPO_PRIVADO
    }

    if not serialized["ninguno"]:
        serialized["dependienteEconomico"] = [
            serialize_dependiente_economico(dependiente_economico) for dependiente_economico in declaracion.conyugedependientes_set.filter(es_pareja=0) 
        ]

    return serialized

def serialize_nivel_orden_gobierno(nivel_gobierno):
    """
    # $ref: '#/components/schemas/nivelOrdenGobierno'
    """
    if nivel_gobierno:
        return  nivel_gobierno.codigo

    return "ESTATAL"

def serialize_ambito_publico(ambito_publico):
    """
    # $ref: '#/components/schemas/ambitoPublico'
                    
    """
    if ambito_publico:
        return ambito_publico.codigo if ambito_publico.codigo else "EJECUTIVO"

    return "EJECUTIVO"

def serialize_actividad_laboral(actividad_aboral, tipo):
    """
    $ref: '#/components/schemas/actividadLaboral'
    """
    clave = "OTRO"
    if actividad_aboral:
        return {
            "clave": actividad_aboral.codigo, # actividad_aboral.clave,
            "valor": actividad_aboral.ambito_laboral, #actividad_aboral.valor
        }

    if tipo == 'EXPERIENCIA':
        clave = "OTR"

    return {"clave": clave, "valor":"No aplica"}

def serialize_tipo_operacion(operacion):
    """
    # $ref : '#/components/schemas/tipoOperacion'
    """
    if operacion:
        return operacion.codigo
    else:
        return 'AGREGAR'


def serialize_relacion_con_declarante(relacion):
    if relacion:
        return relacion.codigo

    return "CONYUGE"

def serialize_parentesco_relacion(parentezco):
    """
     # $ref : '#/components/schemas/parentescoRelacion'               
    """
    if parentezco:
        return {
            "clave": parentezco.codigo,
            "valor": parentezco.tipo_relacion
        }
    return {"clave":"OTRO", "valor": "Otro"}

def serialize_sector_industria(sector):
    """
    # $ref: '#/components/schemas/sector'
    """
    if sector:
        return {
            "clave": sector.codigo,
            "valor": sector.sector_industria
        }
    return {"clave":"OTRO","valor":"No aplica"}


def serialize_participacion(declaracion):
    """
    # $ref: '#/components/schemas/participacion'
    """
    socios_comerciales = declaracion.socioscomerciales_set.all()

    to_be_add = []
    for socio in socios_comerciales:
        titular = serialize_tipo_relacion(socio.tipoRelacion)

        if titular == "DECLARANTE" and socio.tipoRelacion is not None:
            to_be_add.append(socio.pk)
    
    socios_comerciales = socios_comerciales.filter(id__in=to_be_add)
    count_row_total = len(socios_comerciales)
    
    def serialize_socio_comercial(socio_comercial):
        if socios_comerciales:
            tipo_relacion =  socio_comercial.tipoRelacion

            if tipo_relacion:
                # $ref: '#/components/schemas/tipoRelacion'
                serialized= {
                    "tipoRelacion": serialize_tipo_relacion(socio_comercial.tipoRelacion)
                }

                if serialized["tipoRelacion"] ==  "DECLARANTE":
                    moneda = socio_comercial.moneda
                    domicilio = socio_comercial.socio_infopersonalvar.domicilios

                    serialized["nombreEmpresaSociedadAsociacion"]= socio_comercial.actividad_vinculante if socio_comercial.actividad_vinculante else ""
                    serialized["rfc"]= socio_comercial.rfc_entidad_vinculante if socio_comercial.rfc_entidad_vinculante else ""
                    serialized["porcentajeParticipacion"]= int(socio_comercial.porcentaje_participacion) if socio_comercial.porcentaje_participacion else 0
                    serialized["recibeRemuneracion"]= socio_comercial.recibeRemuneracion if socio_comercial.recibeRemuneracion else False

                    if socio_comercial.socio_infopersonalvar.cat_sectores_industria:
                        # $ref: '#/components/schemas/sector'
                        serialized["sector"]: serialize_sector_industria(
                            socio_comercial.socio_infopersonalvar.cat_sectores_industria
                        ) 
                    if socio_comercial.tipoParticipacion:
                        # $ref: '#/components/schemas/tipoParticipacion'
                        serialized["tipoParticipacion"] =  serialize_tipo_participacion(
                            socio_comercial.tipoParticipacion
                        )
                    if socio_comercial.cat_tipos_operaciones:
                        # $ref : '#/components/schemas/tipoOperacion'
                        serialized["tipoOperacion"] = serialize_tipo_operacion(
                            socio_comercial.cat_tipos_operaciones
                        )

                    if moneda:
                        # $ref: '#/components/schemas/monto' AQUI
                        serialized["montoMensual"]: serialize_monto(
                            socio_comercial.montoMensual,
                            moneda
                        )
                    if domicilio:
                        serialized["ubicacion"]= {
                            # $ref: '#/components/schemas/pais' 
                            "pais": domicilio.cat_pais,
                            # $ref: '#/components/schemas/entidadFederativa'
                            "entidadFederativa": serialize_entidad_federativa(socio_infopersonalvar.cat_entidades_federativas)
                        }
            return serialized

    serialized = {
        "ninguno": serialize_declaracion_seccion(declaracion, SECCIONES["PARTICIPACION"],"NINGUNO",count_row_total),
        "participacion": [],
        #"aclaracionesObservaciones": serialize_declaracion_seccion(declaracion, SECCIONES["PARTICIPACION"]) #CAMPO_PRIVADO
    }

    if not serialized["ninguno"]:
        serialized["participacion"] = [
            serialize_socio_comercial(socio_comercial) for socio_comercial in socios_comerciales
        ]

    return serialized

def serialize_clientes_principales(declaracion):
    """
    # $ref: '#/components/schemas/clientesPrincipales'
    """
    clientes_principales = declaracion.clientesprincipales_set.all()

    to_be_add = []
    for cliente in clientes_principales:
        titular = serialize_tipo_relacion(cliente.cat_tipos_relaciones_personales)

        if titular == "DECLARANTE" and cliente.cat_tipos_relaciones_personales is not None:
            to_be_add.append(cliente.pk)
    
    clientes_principales = clientes_principales.filter(id__in=to_be_add)
    count_row_total = len(clientes_principales)


    def serialize_cliente_principal(cliente_principal):
        """
        """
        tipo_relacion = cliente_principal.cat_tipos_relaciones_personales

        if tipo_relacion:
            # $ref: '#/components/schemas/tipoRelacion'
            serialized = {
                "tipoRelacion":serialize_tipo_relacion(tipo_relacion),
                "clientePrincipal": {}
            }

            if serialized["tipoRelacion"] == 'DECLARANTE':
                info_personal_var = cliente_principal.info_personal_var

                serialized["realizaActividadLucrativa"] = cliente_principal.realizaActividadLucrativa
                serialized["empresa"]= {
                    "nombreEmpresaServicio": info_personal_var.nombre_negocio if info_personal_var.nombre_negocio else "",
                    "rfc": info_personal_var.rfc_negocio if info_personal_var.rfc_negocio else ""
                }
                # $ref: '#/components/schemas/ubicacion'
                serialized["ubicacion"]=serialize_ubicacion(info_personal_var.domicilios)
                serialized["clientePrincipal"]["tipoPersona"] = serialize_persona_fisica_moral(info_personal_var.es_fisica)

                if serialized["clientePrincipal"]["tipoPersona"] == 'MORAL':
                    serialized["clientePrincipal"] = {
                        "nombreRazonSocial": serialize_nombre_completo_razon_social(info_personal_var),
                        "rfc": info_personal_var.rfc if info_personal_var.rfc else ""
                    }

                if cliente_principal.cat_tipos_operaciones:
                    # $ref: '#/components/schemas/tipoOperacion'
                    serialized["tipoOperacion"] = serialize_tipo_operacion(
                        cliente_principal.cat_tipos_operaciones
                    )
                if info_personal_var.cat_sectores_industria:
                    # $ref: '#/components/schemas/sector'
                    serialized["sector"] = serialize_sector_industria(
                        info_personal_var.cat_sectores_industria
                    )
                if cliente_principal.moneda:
                    # $ref: '#/components/schemas/monto'
                    serialized["montoAproximadoGanancia"] = serialize_monto(
                        cliente_principal.monto,  cliente_principal.moneda.codigo
                    )
            
        return serialized
    serialized = {
        "ninguno": serialize_declaracion_seccion(declaracion, SECCIONES["CLIENTES"],"NINGUNO",count_row_total),
        "cliente": [],
        #"aclaracionesObservaciones": serialize_declaracion_seccion(declaracion,SECCIONES["CLIENTES"]) #CAMPO_PRIVADO
    }

    if not serialized["ninguno"]:
        serialized["cliente"] = [
            serialize_cliente_principal(cliente_principal) for cliente_principal in clientes_principales  
        ]

    return serialized

def serialize_forma_recepcion(forma_recepcion):
    """
    # $ref: '#/components/schemas/formaRecepcion'
    """
    if forma_recepcion:
        return forma_recepcion.forma_recepcion
    return ""


def serialize_beneficios_privados(declaracion):
    """
    # $ref: '#/components/schemas/beneficiosPrivados'
    """
    beneficios = declaracion.beneficiosgratuitos_set.all()

    to_be_add = []
    for beneficio in beneficios:
        titular = serialize_tipo_relacion(beneficio.cat_tipos_relaciones_personales)

        if titular == "DECLARANTE" and beneficio.cat_tipos_relaciones_personales is not None:
            to_be_add.append(beneficio.pk)
    
    beneficios = beneficios.filter(id__in=to_be_add)
    count_row_total = len(beneficios)

    def serialize_beneficio(beneficio):
        # beneficiarios = beneficio.cat_tipos_relaciones_personales_set.all()
        serialized =  {
            "otorgante": {},
            # $ref: '#/components/schemas/formaRecepcion'
            "formaRecepcion": serialize_forma_recepcion(
                beneficio
            ),
            "especifiqueBeneficio": beneficio.especifiqueBeneficio if beneficio.especifiqueBeneficio else ""         
        }
        if beneficio.cat_tipos_operaciones:
            serialized["tipoOperacion"] = serialize_tipo_operacion(beneficio.cat_tipos_operaciones)
        
        if beneficio.tipo_persona:
            # $ref: '#/components/schemas/tipoPersona'
            serialized["otorgante"]["tipoPersona"]= serialize_persona_fisica_moral(beneficio.es_fisica)

            if serialized["otorgante"]["tipoPersona"] == "MORAL":
                serialized["otorgante"]["tipoPersona"]["nombreRazonSocial"] = beneficio.razon_social_otorgante if beneficio.razon_social_otorgante else "" #CAMPO_PRIVADO
                serialized["otorgante"]["tipoPersona"]["rfc"] = beneficio.rfc_otorgante if beneficio.rfc_otorgante else "" #CAMPO_PRIVADO
        
        if beneficio.cat_tipos_beneficios:
            serialized["tipoBeneficio"] = {
                "clave": beneficio.cat_tipos_beneficios.codigo,
                "valor": beneficio.cat_tipos_beneficios.tipo_beneficio
            }
        if beneficio.cat_tipos_relaciones_personales:
            # $ref: '#/components/schemas/beneficiariosPrograma'
            serialized["beneficiario"] = [
                serialize_parentesco_relacion(beneficio.cat_tipos_relaciones_personales)
            ]
        if beneficio.moneda:
            # $ref: '#/components/schemas/monto'
            serialized["montoMensualAproximado"] = serialize_monto(beneficio.valor_beneficio, beneficio.moneda.codigo)

        if beneficio.cat_sectores_industria:
            # $ref: '#/components/schemas/sector'
            serialized["sector"]: serialize_sector_industria(beneficio.cat_sectores_industria)
        return serialized
    
    serialized = {
        "ninguno": serialize_declaracion_seccion(declaracion, SECCIONES["BENEFICIOS"],"NINGUNO",count_row_total), 
        "beneficio": [],
        #"aclaracionesObservaciones": serialize_declaracion_seccion(declaracion,SECCIONES["BENEFICIOS"]) #CAMPO_PRIVADO
    }

    if not serialized["ninguno"]:
        serialized["beneficio"] = [
            serialize_beneficio(beneficio) for beneficio in beneficios
        ]

    return serialized


def serialize_unidad_medida():
    """
    """
    return 


def serialize_superficie(superficie_valor, superficie_unidad):
    """
    # $ref: '#/components/schemas/superficie'
    """
    return {
        "valor": 0 if superficie_valor is None else int(superficie_valor),
        "unidad": superficie_unidad if superficie_unidad else "m2"
    }

def serialize_tipo_inmueble(tipo_inmueble):
    """
    // '#/components/schemas/tipoInmueble'
    """
    if tipo_inmueble:
        return {
            "clave": tipo_inmueble.codigo, 
            "valor": tipo_inmueble.tipo_inmueble, 
        }
    return {"clave":"OTRO","valor":"No aplica"}

def serialize_tipo_vehiculo(vehiculo):
    """
    $ref: #/components/schemas/tipoVehiculo
    """
    if vehiculo.cat_tipos_muebles:
        return {
            "clave": vehiculo.cat_tipos_muebles.codigo, # vehiculo.cat_tipos_muebles.clave
            "valor": vehiculo.cat_tipos_muebles.tipo_mueble
        }
    else:
        return{"clave":"OTRO","valor":"No aplica"}

def serialize_forma_adquisicion(forma_adquisicion):
    """
    # $ref: '#/components/schemas/formaAdquisicion'  
    """
    if forma_adquisicion:
        return {
            "clave": forma_adquisicion.codigo,
            "valor": forma_adquisicion.forma_adquisicion
        }

    return {"clave":"RST","valor":"RIFA O SORTEO"}


def serialize_forma_pago(forma_pago):
    """
    # $ref: '#/components/schemas/formaPago' 
    """
    if forma_pago:
        return forma_pago
    return ""


def serialize_bienes_inmuebles(declaracion):
    """
    # $ref: '#/components/schemas/bienesInmuebles'
    """
    bienes_inmuebles = declaracion.bienesinmuebles_set.all()
    info_personal_vars = declaracion.infopersonalvar_set.all()
    to_be_add = []
    for inmueble in bienes_inmuebles:
        titular = serialize_titular_bien(inmueble.cat_tipos_titulares)

        if titular[0]["clave"] == 'DEC' and inmueble.cat_tipos_titulares is not None:
            to_be_add.append(inmueble.pk)
    
    bienes_inmuebles = bienes_inmuebles.filter(id__in=to_be_add)
    count_row_total = len(bienes_inmuebles)
       

    def serialize_bien_inmueble(bien_inmueble):
        
        if bien_inmueble:
            tipo_operacion = bien_inmueble.cat_tipos_operaciones
            motivo_baja = bien_inmueble.cat_motivo_baja
            forma_adquisicion = bien_inmueble.cat_formas_adquisiciones

            declarante_persona = BienesPersonas.objects.filter(activos_bienes = bien_inmueble.activos_bienes,cat_tipo_participacion_id=BienesPersonas.DECLARANTE).first()

            serialized = {
                # $ref: '#/components/schemas/tipoInmueble'
                "tipoInmueble": serialize_tipo_inmueble(bien_inmueble.cat_tipos_inmuebles),
                # $ref: '#/components/schemas/titularBien'
                "titular": serialize_titular_bien(bien_inmueble.cat_tipos_titulares), #CAMPO_PRIVADO
                "porcentajePropiedad": 0, # bien_inmueble.porcentaje_inversion, 
                # $ref: '#/components/schemas/superficie'
                "superficieTerreno": serialize_superficie(bien_inmueble.superficie_terreno,bien_inmueble.unidad_medida_terreno),
                # $ref: '#/components/schemas/superficie'
                "superficieConstruccion": serialize_superficie(bien_inmueble.superficie_construccion,bien_inmueble.unidad_medida_construccion),
                # $ref: '#/components/schemas/tercero'
                "tercero": serialize_tercero(bien_inmueble),
                # $ref: '#/components/schemas/transmisor'
                "transmisor": serialize_transmisor(bien_inmueble),
                # $ref: '#/components/schemas/formaPago' 
                "formaPago" : bien_inmueble.forma_pago if bien_inmueble.forma_pago else "NO APLICA",
                # $ref: '#/components/schemas/monto'
                "valorAdquisicion": serialize_monto(int(bien_inmueble.precio_adquisicion) if bien_inmueble.precio_adquisicion else 0,bien_inmueble.cat_monedas.codigo if bien_inmueble.cat_monedas else 'MXN'),
                "fechaAdquisicion": bien_inmueble.fecha_adquisicion.strftime(TIME_FORMAT) if bien_inmueble.fecha_adquisicion else "2020-01-01",
                #"datoIdentificacion": bien_inmueble.num_escritura_publica if bien_inmueble.num_escritura_publica else "", #CAMPO_PRIVADO
                "valorConformeA": bien_inmueble.valor_conforme_a if bien_inmueble.valor_conforme_a else "CONTRATO", 
                # $ref: '#/components/schemas/domicilioMexico'
                #"domicilioMexico":  serialize_domicilio_mexico(bien_inmueble.domicilios), #CAMPO_PRIVADO
                # $ref: '#/components/schemas/domicilioExtranjero'
                #"domicilioExtranjero": serialize_domicilio_extranjero(bien_inmueble.domicilios) #CAMPO_PRIVADO                
            }
            if tipo_operacion:
                # $ref : '#/components/schemas/tipoOperacion'
                serialized["tipoOperacion"] = serialize_tipo_operacion(tipo_operacion)

            if motivo_baja:
                # $ref: '#/components/schemas/motivoBaja'
                serialized["motivoBaja"] = serialize_motivo_baja(motivo_baja)

            if forma_adquisicion:
                # $ref: '#/components/schemas/formaAdquisicion'  
                serialized["formaAdquisicion"] = serialize_forma_adquisicion(forma_adquisicion)

            if declarante_persona:
                if declarante_persona.porcentaje:
                    serialized["porcentajePropiedad"] = declarante_persona.porcentaje

        return serialized

    serialized = {
        "ninguno": serialize_declaracion_seccion(declaracion,SECCIONES["INMUEBLES"],"NINGUNO", count_row_total),
        "bienInmueble": [],
        #"aclaracionesObservaciones": serialize_declaracion_seccion(declaracion,SECCIONES["INMUEBLES"]) #CAMPO_PRIVADO
    }

    if not serialized["ninguno"]:
        serialized["bienInmueble"] = [
            serialize_bien_inmueble(bien_inmueble) for bien_inmueble in bienes_inmuebles
        ]

    return serialized

def serialize_motivo_baja(motivo_baja):
    """
    # $ref: '#/components/schemas/motivoBaja'
    """
    if motivo_baja:
        return {
            "clave": motivo_baja.codigo,
            "valor": motivo_baja.forma_baja
        }
    return{"clave":"OTRO","valor": "No aplica"}

def serialize_vehiculos(declaracion):
    """
    # $ref: '#/components/schemas/vehiculos'   
    """
    vehiculos = declaracion.mueblesnoregistrables_set.all()
    info_personal_vars = declaracion.infopersonalvar_set.all()

    to_be_add = []
    for vehiculo in vehiculos:
        titular = serialize_titular_bien(vehiculo.cat_tipos_titulares)

        if titular[0]["clave"] == 'DEC' and vehiculo.cat_tipos_titulares is not None:
            to_be_add.append(vehiculo.pk)
    
    vehiculos = vehiculos.filter(id__in=to_be_add)
    count_row_total = len(vehiculos)

    def serialize_vehiculo(vehiculo):
        tipo_operacion = vehiculo.cat_tipos_operaciones
        tipo_vehiculo = vehiculo.cat_tipos_muebles
        pais = vehiculo.cat_paises
        motivo_baja = vehiculo.cat_motivo_baja

        serialized = {
            # $ref: '#/components/schemas/titularBien'
            "titular": serialize_titular_bien(vehiculo.cat_tipos_titulares), #CAMPO_PRIVADO
            # $ref: '#/components/schemas/transmisor'
            "transmisor": serialize_transmisor(vehiculo),
            "marca": vehiculo.marca if vehiculo.marca else "",
            "modelo": vehiculo.modelo if vehiculo.modelo else "",
            "anio": vehiculo.anio if vehiculo.anio else 2000,
            #"numeroSerieRegistro": vehiculo.num_serie if vehiculo.num_serie else "", #CAMPO_PRIVADO
            # $ref: '#/components/schemas/tercero'  
            "tercero": serialize_tercero(vehiculo),
            #"lugarRegistro": { #CAMPO_PRIVADO
            #        # $ref: '#/components/schemas/entidadFederativa'
            #        "entidadFederativa": serialize_entidad_federativa(vehiculo.domicilios.cat_entidades_federativas)
            #},
            # $ref: '#/components/schemas/formaAdquisicion'
            "formaAdquisicion": serialize_forma_adquisicion(vehiculo.cat_formas_adquisiciones),
            # $ref: '#/components/schemas/valorAdquisicion'
            "valorAdquisicion": serialize_monto(int(vehiculo.precio_adquisicion) if vehiculo.precio_adquisicion else 0,vehiculo.cat_monedas.codigo if vehiculo.cat_monedas else 'MXN'),
            #$ref: '#/components/schemas/formaPago'
            "formaPago": vehiculo.forma_pago if vehiculo.forma_pago else "NO APLICA",
            "fechaAdquisicion": vehiculo.fecha_adquisicion.strftime(TIME_FORMAT) if vehiculo.fecha_adquisicion else "2020-01-01",
        }

        if tipo_operacion:
            # $ref : '#/components/schemas/tipoOperacion' 
            serialized["tipoOperacion"] = serialize_tipo_operacion(tipo_operacion)

        if motivo_baja:
            # $ref: '#/components/schemas/motivoBaja'
            serialized["motivoBaja"] = serialize_motivo_baja(motivo_baja)
            pass

        if tipo_vehiculo:
            # $ref: '#/components/schemas/tipoVehiculo'
            serialized["tipoVehiculo"] = serialize_tipo_vehiculo(vehiculo)
        if pais:
            # $ref: '#/components/schemas/pais'
            serialized["lugarRegistro"]["pais"] = serialize_pais(vehiculo.cat_paises)
                    
        return serialized

    serialized = {
        "ninguno": serialize_declaracion_seccion(declaracion,SECCIONES["VEHICULOS"],"NINGUNO",count_row_total),
        "vehiculo": [],
        #"aclaracionesObservaciones": serialize_declaracion_seccion(declaracion,SECCIONES["VEHICULOS"]) #CAMPO_PRIVADO
    }

    if not serialized["ninguno"]:
        serialized["vehiculo"] = [
            serialize_vehiculo(vehiculo) for vehiculo in vehiculos
        ]

    return serialized


def serialize_bienes_muebles(declaracion):
    """
    # $ref: '#/components/schemas/bienesMuebles'
    """
    bienes_muebles = declaracion.bienesmuebles_set.all()
    info_personal_vars = declaracion.infopersonalvar_set.all()

    to_be_add = []
    for mueble in bienes_muebles:
        titular = serialize_titular_bien(mueble.cat_tipos_titulares)

        if titular[0]["clave"] == 'DEC' and mueble.cat_tipos_titulares is not None:
            to_be_add.append(mueble.pk)
    
    bienes_muebles = bienes_muebles.filter(id__in=to_be_add)
    count_row_total = len(bienes_muebles)

    def serialize_bien_mueble(bien_mueble):
        """
        """
        tipo_operacion = bien_mueble.cat_tipos_operaciones
        motivo_baja = bien_mueble.cat_motivo_baja
        serialized = {
            # $ref: '#/components/schemas/titularBien'
            "titular": serialize_titular_bien(bien_mueble.cat_tipos_titulares), #CAMPO_PRIVADO
            "tipoBien": serialize_tipos_bien(bien_mueble.cat_tipos_muebles),
            # $ref: '#/components/schemas/transmisor'
            "transmisor": serialize_transmisor(bien_mueble),
            "tercero": serialize_tercero(bien_mueble),
            "descripcionGeneralBien": bien_mueble.descripcion_bien if bien_mueble.descripcion_bien else "",
            "valorAdquisicion": serialize_monto(int(bien_mueble.precio_adquisicion) if bien_mueble.precio_adquisicion else 0,bien_mueble.cat_monedas.codigo if bien_mueble.cat_monedas else 'MXN'),
            "formaPago": bien_mueble.forma_pago if bien_mueble.forma_pago else "NO APLICA",
            "fechaAdquisicion": bien_mueble.fecha_adquisicion.strftime(TIME_FORMAT) if bien_mueble.fecha_adquisicion else "2020-01-01",
        }
        if tipo_operacion:
            # $ref : '#/components/schemas/tipoOperacion'
            serialized["tipoOperacion"] = serialize_tipo_operacion(tipo_operacion)

        if motivo_baja:
            # $ref: '#/components/schemas/motivoBaja'
            serialized["motivoBaja"] = serialize_motivo_baja(motivo_baja)

        if bien_mueble.cat_formas_adquisiciones:
            # $ref: '#/components/schemas/formaAdquisicion'
            serialized["formaAdquisicion"] = serialize_forma_adquisicion(bien_mueble.cat_formas_adquisiciones)
            
        return serialized
    
    serialized = {
        "ninguno": serialize_declaracion_seccion(declaracion,SECCIONES["MUEBLES"],"NINGUNO",count_row_total),
        "bienMueble": [],
        #"aclaracionesObservaciones": serialize_declaracion_seccion(declaracion,SECCIONES["MUEBLES"]) #CAMPO_PRIVADO
    }

    if not serialized["ninguno"]:
        serialized["bienMueble"] = [
            serialize_bien_mueble(bien_mueble) for bien_mueble in bienes_muebles
        ]

    return serialized


def serialize_transmisor(bien_inmueble):
    """
    $ref: '#/components/schemas/transmisor'
    """
    personas = BienesPersonas.objects.filter(activos_bienes = bien_inmueble.activos_bienes,cat_tipo_participacion_id=BienesPersonas.PROPIETARIO_ANTERIOR)

    def serialize_transm(transmisor):
        if transmisor:
            serialized = {
              "tipoPersona": serialize_persona_fisica_moral(transmisor.otra_persona.es_fisica)
            }

            if serialized["tipoPersona"] == 'MORAL':
                serialized["nombreRazonSocial"] = serialize_nombre_completo_razon_social(transmisor.otra_persona) #CAMPO_PRIVADO
                serialized["rfc"] = transmisor.otra_persona.rfc if transmisor.otra_persona.rfc else "" # CAMPO_PRIVADO
                # $ref: '#/components/schemas/parentescoRelacion'
                serialized["relacion"] = serialize_parentesco_relacion(transmisor.tipo_relacion) #CAMPO_PRIVADO

            return serialized
    return [
       serialize_transm(transmisor)
        for transmisor in personas
    ]


def serialize_inversiones_cuentas_valores(declaracion):
    """
    # $ref: '#/components/schemas/inversionesCuentasValores'
    """
    inversiones = declaracion.inversiones_set.all()
    info_personal_vars = declaracion.infopersonalvar_set.all()
    count_row_total = len(inversiones)
    
    def serialize_inversion_cuenta_valores(inversion_cuenta_valores):
        tipo_operacion = inversion_cuenta_valores.cat_tipos_operaciones
        serialized = {
            "tipoInversion": serialize_tipo_inversion(inversion_cuenta_valores.cat_tipos_inversiones), 
            "subTipoInversion": serialize_tipo_inversion(inversion_cuenta_valores.cat_tipos_especificos_inversiones,1),
            # $ref: '#/components/schemas/titularBien'
            "titular": serialize_titular_bien(inversion_cuenta_valores.cat_tipos_titulares), #CAMPO_PRIVADO
            "tercero": serialize_tercero_infovar(inversion_cuenta_valores.info_personal_var),
            #"numeroCuentaContrato": inversion_cuenta_valores.num_cuenta, #CAMPO_PRIVADO
            "localizacionInversion": {
                # $ref: '#/components/schemas/pais'
                "pais": serialize_pais(inversion_cuenta_valores.cat_paises),
                "institucionRazonSocial": inversion_cuenta_valores.institucion if inversion_cuenta_valores.institucion else "",
                "rfc": inversion_cuenta_valores.rfc if inversion_cuenta_valores.rfc else "",
            },
            #"saldoSituacionActual": serialize_monto(inversion_cuenta.saldo_actual, inversion_cuenta.cat_monedas.codigo) #CAMPO_PRIVADO
        }
        if tipo_operacion:
            # $ref : '#/components/schemas/tipoOperacion'
            serialized["tipoOperacion"]= serialize_tipo_operacion(tipo_operacion)
        
        return serialized

    serialized = {
        "ninguno": serialize_declaracion_seccion(declaracion,SECCIONES["INVERSIONES"], "NINGUNO",count_row_total),
        "inversion": [],
        #"aclaracionesObservaciones": serialize_declaracion_seccion(declaracion,SECCIONES["INVERSIONES"]) #CAMPO_PRIVADO
    }

    if not serialized["ninguno"]:
        serialized["inversion"] = [
            serialize_inversion_cuenta_valores(inversion) for inversion in inversiones
        ]

    return serialized


def serialize_tipo_inversion(tipo_inversion,tipo=0):
    """
    # $ref: '#/components/schemas/inversiones/tipo_inversion'         
    """
    if tipo_inversion:

        if tipo == 1:
            tipo_valor = tipo_inversion.tipo_especifico_inversion.upper()
            
        else:
            tipo_valor = tipo_inversion.tipo_inversion.upper()

        return {
            "clave": tipo_inversion.codigo,
            "valor": tipo_valor
        }

    if tipo == 1:
        return_default = {"clave": "AFOR","valor": "AFORES"}
    else:
        return_default = {"clave": "AFOT","valor": "AFORES Y OTROS"}
    
    return return_default

def serialize_titular_bien(titulares):
    """
    # $ref: '#/components/schemas/titularBien'         
    """
    # TBD
    if titulares:
        return [{
                "clave": titulares.codigo if titulares.codigo else "DEC",
                "valor": titulares.tipo_titular if titulares.tipo_titular else "DECLARANTE"
        }]

    return [{"clave":"DEC","valor":"DECLARANTE"}]

def serialize_tipos_bien(tipo_mueble):
    if tipo_mueble:
        return{
            "clave": tipo_mueble.codigo,
            "valor": tipo_mueble.tipo_mueble
        }
    return {"clave":"OTRO", "valor":"No aplica"}

def serialize_adeudos_pasivos(declaracion):
    """
    # $ref: '#/components/schemas/adeudosPasivos'    
    """
    adeudos = declaracion.deudasotros_set.all()
    info_personal_vars = declaracion.infopersonalvar_set.all()

    to_be_add = []
    for adeudo in adeudos:
        titular = serialize_titular_bien(adeudo.cat_tipos_titulares)

        if titular[0]["clave"] == 'DEC' and adeudo.cat_tipos_titulares is not None:
            to_be_add.append(adeudo.pk)
    
    adeudos = adeudos.filter(id__in=to_be_add)
    count_row_total = len(adeudos)
    
    def serialize_adeudo_pasivo(adeudo_pasivo):
        if adeudo_pasivo:
            tipo_operacion = adeudo_pasivo.cat_tipos_operaciones
            tipo_adeudo = adeudo_pasivo.cat_tipos_adeudos
            monto_original = adeudo_pasivo.cat_monedas
            saldoactual = adeudo_pasivo.cat_monedas
            tercero = adeudo_pasivo.tercero_infopersonalvar
            serialized = {
                # $ref: '#/components/schemas/titularBien'
                "titular":  serialize_titular_bien(adeudo_pasivo.cat_tipos_titulares), #CAMPO_PRIVADO
                "tipoAdeudo": serialize_tipo_adeudo(adeudo_pasivo.cat_tipos_adeudos),
                "numeroCuentaContrato": adeudo_pasivo.numero_cuenta if adeudo_pasivo.numero_cuenta else "", #CAMPO_PRIVADO
                "fechaAdquisicion": adeudo_pasivo.fecha_generacion.strftime(TIME_FORMAT) if adeudo_pasivo.fecha_generacion else "2020-01-01",
                # $ref: '#/components/schemas/monto'
                "montoOriginal": serialize_monto( int(adeudo_pasivo.monto_original) if adeudo_pasivo.monto_original else 0, adeudo_pasivo.cat_monedas.codigo if adeudo_pasivo.cat_monedas else 'MXN'),
                # $ref: '#/components/schemas/monto'
                #"saldoInsolutoSituacionActual": serialize_monto(adeudo_pasivo.saldo_pendiente , adeudo_pasivo.cat_monedas.codigo), #CAMPO_PRIVADO
                "otorganteCredito": {
                    "nombreInstitucion": adeudo_pasivo.acreedor_nombre if adeudo_pasivo.acreedor_nombre else "",
                    "rfc": adeudo_pasivo.acreedor_rfc if adeudo_pasivo.acreedor_rfc else "",
                },
                "localizacionAdeudo": {
                    # $ref: '#/components/schemas/pais'
                    "pais": serialize_pais(adeudo_pasivo.cat_paises) #TBD
                }
            }

            # $ref: '#/components/schemas/tercero'
            if tercero:
                serialized["tercero"] = serialize_tercero_infovar(adeudo_pasivo.tercero_infopersonalvar)

            # $ref: '#/components/schemas/monto'
            if monto_original:
                serialized["montoOriginal"] = serialize_monto(adeudo_pasivo.monto_original,monto_original.codigo)
            else:
                serialized["montoOriginal"] = serialize_monto(adeudo_pasivo.monto_original,'MXN')
           
            # $ref: '#/components/schemas/monto'
            #if saldoactual:
            #    serialized["saldoInsolutoSituacionActual"] = serialize_monto(adeudo_pasivo.saldo_pendiente , adeudo_pasivo.cat_monedas.codigo)
            #else:
            #    serialized["saldoInsolutoSituacionActual"] = serialize_monto(adeudo_pasivo.saldo_pendiente , 'MXn')

            if tipo_adeudo:
                serialized["tipoAdeudo"] = {
                    "clave": tipo_adeudo.codigo,
                    "valor": tipo_adeudo.tipo_adeudo
                }
            if tipo_operacion:
                # $ref : '#/components/schemas/tipoOperacion'
                serialized["tipoOperacion"]= serialize_tipo_operacion(tipo_operacion)
            if adeudo_pasivo.acredor_es_fisica:
                # $ref: '#/components/schemas/tipoPersona'
                serialized["otorganteCredito"]["tipoPersona"] = serialize_persona_fisica_moral(adeudo_pasivo.acredor_es_fisica)
                serialized["otorganteCredito"]["razon_social"] = adeudo_pasivo.acreedor_nombre if adeudo_pasivo.acreedor_nombre else "" 
                serialized["otorganteCredito"]["rfc"] = adeudo_pasivo.acreedor_rfc if adeudo_pasivo.acreedor_rfc else ""
                
            return serialized
        return {}
        
    serialized = {
        "ninguno": serialize_declaracion_seccion(declaracion,SECCIONES["ADEUDOS"], "NINGUNO",count_row_total),
        "adeudo": [],
        #"aclaracionesObservaciones": serialize_declaracion_seccion(declaracion,SECCIONES["ADEUDOS"]) #CAMPO_PRIVADO
    }

    if not serialized["ninguno"]:
        serialized["adeudo"] = [
            serialize_adeudo_pasivo(adeudo) for adeudo in adeudos
        ]

    return serialized

def serialize_prestamo_comodato(declaracion):
    """
    # $ref: '#/components/schemas/prestamoComodato'
    """
    prestamocomodato = declaracion.prestamocomodato_set.all()

    def serialize_prestamo(prestamo):

        titular = prestamo.titular_infopersonalVar
        serialized = {
            "tipoOperacion": serialize_tipo_operacion(prestamo.cat_tipos_operaciones),
            "tipoBien": {},
            "duenoTitular": {
               "tipoDuenoTitular": "FISICA",
               "nombreTitular": "",
               "rfc":"",
               "relacionConTitular": ""
            }
        }

        if prestamo.cat_tipos_inmueble is not None:
            serialized["tipoBien"]["inmueble"] = {
                # $ref: '#/components/schemas/tipoInmueble'
                "tipoInmueble": serialize_tipo_inmueble(prestamo.cat_tipos_inmueble),
                # $ref: '#/components/schemas/domicilioMexico'
                #"domicilioMexico": serialize_domicilio_mexico(prestamo.inmueble_domicilios), #CAMPO_PRIVADO
                # $ref: '#/components/schemas/domicilioExtranjero' 
                #"domicilioExtranjero": serialize_domicilio_extranjero(prestamo.inmueble_domicilios) #CAMPO_PRIVADO
            }

        if prestamo.cat_tipos_muebles is not None:
            serialized["tipoBien"]["vehiculo"] = {
                # #/components/schemas/tipoVehiculo
                "tipo": serialize_tipo_vehiculo(prestamo),
                "marca": prestamo.mueble_marca if prestamo.mueble_marca else "",
                "modelo": prestamo.mueble_modelo if prestamo.mueble_modelo else "",
                "anio": int(prestamo.mueble_anio) if prestamo.mueble_anio else 0,
                #"numeroSerieRegistro": prestamo.mueble_num_registro if prestamo.mueble_num_registro else "", #CAMPO_PRIVADO
                #"lugarRegistro": { #CAMPO_PRIVADO
                #    # #/components/schemas/pais
                #    "pais": serialize_pais(prestamo.cat_paises),
                #    # #/components/schemas/entidadFederativa
                #    "entidadFederativa": serialize_entidad_federativa(prestamo.inmueble_domicilios.cat_entidades_federativas)
                #}
            }


        if titular:
            serialized["duenoTitular"] = {
                "tipoDuenoTitular": serialize_persona_fisica_moral(titular.es_fisica)
            }

            if serialized["duenoTitular"]["tipoDuenoTitular"] == 'MORAL':
                serialized["duenoTitular"]["nombreTitular"] = titular.nombres if titular.nombres else ""
                serialized["duenoTitular"]["rfc"] = titular.rfc if titular.rfc else ""
                serialized["duenoTitular"]["relacionConTitular"] = prestamo.titular_relacion.tipo_relacion if prestamo.titular_relacion else ""

        return serialized

    serialized = {
        "ninguno": serialize_declaracion_seccion(declaracion,SECCIONES["PRESTAMO"],"NINGUNO"),
        "prestamo": [],
        #"aclaracionesObservaciones": serialize_declaracion_seccion(declaracion,SECCIONES["PRESTAMO"]) #CAMPO_PRIVADO
    }

    if not serialized["ninguno"]:
        serialized["prestamo"] = [
            serialize_prestamo(prestamo)
            for prestamo in prestamocomodato
        ]

    return serialized


def serialize_tipo_adeudo(tipo_adeudo):

    if tipo_adeudo:
        return {
            "clave": tipo_adeudo.codigo,
            "valor": tipo_adeudo.tipo_adeudo
        }

    return{"clave": "OTRO","valor": "No aplica"}

def serialize_tipo_participacion(tipo_participacion):
    """
    $ref: #/components/schemas/tipoParticipacion
    """
    if tipo_participacion:
        return {
            "clave": tipo_participacion.codigo,
            "valor": tipo_participacion.tipo_persona
        }
    return{"clave": "OTRO","valor": "No aplica"}


def serialize_tercero(bien_inmueble):

    personas = BienesPersonas.objects.filter(activos_bienes = bien_inmueble.activos_bienes,cat_tipo_participacion_id=BienesPersonas.COPROPIETARIO)

    def serialize_tercero_(tercero):
        serialized = {
            "tipoPersona": serialize_persona_fisica_moral(tercero.otra_persona.es_fisica)
        }

        if serialized["tipoPersona"] == 'MORAL':
            serialized["nombreRazonSocial"]= serialize_nombre_completo_razon_social(tercero.otra_persona) #CAMPO_PRIVADO
            serialized["rfc"]= tercero.otra_persona.rfc if tercero.otra_persona.rfc else "" #CAMPO_PRIVADO
            
        return serialized

    return [
        serialize_tercero_(tercero)
        for tercero in personas
    ]

def serialize_tercero_infovar(tercero):
    """
    $ref: '#/components/schemas/tercero'
    """
    def serialize_tercer(tercero):
        serialized = {
            "nombreRazonSocial": serialize_nombre_completo_razon_social(tercero),
            "rfc": tercero.rfc if tercero.rfc else ""
        }

        if tercero.cat_tipo_persona:
            serialized["tipoPersona"] = serialize_persona_fisica_moral(tercero.es_fisica)

        return serialized
    return [
        serialize_tercer(tercero)
    ]


def serialize_monto(valor=0, moneda="MXN"):
    """
    $ref: '#/components/schemas/monto'
    """
    if valor:
        return {
            "valor": 0 if valor is None else int(valor),
            "moneda": moneda
        }
    return {"valor": 0, "moneda": moneda}

def serialize_tipo_instrumento(tipo_instrumento):
    if tipo_instrumento:
        return{ 
            "clave": tipo_instrumento.clave,
            "valor": tipo_instrumento.valor
        }
    else:
        return{"clave":"OTRO","valor":"No aplica"}


def dic_default_ingresos(declaracion):
    
    return {
        "actividadIndustrialComercialEmpresarial": {
            "remuneracionTotal": {
                "valor": 0,
                "moneda": "MXN"
            },
            "actividades": [
                {
                "remuneracion": {
                    "valor": 0,
                    "moneda": "MXN"
                },
                "nombreRazonSocial": "",
                "tipoNegocio": ""
                }
            ]
            },
            "actividadFinanciera": {
            "remuneracionTotal": {
                "valor": 0,
                "moneda": "MXN"
            },
            "actividades": [
                {
                "remuneracion": {
                    "valor": 0,
                    "moneda": "MXN"
                },
                "tipoInstrumento": {
                    "clave": "OTRO",
                    "valor": "No aplica"
                }
                }
            ]
            },
            "serviciosProfesionales": {
            "remuneracionTotal": {
                "valor": 0,
                "moneda": "MXN"
            },
            "servicios": [
                {
                "remuneracion": {
                    "valor": 0,
                    "moneda": "MXN"
                },
                "tipoServicio": ""
                }
            ]
            },
            "otrosIngresos": {
            "remuneracionTotal": {
                "valor": 0,
                "moneda": "MXN"
            },
            "ingresos": [
                {
                "remuneracion": {
                    "valor": 0,
                    "moneda": "MXN"
                },
                "tipoIngreso": ""
                }
            ]
            },
            "enajenacionBienes": {
            "remuneracionTotal": {
                "valor": 0,
                "moneda": "MXN"
            },
            "bienes": [
                {
                "remuneracion": {
                    "valor": 0,
                    "moneda": "MXN"
                },
                "tipoBienEnajenado": "MUEBLE"
                }
            ]
            },
            "aclaracionesObservaciones": "",
            "servidorPublicoAnioAnterior": False,
            "fechaIngreso": "2020-01-01",
            "fechaConclusion": "2020-01-01",
            serialzied_key[declaracion.cat_tipos_declaracion.codigo][0]: {
            "valor": 0,
            "moneda": "MXN"
            },
            "otrosIngresosTotal": {
            "valor": 0,
            "moneda": "MXN"
            },
            serialzied_key[declaracion.cat_tipos_declaracion.codigo][1]: {
            "valor": 0,
            "moneda": "MXN"
            },
            "ingresoNetoAnualParejaDependiente": {
            "valor": 0,
            "moneda": "MXN"
            },
            serialzied_key[declaracion.cat_tipos_declaracion.codigo][2]: {
            "valor": 0,
            "moneda": "MXN"
            }
        }

def serialize_nombre_completo_razon_social(persona):
    nombre_razon_social = ""
    if persona:
        if persona.es_fisica:
            if persona.nombres and persona.apellido1:
                nombre_razon_social = "{} {} {}".format(persona.nombres,persona.apellido1, persona.apellido2)
        else:
            if persona.razon_social:
                nombre_razon_social = persona.razon_social

    return nombre_razon_social

def serialize_declaracion_seccion(declaracion, seccion_id, tipo="OBSERVACION", count_rows = 1):
    """
        Obtiene información relevante de la sección
    """
    dato = "" if tipo == 'OBSERVACION' else False
    dato = True if tipo == 'NINGUNO' else dato

    seccion_declaracion = declaracion.secciondeclaracion_set.filter(seccion=seccion_id).first()
    if seccion_declaracion:
        if tipo == 'OBSERVACION':
            if seccion_declaracion.observaciones:
                dato = seccion_declaracion.observaciones.observacion
        elif tipo == 'NINGUNO':
            dato = True
            if count_rows != 0:
                if seccion_declaracion.aplica:
                    if seccion_declaracion.aplica == True or seccion_declaracion.aplica == 1:
                        dato = False #Si no aplica es 1/True quiere decir hau datos por lo que ninguno debería ser False por que si existen datos
                    else:
                        dato = True #Si no aplica viene 0/False quiere decir que no hay datos por lo que ninguno debería ser True por que no hay ningun registro
                
        elif tipo == 'CAMPOS_PRIVADOS':
            dato = campos_configuracion(seccion_declaracion.seccion,'p')

    return dato

def serialize_empleo_cargo_comision(declaracion, encargo):
    """
    $ref: #/components/schemas/tipoParticipacion

    """
    historico = HistoricoAreasPuestos.objects.filter(info_personal_fija=declaracion.info_personal_fija, fecha_inicio__lte=declaracion.fecha_recepcion.date())
    if len(historico) > 1:
        ''' 
        En caso de que se obtenga más resultados con las mismas fechas inicio, se hace una validación adicional sobrel el nivel del puesto
        El nivel que se guarda en encargo, es el nivel actual del puesto que usa en la declaración y ese mismo nivel se toma 
        para guardarlo en historico, ya que este es por declaración se toma con referencia para filtrar un poco más preciso
        '''
        historico = historico.filter(nivel=encargo.nivel_encargo)

        '''Filtro adicional en caso de que siga arrojando varios resultados,se toma el puesto'''
        if len(historico) > 1:
            historico = historico.filter(id_puesto=encargo.cat_puestos)

    historico = historico.last()
    puesto = historico.txt_puesto
    puesto_codigo = historico.nivel
    area = "{}-{}".format(historico.codigo_area,historico.txt_area)
    
    if puesto:
        return {"puesto": puesto, "puesto_codigo": puesto_codigo, "area": area}
    return None

def serialize_tipo_representacion(representacion):
    if representacion:
        return representacion.codigo

    return "REPRESENTANTE"

def serialize_funciones(funcion):
    if funcion:
        return funcion.funcion if funcion.funcion else ""

    return ""


def date_encoder(obj):
    if isinstance(obj, date):
        return obj.strftime('%Y-%m-%d')  # Convierte la fecha en una cadena en formato ISO
    raise TypeError(f"Object of type {obj.__class__.__name__} is not JSON serializable")


def declaracionesJsonView():
    declaraciones = [ serialize_response_entry(declaracion) for declaracion in Declaraciones.objects.filter(cat_estatus_id=4)]    
    redis_cnx.hmset("declaracion_json",{"declaracion_json":100})

    cadena_json = json.dumps(declaraciones, indent=4) 
    # Guarda los datos JSON en un archivo
    with open('./media/declaraciones/declaraciones.json', 'w') as archivo_json:
        archivo_json.write(cadena_json)
        
    return JsonResponse(declaraciones, safe=False)

if __name__ == "__main__":
    jsonDec = declaracionesJsonView()