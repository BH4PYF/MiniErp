from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db.models import Sum, Q
from django.utils import timezone
from decimal import Decimal, ROUND_HALF_UP


# ========== 软删除基础设施 ==========

class SoftDeleteQuerySet(models.QuerySet):
    """支持软删除的 QuerySet"""

    def delete(self):
        """批量软删除"""
        return self.update(is_deleted=True, deleted_at=timezone.now())

    def hard_delete(self):
        """批量硬删除（真正从数据库删除）"""
        return super().delete()

    def alive(self):
        """只返回未删除的记录"""
        return self.filter(is_deleted=False)

    def dead(self):
        """只返回已删除的记录"""
        return self.filter(is_deleted=True)


class SoftDeleteManager(models.Manager):
    """默认过滤已删除记录的 Manager"""

    def get_queryset(self):
        return SoftDeleteQuerySet(self.model, using=self._db).filter(is_deleted=False)


class AllObjectsManager(models.Manager):
    """包含已删除记录的 Manager（用于备份等场景）"""

    def get_queryset(self):
        return SoftDeleteQuerySet(self.model, using=self._db)


class SoftDeleteModel(models.Model):
    """软删除抽象基类"""
    is_deleted = models.BooleanField('是否已删除', default=False, db_index=True)
    deleted_at = models.DateTimeField('删除时间', null=True, blank=True)

    objects = SoftDeleteManager()
    all_objects = AllObjectsManager()

    class Meta:
        abstract = True

    def delete(self, using=None, keep_parents=False):
        """单条记录软删除"""
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save(update_fields=['is_deleted', 'deleted_at'])

    def hard_delete(self, using=None, keep_parents=False):
        """真正从数据库删除"""
        super().delete(using=using, keep_parents=keep_parents)

    def restore(self):
        """恢复已删除的记录"""
        self.is_deleted = False
        self.deleted_at = None
        self.save(update_fields=['is_deleted', 'deleted_at'])


