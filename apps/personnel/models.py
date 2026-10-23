"""Учётная карточка работника (Person) и её разделы.

Воинский учёт (документ, ВУС, звание, военкомат, бронирование…) — в приложении
military: оно ссылается на карточку, а не наоборот.
Справочные значения — ссылки на apps.references; удалять используемую запись
справочника нельзя (PROTECT): её помечают недействующей.
"""

from django.conf import settings
from django.db import models

from apps.core.models import PeriodModel, TimeStampedModel
from apps.references import models as ref


class Person(TimeStampedModel):
    """Учётная карточка работника."""

    class Gender(models.TextChoices):
        MALE = "М", "Мужской"
        FEMALE = "Ж", "Женский"

    tab_number = models.CharField("Табельный номер", max_length=20, unique=True)
    last_name = models.CharField("Фамилия", max_length=100, db_index=True)
    first_name = models.CharField("Имя", max_length=100)
    patronymic = models.CharField("Отчество", max_length=100, blank=True)
    gender = models.CharField("Пол", max_length=1, choices=Gender.choices)
    birth_date = models.DateField("Дата рождения")
    birth_place = models.CharField("Место рождения", max_length=500, blank=True)
    previous_last_name = models.CharField("Прежняя фамилия", max_length=100, blank=True)
    last_name_changed_on = models.DateField("Дата смены фамилии", null=True, blank=True)

    citizenship = models.CharField("Гражданство", max_length=100, blank=True)
    nationality = models.CharField("Национальность", max_length=100, blank=True)
    family_status = models.ForeignKey(
        ref.FamilyStatus,
        verbose_name="Семейное положение",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )
    inn = models.CharField("ИНН", max_length=12, blank=True)
    snils = models.CharField("СНИЛС", max_length=14, blank=True)
    phone = models.CharField("Телефон", max_length=50, blank=True)
    email = models.EmailField("Эл. почта", blank=True)
    card_number = models.CharField("Номер учётной карточки", max_length=20, blank=True)

    # Работа на предприятии (текущее состояние; история — в назначениях)
    employment_date = models.DateField("Дата приёма", null=True, blank=True)
    dismissal_date = models.DateField("Дата увольнения", null=True, blank=True)
    department = models.ForeignKey(
        ref.Department,
        verbose_name="Цех",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )
    position = models.CharField("Должность", max_length=255, blank=True)
    hire_type = models.CharField("Вид приёма", max_length=255, blank=True)
    hire_source = models.CharField("Откуда принят", max_length=255, blank=True)
    is_svo = models.BooleanField("Участник СВО", default=False)

    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Кто изменил",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        editable=False,
        related_name="+",
    )

    class Meta:
        verbose_name = "учётная карточка"
        verbose_name_plural = "учётные карточки"
        ordering = ["last_name", "first_name", "patronymic"]

    def __str__(self):
        return f"{self.full_name} ({self.tab_number})"

    @property
    def full_name(self):
        return " ".join(
            p for p in (self.last_name, self.first_name, self.patronymic) if p
        )

    @property
    def is_working(self):
        """Работает (не уволен)."""
        return self.dismissal_date is None


class PersonSection(models.Model):
    """Общее для разделов карточки: ссылка на карточку."""

    person = models.ForeignKey(
        Person, verbose_name="Учётная карточка", on_delete=models.CASCADE
    )

    class Meta:
        abstract = True


class IdentityDocument(PersonSection):
    """Документ, удостоверяющий личность (паспорт, загранпаспорт…)."""

    document_type = models.ForeignKey(
        ref.RegistrationDocument, verbose_name="Вид документа", on_delete=models.PROTECT
    )
    series = models.CharField("Серия", max_length=20, blank=True)
    number = models.CharField("Номер", max_length=30)
    issue_date = models.DateField("Дата выдачи", null=True, blank=True)
    issued_by = models.CharField("Кем выдан", max_length=500, blank=True)
    subdivision_code = models.CharField("Код подразделения", max_length=10, blank=True)
    valid_until = models.DateField("Действует до", null=True, blank=True)
    note = models.CharField("Примечание", max_length=500, blank=True)

    class Meta:
        verbose_name = "документ"
        verbose_name_plural = "документы"
        ordering = ["-issue_date"]
        default_related_name = "documents"

    def __str__(self):
        return f"{self.document_type} {self.series} {self.number}".strip()


