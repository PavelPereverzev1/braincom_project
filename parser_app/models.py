from django.db import models


class Product(models.Model):
    title = models.CharField(
        max_length=512,
        null=True,
        blank=True,
        verbose_name="Повна назва товару",
    )

    price_regular = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Ціна звичайна",
    )
    price_promo = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Ціна акційна",
    )

    code = models.CharField(
        max_length=100,
        unique=True,
        null=True,
        blank=True,
        db_index=True,
        verbose_name="Код товару",
    )

    vendor = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name="Виробник",
    )
    color = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name="Колір",
    )
    memory = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name="Об'єм пам'яті",
    )
    screen_diagonal = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        verbose_name="Діагональ екрану",
    )
    screen_resolution = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name="Роздільна здатність дисплея",
    )
    reviews_count = models.IntegerField(
        default=0,
        verbose_name="Кількість відгуків",
    )

    photos = models.JSONField(
        default=list,
        blank=True,
        verbose_name="Список посилань на фото",
    )
    characteristics = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Всі характеристики",
    )

    status = models.CharField(
        max_length=50,
        default="New",
        null=True,
        blank=True,
        verbose_name="Статус парсингу",
    )
    parser_type = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        verbose_name="Тип парсера (BS4/Selenium/Playwright)",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Дата створення",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Дата оновлення",
    )

    class Meta:
        verbose_name = "Товар"
        verbose_name_plural = "Товари"

    def __str__(self):
        return f"{self.title or 'Без назви'} [{self.code or 'Без коду'}]"