class Profile(models.Model):
    """用户扩展信息"""
    ROLE_CHOICES = [
        ('admin', '管理员'),
        ('management', '管理层'),
        ('material_dept', '物资部'),
        ('supplier', '供应商'),
        ('clerk', '材料员'),
        ('subcontractor', '分包商'),
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField('角色', max_length=20, choices=ROLE_CHOICES, default='management')
    phone = models.CharField('联系电话', max_length=20, blank=True)
    supplier_info = models.ForeignKey('Supplier', on_delete=models.SET_NULL, verbose_name='关联供应商档案', null=True, blank=True, related_name='user_profiles')

    class Meta:
        verbose_name = '用户资料'
        verbose_name_plural = verbose_name

    def __str__(self):
        return f"{self.user.username} ({self.get_role_display()})"

    @property
    def display_name(self):
        """显示名称，供应商优先返回供应商档案名称"""
        if self.role == 'supplier' and self.supplier_info:
            return self.supplier_info.name
        return self.user.first_name or self.user.username

    @property
    def is_admin(self):
        return self.role == 'admin'

    @property
    def is_management(self):
        return self.role == 'management'

    @property
    def is_supplier(self):
        return self.role == 'supplier'

    @property
    def is_subcontractor(self):
        return self.role == 'subcontractor'

    def sync_group_permissions(self):
        """同步用户组权限到用户"""
        from django.contrib.auth.models import Group
        if self.user.groups.exists():
            # 同步第一个组的权限到用户
            group = self.user.groups.first()
            self.user.user_permissions.clear()
            for permission in group.permissions.all():
                self.user.user_permissions.add(permission)
            # 不再强制设置角色，保留用户手动设置的角色
        else:
            # 根据角色设置权限
            self.user.user_permissions.clear()
            if self.role == 'admin':
                # 管理员拥有所有权限
                self.user.is_staff = True
                self.user.save()
            elif self.role == 'management':
                # 管理层拥有查看和管理权限
                self.user.is_staff = True
                self.user.save()
            elif self.role == 'subcontractor':
                # 分包商拥有查看进度计量和分包结算的权限
                self.user.is_staff = True
                self.user.save()
            else:
                # 供应商不拥有后台权限
                self.user.is_staff = False
                self.user.save()


class Project(SoftDeleteModel):
    """工程项目"""
    STATUS_CHOICES = [
        ('planning', '筹备中'),
        ('active', '进行中'),
        ('completed', '已完工'),
        ('paused', '暂停')
    ]
    code = models.CharField('项目编号', max_length=20, unique=True)
    name = models.CharField('项目名称', max_length=200)
    manager = models.CharField('项目负责人', max_length=50, null=True, blank=True)
    start_date = models.DateField('开工日期', null=True, blank=True)
    end_date = models.DateField('竣工日期', null=True, blank=True)
    budget = models.DecimalField('项目预算', max_digits=14, decimal_places=2, null=True, blank=True, default=0)
    status = models.CharField('项目状态', max_length=20, choices=STATUS_CHOICES, default='active', db_index=True)
    remark = models.TextField('备注', blank=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        verbose_name = '工程项目'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.code} - {self.name}"

    def get_subcontract_value(self):
        """获取分包产值"""
        from django.db.models import Sum
        # 从结算记录中统计分包产值
        total_value = self.settlements.aggregate(t=Sum('final_amount'))['t'] or Decimal('0')
        return total_value
    
    @property
    def total_settlement(self):
        """结算总额"""
        return self.get_subcontract_value()


class Subcontractor(SoftDeleteModel):
    """分包商"""
    CREDIT_CHOICES = [('excellent', '优秀'), ('good', '良好'), ('average', '一般')]
    code = models.CharField('编号', max_length=20, unique=True)
    name = models.CharField('分包商名称', max_length=200)
    contact = models.CharField('负责人', max_length=50)
    phone = models.CharField('电话', max_length=20)
    main_type = models.CharField('主营类型', max_length=100)
    credit_rating = models.CharField('信用等级', max_length=20, choices=CREDIT_CHOICES, default='good')
    remark = models.TextField('备注', blank=True, null=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    user_profiles = models.ManyToManyField('Profile', verbose_name='关联用户', related_name='subcontractors', blank=True)

    class Meta:
        verbose_name = '分包商'
        verbose_name_plural = verbose_name
        ordering = ['code']

    def __str__(self):
        return f"{self.code} - {self.name}"

    def get_total_value(self):
        """获取累计产值"""
        from django.db.models import Sum
        total_value = self.settlements.aggregate(t=Sum('final_amount'))['t'] or Decimal('0')
        return total_value


class SubcontractCategory(SoftDeleteModel):
    """分包清单分类"""
    category_code = models.CharField('分类编码', max_length=20, unique=True)
    category_name = models.CharField('分类名称', max_length=100)
    remark = models.TextField('备注', blank=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        verbose_name = '分包清单分类'
        verbose_name_plural = verbose_name
        ordering = ['category_code']

    def __str__(self):
        return f"{self.category_code} - {self.category_name}"


class SubcontractList(SoftDeleteModel):
    """分包清单"""
    code = models.CharField('清单编号', max_length=20, unique=True)
    name = models.CharField('清单名称', max_length=200)
    category = models.ForeignKey('SubcontractCategory', on_delete=models.PROTECT, verbose_name='分类', related_name='subcontract_lists', null=True, blank=True)
    construction_params = models.CharField('施工参数', max_length=200)
    unit = models.CharField('计量单位', max_length=20)
    reference_price = models.DecimalField('参考单价', max_digits=12, decimal_places=2, default=0)
    remark = models.TextField('备注', blank=True, null=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        verbose_name = '分包清单'
        verbose_name_plural = verbose_name
        ordering = ['code']

    def __str__(self):
        return f"{self.code} - {self.name}"

    def get_total_completed_quantity(self):
        """获取累计完成量"""
        from django.db.models import Sum
        total_quantity = self.measurement_items.filter(
            measurement__is_deleted=False
        ).aggregate(t=Sum('current_quantity'))['t'] or Decimal('0')
        return total_quantity

    def get_average_price(self):
        """获取平均单价"""
        from django.db.models import Sum, F
        items = self.contract_items.all()
        if not items:
            return Decimal('0')
        total_amount = items.aggregate(t=Sum(F('quantity') * F('unit_price')))['t'] or Decimal('0')
        total_quantity = items.aggregate(t=Sum('quantity'))['t'] or Decimal('0')
        if total_quantity <= 0:
            return Decimal('0')
        return total_amount / total_quantity


class Budget(SoftDeleteModel):
    """分包预算"""
    code = models.CharField('编号', max_length=20, unique=True)
    project = models.ForeignKey(Project, on_delete=models.PROTECT, verbose_name='项目名称', related_name='budgets')
    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        verbose_name = '分包预算'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.code} - {getattr(self.project, 'name', '未知项目')}"

    def get_budget_total(self):
        """获取预算总额"""
        from django.db.models import Sum
        total = self.budget_items.aggregate(t=Sum('total_amount'))['t'] or Decimal('0')
        return total

    def get_actual_value(self):
        """获取实际产值 - 所有分包商进度计量本期产值总和"""
        from django.db.models import Sum
        total = Measurement.objects.filter(
            contract__project=self.project,
            is_deleted=False,
        ).aggregate(t=Sum('current_value'))['t'] or Decimal('0')
        return total

    def get_completion_progress(self):
        """获取完成进度"""
        budget_total = self.get_budget_total()
        if budget_total <= 0:
            return 0
        actual_value = self.get_actual_value()
        return min(100, round((actual_value / budget_total) * 100, 1))


class BudgetItem(models.Model):
    """预算清单"""
    budget = models.ForeignKey(Budget, on_delete=models.CASCADE, related_name='budget_items')
    item_order = models.IntegerField('清单序号')
    subcontract_list = models.ForeignKey(SubcontractList, on_delete=models.PROTECT, verbose_name='清单名称')
    quantity = models.DecimalField('工程量', max_digits=12, decimal_places=2)
    unit_price = models.DecimalField('单价', max_digits=12, decimal_places=2)
    total_amount = models.DecimalField('合价', max_digits=14, decimal_places=2, default=0)

    class Meta:
        verbose_name = '预算清单'
        verbose_name_plural = verbose_name
        ordering = ['budget', 'item_order']

    def save(self, *args, **kwargs):
        self.total_amount = self.quantity * self.unit_price
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.budget.code} - {self.subcontract_list.name}"


class Contract(SoftDeleteModel):
    """分包合同"""
    code = models.CharField('合同编号', max_length=20, unique=True)
    name = models.CharField('合同名称', max_length=200)
    project = models.ForeignKey(Project, on_delete=models.PROTECT, verbose_name='项目名称', related_name='contracts')
    subcontractor = models.ForeignKey(Subcontractor, on_delete=models.PROTECT, verbose_name='分包商', related_name='contracts')
    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        verbose_name = '分包合同'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['project', 'subcontractor']),
        ]

    def __str__(self):
        return f"{self.code} - {self.name}"

    def get_contract_total(self):
        """获取合同总额"""
        from django.db.models import Sum
        total = self.contract_items.aggregate(t=Sum('total_amount'))['t'] or Decimal('0')
        return total

    def get_actual_value(self):
        """获取实际产值 - 汇总所有进度计量的本期产值"""
        from django.db.models import Sum
        return self.measurements.aggregate(
            total=Sum('current_value')
        )['total'] or Decimal('0')
    
    def get_completion_progress(self):
        """获取完成进度"""
        contract_total = self.get_contract_total()
        if contract_total <= 0:
            return 0
        actual_value = self.get_actual_value()
        return min(100, round((actual_value / contract_total) * 100, 1))


