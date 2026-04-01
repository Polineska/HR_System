from __future__ import annotations

from django import forms


class BootstrapFormMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for _, field in self.fields.items():
            widget = field.widget
            existing = widget.attrs.get("class", "")

            if isinstance(widget, forms.Select):
                css = "form-select"
            elif isinstance(widget, (forms.FileInput, forms.ClearableFileInput)):
                css = "form-control"
            else:
                css = "form-control"

            widget.attrs["class"] = (existing + " " + css).strip()


class IndividualAnalysisForm(BootstrapFormMixin, forms.Form):
    gender = forms.ChoiceField(label="Пол", choices=[("Female", "Female"), ("Male", "Male")])
    company_type = forms.ChoiceField(
        label="Компания", choices=[("Service", "Service"), ("Product", "Product")]
    )
    wfh = forms.ChoiceField(label="Удаленка", choices=[("No", "No"), ("Yes", "Yes")])
    designation = forms.FloatField(
        label="Уровень должности (0-5)", min_value=0.0, max_value=5.0, initial=2.0
    )
    mental_fatigue = forms.FloatField(
        label="Ментальная усталость (0-10)", min_value=0.0, max_value=10.0, initial=5.0
    )
    resource_allocation = forms.FloatField(
        label="Распределение ресурсов (1-10)",
        min_value=1.0,
        max_value=10.0,
        initial=5.0,
        help_text="1 — недозагружен, 10 — перегружен.",
    )
    days_employed = forms.IntegerField(
        label="Стаж в компании (в днях)", min_value=1, max_value=5000, initial=500
    )

    education = forms.ChoiceField(
        label="Образование",
        choices=[("Bachelors", "Bachelors"), ("Masters", "Masters"), ("PHD", "PHD")],
    )
    city = forms.ChoiceField(
        label="Город",
        choices=[("Bangalore", "Bangalore"), ("Pune", "Pune"), ("New Delhi", "New Delhi")],
    )
    payment_tier = forms.ChoiceField(
        label="Уровень оплаты", choices=[(1, "1"), (2, "2"), (3, "3")], initial=2
    )
    age = forms.IntegerField(label="Возраст", min_value=18, max_value=65, initial=30)
    joining_year = forms.IntegerField(
        label="Год найма", min_value=2005, max_value=2026, initial=2017
    )
    experience_years = forms.IntegerField(
        label="Опыт в текущей сфере (лет)", min_value=0, max_value=10, initial=3
    )
    ever_benched = forms.ChoiceField(
        label="Был в резерве (Bench)", choices=[("No", "No"), ("Yes", "Yes")]
    )


class MassMonitoringForm(BootstrapFormMixin, forms.Form):
    # необязательно: если приложен файл, он будет сохранен как новый датасет и станет активным
    file = forms.FileField(label="CSV файл (опционально)", required=False)
    dataset_name = forms.CharField(
        label="Название датасета (опционально)",
        required=False,
        help_text="Если не указать, будет использовано имя файла.",
    )


class DatasetUploadForm(BootstrapFormMixin, forms.Form):
    kind = forms.ChoiceField(
        label="Тип датасета",
        choices=[
            ("leave", "Увольнения (Leave)"),
            ("burnout", "Выгорание (Burnout)"),
        ],
    )
    name = forms.CharField(label="Название", required=False)
    file = forms.FileField(label="CSV файл", required=True)
