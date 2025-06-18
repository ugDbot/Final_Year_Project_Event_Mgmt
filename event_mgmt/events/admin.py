from django.contrib import admin
from django.contrib.auth import get_user_model
from .models import Event, Ticket, Attendee

User = get_user_model()

admin.site.register(User)
admin.site.register(Event)
admin.site.register(Ticket)
admin.site.register(Attendee)
