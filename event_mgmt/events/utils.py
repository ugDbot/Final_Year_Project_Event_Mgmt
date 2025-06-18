from django.core.mail import send_mail
from django.conf import settings

def send_notification_email(subject, message, recipient_email):
    send_mail(
        subject,
        message,
        settings.EMAIL_HOST_USER,  # Sender's email
        [recipient_email],  # Recipient's email list
        fail_silently=False,
    )
