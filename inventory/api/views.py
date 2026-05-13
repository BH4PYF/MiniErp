from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from django_filters.rest_framework import FilterSet, filters
from django.shortcuts import get_object_or_404
from django.contrib.auth.models import Group

from ..models import (
    Material, Project, Supplier, Category, InboundRecord, PurchasePlan,
    Subcontractor, SubcontractCategory, SubcontractList,
    Budget, BudgetItem, Contract, ContractItem,
    Measurement, MeasurementItem, Settlement, SettlementItem,
    Delivery, OperationLog, SystemSetting,
    MaterialPlan, MaterialPlanItem,
)
from ..services import MaterialService, ProjectService
from .serializers import (
    MaterialSerializer, ProjectSerializer, SupplierSerializer,
    CategorySerializer, InboundRecordSerializer, PurchasePlanSerializer,
    GroupPermissionSerializer,
    SubcontractorSerializer, SubcontractCategorySerializer, SubcontractListSerializer,
    BudgetSerializer, BudgetItemSerializer, ContractSerializer, ContractItemSerializer,
    MeasurementSerializer, MeasurementItemSerializer, SettlementSerializer, SettlementItemSerializer,
    DeliverySerializer, MaterialPlanSerializer, MaterialPlanItemSerializer,
    OperationLogSerializer, SystemSettingSerializer,
)


class AdminRequiredPermission(permissions.BasePermission):
    """管理员权限验证"""
    def has_permission(self, request, view):
        return request.user.is_authenticated and hasattr(request.user, 'profile') and request.user.profile.role == 'admin'


class MaterialFilter(FilterSet):
    """材料过滤"""
    category = filters.NumberFilter(field_name='category_id')
    name = filters.CharFilter(field_name='name', lookup_expr='icontains')
    code = filters.CharFilter(field_name='code', lookup_expr='icontains')
    
    class Meta:
        model = Material
        fields = ['category', 'name', 'code']


class ProjectFilter(FilterSet):
    """项目过滤"""
    status = filters.CharFilter(field_name='status')
    name = filters.CharFilter(field_name='name', lookup_expr='icontains')
    code = filters.CharFilter(field_name='code', lookup_expr='icontains')
    
    class Meta:
        model = Project
        fields = ['status', 'name', 'code']


class SupplierFilter(FilterSet):
    """供应商过滤"""
    main_type = filters.NumberFilter(field_name='main_type_id')
    credit_rating = filters.CharFilter(field_name='credit_rating')
    name = filters.CharFilter(field_name='name', lookup_expr='icontains')
    
    class Meta:
        model = Supplier
        fields = ['main_type', 'credit_rating', 'name']


class CategoryViewSet(viewsets.ModelViewSet):
    """分类视图集"""
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [AdminRequiredPermission]
    filterset_fields = ['name']
    search_fields = ['name']


class MaterialViewSet(viewsets.ModelViewSet):
    """材料视图集"""
    queryset = Material.objects.all().select_related('category')
    serializer_class = MaterialSerializer
    permission_classes = [AdminRequiredPermission]
    filterset_class = MaterialFilter
    search_fields = ['name', 'code', 'spec']
    ordering_fields = ['code', 'name', 'standard_price']
    
    def list(self, request, *args, **kwargs):
        """获取材料列表"""
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    def create(self, request, *args, **kwargs):
        """创建材料"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # 使用服务层创建材料
        material, error = MaterialService.create_material(serializer.validated_data)
        if error:
            return Response({'error': error}, status=status.HTTP_400_BAD_REQUEST)
        
        serializer = self.get_serializer(material)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    def update(self, request, *args, **kwargs):
        """更新材料"""
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        
        # 使用服务层更新材料
        material, error = MaterialService.update_material(instance.id, serializer.validated_data)
        if error:
            return Response({'error': error}, status=status.HTTP_400_BAD_REQUEST)
        
        serializer = self.get_serializer(material)
        return Response(serializer.data)
    
    def destroy(self, request, *args, **kwargs):
        """删除材料"""
        instance = self.get_object()
        
        # 使用服务层删除材料
        success, error = MaterialService.delete_material(instance.id)
        if not success:
            return Response({'error': error}, status=status.HTTP_400_BAD_REQUEST)
        
        return Response(status=status.HTTP_204_NO_CONTENT)


class ProjectViewSet(viewsets.ModelViewSet):
    """项目视图集"""
    queryset = Project.objects.all()
    serializer_class = ProjectSerializer
    permission_classes = [AdminRequiredPermission]
    filterset_class = ProjectFilter
    search_fields = ['name', 'code', 'manager']
    ordering_fields = ['code', 'name', 'start_date']
    
    def list(self, request, *args, **kwargs):
        """获取项目列表（包含统计信息）"""
        search_query = request.query_params.get('search', '')
        status_filter = request.query_params.get('status')
        
        # 使用服务层获取带统计信息的项目列表
        projects_with_stats = ProjectService.get_projects_with_statistics(
            search_query=search_query,
            status_filter=status_filter
        )
        
        page = self.paginate_queryset(projects_with_stats)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(projects_with_stats, many=True)
        return Response(serializer.data)
    
    def create(self, request, *args, **kwargs):
        """创建项目"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # 使用服务层创建项目
        project, error = ProjectService.create_project(serializer.validated_data)
        if error:
            return Response({'error': error}, status=status.HTTP_400_BAD_REQUEST)
        
        serializer = self.get_serializer(project)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    def update(self, request, *args, **kwargs):
        """更新项目"""
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        
        # 使用服务层更新项目
        project, error = ProjectService.update_project(instance.id, serializer.validated_data)
        if error:
            return Response({'error': error}, status=status.HTTP_400_BAD_REQUEST)
        
        serializer = self.get_serializer(project)
        return Response(serializer.data)
    
    def destroy(self, request, *args, **kwargs):
        """删除项目"""
        instance = self.get_object()
        
        # 使用服务层删除项目
        success, error = ProjectService.delete_project(instance.id)
        if not success:
            return Response({'error': error}, status=status.HTTP_400_BAD_REQUEST)
        
        return Response(status=status.HTTP_204_NO_CONTENT)


