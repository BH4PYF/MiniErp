from rest_framework import serializers
from django.contrib.auth.models import Permission, Group
from ..models import (
    Material, Project, Supplier, Category, InboundRecord, PurchasePlan,
    Subcontractor, SubcontractCategory, SubcontractList,
    Budget, BudgetItem, Contract, ContractItem,
    Measurement, MeasurementItem, Settlement, SettlementItem,
    Delivery, OperationLog, SystemSetting, MaterialPlan, MaterialPlanItem,
)


class CategorySerializer(serializers.ModelSerializer):
    """材料分类序列化器"""
    class Meta:
        model = Category
        fields = ['id', 'name', 'remark']


class MaterialSerializer(serializers.ModelSerializer):
    """材料序列化器"""
    category_name = serializers.CharField(source='category.name', read_only=True)

    class Meta:
        model = Material
        fields = [
            'id', 'code', 'name', 'category', 'category_name',
            'spec', 'unit', 'standard_price', 'safety_stock', 'remark'
        ]


class ProjectSerializer(serializers.ModelSerializer):
    """项目序列化器"""
    total_inbound = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = Project
        fields = [
            'id', 'code', 'name', 'manager', 'start_date',
            'end_date', 'budget', 'status', 'remark', 'total_inbound'
        ]


class SupplierSerializer(serializers.ModelSerializer):
    """供应商序列化器"""
    main_type_name = serializers.CharField(source='main_type.name', read_only=True)

    class Meta:
        model = Supplier
        fields = [
            'id', 'code', 'name', 'contact', 'phone', 'address',
            'main_type', 'main_type_name', 'credit_rating', 'start_date', 'remark'
        ]


class InboundRecordSerializer(serializers.ModelSerializer):
    """入库记录序列化器"""
    project_name = serializers.CharField(source='project.name', read_only=True)
    material_name = serializers.CharField(source='material.name', read_only=True)
    supplier_name = serializers.CharField(source='supplier.name', read_only=True)
    operator_name = serializers.CharField(source='operator.username', read_only=True)

    class Meta:
        model = InboundRecord
        fields = [
            'id', 'no', 'project', 'project_name', 'material', 'material_name',
            'date', 'quantity', 'unit_price', 'total_amount', 'supplier', 'supplier_name',
            'batch_no', 'inspector', 'quality_status', 'spec',
            'operator', 'operator_name', 'operate_time', 'remark'
        ]


class PurchasePlanSerializer(serializers.ModelSerializer):
    """采购计划序列化器"""
    project_name = serializers.CharField(source='project.name', read_only=True)
    material_name = serializers.CharField(source='material.name', read_only=True)
    operator_name = serializers.CharField(source='operator.username', read_only=True)

    class Meta:
        model = PurchasePlan
        fields = [
            'id', 'no', 'project', 'project_name', 'material', 'material_name',
            'quantity', 'unit_price', 'total_amount', 'status', 'planned_date',
            'operator', 'operator_name', 'remark'
        ]


class PermissionSerializer(serializers.ModelSerializer):
    """权限序列化器"""
    app_label = serializers.CharField(source='content_type.app_label', read_only=True)
    model = serializers.CharField(source='content_type.model', read_only=True)

    class Meta:
        model = Permission
        fields = ['id', 'codename', 'name', 'app_label', 'model']


class GroupPermissionSerializer(serializers.ModelSerializer):
    """用户组权限序列化器"""
    permissions = PermissionSerializer(many=True, read_only=True)

    class Meta:
        model = Group
        fields = ['id', 'name', 'permissions']


# ========== 分包商管理 ==========

class SubcontractorSerializer(serializers.ModelSerializer):
    """分包商序列化器"""
    class Meta:
        model = Subcontractor
        fields = [
            'id', 'code', 'name', 'contact', 'phone',
            'main_type', 'credit_rating', 'remark', 'created_at'
        ]


class SubcontractCategorySerializer(serializers.ModelSerializer):
    """分包清单分类序列化器"""
    class Meta:
        model = SubcontractCategory
        fields = ['id', 'category_code', 'category_name', 'remark']


class SubcontractListSerializer(serializers.ModelSerializer):
    """分包清单序列化器"""
    class Meta:
        model = SubcontractList
        fields = [
            'id', 'code', 'name', 'category',
            'construction_params', 'unit', 'reference_price', 'remark'
        ]


# ========== 分包预算 ==========

class BudgetSerializer(serializers.ModelSerializer):
    """分包预算序列化器"""
    project_name = serializers.CharField(source='project.name', read_only=True)
    budget_total = serializers.SerializerMethodField()
    actual_value = serializers.SerializerMethodField()
    completion_progress = serializers.SerializerMethodField()

    class Meta:
        model = Budget
        fields = [
            'id', 'code', 'project', 'project_name', 'created_at',
            'budget_total', 'actual_value', 'completion_progress'
        ]

    def get_budget_total(self, obj):
        return obj.get_budget_total()

    def get_actual_value(self, obj):
        return obj.get_actual_value()

    def get_completion_progress(self, obj):
        return obj.get_completion_progress()


class BudgetItemSerializer(serializers.ModelSerializer):
    """预算清单序列化器"""
    subcontract_list_name = serializers.CharField(source='subcontract_list.name', read_only=True)

    class Meta:
        model = BudgetItem
        fields = [
            'id', 'budget', 'item_order',
            'subcontract_list', 'subcontract_list_name',
            'quantity', 'unit_price', 'total_amount'
        ]
        read_only_fields = ['total_amount']


# ========== 分包合同 ==========

