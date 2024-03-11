from django.urls import path, re_path
from django.conf.urls import url
from declaracion.views import IngresosDeclaracionView
from declaracion.views.ingresos import IngresosDeclaracionDelete, IngresosDeclaracionUpdate, IngresosDeclaracionAdd
from django.views.generic import TemplateView

urlpatterns = [

     re_path(r'^ingresos-netos/(?P<folio>[0-9a-fA-F]{8}\-[0-9a-fA-F]{4}\-[0-9a-fA-F]{4}\-[0-9a-fA-F]{4}\-[0-9a-fA-F]{12})/$',
            IngresosDeclaracionView.as_view(),
            name='ingresos-netos'),

     re_path(r'^ingresos-servidor-publico/(?P<folio>[0-9a-fA-F]{8}\-[0-9a-fA-F]{4}\-[0-9a-fA-F]{4}\-[0-9a-fA-F]{4}\-[0-9a-fA-F]{12})/$',
            IngresosDeclaracionView.as_view(),
            name='ingresos-servidor-publico'),
    url(r'^ajax/delete-ingresos-servidor/$', IngresosDeclaracionDelete, name='ingresos-delete'),
    url(r'^ajax/update-ingresos-servidor/$', IngresosDeclaracionUpdate, name='ingresos-update'),
    url(r'^ajax/add-ingresos-servidor/$', IngresosDeclaracionAdd, name='ingresos-add'),

]
