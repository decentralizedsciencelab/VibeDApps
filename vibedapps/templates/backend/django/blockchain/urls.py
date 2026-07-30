from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

# Create router for viewsets
router = DefaultRouter()
router.register(r'transactions', views.TransactionViewSet)

# Define URL patterns
urlpatterns = [
    # Health check
    path('health/', views.health_check, name='health-check'),
    
    # Contract endpoints
    path('contract/info/', views.get_contract_info, name='contract-info'),
    path('contract/read/<str:method>/', views.read_contract, name='read-contract'),
    path('contract/write/<str:method>/', views.write_contract, name='write-contract'),
    path('contract/events/<str:event_name>/', views.get_events, name='contract-events'),
    
    # Network endpoints
    path('network/status/', views.get_network_status, name='network-status'),
    path('network/gas-price/', views.get_gas_price, name='gas-price'),
    path('network/block/<str:block_number>/', views.get_block_info, name='block-info'),
    
    # Include router URLs
    path('', include(router.urls)),
]
