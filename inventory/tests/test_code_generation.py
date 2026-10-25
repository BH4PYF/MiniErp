from unittest.mock import patch

from django.db import IntegrityError
from django.test import TestCase

from ..models import Project
from ..views.utils import _is_unique_violation, save_with_generated_code


class UniqueViolationDetectionTest(TestCase):
    def test_psycopg_unique_violation(self):
        class PsycopgError(Exception):
            pgcode = '23505'

        exc = IntegrityError('insert or update failed')
        exc.__cause__ = PsycopgError()
        self.assertTrue(_is_unique_violation(exc))

    def test_postgres_error_message(self):
        exc = IntegrityError(
            'duplicate key value violates unique constraint "inventory_project_code_key"'
        )
        self.assertTrue(_is_unique_violation(exc))

    def test_sqlite_error_message(self):
        exc = IntegrityError('UNIQUE constraint failed: inventory_project.code')
        self.assertTrue(_is_unique_violation(exc))

    def test_other_integrity_error_is_not_unique_violation(self):
        exc = IntegrityError('null value in column "remark" violates not-null constraint')
        self.assertFalse(_is_unique_violation(exc))


class SaveWithGeneratedCodeTest(TestCase):
    def test_retries_when_generated_code_already_exists(self):
        Project.objects.create(code='PRJ0001', name='已有项目')
        project = Project(name='新项目')

        with patch(
            'inventory.views.utils.generate_code', return_value='PRJ0001'
        ) as mocked:
            result = save_with_generated_code(project, 'PRJ', Project)

        self.assertTrue(result)
        mocked.assert_called_once()
        self.assertEqual(project.code, 'PRJ0002')
        self.assertTrue(Project.objects.filter(pk=project.pk).exists())

    def test_non_unique_integrity_error_is_reraised(self):
        class BrokenObject:
            code = ''
            pk = None
            _state = type('State', (), {'adding': True})()

            def save(self):
                raise IntegrityError('null value in column "name" violates not-null constraint')

        with patch('inventory.views.utils.generate_code', return_value='XXX0001'):
            with self.assertRaises(IntegrityError):
                save_with_generated_code(BrokenObject(), 'XXX', Project)
