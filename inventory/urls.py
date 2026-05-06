from django.urls import path
from . import views
from .views import tasks as task_views
from .views import subcontractor, subcontract_list, budget, contract, measurement, settlement, api, material_plan, report

urlpatterns = [
    # 登录/登出
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    # 仪表盘
    path('', views.dashboard, name='dashboard'),
    # 项目管理
    path('projects/', views.project_list, name='project_list'),
    path('projects/save/', views.project_save, name='project_save'),
    path('projects/<int:pk>/delete/', views.project_delete, name='project_delete'),
    path('api/projects/<int:pk>/', views.project_detail_api, name='project_detail_api'),
    path('api/projects/check-name/', views.check_project_name, name='check_project_name'),
    # 材料分类
    path('api/categories/', views.category_list_api, name='category_list_api'),
    # 材料管理
    path('materials/', views.material_list, name='material_list'),
    path('materials/save/', views.material_save, name='material_save'),
    path('materials/<int:pk>/delete/', views.material_delete, name='material_delete'),
    path('api/materials/<int:pk>/', views.material_detail_api, name='material_detail_api'),
    path('api/materials/check-duplicate/', views.check_material_duplicate, name='check_material_duplicate'),
    # 供应商管理
    path('suppliers/', views.supplier_list, name='supplier_list'),
    path('suppliers/save/', views.supplier_save, name='supplier_save'),
    path('suppliers/<int:pk>/delete/', views.supplier_delete, name='supplier_delete'),
    path('api/suppliers/<int:pk>/', views.supplier_detail_api, name='supplier_detail_api'),
    path('api/suppliers/check-duplicate/', views.check_supplier_duplicate, name='check_supplier_duplicate'),
    # 采购计划相关
    path('purchase-plans/', views.purchase_plan_list, name='purchase_plan_list'),
    path('purchase-plans/create/', views.purchase_plan_create, name='purchase_plan_create'),
    path('purchase-plans/save/', views.purchase_plan_save, name='purchase_plan_save'),
    path('purchase-plans/delete/<int:pk>/', views.purchase_plan_delete, name='purchase_plan_delete'),
    path('purchase-plans/approve/<int:pk>/', views.purchase_plan_approve, name='purchase_plan_approve'),
    path('purchase-plans/export/', views.export_purchase_plans, name='export_purchase_plans'),
    path('purchase-plans/detail/<int:pk>/', views.purchase_plan_detail_api, name='purchase_plan_detail_api'),
    path('api/inbound-quantity/<int:project_id>/<int:material_id>/', views.get_inbound_quantity_api, name='get_inbound_quantity_api'),
    # 发货管理
    path('deliveries/', views.delivery_list, name='delivery_list'),
    path('deliveries/create/', views.delivery_create, name='delivery_create'),
    path('deliveries/<int:pk>/', views.delivery_detail, name='delivery_detail'),
    path('deliveries/<int:pk>/confirm-ship/', views.delivery_confirm_ship, name='delivery_confirm_ship'),
    path('api/deliveries/<int:pk>/', views.delivery_detail_api, name='delivery_detail_api'),
    path('deliveries/<int:pk>/edit/', views.delivery_edit, name='delivery_edit'),
    path('deliveries/<int:pk>/delete/', views.delivery_delete, name='delivery_delete'),
    path('deliveries/export/', views.export_deliveries, name='export_deliveries'),
    # 快速收货
    path('quick-receive/', views.quick_receive, name='quick_receive'),
    path('api/delivery-by-no/', views.get_delivery_by_no, name='get_delivery_by_no'),
    path('quick-receive/confirm/', views.quick_receive_confirm, name='quick_receive_confirm'),
    # 入库管理
    path('inbound/', views.inbound_list, name='inbound_list'),
    path('inbound/save/', views.inbound_save, name='inbound_save'),
    path('inbound/<int:pk>/delete/', views.inbound_delete, name='inbound_delete'),
    path('api/inbound/<int:pk>/', views.inbound_detail_api, name='inbound_detail_api'),
    # 材料计划管理
    path('material-plans/', views.material_plan.material_plan_list, name='material_plan_list'),
    path('material-plans/save/', views.material_plan.material_plan_save, name='material_plan_save'),
    path('material-plans/create/', views.material_plan.material_plan_create, name='material_plan_create'),
    path('material-plans/edit/<int:id>/', views.material_plan.material_plan_edit, name='material_plan_edit'),
    path('material-plans/delete/<int:id>/', views.material_plan.material_plan_delete, name='material_plan_delete'),
    path('material-plans/detail/<int:id>/', views.material_plan.material_plan_detail, name='material_plan_detail'),
    path('material-plans/export/', views.material_plan.export_material_plans, name='export_material_plans'),
    path('api/material-plan/<int:plan_id>/items/', views.material_plan.material_plan_items_api, name='material_plan_items_api'),
    path('api/material-plan-items/<int:project_id>/', views.material_plan.material_plan_items_by_project_api, name='material_plan_items_by_project_api'),
    # 统计报表
    path('reports/', report.report_page, name='report_page'),
    path('reports/project-cost/', report.report_project_cost, name='report_project_cost'),
    path('reports/supplier-cost/', report.report_supplier_cost, name='report_supplier_cost'),
    path('reports/monthly/', report.report_monthly, name='report_monthly'),
    # 分包分析报表
    path('reports/project-subcontract/', report.report_project_subcontract, name='report_project_subcontract'),
    path('reports/subcontractor-analysis/', report.report_subcontractor_analysis, name='report_subcontractor_analysis'),
    path('reports/monthly-subcontract/', report.report_monthly_subcontract, name='report_monthly_subcontract'),
    # 图表分析
    path('charts/', report.chart_page, name='chart_page'),
    path('api/chart-data/', report.chart_data_api, name='chart_data_api'),
    path('api/years/', report.get_years_list, name='get_years_list'),
    # Excel 导出/导入
    path('export/', views.export_excel, name='export_excel'),
    path('import/', views.import_excel, name='import_excel'),
    path('import/template/', views.download_import_template, name='download_import_template'),
    # 异步任务
    path('api/tasks/<str:task_id>/status/', task_views.task_status, name='task_status'),
    path('api/export/inventory/', task_views.export_inventory_async, name='export_inventory_async'),
    path('api/export/inbound/', task_views.export_inbound_async, name='export_inbound_async'),
    path('api/export/purchase-plans/', task_views.export_purchase_plans_async, name='export_purchase_plans_async'),
    path('api/export/deliveries/', task_views.export_deliveries_async, name='export_deliveries_async'),
    path('api/export/material-plans/', task_views.export_material_plans_async, name='export_material_plans_async'),
    path('api/backup/', task_views.backup_data_async, name='backup_data_async'),
    # 操作日志
    path('logs/', views.log_list, name='log_list'),
    # 性能监控
    path('performance/', views.performance_dashboard, name='performance_dashboard'),
    path('api/performance/stats/', views.api_performance_stats, name='api_performance_stats'),
    # 用户管理
    path('users/', views.user_list, name='user_list'),
    path('users/save/', views.user_save, name='user_save'),
    path('users/<int:pk>/delete/', views.user_delete, name='user_delete'),
    path('users/groups/', views.user_groups, name='user_groups'),
    path('api/users/<int:pk>/', views.user_detail_api, name='user_detail_api'),
    # 个人设置（所有已登录用户）
    path('profile/', views.profile_page, name='profile_page'),
    path('profile/change-password/', views.change_password, name='change_password'),
    path('profile/update/', views.update_profile, name='update_profile'),
    # 系统设置
    path('settings/', views.settings_page, name='settings_page'),
    path('settings/backup/', views.backup_data, name='backup_data'),
    path('settings/restore/', views.restore_data, name='restore_data'),
    path('settings/add-category/', views.add_custom_category, name='add_custom_category'),
    path('settings/delete-category/<int:pk>/', views.delete_category, name='delete_category'),
    path('api/settings/save/', views.save_system_settings, name='save_system_settings'),
    path('api/settings/save-login-security/', views.save_login_security_settings, name='save_login_security_settings'),
    path('api/settings/users/', views.settings_users_api, name='settings_users_api'),
    path('api/settings/logs/', views.settings_logs_api, name='settings_logs_api'),
    path('settings/clear-all-data/', views.clear_all_data, name='clear_all_data'),
    path('settings/init-categories/', views.init_categories, name='init_categories'),
    # 清单分类相关
    path('api/subcontract-category/list/', views.settings.subcontract_category_list_api, name='subcontract_category_list_api'),
    path('settings/delete-subcontract-category/<int:pk>/', views.settings.delete_subcontract_category, name='delete_subcontract_category'),
    path('settings/init-subcontract-categories/', views.settings.init_subcontract_categories, name='init_subcontract_categories'),
    
    # 分包管理
    # 分包商管理
    path('subcontractors/', subcontractor.subcontractor_list, name='subcontractor_list'),
    path('subcontractors/create/', subcontractor.subcontractor_create, name='subcontractor_create'),
    path('subcontractors/<int:pk>/edit/', subcontractor.subcontractor_edit, name='subcontractor_edit'),
    path('subcontractors/<int:pk>/delete/', subcontractor.subcontractor_delete, name='subcontractor_delete'),
    path('subcontractors/<int:pk>/', subcontractor.subcontractor_detail, name='subcontractor_detail'),
    path('subcontractors/export/', subcontractor.export_subcontractors, name='export_subcontractors'),
    
    # 分包清单管理
    path('subcontract-lists/', subcontract_list.subcontract_list_list, name='subcontract_list_list'),
    path('subcontract-lists/create/', subcontract_list.subcontract_list_create, name='subcontract_list_create'),
    path('subcontract-lists/<int:pk>/edit/', subcontract_list.subcontract_list_edit, name='subcontract_list_edit'),
    path('subcontract-lists/<int:pk>/delete/', subcontract_list.subcontract_list_delete, name='subcontract_list_delete'),
    path('subcontract-lists/<int:pk>/', subcontract_list.subcontract_list_detail, name='subcontract_list_detail'),
    path('subcontract-lists/export/', subcontract_list.export_subcontract_lists, name='export_subcontract_lists'),
    
    # 分包预算管理
    path('budgets/', budget.budget_list, name='budget_list'),
    path('budgets/create/', budget.budget_create, name='budget_create'),
    path('budgets/<int:pk>/edit/', budget.budget_edit, name='budget_edit'),
    path('budgets/<int:pk>/delete/', budget.budget_delete, name='budget_delete'),
    path('budgets/<int:pk>/', budget.budget_detail, name='budget_detail'),
    path('budgets/export/', budget.export_budgets, name='export_budgets'),
    path('budgets/<int:pk>/export/', budget.export_budget_detail, name='export_budget_detail'),
    
    # 分包合同管理
    path('contracts/', contract.contract_list, name='contract_list'),
    path('contracts/create/', contract.contract_create, name='contract_create'),
    path('contracts/<int:pk>/edit/', contract.contract_edit, name='contract_edit'),
    path('contracts/<int:pk>/delete/', contract.contract_delete, name='contract_delete'),
    path('contracts/<int:pk>/', contract.contract_detail, name='contract_detail'),
    path('contracts/export/', contract.export_contracts, name='export_contracts'),
    path('contracts/<int:pk>/export/', contract.export_contract_detail, name='export_contract_detail'),
    
    # 进度计量管理
    path('measurements/', measurement.measurement_list, name='measurement_list'),
    path('measurements/create/', measurement.measurement_create, name='measurement_create'),
    path('measurements/<int:pk>/edit/', measurement.measurement_edit, name='measurement_edit'),
    path('measurements/<int:pk>/delete/', measurement.measurement_delete, name='measurement_delete'),
    path('measurements/<int:pk>/', measurement.measurement_detail, name='measurement_detail'),
    path('measurements/export/', measurement.export_measurements, name='export_measurements'),
    path('measurements/<int:pk>/export/', measurement.export_measurement_detail, name='export_measurement_detail'),
    path('api/subcontract-lists-by-contract/', measurement.get_subcontract_lists_by_contract, name='subcontract_lists_by_contract'),
    
    # 分包结算管理
    path('settlements/', settlement.settlement_list, name='settlement_list'),
    path('settlements/create/', settlement.settlement_create, name='settlement_create'),
    path('settlements/<int:pk>/edit/', settlement.settlement_edit, name='settlement_edit'),
    path('settlements/<int:pk>/delete/', settlement.settlement_delete, name='settlement_delete'),
    path('settlements/<int:pk>/', settlement.settlement_detail, name='settlement_detail'),
    path('settlements/export/', settlement.export_settlements, name='export_settlements'),
    path('settlements/<int:pk>/export/', settlement.export_settlement_detail, name='export_settlement_detail'),
    path('api/measurements-by-contract/', settlement.get_measurements_by_contract, name='measurements_by_contract'),
    path('api/measurement-items/', settlement.get_measurement_items, name='measurement_items'),
    # Prometheus监控端点
    path('metrics/', views.utils.prometheus_metrics, name='prometheus_metrics'),
]