class ContractSerializer(serializers.ModelSerializer):
    """分包合同序列化器"""
    project_name = serializers.CharField(source='project.name', read_only=True)
    subcontractor_name = serializers.CharField(source='subcontractor.name', read_only=True)
    contract_total = serializers.SerializerMethodField()
    actual_value = serializers.SerializerMethodField()
    completion_progress = serializers.SerializerMethodField()

    class Meta:
        model = Contract
        fields = [
            'id', 'code', 'name', 'project', 'project_name',
            'subcontractor', 'subcontractor_name', 'created_at',
            'contract_total', 'actual_value', 'completion_progress'
        ]

    def get_contract_total(self, obj):
        return obj.get_contract_total()

    def get_actual_value(self, obj):
        return obj.get_actual_value()

    def get_completion_progress(self, obj):
        return obj.get_completion_progress()


class ContractItemSerializer(serializers.ModelSerializer):
    """合同清单序列化器"""
    subcontract_list_name = serializers.CharField(source='subcontract_list.name', read_only=True)

    class Meta:
        model = ContractItem
        fields = [
            'id', 'contract', 'item_order',
            'subcontract_list', 'subcontract_list_name',
            'quantity', 'unit_price', 'total_amount'
        ]
        read_only_fields = ['total_amount']


# ========== 进度计量 ==========

class MeasurementSerializer(serializers.ModelSerializer):
    """进度计量序列化器"""
    contract_name = serializers.CharField(source='contract.name', read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True)
    subcontractor_name = serializers.CharField(source='subcontractor.name', read_only=True)

    class Meta:
        model = Measurement
        fields = [
            'id', 'code', 'contract', 'contract_name',
            'project', 'project_name',
            'subcontractor', 'subcontractor_name',
            'period_start', 'period_end',
            'previous_value', 'current_value', 'cumulative_value',
            'created_at'
        ]
        read_only_fields = ['current_value', 'cumulative_value']


class MeasurementItemSerializer(serializers.ModelSerializer):
    """计量清单序列化器"""
    subcontract_list_name = serializers.CharField(source='subcontract_list.name', read_only=True)

    class Meta:
        model = MeasurementItem
        fields = [
            'id', 'measurement', 'item_order',
            'subcontract_list', 'subcontract_list_name',
            'previous_quantity', 'current_quantity', 'cumulative_quantity',
            'unit_price', 'current_value'
        ]
        read_only_fields = ['cumulative_quantity', 'current_value']


# ========== 分包结算 ==========

class SettlementSerializer(serializers.ModelSerializer):
    """分包结算序列化器"""
    contract_name = serializers.CharField(source='contract.name', read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True)
    subcontractor_name = serializers.CharField(source='subcontractor.name', read_only=True)

    class Meta:
        model = Settlement
        fields = [
            'id', 'code', 'contract', 'contract_name',
            'project', 'project_name',
            'subcontractor', 'subcontractor_name',
            'period_start', 'period_end',
            'measurement_value', 'deduction_reason', 'deduction_amount',
            'final_amount', 'created_at'
        ]
        read_only_fields = ['final_amount']


class SettlementItemSerializer(serializers.ModelSerializer):
    """结算清单序列化器"""
    subcontract_list_name = serializers.CharField(source='subcontract_list.name', read_only=True)

    class Meta:
        model = SettlementItem
        fields = [
            'id', 'settlement', 'item_order',
            'subcontract_list', 'subcontract_list_name',
            'measurement_quantity', 'adjusted_quantity',
            'unit_price', 'final_value'
        ]
        read_only_fields = ['final_value']


# ========== 发货单 ==========

class DeliverySerializer(serializers.ModelSerializer):
    """发货单序列化器"""
    purchase_plan_no = serializers.CharField(source='purchase_plan.no', read_only=True)
    supplier_name = serializers.CharField(source='supplier.name', read_only=True)

    class Meta:
        model = Delivery
        fields = [
            'id', 'no', 'purchase_plan', 'purchase_plan_no',
            'actual_quantity', 'actual_unit_price', 'actual_total_amount',
            'shipping_method', 'plate_number', 'tracking_no', 'status',
            'supplier', 'supplier_name',
            'create_time', 'ship_time', 'remark'
        ]
        read_only_fields = ['actual_total_amount']


# ========== 材料计划 ==========

class MaterialPlanSerializer(serializers.ModelSerializer):
    """材料计划序列化器"""
    project_name = serializers.CharField(source='project.name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)

    class Meta:
        model = MaterialPlan
        fields = [
            'id', 'plan_number', 'project', 'project_name',
            'plan_date', 'total_amount', 'description',
            'created_by', 'created_by_name', 'created_at'
        ]
        read_only_fields = ['total_amount']


class MaterialPlanItemSerializer(serializers.ModelSerializer):
    """材料计划明细序列化器"""
    material_name = serializers.CharField(source='material.name', read_only=True)

    class Meta:
        model = MaterialPlanItem
        fields = [
            'id', 'material_plan', 'material', 'material_name',
            'quantity', 'unit', 'unit_price', 'amount'
        ]
        read_only_fields = ['amount']


# ========== 操作日志与系统设置 ==========

class OperationLogSerializer(serializers.ModelSerializer):
    """操作日志序列化器"""
    class Meta:
        model = OperationLog
        fields = [
            'id', 'time', 'operator', 'module',
            'op_type', 'details', 'related_no'
        ]


class SystemSettingSerializer(serializers.ModelSerializer):
    """系统设置序列化器"""
    class Meta:
        model = SystemSetting
        fields = ['id', 'key', 'value', 'description', 'updated_at']
        read_only_fields = ['updated_at']