class ContractItem(models.Model):
    """合同清单"""
    contract = models.ForeignKey(Contract, on_delete=models.CASCADE, related_name='contract_items')
    item_order = models.IntegerField('清单序号')
    subcontract_list = models.ForeignKey(SubcontractList, on_delete=models.PROTECT, verbose_name='清单名称', related_name='contract_items')
    quantity = models.DecimalField('工程量', max_digits=12, decimal_places=2)
    unit_price = models.DecimalField('单价', max_digits=12, decimal_places=2)
    total_amount = models.DecimalField('合价', max_digits=14, decimal_places=2, default=0)

    class Meta:
        verbose_name = '合同清单'
        verbose_name_plural = verbose_name
        ordering = ['contract', 'item_order']

    def save(self, *args, **kwargs):
        self.total_amount = self.quantity * self.unit_price
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.contract.code} - {self.subcontract_list.name}"


class Measurement(SoftDeleteModel):
    """进度计量"""
    code = models.CharField('计量编号', max_length=20, unique=True)
    contract = models.ForeignKey(Contract, on_delete=models.PROTECT, verbose_name='合同名称', related_name='measurements')
    project = models.ForeignKey(Project, on_delete=models.PROTECT, verbose_name='项目名称', related_name='measurements')
    subcontractor = models.ForeignKey(Subcontractor, on_delete=models.PROTECT, verbose_name='分包商', related_name='measurements')
    period_start = models.DateField('计量周期开始')
    period_end = models.DateField('计量周期结束')
    previous_value = models.DecimalField('之前产值', max_digits=14, decimal_places=2, default=0)
    current_value = models.DecimalField('本期产值', max_digits=14, decimal_places=2, default=0)
    cumulative_value = models.DecimalField('累计产值', max_digits=14, decimal_places=2, default=0)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        verbose_name = '进度计量'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['contract', 'project']),
            models.Index(fields=['period_end']),
        ]

    def __str__(self):
        return f"{self.code} - {self.contract.name}"

    def save(self, *args, **kwargs):
        # 只有当有主键时才计算产值（避免在首次保存时访问未创建的关系）
        if self.pk:
            # 计算本期产值和累计产值
            from django.db.models import Sum
            current_value = self.measurement_items.aggregate(t=Sum('current_value'))['t'] or Decimal('0')
            self.current_value = current_value
            self.cumulative_value = self.previous_value + current_value
        super().save(*args, **kwargs)


