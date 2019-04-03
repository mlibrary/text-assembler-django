from django import forms

class TextAssemblerWebForm(forms.Form):
    search = forms.CharField(initial='dog')
