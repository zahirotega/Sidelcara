from django.urls import path
from django.conf.urls import url

from declaracion.views import (consultarDeclaracionesAjax, consultarDeclarantesAjax, BusquedaDeclarantesFormView, InfoDeclarantesFormView, InfoDeclaracionFormView,
                               BusquedaDeclaracionesFormView, BusquedaUsDecFormView, BusquedaUsuariosFormView, NuevoUsuariosOICFormView,
                               EliminarUsuarioFormView,InfoUsuarioFormView,EditarUsuarioFormView,DescargarReportesView,
                               DeclaracionesGraficas,DeclaracionesGraficasData,RegistroDeclaranteFormView, descargarReporteView,
                               consultaEstatusTaskPDFReporte, eliminarProcesoPDFReporte, cambiarEstatusDatosPublicosDeclaracion, 
                               cambiarEstatusExtemporaneaDeclaracion, consultaDeclaraciones, consultarDeclarantesExcel)
from sitio.views import (consultaEstatusTaskPDFDeclaracion, crearPDFDeclaracion, eliminarProcesoPDF)

urlpatterns = [
    path('busqueda-declarantes', BusquedaDeclarantesFormView.as_view(),
         name='busqueda-declarantes'),
    path('busqueda-declaraciones', BusquedaDeclaracionesFormView.as_view(),
         name='busqueda-declaraciones'),
    path('busqueda-usuarios', BusquedaUsuariosFormView.as_view(),
         name='busqueda-usuarios'),
    path('busqueda-declarantes-declaraciones', BusquedaUsDecFormView.as_view(),
         name='busqueda-declarantes-declaraciones'),
         
    path('info-declarante/<int:pk>/<tipo_registro>/', InfoDeclarantesFormView.as_view(),
         name='info-declarante'),
    path('info-usuario/<int:pk>/', InfoUsuarioFormView.as_view(),
         name='info-usuario'),

    path('reporte/<tipo>', DescargarReportesView.as_view(),
         name='reporte'),

    path('declaraciones-graficas', DeclaracionesGraficas.as_view(),
         name='declaraciones-graficas'),

    path('api-graficas-data', DeclaracionesGraficasData.as_view(),
        name='api-graficas-data'), 

    path('eliminar-usuario/<int:pk>/', EliminarUsuarioFormView.as_view(),
         name='eliminar-usuario'),
    path('editar-usuario/<int:pk>/', EditarUsuarioFormView.as_view(),
         name='editar-usuario'),
    path('nuevo-usuario', NuevoUsuariosOICFormView.as_view(),
         name='nuevo-usuario'),

    path('nuevo-usuario-declarante',RegistroDeclaranteFormView.as_view(),
         name='nuevo-usuario-declarante'),
    path('editar-usuario-declarante/<int:pk>/<tipo_registro>/',RegistroDeclaranteFormView.as_view(),
         name='editar-usuario-declarante'),

    path('info-declaracion/<int:pk>/<tipo>/', InfoDeclaracionFormView.as_view(),
         name='info-declaracion'),
    url(r'^consultaDeclaraciones/$', consultaDeclaraciones, name='consultaDeclaraciones'),
    url(r'^reporte/crear/$', descargarReporteView, name='crear_reporte'),
    url(r'^reporte/consultar/$', consultaEstatusTaskPDFReporte, name='consultar_estatus_reporte'),
    url(r'^reporte/eliminar/$', eliminarProcesoPDFReporte, name='eliminar_procesos_reporte'),
    url(r'^consultar/declaraciones/$', consultarDeclaracionesAjax, name='consultarDeclaracionesAjax'),
    url(r'^consultar/declarantes/$', consultarDeclarantesAjax, name='consultarDeclarantesAjax'),
    url(r'^consultar/declarantesexel/$', consultarDeclarantesExcel, name='consultarDeclarantesAjaxExcel'),
    url(r'^busqueda-declaraciones/crear_pdf_declaracion/$', crearPDFDeclaracion, name='crear_pdf_declaracion'),
    url(r'^busqueda-declaraciones/estatus_pdf_declaracion/$', consultaEstatusTaskPDFDeclaracion, name='estatus_pdf_declaracion'),
    url(r'^busqueda-declaraciones/eliminar_pdf_declaracion_proceso/$', eliminarProcesoPDF, name='eliminar_pdf_declaracion_proceso'),
    url(r'^busqueda-declaraciones/declaracion/cambiar_datos_publicos$', cambiarEstatusDatosPublicosDeclaracion, name='cambiar_datos_publicos'),
    url(r'^busqueda-declaraciones/declaracion/cambiar_extemporanea$', cambiarEstatusExtemporaneaDeclaracion, name='cambiar_extemporanea'),
]
