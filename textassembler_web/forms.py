from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit, Row, Column
import json

class TextAssemblerWebForm(forms.Form):

    def __init__(self, *args, **kwargs):
        super(TextAssemblerWebForm,self).__init__(*args,**kwargs)

        self.helper = FormHelper()
        self.helper.form_class = 'form-horizontal'
        self.helper.field_class = "col-lg-9"
        self.helper.label_class = "col-lg-3"
        self.helper.form_method = 'post'
        self.helper.form_show_labels = True
        self.helper.help_text_inline = True
        self.helper.add_input(Submit('submit', 'Search'))

    def set_form_action(self):
        '''
        Call the search function in views.py on form-submit
        '''
        self.helper.form_action = reverse("search")

    def set_fields(self, filter_data, search = ''):
        '''
        Add fields:
        * Search Term
        * Filters
        The individual filter fields will be added dynamically by the JS
        '''
        choices = [('','Select one or more filters...')]

        for opt in filter_data:
            choices.append((opt["id"],opt["name"]))

        self.fields['search'] = forms.CharField(
            label='Search Term / Query',
            error_messages={'required': 'Required field'},
            initial= search,
            widget=forms.Textarea(attrs={
                'class':'form-control',
                'placeholder':'Search term',
                'aria-label':'Search Term',
                'rows': 1})
        )
        self.fields['filter_opts'] = forms.ChoiceField(
            choices=choices,
            label="Filters / Options",
            required=False,
            widget=forms.Select(attrs={
                'class':'filter_opts form-control',
                'aria-label':'Filters'}),
        )


