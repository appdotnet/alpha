from django import forms

from paucore.data.fields import Choices

REPORT_POST_CHOICES = Choices(
    (0, 'UNKNOWN', 'Unknown'),
    (1, 'UNWANTED_MENTION', 'Unwanted mention'),
    (2, 'EXCESSIVE_POSTING', 'Excessive posting'),
    (3, 'EXPLICIT_MATERIAL', 'Explicit/offensive material'),
    (4, 'MARKETING_SPAM', 'Marketing spam'),
    (5, 'THREATS', 'Threats'),
)

REPORT_STATUS = Choices(
    (0, 'UNREVIEWED', 'Unreviewed'),
    (1, 'RESOLVED', 'Resolved'),
    (2, 'ESCALATE', 'Escalated'),
)

AVAILABLE_REPORT_POST_CHOICES = [(REPORT_POST_CHOICES.to_enum_dict[key].lower(), REPORT_POST_CHOICES.str_dict[key]) for key in REPORT_POST_CHOICES.key_list if key != REPORT_POST_CHOICES.UNKNOWN]


class ReportPostForm(forms.Form):
    report_post_data = forms.ChoiceField(label='Reason for reporting post', choices=AVAILABLE_REPORT_POST_CHOICES, widget=forms.Select())