class SupplierViewSet(viewsets.ModelViewSet):
    """供应商视图集"""
    queryset = Supplier.objects.all().select_related('main_type')
    serializer_class = SupplierSerializer
    permission_classes = [AdminRequiredPermission]
    filterset_class = SupplierFilter
    search_fields = ['name', 'code', 'contact', 'phone']
    ordering_fields = ['code', 'name', 'credit_rating']


class InboundRecordViewSet(viewsets.ReadOnlyModelViewSet):
    """入库记录视图集（只读）"""
    queryset = InboundRecord.objects.all().select_related(
        'project', 'material', 'supplier', 'operator'
    )
    serializer_class = InboundRecordSerializer
    permission_classes = [AdminRequiredPermission]
    filterset_fields = ['project', 'material', 'supplier', 'date']
    search_fields = ['no', 'batch_no', 'inspector']
    ordering_fields = ['no', 'date', 'total_amount']


class PurchasePlanViewSet(viewsets.ModelViewSet):
    """采购计划视图集"""
    queryset = PurchasePlan.objects.all().select_related(
        'project', 'material', 'operator'
    )
    serializer_class = PurchasePlanSerializer
    permission_classes = [AdminRequiredPermission]
    filterset_fields = ['project', 'material', 'status']
    search_fields = ['no', 'remark']
    ordering_fields = ['no', 'planned_date', 'total_amount']


@api_view(['PUT'])
@permission_classes([AdminRequiredPermission])
def update_group(request, group_id):
    """更新用户组的API端点"""
    group = get_object_or_404(Group, pk=group_id)
    name = request.data.get('name')

    if not name:
        return Response({'success': False, 'message': '用户组名称不能为空'}, status=status.HTTP_400_BAD_REQUEST)

    # 检查名称是否已存在
    if Group.objects.filter(name=name).exclude(id=group_id).exists():
        return Response({'success': False, 'message': '用户组名称已存在'}, status=status.HTTP_400_BAD_REQUEST)

    # 更新用户组名称
    group.name = name
    group.save()

    return Response({'success': True, 'message': '用户组更新成功'})


# ==============================================================================
# 分包商管理
# ==============================================================================

class SubcontractorFilter(FilterSet):
    """分包商过滤"""
    credit_rating = filters.CharFilter(field_name='credit_rating')
    name = filters.CharFilter(field_name='name', lookup_expr='icontains')
    code = filters.CharFilter(field_name='code', lookup_expr='icontains')

    class Meta:
        model = Subcontractor
        fields = ['credit_rating', 'name', 'code']


class SubcontractorViewSet(viewsets.ModelViewSet):
    """分包商视图集"""
    queryset = Subcontractor.objects.all()
    serializer_class = SubcontractorSerializer
    permission_classes = [AdminRequiredPermission]
    filterset_class = SubcontractorFilter
    search_fields = ['name', 'code', 'contact']
    ordering_fields = ['code', 'name']


