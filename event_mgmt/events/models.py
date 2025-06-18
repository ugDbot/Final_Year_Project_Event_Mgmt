import uuid
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.urls import reverse

# Custom User Model
class User(AbstractUser):
    pass  # Extend this if needed

# Event Model
class Event(models.Model):
    id = models.UUIDField(default=uuid.uuid4, primary_key=True, editable=False)
    name = models.CharField(max_length=255)
    description = models.TextField()
    date = models.DateTimeField()
    location = models.CharField(max_length=255)
    creator = models.ForeignKey(User, on_delete=models.CASCADE)
    is_ticketed = models.BooleanField(default=False)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    def get_absolute_url(self):
        return reverse("event_detail", args=[str(self.id)])

    def attendee_count(self):
        return Attendee.objects.filter(event=self).count()
# Ticket Model
class Ticket(models.Model):
    id = models.UUIDField(default=uuid.uuid4, primary_key=True, editable=False)
    event = models.ForeignKey(Event, on_delete=models.CASCADE)
    buyer = models.ForeignKey(User, on_delete=models.CASCADE)
    purchased_at = models.DateTimeField(auto_now_add=True)
    paystack_reference = models.CharField(max_length=100, blank=True, null=True)

# Attendee Model
class Attendee(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("event", "user")
    def __str__(self):
        return f'{self.user.username} attending {self.event.name}'