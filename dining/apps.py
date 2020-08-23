from django.apps import AppConfig


class DiningConfig(AppConfig):
    name = 'dining'

    def ready(self):
        # noinspection PyUnresolvedReferences
        import dining.receivers  # noqa F401
