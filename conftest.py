"""
pytest 全局配置：测试性能优化
"""
import pytest
from django.contrib.auth.models import User
from django.core.cache import cache

from inventory.models import Profile, Category, Material, Project, Supplier


@pytest.fixture(autouse=True)
def _enable_db_access_for_all_tests(db):
    """Django TestCase 自带数据库访问，此 fixture 仅用于 pytest 原生测试函数。"""
    pass


@pytest.fixture(autouse=True)
def _clear_login_rate_limit_cache():
    """每个测试后清理登录限流缓存，避免跨用例污染。"""
    yield
    cache.delete('LOGIN_MAX_ATTEMPTS')
    cache.delete('LOGIN_LOCKOUT_SECONDS')


@pytest.fixture(autouse=True)
def _clear_runtime_cache():
    """每个用例后清理缓存，避免登录限流和全局设置相互污染。"""
    yield
    cache.clear()


@pytest.fixture
def user_factory(db):
    """快速创建带 Profile 的用户。"""
    def _create(username='tester', role='management', password='pass12345', **kwargs):
        user = User.objects.create_user(username=username, password=password, **kwargs)
        Profile.objects.create(user=user, role=role)
        return user
    return _create


@pytest.fixture
def base_data(db):
    """创建常用基础数据（分类/材料/项目/供应商）。"""
    category = Category.objects.create(name='测试分类', code='CAT_FIX')
    material = Material.objects.create(
        name='测试材料', code='MAT_FIX', category=category, unit='个'
    )
    project = Project.objects.create(name='测试项目', code='PRJ_FIX', location='工地A')
    supplier = Supplier.objects.create(name='测试供应商', code='SUP_FIX')
    return {
        'category': category,
        'material': material,
        'project': project,
        'supplier': supplier,
    }


def pytest_collection_modifyitems(config, items):
    """自动为标记 @pytest.mark.slow 的测试添加跳过（除非显式传入 --runslow）。"""
    if config.getoption("--runslow", default=False):
        return
    skip_slow = pytest.mark.skip(reason="需要 --runslow 参数才会运行")
    for item in items:
        if "slow" in item.keywords:
            item.add_marker(skip_slow)


def pytest_addoption(parser):
    parser.addoption(
        "--runslow", action="store_true", default=False, help="运行标记为 slow 的测试"
    )