class MeasurementItem(models.Model):
    """计量清单"""
    measurement = models.ForeignKey(Measurement, on_delete=models.CASCADE, related_name='measurement_items')
    item_order = models.IntegerField('清单序号')
    subcontract_list = models.ForeignKey(SubcontractList, on_delete=models.PROTECT, verbose_name='清单名称', related_name='measurement_items')
    previous_quantity = models.DecimalField('之前工程量', max_digits=12, decimal_places=2, default=0)
    current_quantity = models.DecimalField('本期工程量', max_digits=12, decimal_places=2)
    cumulative_quantity = models.DecimalField('累计工程量', max_digits=12, decimal_places=2, default=0)
    unit_price = models.DecimalField('单价', max_digits=12, decimal_places=2)
    current_value = models.DecimalField('本期产值', max_digits=14, decimal_places=2, default=0)

    class Meta:
        verbose_name = '计量清单'
        verbose_name_plural = verbose_name
        ordering = ['measurement', 'item_order']

    def save(self, *args, **kwargs):
        self.cumulative_quantity = self.previous_quantity + self.current_quantity
        self.current_value = self.current_quantity * self.unit_price
        super().save(*args, **kwargs)
        # 用 update() 避免触发 Measurement.save() 的完整逻辑
        from django.db.models import Sum
        agg = MeasurementItem.objects.filter(measurement_id=self.measurement_id).aggregate(
            t=Sum('current_value')
        )
        current_value = agg['t'] or Decimal('0')
        Measurement.objects.filter(pk=self.measurement_id).update(
            current_value=current_value,
            cumulative_value=self.measurement.previous_value + current_value
        )

    def __str__(self):
        return f"{self.measurement.code} - {self.subcontract_list.name}"


class Settlement(SoftDeleteModel):
    """分包结算"""
    code = models.CharField('结算编号', max_length=20, unique=True)
    contract = models.ForeignKey(Contract, on_delete=models.PROTECT, verbose_name='合同名称', related_name='settlements')
    project = models.ForeignKey(Project, on_delete=models.PROTECT, verbose_name='项目名称', related_name='settlements')
    subcontractor = models.ForeignKey(Subcontractor, on_delete=models.PROTECT, verbose_name='分包商', related_name='settlements')
    period_start = models.DateField('结算周期开始')
    period_end = models.DateField('结算周期结束')
    measurement_value = models.DecimalField('计量产值', max_digits=14, decimal_places=2, default=0)
    deduction_reason = models.CharField('扣款原因', max_length=200)
    deduction_amount = models.DecimalField('扣款金额', max_digits=14, decimal_places=2)
    final_amount = models.DecimalField('最终结算额', max_digits=14, decimal_places=2, default=0)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        verbose_name = '分包结算'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['contract', 'project']),
            models.Index(fields=['period_end']),
        ]

    def __str__(self):
        return f"{self.code} - {self.contract.name}"

    def save(self, *args, **kwargs):
        if self.pk:
            from django.db.models import Sum
            items_total = self.settlement_items.aggregate(
                total=Sum('final_value')
            )['total'] or Decimal('0')
            self.final_amount = items_total - self.deduction_amount
        super().save(*args, **kwargs)