class Address(PersonSection, PeriodModel):
    """Адрес (регистрации, проживания…)."""

    address_type = models.ForeignKey(
        ref.AddressType,
        verbose_name="Тип адреса",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )
    country = models.CharField("Страна", max_length=100, blank=True)
    postal_code = models.CharField("Индекс", max_length=10, blank=True)
    region = models.ForeignKey(
        ref.Region,
        verbose_name="Регион",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )
    district = models.CharField("Район", max_length=255, blank=True)
    city = models.ForeignKey(
        ref.City,
        verbose_name="Населённый пункт",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )
    street = models.ForeignKey(
        ref.Street,
        verbose_name="Улица",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )
    house = models.CharField("Дом", max_length=20, blank=True)
    apartment = models.CharField("Квартира", max_length=10, blank=True)
    registration_date = models.DateField("Дата регистрации", null=True, blank=True)
    phone = models.CharField("Телефон", max_length=50, blank=True)
    # Коды адреса из кадровой системы
    kladr_code = models.CharField("Код КЛАДР", max_length=30, blank=True)
    okato = models.CharField("ОКАТО", max_length=20, blank=True)
    oktmo = models.CharField("ОКТМО", max_length=20, blank=True)
    ifns = models.CharField("ИФНС", max_length=10, blank=True)
    note = models.CharField("Примечание", max_length=500, blank=True)

    class Meta:
        verbose_name = "адрес"
        verbose_name_plural = "адреса"
        ordering = ["-date_from"]
        default_related_name = "addresses"

    def __str__(self):
        parts = [self.postal_code, self.region, self.district, self.city, self.street]
        text = ", ".join(str(p) for p in parts if p)
        if self.house:
            text += f", д. {self.house}"
        if self.apartment:
            text += f", кв. {self.apartment}"
        return text


class Relative(PersonSection):
    """Родственник."""

    relation = models.ForeignKey(
        ref.RelationType, verbose_name="Степень родства", on_delete=models.PROTECT
    )
    last_name = models.CharField("Фамилия", max_length=100)
    first_name = models.CharField("Имя", max_length=100, blank=True)
    patronymic = models.CharField("Отчество", max_length=100, blank=True)
    birth_date = models.DateField("Дата рождения", null=True, blank=True)
    death_date = models.DateField("Дата смерти", null=True, blank=True)
    is_dependent = models.BooleanField("На иждивении", default=False)

    class Meta:
        verbose_name = "родственник"
        verbose_name_plural = "родственники"
        ordering = ["relation__sort_order", "birth_date"]
        default_related_name = "relatives"

    def __str__(self):
        name = " ".join(
            p for p in (self.last_name, self.first_name, self.patronymic) if p
        )
        return f"{self.relation}: {name}"


class Education(PersonSection):
    """Образование."""

    education_type = models.CharField("Вид образования", max_length=255, blank=True)
    institution = models.CharField("Учебное заведение", max_length=500, blank=True)
    study_form = models.CharField("Форма обучения", max_length=100, blank=True)
    speciality = models.CharField("Специальность", max_length=500, blank=True)
    qualification = models.CharField("Квалификация", max_length=500, blank=True)
    program = models.CharField("Образовательная программа", max_length=500, blank=True)
    training_direction = models.CharField(
        "Направление подготовки", max_length=500, blank=True
    )
    admission_date = models.DateField("Дата поступления", null=True, blank=True)
    graduation_date = models.DateField("Дата окончания", null=True, blank=True)
    document = models.CharField("Документ", max_length=255, blank=True)
    document_series = models.CharField("Серия документа", max_length=20, blank=True)
    document_number = models.CharField("Номер документа", max_length=30, blank=True)
    document_date = models.DateField("Дата выдачи документа", null=True, blank=True)
    is_main = models.BooleanField("Основное", default=False)
    note = models.CharField("Примечание", max_length=500, blank=True)

    class Meta:
        verbose_name = "образование"
        verbose_name_plural = "образование"
        ordering = ["-graduation_date"]
        default_related_name = "education"

    def __str__(self):
        return " — ".join(p for p in (self.education_type, self.institution) if p)