class SubcontractCategoryFilter(FilterSet):
    """分包清单分类过滤"""
    category_name = filters.CharFilter(field_name='category_name', lookup_expr='icontains')

    class Meta:
        model = SubcontractCategory
        fields = ['category_name']


class SubcontractCategoryViewSet(viewsets.ModelViewSet):
    """分包清单分类视图集"""
    queryset = SubcontractCategory.objects.all()
    serializer_class = SubcontractCategorySerializer
    permission_classes = [AdminRequiredPermission]
    filterset_class = SubcontractCategoryFilter
    search_fields = ['category_code', 'category_name']
    ordering_fields = ['category_code']


class SubcontractListFilter(FilterSet):
    """分包清单过滤"""
    category = filters.CharFilter(field_name='category', lookup_expr='icontains')

    class Meta:
        model = SubcontractList
        fields = ['category']


class SubcontractListViewSet(viewsets.ModelViewSet):
    """分包清单视图集"""
    queryset = SubcontractList.objects.all()
    serializer_class = SubcontractListSerializer
    permission_classes = [AdminRequiredPermission]
    filterset_class = SubcontractListFilter
    search_fields = ['code', 'name']
    ordering_fields = ['code']


# ==============================================================================
# 分包预算
# ==============================================================================

class BudgetFilter(FilterSet):
    """分包预算过滤"""
    project = filters.NumberFilter(field_name='project_id')

    class Meta:
        model = Budget
        fields = ['project']


class BudgetViewSet(viewsets.ModelViewSet):
    """分包预算视图集"""
    queryset = Budget.objects.all().select_related('project')
    serializer_class = BudgetSerializer
    permission_classes = [AdminRequiredPermission]
    filterset_class = BudgetFilter
    search_fields = ['code']
    ordering_fields = ['code', '-created_at']


class BudgetItemFilter(FilterSet):
    """预算清单过滤"""
    budget = filters.NumberFilter(field_name='budget_id')

    class Meta:
        model = BudgetItem
        fields = ['budget']


class BudgetItemViewSet(viewsets.ModelViewSet):
    """预算清单视图集"""
    queryset = BudgetItem.objects.all().select_related('budget', 'subcontract_list')
    serializer_class = BudgetItemSerializer
    permission_classes = [AdminRequiredPermission]
    filterset_class = BudgetItemFilter
    ordering_fields = ['budget', 'item_order']


# ==============================================================================
# 分包合同
# ==============================================================================

class ContractFilter(FilterSet):
    """分包合同过滤"""
    project = filters.NumberFilter(field_name='project_id')
    subcontractor = filters.NumberFilter(field_name='subcontractor_id')

    class Meta:
        model = Contract
        fields = ['project', 'subcontractor']


class ContractViewSet(viewsets.ModelViewSet):
    """分包合同视图集"""
    queryset = Contract.objects.all().select_related('project', 'subcontractor')
    serializer_class = ContractSerializer
    permission_classes = [AdminRequiredPermission]
    filterset_class = ContractFilter
    search_fields = ['code', 'name']
    ordering_fields = ['code', '-created_at']


class ContractItemFilter(FilterSet):
    """合同清单过滤"""
    contract = filters.NumberFilter(field_name='contract_id')

    class Meta:
        model = ContractItem
        fields = ['contract']


class ContractItemViewSet(viewsets.ModelViewSet):
    """合同清单视图集"""
    queryset = ContractItem.objects.all().select_related('contract', 'subcontract_list')
    serializer_class = ContractItemSerializer
    permission_classes = [AdminRequiredPermission]
    filterset_class = ContractItemFilter
    ordering_fields = ['contract', 'item_order']


# ==============================================================================
# 进度计量
# ==============================================================================

class MeasurementFilter(FilterSet):
    """进度计量过滤"""
    contract = filters.NumberFilter(field_name='contract_id')
    project = filters.NumberFilter(field_name='project_id')
    subcontractor = filters.NumberFilter(field_name='subcontractor_id')

    class Meta:
        model = Measurement
        fields = ['contract', 'project', 'subcontractor']


class MeasurementViewSet(viewsets.ModelViewSet):
    """进度计量视图集"""
    queryset = Measurement.objects.all().select_related('contract', 'project', 'subcontractor')
    serializer_class = MeasurementSerializer
    permission_classes = [AdminRequiredPermission]
    filterset_class = MeasurementFilter
    search_fields = ['code']
    ordering_fields = ['code', '-period_end', '-created_at']


class MeasurementItemFilter(FilterSet):
    """计量清单过滤"""
    measurement = filters.NumberFilter(field_name='measurement_id')

    class Meta:
        model = MeasurementItem
        fields = ['measurement']