class SettlementItem(models.Model):
    """结算清单"""
    settlement = models.ForeignKey(Settlement, on_delete=models.CASCADE, related_name='settlement_items')
    item_order = models.IntegerField('清单序号')
    subcontract_list = models.ForeignKey(SubcontractList, on_delete=models.PROTECT, verbose_name='清单名称')
    measurement_quantity = models.DecimalField('计量汇总工程量', max_digits=12, decimal_places=2, default=0)
    adjusted_quantity = models.DecimalField('修正后工程量', max_digits=12, decimal_places=2)
    unit_price = models.DecimalField('单价', max_digits=12, decimal_places=2)
    final_value = models.DecimalField('最终产值', max_digits=14, decimal_places=2, default=0)

    class Meta:
        verbose_name = '结算清单'
        verbose_name_plural = verbose_name
        ordering = ['settlement', 'item_order']

    def save(self, *args, **kwargs):
        self.final_value = self.adjusted_quantity * self.unit_price
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.settlement.code} - {self.subcontract_list.name}"


class Category(SoftDeleteModel):
    """材料分类"""
    code = models.CharField('分类编号', max_length=20, unique=True)
    name = models.CharField('分类名称', max_length=100)
    remark = models.TextField('备注', blank=True)

    class Meta:
        verbose_name = '材料分类'
        verbose_name_plural = verbose_name

    def __str__(self):
        return self.name


