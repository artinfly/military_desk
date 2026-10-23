from django.apps import AppConfig


class MilitaryConfig(AppConfig):
    """Воинский учёт: документ, ВУС, звание, военкомат, бронирование, служба, сборы…"""

    name = "apps.military"
    label = "military"
    verbose_name = "Воинский учёт"
