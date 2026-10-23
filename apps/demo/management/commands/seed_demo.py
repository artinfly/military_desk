from django.core.management.base import BaseCommand

from apps.demo import generator


class Command(BaseCommand):
    help = (
        "Заполняет базу вымышленными данными: справочники и учётные карточки "
        "(только для разработки)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--count", type=int, default=300, help="Сколько карточек создать (300)"
        )
        parser.add_argument(
            "--seed", type=int, default=1, help="Число для повторяемого результата (1)"
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Удалить все учётные карточки перед генерацией",
        )

    def handle(self, *args, **options):
        created = generator.seed(
            count=options["count"], seed_value=options["seed"], clear=options["clear"]
        )
        self.stdout.write(self.style.SUCCESS("Готово. Создано:"))
        for name, number in created.items():
            self.stdout.write(f"  {name}: {number}")
