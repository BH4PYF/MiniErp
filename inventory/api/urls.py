from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    CategoryViewSet, MaterialViewSet, ProjectViewSet,
    SupplierViewSet, InboundRecordViewSet, PurchasePlanViewSet,
    SubcontractorViewSet, SubcontractCategoryViewSet, SubcontractListViewSet,
    BudgetViewSet, BudgetItemViewSet,
    ContractViewSet, ContractItemViewSet,
    MeasurementViewSet, MeasurementItemViewSet,
    SettlementViewSet, SettlementItemViewSet,
    DeliveryViewSet,
    MaterialPlanViewSet, MaterialPlanItemViewSet,
    OperationLogViewSet, SystemSettingViewSet,
    update_group
)

router = DefaultRouter()
router.register(r'categories', CategoryViewSet, basename='category')
router.register(r'materials', MaterialViewSet, basename='material')
router.register(r'projects', ProjectViewSet, basename='project')
router.register(r'suppliers', SupplierViewSet, basename='supplier')
router.register(r'inbound-records', InboundRecordViewSet, basename='inbound-record')
router.register(r'purchase-plans', PurchasePlanViewSet, basename='purchase-plan')
router.register(r'subcontractors', SubcontractorViewSet, basename='subcontractor')
router.register(r'subcontract-categories', SubcontractCategoryViewSet, basename='subcontract-category')
router.register(r'subcontract-lists', SubcontractListViewSet, basename='subcontract-list')
router.register(r'budgets', BudgetViewSet, basename='budget')
router.register(r'budget-items', BudgetItemViewSet, basename='budget-item')
router.register(r'contracts', ContractViewSet, basename='contract')
router.register(r'contract-items', ContractItemViewSet, basename='contract-item')
router.register(r'measurements', MeasurementViewSet, basename='measurement')
router.register(r'measurement-items', MeasurementItemViewSet, basename='measurement-item')
router.register(r'settlements', SettlementViewSet, basename='settlement')
router.register(r'settlement-items', SettlementItemViewSet, basename='settlement-item')
router.register(r'deliveries', DeliveryViewSet, basename='delivery')
router.register(r'material-plans', MaterialPlanViewSet, basename='material-plan')
router.register(r'material-plan-items', MaterialPlanItemViewSet, basename='material-plan-item')
router.register(r'operation-logs', OperationLogViewSet, basename='operation-log')
router.register(r'system-settings', SystemSettingViewSet, basename='system-setting')

urlpatterns = [
    path('', include(router.urls)),
    path('groups/<int:group_id>/', update_group, name='update_group'),
]