class Material(SoftDeleteModel):
    """材料档案"""
    UNIT_CHOICES = [
        ('吨', '吨'), ('千克', '千克'), ('立方米', '立方米'), ('平方米', '平方米'),
        ('米', '米'), ('根', '根'), ('个', '个'), ('套', '套'), ('箱', '箱'),
        ('袋', '袋'), ('卷', '卷'), ('块', '块'), ('张', '张'), ('件', '件'),
    ]
    code = models.CharField('材料编号', max_length=20, unique=True)
    name = models.CharField('材料名称', max_length=200)
    category = models.ForeignKey(Category, on_delete=models.PROTECT, verbose_name='材料分类', related_name='materials')
    spec = models.CharField('规格型号', max_length=200, blank=True)
    unit = models.CharField('计量单位', max_length=20, choices=UNIT_CHOICES)
    standard_price = models.DecimalField('标准单价', max_digits=12, decimal_places=2, default=0)
    safety_stock = models.DecimalField('安全库存量', max_digits=12, decimal_places=2, default=0)
    remark = models.TextField('备注', blank=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        verbose_name = '材料档案'
        verbose_name_plural = verbose_name
        ordering = ['code']

    def __str__(self):
        if self.spec:
            return f"{self.code} - {self.name} ({self.spec})"
        return f"{self.code} - {self.name}"

    def get_total_inbound(self, project_id=None, start_date=None, end_date=None):
        """获取累计入库量"""
        in_filter = Q(material=self)
        if project_id:
            in_filter &= Q(project_id=project_id)
        if start_date and end_date:
            in_filter &= Q(date__range=[start_date, end_date])
        total_in = InboundRecord.objects.filter(in_filter).aggregate(t=Sum('quantity'))['t'] or Decimal('0')
        return total_in

    def get_weighted_avg_cost(self, start_date=None, end_date=None):
        """获取入库加权平均成本"""
        if start_date and end_date:
            in_filter = Q(material=self, date__range=[start_date, end_date])
        else:
            in_filter = Q(material=self)

        agg = InboundRecord.objects.filter(in_filter).aggregate(
            total_amount=Sum('total_amount'),
            total_qty=Sum('quantity'),
        )
        total_in_qty = agg['total_qty'] or Decimal('0')
        total_in_amount = agg['total_amount'] or Decimal('0')

        if total_in_qty <= 0:
            last_in = InboundRecord.objects.filter(material=self).order_by('-date').first()
            return last_in.unit_price if last_in else Decimal('0')
        return total_in_amount / total_in_qty


class Supplier(SoftDeleteModel):
    """供应商"""
    CREDIT_CHOICES = [('excellent', '优秀'), ('good', '良好'), ('average', '一般')]
    code = models.CharField('供应商编号', max_length=20, unique=True)
    name = models.CharField('供应商名称', max_length=200)
    contact = models.CharField('联系人', max_length=50, blank=True)
    phone = models.CharField('联系电话', max_length=20, blank=True)
    address = models.CharField('地址', max_length=300, blank=True)
    main_type = models.ForeignKey(Category, on_delete=models.SET_NULL, verbose_name='主营材料类型', related_name='suppliers', null=True, blank=True)
    credit_rating = models.CharField('信用等级', max_length=20, choices=CREDIT_CHOICES, default='good')
    start_date = models.DateField('合作开始日期', null=True, blank=True)
    remark = models.TextField('备注', blank=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        verbose_name = '供应商'
        verbose_name_plural = verbose_name
        ordering = ['code']

    def __str__(self):
        return f"{self.code} - {self.name}"

    def get_total_purchase(self):
        return self.inbound_records.aggregate(t=Sum('total_amount'))['t'] or Decimal('0')


class InboundRecord(SoftDeleteModel):
    """入库记录"""
    QUALITY_CHOICES = [('qualified', '合格'), ('unqualified', '不合格')]
    no = models.CharField('入库单号', max_length=30, unique=True)
    project = models.ForeignKey(Project, on_delete=models.PROTECT, verbose_name='所属项目', related_name='inbound_records')
    material = models.ForeignKey(Material, on_delete=models.PROTECT, verbose_name='材料', related_name='inbound_records')
    date = models.DateField('入库日期', db_index=True)
    quantity = models.DecimalField('入库数量', max_digits=12, decimal_places=2)
    unit_price = models.DecimalField('单价', max_digits=12, decimal_places=2)
    total_amount = models.DecimalField('总金额', max_digits=14, decimal_places=2)
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, verbose_name='供应商', related_name='inbound_records', db_index=True)
    batch_no = models.CharField('采购批次号', max_length=50, blank=True)
    inspector = models.CharField('验收人', max_length=50, blank=True)
    quality_status = models.CharField('质量状态', max_length=20, choices=QUALITY_CHOICES, default='qualified')
    # 快照字段：入库时记录规格，防止后续修改导致历史数据不一致
    spec = models.CharField('规格型号（快照）', max_length=100)
    location = models.CharField('存放位置', max_length=100, blank=True)
    operator = models.ForeignKey(User, on_delete=models.PROTECT, verbose_name='操作员', related_name='inbound_ops')
    operate_time = models.DateTimeField('操作时间', auto_now_add=True)
    remark = models.TextField('备注', blank=True)

    class Meta:
        verbose_name = '入库记录'
        verbose_name_plural = verbose_name
        ordering = ['-date', '-operate_time']

    def __str__(self):
        return self.no

    def clean(self):
        if self.quantity is not None and self.quantity <= 0:
            raise ValidationError({'quantity': '入库数量必须为正数'})
        if self.unit_price is not None and self.unit_price < 0:
            raise ValidationError({'unit_price': '单价不能为负数'})

    def save(self, *args, **kwargs):
        if self.quantity is not None and self.unit_price is not None:
            self.total_amount = (self.quantity * self.unit_price).quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP
            )
        # 仅在完整保存时执行验证，部分更新（如软删除）跳过
        if not kwargs.get('update_fields'):
            self.full_clean()
        super().save(*args, **kwargs)


