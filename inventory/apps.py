from django.apps import AppConfig


class InventoryConfig(AppConfig):
    name = 'inventory'

    def ready(self):
        from inventory.metrics import connect_signals
        connect_signals()
