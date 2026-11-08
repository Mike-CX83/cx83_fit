from django.urls import path, include
from django.contrib.auth import views as auth_views
from tracking import views
from tracking import photo_views
from tracking import summary_views
from tracking import exports
from tracking import trends
from tracking import reviews
from dashboard import oauth
from tracking.oura import views as oura_views
from tracking import public_views
from tracking import plan_views
from tracking import diary_views
from tracking import journal_views
from tracking import clinical_views
from tracking import holding_views

urlpatterns = [
    path('privacy/', public_views.privacy, name='privacy'),
    path('terms/', public_views.terms, name='terms'),
    path('integrations/oura/', oura_views.page, name='oura'),
    path('integrations/oura/start/', oura_views.start, name='oura_start'),
    path('integrations/oura/callback/', oura_views.callback, name='oura_callback'),
    path('integrations/oura/<uuid:connection_id>/disconnect/', oura_views.disconnect, name='oura_disconnect'),
    path('integrations/oura/<uuid:connection_id>/sync/', oura_views.start_sync, name='oura_sync'),
    path('integrations/oura/sync/<uuid:run_id>/resume/', oura_views.resume_sync, name='oura_resume'),
    path('integrations/oura/records/<str:collection>/', oura_views.records, name='oura_records'),
    path('.well-known/oauth-authorization-server', oauth.metadata, name='oauth_metadata'),
    path('oauth/', include('dashboard.oauth_urls')),
    path('connections/', oauth.connections, name='connections'),
    path('connections/<int:application_id>/revoke/', oauth.disconnect, name='connection_revoke'),
    path('login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('manifest.webmanifest', views.manifest, name='manifest'),
    path('', views.overview, name='overview'),
    path('diary/', diary_views.page, name='diary'),
    path('plan/', plan_views.page, name='plan'),
    path('records/', clinical_views.page, name='clinical'),
    path('holding/', holding_views.page, name='holding'),
    path('integrations/sms/inbound/', holding_views.inbound, name='sms_inbound'),
    path('integrations/sms/status/', holding_views.delivery, name='sms_status'),
    path('progress/', views.progress, name='progress'),
    path('more/', views.more, name='more'),
    path('export/', exports.download, name='export'),
    path('trends/', trends.page, name='trends'),
    path('journal/', journal_views.page, name='journal'),
    path('journal/preview/', journal_views.preview, name='journal_preview'),
    path('journal/<uuid:entry_id>/', journal_views.detail, name='journal_detail'),
    path('journal/<uuid:entry_id>/delete/', journal_views.remove, name='journal_delete'),
    path('reviews/', reviews.page, name='reviews'),
    path('reviews/<uuid:note_id>/delete/', reviews.remove, name='review_delete'),
    path('measurements/new/', views.measurement, name='measurement_new'),
    path('measurements/import/', views.measurement_import, name='measurement_import'),
    path('measurements/import/review/<uuid:preview_id>/', views.measurement_import_review, name='measurement_import_review'),
    path('measurements/<uuid:record_id>/', views.measurement, name='measurement_edit'),
    path('measurements/<uuid:record_id>/history/', views.measurement_history, name='measurement_history'),
    path('measurements/<uuid:record_id>/delete/', views.measurement_delete, name='measurement_delete'),
    path('photos/', photo_views.gallery, name='photo_gallery'),
    path('photos/new/', photo_views.upload, name='photo_upload'),
    path('photos/compare/', photo_views.compare, name='photo_compare'),
    path('photos/<uuid:photo_id>/', photo_views.detail, name='photo_detail'),
    path('photos/<uuid:photo_id>/image/', photo_views.image, name='photo_image'),
    path('photos/<uuid:photo_id>/original/', photo_views.image, {'original': True}, name='photo_original'),
    path('photos/<uuid:photo_id>/delete/', photo_views.remove, name='photo_delete'),
    path('nutrition/targets/', summary_views.targets, name='nutrition_targets'),
    path('summaries/import/', summary_views.import_upload, name='summary_import'),
    path('summaries/import/review/<uuid:preview_id>/', summary_views.import_review, name='summary_import_review'),
    path('summaries/<str:kind>/', summary_views.listing, name='summary_list'),
    path('summaries/<str:kind>/new/', summary_views.entry, name='summary_new'),
    path('summaries/<str:kind>/<uuid:record_id>/', summary_views.detail, name='summary_detail'),
    path('summaries/<str:kind>/<uuid:record_id>/edit/', summary_views.entry, name='summary_edit'),
    path('summaries/<str:kind>/<uuid:record_id>/delete/', summary_views.remove, name='summary_delete'),
]