class PurchasePlan(SoftDeleteModel):
    """采购计划"""
    STATUS_PENDING = 'pending'
    STATUS_PURCHASING = 'purchasing'
    STATUS_SHIPPED = 'shipped'
    STATUS_RECEIVED = 'received'

    STATUS_CHOICES = [
        (STATUS_PENDING, '审批中'),
        (STATUS_PURCHASING, '采购中'),
        (STATUS_SHIPPED, '已发货'),
        (STATUS_RECEIVED, '已入库'),
    ]
    no = models.CharField('计划编号', max_length=30, unique=True)
    project = models.ForeignKey(Project, on_delete=models.PROTECT, verbose_name='所属项目', related_name='purchase_plans')
    material = models.ForeignKey(Material, on_delete=models.PROTECT, verbose_name='材料', related_name='purchase_plans')
    material_plan = models.ForeignKey('MaterialPlan', on_delete=models.SET_NULL, verbose_name='关联材料计划', related_name='purchase_plans', null=True, blank=True)
    plan_quantity = models.DecimalField('计划数量', max_digits=12, decimal_places=2, default=Decimal('0'))
    inbound_quantity = models.DecimalField('已入库数量', max_digits=12, decimal_places=2, default=Decimal('0'))
    quantity = models.DecimalField('采购数量', max_digits=12, decimal_places=2)
    spec = models.CharField('规格型号', max_length=200, default='')
    unit_price = models.DecimalField('预计单价', max_digits=12, decimal_places=2, default=Decimal('0'))
    total_amount = models.DecimalField('预计金额', max_digits=14, decimal_places=2, default=Decimal('0'))
    supplier = models.ForeignKey('Supplier', on_delete=models.SET_NULL, verbose_name='供应商', related_name='purchase_plans', null=True, blank=True)
    status = models.CharField('状态', max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING, db_index=True)
    planned_date = models.DateField('计划采购日期', null=True, blank=True)
    remark = models.TextField('备注', blank=True)
    operator = models.ForeignKey(User, on_delete=models.PROTECT, verbose_name='操作员', related_name='purchase_plans')
    create_time = models.DateTimeField('创建时间', auto_now_add=True)
    update_time = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = '采购计划'
        verbose_name_plural = verbose_name
        ordering = ['-create_time']

    def __str__(self):
        try:
            material_name = self.material.name
        except (AttributeError, TypeError):
            material_name = '未知材料'
        return f"{self.no} - {material_name}"

    def save(self, *args, **kwargs):
        # 使用预计单价计算预计金额
        if self.quantity is not None and self.unit_price is not None:
            self.total_amount = self.quantity * self.unit_price
        super().save(*args, **kwargs)


class Delivery(SoftDeleteModel):
    """发货单"""
    SHIPPING_CHOICES = [
        ('special', '专车'),
        ('logistics', '物流'),
    ]
    STATUS_PENDING = 'pending'
    STATUS_SHIPPED = 'shipped'
    STATUS_RECEIVED = 'received'

    STATUS_CHOICES = [
        (STATUS_PENDING, '待发货'),
        (STATUS_SHIPPED, '已发货'),
        (STATUS_RECEIVED, '已收货'),
    ]
    no = models.CharField('发货单号', max_length=30, unique=True)
    purchase_plan = models.ForeignKey(PurchasePlan, on_delete=models.PROTECT, verbose_name='采购计划', related_name='deliveries')
    actual_quantity = models.DecimalField('实际发货数量', max_digits=12, decimal_places=2)
    actual_unit_price = models.DecimalField('实际单价', max_digits=12, decimal_places=2)
    actual_total_amount = models.DecimalField('实际金额', max_digits=14, decimal_places=2, default=Decimal('0'))
    shipping_method = models.CharField('送货方式', max_length=20, choices=SHIPPING_CHOICES, default='special')
    plate_number = models.CharField('车牌号', max_length=20, blank=True)
    tracking_no = models.CharField('运单号', max_length=50, blank=True)
    status = models.CharField('状态', max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING, db_index=True)
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, verbose_name='供应商', related_name='deliveries')
    create_time = models.DateTimeField('创建时间', auto_now_add=True)
    ship_time = models.DateTimeField('发货时间', null=True, blank=True)
    remark = models.TextField('备注', blank=True)

    class Meta:
        verbose_name = '发货单'
        verbose_name_plural = verbose_name
        ordering = ['-create_time']
        indexes = [
            models.Index(fields=['supplier', 'status']),
        ]

    def __str__(self):
        try:
            material_name = self.purchase_plan.material.name
        except (AttributeError, TypeError):
            material_name = '未知材料'
        return f"{self.no} - {material_name}"

    def save(self, *args, **kwargs):
        self.actual_total_amount = self.actual_quantity * self.actual_unit_price
        super().save(*args, **kwargs)


