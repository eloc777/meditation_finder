from django import forms

from .models import MeditationGroup, Session


BOOTSTRAP_FIELD_CLASS = {"class": "form-control"}
BOOTSTRAP_CHECK_CLASS = {"class": "form-check-input"}
BOOTSTRAP_SELECT_CLASS = {"class": "form-select"}


class MeditationGroupForm(forms.ModelForm):
    class Meta:
        model = MeditationGroup
        fields = ["name", "description", "style", "religion", "suburb", "postcode", "link", "cost_type"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.update({"class": "form-check-input"})
            elif isinstance(field.widget, forms.Select):
                field.widget.attrs.update({"class": "form-select"})
            else:
                field.widget.attrs.update({"class": "form-control"})


class SessionEditForm(forms.ModelForm):
    class Meta:
        model = Session
        fields = [
            "title",
            "description",
            "style",
            "is_recurring",
            "recurrence",
            "recurrence_pattern",
            "recurrence_note",
            "recurrence_end_date",
            "beginner_friendly",
            "scheduled_from",
            "scheduled_to",
            "suburb",
            "postcode",
            "meeting_link",
            "max_participants",
            "cost",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        widgets = {}
        types = getattr(self.Meta, "_field_types", None)
        for name in self.fields:
            field = self.fields[name]
            if isinstance(field.widget, forms.CheckboxInput):
                widgets[name] = BOOTSTRAP_CHECK_CLASS
            elif isinstance(field.widget, forms.Select):
                widgets[name] = BOOTSTRAP_SELECT_CLASS
            else:
                widgets[name] = BOOTSTRAP_FIELD_CLASS
                if name in {"scheduled_from", "scheduled_to"}:
                    widgets[name]["type"] = "datetime-local"
        for name, attrs in widgets.items():
            existing = getattr(self.fields[name].widget, "attrs", None) or {}
            merged = dict(existing)
            merged.update(attrs)
            self.fields[name].widget.attrs = merged