class MeasurementItemViewSet(viewsets.ModelViewSet):
    """计量清单视图集"""
    queryset = MeasurementItem.objects.all().select_related('measurement', 'subcontract_list')
    serializer_class = MeasurementItemSerializer
    permission_classes = [AdminRequiredPermission]
    filterset_class = MeasurementItemFilter
    ordering_fields = ['measurement', 'item_order']


# ==============================================================================
# 分包结算
# ==============================================================================

class SettlementFilter(FilterSet):
    """分包结算过滤"""
    contract = filters.NumberFilter(field_name='contract_id')
    project = filters.NumberFilter(field_name='project_id')
    subcontractor = filters.NumberFilter(field_name='subcontractor_id')

    class Meta:
        model = Settlement
        fields = ['contract', 'project', 'subcontractor']


class SettlementViewSet(viewsets.ModelViewSet):
    """分包结算视图集"""
    queryset = Settlement.objects.all().select_related('contract', 'project', 'subcontractor')
    serializer_class = SettlementSerializer
    permission_classes = [AdminRequiredPermission]
    filterset_class = SettlementFilter
    search_fields = ['code']
    ordering_fields = ['code', '-period_end', '-created_at']


class SettlementItemFilter(FilterSet):
    """结算清单过滤"""
    settlement = filters.NumberFilter(field_name='settlement_id')

    class Meta:
        model = SettlementItem
        fields = ['settlement']


class SettlementItemViewSet(viewsets.ModelViewSet):
    """结算清单视图集"""
    queryset = SettlementItem.objects.all().select_related('settlement', 'subcontract_list')
    serializer_class = SettlementItemSerializer
    permission_classes = [AdminRequiredPermission]
    filterset_class = SettlementItemFilter
    ordering_fields = ['settlement', 'item_order']


# ==============================================================================
# 发货单
# ==============================================================================

class DeliveryFilter(FilterSet):
    """发货单过滤"""
    status = filters.CharFilter(field_name='status')
    supplier = filters.NumberFilter(field_name='supplier_id')

    class Meta:
        model = Delivery
        fields = ['status', 'supplier']


class DeliveryViewSet(viewsets.ModelViewSet):
    """发货单视图集"""
    queryset = Delivery.objects.all().select_related('purchase_plan', 'supplier')
    serializer_class = DeliverySerializer
    permission_classes = [AdminRequiredPermission]
    filterset_class = DeliveryFilter
    search_fields = ['no', 'plate_number', 'tracking_no']
    ordering_fields = ['no', '-create_time']


# ==============================================================================
# 材料计划
# ==============================================================================

class MaterialPlanFilter(FilterSet):
    """材料计划过滤"""
    project = filters.NumberFilter(field_name='project_id')

    class Meta:
        model = MaterialPlan
        fields = ['project']


class MaterialPlanViewSet(viewsets.ModelViewSet):
    """材料计划视图集"""
    queryset = MaterialPlan.objects.all().select_related('project', 'created_by')
    serializer_class = MaterialPlanSerializer
    permission_classes = [AdminRequiredPermission]
    filterset_class = MaterialPlanFilter
    search_fields = ['plan_number']
    ordering_fields = ['plan_number', '-plan_date', '-created_at']


class MaterialPlanItemFilter(FilterSet):
    """材料计划明细过滤"""
    material_plan = filters.NumberFilter(field_name='material_plan_id')

    class Meta:
        model = MaterialPlanItem
        fields = ['material_plan']


class MaterialPlanItemViewSet(viewsets.ModelViewSet):
    """材料计划明细视图集"""
    queryset = MaterialPlanItem.objects.all().select_related('material_plan', 'material')
    serializer_class = MaterialPlanItemSerializer
    permission_classes = [AdminRequiredPermission]
    filterset_class = MaterialPlanItemFilter
    ordering_fields = ['material_plan', 'id']


# ==============================================================================
# 操作日志与系统设置
# ==============================================================================

class OperationLogViewSet(viewsets.ReadOnlyModelViewSet):
    """操作日志视图集（只读）"""
    queryset = OperationLog.objects.all()
    serializer_class = OperationLogSerializer
    permission_classes = [AdminRequiredPermission]
    filterset_fields = ['module', 'op_type', 'operator']
    search_fields = ['details', 'related_no']
    ordering_fields = ['-time']


class SystemSettingViewSet(viewsets.ModelViewSet):
    """系统设置视图集"""
    queryset = SystemSetting.objects.all()
    serializer_class = SystemSettingSerializer
    permission_classes = [AdminRequiredPermission]
    search_fields = ['key', 'description']
    ordering_fields = ['key']