class Assignment(PersonSection, PeriodModel):
    """Назначение, перевод (кадровое движение)."""

    department = models.ForeignKey(
        ref.Department,
        verbose_name="Цех",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )
    position = models.CharField("Должность", max_length=255, blank=True)
    grade = models.CharField("Разряд", max_length=20, blank=True)
    employee_category = models.CharField(
        "Категория работника", max_length=100, blank=True
    )
    status = models.ForeignKey(
        ref.WorkStatus,
        verbose_name="Статус",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )
    order_kind = models.CharField("Вид приказа", max_length=255, blank=True)
    order_number = models.CharField("Номер приказа", max_length=50, blank=True)
    order_date = models.DateField("Дата приказа", null=True, blank=True)

    class Meta:
        verbose_name = "назначение"
        verbose_name_plural = "назначения"
        ordering = ["-date_from"]
        default_related_name = "assignments"

    def __str__(self):
        return f"{self.department or ''} {self.position}".strip()


class LanguageSkill(PersonSection):
    language = models.ForeignKey(
        ref.Language, verbose_name="Язык", on_delete=models.PROTECT
    )
    level = models.CharField("Степень владения", max_length=100, blank=True)

    class Meta:
        verbose_name = "иностранный язык"
        verbose_name_plural = "иностранные языки"
        default_related_name = "languages"

    def __str__(self):
        return f"{self.language} ({self.level})" if self.level else str(self.language)


class PersonProfession(PersonSection):
    profession = models.ForeignKey(
        ref.Profession, verbose_name="Профессия", on_delete=models.PROTECT
    )
    worker_category = models.ForeignKey(
        ref.WorkerCategory,
        verbose_name="Категория работников",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )
    speciality = models.CharField("Специальность", max_length=255, blank=True)
    training_direction = models.CharField(
        "Направление подготовки", max_length=255, blank=True
    )
    date_from = models.DateField("С какого времени", null=True, blank=True)
    is_main = models.BooleanField("Основная", default=False)
    note = models.CharField("Примечание", max_length=500, blank=True)

    class Meta:
        verbose_name = "профессия"
        verbose_name_plural = "профессии"
        default_related_name = "professions"

    def __str__(self):
        return str(self.profession)


class Pass(PersonSection, PeriodModel):
    """Пропуск на предприятие."""

    number = models.CharField("Номер пропуска", max_length=30)
    office = models.CharField("Бюро пропусков", max_length=50, blank=True)

    class Meta:
        verbose_name = "пропуск"
        verbose_name_plural = "пропуска"
        ordering = ["-date_from"]
        default_related_name = "passes"

    def __str__(self):
        return self.number


class AdditionalAttribute(PersonSection, PeriodModel):
    """Дополнительный атрибут (например, участие в боевых действиях и где)."""

    attribute = models.ForeignKey(
        ref.AttributeType, verbose_name="Атрибут", on_delete=models.PROTECT
    )
    value = models.ForeignKey(
        ref.AttributeValue,
        verbose_name="Значение",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )
    note = models.CharField("Примечание", max_length=500, blank=True)

    class Meta:
        verbose_name = "доп. атрибут"
        verbose_name_plural = "доп. атрибуты"
        ordering = ["-date_from"]
        default_related_name = "attributes"

    def __str__(self):
        return f"{self.attribute}: {self.value}" if self.value else str(self.attribute)
