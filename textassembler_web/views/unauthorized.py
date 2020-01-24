from django.shortcuts import render

def unauthorized(request):

    return render(request, "textassembler_web/unauthorized.html")
