# Views package - 按功能模块拆分
from .auth import login_view, logout_view
from .dashboard import dashboard
from .project import project_list, project_save, project_delete, project_detail_api, check_project_name
from .material import (
    category_list_api, material_list, material_save,
    material_delete, material_detail_api, check_material_duplicate,
)
from .supplier import (
    supplier_list, supplier_save, supplier_delete, supplier_detail_api,
    check_supplier_duplicate,
)
from .inbound import inbound_list, inbound_save, inbound_delete, inbound_detail_api
from .purchase_plan import (
    purchase_plan_list,
    purchase_plan_create,
    purchase_plan_save,
    purchase_plan_delete,
    purchase_plan_approve,
    export_purchase_plans,
    purchase_plan_detail_api,
    get_inbound_quantity_api,
)
from .delivery import (
    delivery_list, export_deliveries, delivery_create, delivery_detail,
    delivery_confirm_ship, delivery_detail_api, delivery_edit, delivery_delete,
    quick_receive, get_delivery_by_no, quick_receive_confirm,
)
from .report import (
    report_page, report_project_cost, report_supplier_cost,
    report_monthly, chart_page, chart_data_api, get_years_list,
)
from .export import export_excel, import_excel, download_import_template
from .settings import (
    settings_page, settings_users_api, settings_logs_api,
    add_custom_category,
    delete_category, save_system_settings, save_login_security_settings,
    backup_data, restore_data, clear_all_data, init_categories,
    save_dingtalk_config, dingtalk_test,
)
from .users import (
    user_list, user_save, user_delete, user_detail_api,
    user_groups,
    profile_page, change_password, update_profile,
    log_list,
)
from .performance import performance_dashboard, api_performance_stats
