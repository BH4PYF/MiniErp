from decimal import Decimal
from typing import List, Optional
from django.db.models import Sum


class MaterialPlanService:
    """材料计划服务类"""

    @staticmethod
    def get_plans_with_progress(plans_queryset):
        """
        获取带有入库进度信息的材料计划列表

        Args:
            plans_queryset: MaterialPlan 查询集或分页对象

        Returns:
            带有进度信息的 MaterialPlan 列表或分页对象
        """
        from inventory.models import InboundRecord

        # 检查是否为分页对象
        is_paged = hasattr(plans_queryset, 'object_list')
        if is_paged:
            plans = list(plans_queryset.object_list)
        else:
            plans = list(plans_queryset)

        if not plans:
            return plans_queryset

        project_ids = [plan.project_id for plan in plans]
        material_ids = []
        for plan in plans:
            for item in plan.items.all():
                material_ids.append(item.material_id)

        if not material_ids:
            for plan in plans:
                plan.total_amount = Decimal('0')
                plan.total_inbound_amount = Decimal('0')
                plan.overall_progress = 0
                for item in plan.items.all():
                    item.inbound_total = Decimal('0')
                    item.progress = 0
            return plans_queryset

        inbound_agg = InboundRecord.objects.filter(
            project_id__in=project_ids,
            material_id__in=material_ids,
            is_deleted=False
        ).values(
            'project_id',
            'material_id'
        ).annotate(
            total_quantity=Sum('quantity'),
            total_amount=Sum('total_amount')
        )

        agg_map = {}
        for row in inbound_agg:
            key = (row['project_id'], row['material_id'])
            agg_map[key] = {
                'total_quantity': row['total_quantity'] or Decimal('0'),
                'total_amount': row['total_amount'] or Decimal('0'),
            }

        for plan in plans:
            total_plan_amount = Decimal('0')
            total_inbound_amount = Decimal('0')

            for item in plan.items.all():
                key = (plan.project_id, item.material_id)
                agg = agg_map.get(key, {
                    'total_quantity': Decimal('0'),
                    'total_amount': Decimal('0'),
                })

                inbound_total = agg['total_quantity']
                item.inbound_total = inbound_total

                if item.quantity > 0:
                    item.progress = min(100, int((inbound_total / item.quantity) * 100))
                else:
                    item.progress = 0

                total_plan_amount += item.amount
                total_inbound_amount += agg['total_amount']

            plan.total_amount = total_plan_amount
            plan.total_inbound_amount = total_inbound_amount

            if total_plan_amount > 0:
                plan.overall_progress = min(100, int((total_inbound_amount / total_plan_amount) * 100))
            else:
                plan.overall_progress = 0

        return plans_queryset

    @staticmethod
    def get_plan_detail_with_progress(plan):
        """
        为单个材料计划添加入库进度信息

        Args:
            plan: MaterialPlan 对象（已 prefetch_related items 和 material）

        Returns:
            带有进度信息的 MaterialPlan 对象
        """
        from inventory.models import InboundRecord

        if not plan.items.exists():
            plan.total_amount = Decimal('0')
            plan.total_inbound_amount = Decimal('0')
            plan.overall_progress = 0
            return plan

        material_ids = [item.material_id for item in plan.items.all()]

        inbound_agg = InboundRecord.objects.filter(
            project=plan.project,
            material_id__in=material_ids,
            is_deleted=False
        ).values(
            'material_id'
        ).annotate(
            total_quantity=Sum('quantity'),
            total_amount=Sum('total_amount')
        )

        agg_map = {row['material_id']: {
            'total_quantity': row['total_quantity'] or Decimal('0'),
            'total_amount': row['total_amount'] or Decimal('0'),
        } for row in inbound_agg}

        total_plan_amount = Decimal('0')
        total_inbound_amount = Decimal('0')
        items_with_progress = []

        for item in plan.items.all():
            agg = agg_map.get(item.material_id, {
                'total_quantity': Decimal('0'),
                'total_amount': Decimal('0'),
            })

            inbound_total = agg['total_quantity']
            item.inbound_total = inbound_total

            if item.quantity > 0:
                item.progress = min(100, int((inbound_total / item.quantity) * 100))
            else:
                item.progress = 0

            total_plan_amount += item.amount
            total_inbound_amount += agg['total_amount']
            items_with_progress.append(item)

        plan.items_list = items_with_progress
        plan.total_amount = total_plan_amount
        plan.total_inbound_amount = total_inbound_amount

        if total_plan_amount > 0:
            plan.overall_progress = min(100, int((total_inbound_amount / total_plan_amount) * 100))
        else:
            plan.overall_progress = 0

        return plan