class OperationLog(models.Model):
    """操作日志"""
    TYPE_CHOICES = [('create', '新增'), ('update', '修改'), ('delete', '删除'), ('export', '导出'), ('login', '登录'), ('other', '其他')]
    time = models.DateTimeField('操作时间', auto_now_add=True, db_index=True)
    operator = models.CharField('操作员', max_length=50)
    module = models.CharField('操作模块', max_length=50)
    op_type = models.CharField('操作类型', max_length=20, choices=TYPE_CHOICES)
    details = models.TextField('操作详情')
    related_no = models.CharField('关联单号', max_length=50, blank=True)

    class Meta:
        verbose_name = '操作日志'
        verbose_name_plural = verbose_name
        ordering = ['-time']
        indexes = [
            models.Index(fields=['operator']),
        ]

    def __str__(self):
        return f"{self.time} - {self.operator} - {self.details}"


class SystemSetting(models.Model):
    """系统设置"""
    key = models.CharField('配置键', max_length=50, unique=True)
    value = models.CharField('配置值', max_length=200, blank=True)
    description = models.CharField('配置说明', max_length=200, blank=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = '系统设置'
        verbose_name_plural = verbose_name

    def __str__(self):
        return f"{self.key}: {self.value}"

    @classmethod
    def get_setting(cls, key, default=''):
        """获取系统配置值"""
        setting = cls.objects.filter(key=key).first()
        return setting.value if setting else default

    @classmethod
    def set_setting(cls, key, value, description=''):
        """设置系统配置值"""
        setting = cls.objects.filter(key=key).first()
        if setting:
            setting.value = value
            if description:
                setting.description = description
            setting.save()
        else:
            cls.objects.create(key=key, value=value, description=description)


# ========== 材料计划模型 ==========

class MaterialPlan(SoftDeleteModel):
    """材料计划模型"""
    project = models.ForeignKey('Project', verbose_name='项目', on_delete=models.CASCADE, related_name='material_plans')
    plan_number = models.CharField('计划编号', max_length=100, unique=True)
    plan_date = models.DateField('计划日期', default=timezone.now)
    total_amount = models.DecimalField('计划总金额', max_digits=12, decimal_places=2, default=0)
    description = models.TextField('计划描述', blank=True)
    created_by = models.ForeignKey(User, verbose_name='创建人', on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)
    
    def __str__(self):
        return f"{self.plan_number} - {getattr(self.project, 'name', '未知项目')}"
    
    class Meta:
        verbose_name = '材料计划'
        verbose_name_plural = '材料计划管理'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['project', 'plan_date']),
        ]

class MaterialPlanItem(models.Model):
    """材料计划明细模型"""
    material_plan = models.ForeignKey(MaterialPlan, verbose_name='材料计划', on_delete=models.CASCADE, related_name='items')
    material = models.ForeignKey('Material', verbose_name='材料', on_delete=models.CASCADE)
    quantity = models.DecimalField('计划数量', max_digits=10, decimal_places=2)
    unit = models.CharField('单位', max_length=20)
    unit_price = models.DecimalField('单价', max_digits=10, decimal_places=2)
    amount = models.DecimalField('金额', max_digits=12, decimal_places=2, default=0)
    
    def save(self, *args, **kwargs):
        self.amount = self.quantity * self.unit_price
        super().save(*args, **kwargs)
        # 用数据库聚合更新总金额，避免 Python 循环
        from django.db.models import Sum
        agg = MaterialPlanItem.objects.filter(material_plan_id=self.material_plan_id).aggregate(
            t=Sum('amount')
        )
        MaterialPlan.objects.filter(pk=self.material_plan_id).update(
            total_amount=agg['t'] or Decimal('0')
        )
    
    def __str__(self):
        return f"{getattr(self.material, 'name', '未知材料')} - {self.quantity} {self.unit}"
    
    class Meta:
        verbose_name = '材料计划明细'
        verbose_name_plural = '材料计划明细管理'
        indexes = [
            models.Index(fields=['material']),
        ]